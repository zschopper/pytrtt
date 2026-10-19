"""Comment arrays retain reviewer notes through both translation JSON formats."""

import json

import pytest

from pytrtt.packages.translation import (
    TranslationPackageError,
    parse_translation_document,
    parse_translation_package,
    serialize_translation_document,
    serialize_translation_package,
)


def content(comment: object, *, document: bool) -> str:
    entry = {"id": 0, "source": "Hello", "translation": "Szia", "comment": comment}
    metadata = {
        "game_id": "example",
        "build_id": "1",
        "source_language": "en",
        "target_language": "hu",
    }
    if document:
        root = {
            "schema_version": 1,
            "metadata": {**metadata, "archive_format": "bigfile", "archive_version": 1},
            "menu": [{"resource_hash": "12345678", "resource_path": "menu", "entries": [entry]}],
        }
    else:
        root = {"schema_version": 1, **metadata, "resource_hash": "12345678", "entries": [entry]}
    return json.dumps(root, ensure_ascii=False)


@pytest.mark.parametrize("document", [False, True])
@pytest.mark.parametrize(
    "notes", [[], [""], ["Árvíztűrő\nSecond line", "[revision: R1] Reason", ""]]
)
def test_comment_arrays_round_trip_in_order(notes: list[str], document: bool) -> None:
    if document:
        parsed = parse_translation_document(content(notes, document=True))
        assert parsed.menu[0].entries[0].comment == tuple(notes)
        serialized = serialize_translation_document(parsed)
        assert parse_translation_document(serialized) == parsed
        actual = json.loads(serialized)["menu"][0]["entries"][0]["comment"]
    else:
        package = parse_translation_package(content(notes, document=False))
        assert package.entries[0].comment == tuple(notes)
        serialized = serialize_translation_package(package)
        assert parse_translation_package(serialized) == package
        actual = json.loads(serialized)["entries"][0]["comment"]
    assert actual == notes


@pytest.mark.parametrize("document", [False, True])
def test_legacy_string_comments_are_normalized_on_read(document: bool) -> None:
    legacy = "First note\n\n[revision: R1] Reason\n"
    if document:
        parsed = parse_translation_document(content(legacy, document=True))
        serialized = serialize_translation_document(parsed)
        actual = json.loads(serialized)["menu"][0]["entries"][0]["comment"]
    else:
        package = parse_translation_package(content(legacy, document=False))
        serialized = serialize_translation_package(package)
        actual = json.loads(serialized)["entries"][0]["comment"]
    assert actual == ["First note", "", "[revision: R1] Reason", ""]
    assert "\n".join(actual) == legacy


@pytest.mark.parametrize("document", [False, True])
@pytest.mark.parametrize("invalid", [7, True, {}, ["Valid", 7], [None], [["Nested"]]])
def test_comments_reject_invalid_containers_and_elements(invalid: object, document: bool) -> None:
    parser = parse_translation_document if document else parse_translation_package
    with pytest.raises(TranslationPackageError, match=r"comment.*array of strings"):
        parser(content(invalid, document=document))


@pytest.mark.parametrize("document", [False, True])
def test_absent_or_null_comments_remain_optional(document: bool) -> None:
    root = json.loads(content(None, document=document))
    entry = root["menu"][0]["entries"][0] if document else root["entries"][0]
    for omit in (False, True):
        if omit:
            entry.pop("comment")
        if document:
            parsed = parse_translation_document(json.dumps(root))
            assert parsed.menu[0].entries[0].comment is None
        else:
            package = parse_translation_package(json.dumps(root))
            assert package.entries[0].comment is None
