# data/

Base datasets, injected ground truth and manifests. [docs/data.md](../docs/data.md) says where each
source comes from and how a dataset is built.

## Committed

| path | content |
|---|---|
| `gtdb/gtdb_arc*.fasta`, `gtdb/gtdb_arc*.tax` | the archaeal base sets and their size subsets. `gtdb_arc1200.aligned.fasta` is the Infernal alignment, an hour of work and a covariance model to rebuild |
| `gtdb/RF01959.cm` | the Rfam covariance model, so the alignment does not depend on Rfam staying reachable |
| `gtdb/*.subset.json`, `gtdb/datasets*.json` | which sequences each subset took, with which seed, and the manifests the workflow reads |
| `bacteria/donor_pool.*` | the bacterial donors for the foreign-sequence cells, aligned on the same model |
| `*/*/*.truth.json` | what was injected in each dataset. Every detection number is scored against it |
| `*/datasets.json` | the manifest of each family of datasets |
| `clade/`, `simulated/`, `grove_sim/`, `grove/` | small enough to keep whole |

## Regenerated

These are rebuilt from their seeds, without a cluster, a container or the network.

| generator | rebuilds |
|---|---|
| `slurm/make_grid.sh` | the `.tax` of the 180 injected datasets and their `.fasta` links |
| `slurm/make_foreign.sh` | the nine foreign-sequence datasets |
| `slurm/make_clade.sh`, `slurm/make_simulation.sh` | refresh the links of the committed clade and simulated datasets |
| `slurm/make_chimera.sh`, `make_ragged.sh`, `make_width.sh`, `make_grid_bac.sh` | the chimera, ragged, width and bacterial datasets |

An injected dataset's `.fasta` is a symlink to `data/gtdb/gtdb_arc2k.fasta`, since injection rewrites a
taxonomy and never an alignment. The links are relative.

`bin/verify_regeneration.py` builds the first four generators' output in a scratch tree and compares
every file, symlinks by target, with the committed one. `bin/verify_manifests.py` checks that each
manifest describes its files: sequence counts, one alignment width, no absolute path. Both run in
`bin/analyses.sh`.

## Not committed

- `raw/ssu_all_r226.fna.gz`, 73 MB. It is fetched by URL and its sha256 is in `assets/datasets.yml`.
- `*.pfam`, the Pfam-format output of `cmalign`. `*.aligned.fasta` is the same alignment in the form
  everything downstream reads.
- `warn.txt`, the notes a generator writes about a dataset. The record is `truth.json`, which holds
  `n_requested`, `n_injected` and `rate_effective`. For example, a request for 101 injections at
  *k* = 10 gives 110, because groups of *k* cannot be split.
