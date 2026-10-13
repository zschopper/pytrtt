"""Check the development toolchain without game data."""

import struct
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

pytestmark = pytest.mark.toolchain


def test_project_python_version() -> None:
    assert sys.version_info[:2] == (3, 13)


def test_utf8_binary_fixture_io(tmp_path: Path) -> None:
    content = "Árvíztűrő tükörfúrógép: ŐőŰű".encode()
    fixture = tmp_path / "fixture.bin"
    fixture.write_bytes(struct.pack("<I", len(content)) + content)
    data = fixture.read_bytes()
    assert struct.unpack_from("<I", data)[0] == len(data) - 4
    assert data[4:].decode("utf-8") == "Árvíztűrő tükörfúrógép: ŐőŰű"


@given(st.integers(min_value=0, max_value=2**32 - 1))
def test_property_test_runner(value: int) -> None:
    assert struct.unpack("<I", struct.pack("<I", value))[0] == value
