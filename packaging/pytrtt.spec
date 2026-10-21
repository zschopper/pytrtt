"""PyInstaller one-file build for the Windows Qt client."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules
from scripts.package_data import collect_catalog_translation_data, collect_package_data

project_root = Path(SPECPATH).parent
gui_root = project_root / "pytrtt" / "resources" / "gui"
resource_data = collect_package_data(
    project_root,
    (project_root / "pytrtt" / "resources",),
    project_root / "packaging" / "package-data.ignore",
)
translation_data = collect_catalog_translation_data(
    project_root,
    project_root / "pytrtt" / "resources" / "gui_games.json",
)

analysis = Analysis(
    [str(project_root / "pytrtt" / "qt_gui.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[*resource_data, *translation_data, (str(project_root / "LICENSE"), ".")],
    hiddenimports=collect_submodules("PySide6.QtWebEngineCore"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="PyTRTT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(gui_root / "app-icon.png"),
    version=str(project_root / "packaging" / "version-info.txt"),
)
