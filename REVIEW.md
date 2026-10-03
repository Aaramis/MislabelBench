# Code review

A pass over every part of this repository, looking for defects rather than confirming that it works:
hardcoded paths, race conditions, assumptions nobody had checked, comments that disagree with their
code, and results that could not be reproduced.

The rule throughout was to **verify rather than conclude**. Where a doubt could be settled by running
something, it was, and several of the findings below are things that reading had already passed over —
one of them more than once.

Twenty findings. Three would have produced a wrong number, eleven were latent, and six were in work
done during the review itself. Twenty more came later, from repatriating the results, cloning the
repository to see whether it still worked, reading the traces of runs already published, and running
newly written code for the first time, rather than from reading it; they are at the end under their
own heading. One of those sixteen changes a published number by a factor of three, one is a job that
the corrected number predicted would run out of memory and then did, one was introduced by the
review itself and ran the whole repository on a login node, and one would have placed every fold
under the wrong substitution model.

## What was reviewed

| | |
|---|---|
| `main.nf` | grid construction, the branch by implementation, the four-way join into `COLLECTRUN` |
| `nextflow.config`, `conf/` | parameters, profiles, trace files, publishing |
| `modules/local/` | all four modules: containers, declared outputs against stub blocks, tool flags |
| `bin/` | 42 scripts: paths, error handling, division guards, condition selection |
| `slurm/` | 29 job scripts, the prelude, the submit wrapper |
| `assets/`, manifests | five dataset manifests against the files they describe, and the judgeability they claim |
| the results | 1 226 run records, cross-checked against the files they summarise |

The counts above were 29, 20 and 927 until they were compared against the repository: twenty-eight
files had been added since this table was written, including the four staged modules and fifteen
`bin/` scripts, and a review that states a coverage it no longer has is worse than one that states
none. The second pass over the added files produced findings 37 and 38.

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

## Found after this report was written

The review stopped at the code. Four defects were in what the code produces, and they came out of
repatriating results from the cluster rather than reading anything.

**21. The evidence behind every version 2 number was not in the repository.** `README.md` said
`results/` is tracked because the runs are the evidence and the tables are rebuilt from them. True of
version 1, whose 170 run directories carry `.log`, `.mis` and `run.json`. For version 2 only
`run.json` had been kept, and every detection number is computed from the `.mis` beside it:
`git ls-files | grep -c inj_` returned 0. A clone could not run `bin/analyses.sh`. 949 run
directories brought back and checked on arrival — `n_mislabels` agrees with its own `.mis` in all
949, which is also what would catch a file copied while a job was still publishing it.

**22. `truth.json` recorded the absolute path of its input**, in all 180 injected cells, so two
machines producing the same cell produced different files, and the field named the input without
identifying it. Now the input's name and sha256. This surfaced only because the claim it breaks was
tested: regenerating the grid on macOS reproduces the Linux `.tax` files byte for byte, and
`source` was the one field that could not match.

**23. A trace tag per job is not unique per submission.** `nextflow.config` names trace files by job
tag, which fixed four jobs colliding in one outdir. A job resubmitted after a failure still finds its
predecessor's file, warns once and writes nothing: the first Kexact run has no trace because the
attempt that died thirty seconds earlier had created the file. The Slurm job id is now appended.

**24. The container was never in the trace**, though the comment beside the trace block said
`trace.txt` is the only record of which image ran each task. `container` is not a default Nextflow
trace field. Appended to the default list, and confirmed with `-stub-run` that the field is accepted
and the column written.

A fifth suspicion did not survive. `trace-baseline.txt` has a header and no rows, and the natural
explanation was that a resumed run lists only what it recomputed. A resumed stub run writes eight
rows, six of them `CACHED`: resuming does not shorten a trace, and that file is simply lost.

**25. Two manifests named one machine.** `data/injected/datasets.json` carried
`/shared/home/agardette/bench/...` in all 360 of its path fields and `data/foreign/datasets.json` in
all 18, while `data/gtdb`'s had always been relative — which is what `main.nf`'s `resolvePath` is
for. `verify_manifests.py` had the opposite of a check: it saw `is_absolute()` and used the path as
given. It rejects one now, and its count, which assumed at most one problem per dataset, no longer
reports 196 datasets as minus 371 sound.

