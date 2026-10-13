"""Tests for the single-file, sectioned translation document format."""

from __future__ import annotations

import json

import pytest

from pytrtt.packages.translation import (
    FontAsset,
    TranslationDocument,
    TranslationEntry,
    TranslationMetadata,
    TranslationPackageError,
    TranslationResource,
    parse_translation_document,
    serialize_translation_document,
)

METADATA_ONLY = """{
  "schema_version": 1,
  "metadata": {
    "game_id": "tomb-raider-anniversary",
    "build_id": "842717",
    "source_language": "en",
    "target_language": "hu",
    "archive_format": "bigfile",
    "archive_version": 1
  }
}"""


def test_metadata_is_required_and_other_sections_are_optional() -> None:
    document = parse_translation_document(METADATA_ONLY)

    assert document.metadata.game_id == "tomb-raider-anniversary"
    assert document.menu == ()
    assert document.subtitles == ()
    assert document.fonts == ()
    assert '"menu"' not in serialize_translation_document(document)


def test_one_document_round_trips_menu_subtitle_and_font_sections() -> None:
    document = TranslationDocument(
        metadata=TranslationMetadata(
            game_id="tomb-raider-anniversary",
            build_id="842717",
            source_language="en",
            target_language="hu",
            archive_format="bigfile",
            archive_version=1,
        ),
        menu=(
            TranslationResource(
                resource_hash="7CD333D3",
                resource_path="pc-w\\local\\locals.bin",
                entries=(TranslationEntry(0, "Start game", "Játék indítása", "Menu label"),),
            ),
        ),
        subtitles=(
            TranslationResource(
                resource_hash="0BDB8EA3",
                resource_path="pc-w\\sndstrm\\vo\\lara\\intro.mul",
                entries=(TranslationEntry(12, "Hello Lara", "Szia, Lara!"),),
            ),
        ),
        fonts=(
            FontAsset(
                resource_hash="12345678",
                resource_path="pc-w\\font.raw",
                replacement_file="fonts/font_hu.raw",
                source_sha256="a" * 64,
                replacement_sha256="b" * 64,
            ),
        ),
    )

    serialized = serialize_translation_document(document)

    assert serialized.index('"metadata"') < serialized.index('"menu"')
    assert parse_translation_document(serialized) == document


def test_document_round_trips_cleared_and_omitted_subtitle_languages() -> None:
    document = TranslationDocument(
        TranslationMetadata("tra", "842717", "en", "hu", "bigfile", 1),
        clear_subtitle_languages=frozenset({2, 4}),
        omit_subtitle_languages=frozenset({1}),
    )

    serialized = serialize_translation_document(document)

    assert parse_translation_document(serialized) == document
    assert '"clear_subtitle_languages": [\n    2,\n    4\n  ]' in serialized
    assert '"omit_subtitle_languages": [\n    1\n  ]' in serialized


@pytest.mark.parametrize(
    "field,value",
    [
        ("clear_subtitle_languages", [256]),
        ("omit_subtitle_languages", [-1]),
        ("clear_subtitle_languages", [True]),
        ("omit_subtitle_languages", [1, 1]),
    ],
)
def test_document_rejects_invalid_subtitle_language_actions(field: str, value: object) -> None:
    content = METADATA_ONLY[:-1] + f', "{field}": {json.dumps(value)}' + "}"

    with pytest.raises(TranslationPackageError, match="subtitle language"):
        parse_translation_document(content)


def test_document_rejects_a_language_that_is_both_cleared_and_omitted() -> None:
    root = json.loads(METADATA_ONLY)
    root["clear_subtitle_languages"] = [1]
    root["omit_subtitle_languages"] = [1]
    content = json.dumps(root)

    with pytest.raises(TranslationPackageError, match="both cleared and omitted"):
        parse_translation_document(content)


def test_document_rejects_duplicate_resource_headers() -> None:
    resource = TranslationResource(
        resource_hash="7CD333D3",
        resource_path="pc-w\\local\\locals.bin",
        entries=(TranslationEntry(0, "Start game", None),),
    )
    document = TranslationDocument(
        TranslationMetadata("tra", "842717", "en", "hu", "bigfile", 1),
        menu=(resource,),
        subtitles=(resource,),
    )

    with pytest.raises(TranslationPackageError, match="duplicate resource hash"):
        parse_translation_document(serialize_translation_document(document))


def test_document_rejects_font_paths_that_escape_translation_package() -> None:
    document = TranslationDocument(
        TranslationMetadata("tra", "842717", "en", "hu", "bigfile", 1),
        fonts=(
            FontAsset(
                "12345678",
                "pc-w\\font.raw",
                "../outside.raw",
                "a" * 64,
                "b" * 64,
            ),
        ),
    )

    with pytest.raises(TranslationPackageError, match="safe relative path"):
        parse_translation_document(serialize_translation_document(document))


def test_document_rejects_windows_drive_font_paths() -> None:
    document = TranslationDocument(
        TranslationMetadata("tra", "842717", "en", "hu", "bigfile", 1),
        fonts=(
            FontAsset(
                "12345678",
                "pc-w\\font.raw",
                "C:/outside.raw",
                "a" * 64,
                "b" * 64,
            ),
        ),
    )

    with pytest.raises(TranslationPackageError, match="safe relative path"):
        parse_translation_document(serialize_translation_document(document))


@pytest.mark.parametrize(
    "content",
    [
        '{"schema_version":1}',
        METADATA_ONLY.replace('"archive_version": 1', '"archive_version": 0'),
        METADATA_ONLY.replace(
            '"game_id": "tomb-raider-anniversary",', '"game_id": "x", "extra": 1,'
        ),
        METADATA_ONLY.replace('"schema_version": 1', '"schema_version": 9'),
        METADATA_ONLY.replace('"build_id": "842717"', '"build_id": "842717", "build_id": "x"'),
    ],
)
def test_document_parser_rejects_missing_invalid_and_duplicate_metadata(content: str) -> None:
    with pytest.raises(TranslationPackageError):
        parse_translation_document(content)
