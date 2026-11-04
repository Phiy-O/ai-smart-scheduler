"""Backend package entry point."""

from pathlib import Path
import sys


_BACKEND_ROOT = str(Path(__file__).resolve().parent)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)
