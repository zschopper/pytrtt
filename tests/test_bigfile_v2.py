import struct
from pathlib import Path

import pytest

from pytrtt.archives.bigfile_v2 import BigFileV2Handler
from pytrtt.archives.contracts import ResourceReplacement
from pytrtt.config import ArchiveSettings, LanguageSlot, ResourceRule, RuntimeSettings


def archive(path: Path, text: bytes) -> None:
    header = struct.pack("<II4I", 1, 0x1234, len(text), 1, 1, 0xAABBCCDD)
    path.write_bytes(header + bytes(2048 - len(header)) + text)


def test_explicit_layers_append_and_restore_twice(tmp_path: Path) -> None:
    archive(tmp_path / "bigfile.000", b"base")
    archive(tmp_path / "patch.000", b"patch")
    originals = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    settings = ArchiveSettings(
        "bigfile", 2, 0x8000, families=("bigfile", "patch"), include_overridden=True
    )
    handler = BigFileV2Handler(tmp_path, settings)
    refs = handler.resources()
    assert [(r.archive_family, handler.read(r)) for r in refs] == [
        ("bigfile", b"base"),
        ("patch", b"patch"),
    ]
    plan = handler.plan(
        tuple(
            ResourceReplacement(
                "text",
                r.name_hash,
                r.locale,
                ("Őű" * 100).encode(),
                archive_family=r.archive_family,
            )
            for r in refs
        )
    )
    runtime = RuntimeSettings(
        settings, (LanguageSlot("en", 1, 0),), "en", (ResourceRule("menu", "*", "locals", 1),)
    )
    journal = tmp_path.parent / (tmp_path.name + "-journal")
    handler.apply(plan, journal, runtime)
    updated = BigFileV2Handler(tmp_path, settings)
    assert all(updated.read(r) == ("Őű" * 100).encode() for r in updated.resources())
    updated.restore(journal)
    updated.restore(journal)
    assert {p.name: p.read_bytes() for p in tmp_path.glob("*.000")} == originals


def test_priority_and_source_revalidation(tmp_path: Path) -> None:
    archive(tmp_path / "bigfile.000", b"base")
    archive(tmp_path / "patch.000", b"patch")
    settings = ArchiveSettings("bigfile", 2, 0x8000, families=("bigfile", "patch"))
    h = BigFileV2Handler(tmp_path, settings)
    assert len(h.resources()) == 1 and h.read(h.resources()[0]) == b"patch"
    p = h.plan((ResourceReplacement("x", 0x1234, 1, b"changed"),))
    (tmp_path / "bigfile.000").write_bytes((tmp_path / "bigfile.000").read_bytes() + b"x")
    with pytest.raises(ValueError, match="changed"):
        p.validate_inputs(tmp_path)
