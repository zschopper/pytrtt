"""Generate Windows build metadata from the version in pyproject.toml."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def project_version(project_root: Path = PROJECT_ROOT) -> str:
    """Read and validate the release version from project metadata."""
    with (project_root / "pyproject.toml").open("rb") as stream:
        value = tomllib.load(stream)["project"]["version"]
    if not isinstance(value, str) or SEMANTIC_VERSION.fullmatch(value) is None:
        raise ValueError("project.version must use MAJOR.MINOR.PATCH")
    return value


def version_info(version: str) -> str:
    """Build a PyInstaller VSVersionInfo source file."""
    major, minor, patch = (int(part) for part in version.split("."))
    numeric = f"({major}, {minor}, {patch}, 0)"
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeric},
    prodvers={numeric},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'PyTRTT'),
         StringStruct('FileDescription', 'Tomb Raider Translation Toolkit'),
         StringStruct('FileVersion', '{version}'),
         StringStruct('InternalName', 'PyTRTT'),
         StringStruct('OriginalFilename', 'PyTRTT.exe'),
         StringStruct('ProductName', 'PyTRTT'),
         StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    """Write files consumed by PyInstaller, Inno Setup, and the application."""
    version = project_version()
    packaging = PROJECT_ROOT / "packaging"
    (packaging / "version-info.txt").write_text(version_info(version), encoding="utf-8")
    (packaging / "version.txt").write_text(version + "\n", encoding="ascii")
    (PROJECT_ROOT / "pytrtt/version.py").write_text(
        f'"""Application version synchronized from project metadata."""\n\nVERSION = "{version}"\n',
        encoding="utf-8",
    )
    print(version)


if __name__ == "__main__":
    main()
