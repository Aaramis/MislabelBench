#!/usr/bin/env python3
"""Compare two conditions cell by cell, which is the only way these numbers can be compared.

Every condition runs on the same injected cells, so the two are paired and the question is whether
the per-cell difference is consistently signed, not whether two marginal means are further apart
than two marginal spreads. Comparing marginals throws the pairing away and hides a real effect
behind cell-to-cell variation that both conditions share: at k=10 the K=5 against K=25 difference
is 0.6 of a marginal standard deviation and far outside the paired one.

Recall is counted from the .mis files rather than read from a summary, so no averaging happens
before the pairing.
"""

import argparse
import json
import statistics as st
from math import comb
from collections import defaultdict
from pathlib import Path


def sign_test(wins, n):
    """Two-sided exact sign test, written out rather than pulled in: scipy is not a dependency of
    this repo and one binomial tail does not justify making it one."""
    if n == 0:
        return 1.0
    def binom(k):
        return comb(n, k) * 0.5 ** n
    tail = sum(binom(i) for i in range(min(wins, n - wins) + 1))
    return min(1.0, 2 * tail)


def flagged(path):
    return {l.split("\t")[0] for l in Path(path).read_text().splitlines()
            if l.strip() and not l.startswith(";")}


def per_cell_recall(injected_dir, runs_dir, condition):
    out = {}
    for truth_p in sorted(Path(injected_dir).glob("*/*.truth.json")):
        cell = truth_p.parent.name
        mis = Path(runs_dir) / f"{cell}__{condition}" / f"{cell}__{condition}.mis"
        if not mis.exists():
            continue
        truth = json.loads(truth_p.read_text())
        injected = set(truth["injected"])
        if not injected:
            continue
        hits = flagged(mis) & injected
        out[cell] = (truth["k"], len(hits) / len(injected))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--injected-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--a", required=True, help="condition suffix, the baseline of the pair")
    p.add_argument("--b", required=True, help="condition suffix compared against it")
    p.add_argument("--out")
    args = p.parse_args()

    a, b = (per_cell_recall(args.injected_dir, args.runs_dir, c) for c in (args.a, args.b))
    shared = sorted(set(a) & set(b))
    if not shared:
        raise SystemExit(f"no cell has both {args.a} and {args.b}")
    print(f"{len(shared)} cells have both conditions\n")

    groups = defaultdict(list)
    for cell in shared:
        k, ra = a[cell]
        groups[k].append(b[cell][1] - ra)

    # The per-cell differences are small against their own spread but consistently signed, so the
    # informative statistic is how often the sign goes one way, not the mean over the spread. A
    # two-sided sign test needs no assumption about the shape of the differences, which is what
    # recommends it over a t-statistic on 36 cells of very unequal difficulty.
    print(f"{'k':>3}{'cells':>7}{'mean b-a':>11}{'sd':>9}{'b>a':>5}{'a>b':>5}{'tied':>6}"
          f"{'sign p':>11}  reading")
    rows = []
    for k in sorted(groups):
        d = groups[k]
        m = st.mean(d)
        sd = st.stdev(d) if len(d) > 1 else 0.0
        wins = sum(1 for x in d if x > 0)
        ties = sum(1 for x in d if x == 0)
        n = len(d) - ties
        pv = sign_test(wins, n)
        reading = ("no difference" if pv > 0.05 else
                   f"b {'better' if wins * 2 > n else 'worse'} in most cells")
        print(f"{k:>3}{len(d):>7}{m:+11.4f}{sd:9.4f}{wins:>5}{n - wins:>5}{len(d) - n:>6}"
              f"{pv:11.2g}  {reading}")
        # cells_a_greater is recorded even though it is n - wins, because it was not, and a
        # throwaway script reading these records with .get("cells_a_greater", 0) produced a
        # published claim that no cell in 180 favours the comparator at any k. Eight do. A field
        # that has to be derived is a field someone will default to zero.
        rows.append({"k": k, "cells": len(d), "mean_difference": round(m, 4),
                     "sd_of_difference": round(sd, 4), "cells_b_greater": wins,
                     "cells_a_greater": n - wins, "cells_tied": len(d) - n,
                     "cells_compared": n, "sign_test_p": float(f"{pv:.3g}"),
                     "reading": reading})
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"a": args.a, "b": args.b, "n_cells": len(shared), "by_k": rows}, indent=2))


if __name__ == "__main__":
    main()
