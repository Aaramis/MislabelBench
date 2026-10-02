#!/usr/bin/env python3
"""Is every cell of a grid present, or did one vanish?

main.nf joins four output channels on the meta map, and Nextflow's join discards unmatched elements
silently. A cell whose outputs failed to pair would disappear from the results with nothing said: the
run count would simply be lower, and every table below would be computed over whatever survived.

errorStrategy is terminate, so in practice a failed task stops the run rather than dropping a cell.
That is a property of the config rather than of the join, and it is the sort of protection that holds
until someone sets errorStrategy to ignore for a good reason.

So this enumerates the cells the grid should hold, from the same manifest and condition list the job
was given, and insists each one has a run record. It exits non-zero when any is missing, which is the
right behaviour even while a grid is still running: an incomplete grid's tables are not final.
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--datasets-json", required=True)
    p.add_argument("--conditions", required=True, help="comma separated, as passed to the job")
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--replicates", type=int, default=1)
    args = p.parse_args()

    names = [d["name"] for d in json.loads(Path(args.datasets_json).read_text())["datasets"]]
    runs = Path(args.runs_dir)
    problems = 0
    for cond in [c.strip() for c in args.conditions.split(",")]:
        want = {f"{n}__{cond}__rep{r}" for n in names for r in range(1, args.replicates + 1)}
        have = {d.name for d in runs.glob(f"*__{cond}__rep*") if d.is_dir()}
        missing, extra = sorted(want - have), sorted(have - want)
        state = "ok" if not missing and not extra else "INCOMPLETE"
        print(f"  {state:11} {cond:22} {len(have)}/{len(want)}")
        for m in missing[:3]:
            print(f"    missing {m}", file=sys.stderr)
        for e in extra[:3]:
            print(f"    unexpected {e}", file=sys.stderr)
        problems += len(missing) + len(extra)

    if problems:
        print(f"{problems} cell(s) missing or unexpected in {runs}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
