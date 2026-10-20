"""Tests for journaled, reversible Bigfile plan execution."""

from __future__ import annotations

import hashlib
import json
import stat
import struct
from pathlib import Path

import pytest

from pytrtt.archives import transaction
from pytrtt.archives.bigfile_v1 import BigFileEntry, BigFileIndex
from pytrtt.archives.write_plan import (
    BigFileReplacement,
    BigFileWritePlan,
    plan_replacements,
    serialize_bigfile_index,
)


def make_fixture(tmp_path: Path) -> tuple[Path, Path, bytes]:
    data_dir = tmp_path / "game-data"
    data_dir.mkdir()
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    index_bytes = (
        struct.pack("<I", 1)
        + struct.pack("<I", entry.hash)
        + struct.pack("<4I", entry.length, entry.location, entry.locale, entry.unknown)
    )
    original = bytearray(0x2000)
    original[: len(index_bytes)] = index_bytes
    original[0x1000:0x1008] = b"original"
    archive = data_dir / "bigfile.000"
    archive.write_bytes(original)
    archive.chmod(0o640)
    return data_dir, tmp_path / "transaction-001", bytes(original)


class GenericWritePlan:
    """Protocol-only plan proving transaction execution is not type-dispatched."""

    def __init__(self, plan: BigFileWritePlan) -> None:
        self.writes = plan.writes
        self.files = plan.files
        self.index_data = {"bigfile.000": serialize_bigfile_index(plan.index)}
        self.backup_bytes = plan.backup_bytes
        self.sufficient_space = plan.sufficient_space

    def validate_inputs(self, _directory: Path) -> None:
        raise ValueError("generic source changed")


def test_journal_path_matches_same_windows_drive_mounted_in_wsl() -> None:
    assert transaction.journal_data_dir_matches(
        r"L:\SteamLibrary\steamapps\common\Tomb Raider Anniversary",
        Path("/mnt/l/SteamLibrary/steamapps/common/Tomb Raider Anniversary"),
    )


def test_transaction_uses_the_write_plan_protocol_for_input_validation(tmp_path: Path) -> None:
    data_dir, transaction_dir, _ = make_fixture(tmp_path)
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    concrete = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (BigFileReplacement("fixture resource", entry.hash, entry.locale, b"translated"),),
        0x4000,
    )

    with pytest.raises(transaction.TransactionError, match="generic source changed"):
        transaction.apply_write_plan(data_dir, GenericWritePlan(concrete), transaction_dir)

    assert not transaction_dir.exists()


def test_execute_saves_only_changed_ranges_and_applies_the_staged_plan(tmp_path: Path) -> None:
    data_dir, transaction_dir, original = make_fixture(tmp_path)
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    plan = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (BigFileReplacement("fixture resource", entry.hash, entry.locale, b"translated"),),
        0x4000,
    )

    transaction.apply_write_plan(data_dir, plan, transaction_dir)

    manifest = json.loads((transaction_dir / "journal.json").read_text(encoding="utf-8"))
    current = (data_dir / "bigfile.000").read_bytes()
    assert manifest["status"] == "applied"
    assert not (transaction_dir / "backups/bigfile.000").exists()
    backups = [
        (transaction_dir / "backups" / item["backup_file"]).read_bytes()
        for item in manifest["write_backups"]
    ]
    assert original[:24] in backups
    assert any(backup.startswith(b"original") for backup in backups)
    assert stat.S_IMODE((data_dir / "bigfile.000").stat().st_mode) == 0o640
    assert (
        manifest["files"]["bigfile.000"]["original_sha256"] == hashlib.sha256(original).hexdigest()
    )
    assert hashlib.sha256(current).hexdigest() == manifest["files"]["bigfile.000"]["staged_sha256"]
    assert current[0x1000:0x100A] == b"translated"
    assert current[0x100A:0x1800] == bytes(0x1800 - 0x100A)


def test_apply_reports_each_staged_translation_write(tmp_path: Path) -> None:
    data_dir, transaction_dir, _ = make_fixture(tmp_path)
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    plan = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (BigFileReplacement("fixture resource", entry.hash, entry.locale, b"translated"),),
        0x4000,
    )
    updates: list[tuple[int, int, str]] = []

    transaction.apply_write_plan(
        data_dir,
        plan,
        transaction_dir,
        progress=lambda current, total, message: updates.append((current, total, message)),
    )

    assert (0, 1, "gui_progress_install_resources") in updates
    assert (1, 1, "gui_progress_install_resources") in updates


