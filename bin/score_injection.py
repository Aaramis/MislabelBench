#!/usr/bin/env python3
"""Score a run against injected truth, on two different thresholds.

SATIVA's `Confidence` scores the taxon it proposes instead. sativa-epang 0.10.2 adds
`OriginalLabelExclusion`, the placement weight that fell outside the declared taxon, which is
what the call actually rests on. The two come apart on stem placements, which report 0.510
whatever the evidence against the declared label. Whether the second separates injected
mislabels better than the first is the question this script exists to answer.

Nothing here is called a false positive. A sequence we did not inject is not known to be
correctly labelled, so flags on non-injected sequences are reported against the baseline run
on the un-injected database, as "added flags".
"""

import argparse
import csv
import json
import sys
from pathlib import Path

RANKS = ["domain", "phylum", "class", "order", "family", "genus", "species"]
BASE_COLUMNS = ["SeqID", "MislabeledLevel", "OriginalLabel", "ProposedLabel", "Confidence",
                "OriginalTaxonomyPath", "ProposedTaxonomyPath", "PerRankConfidence"]


def read_mis(path):
    """Rows of a SATIVA .mis. ';' lines are the header; the column count varies by version.

    A path that does not exist is an error, including for the baseline. It used to give an empty
    dict, so a glob that never expanded came out as nought flags and a recall of zero rather than
    as a failure, and an absent baseline came out as nought baseline flags, which would have
    counted every flag as added. What is optional is passing --baseline-mis at all.
    """
    rows = {}
    if not Path(path).exists():
        sys.exit(f"no such .mis: {path}")
    for line in Path(path).read_text(errors="replace").splitlines():
        if not line.strip() or line.startswith(";"):
            continue
        f = line.split("\t")
        if len(f) < len(BASE_COLUMNS):
            print(f"warning: skipping a row with {len(f)} fields", file=sys.stderr)
            continue
        row = dict(zip(BASE_COLUMNS, f[:len(BASE_COLUMNS)]))
        # 0.10.2 appends OriginalLabelExclusion; -ranktest appends another column after it.
        row["OriginalLabelExclusion"] = float(f[8]) if len(f) > 8 else None
        row["Confidence"] = float(row["Confidence"])
        rows[row["SeqID"]] = row
    return rows


