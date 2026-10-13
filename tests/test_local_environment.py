"""Machine-local paths shared by clients, developer tools and optional tests."""

from pathlib import Path

import pytest

from pytrtt.cli import main as translate
from pytrtt.environment import load_local_environment
from pytrtt.packages.translation import serialize_translation_document
from scripts.extract_strings import main as extract
from tests.test_anniversary_extraction import make_game_dir, make_menu, write_profile
from tests.test_generic_translation import document, make_archive


def test_missing_default_environment_is_optional(tmp_path: Path) -> None:
    settings = load_local_environment(directory=tmp_path)
    assert settings.games == ()
    assert settings.samples_dir == tmp_path / "work/samples"
    with pytest.raises(ValueError, match="No local paths"):
        settings.game("missing")


def test_shared_paths_aliases_relative_roots_and_platform_overrides(tmp_path: Path) -> None:
    config = tmp_path / "pytrtt.local.toml"
    config.write_text(
        """samples_dir = "samples"
[games.fixture-a]
aliases = ["short"]
install_dir = "base-game"
original_dir = "clean"
translated_dir = "translated"
samples_dir = "samples/short/build-1"
[platforms.linux.games.fixture-a]
install_dir = "linux-game"
""",
        encoding="utf-8",
    )
    settings = load_local_environment(directory=tmp_path, platform="linux")
    game = settings.game("short")
    assert game.game_id == "fixture-a"
    assert game.install_dir == tmp_path / "linux-game"
    assert game.original_dir == tmp_path / "clean"
    assert game.translated_dir == tmp_path / "translated"
    assert game.samples_dir == tmp_path / "samples/short/build-1"
    assert settings.game("fixture-a") == game
    assert settings.samples_dir == tmp_path / "samples"


@pytest.mark.parametrize(
    "content",
    [
        "[games.a]\ninstall_dir = 5",
        '[games.a]\nunknown = "value"',
        '[games.a]\naliases = ["b"]\n[games.b]\ninstall_dir = "folder"',
    ],
)
def test_invalid_environment_is_reported_not_silently_ignored(tmp_path: Path, content: str) -> None:
    (tmp_path / "pytrtt.local.toml").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_local_environment(directory=tmp_path)


def test_explicit_environment_file_must_exist(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_local_environment(tmp_path / "missing.toml")


def test_application_uses_local_installation_and_cli_path_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = tmp_path / "game"
    original = make_archive(game)
    translation = tmp_path / "translation.json"
    translation.write_text(serialize_translation_document(document()), encoding="utf-8")
    config = tmp_path / "pytrtt.local.toml"
    config.write_text('[games.fixture-a]\ninstall_dir = "game"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert translate(["--translation-file", str(translation)]) == 0
    assert (game / "bigfile.000").read_bytes() == original
    config.write_text('[games.fixture-a]\ninstall_dir = "missing"\n', encoding="utf-8")
    assert translate(["--translation-file", str(translation), "--game-dir", str(game)]) == 0


def test_extraction_uses_same_environment_by_profile_game_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = tmp_path / "game"
    game.mkdir()
    make_game_dir(game, (make_menu("Start"),), (0x7CD333D3,))
    profile = write_profile(tmp_path)
    (tmp_path / "tra_filelist.txt").write_text(
        "7CD333D3\tpc-w\\local\\locals.bin\n", encoding="utf-8"
    )
    (tmp_path / "pytrtt.local.toml").write_text(
        '[games.tomb-raider-anniversary]\ninstall_dir = "game"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert extract(["--profile", str(profile), "--output-dir", str(tmp_path / "output")]) == 0
    assert (tmp_path / "output/tomb-raider-anniversary.en-to-hu.json").is_file()