**26. `make_foreign.sh` required an image it was about to skip.** Singularity and Infernal were
demanded at the top, then used only inside a branch that does not run when
`donor_pool.aligned.fasta` exists — and it exists, in the repository. So a clone could not rebuild
the nine foreign cells with everything needed present. Required inside the branch now, and the nine
cells rebuilt on a Mac with no singularity come back with the Linux md5s.

**27. A timed run was never alone on the machine.** `maxForks` is a per-process directive, so one
set through `withLabel: process_timed` gives SATIVA one fork and SATIVAEPANG one fork — two tasks at
a time, not one. `trace-baseline2k.txt` has both submitted at 03:00:12, 0.021 s apart, running
together for 38 s at 537% and 797% CPU. `executor.queueSize = 1` when timed is the cap that counts
across processes; verified from two stub runs' traces, where the timed one has no overlap among its
eight tasks and the untimed one has three. Peak concurrency in the committed traces is 3 tasks and
23.2 cores, against 140 reserved and a 510-core exclusive node, so no published number moved.

**28. 737 of 949 records said the opposite of their job about their own timings.**
`--timing_trusted false` arrives as the String `"false"`, which is a true Groovy boolean, so every
grid and foreign cell recorded `true`. The coercion was fixed earlier and the 115 upstream cells run
since are right. What protected the tables was `resource_usage.py` skipping anything not named
`gtdb*` — a name convention doing the work of the flag designed for it. Flags corrected, with
`resource_usage.txt` unchanged, and `bin/verify_timing_flags.py` added as a gate that reads the
intent out of `slurm/*.sh` rather than restating it.

**29. `cpu_model` is in 641 of 949 records, and the README said all of them.** Five absentees are
trusted runs, which is the case that matters at a factor of two per core between generations.
`verify_runs.py` names them with their host now; `cpu-node-123`, which carries the four baselines,
reports `epyc-9754` to Slurm, the model their script pinned.

**30. A missing `.mis` scored as nought flags rather than failing.** `score_injection.py` tolerated a
path that did not exist, which was meant to make `--baseline-mis` optional and applied to the run
being scored too. An unexpanded shell glob therefore produced recall 0.000 for six conditions in a
row with no error. An absent baseline was worse: it came back as nought baseline flags, which would
have counted every flag in the run as added. Both fatal now; `aggregate_grid.py` over all 180 cells
still reproduces its committed summary unchanged, so nothing depended on the tolerance.

**31. Peak memory measured one process where the figure was read as the machine.** `run.json`'s
`max_rss_mb` is `ru_maxrss` over the waited-for children, so the largest single child. The comment
defending that in `resource_usage.py` stated its own undoing in the next sentence — "it would
understate a tool that ran several at once" — and the fork does, as soon as it has more than one
thread. Against the Nextflow traces the tree peak is **1.07x the largest child at T1, 3.55x at T8,
3.15x at T16** for the fork, and a flat 1.44 to 1.48 for upstream, so the gap appears exactly where
concurrency does.

Both figures are real and they answer different questions, so both are printed now. Per process it
is 1.3 MB per sequence, flat across a seventeen-fold size range and across thread counts. Per
machine it is 1.11 MB per sequence at one thread and 4.61 at eight, which is **36 GB at 7 051
sequences rather than 9.4** and a ratio against upstream of about **45x rather than 16x**. The
practical consequence is the largest database that fits in 64 GB: 58 850 sequences single-threaded,
**14 227 at the eight threads every run here uses**.

`process_timed` was also asking for a flat `16.GB`, below the real peak above about 3 400 sequences;
only the job scripts' `--mem` kept those runs alive.

**32. A failed placement task was ignored, and surfaced two minutes later as a JSON error.**
`scaling.sh` launched its N placement tasks with `&` and then a bare `wait`, which returns the status
of the last background job only; `set -e` does not fire for a background one either. An OOM-killed
task therefore left its folds unplaced, the tool wrote empty placement files, logged
`EPA-ng FAIL fold 5:` with nothing after the colon, carried on, and the run died four stages later in
scoring on `JSONDecodeError: Expecting value: line 1 column 1`. Each task is waited on by pid now,
with the status captured in the `||` branch — inside an `if ! wait` it is the status of the negation,
which was checked and did report "failed with status 0" for a task that exited 7.

