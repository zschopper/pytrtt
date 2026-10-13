"""Bridge between indexed menu entries and editable translation packages."""

from __future__ import annotations

from collections.abc import Mapping

from pytrtt.formats.locals_v1 import MenuFormatError, MenuResource, write_locals
from pytrtt.packages.translation import (
    TranslationEntry,
    TranslationPackage,
    TranslationPackageError,
)


def export_menu_package(
    resource: MenuResource,
    *,
    build_id: str,
    game_id: str,
    resource_hash: str,
    source_language: str = "en",
    target_language: str = "hu",
) -> TranslationPackage:
    """Create an editable package from all non-placeholder menu entries."""
    return TranslationPackage(
        game_id=game_id,
        build_id=build_id,
        resource_hash=resource_hash,
        source_language=source_language,
        target_language=target_language,
        entries=tuple(
            TranslationEntry(entry.index, entry.text, None)
            for entry in resource.entries
            if entry.text is not None
        ),
    )


def apply_menu_package(
    resource: MenuResource,
    package: TranslationPackage,
    *,
    expected_build_id: str,
    substitutions: Mapping[str, str] | None = None,
) -> bytes:
    """Apply translations after checking build and source text."""
    if package.build_id != expected_build_id:
        raise TranslationPackageError("package targets a different game build")

    replacements: dict[int, str] = {}
    for entry in package.entries:
        if entry.entry_id >= len(resource.entries):
            raise TranslationPackageError(f"entry id {entry.entry_id} is outside the menu resource")
        source_entry = resource.entries[entry.entry_id]
        if source_entry.text is None:
            raise TranslationPackageError(f"entry id {entry.entry_id} targets a placeholder")
        if source_entry.text != entry.source:
            raise TranslationPackageError(f"source text changed for entry id {entry.entry_id}")
        if entry.translation is not None:
            replacements[entry.entry_id] = (
                (entry.translation or " ")
                if entry.substitution_disabled
                else (entry.translation or " ").translate(
                    {ord(source): target for source, target in (substitutions or {}).items()}
                )
            )

    try:
        return write_locals(resource, replacements)
    except MenuFormatError as exc:
        raise TranslationPackageError(str(exc)) from exc
