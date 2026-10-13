"""Tests for non-mutating Bigfile replacement planning."""

from __future__ import annotations

import hashlib
import shutil
import struct
from io import BytesIO
from pathlib import Path

import pytest

from pytrtt.archives.bigfile_v1 import (
    BigFileEntry,
    BigFileIndex,
    extract_resource,
    read_bigfile_index,
)
from pytrtt.archives.write_plan import (
    BigFilePlanError,
    BigFileReplacement,
    plan_replacements,
    serialize_bigfile_index,
)
from pytrtt.formats.locals_v1 import parse_locals
from pytrtt.packages.locals import apply_menu_package
from pytrtt.packages.translation import TranslationPackage, parse_translation_document
from tests.game_samples import GameSamples


def build_index(entries: tuple[BigFileEntry, ...]) -> bytes:
    hashes = b"".join(struct.pack("<I", entry.hash) for entry in entries)
    records = b"".join(
        struct.pack("<4I", entry.length, entry.location, entry.locale, entry.unknown)
        for entry in entries
    )
    return struct.pack("<I", len(entries)) + hashes + records


def make_entry(
    index: int, name_hash: int, length: int, part: int, offset: int, boundary: int
) -> BigFileEntry:
    location = (part * boundary + offset) // 0x800
    return BigFileEntry(index, name_hash, length, location, 0xFFFFFFE1, 0xABC00000 + index)


def test_plan_overwrites_when_replacement_fits_existing_slot(tmp_path: Path) -> None:
    boundary = 0x4000
    entry = make_entry(0, 0x12345678, 20, 0, 4096, boundary)
    index = BigFileIndex((entry,))
    (tmp_path / "bigfile.000").write_bytes(build_index(index.entries) + b"\0" * 8192)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    plan = plan_replacements(
        tmp_path,
        index,
        (BigFileReplacement("menu", entry.hash, entry.locale, b"translated"),),
        boundary,
    )

    archive_write = next(
        write
        for write in plan.writes
        if write.file_name == "bigfile.000" and write.kind == "resource"
    )
    index_write = next(write for write in plan.writes if write.kind == "index")
    assert archive_write.offset == 4096
    assert archive_write.data.startswith(b"translated")
    assert archive_write.data == b"translated"
    assert index_write.offset == 0
    assert plan.index.entries[0].location == entry.location
    assert plan.index.entries[0].length == len(b"translated")
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_plan_caps_in_place_capacity_at_old_fat_block_allocation(tmp_path: Path) -> None:
    boundary = 0x8000
    entry = make_entry(0, 0x12345678, 20, 0, 0x1000, boundary)
    index = BigFileIndex((entry,))
    (tmp_path / "bigfile.000").write_bytes(build_index(index.entries) + b"\0" * 0x5000)

    plan = plan_replacements(
        tmp_path,
        index,
        (BigFileReplacement("resource", entry.hash, entry.locale, b"x" * 0x801),),
        boundary,
    )

    write = next(write for write in plan.writes if write.kind == "resource")
    assert write.offset == 0x5800
    assert write.data == b"x" * 0x801 + bytes(0x800 - 1)
    assert plan.index.entries[0].part_and_offset(boundary) == (0, 0x5800)


def test_plan_uses_exact_old_fat_block_allocation_when_replacement_fits(
    tmp_path: Path,
) -> None:
    boundary = 0x8000
    entry = make_entry(0, 0x12345678, 20, 0, 0x1000, boundary)
    index = BigFileIndex((entry,))
    (tmp_path / "bigfile.000").write_bytes(build_index(index.entries) + b"\0" * 0x5000)

    plan = plan_replacements(
        tmp_path,
        index,
        (BigFileReplacement("resource", entry.hash, entry.locale, b"x" * 0x800),),
        boundary,
    )

    write = next(write for write in plan.writes if write.kind == "resource")
    assert write.offset == 0x1000
    assert len(write.data) == 0x800
    assert plan.index.entries[0].part_and_offset(boundary) == (0, 0x1000)


def test_plan_appends_growing_resource_and_preserves_other_index_rows(tmp_path: Path) -> None:
    boundary = 0x8000
    target = make_entry(0, 0x11111111, 8, 0, 0x1000, boundary)
    following = make_entry(1, 0x22222222, 12, 0, 0x1800, boundary)
    index = BigFileIndex((target, following))
    index_bytes = build_index(index.entries)
    physical_size = 0x1800 + following.length
    (tmp_path / "bigfile.000").write_bytes(index_bytes + b"\0" * (physical_size - len(index_bytes)))

    plan = plan_replacements(
        tmp_path,
        index,
        (BigFileReplacement("menu", target.hash, target.locale, b"x" * 0x801),),
        boundary,
    )

    resource_write = next(write for write in plan.writes if write.kind == "resource")
    assert resource_write.file_name == "bigfile.000"
    assert resource_write.offset == 0x2000
    assert resource_write.data.startswith(b"x" * 0x801)
    assert len(resource_write.data) % 0x800 == 0
    assert plan.index.entries[0].location == 4
    assert plan.index.entries[0].length == 0x801
    assert plan.index.entries[1] == following
    assert plan.files["bigfile.000"].original_size == physical_size
    assert plan.files["bigfile.000"].final_size == 0x3000


