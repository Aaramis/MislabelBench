# Nextflow traces

One file per pipeline submission: which task ran, on which node, how long it took, how much memory
it used, and what it exited with. These lived only on the cluster until now, which made them no
record at all. The HTML report and timeline Nextflow writes beside them are not kept: they are
rendered from the same data and are two megabytes each.

## The orchestrator's own version

A trace row names the container each task ran in, which pins the tool. It says nothing about the
Nextflow that ran it, and `nextflow.config`'s manifest only sets a floor -- `!>=24.10.0`, which Nextflow
enforces by refusing to start below it, but which is a minimum requirement and not a statement of what
was used. So the version was established from the evidence instead: **every one of the 43 pipeline job
logs on the cluster reports `N E X T F L O W  ~  version 26.04.4`, and none reports any other.** The
environment `slurm/prelude.sh` pins gives `nextflow version 26.04.4.12445`, checked on the cluster, and
it ships its own java, so the orchestrator is self-contained rather than depending on a module nobody
loads. Twelve such environments sit side by side there, from 22.10.0 up, and nothing else on the cluster
provides `nextflow` at all -- so a pin that went stale would fail loudly, which `prelude.sh` now makes it
do at the line that names the path.

No result here was produced by any version below 26.04.4, and none was tested on one.

Task rows per file, and the gaps, which are real and worth stating rather than leaving to be
noticed. Where a row names several files the number is their **total**, which three rows of this
table meant per file until `bin/verify_trace_table.py` found the column saying two things at once:

| file | rows | what it covers |
|---|---|---|
| `trace-grid_fork.txt` | 300 | 150 of the 720 fork-grid cells. Four jobs published into one outdir and the second and later ones failed to create their trace, which is what the per-tag naming in `nextflow.config` now prevents |
| `trace-grid_upstream.txt` | 213 | the upstream grid up to the job that died on the file quota, 210 completed and 3 not |
| `trace-sizes.txt` | 60 | the size gradient, complete |
| `trace-kaxis.txt` | 60 | 58 completed, 2 not |
| `trace-foreign.txt` | 36 | the foreign-sequence cells, complete |
| `trace-threads.txt` | 36 | the thread sweep, complete |
| `trace-baseline2k.txt` | 4 | complete |
| `trace-ksweep.txt` | 4 | complete |
| `trace-determinism.txt` | 2 | complete |
| `trace-nf.txt` | 2 | complete |
| `trace-grid_up_species.txt` | 2 | one of the two jobs that died within a minute and a half on 3 October. The Kexact one is renamed because the successful run an hour later found it already there and wrote nothing, which is the collision the job id in the tag now prevents; the file was moved aside so the next Kexact submission can write its own |
| `trace-kexact_k2_attempt1.txt` | 2 | the other, described in the row above |
| `trace-baseline.txt` | 0 | header only. The baseline job's trace was lost before per-tag naming existed, and nothing can recover it |

Everything that arrived after the table above was written, which is 66 files and **819 task rows** --
nearly as many again as the 721 listed above, and absent from a document whose purpose is to
enumerate them. Grouped rather than listed one by one, since what they have in common is what matters:

