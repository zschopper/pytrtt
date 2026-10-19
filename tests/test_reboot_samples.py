"""Opt-in tests of local Steam 9573671 resource and archive copies; no game assets in Git."""

import hashlib
import json
from dataclasses import replace

import pytest

from pytrtt.archives.tiger_v3 import read_tiger_v3_index
from pytrtt.formats.contracts import TextFormatHandler, TextOptions
from pytrtt.formats.reboot_text import CineV2Handler, LocalsV2Handler, SchV1Handler
from tests.game_samples import GameSamples


@pytest.mark.integration
@pytest.mark.game("tr2013", build="9573671")
@pytest.mark.parametrize(
    ("file", "count"),
    [
        ("7CD333D3-FFFF1101.locals", 753),
        ("00036E34-FFFFDD41.cine", 1),
        ("00165E7F-FFFFDD41.cine", 2),
        ("0032D982-FFFFDD41.cine", 1),
        ("1525CC4D-FFFFFFFF.cine", 4),
        ("EF4C7C2C-FFFFDD41.cine", 32),
        ("185001C1-FFFFFFFF.sch", 6),
        ("1CB7D6A8-FFFFFFFF.sch", 38),
    ],
)
def test_local_text_copy_noop_and_growth(game_samples: GameSamples, file: str, count: int) -> None:
    data = game_samples.require(file).read_bytes()
    handlers: dict[str, TextFormatHandler] = {
        "locals": LocalsV2Handler(),
        "cine": CineV2Handler(),
        "sch": SchV1Handler(),
    }
    handler = handlers[file.rsplit(".", 1)[-1]]
    entries = handler.extract(data, 0)
    assert len(entries) == count
    assert handler.write(data, (), TextOptions(0)) == data
    chosen = next(e for e in entries if e.source and "{0}" not in e.source)
    changed = replace(chosen, translation="Árvíztűrő tükörfúrógép " * 40)
    rebuilt = handler.write(data, (changed,), TextOptions(0))
    result = handler.extract(rebuilt, 0)
    assert len(result) == count
    assert next(e for e in result if e.entry_id == chosen.entry_id).source == changed.translation
    assert [(e.entry_id, e.source) for e in result if e.entry_id != chosen.entry_id] == [
        (e.entry_id, e.source) for e in entries if e.entry_id != chosen.entry_id
    ]
    if file.endswith(".cine"):
        assert rebuilt[:8192] == data[:8192]
        assert handler.extract(rebuilt, 9) == handler.extract(data, 9)


@pytest.mark.integration
@pytest.mark.game("tr2013", build="9573671")
def test_local_archive_index_copies_and_russian_routing(game_samples: GameSamples) -> None:
    for family, priority in [("bigfile", 0), ("title", 64), ("patch", 65), ("patch3", 69)]:
        path = game_samples.require(f"{family}.index")
        with path.open("rb") as stream:
            index = read_tiger_v3_index(stream)
        assert index.priority == priority
        assert index.serialize() == path.read_bytes()
    cine = game_samples.require("EF4C7C2C-FFFFDD41.cine").read_bytes()
    assert sum(e.source_language == "ru" for e in CineV2Handler().extract(cine, 0)) == 2
    manifest = json.loads(game_samples.require("manifest.json").read_text(encoding="utf-8"))
    for record in manifest:
        assert (
            hashlib.sha256(game_samples.require(record["file"]).read_bytes()).hexdigest()
            == (record["sha256"])
        )
