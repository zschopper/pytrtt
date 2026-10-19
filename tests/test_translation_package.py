"""Tests for the editable, comment-preserving translation package format."""

import pytest

from pytrtt.formats.locals_v1 import parse_locals, write_locals
from pytrtt.packages.locals import apply_menu_package, export_menu_package
from pytrtt.packages.translation import (
    TranslationEntry,
    TranslationPackage,
    TranslationPackageError,
    parse_translation_package,
    serialize_translation_package,
)

VALID_PACKAGE = """{
  "schema_version": 1,
  "game_id": "tomb-raider-anniversary",
  "build_id": "842717",
  "resource_hash": "7CD333D3",
  "source_language": "en",
  "target_language": "hu",
  "entries": [
    {
      "id": 0,
      "source": "Choose \\\"quality\\\"\\nnow",
      "translation": "Válassz minőséget",
      "comment": ["Rövid gombfelirat."]
    },
    {"id": 1, "source": "Not translated", "translation": null},
    {"id": 2, "source": "Intentionally empty", "translation": ""}
  ]
}"""


def test_parse_package_keeps_metadata_comments_and_translation_states() -> None:
    package = parse_translation_package(VALID_PACKAGE)

    assert package.game_id == "tomb-raider-anniversary"
    assert package.source_language == "en"
    assert package.target_language == "hu"
    assert package.entries[0].source == 'Choose "quality"\nnow'
    assert package.entries[0].translation == "Válassz minőséget"
    assert package.entries[0].comment == ("Rövid gombfelirat.",)
    assert package.entries[1].translation is None
    assert package.entries[2].translation == ""


def test_serialize_and_parse_keeps_comments_unicode_and_newlines() -> None:
    package = parse_translation_package(VALID_PACKAGE)

    serialized = serialize_translation_package(package)
    reparsed = parse_translation_package(serialized)

    assert "Válassz minőséget" in serialized
    assert reparsed == package


def test_serialize_and_parse_keeps_legacy_character_substitution_flag() -> None:
    package = parse_translation_package(VALID_PACKAGE)
    flagged = TranslationPackage(
        game_id=package.game_id,
        build_id=package.build_id,
        resource_hash=package.resource_hash,
        source_language=package.source_language,
        target_language=package.target_language,
        entries=(
            TranslationEntry(
                package.entries[0].entry_id,
                package.entries[0].source,
                package.entries[0].translation,
                substitution_disabled=True,
            ),
            *package.entries[1:],
        ),
    )

    reparsed = parse_translation_package(serialize_translation_package(flagged))

    assert reparsed == flagged


@pytest.mark.parametrize(
    "content",
    [
        VALID_PACKAGE.replace('"id": 2', '"id": 1'),
        VALID_PACKAGE.replace('"schema_version": 1', '"schema_version": 2'),
        VALID_PACKAGE.replace(
            '"game_id": "tomb-raider-anniversary",', '"game_id": "x", "game_id": "y",'
        ),
        VALID_PACKAGE.replace('"comment": ["Rövid gombfelirat."]', '"comment": 7'),
    ],
)
def test_rejects_duplicate_keys_ids_unsupported_schemas_and_invalid_types(content: str) -> None:
    with pytest.raises(TranslationPackageError):
        parse_translation_package(content)


def test_export_apply_round_trip_preserves_comments_outside_game_resource() -> None:
    menu_fixture = bytes.fromhex("00000000040000000000000018000000000000001a00000041004200")
    resource = parse_locals(menu_fixture)
    package = export_menu_package(
        resource, game_id="tomb-raider-anniversary", resource_hash="7CD333D3", build_id="842717"
    )
    editable = parse_translation_package(serialize_translation_package(package))
    translated = editable.entries[0]
    with_comment = TranslationPackage(
        game_id=editable.game_id,
        build_id=editable.build_id,
        resource_hash=editable.resource_hash,
        source_language=editable.source_language,
        target_language=editable.target_language,
        entries=(
            TranslationEntry(
                translated.entry_id, translated.source, "Árvíztűrő ŐőŰű", ("Fit check",)
            ),
            editable.entries[1],
        ),
    )

    output = apply_menu_package(
        resource,
        with_comment,
        expected_build_id="842717",
        substitutions={"Ő": "Ô", "ő": "ô", "Ű": "Û", "ű": "û"},
    )

    assert parse_locals(output).entries[0].text == "Árvíztûrô ÔôÛû"
    assert b"Fit check" not in output
    assert write_locals(resource) == menu_fixture


def test_menu_package_applies_anniversary_font_character_mapping() -> None:
    fixture = bytes.fromhex("00000000040000000000000018000000000000001a00000041004200")
    resource = parse_locals(fixture)
    package = export_menu_package(
        resource, game_id="tomb-raider-anniversary", resource_hash="7CD333D3", build_id="842717"
    )
    mapped = TranslationPackage(
        game_id=package.game_id,
        build_id=package.build_id,
        resource_hash=package.resource_hash,
        source_language=package.source_language,
        target_language=package.target_language,
        entries=(TranslationEntry(0, "A", "Árvíztűrő ŐőŰű"), package.entries[1]),
    )

    output = apply_menu_package(
        resource,
        mapped,
        expected_build_id="842717",
        substitutions={"Ő": "Ô", "ő": "ô", "Ű": "Û", "ű": "û"},
    )

    assert parse_locals(output).entries[0].text == "Árvíztûrô ÔôÛû"


def test_legacy_setup_directive_preserves_hungarian_double_accents() -> None:
    fixture = bytes.fromhex("00000000040000000000000018000000000000001a00000041004200")
    resource = parse_locals(fixture)
    package = export_menu_package(
        resource, game_id="tomb-raider-anniversary", resource_hash="7CD333D3", build_id="842717"
    )
    configured = TranslationPackage(
        game_id=package.game_id,
        build_id=package.build_id,
        resource_hash=package.resource_hash,
        source_language=package.source_language,
        target_language=package.target_language,
        entries=(
            TranslationEntry(0, "A", "Fényerő", substitution_disabled=True),
            package.entries[1],
        ),
    )

    output = apply_menu_package(
        resource,
        configured,
        expected_build_id="842717",
        substitutions={"Ő": "Ô", "ő": "ô", "Ű": "Û", "ű": "û"},
    )

    assert parse_locals(output).entries[0].text == "Fényerő"


def test_apply_rejects_wrong_build_or_changed_source() -> None:
    resource = parse_locals(
        bytes.fromhex("00000000040000000000000018000000000000001a00000041004200")
    )
    package = export_menu_package(
        resource, game_id="tomb-raider-anniversary", resource_hash="7CD333D3", build_id="842717"
    )

    with pytest.raises(TranslationPackageError, match="different game build"):
        apply_menu_package(resource, package, expected_build_id="other-build")

    changed = TranslationPackage(
        game_id=package.game_id,
        build_id=package.build_id,
        resource_hash=package.resource_hash,
        source_language=package.source_language,
        target_language=package.target_language,
        entries=(TranslationEntry(0, "old source", "Translation"),),
    )
    with pytest.raises(TranslationPackageError, match="source text changed"):
        apply_menu_package(
            resource,
            changed,
            expected_build_id="842717",
            substitutions={"Ő": "Ô", "ő": "ô", "Ű": "Û", "ű": "û"},
        )
