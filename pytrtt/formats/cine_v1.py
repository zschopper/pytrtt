"""Reader and writer for indexed CINE subtitle resources."""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass

CINE_HEADER_SIZE = 0x800
BLOCK_HEADER_SIZE = 0x10
MAX_BLOCK_SIZE = 0x20000
MAX_TEXT_SIZE = 1000
ENIC_MAGIC = 0x43494E45


class CineFormatError(ValueError):
    """Raised when a CINE resource or its subtitle records are malformed."""


@dataclass(frozen=True, slots=True)
class CineBlock:
    """One aligned CINE block, retaining its unknown header and payload bytes."""

    block_type: int
    is_enic: bool
    payload: bytes
    subtitle_pairs: tuple[tuple[int, str], ...]
    has_subtitles: bool
    original_block: bytes


@dataclass(frozen=True, slots=True)
class CineResource:
    """A CINE resource with the original header and exact no-op representation."""

    header: bytes
    blocks: tuple[CineBlock, ...]
    original_data: bytes


def _parse_pairs(raw: bytes) -> tuple[tuple[int, str], ...]:
    if len(raw) < 5 or raw[-1] != 0x0D:
        raise CineFormatError("subtitle payload is missing its final CR delimiter")
    try:
        fields = raw[:-1].decode("utf-8").split("\r")
    except UnicodeDecodeError as exc:
        raise CineFormatError("subtitle payload is not valid UTF-8") from exc
    if len(fields) % 2:
        raise CineFormatError("subtitle payload has an unmatched language or text field")
    pairs: list[tuple[int, str]] = []
    for index in range(0, len(fields), 2):
        try:
            language = int(fields[index], 10)
        except ValueError as exc:
            raise CineFormatError("subtitle language code is not decimal") from exc
        if not 0 <= language <= 0xFF:
            raise CineFormatError("subtitle language code is outside the byte range")
        pairs.append((language, fields[index + 1]))
    if not pairs:
        raise CineFormatError("subtitle payload contains no language records")
    return tuple(pairs)


def _find_subtitle(
    block: bytes, content_offset: int, content_size: int, enabled: bool
) -> tuple[int, tuple[tuple[int, str], ...]]:
    if not enabled:
        return content_size, ()
    last = len(block) - 1
    while last >= 7 and block[last] == 0:
        last -= 1
    if last < 7 or block[last] != 0x0D:
        return content_size, ()
    low = content_offset + 4
    for last_length_byte in range(last - 3, low - 1, -1):
        if block[last_length_byte] != 0:
            continue
        length_offset = last_length_byte - 3
        size = struct.unpack_from("<I", block, length_offset)[0]
        if size != last - last_length_byte:
            continue
        if size > MAX_BLOCK_SIZE:
            continue
        raw = block[length_offset + 4 : last + 1]
        try:
            pairs = _parse_pairs(raw)
        except CineFormatError:
            continue
        return length_offset - content_offset, pairs
    return content_size, ()


def parse_cine(
    data: bytes,
    *,
    opaque_block_types: frozenset[int] = frozenset(),
    max_block_size: int = MAX_BLOCK_SIZE,
) -> CineResource:
    """Read aligned blocks and their CR-delimited language/text pairs."""
    if len(data) <= CINE_HEADER_SIZE:
        raise CineFormatError("CINE resource is shorter than its header and one block")
    header = data[:CINE_HEADER_SIZE]
    blocks: list[CineBlock] = []
    offset = CINE_HEADER_SIZE
    while offset < len(data):
        if len(data) - offset < BLOCK_HEADER_SIZE:
            raise CineFormatError("truncated CINE block header")
        block_type, virtual_payload_size = struct.unpack_from("<II", data, offset)
        if block_type not in (0, 1) and block_type not in opaque_block_types:
            raise CineFormatError(f"unsupported CINE block type {block_type}")
        block_size = BLOCK_HEADER_SIZE + virtual_payload_size
        if block_size > max_block_size or block_size % 16:
            raise CineFormatError("CINE block virtual size is invalid")
        end = offset + block_size
        if end > len(data):
            raise CineFormatError("CINE block extends beyond resource")
        block = data[offset:end]
        if block_type in opaque_block_types:
            blocks.append(CineBlock(block_type, False, block[16:], (), False, block))
            offset = end
            continue
        if block_type == 1:
            if len(block) < 0x14:
                raise CineFormatError("type 1 CINE block is shorter than its size field")
            first_payload_word = struct.unpack_from("<I", block, 0x10)[0]
            is_enic = first_payload_word == ENIC_MAGIC
            content_size = virtual_payload_size if is_enic else first_payload_word
            content_offset = 0x10 if is_enic else 0x14
            if not is_enic and content_size > virtual_payload_size:
                raise CineFormatError("CINE block content size exceeds virtual size")
        else:
            content_size = virtual_payload_size
            content_offset = 0x10
        is_enic = len(block) >= 0x14 and block[0x10:0x14] == b"ENIC"
        # Type 0 and ENIC payloads include the full virtual body; regular type 1
        # payloads carry a precise size in the header.
        if block_type == 0 or is_enic:
            content_size = virtual_payload_size
        enabled = block_type == 1 or is_enic
        text_offset, pairs = _find_subtitle(block, content_offset, content_size, enabled)
        payload = block[content_offset : content_offset + text_offset]
        blocks.append(CineBlock(block_type, is_enic, payload, pairs, bool(pairs), block))
        offset = end
    if offset != len(data) or not blocks:
        raise CineFormatError("CINE resource has an invalid block sequence")
    return CineResource(header, tuple(blocks), data)


