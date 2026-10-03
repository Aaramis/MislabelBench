#!/usr/bin/env python3
"""When the two tools disagree, which one is right?

On un-injected data this is not answerable: the extra flags fall on sequences nobody touched, so the only
handle is whether they land in the reference's own label conflicts, which is weak evidence per sequence.
On the injected grid there is truth, and the question becomes arithmetic.

For every cell, each flagged sequence falls into one of four buckets by which tools flagged it, and within
each bucket it is either injected or not. A tool whose unique calls are mostly injected is finding
mislabels the other misses. A tool whose unique calls are mostly untouched sequences is adding noise --
or finding pre-existing errors, which injected truth cannot distinguish from noise and which is why the
word used here is "untouched" rather than "wrong".
"""

import argparse
import json
import sys
from pathlib import Path


def flagged(path):
    return {l.split("\t")[0] for l in Path(path).read_text(errors="replace").splitlines()
            if l.strip() and not l.startswith(";")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--injected-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--condition-a", required=True, help="the comparator's condition suffix")
    p.add_argument("--condition-b", required=True, help="the fork's condition suffix")
    p.add_argument("--out")
    args = p.parse_args()

    def empty():
        return {k: {"injected": 0, "untouched": 0} for k in ("both", "a only", "b only")}

    tally = empty()
    # Which distances are present is reported, not assumed: a partially finished grid is covered in
    # directory order, so it over-represents whichever distances sort first. The first run of this
    # held class, family and genus complete and neither species nor phylum, the two extremes of recall.
    by_distance = {}
    cells = 0
    missed_by_both = 0
    total_injected = 0

    for truth_p in sorted(Path(args.injected_dir).glob("*/*.truth.json")):
        cell = truth_p.parent.name
        pa = Path(args.runs_dir) / f"{cell}__{args.condition_a}" / f"{cell}__{args.condition_a}.mis"
        pb = Path(args.runs_dir) / f"{cell}__{args.condition_b}" / f"{cell}__{args.condition_b}.mis"
        if not (pa.exists() and pb.exists()):
            continue
        cells += 1
        truth = json.loads(truth_p.read_text())
        injected = set(truth["injected"])
        dist = truth.get("distance", "?")
        by_distance.setdefault(dist, {"cells": 0, "tally": empty()})
        by_distance[dist]["cells"] += 1
        total_injected += len(injected)
        a, b = flagged(pa), flagged(pb)
        for name, bucket in [(n, "both") for n in a & b] + \
                            [(n, "a only") for n in a - b] + \
                            [(n, "b only") for n in b - a]:
            key = "injected" if name in injected else "untouched"
            tally[bucket][key] += 1
            by_distance[dist]["tally"][bucket][key] += 1
        missed_by_both += len(injected - a - b)

    if not cells:
        raise SystemExit("no cell has both conditions")

    print(f"{cells} cells have both conditions, {total_injected} injected sequences in them")
    print(f"{'flagged by':12}{'total':>8}{'injected':>10}{'untouched':>11}{'share injected':>16}")
    for bucket in ("both", "a only", "b only"):
        t = tally[bucket]
        n = t["injected"] + t["untouched"]
        label = {"a only": f"{args.condition_a.split('__')[0]} only",
                 "b only": f"{args.condition_b.split('__')[0]} only"}.get(bucket, bucket)
        print(f"{label[:12]:12}{n:>8}{t['injected']:>10}{t['untouched']:>11}"
              f"{(100 * t['injected'] / n if n else 0):15.1f}%")
    print(f"injected and flagged by neither: {missed_by_both} "
          f"({100 * missed_by_both / total_injected:.1f}% of injected)")

    print(f"\ndistances present, with the share of each tool's unique flags that is injected:")
    print(f"{'distance':10}{'cells':>7}{'a only':>10}{'b only':>10}")
    for dist in sorted(by_distance):
        d = by_distance[dist]
        out = f"{dist:10}{d['cells']:>7}"
        for bucket in ("a only", "b only"):
            t = d["tally"][bucket]
            n = t["injected"] + t["untouched"]
            out += f"{(100 * t['injected'] / n if n else 0):9.1f}%"
        print(out)
    if len(by_distance) < 6:
        print(f"  only {len(by_distance)} of 6 distances present; the grid is not finished and the "
              "cells it holds are not a random subset", file=sys.stderr)

    if args.out:
        Path(args.out).write_text(json.dumps({
            "condition_a": args.condition_a, "condition_b": args.condition_b,
            "cells": cells, "injected_total": total_injected,
            "buckets": tally, "missed_by_both": missed_by_both,
            "distances": {k: {"cells": v["cells"], "buckets": v["tally"]}
                          for k, v in sorted(by_distance.items())}}, indent=2))


if __name__ == "__main__":
    main()
