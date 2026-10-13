"""A fresh clone can test the code without possessing any game samples."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_sample_suite(
    tmp_path: Path, *arguments: str, suite: str | None = None
) -> subprocess.CompletedProcess[str]:
    source = Path(__file__).with_name("conftest.py")
    (tmp_path / "conftest.py").write_text(
        source.read_text() if source.exists() else "", encoding="utf-8"
    )
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    integration: sample checks\n    game(name, build): game data\n",
        encoding="utf-8",
    )
    (tmp_path / "test_sample.py").write_text(
        suite
        or """import pytest

def test_unit():
    assert True

@pytest.mark.integration
@pytest.mark.game("one", build="v1")
def test_one(game_samples):
    assert game_samples.require("marker.txt").read_text() == "sample"

@pytest.mark.integration
@pytest.mark.game("two", build="v2")
def test_two(game_samples):
    game_samples.require("marker.txt")
""",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    environment.pop("PYTEST_ADDOPTS", None)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-c", str(tmp_path / "pytest.ini"), *arguments],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    "arguments,summary",
    [
        ((), "1 passed, 2 deselected"),
        (("--game", "one"), "1 passed, 1 skipped, 1 deselected"),
        (("-m", "integration"), "2 skipped, 1 deselected"),
    ],
)
def test_game_data_is_optional(tmp_path: Path, arguments: tuple[str, ...], summary: str) -> None:
    result = run_sample_suite(tmp_path, *arguments)
    assert result.returncode == 0, result.stdout + result.stderr
    assert summary in result.stdout


def test_only_selected_game_uses_external_sample_directory(tmp_path: Path) -> None:
    samples = tmp_path / "external-samples"
    root = samples / "one/v1"
    root.mkdir(parents=True)
    (root / "marker.txt").write_text("sample", encoding="utf-8")
    result = run_sample_suite(tmp_path, "--game", "one", "--samples-dir", str(samples))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed, 1 deselected" in result.stdout


def test_unknown_game_selection_is_an_actionable_error(tmp_path: Path) -> None:
    result = run_sample_suite(tmp_path, "--game", "typo")
    assert result.returncode == 4
    assert "Unknown game" in result.stderr


def test_game_tests_use_shared_local_paths_without_installation_fallback(tmp_path: Path) -> None:
    sample = tmp_path / "my-samples"
    sample.mkdir()
    (sample / "marker.txt").write_text("sample", encoding="utf-8")
    (tmp_path / "pytrtt.local.toml").write_text(
        """[games.fixture-a]
aliases = ["one"]
install_dir = "installed-game"
original_dir = "safe-original-copy"
translated_dir = "verified-translation"
samples_dir = "my-samples"
""",
        encoding="utf-8",
    )
    suite = """import pytest
@pytest.mark.integration
@pytest.mark.game("one", build="v1")
def test_paths(game_samples):
    assert game_samples.original.name == "safe-original-copy"
    assert game_samples.translated.name == "verified-translation"
    assert game_samples.require("marker.txt").read_text() == "sample"
"""
    result = run_sample_suite(tmp_path, "--game", "one", suite=suite)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
