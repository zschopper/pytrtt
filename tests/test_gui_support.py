"""Read-only GUI support without creating a graphical display."""

import hashlib
import json
from contextlib import AbstractContextManager
from dataclasses import replace
from pathlib import Path

import pytest

from pytrtt.gui_discovery import (
    GameCatalogEntry,
    InstallationCandidate,
    discover_steam_installations,
    load_game_catalog,
    registry_steam_roots,
    validate_packaged_catalog,
)
from pytrtt.gui_support import (
    InstallationInspection,
    InstallationStatus,
    find_interrupted_transactions,
    find_restorable_transaction,
    inspect_installation,
    run_translation_operation,
)


def _entry() -> GameCatalogEntry:
    return GameCatalogEntry(
        game_id="fixture-game",
        display_name="Fixture Game",
        steam_app_id="1234",
        install_dir_name="Fixture Game",
        translation_file=Path("translations/fixture-game/hu.json"),
    )


def test_catalog_is_data_driven_and_contains_anniversary() -> None:
    games = load_game_catalog()
    anniversary = next(game for game in games if game.game_id == "tomb-raider-anniversary")
    assert anniversary.display_name == "Tomb Raider: Anniversary"
    assert anniversary.steam_app_id == "8000"
    assert anniversary.translation_file == Path("translations/tomb-raider-anniversary/hu.json")

    ids = {game.game_id for game in games}
    assert "tomb-raider-legend-demo" in ids
    assert "shadow-of-the-tomb-raider-trial" in ids
    assert anniversary.package_available


def test_available_catalog_packages_are_self_consistent() -> None:
    project_root = Path(__file__).resolve().parents[1]
    assert validate_packaged_catalog(load_game_catalog(), project_root) == ()


def test_packaged_catalog_reports_missing_and_mismatched_packages(tmp_path: Path) -> None:
    missing = GameCatalogEntry(
        "missing-game", "Missing", "1", "Missing", Path("translations/missing/hu.json"), True
    )
    mismatched = GameCatalogEntry(
        "expected-game", "Mismatch", "2", "Mismatch", Path("translations/mismatch/hu.json"), True
    )
    package = tmp_path / mismatched.translation_file
    package.parent.mkdir(parents=True)
    package.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "metadata": {
                    "game_id": "different-game",
                    "build_id": "1",
                    "source_language": "en",
                    "target_language": "hu",
                    "archive_format": "bigfile",
                    "archive_version": 1,
                },
                "menu": [],
                "subtitles": [],
                "fonts": [],
                "clear_subtitle_languages": [],
                "omit_subtitle_languages": [],
            }
        ),
        encoding="utf-8",
    )

    assert validate_packaged_catalog((missing, mismatched), tmp_path) == (
        "missing-game: translation package is missing",
        "expected-game: package metadata targets different-game",
    )


def test_safe_exit_restores_a_just_installed_translation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inspection = InstallationInspection(
        InstallationCandidate(_entry(), tmp_path / "game", "Manual"),
        InstallationStatus.CHANGES_AVAILABLE,
        tmp_path / "hu.json",
    )
    installed = replace(
        inspection,
        status=InstallationStatus.ALREADY_TRANSLATED,
        restore_path=tmp_path / "transaction",
    )
    restored = replace(installed, status=InstallationStatus.RESTORED)
    calls = []

    monkeypatch.setattr("pytrtt.gui_support.apply_translation", lambda *_args, **_kwargs: installed)

    def restore(*_args: object, **_kwargs: object) -> InstallationInspection:
        calls.append("restore")
        return restored

    monkeypatch.setattr("pytrtt.gui_support.restore_translation", restore)

    result, safe_exit_completed = run_translation_operation(
        inspection,
        "install",
        transaction_root=tmp_path / "transactions",
        transaction_roots=(tmp_path / "transactions",),
        safe_exit_requested=True,
    )

    assert result is restored
    assert safe_exit_completed
    assert calls == ["restore"]


