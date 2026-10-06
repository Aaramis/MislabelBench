#!/usr/bin/env python3
"""Rebuild the minimal-case campaign's conclusions from the case directories.

Eleven sweeps ran while the script that produced them was still changing, so their verdicts.tsv
files carry three different first columns: per_family, case, or sequence. Joining them by hand is
how a reader ends up believing a table they cannot check, and every claim README makes about this
campaign was read off those files by eye.

So this reads the directories instead of the tables. Each case directory holds a case.json saying
which sequence was mislabelled and how large the case was, and one subdirectory per arm holding that
arm's .mis -- which lists flagged rows only, so the sequence being absent is the miss. The verdicts
written during the run are left alone and are not an input here: a second reading of the same
evidence is worth more than a tidier copy of the first.

The two numbers README rests on are printed and written out: how often the fork driving RAxML agrees
with upstream, which is what says the difference is the engine rather than the scoring code, and
which cases the fork driving EPA-ng wins alone.
"""

import argparse
import json
import sys
from pathlib import Path

ARMS = ["upstream_raxml", "fork_epang", "fork_raxml"]


def verdict(arm_dir, sequence):
    mis = arm_dir / "case.mis"
    if not mis.is_file():
        # The arm failed. One did, to the OOM reaper, and a summary that silently called that a
        # miss would have turned a lost measurement into a result.
        return "absent"
    for line in mis.read_text().splitlines():
        if line.startswith(";") or not line.strip():
            continue
        f = line.split("\t")
        if f and f[0] == sequence:
            return f"flag:{f[4]}"
    return "miss"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cases-dir", default="results/minimal_case")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    rows = []
    for case_json in sorted(Path(args.cases_dir).glob("*/*/case.json")):
        c = json.loads(case_json.read_text())
        d = case_json.parent
        rows.append({
            "sweep": d.parent.name,
            "case": d.name,
            "sequence": c["sequence"],
            "n_seqs": c["n_seqs"],
            "n_wrong_labels": c.get("n_wrong_labels", 1),
            **{arm: verdict(d / arm, c["sequence"]) for arm in ARMS},
        })

    if not rows:
        sys.exit(f"no case.json under {args.cases_dir}/*/*/")

    # The claim that the difference is the engine: the fork driving RAxML should land where upstream
    # lands. Counted only where both arms ran, since an absent arm agrees with nothing.
    both = [r for r in rows if "absent" not in (r["upstream_raxml"], r["fork_raxml"])]
    same = [r for r in both
            if r["fork_raxml"].split(":")[0] == r["upstream_raxml"].split(":")[0]]
    won = [r for r in rows if r["fork_epang"].startswith("flag")
           and r["upstream_raxml"] == "miss"]

    out = Path(args.out)
    with out.open("w") as fh:
        cols = ["sweep", "case", "sequence", "n_seqs", "n_wrong_labels", *ARMS]
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")
    Path(str(out) + ".json").write_text(json.dumps({
        "n_cases": len(rows),
        "fork_raxml_agrees_with_upstream": len(same),
        "fork_raxml_comparable": len(both),
        "fork_epang_wins_alone": [{"sweep": r["sweep"], "case": r["case"],
                                   "n_seqs": r["n_seqs"],
                                   "n_wrong_labels": r["n_wrong_labels"]} for r in won],
    }, indent=2) + "\n")

    print(f"{len(rows)} cases")
    print(f"  the fork driving RAxML agrees with upstream in {len(same)} of {len(both)}")
    print(f"  the fork driving EPA-ng flags where upstream misses in {len(won)}:")
    for r in won:
        print(f"    {r['sweep']}/{r['case']}: {r['n_seqs']} sequences, "
              f"{r['n_wrong_labels']} wrong labels")


if __name__ == "__main__":
    main()
