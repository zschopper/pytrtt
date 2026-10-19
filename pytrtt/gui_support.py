"""Read-only installation discovery and inspection shared by graphical clients."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Protocol, cast

from pytrtt.archives.transaction import journal_data_dir_matches
from pytrtt.packages.translation import TranslationDocument, TranslationPackageError
from pytrtt.services.translation import TranslationBuild

CATALOG_PATH = Path(__file__).resolve().parent / "resources" / "gui_games.json"
ProgressCallback = Callable[[int, int, str], None]


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


class InstallationStatus(Enum):
    NOT_FOUND = "not_found"
    PACKAGE_UNAVAILABLE = "package_unavailable"
    READY = "ready"
    CHANGES_AVAILABLE = "changes_available"
    ALREADY_TRANSLATED = "already_translated"
    UNKNOWN_MODIFIED = "unknown_modified"
    RESTORED = "restored"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class InstallationInspection:
    candidate: InstallationCandidate
    status: InstallationStatus
    translation_path: Path
    detail: str = ""
    restore_path: Path | None = None
    prepared: PreparedTranslation | None = None


@dataclass(frozen=True, slots=True)
class PreparedTranslation:
    """Validated document and write plan retained between GUI check and apply."""

    document: TranslationDocument
    build: TranslationBuild


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


def inspect_installation(
    candidate: InstallationCandidate, *, project_root: Path
) -> InstallationInspection:
    """Perform the inexpensive checks used before a translation dry run."""
    translation_path = project_root / candidate.game.translation_file
    if not candidate.path.is_dir():
        status = InstallationStatus.NOT_FOUND
    elif not translation_path.is_file():
        status = InstallationStatus.PACKAGE_UNAVAILABLE
    else:
        status = InstallationStatus.READY
    return InstallationInspection(candidate, status, translation_path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _has_verified_restore_payloads(transaction: Path, journal: dict[object, object]) -> bool:
    """Return whether every journaled recovery payload is present and intact."""
    payload_groups = (
        (journal.get("write_backups"), "backup_file", "length", Path("backups")),
        (
            journal.get("restore_data", []),
            "resource_path",
            "size",
            Path("backups/restore-data"),
        ),
    )
    for records, path_field, size_field, base in payload_groups:
        if not isinstance(records, list):
            return False
        for record in records:
            if not isinstance(record, dict):
                return False
            name = record.get(path_field)
            size = record.get(size_field)
            expected_hash = record.get("sha256")
            if (
                not isinstance(name, str)
                or not isinstance(size, int)
                or not isinstance(expected_hash, str)
            ):
                return False
            relative = PurePosixPath(name)
            if (
                not name
                or "\\" in name
                or relative.is_absolute()
                or PureWindowsPath(name).drive
                or ".." in relative.parts
            ):
                return False
            payload = transaction / base / Path(*relative.parts)
            try:
                if payload.stat().st_size != size or _file_sha256(payload) != expected_hash:
                    return False
            except OSError:
                return False
    return True


def find_restorable_transaction(game_dir: Path, roots: tuple[Path, ...]) -> Path | None:
    """Find an applied journal that can safely restore the current complete file state."""
    for root in roots:
        if not root.is_dir():
            continue
        for journal_path in root.rglob("journal.json"):
            try:
                value: object = json.loads(journal_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if (
                not isinstance(value, dict)
                or value.get("status") != "applied"
                or not journal_data_dir_matches(value.get("data_dir"), game_dir.resolve())
            ):
                continue
            files = value.get("files")
            if not isinstance(files, dict) or not files:
                continue
            if not _has_verified_restore_payloads(journal_path.parent, value):
                continue
            safe = True
            for name, record in files.items():
                if not isinstance(name, str) or not isinstance(record, dict):
                    safe = False
                    break
                relative = PurePosixPath(name.replace("\\", "/"))
                if relative.is_absolute() or ".." in relative.parts:
                    safe = False
                    break
                target = game_dir.joinpath(*relative.parts)
                expected = record.get("staged_sha256")
                if (
                    not isinstance(expected, str)
                    or not target.is_file()
                    or _file_sha256(target) != expected
                ):
                    safe = False
                    break
            if safe:
                return journal_path.parent
    return None


def find_interrupted_transactions(root: Path) -> tuple[tuple[Path, Path], ...]:
    """Find journaled writes that may have left an installation in a mixed state."""
    interrupted: list[tuple[Path, Path]] = []
    if not root.is_dir():
        return ()
    for journal_path in root.rglob("journal.json"):
        try:
            value: object = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or value.get("status") not in {"applying", "restoring"}:
            continue
        data_dir = value.get("data_dir")
        if isinstance(data_dir, str) and data_dir:
            interrupted.append((Path(data_dir), journal_path.parent))
    return tuple(interrupted)


def recover_interrupted_transaction(game_dir: Path, transaction: Path) -> None:
    """Resume the journal's idempotent restoration path."""
    from pytrtt.composition import create_translation_service

    create_translation_service().restore(game_dir, transaction)


