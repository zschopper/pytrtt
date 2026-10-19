"""Indexed Bigfile families with explicit layer ordering and append-only placement."""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, replace
from pathlib import Path

from pytrtt.archives.bigfile_v1 import BigFileEntry, BigFileIndex, read_bigfile_index
from pytrtt.archives.contracts import (
    ArchiveResource,
    ArchiveWritePlan,
    PlannedFile,
    PlannedWrite,
    ResourceReplacement,
)
from pytrtt.archives.write_plan import serialize_bigfile_index
from pytrtt.config import ArchiveSettings, RuntimeSettings, runtime_to_dict

PART = re.compile(r"([A-Za-z0-9_-]+)\.([0-9]{3})\Z")


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _align(size: int) -> int:
    return (size + 2047) & ~2047


@dataclass(frozen=True, slots=True)
class BigFileV2WritePlan:
    writes: tuple[PlannedWrite, ...]
    files: dict[str, PlannedFile]
    index_data: dict[str, bytes]
    backup_bytes: int
    additional_bytes_required: int
    free_bytes: int
    source_files: tuple[tuple[str, int, str], ...]
    source_indexes: tuple[str, ...]

    @property
    def sufficient_space(self) -> bool:
        return self.additional_bytes_required <= self.free_bytes

    def validate_inputs(self, directory: Path) -> None:
        if {p.name for p in directory.iterdir() if PART.fullmatch(p.name)} != {
            name for name, _, _ in self.source_files
        }:
            raise ValueError("Bigfile archive family set changed")
        for name, size, digest in self.source_files:
            path = directory / name
            if (
                PART.fullmatch(name) is None
                or path.is_symlink()
                or not path.is_file()
                or path.stat().st_size != size
                or _digest(path) != digest
            ):
                raise ValueError("Bigfile source changed after planning")


