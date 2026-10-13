"""Tests for building a TRA Bigfile write plan from the single translation document."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import replace
from pathlib import Path

import pytest

import pytrtt.cli as translate_cli
from pytrtt.archives.bigfile_v1 import BigFileEntry, BigFileIndex, read_bigfile_index
from pytrtt.archives.write_plan import serialize_bigfile_index
from pytrtt.config import parse_runtime_settings
from pytrtt.packages.translation import (
    FontAsset,
    TranslationDocument,
    TranslationEntry,
    TranslationMetadata,
    TranslationPackageError,
    TranslationResource,
    serialize_translation_document,
)
from pytrtt.services.translation import TranslationService

BOUNDARY = 0x10000
MENU_HASH = 0x7CD333D3
CINE_HASH = 0x10001001
FONT_HASH = 0x625B0E2D
ENGLISH_LOCALE = 0xFFFFFFE1
FONT_LOCALE = 0xFFFFFFFF


def make_menu(text: str) -> bytes:
    return struct.pack("<IIII", 0, 2, 0, 16) + text.encode() + b"\0"


def make_cine(text: str) -> bytes:
    records = f"0\r{text}\r1\rFrench\r".encode()
    prefix = bytearray(0x70)
    struct.pack_into("<I", prefix, 0, 0x43494E45)
    struct.pack_into("<I", prefix, 4, 5)
    prefix[0x10:0x14] = b"ENIC"
    payload = bytes(prefix) + struct.pack("<I", len(records)) + records
    payload += bytes((-len(payload)) % 16)
    block = struct.pack("<4I", 0, len(payload), 0, 0) + payload
    return bytes(0x800) + block


def make_game_dir(game_dir: Path) -> tuple[BigFileIndex, dict[int, str], bytes, bytes, bytes]:
    resources = (make_menu("Start"), make_cine("Hello"), b"old-font")
    hashes = (MENU_HASH, CINE_HASH, FONT_HASH)
    locales = (ENGLISH_LOCALE, ENGLISH_LOCALE, FONT_LOCALE)
    offsets = (0x800, 0x1000, 0x2000)
    entries = tuple(
        BigFileEntry(index, name_hash, len(data), offset // 0x800, locale, 0xAABBCC00 + index)
        for index, (name_hash, data, locale, offset) in enumerate(
            zip(hashes, resources, locales, offsets, strict=True)
        )
    )
    index = BigFileIndex(entries)
    archive = bytearray(0x2800)
    archive[: len(serialize_bigfile_index(index))] = serialize_bigfile_index(index)
    for offset, data in zip(offsets, resources, strict=True):
        archive[offset : offset + len(data)] = data
    (game_dir / "bigfile.000").write_bytes(archive)
    names = {
        MENU_HASH: "pc-w\\local\\locals.bin",
        CINE_HASH: "pc-w\\sndstrm\\vo\\lara\\intro.mul",
        FONT_HASH: "pc-w\\conduitmed_pc.raw",
    }
    return index, names, *resources


def make_document(menu_source: str = "Start") -> TranslationDocument:
    original_font = b"old-font"
    translated_font = b"hu-font!"
    return TranslationDocument(
        TranslationMetadata("tomb-raider-anniversary", "842717", "en", "hu", "bigfile", 1),
        runtime=parse_runtime_settings(
            {
                "archive": {"format": "bigfile", "version": 1, "boundary": BOUNDARY},
                "languages": {"en": {"archive_locale": ENGLISH_LOCALE, "subtitle_language": 0}},
                "replacement_language": "en",
                "resource_types": [
                    {
                        "section": "menu",
                        "pattern": "*/locals.bin",
                        "format": "locals",
                        "version": 1,
                    },
                    {"section": "subtitles", "pattern": "*.mul", "format": "cine", "version": 1},
                    {
                        "section": "fonts",
                        "pattern": "*/conduitmed_pc.raw",
                        "format": "raw",
                        "version": 1,
                        "locale": FONT_LOCALE,
                    },
                ],
                "character_substitutions": {},
            }
        ),
        menu=(
            TranslationResource(
                f"{MENU_HASH:08X}",
                "pc-w\\local\\locals.bin",
                (TranslationEntry(0, menu_source, "Indítás"),),
            ),
        ),
        subtitles=(
            TranslationResource(
                f"{CINE_HASH:08X}",
                "pc-w\\sndstrm\\vo\\lara\\intro.mul",
                (TranslationEntry(0, "Hello", "Szia"),),
            ),
        ),
        fonts=(
            FontAsset(
                f"{FONT_HASH:08X}",
                "pc-w\\conduitmed_pc.raw",
                "fonts/font_hu.raw",
                hashlib.sha256(original_font).hexdigest(),
                hashlib.sha256(translated_font).hexdigest(),
            ),
        ),
    )


def test_translation_document_builds_menu_cine_and_font_replacements(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    make_game_dir(game_dir)
    package_dir = tmp_path / "package"
    (package_dir / "fonts").mkdir(parents=True)
    (package_dir / "fonts/font_hu.raw").write_bytes(b"hu-font!")

    result = TranslationService().plan(
        game_dir,
        make_document(),
        package_dir=package_dir,
        expected_build_id="842717",
    )

    assert result.plan is not None
    writes = {write.label: write for write in result.plan.writes if write.kind == "resource"}
    assert set(writes) == {"Menu 7CD333D3", "Subtitle 10001001", "Font 625B0E2D"}
    assert writes["Font 625B0E2D"].restore_file == "fonts/625B0E2D-FFFFFFFF.raw"
    assert writes["Font 625B0E2D"].resource_original == b"old-font"
    assert result.missing_translations == ()


@pytest.mark.parametrize(
    ("field", "expected_pairs"),
    [
        ("clear_subtitle_languages", ((0, "Szia"), (1, " "))),
        ("omit_subtitle_languages", ((0, "Szia"),)),
    ],
)
def test_document_subtitle_language_action_reaches_cine_writer(
    tmp_path: Path,
    field: str,
    expected_pairs: tuple[tuple[int, str], ...],
) -> None:
    from pytrtt.formats.cine_v1 import parse_cine

    game_dir = tmp_path / "game"
    game_dir.mkdir()
    make_game_dir(game_dir)
    package_dir = tmp_path / "package"
    (package_dir / "fonts").mkdir(parents=True)
    (package_dir / "fonts/font_hu.raw").write_bytes(b"hu-font!")
    if field == "clear_subtitle_languages":
        document = replace(make_document(), clear_subtitle_languages=frozenset({1}))
    else:
        document = replace(make_document(), omit_subtitle_languages=frozenset({1}))

    result = TranslationService().plan(
        game_dir,
        document,
        package_dir=package_dir,
        expected_build_id="842717",
    )

    assert result.plan is not None
    subtitle_write = next(
        write
        for write in result.plan.writes
        if write.kind == "resource" and write.label == "Subtitle 10001001"
    )
    assert parse_cine(subtitle_write.data).blocks[0].subtitle_pairs == expected_pairs


def test_document_builder_rejects_source_text_mismatch_before_planning(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    make_game_dir(game_dir)
    package_dir = tmp_path / "package"
    (package_dir / "fonts").mkdir(parents=True)
    (package_dir / "fonts/font_hu.raw").write_bytes(b"hu-font!")

    with pytest.raises(TranslationPackageError, match="source text changed"):
        TranslationService().plan(
            game_dir,
            make_document("Different source"),
            package_dir=package_dir,
            expected_build_id="842717",
        )


def test_document_build_plan_applies_and_restores_exactly_with_font_raw(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    make_game_dir(game_dir)
    original = (game_dir / "bigfile.000").read_bytes()
    package_dir = tmp_path / "package"
    (package_dir / "fonts").mkdir(parents=True)
    (package_dir / "fonts/font_hu.raw").write_bytes(b"hu-font!")
    result = TranslationService().plan(
        game_dir,
        make_document(),
        package_dir=package_dir,
        expected_build_id="842717",
    )
    assert result.plan is not None

    transaction_dir = tmp_path / "transaction"
    TranslationService().apply(result, transaction_dir)
    backup = transaction_dir / "backups/restore-data/fonts/625B0E2D-FFFFFFFF.raw"
    assert backup.read_bytes() == b"old-font"
    with (game_dir / "bigfile.000").open("rb") as stream:
        translated_index = read_bigfile_index(stream, BOUNDARY)
    assert translated_index.find_hash(FONT_HASH)[0].length == len(b"hu-font!")

    TranslationService().restore(game_dir, transaction_dir)

    assert (game_dir / "bigfile.000").read_bytes() == original


def test_cli_dry_run_apply_and_restore_round_trip(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    make_game_dir(game_dir)
    package_dir = tmp_path / "package"
    (package_dir / "fonts").mkdir(parents=True)
    (package_dir / "fonts/font_hu.raw").write_bytes(b"hu-font!")
    translation_path = package_dir / "translation.json"
    translation_path.write_text(serialize_translation_document(make_document()), encoding="utf-8")
    filelist = tmp_path / "tra_filelist.txt"
    filelist.write_text(
        f"{MENU_HASH:08X}\tpc-w\\local\\locals.bin\n"
        f"{CINE_HASH:08X}\tpc-w\\sndstrm\\vo\\lara\\intro.mul\n"
        f"{FONT_HASH:08X}\tpc-w\\conduitmed_pc.raw\n",
        encoding="utf-8",
    )
    archive = game_dir / "bigfile.000"
    original = archive.read_bytes()
    transaction_dir = tmp_path / "restore-data" / "transaction-001"
    arguments = [
        "--game-dir",
        str(game_dir),
        "--filelist",
        str(filelist),
        "--translation-file",
        str(translation_path),
        "--boundary",
        hex(BOUNDARY),
        "--transaction-dir",
        str(transaction_dir),
    ]

    assert translate_cli.main(arguments) == 0
    assert archive.read_bytes() == original
    assert translate_cli.main([*arguments, "--apply"]) == 0
    assert archive.read_bytes() != original
    assert (transaction_dir / "backups/restore-data/fonts/625B0E2D-FFFFFFFF.raw").read_bytes() == (
        b"old-font"
    )
    assert (
        translate_cli.main(
            ["--game-dir", str(game_dir), "--transaction-dir", str(transaction_dir), "--restore"]
        )
        == 0
    )
    assert archive.read_bytes() == original


def test_cli_writes_missing_translation_report_without_archive_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    make_game_dir(game_dir)
    archive = game_dir / "bigfile.000"
    original = archive.read_bytes()
    document = make_document()
    untranslated = replace(
        document,
        menu=(
            replace(
                document.menu[0],
                entries=(replace(document.menu[0].entries[0], translation=None),),
            ),
        ),
        subtitles=(
            replace(
                document.subtitles[0],
                entries=(replace(document.subtitles[0].entries[0], translation=None),),
            ),
        ),
        fonts=(),
    )
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    translation_path = package_dir / "translation.json"
    translation_path.write_text(serialize_translation_document(untranslated), encoding="utf-8")
    filelist = tmp_path / "tra_filelist.txt"
    filelist.write_text(
        f"{MENU_HASH:08X}\tpc-w\\local\\locals.bin\n"
        f"{CINE_HASH:08X}\tpc-w\\sndstrm\\vo\\lara\\intro.mul\n"
        f"{FONT_HASH:08X}\tpc-w\\conduitmed_pc.raw\n",
        encoding="utf-8",
    )
    user_data_dir = tmp_path / "user-data"
    monkeypatch.setattr(translate_cli, "_user_data_dir", lambda: user_data_dir)

    result = translate_cli.main(
        [
            "--game-dir",
            str(game_dir),
            "--filelist",
            str(filelist),
            "--translation-file",
            str(translation_path),
            "--boundary",
            hex(BOUNDARY),
            "--apply",
        ]
    )

    assert result == 0
    assert archive.read_bytes() == original
    reports = list((user_data_dir / "reports" / "tomb-raider-anniversary").glob("*.txt"))
    assert len(reports) == 1
    report = reports[0].read_text(encoding="utf-8")
    assert "Missing entries: 2" in report
    assert "tombraidertranslations@gmail.com" in report
