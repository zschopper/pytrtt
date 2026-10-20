"""Packaged resource lookup for the Qt graphical client."""

from __future__ import annotations

from pathlib import Path

APPLICATION_RESOURCE_ROOT = Path(__file__).resolve().parent.parent
GUI_RESOURCE_ROOT = APPLICATION_RESOURCE_ROOT / "pytrtt" / "resources" / "gui"


def application_resource_root() -> Path:
    """Return the source or one-file bundle root containing release data."""
    return APPLICATION_RESOURCE_ROOT


def gui_resource(name: str) -> Path:
    """Return a packaged GUI resource without allowing directory traversal."""
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("GUI resource names must be safe relative paths")
    resource = GUI_RESOURCE_ROOT / relative
    if not resource.is_file():
        raise FileNotFoundError(resource)
    return resource


def is_packaged_file(path: str | Path) -> bool:
    """Return whether a filesystem path resolves inside the GUI resource directory."""
    requested = Path(path).resolve()
    resource_root = gui_resource("index.html").parent.resolve()
    return requested.is_relative_to(resource_root)