class BigFileV2Handler:
    def __init__(self, directory: Path, settings: ArchiveSettings) -> None:
        self.directory = directory
        self.settings = settings
        self._loaded: dict[str, BigFileIndex] | None = None
        self._sizes: dict[str, int] = {}
        self._stamps: dict[str, tuple[int, int]] = {}

    def _part_name(self, family: str, part: int) -> str:
        mapped = dict(self.settings.index_files).get(family)
        if mapped is not None:
            if part != 0 or PART.fullmatch(mapped) is None:
                raise ValueError("independent index cannot address another archive part")
            return mapped
        return f"{family}.{part:03}"

    def _indexes(self) -> dict[str, BigFileIndex]:
        if self._loaded is not None:
            for name, stamp in self._stamps.items():
                path = self.directory / name
                if path.is_symlink() or (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
                    raise ValueError("Bigfile source changed during reading")
            return self._loaded
        if not self.settings.families or not 0 < self.settings.boundary <= 0xFFFFF800:
            raise ValueError("Bigfile v2 requires ordered families and a valid boundary")
        indexes = {}
        for family in self.settings.families:
            if re.fullmatch(r"[A-Za-z0-9_-]+", family) is None or family in indexes:
                raise ValueError("invalid or duplicate Bigfile family")
            paths = (
                [self.directory / self._part_name(family, 0)]
                if family in dict(self.settings.index_files)
                else sorted(self.directory.glob(f"{family}.*"))
            )
            if not paths or [p.name for p in paths] != [
                self._part_name(family, part) for part in range(len(paths))
            ]:
                raise ValueError("Bigfile parts must be contiguous")
            for path in paths:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("unsafe Bigfile part")
                stat = path.stat()
                if stat.st_size > self.settings.boundary:
                    raise ValueError("Bigfile part exceeds boundary")
                if path.name in self._sizes:
                    raise ValueError("overlapping Bigfile family files")
                self._sizes[path.name] = stat.st_size
                self._stamps[path.name] = (stat.st_size, stat.st_mtime_ns)
            with paths[0].open("rb") as stream:
                index = read_bigfile_index(stream, self.settings.boundary)
            keys: dict[tuple[int, int], tuple[int, int, int]] = {}
            for entry in index.entries:
                key = entry.hash, entry.locale
                identity = entry.length, entry.location, entry.unknown
                if key in keys and keys[key] != identity:
                    raise ValueError("duplicate physical Bigfile resource")
                keys[key] = identity
                part, offset = entry.part_and_offset(self.settings.boundary)
                size = self._sizes.get(self._part_name(family, part))
                if size is None or offset + entry.length > size:
                    raise ValueError("Bigfile resource exceeds part bounds")
                if part == 0 and entry.length and offset < 4 + 20 * len(index.entries):
                    raise ValueError("Bigfile resource overlaps index")
            indexes[family] = index
        self._loaded = indexes
        return indexes

    def _references(self) -> dict[tuple[str, int, int], BigFileEntry]:
        return {
            (family, e.hash, e.locale): e
            for family, index in self._indexes().items()
            for e in index.entries
        }

    def resources(self) -> tuple[ArchiveResource, ...]:
        physical = self._references()
        if self.settings.include_overridden:
            return tuple(
                ArchiveResource(h, loc, e.length, family)
                for (family, h, loc), e in physical.items()
            )
        effective = {}
        for (family, h, loc), e in physical.items():
            effective[h, loc] = ArchiveResource(h, loc, e.length, family)
        return tuple(effective.values())

    def read(self, resource: ArchiveResource) -> bytes:
        matches = [
            (family, entry)
            for (family, h, loc), entry in self._references().items()
            if h == resource.name_hash
            and loc == resource.locale
            and (resource.archive_family is None or family == resource.archive_family)
        ]
        if resource.archive_family is None and matches:
            matches = matches[-1:]
        if len(matches) != 1 or matches[0][1].length != resource.size:
            raise ValueError("Bigfile resource is absent or changed")
        family, entry = matches[0]
        part, offset = entry.part_and_offset(self.settings.boundary)
        with (self.directory / self._part_name(family, part)).open("rb") as stream:
            stream.seek(offset)
            data = stream.read(entry.length)
        if len(data) != entry.length:
            raise ValueError("truncated Bigfile resource")
        return data

    def plan(self, replacements: tuple[ResourceReplacement, ...]) -> BigFileV2WritePlan:
        indexes = self._indexes()
        physical = self._references()
        updated = dict(indexes)
        cursors: dict[str, tuple[int, int]] = {}
        sizes = dict(self._sizes)
        seen = set()
        writes = []
        for r in replacements:
            candidates = [
                key
                for key in physical
                if key[1:] == (r.name_hash, r.locale)
                and (r.archive_family is None or key[0] == r.archive_family)
            ]
            if r.archive_family is None and candidates:
                candidates = candidates[-1:]
            if len(candidates) != 1 or candidates[0] in seen or not r.data:
                raise ValueError("missing, duplicate or empty Bigfile replacement")
            key = candidates[0]
            seen.add(key)
            family = key[0]
            entry = physical[key]
            part, offset = cursors.get(
                family,
                (
                    0
                    if family in dict(self.settings.index_files)
                    else sum(n.startswith(family + ".") for n in self._sizes) - 1,
                    0,
                ),
            )
            if family not in cursors:
                offset = _align(sizes[self._part_name(family, part)])
            allocation = _align(len(r.data))
            if allocation > self.settings.boundary:
                raise ValueError("replacement exceeds Bigfile part boundary")
            if offset + allocation > self.settings.boundary:
                part += 1
                offset = 0
                if part > 999 or (self.directory / self._part_name(family, part)).exists():
                    raise ValueError("new Bigfile part unavailable")
                sizes[self._part_name(family, part)] = 0
            location = (part * self.settings.boundary + offset) // 2048
            if location > 0xFFFFFFFF:
                raise ValueError("Bigfile location overflow")
            original = self.read(ArchiveResource(entry.hash, entry.locale, entry.length, family))
            writes.append(
                PlannedWrite(
                    self._part_name(family, part),
                    "resource",
                    r.label,
                    offset,
                    r.data + bytes(allocation - len(r.data)),
                    b"",
                    resource_original=original if r.restore_file else None,
                    restore_file=r.restore_file,
                )
            )
            rows = list(updated[family].entries)
            for i, row in enumerate(rows):
                if (row.hash, row.locale) == (entry.hash, entry.locale):
                    rows[i] = replace(row, length=len(r.data), location=location)
            updated[family] = BigFileIndex(tuple(rows))
            cursors[family] = part, offset + allocation
        if not writes:
            raise ValueError("no Bigfile replacements")
        index_data = {}
        for family in cursors:
            name = self._part_name(family, 0)
            new = serialize_bigfile_index(updated[family])
            old = serialize_bigfile_index(indexes[family])
            index_data[name] = new
            writes.append(PlannedWrite(name, "index", "Bigfile index", 0, new, old))
        files = {}
        for name in {w.file_name for w in writes}:
            path = self.directory / name
            files[name] = PlannedFile(
                sizes[name],
                max(sizes[name], *(w.offset + len(w.data) for w in writes if w.file_name == name)),
                _digest(path) if path.exists() else None,
            )
        source_files = tuple(
            (name, size, _digest(self.directory / name)) for name, size in self._sizes.items()
        )
        self._indexes()
        backup = sum(len(w.original_data) + len(w.resource_original or b"") for w in writes)
        return BigFileV2WritePlan(
            tuple(writes),
            files,
            index_data,
            backup,
            backup + 2 * sum(f.final_size for f in files.values()),
            shutil.disk_usage(self.directory).free,
            source_files,
            tuple(self._part_name(family, 0) for family in indexes),
        )

    def apply(
        self, plan: ArchiveWritePlan, transaction_dir: Path, runtime: RuntimeSettings
    ) -> Path:
        from pytrtt.archives.transaction import apply_write_plan

        if not isinstance(plan, BigFileV2WritePlan):
            raise TypeError("write plan belongs to a different archive handler")
        return apply_write_plan(
            self.directory, plan, transaction_dir, runtime_settings=runtime_to_dict(runtime)
        )

    def restore(self, transaction_dir: Path) -> None:
        from pytrtt.archives.transaction import restore_write_plan

        restore_write_plan(self.directory, transaction_dir)
