import io
import struct
from dataclasses import replace
from pathlib import Path

import pytest

from pytrtt.archives.contracts import ResourceReplacement
from pytrtt.archives.tiger_v3 import TigerV3Handler, read_tiger_v3_index
from pytrtt.archives.transaction import TransactionError, apply_write_plan, restore_write_plan
from pytrtt.composition import create_translation_service
from pytrtt.config import ArchiveSettings, LanguageSlot, ResourceRule, RuntimeSettings
from pytrtt.packages.translation import TranslationMetadata


def archive(root: Path, family: str = "bigfile", priority: int = 0, data: bytes = b"old") -> bytes:
    header = b"TAFS" + struct.pack("<4I", 3, 1, 1, priority) + b"pc-w\0" + bytes(27)
    row = struct.pack("<4I", 0x12345678, 0xFFFFFFFF, len(data), 0x800 | (priority << 4))
    content = header + row + bytes(0x800 - 68) + data
    (root / f"{family}.000.tiger").write_bytes(content)
    return content


def test_reads_v3_fields_and_rejects_v5(tmp_path: Path) -> None:
    data = archive(tmp_path, priority=65)
    index = read_tiger_v3_index(io.BytesIO(data))
    assert index.priority == 65
    assert index.entries[0].part == 0
    assert index.entries[0].offset == 0x800
    with pytest.raises(ValueError, match="version"):
        read_tiger_v3_index(io.BytesIO(data[:4] + struct.pack("<I", 5) + data[8:]))


def test_highest_priority_overrides_exact_hash_locale(tmp_path: Path) -> None:
    archive(tmp_path)
    archive(tmp_path, "patch", 65, b"patch")
    handler = TigerV3Handler(tmp_path, ArchiveSettings("tiger", 3, 0x80000000))
    assert len(handler.resources()) == 1
    assert handler.read(handler.resources()[0]) == b"patch"


def test_explicit_layers_remain_addressable_and_restore_independently(tmp_path: Path) -> None:
    root = tmp_path / "copy"
    root.mkdir()
    original = archive(root)
    patch = archive(root, "patch", 65, b"patch")
    settings = ArchiveSettings("tiger", 3, 0x80000000, include_overridden=True)
    handler = TigerV3Handler(root, settings)
    resources = handler.resources()
    assert {r.archive_family for r in resources} == {"bigfile", "patch"}
    assert {r.archive_family: handler.read(r) for r in resources} == {
        "bigfile": b"old",
        "patch": b"patch",
    }
    plan = handler.plan(
        (
            ResourceReplacement(
                "base menu", 0x12345678, 0xFFFFFFFF, b"translated", archive_family="bigfile"
            ),
        )
    )
    apply_write_plan(root, plan, tmp_path / "transaction")
    assert {r.archive_family: handler.read(r) for r in handler.resources()} == {
        "bigfile": b"translated",
        "patch": b"patch",
    }
    restore_write_plan(root, tmp_path / "transaction")
    assert (root / "bigfile.000.tiger").read_bytes() == original
    assert (root / "patch.000.tiger").read_bytes() == patch


def test_service_retains_two_menu_layers_with_same_hash_and_locale(tmp_path: Path) -> None:
    root = tmp_path / "copy"
    root.mkdir()
    archive(root, data=struct.pack("<4I", 0, 0, 1, 16) + b"NEW GAME\0")
    archive(root, "patch", 65, struct.pack("<4I", 0, 0, 1, 16) + b"Invite\0")
    runtime = RuntimeSettings(
        ArchiveSettings("tiger", 3, 0x80000000, include_overridden=True),
        (LanguageSlot("en", 1, 0, locale_is_mask=True),),
        "en",
        (ResourceRule("menu", "locals.bin", "locals", 2),),
    )
    service = create_translation_service()
    result = service.extract(
        root,
        TranslationMetadata("example", "1", "en", "hu", "tiger", 3),
        runtime,
        {0x12345678: "locals.bin"},
    )
    assert len(result.document.menu) == 2
    assert {r.archive_family for r in result.document.menu} == {"bigfile", "patch"}
    resources = tuple(
        replace(r, entries=(replace(r.entries[0], translation="Magyar"),))
        for r in result.document.menu
    )
    document = replace(result.document, menu=resources)
    build = service.plan(root, document, package_dir=tmp_path)
    service.apply(build, tmp_path / "transaction")
    extracted = service.extract(root, document.metadata, runtime, {0x12345678: "locals.bin"})
    assert [r.entries[0].source for r in extracted.document.menu] == ["Magyar", "Magyar"]


def test_equal_priority_conflict_fails_closed(tmp_path: Path) -> None:
    archive(tmp_path)
    archive(tmp_path, "other", 0)
    with pytest.raises(ValueError, match="equal priority"):
        TigerV3Handler(tmp_path, ArchiveSettings("tiger", 3, 0x80000000)).resources()


def test_out_of_bounds_and_invalid_location_identity(tmp_path: Path) -> None:
    data = archive(tmp_path)
    path = tmp_path / "bigfile.000.tiger"
    path.write_bytes(data[:-1])
    with pytest.raises(ValueError, match="bounds"):
        TigerV3Handler(tmp_path, ArchiveSettings("tiger", 3, 0x80000000)).resources()
    bad = bytearray(data)
    struct.pack_into("<I", bad, 64, 0x810)
    with pytest.raises(ValueError, match="identity"):
        read_tiger_v3_index(io.BytesIO(bad))


