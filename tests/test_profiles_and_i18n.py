"""Developer compilation and shared, independently selectable UI messages."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from pytrtt.cli import main
from pytrtt.development.profiles import load_profile
from pytrtt.i18n import Translator
from pytrtt.packages.translation import (
    TranslationEntry,
    TranslationPackageError,
    parse_translation_document,
    serialize_translation_document,
)
from tests.test_generic_translation import document, make_archive, runtime_value


def profile_file(root: Path) -> Path:
    path = root / "developer.json"
    value = {
        "schema_version": 1,
        "game_id": "fixture-a",
        "build_id": "build-1",
        "filelist": "names.txt",
        "asset_root": ".",
        "runtime": runtime_value(),
        "translation_defaults": {"hu": {"character_substitutions": {"ő": "ô"}}},
    }
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def test_compiled_document_works_after_profile_is_removed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    game = tmp_path / "game"
    original = make_archive(game)
    path = profile_file(tmp_path)
    profile = load_profile(path)
    source = replace(document(target="hu"), runtime=None)
    compiled = profile.compile(source)
    assert compiled.menu == source.menu
    assert compiled.subtitles == source.subtitles
    assert compiled.runtime is not None
    assert compiled.runtime.character_substitutions == (("ő", "ô"),)
    translation = tmp_path / "hu.json"
    translation.write_text(serialize_translation_document(compiled), encoding="utf-8")
    path.unlink()
    assert (
        main(
            ["--game-dir", str(game), "--translation-file", str(translation), "--ui-language", "hu"]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert Translator("hu").text("dry_run") in output
    assert "Menu" not in output
    assert (game / "bigfile.000").read_bytes() == original


def test_profile_selects_defaults_by_translation_language(tmp_path: Path) -> None:
    profile = load_profile(profile_file(tmp_path))
    assert profile.settings("pt-BR").character_substitutions == ()
    assert profile.settings("hu").character_substitutions == (("ő", "ô"),)
    with pytest.raises(TranslationPackageError, match="different games"):
        profile.compile(document("other-game"))


def test_profile_can_supply_ordered_optional_capacity_languages(tmp_path: Path) -> None:
    path = profile_file(tmp_path)
    value = json.loads(path.read_text())
    value["translation_defaults"]["hu"]["clear_subtitle_languages_on_overflow"] = [9, 1]
    path.write_text(json.dumps(value))
    profile = load_profile(path)
    source = document(target="hu")
    assert profile.compile(source).clear_subtitle_languages_on_overflow == ()
    compiled = profile.compile(source, apply_defaults=True)
    assert compiled.clear_subtitle_languages_on_overflow == (9, 1)
    assert parse_translation_document(serialize_translation_document(compiled)) == compiled


def test_legacy_empty_translation_remains_space_when_substitution_is_disabled() -> None:
    from pytrtt.formats.locals_v1 import parse_locals
    from pytrtt.packages.locals import apply_menu_package, export_menu_package

    resource = parse_locals(bytes.fromhex("000000000200000000000000100000004100"))
    package = export_menu_package(
        resource, game_id="fixture", resource_hash="12345678", build_id="1"
    )
    package = replace(package, entries=(TranslationEntry(0, "A", "", substitution_disabled=True),))
    result = apply_menu_package(resource, package, expected_build_id="1")
    assert parse_locals(result).entries[0].text == " "


def test_catalogs_keep_identical_keys_and_parameters() -> None:
    english, hungarian = Translator(), Translator("hu")
    assert english.base.keys() == hungarian.localized.keys()
    assert hungarian.text("missing_count", count=7) == "Hiányzó fordítások: 7"
    assert Translator("pt-BR").text("no_changes") == english.text("no_changes")


@pytest.mark.parametrize(
    ("language", "interface", "subtitles"),
    [("en", "Interface", "Subtitles"), ("hu", "Felhasználói felület", "Feliratok")],
)
def test_content_category_names(language: str, interface: str, subtitles: str) -> None:
    translator = Translator(language)
    assert translator.text("section_menu") == interface
    assert translator.text("section_subtitles") == subtitles


def test_invalid_catalog_parameters_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "en.json").write_text('{"message": "Count: {count}"}', encoding="utf-8")
    (tmp_path / "hu.json").write_text('{"message": "Darab: {different}"}', encoding="utf-8")
    with pytest.raises(ValueError, match="placeholder"):
        Translator("hu", catalog_root=tmp_path)
    with pytest.raises(ValueError, match="language"):
        Translator("../hu", catalog_root=tmp_path)


def test_schema_two_requires_runtime_settings() -> None:
    value = json.loads(serialize_translation_document(document()))
    del value["metadata"]["runtime"]
    with pytest.raises(TranslationPackageError, match="runtime"):
        parse_translation_document(json.dumps(value))


def test_help_uses_selected_ui_catalog(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--ui-language", "hu", "--help"])
    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert Translator("hu").text("help_usage") in output
    assert Translator("hu").text("help_translation_file") in output


def test_missing_translation_field_keeps_original_and_is_reported(tmp_path: Path) -> None:
    from pytrtt.services.translation import TranslationService

    game = tmp_path / "game"
    original = make_archive(game)
    value = json.loads(serialize_translation_document(replace(document(), subtitles=())))
    del value["menu"][0]["entries"][0]["translation"]
    parsed = parse_translation_document(json.dumps(value))
    result = TranslationService().plan(game, parsed, package_dir=tmp_path)
    assert result.plan is None
    assert [(item.section, item.entry_id, item.source) for item in result.missing_translations] == [
        ("menu", 0, "A")
    ]
    assert (game / "bigfile.000").read_bytes() == original