def test_transaction_can_be_stored_in_a_dedicated_game_subdirectory(tmp_path: Path) -> None:
    data_dir, _, original = make_fixture(tmp_path)
    transaction_dir = data_dir / "PyTRTT Recovery" / "test" / "transaction"
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    plan = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (BigFileReplacement("fixture resource", entry.hash, entry.locale, b"translated"),),
        0x4000,
    )

    transaction.apply_write_plan(data_dir, plan, transaction_dir)
    updates: list[tuple[int, int, str]] = []
    transaction.restore_write_plan(
        data_dir,
        transaction_dir,
        progress=lambda current, total, message: updates.append((current, total, message)),
    )

    assert (data_dir / "bigfile.000").read_bytes() == original
    assert any(message == "gui_progress_restore_bytes" for _, _, message in updates)
    assert any(
        current == total and total > 0 and message == "gui_progress_restore_bytes"
        for current, total, message in updates
    )


def test_font_original_raw_is_saved_with_restore_data_and_restored(tmp_path: Path) -> None:
    data_dir, transaction_dir, original = make_fixture(tmp_path)
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    plan = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (
            BigFileReplacement(
                "TRA font",
                entry.hash,
                entry.locale,
                b"newfont!",
                restore_file="fonts/12345678-FFFFFFE1.raw",
            ),
        ),
        0x4000,
    )

    transaction.apply_write_plan(data_dir, plan, transaction_dir)

    raw_backup = transaction_dir / "backups/restore-data/fonts/12345678-FFFFFFE1.raw"
    assert raw_backup.read_bytes() == b"original"
    manifest = json.loads((transaction_dir / "journal.json").read_text(encoding="utf-8"))
    assert manifest["restore_data"][0]["size"] == len(b"original")
    assert manifest["write_backups"][0]["backup_file"] == (
        "restore-data/fonts/12345678-FFFFFFE1.raw"
    )
    assert not (transaction_dir / "backups/bigfile.000").exists()

    transaction.restore_write_plan(data_dir, transaction_dir)

    assert (data_dir / "bigfile.000").read_bytes() == original


def test_restore_returns_exact_original_bytes_and_is_idempotent(tmp_path: Path) -> None:
    data_dir, transaction_dir, original = make_fixture(tmp_path)
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    plan = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (BigFileReplacement("fixture resource", entry.hash, entry.locale, b"translated"),),
        0x4000,
    )
    transaction.apply_write_plan(data_dir, plan, transaction_dir)

    transaction.restore_write_plan(data_dir, transaction_dir)
    transaction.restore_write_plan(data_dir, transaction_dir)

    assert (data_dir / "bigfile.000").read_bytes() == original
    assert stat.S_IMODE((data_dir / "bigfile.000").stat().st_mode) == 0o640
    manifest = json.loads((transaction_dir / "journal.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "restored"


def test_apply_rejects_files_changed_after_the_dry_run(tmp_path: Path) -> None:
    data_dir, transaction_dir, _ = make_fixture(tmp_path)
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    plan = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (BigFileReplacement("fixture resource", entry.hash, entry.locale, b"translated"),),
        0x4000,
    )
    archive = data_dir / "bigfile.000"
    archive.write_bytes(archive.read_bytes() + b"external change")
    changed = archive.read_bytes()

    with pytest.raises(transaction.TransactionError, match="changed after planning"):
        transaction.apply_write_plan(data_dir, plan, transaction_dir)

    assert archive.read_bytes() == changed
    assert not transaction_dir.exists()


def test_operation_lock_rejects_a_second_writer_for_the_same_installation(
    tmp_path: Path,
) -> None:
    data_dir, transaction_dir, _ = make_fixture(tmp_path)
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    plan = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (BigFileReplacement("fixture resource", entry.hash, entry.locale, b"translated"),),
        0x4000,
    )

    with transaction._operation_lock(data_dir.resolve()):
        with pytest.raises(transaction.TransactionError, match="another write operation"):
            transaction.apply_write_plan(data_dir, plan, transaction_dir)

    assert not transaction_dir.exists()


def test_restore_refuses_to_overwrite_an_unrecognized_external_change(tmp_path: Path) -> None:
    data_dir, transaction_dir, _ = make_fixture(tmp_path)
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    plan = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (BigFileReplacement("fixture resource", entry.hash, entry.locale, b"translated"),),
        0x4000,
    )
    transaction.apply_write_plan(data_dir, plan, transaction_dir)
    archive = data_dir / "bigfile.000"
    archive.write_bytes(archive.read_bytes() + b"external change")
    changed = archive.read_bytes()

    with pytest.raises(transaction.TransactionError, match="unexpected content"):
        transaction.restore_write_plan(data_dir, transaction_dir)

    assert archive.read_bytes() == changed


