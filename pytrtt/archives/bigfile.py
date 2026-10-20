"""Bigfile version-one implementation of the archive interface."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from pathlib import Path

from pytrtt.archives.bigfile_v1 import (
    BigFileIndex,
    extract_resource,
    read_bigfile_index,
)
from pytrtt.archives.contracts import (
    ArchiveHandler,
    ArchiveResource,
    ArchiveWritePlan,
    ResourceReplacement,
)
from pytrtt.archives.transaction import apply_write_plan, restore_write_plan
from pytrtt.archives.write_plan import BigFileWritePlan, plan_replacements
from pytrtt.config import ArchiveSettings, RuntimeSettings, runtime_to_dict


class BigFileV1Handler(ArchiveHandler):
    def __init__(self, directory: Path, settings: ArchiveSettings) -> None:
        self.directory = directory
        self.settings = settings

    @cached_property
    def index(self) -> BigFileIndex:
        with (self.directory / "bigfile.000").open("rb") as stream:
            return read_bigfile_index(stream, self.settings.boundary)

    def resources(self) -> tuple[ArchiveResource, ...]:
        return tuple(ArchiveResource(e.hash, e.locale, e.length) for e in self.index.entries)

    def read(self, resource: ArchiveResource) -> bytes:
        entries = [
            e for e in self.index.find_hash(resource.name_hash) if e.locale == resource.locale
        ]
        if len(entries) != 1:
            raise ValueError("archive resource is absent or ambiguous")
        return extract_resource(self.directory, entries[0], self.settings.boundary)

    def plan(self, replacements: tuple[ResourceReplacement, ...]) -> ArchiveWritePlan:
        return plan_replacements(self.directory, self.index, replacements, self.settings.boundary)

    def apply(
        self,
        plan: ArchiveWritePlan,
        transaction_dir: Path,
        runtime: RuntimeSettings,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> Path:
        if not isinstance(plan, BigFileWritePlan):
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
        restore_write_plan(self.directory, transaction_dir, progress)
