#!/usr/bin/env python3
"""Are the 0.510 stem flags the same thing as the collateral flags?

Two findings looked like they could be one: injection adds about 0.45 flags per injected sequence
on untouched neighbours, and 31.3 % of all flags sit at confidence 0.510 with no placement weight
inside the declared taxon. If the stem geometry is what produces the collateral flags, the two sets
should overlap heavily. They do: 49.1 % of collateral flags are at 0.510 against 7.3 % of the
injected ones.

0.510 is tested by equality, which is only right if it is a point mass rather than a cluster. It is:
across the 25772 flags of the grid there are 8057 at exactly 0.510, 305 at 0.509 and 85 at 0.511,
against a background of ten to a hundred per bin either side. Two orders of magnitude, so widening
the window would add noise and not signal.
"""
import argparse
import json
import sys
from pathlib import Path


def flagged_names(path):
    return {l.split("\t")[0] for l in path.read_text(errors="replace").splitlines()
            if l.strip() and not l.startswith(";")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-dir", default="results/baseline2k/runs")
    p.add_argument("--injected-dir", default="data/injected")
    p.add_argument("--runs-dir", default="results/grid_fork/runs")
    p.add_argument("--condition", default="epang_T8_K25__rep1")
    args = p.parse_args()

    # sorted, and one match only. This was next(glob(...)): Path.glob returns directory order, so
    # with a second epang condition under baseline2k the baseline would have been whichever the
    # filesystem offered first, and the published shares would differ between machines for no
    # visible reason.
    found = sorted(Path(args.baseline_dir).glob(f"*{args.condition.split('__')[0]}*/*.mis"))
    if len(found) != 1:
        sys.exit(f"need exactly one baseline .mis under {args.baseline_dir}, found {len(found)}")
    base = flagged_names(found[0])

    tot = {f"{g}_{s}": 0 for g in ("injected", "baseline", "collateral") for s in ("stem", "other")}
    cells = 0
    for truth_p in sorted(Path(args.injected_dir).glob("*/*.truth.json")):
        cell = truth_p.parent.name
        mis = Path(args.runs_dir) / f"{cell}__{args.condition}" / f"{cell}__{args.condition}.mis"
        if not mis.exists():
            continue
        cells += 1
        inj = set(json.loads(truth_p.read_text())["injected"])
        for line in mis.read_text(errors="replace").splitlines():
            if not line.strip() or line.startswith(";"):
                continue
            f = line.split("\t")
            # The 9th column is the fork's. An upstream .mis has eight, and skipping its rows one
            # by one would have left every count at zero and divided by it below.
            if len(f) < 9:
                sys.exit(f"{mis} has a {len(f)}-column row; this needs the fork's 9-column format")
            name, conf = f[0], float(f[4])
            stem = "stem" if abs(conf - 0.510) < 1e-9 else "other"
            group = "injected" if name in inj else "baseline" if name in base else "collateral"
            tot[f"{group}_{stem}"] += 1

    if not cells:
        sys.exit(f"no cell matched {args.injected_dir}/*/*.truth.json with a run under {args.runs_dir}")
    print(f"{cells} cells")
    print(f"{'group':12}{'at 0.510':>10}{'elsewhere':>11}{'share at 0.510':>16}")
    for g in ("injected", "baseline", "collateral"):
        s, o = tot[f"{g}_stem"], tot[f"{g}_other"]
        share = f"{100 * s / (s + o):15.1f}%" if s + o else f"{'n/a':>16}"
        print(f"{g:12}{s:10}{o:11}{share}")


if __name__ == "__main__":
    main()
