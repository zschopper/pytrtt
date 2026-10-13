"""Compile developer profiles into self-contained translation documents."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pytrtt.config import RuntimeSettings, parse_runtime_settings
from pytrtt.packages.translation import (
    TranslationDocument,
    TranslationMetadata,
    TranslationPackageError,
    parse_translation_document,
    serialize_translation_document,
)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TranslationPackageError(f"duplicate profile property: {key}")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class DeveloperProfile:
    game_id: str
    build_id: str
    filelist: Path
    asset_root: Path
    runtime_value: dict[str, Any]
    translation_defaults: dict[str, Any]

    def settings(self, target_language: str) -> RuntimeSettings:
        value = dict(self.runtime_value)
        defaults = self.translation_defaults.get(target_language, {})
        for field in ("character_substitutions", "replacement_language"):
            if field in defaults:
                value[field] = defaults[field]
        return parse_runtime_settings(value)

    def metadata(
        self, source_language: str, target_language: str, build_id: str | None = None
    ) -> TranslationMetadata:
        settings = self.settings(target_language)
        return TranslationMetadata(
            self.game_id,
            build_id or self.build_id,
            source_language,
            target_language,
            settings.archive.format,
            settings.archive.version,
        )

    def compile(
        self, document: TranslationDocument, *, apply_defaults: bool = False
    ) -> TranslationDocument:
        if document.metadata.game_id != self.game_id:
            raise TranslationPackageError("profile and translation target different games")
        runtime = self.settings(document.metadata.target_language)
        runtime.language(document.metadata.source_language)
        updated = replace(
            document,
            runtime=runtime,
            metadata=replace(
                document.metadata,
                archive_format=runtime.archive.format,
                archive_version=runtime.archive.version,
            ),
        )
        # Round-trip validation also checks the existing text and font asset declarations.
        value = json.loads(serialize_translation_document(updated))
        if apply_defaults:
            defaults = self.translation_defaults.get(document.metadata.target_language, {})
            for field in ("fonts", "clear_subtitle_languages", "omit_subtitle_languages"):
                if field in defaults:
                    value[field] = defaults[field]
        return parse_translation_document(json.dumps(value, ensure_ascii=False))


def load_profile(path: Path) -> DeveloperProfile:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
    keys = {
        "schema_version",
        "game_id",
        "build_id",
        "filelist",
        "asset_root",
        "runtime",
        "translation_defaults",
    }
    if not isinstance(value, dict) or value.keys() != keys:
        raise TranslationPackageError("invalid developer profile fields")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise TranslationPackageError("unsupported developer profile version")
    for field in ("game_id", "build_id"):
        if not isinstance(value[field], str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value[field]):
            raise TranslationPackageError(f"invalid profile {field}")
    defaults = value["translation_defaults"]
    if not isinstance(defaults, dict) or any(not isinstance(v, dict) for v in defaults.values()):
        raise TranslationPackageError("invalid translation defaults")
    for language, fields in defaults.items():
        if not isinstance(language, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", language):
            raise TranslationPackageError("invalid translation language")
        if fields.keys() - {
            "character_substitutions",
            "replacement_language",
            "fonts",
            "clear_subtitle_languages",
            "omit_subtitle_languages",
        }:
            raise TranslationPackageError("unsupported translation default fields")
    settings = parse_runtime_settings(value["runtime"])
    from pytrtt.config import runtime_to_dict

    root = path.resolve(strict=True).parent
    for field in ("filelist", "asset_root"):
        if not isinstance(value[field], str) or not value[field]:
            raise TranslationPackageError(f"invalid profile {field}")
    profile = DeveloperProfile(
        value["game_id"],
        value["build_id"],
        (root / value["filelist"]).resolve(),
        (root / value["asset_root"]).resolve(),
        runtime_to_dict(settings),
        defaults,
    )
    for language in defaults:
        profile.settings(language)
    return profile
