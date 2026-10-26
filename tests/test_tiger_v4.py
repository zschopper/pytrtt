import struct
from pathlib import Path

import pytest

from pytrtt.archives.tiger_v4 import TigerV4Handler, read_tiger_v4_index
from pytrtt.config import ArchiveSettings


def fixture(path: Path, archive_id: int, text: bytes) -> None:
    header = struct.pack("<4s4I32s", b"TAFS", 4, 1, 1, archive_id, b"pc-w")
    row = struct.pack("<4IhhI", 0x7CD333D3, 1, len(text), 0, 0, archive_id, 2048)
    path.write_bytes(header + row + bytes(2048 - len(header) - len(row)) + text)


@pytest.mark.parametrize(
    "section,format_name,path,content,source,translated",
    [
        (
            "menu",
            "locals",
            "data/locals.bin",
            struct.pack("<3IQ", 0, 0, 1, 20) + b"Hello\0",
            "Hello",
            "Hosszabb őű szöveg",
        ),
        (
            "subtitles",
            "sch",
            "intro.sch",
            b'TextEntry\r\nline0\r\nlang_english 1 "(0.1)[Lara]Hello"\r\n',
            "Hello",
            "Hosszabb őű szöveg",
        ),
    ],
)
def test_v3_text_service_install_restore_and_translate_again(
    tmp_path: Path,
    section: str,
    format_name: str,
    path: str,
    content: bytes,
    source: str,
    translated: str,
) -> None:
    from pytrtt.composition import create_translation_service
    from pytrtt.config import LanguageSlot, ResourceRule, RuntimeSettings
    from pytrtt.packages.translation import (
        TranslationDocument,
        TranslationEntry,
        TranslationMetadata,
        TranslationResource,
    )

    archive = tmp_path / "bigfile.000.tiger"
    fixture(archive, 1, content)
    original = archive.read_bytes()
    settings = ArchiveSettings(
        "tiger",
        4,
        0x7FF00000,
        families=("base",),
        index_files=(("base", archive.name),),
    )
    runtime = RuntimeSettings(
        settings,
        (LanguageSlot("en", 1, 0),),
        "en",
        (ResourceRule(section, path, format_name, 3),),
    )
    resource = TranslationResource(
        "7CD333D3",
        path,
        (TranslationEntry(0, source, translated),),
    )
    document = TranslationDocument(
        TranslationMetadata("fixture", "1", "en", "hu", "tiger", 4),
        menu=(resource,) if section == "menu" else (),
        subtitles=(resource,) if section == "subtitles" else (),
        runtime=runtime,
    )
    service = create_translation_service()
    build = service.plan(tmp_path, document, package_dir=tmp_path)
    assert build.plan is not None
    transaction = tmp_path / "journal"
    service.apply(build, transaction)
    assert translated.encode() in archive.read_bytes()
    assert service.is_translation_installed(tmp_path, document, package_dir=tmp_path)
    for _ in range(2):
        service.restore(tmp_path, transaction)
        assert archive.read_bytes() == original
    restored = service.plan(tmp_path, document, package_dir=tmp_path)
    assert restored.plan is not None
    assert restored.plan.files == build.plan.files
    assert restored.plan.writes == build.plan.writes


def test_priority_with_independent_index_names(tmp_path: Path) -> None:
    fixture(tmp_path / "bigfile.000.tiger", 1, b"base")
    fixture(tmp_path / "bigfile.update1.000_ENGLISH.000.tiger", 10, b"updated")
    settings = ArchiveSettings(
        "tiger",
        4,
        0x7FF00000,
        families=("base", "update"),
        index_files=(
            ("base", "bigfile.000.tiger"),
            ("update", "bigfile.update1.000_ENGLISH.000.tiger"),
        ),
    )
    h = TigerV4Handler(tmp_path, settings)
    refs = h.resources()
    assert len(refs) == 1 and h.read(refs[0]) == b"updated"
    with pytest.raises(ValueError, match="no TIGER"):
        h.plan(())
    (tmp_path / "bigfile.000.tiger").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        h.read(refs[0])


def test_append_translation_preserves_identity_bytes_and_restores_twice(tmp_path: Path) -> None:
    from pytrtt.archives.contracts import ResourceReplacement
    from pytrtt.config import LanguageSlot, RuntimeSettings

    path = tmp_path / "bigfile.update1.000_ENGLISH.000.tiger"
    fixture(path, 10, b"original text")
    original = bytearray(path.read_bytes())
    original[30:34] = b"KEEP"
    path.write_bytes(original)
    settings = ArchiveSettings(
        "tiger",
        4,
        0x7FF00000,
        families=("update",),
        index_files=(("update", path.name),),
    )
    runtime = RuntimeSettings(settings, (LanguageSlot("en", 1, 0),), "en", ())
    handler = TigerV4Handler(tmp_path, settings)
    translated = "Hosszabb magyar szöveg őű".encode()
    plan = handler.plan((ResourceReplacement("menu", 0x7CD333D3, 1, translated),))
    assert path.read_bytes() == original
    handler.apply(plan, tmp_path.with_name(tmp_path.name + "-journal"), runtime)
    result = path.read_bytes()
    assert result[:60] == original[:60]
    assert result[76 : len(original)] == original[76:]
    assert struct.unpack_from("<hhI", result, 68) == (0, 10, 4096)
    reopened = TigerV4Handler(tmp_path, settings)
    assert reopened.read(reopened.resources()[0]) == translated
    for _ in range(2):
        handler.restore(tmp_path.with_name(tmp_path.name + "-journal"))
        assert path.read_bytes() == original


