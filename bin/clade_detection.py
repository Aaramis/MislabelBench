#!/usr/bin/env python3
"""Error kind 3: does detection track how compact the relabelled clade is?

Protocol.md 2.2 states the limit rather than scoring it: with a whole taxon relabelled, nothing
correctly labelled remains to confirm it, so leave-one-out's usual handle is gone. What is left is
whether the clade is distinguishable from the taxon it has been assigned to, and bin/inject_clade.py
measures that as separation -- mean identity within the clade minus mean identity to the recipient.

This reports detection against that, per clade, which is what makes the characterisation falsifiable:
if detection does not track separation, compactness is not the variable and Protocol.md 2.2's account
of the kind is wrong. Recall is reported per clade and not pooled, because a clade is the unit that
was relabelled and pooling 226 sequences over 54 clades of different sizes would weight by size.
"""

import argparse
import json
import statistics as st
import sys
from pathlib import Path


def flagged(path):
    return {l.split("\t")[0] for l in Path(path).read_text(errors="replace").splitlines()
            if l.strip() and not l.startswith(";")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--clade-dir", required=True)
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--condition", required=True)
    p.add_argument("--bins", type=int, default=4)
    p.add_argument("--out")
    args = p.parse_args()

    rows, cells = [], 0
    for truth_p in sorted(Path(args.clade_dir).glob("*/*.truth.json")):
        cell = truth_p.parent.name
        mis = Path(args.runs_dir) / f"{cell}__{args.condition}" / f"{cell}__{args.condition}.mis"
        if not mis.exists():
            continue
        cells += 1
        truth = json.loads(truth_p.read_text())
        hits = flagged(mis)
        # Which sequences belong to which clade, from the truth rather than from the taxonomy: the
        # injected file no longer carries the clade's own label anywhere.
        members = {}
        for name, rec in truth["injected"].items():
            members.setdefault(rec["true"], []).append(name)
        for c in truth["clades"]:
            m = members[c["clade"]]
            found = sum(1 for n in m if n in hits)
            rows.append({"cell": cell, "distance": truth["distance"], "seed": truth["seed"],
                         "clade": c["clade"].split(";")[-1], "size": len(m),
                         "within": c["within"], "to_recipient": c["to_recipient"],
                         "separation": c["separation"],
                         "detected": found, "recall": round(found / len(m), 4)})

    if not cells:
        sys.exit(f"no cell under {args.clade_dir} has a run for {args.condition}")

    print(f"{cells} cells, {len(rows)} clades, {sum(r['size'] for r in rows)} sequences, "
          f"condition {args.condition}")
    print("\nper clade, ordered by how well it can anchor itself")
    print(f"{'distance':9}{'size':>5}{'within':>8}{'recip':>8}{'separation':>11}{'found':>7}{'recall':>8}")
    for r in sorted(rows, key=lambda x: x["separation"]):
        print(f"{r['distance']:9}{r['size']:>5}{r['within']:>8.4f}{r['to_recipient']:>8.4f}"
              f"{r['separation']:>+11.4f}{r['detected']:>7}{r['recall']:>8.3f}")

    # Two gradients, because the first measurement showed the protocol's variable is not the one
    # that predicts detection and `within` is. Equal-count bins rather than equal-width: neither
    # quantity is uniformly distributed and a fixed grid would put most clades in one bin.
    for var, label in (("separation", "separation from the recipient, Protocol.md 2.2's variable"),
                       ("within", "cohesion within the clade")):
        order = sorted(rows, key=lambda x: x[var])
        per = max(1, len(order) // args.bins)
        print(f"\nrecall by {label}")
        print(f"{'range':>22}{'clades':>8}{'seqs':>7}{'detected':>10}{'recall':>8}")
        for i in range(0, len(order), per):
            band = order[i:i + per] if i + per < len(order) else order[i:]
            seqs = sum(b["size"] for b in band)
            det = sum(b["detected"] for b in band)
            print(f"{f'{band[0][var]:+.4f} to {band[-1][var]:+.4f}':>22}"
                  f"{len(band):>8}{seqs:>7}{det:>10}{det / seqs:>8.3f}")
            if i + per >= len(order):
                break

    # The contrast the gradients come down to, as one line each way.
    for lab, g in (("members nearly identical, within >= 0.99",
                    [r for r in rows if r["within"] >= 0.99]),
                   ("diffuse clade, within < 0.99",
                    [r for r in rows if r["within"] < 0.99])):
        if g:
            seqs, det = sum(x["size"] for x in g), sum(x["detected"] for x in g)
            print(f"  {lab:42} {len(g):3} clades {seqs:4} seqs  recall {det / seqs:.3f}")

    # The json keeps the separation gradient, since it is the protocol's variable and a reader
    # comparing against 2.2 needs it in the record even though it is not the one that predicts.
    order = sorted(rows, key=lambda x: x["separation"])
    per = max(1, len(order) // args.bins)
    summary = []
    for i in range(0, len(order), per):
        band = order[i:i + per] if i + per < len(order) else order[i:]
        seqs, det = sum(b["size"] for b in band), sum(b["detected"] for b in band)
        summary.append({"separation_low": band[0]["separation"],
                        "separation_high": band[-1]["separation"], "clades": len(band),
                        "sequences": seqs, "detected": det, "recall": round(det / seqs, 4)})
        if i + per >= len(order):
            break

    neg = [r for r in rows if r["separation"] < 0]
    if neg:
        d, s = sum(r["detected"] for r in neg), sum(r["size"] for r in neg)
        print(f"\nclades closer to their recipient than to themselves: {len(neg)}, "
              f"{d} of {s} sequences detected = {d / s:.3f}")

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"condition": args.condition, "cells": cells, "clades": len(rows),
             "by_separation": summary, "per_clade": rows}, indent=2))


if __name__ == "__main__":
    main()
