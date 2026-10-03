#!/bin/bash
#SBATCH --job-name=raggedchk
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=1:00:00
#SBATCH --output=%x-%j.log
# Does SATIVA accept what nf-core/taxmarker#40 now produces: lineages of unequal depth, and the
# empty lineage that an all-placeholder input collapses to?
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
IMG=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* | head -1)
OUT=$BENCH_ROOT/results/ragged_check
rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"
cp "$BENCH_ROOT/data/gtdb/gtdb_arc400.fasta" aln.fasta

python3 - "$BENCH_ROOT/data/gtdb/gtdb_arc400.tax" <<'PY'
import sys
from pathlib import Path
rows = [l.split("\t", 1) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
# Truncate a quarter of the lineages to genus and a quarter to family, which is what trimming a
# trailing s__ or g__;s__ produces, and leave the rest whole.
with open("ragged.tax", "w") as fh:
    for i, (name, lin) in enumerate(rows):
        r = lin.split(";")
        if i % 4 == 1:
            r = r[:6]
        elif i % 4 == 2:
            r = r[:5]
        fh.write(f"{name}\t{';'.join(r)}\n")
# One sequence with nothing at all, the case an all-placeholder lineage collapses to.
with open("empty.tax", "w") as fh:
    for i, (name, lin) in enumerate(rows):
        fh.write(f"{name}\t{'' if i == 0 else lin}\n")
print("depths in ragged.tax:", sorted({l.count(';') + 1 for l in
      (x.split(chr(9))[1] for x in Path("ragged.tax").read_text().splitlines())}))
PY

se() { singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" sativa-epang "$@"; }
for t in ragged empty; do
    echo "=== $t ==="
    if se -s aln.fasta -t $t.tax -m ultrafast -C 0.4 -x BAC -p 42 -S -n $t -o "$OUT" -T 8 \
         > $t.stdout 2> $t.stderr; then
        echo "  completed; flags: $(grep -vc '^;' $t.mis 2>/dev/null || echo NA)"
    else
        echo "  FAILED rc=$?"
        tail -4 $t.stderr
    fi
done
