"""Vercel entry point. The Python runtime looks for an ASGI `app` in here,
so this just puts the project root on sys.path and re-exports the real one.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

__all__ = ["app"]
