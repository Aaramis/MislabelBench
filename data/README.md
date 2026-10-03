# Inputs

What is here is what cannot be regenerated without the cluster, plus everything small. What is not
here is regenerable, and that claim is checked rather than asserted.

## Kept

| | |
|---|---|
| `gtdb/gtdb_arc*.fasta`, `gtdb/gtdb_arc*.tax` | the archaeal base datasets and their size subsets. `gtdb_arc1200.aligned.fasta` is the Infernal alignment, which costs an hour and a covariance model to rebuild |
| `gtdb/RF01959.cm` | the Rfam covariance model the alignment uses, so the alignment step does not depend on Rfam staying reachable |
| `gtdb/*.subset.json`, `gtdb/datasets*.json` | which sequences each subset took and with which seed |
| `bacteria/donor_pool.*` | the bacterial donors for the foreign-sequence condition, aligned against the same model |
| `injected/*/\*.truth.json`, `foreign/*/\*.truth.json` | the ground truth every detection number is scored against |
| `injected/datasets.json`, `foreign/datasets.json` | the manifests the harness reads |

## Not kept

**`raw/ssu_all_r226.fna.gz`**, 73 MB. Fetched by URL with its sha256 recorded in
`assets/datasets.yml`, which is a stronger guarantee than a copy in git.

**`*.pfam`**, 23 MB. The Pfam-format output of `cmalign`; `*.aligned.fasta` is the same alignment in
the form everything downstream reads.

**The per-cell `.tax` and `.fasta` of the 180 injected cells**, 56 MB. Each is the base taxonomy with
a few hundred labels rewritten, and `slurm/make_grid.sh` rebuilds all 180 from their seeds in under
a minute with no cluster and no container. The alignment is shared, so each cell's `.fasta` was only
ever a symlink to the base.

Checked, because "reproducible from the seed" is the sort of claim that is usually almost true:
regenerating the grid on macOS under python 3.14 gives `.tax` files whose md5 matches the python
3.12 Linux ones byte for byte, and `truth.json` files identical in all 180 cells. The only
field that moved was
`source`, which recorded the absolute path of the input and therefore could not match between two
machines; it now records the input's name and sha256, which can.
