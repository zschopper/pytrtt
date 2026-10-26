"""64-bit locals and optional-header SCH preserve record and binary identity."""

import struct

import pytest

from pytrtt.composition import create_handler_registry
from pytrtt.formats.contracts import TextOptions
from pytrtt.packages.translation import TranslationEntry


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
    assert handler.write(table(), (), TextOptions(0)) == table()


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
    assert handler.write(data, (), TextOptions(0)) == data


def test_sch_variant_rejects_unknown_header() -> None:
    with pytest.raises(ValueError, match="header"):
        create_handler_registry().text_format("sch", 3).extract(b"Version 2\nTextEntry\nline0\n", 0)


def test_locals_growth_preserves_header_inputs_alias_and_opaque_bytes() -> None:
    original = bytearray(table() + b"OPAQUE\xff\x00")
    struct.pack_into("<I", original, 0, 0xAABBCCDD)
    data = bytes(original)
    handler = create_handler_registry().text_format("locals", 3)
    entry = TranslationEntry(1, "Ő{0}ű", "{0} " + "Őű hosszabb " * 40)
    rebuilt = handler.write(data, (entry,), TextOptions(0))
    assert rebuilt[:28] == data[:28]
    assert rebuilt[36 : len(data)] == data[36:]
    assert struct.unpack_from("<Q", rebuilt, 28)[0] == len(data)
    assert rebuilt[len(data) :] == ("\ue001 " + "Őű hosszabb " * 40).encode() + b"\0"
    result = handler.extract(rebuilt, 0)
    assert [(e.entry_id, e.source) for e in result] == [
        (1, entry.translation),
        (2, "Ő{0}ű"),
        (3, ""),
    ]
    assert handler.write(rebuilt, (entry,), TextOptions(0)) == rebuilt


def test_locals_translated_aliases_share_pointer_and_empty_translation_is_space() -> None:
    handler = create_handler_registry().text_format("locals", 3)
    entries = (
        TranslationEntry(1, "Ő{0}ű", "Új {0}"),
        TranslationEntry(2, "Ő{0}ű", "Új {0}"),
        TranslationEntry(3, "", ""),
    )
    rebuilt = handler.write(table(), entries, TextOptions(0))
    assert struct.unpack_from("<Q", rebuilt, 28) == struct.unpack_from("<Q", rebuilt, 36)
    assert [e.source for e in handler.extract(rebuilt, 0)] == ["Új {0}", "Új {0}", " "]


def test_locals_respects_substitution_disabled_and_keeps_literal_format_tokens() -> None:
    original = struct.pack("<3IQ", 7, 0, 1, 20) + b"Format {7}\0"
    handler = create_handler_registry().text_format("locals", 3)
    options = TextOptions(0, (("ő", "ô"),))
    for disabled, expected in ((False, "ô {7}"), (True, "ő {7}")):
        entry = TranslationEntry(0, "Format {7}", "ő {7}", substitution_disabled=disabled)
        rebuilt = handler.write(original, (entry,), options)
        assert handler.extract(rebuilt, 0)[0].source == expected


@pytest.mark.parametrize("text", ["missing", "{0}{0}", "{1}", "{0}{99}", "{0}\ue002"])
def test_locals_rejects_changed_control_placeholders(text: str) -> None:
    with pytest.raises(ValueError, match="placeholder"):
        create_handler_registry().text_format("locals", 3).write(
            table(), (TranslationEntry(1, "Ő{0}ű", text),), TextOptions(0)
        )


@pytest.mark.parametrize("ident", [-1, 0, 4, 100])
def test_locals_rejects_nonexistent_text_slots(ident: int) -> None:
    with pytest.raises(ValueError, match="record"):
        create_handler_registry().text_format("locals", 3).write(
            table(), (TranslationEntry(ident, "", "New"),), TextOptions(0)
        )


