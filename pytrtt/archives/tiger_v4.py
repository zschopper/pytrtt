"""TAFS v4 indexes and append-only, journal-compatible writes.

Layout evidence: TrRebootModTools a79c48b75f1ffaaf623dc73a625211bf98ff0504,
Shared/Cdc/Rise/RiseArchive.cs and Archive.cs; independently implemented.
The observed platform and text handlers are verified separately by developer profiles.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import struct
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISREG
from typing import BinaryIO

from pytrtt.archives.contracts import (
    ArchiveResource,
    ArchiveWritePlan,
    PlannedFile,
    PlannedWrite,
    ResourceReplacement,
)
from pytrtt.config import ArchiveSettings, RuntimeSettings, runtime_to_dict

INDEX_NAME = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.[0-9]{3}\.tiger\Z")


@dataclass(frozen=True, slots=True)
class TigerV4Entry:
    name_hash: int
    locale: int
    size: int
    stored_size: int
    part: int
    archive_id: int
    offset: int


@dataclass(frozen=True, slots=True)
class TigerV4Index:
    num_parts: int
    archive_id: int
    platform: str
    entries: tuple[TigerV4Entry, ...]


def read_tiger_v4_index(stream: BinaryIO) -> TigerV4Index:
    stream.seek(0, 2)
    length = stream.tell()
    stream.seek(0)
    header = stream.read(52)
    if len(header) != 52 or header[:4] != b"TAFS":
        raise ValueError("invalid TIGER v4 header")
    version, parts, count, archive_id = struct.unpack_from("<4I", header, 4)
    if version != 4:
        raise ValueError("unsupported TIGER version")
    if not 1 <= parts <= 0x7FFF or archive_id > 0x7FFF or 52 + count * 24 > length:
        raise ValueError("invalid TIGER v4 index bounds or identity")
    try:
        platform = header[20:52].split(b"\0", 1)[0].decode("ascii")
    except UnicodeError as exc:
        raise ValueError("invalid TIGER v4 platform") from exc
    if not platform:
        raise ValueError("missing TIGER v4 platform")
    raw = stream.read(count * 24)
    if len(raw) != count * 24:
        raise ValueError("truncated TIGER v4 index")
    entries = tuple(TigerV4Entry(*row) for row in struct.iter_unpack("<4IhhI", raw))
    for entry in entries:
        if not 0 <= entry.part < parts or entry.archive_id != archive_id:
            raise ValueError("cross-archive or invalid TIGER v4 resource part")
        if entry.stored_size:
            raise ValueError("TIGER v4 stored-size encoding is not supported")
        if entry.part == 0 and entry.size and entry.offset < 52 + count * 24:
            raise ValueError("TIGER v4 resource overlaps index")
    return TigerV4Index(parts, archive_id, platform, entries)


class TigerV4Handler:
    def __init__(self, directory: Path, settings: ArchiveSettings) -> None:
        self.directory = directory
        self.settings = settings
        self._loaded = False
        self._reading = False
        self._stamps: dict[str, tuple[int, int]] = {}
        self._effective: dict[tuple[int, int], tuple[str, TigerV4Entry, int]] = {}
        self._physical: dict[tuple[str, int, int], tuple[str, TigerV4Entry, int]] = {}

    def _validate_source(self, name: str) -> None:
        path = self.directory / name
        try:
            current = path.lstat()
        except FileNotFoundError as exc:
            raise ValueError("TIGER v4 source changed during reading") from exc
        if (
            not S_ISREG(current.st_mode)
            or (current.st_size, current.st_mtime_ns) != self._stamps[name]
        ):
            raise ValueError("TIGER v4 source changed during reading")

    @contextmanager
    def read_session(self) -> Iterator[None]:
        if self._reading:
            raise ValueError("TIGER v4 read sessions cannot be nested")
        self._load()
        self._reading = True
        try:
            yield
        finally:
            self._reading = False
            self._load()

    def _load(self) -> None:
        if self._loaded:
            if not self._reading:
                for name in self._stamps:
                    self._validate_source(name)
            return
        mapping = dict(self.settings.index_files)
        if not self.settings.families or set(mapping) != set(self.settings.families):
            raise ValueError("TIGER v4 requires explicit family/index_files selection")
        if len(set(mapping.values())) != len(mapping):
            raise ValueError("duplicate TIGER v4 index paths")
        for family in self.settings.families:
            name = mapping[family]
            if INDEX_NAME.fullmatch(name) is None or not name.endswith(".000.tiger"):
                raise ValueError("unsafe TIGER v4 index name")
            path = self.directory / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("missing or unsafe TIGER v4 index")
            with path.open("rb") as stream:
                index = read_tiger_v4_index(stream)
            sizes = []
            for part in range(index.num_parts):
                part_name = name[:-9] + f"{part:03}.tiger"
                part_path = self.directory / part_name
                if part_path.is_symlink() or not part_path.is_file():
                    raise ValueError("missing or unsafe TIGER v4 part")
                stat = part_path.stat()
                sizes.append(stat.st_size)
                self._stamps[part_name] = stat.st_size, stat.st_mtime_ns
            for entry in index.entries:
                if entry.offset + entry.size > sizes[entry.part]:
                    raise ValueError("TIGER v4 resource exceeds file bounds")
                key = entry.name_hash, entry.locale
                physical = family, *key
                if physical in self._physical:
                    raise ValueError("duplicate TIGER v4 hash/locale")
                source = name[:-9] + f"{entry.part:03}.tiger"
                value = source, entry, index.archive_id
                self._physical[physical] = value
                previous = self._effective.get(key)
                if previous is not None and previous[2] == index.archive_id:
                    raise ValueError("ambiguous TIGER v4 archive priority")
                if previous is None or previous[2] < index.archive_id:
                    self._effective[key] = value
        self._loaded = True

    def resources(self) -> tuple[ArchiveResource, ...]:
        self._load()
        if self.settings.include_overridden:
            return tuple(
                ArchiveResource(h, locale, v[1].size, family)
                for (family, h, locale), v in self._physical.items()
            )
        return tuple(
            ArchiveResource(h, locale, v[1].size) for (h, locale), v in self._effective.items()
        )

    def read(self, resource: ArchiveResource) -> bytes:
        self._load()
        value = (
            self._physical.get((resource.archive_family, resource.name_hash, resource.locale))
            if resource.archive_family is not None
            else self._effective.get((resource.name_hash, resource.locale))
        )
        if value is None or value[1].size != resource.size:
            raise ValueError("TIGER v4 resource is absent or changed")
        name, entry, _ = value
        if self._reading:
            self._validate_source(name)
        with (self.directory / name).open("rb") as stream:
            stream.seek(entry.offset)
            data = stream.read(entry.size)
        if len(data) != entry.size:
            raise ValueError("truncated TIGER v4 resource")
        if data.startswith(b"CDRM"):
            raise ValueError("TIGER v4 CDRM decompression is not supported")
        return data

    def plan(self, replacements: tuple[ResourceReplacement, ...]) -> TigerV4WritePlan:
        if any(replacement.embedded_type is not None for replacement in replacements):
            from pytrtt.archives.drm_v22_v4 import plan_embedded

            return plan_embedded(self, replacements)
        self._load()
        boundary = self.settings.boundary
        if not replacements:
            raise ValueError("no TIGER replacements")
        if not 0 < boundary <= 0x100000000 or boundary % 2048:
            raise ValueError("invalid TIGER v4 part boundary")
        mapping = dict(self.settings.index_files)
        tables: dict[str, bytearray] = {}
        counts: dict[str, int] = {}
        for family, name in mapping.items():
            with (self.directory / name).open("rb") as stream:
                index = read_tiger_v4_index(stream)
                stream.seek(0)
                tables[family] = bytearray(stream.read(52 + 24 * len(index.entries)))
                counts[family] = index.num_parts
        original_tables = {family: bytes(data) for family, data in tables.items()}
        sizes = {name: stamp[0] for name, stamp in self._stamps.items()}
        if any(size > boundary for size in sizes.values()):
            raise ValueError("existing TIGER v4 part exceeds configured boundary")
        writes: list[PlannedWrite] = []
        cursors: dict[str, tuple[int, int]] = {}
        seen: set[tuple[str, int, int]] = set()
        for replacement in replacements:
            if replacement.restore_file is not None:
                raise ValueError("TIGER v4 direct font recovery assets are unsupported")
            if not replacement.data or _align(len(replacement.data)) > boundary:
                raise ValueError("TIGER v4 replacement exceeds boundary or is empty")
            value = (
                self._physical.get(
                    (replacement.archive_family, replacement.name_hash, replacement.locale)
                )
                if replacement.archive_family is not None
                else self._effective.get((replacement.name_hash, replacement.locale))
            )
            if value is None:
                raise ValueError("missing TIGER v4 replacement")
            source, entry, _ = value
            families = [family for family, name in mapping.items() if name[:-9] == source[:-9]]
            if len(families) != 1:
                raise ValueError("ambiguous TIGER v4 physical family")
            family = families[0]
            key = family, entry.name_hash, entry.locale
            if key in seen:
                raise ValueError("duplicate TIGER v4 replacement")
            seen.add(key)
            stem = mapping[family][:-9]
            last = counts[family] - 1
            part, offset = cursors.get(family, (last, _align(sizes[f"{stem}{last:03}.tiger"])))
            if offset + _align(len(replacement.data)) > boundary:
                part += 1
                offset = 0
                name = f"{stem}{part:03}.tiger"
                if part > 999 or (self.directory / name).exists():
                    raise ValueError("new TIGER v4 part is unsafe or already exists")
                sizes[name] = 0
            name = f"{stem}{part:03}.tiger"
            data = replacement.data + bytes(_align(len(replacement.data)) - len(replacement.data))
            writes.append(PlannedWrite(name, "resource", replacement.label, offset, data, b""))
            cursors[family] = part, offset + len(data)
            table = tables[family]
            rows = [
                row
                for row in range((len(table) - 52) // 24)
                if struct.unpack_from("<II", table, 52 + row * 24) == key[1:]
            ]
            if len(rows) != 1:
                raise ValueError("ambiguous TIGER v4 index row")
            row_offset = 52 + rows[0] * 24
            struct.pack_into("<I", table, row_offset + 8, len(replacement.data))
            struct.pack_into("<h", table, row_offset + 16, part)
            struct.pack_into("<I", table, row_offset + 20, offset)
            struct.pack_into("<I", table, 8, max(counts[family], part + 1))
        for family in cursors:
            writes.append(
                PlannedWrite(
                    mapping[family],
                    "index",
                    "TIGER v4 index",
                    0,
                    bytes(tables[family]),
                    original_tables[family],
                )
            )
        files = {}
        for name in {write.file_name for write in writes}:
            path = self.directory / name
            files[name] = PlannedFile(
                sizes[name],
                max(sizes[name], *(w.offset + len(w.data) for w in writes if w.file_name == name)),
                _digest(path) if path.exists() else None,
            )
        dependencies = tuple(
            (name, size, _digest(self.directory / name))
            for name, (size, _) in self._stamps.items()
            if name not in files
        )
        self._load()
        backup = sum(len(w.original_data) for w in writes)
        return TigerV4WritePlan(
            tuple(writes),
            files,
            backup,
            backup + 2 * sum(f.final_size for f in files.values()),
            shutil.disk_usage(self.directory).free,
            dependencies,
        )

    def apply(
        self,
        plan: ArchiveWritePlan,
        transaction_dir: Path,
        runtime: RuntimeSettings,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> Path:
        from pytrtt.archives.transaction import apply_write_plan

        if not isinstance(plan, TigerV4WritePlan):
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

    def read_embedded(
        self,
        name_hash: int,
        locale: int,
        kind: int,
        resource_id: int,
        *,
        archive_family: str | None = None,
    ) -> bytes:
        from pytrtt.archives.drm_v22_v4 import read_embedded

        return read_embedded(
            self, name_hash, locale, kind, resource_id, archive_family=archive_family
        )


def _align(value: int) -> int:
    return (value + 2047) & ~2047


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True, slots=True)
class TigerV4WritePlan:
    writes: tuple[PlannedWrite, ...]
    files: dict[str, PlannedFile]
    backup_bytes: int
    additional_bytes_required: int
    free_bytes: int
    source_parts: tuple[tuple[str, int, str], ...]

    @property
    def sufficient_space(self) -> bool:
        return self.additional_bytes_required <= self.free_bytes

    @property
    def index_data(self) -> dict[str, bytes]:
        return {w.file_name: w.data for w in self.writes if w.kind == "index"}

    def validate_inputs(self, directory: Path) -> None:
        for name, size, digest in self.source_parts:
            path = directory / name
            if (
                INDEX_NAME.fullmatch(name) is None
                or path.is_symlink()
                or not path.is_file()
                or path.stat().st_size != size
                or _digest(path) != digest
            ):
                raise ValueError("TIGER v4 source part changed after planning")
