"""Resource handlers consume bytes and return structured text or rebuilt bytes."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pytrtt.packages.translation import TranslationEntry


@dataclass(frozen=True, slots=True)
class TextOptions:
    subtitle_language: int
    substitutions: tuple[tuple[str, str], ...] = ()
    cleared_languages: frozenset[int] = frozenset()
    omitted_languages: frozenset[int] = frozenset()

    def text(self, entry: TranslationEntry) -> str:
        if entry.translation is None:
            raise ValueError("missing translation cannot be serialized")
        value = entry.translation or " "
        return (
            value
            if entry.substitution_disabled
            else value.translate({ord(source): target for source, target in self.substitutions})
        )


@runtime_checkable
class TextFormatHandler(Protocol):
    """File-format logic has no knowledge of games, archive offsets, or user interfaces."""

    @abstractmethod
    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]: ...

    @abstractmethod
    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes: ...