def test_locals_rejects_duplicate_identity_null_delimiter_and_changed_source() -> None:
    handler = create_handler_registry().text_format("locals", 3)
    entry = TranslationEntry(1, "Ő{0}ű", "New {0}")
    with pytest.raises(ValueError, match="duplicate"):
        handler.write(table(), (entry, entry), TextOptions(0))
    with pytest.raises(ValueError, match="null"):
        handler.write(table(), (TranslationEntry(1, "Ő{0}ű", "{0}\0bad"),), TextOptions(0))
    with pytest.raises(ValueError, match="source"):
        handler.write(table(), (TranslationEntry(1, "Changed", "New {0}"),), TextOptions(0))


@pytest.mark.parametrize("header", [b"", b"Version 1\r\n", b"Version 1\n"])
@pytest.mark.parametrize("ending", [b"", b"\r\n", b"\n"])
def test_sch_writes_optional_header_preserving_timing_rows_and_line_endings(
    header: bytes,
    ending: bytes,
) -> None:
    data = (
        header + b"TextEntry\r\nline0\r\n"
        b'lang_english 2018-01-01 12:00:00 "(0.1)[Lara]Hello\\(1.2)World\\nnext"  \r\n'
        b'lang_french 1 "Bonjour"' + ending
    )
    handler = create_handler_registry().text_format("sch", 3)
    entries = (TranslationEntry(1, "World\\nnext", "Őű\\nhosszabb " * 20),)
    rebuilt = handler.write(data, entries, TextOptions(0))
    expected = data.replace(b"World\\nnext", ("Őű\\nhosszabb " * 20).encode())
    assert rebuilt == expected
    extracted = handler.extract(rebuilt, 0)
    assert [(e.entry_id, e.source, e.comment) for e in extracted] == [
        (0, "Hello", ("(0.1)[Lara]",)),
        (1, entries[0].translation, ("(1.2)",)),
    ]
    assert handler.write(rebuilt, entries, TextOptions(0)) == rebuilt
    french = handler.write(data, (TranslationEntry(0, "Bonjour", "Jó napot"),), TextOptions(1))
    assert french == data.replace(b"Bonjour", "Jó napot".encode())


@pytest.mark.parametrize("text", ["bad\nrow", "bad\rrow", "bad\0text", "bad\\(2.0)new", "(2.0)new"])
def test_sch_rejects_structure_injection(text: str) -> None:
    data = b'TextEntry\nline0\nlang_english 1 "Hello"\n'
    with pytest.raises(ValueError, match="delimiter|structure"):
        create_handler_registry().text_format("sch", 3).write(
            data, (TranslationEntry(0, "Hello", text),), TextOptions(0)
        )


def test_sch_validates_identity_and_source() -> None:
    data = b'TextEntry\nline0\nlang_english 1 "Hello"\n'
    handler = create_handler_registry().text_format("sch", 3)
    entry = TranslationEntry(0, "Hello", "Helló")
    with pytest.raises(ValueError, match="duplicate"):
        handler.write(data, (entry, entry), TextOptions(0))
    with pytest.raises(ValueError, match="segment|record"):
        handler.write(data, (TranslationEntry(1, "Hello", "Helló"),), TextOptions(0))
    with pytest.raises(ValueError, match="source"):
        handler.write(data, (TranslationEntry(0, "Other", "Helló"),), TextOptions(0))


@pytest.mark.parametrize(
    "format_name,version,data",
    [
        ("locals", 3, table()),
        ("sch", 3, b'TextEntry\nline0\nlang_english 1 "Hello"\n'),
    ],
)
@pytest.mark.parametrize("clearing", [True, False])
def test_new_writers_reject_unverified_language_clearing(
    format_name: str,
    version: int,
    data: bytes,
    clearing: bool,
) -> None:
    options = TextOptions(
        0,
        cleared_languages=frozenset({1}) if clearing else frozenset(),
        omitted_languages=frozenset() if clearing else frozenset({1}),
    )
    with pytest.raises(ValueError, match="language"):
        create_handler_registry().text_format(format_name, version).write(data, (), options)