def test_failed_restore_is_returned_without_safe_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inspection = InstallationInspection(
        InstallationCandidate(_entry(), tmp_path / "game", "Manual"),
        InstallationStatus.ALREADY_TRANSLATED,
        tmp_path / "hu.json",
        restore_path=tmp_path / "transaction",
    )
    failed = replace(inspection, status=InstallationStatus.ERROR, detail="restore failed")
    monkeypatch.setattr("pytrtt.gui_support.restore_translation", lambda *_args, **_kwargs: failed)

    result, safe_exit_completed = run_translation_operation(
        inspection,
        "restore",
        transaction_root=tmp_path / "transactions",
        transaction_roots=(tmp_path / "transactions",),
    )

    assert result is failed
    assert not safe_exit_completed


def test_steam_discovery_reads_default_and_additional_libraries(tmp_path: Path) -> None:
    steam = tmp_path / "Steam"
    additional = tmp_path / "Games"
    (steam / "steamapps").mkdir(parents=True)
    (additional / "steamapps/common/Fixture Game").mkdir(parents=True)
    (steam / "steamapps/libraryfolders.vdf").write_text(
        '"libraryfolders"\n{\n"0" { "path" "'
        + str(steam).replace("\\", "\\\\")
        + '" }\n"1" { "path" "'
        + str(additional).replace("\\", "\\\\")
        + '" }\n}\n',
        encoding="utf-8",
    )
    (additional / "steamapps/appmanifest_1234.acf").write_text(
        '"AppState"\n{\n"appid" "1234"\n"installdir" "Fixture Game"\n'
        '"buildid" "42"\n"StateFlags" "4"\n}\n',
        encoding="utf-8",
    )

    assert discover_steam_installations((_entry(),), (steam,)) == (
        InstallationCandidate(
            game=_entry(),
            path=additional / "steamapps/common/Fixture Game",
            source="Steam",
            build_id="42",
        ),
    )


def test_discovery_ignores_incomplete_or_missing_installations(tmp_path: Path) -> None:
    steamapps = tmp_path / "Steam/steamapps"
    steamapps.mkdir(parents=True)
    (steamapps / "appmanifest_1234.acf").write_text(
        '"AppState" { "appid" "1234" "installdir" "Fixture Game" "buildid" "42" "StateFlags" "2" }',
        encoding="utf-8",
    )
    assert discover_steam_installations((_entry(),), (tmp_path / "Steam",)) == ()


def test_manual_folder_must_exist_and_translation_package_must_be_available(
    tmp_path: Path,
) -> None:
    candidate = InstallationCandidate(_entry(), tmp_path / "missing", "Manual")
    result = inspect_installation(candidate, project_root=tmp_path)
    assert result.status is InstallationStatus.NOT_FOUND

    candidate = InstallationCandidate(_entry(), tmp_path / "game", "Manual")
    candidate.path.mkdir()
    result = inspect_installation(candidate, project_root=tmp_path)
    assert result.status is InstallationStatus.PACKAGE_UNAVAILABLE
    assert result.translation_path == tmp_path / _entry().translation_file


class FakeRegistryKey:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def __enter__(self) -> "FakeRegistryKey":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class FakeRegistry:
    HKEY_CURRENT_USER = 1
    HKEY_LOCAL_MACHINE = 2
    KEY_READ = 4
    KEY_WOW64_32KEY = 8

    def OpenKey(
        self, hive: int, path: str, _reserved: int, _access: int
    ) -> AbstractContextManager[object]:
        values = {
            (self.HKEY_CURRENT_USER, r"Software\Valve\Steam"): {
                "SteamPath": r"C:\Games\Steam",
                "SteamExe": r"C:\Games\Steam\steam.exe",
            },
            (self.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam"): {
                "InstallPath": r"D:\Steam",
            },
        }
        if (hive, path) not in values:
            raise OSError("missing key")
        return FakeRegistryKey(values[hive, path])

    def QueryValueEx(self, key: object, name: str) -> tuple[object, int]:
        assert isinstance(key, FakeRegistryKey)
        if name not in key.values:
            raise OSError("missing value")
        return key.values[name], 1


