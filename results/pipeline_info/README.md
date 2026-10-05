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

Everything that arrived after the table above was written, which is 27 files and **620 task rows** --
more than half as many again as the 719 listed above, and absent from a document whose purpose is to
enumerate them. Grouped rather than listed one by one, since what they have in common is what matters:

| files | rows | what they cover |
|---|---|---|
| `trace-grid_missing_epang_T8_K25_2183990.txt`, `trace-grid_missing_epang_T8_K25_2183986.txt`, `trace-grid_missing_epang_T8_K25_tree_2184020.txt`, `trace-grid_missing_epang_T8_K5_2184019.txt`, `trace-grid_missing_epang_T8_K5_tree_2184021.txt`, `trace-grid_missing_upstream_raxml_T8_2183991.txt`, `trace-grid_missing_upstream_raxml_T8_2183987.txt` | 189 | the jobs that filled the grid's remaining cells, one per condition; the two at 0 rows found nothing left to run |
| `trace-grid_up_missing.txt` | 150 | the upstream grid's completion after the file-quota death |
| `trace-simulation_2184272.txt`, `trace-simulation_2184091.txt` | 200 | 2.1's control, the second job completing what the first began |
| `trace-kind3_2184084.txt` | 36 | error kind 3, nine cells under both tools |
| `trace-staged_timed_f7_2177364.txt`, `trace-staged_timed_f13_2177363.txt`, `trace-staged_timed_f25_2177362.txt`, `trace-staged_check_2177253.txt` | 31 | the staged runs behind `results/staged_scaling_f*.txt` and DISTRIBUTION.md |
| `trace-m1_check_2182101.txt`, `trace-inputs_check_2183078.txt`, `trace-kexact_k2.txt`, `trace-determinism_2182091.txt` | 14 | the M1 validation, an input check, the Kexact pair, and the determinism rerun |
| `trace-determinism_2192792.txt` | 2 | the determinism rerun on the rebuilt cluster, 5 October: same cell, same seed, containers pulled again, the same `.mis` |
| `trace-grid_k5_local.txt`, `trace-grid_tree_local.txt`, `trace-grid_up_species_local.txt`, `trace-kaxis_upstream_local.txt`, `trace-kexact_k2_local.txt`, `trace-ksweep_local.txt`, `trace-sizes_local.txt`, `trace-threads_local.txt` | 0 | eight `_local` traces with a header and nothing else: submissions that failed before a task ran |

`bin/verify_trace_table.py` keeps this honest -- every `trace-*.txt` in this directory must be named
here, and every row count stated in either table must be the file's. It runs in `bin/analyses.sh`.

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
