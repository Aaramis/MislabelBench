#!/bin/bash
# Build the injection grid for the archaeal subset, and the datasets.json the harness reads.
#
# The injection only rewrites labels, so every cell shares one alignment and differs only in
# its .tax. That also means a cell is reproducible from its seed alone.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-$HOME/bench}"

cd "$BENCH_ROOT/data/gtdb"
OUT="$BENCH_ROOT/data/injected"
mkdir -p "$OUT"

# Idempotent: a cell that already exists is left alone. The grid gained its class axis after
# 150 cells had been computed, and rebuilding all of them to add 30 would have thrown away a
# day of compute for nothing. A cell is a function of its name, so skipping is safe.

ALN="$BENCH_ROOT/data/gtdb/gtdb_arc2k.fasta"
TAX="$BENCH_ROOT/data/gtdb/gtdb_arc2k.tax"

for dist in species genus family order class phylum; do
  for rate in 0.01 0.05; do
    for k in 1 2 3 5 10; do
      for seed in 1 2 3; do
        name="inj_${dist}_r${rate}_k${k}_s${seed}"
        d="$OUT/$name"
        [ -s "$d/$name.tax" ] && continue
        mkdir -p "$d"
        python3 "$BENCH_ROOT/bin/inject_mislabels.py" "$TAX" \
          --distance "$dist" --rate "$rate" --k "$k" --seed "$seed" \
          --prefix "$d/$name" >/dev/null 2>"$d/warn.txt" || {
            echo "FAILED $name" >&2; continue; }
        ln -sf "$ALN" "$d/$name.fasta"
      done
    done
  done
done

python3 - "$OUT" "$ALN" <<'PY'
import json, sys
from pathlib import Path
out, aln = Path(sys.argv[1]), sys.argv[2]
n_seqs = sum(1 for l in open(aln) if l.startswith(">"))
w = len("".join(open(aln).read().split(">")[1].split("\n")[1:]))
sets = []
for d in sorted(out.iterdir()):
    tax = d / f"{d.name}.tax"
    if tax.exists():
        sets.append({"name": d.name, "n_seqs": n_seqs, "aln_len": w,
                     "fasta": str(d / f"{d.name}.fasta"), "tax": str(tax)})
json.dump({"source": "gtdb_arc2k, injected grid", "datasets": sets},
          open(out / "datasets.json", "w"), indent=2)
print(f"{len(sets)} injected datasets, {n_seqs} sequences each, width {w}")
PY

grep -l . "$OUT"/*/warn.txt 2>/dev/null | head -5 | while read f; do
  echo "warning in $(basename "$(dirname "$f")"): $(head -1 "$f")"
done || true
