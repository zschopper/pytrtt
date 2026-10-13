"""Shared extraction, planning, application and restoration workflows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from pytrtt.archives.contracts import (
    ArchiveHandler,
    ArchiveResource,
    ArchiveWritePlan,
    ResourceReplacement,
)
from pytrtt.config import RuntimeSettings, parse_runtime_settings
from pytrtt.formats.contracts import TextOptions
from pytrtt.packages.translation import (
    FontAsset,
    TranslationDocument,
    TranslationMetadata,
    TranslationPackageError,
    TranslationResource,
)
from pytrtt.registry import HandlerResolver, default_registry


@dataclass(frozen=True, slots=True)
class MissingTranslation:
    section: str
    resource_hash: str
    entry_id: int
    source: str


@dataclass(frozen=True, slots=True)
class TranslationBuild:
    handler: ArchiveHandler
    runtime: RuntimeSettings
    plan: ArchiveWritePlan | None
    missing_translations: tuple[MissingTranslation, ...]


@dataclass(frozen=True, slots=True)
class RecoveryAsset:
    name_hash: int
    locale: int
    path: str
    data: bytes


@dataclass(frozen=True, slots=True)
class SkippedResource:
    name_hash: int
    path: str
    reason: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    document: TranslationDocument
    skipped_resources: tuple[SkippedResource, ...]
    empty_resources: int
    recovery_assets: tuple[RecoveryAsset, ...]


def _find(resources: tuple[ArchiveResource, ...], name_hash: int, locale: int) -> ArchiveResource:
    matches = [r for r in resources if r.name_hash == name_hash and r.locale == locale]
    if len(matches) != 1:
        raise TranslationPackageError(
            f"expected one resource {name_hash:08X} in locale {locale:08X}; found {len(matches)}"
        )
    return matches[0]


def parse_filelist(content: str) -> dict[int, str]:
    names: dict[int, str] = {}
    for number, line in enumerate(content.removeprefix("\ufeff").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        hash_text, sep, path = line.partition("\t")
        if not sep or len(hash_text) != 8 or not path.strip():
            raise TranslationPackageError(f"invalid filelist row at line {number}")
        try:
            name_hash = int(hash_text, 16)
        except ValueError as exc:
            raise TranslationPackageError(f"invalid file hash at line {number}") from exc
        if name_hash in names and names[name_hash] != path:
            raise TranslationPackageError(f"file hash {name_hash:08X} maps to multiple paths")
        names[name_hash] = path
    return names


def _runtime(document: TranslationDocument) -> RuntimeSettings:
    settings = document.runtime
    if settings is None:
        raise TranslationPackageError(
            "missing runtime settings; compile this legacy document first"
        )
    metadata = document.metadata
    if (metadata.archive_format, metadata.archive_version) != (
        settings.archive.format,
        settings.archive.version,
    ):
        raise TranslationPackageError("runtime archive format does not match metadata")
    settings.language(metadata.source_language)
    return settings


def _font_bytes(font: FontAsset, package_dir: Path) -> bytes:
    relative = PurePosixPath(font.replacement_file)
    if (
        "\\" in font.replacement_file
        or relative.is_absolute()
        or PureWindowsPath(font.replacement_file).drive
        or ".." in relative.parts
    ):
        raise TranslationPackageError("replacement font path is unsafe")
    root = package_dir.resolve(strict=True)
    path = root.joinpath(*relative.parts).resolve(strict=True)
    if root not in path.parents or not path.is_file():
        raise TranslationPackageError("replacement font is outside the translation package")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != font.replacement_sha256:
        raise TranslationPackageError(f"replacement font hash mismatch for {font.resource_hash}")
    return data


class TranslationService:
    """No printing, UI state, game names or developer profiles enter this service."""

    def __init__(self, registry: HandlerResolver | None = None) -> None:
        # Keep no-argument construction compatible; clients wire dependencies explicitly.
        self.registry: HandlerResolver = registry if registry is not None else default_registry()

    def _open(self, directory: Path, runtime: RuntimeSettings) -> ArchiveHandler:
        # Resolve every declared handler before reading files or planning mutations.
        for rule in runtime.resource_types:
            self.registry.text_format(rule.format, rule.version)
        return self.registry.archive(directory, runtime.archive)

    def extract(
        self,
        directory: Path,
        metadata: TranslationMetadata,
        runtime: RuntimeSettings,
        names: Mapping[int, str],
    ) -> ExtractionResult:
        template = TranslationDocument(metadata, runtime=runtime)
        _runtime(template)
        source = runtime.language(metadata.source_language)
        archive = self._open(directory, runtime)
        resources = archive.resources()
        sections: dict[str, list[TranslationResource]] = {"menu": [], "subtitles": []}
        assets = []
        skipped = []
        empty = 0
        seen: set[tuple[int, int]] = set()
        for resource in resources:
            path = names.get(resource.name_hash)
            if path is None:
                continue
            rule = runtime.rule(path)
            if rule is None:
                continue
            locale = rule.locale if rule.locale is not None else source.archive_locale
            if resource.locale != locale:
                continue
            key = (resource.name_hash, resource.locale)
            if key in seen:
                raise TranslationPackageError(
                    "multiple archive resources have the same hash and locale"
                )
            seen.add(key)
            data = archive.read(resource)
            handler = self.registry.text_format(rule.format, rule.version)
            if rule.section == "fonts":
                assets.append(RecoveryAsset(resource.name_hash, resource.locale, path, data))
                continue
            try:
                entries = handler.extract(data, source.subtitle_language)
            except ValueError as exc:
                if not rule.skip_unrecognized:
                    raise TranslationPackageError(f"cannot extract {path}: {exc}") from exc
                skipped.append(SkippedResource(resource.name_hash, path, str(exc)))
                continue
            if not entries:
                empty += 1
                continue
            sections[rule.section].append(
                TranslationResource(f"{resource.name_hash:08X}", path, entries)
            )
        document = TranslationDocument(
            metadata,
            menu=tuple(sections["menu"]),
            subtitles=tuple(sections["subtitles"]),
            runtime=runtime,
        )
        return ExtractionResult(document, tuple(skipped), empty, tuple(assets))

    def plan(
        self,
        directory: Path,
        document: TranslationDocument,
        *,
        package_dir: Path,
        expected_build_id: str | None = None,
    ) -> TranslationBuild:
        runtime = _runtime(document)
        if expected_build_id is not None and document.metadata.build_id != expected_build_id:
            raise TranslationPackageError("translation document targets a different game build")
        source = runtime.language(document.metadata.source_language)
        target = runtime.language(runtime.replacement_language)
        if target.subtitle_language in (
            document.clear_subtitle_languages | document.omit_subtitle_languages
        ):
            raise TranslationPackageError("cannot clear or omit the replacement language")
        archive = self._open(directory, runtime)
        indexed = archive.resources()
        replacements = []
        missing = []
        used: set[tuple[int, int]] = set()
        options = TextOptions(
            target.subtitle_language,
            runtime.character_substitutions,
            document.clear_subtitle_languages,
            document.omit_subtitle_languages,
        )
        for section, resources in (("menu", document.menu), ("subtitles", document.subtitles)):
            for resource in resources:
                rule = runtime.rule(resource.resource_path, section)
                if rule is None:
                    raise TranslationPackageError(f"no resource rule for {resource.resource_path}")
                handler = self.registry.text_format(rule.format, rule.version)
                name_hash = int(resource.resource_hash, 16)
                source_locale = rule.locale if rule.locale is not None else source.archive_locale
                target_locale = rule.locale if rule.locale is not None else target.archive_locale
                source_ref = _find(indexed, name_hash, source_locale)
                target_ref = _find(indexed, name_hash, target_locale)
                key = (name_hash, target_locale)
                if key in used:
                    raise TranslationPackageError("duplicate translation resource")
                used.add(key)
                source_data = archive.read(source_ref)
                source_entries = handler.extract(source_data, source.subtitle_language)
                records = {e.entry_id: e for e in resource.entries}
                if len(records) != len(resource.entries):
                    raise TranslationPackageError("duplicate translation entry id")
                known = {e.entry_id for e in source_entries}
                if records.keys() - known:
                    raise TranslationPackageError("translation entry has no source record")
                for entry in source_entries:
                    translated = records.get(entry.entry_id)
                    if translated is not None and translated.source != entry.source:
                        raise TranslationPackageError(
                            f"source text changed for entry id {entry.entry_id}"
                        )
                    if translated is None or translated.translation is None:
                        missing.append(
                            MissingTranslation(
                                section, resource.resource_hash, entry.entry_id, entry.source
                            )
                        )
                original = source_data if source_ref == target_ref else archive.read(target_ref)
                target_entries = handler.extract(original, target.subtitle_language)
                target_ids = {entry.entry_id for entry in target_entries}
                if any(
                    e.translation is not None and e.entry_id not in target_ids
                    for e in resource.entries
                ):
                    raise TranslationPackageError(
                        "translation entry has no replacement-slot record"
                    )
                data = handler.write(original, resource.entries, options)
                if data != original:
                    label = (
                        ("Menu" if section == "menu" else "Subtitle") + " " + resource.resource_hash
                    )
                    replacements.append(ResourceReplacement(label, name_hash, target_locale, data))
        for font in document.fonts:
            rule = runtime.rule(font.resource_path, "fonts")
            if rule is None:
                raise TranslationPackageError(f"no font resource rule for {font.resource_path}")
            locale = rule.locale if rule.locale is not None else target.archive_locale
            name_hash = int(font.resource_hash, 16)
            reference = _find(indexed, name_hash, locale)
            original = archive.read(reference)
            if hashlib.sha256(original).hexdigest() != font.source_sha256:
                raise TranslationPackageError(
                    f"original font hash mismatch for {font.resource_hash}"
                )
            data = _font_bytes(font, package_dir)
            if data != original:
                replacements.append(
                    ResourceReplacement(
                        f"Font {font.resource_hash}",
                        name_hash,
                        locale,
                        data,
                        restore_file=f"fonts/{name_hash:08X}-{locale:08X}.raw",
                    )
                )
        plan = archive.plan(tuple(replacements)) if replacements else None
        return TranslationBuild(archive, runtime, plan, tuple(missing))

    def apply(self, result: TranslationBuild, transaction_dir: Path) -> Path | None:
        return (
            result.handler.apply(result.plan, transaction_dir, result.runtime)
            if result.plan is not None
            else None
        )

    def restore(
        self, directory: Path, transaction_dir: Path, runtime: RuntimeSettings | None = None
    ) -> None:
        if runtime is None:
            journal = json.loads((transaction_dir / "journal.json").read_text(encoding="utf-8"))
            if "runtime" not in journal:
                raise TranslationPackageError("legacy journal requires explicit runtime settings")
            runtime = parse_runtime_settings(journal["runtime"])
        self.registry.archive(directory, runtime.archive).restore(transaction_dir)
