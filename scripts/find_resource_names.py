"""Find conservative path candidates in raw or already decompressed resource files.

This investigation tool does not parse archives, decompress data or modify inputs.
Output is JSON Lines; hash matches are candidates, not proof of original names.
"""

import argparse
import json
import mmap
import os
import re
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import TypedDict

DEFAULT_EXTENSIONS = frozenset({"drm", "mul", "sch", "raw", "bin", "tfb", "arg"})
TOKEN = rb"[A-Za-z0-9_./\\-]"
SCAN_CHUNK_SIZE = 4 * 1024 * 1024


class ProgressDisplay:
    """Rate-limited byte progress on stderr, independent of JSONL output."""

    def __init__(self, total: int, enabled: bool) -> None:
        self.total = total
        self.enabled = enabled
        self.completed = 0
        self.last_update = float("-inf")
        self.width = 0

    def update(
        self, amount: int, path: Path, candidates: int, matches: int, *, finished: bool = False
    ) -> None:
        self.completed += amount
        now = time.monotonic()
        if not self.enabled or (not finished and now - self.last_update < 0.2):
            return
        self.last_update = now
        ratio = self.completed / self.total if self.total else 0.0
        percent = 100.0 if finished else min(99.9, ratio * 100)
        filled = int(percent / 100 * 20)
        filename = path.name.replace("\r", " ").replace("\n", " ")[-48:]
        line = (
            f"[{'#' * filled}{'-' * (20 - filled)}] {percent:5.1f}% "
            f"candidates={candidates} matches={matches} {filename}"
        )
        self.width = max(self.width, len(line))
        print(
            "\r" + line.ljust(self.width), end="\n" if finished else "", file=sys.stderr, flush=True
        )

    def abort(self) -> None:
        if self.enabled and self.width:
            print(file=sys.stderr)


class Candidate(TypedDict):
    source: str
    offset: int
    encoding: str
    name: str
    kind: str
    hash_bits: int
    hash: str
    index_match: bool | None


def calculate_hash(name: str, bits: int) -> int:
    """Apply the reference CRC-style 32-bit or FNV-1a 64-bit name algorithm."""
    if bits == 32:
        value = 0xFFFFFFFF
        for char in name:
            value ^= ord(char) << 24
            for _ in range(8):
                value = ((value << 1) ^ (0x04C11DB7 if value & 0x80000000 else 0)) & 0xFFFFFFFF
        return value ^ 0xFFFFFFFF
    if bits == 64:
        value = 0xCBF29CE484222325
        for char in name:
            value = ((value ^ ord(char)) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        return value
    raise ValueError("Hash width must be 32 or 64")


def load_hashes(path: Path, bits: int) -> set[int]:
    """Read one hexadecimal hash per line, allowing blank lines and # comments."""
    values: set[int] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.partition("#")[0].strip()
        if not line:
            continue
        if not re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]+", line):
            raise ValueError(f"Invalid hexadecimal hash at line {number}")
        value = int(line, 16)
        if value >= 1 << bits:
            raise ValueError(f"Hash exceeds {bits} bits at line {number}")
        values.add(value)
    return values


def patterns(extensions: frozenset[str]) -> list[tuple[str, re.Pattern[bytes]]]:
    if not extensions or any(not re.fullmatch(r"[a-zA-Z0-9]+", e) for e in extensions):
        raise ValueError("Extensions must be nonempty ASCII letters or digits, without dots")
    endings = b"|".join(e.encode("ascii") for e in sorted(extensions))
    ascii_pattern = (
        rb"(?<!"
        + TOKEN
        + rb")"
        + TOKEN
        + rb"{1,1024}\."
        + rb"(?:"
        + endings
        + rb")(?!"
        + TOKEN
        + rb")"
    )
    wide_token = TOKEN + rb"\x00"
    wide_endings = b"|".join(
        b"".join(re.escape(bytes([c])) + rb"\x00" for c in e.encode("ascii"))
        for e in sorted(extensions)
    )
    wide_pattern = (
        rb"(?<!"
        + wide_token
        + rb")(?:"
        + wide_token
        + rb"){1,1024}\.\x00(?:"
        + wide_endings
        + rb")(?!"
        + wide_token
        + rb")"
    )
    return [
        ("ascii/utf-8", re.compile(ascii_pattern, re.IGNORECASE)),
        ("utf-16-le", re.compile(wide_pattern, re.IGNORECASE)),
    ]


