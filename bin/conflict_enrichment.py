#!/usr/bin/env python3
"""Are a tool's flags enriched in the one kind of truth un-injected data offers?

Agreement between the two tools is 0.67 on the 7051-sequence set, and each makes calls the other does
not. Whether those extra calls are sensitivity or noise looks unanswerable without injected truth, but
there is a partial truth in the data: groups of byte-identical sequences carrying conflicting labels, in
which at least one member must be wrong whatever the cause.

Membership in such a group is weak evidence about any single sequence -- one member is wrong, not all of
them. It is however *symmetrically* weak, applying to both tools alike, so the comparison between them
is informative even where the absolute reading is not.

Reports an exact binomial tail rather than a ratio, because the counts are small and a 4x enrichment on
eight observations needs a p-value beside it.
"""

import argparse
import json
from collections import defaultdict
from math import exp, lgamma, log, log1p
from pathlib import Path


def read_fasta(path):
    out, name, chunks = {}, None, []
    for line in Path(path).read_text().splitlines():
        if line.startswith(">"):
            if name:
                out[name] = "".join(chunks)
            name, chunks = line[1:].split()[0], []
        else:
            chunks.append(line.strip())
    if name:
        out[name] = "".join(chunks)
    return out


def flagged(path):
    return {l.split("\t")[0] for l in Path(path).read_text(errors="replace").splitlines()
            if l.strip() and not l.startswith(";")}


def tail_ge(k, n, p):
    """Exact P(X >= k) for X ~ Binomial(n, p), summed in log space.

    No scipy: one binomial tail does not justify a dependency. In log space because the direct form
    with comb() overflows for the unflagged group, where n is 6531 and comb(6531, i) does not fit in
    a float -- which it did, on the first run.
    """
    if k <= 0:
        return 1.0
    if p <= 0.0 or p >= 1.0 or k > n:
        return 0.0 if k > n else 1.0
    total = 0.0
    for i in range(k, n + 1):
        logp = (lgamma(n + 1) - lgamma(i + 1) - lgamma(n - i + 1)
                + i * log(p) + (n - i) * log1p(-p))
        total += exp(logp)
    return min(1.0, total)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--alignment", required=True)
    p.add_argument("--taxonomy", required=True)
    p.add_argument("--mis-a", required=True, help="the comparator's .mis")
    p.add_argument("--mis-b", required=True, help="the fork's .mis")
    p.add_argument("--out")
    args = p.parse_args()

    aln = read_fasta(args.alignment)
    tax = {l.partition("\t")[0]: l.partition("\t")[2]
           for l in Path(args.taxonomy).read_text().splitlines() if l.strip()}

    by_row = defaultdict(list)
    for name, seq in aln.items():
        if name in tax:
            by_row[seq].append(name)
    conflict = {n for g in by_row.values()
                if len(g) > 1 and len({tax[x] for x in g}) > 1 for n in g}

    a, b = flagged(args.mis_a), flagged(args.mis_b)
    total = len(tax)
    base = len(conflict) / total
    sets = {"both": a & b, "a only": a - b, "b only": b - a,
            "neither": set(tax) - a - b}

    print(f"{total} sequences, {len(conflict)} in a conflicting identical group ({100*base:.1f}%)")
    print(f"{'flag group':12}{'n':>6}{'in conflict':>13}{'expected':>10}"
          f"{'enrichment':>12}{'P(>=obs)':>11}")
    rows = []
    for name, s in sets.items():
        if not s:
            continue
        k, n = len(s & conflict), len(s)
        exp = n * base
        pv = tail_ge(k, n, base)
        print(f"{name:12}{n:>6}{k:>13}{exp:10.1f}{(k / n) / base:11.2f}x{pv:11.2g}")
        rows.append({"group": name, "n": n, "in_conflict": k, "expected": round(exp, 2),
                     "enrichment": round((k / n) / base, 3), "p_ge": float(f"{pv:.3g}")})

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"sequences": total, "in_conflict": len(conflict), "background": round(base, 5),
             "groups": rows}, indent=2))


if __name__ == "__main__":
    main()
