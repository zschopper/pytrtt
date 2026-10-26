"""Game-independent workflows and embedded runtime configuration."""

import json
import struct
from dataclasses import replace
from pathlib import Path

import pytest

from pytrtt.config import parse_runtime_settings
from pytrtt.packages.translation import (
    TranslationDocument,
    TranslationEntry,
    TranslationMetadata,
    TranslationPackageError,
    TranslationResource,
    parse_translation_document,
    serialize_translation_document,
)
from pytrtt.services.translation import TranslationService
from tests.game_samples import GameSamples


def runtime_value() -> dict[str, object]:
    return {
        "archive": {"format": "bigfile", "version": 1, "boundary": 65536, "data_subdir": "."},
        "languages": {
            "en": {"archive_locale": 4294967265, "subtitle_language": 0},
            "fr": {"archive_locale": 4294967265, "subtitle_language": 1},
        },
        "replacement_language": "en",
        "resource_types": [
            {"section": "menu", "pattern": "*/locals.bin", "format": "locals", "version": 1},
            {
                "section": "subtitles",
                "pattern": "*.mul",
                "format": "cine",
                "version": 1,
                "skip_unrecognized": True,
            },
            {
                "section": "fonts",
                "pattern": "*/font.raw",
                "format": "raw",
                "version": 1,
                "locale": 4294967295,
            },
        ],
        "character_substitutions": {},
    }


@pytest.mark.parametrize(
    "french_size,russian_size,translation_size,cleared",
    [(14000, 0, 14000, True), (100, 0, 14000, False), (6000, 6000, 20000, True)],
)
def test_french_capacity_fallback_roundtrip(
    tmp_path: Path, french_size: int, russian_size: int, translation_size: int, cleared: bool
) -> None:
    from pytrtt.formats.reboot_text import CineV2Handler
    from tests.test_reboot_text import cine

    game = tmp_path / "game"
    game.mkdir()
    pairs = b"0\rHello\r1\r" + b"F" * french_size + b"\r"
    if russian_size:
        pairs += b"9\r" + b"R" * russian_size + b"\r"
    content = cine(pairs, embedded=True)
    raw = bytearray(2048 + len(content))
    raw[:24] = struct.pack("<6I", 1, 0x87654321, len(content), 1, 0xFFFFFFE1, 99)
    raw[2048:] = content
    original = bytes(raw)
    (game / "bigfile.000").write_bytes(original)
    settings = runtime_value()
    settings["archive"] = {"format": "bigfile", "version": 1, "boundary": 32768, "data_subdir": "."}
    settings["resource_types"] = [
        {"section": "subtitles", "pattern": "*.mul", "format": "cine", "version": 2}
    ]
    doc = replace(
        document(),
        menu=(),
        clear_subtitle_languages_on_overflow=(1, 9),
        runtime=parse_runtime_settings(settings),
        subtitles=(
            TranslationResource(
                "87654321", "intro.mul", (TranslationEntry(0, "Hello", "H" * translation_size),)
            ),
        ),
    )
    doc = parse_translation_document(serialize_translation_document(doc))
    service = TranslationService()
    build = service.plan(game, doc, package_dir=tmp_path)
    assert build.plan is not None
    rewritten = next(w.data for w in build.plan.writes if w.kind == "resource")
    handler = CineV2Handler()
    assert handler.extract(rewritten, 0)[0].source == "H" * translation_size
    assert handler.extract(rewritten, 1)[0].source == (" " if cleared else "F" * french_size)
    if russian_size:
        assert handler.extract(rewritten, 9)[0].source == " "
    transaction = tmp_path / "transaction"
    service.apply(build, transaction)
    assert service.is_translation_installed(game, doc, package_dir=tmp_path)
    service.restore(game, transaction, doc.runtime)
    service.restore(game, transaction, doc.runtime)
    assert (game / "bigfile.000").read_bytes() == original
    assert service.plan(game, doc, package_dir=tmp_path).plan is not None


