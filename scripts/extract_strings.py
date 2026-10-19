"""Developer extraction: profile configuration becomes language-document runtime data."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pytrtt.composition import create_translation_service
from pytrtt.development.profiles import load_profile
from pytrtt.environment import resolve_installation
from pytrtt.packages.translation import serialize_translation_document
from pytrtt.services.translation import parse_filelist


def _write_outputs(output: Path, files: dict[str, str | bytes]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name in files:
        if (output / name).exists():
            raise FileExistsError(f"refusing to overwrite existing extraction output: {name}")
    for name, content in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            with path.open("xb") as stream:
                stream.write(content)
        else:
            with path.open("x", encoding="utf-8", newline="\n") as text:
                text.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--game-dir", type=Path)
    parser.add_argument("--local-config", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--filelist", type=Path)
    parser.add_argument("--build-id")
    parser.add_argument("--source-language", default="en")
    parser.add_argument("--target-language", default="hu")
    parser.add_argument("--boundary", type=lambda value: int(value, 0))
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    try:
        profile = load_profile(args.profile)
        game = resolve_installation(profile.game_id, args.game_dir, args.local_config).resolve()
        if output == game or output.is_relative_to(game):
            print("Error: output directory must be outside the game directory.", file=sys.stderr)
            return 2
        runtime = profile.settings(args.target_language)
        if args.boundary is not None:
            runtime = replace(runtime, archive=replace(runtime.archive, boundary=args.boundary))
        metadata = profile.metadata(args.source_language, args.target_language, args.build_id)
        names = parse_filelist((args.filelist or profile.filelist).read_text(encoding="utf-8-sig"))
        result = create_translation_service().extract(game, metadata, runtime, names)
        document = result.document
        # Preserve this invocation's explicit boundary when embedding the profile defaults.
        compiled = profile.compile(document, apply_defaults=True)
        document = replace(compiled, runtime=runtime)
        restore_records = [
            {
                "file": a.recovery_path,
                "resource_hash": f"{a.name_hash:08X}",
                "resource_path": a.path,
                "locale": f"{a.locale:08X}",
                "size": len(a.data),
                "sha256": hashlib.sha256(a.data).hexdigest(),
            }
            for a in result.recovery_assets
        ]
        filename = (
            f"{metadata.game_id}.{metadata.source_language}-to-{metadata.target_language}.json"
        )
        report = {
            "game_id": metadata.game_id,
            "build_id": metadata.build_id,
            "source_locale": f"{runtime.language(metadata.source_language).archive_locale:08X}",
            "packages": [
                {
                    "file": filename,
                    "section": "subtitles" if section == "cine" else section,
                    "resource_hash": r.resource_hash,
                    "resource_path": r.resource_path,
                    "entry_count": len(r.entries),
                }
                for section, resources in (("menu", document.menu), ("cine", document.subtitles))
                for r in resources
            ],
            "package_count": len(document.menu) + len(document.subtitles),
            "empty_resources": result.empty_resources,
            "skipped_resources": [
                {"resource_hash": f"{r.name_hash:08X}", "path": r.path, "reason": r.reason}
                for r in result.skipped_resources
            ],
            "restore_data": restore_records,
        }
        files: dict[str, str | bytes] = {
            filename: serialize_translation_document(document),
            "extraction-report.json": json.dumps(report, indent=2) + "\n",
        }
        for asset in result.recovery_assets:
            files[asset.recovery_path] = asset.data
        for font in document.fonts:
            relative = Path(font.replacement_file)
            asset_path = (profile.asset_root / relative).resolve(strict=True)
            if profile.asset_root.resolve() not in asset_path.parents:
                raise ValueError("font asset escapes developer asset root")
            data = asset_path.read_bytes()
            if hashlib.sha256(data).hexdigest() != font.replacement_sha256:
                raise ValueError("configured font asset hash mismatch")
            files[font.replacement_file] = data
        _write_outputs(output, files)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Extracted {report['package_count']} resources; output: {output / filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
