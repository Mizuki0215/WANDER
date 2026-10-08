"""容許 `python -m wander ...` 直接執行 CLI。"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