def scan_file(
    path: Path,
    extensions: frozenset[str],
    bits: int,
    hashes: set[int] | None,
    *,
    on_progress: Callable[[int], None] | None = None,
) -> Iterator[Candidate]:
    """Scan using a read-only mapping, including UTF-16 strings at odd byte offsets."""
    compiled = patterns(extensions)
    before = path.stat()
    if before.st_size == 0:
        return
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for encoding, pattern in compiled:
            for match in chunk_matches(data, pattern, extensions, on_progress):
                name = match.group().decode("utf-16-le" if encoding == "utf-16-le" else "ascii")
                normalized = name.replace("\\", "/").lower()
                if normalized.startswith(("pc-w/", "pcx64-w/", "local/", "/tr7/")):
                    kind = "full_path"
                else:
                    kind = "relative_path" if "/" in normalized else "basename"
                value = calculate_hash(name, bits)
                yield {
                    "source": str(path),
                    "offset": match.start(),
                    "encoding": encoding,
                    "name": name,
                    "kind": kind,
                    "hash_bits": bits,
                    "hash": f"{value:0{bits // 4}X}",
                    "index_match": None if hashes is None else value in hashes,
                }
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError(f"Input changed during scanning: {path}; discard this run's output")


def chunk_matches(
    data: mmap.mmap,
    pattern: re.Pattern[bytes],
    extensions: frozenset[str],
    on_progress: Callable[[int], None] | None,
) -> Iterator[re.Match[bytes]]:
    # Scan beyond each chunk to preserve complete names and the trailing boundary.
    # Only the chunk containing the match start owns it, preventing duplicate hits.
    overlap = (1024 + 1 + max(map(len, extensions))) * 2 + 2
    for start in range(0, len(data), SCAN_CHUNK_SIZE):
        end = min(start + SCAN_CHUNK_SIZE, len(data))
        for match in pattern.finditer(data, start, min(end + overlap, len(data))):
            if match.start() >= end:
                break
            yield match
        if on_progress:
            on_progress(end - start)


def input_files(inputs: list[Path]) -> Iterator[Path]:
    seen: set[Path] = set()
    for path in inputs:
        if path.is_symlink():
            raise ValueError(f"Symbolic link input is not supported: {path}")
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = []
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(
                    d
                    for d in dirs
                    if d not in {".git", ".svn", ".backups"} and not (Path(root) / d).is_symlink()
                )
                candidates.extend(Path(root) / f for f in sorted(files))
        else:
            raise ValueError(f"Input does not exist or is not a regular file/directory: {path}")
        for candidate in candidates:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs", nargs="+", type=Path, help="Files or directories to scan recursively"
    )
    parser.add_argument(
        "--output", type=Path, help="New JSONL file outside input directories; default stdout"
    )
    parser.add_argument(
        "--hashes", type=Path, help="UTF-8 file with one hexadecimal index hash per line"
    )
    parser.add_argument("--hash-bits", type=int, choices=(32, 64), default=32)
    parser.add_argument("--extensions", default=",".join(sorted(DEFAULT_EXTENSIONS)))
    parser.add_argument(
        "--progress",
        choices=("auto", "always", "never"),
        default="auto",
        help="Show progress on stderr; auto enables it for a terminal",
    )
    args = parser.parse_args(argv)
    extensions = frozenset(args.extensions.split(","))
    progress: ProgressDisplay | None = None
    try:
        patterns(extensions)
        hashes = load_hashes(args.hashes, args.hash_bits) if args.hashes else None
        if args.output:
            target = args.output.resolve()
            for path in args.inputs:
                resolved = path.resolve()
                if target == resolved or (path.is_dir() and target.is_relative_to(resolved)):
                    raise ValueError("Output must be outside all input directories and input files")
        paths = list(input_files(args.inputs))
        # Both encoding passes scan the entire input; count their work equally.
        progress = ProgressDisplay(
            sum(path.stat().st_size for path in paths) * 2,
            args.progress == "always" or (args.progress == "auto" and sys.stderr.isatty()),
        )
        count = files = matches = 0
        current_path = Path("(empty)")

        def advance(amount: int) -> None:
            assert progress is not None
            progress.update(amount, current_path, count, matches)

        with ExitStack() as stack:
            output = (
                stack.enter_context(args.output.open("x", encoding="utf-8"))
                if args.output
                else sys.stdout
            )
            for path in paths:
                current_path = path
                progress.update(0, path, count, matches)
                for candidate in scan_file(
                    path, extensions, args.hash_bits, hashes, on_progress=advance
                ):
                    output.write(json.dumps(candidate, ensure_ascii=True) + "\n")
                    count += 1
                    matches += candidate["index_match"] is True
                files += 1
        progress.update(0, paths[-1] if paths else Path("(empty)"), count, matches, finished=True)
        print(
            f"Scanned {files} files; {count} candidates; {matches} index matches.", file=sys.stderr
        )
        return 0
    except (OSError, ValueError) as error:
        if progress:
            progress.abort()
        print(
            f"Error: {error}. Output may be incomplete; do not treat it as a successful run.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