def test_v4_new_part_and_source_change_guard(tmp_path: Path) -> None:
    from pytrtt.archives.contracts import ResourceReplacement
    from pytrtt.archives.transaction import TransactionError
    from pytrtt.config import LanguageSlot, RuntimeSettings

    path = tmp_path / "bigfile.000.tiger"
    fixture(path, 1, b"original")
    settings = ArchiveSettings(
        "tiger",
        4,
        4096,
        families=("base",),
        index_files=(("base", path.name),),
    )
    runtime = RuntimeSettings(settings, (LanguageSlot("en", 1, 0),), "en", ())
    handler = TigerV4Handler(tmp_path, settings)
    plan = handler.plan((ResourceReplacement("menu", 0x7CD333D3, 1, b"x" * 3000),))
    assert "bigfile.001.tiger" in plan.files
    handler.apply(plan, tmp_path.with_name(tmp_path.name + "-journal"), runtime)
    assert struct.unpack_from("<I", path.read_bytes(), 8)[0] == 2
    handler.restore(tmp_path.with_name(tmp_path.name + "-journal"))
    handler.restore(tmp_path.with_name(tmp_path.name + "-journal"))
    assert not (tmp_path / "bigfile.001.tiger").exists()
    fresh = TigerV4Handler(tmp_path, settings)
    plan = fresh.plan((ResourceReplacement("menu", 0x7CD333D3, 1, b"changed"),))
    with path.open("r+b") as stream:
        stream.seek(2048)
        stream.write(b"modified")
    with pytest.raises(TransactionError, match="changed"):
        fresh.apply(plan, tmp_path.with_name(tmp_path.name + "-rejected"), runtime)


def test_physical_layer_selection_and_unchanged_dependency_guard(tmp_path: Path) -> None:
    from pytrtt.archives.contracts import ResourceReplacement
    from pytrtt.archives.transaction import TransactionError
    from pytrtt.config import LanguageSlot, RuntimeSettings

    fixture(tmp_path / "base.000.tiger", 1, b"base")
    fixture(tmp_path / "patch.000.tiger", 10, b"patch")
    settings = ArchiveSettings(
        "tiger",
        4,
        8192,
        families=("base", "patch"),
        index_files=(("base", "base.000.tiger"), ("patch", "patch.000.tiger")),
    )
    handler = TigerV4Handler(tmp_path, settings)
    replacement = ResourceReplacement(
        "base menu", 0x7CD333D3, 1, b"translated", archive_family="base"
    )
    plan = handler.plan((replacement,))
    assert set(plan.files) == {"base.000.tiger"}
    with pytest.raises(ValueError, match="duplicate"):
        handler.plan((replacement, replacement))
    with (tmp_path / "patch.000.tiger").open("r+b") as stream:
        stream.seek(2048)
        stream.write(b"other")
    runtime = RuntimeSettings(settings, (LanguageSlot("en", 1, 0),), "en", ())
    with pytest.raises(TransactionError, match="source part changed"):
        handler.apply(plan, tmp_path.with_name(tmp_path.name + "-journal"), runtime)


@pytest.mark.parametrize("data", [b"", b"x" * 4097])
def test_v4_rejects_empty_or_oversized_replacement(tmp_path: Path, data: bytes) -> None:
    from pytrtt.archives.contracts import ResourceReplacement

    fixture(tmp_path / "base.000.tiger", 1, b"base")
    settings = ArchiveSettings(
        "tiger", 4, 4096, families=("base",), index_files=(("base", "base.000.tiger"),)
    )
    with pytest.raises(ValueError, match="boundary or is empty"):
        TigerV4Handler(tmp_path, settings).plan((ResourceReplacement("menu", 0x7CD333D3, 1, data),))


def test_v4_rejects_truncation_and_other_versions(tmp_path: Path) -> None:
    fixture(tmp_path / "a", 1, b"text")
    data = (tmp_path / "a").read_bytes()
    import io

    with pytest.raises(ValueError):
        read_tiger_v4_index(io.BytesIO(data[:60]))
    wrong = bytearray(data)
    struct.pack_into("<I", wrong, 4, 3)
    with pytest.raises(ValueError, match="version"):
        read_tiger_v4_index(io.BytesIO(wrong))