| files | rows | what they cover |
|---|---|---|
| `trace-grid_missing_epang_T8_K25_2183990.txt`, `trace-grid_missing_epang_T8_K25_2183986.txt`, `trace-grid_missing_epang_T8_K25_tree_2184020.txt`, `trace-grid_missing_epang_T8_K5_2184019.txt`, `trace-grid_missing_epang_T8_K5_tree_2184021.txt`, `trace-grid_missing_upstream_raxml_T8_2183991.txt`, `trace-grid_missing_upstream_raxml_T8_2183987.txt` | 189 | the jobs that filled the grid's remaining cells, one per condition; the two at 0 rows found nothing left to run |
| `trace-grid_up_missing.txt` | 150 | the upstream grid's completion after the file-quota death |
| `trace-simulation_2184272.txt`, `trace-simulation_2184091.txt` | 200 | 2.1's control, the second job completing what the first began |
| `trace-kind3_2184084.txt` | 36 | error kind 3, nine cells under both tools |
| `trace-staged_timed_f7_2177364.txt`, `trace-staged_timed_f13_2177363.txt`, `trace-staged_timed_f25_2177362.txt`, `trace-staged_check_2177253.txt` | 31 | the staged runs behind `results/staged_scaling_f*.txt` and DISTRIBUTION.md |
| `trace-m1_check_2182101.txt`, `trace-inputs_check_2183078.txt`, `trace-kexact_k2.txt`, `trace-determinism_2182091.txt` | 14 | the M1 validation, an input check, the Kexact pair, and the determinism rerun |
| `trace-kexact_k2_2201201.txt` | 2 | strict leave-one-out at *k*=1, 5 October, the end of the *k* axis where one label is wrong per family and the fold scheme has nothing to co-remove |
| `trace-kexact_k2_2232070.txt` | 2 | strict leave-one-out at *k*=3, 6 October, the cell that closed the *k* axis |
| `trace-kexact_k2_2197932.txt` | 2 | strict leave-one-out at *k*=5, 5 October, the midpoint of the engine/folds decomposition |
| `trace-kexact_k2_2194012.txt` | 2 | strict leave-one-out at *k*=10, 5 October, the cell that extends the engine/folds decomposition along *k* |
| `trace-determinism_2192792.txt` | 2 | the determinism rerun on the rebuilt cluster, 5 October: same cell, same seed, containers pulled again, the same `.mis` |
| `trace-grid_k5_local.txt`, `trace-grid_tree_local.txt`, `trace-grid_up_species_local.txt`, `trace-kaxis_upstream_local.txt`, `trace-kexact_k2_local.txt`, `trace-ksweep_local.txt`, `trace-sizes_local.txt`, `trace-threads_local.txt` | 0 | eight `_local` traces with a header and nothing else: submissions that failed before a task ran |
| `trace-ragged_2296741.txt` | 60 | the ragged-lineage grid, 7 October: fifteen cells at family distance and rate 0.05 under both tools, complete. `results/ragged_cost.txt` is read off these runs |
| `trace-staged_timed_f25_2281826.txt`, `trace-staged_timed_f13_2281828.txt`, `trace-staged_timed_f7_2281829.txt`, `trace-staged_timed_f25_2296742.txt`, `trace-staged_timed_f13_2296743.txt`, `trace-staged_timed_f7_2296744.txt` | 0 | six header-only traces from the two attempts to measure the staged rounds with `--exclusive`. Not a failure to launch: the launchers ran, and every stage they submitted pended on `QOSMaxCpuPerUserLimit` because an exclusive job is charged all 510 cores of the node against a 600-core cap. They are kept because they are the record behind finding 164 and behind the panel still carrying the non-exclusive numbers |
| `trace-threads_gtdb_arc400_2324036.txt`, `trace-threads_gtdb_arc800_2324037.txt` | 24 | the sequential comparison extended off 2 023 sequences: `epang_T1_K25` and `upstream_raxml_T1` at 402 and 801, three replicates each, which gave 15.3x in core-seconds at the smallest size against 18.4 to 18.5 above it and showed `-T 1` giving SATIVA 1.99 cores at every size |
| `trace-memstep_gtdb_arc800_epang_T1_K25_2322823.txt`, `trace-memstep_gtdb_arc800_epang_T1_K25_2322824.txt`, `trace-memstep_gtdb_arc800_epang_T1_K25_2322825.txt` | 6 | the test of finding 200: one thread at 801 sequences, where the eight-thread pool holds an outlier at a third of its siblings. The prediction was 913 to 921 MB and all three runs give 899, which puts the three eight-thread runs at 3.99, 4.33 and 1.25 placements live at the high-water moment |
| `trace-memstep_gtdb_arc1200_epang_T1_K25_2321524.txt`, `trace-memstep_gtdb_arc1200_epang_T1_K25_2321527.txt`, `trace-memstep_gtdb_arc2500_epang_T8_K25_2321525.txt`, `trace-memstep_gtdb_arc2500_epang_T8_K25_2321528.txt`, `trace-memstep_gtdb_arc400_epang_T1_K25_2321523.txt`, `trace-memstep_gtdb_arc400_epang_T1_K25_2321526.txt` | 12 | two more replicates of each of the three single-run points of the memory probe, submitted for the reason finding 198 gives. They confirmed the one-thread law to the megabyte and moved the 2 507-sequence figure from 4.98 to 5.06 MB per sequence |
| `trace-memstep_gtdb_arc1200_epang_T1_K25_2312895.txt`, `trace-memstep_gtdb_arc400_epang_T1_K25_2312894.txt` | 4 | the single-thread half of the memory probe: `epang_T1_K25` at 402 and 7 051 sequences, which gives 1.18 and 1.15 MB per sequence against 4.59 and 5.13 at eight threads and shows the rise with size belongs to the tool's own concurrency rather than to the reference |
| `trace-memstep_gtdb_arc2500_2311369.txt`, `trace-memstep_gtdb_arc3000_2309969.txt`, `trace-memstep_gtdb_arc3000_2311367.txt`, `trace-memstep_gtdb_arc3000_2311368.txt` | 8 | the memory-step probe of 8 October, `slurm/memstep.sh`: one run at 2 507 sequences and three at 3 001, which placed the transition in the fork's memory per sequence between 2 023 and 3 001 and corrected it from a step to a transition. Untimed, so only `peak_rss` is read from them |
| `trace-staged_check_2307514.txt` | 9 | the staged check of 8 October, the first run whose `run.json` carries the executed argv and the tool's own host |
| `trace-staged_timed_f13_r1_2302506.txt`, `trace-staged_timed_f13_r2_2302509.txt`, `trace-staged_timed_f13_r3_2302512.txt`, `trace-staged_timed_f25_r1_2302505.txt`, `trace-staged_timed_f25_r2_2302508.txt`, `trace-staged_timed_f25_r3_2302511.txt`, `trace-staged_timed_f7_r1_2302507.txt`, `trace-staged_timed_f7_r2_2302510.txt`, `trace-staged_timed_f7_r3_2302513.txt` | 66 | the nine staged timing rounds of 8 October, three replicates of each shard count, chained so no two of ours overlapped. They replace the three rounds of 5 October in the scaling panel rather than being averaged with them: the same cell on the same node with a byte-identical `.mis` took 194.5 s for its placement then and 237.0, 243.4 and 235.3 now. `shard_nodes-*.tsv` beside each trace records which node every shard ran on, and the answer is `cpu-node-121` in all nine |

