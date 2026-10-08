#!/usr/bin/env python3
"""Recompute every recall the grid summaries publish, by a second route, and require agreement.

The paper's central claim is that the fork detects shared mislabels upstream misses, and the number
behind it is recall per cell in results/grid_summary_*.json. That number passes through
score_injection.py and then aggregate_grid.py, and both are tested -- but tested against fixtures
written by the same hand that wrote them, so a misunderstanding of what the .mis means would sit in
the code, the fixture and the paper at once.

This computes the same quantity from the two primary files, the cell's truth.json and the run's .mis,
in a few lines that deliberately share nothing with those scripts: a sequence counts as detected when
the run reports it with a Confidence at or above the threshold, and a cell's recall is the fraction of
its injected sequences that are. Then it compares against every by_confidence row of every summary.

Finding 98 is why this exists. The exclusion column's headline number was attached to the wrong
threshold, and no amount of rereading the producing script would have shown it -- the script was
right. Recomputing from the format is what found it, and the same method applied here agrees to the
fourth decimal on all ten headline values. A gate is the way to keep that true.
"""

import argparse
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

CONFIDENCE = 4  # column 5 of the .mis, 0-based


def cell_counts(truth_path, mis_path, threshold):
    """Recall and collateral flags for one cell, from the two primary files.

    Both columns of the published table, because checking one of a pair is how a table ends up half
    verified: recall is the share of injected sequences the run reports, collateral is every other
    sequence it reports. A flag that is neither would mean a name in the .mis that is in no cell.
    """
    injected = set(json.loads(truth_path.read_text())["injected"])
    flagged = set()
    for line in mis_path.read_text().splitlines():
        if line.startswith(";") or not line.strip():
            continue
        f = line.split("\t")
        if float(f[CONFIDENCE]) >= threshold:
            flagged.add(f[0])
    if not injected:
        return None, None
    return len(injected & flagged) / len(injected), len(flagged - injected)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--injected-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--summary", action="append", required=True,
                   metavar="CONDITION=PATH", help="repeatable")
    args = p.parse_args()

    checked, problems = 0, []
    for spec in args.summary:
        cond, _, path = spec.partition("=")
        summary = json.loads(Path(path).read_text())
        # Checked once here and not inside the loop below, which an empty injected directory never
        # enters: the guard was there first and the second pass over summary["rows"] still raised a
        # KeyError from pathlib's depth with nothing naming the file.
        if "rows" not in summary:
            sys.exit(f"{path} has no 'rows': it is not a grid summary")
        mine = defaultdict(list)
        for truth_path in sorted(Path(args.injected_dir).glob("*/*.truth.json")):
            cell = truth_path.parent.name
            mis = Path(args.runs_dir) / f"{cell}__{cond}" / f"{cell}__{cond}.mis"
            if not mis.exists():
                continue
            t = json.loads(truth_path.read_text())
            for row in summary["rows"]:
                if row["metric"] != "by_confidence":
                    continue
                # .get on both sides, not indexing: the foreign cells have no k and their summary
                # rows carry k: null, so a cell is matched on the fields it has. Indexing crashed
                # here and left error kind 6 outside this check entirely.
                if any(row.get(f) != t.get(f) for f in ("distance", "k", "rate")):
                    continue
                r, collateral = cell_counts(truth_path, mis, row["threshold"])
                if r is not None:
                    mine[(row["distance"], row["k"], row["rate"], row["threshold"])].append(
                        (r, collateral))

        for row in summary["rows"]:
            if row["metric"] != "by_confidence":
                continue
            key = (row["distance"], row["k"], row["rate"], row["threshold"])
            if key not in mine:
                continue
            checked += 2
            recalls = [r for r, _ in mine[key]]
            collateral = [c for _, c in mine[key]]
            # The summaries round to four places, so agreement is to that and not to float equality.
            if abs(round(st.mean(recalls), 4) - row["recall_mean"]) > 5e-5:
                problems.append(f"{cond} {key}: recall {round(st.mean(recalls), 4)} recomputed "
                                f"against {row['recall_mean']} published")
            # The collateral column is a mean of integers and is published rounded to whole flags
            # in some rows and to a fraction in others, so compare at the published precision.
            published = row.get("flags_on_non_injected_mean")
            if published is not None and abs(st.mean(collateral) - published) > 0.5:
                problems.append(f"{cond} {key}: collateral {st.mean(collateral):.2f} recomputed "
                                f"against {published} published")

    # A check that compared nothing must not report success.
    if not checked:
        sys.exit("no published recall could be recomputed; check --injected-dir and --runs-dir")
    print(f"{checked} published values recomputed from truth.json and .mis -- recall and collateral "
          f"flags for every by_confidence row -- {checked - len(problems)} agree")
    for pb in problems[:10]:
        print(f"  {pb}", file=sys.stderr)
    if problems:
        sys.exit(f"{len(problems)} published value(s) a second implementation disagrees with")


if __name__ == "__main__":
    main()
