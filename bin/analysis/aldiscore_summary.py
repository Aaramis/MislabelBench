#!/usr/bin/env python3
"""The alignment difficulty of each set, and the foreign cells against the subset they were built on.

slurm/checks/aldiscore.sh writes one JSON line per set to results/aldiscore/scores.jsonl, keeping the
predictor's whole stdout because its format was not known before the first run; it turned out to be
one number per set, the predicted difficulty from 0 to 1. This reads those lines, refuses a set whose
stdout is not exactly one number, and reports the foreign cells as a difference from gtdb_arc2k, the
2 023 sequences every cell adds its donors to: that difference is the "before and after" the protocol
asks of error kind 6. The cmalign bit-score gap (bin/analysis/foreign_score_vs_flag.py) stays beside it as the
per-sequence measurement; this one is per set.
"""

import argparse
import json
import re
import statistics as st
from pathlib import Path

BASE = "gtdb_arc2k"
CELL = re.compile(r"^fgn_r([0-9.]+)_s(\d+)$")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scores", default="results/aldiscore/scores.jsonl")
    p.add_argument("--out")
    args = p.parse_args()

    sets = {}
    for line in Path(args.scores).read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        # The whole stdout must be the number: a warning printed beside it would mean the set was
        # not scored as given, and the numbers the job pulled out of the text are not consulted.
        try:
            difficulty = float(rec["stdout"].strip())
        except ValueError:
            raise SystemExit(f"{rec['set']}: expected one number from the predictor, got "
                             f"{rec['stdout'][:200]!r}")
        sets[rec["set"]] = {"n_sequences": rec["n_sequences"], "difficulty": difficulty}
    if not sets:
        raise SystemExit(f"no set scored in {args.scores}")

    print(f"{'set':26}{'n':>7}{'difficulty':>12}")
    for name, s in sets.items():
        print(f"{name:26}{s['n_sequences']:>7}{s['difficulty']:>12.4f}")

    foreign = {}
    if BASE in sets:
        base = sets[BASE]["difficulty"]
        by_rate = {}
        for name, s in sets.items():
            m = CELL.match(name)
            if m:
                by_rate.setdefault(m.group(1), []).append(s["difficulty"] - base)
        print(f"\nforeign cells against {BASE} ({base:.4f}):")
        print(f"{'rate':>8}{'cells':>7}{'mean delta':>12}{'min':>9}{'max':>9}")
        for rate, deltas in sorted(by_rate.items(), key=lambda kv: float(kv[0])):
            foreign[rate] = {"cells": len(deltas), "mean_delta": round(st.mean(deltas), 5),
                             "min_delta": round(min(deltas), 5), "max_delta": round(max(deltas), 5)}
            print(f"{rate:>8}{len(deltas):>7}{st.mean(deltas):>12.5f}{min(deltas):>9.5f}{max(deltas):>9.5f}")
    else:
        print(f"\n{BASE} not scored, so the foreign cells have nothing to be measured against")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"scores": args.scores, "base": BASE, "sets": sets, "foreign_vs_base": foreign},
            indent=2) + "\n")


if __name__ == "__main__":
    main()
