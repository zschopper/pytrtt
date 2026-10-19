"""Package and archive behavior for fonts stored inside DRM collections."""

import json
import struct
from pathlib import Path

import pytest

from pytrtt.archives.contracts import ResourceReplacement
from pytrtt.archives.tiger_v3 import TigerV3Handler, read_tiger_v3_index
from pytrtt.archives.transaction import apply_write_plan, restore_write_plan
from pytrtt.config import ArchiveSettings
from pytrtt.packages.translation import parse_translation_document, serialize_translation_document


def test_two_fonts_in_one_collection_round_trip() -> None:
    root = {
        "schema_version": 5,
        "metadata": dict(
            game_id="example",
            build_id="one",
            source_language="en",
            target_language="hu",
            archive_format="tiger",
            archive_version=3,
        ),
        "fonts": [
            dict(
                resource_hash="12345678",
                resource_path="font.drm",
                replacement_file=f"assets/fonts/{i}.bin",
                source_sha256="a" * 64,
                replacement_sha256="b" * 64,
                embedded_type=7,
                embedded_id=i,
            )
            for i in (10, 11)
        ],
    }
    doc = parse_translation_document(json.dumps(root))
    assert [f.embedded_id for f in doc.fonts] == [10, 11]
    assert parse_translation_document(serialize_translation_document(doc)) == doc
    fonts = root["fonts"]
    assert isinstance(fonts, list)
    fonts[1]["embedded_id"] = 10
    with pytest.raises(ValueError, match="duplicate font"):
        parse_translation_document(json.dumps(root))


def test_embedded_identity_requires_both_fields_and_schema_five() -> None:
    root = dict(
        schema_version=5,
        metadata=dict(
            game_id="example",
            build_id="one",
            source_language="en",
            target_language="hu",
            archive_format="tiger",
            archive_version=3,
        ),
        fonts=[
            dict(
                resource_hash="12345678",
                resource_path="font.drm",
                replacement_file="a.bin",
                source_sha256="a" * 64,
                replacement_sha256="b" * 64,
                embedded_type=7,
            )
        ],
    )
    with pytest.raises(ValueError, match="embedded"):
        parse_translation_document(json.dumps(root))


def font_archives(root: Path) -> dict[str, bytes]:
    root.mkdir()

    def container(data: bytes) -> bytes:
        return (
            b"CDRM"
            + struct.pack("<3I", 0, 1, 0)
            + struct.pack("<2I", len(data) * 256 + 1, len(data))
            + bytes(8)
            + data
        )

    a, b = container(b"font one"), container(b"font two")
    drm = struct.pack("<8I", 22, 0, 0, 0, 0, 0, 2, 0)
    drm += b"".join(struct.pack("<IBBHIII", 8, 7, 0, 0, 0, i, 0xFFFFFFFF) for i in (10, 11))
    drm += struct.pack("<4I", 0x0700000A, 0x1400, len(a), 0)
    drm += struct.pack("<4I", 0x0700000B, 0x1C00, len(b), 16)
    originals = {}
    for name, priority in [("title", 64), ("patch", 65)]:
        header = b"TAFS" + struct.pack("<4I", 3, 1, 2, priority) + b"pc-w\0" + bytes(27)
        index = struct.pack("<4I", 0x12345678, 0xFFFFFFFF, len(drm), 0x800 | priority * 16)
        index += struct.pack("<4I", 0x87654321, 1, 4, 0x2000 | priority * 16)
        data = bytearray(header + index + bytes(0x2800 - len(header + index)))
        data[0x800 : 0x800 + len(drm)] = drm
        data[0x2000:0x2004] = b"text"
        if name == "title":
            data[0x1000 : 0x1000 + len(a)] = a
            data[0x1030:0x1040] = b"NEXT" + bytes(12)
            data[0x1800 : 0x1800 + len(b)] = b
            data[0x1830:0x1840] = b"NEXT" + bytes(12)
        originals[name + ".000.tiger"] = bytes(data)
        (root / (name + ".000.tiger")).write_bytes(data)
    return originals


