#!/usr/bin/env python3
"""Compatibility launcher for source checkouts and the frozen service."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from skilldesk.skill_desk import main

if __name__ == "__main__":
    main()
