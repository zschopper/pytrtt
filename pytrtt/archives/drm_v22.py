"""DRM v22 nested font placement for TAFS v3 archives.

Independent layout implementation. Reference: TrRebootModTools
 a79c48b75f1ffaaf623dc73a625211bf98ff0504, Archive.AddResource and
 ModInstaller.AddResourcesToArchive. Only reference-free resource bodies are replaced.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from pytrtt.archives.contracts import PlannedFile, PlannedWrite, ResourceReplacement

if TYPE_CHECKING:
    from pytrtt.archives.tiger_v3 import TigerV3Handler, TigerV3WritePlan


def align(value: int, size: int = 16) -> int:
    return (value + size - 1) & ~(size - 1)


def decode_cdrm(raw: bytes) -> bytes:
    if len(raw) < 16 or raw[:4] != b"CDRM":
        raise ValueError("invalid CDRM header")
    count = struct.unpack_from("<I", raw, 8)[0]
    if not 1 <= count <= 16384 or 16 + count * 8 > len(raw):
        raise ValueError("invalid CDRM chunk table")
    cursor = align(16 + count * 8)
    result = bytearray()
    for i in range(count):
        flags, packed = struct.unpack_from("<II", raw, 16 + i * 8)
        size, kind = flags >> 8, flags & 255
        if size > 0x40000 or not size or cursor + packed > len(raw):
            raise ValueError("CDRM chunk exceeds bounds")
        data = raw[cursor : cursor + packed]
        if kind == 1 and packed == size:
            decoded = data
        elif kind == 2:
            inflater = zlib.decompressobj()
            try:
                decoded = inflater.decompress(data, size + 1)
            except zlib.error as exc:
                raise ValueError("invalid CDRM compressed chunk") from exc
            if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
                raise ValueError("invalid CDRM compressed chunk")
        else:
            raise ValueError("unsupported CDRM compression flags")
        if len(decoded) != size:
            raise ValueError("CDRM decoded size mismatch")
        result.extend(decoded)
        cursor = align(cursor + packed)
    return bytes(result)


def encode_cdrm(data: bytes, template: bytes) -> bytes:
    if template[:4] != b"CDRM" or len(template) < 16 or not data:
        raise ValueError("invalid CDRM template or empty resource")
    chunks = []
    for pos in range(0, len(data), 0x40000):
        block = data[pos : pos + 0x40000]
        packed = zlib.compress(block, 9)
        kind = 2
        if len(packed) >= len(block):
            packed, kind = block, 1
        chunks.append(((len(block) << 8) | kind, packed))
    out = bytearray(template[:16])
    struct.pack_into("<I", out, 8, len(chunks))
    for flags, packed in chunks:
        out.extend(struct.pack("<II", flags, len(packed)))
    for _, packed in chunks:
        out.extend(bytes(align(len(out)) - len(out)))
        out.extend(packed)
    return bytes(out)


@dataclass(frozen=True)
class Reference:
    body_position: int
    location_position: int
    kind: int
    resource_id: int
    body_size: int
    references_size: int
    packed_offset: int
    packed_size: int
    virtual_offset: int

    @property
    def address(self) -> tuple[int, int, int]:
        return (
            (self.packed_offset >> 4) & 127,
            self.packed_offset & 15,
            self.packed_offset & ~2047,
        )


@dataclass(frozen=True)
class Collection:
    family: str
    name_hash: int
    locale: int
    data: bytes
    references: tuple[Reference, ...]


def collections(
    archive: TigerV3Handler,
    *,
    hashes: set[tuple[int, int]] | None = None,
    addresses: set[tuple[int, int, int]] | None = None,
    virtuals: dict[tuple[int, int], int] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[Collection]:
    result = []
    indexes = archive._indexes()
    total = sum(len(index.entries) for index in indexes.values())
    processed = 0
    interval = max(total // 100, 1)
    if progress is not None:
        progress(0, total)
    for family, index in indexes.items():
        streams = {}
        try:
            for entry in index.entries:
                processed += 1
                if progress is not None and (processed % interval == 0 or processed == total):
                    progress(processed, total)
                if hashes is not None and (entry.name_hash, entry.locale) not in hashes:
                    continue
                if entry.size < 32:
                    continue
                if entry.part not in streams:
                    streams[entry.part] = (
                        archive.directory / f"{family}.{entry.part:03}.tiger"
                    ).open("rb")
                stream = streams[entry.part]
                stream.seek(entry.offset)
                header = stream.read(32)
                if header[:4] == b"CDRM":
                    raise ValueError("embedded placement requires uncompressed indexed collections")
                if header[:4] != b"\x16\0\0\0":
                    continue
                h = struct.unpack("<8I", header)
                count = h[6]
                locbase = 32 + count * 20 + h[1] + h[2]
                if count > 100000 or locbase + count * 16 > entry.size:
                    raise ValueError("DRM v22 table exceeds bounds")
                stream.seek(entry.offset)
                data = stream.read(entry.size)
                if len(data) != entry.size:
                    raise ValueError("truncated DRM collection")
                refs = []
                for i in range(count):
                    bodypos, locpos = 32 + i * 20, locbase + i * 16
                    body, kind, _, _, subrefs, rid, _ = struct.unpack_from(
                        "<IBBHIII", data, bodypos
                    )
                    key, packed, length, virtual = struct.unpack_from("<4I", data, locpos)
                    # Disabled entries remain in the inventory; patch IDs may be adjusted.
                    if virtual + body + (subrefs >> 8) > 0xFFFFFFFF:
                        raise ValueError("DRM virtual range overflow")
                    address = ((packed >> 4) & 127, packed & 15, packed & ~2047)
                    if virtuals is not None:
                        range_key = address[:2]
                        virtuals[range_key] = max(
                            virtuals.get(range_key, 0), align(virtual + body + (subrefs >> 8))
                        )
                    if addresses is not None and address not in addresses:
                        continue
                    refs.append(
                        Reference(
                            bodypos, locpos, kind, rid, body, subrefs >> 8, packed, length, virtual
                        )
                    )
                if refs:
                    result.append(
                        Collection(family, entry.name_hash, entry.locale, data, tuple(refs))
                    )
        finally:
            for stream in streams.values():
                stream.close()
    return result


def resolve(archive: TigerV3Handler, ref: Reference) -> tuple[str, bytes, bytes]:
    priority, part, offset = ref.address
    matches = []
    for family, index in archive._indexes().items():
        if index.priority != priority or part >= index.num_parts:
            continue
        name = f"{family}.{part:03}.tiger"
        path = archive.directory / name
        if offset + ref.packed_size > path.stat().st_size:
            continue
        with path.open("rb") as stream:
            stream.seek(offset)
            raw = stream.read(ref.packed_size)
        if raw[:4] != b"CDRM":
            continue
        decoded = decode_cdrm(raw)
        if len(decoded) == ref.body_size + ref.references_size:
            matches.append((name, raw, decoded))
    if len(matches) != 1:
        raise ValueError("missing or ambiguous embedded resource location")
    return matches[0]


def find_references(
    items: list[Collection],
    name_hash: int,
    locale: int,
    kind: int,
    resource_id: int,
    *,
    archive_family: str | None = None,
) -> list[Reference]:
    refs = [
        r
        for c in items
        if (c.name_hash, c.locale) == (name_hash, locale)
        and (archive_family is None or c.family == archive_family)
        for r in c.references
        if (r.kind, r.resource_id) == (kind, resource_id)
    ]
    if not refs:
        raise ValueError("embedded font not found in collection")
    if any(r.references_size for r in refs):
        raise ValueError("embedded fonts with reference definitions are unsupported")
    return refs


def read_embedded(
    archive: TigerV3Handler,
    name_hash: int,
    locale: int,
    kind: int,
    resource_id: int,
    *,
    archive_family: str | None = None,
) -> bytes:
    refs = find_references(
        collections(archive, hashes={(name_hash, locale)}),
        name_hash,
        locale,
        kind,
        resource_id,
        archive_family=archive_family,
    )
    values = {resolve(archive, r)[2] for r in refs}
    if len(values) != 1:
        raise ValueError("embedded font layers contain different source data")
    return values.pop()


@dataclass
class Payload:
    name: str
    address: tuple[int, int, int]
    original: bytes
    data: bytes
    packed: bytes
    virtual: int = 0
    offset: int = 0


def plan_embedded(
    archive: TigerV3Handler,
    requests: tuple[ResourceReplacement, ...],
    *,
    progress: Callable[[int, int, str], None] | None = None,
) -> TigerV3WritePlan:
    items = collections(
        archive, hashes={(r.name_hash, r.locale) for r in requests if r.embedded_type is not None}
    )
    payloads: dict[tuple[int, int, int], Payload] = {}
    direct = [r for r in requests if r.embedded_type is None]
    for request in requests:
        if request.embedded_type is None:
            continue
        if request.embedded_id is None or not request.data:
            raise ValueError("invalid embedded resource replacement")
        refs = find_references(
            items,
            request.name_hash,
            request.locale,
            request.embedded_type,
            request.embedded_id,
            archive_family=request.archive_family,
        )
        for ref in refs:
            name, raw, original = resolve(archive, ref)
            if ref.address in payloads:
                if payloads[ref.address].data != request.data:
                    raise ValueError("conflicting embedded resource replacements")
                continue
            payloads[ref.address] = Payload(
                name, ref.address, original, request.data, encode_cdrm(request.data, raw)
            )
    virtuals: dict[tuple[int, int], int] = {}
    affected = collections(
        archive,
        addresses=set(payloads),
        virtuals=virtuals,
        progress=(
            (lambda current, total: progress(current, total, "embedded_collection_scan"))
            if progress is not None
            else None
        ),
    )
    if progress is not None:
        progress(0, 0, "archive_layout")
    keys = {(c.family, c.name_hash, c.locale) for c in affected}
    if any((r.archive_family, r.name_hash, r.locale) in keys for r in direct):
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
        name = payload.name
        start = (
            preliminary.files[name].final_size
            if name in preliminary.files
            else (archive.directory / name).stat().st_size
        )
        payload.offset = align(cursors.get(name, start), 2048)
        cursors[name] = payload.offset + align(align(len(payload.packed)) + 16, 2048)
        if cursors[name] > archive.settings.boundary:
            raise ValueError("embedded font exceeds existing TIGER part boundary")
        key = payload.address[:2]
        payload.virtual = virtuals[key]
        virtuals[key] = align(payload.virtual + len(payload.data))
        if virtuals[key] > 0xFFFFFFFF:
            raise ValueError("embedded font virtual range overflow")
    rebuilt = []
    for c in affected:
        data = bytearray(c.data)
        for ref in c.references:
            p = payloads.get(ref.address)
            if p is None:
                continue
            if ref.references_size or ref.body_size != len(p.original):
                raise ValueError("inconsistent aliased embedded resource")
            struct.pack_into("<I", data, ref.body_position, len(p.data))
            location = p.offset | (p.address[0] << 4) | p.address[1]
            struct.pack_into(
                "<III", data, ref.location_position + 4, location, len(p.packed), p.virtual
            )
        rebuilt.append(
            ResourceReplacement(
                "Font collection", c.name_hash, c.locale, bytes(data), archive_family=c.family
            )
        )
    plan = archive.plan(tuple(direct + rebuilt))
    writes = list(plan.writes)
    files = dict(plan.files)
    recovery = 0
    for i, p in enumerate(payloads.values()):
        group = [q for q in payloads.values() if q.name == p.name]
        at = group.index(p)
        following = group[at + 1].offset if at + 1 < len(group) else None
        marker = p.offset + align(len(p.packed))
        distance = following - marker if following is not None else 0
        blob = p.packed + bytes(align(len(p.packed)) - len(p.packed))
        blob += b"NEXT" + struct.pack("<I", distance) + bytes(8)
        blob += bytes(align(len(blob), 2048) - len(blob))
        writes.append(
            PlannedWrite(
                p.name,
                "resource",
                "Embedded font",
                p.offset,
                blob,
                b"",
                resource_original=p.original,
                restore_file=f"fonts/embedded-{i}.bin",
            )
        )
        recovery += len(p.original)
    for name, end in cursors.items():
        if name in files:
            files[name] = replace(files[name], final_size=end)
        else:
            path = archive.directory / name
            with path.open("rb") as stream:
                sha = hashlib.file_digest(stream, "sha256").hexdigest()
            files[name] = PlannedFile(path.stat().st_size, end, sha)
    backup = plan.backup_bytes + recovery
    return replace(
        plan,
        writes=tuple(writes),
        files=files,
        backup_bytes=backup,
        additional_bytes_required=backup + 2 * sum(f.final_size for f in files.values()),
    )
