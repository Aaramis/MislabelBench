#!/bin/bash
#SBATCH --job-name=foldorder
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=1:00:00
#SBATCH --output=%x-%j.log
#
# Does SATIVA_EPANG_FOLD_ORDER=tree actually change which sequences share a fold?
#
# The option is documented in the tool and defaults to 'name', where folds are a stride over
# sorted accessions and therefore random with respect to the tree. In tree order the stride runs
# over a post-order traversal, so neighbours are dealt into different folds. Before measuring
# what that does to detection, this confirms the knob does what it says: the two fold partitions
# must differ, and under tree order two members of one species must share a fold less often.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

ROOT="$BENCH_ROOT"
OUT="$ROOT/results/fold_order"
IMG=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* 2>/dev/null | head -1)
[ -n "$IMG" ] || { echo "sativa-epang 0.10.2 image not in $HOME/.singularity_cache" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"
cd "$OUT"
cp "$ROOT/data/gtdb/gtdb_arc2k.fasta" aln.fasta
cp "$ROOT/data/gtdb/gtdb_arc2k.tax" tax.tsv

se() { singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" sativa-epang "$@"; }
ARGS=(-m ultrafast -C 0.4 -x BAC -p 42 -S)

# One reference build, reused by both orders: the fold composition is the only thing that differs.
se -s aln.fasta -t tax.tsv "${ARGS[@]}" -n run -o "$OUT" -T "$SLURM_CPUS_PER_TASK" -stage reference

for order in name tree; do
    rm -rf "$OUT/run.l1o_tasks"
    SINGULARITYENV_SATIVA_EPANG_FOLD_ORDER="$order" \
        SINGULARITYENV_SATIVA_EPANG_FOLDS=25 \
        se -r "$OUT/run.refjson" -n run -o "$OUT" -T "$SLURM_CPUS_PER_TASK" -stage loo-tasks
    python3 "$ROOT/bin/fold_composition.py" --taskdir "$OUT/run.l1o_tasks" \
        --tax tax.tsv --label "$order" --out "$OUT/folds_${order}.json"
done

python3 "$ROOT/bin/fold_composition.py" --compare "$OUT/folds_name.json" "$OUT/folds_tree.json"
