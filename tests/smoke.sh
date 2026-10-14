#!/usr/bin/env bash
# The workflow's dataflow with every tool replaced by a stub. Needs Nextflow and a JVM, no container.
# resourceLimits lets it start on a small machine, since the real memory request grows with the dataset.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
echo "process.resourceLimits = [cpus: 2, memory: 2.GB]" > "$tmp/small.config"
nextflow run . -stub-run -profile stub_test -c "$tmp/small.config" \
  --datasets_json data/gtdb/datasets2k.json \
  --datasets gtdb_arc2k --conditions epang_T8_K25 --staged true --timing_trusted false \
  --outdir "$tmp/out"
