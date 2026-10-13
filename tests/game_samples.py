"""Optional local sample paths, independent of any particular game."""

from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class GameSamples:
    root: Path
    original: Path
    translated: Path

    def require(self, path: str | Path) -> Path:
        resolved = self.root / path
        if not resolved.is_file():
            pytest.skip(f"Optional game sample is missing: {resolved}")
        return resolved
