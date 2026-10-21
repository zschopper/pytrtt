"""Read-only TIGER v5 indexes and uncompressed archive resources.

Layout evidence: TrRebootModTools a79c48b75f1ffaaf623dc73a625211bf98ff0504,
Shared/Cdc/Archive.cs and Shared/Cdc/Shadow/ShadowArchive.cs (MIT).
This reader does not implement compression, writing, or archive-set override resolution.
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

HEADER_SIZE = 56
ENTRY_SIZE = 32
ALIGNMENT = 2048
INDEX_NAME = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.[0-9]{3}\.tiger\Z")


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
    if any(
        not 0 <= entry.part < parts or (entry.archive_id, entry.sub_id) != (archive_id, sub_id)
        for entry in entries
    ):
        raise TigerFormatError("TIGER entry references an invalid part or archive identity")
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


def _align(value: int) -> int:
    return (value + ALIGNMENT - 1) & ~(ALIGNMENT - 1)


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True, slots=True)
class TigerV5WritePlan:
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
        return {write.file_name: write.data for write in self.writes if write.kind == "index"}

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
                raise ValueError("TIGER v5 source part changed after planning")


class TigerV5Handler:
    """TAFS v5 reader and append-only, journal-compatible writer."""

    def __init__(self, directory: Path, settings: ArchiveSettings) -> None:
        self.directory = directory
        self.settings = settings
        self._loaded = False
        self._reading = False
        self._stamps: dict[str, tuple[int, int]] = {}
        self._indexes: dict[str, TigerIndex] = {}
        self._physical: dict[tuple[str, int, int], tuple[str, TigerEntry]] = {}
        self._effective: dict[tuple[int, int], tuple[str, TigerEntry]] = {}

    def _validate_source(self, name: str) -> None:
        path = self.directory / name
        try:
            current = path.lstat()
        except FileNotFoundError as exc:
            raise ValueError("TIGER v5 source changed during reading") from exc
        if (
            not S_ISREG(current.st_mode)
            or (current.st_size, current.st_mtime_ns) != self._stamps[name]
        ):
            raise ValueError("TIGER v5 source changed during reading")

    @contextmanager
    def read_session(self) -> Iterator[None]:
        if self._reading:
            raise ValueError("TIGER v5 read sessions cannot be nested")
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
            raise ValueError("TIGER v5 requires explicit family/index_files selection")
        if len(set(mapping.values())) != len(mapping):
            raise ValueError("duplicate TIGER v5 index paths")
        for family in self.settings.families:
            name = mapping[family]
            if INDEX_NAME.fullmatch(name) is None or not name.endswith(".000.tiger"):
                raise ValueError("unsafe TIGER v5 index name")
            path = self.directory / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("missing or unsafe TIGER v5 index")
            with path.open("rb") as stream:
                index = read_tiger_index(stream)
            self._indexes[family] = index
            sizes = []
            for part in range(index.num_parts):
                part_name = name[:-9] + f"{part:03}.tiger"
                part_path = self.directory / part_name
                if part_path.is_symlink() or not part_path.is_file():
                    raise ValueError("missing or unsafe TIGER v5 part")
                stat = part_path.stat()
                sizes.append(stat.st_size)
                self._stamps[part_name] = stat.st_size, stat.st_mtime_ns
            for entry in index.entries:
                if entry.offset + entry.size > sizes[entry.part]:
                    raise ValueError("TIGER v5 resource exceeds file bounds")
                key = entry.name_hash, entry.locale
                physical_key = family, *key
                if physical_key in self._physical:
                    raise ValueError("duplicate TIGER v5 hash/locale")
                source = name[:-9] + f"{entry.part:03}.tiger"
                value = source, entry
                self._physical[physical_key] = value
                previous = self._effective.get(key)
                priority = entry.archive_id, entry.sub_id
                if previous is not None:
                    old_priority = previous[1].archive_id, previous[1].sub_id
                    if old_priority == priority:
                        raise ValueError("ambiguous TIGER v5 archive priority")
                    if old_priority > priority:
                        continue
                self._effective[key] = value
        self._loaded = True

    def resources(self) -> tuple[ArchiveResource, ...]:
        self._load()
        if self.settings.include_overridden:
            return tuple(
                ArchiveResource(name_hash, locale, value[1].size, family)
                for (family, name_hash, locale), value in self._physical.items()
            )
        return tuple(
            ArchiveResource(name_hash, locale, value[1].size)
            for (name_hash, locale), value in self._effective.items()
        )

    def read(self, resource: ArchiveResource) -> bytes:
        self._load()
        value = (
            self._physical.get((resource.archive_family, resource.name_hash, resource.locale))
            if resource.archive_family is not None
            else self._effective.get((resource.name_hash, resource.locale))
        )
        if value is None or value[1].size != resource.size:
            raise ValueError("TIGER v5 resource is absent or changed")
        name, entry = value
        if self._reading:
            self._validate_source(name)
        return read_tiger_resource(
            self.directory / name.replace(f"{entry.part:03}.tiger", "000.tiger"),
            self._index_for(entry),
            entry,
        )

    def _index_for(self, entry: TigerEntry) -> TigerIndex:
        matches = [
            index
            for index in self._indexes.values()
            if (index.archive_id, index.sub_id) == (entry.archive_id, entry.sub_id)
        ]
        if len(matches) != 1:
            raise ValueError("ambiguous TIGER v5 archive identity")
        return matches[0]

    def plan(self, replacements: tuple[ResourceReplacement, ...]) -> TigerV5WritePlan:
        self._load()
        if not replacements:
            raise ValueError("no TIGER v5 replacements")
        boundary = self.settings.boundary
        if not 0 < boundary <= 0x100000000 or boundary % ALIGNMENT:
            raise ValueError("invalid TIGER v5 part boundary")
        mapping = dict(self.settings.index_files)
        tables: dict[str, bytearray] = {}
        original_tables: dict[str, bytes] = {}
        sizes = {name: stamp[0] for name, stamp in self._stamps.items()}
        counts = {family: index.num_parts for family, index in self._indexes.items()}
        for family, index in self._indexes.items():
            length = HEADER_SIZE + ENTRY_SIZE * len(index.entries)
            data = (self.directory / mapping[family]).read_bytes()[:length]
            tables[family] = bytearray(data)
            original_tables[family] = data
        writes: list[PlannedWrite] = []
        cursors: dict[str, tuple[int, int]] = {}
        seen: set[tuple[str, int, int]] = set()
        for replacement in replacements:
            if replacement.restore_file is not None or replacement.embedded_type is not None:
                raise ValueError("TIGER v5 embedded or font recovery replacements are unsupported")
            if not replacement.data or _align(len(replacement.data)) > boundary:
                raise ValueError("TIGER v5 replacement exceeds boundary or is empty")
            value = (
                self._physical.get(
                    (replacement.archive_family, replacement.name_hash, replacement.locale)
                )
                if replacement.archive_family is not None
                else self._effective.get((replacement.name_hash, replacement.locale))
            )
            if value is None:
                raise ValueError("missing TIGER v5 replacement")
            source, entry = value
            if entry.stored_size:
                raise ValueError("compressed TIGER v5 replacement sources are unsupported")
            families = [family for family, name in mapping.items() if name[:-9] == source[:-9]]
            if len(families) != 1:
                raise ValueError("ambiguous TIGER v5 physical family")
            family = families[0]
            key = family, entry.name_hash, entry.locale
            if key in seen:
                raise ValueError("duplicate TIGER v5 replacement")
            seen.add(key)
            stem = mapping[family][:-9]
            last = counts[family] - 1
            part, offset = cursors.get(family, (last, _align(sizes[f"{stem}{last:03}.tiger"])))
            if offset + _align(len(replacement.data)) > boundary:
                part += 1
                offset = 0
                name = f"{stem}{part:03}.tiger"
                if part > 32767 or (self.directory / name).exists():
                    raise ValueError("new TIGER v5 part is unsafe or already exists")
                sizes[name] = 0
            name = f"{stem}{part:03}.tiger"
            padded = replacement.data + bytes(_align(len(replacement.data)) - len(replacement.data))
            writes.append(PlannedWrite(name, "resource", replacement.label, offset, padded, b""))
            cursors[family] = part, offset + len(padded)
            rows = [
                row
                for row, indexed in enumerate(self._indexes[family].entries)
                if (indexed.name_hash, indexed.locale) == (entry.name_hash, entry.locale)
            ]
            if len(rows) != 1:
                raise ValueError("ambiguous TIGER v5 index row")
            row_offset = HEADER_SIZE + rows[0] * ENTRY_SIZE
            struct.pack_into(
                "<IIh", tables[family], row_offset + 16, len(replacement.data), 0, part
            )
            struct.pack_into("<I", tables[family], row_offset + 28, offset)
            struct.pack_into("<I", tables[family], 8, max(counts[family], part + 1))
        for family in cursors:
            writes.append(
                PlannedWrite(
                    mapping[family],
                    "index",
                    "TIGER v5 index",
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
                max(
                    sizes[name],
                    *(
                        write.offset + len(write.data)
                        for write in writes
                        if write.file_name == name
                    ),
                ),
                _digest(path) if path.exists() else None,
            )
        dependencies = tuple(
            (name, size, _digest(self.directory / name))
            for name, (size, _) in self._stamps.items()
            if name not in files
        )
        backup = sum(len(write.original_data) for write in writes)
        return TigerV5WritePlan(
            tuple(writes),
            files,
            backup,
            backup + 2 * sum(file.final_size for file in files.values()),
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

        if not isinstance(plan, TigerV5WritePlan):
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
