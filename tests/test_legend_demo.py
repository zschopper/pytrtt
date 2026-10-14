"""Legend demo data validation and opt-in checks against local game copies."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from pytrtt.archives.bigfile import BigFileV1Handler
from pytrtt.development.profiles import load_profile
from pytrtt.formats.cine_v1 import parse_cine
from pytrtt.formats.locals_v1 import parse_locals
from pytrtt.packages.translation import parse_translation_document
from pytrtt.registry import default_registry
from pytrtt.services.translation import TranslationService, parse_filelist
from tests.game_samples import GameSamples

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles/tomb-raider-legend-demo.json"
PACKAGE = ROOT / "translations/tomb-raider-legend-demo"


def test_demo_uses_shared_handlers_and_complete_historical_translation() -> None:
    profile = load_profile(PROFILE)
    document = parse_translation_document((PACKAGE / "hu.json").read_text(encoding="utf-8"))
    assert profile.game_id == document.metadata.game_id == "tomb-raider-legend-demo"
    assert profile.build_id == document.metadata.build_id == "251815"
    assert document.runtime == profile.settings("hu")
    assert profile.compile(document, apply_defaults=True) == document
    assert isinstance(
        default_registry().archive(Path("."), profile.settings("hu").archive), BigFileV1Handler
    )
    names = parse_filelist(profile.filelist.read_text(encoding="utf-8"))
    assert len(document.menu) == 1
    assert len(document.menu[0].entries) == 1184
    assert len(document.subtitles) == 445
    assert sum(len(r.entries) for r in document.subtitles) == 492
    menu_entries = {entry.entry_id: entry for entry in document.menu[0].entries}
    assert not menu_entries[50].substitution_disabled
    assert not menu_entries[53].substitution_disabled
    for resource in (*document.menu, *document.subtitles):
        assert names[int(resource.resource_hash, 16)] == resource.resource_path
        assert all(entry.translation is not None for entry in resource.entries)
    assert len(document.fonts) == 1
    font = document.fonts[0]
    assert hashlib.sha256((PACKAGE / font.replacement_file).read_bytes()).hexdigest() == (
        font.replacement_sha256
    )
    provenance = json.loads((PACKAGE / "provenance.json").read_text(encoding="utf-8"))
    assert (
        provenance["translation_sha256"]
        == hashlib.sha256((PACKAGE / "hu.json").read_bytes()).hexdigest()
    )


@pytest.mark.integration
@pytest.mark.game("trld", build="251815")
def test_demo_full_extraction_matches_packaged_sources(game_samples: GameSamples) -> None:
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
            (r.resource_hash, [(e.entry_id, e.source) for e in r.entries]) for r in extracted
        ] == [(r.resource_hash, [(e.entry_id, e.source) for e in r.entries]) for r in translated]
    assert not result.skipped_resources
    assert result.empty_resources == 112
    assert len(result.recovery_assets) == 1
    assert hashlib.sha256(result.recovery_assets[0].data).hexdigest() == (
        packaged.fonts[0].source_sha256
    )


@pytest.mark.integration
@pytest.mark.game("trld", build="251815")
def test_demo_subset_translation_and_exact_restore(
    game_samples: GameSamples, tmp_path: Path
) -> None:
    original = game_samples.require("subset/original/bigfile.000")
    document_path = game_samples.require("subset/hu.json")
    document = parse_translation_document(document_path.read_text(encoding="utf-8"))
    game = tmp_path / "game"
    game.mkdir()
    shutil.copyfile(original, game / "bigfile.000")
    before = (game / "bigfile.000").read_bytes()
    service = TranslationService()
    build = service.plan(game, document, package_dir=PACKAGE)
    assert not build.missing_translations
    assert build.plan is not None
    assert sum(w.kind != "index" for w in build.plan.writes) == (
        len(document.menu) + len(document.subtitles) + 1
    )
    transaction = tmp_path / "transaction"
    service.apply(build, transaction)
    assert (game / "bigfile.000").read_bytes() != before
    assert document.runtime is not None
    archive = default_registry().archive(game, document.runtime.archive)
    font = document.fonts[0]
    font_ref = next(r for r in archive.resources() if r.name_hash == int(font.resource_hash, 16))
    assert archive.read(font_ref) == (PACKAGE / font.replacement_file).read_bytes()
    menu_ref = next(r for r in archive.resources() if r.name_hash == 0x7CD333D3)
    menu = parse_locals(archive.read(menu_ref))
    substitutions = {
        ord(source): target for source, target in document.runtime.character_substitutions
    }
    for entry in document.menu[0].entries:
        assert entry.translation is not None
        expected = entry.translation or " "
        if not entry.substitution_disabled:
            expected = expected.translate(substitutions)
        assert menu.entries[entry.entry_id].text == expected
    assert menu.entries[50].text == "Grafikus Vezérlô"
    assert menu.entries[53].text == "Teljesképernyôs Effektek"
    for resource in document.subtitles:
        reference = next(
            r for r in archive.resources() if r.name_hash == int(resource.resource_hash, 16)
        )
        cine = parse_cine(archive.read(reference))
        for entry in resource.entries:
            assert entry.translation is not None
            pairs = dict(cine.blocks[entry.entry_id].subtitle_pairs)
            assert pairs[0] == (entry.translation or " ").translate(substitutions)
            assert 1 not in pairs
    saved_font = transaction / "backups/restore-data/fonts/625B0E2D-FFFFFFFF.raw"
    assert hashlib.sha256(saved_font.read_bytes()).hexdigest() == font.source_sha256
    service.restore(game, transaction)
    assert (game / "bigfile.000").read_bytes() == before
    service.restore(game, transaction)
    assert (game / "bigfile.000").read_bytes() == before
