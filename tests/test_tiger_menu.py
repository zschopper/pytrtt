"""Independent byte fixtures for TIGER v5 indexes and keyed UTF-8 menu tables."""

import io
import struct
from pathlib import Path

import pytest

from pytrtt.archives.contracts import ResourceReplacement
from pytrtt.archives.tiger_v5 import (
    TigerFormatError,
    TigerV5Handler,
    read_tiger_index,
    read_tiger_resource,
)
from pytrtt.composition import create_translation_service
from pytrtt.config import ArchiveSettings, LanguageSlot, ResourceRule, RuntimeSettings
from pytrtt.formats.contracts import TextOptions
from pytrtt.formats.keyed_locals import KeyedLocalsError, KeyedLocalsHandler, parse_keyed_locals
from pytrtt.packages.translation import (
    TranslationDocument,
    TranslationEntry,
    TranslationMetadata,
    TranslationResource,
)

# TAFS, v5, one part/file, archive 1/sub-id 27, pcx64-w platform.
HEADER = bytes.fromhex(
    "54414653 05000000 01000000 01000000 01000000 1b000000"
    "70637836342d7700 0000000000000000 0000000000000000 0000000000000000"
)
# 64-bit name hash/locale, 37 bytes, raw, part zero, IDs 1/27, offset 96.
ROW = bytes.fromhex("808edbc39b331f33 0104ffffffffffff 25000000 00000000 0000 01 1b 60000000")
# Language 0, three slots: placeholder, record at 32, alias to the same record.
MENU = bytes.fromhex(
    "00000000 03000000 0000000000000000 2000000000000000 20000000000000004b20c59100"
)


def test_reads_64_bit_hash_locale_and_preserves_all_index_fields() -> None:
    index = read_tiger_index(io.BytesIO(HEADER + ROW))
    assert (index.archive_id, index.sub_id, index.num_parts) == (1, 27, 1)
    assert index.platform == "pcx64-w"
    entry = index.entries[0]
    assert (entry.name_hash, entry.locale) == (0x331F339BC3DB8E80, 0xFFFFFFFFFFFF0401)
    assert (entry.size, entry.stored_size, entry.part, entry.offset) == (37, 0, 0, 96)
    assert index.header_data == HEADER


def test_reads_resource_without_changing_archive(tmp_path: Path) -> None:
    path = tmp_path / "example.000.tiger"
    original = HEADER + ROW + bytes(8) + MENU
    path.write_bytes(original)
    index = read_tiger_index(io.BytesIO(original))
    assert read_tiger_resource(path, index, index.entries[0]) == MENU
    assert path.read_bytes() == original


@pytest.mark.parametrize("data", [b"", HEADER[:-1], HEADER + ROW[:-1]])
def test_rejects_truncated_index(data: bytes) -> None:
    with pytest.raises(TigerFormatError):
        read_tiger_index(io.BytesIO(data))


def test_rejects_unsupported_archive_version() -> None:
    data = HEADER[:4] + bytes.fromhex("04000000") + HEADER[8:] + ROW
    with pytest.raises(TigerFormatError, match="version"):
        read_tiger_index(io.BytesIO(data))


def test_rejects_part_outside_archive() -> None:
    row = ROW[:24] + bytes.fromhex("0100") + ROW[26:]
    with pytest.raises(TigerFormatError, match="part"):
        read_tiger_index(io.BytesIO(HEADER + row))


def test_rejects_out_of_bounds_resource(tmp_path: Path) -> None:
    path = tmp_path / "example.000.tiger"
    path.write_bytes(HEADER + ROW + bytes(8) + MENU[:-1])
    index = read_tiger_index(io.BytesIO(HEADER + ROW))
    with pytest.raises(TigerFormatError, match="bounds"):
        read_tiger_resource(path, index, index.entries[0])


def test_compressed_resource_fails_explicitly_until_supported(tmp_path: Path) -> None:
    path = tmp_path / "example.000.tiger"
    path.write_bytes(HEADER + ROW + bytes(8) + b"CDRM" + bytes(33))
    index = read_tiger_index(io.BytesIO(HEADER + ROW))
    with pytest.raises(TigerFormatError, match="compressed"):
        read_tiger_resource(path, index, index.entries[0])


def test_tiger_v5_appends_replacement_and_restores_exact_bytes(tmp_path: Path) -> None:
    path = tmp_path / "shadow.000.tiger"
    original = HEADER + ROW + bytes(8) + MENU
    path.write_bytes(original)
    settings = ArchiveSettings(
        "tiger", 5, 4096, families=("main",), index_files=(("main", path.name),)
    )
    runtime = RuntimeSettings(settings, (LanguageSlot("en", 0xFFFFFFFFFFFF0401, 0),), "en", ())
    handler = TigerV5Handler(tmp_path, settings)
    replacement = MENU + b"longer"

    plan = handler.plan(
        (ResourceReplacement("menu", 0x331F339BC3DB8E80, 0xFFFFFFFFFFFF0401, replacement),)
    )
    journal = tmp_path.with_name(tmp_path.name + "-journal")
    handler.apply(plan, journal, runtime)

    reopened = TigerV5Handler(tmp_path, settings)
    assert reopened.read(reopened.resources()[0]) == replacement
    reopened.restore(journal)
    reopened.restore(journal)
    assert path.read_bytes() == original