def check_translation(
    inspection: InstallationInspection,
    *,
    transaction_roots: tuple[Path, ...] = (),
    progress: ProgressCallback | None = None,
) -> InstallationInspection:
    """Run the existing translation planner without modifying the installation."""
    if inspection.status is not InstallationStatus.READY:
        return inspection
    try:
        from pytrtt.composition import create_translation_service
        from pytrtt.packages.translation import parse_translation_document

        if progress is not None:
            progress(0, 3, "gui_progress_package")
        document = parse_translation_document(
            inspection.translation_path.read_text(encoding="utf-8")
        )
        if progress is not None:
            progress(1, 3, "gui_progress_files")
        service = create_translation_service()
        if service.is_translation_installed(
            inspection.candidate.path,
            document,
            package_dir=inspection.translation_path.parent,
            progress=(
                (lambda current, total: progress(current, total, "gui_progress_detect_resources"))
                if progress is not None
                else None
            ),
        ):
            restore_path = find_restorable_transaction(inspection.candidate.path, transaction_roots)
            if progress is not None:
                progress(3, 3, "gui_progress_complete")
            return InstallationInspection(
                inspection.candidate,
                InstallationStatus.ALREADY_TRANSLATED,
                inspection.translation_path,
                "0",
                restore_path,
            )
        if progress is not None:
            progress(2, 3, "gui_progress_plan")
        result = service.plan(
            inspection.candidate.path,
            document,
            package_dir=inspection.translation_path.parent,
            expected_build_id=inspection.candidate.build_id or None,
            progress=(
                (lambda current, total: progress(current, total, "gui_progress_plan_resources"))
                if progress is not None
                else None
            ),
        )
        status = (
            InstallationStatus.ALREADY_TRANSLATED
            if result.plan is None
            else InstallationStatus.CHANGES_AVAILABLE
        )
        detail = str(len(result.missing_translations))
        if progress is not None:
            progress(3, 3, "gui_progress_complete")
        return InstallationInspection(
            inspection.candidate,
            status,
            inspection.translation_path,
            detail,
            prepared=PreparedTranslation(document, result),
        )
    except TranslationPackageError as exc:
        return InstallationInspection(
            inspection.candidate,
            InstallationStatus.UNKNOWN_MODIFIED,
            inspection.translation_path,
            str(exc),
        )
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return InstallationInspection(
            inspection.candidate,
            InstallationStatus.ERROR,
            inspection.translation_path,
            f"{type(exc).__name__}: {exc}",
        )