def _serialize_block(
    block: CineBlock, pairs: tuple[tuple[int, str], ...], *, preserve_payload_padding: bool = False
) -> bytes:
    if pairs == block.subtitle_pairs:
        return block.original_block
    header_size = BLOCK_HEADER_SIZE + (4 if block.block_type == 1 and not block.is_enic else 0)
    content = bytearray(block.payload)
    if pairs:
        # For legacy non-ENIC blocks, retain binary bytes but discard only the
        # zero padding before the subtitle length word; align that word to 4 bytes.
        if header_size == 0x14 and not preserve_payload_padding:
            while content and content[-1] == 0:
                content.pop()
            desired = (-((header_size + len(content)) % 4)) % 4
            content.extend(bytes(desired))
        raw = "".join(f"{language}\r{text}\r" for language, text in pairs).encode("utf-8")
        content.extend(struct.pack("<I", len(raw)))
        content.extend(raw)
    virtual_block_size = (header_size + len(content) + 15) & ~15
    if virtual_block_size > MAX_BLOCK_SIZE:
        raise CineFormatError("rebuilt CINE block exceeds maximum block size")
    content.extend(bytes(virtual_block_size - header_size - len(content)))
    result = bytearray(block.original_block[:header_size])
    result.extend(content)
    struct.pack_into("<II", result, 0, block.block_type, virtual_block_size - BLOCK_HEADER_SIZE)
    if header_size == 0x14:
        struct.pack_into("<I", result, 0x10, len(content))
    return bytes(result)


def apply_cine_translations(
    resource: CineResource,
    translations: Mapping[int, str],
    *,
    cleared_languages: frozenset[int] = frozenset(),
    omitted_languages: frozenset[int] = frozenset(),
    subtitle_language: int = 0,
    substitutions: Mapping[str, str] | None = None,
    preserve_payload_padding: bool = False,
) -> bytes:
    """Apply selected-language text, retaining, blanking, or omitting other language records."""
    if any(not 0 <= index < len(resource.blocks) for index in translations):
        raise CineFormatError("translation block index is outside the resource")
    if any("\0" in text or "\r" in text for text in translations.values()):
        raise CineFormatError("translation contains a null or CR delimiter")
    if not 0 <= subtitle_language <= 255:
        raise CineFormatError("selected subtitle language is outside the byte range")
    language_sets = cleared_languages | omitted_languages
    if subtitle_language in language_sets:
        raise CineFormatError("cannot clear or omit the replacement language")
    if any(not 0 <= language <= 0xFF for language in language_sets):
        raise CineFormatError("language code is outside the byte range")
    if cleared_languages & omitted_languages:
        raise CineFormatError("a language cannot be both cleared and omitted")
    for index in translations:
        if not any(
            language == subtitle_language for language, _ in resource.blocks[index].subtitle_pairs
        ):
            raise CineFormatError(f"translation block {index} has no selected language record")
    output = bytearray(resource.header)
    changed = False
    for index, block in enumerate(resource.blocks):
        pairs = list(block.subtitle_pairs)
        if pairs:
            if index in translations:
                pairs.sort(key=lambda pair: pair[0] != subtitle_language)
            rebuilt_pairs: list[tuple[int, str]] = []
            for language, text in pairs:
                if language in omitted_languages:
                    continue
                if language in cleared_languages:
                    rebuilt_pairs.append((language, " "))
                elif language == subtitle_language and index in translations:
                    translated_text = translations[index] or " "
                    rebuilt_pairs.append(
                        (
                            language,
                            translated_text.translate(
                                {
                                    ord(source): target
                                    for source, target in (substitutions or {}).items()
                                }
                            ),
                        )
                    )
                else:
                    rebuilt_pairs.append((language, text))
            new_pairs = tuple(rebuilt_pairs)
            block_data = _serialize_block(
                block, new_pairs, preserve_payload_padding=preserve_payload_padding
            )
            changed |= block_data != block.original_block
        else:
            block_data = block.original_block
        output.extend(block_data)
    return bytes(output) if changed else resource.original_data
