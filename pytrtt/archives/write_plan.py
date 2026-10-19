"""Non-mutating write planning for the indexed Bigfile v1 pilot."""

from __future__ import annotations

import hashlib
import re
import shutil
import struct
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath, PureWindowsPath

from pytrtt.archives.bigfile_v1 import BLOCK_SIZE, BigFileEntry, BigFileIndex
from pytrtt.archives.contracts import PlannedFile, PlannedWrite, ResourceReplacement

PART_NAME = re.compile(r"bigfile\.([0-9]{3})\Z")
UINT32_MAX = 0xFFFFFFFF


class BigFilePlanError(ValueError):
    """Raised when a safe Bigfile replacement plan cannot be made."""


BigFileReplacement = ResourceReplacement


@dataclass(frozen=True, slots=True)
class BigFileWritePlan:
    """Dry-run result with updated index model and conservative space estimates."""

    index: BigFileIndex
    writes: tuple[PlannedWrite, ...]
    files: dict[str, PlannedFile]
    backup_bytes: int
    staging_bytes: int
    additional_bytes_required: int
    free_bytes: int

    @property
    def sufficient_space(self) -> bool:
        """Whether the conservative transaction peak fits on the data volume."""
        return self.additional_bytes_required <= self.free_bytes

    @property
    def index_data(self) -> dict[str, bytes]:
        return {"bigfile.000": serialize_bigfile_index(self.index)}

    def validate_inputs(self, _directory: Path) -> None:
        """Bigfile v1 inputs are fully covered by the per-file plan hashes."""


def _align(value: int) -> int:
    return (value + BLOCK_SIZE - 1) // BLOCK_SIZE * BLOCK_SIZE


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _read_original_range(path: Path, offset: int, length: int) -> bytes:
    if not path.is_file() or offset >= path.stat().st_size:
        return b""
    with path.open("rb") as stream:
        stream.seek(offset)
        return stream.read(min(length, path.stat().st_size - offset))


def serialize_bigfile_index(index: BigFileIndex) -> bytes:
    """Serialize count, hashes, and 16-byte records without changing row order."""
    if len(index.entries) > UINT32_MAX:
        raise BigFilePlanError("too many Bigfile index entries")
    for position, entry in enumerate(index.entries):
        if entry.index != position:
            raise BigFilePlanError("Bigfile index row ids must be contiguous and ordered")
        fields = (entry.hash, entry.length, entry.location, entry.locale, entry.unknown)
        if any(not 0 <= value <= UINT32_MAX for value in fields):
            raise BigFilePlanError("Bigfile index field is outside the unsigned 32-bit range")

    hashes = b"".join(struct.pack("<I", entry.hash) for entry in index.entries)
    records = b"".join(
        struct.pack("<4I", entry.length, entry.location, entry.locale, entry.unknown)
        for entry in index.entries
    )
    return struct.pack("<I", len(index.entries)) + hashes + records


def _archive_parts(data_dir: Path) -> dict[int, Path]:
    parts: dict[int, Path] = {}
    try:
        children = tuple(data_dir.iterdir())
    except OSError as exc:
        raise BigFilePlanError(f"cannot inspect Bigfile directory: {exc}") from exc

    for path in children:
        if not path.name.startswith("bigfile."):
            continue
        match = PART_NAME.fullmatch(path.name)
        if match is None:
            raise BigFilePlanError(f"unexpected Bigfile part name: {path.name}")
        part = int(match.group(1))
        if part in parts:
            raise BigFilePlanError(f"duplicate Bigfile part number: {part}")
        if path.is_symlink() or not path.is_file():
            raise BigFilePlanError(f"Bigfile part is not a regular file: {path.name}")
        parts[part] = path

    if not parts or 0 not in parts:
        raise BigFilePlanError("bigfile.000 is missing")
    expected = set(range(max(parts) + 1))
    if parts.keys() != expected:
        raise BigFilePlanError("Bigfile part numbers are not contiguous from bigfile.000")
    return parts


