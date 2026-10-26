"""Unkeyed UTF-8 locals with input key IDs and 64-bit text pointers.

Layout evidence: TrRebootModTools a79c48b75f1ffaaf623dc73a625211bf98ff0504,
Shared/Cdc/Rise/RiseLocalsBin.cs and Tr2013/Tr2013LocalsBin.cs.
Independently implemented; input key IDs are not text slots.
"""

from __future__ import annotations

import re
import struct
from collections import Counter

from pytrtt.formats.contracts import TextOptions
from pytrtt.formats.reboot_text import _changes, _menu_placeholders
from pytrtt.packages.translation import TranslationEntry


class LocalsV3Handler:
    @staticmethod
    def _records(data: bytes) -> tuple[int, dict[int, tuple[int, str]]]:
        if len(data) < 12:
            raise ValueError("locals header is truncated")
        _, input_count, count = struct.unpack_from("<3I", data)
        start = 12 + 4 * input_count
        table_end = start + 8 * count
        if table_end > len(data):
            raise ValueError("locals pointer table exceeds bounds")
        records = {}
        for index, (offset,) in enumerate(struct.iter_unpack("<Q", data[start:table_end])):
            if offset == 0:
                continue
            if not table_end <= offset < len(data):
                raise ValueError("locals text pointer exceeds bounds")
            end = data.find(b"\0", offset)
            if end < 0:
                raise ValueError("locals text lacks terminator")
            records[index] = offset, data[offset:end].decode("utf-8")
        return start, records

    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        _, records = self._records(data)
        return tuple(
            TranslationEntry(index, _menu_placeholders(text)[0], None)
            for index, (_, text) in records.items()
        )

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        if options.cleared_languages or options.omitted_languages:
            raise ValueError("locals language clearing and omission are unsupported")
        start, records = self._records(data)
        changes = _changes(entries)
        if {entry.entry_id for entry in entries} - records.keys():
            raise ValueError("locals translation has no text record")
        result = bytearray(data)
        appended: dict[tuple[int, str], int] = {}
        for index, entry in changes.items():
            offset, original = records[index]
            source, controls = _menu_placeholders(original)
            text = options.text(entry)
            if "\0" in text:
                raise ValueError("locals translation contains a null delimiter")
            if _menu_placeholders(text)[1]:
                raise ValueError(
                    f"locals entry {index}: translation contains raw control placeholders"
                )
            if Counter(re.findall(r"\{\d+\}", text)) != Counter(re.findall(r"\{\d+\}", source)):
                raise ValueError(f"locals entry {index}: translation changed control placeholders")
            for number, char in enumerate(controls):
                token = f"{{{number}}}"
                if text.count(token) != 1:
                    raise ValueError("locals translation has ambiguous control placeholders")
                text = text.replace(token, char)
            if entry.source != source and text != original:
                raise ValueError("locals source text changed")
            if text == original:
                continue
            key = offset, text
            if key not in appended:
                appended[key] = len(result)
                result.extend(text.encode("utf-8") + b"\0")
            struct.pack_into("<Q", result, start + index * 8, appended[key])
        return bytes(result)
