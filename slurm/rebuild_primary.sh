#!/bin/bash
#SBATCH --job-name=rebuildprim
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=2:00:00
#SBATCH --output=%x-%j.log
#
# Does the primary dataset follow from the release its sha256 records?
#
# data/README.md justifies leaving the 73 MB GTDB release out of git by pinning it with a sha256,
# "a stronger guarantee than a copy in git". That guarantees the input. Nothing has ever checked
# that the files everything here rests on follow from it -- and the archaeal set is the only one of
# the three datasets with no counts sidecar, so there was no build record either, while the
# bacterial donor pool and both UNITE subsets have one.
#
# Rebuilds gtdb_arc1200 from the release with the parameters the manifest records and compares,
# byte for byte, against the committed files.
set -euo pipefail
source "${BENCH_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/slurm/prelude.sh"
export PATH="$BENCH_ROOT/bin:$PATH"

RAW="$BENCH_ROOT/data/raw"
SHA=$(dataset_field.py gtdb_archaea_ssu sha256)
URL=$(dataset_field.py gtdb_archaea_ssu url)
mkdir -p "$RAW"
cd "$RAW"
[ -s ssu_all_r226.fna.gz ] || curl -sSL -o ssu_all_r226.fna.gz "$URL"
got=$(sha256sum ssu_all_r226.fna.gz | cut -d' ' -f1)
echo "release sha256 recorded: $SHA"
echo "release sha256 now:      $got"
[ "$got" = "$SHA" ] || { echo "the release is not the one assets/datasets.yml records" >&2; exit 1; }

OUT=$BENCH_ROOT/results/rebuild_primary
rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"
prepare_gtdb.py "$RAW/ssu_all_r226.fna.gz" --domain d__Archaea --min-len 1200 --prefix gtdb_arc1200

echo
echo "=== against the committed files"
fail=0
for ext in fasta tax; do
    a=$BENCH_ROOT/data/gtdb/gtdb_arc1200.$ext
    b=$OUT/gtdb_arc1200.$ext
    printf "  %-6s committed %s  rebuilt %s  " "$ext" \
        "$(md5sum "$a" | cut -c1-12)" "$(md5sum "$b" | cut -c1-12)"
    if cmp -s "$a" "$b"; then echo "identical"; else echo "DIFFER"; fail=1; fi
done
[ "$fail" = "0" ] || { echo "VERDICT: the primary dataset does not follow from the recorded release" >&2; exit 1; }
echo "VERDICT: the primary dataset is reproducible from the release its sha256 pins"
echo
echo "=== the build record that was missing"
cat "$OUT/gtdb_arc1200.counts.json"