**33. Two job scripts asked for less memory than the real peak.** `scaling.sh` carried `--mem=32G`,
fine on 2 023 sequences and not on 7 051, where the measured tree peak is 36 GB: every N=2 job was
OOM-killed within three minutes. `baseline.sh` asked 48G for the same set and survived on 33 %
headroom, chosen when the only figure available said 9.4 GB. Both raised; the other twenty scripts
were checked against the measured peak of what they run and none is within a factor of two.

**34. A file list interpolated into an ssh command string ran the repository on the login node.**
`bin/push_code.sh` compared checksums with `ssh host "cd ~/bench && md5sum $files"`, and `$files` is
newline-separated, so the remote shell took every filename after the first as a command. The login
node ran `slurm/submit.sh`, `slurm/scaling.sh` and the rest in sequence; `scaling.sh` built a
reference tree and placed folds there for fourteen minutes before failing. Nothing was lost, and
that was luck: `determinism.sh` and `make_foreign.sh` both begin with `rm -rf`, and both targets
happen to be committed and deterministic. The list goes over stdin now.

This one was introduced during the review, in tooling written an hour earlier to make a different
hazard safer.

**35. `determinism.sh` cleared a directory that was not there.** `rm -rf work_det
results/determinism` runs after `nf_launch_dir` has changed the working directory, so the relative
path resolved under `.nf/determinism`, where nothing of the sort exists; the outdir the job promises
to clear was never cleared. Found from the other side, when a stray run wrote a trace file into
`results/determinism` and left every other file in it dated three days earlier. Absolute now, and
the other twenty-one scripts were checked: every other `rm -rf` already uses an absolute path.

**36. The staged path's flags never arrived, and then its model did not either.** Both found on the
first real runs of the new code, both exiting 0. `withName: 'SATIVA|SATIVAEPANG'` does not match
`STAGEDREFERENCE`, so the tool ran without `-x`, printed its usage and stopped after 0.21 s — and
would have run `-m thorough`. Then `loo-tasks` was given no `run.model`, fell back to `GTR+G`, and
would have placed every fold under a model the reference stage never fitted, producing a `.mis`
that differs from the single-process one for a reason unrelated to distribution. What caught both
was a declared output, `run.refjson` and `run.l1o_tasks/model`; nothing in this repository would
have. After the fixes the two routes give byte-identical output, 93 flags and the same md5.

**A rule that came out of three false passes.** This check, the `set -- $pair` in the detection-law
comparison, and the matched-versus-unmatched check that compared two paths neither of which existed
all *passed* while testing nothing — twice because zsh does not word-split an unquoted variable and
once because `cmp -s` on two missing files returns 0. A shell check that passes is not evidence
until it has been shown to fail when it should.

**37. `agreement.py` drops a short row without saying so.** `read_mis` keeps a line only if it has
seven fields or more, silently, where `score_injection.py` warns in the same situation. A malformed
row would move a Jaccard figure with no trace. **Latent and shown to be latent**: across the 1 190
committed `.mis` files, 158 098 data rows are 8 or 9 fields wide — upstream's eight and the fork's
nine — and none is shorter.

**38. The binomial tail answered 1.0 where it should answer 0.** `conflict_enrichment.py` folded
`p <= 0` and `p >= 1` into one return, and with a rate of zero and `k >= 1` the upper tail is 0, not
1. Latent, because a tool that flags nothing gives `k = 0` as well, which an earlier branch catches
— but a conservative wrong answer in a significance test is the kind nobody questions. The function
is otherwise exact: checked against rational arithmetic with `Fraction` and `comb`, it reproduces
the published 0.000538 for 8 of 51 at p = 0.037, and `tests/test_scoring.py` now holds that check
along with the two degenerate rates and the n = 6531 case that overflowed once.

