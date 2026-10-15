# Changelog

## Unreleased
- Panel D of the paper figure (`results/figure3.svg`) shows the share of each group (initial flags, injected errors,
  collateral flags), each summing to 100, instead of the mean number of sequences per dataset. The mean number per
  group is printed under its title and written to `results/figure3_values.tsv`. The counts per dataset are still in
  `results/upset_tables.txt`. No other table, figure or number changes.

## 1.1 (2026)

Tidying of the repository after the first release. No table, figure or number of the application note
changes: `bin/analyses.sh` rebuilds all 59 tables identically.

- 7,425 tracked files become 5,093. Removed: 1,936 run logs that no check reads, the UNITE fungal
  reference, a simulated control made by hand (the RAxML Grove one stays), the 50 alignments and trees of
  `results/shared_reference` (its summary and the three `.mis` stay), and 28 derived tables that the
  supplement does not use, with the scripts that built them.
- `slurm/` is grouped into `data/`, `detection/`, `timing/` and `checks/`, and `bin/` into `data/`,
  `analysis/`, `verify/`, `figures/`, `timing/` and `ops/`. Every path in the documents, the tests and
  the continuous integration follows.
- The continuous integration runs the trace-table and document-path checks as two separate steps.
- Author order in `CITATION.cff` and `.zenodo.json`: Gardette, Lundin, Zucker, Stamatakis, Belda.

## 1.0 (2026)

First release. The repository is the evidence behind the SATIVA-epang application note.

- 180 injected datasets, datasets for the four other error types, a control on
  sequences simulated along a RAxML Grove tree, and a bacterial replication, all rebuilt from seeds and checked byte for byte
  (`bin/verify/verify_regeneration.py`).
- A Nextflow workflow running SATIVA and SATIVA-epang in containers pinned by tag and by digest
  (`assets/containers.yml`), with the leave-one-out split in four stages.
- `bin/analyses.sh` rebuilds every table and runs every check.
- Code under MIT, data and results under CC BY-SA 4.0.

**Correction of the first version.** The first public state of this repository (before this
release) reported, on ITS data with one replicate per scenario, that SATIVA finds 28 of 33 injected
errors and SATIVA-epang 33 of 33, and that every miss comes from several sequences sharing one wrong
label. The 180-dataset grid does not bear that out. Recall falls with the number of sequences sharing
the wrong label for both tools, and SATIVA-epang finds more errors only at intermediate numbers
(see [docs/results.md](docs/results.md)). Do not cite the earlier claim.

**Cleaning for release**

- Removed the internal audit log and the scripts and results of probes that no table reads.
- Cluster paths, the remote host and the Nextflow environment are now variables, with the IFB values as
  defaults. `BENCH_ROOT` defaults to the repository.
- The pinned image of Infernal is the one that produced the alignment (`..._4`). The unused
  `ALIGNSSU` module is gone.
- Absolute paths in the committed logs and manifests are replaced by `$BENCH_ROOT` and `$HOME`.
