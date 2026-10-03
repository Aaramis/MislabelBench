#!/usr/bin/env python3
"""What shape does the Confidence column actually have?

parent_lhw_coeff is upstream code: a placement sitting on a taxon's stem is credited 0.51 to the parent
and 0.49 to the taxon, so such a call reports 0.510 whatever the evidence against the declared label. The
protocol attributes that artefact to SATIVA and says the fork inherits it, and every measurement of it so
far came from the fork alone. This checks both tools.

It also reports how concentrated the column is, which turns out to explain more than the artefact does.
If nearly every flag sits at one of two values then Confidence is close to a three-level variable, and a
threshold on it has almost no dynamic range -- it can separate those two levels and little else.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

STEM = 0.510


def confidences(path):
    out = []
    for line in Path(path).read_text(errors="replace").splitlines():
        if line.strip() and not line.startswith(";"):
            f = line.split("\t")
            if len(f) > 4:
                out.append(float(f[4]))
    return out


def describe(label, path):
    v = confidences(path)
    if not v:
        return {"tool": label, "flags": 0}
    c = Counter(v)
    stem, certain = c.get(STEM, 0), c.get(1.0, 0)
    print(f"{label}: {len(v)} flags")
    print(f"  at exactly {STEM}        {stem:5} ({100 * stem / len(v):5.1f}%)")
    print(f"  at exactly 1.000        {certain:5} ({100 * certain / len(v):5.1f}%)")
    print(f"  at one of those two     {stem + certain:5} "
          f"({100 * (stem + certain) / len(v):5.1f}%)")
    print(f"  anywhere else           {len(v) - stem - certain:5} "
          f"({100 * (len(v) - stem - certain) / len(v):5.1f}%)")
    return {"tool": label, "flags": len(v), "at_stem": stem, "at_one": certain,
            "share_at_two_values": round((stem + certain) / len(v), 4)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mis", action="append", required=True, metavar="LABEL=PATH",
                   help="repeatable, e.g. --mis upstream=/path/a.mis --mis fork=/path/b.mis")
    p.add_argument("--out")
    args = p.parse_args()

    rows = []
    for spec in args.mis:
        label, _, path = spec.partition("=")
        if not path:
            raise SystemExit(f"expected LABEL=PATH, got {spec!r}")
        rows.append(describe(label, path))
    if args.out:
        Path(args.out).write_text(json.dumps({"stem_value": STEM, "tools": rows}, indent=2))


if __name__ == "__main__":
    main()
