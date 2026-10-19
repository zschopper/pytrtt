"""Read-only unkeyed UTF-8 locals with input key IDs and 64-bit text pointers.

Layout evidence: TrRebootModTools a79c48b75f1ffaaf623dc73a625211bf98ff0504,
Shared/Cdc/Rise/RiseLocalsBin.cs and Tr2013/Tr2013LocalsBin.cs.
Independently implemented; input key IDs are not text slots.
"""

from __future__ import annotations

import struct

from pytrtt.formats.contracts import TextOptions
from pytrtt.formats.reboot_text import _menu_placeholders
from pytrtt.packages.translation import TranslationEntry


class LocalsV3Handler:
    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        if len(data) < 12:
            raise ValueError("locals header is truncated")
        _, input_count, count = struct.unpack_from("<3I", data)
        start = 12 + 4 * input_count
        table_end = start + 8 * count
        if table_end > len(data):
            raise ValueError("locals pointer table exceeds bounds")
        entries = []
        for index, (offset,) in enumerate(struct.iter_unpack("<Q", data[start:table_end])):
            if offset == 0:
                continue
            if not table_end <= offset < len(data):
                raise ValueError("locals text pointer exceeds bounds")
            end = data.find(b"\0", offset)
            if end < 0:
                raise ValueError("locals text lacks terminator")
            source = _menu_placeholders(data[offset:end].decode("utf-8"))[0]
            entries.append(TranslationEntry(index, source, None))
        return tuple(entries)

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        raise ValueError("64-bit unkeyed locals handler is read-only")