@pytest.mark.parametrize(
    "offset,fmt,value", [(68, "h", -1), (70, "h", 2), (72, "I", 64), (64, "I", 1)]
)
def test_invalid_v4_locations_and_storage_are_rejected(
    tmp_path: Path, offset: int, fmt: str, value: int
) -> None:
    import io

    fixture(tmp_path / "a", 1, b"data")
    data = bytearray((tmp_path / "a").read_bytes())
    struct.pack_into("<" + fmt, data, offset, value)
    with pytest.raises(ValueError):
        read_tiger_v4_index(io.BytesIO(data))


def test_v4_read_rejects_resources_past_eof_and_compressed_data(tmp_path: Path) -> None:
    path = tmp_path / "bigfile.000.tiger"
    fixture(path, 1, b"CDRMdata")
    settings = ArchiveSettings(
        "tiger", 4, 0x7FF00000, families=("base",), index_files=(("base", path.name),)
    )
    handler = TigerV4Handler(tmp_path, settings)
    with pytest.raises(ValueError, match="decompression"):
        handler.read(handler.resources()[0])
    data = bytearray(path.read_bytes())
    struct.pack_into("<I", data, 72, len(data))
    path.write_bytes(data)
    with pytest.raises(ValueError, match="bounds"):
        TigerV4Handler(tmp_path, settings).resources()


def test_v4_detects_same_size_changes_and_symlink_replacement(tmp_path: Path) -> None:
    import os

    path = tmp_path / "bigfile.000.tiger"
    fixture(path, 1, b"text")
    settings = ArchiveSettings(
        "tiger", 4, 0x7FF00000, families=("base",), index_files=(("base", path.name),)
    )
    handler = TigerV4Handler(tmp_path, settings)
    resource = handler.resources()[0]
    stamp = path.stat()
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1000000000))
    with pytest.raises(ValueError, match="changed"):
        handler.read(resource)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    other = tmp_path / "original"
    path.rename(other)
    path.symlink_to(other)
    with pytest.raises(ValueError, match="changed"):
        handler.read(resource)
    path.unlink()
    with pytest.raises(ValueError, match="changed"):
        handler.read(resource)


def test_read_session_rejects_changes_to_other_sources_on_exit(tmp_path: Path) -> None:
    fixture(tmp_path / "bigfile.000.tiger", 1, b"base")
    fixture(tmp_path / "update.000.tiger", 10, b"new")
    settings = ArchiveSettings(
        "tiger",
        4,
        0x7FF00000,
        families=("base", "update"),
        index_files=(("base", "bigfile.000.tiger"), ("update", "update.000.tiger")),
    )
    handler = TigerV4Handler(tmp_path, settings)
    resource = handler.resources()[0]
    with pytest.raises(ValueError, match="changed"):
        with handler.read_session():
            assert handler.read(resource) == b"new"
            (tmp_path / "bigfile.000.tiger").write_bytes(b"changed")
            assert handler.read(resource) == b"new"
    with pytest.raises(ValueError, match="changed"):
        handler.read(resource)


def test_read_session_checks_the_current_file_immediately(tmp_path: Path) -> None:
    path = tmp_path / "bigfile.000.tiger"
    fixture(path, 1, b"base")
    settings = ArchiveSettings(
        "tiger", 4, 0x7FF00000, families=("base",), index_files=(("base", path.name),)
    )
    handler = TigerV4Handler(tmp_path, settings)
    resource = handler.resources()[0]
    with pytest.raises(ValueError, match="changed"):
        with handler.read_session():
            path.write_bytes(b"changed")
            handler.read(resource)


def test_extraction_does_not_return_a_document_if_final_source_validation_fails(
    tmp_path: Path,
) -> None:
    from pytrtt.composition import create_handler_registry
    from pytrtt.config import LanguageSlot, ResourceRule, RuntimeSettings
    from pytrtt.formats.reboot_text import LocalsV2Handler
    from pytrtt.packages.translation import TranslationEntry, TranslationMetadata
    from pytrtt.services.translation import TranslationService

    fixture(tmp_path / "bigfile.000.tiger", 1, b"base")
    fixture(tmp_path / "update.000.tiger", 10, b"new")
    settings = ArchiveSettings(
        "tiger",
        4,
        0x7FF00000,
        families=("base", "update"),
        index_files=(("base", "bigfile.000.tiger"), ("update", "update.000.tiger")),
    )

    class ChangingSourceHandler(LocalsV2Handler):
        def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
            (tmp_path / "bigfile.000.tiger").write_bytes(b"changed after last resource read")
            return (TranslationEntry(0, "Source", None),)

    registry = create_handler_registry()
    registry.formats[("test", 1)] = ChangingSourceHandler()
    runtime = RuntimeSettings(
        settings, (LanguageSlot("en", 1, 0),), "en", (ResourceRule("menu", "*.bin", "test", 1),)
    )
    metadata = TranslationMetadata("test", "1", "en", "hu", "tiger", 4)
    with pytest.raises(ValueError, match="changed"):
        TranslationService(registry).extract(tmp_path, metadata, runtime, {0x7CD333D3: "menu.bin"})
