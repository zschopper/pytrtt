"""Archive interfaces; clients never select handlers by game identity."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from pytrtt.config import RuntimeSettings


@dataclass(frozen=True, slots=True)
class ArchiveResource:
    name_hash: int
    locale: int
    size: int


@dataclass(frozen=True, slots=True)
class ResourceReplacement:
    label: str
    name_hash: int
    locale: int
    data: bytes
    restore_file: str | None = None


@dataclass(frozen=True, slots=True)
class PlannedWrite:
    file_name: str
    kind: str
    label: str
    offset: int
    data: bytes
    original_data: bytes
    resource_original_file_name: str | None = None
    resource_original_offset: int | None = None
    resource_original: bytes | None = None
    restore_file: str | None = None


@dataclass(frozen=True, slots=True)
class PlannedFile:
    original_size: int
    final_size: int
    original_sha256: str | None


class ArchiveWritePlan(Protocol):
    @property
    def writes(self) -> tuple[PlannedWrite, ...]: ...
    @property
    def files(self) -> dict[str, PlannedFile]: ...
    @property
    def backup_bytes(self) -> int: ...
    @property
    def sufficient_space(self) -> bool: ...


@runtime_checkable
class ArchiveHandler(Protocol):
    """An archive family/version owns addressing, allocation and journal restoration."""

    @abstractmethod
    def resources(self) -> tuple[ArchiveResource, ...]: ...

    @abstractmethod
    def read(self, resource: ArchiveResource) -> bytes: ...

    @abstractmethod
    def plan(self, replacements: tuple[ResourceReplacement, ...]) -> ArchiveWritePlan: ...

    @abstractmethod
    def apply(
        self, plan: ArchiveWritePlan, transaction_dir: Path, runtime: RuntimeSettings
    ) -> Path: ...

    @abstractmethod
    def restore(self, transaction_dir: Path) -> None: ...
