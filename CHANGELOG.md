# Changelog

## 1.0 (2026)

First release. The repository is the evidence behind the SATIVA-epang application note.

- 180 injected datasets, datasets for the four other error types, a control on
  sequences simulated along a RAxML Grove tree, and a bacterial replication, all rebuilt from seeds and checked byte for byte
  (`bin/verify/verify_regeneration.py`).
- A Nextflow workflow running SATIVA and SATIVA-epang in containers pinned by tag and by digest
  (`assets/containers.yml`), with the leave-one-out split in four stages.
- `bin/analyses.sh` rebuilds every table and runs every check.
- Code under MIT, data and results under CC BY-SA 4.0.

**Correction of the first version.** The first public state of this repository (branch `main` before this
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
