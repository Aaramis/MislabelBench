#!/bin/bash
#SBATCH --job-name=beforeafter
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=1:00:00
#SBATCH --output=%x-%j.log
# Is the empty lineage a regression from taxmarker#40, or did the input already fail?
# Before the PR, an all-placeholder lineage reached SATIVA verbatim. After it, it is trimmed to
# nothing. These are the two inputs, same tool, same everything else.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity
IMG=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* | head -1)
OUT=$BENCH_ROOT/results/ragged_check
cd "$OUT"
python3 - "$BENCH_ROOT/data/gtdb/gtdb_arc400.tax" <<'PY'
import sys
from pathlib import Path
rows = [l.split("\t", 1) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
variants = {
    "before_placeholders": "d__;p__;c__;o__;f__;g__;s__",   # what reached SATIVA before the PR
    "before_semicolons":   ";;;;;;",                        # the other untrimmed form
    "after_trimmed":       "",                              # what the PR produces from either
}
for tag, lineage in variants.items():
    with open(f"{tag}.tax", "w") as fh:
        for i, (name, lin) in enumerate(rows):
            fh.write(f"{name}\t{lineage if i == 0 else lin}\n")
PY
se() { singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" sativa-epang "$@"; }
for t in before_placeholders before_semicolons after_trimmed; do
    printf "%-22s " "$t"
    if se -s aln.fasta -t $t.tax -m ultrafast -C 0.4 -x BAC -p 42 -S -n $t -o "$OUT" -T 8 \
         > $t.stdout 2> $t.stderr; then
        echo "completed, flags: $(grep -vc '^;' $t.mis 2>/dev/null || echo 0)"
    else
        echo "FAILED: $(grep -oE '[A-Za-z]*Error.*' $t.stderr | tail -1)"
    fi
done
