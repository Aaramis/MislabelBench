#!/bin/bash
#SBATCH --job-name=kexactlost
#SBATCH --nodes=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=4:00:00
#SBATCH --output=%x-%j.log
#
# Which two sequences does Kexact lose, and are they injected ones?
#
# README.md splits the fork's k=2 advantage into the engine (+0.284, +0.177) and the fold scheme
# (-0.020, 0.000). The engine term is 29 and 18 of 102 injected sequences and is not in doubt. The
# fold term is 2 and 0 of them, and the logs of the same runs say:
#
#   [epang-l1o] placed 2023/2023 folds
#   [epang-l1o] placements produits: 2021 (K=2023 folds, remap 50.7s)
#
# Every fold placed, and two placements vanished in the remap with no warning. K5 loses none, K25
# loses two and one. So the published fold term is the same size as a silent loss nobody has
# accounted for, and whether it is a measurement or an artefact depends on whether the lost
# sequences are injected ones. That is a question about two specific names, so get the two names.
#
# Runs the staged path, which exposes one jplace per fold, and counts the queries inside each
# rather than trusting the file to exist -- the loss is downstream of placement, so every file
# does exist and 2021 of them carry a query.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

CELL="${KEXACT_CELL:-inj_family_r0.05_k2_s1}"
ROOT="$BENCH_ROOT"
OUT="$ROOT/results/kexact_lost/$CELL"
ALN="$ROOT/data/gtdb/gtdb_arc2k.fasta"
TAX="$ROOT/data/injected/$CELL/$CELL.tax"
TRUTH="$ROOT/data/injected/$CELL/$CELL.truth.json"
for f in "$ALN" "$TAX" "$TRUTH"; do
    [ -s "$f" ] || { echo "missing: $f" >&2; exit 1; }
done
IMG=$(ls "$HOME"/.singularity_cache/*sativa-epang*0.10.2*py314hab16a5f_0* 2>/dev/null | head -1)
[ -n "$IMG" ] || { echo "sativa-epang 0.10.2 image not in $HOME/.singularity_cache" >&2; exit 1; }

rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"
cp "$ALN" aln.fasta; cp "$TAX" tax.tsv
se() { singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" sativa-epang "$@"; }

# Same flags as conf/modules.config, and FOLDS above the leaf count so the tool caps it at one
# sequence per fold, which is what makes this condition Kexact.
export SATIVA_EPANG_FOLDS=999999
se -s aln.fasta -t tax.tsv -m ultrafast -C 0.4 -x BAC -p 42 -S -n run -o "$OUT" -T 8 -stage reference
se -r "$OUT/run.refjson" -n run -o "$OUT" -T 8 -stage loo-tasks

# Four shards of two threads, which is how the single-process run placed them ("4 at a time,
# 2 threads each"), so the work is the same shape and only the inspection is new.
pids=()
for i in 0 1 2 3; do
    (
        singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" \
            sativa-epang -stage loo-place -taskdir "$OUT/run.l1o_tasks" -T 2 \
            -folds "${i}/4" > "$OUT/place_shard${i}.log" 2>&1
    ) &
    pids+=($!)
done
failed=0
for i in "${!pids[@]}"; do
    st=0; wait "${pids[$i]}" || st=$?
    [ "$st" = "0" ] || { echo "placement shard $i failed with status $st" >&2; failed=1; }
done
[ "$failed" = "0" ] || exit 1

python3 - "$OUT" "$TRUTH" <<'PY'
import json, sys
from pathlib import Path

out, truth_p = Path(sys.argv[1]), Path(sys.argv[2])
injected = set(json.loads(truth_p.read_text())["injected"])

folds = sorted(out.glob("run.l1o_tasks/fold_*"), key=lambda p: int(p.name.split("_")[1]))
print(f"{len(folds)} folds, {len(injected)} injected sequences in the cell\n")

empty, total_q = [], 0
for f in folds:
    jp = f / "epa_result.jplace"
    if not jp.exists() or jp.stat().st_size == 0:
        empty.append((f.name, "no jplace", []))
        continue
    pl = json.loads(jp.read_text()).get("placements", [])
    # A jplace names its queries either as 'n' (a list) or 'nm' (name/multiplicity pairs).
    names = []
    for p in pl:
        names += list(p.get("n", [])) or [nm[0] for nm in p.get("nm", [])]
    total_q += len(names)
    if not names:
        # Which sequence this fold was holding out, so the loss has a name rather than an index.
        held = [l[1:].split()[0] for l in (f / "query.fasta").read_text().splitlines()
                if l.startswith(">")] if (f / "query.fasta").exists() else []
        empty.append((f.name, "placed nothing", held))

print(f"queries placed across all folds: {total_q}")
print(f"folds yielding no placement:     {len(empty)}\n")
for name, why, held in empty:
    tag = [f"{h} {'INJECTED' if h in injected else 'not injected'}" for h in held] or ["query name unknown"]
    print(f"  {name}: {why} -> " + "; ".join(tag))

if not empty:
    print("nothing was lost in this run, so the loss is not deterministic across runs")
PY
