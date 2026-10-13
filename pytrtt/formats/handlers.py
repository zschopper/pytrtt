"""Versioned resource handlers for locals, CINE, and opaque font assets."""

from __future__ import annotations

from pytrtt.formats.cine_v1 import apply_cine_translations, parse_cine
from pytrtt.formats.contracts import TextFormatHandler, TextOptions
from pytrtt.formats.locals_v1 import parse_locals, write_locals
from pytrtt.packages.translation import TranslationEntry


class LocalsV1Handler(TextFormatHandler):
    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        return tuple(
            TranslationEntry(e.index, e.text, None)
            for e in parse_locals(data).entries
            if e.text is not None
        )

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        return write_locals(
            parse_locals(data),
            {e.entry_id: options.text(e) for e in entries if e.translation is not None},
        )


class CineV1Handler(TextFormatHandler):
    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        result = []
        for index, block in enumerate(parse_cine(data).blocks):
            texts = [
                text for language, text in block.subtitle_pairs if language == subtitle_language
            ]
            if len(texts) > 1:
                raise ValueError(f"multiple subtitle records for block {index}")
            if texts:
                result.append(TranslationEntry(index, texts[0], None))
        return tuple(result)

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        return apply_cine_translations(
            parse_cine(data),
            {e.entry_id: options.text(e) for e in entries if e.translation is not None},
            subtitle_language=options.subtitle_language,
            cleared_languages=options.cleared_languages,
            omitted_languages=options.omitted_languages,
        )


class RawHandler(TextFormatHandler):
    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        return ()

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        if entries:
            raise ValueError("raw assets have no text records")
        return data
