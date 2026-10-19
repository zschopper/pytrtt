"""Embedded DRM resources in TIGER v4 archives."""

import struct
from pathlib import Path

from pytrtt.archives.contracts import ResourceReplacement
from pytrtt.archives.tiger_v4 import TigerV4Handler
from pytrtt.archives.transaction import apply_write_plan, restore_write_plan
from pytrtt.config import ArchiveSettings


def _cdrm(data: bytes) -> bytes:
    return (
        b"CDRM"
        + struct.pack("<3I", 0, 1, 0)
        + struct.pack("<2I", len(data) * 256 + 1, len(data))
        + bytes(8)
        + data
    )


def _archive(root: Path, family: str, archive_id: int, collection: bytes, font: bytes) -> bytes:
    header = b"TAFS" + struct.pack("<4I", 4, 1, 1, archive_id) + b"pc-w\0" + bytes(27)
    entry = struct.pack(
        "<4IhhI", 0x12345678, 0xFFFFFFFF, len(collection), 0, 0, archive_id, 0x800
    )
    data = bytearray(header + entry + bytes(0x3000 - len(header + entry)))
    data[0x800 : 0x800 + len(collection)] = collection
    if archive_id == 1:
        packed = _cdrm(font)
        data[0x1800 : 0x1800 + len(packed)] = packed
        data[0x1800 + ((len(packed) + 15) & ~15) : 0x1800 + 0x800] = (
            b"NEXT" + bytes(12) + bytes(0x7F0 - ((len(packed) + 15) & ~15))
        )
    path = root / f"{family}.000.tiger"
    path.write_bytes(data)
    return bytes(data)


def test_embedded_v4_font_round_trip_and_restore(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    font = b"old font"
    packed = _cdrm(font)
    drm = struct.pack("<8I", 22, 0, 0, 0, 0, 0, 1, 0)
    drm += struct.pack("<IBBHIII", len(font), 7, 0, 0, 0, 2473, 0xFFFFFFFF)
    drm += struct.pack("<IIhhIII", 0x070009A9, 0, 0, 1, 0x1800, len(packed), 0x1000)
    originals = {
        "base.000.tiger": _archive(root, "base", 1, drm, font),
        "update.000.tiger": _archive(root, "update", 10, drm, font),
    }
    settings = ArchiveSettings(
        "tiger",
        4,
        0x80000000,
        families=("base", "update"),
        index_files=(
            ("base", "base.000.tiger"),
            ("update", "update.000.tiger"),
        ),
    )
    archive = TigerV4Handler(root, settings)
    assert archive.read_embedded(0x12345678, 0xFFFFFFFF, 7, 2473) == font
    request = ResourceReplacement(
        "font",
        0x12345678,
        0xFFFFFFFF,
        b"new Hungarian font" * 20,
        embedded_type=7,
        embedded_id=2473,
    )
    plan = archive.plan((request,))
    transaction = tmp_path / "transaction"
    apply_write_plan(root, plan, transaction)
    fresh = TigerV4Handler(root, settings)
    assert fresh.read_embedded(0x12345678, 0xFFFFFFFF, 7, 2473) == request.data
    assert (transaction / "backups/restore-data/fonts/embedded-1-0-0.bin").read_bytes() == font
    restore_write_plan(root, transaction)
    restore_write_plan(root, transaction)
    assert {name: (root / name).read_bytes() for name in originals} == originals


def test_maintained_lctoo_fonts_match_package_hashes() -> None:
    import hashlib
    import json

    package = (
        Path(__file__).resolve().parents[1]
        / "translations/lara-croft-and-the-temple-of-osiris"
    )
    document = json.loads((package / "hu.json").read_text(encoding="utf-8"))
    assert document["metadata"]["runtime"]["character_substitutions"] == {}
    assert {font["embedded_id"] for font in document["fonts"]} == {2473, 2474}
    for font in document["fonts"]:
        assert "character_substitutions" not in font
        asset = package / font["replacement_file"]
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == font["replacement_sha256"]
