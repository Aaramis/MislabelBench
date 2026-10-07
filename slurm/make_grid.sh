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

# The cell alignments are symlinks to the one file every cell shares. Relative, so a clone of this
# repository resolves them wherever it sits: committed as absolute paths they named one machine under
# one home, which is the defect this script's own comment below warns about for manifests. Every cell
# directory is one level under $OUT, so the path from any of them to the alignment is the same.
ALN_REL=$(python3 -c 'import os, sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' \
          "$ALN" "$OUT/any_cell")

# Rates: the two Protocol.md 2.3 defines. A 2 % arm was generated and then removed, the repository
# being scoped to exactly what the protocol defines. What that arm would have bought is recorded in
# D125 and D128: the axis is not flat, 0.042 recall at 1 % against 0.148 at 5 % at k=10, and 2 % is the
# only one of the two missing rates that is informative at every k -- at 0.5 % a cell holds one donor
# group at k=10, where recall is a single draw. If the axis is ever widened, 2 % is the one to add.
for dist in species genus family order class phylum; do
  for rate in 0.01 0.05; do
    for k in 1 2 3 5 10; do
      for seed in 1 2 3; do
        name="inj_${dist}_r${rate}_k${k}_s${seed}"
        d="$OUT/$name"
        if [ ! -s "$d/$name.tax" ]; then
          mkdir -p "$d"
          python3 "$BENCH_ROOT/bin/inject_mislabels.py" "$TAX" \
            --distance "$dist" --rate "$rate" --k "$k" --seed "$seed" \
            --prefix "$d/$name" >/dev/null 2>"$d/warn.txt" || {
              echo "FAILED $name" >&2; continue; }
        fi
        # Outside the guard, so a skipped cell still gets its link refreshed -- a link written on
        # another machine points at where that machine kept the alignment.
        ln -sfn "$ALN_REL" "$d/$name.fasta"
      done
    done
  done
done

# Paths go in relative to BENCH_ROOT, the way data/gtdb/datasets.json already writes them. An
# absolute path makes the manifest work on exactly one machine under exactly one home: the committed
# one named /shared/home/agardette/bench in all 180 entries. main.nf resolves a relative path against
# projectDir, which is what resolvePath is there for.
python3 - "$OUT" "$ALN" "$BENCH_ROOT" <<'PY'
import json, sys
from pathlib import Path
out, aln, root = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
n_seqs = sum(1 for l in open(aln) if l.startswith(">"))
w = len("".join(open(aln).read().split(">")[1].split("\n")[1:]))
sets = []
for d in sorted(out.iterdir()):
    tax = d / f"{d.name}.tax"
    if tax.exists():
        sets.append({"name": d.name, "n_seqs": n_seqs, "aln_len": w,
                     "fasta": str((d / f"{d.name}.fasta").relative_to(root)),
                     "tax": str(tax.relative_to(root))})
json.dump({"source": "gtdb_arc2k, injected grid", "datasets": sets},
          open(out / "datasets.json", "w"), indent=2)
print(f"{len(sets)} injected datasets, {n_seqs} sequences each, width {w}")
PY

grep -l . "$OUT"/*/warn.txt 2>/dev/null | head -5 | while read f; do
  echo "warning in $(basename "$(dirname "$f")"): $(head -1 "$f")"
done || true
