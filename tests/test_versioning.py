from __future__ import annotations

import tomllib
from pathlib import Path

from pytrtt.version import VERSION
from scripts.generate_windows_version import project_version, version_info


def test_application_version_has_one_project_metadata_source() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as stream:
        configured = tomllib.load(stream)["project"]["version"]

    assert configured == VERSION == project_version(root) == "0.2.0"


def test_windows_version_resource_uses_four_numeric_components() -> None:
    generated = version_info("2.3.4")

    assert "filevers=(2, 3, 4, 0)" in generated
    assert "prodvers=(2, 3, 4, 0)" in generated
    assert "StringStruct('ProductVersion', '2.3.4')" in generated