def test_tiger_v5_rejects_compressed_replacement_source(tmp_path: Path) -> None:
    path = tmp_path / "shadow.000.tiger"
    compressed_row = bytearray(ROW)
    struct.pack_into("<I", compressed_row, 20, len(MENU))
    path.write_bytes(HEADER + compressed_row + bytes(8) + MENU)
    settings = ArchiveSettings(
        "tiger", 5, 4096, families=("main",), index_files=(("main", path.name),)
    )
    with pytest.raises(ValueError, match="compressed"):
        TigerV5Handler(tmp_path, settings).plan(
            (ResourceReplacement("menu", 0x331F339BC3DB8E80, 0xFFFFFFFFFFFF0401, MENU),)
        )


def test_translation_service_applies_and_restores_keyed_tiger_v5_menu(tmp_path: Path) -> None:
    path = tmp_path / "shadow.000.tiger"
    original = HEADER + ROW + bytes(8) + MENU
    path.write_bytes(original)
    settings = ArchiveSettings(
        "tiger", 5, 4096, families=("main",), index_files=(("main", path.name),)
    )
    runtime = RuntimeSettings(
        settings,
        (LanguageSlot("en", 0xFFFFFFFFFFFF0401, 0),),
        "en",
        (ResourceRule("menu", "*/locals.bin", "locals", 4),),
    )
    document = TranslationDocument(
        TranslationMetadata("shadow", "1", "en", "hu", "tiger", 5),
        menu=(
            TranslationResource(
                "331F339BC3DB8E80",
                "pcx64-w\\local\\locals.bin",
                (
                    TranslationEntry(1, "ő", "magyar őű", key="K"),
                    TranslationEntry(2, "ő", "magyar őű", key="K"),
                ),
            ),
        ),
        runtime=runtime,
    )
    service = create_translation_service()

    build = service.plan(tmp_path, document, package_dir=tmp_path, expected_build_id="1")
    journal = tmp_path.with_name(tmp_path.name + "-service-journal")
    service.apply(build, journal)
    assert service.is_translation_installed(tmp_path, document, package_dir=tmp_path)
    service.restore(tmp_path, journal, runtime)
    assert path.read_bytes() == original


def test_parses_unicode_keys_placeholders_and_shared_offsets() -> None:
    result = parse_keyed_locals(MENU)
    assert result.language_id == 0
    assert [(e.index, e.offset, e.key, e.text) for e in result.entries] == [
        (0, 0, None, None),
        (1, 32, "K", "ő"),
        (2, 32, "K", "ő"),
    ]
    assert result.original_data == MENU


def test_keyed_locals_handler_rebuilds_text_and_preserves_aliases() -> None:
    handler = KeyedLocalsHandler()
    extracted = handler.extract(MENU, 0)
    assert extracted == (
        TranslationEntry(0, "", None),
        TranslationEntry(1, "ő", None, key="K"),
        TranslationEntry(2, "ő", None, key="K"),
    )

    rebuilt = handler.write(
        MENU,
        (
            TranslationEntry(1, "ő", "hosszabb őű", key="K"),
            TranslationEntry(2, "ő", "hosszabb őű", key="K"),
        ),
        TextOptions(0),
    )
    parsed = parse_keyed_locals(rebuilt)
    assert parsed.entries[1].text == "hosszabb őű"
    assert parsed.entries[1].offset == parsed.entries[2].offset


def test_keyed_locals_handler_rejects_changed_keys_and_split_aliases() -> None:
    handler = KeyedLocalsHandler()
    with pytest.raises(KeyedLocalsError, match="key"):
        handler.write(MENU, (TranslationEntry(1, "ő", "x", key="other"),), TextOptions(0))
    with pytest.raises(KeyedLocalsError, match="alias"):
        handler.write(
            MENU,
            (TranslationEntry(1, "ő", "x", key="K"), TranslationEntry(2, "ő", "y", key="K")),
            TextOptions(0),
        )


@pytest.mark.parametrize("data", [b"", MENU[:7], MENU[:31]])
def test_rejects_invalid_locals_header_or_table(data: bytes) -> None:
    with pytest.raises(KeyedLocalsError):
        parse_keyed_locals(data)


def test_rejects_pointer_inside_table() -> None:
    data = MENU[:16] + bytes.fromhex("1000000000000000") + MENU[24:]
    with pytest.raises(KeyedLocalsError, match="pointer"):
        parse_keyed_locals(data)


def test_rejects_unterminated_text() -> None:
    with pytest.raises(KeyedLocalsError, match="terminated"):
        parse_keyed_locals(MENU[:-1])


def test_rejects_record_without_key_separator() -> None:
    with pytest.raises(KeyedLocalsError, match="separator"):
        parse_keyed_locals(MENU[:32] + b"missing-key-separator\x00")
