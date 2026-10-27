"""Current draft coverage and immutable source identities must match their evidence."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from pytrtt.packages.translation import parse_translation_document

TRANSLATIONS = Path(__file__).resolve().parents[1] / "translations"


def test_rise_preserves_original_source_records() -> None:
    directory = TRANSLATIONS / "rise-of-the-tomb-raider"
    source = parse_translation_document((directory / "en.json").read_text(encoding="utf-8"))
    translated = parse_translation_document((directory / "hu.json").read_text(encoding="utf-8"))
    assert translated.metadata.build_id == source.metadata.build_id
    for originals, resources in (
        (source.menu, translated.menu),
        (source.subtitles, translated.subtitles),
    ):
        assert len(originals) == len(resources)
        for original, resource in zip(originals, resources, strict=True):
            assert len(original.entries) == len(resource.entries)
            restored = tuple(
                replace(entry, translation=prior.translation)
                for prior, entry in zip(original.entries, resource.entries, strict=True)
            )
            assert replace(resource, entries=restored) == original


def test_shadow_trial_preserves_source_slots_and_keys_from_legacy_export() -> None:
    directory = TRANSLATIONS / "shadow-of-the-tomb-raider-trial"
    source = json.loads((directory / "en.json").read_text(encoding="utf-8"))
    document = parse_translation_document((directory / "hu.json").read_text(encoding="utf-8"))
    assert document.metadata.build_id == source["metadata"]["build_id"]
    assert len(document.menu) == 1
    resource = document.menu[0]
    assert resource.resource_hash == source["metadata"]["resource_hash"]
    assert document.runtime is not None
    locale = resource.archive_locale
    if locale is None:
        locale = document.runtime.language(document.metadata.source_language).archive_locale
    assert locale == int(source["metadata"]["archive_locale"], 16)
    assert len(resource.entries) == len(source["entries"])
    for entry, prior in zip(resource.entries, source["entries"], strict=True):
        # Empty slots in the historical export use JSON null; the runtime schema uses empty text.
        assert (entry.entry_id, entry.key, entry.source) == (
            prior["id"],
            prior["key"],
            prior["source"] or "",
        )


def test_rise_current_coverage_and_package_hash_match_provenance() -> None:
    directory = TRANSLATIONS / "rise-of-the-tomb-raider"
    raw = (directory / "hu.json").read_bytes()
    document = parse_translation_document(raw.decode("utf-8"))
    provenance = json.loads((directory / "provenance.json").read_text(encoding="utf-8"))
    latest = provenance["complete_translation_review_20261027"]
    assert hashlib.sha256(raw).hexdigest() == latest["after_sha256"]
    interface = [entry for resource in document.menu for entry in resource.entries]
    subtitles = [entry for resource in document.subtitles for entry in resource.entries]
    assert len(interface) == 27113
    assert sum(entry.translation is not None for entry in interface) == 27111
    assert all(entry.translation is not None for entry in interface if entry.source.strip())
    assert provenance["french_import_cleanup_20261027"]["cleared_records"] == 730
    assert provenance["subtitle_syria_gameplay_20261027"]["corrected_existing_records"] == 6
    assert (
        provenance["subtitle_syria_cinematics_20261027"]["intentional_unchanged_name_records"] == 12
    )
    assert sum(entry.translation is not None for entry in subtitles) == 28214
    assert (
        sum(entry.translation is None and bool(entry.source.strip()) for entry in subtitles)
        == latest["subtitle_nonblank_missing"]
        == 0
    )
    assert (
        sum(entry.translation is not None for entry in interface + subtitles)
        == provenance["counts"]["translated_entries"]
    )
    assert (
        sum(entry.translation == entry.source and bool(entry.source.strip()) for entry in subtitles)
        == 205
    )


def test_rise_review_is_complete_and_hungarian_uses_real_double_accents() -> None:
    directory = TRANSLATIONS / "rise-of-the-tomb-raider"
    document = parse_translation_document((directory / "hu.json").read_text(encoding="utf-8"))
    provenance = json.loads((directory / "provenance.json").read_text(encoding="utf-8"))
    review = provenance["complete_translation_review_20261027"]
    assert review["reviewed_logical_import_groups"] == 9552
    assert review["pending_logical_import_groups"] == 0
    for resource in document.menu + document.subtitles:
        for entry in resource.entries:
            if entry.source.strip():
                assert entry.translation is not None
            if entry.translation is not None and not entry.source.startswith("FONT VALIDATION:"):
                assert not set("ôûÔÛ").intersection(entry.translation)
    assert len(document.fonts) == 1
    font = document.fonts[0]
    assert font.resource_hash == "55C5BF5F"
    assert font.embedded_id == 180260
    assert hashlib.sha256((directory / font.replacement_file).read_bytes()).hexdigest() == (
        font.replacement_sha256
    )


def test_rise_named_syria_resources_only_retain_source_equal_names() -> None:
    raw = (TRANSLATIONS / "rise-of-the-tomb-raider" / "hu.json").read_text(encoding="utf-8")
    document = parse_translation_document(raw)
    names = {
        "Lara:  Ana!",
        "Lara:  Jonah!",
        "Jonah:  Lara!",
        "Jonah, ",
        "Lara:  ... Jonah...?",
        "Jonah:  Lara...",
    }
    entries = [
        entry
        for resource in document.subtitles
        if "100_bp_black_sea_prologue" in resource.resource_path
        for entry in resource.entries
        if entry.source.strip()
    ]
    assert entries
    assert all(entry.translation is not None for entry in entries)
    # Imported captions normalize speaker-prefix spacing and may continue a
    # sentence after a name; these are no longer byte-identical to the source.
    assert not {entry.source for entry in entries if entry.translation == entry.source} - names
    named = [entry for entry in entries if entry.source in names]
    assert {entry.source for entry in named} == names
    for entry in named:
        assert entry.translation is not None
        assert "".join(entry.translation.split()).startswith("".join(entry.source.split()))


def test_rise_syria_import_meaning_corrections_match_english_sources() -> None:
    raw = (TRANSLATIONS / "rise-of-the-tomb-raider" / "hu.json").read_text(encoding="utf-8")
    document = parse_translation_document(raw)
    corrections = {
        "These people were buried alive.": "Ezeket az embereket élve temették el.",
        "These murals...": "Ezek a falfestmények...",
        "The Prophet's peace...upon his word,": "A Próféta békéje... szavára",
        "...when the drought of a thousand days choked the land,": (
            "...amikor ezer napig tartó aszály fojtogatta a vidéket,"
        ),
    }
    seen = set()
    for resource in document.subtitles:
        if "100_bp_black_sea_prologue\\100_bp_" not in resource.resource_path:
            continue
        for entry in resource.entries:
            if entry.source in corrections:
                assert entry.translation == corrections[entry.source]
                seen.add(entry.source)
    assert seen == corrections.keys()


def test_shadow_trial_updated_package_matches_roundtrip_evidence() -> None:
    directory = TRANSLATIONS / "shadow-of-the-tomb-raider-trial"
    raw = (directory / "hu.json").read_bytes()
    document = parse_translation_document(raw.decode("utf-8"))
    provenance = json.loads((directory / "provenance.json").read_text(encoding="utf-8"))
    evidence = provenance["updated_batch_gui_roundtrip_20261026"]
    assert hashlib.sha256(raw).hexdigest() == evidence["package_sha256"]
    entries = [entry for resource in document.menu for entry in resource.entries]
    assert len(entries) == 39345
    assert sum(entry.translation is not None for entry in entries) == 38055
    assert all(entry.translation is not None for entry in entries if entry.source.strip())
    assert evidence["post_restore_installation_enabled"]
    assert evidence["gui_restore_size_sha256_match"]
