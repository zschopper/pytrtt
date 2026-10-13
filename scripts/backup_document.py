"""Preserve a document before editing it; never overwrite an earlier backup."""

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    args = parser.parse_args()
    document: Path = args.document.resolve(strict=True)
    if not document.is_file():
        parser.error("The document must be a regular file.")
    stamp = datetime.now(ZoneInfo("Europe/Budapest")).strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = document.parent / ".backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f"{stamp}-{document.name}"
    with backup.open("xb") as stream:
        stream.write(document.read_bytes())
    print(backup)


if __name__ == "__main__":
    main()
