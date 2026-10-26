import struct

import pytest

from pytrtt.formats.contracts import TextOptions
from pytrtt.formats.reboot_text import CineV2Handler, LocalsV2Handler, SchV1Handler
from pytrtt.packages.translation import TranslationEntry


def test_cine_french_reclamation_preserves_timing_and_other_languages() -> None:
    handler = CineV2Handler()
    original = cine(b"0\r[p1]Hello\r1\r[p1]Bonjour\r9\rRussian\r", embedded=True)
    rebuilt = handler.clear_subtitle_language(original, 1)
    assert handler.extract(rebuilt, 0) == handler.extract(original, 0)
    assert handler.extract(rebuilt, 9) == handler.extract(original, 9)
    assert handler.extract(rebuilt, 1)[0].source == " "
    assert handler.extract(rebuilt, 1)[0].comment == ("[p1]",)
    assert handler.clear_subtitle_language(rebuilt, 1) == rebuilt


def test_subtitle_exact_capacity_keeps_french_bytes() -> None:
    from pytrtt.services.translation import _fit_subtitle_resource

    data = cine(b"0\rHello\r1\rBonjour\r", embedded=True)
    assert (
        _fit_subtitle_resource(
            CineV2Handler(),
            data,
            boundary=len(data),
            target_language=0,
            original_size=len(data),
            identity="fixture",
            clear_languages=(1,),
        )
        == data
    )


def test_sch_french_reclamation_preserves_segment_structure() -> None:
    from pytrtt.formats.reboot_text import SchV3Handler

    original = (
        b"TextEntry\r\nline0\r\n"
        b'lang_english 1 "(1.0)[p]Hello"\r\n'
        b'lang_french 1 "(1.0)[p]Bonjour\\(2.0)Monde"  \r\n'
    )
    handler = SchV3Handler()
    rebuilt = handler.clear_subtitle_language(original, 1)
    assert rebuilt == (
        b"TextEntry\r\nline0\r\n"
        b'lang_english 1 "(1.0)[p]Hello"\r\n'
        b'lang_french 1 "(1.0)[p] \\(2.0) "  \r\n'
    )
    assert handler.clear_subtitle_language(rebuilt, 1) == rebuilt


@pytest.mark.parametrize("target_language,boundary", [(1, 8300), (0, 8192)])
def test_subtitle_capacity_rejects_target_clearing_and_insufficient_savings(
    target_language: int, boundary: int
) -> None:
    from pytrtt.packages.translation import TranslationPackageError
    from pytrtt.services.translation import _fit_subtitle_resource

    data = cine(b"0\r" + b"H" * 200 + b"\r1\r" + b"F" * 200 + b"\r", embedded=True)
    with pytest.raises(TranslationPackageError, match="boundary|replacement language"):
        _fit_subtitle_resource(
            CineV2Handler(),
            data,
            boundary=boundary,
            target_language=target_language,
            original_size=len(data),
            identity="fixture",
            clear_languages=(1,),
        )


@pytest.mark.parametrize("languages,expected", [((1,), (" ", "Russian")), ((9,), ("Bonjour", " "))])
def test_capacity_clears_only_configured_languages(
    languages: tuple[int, ...], expected: tuple[str, str]
) -> None:
    handler = CineV2Handler()
    data = cine(b"0\rHello\r1\rBonjour\r9\rRussian\r", embedded=True)
    rebuilt = handler.clear_subtitle_language(data, languages[0])
    assert (
        handler.extract(rebuilt, 1)[0].source,
        handler.extract(rebuilt, 9)[0].source,
    ) == expected


def test_capacity_can_require_two_languages_and_stops_once_fitting() -> None:
    from pytrtt.services.translation import _fit_subtitle_resource

    handler = CineV2Handler()
    data = cine(
        b"0\rHello\r1\r" + b"F" * 500 + b"\r9\r" + b"R" * 500 + b"\r2\rKeep\r", embedded=True
    )
    rebuilt = _fit_subtitle_resource(
        handler,
        data,
        boundary=8500,
        target_language=0,
        original_size=len(data),
        identity="fixture",
        clear_languages=(1, 9, 2),
    )
    assert handler.extract(rebuilt, 0)[0].source == "Hello"
    assert handler.extract(rebuilt, 1)[0].source == " "
    assert handler.extract(rebuilt, 9)[0].source == " "
    assert handler.extract(rebuilt, 2)[0].source == "Keep"


