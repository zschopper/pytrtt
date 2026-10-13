"""Unit tests for the Tomb Raider: Anniversary menu resource."""

import json

import pytest

from pytrtt.formats.locals_v1 import MenuFormatError, parse_locals, write_locals
from tests.game_samples import GameSamples

MINIMAL_RESOURCE = bytes.fromhex("00000000040000000000000018000000000000001a00000041004200")


def test_parse_menu_header_entries_and_placeholder() -> None:
    resource = parse_locals(MINIMAL_RESOURCE)

    assert resource.language_code == 0
    assert resource.entry_count_fields == (4, 0)
    assert [entry.text for entry in resource.entries] == ["A", None, "B"]
    assert resource.entries[1].offset == 0


def test_write_unchanged_menu_as_exact_original_bytes() -> None:
    resource = parse_locals(MINIMAL_RESOURCE)

    assert write_locals(resource) == MINIMAL_RESOURCE


def test_write_longer_hungarian_text_preserves_header_and_placeholder() -> None:
    resource = parse_locals(MINIMAL_RESOURCE)

    translated = write_locals(resource, {2: "Árvíztűrő ŐőŰű"})
    reparsed = parse_locals(translated)

    assert reparsed.language_code == 0
    assert reparsed.entry_count_fields == (4, 0)
    assert reparsed.entries[1].offset == 0
    assert [entry.text for entry in reparsed.entries] == ["A", None, "Árvíztűrő ŐőŰű"]
    assert len(translated) > len(MINIMAL_RESOURCE)


def test_write_rebuilds_duplicate_strings_as_separate_menu_entries() -> None:
    shared_resource = bytes.fromhex("00000000040000000000000018000000180000001a00000041004200")
    resource = parse_locals(shared_resource)

    translated = write_locals(resource, {2: "C"})
    result = parse_locals(translated)

    assert result.entries[0].text == result.entries[1].text == "A"
    assert result.entries[0].offset != result.entries[1].offset


def test_write_preserves_embedded_newlines_in_text() -> None:
    resource = parse_locals(MINIMAL_RESOURCE)

    translated = write_locals(resource, {0: "első sor\nmásodik sor"})

    assert parse_locals(translated).entries[0].text == "első sor\nmásodik sor"


@pytest.mark.parametrize(
    "content",
    [
        b"short",
        bytes.fromhex("0000000004000000"),
        bytes.fromhex("00000000040000000000000014000000000000001a00000041004200"),
        bytes.fromhex("00000000040000000000000018000000000000001a000000ff004200"),
        bytes.fromhex("00000000040000000000000018000000000000001d00000041004200"),
    ],
)
def test_rejects_truncated_or_invalid_menu_resources(content: bytes) -> None:
    with pytest.raises(MenuFormatError):
        parse_locals(content)


@pytest.mark.integration
@pytest.mark.game("tra", build="842717")
def test_copied_anniversary_language_samples_round_trip_and_accept_translation(
    game_samples: GameSamples,
) -> None:
    sample_dir = game_samples.root
    metadata_path = sample_dir / "locals-samples.json"
    game_samples.require(metadata_path)

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for sample in metadata:
        original = game_samples.require(sample["sample"]).read_bytes()
        resource = parse_locals(original)
        assert len(resource.entries) == 1419
        assert write_locals(resource) == original

    english_sample = next(row for row in metadata if row["locale_mask"] == "FFFFFFE1")
    english_data = (sample_dir / english_sample["sample"]).read_bytes()
    english_resource = parse_locals(english_data)
    translated_text = "Árvíztűrő tükörfúrógép: ŐőŰű"
    translated_data = write_locals(english_resource, {0: translated_text})

    assert parse_locals(translated_data).entries[0].text == translated_text
