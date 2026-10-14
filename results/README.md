# Results

Everything here is a run or a table built from runs. `bin/analyses.sh` rebuilds every table from the
runs and then runs the checks, so a changed script shows up as a diff. A run directory holds `run.json`
(tool, condition, seed, time, memory, CPU model), the `.mis` the tool wrote, and its logs. Machine paths
in the logs are replaced by `$BENCH_ROOT` and `$HOME`. The placement files and the unabridged logs of
the largest experiments are in the release archive, not in git.

| folder | experiment | made by |
|---|---|---|
| `baseline*`, `agreement_*` | both tools on the unmodified databases | `baseline.sh`, `base2k.sh`, `baseline_bac2k.sh`, `bac.sh` |
| `grid_fork/` | the 180 datasets, SATIVA-epang and SATIVA | `grid_fork.sh`, `grid_upstream*.sh`, `grid_k5.sh`, `grid_treeorder.sh` |
| `grid_summary_*.json`, `detection_law_*.json`, `paired_*.json` | recall tables built from `grid_fork/` | `bin/analyses.sh` |
| `kaxis/`, `ksweep/` | the *k* axis and the *K* sweep | `kaxis_upstream.sh`, `ksweep.sh` |
| `clade/`, `foreign/`, `chimera/`, `ragged/` | the other error types | `kind3.sh`, `foreign.sh`, `chimera.sh`, `ragged_grid.sh` |
| `simulated/`, `grove_simulated/` | the two controls | `simulation.sh`, `grove_simulation.sh` |
| `grid_bac/` | the bacterial replication | `bac.sh` |
| `sizes/`, `scaling/`, `threads/`, `memstep_*`, `width/` | time and memory against size, threads and width | `sizes.sh`, `scaling.sh`, `threads.sh`, `memstep.sh`, `width.sh` |
| `staged_*` | the four-stage run on one and several nodes | `staged_timed.sh`, `staged_nodes.sh`, `staged_check.sh` |
| `placements_k25/`, `placements_kexact/`, `shared_reference/` | placements of both engines on one dataset | `placements*.sh`, `shared_reference.sh` |
| `minimal_case/` | the smallest dataset where the tools disagree | `minimal_case.sh` |
| `determinism/`, `inputs_check/` | byte-identical repeats, input checks | `determinism.sh`, `inputs_check.sh` |
| `aldiscore/` | alignment difficulty | `aldiscore.sh` |
| `pipeline_info/` | one Nextflow trace per submission, see its README | the workflow |
| `figure3.svg`, `figure3_values.tsv` | figure 3 of the note and its values | `bin/main_figure.py` |
| `supplement_figures/`, `supplement_figures_values.tsv`, `paired_stats.tsv`, `upset_tables.txt` | the supplement's figures and statistics | `bin/supplement_figures.py`, `paired_stats.py`, `upset_tables.py` |

The other `*.json`, `*.txt` and `*.tsv` at this level are tables read by the supplement or by another step. Each is made by
the script of the same name in `bin/`, for example `resource_usage.txt` by `bin/resource_usage.py`. [docs/reproduce.md](../docs/reproduce.md) maps each experiment to its script,
and [docs/results.md](../docs/results.md) says what the numbers show.
