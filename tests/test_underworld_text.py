import struct

import pytest

from pytrtt.formats.contracts import TextOptions
from pytrtt.formats.handlers import CineV3Handler
from pytrtt.formats.reboot_text import SchV2Handler
from pytrtt.packages.translation import TranslationEntry


def test_cine_opaque_type_three_growth_and_other_language() -> None:
    opaque = struct.pack("<4I", 3, 16, 77, 88) + b"opaque binary!!!"
    text = b"0\rHello\r1\rBonjour\r"
    content = b"unknown!" + bytes(16) + struct.pack("<I", len(text)) + text
    body = struct.pack("<I", len(content)) + content
    body += bytes((-len(body)) % 16)
    block = struct.pack("<4I", 1, len(body), 123, 456) + body
    data = bytes(2048) + opaque + block
    h = CineV3Handler()
    assert h.extract(data, 0)[0].entry_id == 1
    assert h.write(data, (), TextOptions(0)) == data
    new = h.write(data, (TranslationEntry(1, "Hello", "ŐőŰű" * 30),), TextOptions(0))
    assert new[2048 : 2048 + len(opaque)] == opaque
    assert new[2048 + len(opaque) + 20 : 2048 + len(opaque) + 44] == b"unknown!" + bytes(16)
    assert h.extract(new, 0)[0].source == "ŐőŰű" * 30
    assert h.extract(new, 1)[0].source == "Bonjour"
    with pytest.raises(ValueError):
        h.extract(data[:-1], 0)


def test_sch_inline_escape_preserves_segments_and_times() -> None:
    data = (
        b"Version 1\r\nTextEntry\r\nline0\r\n"
        b'lang_english 2008-11-03 11:59:59 "Hello\\nthere\\(2.0)Next"\r\n'
    )
    h = SchV2Handler()
    assert [e.source for e in h.extract(data, 0)] == [r"Hello\nthere", "Next"]
    translated = h.write(
        data, (TranslationEntry(0, r"Hello\nthere", r"Helló\nott"),), TextOptions(0)
    )
    assert b"\\(2.0)Next" in translated
    assert h.extract(translated, 0)[0].source == r"Helló\nott"
    with pytest.raises(ValueError, match="delimiter"):
        h.write(data, (TranslationEntry(0, r"Hello\nthere", r"bad\(3)segment"),), TextOptions(0))


def test_large_enic_metadata_is_preserved_without_subtitles() -> None:
    body = b"ENIC" + bytes(0x2000C)
    data = bytes(2048) + struct.pack("<4I", 1, len(body), 17, 29) + body
    h = CineV3Handler()
    assert h.extract(data, 0) == ()
    assert h.write(data, (), TextOptions(0)) == data
