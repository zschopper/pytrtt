"""Select release data files using project-relative glob patterns."""

import json
from pathlib import Path, PurePath


def _read_patterns(ignore_file: Path) -> tuple[tuple[str, bool], ...]:
    patterns: list[tuple[str, bool]] = []
    for raw_line in ignore_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        included = line.startswith("!")
        pattern = line[1:] if included else line
        if pattern:
            patterns.append((pattern.lstrip("/"), included))
    return tuple(patterns)


def _is_included(relative_path: Path, patterns: tuple[tuple[str, bool], ...]) -> bool:
    included = True
    candidate = PurePath(relative_path.as_posix())
    for pattern, pattern_includes in patterns:
        if candidate.full_match(pattern):
            included = pattern_includes
    return included


def collect_package_data(
    project_root: Path,
    include_roots: tuple[Path, ...],
    ignore_file: Path,
) -> list[tuple[str, str]]:
    """Return PyInstaller data entries selected by project-relative glob patterns."""
    resolved_project_root = project_root.resolve()
    patterns = _read_patterns(ignore_file)
    selected: list[tuple[str, str]] = []

    for include_root in include_roots:
        source_root = (
            include_root.resolve()
            if include_root.is_absolute()
            else (resolved_project_root / include_root).resolve()
        )
        try:
            source_root.relative_to(resolved_project_root)
        except ValueError as error:
            message = f"Package data root is outside the project root: {source_root}"
            raise ValueError(message) from error

        for source in source_root.rglob("*"):
            if not source.is_file():
                continue
            relative_path = source.relative_to(resolved_project_root)
            if _is_included(relative_path, patterns):
                selected.append((str(source), relative_path.parent.as_posix()))

    return sorted(selected)


def collect_catalog_translation_data(
    project_root: Path,
    catalog_file: Path,
) -> list[tuple[str, str]]:
    """Collect available GUI translation documents and their referenced assets."""
    resolved_project_root = project_root.resolve()
    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
    if not isinstance(catalog, list):
        raise ValueError("GUI game catalog must be a list")

    selected: set[Path] = set()
    for item in catalog:
        if not isinstance(item, dict):
            raise ValueError("GUI game catalog entries must be objects")
        if item.get("package_available") is not True:
            continue
        translation_file = item.get("translation_file")
        if not isinstance(translation_file, str):
            raise ValueError("Available GUI catalog entries need a translation_file")
        package = (resolved_project_root / translation_file).resolve()
        try:
            package.relative_to(resolved_project_root)
        except ValueError as error:
            message = f"Translation package is outside the project root: {package}"
            raise ValueError(message) from error
        if not package.is_file():
            raise ValueError(f"Catalog translation package is missing: {package}")
        selected.add(package)

        document = json.loads(package.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError(f"Translation package must be an object: {package}")
        fonts = document.get("fonts", [])
        if not isinstance(fonts, list):
            raise ValueError(f"Translation package fonts must be a list: {package}")
        for font in fonts:
            if not isinstance(font, dict):
                raise ValueError(f"Translation font entries must be objects: {package}")
            replacement_file = font.get("replacement_file")
            if not isinstance(replacement_file, str):
                raise ValueError(f"Translation font needs a replacement_file: {package}")
            asset = (package.parent / replacement_file).resolve()
            if package.parent not in asset.parents or not asset.is_file():
                raise ValueError(f"Referenced translation asset is missing or unsafe: {asset}")
            selected.add(asset)

    return sorted(
        (str(source), source.relative_to(resolved_project_root).parent.as_posix())
        for source in selected
    )
