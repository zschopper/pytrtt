"""Two copies of the same game retain independent status and recovery data."""

import os
from dataclasses import replace
from pathlib import Path

import pytest

from pytrtt.archives.transaction import journal_data_dir_matches
from pytrtt.gui_support import (
    GameCatalogEntry,
    InstallationCandidate,
    InstallationInspection,
    InstallationStatus,
    apply_translation,
    check_translation,
    find_restorable_transaction,
    inspect_installation,
    installation_choices,
    restore_translation,
)
from pytrtt.packages.translation import serialize_translation_document
from tests.test_generic_translation import document, make_archive


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only case-sensitive directory identity")
def test_case_sensitive_posix_folders_are_different_installations(tmp_path: Path) -> None:
    first, second = tmp_path / "Game", tmp_path / "game"
    first.mkdir()
    second.mkdir()
    assert not journal_data_dir_matches(str(first), second)


def test_selector_retains_two_paths_for_the_same_game(tmp_path: Path) -> None:
    game = GameCatalogEntry("fixture-a", "Fixture", "1", "Fixture", Path("hu.json"))
    first = InstallationCandidate(game, tmp_path / "one", "Steam")
    second = InstallationCandidate(game, tmp_path / "two", "Steam")
    assert installation_choices((first, second), game.game_id) == {
        str(first.path): first,
        str(second.path): second,
    }


def test_two_identical_translated_copies_restore_independently(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    original = make_archive(first)
    make_archive(second)
    package = tmp_path / "package"
    package.mkdir()
    doc = replace(document(), fonts=())
    (package / "hu.json").write_text(serialize_translation_document(doc), encoding="utf-8")
    game = GameCatalogEntry("fixture-a", "Fixture", "1", "Fixture", Path("hu.json"))
    a = InstallationCandidate(game, first, "Manual")
    b = InstallationCandidate(game, second, "Manual")
    transactions = tmp_path / "portable/transactions"
    roots = (transactions,)

    def check(candidate: InstallationCandidate) -> InstallationInspection:
        return check_translation(
            inspect_installation(candidate, project_root=package), transaction_roots=roots
        )

    a_installed = apply_translation(check(a), transaction_root=transactions)
    assert a_installed.status is InstallationStatus.ALREADY_TRANSLATED
    assert check(b).status is InstallationStatus.CHANGES_AVAILABLE
    assert find_restorable_transaction(second, roots) is None
    b_installed = apply_translation(check(b), transaction_root=transactions)
    assert b_installed.status is InstallationStatus.ALREADY_TRANSLATED
    assert a_installed.restore_path != b_installed.restore_path
    assert a_installed.restore_path is not None
    assert find_restorable_transaction(second, (a_installed.restore_path,)) is None
    assert (first / "bigfile.000").read_bytes() == (second / "bigfile.000").read_bytes()
    assert (
        restore_translation(a_installed, transaction_roots=roots).status
        is InstallationStatus.RESTORED
    )
    assert (first / "bigfile.000").read_bytes() == original
    assert check(a).status is InstallationStatus.CHANGES_AVAILABLE
    assert check(b).status is InstallationStatus.ALREADY_TRANSLATED
    assert (
        restore_translation(check(b), transaction_roots=roots).status is InstallationStatus.RESTORED
    )
    assert (second / "bigfile.000").read_bytes() == original


def test_windows_network_path_matching_remains_case_insensitive() -> None:
    assert journal_data_dir_matches(r"\\NAS\Library\Game", Path("//nas/library/game"))
