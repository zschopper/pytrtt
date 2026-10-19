"""Read-only installation discovery and inspection shared by graphical clients."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath

from pytrtt import gui_discovery as _discovery
from pytrtt.archives.transaction import journal_data_dir_matches
from pytrtt.packages.translation import TranslationDocument, TranslationPackageError
from pytrtt.services.translation import TranslationBuild

ProgressCallback = Callable[[int, int, str], None]
GameCatalogEntry = _discovery.GameCatalogEntry
InstallationCandidate = _discovery.InstallationCandidate
discover_steam_installations = _discovery.discover_steam_installations
installation_choices = _discovery.installation_choices
load_game_catalog = _discovery.load_game_catalog
registry_steam_roots = _discovery.registry_steam_roots
validate_packaged_catalog = _discovery.validate_packaged_catalog


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
