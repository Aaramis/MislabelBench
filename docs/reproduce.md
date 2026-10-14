# Reproducing the paper

Every number in the paper comes from a run directory under `results/`, and `bin/analyses.sh` rebuilds
every table from those runs. Two ways to check the work.

**Rebuild the tables from the committed runs.** No cluster, about half an hour.

```bash
python3 -m unittest discover -s tests
bin/analyses.sh
git status results/     # only logs and tables whose inputs changed should differ
```

`bin/analyses.sh` stops at the first failing check. It runs each `bin/verify_*.py` gate: the datasets
against their manifests, each generated cell against its seed, the grid against its design, every
timed run against its flags, and every published recall against a second implementation.

**Rerun an experiment.** Needs Nextflow, Singularity and a Slurm cluster, see [cluster.md](cluster.md).
Each script writes into `results/<name>/`. The resources are the request in the script's header.

## Datasets

| script | builds | needs |
|---|---|---|
| `slurm/make_grid.sh` | the 180 injected cells (kinds 1, 2 and 4) | nothing |
| `slurm/make_foreign.sh` | 9 cells of foreign sequences (kind 6) | nothing |
| `slurm/make_clade.sh` | 9 cells with a whole taxon relabelled (kind 3) | nothing |
| `slurm/make_chimera.sh` | 36 chimera cells (kind 7) | nothing |
| `slurm/make_ragged.sh` | the ragged-lineage cells (kind 5) | nothing |
| `slurm/make_width.sh` | the 2023-sequence set at five alignment widths | nothing |
| `slurm/make_grid_bac.sh` | the 15 cells of the bacterial replication | `slurm/fetch_bacterial_clade.sh` |
| `slurm/fetch_grove.sh`, `make_grove_simulation.sh` | the simulated control on a RAxML Grove tree | network, about 140 MB |

The base sets (GTDB r226 archaea, alignment on Rfam RF01959) are committed under `data/gtdb/`. The
download and the filtering are in `bin/prepare_gtdb.py`, and every source is pinned by sha256 in
`assets/datasets.yml`. `bin/verify_regeneration.py` rebuilds the first four generators in a scratch
directory and compares every file with the committed one.

## Experiments

Run `slurm/submit.sh slurm/<script>.sh`. The runs are committed, so none of this is needed to check the
tables.

| script | experiment | output in `results/` |
|---|---|---|
| `baseline.sh`, `base2k.sh`, `baseline_bac2k.sh`, `bac.sh` | both tools on the unmodified databases | `baseline*/`, `agreement_*.json` |
| `grid_fork.sh`, `grid_k5.sh`, `grid_treeorder.sh` | SATIVA-epang over the 180 cells, with *K* = 25 and 5 and tree-ordered folds | `grid_fork/`, `grid_summary_*.json` |
| `grid_upstream.sh`, `grid_upstream_species.sh`, `grid_upstream_missing.sh` | SATIVA over the same cells | `grid_fork/`, `grid_summary_upstream_raxml_T8.json` |
| `kaxis_upstream.sh`, `ksweep.sh` | the *k* axis and the *K* sweep | `kaxis/`, `ksweep/` |
| `kexact_k2.sh` | strict leave-one-out (one sequence per fold) | `grid_fork/`, `kexact_*` |
| `foreign.sh` | kind 6, foreign sequences | `foreign/`, `foreign_summary_*.json` |
| `kind3.sh` | kind 3, whole taxa relabelled | `clade/`, `clade_detection_*.json` |
| `chimera.sh` | kind 7, chimeras | `chimera/`, `chimera_detection_*.json` |
| `ragged_grid.sh` | kind 5, ragged lineages | `ragged/`, `ragged_cost.json` |
| `grove_simulation.sh` | the control on a Grove tree | `grove_simulated/` |
| `bac.sh` | the bacterial replication | `grid_bac/`, `grid_summary_bac_*.json` |
| `sizes.sh`, `scaling.sh` | time and memory against reference size | `sizes/`, `scaling/`, `resource_usage.txt` |
| `threads.sh` | the thread sweep | `threads/` |
| `memstep.sh`, `width.sh` | the memory law, against size and alignment width | `memstep_*/`, `width/`, `memory_width.json` |
| `staged_timed.sh`, `staged_nodes.sh`, `staged_check.sh` | the four-stage run, distributed over shards | `staged_*/`, `staged_scaling_*.txt` |
| `placements.sh`, `placements_upstream.sh` | placements of both engines on one cell, for the engine comparison | `placements_*/` |
| `minimal_case.sh` | the smallest dataset where the tools disagree | `minimal_case/` |
| `determinism.sh` | the same cell and seed twice | `determinism/` |
| `aldiscore.sh` | alignment difficulty of each set | `aldiscore/` |

The timed experiments (`baseline`, `sizes`, `threads`, `scaling`, `staged_*`) pin the CPU model, see
the rules in [cluster.md](cluster.md). Their seconds are comparable only within one model.

## Where each result is made

`bin/analyses.sh` is the index. Each step is named when it runs, and each script says in its header
what it reads and writes. The figures are `bin/main_figure.py` (figure 3 of the paper, with its values in
`results/figure3_values.tsv`) and `bin/supplement_figures.py`. Every supplement table is named by its
`\fichier{...}` in the supplement source.

## What is not committed

The runs of the largest experiments carry their placement files, which are too large for git. They are
archived on Zenodo, see the main [README](../README.md#citation). Everything the tables need is in the
repository.

`bin/make_archive.sh` packs these ignored files under `results/` into one `.tar.zst` with a
`SHA256SUMS`, which is what the second Zenodo record holds. Unpack it at the repository root to restore
them.
