#!/usr/bin/env python
"""Entry point for outlier-detector CLI."""

import sys
from pathlib import Path

# Add src to path so imports work without installing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from outlier_detector.cli import app

if __name__ == "__main__":
    app()
