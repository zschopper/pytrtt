"""Console adapter for the same service a graphical client can call."""

from __future__ import annotations

import argparse
import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from pytrtt.composition import create_translation_service
from pytrtt.environment import resolve_installation
from pytrtt.i18n import Translator
from pytrtt.packages.translation import (
    FontAsset,
    TranslationDocument,
    TranslationResource,
    parse_translation_document,
)
from pytrtt.services.translation import MissingTranslation, parse_filelist

DEVELOPER_EMAIL = "tombraidertranslations@gmail.com"


class LocalizedArgumentParser(argparse.ArgumentParser):
    def __init__(self, translator: Translator) -> None:
        self.translator = translator
        super().__init__(description=translator.text("description"), add_help=False)
        self._optionals.title = translator.text("help_options")
        self.add_argument("-h", "--help", action="help", help=translator.text("help_help"))

    def format_usage(self) -> str:
        return self._localized_usage(super().format_usage())

    def format_help(self) -> str:
        return self._localized_usage(super().format_help())

    def _localized_usage(self, value: str) -> str:
        prefix = "usage: "
        return (
            self.translator.text("help_usage") + value[len(prefix) :]
            if value.startswith(prefix)
            else value
        )

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(2, self.translator.text("argument_error") + "\n")


def _localized_label(label: str, translator: Translator) -> str:
    kind, separator, identifier = label.partition(" ")
    keys = {"Menu": "section_menu", "Subtitle": "section_subtitles", "Font": "section_fonts"}
    return translator.text(keys[kind]) + separator + identifier if kind in keys else label


def _parser(translator: Translator) -> argparse.ArgumentParser:
    parser = LocalizedArgumentParser(translator)
    for name, required in (
        ("game-dir", False),
        ("translation-file", False),
        ("package-dir", False),
        ("transaction-dir", False),
        ("filelist", False),
        ("local-config", False),
    ):
        parser.add_argument(
            "--" + name,
            required=required,
            type=Path,
            help=translator.text("help_" + name.replace("-", "_")),
        )
    parser.add_argument("--game", help=translator.text("help_game_selector"))
    parser.add_argument("--build-id", help=translator.text("help_build_id"))
    parser.add_argument(
        "--boundary", type=lambda value: int(value, 0), help=translator.text("help_boundary")
    )
    parser.add_argument(
        "--ui-language", default=translator.language, help=translator.text("help_ui_language")
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help=translator.text("help_apply"))
    action.add_argument("--restore", action="store_true", help=translator.text("help_restore"))
    return parser


def _user_data_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "PyTRTT"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "pytrtt"


def _stamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", value)


def _report_path(game_id: str, kind: str) -> Path:
    return _user_data_dir() / "reports" / _slug(game_id) / f"{kind}-{_stamp()}.txt"


