#!/bin/bash
# The part of the injection grid the bacterial clade replicates: the k axis at family distance and
# 5 %, three seeds, fifteen cells, on the clade's whole-taxa subset. Not the full grid: the question
# is whether the detection law has the same shape on another domain, and the k axis answers it.
set -euo pipefail
BENCH_ROOT="${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
ALN="$BENCH_ROOT/data/gtdb/gtdb_bac2k.fasta"
TAX="$BENCH_ROOT/data/gtdb/gtdb_bac2k.tax"
OUT="$BENCH_ROOT/data/injected_bac"
[ -s "$TAX" ] || { echo "no $TAX: run slurm/data/fetch_bacterial_clade.sh first" >&2; exit 1; }
mkdir -p "$OUT"
ALN_REL=$(python3 -c 'import os, sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$ALN" "$OUT/any_cell")
for k in 1 2 3 5 10; do
  for seed in 1 2 3; do
    name="binj_family_r0.05_k${k}_s${seed}"
    d="$OUT/$name"
    if [ ! -s "$d/$name.tax" ]; then
      mkdir -p "$d"
      python3 "$BENCH_ROOT/bin/data/inject_mislabels.py" "$TAX" --distance family --rate 0.05 \
        --k "$k" --seed "$seed" --prefix "$d/$name" >/dev/null 2>"$d/warn.txt" || { echo "FAILED $name" >&2; continue; }
    fi
    ln -sfn "$ALN_REL" "$d/$name.fasta"
  done
done
python3 - "$OUT" "$ALN" "$BENCH_ROOT" <<'PY'
import json, sys
from pathlib import Path
out, aln, root = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
lines = aln.read_text().splitlines()
n, w = sum(1 for l in lines if l.startswith(">")), len(lines[1])
cells = [{"name": d.name, "n_seqs": n, "aln_len": w,
          "fasta": str((d / f"{d.name}.fasta").relative_to(root)),
          "tax": str((d / f"{d.name}.tax").relative_to(root))}
         for d in sorted(out.iterdir()) if (d / f"{d.name}.tax").exists()]
(out / "datasets.json").write_text(json.dumps(
    {"source": "the k axis at family distance and 5 % on the bacterial clade's subset", "datasets": cells}, indent=2) + "\n")
print(f"{len(cells)} bacterial cells of {n} sequences")
PY
