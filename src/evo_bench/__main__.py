"""Allow ``python -m evo_bench``."""

from __future__ import annotations

import sys

from evo_bench.cli import main

if __name__ == "__main__":
    sys.exit(main())
