"""Static checks for the native Windows GUI launcher."""

from pathlib import Path


def test_windows_launcher_uses_python_and_preserves_arguments() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / "scripts/run-gui.cmd").read_text(encoding="utf-8")
    assert 'cd /d "%~dp0.."' in content
    assert "python -m pytrtt.qt_gui --recovery-in-game %*" in content
    assert not (root / "pytrtt/gui.py").exists()


def test_qt_gui_keeps_in_game_recovery_behind_an_explicit_switch() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / "pytrtt/qt_gui.py").read_text(encoding="utf-8")
    assert 'recovery_in_game = "--recovery-in-game" in parser_arguments' in content
    assert "game_transaction_root(inspection.candidate.path)" in content
    assert "PROJECT_ROOT = application_resource_root()" in content


def test_qt_gui_stores_user_preferences_in_local_app_data_ini() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / "pytrtt/qt_gui.py").read_text(encoding="utf-8")
    assert 'os.environ.get("LOCALAPPDATA")' in content
    assert 'settings_dir / "settings.ini"' in content
    assert '"ui/show_welcome"' in content
    assert '"ui/language"' in content
    assert 'self._settings.setValue("ui/language", language)' in content
    assert "self._settings.sync()" in content
    assert 'settings.value("ui/language", locale, type=str)' in content
    assert "def setWelcomeEnabled" in content


def test_qt_gui_disables_user_zoom_controls() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / "pytrtt/qt_gui.py").read_text(encoding="utf-8")
    assert "class FixedZoomWebEngineView" in content
    assert "Qt.KeyboardModifier.ControlModifier" in content
    assert "view.setZoomFactor(1.0)" in content
    assert "installEventFilter(self)" in content
    assert '"--disable-direct-composition"' in content
    assert "def exitApplication" in content
    assert 'smoke_test = "--smoke-test" in parser_arguments' in content
    assert "frontendReady.connect" in content
    assert "QTimer.singleShot(30_000" in content


def test_qt_gui_protects_active_file_operations_on_close() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / "pytrtt/qt_gui.py").read_text(encoding="utf-8")
    assert "def closeEvent" in content
    assert "QMessageBox" in content
    assert "request_safe_exit" in content
    assert "safeExitCompleted" in content
    assert "def setApplicationLanguage" in content
    assert "applicationLanguageChanged" in content
    assert "def copyText" in content
    assert "def launchGame" in content
    assert 'launch_uri = f"steam://rungameid/{app_id}"' in content
    assert "QDesktopServices.openUrl" in content
    assert "def recover_interrupted_operations" in content
    assert "find_interrupted_transactions_in_roots" in content
    assert "recover_interrupted_transaction" in content
    assert "QTimer.singleShot(0, window.recover_interrupted_operations)" in content
    assert 'self._translator.text("gui_confirm_yes")' in content
    assert 'self._translator.text("gui_confirm_no")' in content


def test_windows_packaging_builds_an_installed_app_and_preserves_recovery_data() -> None:
    root = Path(__file__).resolve().parents[1]
    specification = (root / "packaging/pytrtt.spec").read_text(encoding="utf-8")
    installer = (root / "packaging/PyTRTT.iss").read_text(encoding="utf-8")
    build = (root / "scripts/build-windows.cmd").read_text(encoding="utf-8")
    archive = (root / "scripts/archive-windows-exe.ps1").read_text(encoding="utf-8")
    assert 'name="PyTRTT"' in specification
    assert "project_root = Path(SPECPATH).parent" in specification
    assert 'project_root / "pytrtt" / "qt_gui.py"' in specification
    assert 'project_root / "packaging" / "package-data.ignore"' in specification
    assert "collect_package_data" in specification
    assert "collect_catalog_translation_data" in specification
    assert 'version=str(project_root / "packaging" / "version-info.txt")' in specification
    assert "console=False" in specification
    assert 'project_root / "pytrtt" / "resources" / "gui_games.json"' in specification
    assert "python -m PyInstaller" in build
    assert 'set "PYTRTT_BUILD_ROOT=%LOCALAPPDATA%\\PyTRTT\\build-cache"' in build
    assert '--workpath "%PYTRTT_BUILD_ROOT%\\work"' in build
    assert '--distpath "%PYTRTT_BUILD_ROOT%\\dist"' in build
    assert "archive-windows-exe.ps1" in build
    assert build.index("archive-windows-exe.ps1") < build.index(
        'copy /Y "%PYTRTT_BUILD_ROOT%\\dist\\PyTRTT.exe"'
    )
    assert 'copy /Y "%PYTRTT_BUILD_ROOT%\\dist\\PyTRTT.exe"' in build
    assert 'if /I "%~1"=="--clean"' in build
    assert 'python -m pip install "pyinstaller>=6" "pillow>=11"' in build
    assert 'python -m pip install "pyside6>=6.10.1,<6.11"' in build
    assert "ISCC.exe" in build
    assert "generate_windows_version.py" in build
    assert "/DAppVersion=%PYTRTT_VERSION%" in build
    assert '"dist\\PyTRTT.exe" --smoke-test' in build
    assert ".VersionInfo.ProductVersion" in archive
    assert '"${applicationName}-v${version}.exe"' in archive
    assert '"${applicationName}-v${version}.${suffix}.exe"' in archive
    assert "Move-Item -LiteralPath $resolvedTarget -Destination $candidate" in archive
    assert "UninstallDisplayName={#AppName}" in installer
    assert "{localappdata}\\PyTRTT" in installer
    assert "Recovery data stored beside games will always be kept." in installer
    assert "PyTRTT Recovery" not in installer


def test_windows_visual_smoke_checklist_covers_required_scaling() -> None:
    root = Path(__file__).resolve().parents[1]
    checklist = (root / "docs/windows-gui-smoke-checklist.md").read_text(encoding="utf-8")
    for scale in ("100%", "125%", "150%", "200%"):
        assert scale in checklist
    assert "960 × 640" in checklist
    assert "high-contrast/forced-colors" in checklist
    assert "Tab" in checklist