def test_plan_uses_next_new_part_when_last_part_has_no_room(tmp_path: Path) -> None:
    boundary = 0x1000
    entry = make_entry(0, 0x12345678, 1000, 1, 0x800, boundary)
    index = BigFileIndex((entry,))
    index_bytes = build_index(index.entries)
    (tmp_path / "bigfile.000").write_bytes(index_bytes + b"\0" * (boundary - len(index_bytes)))
    (tmp_path / "bigfile.001").write_bytes(b"\0" * boundary)

    plan = plan_replacements(
        tmp_path,
        index,
        (BigFileReplacement("full", entry.hash, entry.locale, b"x" * 3000),),
        boundary,
    )

    resource_write = next(write for write in plan.writes if write.kind == "resource")
    assert resource_write.file_name == "bigfile.002"
    assert resource_write.offset == 0
    assert plan.index.entries[0].part_and_offset(boundary) == (2, 0)
    assert plan.files["bigfile.002"].original_size == 0


def test_plan_estimates_atomic_replacement_peak_space_and_does_not_write(tmp_path: Path) -> None:
    boundary = 0x4000
    entry = make_entry(0, 0x12345678, 20, 0, 4096, boundary)
    index = BigFileIndex((entry,))
    (tmp_path / "bigfile.000").write_bytes(build_index(index.entries) + b"\0" * 8192)
    original = (tmp_path / "bigfile.000").read_bytes()

    plan = plan_replacements(
        tmp_path,
        index,
        (BigFileReplacement("menu", entry.hash, entry.locale, b"translated"),),
        boundary,
    )

    expected_peak = plan.backup_bytes + 2 * plan.files["bigfile.000"].final_size
    assert plan.additional_bytes_required == expected_peak
    assert plan.free_bytes == shutil.disk_usage(tmp_path).free
    assert (tmp_path / "bigfile.000").read_bytes() == original


@pytest.mark.parametrize("bad_part_name", ["bigfile.002", "bigfile.foo"])
def test_plan_rejects_non_contiguous_or_malformed_archive_parts(
    tmp_path: Path, bad_part_name: str
) -> None:
    entry = BigFileEntry(0, 0x12345678, 1, 0, 0xFFFFFFE1, 0)
    (tmp_path / "bigfile.000").write_bytes(build_index((entry,)) + b"\0" * 0x1000)
    (tmp_path / bad_part_name).write_bytes(b"x")

    with pytest.raises(BigFilePlanError):
        plan_replacements(
            tmp_path,
            BigFileIndex((entry,)),
            (BigFileReplacement("entry", entry.hash, entry.locale, b"x"),),
            0x4000,
        )


def test_index_serializer_preserves_every_record_field() -> None:
    boundary = 0x4000
    entries = (
        make_entry(0, 0x12345678, 20, 0, 4096, boundary),
        make_entry(1, 0xABCDEF01, 32, 1, 2048, boundary),
    )
    index = BigFileIndex(entries)

    rebuilt = read_bigfile_index(BytesIO(serialize_bigfile_index(index)), boundary)

    assert rebuilt == index


@pytest.mark.integration
@pytest.mark.game("tra", build="842717")
def test_copied_anniversary_menu_and_font_have_a_read_only_plan(game_samples: GameSamples) -> None:
    install = game_samples.original
    sample_dir = game_samples.root
    package_path = Path("translations/tomb-raider-anniversary/hu.json")
    package_dir = package_path.parent
    index_path = install / "bigfile.000"
    game_samples.require(index_path)
    game_samples.require("font_original.raw")
    assert package_path.is_file()

    boundary = 0x09600000
    files_before = {
        name: (install / name).stat().st_size for name in ("bigfile.000", "bigfile.026")
    }
    with index_path.open("rb") as stream:
        index = read_bigfile_index(stream, boundary)
    menu_entry = next(entry for entry in index.find_hash(0x7CD333D3) if entry.locale == 0xFFFFFFE1)
    font_entry = next(entry for entry in index.find_hash(0x625B0E2D) if entry.locale == 0xFFFFFFFF)
    original_menu = extract_resource(install, menu_entry, boundary)
    original_font = extract_resource(install, font_entry, boundary)
    document = parse_translation_document(package_path.read_text(encoding="utf-8"))
    metadata = document.metadata
    menu = document.menu[0]
    font = document.fonts[0]
    translated_font = (package_dir / font.replacement_file).read_bytes()
    assert original_font == (sample_dir / "font_original.raw").read_bytes()
    package = TranslationPackage(
        metadata.game_id,
        metadata.build_id,
        menu.resource_hash,
        metadata.source_language,
        metadata.target_language,
        menu.entries,
    )
    translated_menu = apply_menu_package(
        parse_locals(original_menu),
        package,
        expected_build_id="842717",
        substitutions=dict(document.runtime.character_substitutions) if document.runtime else None,
    )
    plan = plan_replacements(
        install,
        index,
        (
            BigFileReplacement(
                "Hungarian menu", menu_entry.hash, menu_entry.locale, translated_menu
            ),
            BigFileReplacement(
                "Hungarian font", font_entry.hash, font_entry.locale, translated_font
            ),
        ),
        boundary,
    )

    menu_plan_entry = plan.index.entries[menu_entry.index]
    font_plan_entry = plan.index.entries[font_entry.index]
    assert menu_plan_entry.part_and_offset(boundary) == menu_entry.part_and_offset(boundary)
    assert menu_plan_entry.length == len(translated_menu)
    assert font_plan_entry.location == font_entry.location
    assert font_plan_entry.length == font_entry.length
    assert set(plan.files) == {"bigfile.000", "bigfile.003"}
    assert plan.sufficient_space
    assert (
        hashlib.sha256(original_menu).hexdigest()
        == "35a422e60f33ab20e12d7dbc1e452ec85e44dce2431660d3ca5e21b11de18a52"
    )
    assert {name: (install / name).stat().st_size for name in files_before} == files_before
