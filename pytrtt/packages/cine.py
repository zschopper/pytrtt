"""Bridge between indexed CINE subtitles and editable translation packages."""

from __future__ import annotations

import re

from pytrtt.formats.cine_v1 import CineResource
from pytrtt.packages.translation import (
    TranslationEntry,
    TranslationPackage,
    TranslationPackageError,
)


def export_cine_package(
    resource: CineResource,
    *,
    resource_hash: str,
    build_id: str,
    game_id: str,
    subtitle_language: int = 0,
    source_language: str = "en",
    target_language: str = "hu",
) -> TranslationPackage:
    """Export selected-language CINE subtitle records, using each block index as its stable ID."""
    if re.fullmatch(r"[0-9A-Fa-f]{8}", resource_hash) is None:
        raise TranslationPackageError("resource_hash must contain exactly eight hexadecimal digits")

    entries: list[TranslationEntry] = []
    for block_index, block in enumerate(resource.blocks):
        selected_texts = [
            text for language, text in block.subtitle_pairs if language == subtitle_language
        ]
        if len(selected_texts) > 1:
            raise TranslationPackageError(
                f"CINE block {block_index} contains multiple selected-language subtitle records"
            )
        if selected_texts:
            entries.append(TranslationEntry(block_index, selected_texts[0], None))

    return TranslationPackage(
        game_id=game_id,
        build_id=build_id,
        resource_hash=resource_hash.upper(),
        source_language=source_language,
        target_language=target_language,
        entries=tuple(entries),
    )
