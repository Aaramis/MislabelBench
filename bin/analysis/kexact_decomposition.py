#!/usr/bin/env python3
"""Split the fork's advantage at k=2 into the engine and the fold scheme.

The fork beats upstream by a wide margin at k=2 and the cause was not identified: the engine
measured at k=1 looked worth 0.018 and the fold count 0.035, which leaves most of the gap
unaccounted for. k=1 is the worst place to look, and not for the reason first given here. It is a
ceiling, not a floor: with one sequence relabelled per group the rest of the group keeps the right
label and both tools detect over 92% of injections, so there is no headroom for either to differ.
k=10 is the other end, both near 12%, where there is nothing left to find. The fork's advantage
lives in between and peaks at k=2.

epang_T8_Kexact separates the two cleanly. One sequence per fold is upstream's own leave-one-out
protocol run through EPA-ng, so:

    Kexact against upstream_raxml_T8   the engine, with the fold scheme removed
    Kexact against epang_T8_K25        the fold scheme, with the engine held fixed

Recall is reported at threshold 0 as well as at 0.9, because a difference at 0 is a difference in
which sequences are flagged at all and cannot be an artefact of the fork's confidence column.

Two recalls that differ do not say which sequences they differ on, and that question had been
answered by hand. The names are recorded here instead, with the fork's confidence and exclusion on
the ones only it catches beside the same figures on the ones both catch: if the two distributions
match, the fork is not straining on its extra calls and the difference is entirely the other tool's.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

CONDITIONS = ["upstream_raxml_T8", "epang_T8_Kexact", "epang_T8_K5", "epang_T8_K25"]


def flagged(mis):
    """Sequence -> (confidence, exclusion) for every row the tool wrote.

    The .mis holds flagged rows only, so membership of this mapping is the flag at threshold 0.
    Exclusion is the ninth column and upstream has eight, hence the None.
    """
    out = {}
    for line in Path(mis).read_text().splitlines():
        if line.startswith(";") or not line.strip():
            continue
        f = line.split("\t")
        out[f[0]] = (float(f[4]), float(f[8]) if len(f) > 8 else None)
    return out


def median(values):
    v = sorted(values)
    if not v:
        return None
    mid = len(v) // 2
    return round(v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2, 3)


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
    p.add_argument("--scorer", default=str(Path(__file__).with_name("score_injection.py")))
    # Required, with no default. A default that names a committed record means running the script
    # from the repository root without --out overwrites that record, which is how grid_summary.json
    # and shape.json were each created and then silently replaced. Third instance of the same trap.
    p.add_argument("--out", required=True)
    # The sequences only the fork catches, as 'name<TAB>wrong label', which is what
    # slurm/detection/minimal_case.sh takes to hunt for a case small enough to send to someone. Written by
    # this script rather than typed, because a hand-made list of 64 names and lineages is the kind
    # of file that is wrong once and then believed.
    p.add_argument("--pairs-out", help="write the fork-only sequences and their injected labels here")
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
        rows_by_cond = {}
        for cond in CONDITIONS:
            run = Path(args.runs_dir) / f"{cell}__{cond}__rep1"
            mis = sorted(run.glob("*.mis"))
            if not mis:
                rec["recall"][cond] = None
                continue
            rows_by_cond[cond] = flagged(mis[0])
            s = score(args.scorer, truth, mis[0])
            at = {t["threshold"]: t["recall"] for t in s["by_confidence"]}
            rec["recall"][cond] = {"flags": s["n_flagged_total"], "at_0": at[0.0], "at_0.9": at[0.9]}
        r = rec["recall"]
        if r["epang_T8_Kexact"] and r["upstream_raxml_T8"]:
            rec["engine_at_0"] = round(r["epang_T8_Kexact"]["at_0"] - r["upstream_raxml_T8"]["at_0"], 4)
        if r["epang_T8_Kexact"] and r["epang_T8_K25"]:
            rec["folds_at_0"] = round(r["epang_T8_K25"]["at_0"] - r["epang_T8_Kexact"]["at_0"], 4)

        # Restricted to the injected sequences, because an extra flag on an untouched sequence has
        # no truth to be judged against and is the subject of disagreement_truth.py instead.
        fork, up = rows_by_cond.get("epang_T8_Kexact"), rows_by_cond.get("upstream_raxml_T8")
        if fork is not None and up is not None:
            injected = set(json.loads(truth.read_text())["injected"])
            fork_only = sorted((injected & set(fork)) - set(up))
            both = sorted(injected & set(fork) & set(up))
            rec["one_sided"] = {
                "fork_only": fork_only,
                "upstream_only": sorted((injected & set(up)) - set(fork)),
                "n_both": len(both),
                "fork_only_median_confidence": median([fork[n][0] for n in fork_only]),
                "both_median_confidence": median([fork[n][0] for n in both]),
                "fork_only_median_exclusion": median([fork[n][1] for n in fork_only
                                                      if fork[n][1] is not None]),
                "both_median_exclusion": median([fork[n][1] for n in both
                                                 if fork[n][1] is not None]),
                # Per sequence and per tool, for the table the co-author's question needs: which
                # sequences, in which cell, at what confidence in each engine. A missing tool is
                # the sequence not being flagged there, written as null and not as zero.
                "pairs": {n: {"fork_confidence": fork[n][0] if n in fork else None,
                              "fork_exclusion": fork[n][1] if n in fork else None,
                              "upstream_confidence": up[n][0] if n in up else None}
                          for n in sorted(set(fork_only) | (injected & set(up)) - set(fork))},
            }
        rows.append(rec)

    Path(args.out).write_text(json.dumps({"cells": rows}, indent=2))

    if args.pairs_out:
        # One row per one-sided sequence, both directions, with the cell it comes from and each
        # tool's confidence. The first version wrote the fork-only names and their wrong label and
        # nothing else, so the 84 names were on file and the cell and the confidences were not.
        lines = ["cell\tside\tsequence\twrong_label\tfork_confidence\tfork_exclusion"
                 "\tupstream_confidence"]
        n_rows = 0
        for rec in rows:
            os = rec.get("one_sided")
            if not os:
                continue
            truth = json.loads((Path(args.injected_dir) / rec["cell"] /
                                f"{rec['cell']}.truth.json").read_text())["injected"]
            for side, names in (("fork_only", os["fork_only"]), ("upstream_only", os["upstream_only"])):
                for n in names:
                    pr = os["pairs"][n]
                    lines.append(f"{rec['cell']}\t{side}\t{n}\t{truth[n]['wrong']}\t"
                                 f"{pr['fork_confidence']}\t{pr['fork_exclusion']}\t"
                                 f"{pr['upstream_confidence']}")
                    n_rows += 1
        Path(args.pairs_out).write_text("\n".join(lines) + "\n")
        print(f"{n_rows} one-sided sequences written to {args.pairs_out}")
    for rec in rows:
        print(f"{rec['cell']} (k={rec['k']})")
        for cond, v in rec["recall"].items():
            print(f"  {cond:22} " + ("absent" if not v else
                  f"flags {v['flags']:4}  recall@0 {v['at_0']:.3f}  @0.9 {v['at_0.9']:.3f}"))
        print(f"  engine, folds removed : {rec.get('engine_at_0')}")
        print(f"  folds, engine fixed   : {rec.get('folds_at_0')}")
        os = rec.get("one_sided")
        if os:
            print(f"  injected caught by the fork only: {len(os['fork_only'])}, "
                  f"by upstream only: {len(os['upstream_only'])}, by both: {os['n_both']}")
            print(f"  the fork's confidence on its own calls {os['fork_only_median_confidence']} "
                  f"against {os['both_median_confidence']} on the shared ones, "
                  f"exclusion {os['fork_only_median_exclusion']} against "
                  f"{os['both_median_exclusion']}")


if __name__ == "__main__":
    main()