def test_growth_plan_preserves_unknown_bytes_and_moves_to_new_part(tmp_path: Path) -> None:
    original = archive(tmp_path)
    handler = TigerV3Handler(tmp_path, ArchiveSettings("tiger", 3, 0x1000))
    plan = handler.plan((ResourceReplacement("text", 0x12345678, 0xFFFFFFFF, b"x" * 2049),))
    assert (tmp_path / "bigfile.000.tiger").read_bytes() == original
    assert plan.files["bigfile.001.tiger"].original_sha256 is None
    index = read_tiger_v3_index(io.BytesIO(plan.index_data["bigfile.000.tiger"]))
    assert index.num_parts == 2
    assert index.entries[0].part == 1
    assert index.entries[0].offset == 0
    assert index.header_data[20:] == original[20:52]


def test_boundary_overflow_is_rejected(tmp_path: Path) -> None:
    archive(tmp_path)
    handler = TigerV3Handler(tmp_path, ArchiveSettings("tiger", 3, 0x1000))
    with pytest.raises(ValueError, match="boundary"):
        handler.plan((ResourceReplacement("text", 0x12345678, 0xFFFFFFFF, b"x" * 4097),))


def test_apply_restore_growth_and_repeated_restore(tmp_path: Path) -> None:
    root = tmp_path / "copy"
    root.mkdir()
    original = archive(root)
    handler = TigerV3Handler(root, ArchiveSettings("tiger", 3, 0x1000))
    translated = b"x" * 2049
    plan = handler.plan((ResourceReplacement("text", 0x12345678, 0xFFFFFFFF, translated),))
    journal = tmp_path / "transaction"
    apply_write_plan(root, plan, journal)
    assert handler.read(handler.resources()[0]) == translated
    restore_write_plan(root, journal)
    restore_write_plan(root, journal)
    assert (root / "bigfile.000.tiger").read_bytes() == original
    assert not (root / "bigfile.001.tiger").exists()
    with pytest.raises(TransactionError, match="already exists"):
        apply_write_plan(root, plan, journal)


def test_plan_rejects_changed_archive_before_writing(tmp_path: Path) -> None:
    root = tmp_path / "copy"
    root.mkdir()
    archive(root)
    handler = TigerV3Handler(root, ArchiveSettings("tiger", 3, 0x80000000))
    plan = handler.plan((ResourceReplacement("text", 0x12345678, 0xFFFFFFFF, b"new"),))
    path = root / "bigfile.000.tiger"
    path.write_bytes(path.read_bytes().replace(b"old", b"NEW"))
    with pytest.raises(TransactionError, match="changed"):
        apply_write_plan(root, plan, tmp_path / "transaction")


def test_plan_rejects_new_override_before_writing(tmp_path: Path) -> None:
    root = tmp_path / "copy"
    root.mkdir()
    original = archive(root)
    handler = TigerV3Handler(root, ArchiveSettings("tiger", 3, 0x80000000))
    plan = handler.plan((ResourceReplacement("text", 0x12345678, 0xFFFFFFFF, b"new"),))
    archive(root, "patch", 65, b"unexpected")
    with pytest.raises(TransactionError, match="archive set changed"):
        apply_write_plan(root, plan, tmp_path / "transaction")
    assert (root / "bigfile.000.tiger").read_bytes() == original


def test_plan_rejects_changed_source_part_even_when_appending_to_another_part(
    tmp_path: Path,
) -> None:
    root = tmp_path / "copy"
    root.mkdir()
    header = b"TAFS" + struct.pack("<4I", 3, 3, 1, 0) + bytes(32)
    row = struct.pack("<4I", 0x12345678, 0xFFFFFFFF, 3, 1)
    (root / "bigfile.000.tiger").write_bytes(header + row + bytes(0x800 - 68))
    (root / "bigfile.001.tiger").write_bytes(b"old")
    (root / "bigfile.002.tiger").write_bytes(b"tail")
    handler = TigerV3Handler(root, ArchiveSettings("tiger", 3, 0x80000000))
    plan = handler.plan((ResourceReplacement("text", 0x12345678, 0xFFFFFFFF, b"new"),))
    (root / "bigfile.001.tiger").write_bytes(b"NEW")
    with pytest.raises(TransactionError, match="source part changed"):
        apply_write_plan(root, plan, tmp_path / "transaction")


def test_service_extracts_and_writes_masked_locale_without_using_mask_as_record_locale(
    tmp_path: Path,
) -> None:
    root = tmp_path / "copy"
    root.mkdir()
    menu = struct.pack("<4I", 0, 0, 1, 16) + b"Hello\0"
    original = archive(root, data=menu)
    runtime = RuntimeSettings(
        ArchiveSettings("tiger", 3, 0x80000000),
        (LanguageSlot("en", 1, 0, locale_is_mask=True),),
        "en",
        (ResourceRule("menu", "locals.bin", "locals", 2),),
    )
    service = create_translation_service()
    result = service.extract(
        root,
        TranslationMetadata("example", "1", "en", "hu", "tiger", 3),
        runtime,
        {0x12345678: "locals.bin"},
    )
    document = result.document
    resource = document.menu[0]
    document = replace(
        document,
        menu=(replace(resource, entries=(replace(resource.entries[0], translation="Őű"),)),),
    )
    build = service.plan(root, document, package_dir=tmp_path)
    assert build.plan is not None
    assert not build.missing_translations
    service.apply(build, tmp_path / "transaction")
    translated = service.extract(root, document.metadata, runtime, {0x12345678: "locals.bin"})
    assert translated.document.menu[0].entries[0].source == "Őű"
    service.restore(root, tmp_path / "transaction")
    assert (root / "bigfile.000.tiger").read_bytes() == original
