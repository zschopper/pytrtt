"""Archive interfaces; clients never select handlers by game identity."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from pytrtt.config import RuntimeSettings


@dataclass(frozen=True, slots=True)
class ArchiveResource:
    name_hash: int
    locale: int
    size: int
    archive_family: str | None = None


@dataclass(frozen=True, slots=True)
class ResourceReplacement:
    label: str
    name_hash: int
    locale: int
    data: bytes
    restore_file: str | None = None
    archive_family: str | None = None
    embedded_type: int | None = None
    embedded_id: int | None = None


@runtime_checkable
class ReadSessionArchive(Protocol):
    """Optional batch reading with whole-source validation before and after extraction."""

    def read_session(self) -> AbstractContextManager[None]: ...


@runtime_checkable
class EmbeddedResourceArchive(Protocol):
    """Optional archive support for resources referenced by indexed collections."""

    def read_embedded(
        self,
        name_hash: int,
        locale: int,
        kind: int,
        resource_id: int,
        *,
        archive_family: str | None = None,
    ) -> bytes: ...


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
    @property
    def index_data(self) -> dict[str, bytes]: ...

    def validate_inputs(self, directory: Path) -> None: ...


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
        self,
        plan: ArchiveWritePlan,
        transaction_dir: Path,
        runtime: RuntimeSettings,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> Path: ...

    @abstractmethod
    def restore(
        self,
        transaction_dir: Path,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> None: ...
