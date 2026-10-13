"""Recalculate candidate filename hashes and compare them with known filelists."""

import argparse
import csv
import importlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    hash_module = importlib.import_module("scripts.find_resource_names")
except ModuleNotFoundError:
    hash_module = importlib.import_module("find_resource_names")
calculate_hash = hash_module.calculate_hash


@dataclass
class ReviewStats:
    checked: int = 0
    newly_known: int = 0
    still_candidates: int = 0
    already_known: int = 0
    invalidated_known: int = 0
    new_matches: list[tuple[str, str, str]] = field(default_factory=list)


def load_review_offsets(path: Path) -> dict[tuple[str, str], int]:
    offsets: dict[tuple[str, str], int] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"exe", "offset", "name"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"Review TSV must contain columns: {', '.join(sorted(required))}")
        for number, row in enumerate(reader, 2):
            try:
                key = (row["exe"], row["name"])
                offset = int(row["offset"], 10)
            except (TypeError, ValueError) as error:
                raise ValueError(f"Invalid executable offset at TSV line {number}") from error
            offsets[key] = min(offsets.get(key, offset), offset)
    return offsets


def review_candidates(
    candidate_file: Path,
    review_file: Path,
    hashes_by_list: dict[str, set[int]],
    profiles: dict[str, tuple[int, list[str]]],
) -> ReviewStats:
    """Update offsets and hashes in place, promoting candidates with known hashes."""
    offsets = load_review_offsets(review_file)
    content = candidate_file.read_text(encoding="utf-8-sig")
    output: list[str] = []
    current_exe: str | None = None
    profile_names = {name.casefold(): name for name in profiles}
    stats = ReviewStats()

    for number, line in enumerate(content.splitlines(), 1):
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1]
            if section_name.casefold().endswith(".exe"):
                section_name = section_name[:-4]
            current_exe = profile_names.get(section_name.casefold())
            output.append(line)
            continue
        if not line.startswith(("CANDIDATE\t", "KNOWN\t")):
            output.append(line)
            continue
        if current_exe not in profiles:
            raise ValueError(
                f"Unknown executable section at candidate file line {number}: {current_exe}"
            )

        fields = line.split("\t")
        status = fields[0]
        bits, list_names = profiles[current_exe]
        if len(fields) == 4:
            _, old_hash, name, _match_status = fields
            try:
                offset = offsets[(current_exe, name)]
            except KeyError as error:
                raise ValueError(
                    f"No EXE offset for {current_exe} candidate at line {number}: {name}"
                ) from error
        elif len(fields) >= 5:
            _, offset_text, old_hash, name, *_metadata = fields
            if not re.fullmatch(r"[0-9a-fA-F]+", offset_text):
                raise ValueError(f"Invalid hexadecimal EXE offset at candidate file line {number}")
            offset = int(offset_text, 16)
        else:
            raise ValueError(f"Malformed CANDIDATE row at candidate file line {number}")

        calculated = calculate_hash(name, bits)
        matched = any(
            calculated in hashes_by_list.get(list_name, set()) for list_name in list_names
        )
        new_status = "KNOWN" if matched else "CANDIDATE"
        if matched:
            if status == "CANDIDATE":
                stats.newly_known += 1
                stats.new_matches.append((current_exe, f"{calculated:0{bits // 4}X}", name))
            else:
                stats.already_known += 1
        else:
            if status == "KNOWN":
                stats.invalidated_known += 1
            else:
                stats.still_candidates += 1
        stats.checked += 1
        output.append(
            f"{new_status}\t{offset:08X}\t{calculated:0{bits // 4}X}\t{name}"
            f"\tindex-match: {str(matched)}"
        )

    if output != content.splitlines():
        _write_atomically(candidate_file, "\n".join(output) + "\n")
    return stats


def _write_atomically(path: Path, text: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _load_hashes(path: Path) -> set[int]:
    values: set[int] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        hash_text = line.partition("\t")[0].strip()
        if not hash_text or hash_text.startswith("#"):
            continue
        if not re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]+", hash_text):
            raise ValueError(f"Invalid hexadecimal hash at {path}:{number}")
        values.add(int(hash_text.removeprefix("0x").removeprefix("0X"), 16))
    return values


def _load_inputs(
    summary_path: Path, filelists_dir: Path
) -> tuple[dict[str, set[int]], dict[str, tuple[int, list[str]]]]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    hashes_by_list: dict[str, set[int]] = {}
    profiles: dict[str, tuple[int, list[str]]] = {}
    for executable in summary["executables"]:
        name = executable["exe"]
        list_names = executable["associated_filelists"]
        profiles[name] = (int(executable["hash_bits"]), list_names)
        for list_name in list_names:
            if list_name in hashes_by_list:
                continue
            list_path = filelists_dir / f"{list_name}_filelist.txt"
            if not list_path.is_file():
                continue
            hashes_by_list[list_name] = _load_hashes(list_path)
    return hashes_by_list, profiles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("work/runs/exe-search/m1/filelist-regex/name-candidates.txt"),
    )
    parser.add_argument(
        "--review",
        type=Path,
        default=Path("work/runs/exe-search/m1/filelist-regex/candidate-review.tsv"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("work/runs/exe-search/m1/filelist-regex/summary.json"),
    )
    parser.add_argument("--filelists-dir", type=Path, default=Path("references/filelists"))
    args = parser.parse_args(argv)
    try:
        hashes_by_list, profiles = _load_inputs(args.summary, args.filelists_dir)
        stats = review_candidates(args.candidates, args.review, hashes_by_list, profiles)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    for exe, value, name in stats.new_matches:
        print(f"NEW KNOWN\t{exe}\t{value}\t{name}")
    print(
        f"Checked {stats.checked} rows; {stats.newly_known} newly known; "
        f"{stats.still_candidates} remain candidates; {stats.already_known} still known; "
        f"{stats.invalidated_known} known hashes no longer match."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
