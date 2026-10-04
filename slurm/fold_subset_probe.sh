#!/bin/bash
#SBATCH --job-name=foldprobe
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=0:30:00
#SBATCH --output=%x-%j.log
#
# One question, which decides the shape of the distributed mode in DISTRIBUTION.md.
#
# -folds i/N is a stride over the fold list in manifest.json, and the manifest names every fold
# whatever the task directory holds. If the tool will place fold i from a directory containing only
# manifest.json, model and fold_i, then a Nextflow fan-out can stage 11 MB per fold. If it insists on
# finding all 25, the whole 275 MB has to be staged per task and the design changes.
#
# No timing is taken here, so where it lands does not matter to the measurement -- but the caller
# should still keep it off the nodes a timed job is holding.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

SRC="${PROBE_TASKDIR:?set PROBE_TASKDIR to an existing run.l1o_tasks}"
FOLD="${PROBE_FOLD:-7}"
N=$(python3 -c "import json;print(json.load(open('$SRC/manifest.json'))['n_folds'])")
name=$(printf "fold_%03d" "$FOLD")
[ -d "$SRC/$name" ] || { echo "no $name in $SRC" >&2; exit 1; }

IMG=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* | head -1)
[ -n "$IMG" ] || { echo "no sativa-epang image in $HOME/.singularity_cache" >&2; exit 1; }

OUT="$BENCH_ROOT/results/fold_subset_probe"
rm -rf "$OUT"
mkdir -p "$OUT/subset"
cp "$SRC/manifest.json" "$SRC/model" "$OUT/subset/"
# Without the placement the fold already carries, so a jplace appearing is this run's work.
mkdir -p "$OUT/subset/$name"
# ref.nwk and the per-fold model are optional, depending on where the tool keeps them; the
# alignment and the query are not. They were all copied with `|| true`, so a subset that staged
# nothing would have run, placed nothing and reported "not enough" -- a false negative on the
# question that decides the shape of the fan-out.
for f in ref.fasta query.fasta; do
    cp "$SRC/$name/$f" "$OUT/subset/$name/" || { echo "cannot stage $name/$f from $SRC" >&2; exit 1; }
done
for f in ref.nwk model; do
    cp "$SRC/$name/$f" "$OUT/subset/$name/" 2>/dev/null || echo "note: $name/$f not present, continuing"
done
echo "subset holds: $(ls "$OUT/subset" | tr '\n' ' ')"
echo "staged for $name: $(du -sh "$OUT/subset" | cut -f1) against $(du -sh "$SRC" | cut -f1) for the whole directory"

status=0
singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" \
    sativa-epang -stage loo-place -taskdir "$OUT/subset" -T "${SLURM_CPUS_PER_TASK:-8}" \
    -folds "${FOLD}/${N}" > "$OUT/place.log" 2>&1 || status=$?

echo "exit status: $status"
tail -20 "$OUT/place.log"
if [ -s "$OUT/subset/$name/epa_result.jplace" ]; then
    echo "VERDICT: a one-fold task directory is enough; $name was placed"
    echo "jplace: $(wc -c < "$OUT/subset/$name/epa_result.jplace") bytes"
else
    echo "VERDICT: not enough; $name has no placement"
fi
