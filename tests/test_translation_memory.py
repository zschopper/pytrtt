import json
from pathlib import Path

import pytest

from pytrtt.packages.translation import (
    TranslationDocument,
    TranslationEntry,
    TranslationMetadata,
    TranslationPackageError,
    TranslationResource,
    parse_translation_document,
    serialize_translation_document,
)
from pytrtt.packages.translation_memory import bind_translation_memory
from pytrtt.services.translation import TranslationService


def document(*entries: TranslationEntry, identity: str = "record") -> TranslationDocument:
    return TranslationDocument(
        TranslationMetadata("example", "unverified", "en", "hu", "tiger", 3),
        menu=(TranslationResource("12345678", "locals.bin", entries),),
        entry_identity=identity,
    )


def test_memory_identity_round_trip_and_installation_guard(tmp_path: Path) -> None:
    memory = document(TranslationEntry(0, "A", "Á"), identity="source_text")
    serialized = serialize_translation_document(memory)
    assert json.loads(serialized)["schema_version"] == 4
    assert parse_translation_document(serialized) == memory
    with pytest.raises(TranslationPackageError, match="translation memory"):
        TranslationService().plan(tmp_path, memory, package_dir=tmp_path)


def test_binding_covers_repeated_occurrences_without_using_memory_ids() -> None:
    memory = document(TranslationEntry(700, "A\r\nB", "Á"), identity="source_text")
    extracted = document(TranslationEntry(2, "A\nB", None), TranslationEntry(5, "A\nB", None))
    bound = bind_translation_memory(memory, extracted)
    assert [(e.entry_id, e.translation) for e in bound.menu[0].entries] == [(2, "Á"), (5, "Á")]
    assert bound.entry_identity == "record"


def test_binding_keeps_spaces_and_source_languages_distinct() -> None:
    memory = document(
        TranslationEntry(0, "A", "English"),
        TranslationEntry(1, "A", "Russian", source_language="ru"),
        identity="source_text",
    )
    extracted = document(
        TranslationEntry(8, "A", None, source_language="ru"),
        TranslationEntry(9, " A", None),
    )
    entries = bind_translation_memory(memory, extracted).menu[0].entries
    assert entries[0].translation == "Russian"
    assert entries[1].translation is None


def test_conflicting_normalized_memory_entries_are_rejected() -> None:
    memory = document(
        TranslationEntry(0, "A\r\nB", "one"),
        TranslationEntry(1, "A\nB", "two"),
        identity="source_text",
    )
    with pytest.raises(TranslationPackageError, match="conflicting"):
        bind_translation_memory(memory, document(TranslationEntry(4, "A\nB", None)))


def test_legacy_context_is_preserved_without_becoming_record_identity() -> None:
    entry = TranslationEntry(
        0, "A", "Á", legacy_tuid="00069A", legacy_context=(("blockNo", "00000002"),)
    )
    memory = document(entry, identity="source_text")
    assert parse_translation_document(serialize_translation_document(memory)) == memory
    root = json.loads(serialize_translation_document(memory))
    root["schema_version"] = 3
    with pytest.raises(TranslationPackageError, match="schema version 4"):
        parse_translation_document(json.dumps(root))


def test_maintained_reboot_import_is_explicitly_a_memory() -> None:
    path = Path(__file__).resolve().parents[1] / "translations/tomb-raider/hu.json"
    memory = parse_translation_document(path.read_text(encoding="utf-8"))
    assert memory.entry_identity == "source_text"
    assert memory.runtime is None
    entries = [e for r in (*memory.menu, *memory.subtitles) for e in r.entries]
    assert len(entries) == 7910
    assert sum(e.source_language == "ru" for e in entries) == 8
    assert sum("time" in dict(e.legacy_context) for e in entries) == 555
    assert sum(e.legacy_tuid is not None for e in entries) == 7878
    assert (
        sum(e.comment is not None and "reviewed 2026-10-21" in e.comment[0] for e in entries) == 29
    )
    for resource in (*memory.menu, *memory.subtitles):
        assert [e.entry_id for e in resource.entries] == list(range(len(resource.entries)))
        assert all(
            dict(e.legacy_context)["hash"] == resource.resource_hash
            for e in resource.entries
            if e.legacy_context
        )


def test_same_hash_records_in_distinct_archive_locales_round_trip() -> None:
    from dataclasses import replace

    first = document(TranslationEntry(0, "A", None)).menu[0]
    extracted = replace(
        document(),
        menu=(
            replace(first, archive_locale=0xFFFFDD41),
            replace(first, archive_locale=0xFFFFFD41),
        ),
    )
    serialized = serialize_translation_document(extracted)
    assert json.loads(serialized)["schema_version"] == 4
    assert parse_translation_document(serialized) == extracted


def test_same_hash_locale_in_explicit_archive_layers_round_trips() -> None:
    from dataclasses import replace

    first = document(TranslationEntry(0, "A", None)).menu[0]
    extracted = replace(
        document(),
        menu=(
            replace(first, archive_locale=0xFFFF1101, archive_family="title"),
            replace(first, archive_locale=0xFFFF1101, archive_family="patch3"),
        ),
    )
    assert parse_translation_document(serialize_translation_document(extracted)) == extracted
