# Code review

A pass over every part of this repository, looking for defects rather than confirming that it works:
hardcoded paths, race conditions, assumptions nobody had checked, comments that disagree with their
code, and results that could not be reproduced.

The rule throughout was to **verify rather than conclude**. Where a doubt could be settled by running
something, it was, and several of the findings below are things that reading had already passed over —
one of them more than once.

Twenty findings. Three would have produced a wrong number, eleven were latent, and six were in work
done during the review itself.

## What was reviewed

| | |
|---|---|
| `main.nf` | grid construction, the branch by implementation, the four-way join into `COLLECTRUN` |
| `nextflow.config`, `conf/` | parameters, profiles, trace files, publishing |
| `modules/local/` | all four modules: containers, declared outputs against stub blocks, tool flags |
| `bin/` | 29 scripts: paths, error handling, division guards, condition selection |
| `slurm/` | 20 job scripts, the prelude, the submit wrapper |
| `assets/`, manifests | five dataset manifests against the files they describe |
| the results | 927 run records, cross-checked against the files they summarise |

## Findings that produced a wrong number

**1. `--timing_trusted false` arrived as the string `"false"`.** A non-empty string is truthy in
Groovy, so the ternary that set `maxForks` always took the first branch and every untimed run was
serialised. Worse, `timing_trusted` was recorded as `true` in run records that had shared a machine.
Fixed by coercing once, `params.timed = params.timing_trusted.toString().toBoolean()`, and 195 run
records were rewritten.

**2. `slurm/scaling.sh` measured a different algorithm.** It passed only `-x BAC`, omitting the
`-m ultrafast -C 0.4 -p 42 -S` that `conf/modules.config` gives every other run. `-m` defaults to
`thorough`, a full constrained RAxML search, so the reference build came out at 249 s where the rest
of the benchmark sees 19 s. The measurement was discarded and the flags now live in one array with a
comment naming where they come from.

**3. Timed runs were not pinned to a CPU model.** The partition mixes four generations whose per-core
speed differs by about a factor of two, and `run.json` recorded the hostname but not the model. A
reserved allocation appeared 25 % faster than an exclusive one when the only difference was a 2014
xeon against a 2023 epyc. Timed jobs now pass `--constraint`, every run records `cpu_model`, and
measurements are replicated.

## Findings that were latent

**4. `BENCH_ROOT` was honoured on one line per script.** Every Slurm script resolved `prelude.sh`
through `${BENCH_ROOT:-$HOME/bench}` and then reached for `$HOME/bench` directly for the `cd`, the
`--outdir`, the data and the `bin` path: 30 lines across 16 scripts. The variable made the scripts
look relocatable when they were not, so a reader cloning the repo would either fail or, if `~/bench`
happened to exist, run against someone else's data. Verified fixed by relocation, not by reading.

**5. A manifest's relative paths resolved against the launch directory.** Harmless while every job
launched from the repo root, and broken the moment each got its own directory so they could run
concurrently. `main.nf` now resolves them against `projectDir`.

**6. The python container was a floating tag.** Three of four modules pinned with a build string;
`COLLECTRUN`, which writes every `run.json`, used `python:3.12`. Pinned to `3.12.12`, which exists on
conda-forge, quay.io and depot.galaxyproject.org, so all three paths pin to the same thing — a digest
would have pinned only the docker one.

**7. Concurrent jobs overwrote each other's trace files.** Four job scripts publish into one `outdir`,
and once they ran at once the second and every job after it died on `FileAlreadyExistsException` for
`pipeline_info/report.html`. Nextflow only warns, so the runs finished and nothing flagged it: the
trace, report and timeline of 540 of 720 cells were never written. No result was wrong; the execution
provenance was lost. Each job now writes a tagged set.

**8. A failed run would have entered the tables.** `_timeit.py` reports the tool's return code and
exits 0; `collect_run.py` turns it into a status and also exits 0. Nothing downstream read that field:
the timing scripts read `wall_sec` and the detection scripts read the `.mis` directly. A tool that
died halfway would have contributed its surviving seconds to a median and a truncated `.mis` to a
recall, as zero detections. All 927 runs are ok, which is the only reason this cost nothing.
`verify_runs.py` is now a gate.

**9. A dropped cell would have been invisible.** Nextflow's `join` discards unmatched elements
silently, so a cell whose four outputs failed to pair would vanish and leave only a smaller
denominator. Fourteen of fifteen grid-and-condition pairs are exactly complete and the fifteenth is
still running, so it has never happened. `verify_grid_complete.py` now enumerates what should be there.

**10. `column_comparison.py` divided by a count that can be zero.** The number of flags at the stem
confidence is 31.3 % on this grid, so it never bit; on a dataset where `parent_lhw_coeff` never fires
it would have raised `ZeroDivisionError`. It now reports the absence.

**11. Two scripts globbed every condition at once.** Correct while one condition had been run, and a
silent mixture once four fold orders and the comparator shared the runs directory: the first rebuild
after the K=5 grid reported 772 cells where 180 existed. Both now require `--condition`.

