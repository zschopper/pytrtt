"""Optional machine-local paths shared by all entry points, never packaged as game data."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOCAL_FILENAME = "pytrtt.local.toml"
PATH_FIELDS = {"install_dir", "original_dir", "translated_dir", "samples_dir"}


@dataclass(frozen=True, slots=True)
class LocalGamePaths:
    game_id: str
    aliases: tuple[str, ...] = ()
    install_dir: Path | None = None
    original_dir: Path | None = None
    translated_dir: Path | None = None
    samples_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class LocalEnvironment:
    games: tuple[LocalGamePaths, ...]
    samples_dir: Path

    def find_game(self, identifier: str) -> LocalGamePaths | None:
        return next(
            (
                game
                for game in self.games
                if identifier == game.game_id or identifier in game.aliases
            ),
            None,
        )

    def game(self, identifier: str) -> LocalGamePaths:
        game = self.find_game(identifier)
        if game is None:
            raise ValueError(f"No local paths configured for game: {identifier}")
        return game


def _table(value: Any, allowed: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or (allowed is not None and value.keys() - allowed):
        raise ValueError("Invalid local environment fields")
    return value


def _path(value: Any, root: Path) -> Path | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Local paths must be strings")
    path = Path(value).expanduser()
    return (root / path).resolve()


def load_local_environment(
    path: Path | None = None, *, directory: Path | None = None, platform: str | None = None
) -> LocalEnvironment:
    """Relative paths use the config's directory; a missing implicit file is harmless."""
    root = (directory or Path.cwd()).resolve()
    config = path if path is not None else root / LOCAL_FILENAME
    if path is None and not config.exists():
        return LocalEnvironment((), root / "work/samples")
    with config.open("rb") as stream:
        value = _table(tomllib.load(stream), {"samples_dir", "games", "platforms"})
    root = config.resolve().parent
    host = platform or (
        "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"
    )
    platforms = _table(value.get("platforms", {}), {"windows", "linux", "macos"})
    for settings in platforms.values():
        fields = _table(settings, {"samples_dir", "games"})
        for game in _table(fields.get("games", {})).values():
            _table(game, PATH_FIELDS)
            for field in game.values():
                _path(field, root)
        _path(fields.get("samples_dir"), root)
    overrides = platforms.get(host, {})
    base_games = _table(value.get("games", {}))
    host_games = _table(overrides.get("games", {}))
    identifiers = set(base_games) | set(host_games)
    games = []
    used = set(identifiers)
    for identifier in sorted(identifiers):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", identifier):
            raise ValueError("Invalid local game identifier")
        base = _table(base_games.get(identifier, {}), PATH_FIELDS | {"aliases"})
        aliases = base.get("aliases", [])
        if not isinstance(aliases, list) or any(
            not isinstance(a, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", a)
            for a in aliases
        ):
            raise ValueError("Invalid local game aliases")
        for alias in aliases:
            if alias in used:
                raise ValueError(f"Duplicate local game identifier or alias: {alias}")
            used.add(alias)
        fields = {**base, **host_games.get(identifier, {})}
        games.append(
            LocalGamePaths(
                identifier,
                tuple(aliases),
                *(
                    _path(fields.get(field), root)
                    for field in ("install_dir", "original_dir", "translated_dir", "samples_dir")
                ),
            )
        )
    samples = _path(overrides.get("samples_dir", value.get("samples_dir")), root)
    return LocalEnvironment(tuple(games), samples or root / "work/samples")


def resolve_installation(
    identifier: str | None, explicit: Path | None, local_config: Path | None = None
) -> Path:
    """An explicit CLI path wins; local configuration never changes core runtime settings."""
    if explicit is not None:
        return explicit
    if identifier is None:
        raise ValueError("Specify --game-dir or select a game to use local paths")
    game = load_local_environment(local_config).game(identifier)
    if game.install_dir is None:
        raise ValueError(f"No local installation directory configured for game: {identifier}")
    return game.install_dir
