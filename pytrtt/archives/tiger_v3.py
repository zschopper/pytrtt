"""TAFS v3 resource indexes and conservative, journal-compatible write planning.

Layout evidence: supplied TRTR decompilation BigFile.cs and FATEntry.cs;
TRTR reference c12c237a7a6e044540b4096a2d9579defb55f99c, FATClassesV3.cs.
Independently implemented from layout observations; no historical code is copied.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import struct
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import BinaryIO

from pytrtt.archives.contracts import (
    ArchiveResource,
    ArchiveWritePlan,
    PlannedFile,
    PlannedWrite,
    ResourceReplacement,
)
from pytrtt.config import ArchiveSettings, RuntimeSettings, runtime_to_dict

HEADER_SIZE = 52
ENTRY_SIZE = 16
ALIGNMENT = 0x800
PART_NAME = re.compile(r"([A-Za-z0-9_-]+)\.([0-9]{3})\.tiger\Z")


@dataclass(frozen=True, slots=True)
class TigerV3Entry:
    name_hash: int
    locale: int
    size: int
    location: int

    @property
    def part(self) -> int:
        return self.location & 15

    @property
    def offset(self) -> int:
        return self.location & ~0x7FF


@dataclass(frozen=True, slots=True)
class TigerV3Index:
    num_parts: int
    priority: int
    entries: tuple[TigerV3Entry, ...]
    header_data: bytes

    def serialize(self) -> bytes:
        header = bytearray(self.header_data)
        struct.pack_into("<I", header, 8, self.num_parts)
        return bytes(header) + b"".join(
            struct.pack("<4I", e.name_hash, e.locale, e.size, e.location) for e in self.entries
        )


def read_tiger_v3_index(stream: BinaryIO) -> TigerV3Index:
    stream.seek(0, 2)
    length = stream.tell()
    stream.seek(0)
    header = stream.read(HEADER_SIZE)
    if len(header) != HEADER_SIZE or header[:4] != b"TAFS":
        raise ValueError("invalid TIGER v3 header")
    version, parts, count, priority = struct.unpack_from("<4I", header, 4)
    if version != 3:
        raise ValueError(f"unsupported TIGER version: {version}")
    if not 1 <= parts <= 16 or priority > 127:
        raise ValueError("invalid TIGER part count or priority")
    if HEADER_SIZE + count * ENTRY_SIZE > length:
        raise ValueError("TIGER table exceeds file bounds")
    table = stream.read(count * ENTRY_SIZE)
    if len(table) != count * ENTRY_SIZE:
        raise ValueError("truncated TIGER table")
    entries = tuple(TigerV3Entry(*row) for row in struct.iter_unpack("<4I", table))
    for entry in entries:
        if entry.part >= parts or (entry.location >> 4) & 127 != priority:
            raise ValueError("invalid TIGER location identity or part")
        if entry.part == 0 and entry.size and entry.offset < HEADER_SIZE + count * ENTRY_SIZE:
            raise ValueError("TIGER resource overlaps index")
    return TigerV3Index(parts, priority, entries, header)


def _align(value: int) -> int:
    return (value + ALIGNMENT - 1) & ~(ALIGNMENT - 1)


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True, slots=True)
class TigerV3WritePlan:
    writes: tuple[PlannedWrite, ...]
    files: dict[str, PlannedFile]
    index_data: dict[str, bytes]
    backup_bytes: int
    additional_bytes_required: int
    free_bytes: int
    source_indexes: tuple[tuple[str, str], ...]
    discover_families: bool
    source_parts: tuple[tuple[str, int, str], ...]

    @property
    def sufficient_space(self) -> bool:
        return self.additional_bytes_required <= self.free_bytes

    def validate_inputs(self, directory: Path) -> None:
        if self.discover_families and {p.name for p in directory.glob("*.000.tiger")} != {
            name for name, _ in self.source_indexes
        }:
            raise ValueError("TIGER archive set changed after planning")
        for name, expected in self.source_indexes:
            path = directory / name
            if PART_NAME.fullmatch(name) is None or path.is_symlink() or not path.is_file():
                raise ValueError("missing or unsafe TIGER source index")
            with path.open("rb") as stream:
                data = read_tiger_v3_index(stream).serialize()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("TIGER source index changed after planning")
        for name, size, digest in self.source_parts:
            path = directory / name
            if PART_NAME.fullmatch(name) is None or path.is_symlink() or not path.is_file():
                raise ValueError("missing or unsafe TIGER source part")
            if path.stat().st_size != size or _digest(path) != digest:
                raise ValueError("TIGER source part changed after planning")


class TigerV3Handler:
    def __init__(self, directory: Path, settings: ArchiveSettings) -> None:
        self.directory = directory
        self.settings = settings
        self._loaded: dict[str, TigerV3Index] | None = None
        self._stamps: tuple[tuple[str, int, int], ...] = ()
        self._references: dict[tuple[int, int], tuple[str, int, TigerV3Entry]] = {}
        self._physical_references: dict[tuple[str, int, int], tuple[str, int, TigerV3Entry]] = {}

    def _fingerprint(self, paths: list[Path]) -> tuple[tuple[str, int, int], ...]:
        stamps = []
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise ValueError("missing or unsafe TIGER part")
            stat = path.stat()
            stamps.append((path.name, stat.st_size, stat.st_mtime_ns))
        return tuple(stamps)

    def _indexes(self) -> dict[str, TigerV3Index]:
        paths = sorted(self.directory.glob("*.000.tiger"))
        if self.settings.families:
            paths = [self.directory / f"{name}.000.tiger" for name in self.settings.families]
        if not paths:
            raise ValueError("no TIGER v3 archives")
        if self._loaded is not None:
            expected = [
                self.directory / f"{family}.{part:03}.tiger"
                for family, index in self._loaded.items()
                for part in range(index.num_parts)
            ]
            if {p.name for p in paths} != {f"{name}.000.tiger" for name in self._loaded} or (
                self._fingerprint(expected) != self._stamps
            ):
                raise ValueError("TIGER archive set changed during operation")
            return self._loaded
        indexes = {}
        for path in paths:
            match = PART_NAME.fullmatch(path.name)
            if match is None or path.is_symlink() or not path.is_file():
                raise ValueError("invalid TIGER archive path")
            family = match[1]
            with path.open("rb") as stream:
                index = read_tiger_v3_index(stream)
            sizes = []
            for part in range(index.num_parts):
                part_path = self.directory / f"{family}.{part:03}.tiger"
                if part_path.is_symlink() or not part_path.is_file():
                    raise ValueError("missing or unsafe TIGER part")
                sizes.append(part_path.stat().st_size)
            for entry in index.entries:
                if entry.offset + entry.size > sizes[entry.part]:
                    raise ValueError("TIGER resource exceeds part bounds")
            indexes[family] = index
        self._loaded = indexes
        self._physical_references = self._physical(indexes)
        self._references = {} if self.settings.include_overridden else self._effective(indexes)
        self._stamps = self._fingerprint(
            [
                self.directory / f"{family}.{part:03}.tiger"
                for family, index in indexes.items()
                for part in range(index.num_parts)
            ]
        )
        return indexes

    @staticmethod
    def _physical(
        indexes: dict[str, TigerV3Index],
    ) -> dict[tuple[str, int, int], tuple[str, int, TigerV3Entry]]:
        result = {}
        for family, index in indexes.items():
            for row, entry in enumerate(index.entries):
                key = family, entry.name_hash, entry.locale
                if key in result:
                    raise ValueError("duplicate TIGER hash and locale within archive")
                result[key] = family, row, entry
        return result

    @staticmethod
    def _effective(
        indexes: dict[str, TigerV3Index],
    ) -> dict[tuple[int, int], tuple[str, int, TigerV3Entry]]:
        result: dict[tuple[int, int], tuple[str, int, TigerV3Entry]] = {}
        for family, index in indexes.items():
            local_keys = set()
            for row, entry in enumerate(index.entries):
                key = entry.name_hash, entry.locale
                if key in local_keys:
                    raise ValueError("duplicate TIGER hash and locale within archive")
                local_keys.add(key)
                previous = result.get(key)
                if previous is not None:
                    old_priority = indexes[previous[0]].priority
                    if old_priority == index.priority:
                        raise ValueError("ambiguous TIGER hash and locale at equal priority")
                    if old_priority > index.priority:
                        continue
                result[key] = family, row, entry
        return result

    def resources(self) -> tuple[ArchiveResource, ...]:
        self._loaded = None
        self._indexes()
        if self.settings.include_overridden:
            return tuple(
                ArchiveResource(e.name_hash, e.locale, e.size, archive_family=family)
                for family, _, e in self._physical_references.values()
            )
        return tuple(
            ArchiveResource(e.name_hash, e.locale, e.size, archive_family=family)
            for family, _, e in self._references.values()
        )

    def read(self, resource: ArchiveResource) -> bytes:
        if self._loaded is None:
            self._indexes()
        reference = (
            self._physical_references.get(
                (resource.archive_family, resource.name_hash, resource.locale)
            )
            if resource.archive_family is not None
            else self._references.get((resource.name_hash, resource.locale))
        )
        if reference is None or reference[2].size != resource.size:
            raise ValueError("TIGER resource changed or missing")
        family, _, entry = reference
        names = {f"{family}.000.tiger", f"{family}.{entry.part:03}.tiger"}
        paths = [self.directory / name for name, _, _ in self._stamps if name in names]
        if self._fingerprint(paths) != tuple(s for s in self._stamps if s[0] in names):
            raise ValueError("TIGER archive changed during resource reading")
        with (self.directory / f"{family}.{entry.part:03}.tiger").open("rb") as stream:
            stream.seek(entry.offset)
            data = stream.read(entry.size)
        if len(data) != entry.size:
            raise ValueError("truncated TIGER resource")
        if data.startswith(b"CDRM"):
            raise ValueError("compressed TIGER resources are unsupported")
        return data

    def plan(
        self,
        replacements: tuple[ResourceReplacement, ...],
        *,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> TigerV3WritePlan:
        if any(r.embedded_type is not None for r in replacements):
            from pytrtt.archives.drm_v22 import plan_embedded

            return plan_embedded(self, replacements, progress=progress)
        boundary = self.settings.boundary
        if not 0 < boundary <= 0x100000000 or boundary % ALIGNMENT:
            raise ValueError("invalid TIGER part boundary")
        if not replacements:
            raise ValueError("no TIGER replacements")
        indexes = self._indexes()
        effective = (
            self._effective(indexes) if any(r.archive_family is None for r in replacements) else {}
        )
        physical = self._physical(indexes)
        writes = []
        seen = set()
        sizes: dict[str, int] = {}
        cursors: dict[str, tuple[int, int]] = {}
        updated = dict(indexes)
        source_parts = set()
        for replacement in replacements:
            reference = (
                physical.get(
                    (replacement.archive_family, replacement.name_hash, replacement.locale)
                )
                if replacement.archive_family is not None
                else effective.get((replacement.name_hash, replacement.locale))
            )
            if reference is None:
                raise ValueError("duplicate or missing TIGER replacement")
            family, row, entry = reference
            key = family, row
            if key in seen:
                raise ValueError("duplicate TIGER replacement for physical resource")
            seen.add(key)
            if replacement.restore_file is not None:
                raise ValueError("TIGER font recovery assets are not supported yet")
            if (
                not replacement.data
                or len(replacement.data) > 0xFFFFFFFF
                or (_align(len(replacement.data)) > boundary)
            ):
                raise ValueError("TIGER replacement exceeds part boundary or is empty")
            source_parts.add(f"{family}.{entry.part:03}.tiger")
            index = updated[family]
            for part in range(indexes[family].num_parts):
                name = f"{family}.{part:03}.tiger"
                sizes.setdefault(name, (self.directory / name).stat().st_size)
                if sizes[name] > boundary:
                    raise ValueError("existing TIGER part exceeds configured boundary")
            # Append all changes: never overwrite aliases, padding, or unknown allocations.
            part, offset = cursors.get(
                family,
                (index.num_parts - 1, _align(sizes[f"{family}.{index.num_parts - 1:03}.tiger"])),
            )
            if offset + _align(len(replacement.data)) > boundary:
                part += 1
                offset = 0
                if part >= 16:
                    raise ValueError("TIGER part index exhausted")
                name = f"{family}.{part:03}.tiger"
                if (self.directory / name).exists():
                    raise ValueError("new TIGER part already exists")
                sizes[name] = 0
            data = replacement.data + bytes(_align(len(replacement.data)) - len(replacement.data))
            name = f"{family}.{part:03}.tiger"
            writes.append(PlannedWrite(name, "resource", replacement.label, offset, data, b""))
            cursors[family] = part, offset + len(data)
            entries = list(index.entries)
            entries[row] = replace(
                entry, size=len(replacement.data), location=(offset | index.priority << 4 | part)
            )
            updated[family] = replace(
                index, num_parts=max(index.num_parts, part + 1), entries=tuple(entries)
            )
        index_data = {}
        for family in cursors:
            name = f"{family}.000.tiger"
            data = updated[family].serialize()
            original = indexes[family].serialize()
            writes.append(PlannedWrite(name, "index", "TIGER v3 index", 0, data, original))
            index_data[name] = data
        files = {}
        for name in {w.file_name for w in writes}:
            path = self.directory / name
            original_size = sizes[name]
            final_size = max(
                original_size, *(w.offset + len(w.data) for w in writes if w.file_name == name)
            )
            files[name] = PlannedFile(
                original_size, final_size, _digest(path) if path.exists() else None
            )
        backup_bytes = sum(len(w.original_data) for w in writes)
        required = backup_bytes + 2 * sum(f.final_size for f in files.values())
        dependencies = tuple(
            (name, (self.directory / name).stat().st_size, _digest(self.directory / name))
            for name in sorted(source_parts - files.keys())
        )
        self._indexes()  # Reject source changes while collecting fingerprints.
        return TigerV3WritePlan(
            tuple(writes),
            files,
            index_data,
            backup_bytes,
            required,
            shutil.disk_usage(self.directory).free,
            tuple(
                (f"{family}.000.tiger", hashlib.sha256(index.serialize()).hexdigest())
                for family, index in indexes.items()
            ),
            not self.settings.families,
            dependencies,
        )

    def read_embedded(
        self,
        name_hash: int,
        locale: int,
        kind: int,
        resource_id: int,
        *,
        archive_family: str | None = None,
    ) -> bytes:
        from pytrtt.archives.drm_v22 import read_embedded

        return read_embedded(
            self, name_hash, locale, kind, resource_id, archive_family=archive_family
        )

    def apply(
        self,
        plan: ArchiveWritePlan,
        transaction_dir: Path,
        runtime: RuntimeSettings,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> Path:
        from pytrtt.archives.transaction import apply_write_plan

        if not isinstance(plan, TigerV3WritePlan):
            raise TypeError("write plan belongs to a different archive handler")
        return apply_write_plan(
            self.directory,
            plan,
            transaction_dir,
            runtime_settings=runtime_to_dict(runtime),
            progress=progress,
        )

    def restore(
        self,
        transaction_dir: Path,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> None:
        from pytrtt.archives.transaction import restore_write_plan

        restore_write_plan(self.directory, transaction_dir, progress)
