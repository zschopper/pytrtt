"""Read-only TIGER v5 indexes and uncompressed archive resources.

Layout evidence: TrRebootModTools a79c48b75f1ffaaf623dc73a625211bf98ff0504,
Shared/Cdc/Archive.cs and Shared/Cdc/Shadow/ShadowArchive.cs (MIT).
This reader does not implement compression, writing, or archive-set override resolution.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

HEADER_SIZE = 56
ENTRY_SIZE = 32


class TigerFormatError(ValueError):
    """Unsupported or malformed TIGER data."""


@dataclass(frozen=True, slots=True)
class TigerEntry:
    name_hash: int
    locale: int
    size: int
    stored_size: int
    part: int
    archive_id: int
    sub_id: int
    offset: int


@dataclass(frozen=True, slots=True)
class TigerIndex:
    num_parts: int
    archive_id: int
    sub_id: int
    entries: tuple[TigerEntry, ...]
    header_data: bytes

    @property
    def platform(self) -> str:
        return self.header_data[24:56].split(b"\0", 1)[0].decode("ascii")


def read_tiger_index(stream: BinaryIO) -> TigerIndex:
    stream.seek(0, 2)
    length = stream.tell()
    stream.seek(0)
    header = stream.read(HEADER_SIZE)
    if len(header) != HEADER_SIZE or header[:4] != b"TAFS":
        raise TigerFormatError("invalid TIGER header")
    version, parts, count, archive_id, sub_id = struct.unpack_from("<5I", header, 4)
    if version != 5:
        raise TigerFormatError(f"unsupported TIGER version: {version}")
    if not 1 <= parts <= 0x8000 or archive_id > 255 or sub_id > 255:
        raise TigerFormatError("invalid TIGER part count or archive identity")
    if HEADER_SIZE + count * ENTRY_SIZE > length:
        raise TigerFormatError("TIGER entry table exceeds file bounds")
    records = stream.read(count * ENTRY_SIZE)
    if len(records) != count * ENTRY_SIZE:
        raise TigerFormatError("truncated TIGER entry table")
    entries = tuple(TigerEntry(*values) for values in struct.iter_unpack("<QQIIhBBI", records))
    if any(not 0 <= entry.part < parts for entry in entries):
        raise TigerFormatError("TIGER entry references an invalid part")
    return TigerIndex(parts, archive_id, sub_id, entries, header)


def read_tiger_resource(base_path: Path, index: TigerIndex, entry: TigerEntry) -> bytes:
    if not base_path.name.endswith(".000.tiger"):
        raise TigerFormatError("expected a base .000.tiger archive")
    if (entry.archive_id, entry.sub_id) != (index.archive_id, index.sub_id):
        raise TigerFormatError("cross-archive resource references are not supported")
    if not 0 <= entry.part < index.num_parts:
        raise TigerFormatError("invalid resource part")
    if entry.part == 0 and entry.offset < HEADER_SIZE + len(index.entries) * ENTRY_SIZE:
        raise TigerFormatError("resource overlaps the TIGER index")
    path = base_path.with_name(base_path.name[:-9] + f"{entry.part:03}.tiger")
    with path.open("rb") as stream:
        stream.seek(0, 2)
        length = stream.tell()
        if entry.offset < 0 or entry.size < 0 or entry.offset + entry.size > length:
            raise TigerFormatError("resource exceeds archive bounds")
        stream.seek(entry.offset)
        prefix = stream.read(min(entry.size, 4))
        if prefix == b"CDRM":
            raise TigerFormatError("compressed TIGER resource reading is not supported yet")
        data = prefix + stream.read(entry.size - len(prefix))
        if len(data) != entry.size:
            raise TigerFormatError("truncated TIGER resource")
        return data