def plan_replacements(
    data_dir: Path,
    index: BigFileIndex,
    replacements: tuple[BigFileReplacement, ...],
    boundary: int,
) -> BigFileWritePlan:
    """Plan in-place writes or aligned appends without creating or modifying files.

    A replacement uses its existing FAT block allocation when it fits before the next indexed
    resource. Otherwise the bytes are appended to the last part, or to a new part if that part
    is full. The caller remains responsible for executing the returned plan transactionally.
    """
    if boundary <= 0 or boundary % BLOCK_SIZE:
        raise BigFilePlanError("part boundary must be a positive multiple of 2048 bytes")
    if not replacements:
        raise BigFilePlanError("at least one resource replacement is required")
    parts = _archive_parts(data_dir)
    sizes = {part: path.stat().st_size for part, path in parts.items()}
    if any(size > boundary for size in sizes.values()):
        raise BigFilePlanError("an archive part exceeds the configured part boundary")

    index_region_size = 4 + len(index.entries) * 20
    rows_by_key: dict[tuple[int, int], list[BigFileEntry]] = {}
    ranges_by_part: dict[int, list[tuple[int, int, BigFileEntry]]] = {}
    for entry in index.entries:
        part, offset = entry.part_and_offset(boundary)
        if part not in parts:
            raise BigFilePlanError(f"index row {entry.index} refers to missing part {part:03d}")
        if offset + entry.length > sizes[part]:
            raise BigFilePlanError(f"index row {entry.index} extends beyond bigfile.{part:03d}")
        if part == 0 and offset < index_region_size and offset + entry.length > 0:
            raise BigFilePlanError(f"index row {entry.index} overlaps the Bigfile index table")
        rows_by_key.setdefault((entry.hash, entry.locale), []).append(entry)
        ranges_by_part.setdefault(part, []).append((offset, offset + entry.length, entry))

    changed_entries = list(index.entries)
    planned_writes: list[PlannedWrite] = []
    append_part = max(parts)
    append_offset = _align(sizes[append_part])
    replacement_keys: set[tuple[int, int]] = set()

    for replacement in replacements:
        key = replacement.name_hash, replacement.locale
        if key in replacement_keys:
            raise BigFilePlanError(
                "duplicate replacement for hash "
                f"{replacement.name_hash:08X} and locale {replacement.locale:08X}"
            )
        replacement_keys.add(key)
        if not replacement.data:
            raise BigFilePlanError(f"replacement {replacement.label!r} has no data")
        if replacement.restore_file is not None:
            restore_path = PurePosixPath(replacement.restore_file)
            windows_restore_path = PureWindowsPath(replacement.restore_file)
            if (
                not replacement.restore_file.endswith(".raw")
                or "\\" in replacement.restore_file
                or restore_path.is_absolute()
                or windows_restore_path.drive
                or ".." in restore_path.parts
            ):
                raise BigFilePlanError("restore_file must be a safe relative .raw path")
        matches = rows_by_key.get(key, [])
        if len(matches) != 1:
            raise BigFilePlanError(
                f"expected one index row for hash {replacement.name_hash:08X} "
                f"and locale {replacement.locale:08X}; found {len(matches)}"
            )

        entry = matches[0]
        current_part, current_offset = entry.part_and_offset(boundary)
        source_path = data_dir / f"bigfile.{current_part:03d}"
        resource_original = _read_original_range(source_path, current_offset, entry.length)
        if len(resource_original) != entry.length:
            raise BigFilePlanError(f"original resource {replacement.label!r} is truncated")
        sorted_ranges = sorted(
            ranges_by_part[current_part], key=lambda item: (item[0], item[2].index)
        )
        other_starts = [
            start
            for start, _, other in sorted_ranges
            if other.index != entry.index and start >= current_offset
        ]
        next_start = min(other_starts, default=boundary)
        has_previous_overlap = any(
            other.index != entry.index and start < current_offset < end
            for start, end, other in sorted_ranges
        )
        gap_to_next = max(0, next_start - current_offset)
        old_allocation = _align(entry.length)
        available = 0 if has_previous_overlap else min(gap_to_next, old_allocation)

        replacement_allocation = _align(len(replacement.data))
        if replacement_allocation <= available:
            destination_part = current_part
            destination_offset = current_offset
            action_data = replacement.data
        else:
            if append_offset + len(replacement.data) > boundary:
                append_part += 1
                if append_part > 999:
                    raise BigFilePlanError(
                        "Bigfile part number exceeds the three-digit filename range"
                    )
                if append_part in parts:
                    raise BigFilePlanError(
                        f"new Bigfile part already exists: bigfile.{append_part:03d}"
                    )
                parts[append_part] = data_dir / f"bigfile.{append_part:03d}"
                sizes[append_part] = 0
                append_offset = 0
            destination_part = append_part
            destination_offset = append_offset
            final_end = destination_offset + len(replacement.data)
            action_end = _align(final_end)
            action_data = replacement.data + bytes(action_end - final_end)
            append_offset = action_end

        location_value = (destination_part * boundary + destination_offset) // BLOCK_SIZE
        if location_value > UINT32_MAX:
            raise BigFilePlanError("replacement location exceeds the Bigfile index range")
        changed_entries[entry.index] = replace(
            entry,
            length=len(replacement.data),
            location=location_value,
        )
        planned_writes.append(
            PlannedWrite(
                file_name=f"bigfile.{destination_part:03d}",
                kind="resource",
                label=replacement.label,
                offset=destination_offset,
                data=action_data,
                original_data=_read_original_range(
                    data_dir / f"bigfile.{destination_part:03d}",
                    destination_offset,
                    len(action_data),
                ),
                resource_original_file_name=f"bigfile.{current_part:03d}",
                resource_original_offset=current_offset,
                resource_original=resource_original if replacement.restore_file else None,
                restore_file=replacement.restore_file,
            )
        )

    updated_index = BigFileIndex(tuple(changed_entries))
    index_data = serialize_bigfile_index(updated_index)
    if len(index_data) > sizes[0]:
        raise BigFilePlanError("updated index does not fit in bigfile.000")
    planned_writes.append(
        PlannedWrite(
            file_name="bigfile.000",
            kind="index",
            label="Bigfile index table",
            offset=0,
            data=index_data,
            original_data=_read_original_range(data_dir / "bigfile.000", 0, len(index_data)),
        )
    )

    file_names = {write.file_name for write in planned_writes}
    file_plans: dict[str, PlannedFile] = {}
    for file_name in sorted(file_names):
        part = int(file_name[-3:])
        original_size = sizes.get(part, 0)
        final_size = max(
            original_size,
            max(
                write.offset + len(write.data)
                for write in planned_writes
                if write.file_name == file_name
            ),
        )
        original_path = data_dir / file_name
        original_sha256 = _sha256(original_path) if original_path.exists() else None
        file_plans[file_name] = PlannedFile(original_size, final_size, original_sha256)

    backup_bytes = 0
    for write in planned_writes:
        if write.restore_file is None:
            backup_bytes += len(write.original_data)
        else:
            backup_bytes += len(write.resource_original or b"")
            if (
                write.resource_original_file_name != write.file_name
                or write.resource_original_offset != write.offset
            ):
                backup_bytes += len(write.original_data)
            else:
                backup_bytes += max(
                    0, len(write.original_data) - len(write.resource_original or b"")
                )
    staging_bytes = sum(file.final_size for file in file_plans.values())
    return BigFileWritePlan(
        index=updated_index,
        writes=tuple(planned_writes),
        files=file_plans,
        backup_bytes=backup_bytes,
        staging_bytes=staging_bytes,
        # Include backups, staged files, and temporary target copies used for atomic replacement.
        additional_bytes_required=backup_bytes + staging_bytes * 2,
        free_bytes=shutil.disk_usage(data_dir).free,
    )
