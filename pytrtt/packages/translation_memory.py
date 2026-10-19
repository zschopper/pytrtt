"""Bind historical source-text memories to independently extracted game records.

Legacy TMX IDs and notes are evidence about a memory export, not game record addresses.
Only CRLF and legacy XML newline literals are normalized; spaces remain significant.
"""

from dataclasses import replace

from pytrtt.packages.translation import (
    TranslationDocument,
    TranslationEntry,
    TranslationPackageError,
    TranslationResource,
)


def normalize_memory_source(text: str) -> str:
    return text.replace("&#13;", "\r").replace("&#10;", "\n").replace("\r\n", "\n")


def bind_translation_memory(
    memory: TranslationDocument, extracted: TranslationDocument
) -> TranslationDocument:
    """Copy translations onto verified record IDs, including every repeated occurrence.

    The extracted document supplies resource identities, languages, source text, and runtime.
    Ambiguous translations fail instead of inheriting the historical hash collision behavior.
    """
    if memory.entry_identity != "source_text" or extracted.entry_identity != "record":
        raise TranslationPackageError("expected source_text memory and extracted record document")
    if (memory.metadata.game_id, memory.metadata.target_language) != (
        extracted.metadata.game_id,
        extracted.metadata.target_language,
    ):
        raise TranslationPackageError("memory game or target language does not match extraction")
    lookup: dict[tuple[str, str], TranslationEntry] = {}
    for resource in (*memory.menu, *memory.subtitles):
        for entry in resource.entries:
            if entry.translation is None:
                continue
            key = (
                entry.source_language or memory.metadata.source_language,
                normalize_memory_source(entry.source),
            )
            previous = lookup.get(key)
            if previous is not None and (
                previous.translation != entry.translation
                or previous.substitution_disabled != entry.substitution_disabled
            ):
                raise TranslationPackageError(f"conflicting translation memory for {key!r}")
            lookup[key] = entry

    def bind(resource: TranslationResource) -> TranslationResource:
        result = []
        for entry in resource.entries:
            match = lookup.get(
                (
                    entry.source_language or extracted.metadata.source_language,
                    normalize_memory_source(entry.source),
                )
            )
            result.append(
                replace(
                    entry,
                    translation=match.translation,
                    substitution_disabled=match.substitution_disabled,
                )
                if match is not None and entry.translation is None
                else entry
            )
        return replace(resource, entries=tuple(result))

    if memory.fonts and extracted.fonts and memory.fonts != extracted.fonts:
        raise TranslationPackageError("memory and extraction contain conflicting fonts")
    return replace(
        extracted,
        menu=tuple(map(bind, extracted.menu)),
        subtitles=tuple(map(bind, extracted.subtitles)),
        fonts=memory.fonts or extracted.fonts,
    )
