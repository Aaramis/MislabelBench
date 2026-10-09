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

ROOT="$BENCH_ROOT"
BAC="$ROOT/data/bacteria"
OUT="$ROOT/data/foreign"
ALN="$ROOT/data/gtdb/gtdb_arc2k.fasta"
TAX="$ROOT/data/gtdb/gtdb_arc2k.tax"

cd "$BAC"
# Singularity and the Infernal image are needed for the alignment and for nothing else, so they are
# required inside the branch that uses them. donor_pool.aligned.fasta is in the repository, so a
# clone rebuilds the nine foreign cells from the committed alignment with python alone -- which it
# could not do while this script demanded an image it was about to skip.
if [ ! -s donor_pool.aligned.fasta ]; then
    require_singularity
    # The Infernal image, pinned by tag and pulled when the cache does not hold it. It used to be found
    # by globbing ~/.singularity_cache, which the first run of this script showed is a cache and not a
    # record: the glob matched nothing, and under pipefail the empty `ls | head` exited 2 before the
    # message meant for that case could print. The tag is biocontainers' latest 1.1.5 build; the digest
    # the pull resolves to is printed so it can go in assets/datasets.yml.
    INFERNAL_TAG="1.1.5--pl5321h7b50bb2_4"
    IMG="$HOME/.singularity_cache/infernal-${INFERNAL_TAG}.sif"
    mkdir -p "$HOME/.singularity_cache"
    if [ ! -s "$IMG" ]; then
        singularity pull --name "$IMG" "docker://quay.io/biocontainers/infernal:${INFERNAL_TAG}"
    fi
    echo "infernal image $IMG sha256 $(sha256sum "$IMG" | cut -d' ' -f1)"
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

# Relative to BENCH_ROOT, for the reason spelled out in make_grid.sh.
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
    w = len("".join(fa.read_text().split(">")[1].split("\n")[1:]))
    sets.append({"name": d.name, "n_seqs": n, "aln_len": w,
                 "fasta": str(fa.relative_to(root)), "tax": str(tax.relative_to(root))})
json.dump({"source": "gtdb_arc2k plus bacterial donors under archaeal labels",
           "datasets": sets}, open(out / "datasets.json", "w"), indent=2)
print(f"{len(sets)} foreign-sequence datasets, {sets[0]['n_seqs']}-{sets[-1]['n_seqs']} sequences")
PY
