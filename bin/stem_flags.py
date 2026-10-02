#!/usr/bin/env python3
"""Are the 0.510 stem flags the same thing as the collateral flags?

Two findings so far look like they could be one: injection adds about 0.45 flags per injected
sequence on untouched neighbours, and 31.5 % of all flags sit at confidence 0.510 with no
placement weight inside the declared taxon. If the stem geometry is what produces the collateral
flags, the two sets should overlap heavily.
"""
import json
from pathlib import Path

base_mis = next(Path("results/baseline2k/runs").glob("*epang*/*.mis"))
base = {l.split("\t")[0] for l in base_mis.read_text().splitlines()
        if l.strip() and not l.startswith(";")}

tot = {"baseline_stem": 0, "baseline_other": 0,
       "collateral_stem": 0, "collateral_other": 0,
       "injected_stem": 0, "injected_other": 0}
for truth_p in sorted(Path("data/injected").glob("*/*.truth.json")):
    cell = truth_p.parent.name
    mis = Path(f"results/grid_fork/runs/{cell}__epang_T8_K25__rep1/"
               f"{cell}__epang_T8_K25__rep1.mis")
    if not mis.exists():
        continue
    inj = set(json.loads(truth_p.read_text())["injected"])
    for line in mis.read_text().splitlines():
        if not line.strip() or line.startswith(";"):
            continue
        f = line.split("\t")
        if len(f) < 9:
            continue
        name, conf = f[0], float(f[4])
        stem = "stem" if abs(conf - 0.510) < 1e-9 else "other"
        if name in inj:
            group = "injected"
        elif name in base:
            group = "baseline"
        else:
            group = "collateral"
        tot[f"{group}_{stem}"] += 1

print(f"{'group':12}{'at 0.510':>10}{'elsewhere':>11}{'share at 0.510':>16}")
for g in ("injected", "baseline", "collateral"):
    s, o = tot[f"{g}_stem"], tot[f"{g}_other"]
    print(f"{g:12}{s:10}{o:11}{100 * s / (s + o):15.1f}%")
