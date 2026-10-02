#!/bin/bash
#SBATCH --job-name=makeforeign
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=2:00:00
#SBATCH --output=%x-%j.log
#
# Error kind 6, on A. Stamatakis's construction: bacterial sequences added to the archaeal
# database under an archaeal label.
#
# The donors are aligned against the same covariance model as the base, with --matchonly, which
# emits exactly the model's match columns. Two separate cmalign runs therefore produce the same
# width and the alignments concatenate. inject_foreign.py asserts that rather than trusting it.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
require_singularity

ROOT="$BENCH_ROOT"
BAC="$ROOT/data/bacteria"
OUT="$ROOT/data/foreign"
ALN="$ROOT/data/gtdb/gtdb_arc2k.fasta"
TAX="$ROOT/data/gtdb/gtdb_arc2k.tax"
IMG=$(ls "$HOME"/.singularity_cache/*infernal*1.1.5* 2>/dev/null | head -1)
[ -n "$IMG" ] || { echo "no infernal image in $HOME/.singularity_cache" >&2; exit 1; }

cd "$BAC"
if [ ! -s donor_pool.aligned.fasta ]; then
    singularity exec -B "$BAC:$BAC" --pwd "$BAC" "$IMG" \
        cmalign --cpu "${SLURM_CPUS_PER_TASK:-8}" --dnaout --matchonly --outformat Pfam \
        -o donor_pool.pfam --sfile donor_pool.cmalign.txt \
        "$ROOT/data/gtdb/RF01959.cm" donor_pool.fasta
    awk '!/^#/ && !/^\/\// && NF==2 {print ">"$1"\n"$2}' donor_pool.pfam > donor_pool.aligned.fasta
fi
echo "donor alignment width: $(awk '!/^>/{print length($0); exit}' donor_pool.aligned.fasta)"
echo "base alignment width:  $(awk '!/^>/{print length($0); exit}' "$ALN")"

rm -rf "$OUT"
mkdir -p "$OUT"
# Rates as a proportion of the base, so the cells read on the same axis as the relabelling grid.
for rate in 0.005 0.01 0.05; do
    n=$(python3 -c "print(round($rate * $(grep -c '^>' "$ALN")))")
    for seed in 1 2 3; do
        name="fgn_r${rate}_s${seed}"
        d="$OUT/$name"
        mkdir -p "$d"
        python3 "$ROOT/bin/inject_foreign.py" \
            --base-fasta "$ALN" --base-tax "$TAX" \
            --donor-fasta "$BAC/donor_pool.aligned.fasta" --donor-tax "$BAC/donor_pool.tax" \
            --n "$n" --seed "$seed" --prefix "$d/$name"
    done
done

python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
sets = []
for d in sorted(out.iterdir()):
    if not d.is_dir():
        continue
    fa, tax = d / f"{d.name}.fasta", d / f"{d.name}.tax"
    n = sum(1 for l in fa.open() if l.startswith(">"))
    w = len("".join(fa.read_text().split(">")[1].split("\n")[1:]))
    sets.append({"name": d.name, "n_seqs": n, "aln_len": w, "fasta": str(fa), "tax": str(tax)})
json.dump({"source": "gtdb_arc2k plus bacterial donors under archaeal labels",
           "datasets": sets}, open(out / "datasets.json", "w"), indent=2)
print(f"{len(sets)} foreign-sequence datasets, {sets[0]['n_seqs']}-{sets[-1]['n_seqs']} sequences")
PY