def test_windows_registry_adds_unique_steam_installation_roots() -> None:
    assert registry_steam_roots(FakeRegistry()) == (
        Path(r"C:\Games\Steam"),
        Path(r"D:\Steam"),
    )


def test_restore_transaction_requires_matching_path_and_complete_file_hash(tmp_path: Path) -> None:
    game = tmp_path / "game"
    game.mkdir()
    data = b"translated"
    (game / "bigfile.000").write_bytes(data)
    root = tmp_path / "transactions"
    transaction = root / "tra/install"
    transaction.mkdir(parents=True)
    backup = transaction / "backups/ranges/000000.bin"
    backup.parent.mkdir(parents=True)
    backup.write_bytes(b"original range")
    (transaction / "journal.json").write_text(
        json.dumps(
            {
                "status": "applied",
                "data_dir": str(game.resolve()),
                "files": {
                    "bigfile.000": {
                        "staged_sha256": hashlib.sha256(data).hexdigest(),
                    }
                },
                "write_backups": [
                    {
                        "backup_file": "ranges/000000.bin",
                        "length": backup.stat().st_size,
                        "sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
                    }
                ],
                "restore_data": [],
            }
        ),
        encoding="utf-8",
    )
    assert find_restorable_transaction(game, (root,)) == transaction

    (game / "bigfile.000").write_bytes(b"modded")
    assert find_restorable_transaction(game, (root,)) is None


def test_restore_transaction_requires_recovery_payloads(tmp_path: Path) -> None:
    game = tmp_path / "game"
    game.mkdir()
    data = b"translated"
    (game / "bigfile.000").write_bytes(data)
    transaction = tmp_path / "transactions/tra/install"
    transaction.mkdir(parents=True)
    (transaction / "journal.json").write_text(
        json.dumps(
            {
                "status": "applied",
                "data_dir": str(game.resolve()),
                "files": {
                    "bigfile.000": {
                        "staged_sha256": hashlib.sha256(data).hexdigest(),
                    }
                },
                "write_backups": [
                    {
                        "backup_file": "ranges/missing.bin",
                        "length": 8,
                        "sha256": hashlib.sha256(b"original").hexdigest(),
                    }
                ],
                "restore_data": [],
            }
        ),
        encoding="utf-8",
    )

    assert find_restorable_transaction(game, (tmp_path / "transactions",)) is None


def test_interrupted_transactions_include_only_incomplete_file_writes(tmp_path: Path) -> None:
    root = tmp_path / "transactions"
    applying = root / "game/applying"
    restored = root / "game/restored"
    applying.mkdir(parents=True)
    restored.mkdir(parents=True)
    (applying / "journal.json").write_text(
        json.dumps({"status": "applying", "data_dir": str(tmp_path / "game")}),
        encoding="utf-8",
    )
    (restored / "journal.json").write_text(
        json.dumps({"status": "restored", "data_dir": str(tmp_path / "game")}),
        encoding="utf-8",
    )

    assert find_interrupted_transactions(root) == ((tmp_path / "game", applying),)


def test_discovery_retains_the_same_game_in_two_libraries(tmp_path: Path) -> None:
    first, second = tmp_path / "Steam-A", tmp_path / "Steam-B"
    for root in (first, second):
        (root / "steamapps/common/Fixture Game").mkdir(parents=True)
        (root / "steamapps/appmanifest_1234.acf").write_text(
            '"AppState" { "appid" "1234" "installdir" "Fixture Game" "StateFlags" "4" }',
            encoding="utf-8",
        )
    found = discover_steam_installations((_entry(),), (first, second))
    assert {item.path for item in found} == {
        first / "steamapps/common/Fixture Game",
        second / "steamapps/common/Fixture Game",
    }
