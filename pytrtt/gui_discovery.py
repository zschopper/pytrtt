"""Declarative game catalog and Steam installation discovery."""

from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Protocol, cast

from pytrtt.packages.translation import TranslationPackageError

CATALOG_PATH = Path(__file__).resolve().parent / "resources" / "gui_games.json"


class RegistryModule(Protocol):
    HKEY_CURRENT_USER: int
    HKEY_LOCAL_MACHINE: int
    KEY_READ: int
    KEY_WOW64_32KEY: int

    def OpenKey(
        self, hive: int, path: str, reserved: int, access: int
    ) -> AbstractContextManager[object]: ...

    def QueryValueEx(self, key: object, name: str) -> tuple[object, int]: ...


@dataclass(frozen=True, slots=True)
class GameCatalogEntry:
    game_id: str
    display_name: str
    steam_app_id: str
    install_dir_name: str
    translation_file: Path
    package_available: bool = False


@dataclass(frozen=True, slots=True)
class InstallationCandidate:
    game: GameCatalogEntry
    path: Path
    source: str
    build_id: str = ""


def installation_choices(
    candidates: tuple[InstallationCandidate, ...], game_id: str
) -> dict[str, InstallationCandidate]:
    """Keep separate folder choices for every installation of one game."""
    return {str(item.path): item for item in candidates if item.game.game_id == game_id}


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid GUI game catalog field: {field}")
    return value


def load_game_catalog(path: Path = CATALOG_PATH) -> tuple[GameCatalogEntry, ...]:
    """Load the declarative list shown by the graphical client."""
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("GUI game catalog must be an array")
    games = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "game_id",
            "display_name",
            "steam_app_id",
            "install_dir_name",
            "translation_file",
            "package_available",
        }:
            raise ValueError("invalid GUI game catalog entry")
        relative = Path(_required_text(item["translation_file"], "translation_file"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("translation_file must be a safe relative path")
        package_available = item["package_available"]
        if type(package_available) is not bool:
            raise ValueError("package_available must be a boolean")
        games.append(
            GameCatalogEntry(
                _required_text(item["game_id"], "game_id"),
                _required_text(item["display_name"], "display_name"),
                _required_text(item["steam_app_id"], "steam_app_id"),
                _required_text(item["install_dir_name"], "install_dir_name"),
                relative,
                package_available,
            )
        )
    if len({game.game_id for game in games}) != len(games):
        raise ValueError("duplicate game_id in GUI game catalog")
    return tuple(games)


def validate_packaged_catalog(
    games: tuple[GameCatalogEntry, ...], project_root: Path
) -> tuple[str, ...]:
    """Validate packages explicitly selected for a distributable release."""
    from pytrtt.packages.translation import parse_translation_document

    root = project_root.resolve(strict=True)
    errors = []
    for game in games:
        if not game.package_available:
            continue
        package = (root / game.translation_file).resolve(strict=False)
        if root not in package.parents or not package.is_file():
            errors.append(f"{game.game_id}: translation package is missing")
            continue
        try:
            document = parse_translation_document(package.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TranslationPackageError) as exc:
            errors.append(f"{game.game_id}: invalid translation package: {exc}")
            continue
        if document.metadata.game_id != game.game_id:
            errors.append(f"{game.game_id}: package metadata targets {document.metadata.game_id}")
            continue
        package_root = package.parent.resolve(strict=True)
        for font in document.fonts:
            relative = PurePosixPath(font.replacement_file)
            asset = package_root.joinpath(*relative.parts).resolve(strict=False)
            if package_root not in asset.parents or not asset.is_file():
                errors.append(f"{game.game_id}: font asset is missing: {font.replacement_file}")
                continue
            if hashlib.sha256(asset.read_bytes()).hexdigest() != font.replacement_sha256:
                errors.append(f"{game.game_id}: font asset hash mismatch: {font.replacement_file}")
    return tuple(errors)


def default_steam_roots() -> tuple[Path, ...]:
    """Return plausible Steam roots without touching the registry or the network."""
    roots: list[Path] = []
    for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value) / "Steam")
    if os.name == "nt":
        roots.extend(registry_steam_roots())
    if os.name != "nt":
        roots.extend((Path.home() / ".steam/steam", Path.home() / ".local/share/Steam"))
    return tuple(dict.fromkeys(roots))


def registry_steam_roots(registry: RegistryModule | None = None) -> tuple[Path, ...]:
    """Read Steam installation roots from the Windows registry when available."""
    if registry is None:
        if os.name != "nt":
            return ()
        import winreg

        active_registry = cast(RegistryModule, winreg)
    else:
        active_registry = registry
    locations = (
        (active_registry.HKEY_CURRENT_USER, r"Software\Valve\Steam", 0),
        (
            active_registry.HKEY_LOCAL_MACHINE,
            r"Software\Valve\Steam",
            active_registry.KEY_WOW64_32KEY,
        ),
    )
    roots: list[Path] = []
    seen: set[str] = set()
    for hive, key_path, view in locations:
        try:
            with active_registry.OpenKey(hive, key_path, 0, active_registry.KEY_READ | view) as key:
                for name in ("SteamPath", "InstallPath", "SteamExe"):
                    try:
                        raw, _kind = active_registry.QueryValueEx(key, name)
                    except OSError:
                        continue
                    if not isinstance(raw, str) or not raw.strip():
                        continue
                    windows_path = PureWindowsPath(raw)
                    if name == "SteamExe":
                        windows_path = windows_path.parent
                    value = Path(str(windows_path))
                    normalized = str(value).casefold()
                    if normalized not in seen:
                        seen.add(normalized)
                        roots.append(value)
        except OSError:
            continue
    return tuple(roots)


def _vdf_pairs(text: str) -> dict[str, str]:
    return {
        key.casefold(): value.replace("\\\\", "\\")
        for key, value in re.findall(r'"([^"\\]+)"\s+"((?:\\.|[^"\\])*)"', text)
    }


def _steam_libraries(root: Path) -> tuple[Path, ...]:
    libraries = [root]
    library_file = root / "steamapps/libraryfolders.vdf"
    try:
        text = library_file.read_text(encoding="utf-8-sig")
    except OSError:
        return tuple(libraries)
    for value in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', text, re.IGNORECASE):
        path = Path(value.replace("\\\\", "\\"))
        if path not in libraries:
            libraries.append(path)
    return tuple(libraries)


def discover_steam_installations(
    games: tuple[GameCatalogEntry, ...],
    steam_roots: tuple[Path, ...] | None = None,
) -> tuple[InstallationCandidate, ...]:
    """Discover complete Steam installations from their manifests."""
    by_app_id = {game.steam_app_id: game for game in games}
    candidates: list[InstallationCandidate] = []
    seen: set[tuple[str, Path]] = set()
    for root in steam_roots if steam_roots is not None else default_steam_roots():
        for library in _steam_libraries(root):
            steamapps = library / "steamapps"
            for app_id, game in by_app_id.items():
                manifest = steamapps / f"appmanifest_{app_id}.acf"
                try:
                    fields = _vdf_pairs(manifest.read_text(encoding="utf-8-sig"))
                    complete = int(fields.get("stateflags", "0")) & 4
                except (OSError, UnicodeError, ValueError):
                    continue
                install_dir = fields.get("installdir", game.install_dir_name)
                path = steamapps / "common" / install_dir
                key = (game.game_id, path)
                if complete and path.is_dir() and key not in seen:
                    seen.add(key)
                    candidates.append(
                        InstallationCandidate(
                            game,
                            path,
                            "Steam",
                            fields.get("buildid", ""),
                        )
                    )
    return tuple(candidates)
