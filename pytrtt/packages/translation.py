"""Strict JSON translation package with per-entry translator comments."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from pytrtt.config import (
    ConfigurationError,
    RuntimeSettings,
    parse_runtime_settings,
    runtime_to_dict,
)

PACKAGE_KEYS = {
    "schema_version",
    "game_id",
    "build_id",
    "resource_hash",
    "source_language",
    "target_language",
    "entries",
}
ENTRY_KEYS = {
    "id",
    "source",
    "translation",
    "comment",
    "substitution_disabled",
}
DOCUMENT_ENTRY_KEYS = ENTRY_KEYS | {"source_language", "legacy_tuid", "legacy_context", "key"}
DOCUMENT_KEYS = {
    "schema_version",
    "metadata",
    "menu",
    "subtitles",
    "fonts",
    "clear_subtitle_languages",
    "omit_subtitle_languages",
    "clear_subtitle_languages_on_overflow",
    "entry_identity",
    "credits",
}
METADATA_KEYS = {
    "game_id",
    "build_id",
    "source_language",
    "target_language",
    "archive_format",
    "archive_version",
}
RESOURCE_KEYS = {"resource_hash", "resource_path", "entries", "archive_locale", "archive_family"}
FONT_KEYS = {
    "resource_hash",
    "resource_path",
    "replacement_file",
    "source_sha256",
    "replacement_sha256",
}
EMBEDDED_FONT_KEYS = {"embedded_type", "embedded_id", "archive_locale", "character_substitutions"}


class TranslationPackageError(ValueError):
    """Raised when a translation package is malformed or unsupported."""


@dataclass(frozen=True, slots=True)
class TranslationEntry:
    """One source string, optional translation, and ordered translator notes."""

    entry_id: int
    source: str
    translation: str | None
    comment: tuple[str, ...] | None = None
    substitution_disabled: bool = False
    source_language: str | None = None
    legacy_tuid: str | None = None
    legacy_context: tuple[tuple[str, str], ...] = ()
    key: str | None = None


@dataclass(frozen=True, slots=True)
class TranslationPackage:
    """Versioned translations for one game resource and language pair."""

    game_id: str
    build_id: str
    resource_hash: str
    source_language: str
    target_language: str
    entries: tuple[TranslationEntry, ...]


@dataclass(frozen=True, slots=True)
class TranslationMetadata:
    """Required game, build, language, and archive metadata for one translation file."""

    game_id: str
    build_id: str
    source_language: str
    target_language: str
    archive_format: str
    archive_version: int


@dataclass(frozen=True, slots=True)
class TranslationCredit:
    """One contributor role and its ordered, unique display names."""

    role: str
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TranslationResource:
    """Text records belonging to one archive resource, grouped under its path and hash."""

    resource_hash: str
    resource_path: str
    entries: tuple[TranslationEntry, ...]
    archive_locale: int | None = None
    archive_family: str | None = None


@dataclass(frozen=True, slots=True)
class FontAsset:
    """Optional replacement font file stored beside the translation document."""

    resource_hash: str
    resource_path: str
    replacement_file: str
    source_sha256: str
    replacement_sha256: str
    embedded_type: int | None = None
    embedded_id: int | None = None
    archive_locale: int = 0xFFFFFFFF
    character_substitutions: tuple[tuple[str, str], ...] = ()
    archive_family: str | None = None


@dataclass(frozen=True, slots=True)
class TranslationDocument:
    """Single-file translation document with optional menu, subtitle, and font sections."""

    metadata: TranslationMetadata
    menu: tuple[TranslationResource, ...] = ()
    subtitles: tuple[TranslationResource, ...] = ()
    fonts: tuple[FontAsset, ...] = ()
    clear_subtitle_languages: frozenset[int] = frozenset()
    omit_subtitle_languages: frozenset[int] = frozenset()
    runtime: RuntimeSettings | None = None
    entry_identity: str = "record"
    credits: tuple[TranslationCredit, ...] = ()
    clear_subtitle_languages_on_overflow: tuple[int, ...] = ()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TranslationPackageError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def _require_keys(value: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    missing = required - value.keys()
    extra = value.keys() - allowed
    if missing:
        raise TranslationPackageError(f"missing required properties: {', '.join(sorted(missing))}")
    if extra:
        raise TranslationPackageError(f"unsupported properties: {', '.join(sorted(extra))}")


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TranslationPackageError(f"{name} must be a non-empty string")
    return value


def _reject_constant(value: str) -> None:
    raise TranslationPackageError(f"non-standard JSON constant is unsupported: {value}")


def _parse_comments(value: Any, field: str) -> tuple[str, ...] | None:
    """Normalize legacy string notes; write all new notes as JSON arrays."""
    if value is None:
        return None
    if isinstance(value, str):
        return tuple(value.split("\n"))
    if not isinstance(value, list) or any(not isinstance(note, str) for note in value):
        raise TranslationPackageError(f"{field} must be an array of strings or null")
    return tuple(value)


def parse_translation_package(content: str) -> TranslationPackage:
    """Parse and validate the pilot JSON schema without executing package contents."""
    try:
        root = json.loads(
            content,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise TranslationPackageError(f"invalid JSON: {exc.msg}") from exc

    if not isinstance(root, dict):
        raise TranslationPackageError("package root must be a JSON object")
    _require_keys(root, PACKAGE_KEYS, PACKAGE_KEYS)
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise TranslationPackageError("unsupported translation package schema version")

    game_id = _nonempty_string(root["game_id"], "game_id")
    build_id = _nonempty_string(root["build_id"], "build_id")
    resource_hash = _nonempty_string(root["resource_hash"], "resource_hash")
    if re.fullmatch(r"[0-9A-Fa-f]{8}", resource_hash) is None:
        raise TranslationPackageError("resource_hash must contain exactly eight hexadecimal digits")
    source_language = _nonempty_string(root["source_language"], "source_language")
    target_language = _nonempty_string(root["target_language"], "target_language")
    if not isinstance(root["entries"], list):
        raise TranslationPackageError("entries must be a JSON array")

    entries: list[TranslationEntry] = []
    entry_ids: set[int] = set()
    for position, value in enumerate(root["entries"]):
        if not isinstance(value, dict):
            raise TranslationPackageError(f"entries[{position}] must be a JSON object")
        required = ENTRY_KEYS - {"translation", "comment", "substitution_disabled"}
        _require_keys(value, ENTRY_KEYS, required)
        entry_id = value["id"]
        if type(entry_id) is not int or entry_id < 0:
            raise TranslationPackageError(f"entries[{position}].id must be a non-negative integer")
        if entry_id in entry_ids:
            raise TranslationPackageError(f"duplicate translation entry id: {entry_id}")
        entry_ids.add(entry_id)

        source = value["source"]
        translation = value.get("translation")
        comment = _parse_comments(value.get("comment"), f"entries[{position}].comment")
        substitution_disabled = value.get("substitution_disabled", False)
        if not isinstance(source, str):
            raise TranslationPackageError(f"entries[{position}].source must be a string")
        if translation is not None and not isinstance(translation, str):
            raise TranslationPackageError(
                f"entries[{position}].translation must be a string or null"
            )
        if type(substitution_disabled) is not bool:
            raise TranslationPackageError(
                f"entries[{position}].substitution_disabled must be a boolean"
            )
        entries.append(
            TranslationEntry(entry_id, source, translation, comment, substitution_disabled)
        )

    return TranslationPackage(
        game_id=game_id,
        build_id=build_id,
        resource_hash=resource_hash.upper(),
        source_language=source_language,
        target_language=target_language,
        entries=tuple(entries),
    )


def serialize_translation_package(package: TranslationPackage) -> str:
    """Serialize a package as readable UTF-8 JSON text with stable property order."""
    document: dict[str, Any] = {
        "schema_version": 1,
        "game_id": package.game_id,
        "build_id": package.build_id,
        "resource_hash": package.resource_hash,
        "source_language": package.source_language,
        "target_language": package.target_language,
        "entries": [],
    }
    serialized_entries: list[dict[str, Any]] = []
    for entry in package.entries:
        value: dict[str, Any] = {
            "id": entry.entry_id,
            "source": entry.source,
            "translation": entry.translation,
        }
        if entry.comment is not None:
            value["comment"] = list(entry.comment)
        if entry.substitution_disabled:
            value["substitution_disabled"] = True
        serialized_entries.append(value)
    document["entries"] = serialized_entries
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def _parse_entries(value: Any, field: str) -> tuple[TranslationEntry, ...]:
    if not isinstance(value, list):
        raise TranslationPackageError(f"{field} must be a JSON array")
    entries: list[TranslationEntry] = []
    entry_ids: set[int] = set()
    for position, item in enumerate(value):
        field_name = f"{field}[{position}]"
        if not isinstance(item, dict):
            raise TranslationPackageError(f"{field_name} must be a JSON object")
        _require_keys(
            item,
            DOCUMENT_ENTRY_KEYS,
            DOCUMENT_ENTRY_KEYS
            - {
                "translation",
                "comment",
                "substitution_disabled",
                "source_language",
                "legacy_tuid",
                "legacy_context",
                "key",
            },
        )
        entry_id = item["id"]
        if type(entry_id) is not int or entry_id < 0:
            raise TranslationPackageError(f"{field_name}.id must be a non-negative integer")
        if entry_id in entry_ids:
            raise TranslationPackageError(f"duplicate translation entry id: {entry_id}")
        entry_ids.add(entry_id)
        source = item["source"]
        translation = item.get("translation")
        comment = _parse_comments(item.get("comment"), f"{field_name}.comment")
        substitution_disabled = item.get("substitution_disabled", False)
        source_language = item.get("source_language")
        if not isinstance(source, str):
            raise TranslationPackageError(f"{field_name}.source must be a string")
        if translation is not None and not isinstance(translation, str):
            raise TranslationPackageError(f"{field_name}.translation must be a string or null")
        if type(substitution_disabled) is not bool:
            raise TranslationPackageError(f"{field_name}.substitution_disabled must be a boolean")
        if source_language is not None:
            source_language = _nonempty_string(source_language, f"{field_name}.source_language")
        legacy_tuid = item.get("legacy_tuid")
        if legacy_tuid is not None:
            legacy_tuid = _nonempty_string(legacy_tuid, f"{field_name}.legacy_tuid")
        context = item.get("legacy_context", {})
        if not isinstance(context, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in context.items()
        ):
            raise TranslationPackageError(f"{field_name}.legacy_context must map strings")
        key = item.get("key")
        if key is not None:
            key = _nonempty_string(key, f"{field_name}.key")
        entries.append(
            TranslationEntry(
                entry_id,
                source,
                translation,
                comment,
                substitution_disabled,
                source_language,
                legacy_tuid,
                tuple(context.items()),
                key,
            )
        )
    return tuple(entries)


def _parse_resource(value: Any, field: str) -> TranslationResource:
    if not isinstance(value, dict):
        raise TranslationPackageError(f"{field} must be a JSON object")
    _require_keys(value, RESOURCE_KEYS, RESOURCE_KEYS - {"archive_locale", "archive_family"})
    resource_hash = _nonempty_string(value["resource_hash"], f"{field}.resource_hash")
    if re.fullmatch(r"(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{16})", resource_hash) is None:
        raise TranslationPackageError(
            f"{field}.resource_hash must be eight or sixteen hexadecimal digits"
        )
    resource_path = _nonempty_string(value["resource_path"], f"{field}.resource_path")
    archive_locale = value.get("archive_locale")
    archive_family = value.get("archive_family")
    if archive_family is not None and (
        not isinstance(archive_family, str)
        or re.fullmatch(r"[A-Za-z0-9_-]+", archive_family) is None
    ):
        raise TranslationPackageError(f"{field}.archive_family must be a safe archive name")
    if archive_locale is not None and (
        type(archive_locale) is not int or not 0 <= archive_locale <= 0xFFFFFFFF
    ):
        raise TranslationPackageError(f"{field}.archive_locale must be an unsigned 32-bit integer")
    return TranslationResource(
        resource_hash.upper(),
        resource_path,
        _parse_entries(value["entries"], f"{field}.entries"),
        archive_locale,
        archive_family,
    )


def parse_translation_document(content: str) -> TranslationDocument:
    """Parse one complete JSON translation document with optional resource sections."""
    try:
        root = json.loads(
            content,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise TranslationPackageError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(root, dict):
        raise TranslationPackageError("document root must be a JSON object")
    _require_keys(root, DOCUMENT_KEYS, {"schema_version", "metadata"})
    if type(root["schema_version"]) is not int or root["schema_version"] not in (
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
    ):
        raise TranslationPackageError("unsupported translation document schema version")
    identity = root.get("entry_identity", "record")
    if identity not in ("record", "source_text"):
        raise TranslationPackageError("unsupported entry_identity")
    if "entry_identity" in root and root["schema_version"] < 4:
        raise TranslationPackageError("entry_identity requires schema version 4")

    metadata_value = root["metadata"]
    if not isinstance(metadata_value, dict):
        raise TranslationPackageError("metadata must be a JSON object")
    _require_keys(metadata_value, METADATA_KEYS | {"runtime"}, METADATA_KEYS)
    runtime = None
    if "runtime" in metadata_value:
        try:
            runtime = parse_runtime_settings(metadata_value["runtime"])
        except ConfigurationError as exc:
            raise TranslationPackageError(str(exc)) from exc
    elif root["schema_version"] == 2:
        raise TranslationPackageError("schema version 2 requires metadata.runtime")
    if runtime is not None and (
        runtime.archive.format != metadata_value["archive_format"]
        or runtime.archive.version != metadata_value["archive_version"]
    ):
        raise TranslationPackageError("runtime archive format does not match metadata")
    archive_version = metadata_value["archive_version"]
    if type(archive_version) is not int or archive_version < 1:
        raise TranslationPackageError("metadata.archive_version must be a positive integer")
    metadata = TranslationMetadata(
        game_id=_nonempty_string(metadata_value["game_id"], "metadata.game_id"),
        build_id=_nonempty_string(metadata_value["build_id"], "metadata.build_id"),
        source_language=_nonempty_string(
            metadata_value["source_language"], "metadata.source_language"
        ),
        target_language=_nonempty_string(
            metadata_value["target_language"], "metadata.target_language"
        ),
        archive_format=_nonempty_string(
            metadata_value["archive_format"], "metadata.archive_format"
        ),
        archive_version=archive_version,
    )

    menu_value = root.get("menu", [])
    if not isinstance(menu_value, list):
        raise TranslationPackageError("menu must be a JSON array")
    menu = tuple(
        _parse_resource(item, f"menu[{position}]") for position, item in enumerate(menu_value)
    )
    subtitles_value = root.get("subtitles", [])
    if not isinstance(subtitles_value, list):
        raise TranslationPackageError("subtitles must be a JSON array")
    subtitles = tuple(
        _parse_resource(item, f"subtitles[{position}]")
        for position, item in enumerate(subtitles_value)
    )
    if root["schema_version"] < 3 and any(
        entry.source_language is not None
        for resource in (*menu, *subtitles)
        for entry in resource.entries
    ):
        raise TranslationPackageError("entry source_language requires schema version 3")
    if root["schema_version"] < 7 and (
        any(len(resource.resource_hash) == 16 for resource in (*menu, *subtitles))
        or any(
            entry.key is not None for resource in (*menu, *subtitles) for entry in resource.entries
        )
    ):
        raise TranslationPackageError("64-bit hashes and keyed entries require schema version 7")
    if any(
        entry.legacy_tuid is not None or entry.legacy_context
        for resource in (*menu, *subtitles)
        for entry in resource.entries
    ) and (root["schema_version"] < 4 or identity != "source_text"):
        raise TranslationPackageError("legacy context requires schema version 4 source_text memory")
    if identity == "source_text" and runtime is not None:
        raise TranslationPackageError("translation memory cannot contain installation runtime")
    if root["schema_version"] < 4 and any(
        resource.archive_locale is not None or resource.archive_family is not None
        for resource in (*menu, *subtitles)
    ):
        raise TranslationPackageError("resource archive_locale requires schema version 4")
    resource_hashes: set[tuple[str, int | None, str | None]] = set()
    for resource in (*menu, *subtitles):
        key = resource.resource_hash, resource.archive_locale, resource.archive_family
        if key in resource_hashes:
            raise TranslationPackageError(f"duplicate resource hash: {resource.resource_hash}")
        resource_hashes.add(key)
    fonts_value = root.get("fonts", [])
    if not isinstance(fonts_value, list):
        raise TranslationPackageError("fonts must be a JSON array")
    fonts: list[FontAsset] = []
    font_hashes: set[tuple[str, int | None, int | None, int, str | None]] = set()
    for position, value in enumerate(fonts_value):
        field = f"fonts[{position}]"
        if not isinstance(value, dict):
            raise TranslationPackageError(f"{field} must be a JSON object")
        _require_keys(value, FONT_KEYS | EMBEDDED_FONT_KEYS | {"archive_family"}, FONT_KEYS)
        archive_family = value.get("archive_family")
        if archive_family is not None:
            if (
                not isinstance(archive_family, str)
                or re.fullmatch(r"[A-Za-z0-9_-]+", archive_family) is None
            ):
                raise TranslationPackageError(f"{field}.archive_family must be a safe archive name")
            if root["schema_version"] < 5:
                raise TranslationPackageError("font archive_family requires schema version 5")
        embedded_type = value.get("embedded_type")
        embedded_id = value.get("embedded_id")
        font_locale = value.get("archive_locale", 0xFFFFFFFF)
        substitutions = value.get("character_substitutions", {})
        if EMBEDDED_FONT_KEYS & value.keys():
            if root["schema_version"] < 5:
                raise TranslationPackageError("embedded fonts require schema version 5")
            if (
                type(embedded_type) is not int
                or not 0 <= embedded_type <= 255
                or type(embedded_id) is not int
                or not 0 <= embedded_id <= 0xFFFFFF
                or type(font_locale) is not int
                or not 0 <= font_locale <= 0xFFFFFFFF
            ):
                raise TranslationPackageError("embedded fonts require a valid type and id")
        if not isinstance(substitutions, dict) or any(
            not isinstance(k, str) or len(k) != 1 or not isinstance(v, str) or len(v) != 1
            for k, v in substitutions.items()
        ):
            raise TranslationPackageError("invalid font character substitutions")
        resource_hash = _nonempty_string(value["resource_hash"], f"{field}.resource_hash")
        if re.fullmatch(r"[0-9A-Fa-f]{8}", resource_hash) is None:
            raise TranslationPackageError(f"{field}.resource_hash must be eight hexadecimal digits")
        normalized_hash = resource_hash.upper()
        font_key = normalized_hash, embedded_type, embedded_id, font_locale, archive_family
        if font_key in font_hashes:
            raise TranslationPackageError(f"duplicate font resource hash: {normalized_hash}")
        font_hashes.add(font_key)
        source_sha256 = _nonempty_string(value["source_sha256"], f"{field}.source_sha256")
        replacement_sha256 = _nonempty_string(
            value["replacement_sha256"], f"{field}.replacement_sha256"
        )
        if re.fullmatch(r"[0-9A-Fa-f]{64}", source_sha256) is None:
            raise TranslationPackageError(f"{field}.source_sha256 must be a SHA-256 digest")
        if re.fullmatch(r"[0-9A-Fa-f]{64}", replacement_sha256) is None:
            raise TranslationPackageError(f"{field}.replacement_sha256 must be a SHA-256 digest")
        replacement_file = _nonempty_string(value["replacement_file"], f"{field}.replacement_file")
        relative_file = PurePosixPath(replacement_file)
        windows_file = PureWindowsPath(replacement_file)
        if (
            "\\" in replacement_file
            or relative_file.is_absolute()
            or windows_file.drive
            or ".." in relative_file.parts
        ):
            raise TranslationPackageError(f"{field}.replacement_file must be a safe relative path")
        fonts.append(
            FontAsset(
                normalized_hash,
                _nonempty_string(value["resource_path"], f"{field}.resource_path"),
                replacement_file,
                source_sha256.lower(),
                replacement_sha256.lower(),
                embedded_type,
                embedded_id,
                font_locale,
                tuple(substitutions.items()),
                archive_family,
            )
        )

    def parse_language_set(field: str) -> frozenset[int]:
        value = root.get(field, [])
        if not isinstance(value, list):
            raise TranslationPackageError(f"{field} must be a JSON array")
        if any(type(language) is not int or not 0 <= language <= 0xFF for language in value):
            raise TranslationPackageError(f"{field} contains an invalid subtitle language code")
        if len(set(value)) != len(value):
            raise TranslationPackageError(f"{field} contains duplicate subtitle language codes")
        return frozenset(value)

    clear_languages = parse_language_set("clear_subtitle_languages")
    omitted_languages = parse_language_set("omit_subtitle_languages")
    overflow_field = "clear_subtitle_languages_on_overflow"
    overflow_set = parse_language_set(overflow_field)
    overflow_languages = tuple(root.get(overflow_field, []))
    if overflow_field in root and root["schema_version"] < 8:
        raise TranslationPackageError(f"{overflow_field} requires schema version 8")
    if overflow_set & (clear_languages | omitted_languages):
        raise TranslationPackageError(
            "conditional subtitle languages overlap unconditional actions"
        )
    if (
        runtime is not None
        and runtime.language(runtime.replacement_language).subtitle_language in overflow_set
    ):
        raise TranslationPackageError("cannot conditionally clear the replacement language")
    if clear_languages & omitted_languages:
        raise TranslationPackageError("a subtitle language cannot be both cleared and omitted")

    credits_value = root.get("credits", {})
    if not isinstance(credits_value, dict):
        raise TranslationPackageError("credits must be a JSON object")
    if credits_value and root["schema_version"] < 6:
        raise TranslationPackageError("credits require schema version 6")
    credits: list[TranslationCredit] = []
    for role, names_value in credits_value.items():
        if not isinstance(role, str) or re.fullmatch(r"[a-z][a-z0-9_]*", role) is None:
            raise TranslationPackageError("credit roles must use lowercase snake_case")
        if not isinstance(names_value, list) or not names_value:
            raise TranslationPackageError(f"credits.{role} must be a non-empty JSON array")
        names = tuple(
            _nonempty_string(name, f"credits.{role}[{position}]")
            for position, name in enumerate(names_value)
        )
        if len(set(names)) != len(names):
            raise TranslationPackageError(f"credits.{role} contains duplicate names")
        credits.append(TranslationCredit(role, names))

    return TranslationDocument(
        metadata,
        menu,
        subtitles,
        tuple(fonts),
        clear_languages,
        omitted_languages,
        runtime,
        identity,
        tuple(credits),
        overflow_languages,
    )


def _serialize_entries(entries: tuple[TranslationEntry, ...]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in entries:
        value: dict[str, Any] = {
            "id": entry.entry_id,
            "source": entry.source,
            "translation": entry.translation,
        }
        if entry.comment is not None:
            value["comment"] = list(entry.comment)
        if entry.substitution_disabled:
            value["substitution_disabled"] = True
        if entry.source_language is not None:
            value["source_language"] = entry.source_language
        if entry.legacy_tuid is not None:
            value["legacy_tuid"] = entry.legacy_tuid
        if entry.legacy_context:
            value["legacy_context"] = dict(entry.legacy_context)
        if entry.key is not None:
            value["key"] = entry.key
        result.append(value)
    return result


def _serialize_resource(resource: TranslationResource) -> dict[str, Any]:
    return {
        "resource_hash": resource.resource_hash.upper(),
        "resource_path": resource.resource_path,
        "entries": _serialize_entries(resource.entries),
        **(
            {"archive_locale": resource.archive_locale}
            if resource.archive_locale is not None
            else {}
        ),
        **(
            {"archive_family": resource.archive_family}
            if resource.archive_family is not None
            else {}
        ),
    }


def serialize_translation_document(document: TranslationDocument) -> str:
    """Serialize one editable JSON file, omitting absent optional sections."""
    metadata = document.metadata
    root: dict[str, Any] = {
        "schema_version": 1,
        "metadata": {
            "game_id": metadata.game_id,
            "build_id": metadata.build_id,
            "source_language": metadata.source_language,
            "target_language": metadata.target_language,
            "archive_format": metadata.archive_format,
            "archive_version": metadata.archive_version,
        },
    }
    if document.runtime is not None:
        root["schema_version"] = 2
        root["metadata"]["runtime"] = runtime_to_dict(document.runtime)
    if document.credits:
        root["credits"] = {credit.role: list(credit.names) for credit in document.credits}
    if any(
        entry.source_language is not None
        for resource in (*document.menu, *document.subtitles)
        for entry in resource.entries
    ):
        root["schema_version"] = 3
    if (
        document.entry_identity != "record"
        or any(
            resource.archive_locale is not None or resource.archive_family is not None
            for resource in (*document.menu, *document.subtitles)
        )
        or any(
            e.legacy_tuid is not None or e.legacy_context
            for r in (*document.menu, *document.subtitles)
            for e in r.entries
        )
    ):
        root["schema_version"] = 4
        root["entry_identity"] = document.entry_identity
    if document.menu:
        root["menu"] = [_serialize_resource(resource) for resource in document.menu]
    if document.subtitles:
        root["subtitles"] = [_serialize_resource(resource) for resource in document.subtitles]
    if document.fonts:
        if any(f.embedded_type is not None or f.archive_family is not None for f in document.fonts):
            root["schema_version"] = 5
        root["fonts"] = [
            {
                "resource_hash": font.resource_hash.upper(),
                "resource_path": font.resource_path,
                "replacement_file": font.replacement_file,
                "source_sha256": font.source_sha256.lower(),
                "replacement_sha256": font.replacement_sha256.lower(),
                **(
                    {"archive_family": font.archive_family}
                    if font.archive_family is not None
                    else {}
                ),
                **(
                    {
                        "embedded_type": font.embedded_type,
                        "embedded_id": font.embedded_id,
                        "archive_locale": font.archive_locale,
                        **(
                            {"character_substitutions": dict(font.character_substitutions)}
                            if font.character_substitutions
                            else {}
                        ),
                    }
                    if font.embedded_type is not None
                    else {}
                ),
            }
            for font in document.fonts
        ]
    if document.clear_subtitle_languages:
        root["clear_subtitle_languages"] = sorted(document.clear_subtitle_languages)
    if document.omit_subtitle_languages:
        root["omit_subtitle_languages"] = sorted(document.omit_subtitle_languages)
    if document.credits:
        root["schema_version"] = 6
    if any(
        len(resource.resource_hash) == 16
        or any(entry.key is not None for entry in resource.entries)
        for resource in (*document.menu, *document.subtitles)
    ):
        root["schema_version"] = 7
    if document.clear_subtitle_languages_on_overflow:
        root["schema_version"] = 8
        root["clear_subtitle_languages_on_overflow"] = list(
            document.clear_subtitle_languages_on_overflow
        )
    return json.dumps(root, ensure_ascii=False, indent=2) + "\n"