def test_capacity_disabled_by_default() -> None:
    from pytrtt.packages.translation import TranslationPackageError
    from pytrtt.services.translation import _fit_subtitle_resource

    data = cine(b"0\rHello\r1\r" + b"F" * 500 + b"\r", embedded=True)
    with pytest.raises(TranslationPackageError, match="without safe reclamation"):
        _fit_subtitle_resource(
            CineV2Handler(),
            data,
            boundary=8500,
            target_language=0,
            original_size=len(data),
            identity="fixture",
        )


def test_capacity_respects_priority_without_sorting_languages() -> None:
    from pytrtt.services.translation import _fit_subtitle_resource

    handler = CineV2Handler()
    data = cine(b"0\rHello\r1\r" + b"F" * 500 + b"\r9\r" + b"R" * 500 + b"\r", embedded=True)
    rebuilt = _fit_subtitle_resource(
        handler,
        data,
        boundary=9000,
        target_language=0,
        original_size=len(data),
        identity="fixture",
        clear_languages=(9, 1),
    )
    assert handler.extract(rebuilt, 9)[0].source == " "
    assert handler.extract(rebuilt, 1)[0].source == "F" * 500


def cine(text: bytes, *, embedded: bool = False) -> bytes:
    if embedded:
        payload = b"ENIC" + struct.pack("<II", 13, 100) + bytes(96)
        payload += struct.pack("<III", (8 + len(text) + 15) & ~15, 0, len(text)) + text
    else:
        payload = b"opaque data!" + struct.pack("<I", len(text)) + text
    payload += bytes((-len(payload)) % 16)
    return bytes(8192) + struct.pack("<4I", 1, len(payload), 17, 29) + payload


@pytest.mark.parametrize("embedded", [True, False])
def test_cine_noop_growth_and_language_preservation(embedded: bool) -> None:
    original = cine(b"0\r[p1]Hello\r9\rRussian\r", embedded=embedded)
    handler = CineV2Handler()
    entries = handler.extract(original, 0)
    assert entries[0].source == "Hello"
    assert entries[0].comment == ("[p1]",)
    assert handler.write(original, (), TextOptions(0)) == original
    translated = handler.write(original, (TranslationEntry(0, "Hello", "Őű" * 80),), TextOptions(0))
    assert handler.extract(translated, 0)[0].source == "Őű" * 80
    assert handler.extract(translated, 9)[0].source == "Russian"
    assert translated[:8192] == original[:8192]
    assert translated[8200:8208] == original[8200:8208]
    assert len(translated) % 16 == 0


def test_cine_russian_source_routing_and_prefix() -> None:
    original = cine("0\r[c4]speaking Russian\r9\r[c4]Привет\r".encode(), embedded=True)
    handler = CineV2Handler()
    entry = handler.extract(original, 0)[0]
    assert entry.source == "Привет"
    assert entry.source_language == "ru"
    assert entry.comment == ("[c4]",)
    translated = handler.write(original, (TranslationEntry(0, "Привет", "Helló!"),), TextOptions(0))
    assert b"[c4]Hell\xc3\xb3!" in translated
    assert handler.extract(translated, 9)[0].source == "Привет"


def test_cine_rejects_truncated_block_and_delimiter_in_translation() -> None:
    handler = CineV2Handler()
    original = cine(b"0\rHello\r", embedded=True)
    with pytest.raises(ValueError, match="bounds"):
        handler.extract(original[:-1], 0)
    with pytest.raises(ValueError, match="delimiter"):
        handler.write(original, (TranslationEntry(0, "Hello", "bad\rtext"),), TextOptions(0))


def test_cine_block_and_occurrence_identity_preserves_opaque_blocks() -> None:
    binary = struct.pack("<4I", 0, 16, 0x12345678, 0xABCDEF01) + b"opaque binary!!!"
    suffix = struct.pack("<4I", 3, 16, 7, 9) + bytes(range(16))
    text = cine(b"0\rOne\r0\rTwo\r9\rRussian\r", embedded=True)[8192:]
    original = bytes(8192) + binary + text + suffix
    handler = CineV2Handler()
    entries = handler.extract(original, 0)
    assert [(e.entry_id, e.source) for e in entries] == [(0x10000, "One"), (0x10001, "Two")]
    rebuilt = handler.write(
        original, (TranslationEntry(0x10001, "Two", "Kettő" * 40),), TextOptions(0)
    )
    assert rebuilt[8192 : 8192 + len(binary)] == binary
    assert rebuilt[-len(suffix) :] == suffix
    assert handler.extract(rebuilt, 0)[0].source == "One"
    assert handler.extract(rebuilt, 0)[1].source == "Kettő" * 40