def mismatch_rank(row, declared=None):
    """Rank index where declared and proposed first differ, from the paths rather than the
    MislabeledLevel name, which is a rank name and not a position.

    `declared` is the lineage the cell's own taxonomy gives this sequence, and it is preferred over
    the row's OriginalTaxonomyPath because that column does not always describe the sequence in
    column 1. SATIVA collapses identical sequences into taxonomic clusters and reports the
    cluster representative's path, marked `__TAXCLUSTER<n>__` in the lineage: measured over the
    whole grid, 2 642 of 127 172 flagged rows, 2.08 %, carry a path that is not a prefix of the
    named sequence's own lineage, and 185 of those are injected sequences -- 0.71 % of all injected
    rows. `recall_at_injected_rank` is read off this function, so the 0.71 % is the bound on how
    far that figure can be off; it is not corrected here because the declared path is preferred
    whenever the cell supplies one, which it always does.
    """
    a = (declared or row["OriginalTaxonomyPath"]).split(";")
    b = row["ProposedTaxonomyPath"].split(";")
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--truth", required=True, help="truth.json from inject_mislabels.py")
    p.add_argument("--mis", required=True, help=".mis from the injected run")
    p.add_argument("--baseline-mis", help=".mis from the same tool on the un-injected database")
    p.add_argument("--out", default="score.json")
    p.add_argument("--thresholds", default="0.0,0.5,0.6,0.7,0.8,0.9,0.95,0.99")
    args = p.parse_args()

    truth = json.loads(Path(args.truth).read_text())
    injected = truth["injected"]
    # The label each injected sequence actually carries in this cell, which is the wrong one by
    # definition. Used instead of the .mis row's OriginalTaxonomyPath wherever it is available,
    # because that column reports the taxonomic cluster's representative and not always the
    # sequence named beside it.
    declared_of = {name: rec["wrong"] for name, rec in injected.items()}
    flagged = read_mis(args.mis)
    baseline = set(read_mis(args.baseline_mis)) if args.baseline_mis else set()

    distance_rank = RANKS.index(truth["distance"])
    # The third question the protocol asks of every injected sequence: does the label the tool
    # proposes match the true one? Exact, the whole lineage; and at rank, agreement down to the
    # rank that was changed, which is the correction a user would apply. The first two questions,
    # flagged and at which rank, were answered here from the start; this one was not, and nothing
    # in the repository compared ProposedTaxonomyPath with rec["true"].
    true_of = {name: rec["true"] for name, rec in injected.items()}

    def proposed_matches(s, exact):
        a = true_of[s].split(";")
        b = flagged[s]["ProposedTaxonomyPath"].split(";")
        return a == b if exact else a[:distance_rank + 1] == b[:distance_rank + 1]
    # Error kind 6 adds bacterial sequences under an archaeal label. The taxonomy the tool is
    # given contains no bacteria, so it cannot name the true lineage at any rank and
    # mismatch_rank can never reach the domain. "Was it flagged at all" is the only meaningful
    # question there, so the at-rank metric is reported as absent rather than as zero.
    kind = truth.get("kind", "relabel")
    # Kind 7, a chimera, is like kind 6 for the rank questions: the label it carries is one parent's
    # and names a real clade it is half from, so "the rank at which the label is wrong" has no
    # answer. What can be asked is whether the lineage the tool proposes instead sides with the
    # other parent at the rank where the two differ -- that is, whether the placement went to the
    # unlabelled half.
    rank_metric_meaningful = kind not in ("foreign", "chimera")
    other_of = ({name: rec["lineage_b"] for name, rec in injected.items()}
                if kind == "chimera" else {})
    thresholds = [float(t) for t in args.thresholds.split(",")]
    have_exclusion = any(r["OriginalLabelExclusion"] is not None for r in flagged.values())

    def score(metric):
        out = []
        for t in thresholds:
            def passes(row):
                v = row["Confidence"] if metric == "confidence" else row["OriginalLabelExclusion"]
                return v is not None and v >= t
            hits = {s for s in injected if s in flagged and passes(flagged[s])}
            at_rank = {s for s in hits
                       if mismatch_rank(flagged[s], declared_of.get(s)) == distance_rank}
            label_exact = {s for s in hits if proposed_matches(s, True)}
            label_at_rank = {s for s in hits if proposed_matches(s, False)}
            sides_b = {s for s in hits if s in other_of
                       and (flagged[s]["ProposedTaxonomyPath"].split(";")[:distance_rank + 1]
                            == other_of[s].split(";")[:distance_rank + 1])}
            others = {s for s, r in flagged.items() if s not in injected and passes(r)}
            out.append({
                "threshold": t,
                "recall": len(hits) / len(injected) if injected else None,
                "recall_at_injected_rank": (len(at_rank) / len(injected)
                                            if injected and rank_metric_meaningful else None),
                "recall_label_correct": (len(label_exact) / len(injected)
                                         if injected and rank_metric_meaningful else None),
                "recall_label_correct_at_rank": (len(label_at_rank) / len(injected)
                                                 if injected and rank_metric_meaningful else None),
                "proposed_sides_with_other_parent": (len(sides_b) / len(hits) if hits else None)
                                                    if kind == "chimera" else None,
                "flags_on_non_injected": len(others),
                # Keyed on whether a baseline was given, not on whether it holds anything. An
                # empty baseline is a real answer -- a database the tool flags nothing in -- and
                # `if baseline` called it unmeasured while the record said baseline_flags: 0 two
                # fields below, so one record asserted both that the baseline was known and that
                # the added count could not be computed from it. Reproduced on an empty baseline
                # with two collateral flags: it reported null where the answer is 2.
                "added_vs_baseline": (len(others - baseline)
                                      if args.baseline_mis else None),
            })
        return out

    result = {
        "truth": args.truth,
        "mis": args.mis,
        "kind": kind,
        "distance": truth["distance"],
        "breakpoint": truth.get("breakpoint"),
        "rate": truth.get("rate"),
        "k": truth.get("k"),
        "seed": truth["seed"],
        "n_injected": len(injected),
        "n_flagged_total": len(flagged),
        "baseline_flags": len(baseline) if args.baseline_mis else None,
        # As a rate too: the protocol reports "the baseline flag rate before any injection", and a
        # count of 93 means nothing without the 2 023 it is counted over.
        "baseline_rate": (round(len(baseline) / truth["n_total"], 4)
                          if args.baseline_mis and truth.get("n_total") else None),
        "has_exclusion_column": have_exclusion,
        "by_confidence": score("confidence"),
        "by_exclusion": score("exclusion") if have_exclusion else None,
    }
    Path(args.out).write_text(json.dumps(result, indent=2))

    head = f"{kind} {truth['distance']} k={truth.get('k')} rate={truth.get('rate')}"
    print(f"{head}: {len(injected)} injected, {len(flagged)} flagged")
    for row in result["by_confidence"]:
        print(f"  conf >= {row['threshold']:.2f}  recall {row['recall']:.3f}  "
              f"other flags {row['flags_on_non_injected']}")


if __name__ == "__main__":
    main()
