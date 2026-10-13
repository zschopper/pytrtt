"""Explicit format/version registry, with no game-dependent dispatch or imports."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pytrtt.archives.contracts import ArchiveHandler
from pytrtt.config import ArchiveSettings
from pytrtt.formats.contracts import TextFormatHandler
from pytrtt.packages.translation import TranslationPackageError

ArchiveFactory = Callable[[Path, ArchiveSettings], ArchiveHandler]


class HandlerResolver(Protocol):
    """Only the format lookups needed by translation workflows."""

    def archive(self, directory: Path, settings: ArchiveSettings) -> ArchiveHandler: ...

    def text_format(self, format_name: str, version: int) -> TextFormatHandler: ...


class HandlerRegistry:
    def __init__(self) -> None:
        self.archives: dict[tuple[str, int], ArchiveFactory] = {}
        self.formats: dict[tuple[str, int], TextFormatHandler] = {}

    def archive(self, directory: Path, settings: ArchiveSettings) -> ArchiveHandler:
        factory = self.archives.get((settings.format, settings.version))
        if factory is None:
            raise TranslationPackageError(
                f"unsupported archive format/version: {settings.format}/{settings.version}"
            )
        root = directory.resolve(strict=True)
        data = (root / settings.data_subdir).resolve(strict=True)
        if data != root and root not in data.parents:
            raise TranslationPackageError("archive directory escapes the game directory")
        return factory(data, settings)

    def text_format(self, format_name: str, version: int) -> TextFormatHandler:
        handler = self.formats.get((format_name, version))
        if handler is None:
            raise TranslationPackageError(
                f"unsupported resource format/version: {format_name}/{version}"
            )
        return handler


def default_registry() -> HandlerRegistry:
    """Compatibility entry point for the application's default composition."""
    from pytrtt.composition import create_handler_registry

    return create_handler_registry()
