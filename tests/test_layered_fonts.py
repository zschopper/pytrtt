"""Font assets can target one physical layer without replacing another layer."""

import hashlib
import json
import struct
from pathlib import Path
from typing import cast

import pytest

from pytrtt.archives.bigfile_v2 import BigFileV2Handler
from pytrtt.archives.transaction import restore_write_plan
from pytrtt.composition import create_translation_service
from pytrtt.packages.translation import parse_translation_document, serialize_translation_document


def package() -> dict[str, object]:
    return {
        "schema_version": 5,
        "metadata": {
            "game_id": "example",
            "build_id": "one",
            "source_language": "en",
            "target_language": "hu",
            "archive_format": "bigfile",
            "archive_version": 2,
            "runtime": {
                "archive": {
                    "format": "bigfile",
                    "version": 2,
                    "boundary": 32768,
                    "families": ["base", "patch"],
                    "include_overridden": True,
                },
                "languages": {"en": {"archive_locale": 1, "subtitle_language": 0}},
                "replacement_language": "en",
                "resource_types": [
                    {
                        "section": "fonts",
                        "pattern": "*.drm",
                        "format": "raw",
                        "version": 1,
                        "locale": 4294967295,
                    }
                ],
            },
        },
        "fonts": [
            {
                "resource_hash": "12345678",
                "resource_path": "font.drm",
                "replacement_file": "font.bin",
                "source_sha256": hashlib.sha256(b"patch font").hexdigest(),
                "replacement_sha256": hashlib.sha256(b"Hungarian glyphs").hexdigest(),
                "archive_family": "patch",
            }
        ],
    }


@pytest.mark.parametrize("families", [("patch",), ("base", "patch")])
def test_font_replaces_only_selected_layer_and_restores(
    tmp_path: Path, families: tuple[str, ...]
) -> None:
    root = tmp_path / "game"
    root.mkdir()
    originals = {}
    for family in ("base", "patch"):
        body = (family + " font").encode()
        header = struct.pack("<6I", 1, 0x12345678, len(body), 1, 0xFFFFFFFF, 0)
        original = header + bytes(2048 - len(header)) + body
        originals[family] = original
        (root / (family + ".000")).write_bytes(original)
    (tmp_path / "font.bin").write_bytes(b"Hungarian glyphs")
    data = package()
    template = cast(list[dict[str, object]], data["fonts"])[0]
    data["fonts"] = [
        dict(
            template,
            archive_family=family,
            source_sha256=hashlib.sha256((family + " font").encode()).hexdigest(),
        )
        for family in families
    ]
    doc = parse_translation_document(json.dumps(data))
    assert parse_translation_document(serialize_translation_document(doc)) == doc
    service = create_translation_service()
    build = service.plan(root, doc, package_dir=tmp_path)
    assert build.plan is not None
    assert set(build.plan.files) == {family + ".000" for family in families}
    tx = tmp_path / "transaction"
    service.apply(build, tx)
    assert doc.runtime is not None
    archive = BigFileV2Handler(root, doc.runtime.archive)
    assert {r.archive_family: archive.read(r) for r in archive.resources()} == {
        family: b"Hungarian glyphs" if family in families else (family + " font").encode()
        for family in ("base", "patch")
    }
    restore_write_plan(root, tx)
    restore_write_plan(root, tx)
    assert {family: (root / (family + ".000")).read_bytes() for family in originals} == originals


@pytest.mark.parametrize("family", ["../patch", "", "patch.000", 42])
def test_font_rejects_unsafe_family(family: object) -> None:
    data = package()
    cast(list[dict[str, object]], data["fonts"])[0]["archive_family"] = family
    with pytest.raises(ValueError, match="archive_family"):
        parse_translation_document(json.dumps(data))


def test_two_layer_fonts_can_share_hash_but_duplicate_layer_is_rejected() -> None:
    data = package()
    fonts = cast(list[dict[str, object]], data["fonts"])
    first = fonts[0]
    fonts.append(dict(first, archive_family="base"))
    doc = parse_translation_document(json.dumps(data))
    assert len(doc.fonts) == 2
    assert parse_translation_document(serialize_translation_document(doc)) == doc
    fonts.append(dict(first))
    with pytest.raises(ValueError, match="duplicate font"):
        parse_translation_document(json.dumps(data))


def test_extraction_keeps_distinct_layer_recovery_paths(tmp_path: Path) -> None:
    for family in ("base", "patch"):
        body = (family + " font").encode()
        header = struct.pack("<6I", 1, 0x12345678, len(body), 1, 0xFFFFFFFF, 0)
        (tmp_path / (family + ".000")).write_bytes(header + bytes(2048 - len(header)) + body)
    doc = parse_translation_document(json.dumps(package()))
    assert doc.runtime is not None
    result = create_translation_service().extract(
        tmp_path, doc.metadata, doc.runtime, {0x12345678: "font.drm"}
    )
    recovery = {asset.recovery_path: asset.data for asset in result.recovery_assets}
    assert recovery == {
        "restore-data/fonts/12345678-FFFFFFFF-base.raw": b"base font",
        "restore-data/fonts/12345678-FFFFFFFF-patch.raw": b"patch font",
    }
