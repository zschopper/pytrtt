"""Reader and writer for the tested indexed locals.bin layout."""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass

UINT32_MASK = 0xFFFFFFFF
HEADER_SIZE = 12


class MenuFormatError(ValueError):
    """Raised when an indexed menu resource is structurally invalid."""


@dataclass(frozen=True, slots=True)
class MenuEntry:
    """One indexed text entry; ``None`` marks a preserved placeholder."""

    index: int
    offset: int
    text: str | None


@dataclass(frozen=True, slots=True)
class MenuResource:
    """Parsed indexed menu resource with its original bytes for exact no-op output."""

    language_code: int
    entry_count_fields: tuple[int, int]
    entries: tuple[MenuEntry, ...]
    original_data: bytes


def parse_locals(data: bytes) -> MenuResource:
    """Parse the three-field header, offset table, and UTF-8 null-terminated strings."""
    if len(data) < HEADER_SIZE:
        raise MenuFormatError("resource is shorter than its 12-byte header")

    language_code, count_a, count_b = struct.unpack_from("<III", data)
    count = (count_a + ((count_b - 1) & UINT32_MASK)) & UINT32_MASK
    table_end = HEADER_SIZE + count * 4
    text_start = (count + 3) * 4
    if table_end > len(data) or text_start > len(data):
        raise MenuFormatError("entry count exceeds the available offset table")

    offsets = struct.unpack_from(f"<{count}I", data, HEADER_SIZE) if count else ()
    active_offsets = [offset for offset in offsets if offset > count * 4]
    if any(offset < text_start or offset >= len(data) for offset in active_offsets):
        raise MenuFormatError("text offset is outside the text block")
    if any(left > right for left, right in zip(active_offsets, active_offsets[1:], strict=False)):
        raise MenuFormatError("text offsets are not in entry order")

    unique_offsets = sorted(set(active_offsets))
    text_by_offset: dict[int, str] = {}
    for position, offset in enumerate(unique_offsets):
        next_offset = unique_offsets[position + 1] if position + 1 < len(unique_offsets) else None
        if next_offset is None:
            if data[-1] != 0:
                raise MenuFormatError("last text entry is not null-terminated")
            raw_text = data[offset:-1]
        else:
            terminator = next_offset - 1
            if terminator < offset or data[terminator] != 0:
                raise MenuFormatError("text entry is not null-terminated before the next offset")
            raw_text = data[offset:terminator]
        if b"\0" in raw_text:
            raise MenuFormatError("text entry contains an embedded null byte")
        try:
            text_by_offset[offset] = raw_text.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MenuFormatError(f"text entry at offset {offset} is not valid UTF-8") from exc

    entries = tuple(
        MenuEntry(
            index=index,
            offset=offset,
            text=None if offset <= count * 4 else text_by_offset[offset],
        )
        for index, offset in enumerate(offsets)
    )
    return MenuResource(
        language_code=language_code,
        entry_count_fields=(count_a, count_b),
        entries=entries,
        original_data=data,
    )


def write_locals(
    resource: MenuResource,
    translations: Mapping[int, str] | None = None,
) -> bytes:
    """Rebuild a menu resource, retaining exact bytes when no text value changes."""
    replacements = translations or {}
    for index, text in replacements.items():
        if not 0 <= index < len(resource.entries):
            raise MenuFormatError(f"translation index {index} is outside the resource")
        if resource.entries[index].text is None:
            raise MenuFormatError(f"translation index {index} refers to a placeholder")
        if "\0" in text:
            raise MenuFormatError(f"translation at index {index} contains a null character")

    changed = any(resource.entries[index].text != text for index, text in replacements.items())
    if not changed:
        return resource.original_data

    count = len(resource.entries)
    text_start = (count + 3) * 4
    offsets: list[int] = []
    text_block = bytearray()
    for entry in resource.entries:
        if entry.text is None:
            offsets.append(entry.offset)
            continue
        text = replacements.get(entry.index, entry.text)
        output_offset = text_start + len(text_block)
        offsets.append(output_offset)
        text_block.extend(text.encode("utf-8"))
        text_block.append(0)

    count_a, count_b = resource.entry_count_fields
    header = struct.pack("<III", resource.language_code, count_a, count_b)
    table = struct.pack(f"<{count}I", *offsets) if count else b""
    return header + table + bytes(text_block)
