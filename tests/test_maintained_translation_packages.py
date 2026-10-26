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
    latest = provenance["french_import_cleanup_20261027"]
    assert hashlib.sha256(raw).hexdigest() == latest["after_sha256"]
    interface = [entry for resource in document.menu for entry in resource.entries]
    subtitles = [entry for resource in document.subtitles for entry in resource.entries]
    assert len(interface) == 27113
    assert sum(entry.translation is not None for entry in interface) == 27111
    assert all(entry.translation is not None for entry in interface if entry.source.strip())
    assert latest["cleared_records"] == 730
    assert sum(entry.translation is not None for entry in subtitles) == 8618
    assert (
        sum(entry.translation is None and bool(entry.source.strip()) for entry in subtitles)
        == latest["subtitle_nonblank_missing"]
        == 19596
    )
    assert (
        sum(entry.translation is not None for entry in interface + subtitles)
        == provenance["counts"]["translated_entries"]
    )
    assert (
        sum(entry.translation == entry.source and bool(entry.source.strip()) for entry in subtitles)
        == 6517
    )


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
