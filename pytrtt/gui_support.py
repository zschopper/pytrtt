"""Read-only installation discovery and inspection shared by graphical clients."""

from __future__ import annotations

import hashlib
import json
import logging
import time
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
LOGGER = logging.getLogger("pytrtt.gui")
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
    RECOVERY_AVAILABLE = "recovery_available"
    TRANSLATION_UNBOUND = "translation_unbound"
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


def find_interrupted_transactions_in_roots(
    roots: tuple[Path, ...],
) -> tuple[tuple[Path, Path], ...]:
    """Collect interrupted writes once when recovery roots overlap."""
    interrupted: list[tuple[Path, Path]] = []
    seen: set[Path] = set()
    for root in roots:
        for game_dir, transaction in find_interrupted_transactions(root):
            identity = transaction.resolve()
            if identity in seen:
                continue
            seen.add(identity)
            interrupted.append((game_dir, transaction))
    return tuple(interrupted)


def _applied_journal_summaries(
    game_dir: Path, roots: tuple[Path, ...]
) -> tuple[tuple[str, str, int, int, int], ...]:
    """Describe matching applied journals without hashing or changing game files."""
    summaries: list[tuple[str, str, int, int, int]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for journal_path in root.rglob("journal.json"):
            identity = journal_path.resolve()
            if identity in seen:
                continue
            seen.add(identity)
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
            backups = value.get("write_backups")
            restore_data = value.get("restore_data", [])
            summaries.append(
                (
                    str(journal_path.parent),
                    "applied",
                    len(files) if isinstance(files, dict) else 0,
                    len(backups) if isinstance(backups, list) else 0,
                    len(restore_data) if isinstance(restore_data, list) else 0,
                )
            )
    return tuple(summaries)


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
    check_started = time.monotonic()
    recovery_checked = False
    recovery_path: Path | None = None

    def recovery_inspection() -> InstallationInspection | None:
        nonlocal recovery_checked, recovery_path
        if not recovery_checked:
            recovery_path = find_restorable_transaction(
                inspection.candidate.path, transaction_roots
            )
            recovery_checked = True
        if recovery_path is None:
            return None
        LOGGER.info(
            "Verified recovery available independently of selected package: game=%s "
            "game_dir=%s transaction=%s",
            inspection.candidate.game.game_id,
            inspection.candidate.path,
            recovery_path,
        )
        if progress is not None:
            progress(3, 3, "gui_progress_complete")
        return InstallationInspection(
            inspection.candidate,
            InstallationStatus.RECOVERY_AVAILABLE,
            inspection.translation_path,
            "verified recovery is available; restore before installing the selected package",
            recovery_path,
        )

    try:
        from pytrtt.composition import create_translation_service
        from pytrtt.packages.translation import parse_translation_document

        LOGGER.info(
            "Translation check started: game=%s build=%s source=%s game_dir=%s "
            "package=%s transaction_roots=%s",
            inspection.candidate.game.game_id,
            inspection.candidate.build_id or "unknown",
            inspection.candidate.source,
            inspection.candidate.path,
            inspection.translation_path,
            transaction_roots,
        )
        if progress is not None:
            progress(0, 3, "gui_progress_package")
        package_bytes = inspection.translation_path.read_bytes()
        package_sha256 = hashlib.sha256(package_bytes).hexdigest()
        LOGGER.debug(
            "Translation package bytes read: path=%s bytes=%d sha256=%s",
            inspection.translation_path,
            len(package_bytes),
            package_sha256,
        )
        document = parse_translation_document(package_bytes.decode("utf-8"))
        LOGGER.info(
            "Translation package loaded: path=%s bytes=%d sha256=%s "
            "game=%s build=%s identity=%s menu_resources=%d subtitle_resources=%d "
            "fonts=%d runtime=%s",
            inspection.translation_path,
            len(package_bytes),
            package_sha256,
            document.metadata.game_id,
            document.metadata.build_id,
            document.entry_identity,
            len(document.menu),
            len(document.subtitles),
            len(document.fonts),
            document.runtime is not None,
        )
        if document.entry_identity != "record":
            if progress is not None:
                progress(3, 3, "gui_progress_complete")
            return InstallationInspection(
                inspection.candidate,
                InstallationStatus.TRANSLATION_UNBOUND,
                inspection.translation_path,
                "translation memory must be bound to extracted records first",
            )
        if progress is not None:
            progress(1, 3, "gui_progress_files")
        service = create_translation_service()
        installed = service.is_translation_installed(
            inspection.candidate.path,
            document,
            package_dir=inspection.translation_path.parent,
            expected_build_id=inspection.candidate.build_id or None,
            progress=(
                (lambda current, total: progress(current, total, "gui_progress_detect_resources"))
                if progress is not None
                else None
            ),
        )
        LOGGER.info(
            "Installed-state comparison complete: game=%s game_dir=%s translated=%s",
            inspection.candidate.game.game_id,
            inspection.candidate.path,
            installed,
        )
        if installed:
            restore_path = find_restorable_transaction(inspection.candidate.path, transaction_roots)
            LOGGER.info(
                "Installed translation has recovery transaction: game=%s game_dir=%s "
                "recovery_path=%s",
                inspection.candidate.game.game_id,
                inspection.candidate.path,
                restore_path,
            )
            if progress is not None:
                progress(3, 3, "gui_progress_complete")
            return InstallationInspection(
                inspection.candidate,
                InstallationStatus.ALREADY_TRANSLATED,
                inspection.translation_path,
                "0",
                restore_path,
            )
        if recovery := recovery_inspection():
            return recovery
        if progress is not None:
            progress(2, 3, "gui_progress_plan")

        def report_plan_resources(current: int, total: int) -> None:
            message = "gui_progress_plan_resources"
            if total > 0 and current >= total:
                message = "gui_progress_plan_finalize"
            if progress is not None:
                progress(current, total, message)

        result = service.plan(
            inspection.candidate.path,
            document,
            package_dir=inspection.translation_path.parent,
            expected_build_id=inspection.candidate.build_id or None,
            progress=report_plan_resources if progress is not None else None,
            planning_progress=progress,
        )
        status = (
            InstallationStatus.ALREADY_TRANSLATED
            if result.plan is None
            else InstallationStatus.CHANGES_AVAILABLE
        )
        detail = str(len(result.missing_translations))
        plan = result.plan
        LOGGER.info(
            "Translation plan ready: game=%s game_dir=%s status=%s missing=%d "
            "plan_present=%s sufficient_space=%s files=%s resource_writes=%d "
            "font_writes=%d elapsed_seconds=%.3f",
            inspection.candidate.game.game_id,
            inspection.candidate.path,
            status.value,
            len(result.missing_translations),
            plan is not None,
            plan.sufficient_space if plan is not None else None,
            sorted(plan.files) if plan is not None else (),
            sum(write.kind == "resource" for write in plan.writes) if plan is not None else 0,
            sum(write.kind == "font" for write in plan.writes) if plan is not None else 0,
            time.monotonic() - check_started,
        )
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
        LOGGER.exception(
            "Translation validation failed: game=%s build=%s source=%s game_dir=%s "
            "package=%s elapsed_seconds=%.3f",
            inspection.candidate.game.game_id,
            inspection.candidate.build_id or "unknown",
            inspection.candidate.source,
            inspection.candidate.path,
            inspection.translation_path,
            time.monotonic() - check_started,
        )
        LOGGER.error(
            "Applied recovery journals at validation failure: game_dir=%s journals=%s",
            inspection.candidate.path,
            _applied_journal_summaries(inspection.candidate.path, transaction_roots),
        )
        if recovery := recovery_inspection():
            return recovery
        return InstallationInspection(
            inspection.candidate,
            InstallationStatus.UNKNOWN_MODIFIED,
            inspection.translation_path,
            str(exc),
        )
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        LOGGER.exception(
            "Translation check failed outside package validation: game=%s build=%s "
            "game_dir=%s package=%s elapsed_seconds=%.3f",
            inspection.candidate.game.game_id,
            inspection.candidate.build_id or "unknown",
            inspection.candidate.path,
            inspection.translation_path,
            time.monotonic() - check_started,
        )
        if recovery := recovery_inspection():
            return recovery
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
            LOGGER.info(
                "Install requested but plan is empty: game=%s game_dir=%s",
                inspection.candidate.game.game_id,
                inspection.candidate.path,
            )
            return check_translation(inspection, transaction_roots=(transaction_root,))
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        transaction = transaction_root / inspection.candidate.game.game_id / stamp
        LOGGER.info(
            "Applying translation: game=%s build=%s game_dir=%s transaction=%s "
            "files=%s writes=%d backup_bytes=%d sufficient_space=%s",
            inspection.candidate.game.game_id,
            inspection.candidate.build_id or "unknown",
            inspection.candidate.path,
            transaction,
            sorted(result.plan.files),
            len(result.plan.writes),
            result.plan.backup_bytes,
            result.plan.sufficient_space,
        )
        if progress is not None:
            progress(2, 4, "gui_progress_install")
        service.apply(result, transaction, progress)
        if progress is not None:
            progress(3, 4, "gui_progress_verify")
        ready = InstallationInspection(
            inspection.candidate,
            InstallationStatus.READY,
            inspection.translation_path,
        )
        checked = check_translation(ready, transaction_roots=(transaction_root,))
        LOGGER.info(
            "Translation apply verification: game=%s transaction=%s status=%s detail=%s "
            "recovery_path=%s",
            inspection.candidate.game.game_id,
            transaction,
            checked.status.value,
            checked.detail,
            checked.restore_path,
        )
        if progress is not None:
            progress(4, 4, "gui_progress_complete")
        return checked
    except (OSError, UnicodeError, ValueError, TypeError, RuntimeError) as exc:
        LOGGER.exception(
            "Translation apply failed: game=%s build=%s game_dir=%s transaction_root=%s",
            inspection.candidate.game.game_id,
            inspection.candidate.build_id or "unknown",
            inspection.candidate.path,
            transaction_root,
        )
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
        restore_started = time.monotonic()
        LOGGER.info(
            "Restoration started: game=%s build=%s game_dir=%s transaction=%s transaction_roots=%s",
            inspection.candidate.game.game_id,
            inspection.candidate.build_id or "unknown",
            inspection.candidate.path,
            restore_path,
            transaction_roots,
        )
        try:
            from pytrtt.composition import create_translation_service

            if progress is not None:
                progress(0, 3, "gui_progress_package")
            if progress is not None:
                progress(1, 3, "gui_progress_restore")
            service = create_translation_service()
            current = restore_path
            restored: set[Path] = set()
            while True:
                # New journals own their runtime; the selected package may have changed or vanished.
                journal = json.loads((current / "journal.json").read_text(encoding="utf-8"))
                runtime = None
                if "runtime" not in journal:
                    from pytrtt.packages.translation import parse_translation_document

                    runtime = parse_translation_document(
                        inspection.translation_path.read_text(encoding="utf-8")
                    ).runtime
                service.restore(
                    inspection.candidate.path,
                    current,
                    runtime,
                    progress,
                )
                restored.add(current.resolve())
                next_transaction = find_restorable_transaction(
                    inspection.candidate.path, transaction_roots or (restore_path.parent,)
                )
                if next_transaction is None:
                    break
                if next_transaction.resolve() in restored:
                    LOGGER.error(
                        "Restoration chain incomplete: game=%s game_dir=%s "
                        "transaction=%s restored_transactions=%s",
                        inspection.candidate.game.game_id,
                        inspection.candidate.path,
                        current,
                        sorted(str(path) for path in restored),
                    )
                    return InstallationInspection(
                        inspection.candidate,
                        InstallationStatus.ERROR,
                        inspection.translation_path,
                        "recovery transaction cycle detected; refusing to restore again",
                    )
                current = next_transaction
            if progress is not None:
                progress(3, 3, "gui_progress_complete")
            LOGGER.info(
                "Restoration complete: game=%s game_dir=%s transactions=%s elapsed_seconds=%.3f",
                inspection.candidate.game.game_id,
                inspection.candidate.path,
                sorted(str(path) for path in restored),
                time.monotonic() - restore_started,
            )
            return InstallationInspection(
                inspection.candidate,
                InstallationStatus.RESTORED,
                inspection.translation_path,
            )
        except (OSError, UnicodeError, ValueError, TypeError, RuntimeError) as exc:
            LOGGER.exception(
                "Restoration failed: game=%s game_dir=%s transaction=%s",
                inspection.candidate.game.game_id,
                inspection.candidate.path,
                restore_path,
            )
            return InstallationInspection(
                inspection.candidate,
                InstallationStatus.ERROR,
                inspection.translation_path,
                f"{type(exc).__name__}: {exc}",
                restore_path,
            )
    LOGGER.warning(
        "Restore requested without a verified recovery transaction: game=%s build=%s "
        "game_dir=%s transaction_roots=%s",
        inspection.candidate.game.game_id,
        inspection.candidate.build_id or "unknown",
        inspection.candidate.path,
        transaction_roots,
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
    safe_exit_requested: bool | Callable[[], bool] = False,
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
    should_exit_safely = (
        safe_exit_requested() if callable(safe_exit_requested) else safe_exit_requested
    )
    if (
        action == "install"
        and should_exit_safely
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