def test_restore_preflights_all_targets_before_reverting_any(tmp_path: Path) -> None:
    data_dir, transaction_dir, _ = make_fixture(tmp_path)
    first = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    second = BigFileEntry(1, 0x87654321, 8, 9, 0xFFFFFFE1, 0xABCDEF02)
    second_archive = data_dir / "bigfile.001"
    second_archive.write_bytes(bytes(0x1000))
    with second_archive.open("r+b") as stream:
        stream.seek(0x800)
        stream.write(b"second!!")
    index_bytes = (
        struct.pack("<I", 2)
        + struct.pack("<2I", first.hash, second.hash)
        + b"".join(
            struct.pack("<4I", row.length, row.location, row.locale, row.unknown)
            for row in (first, second)
        )
    )
    first_archive = data_dir / "bigfile.000"
    with first_archive.open("r+b") as stream:
        stream.seek(0)
        stream.write(index_bytes)
    plan = plan_replacements(
        data_dir,
        BigFileIndex((first, second)),
        (
            BigFileReplacement("first", first.hash, first.locale, b"first-new"),
            BigFileReplacement("second", second.hash, second.locale, b"second-new"),
        ),
        0x4000,
    )
    transaction.apply_write_plan(data_dir, plan, transaction_dir)
    first_installed = first_archive.read_bytes()
    second_archive.write_bytes(second_archive.read_bytes() + b"external")
    second_changed = second_archive.read_bytes()

    with pytest.raises(transaction.TransactionError, match="unexpected content"):
        transaction.restore_write_plan(data_dir, transaction_dir)

    assert first_archive.read_bytes() == first_installed
    assert second_archive.read_bytes() == second_changed


def test_interrupted_apply_can_be_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir, transaction_dir, original = make_fixture(tmp_path)
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    second = BigFileEntry(1, 0x87654321, 8, 9, 0xFFFFFFE1, 0xABCDEF02)
    archive = data_dir / "bigfile.000"
    second_archive = data_dir / "bigfile.001"
    second_original = bytearray(0x1000)
    second_original[0x800:0x808] = b"second!!"
    second_archive.write_bytes(second_original)
    boundary = 0x4000
    entry_bytes = (entry, second)
    index_bytes = (
        struct.pack("<I", 2)
        + struct.pack("<2I", entry.hash, second.hash)
        + b"".join(
            struct.pack("<4I", row.length, row.location, row.locale, row.unknown)
            for row in entry_bytes
        )
    )
    data = bytearray(archive.read_bytes())
    data[: len(index_bytes)] = index_bytes
    archive.write_bytes(data)
    original = archive.read_bytes()
    original_second = second_archive.read_bytes()
    index = BigFileIndex(entry_bytes)
    plan = plan_replacements(
        data_dir,
        index,
        (
            BigFileReplacement("first", entry.hash, entry.locale, b"first-new"),
            BigFileReplacement("second", second.hash, second.locale, b"second-new"),
        ),
        boundary,
    )
    replace_target = transaction._replace_target
    calls = 0

    def fail_on_second_replace(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated power loss")
        replace_target(source, target)

    monkeypatch.setattr(transaction, "_replace_target", fail_on_second_replace)
    with pytest.raises(OSError, match="simulated power loss"):
        transaction.apply_write_plan(data_dir, plan, transaction_dir)
    monkeypatch.setattr(transaction, "_replace_target", replace_target)

    transaction.restore_write_plan(data_dir, transaction_dir)

    assert archive.read_bytes() == original
    assert second_archive.read_bytes() == original_second


def test_restore_removes_a_new_archive_part_created_by_the_plan(tmp_path: Path) -> None:
    data_dir = tmp_path / "game-data"
    data_dir.mkdir()
    entry = BigFileEntry(0, 0x12345678, 8, 3, 0xFFFFFFE1, 0xABCDEF01)
    index_bytes = (
        struct.pack("<I", 1)
        + struct.pack("<I", entry.hash)
        + struct.pack("<4I", entry.length, entry.location, entry.locale, entry.unknown)
    )
    (data_dir / "bigfile.000").write_bytes(index_bytes + bytes(0x1000 - len(index_bytes)))
    (data_dir / "bigfile.001").write_bytes(bytes(0x1000))
    index_before = (data_dir / "bigfile.000").read_bytes()
    plan = plan_replacements(
        data_dir,
        BigFileIndex((entry,)),
        (BigFileReplacement("large resource", entry.hash, entry.locale, b"x" * 0x1800),),
        0x1000,
    )
    transaction_dir = tmp_path / "transaction-002"

    transaction.apply_write_plan(data_dir, plan, transaction_dir)
    assert (data_dir / "bigfile.002").is_file()

    transaction.restore_write_plan(data_dir, transaction_dir)

    assert not (data_dir / "bigfile.002").exists()
    assert (data_dir / "bigfile.000").read_bytes() == index_before
