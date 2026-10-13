"""Shared user-facing message catalogs for CLI and future graphical clients."""

from __future__ import annotations

import json
from pathlib import Path
from string import Formatter

CATALOG_ROOT = Path(__file__).resolve().parent / "resources" / "locales"


class Translator:
    """Explicit locale with English fallback; formatting never evaluates catalog code."""

    def __init__(self, language: str = "en", *, catalog_root: Path = CATALOG_ROOT) -> None:
        self.language = language
        self.base = self._load(catalog_root / "en.json")
        # A locale is an identifier, never an arbitrary path.
        if not language or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in language
        ):
            raise ValueError("invalid UI language code")
        path = catalog_root / f"{language}.json"
        self.localized = self._load(path) if path.is_file() else {}
        formatter = Formatter()
        for key, value in self.localized.items():
            if key not in self.base:
                raise ValueError(f"unknown catalog message: {key}")

            def fields(text: str) -> set[str]:
                return {f for _, f, _, _ in formatter.parse(text) if f is not None}

            if fields(value) != fields(self.base[key]):
                raise ValueError(f"catalog placeholder mismatch: {key}")

    @staticmethod
    def _load(path: Path) -> dict[str, str]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or any(not isinstance(v, str) for v in value.values()):
            raise ValueError("message catalog must map identifiers to text")
        return value

    def text(self, key: str, **parameters: object) -> str:
        return self.localized.get(key, self.base[key]).format_map(parameters)
