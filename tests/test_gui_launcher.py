"""Static checks for the native Windows GUI launcher."""

from pathlib import Path


def test_windows_launcher_uses_project_environment_and_preserves_arguments() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / "scripts/run-gui.cmd").read_text(encoding="utf-8")
    assert 'cd /d "%~dp0.."' in content
    assert '".venv\\Scripts\\python.exe" -m pytrtt.gui %*' in content
    assert "py -3.13 -m pytrtt.gui %*" in content
    assert "py -3.14 -m pytrtt.gui %*" in content
    assert "python -m pytrtt.gui %*" in content
