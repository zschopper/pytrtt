"""Portable application storage and discovery of older recovery locations."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def program_directory() -> Path:
    """Use the executable's directory in a bundle and the project root from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def transaction_root() -> Path:
    return program_directory() / "transactions"


def user_data_directory() -> Path:
    """Retain the existing location of CLI reports and legacy CLI transactions."""
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "PyTRTT"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "pytrtt"


def transaction_search_roots() -> tuple[Path, ...]:
    """Write to the portable root; discover older journals without moving recovery data."""
    return tuple(
        dict.fromkeys(
            (
                transaction_root(),
                program_directory() / "work/transactions",
                user_data_directory() / "transactions",
            )
        )
    )