**39. The stem artefact was counted by exact equality and is a cluster.** `confidence_shape.py`
counts flags at exactly 0.510, which is what `parent_lhw_coeff` predicts — 0.51 to the parent, 0.49
to the taxon — and the column does spike there. It also has a thin shoulder that exact equality
misses: on the 7 051-sequence set upstream has 129 flags at exactly 0.510 and **148 within 0.005**,
the fork 155 and 164, with neighbours at 0.506 to 0.514 in ones and twos. So the published
concentration is a lower bound, understating the artefact's reach by 6 % for the fork and 15 % for
upstream. Both figures are reported now, because the spike is what the mechanism predicts and the
shoulder is what it does not — a few thousandths of placement weight landing somewhere the 0.51/0.49
split does not account for. No committed number changed; the band is an addition.

**40. A defaulting `.get` fabricated a published claim.** The README and the decision log said no
cell in 180 favours upstream at any *k*, with a column of zeros to show it. Eight do: five at *k*=1,
one at *k*=5, two at *k*=10. The zeros came from a throwaway script that built that table by reading
`paired_upstream_vs_epang_T8_K25.json` with `.get("cells_a_greater", 0)` — a field the record never
had, since it stores `cells_b_greater` and `cells_compared` and leaves the losses to be derived.

The sign test is sound, which is what the audit was for: recomputed with exact rational arithmetic
from the counts the record does hold, all five p-values match to three figures, and it takes `n` as
the non-tied pairs and `min(wins, n - wins)` as the tail, both correctly. What was wrong was the
reading. `paired_conditions.py` records and prints the losses and the ties now, because a field that
has to be derived is a field someone will default to zero.

This is the third instance of one shape in this review — an absent thing read as a benign value. The
others were a `cmp -s` on two paths neither of which existed and a `set -- $pair` that did not
word-split. D90's rule was about shell checks and it generalises: **an absent field, like a passing
check, is not evidence until something has been shown to fail.** The fix belongs in the record, not
only in the reader.

**The headline disagreement figure was audited by reimplementation**, not by rereading the script
that produces it: an independent pass over the `.mis` files reproduces all seven numbers in
`results/disagreement_truth.json` exactly — 180 cells, 11 178 injected, and the four buckets. The
recount also surfaced what the README was not saying: **both tools miss 5 617 of the 11 178
injections, 50.3 %**. The fork finds 48.7 % and upstream 38.6 %, so the gap between the tools is
real and smaller than the gap between either tool and the truth. Quoting 1 243 against 115 alone
invited the opposite impression.

Also checked on the added files and found correct: `duplicate_conflicts.py`'s
`first_disagreement`, which would raise on a single-label group and is only ever called on groups
filtered to have two, and its `all(n in raw for n in g)` guard, without which a name missing from
the unaligned file would have counted as an identical pair; and its percentage denominator, which
comes from the alignment while the groups come from the alignment intersected with the taxonomy —
the two cover exactly the same 7 051 and 2 023 names.

All of these came out of tests that should have been run earlier: clone the repository into an empty
directory and rebuild, read the traces of runs already published rather than the records derived from
them, and then watch what the corrected numbers predict. Finding 33 is the only one here that a
measurement predicted before the cluster confirmed it. After them, `bin/analyses.sh` runs to its last gate and 43 of the 45
committed tables come back byte-identical, the two that move being the ones that read the upstream
grid while it is still growing.

## Deferred, with reasons

Two pipeline-side improvements were held back while the upstream grid ran, on the grounds that
changing `bin/` or `main.nf` would cost that job its resume — which editing the pipeline between a
failure and its retry has already cost once. That was stated too broadly: the cluster copy of the
repository is an rsync of it and not a checkout, so a commit here cannot reach a running job. Both
are done, and what waits for the grid is the sync, not the edit.

- `collect_run.py` records the parse outcome as `sativa_timing`: `parsed`, `no match` or
  `log missing`. An absent phase timing used to mean either, and the second — a reworded log line —
  would empty the timings of every run at once with nothing failing.
- `main.nf` compares the number of `COLLECTRUN` records against datasets x conditions x replicates
  and exits 1 if they differ, so a dropped join fails the run instead of quietly shortening the grid.
  Checked with `-stub-run` on four cells, including a deliberately filtered timing channel.

`sativa_epang/` stays despite not being what runs: `scripts/README.md` builds version 1's RAxML
binaries from it, so removing it would make version 1's published figures unreproducible. It carries a
`NOT_WHAT_RUNS.md` saying so.
