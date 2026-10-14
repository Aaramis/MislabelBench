# Nextflow traces

One file per pipeline submission: which task ran, on which node, for how long, with how much memory,
and its exit status. They are provenance, not measurements. No script in `bin/` reads them. Every
number in `results/` comes from the `run.json` of each run, which records wall clock, CPU time, peak
memory, host and CPU model on its own.

The HTML report and timeline Nextflow writes beside each trace are not kept. They hold the same data
and weigh two megabytes each.

## Nextflow version

Every pipeline job log reports Nextflow 26.04.4, and none reports any other. `slurm/prelude.sh` pins
that version. No result here was produced or tested with an earlier one.

## Files

Where a row names several files, the count is their total.

| files | rows | what they cover |
|---|---|---|
| `trace-grid_k5_local.txt`, `trace-grid_tree_local.txt`, `trace-grid_up_species_local.txt`, `trace-kaxis_upstream_local.txt`, `trace-kexact_k2_local.txt`, `trace-ksweep_local.txt`, `trace-sizes_local.txt`, `trace-threads_local.txt` | 0 | Eight header-only files: submissions that failed before a task ran. |
| `trace-grid_fork.txt` | 300 | Fork grid, first 150 of the 720 cells. Four jobs shared one output directory and only the first wrote a trace; per-tag naming in `nextflow.config` now prevents this. |
| `trace-grid_missing_epang_T8_K25_2183986.txt`, `trace-grid_missing_epang_T8_K25_2183990.txt`, `trace-grid_missing_epang_T8_K25_tree_2184020.txt`, `trace-grid_missing_epang_T8_K5_2184019.txt`, `trace-grid_missing_epang_T8_K5_tree_2184021.txt` | 181 | Jobs that filled the remaining fork-grid cells, one per condition. The empty ones found nothing left to run. |
| `trace-grid_upstream.txt`, `trace-grid_up_species.txt`, `trace-grid_up_missing.txt`, `trace-grid_missing_upstream_raxml_T8_2183987.txt`, `trace-grid_missing_upstream_raxml_T8_2183991.txt` | 373 | Upstream grid, including the completion after the job that died on the file quota. |
| `trace-sizes.txt` | 60 | Size gradient. |
| `trace-kaxis.txt` | 60 | The *k* axis. Two cells did not complete. |
| `trace-foreign.txt` | 36 | Foreign-sequence cells. |
| `trace-threads.txt`, `trace-threads_gtdb_arc400_2324036.txt`, `trace-threads_gtdb_arc800_2324037.txt` | 60 | Thread sweep, extended to the smaller sizes. |
| `trace-baseline.txt`, `trace-baseline2k.txt`, `trace-baseline_2360005.txt`, `trace-baseline_bac2k_2339220.txt`, `trace-baseline_bac_2337573.txt` | 16 | Baseline runs on the unmodified references. The first has a header only: its trace was lost before per-tag naming existed. |
| `trace-ksweep.txt` | 4 | The *K* sweep. |
| `trace-determinism.txt`, `trace-determinism_2182091.txt`, `trace-determinism_2192792.txt`, `trace-nf.txt` | 8 | Determinism reruns and the Nextflow check. |
| `trace-simulation_2184091.txt`, `trace-simulation_2184272.txt` | 200 | Simulated control, in two jobs. |
| `trace-kind3_2184084.txt`, `trace-m1_check_2182101.txt`, `trace-inputs_check_2183078.txt` | 46 | Error kind 3, the M1 validation and an input check. |
| `trace-chimera_2336622.txt`, `trace-chimera_2336970.txt` | 144 | Chimera grid. The first job has a header only. |
| `trace-grid_bac_2337573.txt` | 60 | Bacterial grid. |
| `trace-grove_simulation_2336966.txt` | 148 | Simulation on the RAxML Grove tree. |
| `trace-ragged_2296741.txt` | 60 | Ragged-lineage grid. |
| `trace-placements_k25_2337570.txt`, `trace-placements_k25_2337652.txt`, `trace-placements_kexact_2336626.txt`, `trace-placements_kexact_2337570.txt`, `trace-placements_kexact_2337652.txt`, `trace-placements_kexact_2339044.txt` | 83 | Placement reruns. Rows with status `CACHED` are tasks resumed from an earlier run. |
| `trace-kexact_k2.txt`, `trace-kexact_k2_2194012.txt`, `trace-kexact_k2_2197932.txt`, `trace-kexact_k2_2201201.txt`, `trace-kexact_k2_2232070.txt`, `trace-kexact_k2_attempt1.txt`, `trace-kexact_k2_recovered.txt` | 14 | Strict leave-one-out runs, one per *k*. `trace-kexact_k2_recovered.txt` is not a Nextflow trace. It was rebuilt from an HTML report that is no longer kept, because the original trace had been overwritten. `trace-kexact_k2_attempt1.txt` is a run that died within two minutes. |
| `trace-memstep_gtdb_arc1200_epang_T1_K25_2312895.txt`, `trace-memstep_gtdb_arc1200_epang_T1_K25_2321524.txt`, `trace-memstep_gtdb_arc1200_epang_T1_K25_2321527.txt`, `trace-memstep_gtdb_arc2500_2311369.txt`, `trace-memstep_gtdb_arc2500_epang_T8_K25_2321525.txt`, `trace-memstep_gtdb_arc2500_epang_T8_K25_2321528.txt`, `trace-memstep_gtdb_arc3000_2309969.txt`, `trace-memstep_gtdb_arc3000_2311367.txt`, `trace-memstep_gtdb_arc3000_2311368.txt`, `trace-memstep_gtdb_arc400_epang_T1_K25_2312894.txt`, `trace-memstep_gtdb_arc400_epang_T1_K25_2321523.txt`, `trace-memstep_gtdb_arc400_epang_T1_K25_2321526.txt`, `trace-memstep_gtdb_arc800_epang_T1_K25_2322823.txt`, `trace-memstep_gtdb_arc800_epang_T1_K25_2322824.txt`, `trace-memstep_gtdb_arc800_epang_T1_K25_2322825.txt` | 30 | Memory probes at 402 to 7051 sequences, with one thread and with eight. Untimed, only `peak_rss` is read. |
| `trace-width_2341720.txt` | 20 | Memory against alignment width. |
| `trace-staged_check_2177253.txt`, `trace-staged_check_2307514.txt`, `trace-staged_check_2325079.txt` | 27 | Staged checks, the first runs whose `run.json` holds the executed command and the host. |
| `trace-staged_timed_f13_r1_2302506.txt`, `trace-staged_timed_f13_r2_2302509.txt`, `trace-staged_timed_f13_r3_2302512.txt`, `trace-staged_timed_f25_r1_2302505.txt`, `trace-staged_timed_f25_r2_2302508.txt`, `trace-staged_timed_f25_r3_2302511.txt`, `trace-staged_timed_f7_r1_2302507.txt`, `trace-staged_timed_f7_r2_2302510.txt`, `trace-staged_timed_f7_r3_2302513.txt` | 66 | Staged timing rounds, three replicates of 7, 13 and 25 shards, chained so none overlapped. They replace the earlier rounds in the scaling panel. `shard_nodes-*.tsv` lists the node of each shard. |
| `trace-staged_nodes_n4_r1_2337807.txt`, `trace-staged_nodes_n4_r2_2337624.txt`, `trace-staged_nodes_n4_r3_2337625.txt`, `trace-staged_nodes_n4_r4_2360006.txt` | 36 | Staged runs on four nodes, four replicates. `shard_nodes-*.tsv` lists the node of each shard. |
| `trace-staged_timed_f13_2177363.txt`, `trace-staged_timed_f13_2281828.txt`, `trace-staged_timed_f13_2296743.txt`, `trace-staged_timed_f25_2177362.txt`, `trace-staged_timed_f25_2281826.txt`, `trace-staged_timed_f25_2296742.txt`, `trace-staged_timed_f7_2177364.txt`, `trace-staged_timed_f7_2281829.txt`, `trace-staged_timed_f7_2296744.txt` | 22 | Earlier staged timing rounds. The header-only files come from attempts with `--exclusive`, whose jobs stayed pending because an exclusive job is charged all 510 cores of a node against a 600-core cap. |

`bin/verify_trace_table.py` checks this page. Every `trace-*.txt` here must be named in the table,
every row count must match its files, and every run collected since 2026-10-03 must appear in some
trace. A trace left on the cluster is therefore a failure and not a silence. It runs in
`bin/analyses.sh`.

A resumed run lists its cached tasks with status `CACHED`, so resuming does not shorten a trace.