def apply_translation(
    inspection: InstallationInspection,
    *,
    transaction_root: Path,
    progress: ProgressCallback | None = None,
) -> InstallationInspection:
    """Plan and apply a translation, then return its newly inspected state."""
    if inspection.status is not InstallationStatus.CHANGES_AVAILABLE:
        return InstallationInspection(
            inspection.candidate,
            InstallationStatus.ERROR,
            inspection.translation_path,
            "the installation is not ready to translate",
        )
    try:
        from pytrtt.composition import create_translation_service

        prepared = inspection.prepared
        if prepared is None:
            return InstallationInspection(
                inspection.candidate,
                InstallationStatus.ERROR,
                inspection.translation_path,
                "the checked translation plan is unavailable",
            )
        service = create_translation_service()
        result = prepared.build
        if result.plan is None:
            return check_translation(inspection, transaction_roots=(transaction_root,))
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        transaction = transaction_root / inspection.candidate.game.game_id / stamp
        if progress is not None:
            progress(2, 4, "gui_progress_install")
        service.apply(result, transaction)
        if progress is not None:
            progress(3, 4, "gui_progress_verify")
        ready = InstallationInspection(
            inspection.candidate,
            InstallationStatus.READY,
            inspection.translation_path,
        )
        checked = check_translation(ready, transaction_roots=(transaction_root,))
        if progress is not None:
            progress(4, 4, "gui_progress_complete")
        return checked
    except (OSError, UnicodeError, ValueError, TypeError, RuntimeError) as exc:
        return InstallationInspection(
            inspection.candidate,
            InstallationStatus.ERROR,
            inspection.translation_path,
            f"{type(exc).__name__}: {exc}",
        )


def restore_translation(
    inspection: InstallationInspection,
    *,
    transaction_roots: tuple[Path, ...] = (),
    progress: ProgressCallback | None = None,
) -> InstallationInspection:
    """Restore using the exact applicable journal selected during status inspection."""
    if restore_path := inspection.restore_path:
        try:
            from pytrtt.composition import create_translation_service
            from pytrtt.packages.translation import parse_translation_document

            if progress is not None:
                progress(0, 3, "gui_progress_package")
            document = parse_translation_document(
                inspection.translation_path.read_text(encoding="utf-8")
            )
            if progress is not None:
                progress(1, 3, "gui_progress_restore")
            service = create_translation_service()
            current = restore_path
            restored: set[Path] = set()
            while True:
                service.restore(inspection.candidate.path, current, document.runtime)
                restored.add(current.resolve())
                if not service.is_translation_installed(
                    inspection.candidate.path,
                    document,
                    package_dir=inspection.translation_path.parent,
                ):
                    break
                next_transaction = find_restorable_transaction(
                    inspection.candidate.path, transaction_roots
                )
                if next_transaction is None or next_transaction.resolve() in restored:
                    return InstallationInspection(
                        inspection.candidate,
                        InstallationStatus.ERROR,
                        inspection.translation_path,
                        "the translation is still installed but no earlier safe "
                        "transaction is available",
                    )
                current = next_transaction
            if progress is not None:
                progress(3, 3, "gui_progress_complete")
            return InstallationInspection(
                inspection.candidate,
                InstallationStatus.RESTORED,
                inspection.translation_path,
            )
        except (OSError, UnicodeError, ValueError, TypeError, RuntimeError) as exc:
            return InstallationInspection(
                inspection.candidate,
                InstallationStatus.ERROR,
                inspection.translation_path,
                f"{type(exc).__name__}: {exc}",
                restore_path,
            )
    return InstallationInspection(
        inspection.candidate,
        InstallationStatus.ERROR,
        inspection.translation_path,
        "no safe restore transaction is available",
    )


def run_translation_operation(
    inspection: InstallationInspection,
    action: str,
    *,
    transaction_root: Path,
    transaction_roots: tuple[Path, ...],
    safe_exit_requested: bool = False,
    progress: ProgressCallback | None = None,
) -> tuple[InstallationInspection, bool]:
    """Run one GUI operation and complete a requested post-install safe exit."""
    if action == "restore":
        result = restore_translation(
            inspection,
            transaction_roots=transaction_roots,
            progress=progress,
        )
    elif action == "install":
        result = apply_translation(
            inspection,
            transaction_root=transaction_root,
            progress=progress,
        )
    else:
        result = check_translation(
            inspection,
            transaction_roots=transaction_roots,
            progress=progress,
        )
    if (
        action == "install"
        and safe_exit_requested
        and result.status is InstallationStatus.ALREADY_TRANSLATED
        and result.restore_path is not None
    ):
        return (
            restore_translation(
                result,
                transaction_roots=transaction_roots,
                progress=progress,
            ),
            True,
        )
    return result, False