def test_embedded_fonts_combine_with_text_and_restore_exactly(tmp_path: Path) -> None:
    root = tmp_path / "game"
    originals = font_archives(root)
    h = TigerV3Handler(root, ArchiveSettings("tiger", 3, 0x80000000, include_overridden=True))
    assert h.read_embedded(0x12345678, 0xFFFFFFFF, 7, 10) == b"font one"
    requests = (
        ResourceReplacement(
            "font", 0x12345678, 0xFFFFFFFF, b"font one grew" * 50, embedded_type=7, embedded_id=10
        ),
        ResourceReplacement("text", 0x87654321, 1, b"magyar", archive_family="title"),
    )
    plan = h.plan(requests)
    tx = tmp_path / "transaction"
    apply_write_plan(root, plan, tx)
    fresh = TigerV3Handler(root, h.settings)
    assert fresh.read_embedded(0x12345678, 0xFFFFFFFF, 7, 10) == b"font one grew" * 50
    assert fresh.read_embedded(0x12345678, 0xFFFFFFFF, 7, 11) == b"font two"
    # Both physical collection layers must point to the same new, nonoverlapping range.
    virtuals = []
    for family in ("title", "patch"):
        p = root / (family + ".000.tiger")
        with p.open("rb") as f:
            idx = read_tiger_v3_index(f)
            entry = idx.entries[0]
            f.seek(entry.offset)
            drm = f.read(entry.size)
        key, packed, size, virtual = struct.unpack_from("<4I", drm, 72)
        virtuals.append(virtual)
        assert virtual >= 32
        with (root / "title.000.tiger").open("rb") as f:
            f.seek((packed & ~2047) + ((size + 15) & ~15))
            assert f.read(16) == b"NEXT" + bytes(12)
    assert virtuals[0] == virtuals[1]
    restore_write_plan(root, tx)
    restore_write_plan(root, tx)
    assert {n: (root / n).read_bytes() for n in originals} == originals


def test_shared_service_validates_assets_and_applies_font_substitutions(tmp_path: Path) -> None:
    import hashlib
    from dataclasses import replace

    from pytrtt.composition import create_translation_service
    from pytrtt.config import LanguageSlot, ResourceRule, RuntimeSettings
    from pytrtt.packages.translation import FontAsset, TranslationDocument, TranslationMetadata
    from pytrtt.packages.translation_memory import bind_translation_memory

    root = tmp_path / "game"
    font_archives(root)
    asset = tmp_path / "font.bin"
    asset.write_bytes(b"new font")
    font = FontAsset(
        "12345678",
        "font.drm",
        "font.bin",
        hashlib.sha256(b"font one").hexdigest(),
        hashlib.sha256(b"new font").hexdigest(),
        7,
        10,
        character_substitutions=(("ő", "ô"),),
    )
    runtime = RuntimeSettings(
        ArchiveSettings("tiger", 3, 0x80000000, include_overridden=True),
        (LanguageSlot("en", 1, 0),),
        "en",
        (ResourceRule("menu", "*.bin", "locals", 2),),
    )
    doc = TranslationDocument(
        TranslationMetadata("example", "one", "en", "hu", "tiger", 3),
        fonts=(font,),
        runtime=runtime,
    )
    service = create_translation_service()
    build = service.plan(root, doc, package_dir=tmp_path)
    assert build.plan is not None
    assert build.runtime.character_substitutions == (("ő", "ô"),)
    memory = replace(doc, entry_identity="source_text", runtime=None)
    bound = bind_translation_memory(memory, replace(doc, fonts=()))
    assert bound.fonts == doc.fonts
    assert bound.runtime == runtime
    with pytest.raises(ValueError, match="original embedded font hash"):
        service.plan(
            root, replace(doc, fonts=(replace(font, source_sha256="0" * 64),)), package_dir=tmp_path
        )
    asset.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="replacement font hash"):
        service.plan(root, doc, package_dir=tmp_path)


@pytest.mark.parametrize(
    "flags,packed,data", [(0x801, 7, b"1234567"), (0x803, 8, b"12345678"), (0x802, 4, b"bad!")]
)
def test_invalid_compressed_font_chunks_fail(flags: int, packed: int, data: bytes) -> None:
    from pytrtt.archives.drm_v22 import decode_cdrm

    raw = (
        b"CDRM" + struct.pack("<3I", 0, 1, 0) + struct.pack("<2I", flags, packed) + bytes(8) + data
    )
    with pytest.raises(ValueError):
        decode_cdrm(raw)


def test_maintained_fonts_match_verified_assets() -> None:
    import hashlib

    package = Path(__file__).resolve().parents[1] / "translations/tomb-raider"
    doc = parse_translation_document((package / "hu.json").read_text(encoding="utf-8"))
    expected = {
        24842: "ae7ca6d9d25097b05fb963c31f1130f5c96aeeda6872b26ab957eba1bcc4fc5b",
        121631: "3e5feed8b5e5ba510c689188c059f6fe8456549e9564996bead6690395198f41",
    }
    assert len(doc.fonts) == 2
    for font in doc.fonts:
        assert font.embedded_id in expected
        assert font.replacement_sha256 == expected[font.embedded_id]
        assert (
            hashlib.sha256((package / font.replacement_file).read_bytes()).hexdigest()
            == font.replacement_sha256
        )
        assert font.character_substitutions == (("Ő", "Ô"), ("ő", "ô"), ("Ű", "Û"), ("ű", "û"))
