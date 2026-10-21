"""Read named UTF-8 locals records through a 64-bit pointer table.

Layout evidence: TrRebootModTools a79c48b75f1ffaaf623dc73a625211bf98ff0504,
Shared/Cdc/Shadow/ShadowLocalsBin.cs. Original bytes, placeholder slots and aliases are retained.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from pytrtt.formats.contracts import TextOptions
from pytrtt.packages.translation import TranslationEntry


class KeyedLocalsError(ValueError):
    """Malformed named-text table."""


@dataclass(frozen=True, slots=True)
class KeyedEntry:
    index: int
    offset: int
    key: str | None
    text: str | None


@dataclass(frozen=True, slots=True)
class KeyedLocals:
    language_id: int
    entries: tuple[KeyedEntry, ...]
    original_data: bytes


def parse_keyed_locals(data: bytes) -> KeyedLocals:
    if len(data) < 8:
        raise KeyedLocalsError("locals resource is shorter than its header")
    language_id, count = struct.unpack_from("<2I", data)
    table_end = 8 + 8 * count
    if table_end > len(data):
        raise KeyedLocalsError("locals pointer table exceeds resource bounds")
    offsets = struct.unpack_from(f"<{count}Q", data, 8) if count else ()
    records: dict[int, tuple[str, str]] = {}
    for offset in set(offsets) - {0}:
        if not table_end <= offset < len(data):
            raise KeyedLocalsError("locals pointer is outside the text block")
        end = data.find(b"\0", offset)
        if end < 0:
            raise KeyedLocalsError("locals text is not null-terminated")
        raw_key, separator, raw_text = data[offset:end].partition(b" ")
        if not separator or not raw_key:
            raise KeyedLocalsError("locals record has no key separator")
        try:
            records[offset] = (raw_key.decode("utf-8"), raw_text.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise KeyedLocalsError("locals record is not valid UTF-8") from exc
    entries = tuple(
        KeyedEntry(index, offset, *records[offset]) if offset else KeyedEntry(index, 0, None, None)
        for index, offset in enumerate(offsets)
    )
    return KeyedLocals(language_id, entries, data)


class KeyedLocalsHandler:
    """Extract and rebuild Shadow's keyed UTF-8 locals table."""

    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        del subtitle_language
        parsed = parse_keyed_locals(data)
        return tuple(
            TranslationEntry(entry.index, entry.text or "", None, key=entry.key)
            for entry in parsed.entries
        )

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        parsed = parse_keyed_locals(data)
        by_id = {entry.entry_id: entry for entry in entries}
        if len(by_id) != len(entries):
            raise KeyedLocalsError("duplicate keyed locals entry id")
        if any(entry_id < 0 or entry_id >= len(parsed.entries) for entry_id in by_id):
            raise KeyedLocalsError("keyed locals entry id is outside the table")
        groups: dict[int, list[KeyedEntry]] = {}
        for original in parsed.entries:
            if original.offset:
                groups.setdefault(original.offset, []).append(original)
        selected: dict[int, str] = {}
        for offset, aliases in groups.items():
            translations = set()
            for original in aliases:
                replacement = by_id.get(original.index)
                if replacement is None:
                    continue
                desired = options.text(replacement) if replacement.translation is not None else None
                if original.text != replacement.source and original.text != desired:
                    raise KeyedLocalsError("keyed locals source text changed")
                if replacement.key is not None and replacement.key != original.key:
                    raise KeyedLocalsError("keyed locals key changed")
                if desired is not None:
                    translations.add(desired)
            if len(translations) > 1:
                raise KeyedLocalsError("keyed locals alias translations conflict")
            selected[offset] = next(iter(translations), aliases[0].text or "")
        table_end = 8 + 8 * len(parsed.entries)
        result = bytearray(
            struct.pack("<2I", parsed.language_id, len(parsed.entries))
            + bytes(8 * len(parsed.entries))
        )
        new_offsets: dict[int, int] = {}
        for old_offset, aliases in groups.items():
            key = aliases[0].key
            if key is None:
                raise KeyedLocalsError("keyed locals record is missing its key")
            new_offsets[old_offset] = len(result)
            try:
                result.extend(f"{key} {selected[old_offset]}".encode() + b"\0")
            except UnicodeEncodeError as exc:
                raise KeyedLocalsError("keyed locals text is not valid UTF-8") from exc
        for entry in parsed.entries:
            struct.pack_into("<Q", result, 8 + 8 * entry.index, new_offsets.get(entry.offset, 0))
        if len(result) < table_end:
            raise AssertionError("keyed locals table rebuild failed")
        return bytes(result)
