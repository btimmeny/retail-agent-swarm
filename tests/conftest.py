"""Shared pytest fixtures."""

import sys
from pathlib import Path

# Ensure the repo root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
