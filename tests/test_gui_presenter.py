from pathlib import Path

from pytrtt.gui_discovery import GameCatalogEntry, InstallationCandidate
from pytrtt.gui_presenter import (
    installation_payload,
    operation_payload,
    translation_credits_payload,
)
from pytrtt.gui_support import InstallationInspection, InstallationStatus
from pytrtt.packages.translation import parse_translation_document


def test_installation_payload_filters_game_and_reports_validation(tmp_path: Path) -> None:
    package = tmp_path / "translations/game-a/hu.json"
    package.parent.mkdir(parents=True)
    package.write_text("{}", encoding="utf-8")
    installation = tmp_path / "installed"
    installation.mkdir()
    game_a = GameCatalogEntry("game-a", "Game A", "1", "A", Path("translations/game-a/hu.json"))
    game_b = GameCatalogEntry("game-b", "Game B", "2", "B", Path("translations/game-b/hu.json"))

    assert installation_payload(
        (
            InstallationCandidate(game_a, installation, "Steam", "123"),
            InstallationCandidate(game_b, tmp_path / "other", "Epic Games"),
        ),
        "game-a",
        project_root=tmp_path,
    ) == [
        {
            "path": str(installation),
            "source": "Steam",
            "build": "123",
            "status": "ready",
            "selectable": True,
        }
    ]


def test_operation_payload_enables_only_safe_backend_operations(tmp_path: Path) -> None:
    game = GameCatalogEntry("game-a", "Game A", "1", "A", Path("hu.json"))
    candidate = InstallationCandidate(game, tmp_path, "Steam")
    inspection = InstallationInspection(
        candidate,
        InstallationStatus.CHANGES_AVAILABLE,
        tmp_path / "hu.json",
    )

    payload = operation_payload(inspection)

    assert payload["status"] == "changes_available"
    assert [item["available"] for item in payload["operations"]] == [True, True, False]


def test_translation_credits_payload_reads_names_from_the_package(tmp_path: Path) -> None:
    package = tmp_path / "translations/game/hu.json"
    package.parent.mkdir(parents=True)
    package.write_text(
        """{
          "schema_version": 6,
          "metadata": {
            "game_id": "game", "build_id": "1", "source_language": "en",
            "target_language": "hu", "archive_format": "bigfile", "archive_version": 1
          },
          "credits": {"translators": ["Lara", "Zip"], "testers": ["Winston"]}
        }""",
        encoding="utf-8",
    )

    document = parse_translation_document(package.read_text(encoding="utf-8"))

    assert translation_credits_payload(document) == [
        {"role": "translators", "names": ["Lara", "Zip"]},
        {"role": "testers", "names": ["Winston"]},
    ]
