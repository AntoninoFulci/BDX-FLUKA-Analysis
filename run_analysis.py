#!/usr/bin/env python

import sys
from pathlib import Path

# Ensure src on sys.path then delegate
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from analysis import main


if __name__ == "__main__":
    main()