**12. Manifests were never checked against their files.** `n_seqs` and `aln_len` are declared by hand,
flow into `meta` and are recorded in every `run.json`. All 196 datasets across 5 manifests agree, and
`verify_manifests.py` now insists on it.

**13. The home filesystem has a file quota, not a byte quota.** 100 000 files; the home held 85 219,
of which work directories were 66 000. The upstream grid died after 8 h 39 on `Failed to publish file`,
which names nothing. Space was never close: 50 GB of 100. `cleanup = true` now removes a run's work
directory on success, which was verified safe first — every published output is `mode: 'copy'` and a
real file, so with symlink publishing the same change would have destroyed every result.

**14. `conf/ifb.config` was dead and contradicted three later decisions.** Declared as a profile,
documented with its own command line, used by nothing. It set `executor = 'slurm'` where the harness
runs Nextflow inside one sbatch, `clusterOptions = '--exclusive'` which bills 510 cores against a
600-core quota, and no `--constraint`. A config that would silently undo three fixes is worse than
none; removed.

**15. The README advertised a claim the grid refuted.** Its headline said upstream found 28 of 33
injected mislabels and this version 33, and that every miss came from shared labels "which a strict
leave-one-out cannot see and a fold can". Recall falls with *k* for both tools alike. Rewritten; the
version 1 setup instructions moved to `scripts/README.md` rather than deleted, since `RESULTS.md`
cites those numbers.

## Findings in work done during the review

These are recorded because the pattern matters more than the instances: six of twenty defects were
introduced or missed by the review itself.

**16. A mechanical rewrite left `${BENCH_ROOT:-$BENCH_ROOT}` in 13 scripts.** The first pass aborted
part way and mangled them; the second skipped them because they no longer contained the string it was
looking for; and the verification grepped for that same absent string, so it could not have failed.
With the variable unset the default is empty and every path becomes absolute at `/`.

**17. A hand-written rank map omitted `class`.** `collateral_locality.py` carried
`{"species": 6, ..., "phylum": 1}` and died on the cells added for the rank Daniel asked about. It now
derives the map from the canonical list, so the next rank cannot reproduce it.

**18. A silent zero from a name prefix.** `fold_composition.py` reported `0/0` same-species pairs
because the tool writes leaves as `r_<name>` and the join matched nothing. An empty join now fails
loudly.

**19. A dict comprehension collapsed a grid to one slice.** `fold_mechanism.py` used
`{r["k"]: r for r in rows}`, which keeps whichever row sorts last. Harmless on the fifteen-cell sweeps
it was written for and wrong the moment it was pointed at 180 cells, where it reported the species/5 %
slice as if it were the whole grid. This one changed a conclusion before it was caught.

**20. A script was only ever run with `python3` in front.** `collateral_locality.py` had no shebang,
so invoking it by name ran it through the shell. Invisible for as long as the file existed, and found
by running `analyses.sh` rather than by reading it.

## What was checked and found correct

Worth stating, because an audit that only lists faults does not say what it covered.

- **Stub blocks.** All four modules create every output their declaration names, each with its own
  `mkdir -p`. Stub runs are how every config and wiring change here was validated, so a stub omitting
  an output would have weakened all of those; none does.
- **Tool symmetry.** Both tool modules export the same three BLAS thread variables from
  `meta.threads` and pass the same `-T`. An asymmetry would have invalidated the speed comparison
  rather than shading it.
- **`RUSAGE_CHILDREN` covers the subprocess tree.** `user_cpu_sec` includes RAxML and EPA-ng and not
  only the python parent, which is what the cores-used analysis rests on.
- **Derived fields.** `n_mislabels` agrees with its `.mis` in all 927 runs, the phase-timing regex
  matched every log, and `reftree + l1out` is consistent with the reported total throughout.
- **Error handling.** No bare `except` and no `except Exception` in `bin/`; the two captures are
  narrow. This mattered because an `except Exception` early in the project swallowed a `NameError` and
  invalidated a set of validation numbers.
- **Determinism.** Two independent runs on different nodes with separate work directories produce
  byte-identical `.mis`.
- **Reproducibility of the tables.** `bin/analyses.sh` rebuilds every committed result from the run
  directories, and five of six come back byte-identical; the sixth is a timing table still gaining
  replicates.

## Deferred, with reasons

Two pipeline-side improvements wait for the upstream grid to finish, because `bin/` is staged into
every task and `main.nf` sets the project revision, so changing either now would cost that job its
resume — which editing the pipeline between a failure and its retry has already cost once.

- `collect_run.py` should record explicitly whether the phase-timing regex matched, rather than
  leaving its absence to be inferred. The analysis-side gate already reports it.
- `main.nf` should compare the cell count against what `COLLECTRUN` emitted, so the pipeline notices a
  dropped join itself rather than relying on a later check.

`sativa_epang/` stays despite not being what runs: `scripts/README.md` builds version 1's RAxML
binaries from it, so removing it would make version 1's published figures unreproducible. It carries a
`NOT_WHAT_RUNS.md` saying so.
