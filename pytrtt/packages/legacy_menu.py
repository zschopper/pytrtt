"""Importer for the historical indexed ``menu.txt`` translation format."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pytrtt.packages.translation import TranslationEntry, TranslationPackage

ENTRY_MARKER = re.compile(r"@([0-9]{4})\Z")
ALIAS_MARKER = re.compile(r"\*([0-9]+)\Z")


class LegacyMenuImportError(ValueError):
    """Raised when a historical menu export cannot be imported safely."""


@dataclass(frozen=True, slots=True)
class LegacyMenuImportReport:
    """Summary of the source comparison and legacy directives during import."""

    exact_source_matches: int
    whitespace_source_differences: int
    content_source_differences: int
    aliases_preserved: int
    deleted_entries_replaced: int
    untranslated_entries: int


@dataclass(frozen=True, slots=True)
class _LegacyEntry:
    entry_id: int
    source: str
    payload: tuple[str, ...]
    comments: tuple[str, ...]


def _parse_entries(content: str) -> dict[int, _LegacyEntry]:
    entries: dict[int, _LegacyEntry] = {}
    current_id: int | None = None
    source_lines: list[str] = []
    payload_lines: list[str] = []
    comments: list[str] = []
    in_payload = False

    def save_current() -> None:
        if current_id is None:
            return
        if current_id in entries:
            raise LegacyMenuImportError(f"duplicate legacy entry id: {current_id}")
        while payload_lines and payload_lines[-1] == "":
            payload_lines.pop()
        entries[current_id] = _LegacyEntry(
            current_id,
            "\n".join(source_lines),
            tuple(payload_lines),
            tuple(comment for comment in comments if comment),
        )

    for line_number, line in enumerate(content.removeprefix("\ufeff").splitlines(), start=1):
        marker = ENTRY_MARKER.fullmatch(line)
        if marker:
            save_current()
            current_id = int(marker.group(1))
            source_lines = []
            payload_lines = []
            comments = []
            in_payload = False
            continue
        if current_id is None:
            if line.strip() and not line.startswith(";"):
                raise LegacyMenuImportError(f"content outside an entry at line {line_number}")
            continue
        if line.startswith(";"):
            comments.append(line[1:])
        elif not in_payload and line.startswith("#"):
            source_lines.append(line[1:])
        elif not line and not in_payload:
            in_payload = True
        else:
            in_payload = True
            payload_lines.append(line)

    save_current()
    return entries


def _normalized_source(text: str) -> str:
    return " ".join(text.split())


def import_legacy_menu(
    content: str,
    package: TranslationPackage,
) -> tuple[TranslationPackage, LegacyMenuImportReport]:
    """Merge legacy translations by entry id while retaining review context in comments.

    Historical source text is used only for comparison. The current package source remains
    authoritative, so subsequent imports still validate against the selected game build.
    """
    legacy_entries = _parse_entries(content)
    package_entries = {entry.entry_id: entry for entry in package.entries}
    missing = package_entries.keys() - legacy_entries.keys()
    extra = legacy_entries.keys() - package_entries.keys()
    if missing:
        raise LegacyMenuImportError(f"legacy export is missing entry ids: {sorted(missing)[:8]}")
    if extra:
        raise LegacyMenuImportError(f"legacy export has unknown entry ids: {sorted(extra)[:8]}")

    alias_targets: dict[int, int] = {}
    translated_payloads: dict[int, str | None] = {}
    directives_by_id: dict[int, tuple[str, ...]] = {}
    comments_by_id: dict[int, tuple[str, ...]] = {}
    exact_matches = 0
    whitespace_differences = 0
    content_differences = 0
    deleted = 0
    untranslated = 0

    for entry_id, old in legacy_entries.items():
        current = package_entries[entry_id]
        if old.source == current.source:
            exact_matches += 1
        elif _normalized_source(old.source) == _normalized_source(current.source):
            whitespace_differences += 1
        else:
            content_differences += 1

        body = list(old.payload)
        directives = tuple(
            line
            for line in body
            if line == "$DEL" or line == "$SETUP" or line.startswith("$PALYA=")
        )
        body = [line for line in body if line not in directives]
        alias = ALIAS_MARKER.fullmatch(body[0]) if len(body) == 1 else None
        if alias:
            target = int(alias.group(1))
            alias_targets[entry_id] = target
            translated_payloads[entry_id] = f"*{target:04d}"
        elif "$DEL" in directives:
            translated_payloads[entry_id] = "?"
            deleted += 1
        else:
            value = "\n".join(body)
            value = value.replace("!TESZT! ", "")
            translated_payloads[entry_id] = value if value else None
            if not value:
                untranslated += 1
        directives_by_id[entry_id] = directives
        comments_by_id[entry_id] = old.comments

    visiting: set[int] = set()
    validated: set[int] = set()

    def validate_alias(entry_id: int) -> None:
        if entry_id in validated:
            return
        if entry_id in visiting:
            raise LegacyMenuImportError(
                f"legacy translation alias cycle includes entry id {entry_id}"
            )
        if entry_id not in legacy_entries:
            raise LegacyMenuImportError(
                f"legacy translation alias references missing id {entry_id}"
            )
        visiting.add(entry_id)
        if entry_id in alias_targets:
            validate_alias(alias_targets[entry_id])
        visiting.remove(entry_id)
        validated.add(entry_id)

    for entry_id in alias_targets:
        validate_alias(entry_id)

    aliases_preserved = 0
    merged: list[TranslationEntry] = []
    for current in package.entries:
        entry_id = current.entry_id
        translation = translated_payloads[entry_id]
        comments = list(comments_by_id[entry_id])
        for directive in directives_by_id[entry_id]:
            comments.append(f"Legacy directive: {directive}")
        if entry_id in alias_targets:
            comments.append(f"Legacy alias: *{alias_targets[entry_id]:04d}")
            aliases_preserved += 1
        if "$DEL" in directives_by_id[entry_id]:
            comments.append(
                "Legacy $DEL directive mapped to the historical visible placeholder '?'."
            )
        old_source = legacy_entries[entry_id].source
        if old_source != current.source and _normalized_source(old_source) != _normalized_source(
            current.source
        ):
            comments.append(f"Historical source differed: {old_source}")
        merged.append(
            TranslationEntry(
                entry_id=current.entry_id,
                source=current.source,
                translation=translation,
                comment="\n".join(comments) if comments else current.comment,
                substitution_disabled="$SETUP" in directives_by_id[entry_id],
            )
        )

    result = TranslationPackage(
        game_id=package.game_id,
        build_id=package.build_id,
        resource_hash=package.resource_hash,
        source_language=package.source_language,
        target_language=package.target_language,
        entries=tuple(merged),
    )
    return result, LegacyMenuImportReport(
        exact_source_matches=exact_matches,
        whitespace_source_differences=whitespace_differences,
        content_source_differences=content_differences,
        aliases_preserved=aliases_preserved,
        deleted_entries_replaced=deleted,
        untranslated_entries=untranslated,
    )
