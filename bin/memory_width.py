#!/usr/bin/env python3
"""Peak memory per sequence against the alignment width, from the width cells' run records.

Reads results/width/runs/<cell>__<condition>__rep1/run.json (n_seqs, max_rss_mb, the largest
process's peak) and data/width/datasets.json (aln_len per cell), and fits, per condition, peak =
a + b x n x columns by least squares, so that b is the coefficient per sequence and per column that
the memory law states and the article quotes. The fit is over the width axis at one n; a and b are
printed with the per-width residuals, which is how a reader sees whether a line is what the points
make.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path


def fit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    return my - b * mx, b


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs-dir", default="results/width/runs")
    p.add_argument("--datasets", default="data/width/datasets.json")
    p.add_argument("--out")
    args = p.parse_args()

    width_of = {d["name"]: d["aln_len"] for d in json.loads(Path(args.datasets).read_text())["datasets"]}
    rows = defaultdict(list)
    for rj in sorted(Path(args.runs_dir).glob("*/run.json")):
        cell, cond, _ = rj.parent.name.split("__")
        r = json.loads(rj.read_text())
        if r.get("max_rss_mb") is None or cell not in width_of:
            continue
        rows[cond].append({"cell": cell, "columns": width_of[cell], "n_seqs": r["n_seqs"],
                           "max_rss_mb": r["max_rss_mb"]})
    if not rows:
        raise SystemExit(f"no width run with a peak under {args.runs_dir}")

    out = {}
    for cond, rs in sorted(rows.items()):
        rs.sort(key=lambda r: r["columns"])
        xs = [r["columns"] * r["n_seqs"] for r in rs]
        ys = [r["max_rss_mb"] for r in rs]
        a, b = fit(xs, ys)
        print(f"{cond}: peak = {a:.1f} MB + {b * 1024:.3f} kB per sequence per column, {len(rs)} widths")
        print(f"{'columns':>9}{'n':>7}{'peak MB':>10}{'MB/seq':>9}{'fit MB':>9}{'resid':>8}")
        for r, x, y in zip(rs, xs, ys):
            pred = a + b * x
            r.update({"mb_per_seq": round(y / r["n_seqs"], 4), "fit_mb": round(pred, 1),
                      "residual_mb": round(y - pred, 1)})
            print(f"{r['columns']:>9}{r['n_seqs']:>7}{y:>10.1f}{r['mb_per_seq']:>9.3f}{pred:>9.1f}{y - pred:>8.1f}")
        out[cond] = {"intercept_mb": round(a, 2), "kb_per_seq_per_column": round(b * 1024, 4),
                     "rows": rs}
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
