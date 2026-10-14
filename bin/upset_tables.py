#!/usr/bin/env python3
"""The UpSet panel as tables: one SATIVA baseline on the unmodified database, then both tools after injection.

Every sequence that is in the baseline, injected, or flagged by either tool is classed as a baseline
flag (in the baseline, not injected), an injected error, or a collateral flag (neither), and by who
flags it after injection. Means per dataset, by confidence floor, injection rate and distance.
"""
import collections
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import background_stability as bs

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
RUNS = ROOT / "results/grid_fork/runs"
COND = lambda c: f"{c}/{c}.mis"
BASE = ROOT / "results/baseline2k/runs/gtdb_arc2k__upstream_raxml_T8__rep1/gtdb_arc2k__upstream_raxml_T8__rep1.mis"
CLASSES = [(k, u, e) for k in ("baseline", "injected", "collateral") for u, e in
           ((1, 1), (1, 0), (0, 1), (0, 0)) if not (k == "collateral" and not u and not e)]
cells = []
for d in sorted((ROOT / "data/injected").glob("inj_*")):
    t = json.loads((d / f"{d.name}.truth.json").read_text())
    cells.append((d.name, d.name.split("_")[2], t["distance"], set(t["injected"])))

print("class = kind, flagged by SATIVA, flagged by SATIVA-epang; mean per dataset\n")
for floor in (0.0, 0.511):
    base = set(bs.flagged(BASE, floor))
    here = collections.defaultdict(list)
    for name, rate, dist, inj in cells:
        u = set(bs.flagged(RUNS / COND(f"{name}__upstream_raxml_T8__rep1"), floor))
        e = set(bs.flagged(RUNS / COND(f"{name}__epang_T8_K25__rep1"), floor))
        c = collections.Counter()
        for s in base | inj | u | e:
            kind = "baseline" if s in base and s not in inj else "injected" if s in inj else "collateral"
            c[(kind, int(s in u), int(s in e))] += 1
        row = {k: c[k] for k in CLASSES}
        row["n_injected"] = len(inj)
        for key in ((rate,), (rate, dist), ("all",), ("all", dist)):
            here[key].append(row)
    print(f"confidence >= {floor}, baseline of {len(base)} SATIVA flags")
    print("group\tn\tinjected\t" + "\t".join("/".join(map(str, k)) for k in CLASSES))
    for key in sorted(here, key=lambda k: (k[0] != "all", k)):
        rows = here[key]
        print("_".join(key) + f"\t{len(rows)}\t{st.mean(r['n_injected'] for r in rows):.1f}\t"
              + "\t".join(f"{st.mean(r[k] for r in rows):.1f}" for k in CLASSES))
    print()
