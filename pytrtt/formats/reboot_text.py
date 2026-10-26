"""Indexed UTF-8 menus, 8192-byte CINE streams, and Version 1 SCH records.

Layout evidence: supplied TRTR MenuFile.cs, CineFile.cs, CineConsts.cs, MovieFile.cs.
Independent implementation; preserves opaque bytes and rejects unsafe structure changes.
IDs identify table slots, block/occurrence pairs, or SCH segment occurrences, never TMX IDs.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass

from pytrtt.formats.contracts import TextOptions
from pytrtt.packages.translation import TranslationEntry


def _prefix(text: str) -> tuple[str, str]:
    match = re.fullmatch(r"(\[[0-9a-z.]+\])?(.*)", text, re.I | re.S)
    if match is None:
        raise ValueError("invalid subtitle prefix")
    return match[1] or "", match[2]


def _changes(entries: tuple[TranslationEntry, ...]) -> dict[int, TranslationEntry]:
    changes = {e.entry_id: e for e in entries if e.translation is not None}
    if len({e.entry_id for e in entries}) != len(entries):
        raise ValueError("duplicate record identity")
    return changes


def _menu_placeholders(text: str) -> tuple[str, tuple[str, ...]]:
    chars = tuple(c for c in text if 0xE000 <= ord(c) <= 0xF8FF)
    result = []
    number = 0
    for char in text:
        if 0xE000 <= ord(char) <= 0xF8FF:
            result.append(f"{{{number}}}")
            number += 1
        else:
            result.append(char)
    return "".join(result), chars


class LocalsV2Handler:
    @staticmethod
    def _records(data: bytes) -> tuple[tuple[int, str], ...]:
        if len(data) < 12:
            raise ValueError("menu header is truncated")
        _, count_a, count_b = struct.unpack_from("<3I", data)
        count = count_a + count_b
        table_end = 12 + count * 4
        if table_end > len(data):
            raise ValueError("menu table exceeds bounds")
        records = []
        for number, (offset,) in enumerate(struct.iter_unpack("<I", data[12:table_end])):
            if offset <= count * 4 or offset == 0xFFFFFFFF:
                continue
            if not table_end <= offset < len(data):
                raise ValueError("menu text pointer exceeds bounds")
            end = data.find(b"\0", offset)
            if end < 0:
                raise ValueError("menu string lacks terminator")
            records.append((number, data[offset:end].decode("utf-8")))
        return tuple(records)

    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        return tuple(
            TranslationEntry(i, _menu_placeholders(text)[0], None)
            for i, text in self._records(data)
        )

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        records = dict(self._records(data))
        changes = _changes(entries)
        if changes.keys() - records.keys():
            raise ValueError("menu translation has no record")
        result = bytearray(data)
        for number, entry in changes.items():
            text = options.text(entry).replace("\r\n", "\n")
            _, chars = _menu_placeholders(records[number])
            for index, char in enumerate(chars):
                token = f"{{{index}}}"
                if text.count(token) != 1:
                    raise ValueError("menu translation changed control placeholders")
                text = text.replace(token, char)
            if "\0" in text:
                raise ValueError("menu translation contains null delimiter")
            if text == records[number]:
                continue
            if len(result) > 0xFFFFFFFF:
                raise ValueError("menu offset overflow")
            struct.pack_into("<I", result, 12 + number * 4, len(result))
            result.extend(text.encode("utf-8") + b"\0")
        return bytes(result)


@dataclass(frozen=True, slots=True)
class _CineBlock:
    raw: bytes
    text_offset: int | None = None
    text_length: int = 0
    embedded: bool = False

    def pairs(self) -> tuple[tuple[int, str], ...]:
        if self.text_offset is None:
            return ()
        text = self.raw[self.text_offset : self.text_offset + self.text_length].decode("utf-8")
        values = text.split("\r")
        if values[-1] != "" or len(values) % 2 != 1:
            raise ValueError("invalid CINE language/text delimiters")
        pairs = []
        for pos in range(0, len(values) - 1, 2):
            if not values[pos].isdigit() or not 0 <= int(values[pos]) <= 255:
                raise ValueError("invalid CINE language")
            pairs.append((int(values[pos]), values[pos + 1]))
        return tuple(pairs)


def _cine_blocks(data: bytes) -> tuple[_CineBlock, ...]:
    if len(data) < 8192:
        raise ValueError("CINE header is shorter than 8192 bytes")
    blocks = []
    offset = 8192
    while offset < len(data):
        if offset + 16 > len(data):
            raise ValueError("CINE block header exceeds bounds")
        kind, size = struct.unpack_from("<2I", data, offset)
        end = offset + ((size + 31) & ~15)
        if kind not in (0, 1, 3) or end > len(data):
            raise ValueError("CINE block type or size exceeds bounds")
        raw = data[offset:end]
        block = _CineBlock(raw)
        if kind == 1:
            if raw[16:20] == b"ENIC":
                if size >= 120 and struct.unpack_from("<I", raw, 24)[0] == 100:
                    length = struct.unpack_from("<I", raw, 132)[0]
                    if 136 + length > 16 + size:
                        raise ValueError("CINE embedded text exceeds bounds")
                    block = _CineBlock(raw, 136, length, True)
            else:
                # An opaque type-1 block may end in a length-prefixed CR-terminated text table.
                payload = raw[: 16 + size]
                last = len(payload.rstrip(b"\0"))
                if last > 20 and payload[last - 1 : last] == b"\r":
                    candidates = []
                    for pos in range(16, last - 3, 4):
                        length = struct.unpack_from("<I", payload, pos)[0]
                        if length and pos + 4 + length == last:
                            candidate = _CineBlock(raw, pos + 4, length)
                            try:
                                candidate.pairs()
                            except ValueError:
                                continue
                            candidates.append(candidate)
                    if len(candidates) > 1:
                        raise ValueError("ambiguous CINE text location")
                    if candidates:
                        block = candidates[0]
        block.pairs()
        blocks.append(block)
        offset = end
    return tuple(blocks)


def _cine_source(pairs: tuple[tuple[int, str], ...], text: str) -> tuple[str, str, str | None]:
    language = None
    if "speaking russian" in text.lower():
        russian = [t for lang, t in pairs if lang == 9]
        if len(russian) != 1:
            raise ValueError("Russian marker lacks an unambiguous Russian source")
        text = russian[0]
        language = "ru"
    prefix, source = _prefix(text)
    return prefix, source, language


class CineV2Handler:
    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        result = []
        for number, block in enumerate(_cine_blocks(data)):
            pairs = block.pairs()
            for occurrence, text in enumerate(t for lang, t in pairs if lang == subtitle_language):
                if occurrence >= 0x10000:
                    raise ValueError("too many CINE subtitle occurrences")
                prefix, source, language = _cine_source(pairs, text)
                result.append(
                    TranslationEntry(
                        number * 0x10000 + occurrence,
                        source,
                        None,
                        (prefix,) if prefix else None,
                        source_language=language,
                    )
                )
        return tuple(result)

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        if options.cleared_languages or options.omitted_languages:
            raise ValueError("CINE language clearing and omission are unverified for this format")
        changes = _changes(entries)
        known = {e.entry_id for e in self.extract(data, options.subtitle_language)}
        if changes.keys() - known:
            raise ValueError("CINE translation has no record in selected language")
        result = bytearray(data[:8192])
        for number, block in enumerate(_cine_blocks(data)):
            occurrence = 0
            changed = False
            parts = []
            pairs = block.pairs()
            for language, text in pairs:
                if language == options.subtitle_language:
                    entry = changes.get(number * 0x10000 + occurrence)
                    occurrence += 1
                    if entry is not None:
                        prefix, _, _ = _cine_source(pairs, text)
                        translation = options.text(entry).replace("\r\n", "\n")
                        if "\r" in translation or "\0" in translation:
                            raise ValueError("CINE translation contains a language delimiter")
                        replaced = prefix + translation.replace("\r\n", "\n")
                        changed |= replaced != text
                        text = replaced
                parts.append(f"{language}\r{text}\r")
            if not changed:
                result.extend(block.raw)
                continue
            assert block.text_offset is not None
            end = block.text_offset + block.text_length
            if any(block.raw[end:]):
                raise ValueError("CINE text has an unknown nonzero suffix")
            encoded = "".join(parts).encode("utf-8")
            rebuilt = bytearray(block.raw[: block.text_offset])
            struct.pack_into("<I", rebuilt, block.text_offset - 4, len(encoded))
            rebuilt.extend(encoded)
            rebuilt.extend(bytes((-len(rebuilt)) % 16))
            struct.pack_into("<I", rebuilt, 4, len(rebuilt) - 16)
            if block.embedded:
                struct.pack_into("<I", rebuilt, 124, (8 + len(encoded) + 15) & ~15)
            result.extend(rebuilt)
        return bytes(result)


_SCH_LANGUAGES = {0: "english", 1: "french"}
_SCH_SEGMENT = re.compile(r"^(\([ 0-9:.]+\))?(\[.*?\])?(.*)$", re.S)


class SchV1Handler:
    @staticmethod
    def _line_pattern(language: int) -> re.Pattern[str]:
        name = _SCH_LANGUAGES.get(language)
        if name is None:
            raise ValueError("unsupported SCH language slot")
        return re.compile(rf'^(lang_{name} [0-9\-: ]+ ")(.*)(" *)(\r?\n|)$')

    @staticmethod
    def _segments(text: str) -> list[str]:
        return text.split("\\")

    @staticmethod
    def _validate_translation(text: str) -> None:
        if any(c in text for c in "\\\r\n\0"):
            raise ValueError("SCH translation contains a structure delimiter")

    @staticmethod
    def _lines(data: bytes, language: int) -> list[str]:
        pattern = SchV1Handler._line_pattern(language)
        name = _SCH_LANGUAGES[language]
        lines = data.decode("utf-8").splitlines(keepends=True)
        if [line.rstrip("\r\n") for line in lines[:3]] != ["Version 1", "TextEntry", "line0"]:
            raise ValueError("unsupported SCH header")
        for line in lines[3:]:
            if line.startswith(f"lang_{name}") and pattern.fullmatch(line) is None:
                raise ValueError(f"malformed SCH {name} row")
            if line.strip() and not re.fullmatch(r'lang_\w+ [0-9\-: ]+ ".*" *\r?\n?', line):
                raise ValueError("malformed SCH row")
        return lines

    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        result: list[TranslationEntry] = []
        pattern = self._line_pattern(subtitle_language)
        for line in self._lines(data, subtitle_language)[3:]:
            match = pattern.fullmatch(line)
            if match is None:
                continue
            for segment in self._segments(match[2]):
                parsed = _SCH_SEGMENT.fullmatch(segment)
                if parsed is None:
                    raise ValueError("malformed SCH segment")
                prefix = (parsed[1] or "") + (parsed[2] or "")
                result.append(
                    TranslationEntry(len(result), parsed[3], None, (prefix,) if prefix else None)
                )
        return tuple(result)

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        if options.cleared_languages or options.omitted_languages:
            raise ValueError("SCH language clearing and omission are unsupported")
        lines = self._lines(data, options.subtitle_language)
        pattern = self._line_pattern(options.subtitle_language)
        changes = _changes(entries)
        known = {e.entry_id for e in self.extract(data, options.subtitle_language)}
        if changes.keys() - known:
            raise ValueError("SCH translation has no segment")
        number = 0
        for pos, line in enumerate(lines):
            match = pattern.fullmatch(line)
            if match is None:
                continue
            parts = []
            for segment in self._segments(match[2]):
                parsed = _SCH_SEGMENT.fullmatch(segment)
                assert parsed is not None
                entry = changes.get(number)
                number += 1
                if entry is None:
                    parts.append(segment)
                    continue
                text = options.text(entry)
                self._validate_translation(text)
                parts.append((parsed[1] or "") + (parsed[2] or "") + text)
            lines[pos] = match[1] + "\\".join(parts) + match[3] + match[4]
        return "".join(lines).encode("utf-8")


class SchV2Handler(SchV1Handler):
    """SCH with inline backslash-n escapes distinct from timed segment starts."""

    @staticmethod
    def _segments(text: str) -> list[str]:
        return re.split(r"\\(?=\()", text)

    @staticmethod
    def _validate_translation(text: str) -> None:
        if any(c in text for c in "\r\n\0") or re.search(r"\\(?!n)", text):
            raise ValueError("SCH translation contains a structure delimiter")


class SchV3Handler:
    """SCH timed segments, preserving an optional Version 1 header line."""

    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        lines = data.splitlines()
        if lines[:2] == [b"TextEntry", b"line0"]:
            data = b"Version 1\n" + data
        return SchV2Handler().extract(data, subtitle_language)

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        if options.cleared_languages or options.omitted_languages:
            raise ValueError("SCH language clearing and omission are unsupported")
        original = {
            entry.entry_id: entry for entry in self.extract(data, options.subtitle_language)
        }
        changes = _changes(entries)
        if {entry.entry_id for entry in entries} - original.keys():
            raise ValueError("SCH translation has no segment")
        for index, entry in changes.items():
            if (
                entry.source != original[index].source
                and options.text(entry) != original[index].source
            ):
                raise ValueError("SCH source text changed")
        prefix = b"Version 1\n" if data.splitlines()[:2] == [b"TextEntry", b"line0"] else b""
        rebuilt = SchV2Handler().write(prefix + data, entries, options)
        assert rebuilt.startswith(prefix)
        rebuilt = rebuilt[len(prefix) :]
        result = self.extract(rebuilt, options.subtitle_language)
        if len(result) != len(original):
            raise ValueError("SCH translation changes segment structure")
        for actual in result:
            prior = original[actual.entry_id]
            replacement = changes.get(actual.entry_id)
            expected = options.text(replacement) if replacement is not None else prior.source
            if actual.source != expected or actual.comment != prior.comment:
                raise ValueError("SCH translation changes segment structure")
        return rebuilt
