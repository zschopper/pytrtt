"""Independent fixtures for the read-only resource name investigation tool."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import find_resource_names
from scripts.find_resource_names import calculate_hash, load_hashes, scan_file


def test_known_hashes() -> None:
    assert calculate_hash(r"pc-w\local\locals.bin", 32) == 0x7CD333D3
    assert calculate_hash(r"pc-w\conduitmed_pc.raw", 32) == 0x625B0E2D
    assert calculate_hash("hello", 64) == 0xA430D84680AABD0B


def test_ascii_utf8_and_utf16_offsets(tmp_path: Path) -> None:
    name = r"pc-w\local\locals.bin"
    prefix = b"\xff\x00" + "ő".encode()
    data = prefix + name.encode() + b"\x00\xfe" + name.encode("utf-16-le") + b"\x00\x00"
    fixture = tmp_path / "data.bin"
    fixture.write_bytes(data)
    found = list(scan_file(fixture, frozenset({"bin"}), 32, {0x7CD333D3}))
    assert [(r["offset"], r["encoding"], r["name"]) for r in found] == [
        (len(prefix), "ascii/utf-8", name),
        (len(prefix) + len(name) + 2, "utf-16-le", name),
    ]
    assert all(r["index_match"] is True for r in found)
    assert fixture.read_bytes() == data


def test_relative_names_boundaries_and_case(tmp_path: Path) -> None:
    fixture = tmp_path / "data.bin"
    fixture.write_bytes(b"vo/ Lara.RAW\0vo/lara/hint.mul\0PC-W/local/locals.bin\0x.bin.bak\0")
    found = list(scan_file(fixture, frozenset({"raw", "mul", "bin"}), 32, None))
    assert [(r["name"], r["kind"]) for r in found] == [
        ("Lara.RAW", "basename"),
        ("vo/lara/hint.mul", "relative_path"),
        ("PC-W/local/locals.bin", "full_path"),
    ]
    assert all(r["index_match"] is None for r in found)


def test_long_input_empty_file_and_unmatched_hash(tmp_path: Path) -> None:
    fixture = tmp_path / "data.bin"
    fixture.write_bytes(b"\x00" * 65530 + b"pc-w/local/locals.bin\0")
    found = list(scan_file(fixture, frozenset({"bin"}), 32, set()))
    assert len(found) == 1
    assert found[0]["offset"] == 65530
    assert found[0]["index_match"] is False
    fixture.write_bytes(b"")
    assert list(scan_file(fixture, frozenset({"bin"}), 32, None)) == []


def test_hash_list_validation(tmp_path: Path) -> None:
    path = tmp_path / "hashes.txt"
    path.write_text("# Example\n7CD333D3\n0x625B0E2D\n7CD333D3\n")
    assert load_hashes(path, 32) == {0x7CD333D3, 0x625B0E2D}
    path.write_text("100000000\n")
    with pytest.raises(ValueError, match="line 1"):
        load_hashes(path, 32)


def test_cli_and_existing_output_protection(tmp_path: Path) -> None:
    fixture = tmp_path / "input.bin"
    fixture.write_bytes(b"pc-w\\local\\locals.bin\0")
    command = [sys.executable, "scripts/find_resource_names.py", str(fixture)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["hash"] == "7CD333D3"
    output = tmp_path / "output.jsonl"
    output.write_text("keep this\n")
    result = subprocess.run(
        [*command, "--output", str(output)], capture_output=True, text=True, check=False
    )
    assert result.returncode != 0
    assert output.read_text() == "keep this\n"


def test_cli_rejects_output_inside_input_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/find_resource_names.py",
            str(tmp_path),
            "--output",
            str(tmp_path / "report.jsonl"),
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert list(tmp_path.iterdir()) == []


def test_recursive_cli_skips_metadata_and_repeated_inputs(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    nested = inputs / "nested"
    nested.mkdir(parents=True)
    fixture = nested / "data.bin"
    fixture.write_bytes(b"pc-w\\conduitmed_pc.raw\0")
    metadata = inputs / ".svn"
    metadata.mkdir()
    (metadata / "data.bin").write_bytes(fixture.read_bytes())
    output = tmp_path / "report.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/find_resource_names.py",
            str(inputs),
            str(fixture),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["hash"] == "625B0E2D"
    assert "Scanned 1 files" in result.stderr


def test_chunk_edges_preserve_names_and_reject_partial_extensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(find_resource_names, "SCAN_CHUNK_SIZE", 24)
    name = r"pc-w\local\locals.bin"
    data = b"\0" * 17 + name.encode() + b"\0\xff" + name.encode("utf-16-le") + b"\0\0x.bin.bak\0"
    fixture = tmp_path / "data.bin"
    fixture.write_bytes(data)
    steps: list[int] = []
    found = list(scan_file(fixture, frozenset({"bin"}), 32, None, on_progress=steps.append))
    assert [r["name"] for r in found] == [name, name]
    assert [r["offset"] for r in found] == [17, 17 + len(name) + 2]
    assert sum(steps) == len(data) * 2
    assert len(steps) > 2


def test_progress_is_separate_from_json_output(tmp_path: Path) -> None:
    fixture = tmp_path / "data.bin"
    fixture.write_bytes(b"pc-w\\local\\locals.bin\0")
    hashes = tmp_path / "hashes.txt"
    hashes.write_text("7CD333D3\n")
    command = [
        sys.executable,
        "scripts/find_resource_names.py",
        str(fixture),
        "--hashes",
        str(hashes),
        "--progress",
        "always",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["index_match"] is True
    assert "100.0%" in result.stderr
    assert "candidates=1" in result.stderr
    assert "matches=1" in result.stderr
    result = subprocess.run([*command[:-1], "never"], capture_output=True, text=True, check=True)
    assert "%" not in result.stderr
    assert json.loads(result.stdout)["name"] == r"pc-w\local\locals.bin"
