#!/usr/bin/env python3
"""Paired tests of SATIVA-epang against SATIVA on the supplement figures' datasets.

One recall per dataset and tool, so the unit is the dataset and the two tools are paired on it. For
each family, the mean difference with a bootstrap 95 % interval (resampling datasets), the exact
sign test, and the exact Wilcoxon signed-rank test (null distribution by enumeration over the
midranks, so ties are handled exactly; scipy is not a dependency of this repo). Holm adjusts the
Wilcoxon p-values over all rows. Writes results/paired_stats.tsv.
"""
import json
import random
import statistics as st
import sys
from math import comb
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
RES = ROOT / "results"
EP, UP = "epang_T8_K25", "upstream_raxml_T8"


def flagged(path):
    return {l.split("\t")[0] for l in path.read_text(errors="replace").splitlines()
            if l.strip() and not l.startswith(";")}


def recalls(root_dir, data_dir, tool):
    out = {}
    for truth in sorted((ROOT / data_dir).glob("*/*.truth.json")):
        name = truth.parent.name
        mis = RES / root_dir / "runs" / f"{name}__{tool}__rep1" / f"{name}__{tool}__rep1.mis"
        if mis.exists():
            injected = set(json.loads(truth.read_text())["injected"])
            out[name] = len(flagged(mis) & injected) / len(injected)
    return out


def grid(tool):
    out = {}
    for score in sorted((RES / "grid_fork/runs").glob(f"*__{tool}__rep1/score.json")):
        s = json.loads(score.read_text())
        row = next(r for r in s["by_confidence"] if r["threshold"] == 0.0)
        out[score.parent.name.split("__")[0]] = (s["k"], s["distance"], row["recall"])
    return out


def clades(tool):
    cells = {}
    for c in json.loads((RES / f"clade_detection_{tool}.json").read_text())["per_clade"]:
        d = cells.setdefault(c["cell"], [0, 0])
        d[0] += c["detected"]
        d[1] += c["size"]
    return {k: d / n for k, (d, n) in cells.items()}


def sign_p(pos, n):
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(pos, n - pos) + 1)) * 0.5 ** n)


def wilcoxon_p(diffs):
    d = [x for x in diffs if abs(x) > 1e-12]
    n = len(d)
    if n == 0:
        return 1.0
    order = sorted(range(n), key=lambda i: abs(d[i]))
    rank2 = [0] * n  # twice the midrank, an integer
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(abs(d[order[j + 1]]) - abs(d[order[i]])) < 1e-12:
            j += 1
        for t in range(i, j + 1):
            rank2[order[t]] = i + j + 2
        i = j + 1
    total = sum(rank2)
    ways = [0] * (total + 1)
    ways[0] = 1
    for r in rank2:
        for s in range(total, r - 1, -1):
            ways[s] += ways[s - r]
    w = sum(r for r, x in zip(rank2, d) if x > 0)
    lo, hi = min(w, total - w), max(w, total - w)
    return min(1.0, (sum(ways[:lo + 1]) + sum(ways[hi:])) / 2 ** n)


def boot_ci(diffs, rng, reps=10000):
    n = len(diffs)
    means = sorted(sum(rng.choices(diffs, k=n)) / n for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def pair(a, b, names=None):
    names = sorted(set(a) & set(b)) if names is None else names
    return [a[n] - b[n] for n in names]


def main():
    ep_g, up_g = grid(EP), grid(UP)
    both = sorted(set(ep_g) & set(up_g))
    fam = {}
    fam["Sequence from another domain"] = pair(recalls("foreign", "data/foreign", EP),
                                               recalls("foreign", "data/foreign", UP))
    fam["Lineage stopping early"] = pair(recalls("ragged", "data/ragged", EP),
                                         recalls("ragged", "data/ragged", UP))
    fam["Whole taxon misnamed"] = pair(clades(EP), clades(UP))
    chim_e, chim_u = recalls("chimera", "data/chimera", EP), recalls("chimera", "data/chimera", UP)
    fam["Chimeras, all"] = pair(chim_e, chim_u)
    for dist in ("genus", "family", "order", "phylum"):
        names = [n for n in sorted(set(chim_e) & set(chim_u)) if n.startswith(f"chi_{dist}_")]
        fam[f"Chimeras, {dist}"] = pair(chim_e, chim_u, names)
    fam["Single mislabelled sequence (k = 1)"] = [ep_g[n][2] - up_g[n][2] for n in both if ep_g[n][0] == 1]
    fam["Right genus, wrong species"] = [ep_g[n][2] - up_g[n][2] for n in both if ep_g[n][1] == "species"]
    for k in (1, 2, 3, 5, 10):
        fam[f"Recall by k, k = {k}"] = [ep_g[n][2] - up_g[n][2] for n in both if ep_g[n][0] == k]
    fam["Recall by k, all 180 datasets"] = [ep_g[n][2] - up_g[n][2] for n in both]

    rng = random.Random(1)
    rows = []
    for name, d in fam.items():
        pos, neg = sum(x > 1e-12 for x in d), sum(x < -1e-12 for x in d)
        lo, hi = boot_ci(d, rng)
        rows.append([name, len(d), st.mean(d), lo, hi, pos, neg, len(d) - pos - neg,
                     sign_p(pos, pos + neg), wilcoxon_p(d)])
    order = sorted(range(len(rows)), key=lambda i: rows[i][9])
    holm, run = {}, 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, rows[i][9] * (len(rows) - r)))
        holm[i] = run
    head = ["family", "datasets", "mean_diff", "ci_low", "ci_high", "epang_better", "sativa_better",
            "ties", "sign_p", "wilcoxon_p", "wilcoxon_p_holm"]
    lines = ["\t".join(head)]
    for i, r in enumerate(rows):
        lines.append("\t".join([r[0], str(r[1])] + [f"{x:.4f}" for x in r[2:5]] + [str(x) for x in r[5:8]]
                               + [f"{r[8]:.2g}", f"{r[9]:.2g}", f"{holm[i]:.2g}"]))
    (RES / "paired_stats.tsv").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


main()
