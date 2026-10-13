"""Tests for exporting Anniversary CINE source strings to translation packages."""

from __future__ import annotations

import struct
from dataclasses import replace

from pytrtt.formats.cine_v1 import parse_cine
from pytrtt.packages.cine import export_cine_package
from pytrtt.packages.translation import parse_translation_package, serialize_translation_package


def make_enic_resource(text: str) -> bytes:
    records = f"0\r{text}\r10\rCzech text\r1\rFrench text\r".encode()
    prefix = bytearray(0x10)
    struct.pack_into("<I", prefix, 0, 0x43494E45)
    struct.pack_into("<I", prefix, 4, 5)
    prefix.extend(b"ENIC")
    body = bytes(prefix) + bytes(0x60)
    body = body[:0x10] + b"ENIC" + body[0x14:]
    body = body[:0x70] + struct.pack("<I", len(records)) + records
    body += bytes((-len(body)) % 16)
    block = struct.pack("<4I", 0, len(body), 0x12345678, 0x90ABCDEF) + body
    return b"R" * 0x800 + block


def test_export_cine_package_contains_english_text_and_block_ids() -> None:
    resource = parse_cine(make_enic_resource("Hello Lara"))

    package = export_cine_package(
        resource,
        game_id="tomb-raider-anniversary",
        resource_hash="0BDB8EA3",
        build_id="842717",
    )

    assert package.game_id == "tomb-raider-anniversary"
    assert package.resource_hash == "0BDB8EA3"
    assert package.source_language == "en"
    assert package.target_language == "hu"
    assert [(entry.entry_id, entry.source, entry.translation) for entry in package.entries] == [
        (0, "Hello Lara", None)
    ]
    assert parse_translation_package(serialize_translation_package(package)) == package


def test_export_skips_blocks_without_english_subtitles() -> None:
    resource = parse_cine(make_enic_resource("Hello Lara"))
    block = resource.blocks[0]
    resource = replace(
        resource,
        blocks=(replace(block, subtitle_pairs=((10, "Czech"),), has_subtitles=True),),
    )

    package = export_cine_package(
        resource, game_id="tomb-raider-anniversary", resource_hash="0BDB8EA3", build_id="842717"
    )

    assert package.entries == ()
