#!/bin/bash
#SBATCH --job-name=sharedref
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=%x-%j.log
#
# Does the rate heterogeneity model explain any of the fork's advantage?
#
# Every run writes its reference with a ratehet_model field, and above 402 sequences it
# reads GTRCAT for upstream and GTRGAMMA for the fork. The benchmark's claim is that only the
# placement engine differs, and above that size it is false in one more respect. The model cannot be
# forced from either command line, so it cannot be held fixed by a flag.
#
# It can be held fixed by sharing the reference. Both tools take -r to reuse one that has already
# been built, so upstream builds it once, with its own GTRCAT, and the fork's staged leave-one-out
# runs against that same file. Model, tree and branch lengths are then identical and the only thing
# left between the two sets of flags is the placement engine. That is the experiment the earlier
# comparison was meant to be.
#
# Three arms on one cell, in one job:
#   upstream        its own reference, its own placement           the published comparator
#   fork_shared     upstream's reference, EPA-ng placement         the engine alone
#   fork_own        its own reference, EPA-ng placement            the published fork
#
# If fork_shared flags what fork_own flags, the model changes nothing and the note needs one
# sentence. If it flags what upstream flags, part of what this benchmark calls the engine is the
# rate model, and the attribution has to be redone.
set -uo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
require_singularity

ROOT="$BENCH_ROOT"
CELL="${SHARED_CELL:-inj_family_r0.05_k2_s1}"
FOLDS="${SHARED_FOLDS:-25}"
THREADS=8
OUT="$ROOT/results/shared_reference/$CELL"
[ -d "$ROOT/data/injected/$CELL" ] || { echo "no such cell: $CELL" >&2; exit 1; }

FORK=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* 2>/dev/null | head -1)
UP=$(ls "$HOME"/.singularity_cache/*sativa*0.9.3*py312h031d066_0* 2>/dev/null | grep -v epang | head -1)
[ -n "$FORK" ] && [ -n "$UP" ] || { echo "missing a container image" >&2; exit 1; }

rm -rf "$OUT"; mkdir -p "$OUT"
prep() { mkdir -p "$1"; cp "$ROOT/data/injected/$CELL/$CELL.fasta" "$1/aln.fasta"
         cp "$ROOT/data/injected/$CELL/$CELL.tax" "$1/tax.tsv"; }
model() { python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['ratehet_model'])" "$1" 2>/dev/null || echo "?"; }
failed=0
check() { [ "$1" = "0" ] && [ -s "$2" ] || { echo "ARM FAILED: $3 (status $1)" >&2; tail -4 "$4" >&2; failed=$((failed + 1)); }; }

# 1. Upstream, whole run. Its reference is the one the other arm will borrow.
d="$OUT/upstream"; prep "$d"
( cd "$d" && SINGULARITYENV_OMP_NUM_THREADS=$THREADS singularity exec -B "$d:$d" --pwd "$d" "$UP" \
    sativa.py -s aln.fasta -t tax.tsv -T $THREADS -n run -tmpdir "$d/tmp" \
              -m ultrafast -C 0.4 -x BAC -p 42 -S > stdout.log 2>&1 )
check $? "$d/run.mis" upstream "$d/stdout.log"
echo "upstream   : model $(model "$d/run.refjson"), $(grep -vc '^;' "$d/run.mis" 2>/dev/null) flags"

# 2. The fork placing against upstream's reference, staged so the reference step is skipped.
d="$OUT/fork_shared"; prep "$d"
cp "$OUT/upstream/run.refjson" "$d/run.refjson"
( cd "$d" && SINGULARITYENV_SATIVA_L1O_ENGINE=epang SINGULARITYENV_SATIVA_EPANG_FOLDS=$FOLDS \
    SINGULARITYENV_OMP_NUM_THREADS=$THREADS singularity exec -B "$d:$d" --pwd "$d" "$FORK" \
    bash -c "sativa-epang -r run.refjson -n run -o . -T $THREADS -stage loo-tasks && \
             sativa-epang -stage loo-place -taskdir ./run.l1o_tasks -T $THREADS && \
             sativa-epang -r run.refjson -C 0.4 -S -n run -o . -T $THREADS -stage loo-score \
                          -taskdir ./run.l1o_tasks" > stdout.log 2>&1 )
check $? "$d/run.mis" fork_shared "$d/stdout.log"
echo "fork_shared: model $(model "$d/run.refjson"), $(grep -vc '^;' "$d/run.mis" 2>/dev/null) flags"

# 3. The fork as published, building its own reference.
d="$OUT/fork_own"; prep "$d"
( cd "$d" && SINGULARITYENV_SATIVA_L1O_ENGINE=epang SINGULARITYENV_SATIVA_EPANG_FOLDS=$FOLDS \
    SINGULARITYENV_OMP_NUM_THREADS=$THREADS singularity exec -B "$d:$d" --pwd "$d" "$FORK" \
    sativa-epang -s aln.fasta -t tax.tsv -T $THREADS -n run -tmpdir "$d/tmp" \
                 -m ultrafast -C 0.4 -x BAC -p 42 -S > stdout.log 2>&1 )
check $? "$d/run.mis" fork_own "$d/stdout.log"
echo "fork_own   : model $(model "$d/run.refjson"), $(grep -vc '^;' "$d/run.mis" 2>/dev/null) flags"

[ "$failed" = "0" ] || { echo "$failed arm(s) failed; nothing below is a measurement" >&2; exit 1; }

python3 - "$OUT" "$ROOT/data/injected/$CELL/$CELL.truth.json" <<'PY'
import json, sys
from pathlib import Path
out, truth = Path(sys.argv[1]), set(json.loads(Path(sys.argv[2]).read_text())["injected"])
def flags(arm):
    return {l.split("\t")[0] for l in (out / arm / "run.mis").read_text().splitlines()
            if not l.startswith(";") and l.strip()}
a = {arm: flags(arm) for arm in ("upstream", "fork_shared", "fork_own")}
print()
for arm, f in a.items():
    print(f"{arm:12} {len(f):4} flags, {len(f & truth):3} of {len(truth)} injected found "
          f"(recall {len(f & truth) / len(truth):.3f})")
print()
for x, y in (("fork_own", "fork_shared"), ("fork_shared", "upstream"), ("fork_own", "upstream")):
    j = len(a[x] & a[y]) / len(a[x] | a[y])
    print(f"{x:12} vs {y:12} shared {len(a[x] & a[y]):4}, only {x} {len(a[x] - a[y]):3}, "
          f"only {y} {len(a[y] - a[x]):3}, jaccard {j:.3f}")
PY
echo ALLDONE
