# Results

Everything here is a run or a table built from runs. `bin/analyses.sh` rebuilds every table from the
runs and then runs the checks, so a changed script shows up as a diff. A run directory holds `run.json`
(tool, condition, seed, time, memory, CPU model), the `.mis` the tool wrote, and its logs. Machine paths
in the logs are replaced by `$BENCH_ROOT` and `$HOME`. The placement files and the unabridged logs of
the largest experiments are in the release archive, not in git.

| folder | experiment | made by |
|---|---|---|
| `baseline*`, `agreement_*` | both tools on the unmodified databases | `slurm/detection/baseline.sh`, `slurm/detection/base2k.sh`, `slurm/detection/baseline_bac2k.sh`, `slurm/detection/bac.sh` |
| `grid_fork/` | the 180 datasets, SATIVA-epang and SATIVA | `slurm/detection/grid_fork.sh`, `slurm/detection/grid_upstream*.sh`, `slurm/detection/grid_k5.sh`, `slurm/detection/grid_treeorder.sh` |
| `grid_summary_*.json`, `detection_law_*.json`, `paired_*.json` | recall tables built from `grid_fork/` | `bin/analyses.sh` |
| `kaxis/`, `ksweep/` | the *k* axis and the *K* sweep | `slurm/detection/kaxis_upstream.sh`, `slurm/detection/ksweep.sh` |
| `clade/`, `foreign/`, `chimera/`, `ragged/` | the other error types | `slurm/detection/kind3.sh`, `slurm/detection/foreign.sh`, `slurm/detection/chimera.sh`, `slurm/detection/ragged_grid.sh` |
| `grove_simulated/` | the simulated control | `slurm/detection/grove_simulation.sh` |
| `grid_bac/` | the bacterial replication | `slurm/detection/bac.sh` |
| `sizes/`, `scaling/`, `threads/`, `memstep_*`, `width/` | time and memory against size, threads and width | `slurm/timing/sizes.sh`, `slurm/timing/scaling.sh`, `slurm/timing/threads.sh`, `slurm/timing/memstep.sh`, `slurm/timing/width.sh` |
| `staged_*` | the four-stage run on one and several nodes | `slurm/timing/staged_timed.sh`, `slurm/timing/staged_nodes.sh`, `slurm/timing/staged_check.sh` |
| `placements_k25/`, `placements_kexact/`, `shared_reference/` | placements of both engines on one dataset | `slurm/checks/placements*.sh`, `slurm/detection/shared_reference.sh` |
| `minimal_case/` | the smallest dataset where the tools disagree | `slurm/detection/minimal_case.sh` |
| `determinism/`, `inputs_check/` | byte-identical repeats, input checks | `slurm/checks/determinism.sh`, `slurm/checks/inputs_check.sh` |
| `aldiscore/` | alignment difficulty | `slurm/checks/aldiscore.sh` |
| `pipeline_info/` | one Nextflow trace per submission, see its README | the workflow |
| `figure3.svg`, `figure3_values.tsv` | figure 3 of the note and its values | `bin/main_figure.py` |
| `supplement_figures/`, `supplement_figures_values.tsv`, `paired_stats.tsv`, `upset_tables.txt` | the supplement's figures and statistics | `bin/supplement_figures.py`, `paired_stats.py`, `upset_tables.py` |

The other `*.json`, `*.txt` and `*.tsv` at this level are tables read by the supplement or by another step. Each is made by
the script of the same name in `bin/`, for example `resource_usage.txt` by `bin/resource_usage.py`. [docs/reproduce.md](../docs/reproduce.md) maps each experiment to its script,
and [docs/results.md](../docs/results.md) says what the numbers show.
