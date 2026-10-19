"""Read named UTF-8 locals records through a 64-bit pointer table.

Layout evidence: TrRebootModTools a79c48b75f1ffaaf623dc73a625211bf98ff0504,
Shared/Cdc/Shadow/ShadowLocalsBin.cs. Original bytes, placeholder slots and aliases are retained.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


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
