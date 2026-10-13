"""Game-free defaults and explicit selection of optional local integration data."""

from pathlib import Path

import pytest

from pytrtt.environment import load_local_environment
from tests.game_samples import GameSamples


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("game samples")
    group.addoption(
        "--game",
        action="append",
        default=[],
        metavar="ID",
        help="Enable integration tests for this game; repeat for several games",
    )
    group.addoption(
        "--samples-dir",
        default=None,
        metavar="PATH",
        help="Local sample root with <game>/<build>/ directories",
    )
    group.addoption(
        "--local-config",
        default=None,
        metavar="PATH",
        help="Optional machine-local TOML environment file",
    )
    group.addoption(
        "--game-copy",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="Original game copy used for integration tests; repeat per game",
    )


def _copies(config: pytest.Config) -> dict[str, Path]:
    paths = {}
    for value in config.getoption("game_copy"):
        game, separator, path = value.partition("=")
        if not separator or not game or not path or game in paths:
            raise pytest.UsageError("--game-copy requires a unique ID=PATH for each game")
        paths[game] = Path(path).resolve()
    return paths


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    games = set(config.getoption("game"))
    _copies(config)
    available = set()
    for item in items:
        if item.get_closest_marker("integration") is not None:
            marker = item.get_closest_marker("game")
            if marker is None or len(marker.args) != 1 or not isinstance(marker.args[0], str):
                raise pytest.UsageError(
                    f"Integration test needs @pytest.mark.game(ID): {item.nodeid}"
                )
            available.add(marker.args[0])
    if games - available:
        raise pytest.UsageError("Unknown game selection: " + ", ".join(sorted(games - available)))
    explicit = bool(games) or "integration" in config.option.markexpr
    selected, excluded = [], []
    for item in items:
        integration = item.get_closest_marker("integration") is not None
        marker = item.get_closest_marker("game")
        if integration and (
            not explicit or (games and marker is not None and marker.args[0] not in games)
        ):
            excluded.append(item)
        else:
            selected.append(item)
    if excluded:
        items[:] = selected
        config.hook.pytest_deselected(items=excluded)


@pytest.fixture
def game_samples(request: pytest.FixtureRequest) -> GameSamples:
    marker = request.node.get_closest_marker("game")
    if marker is None or len(marker.args) != 1 or not isinstance(marker.args[0], str):
        raise pytest.UsageError("game_samples requires @pytest.mark.game(ID, build=BUILD)")
    build = marker.kwargs.get("build")
    if not isinstance(build, str) or not build:
        raise pytest.UsageError("game_samples requires an explicit build identifier")
    config_path = request.config.getoption("local_config")
    try:
        settings = load_local_environment(
            Path(config_path) if config_path else None, directory=request.config.rootpath
        )
    except (OSError, ValueError) as exc:
        raise pytest.UsageError(f"Invalid local environment: {exc}") from exc
    game = settings.find_game(marker.args[0])
    sample_option = request.config.getoption("samples_dir")
    if sample_option is not None:
        root = Path(sample_option)
        if not root.is_absolute():
            root = request.config.rootpath / root
        root = root.resolve() / marker.args[0] / build
    elif game is not None and game.samples_dir is not None:
        root = game.samples_dir
    else:
        root = settings.samples_dir / marker.args[0] / build
    if not root.is_dir():
        pytest.skip(f"Optional game sample directory is missing: {root}")
    original = _copies(request.config).get(marker.args[0])
    if original is None:
        original = game.original_dir if game is not None else None
    translated = game.translated_dir if game is not None else None
    return GameSamples(
        root, original or root / "restored-game-copy", translated or root / "gameplay-test-copy"
    )
