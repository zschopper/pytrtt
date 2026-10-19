"""TRL data checks and opt-in integration checks for Steam build 251820."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pytrtt.development.profiles import load_profile
from pytrtt.packages.translation import parse_translation_document
from pytrtt.services.translation import TranslationService, parse_filelist
from tests.game_samples import GameSamples

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/tomb-raider-legend.json"
PACKAGE = ROOT / "translations/tomb-raider-legend"
DOCUMENT_PATH = PACKAGE / "hu.json"


def test_legend_hungarian_package_is_complete_for_the_verified_build() -> None:
    profile = load_profile(PROFILE)
    document = parse_translation_document(DOCUMENT_PATH.read_text(encoding="utf-8"))
    assert profile.game_id == document.metadata.game_id == "tomb-raider-legend"
    assert profile.build_id == document.metadata.build_id == "251820"
    assert document.runtime == profile.settings("hu")
    assert document.omit_subtitle_languages == frozenset({1})

    names = parse_filelist(profile.filelist.read_text(encoding="utf-8"))
    assert len(document.menu) == 1
    assert len(document.menu[0].entries) == 1268
    assert len(document.subtitles) == 1628
    assert sum(len(resource.entries) for resource in document.subtitles) == 2459
    for resource in (*document.menu, *document.subtitles):
        assert names[int(resource.resource_hash, 16)] == resource.resource_path
    for font in document.fonts:
        assert names[int(font.resource_hash, 16)] == font.resource_path

    menu = {entry.entry_id: entry for entry in document.menu[0].entries}
    assert menu[131].translation is not None
    assert menu[167].translation == " "
    assert menu[671].translation == " "
    assert all(entry.translation is not None for entry in menu.values())
    assert menu[46].substitution_disabled
    assert menu[50].substitution_disabled
    assert menu[53].substitution_disabled
    assert any(note.startswith("Historical source differed:") for note in menu[379].comment or ())
    assert any(note.startswith("Historical source differed:") for note in menu[381].comment or ())
    assert all(entry.translation is not None for r in document.subtitles for entry in r.entries)

    font = document.fonts[0]
    assert font.source_sha256 == "8743f75e1a1665b6f686b3eccb7e2dc84ee26f669e5fee26e9cafe93d9f7e1cb"
    assert hashlib.sha256((PACKAGE / font.replacement_file).read_bytes()).hexdigest() == (
        font.replacement_sha256
    )
    provenance = json.loads((PACKAGE / "provenance.json").read_text(encoding="utf-8"))
    assert (
        provenance["translation_sha256"] == hashlib.sha256(DOCUMENT_PATH.read_bytes()).hexdigest()
    )


@pytest.mark.integration
@pytest.mark.game("tomb-raider-legend", build="251820")
def test_legend_extraction_matches_public_translation_sources(game_samples: GameSamples) -> None:
    original = game_samples.require(game_samples.original / "bigfile.000")
    assert original.parent == game_samples.original
    profile = load_profile(PROFILE)
    extracted = TranslationService().extract(
        game_samples.original,
        profile.metadata("en", "hu"),
        profile.settings("hu"),
        parse_filelist(profile.filelist.read_text(encoding="utf-8")),
    )
    packaged = parse_translation_document(DOCUMENT_PATH.read_text(encoding="utf-8"))
    for actual, expected in (
        (extracted.document.menu, packaged.menu),
        (extracted.document.subtitles, packaged.subtitles),
    ):
        assert [
            (resource.resource_hash, [(entry.entry_id, entry.source) for entry in resource.entries])
            for resource in actual
        ] == [
            (resource.resource_hash, [(entry.entry_id, entry.source) for entry in resource.entries])
            for resource in expected
        ]
    assert not extracted.skipped_resources
    assert extracted.empty_resources == 313
    assert len(extracted.recovery_assets) == 1
    assert hashlib.sha256(extracted.recovery_assets[0].data).hexdigest() == (
        packaged.fonts[0].source_sha256
    )


@pytest.mark.integration
@pytest.mark.game("tomb-raider-legend", build="251820")
def test_legend_full_translation_has_a_safe_write_plan(game_samples: GameSamples) -> None:
    game_samples.require(game_samples.original / "bigfile.000")
    document = parse_translation_document(DOCUMENT_PATH.read_text(encoding="utf-8"))
    result = TranslationService().plan(
        game_samples.original,
        document,
        package_dir=PACKAGE,
        expected_build_id="251820",
    )
    assert result.plan is not None
    assert result.plan.sufficient_space
    assert not result.missing_translations
