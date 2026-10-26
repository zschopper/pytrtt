"""Anniversary demo package validation and opt-in extraction checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pytrtt.archives.bigfile import BigFileV1Handler
from pytrtt.development.profiles import load_profile
from pytrtt.packages.translation import parse_translation_document
from pytrtt.registry import default_registry
from pytrtt.services.translation import TranslationService, parse_filelist
from tests.game_samples import GameSamples

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/tomb-raider-anniversary-demo.json"
PACKAGE = ROOT / "translations/tomb-raider-anniversary-demo"


def test_anniversary_demo_package_is_complete_and_self_consistent() -> None:
    profile = load_profile(PROFILE)
    document = parse_translation_document((PACKAGE / "hu.json").read_text(encoding="utf-8"))
    assert profile.game_id == document.metadata.game_id == "tomb-raider-anniversary-demo"
    assert profile.build_id == document.metadata.build_id == "251873"
    assert document.runtime == profile.settings("hu")
    assert profile.compile(document, apply_defaults=True) == document
    assert isinstance(
        default_registry().archive(Path("."), profile.settings("hu").archive), BigFileV1Handler
    )
    names = parse_filelist(profile.filelist.read_text(encoding="utf-8"))
    assert len(names) == 64
    assert len(document.menu) == 1
    assert len(document.menu[0].entries) == 1001
    assert len(document.subtitles) == 62
    assert sum(len(resource.entries) for resource in document.subtitles) == 73
    for resource in (*document.menu, *document.subtitles):
        assert names[int(resource.resource_hash, 16)] == resource.resource_path
        assert all(entry.translation is not None for entry in resource.entries)
    menu = {entry.entry_id: entry for entry in document.menu[0].entries}
    assert menu[16].translation == menu[16].source
    assert menu[32].translation == menu[32].source
    assert menu[66].translation == menu[66].source
    assert menu[865].translation == (
        "Előre ugrás közben gyorsan nyomj ᠂ gombot a FECSKEUGRÁS kivitelezéséhez."
    )
    assert menu[866].translation == "*0865"
    assert menu[882].translation == (
        "Nyomj ᠁ gombot a gyűjthető tárgyak, például lőszerek és eü. csomagok FELVÉTELÉHEZ."
    )
    assert menu[883].translation == "*0882"
    assert len(document.fonts) == 1
    font = document.fonts[0]
    assert hashlib.sha256((PACKAGE / font.replacement_file).read_bytes()).hexdigest() == (
        font.replacement_sha256
    )
    provenance = json.loads((PACKAGE / "provenance.json").read_text(encoding="utf-8"))
    assert (
        provenance["package"]["translation_sha256"]
        == hashlib.sha256((PACKAGE / "hu.json").read_bytes()).hexdigest()
    )


@pytest.mark.integration
@pytest.mark.game("trad", build="251873")
def test_anniversary_demo_extraction_matches_packaged_sources(
    game_samples: GameSamples,
) -> None:
    game_samples.require(game_samples.original / "bigfile.000")
    profile = load_profile(PROFILE)
    result = TranslationService().extract(
        game_samples.original,
        profile.metadata("en", "hu"),
        profile.settings("hu"),
        parse_filelist(profile.filelist.read_text(encoding="utf-8")),
    )
    packaged = parse_translation_document((PACKAGE / "hu.json").read_text(encoding="utf-8"))
    for extracted, translated in (
        (result.document.menu, packaged.menu),
        (result.document.subtitles, packaged.subtitles),
    ):
        assert [
            (resource.resource_hash, [(entry.entry_id, entry.source) for entry in resource.entries])
            for resource in extracted
        ] == [
            (resource.resource_hash, [(entry.entry_id, entry.source) for entry in resource.entries])
            for resource in translated
        ]
    assert not result.skipped_resources
    assert result.empty_resources == 0
    assert len(result.recovery_assets) == 1
    assert hashlib.sha256(result.recovery_assets[0].data).hexdigest() == (
        packaged.fonts[0].source_sha256
    )