def _write_missing_report(
    path: Path,
    document: TranslationDocument,
    items: tuple[MissingTranslation, ...],
    translator: Translator,
) -> None:
    metadata = document.metadata
    display_name = document.runtime.display_name if document.runtime else metadata.game_id
    lines = [
        translator.text("missing_heading"),
        translator.text("platform", value=platform.platform()),
        translator.text("game", value=f"{display_name} ({metadata.game_id})"),
        translator.text("build", value=metadata.build_id),
        translator.text("source_language", value=metadata.source_language),
        translator.text("target_language", value=metadata.target_language),
        translator.text("missing_entries", count=len(items)),
        "",
    ]
    for item in items:
        lines.extend(
            (
                translator.text(
                    "record",
                    section=translator.text("section_" + item.section),
                    resource=item.resource_hash,
                    entry=item.entry_id,
                ),
                translator.text("source", value=item.source),
                "",
            )
        )
    lines.extend((translator.text("send_report", email=DEVELOPER_EMAIL), ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    language = "en"
    for index, item in enumerate(arguments):
        if item == "--ui-language" and index + 1 < len(arguments):
            language = arguments[index + 1]
        elif item.startswith("--ui-language="):
            language = item.partition("=")[2]
    try:
        translator = Translator(language)
    except ValueError:
        translator = Translator()
    args = _parser(translator).parse_args(arguments)
    service = create_translation_service()
    game_id = "unknown"
    try:
        document = None
        if args.translation_file:
            translation_path = args.translation_file.resolve(strict=True)
            document = parse_translation_document(translation_path.read_text(encoding="utf-8"))
            game_id = document.metadata.game_id
        selector = document.metadata.game_id if document else args.game
        game_dir = resolve_installation(selector, args.game_dir, args.local_config).resolve(
            strict=True
        )
        if args.restore:
            if args.transaction_dir is None:
                raise ValueError("--restore requires --transaction-dir")
            service.restore(game_dir, args.transaction_dir, document.runtime if document else None)
            print(translator.text("restored", path=args.transaction_dir.resolve()))
            return 0
        if document is None:
            raise ValueError("--translation-file is required unless --restore is used")
        if args.boundary is not None and (
            document.runtime is None or args.boundary != document.runtime.archive.boundary
        ):
            raise ValueError("--boundary must match embedded runtime settings")
        if args.filelist is not None:
            names = parse_filelist(args.filelist.read_text(encoding="utf-8-sig"))
            resources: tuple[TranslationResource | FontAsset, ...] = (
                *document.menu,
                *document.subtitles,
                *document.fonts,
            )
            for resource in resources:
                actual = names.get(int(resource.resource_hash, 16), "")
                if (
                    actual.replace("\\", "/").casefold()
                    != resource.resource_path.replace("\\", "/").casefold()
                ):
                    raise ValueError("resource path does not match developer filelist")
        package_dir = args.package_dir or args.translation_file.parent
        result = service.plan(
            game_dir, document, package_dir=package_dir, expected_build_id=args.build_id
        )
        transaction_dir = args.transaction_dir or (
            _user_data_dir() / "transactions" / _slug(game_id) / _stamp()
        )
        if result.plan is None:
            print(translator.text("no_changes"))
        else:
            plan = result.plan
            changed = [w for w in plan.writes if w.kind == "resource"]
            print(
                translator.text(
                    "plan_summary",
                    resources=len(changed),
                    files=len(plan.files),
                    bytes=plan.backup_bytes,
                    space=translator.text("yes" if plan.sufficient_space else "no"),
                )
            )
            if not plan.sufficient_space:
                raise ValueError("insufficient free space for the planned operation")
            for write in changed:
                print(
                    translator.text(
                        "resource_write",
                        label=_localized_label(write.label, translator),
                        file=write.file_name,
                        offset=write.offset,
                        bytes=len(write.data),
                    )
                )
        if result.missing_translations:
            key = "missing_count" if args.apply else "missing_pending"
            print(translator.text(key, count=len(result.missing_translations)))
            if args.apply:
                path = _report_path(game_id, "missing-translations")
                _write_missing_report(path, document, result.missing_translations, translator)
                print(translator.text("report_path", path=path))
                print(translator.text("send_report", email=DEVELOPER_EMAIL))
        if not args.apply:
            print(translator.text("dry_run"))
            if result.plan is not None:
                print(translator.text("transaction_path", path=transaction_dir))
            return 0
        if result.plan is not None:
            service.apply(result, transaction_dir)
            print(translator.text("applied", path=transaction_dir.resolve()))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        try:
            path = _report_path(game_id, "diagnostic")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(
                    translator.text("error_heading")
                    + "\n"
                    + translator.text("platform", value=platform.platform())
                    + "\n"
                    + translator.text("diagnostic", value=f"{type(exc).__name__}: {exc}")
                    + "\n"
                )
            print(translator.text("operation_failed", path=path), file=sys.stderr)
        except OSError:
            print(translator.text("diagnostic_failed", type=type(exc).__name__), file=sys.stderr)
        return 1
    return 0
