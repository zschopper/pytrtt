"""Portable storage belongs beside the program, independent of the working directory."""

import sys
from pathlib import Path

import pytest

from pytrtt.application_paths import (
    ensure_game_transaction_root,
    game_transaction_root,
    program_directory,
    transaction_root,
    transaction_search_roots,
)


def test_source_storage_does_not_follow_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = Path(__file__).resolve().parents[1]
    assert program_directory() == root
    assert transaction_root() == root / "transactions"
    assert root / "dist/transactions" in transaction_search_roots()
    assert root / "work/transactions" in transaction_search_roots()


def test_frozen_program_stores_beside_executable_not_unpack_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "portable/PyTRTT.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "unpacked"), raising=False)
    assert program_directory() == executable.parent
    assert transaction_root() == executable.parent / "transactions"
    assert transaction_search_roots()[0] == transaction_root()
    assert executable.parent / "dist/transactions" not in transaction_search_roots()


def test_game_transaction_root_is_discovered_before_legacy_locations(tmp_path: Path) -> None:
    game = tmp_path / "Tomb Raider Anniversary"
    expected = game / "PyTRTT Recovery"
    assert game_transaction_root(game) == expected
    assert transaction_search_roots(game)[0] == expected

    root = ensure_game_transaction_root(game)
    readme = (root / "README.txt").read_text(encoding="utf-8")
    assert "DO NOT DELETE" in readme
    assert "NE TÖRÖLD" in readme
    assert "restore" in readme
    assert "visszaállítás" in readme


def test_cli_uses_portable_default_when_transaction_option_is_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    from pytrtt.cli import main
    from pytrtt.packages.translation import serialize_translation_document
    from tests.test_generic_translation import document, make_archive

    game = tmp_path / "game"
    original = make_archive(game)
    package = tmp_path / "hu.json"
    package.write_text(
        serialize_translation_document(replace(document(), fonts=())), encoding="utf-8"
    )
    executable = tmp_path / "portable/PyTRTT.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert main(["--game-dir", str(game), "--translation-file", str(package), "--apply"]) == 0
    journals = list((executable.parent / "transactions").rglob("journal.json"))
    assert len(journals) == 1
    assert (journals[0].parent / "backups/ranges").is_dir()
    assert (
        main(["--game-dir", str(game), "--transaction-dir", str(journals[0].parent), "--restore"])
        == 0
    )
    assert (game / "bigfile.000").read_bytes() == original
