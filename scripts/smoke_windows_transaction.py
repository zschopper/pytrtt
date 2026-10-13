"""Exercise Bigfile transaction, rollback, and locking on native Windows."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pytrtt.archives.bigfile_v1 import BigFileEntry, BigFileIndex
from pytrtt.archives.transaction import (
    TransactionError,
    _operation_lock,
    apply_write_plan,
    restore_write_plan,
)
from pytrtt.archives.write_plan import BigFileReplacement, plan_replacements


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_fixture(data_dir: Path) -> tuple[BigFileIndex, bytes]:
    """Create a minimal, independent Bigfile v1 fixture."""
    entry = BigFileEntry(0, 0x12345678, 8, 2, 0xFFFFFFE1, 0xABCDEF01)
    original = bytearray(0x2000)
    original[:4] = struct.pack("<I", 1)
    original[4:8] = struct.pack("<I", entry.hash)
    original[8:24] = struct.pack("<4I", entry.length, entry.location, entry.locale, entry.unknown)
    original[0x1000:0x1008] = b"original"
    (data_dir / "bigfile.000").write_bytes(original)
    return BigFileIndex((entry,)), bytes(original)


def run_smoke_test() -> None:
    """Run the transactional round trip and Windows lock contention check."""
    if os.name != "nt":
        raise SystemExit("Run this smoke test with native Windows Python, not WSL Python.")

    with tempfile.TemporaryDirectory(prefix="pytrtt-transaction-smoke-") as temporary:
        root = Path(temporary)
        data_dir = root / "game-data"
        data_dir.mkdir()
        index, original = write_fixture(data_dir)
        archive = data_dir / "bigfile.000"
        transaction_dir = root / "transaction-001"
        plan = plan_replacements(
            data_dir,
            index,
            (BigFileReplacement("Windows smoke text", 0x12345678, 0xFFFFFFE1, b"translated"),),
            0x4000,
        )

        with _operation_lock(data_dir.resolve()):
            try:
                apply_write_plan(data_dir, plan, transaction_dir)
            except TransactionError as error:
                if "another write operation" not in str(error):
                    raise
            else:
                raise AssertionError("lock contention did not prevent a second write")
        if transaction_dir.exists():
            raise AssertionError("lock contention created a transaction directory")

        apply_write_plan(data_dir, plan, transaction_dir)
        journal = json.loads((transaction_dir / "journal.json").read_text(encoding="utf-8"))
        if journal["status"] != "applied":
            raise AssertionError("journal did not record the applied state")
        if sha256(archive) != journal["files"]["bigfile.000"]["staged_sha256"]:
            raise AssertionError("installed archive does not match the journal")

        restore_write_plan(data_dir, transaction_dir)
        restore_write_plan(data_dir, transaction_dir)
        if archive.read_bytes() != original:
            raise AssertionError("restored bytes differ from the original fixture")
        journal = json.loads((transaction_dir / "journal.json").read_text(encoding="utf-8"))
        if journal["status"] != "restored":
            raise AssertionError("journal did not record the restored state")

    print("PASS: native Windows transaction, lock contention, idempotent restore, exact bytes")


if __name__ == "__main__":
    run_smoke_test()
