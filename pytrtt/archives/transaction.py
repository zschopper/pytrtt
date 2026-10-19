"""Journaled execution and restoration for a Bigfile write plan."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from pytrtt.archives.contracts import ArchiveWritePlan

FILE_NAME = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.[0-9]{3}(?:\.tiger)?\Z")
JOURNAL_NAME = "journal.json"
JOURNAL_VERSION = 2


class TransactionError(RuntimeError):
    """Raised when a write plan cannot be safely applied or restored."""


def _acquire_descriptor(descriptor: int) -> None:
    if os.name == "nt":
        msvcrt_module: Any = __import__("msvcrt")
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            msvcrt_module.locking(descriptor, msvcrt_module.LK_NBLCK, 1)
        except OSError as exc:
            raise TransactionError("another write operation is active for this directory") from exc
    else:
        import fcntl

        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise TransactionError("another write operation is active for this directory") from exc


def _release_descriptor(descriptor: int) -> None:
    if os.name == "nt":
        msvcrt_module: Any = __import__("msvcrt")
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt_module.locking(descriptor, msvcrt_module.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_UN)


@contextmanager
def _operation_lock(data_root: Path) -> Iterator[None]:
    """Acquire a cross-process lock without placing lock files in the game directory."""
    lock_dir = Path(tempfile.gettempdir()) / "pytrtt-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_key = str(data_root)
    if os.name == "nt":
        lock_key = os.path.normcase(lock_key)
    lock_name = hashlib.sha256(os.fsencode(lock_key)).hexdigest() + ".lock"
    lock_path = lock_dir / lock_name
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        _acquire_descriptor(descriptor)
        try:
            yield
        finally:
            _release_descriptor(descriptor)
    finally:
        os.close(descriptor)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _replace_target(source: Path, target: Path) -> None:
    os.replace(source, target)


def _write_journal(transaction_dir: Path, journal: dict[str, Any]) -> None:
    temporary = transaction_dir / f"{JOURNAL_NAME}.tmp"
    payload = json.dumps(journal, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, transaction_dir / JOURNAL_NAME)
    _fsync_directory(transaction_dir)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _copy_to_target(source: Path, target: Path) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".pytrtt-restore-", dir=target.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        shutil.copymode(source, temporary)
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        _replace_target(temporary, target)
        _fsync_directory(target.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_roots(data_dir: Path, transaction_dir: Path) -> tuple[Path, Path]:
    try:
        data_root = data_dir.resolve(strict=True)
    except OSError as exc:
        raise TransactionError(f"game data directory is unavailable: {exc}") from exc
    if not data_root.is_dir():
        raise TransactionError("game data path is not a directory")
    transaction_root = transaction_dir.resolve(strict=False)
    if transaction_root == data_root or data_root in transaction_root.parents:
        raise TransactionError("transaction directory must be outside the game data directory")
    return data_root, transaction_root


def _target_path(data_root: Path, name: str) -> Path:
    if FILE_NAME.fullmatch(name) is None:
        raise TransactionError(f"unsafe archive file name in journal: {name!r}")
    target = data_root / name
    if target.is_symlink():
        raise TransactionError(f"archive target is a symbolic link: {name}")
    return target


def _backup_path(transaction_root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (
        "\\" in name
        or relative.is_absolute()
        or PureWindowsPath(name).drive
        or ".." in relative.parts
    ):
        raise TransactionError(f"unsafe backup file name in journal: {name!r}")
    target = transaction_root / "backups" / Path(*relative.parts)
    if transaction_root not in target.resolve(strict=False).parents:
        raise TransactionError(f"backup path escapes transaction directory: {name!r}")
    return target


def _apply_write_plan_locked(
    data_dir: Path,
    plan: ArchiveWritePlan,
    transaction_dir: Path,
    runtime_settings: dict[str, Any] | None = None,
) -> Path:
    """Back up, stage, journal, and apply a plan; return the journal directory."""
    data_root, transaction_root = _validate_roots(data_dir, transaction_dir)
    if transaction_root.exists():
        raise TransactionError("transaction directory already exists")
    try:
        plan.validate_inputs(data_root)
    except ValueError as exc:
        raise TransactionError(str(exc)) from exc
    transaction_root.parent.mkdir(parents=True, exist_ok=True)
    if plan.files.keys() != {write.file_name for write in plan.writes}:
        raise TransactionError("write plan file list does not match its writes")
    if any(
        file.original_size < 0 or file.final_size < file.original_size or file.final_size < 0
        for file in plan.files.values()
    ):
        raise TransactionError("write plan contains invalid file sizes")
    for write in plan.writes:
        file_plan = plan.files[write.file_name]
        if write.offset < 0 or write.offset + len(write.data) > file_plan.final_size:
            raise TransactionError(f"write plan range exceeds {write.file_name}")
    indexes = plan.index_data
    index_writes = [write for write in plan.writes if write.kind == "index"]
    if (
        not indexes
        or len(index_writes) != len(indexes)
        or {write.file_name for write in index_writes} != indexes.keys()
    ):
        raise TransactionError("write plan must contain one write per archive index")
    if any(write.offset != 0 or write.data != indexes[write.file_name] for write in index_writes):
        raise TransactionError("write plan index bytes do not match the planned index")

    backup_bytes = plan.backup_bytes
    staging_bytes = sum(file.final_size for file in plan.files.values())
    data_free = shutil.disk_usage(data_root).free
    transaction_free = shutil.disk_usage(transaction_root.parent).free
    same_volume = data_root.stat().st_dev == transaction_root.parent.stat().st_dev
    if same_volume:
        required = backup_bytes + staging_bytes * 2
        if data_free < required:
            raise TransactionError(
                "insufficient free space for backups, staging, and atomic replacement"
            )
    elif transaction_free < backup_bytes or data_free < staging_bytes * 2:
        raise TransactionError("insufficient free space on the game or transaction volume")

    for name, file_plan in plan.files.items():
        target = _target_path(data_root, name)
        if file_plan.original_sha256 is None:
            if target.exists():
                raise TransactionError(f"{name} appeared after planning")
        elif not target.is_file() or target.stat().st_size != file_plan.original_size:
            raise TransactionError(f"{name} changed after planning")
        elif _sha256(target) != file_plan.original_sha256:
            raise TransactionError(f"{name} changed after planning")

    transaction_root.mkdir(parents=True)
    backups_dir = transaction_root / "backups"
    staged_dir = transaction_root / "staged"
    (backups_dir / "ranges").mkdir(parents=True)
    staged_dir.mkdir()
    file_records: dict[str, dict[str, Any]] = {}

    for name, file_plan in sorted(plan.files.items()):
        target = _target_path(data_root, name)
        staged = staged_dir / name
        existed = file_plan.original_sha256 is not None
        if existed:
            shutil.copy2(target, staged)
        else:
            staged.touch()

        with staged.open("r+b") as stream:
            for write in plan.writes:
                if write.file_name == name:
                    stream.seek(write.offset)
                    stream.write(write.data)
            stream.truncate(file_plan.final_size)
            stream.flush()
            os.fsync(stream.fileno())
        if staged.stat().st_size != file_plan.final_size:
            raise TransactionError(f"staged size verification failed for {name}")
        file_records[name] = {
            "existed": existed,
            "original_size": file_plan.original_size,
            "original_sha256": file_plan.original_sha256,
            "original_mode": (target.stat().st_mode & 0o777) if existed else None,
            "staged_size": file_plan.final_size,
            "staged_sha256": _sha256(staged),
        }

    range_records: list[dict[str, Any]] = []
    restore_records: list[dict[str, Any]] = []
    restore_assets: dict[str, bytes] = {}
    for write in plan.writes:
        if write.restore_file is None:
            continue
        if write.resource_original is None:
            raise TransactionError("restore asset is missing its original resource bytes")
        asset_name = f"restore-data/{write.restore_file}"
        asset_path = _backup_path(transaction_root, asset_name)
        if asset_path.exists() or asset_name in restore_assets:
            raise TransactionError(f"duplicate restore asset path: {write.restore_file}")
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(write.resource_original)
        restore_assets[asset_name] = write.resource_original
        restore_records.append(
            {
                "resource_path": write.restore_file,
                "size": len(write.resource_original),
                "sha256": hashlib.sha256(write.resource_original).hexdigest(),
            }
        )

    range_number = 0
    for write in plan.writes:
        if write.restore_file is not None:
            asset_name = f"restore-data/{write.restore_file}"
            if (
                write.resource_original_file_name == write.file_name
                and write.resource_original_offset == write.offset
            ):
                payload = restore_assets[asset_name]
                range_records.append(
                    {
                        "file_name": write.file_name,
                        "offset": write.offset,
                        "backup_file": asset_name,
                        "length": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
                tail = write.original_data[len(payload) :]
                tail_offset = write.offset + len(payload)
                if tail:
                    range_name = f"ranges/{range_number:06d}.bin"
                    range_number += 1
                    _backup_path(transaction_root, range_name).write_bytes(tail)
                    range_records.append(
                        {
                            "file_name": write.file_name,
                            "offset": tail_offset,
                            "backup_file": range_name,
                            "length": len(tail),
                            "sha256": hashlib.sha256(tail).hexdigest(),
                        }
                    )
                continue
        if not write.original_data:
            continue
        range_name = f"ranges/{range_number:06d}.bin"
        range_number += 1
        _backup_path(transaction_root, range_name).write_bytes(write.original_data)
        range_records.append(
            {
                "file_name": write.file_name,
                "offset": write.offset,
                "backup_file": range_name,
                "length": len(write.original_data),
                "sha256": hashlib.sha256(write.original_data).hexdigest(),
            }
        )

    for name, index_data in indexes.items():
        with (staged_dir / name).open("rb") as stream:
            if stream.read(len(index_data)) != index_data:
                raise TransactionError("staged archive index verification failed")

    journal: dict[str, Any] = {
        "version": JOURNAL_VERSION,
        "data_dir": str(data_root),
        "status": "prepared",
        "files": file_records,
        "write_backups": range_records,
        "restore_data": restore_records,
    }
    if runtime_settings is not None:
        journal["runtime"] = runtime_settings
    _write_journal(transaction_root, journal)
    journal["status"] = "applying"
    _write_journal(transaction_root, journal)

    for name, record in sorted(file_records.items()):
        target = _target_path(data_root, name)
        current_hash = _sha256(target) if target.is_file() else None
        if current_hash == record["staged_sha256"]:
            continue
        if current_hash != record["original_sha256"]:
            raise TransactionError(f"{name} changed during installation")
        staged = staged_dir / name
        if _sha256(staged) != record["staged_sha256"]:
            raise TransactionError(f"staged file verification failed for {name}")
        _copy_to_target(staged, target)

    journal["status"] = "applied"
    _write_journal(transaction_root, journal)
    return transaction_root


def apply_write_plan(
    data_dir: Path,
    plan: ArchiveWritePlan,
    transaction_dir: Path,
    *,
    runtime_settings: dict[str, Any] | None = None,
) -> Path:
    """Apply a plan while holding the per-installation process lock."""
    data_root, _ = _validate_roots(data_dir, transaction_dir)
    with _operation_lock(data_root):
        return _apply_write_plan_locked(data_root, plan, transaction_dir, runtime_settings)


def _restore_write_plan_locked(data_dir: Path, transaction_dir: Path) -> None:
    """Rebuild original archives from backed-up changed ranges and the original sizes."""
    data_root, transaction_root = _validate_roots(data_dir, transaction_dir)
    journal_path = transaction_root / JOURNAL_NAME
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TransactionError(f"cannot read transaction journal: {exc}") from exc
    if journal.get("version") != JOURNAL_VERSION:
        raise TransactionError("unsupported transaction journal version")
    if not journal_data_dir_matches(journal.get("data_dir"), data_root):
        raise TransactionError("transaction journal belongs to a different game directory")
    if journal.get("status") == "restored":
        return
    records = journal.get("files")
    if not isinstance(records, dict) or not records:
        raise TransactionError("transaction journal has no file records")

    range_records = journal.get("write_backups")
    if not isinstance(range_records, list):
        raise TransactionError("transaction journal has no range backups")
    for item in range_records:
        if not isinstance(item, dict):
            raise TransactionError("transaction journal contains an invalid range backup")
        backup = _backup_path(transaction_root, item.get("backup_file", ""))
        try:
            valid = backup.stat().st_size == item.get("length") and _sha256(backup) == item.get(
                "sha256"
            )
        except OSError:
            valid = False
        if not valid:
            raise TransactionError("range backup verification failed")

    restore_records = journal.get("restore_data", [])
    if not isinstance(restore_records, list):
        raise TransactionError("transaction journal contains invalid restore data")
    for item in restore_records:
        if not isinstance(item, dict):
            raise TransactionError("transaction journal contains invalid restore data")
        backup = _backup_path(transaction_root, f"restore-data/{item.get('resource_path', '')}")
        try:
            valid = backup.stat().st_size == item.get("size") and _sha256(backup) == item.get(
                "sha256"
            )
        except OSError:
            valid = False
        if not valid:
            raise TransactionError("restore asset verification failed")

    restore_staging = transaction_root / "staged" / "restore"
    restore_staging.mkdir(exist_ok=True)
    restore_targets: dict[str, Path] = {}
    for name, record in records.items():
        target = _target_path(data_root, name)
        current_hash = _sha256(target) if target.is_file() else None
        original_hash = record.get("original_sha256")
        staged_hash = record.get("staged_sha256")
        if record.get("existed"):
            if current_hash not in (original_hash, staged_hash):
                raise TransactionError(f"{name} has unexpected content; refusing to restore")
        elif current_hash not in (None, staged_hash):
            raise TransactionError(f"{name} has unexpected content; refusing to restore")

        if record.get("existed") and current_hash != original_hash:
            restored = restore_staging / name
            restored.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, restored)
            with restored.open("r+b") as stream:
                for item in range_records:
                    if item.get("file_name") != name:
                        continue
                    backup = _backup_path(transaction_root, item["backup_file"])
                    payload = backup.read_bytes()
                    stream.seek(item["offset"])
                    stream.write(payload)
                stream.truncate(record["original_size"])
                stream.flush()
                os.fsync(stream.fileno())
            if _sha256(restored) != original_hash:
                raise TransactionError(f"range backups do not reconstruct original {name}")
            restore_targets[name] = restored

    journal["status"] = "restoring"
    _write_journal(transaction_root, journal)
    for name, record in sorted(records.items()):
        target = _target_path(data_root, name)
        current_hash = _sha256(target) if target.is_file() else None
        original_hash = record.get("original_sha256")
        staged_hash = record.get("staged_sha256")
        if record.get("existed"):
            if current_hash == original_hash:
                continue
            restored = restore_targets.get(name)
            if restored is None:
                raise TransactionError(f"restore staging is missing for {name}")
            _copy_to_target(restored, target)
        else:
            if current_hash is None:
                continue
            if current_hash != staged_hash:
                raise TransactionError(f"{name} has unexpected content; refusing to restore")
            target.unlink()
            _fsync_directory(data_root)

    journal["status"] = "restored"
    _write_journal(transaction_root, journal)


def restore_write_plan(data_dir: Path, transaction_dir: Path) -> None:
    """Restore a plan while holding the per-installation process lock."""
    data_root, _ = _validate_roots(data_dir, transaction_dir)
    with _operation_lock(data_root):
        _restore_write_plan_locked(data_root, transaction_dir)


def journal_data_dir_matches(recorded: object, current: Path) -> bool:
    """Match a Windows path with the same drive mounted below /mnt in WSL."""
    if not isinstance(recorded, str):
        return False

    def key(value: str) -> str:
        normalized = value.replace("\\", "/").rstrip("/")
        drive = re.fullmatch(r"([A-Za-z]):/(.*)", normalized)
        if drive is not None:
            normalized = f"/mnt/{drive.group(1).lower()}/{drive.group(2)}"
        if normalized.startswith("//") or re.match(r"/mnt/[A-Za-z]/", normalized):
            return normalized.casefold()
        return normalized

    return key(recorded) == key(str(current))
