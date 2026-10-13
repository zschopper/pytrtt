"""Console entry point for any supported translation document."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pytrtt.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
