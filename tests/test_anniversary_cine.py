"""Tests for the Anniversary CINE subtitle resource format."""

from __future__ import annotations

import struct

import pytest

from pytrtt.formats.cine_v1 import (
    CineFormatError,
    apply_cine_translations,
    parse_cine,
)


def make_enic_resource(text: str) -> bytes:
    """Build an independent ENIC sample with two existing language records."""
    language_text = f"0\r{text}\r10\rCzech text\r1\rFrench text\r".encode()
    prefix = bytearray(0x10)
    struct.pack_into("<I", prefix, 0, 0x43494E45)
    struct.pack_into("<I", prefix, 4, 5)
    prefix.extend(b"ENIC")
    payload = bytes(prefix) + bytes(0x60)
    payload = payload[:0x10] + b"ENIC" + payload[0x14:]
    payload = payload[:0x70] + struct.pack("<I", len(language_text)) + language_text
    payload += bytes((-len(payload)) % 16)
    block = struct.pack("<4I", 0, len(payload), 0x12345678, 0x90ABCDEF) + payload
    return b"R" * 0x800 + block


def make_type1_subtitle_resource(text: str) -> bytes:
    """Build a non-ENIC type 1 block with a length-prefixed subtitle trailer."""
    raw_text = f"0\r{text}\r1\rAutre langue\r".encode()
    body = b"opaque" + bytes(2) + struct.pack("<I", len(raw_text)) + raw_text
    body += bytes((-((0x14 + len(body)) % 16)) % 16)
    block = bytearray(struct.pack("<4I", 1, len(body) + 4, 0x11111111, 0x22222222))
    block.extend(struct.pack("<I", len(body)))
    block.extend(body)
    return b"H" * 0x800 + bytes(block)


def test_parser_reads_enic_language_records_and_preserves_original_bytes() -> None:
    original = make_enic_resource("Hello")

    resource = parse_cine(original)

    assert resource.original_data == original
    assert len(resource.blocks) == 1
    assert resource.blocks[0].subtitle_pairs == (
        (0, "Hello"),
        (10, "Czech text"),
        (1, "French text"),
    )
    assert apply_cine_translations(resource, {}) == original


def test_translation_rebuilds_enic_text_and_preserves_other_languages() -> None:
    resource = parse_cine(make_enic_resource("Hello"))

    translated = apply_cine_translations(
        resource,
        {0: "Árvíztűrő tükörfúrógép"},
        substitutions={"ő": "ô", "ű": "û"},
    )
    reparsed = parse_cine(translated)

    assert reparsed.blocks[0].subtitle_pairs == (
        (0, "Árvíztûrô tükörfúrógép"),
        (10, "Czech text"),
        (1, "French text"),
    )
    assert translated[:0x800] == resource.original_data[:0x800]


def test_type1_subtitle_block_can_be_translated_and_reparsed() -> None:
    resource = parse_cine(make_type1_subtitle_resource("Hello"))

    translated = apply_cine_translations(resource, {0: "Magyar"})

    result = parse_cine(translated)
    assert result.blocks[0].block_type == 1
    assert result.blocks[0].subtitle_pairs == ((0, "Magyar"), (1, "Autre langue"))


def test_cleared_language_keeps_one_space_and_missing_translation_keeps_source() -> None:
    resource = parse_cine(make_enic_resource("Hello"))

    translated = apply_cine_translations(
        resource,
        {},
        cleared_languages=frozenset({1}),
    )

    assert parse_cine(translated).blocks[0].subtitle_pairs == (
        (0, "Hello"),
        (10, "Czech text"),
        (1, " "),
    )


def test_omitted_language_record_is_removed_entirely() -> None:
    resource = parse_cine(make_enic_resource("Hello"))
    from dataclasses import replace

    block = resource.blocks[0]
    resource = replace(
        resource,
        blocks=(
            replace(
                block,
                subtitle_pairs=(
                    (10, "Czech text"),
                    (0, "Hello"),
                    (1, "French text"),
                ),
            ),
        ),
    )

    translated = apply_cine_translations(
        resource,
        {0: "Magyar"},
        omitted_languages=frozenset({1}),
    )

    assert parse_cine(translated).blocks[0].subtitle_pairs == (
        (0, "Magyar"),
        (10, "Czech text"),
    )


def test_explicit_empty_translation_becomes_one_space() -> None:
    resource = parse_cine(make_enic_resource("Hello"))

    translated = apply_cine_translations(resource, {0: ""})

    assert parse_cine(translated).blocks[0].subtitle_pairs[0] == (0, " ")


def test_translation_target_without_english_record_is_rejected() -> None:
    resource = parse_cine(make_enic_resource("Hello"))
    block = resource.blocks[0]
    from dataclasses import replace

    resource = replace(resource, blocks=(replace(block, subtitle_pairs=((1, "French"),)),))

    with pytest.raises(CineFormatError, match="selected language record"):
        apply_cine_translations(resource, {0: "Magyar"})


@pytest.mark.parametrize(
    "data",
    [b"short", b"R" * 0x800],
)
def test_parser_rejects_truncated_or_empty_cine_files(data: bytes) -> None:
    with pytest.raises(CineFormatError):
        parse_cine(data)
