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
| `trace-grid_up_species.txt`, `trace-kexact_k2_attempt1.txt` | 2 | the two jobs that died within a minute and a half on 3 October. The Kexact one is renamed because the successful run an hour later found it already there and wrote nothing, which is the collision the job id in the tag now prevents; the file was moved aside so the next Kexact submission can write its own |
| `trace-baseline.txt` | 0 | header only. The baseline job's trace was lost before per-tag naming existed, and nothing can recover it |

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
