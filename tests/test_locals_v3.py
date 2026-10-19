"""64-bit unkeyed locals extraction uses text slots, not input-specific key IDs."""

import struct

import pytest

from pytrtt.composition import create_handler_registry
from pytrtt.formats.contracts import TextOptions


def table() -> bytes:
    # Two input key IDs; four slots: absent, Unicode text, alias, empty text.
    return struct.pack("<3I2I4Q", 0, 2, 4, 100, 200, 0, 52, 52, 59) + "Ő\ue001ű".encode() + b"\0\0"


def test_extract_slots_aliases_empty_and_control_placeholders() -> None:
    handler = create_handler_registry().text_format("locals", 3)
    entries = handler.extract(table(), 0)
    assert [(e.entry_id, e.source, e.translation) for e in entries] == [
        (1, "Ő{0}ű", None),
        (2, "Ő{0}ű", None),
        (3, "", None),
    ]
    with pytest.raises(ValueError, match="read-only"):
        handler.write(table(), (), TextOptions(0))


@pytest.mark.parametrize("data", [b"", struct.pack("<3I", 0, 0, 1), table()[:-2]])
def test_rejects_truncated_tables_and_unterminated_strings(data: bytes) -> None:
    with pytest.raises(ValueError):
        create_handler_registry().text_format("locals", 3).extract(data, 0)


@pytest.mark.parametrize("offset", [1, 20, 51, 1000, 0x100000034])
def test_validates_full_64_bit_pointers(offset: int) -> None:
    data = bytearray(table())
    struct.pack_into("<Q", data, 28, offset)
    with pytest.raises(ValueError, match="pointer"):
        create_handler_registry().text_format("locals", 3).extract(bytes(data), 0)


@pytest.mark.parametrize("header", [b"Version 1\r\n", b""])
def test_sch_optional_header_and_segment_identity(
    header: bytes,
) -> None:
    data = (
        header + b'TextEntry\r\nline0\r\nlang_english 0 "(0.1)[Lara]Hello\\(1.2)World\\nnext"\r\n'
    )
    handler = create_handler_registry().text_format("sch", 3)
    entries = handler.extract(data, 0)
    assert [(e.entry_id, e.source, e.comment) for e in entries] == [
        (0, "Hello", ("(0.1)[Lara]",)),
        (1, "World\\nnext", ("(1.2)",)),
    ]
    with pytest.raises(ValueError, match="read-only"):
        handler.write(data, (), TextOptions(0))


def test_sch_variant_rejects_unknown_header() -> None:
    with pytest.raises(ValueError, match="header"):
        create_handler_registry().text_format("sch", 3).extract(b"Version 2\nTextEntry\nline0\n", 0)
