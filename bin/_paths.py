#!/usr/bin/env python3
"""One helper, shared because five scripts had the same defect for the same reason.

Imported rather than copied: `sys.path[0]` is the script's own directory for every way these are
run -- `bin/x.py`, or `x.py` with `$BENCH_ROOT/bin` on PATH as bin/analyses.sh puts it -- so `import
_paths` resolves without anything on PYTHONPATH. `_timeit.py` is a wrapper command and not an import,
so this is the first module here, which is why the reasoning is written down.
"""

import glob
from pathlib import Path


def expand(pattern):
    """Paths matching `pattern`, which may be absolute.

    `Path(".").glob` raises `NotImplementedError: Non-relative patterns are unsupported` on an
    absolute pattern. Five gates passed their `--glob` flag straight to it, so the flag only ever
    worked for a caller already standing in the benchmark root, and pointing it at a scratch tree
    crashed inside pathlib. Worse, three of those five already carried a "nothing matched" guard
    that the crash made unreachable, so the failure looked exactly like the guard firing.
    """
    return [Path(p) for p in glob.glob(pattern)]
