import json
from pathlib import Path

import pytest

from scripts.package_data import collect_catalog_translation_data, collect_package_data


def test_collect_package_data_applies_ignore_patterns_and_negation(tmp_path: Path) -> None:
    (tmp_path / "translations/game/.backups").mkdir(parents=True)
    (tmp_path / "translations/game/assets").mkdir()
    (tmp_path / "translations/game/hu.json").write_text("{}", encoding="utf-8")
    (tmp_path / "translations/game/.backups/old.json").write_text("{}", encoding="utf-8")
    (tmp_path / "translations/game/assets/keep.bin").write_bytes(b"keep")
    (tmp_path / "translations/game/assets/drop.bin").write_bytes(b"drop")
    ignore_file = tmp_path / "packaging/package-data.ignore"
    ignore_file.parent.mkdir()
    ignore_file.write_text(
        "# Release package exclusions\n"
        "**/.backups/**\n"
        "translations/**/assets/*.bin\n"
        "!translations/**/assets/keep.bin\n",
        encoding="utf-8",
    )

    data = collect_package_data(
        tmp_path,
        (Path("translations"),),
        ignore_file,
    )

    assert data == [
        (
            str(tmp_path / "translations/game/assets/keep.bin"),
            "translations/game/assets",
        ),
        (str(tmp_path / "translations/game/hu.json"), "translations/game"),
    ]


def test_collect_package_data_rejects_patterns_outside_project(tmp_path: Path) -> None:
    (tmp_path / "translations").mkdir()
    outside = tmp_path.parent / "outside"
    ignore_file = tmp_path / "package-data.ignore"
    ignore_file.write_text("", encoding="utf-8")

    try:
        collect_package_data(tmp_path, (outside,), ignore_file)
    except ValueError as error:
        assert "outside the project root" in str(error)
    else:
        raise AssertionError("An include root outside the project should be rejected")


def test_collect_catalog_translation_data_includes_only_available_packages_and_assets(
    tmp_path: Path,
) -> None:
    package = tmp_path / "translations/game/hu.json"
    package.parent.mkdir(parents=True)
    asset = package.parent / "assets/font.bin"
    asset.parent.mkdir()
    asset.write_bytes(b"font")
    package.write_text(
        json.dumps({"fonts": [{"replacement_file": "assets/font.bin"}]}),
        encoding="utf-8",
    )
    (package.parent / "en.json").write_text("{}", encoding="utf-8")
    unavailable = tmp_path / "translations/future/hu.json"
    unavailable.parent.mkdir(parents=True)
    unavailable.write_text("{}", encoding="utf-8")
    catalog = tmp_path / "pytrtt/resources/gui_games.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        json.dumps(
            [
                {
                    "translation_file": "translations/game/hu.json",
                    "package_available": True,
                },
                {
                    "translation_file": "translations/future/hu.json",
                    "package_available": False,
                },
            ]
        ),
        encoding="utf-8",
    )

    assert collect_catalog_translation_data(tmp_path, catalog) == [
        (str(asset), "translations/game/assets"),
        (str(package), "translations/game"),
    ]


def test_collect_catalog_translation_data_rejects_missing_referenced_asset(tmp_path: Path) -> None:
    package = tmp_path / "translations/game/hu.json"
    package.parent.mkdir(parents=True)
    package.write_text(
        json.dumps({"fonts": [{"replacement_file": "assets/missing.bin"}]}),
        encoding="utf-8",
    )
    catalog = tmp_path / "gui_games.json"
    catalog.write_text(
        json.dumps(
            [
                {
                    "translation_file": "translations/game/hu.json",
                    "package_available": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Referenced translation asset is missing"):
        collect_catalog_translation_data(tmp_path, catalog)


def test_current_release_data_excludes_developer_translation_material() -> None:
    root = Path(__file__).resolve().parents[1]
    resources = collect_package_data(
        root,
        (root / "pytrtt/resources",),
        root / "packaging/package-data.ignore",
    )
    translations = collect_catalog_translation_data(
        root,
        root / "pytrtt/resources/gui_games.json",
    )
    selected = {Path(source).relative_to(root).as_posix() for source, _ in resources + translations}

    assert not any("/.backups/" in path for path in selected)
    assert not any(path.startswith("pytrtt/resources/filelists/") for path in selected)
    assert not any(path.endswith("provenance.json") for path in selected)
    translation_paths = {path for path in selected if path.startswith("translations/")}
    assert not any(path.endswith("/en.json") for path in translation_paths)
    assert not any(
        "memory" in path or "candidates" in path or "source" in path for path in translation_paths
    )