def test_conditional_clearing_rejects_replacement_language_before_opening_archive(
    tmp_path: Path,
) -> None:
    doc = replace(document(), clear_subtitle_languages_on_overflow=(1, 0))
    with pytest.raises(TranslationPackageError, match="replacement language"):
        TranslationService().plan(tmp_path / "missing", doc, package_dir=tmp_path)
    with pytest.raises(TranslationPackageError, match="replacement language"):
        parse_translation_document(serialize_translation_document(doc))


def make_archive(directory: Path) -> bytes:
    menu = bytes.fromhex("000000000200000000000000100000004100")
    raw = b"0\rHello\r1\rBonjour\r"
    payload = b"ENIC" + bytes(12) + struct.pack("<I", len(raw)) + raw
    payload += bytes(-len(payload) % 16)
    cine = bytes(0x800) + struct.pack("<4I", 1, len(payload), 0, 0) + payload
    values = ((0x12345678, menu, 0x800), (0x87654321, cine, 0x1000))
    index = struct.pack("<I2I", 2, *(v[0] for v in values))
    index += b"".join(struct.pack("<4I", len(v[1]), v[2] // 2048, 0xFFFFFFE1, 99) for v in values)
    data = bytearray(0x2800)
    data[: len(index)] = index
    for _, content, offset in values:
        data[offset : offset + len(content)] = content
    directory.mkdir()
    original = bytes(data)
    (directory / "bigfile.000").write_bytes(original)
    return original


def document(game_id: str = "fixture-a", target: str = "pt-BR") -> TranslationDocument:
    return TranslationDocument(
        TranslationMetadata(game_id, "build-1", "en", target, "bigfile", 1),
        menu=(
            TranslationResource(
                "12345678", "data/locals.bin", (TranslationEntry(0, "A", "Ação ő"),)
            ),
        ),
        subtitles=(
            TranslationResource(
                "87654321", "data/intro.mul", (TranslationEntry(0, "Hello", "Olá ő"),)
            ),
        ),
        runtime=parse_runtime_settings(runtime_value()),
    )


def test_embedded_settings_round_trip_without_a_developer_profile() -> None:
    doc = document()
    result = parse_translation_document(serialize_translation_document(doc))
    assert result == doc
    assert json.loads(serialize_translation_document(doc))["schema_version"] == 2


@pytest.mark.parametrize("game_id", ["fixture-a", "completely-new-game"])
def test_same_handlers_translate_any_game_and_language(tmp_path: Path, game_id: str) -> None:
    game = tmp_path / "game"
    original = make_archive(game)
    service = TranslationService()
    result = service.plan(game, document(game_id), package_dir=tmp_path)
    assert result.plan is not None
    assert result.missing_translations == ()
    transaction = tmp_path / "transaction"
    service.apply(result, transaction)
    assert b"A\xc3\xa7\xc3\xa3o \xc5\x91" in (game / "bigfile.000").read_bytes()
    assert b"Ol\xc3\xa1 \xc5\x91" in (game / "bigfile.000").read_bytes()
    service.restore(game, transaction, document(game_id).runtime)
    assert (game / "bigfile.000").read_bytes() == original


def test_character_substitution_is_data_and_can_be_disabled_per_record(tmp_path: Path) -> None:
    make_archive(tmp_path / "game")
    value = runtime_value()
    value["character_substitutions"] = {"ő": "ô"}
    doc = replace(document(), runtime=parse_runtime_settings(value))
    result = TranslationService().plan(tmp_path / "game", doc, package_dir=tmp_path)
    assert result.plan is not None
    assert any("Olá ô".encode() in w.data for w in result.plan.writes)
    flagged = replace(doc.menu[0].entries[0], substitution_disabled=True)
    doc = replace(doc, menu=(replace(doc.menu[0], entries=(flagged,)),))
    result = TranslationService().plan(tmp_path / "game", doc, package_dir=tmp_path)
    assert result.plan is not None
    assert any("Ação ő".encode() in w.data for w in result.plan.writes)


def test_replacement_language_selects_other_subtitle_slot(tmp_path: Path) -> None:
    from pytrtt.formats.cine_v1 import parse_cine

    make_archive(tmp_path / "game")
    value = runtime_value()
    value["replacement_language"] = "fr"
    doc = replace(document(), menu=(), runtime=parse_runtime_settings(value))
    result = TranslationService().plan(tmp_path / "game", doc, package_dir=tmp_path)
    assert result.plan is not None
    cine = next(w for w in result.plan.writes if w.kind == "resource")
    assert dict(parse_cine(cine.data).blocks[0].subtitle_pairs) == {0: "Hello", 1: "Olá ő"}


def test_unknown_format_version_fails_before_any_archive_write(tmp_path: Path) -> None:
    original = make_archive(tmp_path / "game")
    value = runtime_value()
    archive = value["archive"]
    assert isinstance(archive, dict)
    archive["version"] = 99
    doc = replace(
        document(),
        metadata=replace(document().metadata, archive_version=99),
        runtime=parse_runtime_settings(value),
    )
    with pytest.raises(TranslationPackageError, match="unsupported archive"):
        TranslationService().plan(tmp_path / "game", doc, package_dir=tmp_path)
    assert (tmp_path / "game/bigfile.000").read_bytes() == original


def test_missing_runtime_does_not_guess_a_game_profile(tmp_path: Path) -> None:
    doc = replace(document(), runtime=None)
    with pytest.raises(TranslationPackageError, match="runtime"):
        TranslationService().plan(tmp_path, doc, package_dir=tmp_path)


@pytest.mark.parametrize(
    "field,value", [("character_substitutions", {"ab": "x"}), ("replacement_language", "missing")]
)
def test_runtime_rejects_invalid_settings(field: str, value: object) -> None:
    settings = runtime_value()
    settings[field] = value
    with pytest.raises(ValueError):
        parse_runtime_settings(settings)


def test_registered_format_version_can_handle_a_new_game(tmp_path: Path) -> None:
    from pytrtt.formats.contracts import TextFormatHandler, TextOptions
    from pytrtt.registry import default_registry

    class CustomFormat(TextFormatHandler):
        def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
            return (TranslationEntry(0, "custom source", None),)

        def write(
            self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
        ) -> bytes:
            return b"custom format:" + options.text(entries[0]).encode()

    game = tmp_path / "game"
    original = make_archive(game)
    value = runtime_value()
    value["resource_types"] = [
        {"section": "menu", "pattern": "*.widget", "format": "custom", "version": 7},
    ]
    doc = replace(
        document("new-game"),
        runtime=parse_runtime_settings(value),
        subtitles=(),
        menu=(
            TranslationResource(
                "12345678", "ui/menu.widget", (TranslationEntry(0, "custom source", "Olá"),)
            ),
        ),
    )
    registry = default_registry()
    registry.formats[("custom", 7)] = CustomFormat()
    service = TranslationService(registry)
    result = service.plan(game, doc, package_dir=tmp_path)
    assert result.plan is not None
    assert result.plan.writes[0].data == b"custom format:Ol\xc3\xa1"
    transaction = tmp_path / "transaction"
    service.apply(result, transaction)
    service.restore(game, transaction)
    assert (game / "bigfile.000").read_bytes() == original


@pytest.mark.parametrize("subdir", ["../other", "/tmp", "C:/games", "dir\\child"])
def test_archive_directory_must_stay_inside_game(subdir: str) -> None:
    value = runtime_value()
    value["archive"] = {"format": "bigfile", "version": 1, "boundary": 65536, "data_subdir": subdir}
    with pytest.raises(ValueError, match="safe relative"):
        parse_runtime_settings(value)


def test_ambiguous_resource_rules_never_choose_a_handler(tmp_path: Path) -> None:
    game = tmp_path / "game"
    original = make_archive(game)
    value = runtime_value()
    value["resource_types"] = [
        {"section": "menu", "pattern": "*/locals.bin", "format": "locals", "version": 1},
        {"section": "menu", "pattern": "*.bin", "format": "locals", "version": 1},
    ]
    doc = replace(document(), runtime=parse_runtime_settings(value))
    with pytest.raises(ValueError, match="ambiguous"):
        TranslationService().plan(game, doc, package_dir=tmp_path)
    assert (game / "bigfile.000").read_bytes() == original


@pytest.mark.integration
@pytest.mark.game("tra", build="842717")
def test_tra_menu_handler_preserves_pre_refactor_binary_result(game_samples: GameSamples) -> None:
    import hashlib

    from pytrtt.formats.contracts import TextOptions
    from pytrtt.registry import default_registry

    original_path = game_samples.require("bigfile.000-entry-2058-FFFFFFE1.bin")
    doc = parse_translation_document(
        Path("translations/tomb-raider-anniversary/hu.json").read_text(encoding="utf-8")
    )
    assert doc.runtime is not None
    rule = doc.runtime.rule(doc.menu[0].resource_path, "menu")
    assert rule is not None
    handler = default_registry().text_format(rule.format, rule.version)
    output = handler.write(
        original_path.read_bytes(),
        doc.menu[0].entries,
        TextOptions(0, doc.runtime.character_substitutions),
    )
    assert len(output) == 56335
    assert (
        hashlib.sha256(output).hexdigest()
        == "58b2464bff168138acc18120167559c0fa0260057fe5564639e6b9be22742bea"
    )


@pytest.mark.integration
@pytest.mark.game("tra", build="842717")
def test_tra_extraction_and_all_formats_match_verified_local_copy(
    game_samples: GameSamples,
) -> None:
    import hashlib

    from pytrtt.development.profiles import load_profile
    from pytrtt.formats.contracts import TextOptions
    from pytrtt.registry import default_registry
    from pytrtt.services.translation import parse_filelist

    original_dir = game_samples.original
    translated_dir = game_samples.translated
    game_samples.require(original_dir / "bigfile.000")
    game_samples.require(translated_dir / "bigfile.000")
    profile = load_profile(Path("profiles/tomb-raider-anniversary.json"))
    runtime = profile.settings("hu")
    names = parse_filelist(profile.filelist.read_text(encoding="utf-8"))
    extracted = TranslationService().extract(
        original_dir, profile.metadata("en", "hu"), runtime, names
    )
    assert len(extracted.document.menu) == 1
    assert len(extracted.document.subtitles) == 283
    assert sum(len(r.entries) for r in extracted.document.menu) == 1419
    assert sum(len(r.entries) for r in extracted.document.subtitles) == 484
    assert extracted.empty_resources == 46
    assert not extracted.skipped_resources
    assert len(extracted.recovery_assets) == 1
    doc = parse_translation_document(
        Path("translations/tomb-raider-anniversary/hu.json").read_text(encoding="utf-8")
    )
    registry = default_registry()
    original = registry.archive(original_dir, runtime.archive)
    translated = registry.archive(translated_dir, runtime.archive)
    old_refs = {(r.name_hash, r.locale): r for r in original.resources()}
    new_refs = {(r.name_hash, r.locale): r for r in translated.resources()}
    language = runtime.language("en")
    options = TextOptions(
        language.subtitle_language,
        runtime.character_substitutions,
        doc.clear_subtitle_languages,
        doc.omit_subtitle_languages,
    )
    for section, resources, sources in (
        ("menu", doc.menu, extracted.document.menu),
        ("subtitles", doc.subtitles, extracted.document.subtitles),
    ):
        assert [
            (r.resource_hash, [(e.entry_id, e.source) for e in r.entries]) for r in resources
        ] == [(r.resource_hash, [(e.entry_id, e.source) for e in r.entries]) for r in sources]
        for resource in resources:
            rule = runtime.rule(resource.resource_path, section)
            assert rule is not None
            handler = registry.text_format(rule.format, rule.version)
            key = (int(resource.resource_hash, 16), language.archive_locale)
            generated = handler.write(original.read(old_refs[key]), resource.entries, options)
            assert generated == translated.read(new_refs[key]), resource.resource_hash
    font = doc.fonts[0]
    assert hashlib.sha256(extracted.recovery_assets[0].data).hexdigest() == font.source_sha256
    assert (
        hashlib.sha256(
            translated.read(new_refs[(int(font.resource_hash, 16), 0xFFFFFFFF)])
        ).hexdigest()
        == font.replacement_sha256
    )
