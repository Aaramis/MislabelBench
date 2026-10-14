#!/bin/bash
#SBATCH --job-name=fetchbac
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=4:00:00
#SBATCH --output=%x-%j.log
#
# Donor pool for error kind 6: bacterial SSU sequences that will be given an archaeal lineage.
# A. Stamatakis proposed this construction, and it is better than the "long-branch and chimeric"
# wording it replaces, because the truth is recoverable by definition.
#
# The archive is the same ssu_all_r226.fna.gz the archaeal set came from, re-downloaded and
# checked against the sha256 in assets/datasets.yml. One phylum, randomly subsampled to a pool
# large enough for three disjoint seeds at the highest injection rate.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/slurm/prelude.sh"
export PATH="$BENCH_ROOT/bin:$(printf '%s:' "$BENCH_ROOT"/bin/*/)$PATH"

ROOT="$BENCH_ROOT"
RAW="$ROOT/data/raw"
OUT="$ROOT/data/bacteria"
# From assets/datasets.yml, not copied here: two places holding one checksum is how the
# judgeability figure in that same file came to disagree with the data for days.
SHA=$(dataset_field.py gtdb_archaea_ssu sha256)
URL=$(dataset_field.py gtdb_archaea_ssu url)
mkdir -p "$RAW" "$OUT"
cd "$RAW"

if [ ! -f ssu_all_r226.fna.gz ] || [ "$(sha256sum ssu_all_r226.fna.gz | cut -d' ' -f1)" != "$SHA" ]; then
    curl -fsSL -o ssu_all_r226.fna.gz "$URL"
fi
echo "$SHA  ssu_all_r226.fna.gz" | sha256sum -c -

# Which phylum to draw from is decided by the data, not by a name we remember: the largest one
# gives the most room to subsample from and is the least likely to be a sparse oddity.
zcat ssu_all_r226.fna.gz | awk '/^>/ {
    i = index($0, "d__Bacteria;p__"); if (!i) next
    s = substr($0, i); split(s, f, ";"); print f[2]
}' | sort | uniq -c | sort -rn > "$OUT/bacterial_phyla.txt"
head -5 "$OUT/bacterial_phyla.txt"
PHYLUM=$(head -1 "$OUT/bacterial_phyla.txt" | awk '{print $2}')
echo "donor phylum: $PHYLUM"

cd "$OUT"
python3 "$ROOT/bin/data/prepare_gtdb.py" "$RAW/ssu_all_r226.fna.gz" \
    --domain "d__Bacteria;$PHYLUM" --min-len 1200 --prefix donor_full

# 600 is the pool: three seeds x 101 sequences at the top rate of 5 % of 2 023, with room over.
python3 "$ROOT/bin/data/subsample_fasta.py" --fasta donor_full.fasta --tax donor_full.tax \
    --n 600 --seed 42 --prefix donor_pool
rm -f donor_full.fasta donor_full.tax
wc -l donor_pool.tax
