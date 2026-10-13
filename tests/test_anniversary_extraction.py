"""Tests for read-only TRA archive text extraction."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from pytrtt.archives.bigfile_v1 import BigFileEntry, BigFileIndex
from pytrtt.archives.write_plan import serialize_bigfile_index
from pytrtt.config import parse_runtime_settings
from pytrtt.packages.translation import TranslationMetadata, TranslationPackageError
from pytrtt.services.translation import ExtractionResult, TranslationService, parse_filelist
from scripts.extract_strings import main


def make_menu(text: str) -> bytes:
    raw = text.encode() + b"\0"
    return struct.pack("<IIII", 0, 2, 0, 16) + raw


def make_cine(text: str) -> bytes:
    records = f"0\r{text}\r1\rFrench\r".encode()
    prefix = bytearray(0x10)
    struct.pack_into("<I", prefix, 0, 0x43494E45)
    struct.pack_into("<I", prefix, 4, 5)
    prefix.extend(b"ENIC")
    payload = bytes(prefix) + bytes(0x60)
    payload = payload[:0x10] + b"ENIC" + payload[0x14:]
    payload = payload[:0x70] + struct.pack("<I", len(records)) + records
    payload += bytes((-len(payload)) % 16)
    block = struct.pack("<4I", 0, len(payload), 0, 0) + payload
    return b"H" * 0x800 + block


def make_game_dir(
    tmp_path: Path,
    resources: tuple[bytes, ...],
    hashes: tuple[int, ...] | None = None,
    locales: tuple[int, ...] | None = None,
) -> tuple[Path, BigFileIndex]:
    entries: list[BigFileEntry] = []
    offset = 0x800
    for row, resource in enumerate(resources):
        name_hash = hashes[row] if hashes is not None else 0x1000 + row
        entries.append(
            BigFileEntry(
                index=row,
                hash=name_hash,
                length=len(resource),
                location=offset // 0x800,
                locale=locales[row] if locales is not None else 0xFFFFFFE1,
                unknown=0,
            )
        )
        offset = (offset + len(resource) + 0x7FF) & ~0x7FF
    index = BigFileIndex(tuple(entries))
    prefix = serialize_bigfile_index(index)
    data = bytearray(prefix)
    for entry, resource in zip(entries, resources, strict=True):
        resource_offset = entry.location * 0x800
        data.extend(bytes(max(0, resource_offset - len(data))))
        data.extend(resource)
    (tmp_path / "bigfile.000").write_bytes(data)
    return tmp_path, index


def runtime_value() -> dict[str, object]:
    return {
        "archive": {"format": "bigfile", "version": 1, "boundary": 0x10000},
        "languages": {"en": {"archive_locale": 0xFFFFFFE1, "subtitle_language": 0}},
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
                "pattern": "*/conduitmed_pc.raw",
                "format": "raw",
                "version": 1,
                "locale": 0xFFFFFFFF,
            },
        ],
        "character_substitutions": {},
    }


def write_profile(root: Path) -> Path:
    path = root / "profile.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "game_id": "tomb-raider-anniversary",
                "build_id": "842717",
                "runtime": runtime_value(),
                "filelist": "tra_filelist.txt",
                "asset_root": ".",
                "translation_defaults": {},
            }
        ),
        encoding="utf-8",
    )
    return path


def extract(game_dir: Path, names: dict[int, str]) -> ExtractionResult:
    return TranslationService().extract(
        game_dir,
        TranslationMetadata("tomb-raider-anniversary", "842717", "en", "hu", "bigfile", 1),
        parse_runtime_settings(runtime_value()),
        names,
    )


def test_parse_filelist_maps_hash_to_resource_path() -> None:
    assert parse_filelist("1234ABCD\tpc-w\\local\\locals.bin\n") == {
        0x1234ABCD: "pc-w\\local\\locals.bin"
    }


@pytest.mark.parametrize(
    "content",
    ["not-a-hash\tfile.mul", "12345678\tfile.mul\n12345678\tother.mul"],
)
def test_parse_filelist_rejects_invalid_or_ambiguous_rows(content: str) -> None:
    with pytest.raises(TranslationPackageError):
        parse_filelist(content)


def test_extracts_menu_and_cine_strings_as_translation_packages(tmp_path: Path) -> None:
    menu = make_menu("Start game")
    cine = make_cine("Hello Lara")
    game_dir, _ = make_game_dir(tmp_path, (menu, cine), (0x7CD333D3, 0x1001))
    names = {
        0x7CD333D3: "pc-w\\local\\locals.bin",
        0x1001: "pc-w\\sndstrm\\vo\\lara\\intro.mul",
    }

    result = extract(
        game_dir,
        names,
    )

    menu_package, cine_package = result.document.menu[0], result.document.subtitles[0]
    assert menu_package.resource_hash == "7CD333D3"
    assert cine_package.resource_hash == "00001001"
    assert [entry.source for entry in menu_package.entries] == ["Start game"]
    assert [entry.source for entry in cine_package.entries] == ["Hello Lara"]
    assert result.skipped_resources == ()


def test_reports_unrecognized_mul_without_failing_other_extraction(tmp_path: Path) -> None:
    cine = make_cine("Hello Lara")
    invalid_mul = b"not a CINE resource"
    game_dir, _ = make_game_dir(tmp_path, (cine, invalid_mul))

    result = extract(
        game_dir,
        {0x1000: "vo\\intro.mul", 0x1001: "vo\\unrecognized.mul"},
    )

    assert len(result.document.subtitles) == 1
    assert len(result.skipped_resources) == 1
    assert result.skipped_resources[0].name_hash == 0x1001


def test_requires_a_unique_english_menu_resource(tmp_path: Path) -> None:
    menu = make_menu("Start game")
    game_dir, _ = make_game_dir(tmp_path, (menu, menu), (0x7CD333D3, 0x7CD333D3))

    with pytest.raises(ValueError, match="ambiguous|same hash and locale"):
        extract(
            game_dir,
            {0x7CD333D3: "local\\locals.bin"},
        )


def test_cli_writes_editable_packages_and_report_outside_game_dir(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    make_game_dir(
        game_dir,
        (make_menu("Start game"), make_cine("Hello Lara")),
        (0x7CD333D3, 0x1001),
    )
    filelist = tmp_path / "tra_filelist.txt"
    filelist.write_text(
        "7CD333D3\tpc-w\\local\\locals.bin\n00001001\tpc-w\\sndstrm\\vo\\lara\\intro.mul\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "extracted"

    result = main(
        [
            "--profile",
            str(write_profile(tmp_path)),
            "--game-dir",
            str(game_dir),
            "--filelist",
            str(filelist),
            "--output-dir",
            str(output_dir),
            "--boundary",
            "0x10000",
        ]
    )

    assert result == 0
    package_path = output_dir / "tomb-raider-anniversary.en-to-hu.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert package["metadata"]["source_language"] == "en"
    assert package["menu"][0]["resource_hash"] == "7CD333D3"
    assert package["menu"][0]["resource_path"] == "pc-w\\local\\locals.bin"
    assert package["menu"][0]["entries"][0]["source"] == "Start game"
    assert package["subtitles"][0]["resource_hash"] == "00001001"
    assert package["subtitles"][0]["entries"][0]["source"] == "Hello Lara"
    assert "fonts" not in package
    report = json.loads((output_dir / "extraction-report.json").read_text(encoding="utf-8"))
    assert report["package_count"] == 2
    assert report["packages"][0]["resource_path"] == "pc-w\\local\\locals.bin"
    assert (game_dir / "bigfile.000").is_file()

    package_path.write_text("translator edits", encoding="utf-8")
    assert (
        main(
            [
                "--profile",
                str(write_profile(tmp_path)),
                "--game-dir",
                str(game_dir),
                "--filelist",
                str(filelist),
                "--output-dir",
                str(output_dir),
                "--boundary",
                "0x10000",
            ]
        )
        == 1
    )
    assert package_path.read_text(encoding="utf-8") == "translator edits"


def test_cli_saves_original_raw_font_under_recovery_data(tmp_path: Path) -> None:
    font = b"original TRA font bytes"
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    make_game_dir(
        game_dir,
        (make_menu("Start game"), font),
        (0x7CD333D3, 0x625B0E2D),
        (0xFFFFFFE1, 0xFFFFFFFF),
    )
    filelist = tmp_path / "tra_filelist.txt"
    filelist.write_text(
        "7CD333D3\tpc-w\\local\\locals.bin\n625B0E2D\tpc-w\\conduitmed_pc.raw\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "extracted"

    result = main(
        [
            "--profile",
            str(write_profile(tmp_path)),
            "--game-dir",
            str(game_dir),
            "--filelist",
            str(filelist),
            "--output-dir",
            str(output_dir),
            "--boundary",
            "0x10000",
        ]
    )

    assert result == 0
    backup = output_dir / "restore-data/fonts/625B0E2D-FFFFFFFF.raw"
    assert backup.read_bytes() == font
    report = json.loads((output_dir / "extraction-report.json").read_text(encoding="utf-8"))
    assert report["restore_data"][0]["file"] == "restore-data/fonts/625B0E2D-FFFFFFFF.raw"
    assert report["restore_data"][0]["size"] == len(font)


def test_cli_refuses_output_inside_game_directory(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    result = main(
        [
            "--profile",
            str(write_profile(tmp_path)),
            "--game-dir",
            str(game_dir),
            "--filelist",
            str(tmp_path / "missing.txt"),
            "--output-dir",
            str(game_dir / "extracted"),
        ]
    )

    assert result == 2
