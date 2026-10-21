"""DRM v22 nested-resource placement for TAFS v4 archives."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, replace
from pathlib import Path

from pytrtt.archives.contracts import PlannedFile, PlannedWrite, ResourceReplacement
from pytrtt.archives.drm_v22 import align, decode_cdrm, encode_cdrm
from pytrtt.archives.tiger_v4 import (
    TigerV4Handler,
    TigerV4Index,
    TigerV4WritePlan,
    read_tiger_v4_index,
)


@dataclass(frozen=True, slots=True)
class Reference:
    body_position: int
    location_position: int
    kind: int
    resource_id: int
    body_size: int
    references_size: int
    archive_id: int
    part: int
    offset: int
    packed_size: int
    virtual_offset: int


@dataclass(frozen=True, slots=True)
class Collection:
    family: str
    name_hash: int
    locale: int
    data: bytes
    references: tuple[Reference, ...]


def _indexes(archive: TigerV4Handler) -> dict[str, tuple[Path, TigerV4Index]]:
    result: dict[str, tuple[Path, TigerV4Index]] = {}
    for family, name in archive.settings.index_files:
        path = archive.directory / name
        with path.open("rb") as stream:
            result[family] = (path, read_tiger_v4_index(stream))
    return result


def _collections(archive: TigerV4Handler, hashes: set[tuple[int, int]] | None) -> list[Collection]:
    archive._load()
    result = []
    for (family, name_hash, locale), (name, entry, _) in archive._physical.items():
        if (hashes is not None and (name_hash, locale) not in hashes) or entry.size < 32:
            continue
        with (archive.directory / name).open("rb") as stream:
            stream.seek(entry.offset)
            raw = stream.read(entry.size)
        data = decode_cdrm(raw) if raw[:4] == b"CDRM" else raw
        if len(data) < 32 or struct.unpack_from("<I", data)[0] != 22:
            continue
        header = struct.unpack_from("<8I", data)
        count = header[6]
        location_base = 32 + count * 20 + header[1] + header[2]
        if count > 100000 or location_base + count * 24 > len(data):
            raise ValueError("DRM v22 table exceeds bounds")
        references = []
        for i in range(count):
            body_position = 32 + i * 20
            location_position = location_base + i * 24
            body, kind, _, _, flags, resource_id, _ = struct.unpack_from(
                "<IBBHIII", data, body_position
            )
            _, _, part, archive_id, offset, packed, decoded = struct.unpack_from(
                "<IIhhIII", data, location_position
            )
            if min(part, archive_id) < 0 or min(offset, packed, decoded) < 0:
                raise ValueError("invalid DRM v22 location")
            references.append(
                Reference(
                    body_position,
                    location_position,
                    kind,
                    resource_id,
                    body,
                    flags >> 8,
                    archive_id,
                    part,
                    offset,
                    packed,
                    decoded,
                )
            )
        result.append(Collection(family, name_hash, locale, data, tuple(references)))
    return result


def _resolve(archive: TigerV4Handler, ref: Reference) -> tuple[str, bytes, bytes]:
    matches = []
    for _, (path, index) in _indexes(archive).items():
        if index.archive_id != ref.archive_id or ref.part >= index.num_parts:
            continue
        name = path.name[:-9] + f"{ref.part:03}.tiger"
        part = archive.directory / name
        if ref.offset + ref.packed_size > part.stat().st_size:
            continue
        with part.open("rb") as stream:
            stream.seek(ref.offset)
            raw = stream.read(ref.packed_size)
        if raw[:4] != b"CDRM":
            continue
        decoded = decode_cdrm(raw)
        if len(decoded) == ref.body_size + ref.references_size:
            matches.append((name, raw, decoded))
    if len(matches) != 1:
        raise ValueError("missing or ambiguous embedded resource location")
    return matches[0]


def _references(
    collections: list[Collection],
    name_hash: int,
    locale: int,
    kind: int,
    resource_id: int,
    *,
    archive_family: str | None = None,
) -> list[Reference]:
    result = [
        ref
        for collection in collections
        if (collection.name_hash, collection.locale) == (name_hash, locale)
        and (archive_family is None or collection.family == archive_family)
        for ref in collection.references
        if (ref.kind, ref.resource_id) == (kind, resource_id)
    ]
    if not result:
        raise ValueError("embedded font not found in collection")
    if any(ref.references_size for ref in result):
        raise ValueError("embedded fonts with reference definitions are unsupported")
    return result


def read_embedded(
    archive: TigerV4Handler,
    name_hash: int,
    locale: int,
    kind: int,
    resource_id: int,
    *,
    archive_family: str | None = None,
) -> bytes:
    items = _collections(archive, {(name_hash, locale)})
    refs = _references(items, name_hash, locale, kind, resource_id, archive_family=archive_family)
    values = {_resolve(archive, ref)[2] for ref in refs}
    if len(values) != 1:
        raise ValueError("embedded font layers contain different source data")
    return values.pop()


@dataclass(slots=True)
class Payload:
    name: str
    original: bytes
    data: bytes
    packed: bytes
    archive_id: int
    part: int
    offset: int = 0
    virtual_offset: int = 0


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def plan_embedded(
    archive: TigerV4Handler, requests: tuple[ResourceReplacement, ...]
) -> TigerV4WritePlan:
    embedded = [request for request in requests if request.embedded_type is not None]
    direct = [request for request in requests if request.embedded_type is None]
    items = _collections(archive, {(r.name_hash, r.locale) for r in embedded})
    virtuals: dict[tuple[int, int], int] = {}
    for collection in _collections(archive, None):
        for ref in collection.references:
            key = ref.archive_id, ref.part
            virtuals[key] = max(
                virtuals.get(key, 0),
                align(ref.virtual_offset + ref.body_size + ref.references_size),
            )
    payloads: dict[tuple[int, int, int], Payload] = {}
    for request in embedded:
        kind = request.embedded_type
        if kind is None or request.embedded_id is None or not request.data:
            raise ValueError("invalid embedded resource replacement")
        refs = _references(
            items,
            request.name_hash,
            request.locale,
            kind,
            request.embedded_id,
            archive_family=request.archive_family,
        )
        for ref in refs:
            address = ref.archive_id, ref.part, ref.offset
            name, raw, original = _resolve(archive, ref)
            previous = payloads.get(address)
            if previous is not None and previous.data != request.data:
                raise ValueError("conflicting embedded resource replacements")
            payloads[address] = Payload(
                name,
                original,
                request.data,
                encode_cdrm(request.data, raw),
                ref.archive_id,
                ref.part,
            )

    affected = [
        collection
        for collection in items
        if any((ref.archive_id, ref.part, ref.offset) in payloads for ref in collection.references)
    ]
    affected_keys = {(c.family, c.name_hash, c.locale) for c in affected}
    if any((r.archive_family, r.name_hash, r.locale) in affected_keys for r in direct):
        raise ValueError("collection and embedded resource replacements conflict")
    placeholders = [
        ResourceReplacement(
            "Font collection", c.name_hash, c.locale, c.data, archive_family=c.family
        )
        for c in affected
    ]
    preliminary = archive.plan(tuple(direct + placeholders))
    cursors: dict[str, int] = {}
    for payload in payloads.values():
        start = (
            preliminary.files[payload.name].final_size
            if payload.name in preliminary.files
            else (archive.directory / payload.name).stat().st_size
        )
        payload.offset = align(cursors.get(payload.name, start), 2048)
        cursors[payload.name] = payload.offset + align(align(len(payload.packed)) + 16, 2048)
        if cursors[payload.name] > archive.settings.boundary:
            raise ValueError("embedded font exceeds existing TIGER part boundary")
        key = payload.archive_id, payload.part
        payload.virtual_offset = virtuals.get(key, 0)
        virtuals[key] = align(payload.virtual_offset + len(payload.data))
        if virtuals[key] > 0xFFFFFFFF:
            raise ValueError("embedded font virtual range overflow")

    rebuilt = []
    for collection in affected:
        data = bytearray(collection.data)
        for ref in collection.references:
            selected_payload = payloads.get((ref.archive_id, ref.part, ref.offset))
            if selected_payload is None:
                continue
            if ref.body_size != len(selected_payload.original):
                raise ValueError("inconsistent aliased embedded resource")
            struct.pack_into("<I", data, ref.body_position, len(selected_payload.data))
            struct.pack_into(
                "<hhIII",
                data,
                ref.location_position + 8,
                selected_payload.part,
                selected_payload.archive_id,
                selected_payload.offset,
                len(selected_payload.packed),
                selected_payload.virtual_offset,
            )
        rebuilt.append(
            ResourceReplacement(
                "Font collection",
                collection.name_hash,
                collection.locale,
                bytes(data),
                archive_family=collection.family,
            )
        )
    plan = archive.plan(tuple(direct + rebuilt))
    writes = list(plan.writes)
    files = dict(plan.files)
    recovery = 0
    grouped: dict[str, list[Payload]] = {}
    for payload in payloads.values():
        grouped.setdefault(payload.name, []).append(payload)
    for name, group in grouped.items():
        group.sort(key=lambda payload: payload.offset)
        for i, payload in enumerate(group):
            marker = payload.offset + align(len(payload.packed))
            following = group[i + 1].offset if i + 1 < len(group) else None
            distance = following - marker if following is not None else 0
            blob = payload.packed + bytes(align(len(payload.packed)) - len(payload.packed))
            blob += b"NEXT" + struct.pack("<I", distance) + bytes(8)
            blob += bytes(align(len(blob), 2048) - len(blob))
            writes.append(
                PlannedWrite(
                    name,
                    "resource",
                    "Embedded font",
                    payload.offset,
                    blob,
                    b"",
                    resource_original=payload.original,
                    restore_file=f"fonts/embedded-{payload.archive_id}-{payload.part}-{i}.bin",
                )
            )
            recovery += len(payload.original)
        end = cursors[name]
        if name in files:
            files[name] = replace(files[name], final_size=end)
        else:
            path = archive.directory / name
            files[name] = PlannedFile(path.stat().st_size, end, _digest(path))
    backup = plan.backup_bytes + recovery
    return replace(
        plan,
        writes=tuple(writes),
        files=files,
        backup_bytes=backup,
        additional_bytes_required=backup + 2 * sum(f.final_size for f in files.values()),
    )
