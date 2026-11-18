"""`python -m mp4tool` 入口 / entry point for `python -m mp4tool`."""
import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
