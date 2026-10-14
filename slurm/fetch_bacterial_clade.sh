#!/bin/bash
#SBATCH --job-name=fetchbac
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=%x-%j.log
#
# The bacterial clade the archaeal results are replicated on, fetched, filtered, aligned and
# subsetted the way the archaeal set was.
#
# Which clade is not decided here. bin/select_bacterial_clade.py scored every bacterial class and
# order of the release on the two numbers the archaeal set is characterised by, and wrote the choice
# and the runners-up to data/gtdb/bacterial_clade_selection.json; this script reads it. Changing the
# clade means changing that record, which is where the reasoning is.
#
# Aligned against Rfam RF00177, the bacterial SSU model, and not the archaeal RF01959 the donor pool
# used. The donors had to share the archaeal alignment's width to be concatenated into it; this set
# runs on its own, so the model is the one for the molecule. Extracted from the same pinned Rfam.cm.gz
# as RF01959 was, with cmfetch from the same Infernal image.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
require_singularity
export PATH="$BENCH_ROOT/bin:$PATH"

RAW="$BENCH_ROOT/data/raw"
OUT="$BENCH_ROOT/data/gtdb"
mkdir -p "$RAW"
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

# The selection record is made here when it is not here: bin/push_code.sh sends code and truth and
# not data/gtdb records, and the choice is a function of the release file, so recomputing it on the
# cluster from the same file gives the same record, which git then shows.
SHA=$(dataset_field.py gtdb_archaea_ssu sha256)
URL=$(dataset_field.py gtdb_archaea_ssu url)
cd "$RAW"
if [ ! -f ssu_all_r226.fna.gz ] || [ "$(sha256sum ssu_all_r226.fna.gz | cut -d' ' -f1)" != "$SHA" ]; then
    curl -fsSL -o ssu_all_r226.fna.gz "$URL"
fi
echo "$SHA  ssu_all_r226.fna.gz" | sha256sum -c -
[ -s "$OUT/bacterial_clade_selection.json" ] || python3 "$BENCH_ROOT/bin/select_bacterial_clade.py" \
    --fasta "$RAW/ssu_all_r226.fna.gz" --out "$OUT/bacterial_clade_selection.json"
CLADE=$(python3 -c "import json;print(json.load(open('$OUT/bacterial_clade_selection.json'))['chosen']['clade'])")
TAG=$(echo "$CLADE" | awk -F';' '{print tolower($NF)}' | sed 's/^o__//; s/^c__//')
echo "clade: $CLADE  -> gtdb_bac_${TAG}"

# The model, from the pinned Rfam.cm.gz. RF01959.cm was extracted by hand once and committed; this
# makes the extraction a step of the record for RF00177, and prints the sha256 for datasets.yml.
RSHA=$(dataset_field.py rfam_ssu_archaea sha256)
RURL=$(dataset_field.py rfam_ssu_archaea url)
if [ ! -f Rfam.cm.gz ] || [ "$(sha256sum Rfam.cm.gz | cut -d' ' -f1)" != "$RSHA" ]; then
    curl -fsSL -o Rfam.cm.gz "$RURL"
fi
echo "$RSHA  Rfam.cm.gz" | sha256sum -c -
if [ ! -s "$OUT/RF00177.cm" ]; then
    [ -f Rfam.cm ] || gunzip -k Rfam.cm.gz
    singularity exec -B "$RAW:$RAW" -B "$OUT:$OUT" --pwd "$RAW" "$IMG" cmfetch Rfam.cm RF00177 > "$OUT/RF00177.cm"
fi
echo "RF00177.cm sha256 $(sha256sum "$OUT/RF00177.cm" | cut -d' ' -f1), CLEN $(grep -m1 '^CLEN' "$OUT/RF00177.cm")"

# Select, filter, align: the archaeal steps with the clade as the prefix.
cd "$OUT"
python3 "$BENCH_ROOT/bin/prepare_gtdb.py" "$RAW/ssu_all_r226.fna.gz" \
    --domain "$CLADE" --min-len 1200 --prefix "gtdb_bac_${TAG}"
singularity exec -B "$OUT:$OUT" --pwd "$OUT" "$IMG" \
    cmalign --cpu "${SLURM_CPUS_PER_TASK:-8}" --dnaout --matchonly --outformat Pfam \
    -o "gtdb_bac_${TAG}.pfam" --sfile "gtdb_bac_${TAG}.cmalign.txt" \
    "$OUT/RF00177.cm" "gtdb_bac_${TAG}.fasta"
awk '!/^#/ && !/^\/\// && NF==2 {print ">"$1"\n"$2}' "gtdb_bac_${TAG}.pfam" > "gtdb_bac_${TAG}.aligned.fasta"
rm -f "gtdb_bac_${TAG}.pfam"
W=$(awk '!/^>/{print length($0); exit}' "gtdb_bac_${TAG}.aligned.fasta")
N=$(grep -c '^>' "gtdb_bac_${TAG}.aligned.fasta")
echo "aligned: $N sequences, width $W"

# The grid's subset, by whole taxa, as gtdb_arc2k was.
python3 "$BENCH_ROOT/bin/subset_taxa.py" "gtdb_bac_${TAG}.aligned.fasta" "gtdb_bac_${TAG}.tax" \
    --target 2000 --seed 42 --prefix "gtdb_bac2k"
N2=$(grep -c '^>' gtdb_bac2k.fasta)

# The protocol's dataset table for this clade, from the same release files.
python3 "$BENCH_ROOT/bin/dataset_table.py" --ssu-all "$RAW/ssu_all_r226.fna.gz" \
    --clade "$CLADE" --out "$OUT/dataset_table_bac.json"

python3 - "$OUT" "$BENCH_ROOT" "$TAG" "$N" "$N2" "$W" "$CLADE" <<'PY'
import json, sys
from pathlib import Path
out, root, tag, n, n2, w, clade = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7]
rel = lambda p: str((out / p).relative_to(root))
(out / "datasets_bac.json").write_text(json.dumps({
    "source": f"GTDB r226 ssu_all, {clade}, >= 1200 nt, aligned against Rfam RF00177; the bacterial replication",
    "datasets": [
        {"name": f"gtdb_bac_{tag}", "n_seqs": n, "aln_len": w,
         "fasta": rel(f"gtdb_bac_{tag}.aligned.fasta"), "tax": rel(f"gtdb_bac_{tag}.tax")},
        {"name": "gtdb_bac2k", "n_seqs": n2, "aln_len": w,
         "fasta": rel("gtdb_bac2k.fasta"), "tax": rel("gtdb_bac2k.tax")}]}, indent=2) + "\n")
print(f"manifest: gtdb_bac_{tag} ({n}) and gtdb_bac2k ({n2}), width {w}")
PY
python3 "$BENCH_ROOT/bin/dataset_shape.py" --convention gtdb --fasta "gtdb_bac_${TAG}.aligned.fasta" \
    --tax "gtdb_bac_${TAG}.tax" --out "$OUT/shape_gtdb_bac_${TAG}.json" | tail -9
