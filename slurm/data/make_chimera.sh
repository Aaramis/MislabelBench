#!/bin/bash
# Error kind 7: chimeras of two real sequences, labelled as one parent, on the grid's base set.
#
# Two axes, as the reviewed protocol puts it -- "varying the distance between parents and the
# breakpoint" -- crossed with three seeds: parents differing at genus, family, order or phylum, the
# breakpoint at a quarter, a half or three quarters of parent A's ungapped length, 36 cells. Twenty
# chimeras per cell, which is 1 % of the base and the grid's lower rate; the cells are small so that
# an effect of the breakpoint is read against the same twenty parents at each distance, not against
# different draws.
#
# Added, not substituted, like kind 6, so the baseline flag set stays comparable. Deterministic from
# the seed, like every generator here, and refreshed in place rather than kept: 36 cells of 2 043
# sequences are 36 copies of the alignment, which is why only the truth is committed.
set -euo pipefail

BENCH_ROOT="${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
ALN="$BENCH_ROOT/data/gtdb/gtdb_arc2k.fasta"
TAX="$BENCH_ROOT/data/gtdb/gtdb_arc2k.tax"
OUT="$BENCH_ROOT/data/chimera"
mkdir -p "$OUT"

for dist in genus family order phylum; do
  for bp in 0.25 0.5 0.75; do
    for seed in 1 2 3; do
      name="chi_${dist}_b${bp}_s${seed}"
      d="$OUT/$name"
      mkdir -p "$d"
      python3 "$BENCH_ROOT/bin/inject_chimera.py" --base-fasta "$ALN" --base-tax "$TAX" \
        --distance "$dist" --breakpoint "$bp" --n 20 --seed "$seed" --prefix "$d/$name" >/dev/null
    done
  done
done

python3 "$BENCH_ROOT/bin/verify_chimera.py" --base-fasta "$ALN" --base-tax "$TAX" --chimera-dir "$OUT"

# The manifest in the shape main.nf reads, paths relative to BENCH_ROOT as in make_grid.sh.
python3 - "$OUT" "$BENCH_ROOT" <<'PY'
import json, sys
from pathlib import Path
out, root = Path(sys.argv[1]), Path(sys.argv[2])
sets = []
for d in sorted(out.iterdir()):
    if not d.is_dir():
        continue
    fa, tax = d / f"{d.name}.fasta", d / f"{d.name}.tax"
    n = sum(1 for l in fa.open() if l.startswith(">"))
    w = len(fa.read_text().split(">")[1].split("\n")[1])
    sets.append({"name": d.name, "n_seqs": n, "aln_len": w,
                 "fasta": str(fa.relative_to(root)), "tax": str(tax.relative_to(root))})
(out / "datasets.json").write_text(json.dumps(
    {"source": "chimeras of two gtdb_arc2k sequences labelled as parent A",
     "datasets": sets}, indent=2) + "\n")
print(f"{len(sets)} chimera cells, {sets[0]['n_seqs']} sequences of {sets[0]['aln_len']} columns")
PY
