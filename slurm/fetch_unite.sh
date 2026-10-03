#!/bin/bash
#SBATCH --job-name=fetchunite
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=4:00:00
#SBATCH --output=%x-%j.log
#
# The secondary dataset: UNITE v10.0, fungal ITS, RepS subset. Secondary because the primary is
# 16S and a reviewer is entitled to ask whether anything here is specific to one marker -- the
# question D. Lundin put as "all are rRNA, maybe use coI".
#
# RepS and not RefS, which is the more curated subset, for a reason that is measured rather than
# preferred: leave-one-out cannot judge a sequence with no sibling of the same taxon, and RefS is
# 8.5 % judgeable at species against RepS's 85.7 %. assets/datasets.yml carries both numbers.
#
# This also re-tests the one verification the plan promises for provenance and that has never been
# rerun: re-downloading an unchanged source must reproduce the recorded sha256. If it does not, the
# release has been revised under its own DOI and that is worth knowing before anything is built on
# it.
#
# No alignment here. UNITE ships none, ITS alignment is contested, and what that costs is an open
# question in the protocol rather than something to settle by picking an aligner quietly.
set -euo pipefail
source "${BENCH_ROOT:-$HOME/bench}/slurm/prelude.sh"
export PATH="$BENCH_ROOT/bin:$PATH"

ROOT="$BENCH_ROOT"
RAW="$ROOT/data/raw"
OUT="$ROOT/data/unite"
# From assets/datasets.yml, not copied here: two places holding one checksum is how the
# judgeability figure in that same file came to disagree with the data for days.
SHA=$(dataset_field.py unite_fungi sha256)
URL=$(dataset_field.py unite_fungi url)
MEMBER=sh_general_release_dynamic_19.02.2025.fasta
mkdir -p "$RAW" "$OUT"
cd "$RAW"

if [ ! -s unite_v10.tgz ]; then
    curl -sSL -o unite_v10.tgz "$URL"
fi
got=$(sha256sum unite_v10.tgz | cut -d' ' -f1)
echo "sha256 recorded: $SHA"
echo "sha256 now:      $got"
[ "$got" = "$SHA" ] || { echo "the release at this URL is not the one assets/datasets.yml records" >&2; exit 1; }

tar xzf unite_v10.tgz -C "$RAW" "$MEMBER" 2>/dev/null || tar xzf unite_v10.tgz -C "$RAW"
src=$(find "$RAW" -name "$MEMBER" | head -1)
[ -s "$src" ] || { echo "$MEMBER not in the archive" >&2; exit 1; }

cd "$OUT"
prepare_unite.py "$src" --subset reps --prefix unite_reps
echo
echo "=== what the subset looks like, before any alignment question"
unite_shape.py --fasta unite_reps.fasta --tax unite_reps.tax --out "$OUT/unite_shape.json"