def test_sch_occurrences_not_timestamps_are_ids_and_round_trip_preserves_other_lines() -> None:
    original = (
        b"Version 1\r\nTextEntry\r\nline0\r\n"
        b'lang_english 2012-12-12 17:15:53 "(1.0)[p]Hello\\(1.0)Hello"  \r\n'
        b'lang_russian 2012-12-12 17:15:53 "Russian"\r\n'
    )
    handler = SchV1Handler()
    entries = handler.extract(original, 0)
    assert [(e.entry_id, e.source) for e in entries] == [(0, "Hello"), (1, "Hello")]
    assert [e.comment for e in entries] == [("(1.0)[p]",), ("(1.0)",)]
    assert handler.write(original, (), TextOptions(0)) == original
    translated = handler.write(
        original, (TranslationEntry(1, "Hello", "Hosszú Őű"),), TextOptions(0)
    )
    assert b'(1.0)[p]Hello\\(1.0)Hossz\xc3\xba \xc5\x90\xc5\xb1"  \r\n' in translated
    assert translated.splitlines()[-1] == original.splitlines()[-1]
    with pytest.raises(ValueError, match="language"):
        handler.extract(original, 9)


def test_sch_extracts_and_writes_french_language_slot() -> None:
    original = (
        b"Version 1\r\nTextEntry\r\nline0\r\n"
        b'lang_english 1 "Hello"\r\n'
        b'lang_french 1 "(1.0)[p]Bonjour\\(2.0)Monde"\r\n'
    )
    handler = SchV1Handler()

    entries = handler.extract(original, 1)

    assert [(entry.entry_id, entry.source) for entry in entries] == [
        (0, "Bonjour"),
        (1, "Monde"),
    ]
    translated = handler.write(
        original,
        (TranslationEntry(1, "Monde", "Világ"),),
        TextOptions(1),
    )
    assert b'lang_english 1 "Hello"\r\n' in translated
    assert b'lang_french 1 "(1.0)[p]Bonjour\\(2.0)Vil\xc3\xa1g"\r\n' in translated


def test_menu_preserves_placeholders_aliases_and_unknown_tail() -> None:
    original = struct.pack("<3I4I", 0, 1, 3, 0xFFFFFFFF, 28, 28, 0) + b"Hello\0tail"
    handler = LocalsV2Handler()
    assert [(e.entry_id, e.source) for e in handler.extract(original, 0)] == [
        (1, "Hello"),
        (2, "Hello"),
    ]
    assert handler.write(original, (), TextOptions(0)) == original
    translated = handler.write(original, (TranslationEntry(1, "Hello", "Őű" * 40),), TextOptions(0))
    assert handler.extract(translated, 0)[0].source == "Őű" * 40
    assert handler.extract(translated, 0)[1].source == "Hello"
    assert translated[28:38] == original[28:38]
    assert struct.unpack_from("<I", translated, 12)[0] == 0xFFFFFFFF


def test_sch_rejects_unencodable_structure_changes() -> None:
    original = b'Version 1\r\nTextEntry\r\nline0\r\nlang_english 1 "Hello"\r\n'
    with pytest.raises(ValueError, match="delimiter"):
        SchV1Handler().write(original, (TranslationEntry(0, "Hello", "bad\\text"),), TextOptions(0))


def test_sch_preserves_embedded_quotes_as_used_by_real_sources() -> None:
    original = b'Version 1\r\nTextEntry\r\nline0\r\nlang_english 1 "Say "hello""\r\n'
    handler = SchV1Handler()
    assert handler.extract(original, 0)[0].source == 'Say "hello"'
    rebuilt = handler.write(
        original, (TranslationEntry(0, 'Say "hello"', 'Mondd: "helló"'),), TextOptions(0)
    )
    assert handler.extract(rebuilt, 0)[0].source == 'Mondd: "helló"'