`bin/verify_trace_table.py` keeps this honest -- every `trace-*.txt` in this directory must be named
here, every row count stated in either table must be the file's, and each table's own totals must be
what the sentence introducing it says. It also reads the other way, which is the only check here that
does: every run collected on or after 2026-10-03 must be named by some trace, so a trace left behind on
the cluster is a failure rather than a silence. It runs in `bin/analyses.sh`.

A resumed run does list its cached tasks, with status `CACHED` rather than `COMPLETED`, so resuming
does not silently shorten a trace. Checked with `-stub-run`: six cached and two run, eight rows.

None of these files is read by any script in `bin/`. Every number in `results/` comes from
`run.json`, which records wall clock, CPU time, peak RSS, host and CPU model independently of the
trace. These are provenance, not measurements.

## One trace recovered from its report

`trace-kexact_k2_recovered.txt` is not a trace file. The Kexact run that produced
`inj_family_r0.05_k2_s1__epang_T8_Kexact__rep1` wrote no trace, having found its predecessor's file
already there, but it did write `report-kexact_k2.html` at completion, and that embeds the same task
records as JSON under `window.data`. `bin/recover_trace_from_report.py` extracts them: 4 259 s for
the placement at a process-tree peak of 9.83 GB, 0.85 s for the collection, and the two container
images by path. `submit` is epoch milliseconds and the durations are milliseconds, which is how the
report stores them; `%cpu` is not recoverable, being empty or uninterpretable there.

The report's `peak_rss` is calibrated against the text traces rather than assumed to mean the same
thing: for a fork-grid task the report gives 9 968 144 384 where `trace-grid_fork.txt` gives 9.3 GB.
So the 9.83 GB here is comparable, and it is what started the peak-memory finding in `REVIEW.md` —
the `run.json` for the same run says 2.49 GB.

**This file cannot be rebuilt.** `report-kexact_k2.html` is gone from the repository and from the
cluster, overwritten by a later Kexact run writing the same untagged name: the same collision that
destroyed the original trace and that per-tag naming now prevents. The six reports still on the
cluster are all per-tag. What the file says is corroborated without it, which is why no number here
depends on a file nobody has: the five sibling Kexact runs each have their own committed trace and peak
at 9.2 to 9.7 GB against this run's 9.83, and this cell's own `run.json` gives 4 257.74 s against the
4 259.3 recovered here.
