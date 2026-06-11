import sys
import os

# ── Allow running from project root ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from src.cli.cli import main

if __name__ == "__main__":
    main()
