#!/usr/bin/env bash
# Pack the run outputs that git does not keep (placements, reference trees, tool logs) for the data
# record on Zenodo. Usage: bin/ops/make_archive.sh [output_dir]   (default: ./archive)
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-archive}"; mkdir -p "$out"
name="mislabelbench-run-outputs-$(git describe --tags --always)"
git ls-files -o -i --exclude-standard results | sort > "$out/$name.files"
tar --files-from "$out/$name.files" -cf - | zstd -19 -T0 -q -o "$out/$name.tar.zst" -f
( cd "$out" && shasum -a 256 "$name.tar.zst" "$name.files" > SHA256SUMS )
echo "$(wc -l < "$out/$name.files") files, $(du -h "$out/$name.tar.zst" | cut -f1) in $out/$name.tar.zst"
