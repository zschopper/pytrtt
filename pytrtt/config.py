"""Declarative runtime settings shared by profiles, packages, and clients."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import PurePosixPath, PureWindowsPath
from typing import cast


class ConfigurationError(ValueError):
    """Invalid declarative configuration; configuration never executes code."""


@dataclass(frozen=True, slots=True)
class ArchiveSettings:
    format: str
    version: int
    boundary: int
    data_subdir: str = "."
    families: tuple[str, ...] = ()
    include_overridden: bool = False
    index_files: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class LanguageSlot:
    code: str
    archive_locale: int
    subtitle_language: int
    locale_is_mask: bool = False


@dataclass(frozen=True, slots=True)
class ResourceRule:
    section: str
    pattern: str
    format: str
    version: int
    locale: int | None = None
    skip_unrecognized: bool = False

    def matches(self, path: str) -> bool:
        return fnmatchcase(path.replace("\\", "/").casefold(), self.pattern.casefold())


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    archive: ArchiveSettings
    languages: tuple[LanguageSlot, ...]
    replacement_language: str
    resource_types: tuple[ResourceRule, ...]
    character_substitutions: tuple[tuple[str, str], ...] = ()
    display_name: str = ""

    def language(self, code: str) -> LanguageSlot:
        matches = [slot for slot in self.languages if slot.code == code]
        if len(matches) != 1:
            raise ConfigurationError(f"unsupported language slot: {code}")
        return matches[0]

    def rule(self, path: str, section: str | None = None) -> ResourceRule | None:
        rules = [
            rule
            for rule in self.resource_types
            if (section is None or rule.section == section) and rule.matches(path)
        ]
        if len(rules) > 1:
            raise ConfigurationError(f"ambiguous resource rules: {path}")
        return rules[0] if rules else None


def _object(value: object, keys: set[str], required: set[str], field: str) -> dict[str, object]:
    if not isinstance(value, dict) or value.keys() - keys or required - value.keys():
        raise ConfigurationError(f"invalid fields in {field}")
    # The key check above restricts the mapping to declared string keys.
    return cast(dict[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field} must be a non-empty string")
    return value


def _integer(value: object, field: str, minimum: int = 0, maximum: int = 0xFFFFFFFF) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ConfigurationError(f"{field} must be an integer in {minimum}..{maximum}")
    return value


def parse_runtime_settings(value: object) -> RuntimeSettings:
    keys = {
        "archive",
        "languages",
        "replacement_language",
        "resource_types",
        "character_substitutions",
        "display_name",
    }
    root = _object(value, keys, keys - {"display_name", "character_substitutions"}, "runtime")
    arc = _object(
        root["archive"],
        {
            "format",
            "version",
            "boundary",
            "data_subdir",
            "families",
            "include_overridden",
            "index_files",
        },
        {"format", "version", "boundary"},
        "archive",
    )
    subdir = _text(arc.get("data_subdir", "."), "data_subdir")
    if (
        "\\" in subdir
        or PurePosixPath(subdir).is_absolute()
        or PureWindowsPath(subdir).drive
        or ".." in PurePosixPath(subdir).parts
    ):
        raise ConfigurationError("archive data_subdir must be a safe relative path")
    families = arc.get("families", [])
    if (
        not isinstance(families, list)
        or any(
            not isinstance(name, str)
            or not name
            or any(
                c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for c in name
            )
            for name in families
        )
        or len(set(families)) != len(families)
    ):
        raise ConfigurationError("archive families must be unique safe names")
    include_overridden = arc.get("include_overridden", False)
    if type(include_overridden) is not bool:
        raise ConfigurationError("include_overridden must be boolean")
    index_files = arc.get("index_files", {})
    if (
        not isinstance(index_files, dict)
        or any(
            alias not in families
            or not isinstance(filename, str)
            or re.fullmatch(
                r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.[0-9]{3}\.tiger"
                if arc.get("format") == "tiger"
                else r"[A-Za-z0-9_-]+\.[0-9]{3}",
                filename,
            )
            is None
            for alias, filename in index_files.items()
        )
        or len(set(index_files.values())) != len(index_files)
    ):
        raise ConfigurationError(
            "index_files must map declared families to unique safe archive files"
        )
    archive = ArchiveSettings(
        _text(arc["format"], "format"),
        _integer(arc["version"], "version", 1),
        _integer(arc["boundary"], "boundary", 1),
        subdir,
        tuple(families),
        include_overridden,
        tuple(index_files.items()),
    )
    language_value = root["languages"]
    if not isinstance(language_value, dict) or not language_value:
        raise ConfigurationError("languages must be a non-empty object")
    languages = []
    for code, data in language_value.items():
        code = _text(code, "language code")
        fields = _object(
            data,
            {"archive_locale", "subtitle_language", "locale_is_mask"},
            {"archive_locale", "subtitle_language"},
            "language slot",
        )
        mask = fields.get("locale_is_mask", False)
        if type(mask) is not bool:
            raise ConfigurationError("locale_is_mask must be boolean")
        languages.append(
            LanguageSlot(
                code,
                _integer(
                    fields["archive_locale"],
                    "archive_locale",
                    maximum=0xFFFFFFFFFFFFFFFF,
                ),
                _integer(fields["subtitle_language"], "subtitle_language", maximum=255),
                mask,
            )
        )
    raw_rules = root["resource_types"]
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ConfigurationError("resource_types must be a non-empty array")
    rules = []
    for raw in raw_rules:
        rule = _object(
            raw,
            {
                "section",
                "pattern",
                "format",
                "version",
                "locale",
                "skip_unrecognized",
            },
            {"section", "pattern", "format", "version"},
            "resource rule",
        )
        section = _text(rule["section"], "section")
        if section not in {"menu", "subtitles", "fonts"}:
            raise ConfigurationError("unsupported resource section")
        skip = rule.get("skip_unrecognized", False)
        if type(skip) is not bool:
            raise ConfigurationError("skip_unrecognized must be boolean")
        pattern = _text(rule["pattern"], "pattern").replace("\\", "/")
        rules.append(
            ResourceRule(
                section,
                pattern,
                _text(rule["format"], "format"),
                _integer(rule["version"], "version", 1),
                _integer(rule["locale"], "locale") if "locale" in rule else None,
                skip,
            )
        )
    substitutions = root.get("character_substitutions", {})
    if not isinstance(substitutions, dict) or any(
        not isinstance(k, str)
        or len(k) != 1
        or not isinstance(v, str)
        or len(v) != 1
        or "\0" in k + v
        or "\r" in k + v
        for k, v in substitutions.items()
    ):
        raise ConfigurationError("character substitutions must map single characters")
    display = root.get("display_name", "")
    if not isinstance(display, str):
        raise ConfigurationError("display_name must be a string")
    settings = RuntimeSettings(
        archive,
        tuple(languages),
        _text(root["replacement_language"], "replacement_language"),
        tuple(rules),
        tuple(cast(dict[str, str], substitutions).items()),
        display,
    )
    settings.language(settings.replacement_language)
    return settings


def runtime_to_dict(settings: RuntimeSettings) -> dict[str, object]:
    return {
        "archive": {
            "format": settings.archive.format,
            "version": settings.archive.version,
            "boundary": settings.archive.boundary,
            "data_subdir": settings.archive.data_subdir,
            **({"families": list(settings.archive.families)} if settings.archive.families else {}),
            **({"include_overridden": True} if settings.archive.include_overridden else {}),
            **(
                {"index_files": dict(settings.archive.index_files)}
                if settings.archive.index_files
                else {}
            ),
        },
        "languages": {
            slot.code: {
                "archive_locale": slot.archive_locale,
                "subtitle_language": slot.subtitle_language,
                **({"locale_is_mask": True} if slot.locale_is_mask else {}),
            }
            for slot in settings.languages
        },
        "replacement_language": settings.replacement_language,
        "resource_types": [
            {
                "section": rule.section,
                "pattern": rule.pattern,
                "format": rule.format,
                "version": rule.version,
                **({"locale": rule.locale} if rule.locale is not None else {}),
                **({"skip_unrecognized": True} if rule.skip_unrecognized else {}),
            }
            for rule in settings.resource_types
        ],
        "character_substitutions": dict(settings.character_substitutions),
        **({"display_name": settings.display_name} if settings.display_name else {}),
    }
