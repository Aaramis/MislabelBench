#!/usr/bin/env python3
"""Split the fork's advantage at k=2 into the engine and the fold scheme.

The fork beats upstream by a wide margin at k=2 and the cause was not identified: the engine
measured at k=1 looked worth 0.018 and the fold count 0.035, which leaves most of the gap
unaccounted for. k=1 is the worst place to look, because no sibling keeps the correct label and
neither tool can detect anything, so both sit on the floor.

epang_T8_Kexact separates the two cleanly. One sequence per fold is upstream's own leave-one-out
protocol run through EPA-ng, so:

    Kexact against upstream_raxml_T8   the engine, with the fold scheme removed
    Kexact against epang_T8_K25        the fold scheme, with the engine held fixed

Recall is reported at threshold 0 as well as at 0.9, because a difference at 0 is a difference in
which sequences are flagged at all and cannot be an artefact of the fork's confidence column.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

CONDITIONS = ["upstream_raxml_T8", "epang_T8_Kexact", "epang_T8_K5", "epang_T8_K25"]


def score(scorer, truth, mis):
    # To a temporary file, not /dev/stdout: the scorer prints a human line as well as writing the
    # record, so the two arrive interleaved and the JSON no longer parses.
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        out = subprocess.run([scorer, "--truth", str(truth), "--mis", str(mis), "--out", tmp.name],
                             capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit(f"{scorer} failed on {mis}: {out.stderr.strip()}")
        return json.loads(Path(tmp.name).read_text())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--injected-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--scorer", default="score_injection.py")
    p.add_argument("--out", default="results/kexact_decomposition.json")
    args = p.parse_args()

    # Whichever cells have a Kexact run. One cell is a measurement, not a distribution, and the
    # file saying so is better than a reader assuming three seeds are behind it.
    cells = sorted(d.name.split("__")[0] for d in Path(args.runs_dir).glob("*__epang_T8_Kexact__rep1"))
    if not cells:
        sys.exit(f"no epang_T8_Kexact run under {args.runs_dir}")

    rows = []
    for cell in cells:
        truth = Path(args.injected_dir) / cell / f"{cell}.truth.json"
        rec = {"cell": cell, "k": json.loads(truth.read_text())["k"], "recall": {}}
        for cond in CONDITIONS:
            run = Path(args.runs_dir) / f"{cell}__{cond}__rep1"
            mis = sorted(run.glob("*.mis"))
            if not mis:
                rec["recall"][cond] = None
                continue
            s = score(args.scorer, truth, mis[0])
            at = {t["threshold"]: t["recall"] for t in s["by_confidence"]}
            rec["recall"][cond] = {"flags": s["n_flagged_total"], "at_0": at[0.0], "at_0.9": at[0.9]}
        r = rec["recall"]
        if r["epang_T8_Kexact"] and r["upstream_raxml_T8"]:
            rec["engine_at_0"] = round(r["epang_T8_Kexact"]["at_0"] - r["upstream_raxml_T8"]["at_0"], 4)
        if r["epang_T8_Kexact"] and r["epang_T8_K25"]:
            rec["folds_at_0"] = round(r["epang_T8_K25"]["at_0"] - r["epang_T8_Kexact"]["at_0"], 4)
        rows.append(rec)

    Path(args.out).write_text(json.dumps({"cells": rows}, indent=2))
    for rec in rows:
        print(f"{rec['cell']} (k={rec['k']})")
        for cond, v in rec["recall"].items():
            print(f"  {cond:22} " + ("absent" if not v else
                  f"flags {v['flags']:4}  recall@0 {v['at_0']:.3f}  @0.9 {v['at_0.9']:.3f}"))
        print(f"  engine, folds removed : {rec.get('engine_at_0')}")
        print(f"  folds, engine fixed   : {rec.get('folds_at_0')}")


if __name__ == "__main__":
    main()
