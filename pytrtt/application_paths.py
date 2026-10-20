"""Portable application storage and discovery of older recovery locations."""

from __future__ import annotations

import os
import sys
from pathlib import Path

GAME_RECOVERY_DIRECTORY = "PyTRTT Recovery"
RECOVERY_README = """PyTRTT recovery data — DO NOT DELETE

This directory contains backups and transaction journals required to restore the original
game files. Do not rename, move, edit, or delete this directory or any file inside it.
Use PyTRTT's restore operation to restore the game safely.

PyTRTT helyreállítási adatok — NE TÖRÖLD

Ez a mappa az eredeti játékfájlok visszaállításához szükséges biztonsági mentéseket és
tranzakciós naplókat tartalmazza. Ne nevezd át, ne helyezd át, ne módosítsd és ne töröld
ezt a mappát vagy a benne lévő fájlokat. A biztonságos visszaállításhoz használd a PyTRTT
helyreállítási műveletét.
"""


def program_directory() -> Path:
    """Use the executable's directory in a bundle and the project root from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def transaction_root() -> Path:
    return program_directory() / "transactions"


def game_transaction_root(game_directory: Path) -> Path:
    """Return the optional user-visible recovery root inside one game installation."""
    return game_directory / GAME_RECOVERY_DIRECTORY


def ensure_game_transaction_root(game_directory: Path) -> Path:
    """Create the in-game recovery root and its bilingual preservation notice."""
    root = game_transaction_root(game_directory)
    root.mkdir(parents=True, exist_ok=True)
    readme = root / "README.txt"
    if not readme.exists():
        readme.write_text(RECOVERY_README, encoding="utf-8", newline="\r\n")
    return root


def user_data_directory() -> Path:
    """Retain the existing location of CLI reports and legacy CLI transactions."""
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "PyTRTT"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "pytrtt"


def transaction_search_roots(game_directory: Path | None = None) -> tuple[Path, ...]:
    """Discover in-game, portable, and legacy journals without moving recovery data."""
    local_roots = () if game_directory is None else (game_transaction_root(game_directory),)
    return tuple(
        dict.fromkeys(
            (
                *local_roots,
                transaction_root(),
                program_directory() / "work/transactions",
                user_data_directory() / "transactions",
            )
        )
    )
