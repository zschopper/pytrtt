"""Read-only reader for the indexed Bigfile v1 layout used by the TRA pilot."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

BLOCK_SIZE = 0x800
INDEX_ENTRY_SIZE = 0x14
RECORD_SIZE = 0x10


class BigFileFormatError(ValueError):
    """Raised when a Bigfile index or referenced resource is invalid."""


@dataclass(frozen=True, slots=True)
class BigFileEntry:
    """One original index row, including fields whose meaning is not yet known."""

    index: int
    hash: int
    length: int
    location: int
    locale: int
    unknown: int

    def part_and_offset(self, boundary: int) -> tuple[int, int]:
        """Convert the 2048-byte-block location to an archive part and byte offset."""
        blocks_per_part = _blocks_per_part(boundary)
        part, block_offset = divmod(self.location, blocks_per_part)
        return part, block_offset * BLOCK_SIZE


@dataclass(frozen=True, slots=True)
class BigFileIndex:
    """Parsed hash table and corresponding 16-byte location records."""

    entries: tuple[BigFileEntry, ...]

    def find_hash(self, name_hash: int) -> tuple[BigFileEntry, ...]:
        """Return every record for a hash, preserving index order and language variants."""
        return tuple(entry for entry in self.entries if entry.hash == name_hash)


def _blocks_per_part(boundary: int) -> int:
    if boundary <= 0 or boundary % BLOCK_SIZE:
        raise BigFileFormatError("part boundary must be a positive multiple of 2048 bytes")
    return boundary // BLOCK_SIZE


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise BigFileFormatError("Bigfile index is truncated")
    return data


def read_bigfile_index(stream: BinaryIO, boundary: int) -> BigFileIndex:
    """Read only the count, hash table, and record table from ``bigfile.000``."""
    _blocks_per_part(boundary)
    if not stream.seekable():
        raise BigFileFormatError("Bigfile index stream must be seekable")

    stream.seek(0, 2)
    file_size = stream.tell()
    stream.seek(0)
    if file_size < 4:
        raise BigFileFormatError("Bigfile index is shorter than its entry count")

    count = struct.unpack("<I", _read_exact(stream, 4))[0]
    index_size = 4 + count * INDEX_ENTRY_SIZE
    if index_size > file_size:
        raise BigFileFormatError("entry count exceeds the available index tables")

    hashes = struct.unpack(f"<{count}I", _read_exact(stream, count * 4)) if count else ()
    records = _read_exact(stream, count * RECORD_SIZE)
    entries = tuple(
        BigFileEntry(
            index=index,
            hash=name_hash,
            length=struct.unpack_from("<I", records, index * RECORD_SIZE)[0],
            location=struct.unpack_from("<I", records, index * RECORD_SIZE + 4)[0],
            locale=struct.unpack_from("<I", records, index * RECORD_SIZE + 8)[0],
            unknown=struct.unpack_from("<I", records, index * RECORD_SIZE + 12)[0],
        )
        for index, name_hash in enumerate(hashes)
    )
    return BigFileIndex(entries)


def extract_resource(data_dir: Path, entry: BigFileEntry, boundary: int) -> bytes:
    """Read one indexed resource from its archive part without modifying game files."""
    part, offset = entry.part_and_offset(boundary)
    if entry.length > boundary - offset:
        raise BigFileFormatError("resource extends beyond its archive part")

    archive_path = data_dir / f"bigfile.{part:03d}"
    try:
        file_size = archive_path.stat().st_size
    except OSError as exc:
        raise BigFileFormatError(f"archive part is unavailable: {archive_path.name}") from exc
    if offset + entry.length > file_size:
        raise BigFileFormatError(f"resource extends beyond {archive_path.name}")

    try:
        with archive_path.open("rb") as stream:
            stream.seek(offset)
            return _read_exact(stream, entry.length)
    except OSError as exc:
        raise BigFileFormatError(f"cannot read archive part: {archive_path.name}") from exc
