import struct
from pathlib import Path
from typing import cast

import pytest

from pytrtt.archives.bigfile_v2 import BigFileV2Handler
from pytrtt.archives.contracts import ResourceReplacement
from pytrtt.config import parse_runtime_settings, runtime_to_dict


def runtime_data() -> dict[str, object]:
    return {
        "archive": {
            "format": "bigfile",
            "version": 2,
            "boundary": 32768,
            "families": ["patch0", "patch1"],
            "include_overridden": True,
            "index_files": {"patch0": "patch.000", "patch1": "patch.001"},
        },
        "languages": {"en": {"archive_locale": 1, "subtitle_language": 0}},
        "replacement_language": "en",
        "resource_types": [{"section": "menu", "pattern": "*", "format": "locals", "version": 1}],
    }


def test_independent_indexes_and_exact_aliases_restore_twice(tmp_path: Path) -> None:
    for name, text in [("patch.000", b"base"), ("patch.001", b"later")]:
        # Two distinct index rows alias the same original data, including unknown metadata.
        index = struct.pack(
            "<3I8I", 2, 0x1234, 0x1234, len(text), 1, 1, 0xAABB, len(text), 1, 1, 0xAABB
        )
        (tmp_path / name).write_bytes(index + bytes(2048 - len(index)) + text)
    originals = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    runtime = parse_runtime_settings(runtime_data())
    assert parse_runtime_settings(runtime_to_dict(runtime)) == runtime
    handler = BigFileV2Handler(tmp_path, runtime.archive)
    assert [handler.read(r) for r in handler.resources()] == [b"base", b"later"]
    plan = handler.plan(
        tuple(
            ResourceReplacement(
                "x", r.name_hash, r.locale, "ŐőŰű".encode(), archive_family=r.archive_family
            )
            for r in handler.resources()
        )
    )
    journal = tmp_path.parent / (tmp_path.name + "-journal")
    handler.apply(plan, journal, runtime)
    for name in originals:
        data = (tmp_path / name).read_bytes()
        assert data[12:28] == data[28:44]
    updated = BigFileV2Handler(tmp_path, runtime.archive)
    assert all(updated.read(r) == "ŐőŰű".encode() for r in updated.resources())
    updated.restore(journal)
    updated.restore(journal)
    assert {name: (tmp_path / name).read_bytes() for name in originals} == originals


@pytest.mark.parametrize(
    "filename", ["../patch.001", "patch.001.tiger", "patch.000/evil", "patch.abc"]
)
def test_independent_index_names_are_safe(filename: str) -> None:
    data = runtime_data()
    cast(dict[str, object], data["archive"])["index_files"] = {
        "patch0": "patch.000",
        "patch1": filename,
    }
    with pytest.raises(ValueError):
        parse_runtime_settings(data)


def test_conflicting_duplicate_rows_are_rejected(tmp_path: Path) -> None:
    index = struct.pack("<3I8I", 2, 0x1234, 0x1234, 4, 1, 1, 0, 4, 1, 1, 99)
    for name in ["patch.000", "patch.001"]:
        (tmp_path / name).write_bytes(index + bytes(2048 - len(index)) + b"data")
    runtime = parse_runtime_settings(runtime_data())
    with pytest.raises(ValueError, match="duplicate"):
        BigFileV2Handler(tmp_path, runtime.archive).resources()
