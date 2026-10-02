#!/usr/bin/env python3
"""Does injection change which *other* sequences get flagged?

Daniel's point on the background flag rate: reporting added flags as a count assumes the
pre-existing flags stay put. They need not. Injecting a wrong label moves a sequence in the
reference tree, which can change the placement of its neighbours, so a baseline flag can
disappear and an untouched sequence can start being flagged.

For every grid cell this compares the set of flagged non-injected sequences against the
baseline set on the same database:

  retained  flagged in both
  lost      flagged at baseline, no longer flagged after injection
  gained    not flagged at baseline, flagged after injection, and not injected

`gained` is the quantity the protocol calls an added flag. `lost` is the one it did not ask
about, and a large `lost` would mean the baseline is not a fixed reference point to subtract.
"""

import argparse
import json
from pathlib import Path


def flagged(mis_path):
    out = {}
    for line in Path(mis_path).read_text().splitlines():
        if line.startswith(";") or not line.strip():
            continue
        f = line.split("\t")
        out[f[0]] = f[1]
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", required=True, help=".mis of the un-injected run")
    p.add_argument("--runs", required=True, help="directory of <cell>/<cell>.mis")
    p.add_argument("--injected-dir", required=True, help="directory of <cell>/<cell>.truth.json")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    base = set(flagged(args.baseline))
    rows = []
    for mis in sorted(Path(args.runs).glob("*/*.mis")):
        cell = mis.parent.name.split("__")[0]
        truth = Path(args.injected_dir) / cell / f"{cell}.truth.json"
        if not truth.exists():
            continue
        injected = set(json.loads(truth.read_text())["injected"])
        after = set(flagged(mis)) - injected
        # An injected sequence flagged at baseline was already suspect before we touched it,
        # so it cannot count as lost: exclude it from the baseline side too.
        ref = base - injected
        rows.append({
            "cell": cell,
            "n_injected": len(injected),
            "baseline": len(ref),
            "retained": len(ref & after),
            "lost": len(ref - after),
            "gained": len(after - ref),
        })

    hdr = ["cell", "n_injected", "baseline", "retained", "lost", "gained"]
    with open(args.out, "w") as fh:
        fh.write("\t".join(hdr) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[h]) for h in hdr) + "\n")

    n = len(rows)
    print(f"{n} cells against a baseline of {len(base)} flags")
    for key in ("lost", "gained"):
        v = sorted(r[key] for r in rows)
        print(f"  {key}: median {v[n // 2]}, max {v[-1]}, mean {sum(v) / n:.1f}")


if __name__ == "__main__":
    main()
