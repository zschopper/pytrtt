"""Unit tests for the read-only Anniversary Bigfile v1 index reader."""

import hashlib
import json
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest

from pytrtt.archives.bigfile_v1 import (
    BigFileFormatError,
    extract_resource,
    read_bigfile_index,
)
from tests.game_samples import GameSamples

TRA_BOUNDARY = 0x09600000
SMALL_INDEX = bytes.fromhex(
    "0200000044332211887766550500000003000000e1ffffff0100000009000000072c01000800000002000000"
)


def test_read_bigfile_index_keeps_hash_order_and_unknown_record_fields() -> None:
    index = read_bigfile_index(BytesIO(SMALL_INDEX), TRA_BOUNDARY)

    assert len(index.entries) == 2
    assert index.entries[0].index == 0
    assert index.entries[0].hash == 0x11223344
    assert index.entries[0].length == 5
    assert index.entries[0].locale == 0xFFFFFFE1
    assert index.entries[0].unknown == 1
    assert index.entries[1].hash == 0x55667788
    assert index.entries[1].unknown == 2


def test_bigfile_location_uses_tra_boundary_and_2048_byte_blocks() -> None:
    index = read_bigfile_index(BytesIO(SMALL_INDEX), TRA_BOUNDARY)

    assert index.entries[0].part_and_offset(TRA_BOUNDARY) == (0, 3 * 2048)
    assert index.entries[1].part_and_offset(TRA_BOUNDARY) == (1, 7 * 2048)


def test_extract_resource_reads_only_indexed_bytes(tmp_path: Path) -> None:
    (tmp_path / "bigfile.000").write_bytes(b"index-part")
    (tmp_path / "bigfile.001").write_bytes(b"\0" * (3 * 2048) + b"hello" + b"suffix")
    entry = replace(
        read_bigfile_index(BytesIO(SMALL_INDEX), TRA_BOUNDARY).entries[1],
        length=5,
        location=TRA_BOUNDARY // 2048 + 3,
    )

    assert extract_resource(tmp_path, entry, TRA_BOUNDARY) == b"hello"


@pytest.mark.parametrize(
    "data",
    [
        b"\x02\x00\x00",
        bytes.fromhex("02000000") + b"\x00" * 12,
        bytes.fromhex("ffffffff"),
    ],
)
def test_rejects_truncated_or_impossible_bigfile_indexes(data: bytes) -> None:
    with pytest.raises(BigFileFormatError):
        read_bigfile_index(BytesIO(data), TRA_BOUNDARY)


def test_rejects_unaligned_boundary() -> None:
    with pytest.raises(BigFileFormatError):
        read_bigfile_index(BytesIO(SMALL_INDEX), TRA_BOUNDARY - 1)


@pytest.mark.integration
@pytest.mark.game("tra", build="842717")
def test_copied_anniversary_menu_entries_match_saved_samples(game_samples: GameSamples) -> None:
    game_dir = game_samples.original
    sample_dir = game_samples.root
    index_path = game_dir / "bigfile.000"
    metadata_path = sample_dir / "locals-samples.json"
    game_samples.require(index_path)
    game_samples.require(metadata_path)

    with index_path.open("rb") as stream:
        index = read_bigfile_index(stream, TRA_BOUNDARY)
    entries = index.find_hash(0x7CD333D3)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert len(entries) == len(metadata) == 5
    for entry, sample in zip(entries, metadata, strict=True):
        assert entry.index == sample["index_entry"]
        assert entry.locale == int(sample["locale_mask"], 16)
        content = extract_resource(game_dir, entry, TRA_BOUNDARY)
        assert hashlib.sha256(content).hexdigest() == sample["sha256"]
        assert content == game_samples.require(sample["sample"]).read_bytes()
