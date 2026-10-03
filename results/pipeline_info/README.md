# Nextflow traces

One file per pipeline submission: which task ran, on which node, how long it took, how much memory
it used, and what it exited with. These lived only on the cluster until now, which made them no
record at all. The HTML report and timeline Nextflow writes beside them are not kept: they are
rendered from the same data and are two megabytes each.

Task rows per file, and the gaps, which are real and worth stating rather than leaving to be
noticed:

| file | rows | what it covers |
|---|---|---|
| `trace-grid_fork.txt` | 300 | 150 of the 720 fork-grid cells. Four jobs published into one outdir and the second and later ones failed to create their trace, which is what the per-tag naming in `nextflow.config` now prevents |
| `trace-grid_upstream.txt` | 213 | the upstream grid up to the job that died on the file quota, 210 completed and 3 not |
| `trace-sizes.txt` | 60 | the size gradient, complete |
| `trace-kaxis.txt` | 60 | 58 completed, 2 not |
| `trace-foreign.txt` | 36 | the foreign-sequence cells, complete |
| `trace-threads.txt` | 36 | the thread sweep, complete |
| `trace-baseline2k.txt`, `trace-ksweep.txt` | 4 | complete |
| `trace-determinism.txt`, `trace-nf.txt` | 2 | complete |
| `trace-grid_up_species.txt`, `trace-kexact_k2.txt` | 2 | the two jobs that died within a minute and a half on 3 October |
| `trace-baseline.txt` | 0 | header only. The baseline job's trace was lost before per-tag naming existed, and nothing can recover it |

A resumed run does list its cached tasks, with status `CACHED` rather than `COMPLETED`, so resuming
does not silently shorten a trace. Checked with `-stub-run`: six cached and two run, eight rows.

None of these files is read by any script in `bin/`. Every number in `results/` comes from
`run.json`, which records wall clock, CPU time, peak RSS, host and CPU model independently of the
trace. These are provenance, not measurements.
