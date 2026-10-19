"""Bind a source-text translation memory to freshly extracted record identities."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pytrtt.packages.translation import (
    parse_translation_document,
    serialize_translation_document,
)
from pytrtt.packages.translation_memory import bind_translation_memory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory", required=True, type=Path)
    parser.add_argument("--extracted", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        memory = parse_translation_document(args.memory.read_text(encoding="utf-8"))
        extracted = parse_translation_document(args.extracted.read_text(encoding="utf-8"))
        bound = bind_translation_memory(memory, extracted)
        content = serialize_translation_document(bound)
        parse_translation_document(content)
        asset_root = args.memory.parent if memory.fonts else args.extracted.parent
        for font in bound.fonts:
            source = (asset_root / font.replacement_file).resolve()
            if not source.is_relative_to(asset_root.resolve()):
                raise ValueError("font asset is outside the memory package")
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() != font.replacement_sha256:
                raise ValueError("font asset hash mismatch")
            target = (args.output.parent / font.replacement_file).resolve()
            if not target.is_relative_to(args.output.parent.resolve()):
                raise ValueError("font output is outside the bound package")
            if target.exists():
                if target.read_bytes() != data:
                    raise ValueError("refusing to overwrite a different font asset")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
