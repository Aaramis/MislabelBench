# Code review

A pass over every part of this repository, looking for defects rather than confirming that it works:
hardcoded paths, race conditions, assumptions nobody had checked, comments that disagree with their
code, and results that could not be reproduced.

The rule throughout was to **verify rather than conclude**. Where a doubt could be settled by running
something, it was, and several of the findings below are things that reading had already passed over —
one of them more than once.

Twenty findings. Three would have produced a wrong number, eleven were latent, and six were in work
done during the review itself. Thirty-three more came later, from repatriating the results, cloning the
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

- **`bin/disagreement_truth.py`.** Covers all 180 cells with 30 at each of the six distances, so the
  bias it warns about -- directory order over-representing whichever distances sort first -- is absent
  here. Its arithmetic closes exactly: 4203 both + 115 upstream-only + 1243 fork-only + 5617 missed by
  both = 11 178 injected. Its set-based flag counting agrees with a row count, 25 772 either way, with
  no sequence listed twice in any of the 180 `.mis`. And the result is strong: 26.5 % of the fork's
  unique flags are injected against 4.3 % of upstream's.
- **The grid's provenance is uniform.** All 180 upstream cells were produced by three separate jobs --
  the main grid, a species-first job, and a job for whatever was missing after the work directory was
  deleted for quota -- and every one records `sativa`, `raxml`, 8 threads and `timing_trusted` false.
  Assembling a grid out of three runs is the kind of thing that leaves a seam; this one has none.
- **The donor pool is deterministic across machines.** Rebuilt on the cluster a day after the local
  copies, `donor_pool.fasta`, `.tax` and `.aligned.fasta` all match by md5 with the same 600 names.
- **`bin/dataset_field.py`.** Resolves the manifest relative to its own file rather than the working
  directory, and names the known datasets or fields when asked for one that is absent. Its one trap
  was cosmetic and is fixed: a non-scalar field printed as a Python repr, so `counts` could not be
  piped to a parser.
- **Every job script, swept for the four faults that would be systematic.** All 33 under `slurm/` set
  `set -euo pipefail` except `prelude.sh`, which is sourced and must not impose `-e` on its caller.
  All source the prelude except `submit.sh`, which runs from a login shell and needs nothing from it,
  and `make_grid.sh`, which validates `BENCH_ROOT` by consequence: it `cd`s into it at line 10 under
  `set -e`, so a wrong root fails at the first use rather than writing somewhere unintended. Every
  omission of `require_singularity` is correct -- the fetch scripts and `rebuild_primary.sh` only
  download and parse, and `staged_timed.sh` launches through Slurm, where each task gets its own node
  and the launcher needs no container runtime. The one `rm -rf` with a relative operand is
  `determinism.sh`'s `work_det`, deliberate and documented beside the absolute outdir that the same
  line clears, which is where that bug was.
- **The rest of `slurm/`, read rather than swept.** `slurm/grid_fork.sh`, `grid_upstream.sh`,
  `grid_k5.sh`, `grid_treeorder.sh`, `grid_upstream_missing.sh`, `grid_upstream_species.sh` and
  `kexact_k2.sh` all publish into one `--outdir`, from six different launch directories, concurrently
  by design. That is safe and was checked rather than assumed: run directories are per (cell,
  condition), and `timeline`, `report` and `trace` are all named by `--trace_tag`, which every job
  passes -- so nothing collides. The grid they produced is complete: **180 cells in each of five
  conditions plus the two Kexact cells, 902 run directories, every one holding a `run.json` and a
  `.mis`, zero incomplete.** `grid_upstream` and `grid_up_species` are missing their report and
  timeline because those are written at completion and both jobs died -- `sacct` and the log say
  CANCELLED and "Disk quota exceeded", which is the documented event `grid_upstream_missing.sh` exists
  to clean up after, not a hidden fault.
- **`slurm/base2k.sh` and `slurm/foreign.sh`**: consistent with the timed/untimed policy -- base2k takes
  the node exclusively with the model pinned and declares `timing_trusted true`, foreign does neither
  and declares false.
- **`slurm/m1_check.sh` and `slurm/staged_check.sh`** assert rather than report: each compares a `.mis`
  against a committed reference and exits non-zero if it differs. Both references are tracked -- the v1
  `n800` run, the `baseline2k` run and the whole of `data_ascii` -- so both scripts work from a clone,
  which is what makes their verdicts worth anything.
- **Both cardinality guards in `main.nf` are live, and `slurm/guard_probe.sh` is how that is known.**
  `join()` pairs on the meta map and drops whatever finds no partner without a word, so a cell that lost
  one of its outputs would never reach `COLLECTRUN` and a short grid would look complete. The only
  protection is two counters that call `error()` inside a `.count().subscribe { }` closure -- on the
  dataflow thread, where whether a thrown exception reaches the launcher is a property of the runtime and
  not something to reason about. Four stub runs settle it: each path with its expected count untouched and
  then off by one. Untouched, both pass, which also checks the arithmetic, since the staged guard counts
  only the fork conditions and a wrong expression there would fail a correct run. Off by one, both fail,
  **each through its own message** -- "collected 2 run records for 3 cells" and "staged path scored 1 cells
  for 2 fork cells", read per file after a `grep` across both logs had been unable to tell them apart. A
  stub run executes no tool, so the probe costs seconds and can be rerun against any Nextflow version,
  which is the point: this is a guarantee about the runtime's behaviour, not about this repository's code.
## What this report does not cover

`bin/review_coverage.py` lists the repository's reviewable files and names the ones this report never
mentions. That is not a claim those files were never read — most went
through the first pass as a batch — but a file the report never names has at best been read without
record, and this review found out what that costs: `bin/_timeit.py` produces every second and every
memory figure here and went unexamined through forty-eight findings, because it sat inside a coverage
count that had quietly stopped being true.

The count is gone, replaced by a list that cannot drift. Run the script, not the prose.

Every job script has since been read line by line, which is what that note had been waiting for, and
the reading produced findings 67 through 72. **The list is now empty: 91 of 91.** The mechanical sweep
for the four systematic faults is recorded above and still stands; it was a sweep and not a review,
which is why the scripts were left unnamed until they had actually been read. An empty list is not a
claim that nothing is left to find -- `bin/review_coverage.py` counts names, not understanding, and the
faults in findings 67 to 72 sat in files that a previous pass had already walked past. The one entry
with no logic in it is `slurm/bad_nodes.txt`, which is generated: `prelude.sh` appends a node that
turns out to lack singularity and `submit.sh` passes the list as `--exclude`, so the cluster is learned
once instead of rediscovered by every job. It holds four: cpu-node-127 through 130.

## The whole of it, reproduced from a clone

The claim the rest of this report rests on, tested rather than asserted, and retested after forty
commits had changed four output formats:

```
git clone -b nextflow <repo> fresh && cd fresh
bash slurm/make_grid.sh && bash slurm/make_foreign.sh
bin/analyses.sh
git status --short | grep -v '^??'      # 0 lines
```

**Zero of the tracked files under `results/` differs.** Twenty-two analysis steps run, the gates among
them: every run record checked clean, every one agreeing with the `--timing_trusted` its job script
declared and with no outdir unclaimed, 196 datasets across five manifests sound, 180 injected cells
and 9 foreign cells verified against their truth, and every grid complete at 180 of 180.

The counts are deliberately not written out here. They were — 5 231 files and 1 019 records — and
two days of work moved them to 5 245 and 1 022, which is the drift this report has already recorded
twice, in its own coverage table and in a comment quoting a figure the script beside it computes.
The gates print their counts and `git status` prints the diff.

No cluster, no container, no network. The two `make_` scripts rebuild the 189 generated cells from
their seeds, which is why they are not committed, and this run checked that directly instead of
deferring to `data/README.md`: **all 378 regenerated files byte-identical**, and then every one of the
41 tracked tables rewritten -- counted, because a clean `git status` over files nothing rewrote would
say nothing at all. Only the three version 1 files are left alone, which is now stated rather than
implied.

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

**41. One numeric default stood where a measurement belongs.** `resource_usage.py` read
`d.get("user_cpu_sec") or 0` and `d.get("max_rss_mb") or 0` into the tuples behind the medians of
CPU time and peak memory. A record missing either field would have put a zero into a published
median and shifted it down silently. It has never fired — all 56 trusted records with a `wall_sec`
carry both fields, none zero — which is the reason to make it loud rather than leave it, since the
records added next are the ones nobody has checked. Such a record is now excluded and named.

Found by sweeping for the shape rather than waiting for it: every defaulting `.get` in `bin/` was
inventoried, and the rest are dict lookups on internal structures or accumulator initialisations —
`collateral_locality.py`'s `.get(d, (0, 0))` is the starting value for a new key, not a substitute
for data.

Denominators were the other half of that sweep, since the judgeability error was a denominator and
not a default. `conflict_enrichment.py`'s base rate uses `len(tax)` and draws its conflicts from the
same population, and all 870 flagged names across both baseline runs are in that taxonomy, so the
group sizes and the expected counts are over one population. The unguarded divisions that remain
would raise `ZeroDivisionError` rather than print a wrong number, and a crash announces itself; six
guards would be churn, and the class worth hunting is the silent one.

This is the third instance of one shape in this review — an absent thing read as a benign value. The
others were a `cmp -s` on two paths neither of which existed and a `set -- $pair` that did not
word-split. D90's rule was about shell checks and it generalises: **an absent field, like a passing
check, is not evidence until something has been shown to fail.** The fix belongs in the record, not
only in the reader.

**42. A range was published as a plus-or-minus.** `scaling_summary.py` computes `max(v) - min(v)`
over the replicates and printed it as `195.59 ± 0.67`, which reads as a standard deviation or a
symmetric uncertainty and is neither; `scaling.sh`'s comment went further and called 7.8 on a mean of
27.9 "a standard deviation of 28%". With three replicates the range is the honest summary and the
sign was not. The figures are unchanged, now bracketed with the column labelled and the header
stating what they are, and `DISTRIBUTION.md` says it once for the tables it carries.

Found by sweeping comments that state a number — the mandate's comment-against-code class made
checkable, since a numeric claim can be tested and a prose one argued about. 218 such lines. The
sweep found one stale figure beside the mislabelling: `column_comparison.py` said 31.5 % of the
grid's flags sit at 0.510, measured when the grid was partial, where the complete grid gives 31.3 %.
That comment no longer carries a copy of a number the script computes four lines above it.

Two claims checked and holding, which is the more useful half: `subset_taxa.py` says preferring taxa
that have siblings produced a subset judgeable at 100 % against a source at 72.7 %, and that taking
groups as they come reproduces the source profile to within a few points — the source measures
72.7 % at species and the subset 74.9 %, so 2.2 points, and that comment predates
`bin/dataset_shape.py` and agrees with it, which makes each a check on the other.
`confidence_shape.py`'s 355, 391 and 405 flags and its 88 % are the baseline measurements, and
355/405 is 87.7 %.

**43. The injection rate is not the rate requested, and nothing said so.** The grid injects whole
groups of *k* sequences sharing one wrong label, and the loop stops after a group has reached the
target, so the last group always completes and the overshoot is up to *k*−1. The warning fired only
on a shortfall. **90 of the 180 cells carry more injections than their rate asks**, by 9 of 101 at
*k*=10 and rate 0.05 — an effective 5.44 % against 5.00 %. Averaged over the grid the effective rate
rises with *k*: 2.99 % at *k*=1 to 3.21 % at *k*=10, a 7.1 % relative increase **on the axis that
carries the main result**.

Protocol.md says cells are "dropped rather than silently rounded"; they are rounded up. Whole groups
are the right semantics — *k* sequences sharing a wrong label is what *k* means — so the behaviour
stays and the record changed: `truth.json` carries `n_requested` and `rate_effective`, the script
says so on stderr when it rounds, and the numbers are in the comment. The 180 truth files were
regenerated and differ from their predecessors in those two fields alone; rebuilding every table
changes nothing, because recall has always been a fraction of `n_injected`.

Which direction it cuts, since a confound on the main axis has to be answered and not only declared:
more corruption makes a cell harder, and the extra corruption is at high *k* where recall is already
lowest. It reinforces the fall from 0.92 at *k*=1 to 0.13 at *k*=10 rather than producing it, and a
7 % change in corruption cannot produce a sevenfold change in recall.

**44. The *k* axis is not an independent variable, and nothing said so.** Injecting *k* sequences
from one taxon needs a taxon with *k*+1 members, so raising *k* shrinks the eligible pool and shifts
it towards large taxa — 319 species-level taxa qualify at *k*=1 and 31 at *k*=10. The donor groups
used go from a median of 3 members to 14, and **the share of each group carrying the wrong label
rises from 0.34 to 0.67**.

That share is the quantity the detection law identifies as the predictor, so *k* is a proxy for it
and the design cannot pull them apart: holding group size fixed while varying *k* would leave 31
taxa to draw from. The *k* table and the surviving-label curve are the same axis seen twice, which
is why recall falls 0.92 to 0.13 along it. Not a defect in the code — a limitation of the design that
the repository reported around without stating, and a reviewer reading the *k* table as an
independent sweep would be entitled to ask.

This is the same class as finding 43 and came from the same question: what does the design promise,
and does it deliver. Two in one pass, both on the axis the headline result is measured along.

**45. The invariant the injection design rests on was never checked.** `inject_mislabels.py`
enforces `floor = k + 1` so a donor taxon always retains a correctly labelled member — that is what
gives leave-one-out something true to place an injected sequence against. A fully relabelled group
would be undetectable by construction and its sequences would sit in the truth as misses no method
could find: a silent ceiling on recall with no trace in any file. `verify_injection.py` checked that
the labels are the ones truth records, which is a different claim.

It holds: **0 orphaned donor groups across all 180 cells**, so the design's load-bearing assumption
moves from reasoned to measured. It is a gate now rather than a measurement taken once, and shown to
fail before being trusted to pass — on a fabricated cell where both members of a two-member group
are relabelled, it names the group and exits 1.

One detail decided whether the gate would work at all: membership comes from the base taxonomy and
not from the injected file. A wrong label is drawn from a real taxon at the same prefix, so a
sequence relabelled *into* a group makes that group look populated when its own members have all
been relabelled away — reading the injected file would have passed on exactly the case the check
exists to catch.

**46. The detectability ceiling was never localised to the set it bounds.** The 7 051-sequence set
has 847 groups of byte-identical rows and 54 carrying conflicting labels — 7 first disagreeing at
phylum, 6 at class — which the protocol presents, correctly, as a ceiling on what any method placing
this marker can find. The grid does not run on that set. The 2 023-sequence subset has 241 identical
groups and **3 conflicting, none above genus**, which is what chance gives: 54 groups each needing
both members to survive a 29 % subsample is 4.4 expected.

So the ceiling bounds the agreement figures, measured on the 7 051 set, and does not bound the recall
figures, measured on the 2 023 one. Worth stating because it cuts both ways — it localises a
limitation and it removes a doubt about the grid that a reader would otherwise be right to raise.

**Four protocol figures checked against the committed results while finding this, all holding
exactly**: 82 of 103 flags shared at 2 023 with Jaccard 0.796, 350 of 520 at 7 051 with 0.673, 54
conflicting groups, 265 sequences in one. Three other protocol figures were wrong this week, which
is the reason to check the rest rather than the reason to assume they are too.

**47. The `.mis` original-label column does not always describe the sequence beside it.** SATIVA
collapses identical sequences into taxonomic clusters and reports the cluster representative's
lineage, marked `__TAXCLUSTER<n>__`. Measured over the grid: **2 642 of 127 172 flagged rows, 2.08 %**,
carry an `OriginalTaxonomyPath` that is not a prefix of the named sequence's own lineage in that
cell's taxonomy; 185 of those are injected sequences, **0.71 % of all 25 996 injected rows**. The same
sequence fails in all five conditions of a cell, which is what identified the cause as the tool's
clustering rather than a run reading the wrong input.

One function read that column — `mismatch_rank`, feeding `recall_at_injected_rank` — and it now
prefers the lineage the cell's own taxonomy gives an injected sequence. **Nothing published is
affected**, which is why 0.71 % is a bound and not a correction: that metric appears in no committed
table, nothing aggregates it, and it lives only in the per-cell `score.json` that `.gitignore`
excludes. The plain recall figure was never at risk — it matches names against names and reads no
lineage.

Found by testing a claim nothing records: Protocol.md 2.5 says both tools run on the identical
database in every cell, and `run.json` does not record which bytes a run consumed. So the check had
to be the claim's consequence — every flagged row's declared lineage must match the cell it claims —
and the exceptions turned out to be the tool, not a mix-up. **The claim stands and is still
unrecorded**, which is the next thing worth fixing: an input digest in `run.json` would make it
provable rather than inferable.

**48. Four gates could pass without checking anything.** Found by the newest one doing it:
`verify_inputs.py`, written to prove both tools read the same database, printed "0 cells with
recorded input digests, 0 consistent" and **exited 0** having matched no files — the job script had
left the working directory at the Nextflow launch dir, so the relative glob resolved under `.nf/`.
The instrument built to prevent a silent pass performed one.

The same question put to the other six found three with the identical shape — a counter starting at
zero, a loop over a glob, a summary line printed either way: `verify_injection.py` and
`verify_foreign.py` reporting "0 cells checked, 0 sound", `verify_timing_flags.py` reporting
"0 run records checked". All four refuse now, each checked by running it where nothing matches, and
`verify_timing_flags.py` also refuses when no job script declares an outdir and a trust flag, which
would otherwise make every record unclaimed and nothing wrong. `verify_manifests.py` and
`verify_runs.py` already guarded it.

**What this closed.** `inputs_check.sh` ran one cell under both tools and the digests are identical,
so Protocol.md 2.5's premise — both tools read the identical database — is now evidence rather than a
property of how `main.nf` happens to be written.

**49. The script behind every second in the benchmark had not been read.** `bin/_timeit.py` produces
every `wall_sec` and every `max_rss_mb`. Two faults, neither of which bit.

It timed with `time.time()`, which NTP can step, where a duration needs `time.monotonic()`. At the
precision quoted here — a spread of 0.67 s on 195.59 — a correction of a few hundred milliseconds
would be visible.

**And the check is worth more than the fix.** Across the 430 runs appearing in both a `run.json` and
a Nextflow trace, keyed on `(outdir, run_name)`, the two independent measurements differ by more than
2 s or 2 % in **three**: −21.8, +11.1, −2.1 s. A clock step shows as a one-sided outlier; this is the
trace's integer-second rounding, and `_timeit` exceeds the trace in 85 of 430, which is the symmetry
that says so. So every published second is now cross-validated against a measurement taken by other
means.

`ru_maxrss` is kilobytes on Linux and bytes on macOS, so the fixed divisor was wrong by 1024 on one
platform. Nothing here measures on a Mac, and the wrong answer looks plausible: a `sleep 0.4`
reported **11 808 MB** while demonstrating the timeout path. Divisor by platform now.

The first attempt at the cross-validation keyed on `run_name` alone and reported 25 outliers up to
+911 s. `gtdb_arc1200__upstream_raxml_T8__rep1` exists under both `results/baseline` and
`results/sizes`, so it compared different runs on different nodes — **the third time in this review
that a check compared the wrong things**, and the reason the outliers were chased rather than
reported.

**50. The detection law's two tables could disagree in silence.** `detection_law.py` produces the
claim the rest of the analysis leans on — that what predicts detection is the fraction of a
sequence's surviving relatives carrying the wrong label — and was never named in this report either.
The arithmetic is right: after removing one injected sequence its group holds *k*−1 relatives with
the wrong label and `group_size`−*k* with the right one, summing to `group_size`−1, so the ratio is
(*k*−1)/(`group_size`−1), strictly below 1 because `floor = k + 1` guarantees a survivor and exactly
0 at *k*=1 whatever the group size — finding 44 arriving from the other direction.

One path was unguarded. `group_size` is a `defaultdict`, so a true lineage absent from the base
taxonomy gives `right = -k`, a negative ratio, a negative bucket index, and a row tallied into a
bucket the print loop never visits: dropped from the ratio table while `by_k` keeps it, the two
tables disagreeing on their totals with nothing to say so. **Unreachable in the data** — of 11 178
injected sequences, 0 have a missing lineage, 0 sit in a group without a survivor, 0 give a negative
denominator — so the fix is the comparison that would have caught it rather than a defensive branch:
the two tables count the same sequences, and the script now stops if they disagree.

**51. A format mismatch was reported as a measurement.** `threshold_holdout.py` supports a claim the
protocol makes outright — thresholds chosen on one seed and reported on the others — and the coverage
list said this report had never named it.

**The hold-out is clean.** Candidate thresholds come from the selection seed alone, the choice is made
by a budget evaluated on that seed alone, and the held-out cells are consulted only afterwards at the
chosen threshold; the split is by seed over all 180 cells, 60 fit and 120 held, disjoint by
construction. Its own diagnostic says the selection is not fitted to noise: **the gap between fit and
held-out recall is +0.007 to +0.008** across every budget and both columns, and the sign is positive —
held-out slightly above fit, the opposite of an optimistic bias.

The fault is in what it does with the wrong input. `read_mis` keeps only rows carrying the ninth
column, so a tool that writes no `OriginalLabelExclusion` yields nothing at all — not even its
`Confidence` values. Run on an upstream condition it printed "baseline 0 flags", "unfiltered
collateral flags per cell: 0.0" and "unreachable" for every budget, which reads as a measurement of a
tool that flags nothing. It names the missing column and exits 1 now. Nothing published was affected:
`analyses.sh` only ever runs it on the fork.

**52. The baseline is not a fixed reference point, and the measurement saying so was unquoted.**
`background_stability.py` exists because reporting added flags as a count assumes the pre-existing
flags stay put, and its own docstring says a large `lost` would mean the baseline is not a fixed
reference to subtract. **It is large**: over 180 cells against a baseline of 93 flags, a typical cell
loses **11** (12 %, up to 21) while gaining 29 (31 %, up to 70). The churn is about 40 flags where the
net change is 18, so a count of added flags describes the smaller half of what injection does to the
background.

That is the measurement behind Q6 of the protocol, which asks whether reporting both directions is
the right rule. The answer was in `results/background_stability.tsv` and in no document. It is in the
README now, with the share of the baseline beside the count, since 11 means nothing without the 93.

Two small faults alongside: the statistic labelled median was `v[n // 2]`, the upper middle element
for an even *n*, which agrees with the median on this grid for both columns and is not the median; and
a condition matching no cell raised `IndexError` on an empty list rather than saying so. The
arithmetic is otherwise right — injected sequences are excluded from the baseline side as well as the
after side, so a sequence already suspect before being relabelled cannot count as lost.

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

**53. The primary dataset had no record of how it was built, and its judgeability was quoted for a
set that was never benchmarked.** `bin/prepare_gtdb.py` writes a `{prefix}.counts.json` beside every
dataset it builds. The bacterial donor pool has one, both UNITE subsets have one, and the archaeal
set -- the one every number in this benchmark rests on -- had none, locally or on the cluster. So the
only build record for the primary dataset was three figures typed into `assets/datasets.yml`.

Checking them meant rebuilding, and rebuilding tested something stronger that nothing had tested.
`data/README.md` justifies leaving the 73 MB GTDB release out of git by pinning it with a sha256, "a
stronger guarantee than a copy in git". That guarantees the *input*. Whether the committed
`gtdb_arc1200.fasta` and `.tax` actually follow from it was an assumption. `slurm/rebuild_primary.sh`
re-runs the preparation on the pinned release and compares: both files come back **byte-identical**,
and the counts confirm all three manifest figures, with the identity `in_domain == too_short +
name_collision + kept` holding exactly at 13 754 = 6 703 + 0 + 7 051.

What did not survive was the judgeability block beside those counts. Its comment read "taxa with at
least two members, by rank" while the numbers were the share of *sequences* whose taxon has at least
two members -- a different statistic on the same file, and at species they are 37.3 % and 72.7 %, so
the label was wrong by 35 points while the numbers sat there looking right. And the numbers were
right for the 13 754 sequences before the >= 1200 nt filter, not for the 7 051 that every measurement
here was made on: genus 95.7 % against 91.7 %, species **81.5 % against 72.7 %**.

The repository already knew, in three places. `results/shape_gtdb_arc1200.json` is committed, is
produced by `bin/analyses.sh` on every run, and records genus 91.7 and species 72.7 outright;
`bin/subset_taxa.py:103` reasons from "a source at 72.7 %"; REVIEW.md:424 quotes the same. Only
`assets/datasets.yml` and the protocol said 81.5 %. Nothing read the YAML field programmatically, so
a measured number and a typed one sat in the same repository without ever having to meet. Both stages are now recorded under names that say which set they describe, and both
reproduce from `bin/dataset_shape.py`, whose output was checked against an independent count before
either was written down.

**54. A file name says "aligned" for one dataset and not the other, and the script that depends on
it could not tell.** `bin/cluster_conflict.py` compares two sequences column by column, which is only
meaningful on a fixed-width alignment; its docstring says so. `bin/analyses.sh` passes it
`data/gtdb/gtdb_arc2k.fasta`, and that file *is* an alignment -- 2023 rows of 1478 columns,
subsampled from `gtdb_arc1200.aligned.fasta`, as its own `subset.json` records. But
`gtdb_arc1200.fasta` with the same suffix is the unaligned release at 1200 to 2684 nt, and its
alignment is `gtdb_arc1200.aligned.fasta`. So the suffix means one thing for one dataset and the
opposite for the other, and the script given the wrong one would have compared position 400 of a
1200 nt sequence with position 400 of a 2684 nt one and reported a plausible fraction. `slurm/scaling.sh`
already guards against this by preferring `.aligned.fasta` and falling back; `analyses.sh` hardcodes.
Checked rather than assumed: the widths are uniform, so no published number is affected. The script
now refuses a file that is not fixed-width, which is the check that generalises past this one caller.

The same script had the D110 shape. Given an `--injected-dir` that matches nothing it printed its
header, wrote `{"by_k": []}` and exited 0 -- and `analyses.sh` sends its stdout to `/dev/null`, so a
valid-looking empty file would have been the only trace. Two silent-zero paths inside it were
measured rather than reasoned about: `by_group` is a `defaultdict`, so a true lineage absent from the
base taxonomy scores 0.0 instead of failing, and `max(..., default=0.0)` does the same for a group
with no correctly labelled member. Both are empty on the real data, 0 of 11 178 injected sequences,
so the five published rows are clean. With the guard in place the committed
`results/cluster_conflict.json` reproduces identically.

**55. The dataset the choice of dataset is argued against could not be rebuilt.** Protocol.md §2.6
justifies RepS over RefS with a candidate table, and the RefS row -- 20 295 sequences, 4.3 %
judgeable at species -- decides it. `data/unite/unite_refs.counts.json` and
`data/unite/unite_refs_shape.json` are committed and carry exactly those figures.
`slurm/fetch_unite.sh` builds only RepS. The RefS pair came from a `prepare_unite.py --subset
refs_all` run by hand, so the dataset the benchmark uses was reproducible and the comparison that
selected it was not. Both commands are now in the script. The committed counts are internally sound
and were checked rather than taken on trust: 16 120 refs plus 4 175 singletons is the 20 295 published,
the three subsets sum to the 102 137 records in the release, and `in_subset == too_short +
name_collision + kept` holds for both subsets.

`prepare_unite.py` also had the D110 shape, and a worse version of it than the others. The subset is
selected by string equality on field 4 of the header, so a subset that matches nothing wrote an empty
FASTA, an empty taxonomy and a counts file with no `kept` key, and exited 0 -- which is exactly how a
rename in a future UNITE release would arrive, with the next step building a reference on an empty
file. It now exits non-zero and names the subsets it did see, since those were already counted:
`--subset reps matched nothing. subsets present: nosuchsubset=1`.

**56. The explanation of a corrected number was itself wrong, in three places.** `assets/datasets.yml`
explains why UNITE RepS is 10.9 % judgeable at species and not the 85.7 % published, and the
explanation is right: unresolved labels were counted as real taxa. Checked rather than accepted --
scoring the same file with every label taken as resolved returns 98.2 % and 85.7 %, the two published
figures reproduced to the decimal, so that is the whole of the difference and nothing else is hiding
in it. But the comment said a sequence labelled `Cortinarius_sp` "shares that label with 62128
others". 62129 is every unresolved sequence at species across all the `X_sp` forms; the largest
single label is `Tomentella_sp` at 2727. A total was written as a group. The same comment credits
`bin/unite_shape.py`, which was renamed to `dataset_shape.py` and does not exist, while two other
lines in the same file name it correctly. And the comment added to `slurm/fetch_unite.sh` earlier in
this review repeated the group error before it was caught, which is the argument for checking a
mechanism even when the number it explains is already known to be right.

**57. The one script with no arguments at all, and the equality test that turned out to be right.**
`bin/stem_flags.py` had no `argparse`: the baseline directory, the injected directory, the runs
directory and the condition were four literals in the body, so the script that answers whether the
stem artefact explains the collateral flags could only ever be asked about one condition of one
dataset, and the same question about UNITE would have meant editing it. Every sibling script takes
these as flags. It now does too, with the former literals as defaults, so `bin/analyses.sh` is
unchanged.

It also picked its baseline with `next(Path(...).glob("*epang*/*.mis"))`. `Path.glob` yields
directory order, not sorted order, so with a second epang condition under `results/baseline2k` the
baseline would have been whichever the filesystem offered first and the published shares could differ
between machines with nothing to show why. There is one match today, which is why this never fired.
Now sorted, and it refuses anything but exactly one. Two further paths were silent: a group with no
flags divided by zero, and a row with fewer than 9 columns was skipped one at a time, so an upstream
`.mis` -- eight columns -- would have had every row skipped and then divided zero by zero. Pointed at
`upstream_raxml_T8__rep1` it now names the file and the column count.

The substance survived all of it. The artefact is identified by `abs(conf - 0.510) < 1e-9`, an
equality test on a float, which is only sound if 0.510 is a point mass. Counted across the grid's
25 772 flags: 8057 at exactly 0.510, 305 at 0.509, 85 at 0.511, against ten to a hundred per bin
across the rest of the 0.49-0.53 band. Two orders of magnitude, so the window is right and widening
it would add background. The three published shares reproduce byte-identically, and their group
totals sum to 25 772 against an independent recount. The docstring's "31.5 % of all flags" was the
one thing wrong: 8057 of 25 772 is 31.3 %.

**58. A caveat was ruled out with a statistic that could not have detected it.** `bin/foreign_score_vs_flag.py`
answers whether the bacterial donors of error kind 6 are flagged for where they place or for aligning
badly against the archaeal covariance model, and it answers by comparing medians: 1009.14 bits flagged
against 1009.16 unflagged, a difference of 0.02 bits. Correct arithmetic, and no evidence either way,
because three quarters of the donors sit between 1001 and 1014 bits. A median that discriminating
cannot see the only place an alignment effect could live, which is the left tail -- the donor that
aligns at 461 bits is the one that might be flagged for aligning badly rather than for its position.
And the tail is where the reader's suspicion naturally goes, since the unflagged donors bottom out at
975 while the flagged reach 461.

Counted against what independence predicts, the caveat is genuinely dead. Below the 5th percentile of
score, 20 donors are flagged and 0 unflagged where 19.0 flagged is expected; below the 10th, 39 and 1
against 38.0; below the 25th, 94 and 5 against 94.0. The same three rows for upstream. So the worst
aligning donors are all flagged for the reason 95 % of the donors are flagged and not for their score,
and the protocol's caveat was overcautious in the direction the protocol guessed. The counts are now
in the two published records and in what the script prints, so the conclusion rests on the statistic
that can carry it.

Two things that were checked and did hold: the parse reads `bit sc` and not a neighbouring column,
confirmed against the `--sfile` header, and all 393 donor injections have a score in both conditions
-- 373 + 20 and 376 + 17 -- so the silent `continue` for a donor missing from the score table never
fires.

**59. Error kind 6 is not the isolated case it says it is, and that is where its entire miss rate
lives.** `bin/inject_foreign.py` drew its target labels with `rng.choices` -- with replacement -- while
its docstring said "the target species is drawn per donor rather than shared, which makes this the
isolated case; a shared variant would be kind 2 crossed with this one". It also draws a target
*sequence* and takes that sequence's lineage, and 7051 sequences carry only 3067 distinct species
lineages, so labels collide far more often than a birthday estimate over sequences suggests. Across
the nine committed cells **94 of 393 donors share their archaeal label with another donor**, 32 of 101
in the densest.

Those donors are kind 2 crossed with kind 6, by accident, and the measurement says so unambiguously.
Stratified by whether a donor's label is shared:

| | isolated | shared |
|---|---|---|
| `epang_T8_K25` | **299/299 = 100.0 %** | 74/94 = 78.7 % |
| `upstream_raxml_T8` | 298/299 = 99.7 % | 78/94 = 83.0 % |

Fisher exact two-sided p < 0.001 for both. Every one of the fork's 20 misses is a shared-label donor
and 16 of upstream's 17 are. The group sizes of the misses are the mechanism in miniature: 2, 3, 4 and
7, with seven donors sitting in one group of seven that carries a single archaeal label, so
leave-one-out removing any one of them leaves six anchoring it.

This reinterprets the published table rather than contradicting it. `foreign_summary_*.json` records
recall 1.000 at rate 0.005, 0.967 at 0.01 and 0.941 at 0.05, and the shared-donor counts across those
same cells are 0, 0, 0, then 7, 2, 2, then 25, 26, 32. Kind 6 recall is 100 % wherever the
construction is actually isolated; the decline with rate is the collision probability rising with *n*,
not foreign sequences becoming harder to detect when there are more of them. It is also what explains
finding 58's residual: the 20 donors that no alignment score distinguished are the shared ones.

The default draw is unchanged, so the committed cells reproduce from this file -- verified, the
`.fasta` and `.tax` of all nine are byte-identical and the regenerated `foreign_summary_*.json` match.
`--distinct-labels` gives the construction the docstring describes, and every cell's `truth.json` now
carries `n_shared_label_donors` and the group sizes, so a recall figure for kind 6 cannot be read
without the stratum it belongs to.

**60. The donor phylum was a parameter chosen by `head -1` and recorded nowhere.**
`slurm/fetch_bacteria.sh` counts bacterial phyla in the release and takes the most abundant as the
source of kind 6's foreign sequences. That resolves to `p__Pseudomonadota` at 543 726 sequences
against `p__Bacillota`'s 306 490, and nothing declarative said so: not `assets/datasets.yml`, not any
record under `data/bacteria`. The choice was recoverable only by reading the first line of a generated
file or by counting the pool's own taxonomy. It is reproducible, because the release is pinned, but a
future release in which Bacillota overtook Pseudomonadota would silently change what error kind 6
means, and the paper's description of the construction would still read the same. The pool is now a
declared dataset with its phylum, the rule that picked it, its counts and its seed, so the rule can
stay -- it should stay, the largest pool is the right pool -- while a change in what it selects
becomes visible.

`bin/subsample_fasta.py` recorded `{source_sequences: 392425, drawn: 600, seed: 42}`: how many, not
what from. `fetch_bacteria.sh` deletes `donor_full.fasta` immediately after drawing, so nothing
downstream could name the file the pool came out of. This is finding 22's gap exactly, fixed there for
`truth.json` and left here. The record now carries both source names and their sha256.

What was checked and held: the pool reproduces. `donor_pool.fasta`, `.tax` and `.aligned.fasta` were
rebuilt on the cluster a day after the committed copies were made, and all three md5 sums match the
local ones with all 600 names agreeing across the three files -- so the seed and the pinned release do
make the draw deterministic across machines, which had been designed for and never demonstrated. The
timestamps are what prompted the check: the alignment on the cluster is a day older than the sequences
beside it, which is what a stale alignment would also look like.

One of this review's own checks was vacuous and had to be redone. `bin/push_code.sh` refuses to sync
while a job is running and exits 1 saying so. Called as `push_code.sh >/dev/null 2>&1;` its message was
hidden and its status ignored, so the manifest edits above were validated against the cluster's older
copy. Re-validated locally in a throwaway virtual environment instead, which removes the dependency on
a remote copy for a question about a local file. The script is not at fault and is unchanged.

**61. The scaling efficiency was measured against a ceiling the fold count makes unreachable.**
README.md reported the staged placement distributing at 87 % and 86 % efficiency on 2 and 4 shards.
The timings reproduce exactly from `bin/staged_scaling.py` -- 194.5, 111.2 and 56.4 s, giving 1.75
and 3.45 -- and the efficiency is the conventional speedup over shard count. It is also the wrong
figure to quote alone. 25 folds over 4 shards split 7, 6, 6, 6, read off each shard's own log, and
the step ends when the shard holding 7 ends, so no distribution however free beats 25/7 = 3.57. The
86 % is mostly the arithmetic of 25 not dividing by 4. Against the ceiling the split leaves, the
placement runs at 96.5 %, and the four shards finish within 0.6 s of each other where the `srun`
version threw one straggler per allocation at 124 to 258 s against its own 56 to 62. The script now
prints the fold counts and the ceiling beside the timings, and the README table carries both columns,
because the two numbers answer different questions and only one of them is about overhead.

One latent fault in the same script: `secs[stage].append(json.loads(...).get("wall_sec") or 0.0)`
makes a record missing `wall_sec` contribute 0 to the total, and the completeness check above it
cannot catch that because `[0.0]` is a non-empty list, so the stage looks present. All 16 committed
records carry the field, which is why it has never fired.

**62. The test suite pinned every field except the one that broke.** `tests/test_conditions.py` is
the regression net for condition selection and it is a good one: it builds two cells under two
conditions with deliberately different detections, insists each script sees one condition, and
insists a missing condition fails rather than returning nothing. Its paired-comparison test asserted
`cells`, `cells_b_greater` and `mean_difference`. It did not assert `cells_a_greater`, which is the
field whose absence let a throwaway script read `.get("cells_a_greater", 0)` and publish "no cell in
180 favours upstream" when eight do -- the error recorded in finding 20 and D84. The field was added
to `paired_conditions.py`; nothing was added here, so the test suite would have passed either way.

Now asserted, with `cells_tied`, and with the partition `a_greater + b_greater + tied == cells`,
which is the shape of the error rather than one value of it. Mutation-checked rather than assumed
live: changing the expected 1 to 99 fails the test and changing it back passes. The invariant also
holds on every committed `results/paired_*.json` row, 0 mismatches, which is a check the records had
never been put to.

**63. The input-digest provenance covered 0 of 1022 published records, and its gate passed anyway.**
Finding 20 added input digests: the tool modules write the sha256 of what they read, `collect_run.py`
folds them into `run.json`, and `verify_inputs.py` compares them across a cell's conditions, which is
what Protocol.md 2.5 rests on. Counted across the repository: **0 of 1022** `run.json` records carry
the field. Every published result predates it, in all ten conditions.

The gate did not say so, because its own empty-match guard had a second shape. It failed only when
`not by_cell and not without` -- nothing matched at all -- which is the fault it was written for. With
1022 records present and none carrying the field, `without` is long, `by_cell` is empty, nothing is
compared, and it exits 0. That is the same defect it was created to fix, one level up. It now fails
when `by_cell` is empty however many records matched, naming the count.

The mechanism does work and was demonstrated -- `slurm/inputs_check.sh` ran one cell under both tools
and both records carry identical digests -- but the two run directories were never repatriated, so the
demonstration existed only on the cluster and a clone saw a gate with nothing to check. They are in
the repository now, which is also what makes the corrected gate pass for `bin/analyses.sh`.

And the check was made stronger while it was open, because cross-condition agreement does not say what
it sounds like: two conditions can agree on a database neither of them got from here. Every recorded
name is now looked for under `data/` and its digest compared against the file on disk. All four match.
That is one step shorter than it first reads: `data/injected/*/*.tax` and `*.fasta` are gitignored and
rebuilt from their seeds, so what the digest is compared against is the regenerated file, and the chain
to the repository runs through data/README.md's check that regeneration is byte-identical rather than
through a committed byte. On a fresh clone the comparison has nothing to compare until `make_grid.sh`
has run, which the script now counts and reports rather than passing over.

**64. A filter rule that never applied, and a comment that explained the wrong thing.**
`bin/repatriate.sh` says only `run.json`, the `.mis` and the tool's log are wanted, "stdout.log
duplicates the log and score.json is derived from committed inputs, so both stay out". rsync takes the
first matching filter rule and `--include='*.log'` precedes `--exclude='stdout.log'`, so that exclude
has never applied: 1022 stdout.logs are here, 6.2 MB. No harm done, because `.gitignore` carries
`results/**/stdout.log` and git is where "stays out" mattered. But two statements were wrong. The rule
was dead, and stdout.log does not duplicate the `.log` -- they differ in every run directory checked,
one being the tool's own log and the other the wrapper's stdout. The rule is removed and the file is
kept on purpose, which is what was happening anyway. `score.json`'s exclude is reached and does work.

This surfaced from my own rsync pulling a `stdout.log` I had told it to skip, with the same rule order.

**65. The baseline run has no task-level record, and its trusted seconds did not say which CPU they
were measured on.** Two gaps in the same run, which is the one every "added flags against baseline"
number is measured against and the source of the fork's published 263 s on 7 051 sequences.

`results/pipeline_info/trace-baseline.txt` has a header and zero rows. That is the fault
`bin/recover_trace_from_report.py` exists for -- a resubmitted job finds the trace already there,
warns, and writes nothing -- so the report was the fallback. It is empty too: `window.data` parses and
holds `trace: []`, `summary: []`, checked directly rather than inferred from the script's message, so
the script is looking in the right key and there is nothing to find. The container digest and per-task
timings for that outdir are gone. Nine trace files have zero rows in total; the other eight are
`*_local.txt` stub runs where it is expected. Reports are also never repatriated -- `bin/repatriate.sh`
copies `trace*.txt` only -- so for every other outdir the fallback exists solely on the cluster, 43 MB
of it.

The second gap was already known and is now closed. `bin/verify_runs.py` reports it on every run --
"4 trusted runs with no recorded cpu_model ... their seconds are not comparable without the node's
Slurm features" -- so what was missing was not the detection but the answer. Of 1024 records those 4
are exactly the four baseline runs, and all 54 other trusted timings record `AMD EPYC 9754 128-Core
Processor`. Comparing seconds across CPU models is the hazard `--constraint=epyc-9754` exists for, so
four trusted figures without one is not cosmetic. The gate names the host, which is what makes them
recoverable: all four record `host:
cpu-node-123`, and Slurm reports that node as `ActiveFeatures=epyc-9754`. Same model as every other
trusted timing, so the baseline seconds are comparable with the rest -- which had been assumed
throughout and is now established. Not backfilled into the records, because a value inferred from a
hostname would afterwards read as one the run measured.

**66. A log line that reads like lost data and is not, and the engine/folds split checked against it.**
`bin/kexact_decomposition.py` splits the fork's k=2 advantage into the engine (+0.284, +0.177) and the
fold scheme (−0.020, 0.000), and README states "the cause is the engine, not the fold scheme". Reading
the runs behind it turned up this, in both Kexact logs:

    [epang-l1o] placed 2023/2023 folds
    [epang-l1o] placements produits: 2021 (K=2023 folds, remap 50.7s)

Every fold placed and two placements then vanished in the remap, with no warning and no FAIL line.
`epang_T8_K5` loses none, `epang_T8_K25` loses two and one. The recall denominator is 102 injected
sequences, so one lost sequence is worth 0.0098 of recall and the published fold term is −0.0196 and
0.000 -- the same size as the loss. The engine term is 29 and 18 of 102 and an order of magnitude
clear of it; the fold term was not.

So it was measured rather than argued about. `slurm/kexact_lost_placements.sh` reruns the cell through
the staged path, which keeps one jplace per fold, and counts the queries inside each rather than
trusting the files to exist, since the loss is downstream of placement and every file does exist.
Result: **2023 queries placed across 2023 folds, nothing lost**. Then scoring that task directory gives
191 flags, and the `.mis` is **identical to the committed Kexact run's**, same md5 over sorted rows,
zero differing rows.

Three things follow. The fold term is not an artefact of placement loss -- the suspicion that prompted
this is refuted, and the term stands as measured, with the caveat README already carries that it rests
on two cells. `placements produits: N (K=M folds)` with N < M is not a loss of information: whatever it
counts, it changed no flag here, so it should not be read as data lost and the next person to see it
can stop. And the staged path reproduces the monolithic path's `.mis` byte for byte at one fold per
sequence, 2023 folds, which is a considerably harder case than the 25-fold equality already
established and was not previously known.

**67. One script's `rm -rf` destroyed another's results, and the dependency ran the other way.**
`slurm/before_after.sh` answers whether taxmarker#40's trimmed lineage is a regression. It set
`OUT=$BENCH_ROOT/results/ragged_check`, `cd`ed there and called `-s aln.fasta` relative to it -- so it
could only run after `slurm/ragged_check.sh` had left an `aln.fasta` there, an undeclared dependency
with no assertion. And `ragged_check.sh` opens with `rm -rf "$OUT"` on that same directory. The two
scripts could never coexist: the only order that works is ragged first, and running ragged again
deletes before_after's output.

Not hypothetical. The repository commits `before_placeholders.{log,mis}`,
`before_semicolons.{log,mis}` and `after_trimmed.log`; on the cluster that directory holds only
`ragged_check`'s files, stamped 20:43 on 3 October. The before/after evidence survives solely because
it had been committed, and nothing in the repository could regenerate it.

`before_after.sh` now has its own output directory and its own copy of the alignment from the
committed `gtdb_arc400`, with a guard on the source. Verified by rerunning it: 14 flags for
`before_placeholders` and 14 for `before_semicolons`, both `.mis` **byte-identical to the committed
ones**, `after_trimmed` failing as recorded, and `results/ragged_check` untouched. Either script can
now run in any order, any number of times. The committed artefacts moved with `git mv`, so the
evidence keeps its history.

Rerunning it also produced something the repository did not have. For these two experiments the result
*is* a failure, and `after_trimmed.log` stops at "Loading taxonomy from file" -- the traceback goes to
stderr, which `bin/repatriate.sh` did not collect. So the fact of the failure was committed and its
cause was not. It is `IndexError: list index out of range` at `epac/taxonomy_util.py` line 337 in
`load_taxonomy`: an empty lineage crashes SATIVA inside its own taxonomy parser, which is a far more
useful thing to say about taxmarker#40 than "it fails". Both stderr files are committed and
`repatriate.sh` collects `.stderr` from now on.

**68. The script that eliminated two mechanisms could not have reported its own failure.**
`slurm/startcost.sh` produced the table in D49 that ruled out container startup and task-directory
I/O as causes of the N=4 regression. Three faults, all latent, all of a kind the repository had already
learned elsewhere.

Its `TASKDIR` was hardcoded to `results/scaling/N4_c140_r1`, a directory name `scaling.sh` stopped
producing when `SCALING_DATASET` put the dataset into the path (D82). It exists today only as a
leftover of the first round on the cluster and is absent from a clone, with no existence check. Both
`wait`s were bare -- the exact fault `scaling.sh` documents at length having been bitten by, where a
killed task went unnoticed and surfaced four stages later. And the read was
`cat fold_0*/ref.fasta 2>/dev/null || cat fold_0*/query.fasta`, which treats a missing directory as a
successful fast read. Together: a missing task directory would have timed four tasks reading nothing,
reported it as fast, and **inverted the conclusion the script exists to reach**.

The published numbers are sound, checked rather than assumed. `startcost-2161299.log` matches D49's
table to the hundredth -- 0.76/2.09, 0.51/0.90, 0.62/0.92 -- and contains zero error lines, so nothing
failed and the directory was there. `TASKDIR` is now overridable with a default that exists,
guarded against a directory with no `fold_0*` in it as well as against a missing one, the waits check
each pid, and the read insists on a non-zero byte count. Worth noting for anyone rerunning it: the
published figures were measured on the 82 MB arc2k task directory, and the current default is the
arc1200 one at 268 MB over 25 folds.

**And the conclusion that rested on it had been overturned without the log saying so.** D49 is titled
"Four nodes are slower than two, and the mode's optimum is two" and ends by asking that Protocol.md be
told "the measured optimum is two and that four regresses". D82 later found the regression was the
dataset, and D95 measured the staged pipeline at 3.45x on four shards. Neither names D49, and nothing
anywhere in 117 entries pointed at it, so a reader working through the log in order would have carried
that correction to Stamatakis. D49 now opens with a superseded note naming D82 and D95, keeping its
measurements and marking its consequence as not to be acted on.

**69. A committed record did not have the format the committed code produces, and the check that
depended on it had never run.** `bin/fold_composition.py --compare` is the last line of
`slurm/fold_order_check.sh` and carries the assertion behind the fold-order work: if the two orders
produce the same partition, the option did nothing and the script must fail. Run on the two committed
records it raised `KeyError: 'membership'`.

The cause is a two-minute window. `membership` entered `fold_composition.py` in `f00554a` at 09:45 on
2 October; the records were committed in `7b0d674` at 09:47. The job that produced them had run on the
cluster against the copy synced *before* that field existed, so the record and the code beside it in
the same repository describe different formats, and nothing compares the two. The rates were readable,
which is why this went unnoticed: the published 2.58 % and 0.64 % come from fields that were there.

Both fixed and both verified. `--compare` now names the records missing the field instead of raising,
and fails if the co-location counts are also equal, so a record it cannot fully check still cannot pass
silently. Then the job was rerun to produce complete records: **193/7483 = 0.02579 and 48/7483 =
0.00641**, the published figures to the digit, and `identical partitions: False` -- the assertion that
had never been exercised now runs and passes, which is what shows the option changes the partition
rather than only the rate. The records also carry a `label` now, because both were written from one
reused task directory and their own `taskdir` field was identical; only the filename distinguished
them.

The general hazard is worth stating: editing an analysis script between running it and committing its
output decouples the two with nothing to detect it. That is what happened here, in two minutes, to a
record whose job had already finished.

**70. The same stale-format defect, twice more, and the reason it is systematic.** Finding 69 found a
committed record written two minutes before its producer gained a field. Rerunning the two jobs that
own the rest of the derived records found two more instances of the same shape and one that was mine.

`data/unite/unite_shape.json` and `unite_refs_shape.json` were committed in `8c38bf6` at 22:15 on 3
October; `bin/dataset_shape.py` gained its `convention` field in `2b1841c` at 22:43, 28 minutes later.
Nothing crashed, because no consumer reads that key -- which is exactly why it was invisible, where the
`membership` case announced itself with a `KeyError`. And `donor_pool.subsample.json` was one I created
this session by adding source digests to `bin/subsample_fasta.py` without rerunning it, which would
have left the repository in the state I had just written a finding about.

So the rule, which is the useful part: **a committed record is only known to match its producer when
the producer is rerun.** `bin/analyses.sh` does that for the 45 tables it rebuilds, which is why those
never drift. Eight scripts in `bin/` are invoked only from job scripts and never from `analyses.sh` --
`dataset_field`, `fold_composition`, `inject_foreign`, `inject_mislabels`, `prepare_gtdb`,
`prepare_unite`, `staged_scaling`, `subsample_fasta` -- and every stale record found in this review
came from that list. All eight have now been rerun.

What the reruns confirmed, which is the other half: `fetch_unite.sh` reproduces RepS at 97.4/59.9 genus
and 45.3/10.9 species and the unresolved counts 1846/7828/11332/23016/31482/62129 exactly, and the
RefS branch added earlier in this review gives 20 295 = 16 120 + 4 175 with 90.6/89.7 and 4.5/4.3 --
so the comparison that chose RepS is now reproducible and reproduces. `fetch_bacteria.sh` still selects
`p__Pseudomonadota` at 543 726 against Bacillota's 306 490, its counts match to the record, and
`donor_pool.fasta`, `.tax` and `.aligned.fasta` come back md5-identical for the third independent time.

**71. Four job scripts described work they do not do.** Reading the last of `slurm/` line by line
rather than sweeping it turned up a copied comment and three stale ones. None changes a number; all
four would mislead anyone reading the script to find out what produced a result.

`ksweep.sh` and `kaxis_upstream.sh` both open with grid_fork.sh's comment, "The whole grid on the
fork". `ksweep.sh` runs six cells at two fold counts. `kaxis_upstream.sh` runs fifteen -- species
distance, every *k*, three seeds -- under **both** tools, so the copied line is wrong on both counts;
its 30 run directories are 15 cells times 2 conditions, counted. `kexact_k2.sh` says "Six cells rather
than the grid: k=2 at family distance, both rates, three seeds". Two were run, s1 and s2 at r0.05,
which is what README honestly reports the decomposition on; the script's own file-cost paragraph is
the reason, and the comment never caught up with it. `sizes.sh` says the trustworthiness of reserving
most of a node instead of holding it "is being checked separately at one node; until that lands" --
it landed, as D39, and `threads.sh` three directories away states the result as settled. Two scripts
disagreeing about whether the same question is open is the shape worth noticing.

**72. A probe that decided the fan-out's shape staged its inputs with `|| true`.**
`slurm/fold_subset_probe.sh` answers the question DISTRIBUTION.md is built on: will the tool place
fold *i* from a directory holding only `manifest.json`, the model and `fold_i`, so a Nextflow fan-out
can stage 11 MB per fold instead of the whole 275 MB? It staged the fold's four files with
`cp ... 2>/dev/null || true`. Two of them, `ref.nwk` and the per-fold model, genuinely are optional;
the alignment and the query are not. With every copy's failure discarded, a probe that staged nothing
would have run, placed nothing, and printed "VERDICT: not enough" -- a false negative on a design
decision, reached for the opposite reason to the one reported. The two essential files are now copied
with a hard failure and the two optional ones say so when absent.

**73. "One command rebuilds every committed result" was false for eight files, and the gate said
nothing.** `bin/analyses.sh` opens with that claim and "a change to any script shows up as a diff".
Running it and then counting what it actually rewrote -- 958 files, of which 40 tracked -- left eight
committed files under `results/` untouched.

Three were version 1 on the ITS sets: `summary.tsv`, `concordance.tsv`, `concordance_vs_gamma.tsv`,
whose conditions were the `port_py3_*` ones over `n100` to `n5402`. There was no version 1 run tree to
rebuild them from, so they were out of scope and the header said so instead of claiming otherwise. They
have since been removed with the rest of version 1, which is the cleaner end: the script's claim to
rebuild every committed result is now exact, with no exception to state.

Four are current and were simply never rebuilt: `kaxis_epang_T8_K25.json`,
`kaxis_upstream_raxml_T8.json`, `ksweep_epang_T8_K25.json`, `ksweep_epang_T8_K5.json`. Their runs are
under `results/kaxis/runs` and `results/ksweep/runs` and every loop in the script reads
`results/grid_fork/runs`, so a change to `aggregate_grid.py` or `score_injection.py` could not have
shown up in them. They are rebuilt now. Their `n_missing` moves from 135 and 144 to 165 and 174,
because it counts cells in `data/injected` with no run and that directory held 150 when they were
written and holds 180 now -- `15 + 135` and `6 + 144` both being 150 is what gave that away.

The eighth, `results/grid_summary.json`, is deleted. It holds 600 rows against the 720 and 360 of the
five per-condition summaries that supersede it, so it is a snapshot of a partial grid under the most
authoritative-looking name in the directory. Nothing reads it; it exists because
`aggregate_grid.py --out` defaulted to that filename, so a run without `--out` from the repository root
created and then overwrote it. That default is gone, the same trap as `dataset_shape.py`'s `shape.json`
earlier in this review.

**74. Two committed records used one row order and five used another.** Rebuilding the k-axis summaries
produced the same 60 keys with every value identical and the rows in a different sequence. The cause is
`sorted(grouped.items(), key=lambda kv: str(kv[0]))`: stringifying the key sorts *k* lexicographically,
so every grid summary a reader opens runs **1, 10, 2, 3, 5**. The committed k-axis records are in
numeric order, because they predate that `str()` -- which was itself a reasonable fix, the foreign grid
having `k: null` where `None < int` raises, and whose comment claimed it was done "without reordering
anything that matters". It reordered *k*, and it left two of the repository's records ordered one way
and five the other.

Now `tuple((x is None, x) for x in kv[0])`, which orders ints as ints and sends null last. Nine records
move and the change was checked to be order and nothing else: **key sets identical and every value
identical in all nine**, the four k-axis and fold-sweep records landing back in exactly their committed
order, which is what confirms the diagnosis rather than merely fitting it.

**75. The reproducibility check was narrower than the claim it licenses, and the figure justifying it
was wrong by a factor of seven.** The repository does not commit the per-cell datasets, on the grounds
that they are regenerable from their seeds and that the regeneration is checked. Both halves needed
looking at.

`data/README.md` records the check as "`.tax` files whose md5 matches ... and `truth.json` files
identical in all 180 cells". A cell also carries a `.fasta`, and that is the file SATIVA reads; a
taxonomy matching while the alignment did not would be worse than the reverse, not better. The nine
foreign cells were not covered either. Rerun from a fresh clone with nothing but `make_grid.sh` and
`make_foreign.sh`: **378 of 378 regenerated files byte-identical** -- 180 injected `.tax`, 180 injected
`.fasta`, and both for the nine foreign cells. The claim holds and now says what was actually checked.
The 180 injected `.fasta` turn out to be exact copies of `gtdb_arc2k.fasta`, because injection rewrites
a taxonomy and never an alignment.

`.gitignore` justified the exclusion with "86 MB of near-copies of one taxonomy and one alignment",
and this finding first reported that as **wrong by a factor of seven, 642 MB**. That correction was the
error. An injected cell's `.fasta` is a **symlink** to `gtdb_arc2k.fasta`, 78 bytes of it, because
injection rewrites a taxonomy and never an alignment. `os.path.getsize` follows a symlink, so summing it
counted one 3 MB file 180 times. On disk it is **92 MB** -- 62 under `data/injected`, almost all of it
`.tax`, and 30 for the nine foreign cells, whose `.fasta` carry appended donors and are real files. The
original 86 MB measured the disk and was right, to within the growth of the grid since. "Near-copies of
one taxonomy and one alignment" was right too, and more exactly than it reads: there is one alignment.

The accusation was the same one being made: a figure asserted from the wrong measurement while
correcting a figure taken from the right one. It was caught by reading `make_grid.sh`, which ends each
cell with `ln -sf`, for an unrelated reason two sessions later.

The clone run is the end of the chain rather than a step in it: clone, regenerate 378 files from seeds,
rebuild 41 tables, **zero diffs**, 22 steps, every gate passing, no cluster and no container. The 41 was
counted rather than inferred from a clean `git status`, which over files nothing rewrote would have said
nothing at all -- the same trap as every other check in this review that reported success without having
looked.

**76. The one result the plan calls decisive was absent from the document that reports results.** The
plan names the exclusion-column comparison as "the result that decides what the paper claims about the
new column", and the mandate asks for recall against `Confidence` **and** against
`OriginalLabelExclusion`. `README.md` carries fourteen findings -- speed, determinism, detection, engine
versus folds, distribution, the *k* axis -- and mentions the column nowhere. Nor the 0.510 stem artefact,
which is the root-cause work the fork exists to report. Both absent from the only summary a reader of the
repository sees, while the data sits in every `grid_summary_*.json` as `metric: by_exclusion` and the
conclusion sits in D19.

Recounted from the raw `.mis` with independent code, no `score_injection.py` and no `aggregate_grid.py`,
on the complete 180-cell grid: **99.0 % of the 25 772 flags have exclusion >= 0.99**, so no threshold on
it brings the calls on untouched sequences below 19 809 of 20 326, where confidence reaches 10 320. One
column filters and the other does not. **8 057 flags, 31.3 %, sit at confidence exactly 0.510, and all
8 057 carry exclusion >= 0.99** -- the column saying independently that the declared taxon holds no
placement weight. D19 reached that on a smaller grid, 6 923 of 21 944 and "all of them"; the share and
the "all" both reproduce.

The recount also found its own producer. `bin/column_comparison.py` already computes every one of those
figures and `bin/analyses.sh` already rebuilds it: `n_flags` 25 772, `untouched_floor` 10 320 and 19 809,
`stem_flags` 8 057 and `stem_exclusion_ge_099` 8 057 -- identical to the independent recount, which makes
the two implementations a check on each other rather than one being redundant. The only figure quoted in
README that the record lacked was the saturation share, and a published number with no committed producer
is finding 73's defect; it is now `flags_exclusion_ge_099`, 25 516 of 25 772, with every other key
unchanged.

So the column explains calls and does not rank them, and that is now in README with the numbers that
support it and a pointer to the record that regenerates them. The held-out figures quoted alongside were checked against the committed record rather than
copied from the log: confidence picks 0.511 and held-out collateral falls 3 960 to 1 656, a 58 % cut,
while exclusion returns "budget unreachable" at the same budgets. D22 quotes 3 904 and 1 641 for that
pair -- the percentage holds, the absolutes drifted when the record was rebuilt, which is the same
stale-number class as findings 69, 70 and 73, this time in the decision log rather than in the repository.

**77. The documents carrying the claims were outside the instrument that measures coverage.**
`bin/review_coverage.py` lists `bin/`, `slurm/`, `modules/`, `conf/`, `tests/`, `main.nf` and
`nextflow.config`. Not the markdown at the root. So it reported 92 of 92 while two documents had never
been read in any pass of this review, and a claim is as reviewable as a line of code. The documents are
in the list now, which is why the count moved to 97.

`DISTRIBUTION.md` had four aggregate figures that had been carried forward rather than measured. Against
a real `run.l1o_tasks` on gtdb_arc1200: the directory is **284 MB and 177 files**, not 275 MB and 146;
the per-fold alignment copies are **257 MB**, not 246; and the placements the stage produces total
**19.2 MB**, not 8.9 -- out by a factor of two. Every *per-fold* figure in the same listing was right,
which is how the sums survived: 10.3 MB of `ref.fasta`, 430 KB of query, 760 KB of jplace, and
`ref.nwk` at 384 KB. Three more, each a document disagreeing with itself or with another: it said 73 %
parallel efficiency at N=2 where its own table gives 1.58x and therefore 79 %, the 73 % being 1.47x
from the superseded gtdb_arc2k round; it said staging is 11 MB per fold where 11 MB is the total of all
25 queries and a fold costs 12 MB because it carries its own alignment; and it asked for the fold
completeness check "the staged pipeline needs" without recording that it has it twice, in
`stagedlooplace` per shard and in `stagedlooscore` against the manifest's `n_folds`. Its efficiency
table now carries the fold-split ceiling that finding 61 put in README, which the two documents had
stopped agreeing about the moment that finding landed.

`PUBLISHING.md` opened with "Everything below is prepared. Nothing is public until you push" and told
you to add a remote. **`origin` has been configured all along and `origin/main` holds 8 commits**: local
`main` and `origin/main` are identical, 0 either way, and GitHub's default branch is `main`. Version 1
is public. The consequence is the finding rather than the staleness: **`RESULTS.md` on `main` states the
refuted detection claim and carries no refutation**, because the banner that refutes it -- 0.94 at *k*=1
to 0.13 at *k*=10 for both tools alike, the fold scheme worth 0.035 and only at *k*=10 -- exists only on
`nextflow`, 201 commits that have never been pushed. Nothing here pushes anything, so this is reported
and not fixed; the branch is a fast-forward over `origin/main` and contains all of its history, which is
the cheapest of the three ways out and the only one that also publishes the work that did the refuting.

The same file's other claims, now measured rather than repeated: the version 1 machinery the plan says
is deleted is still tracked, 97 files and about 6 MB across `scripts/`, `sativa_epang/`, `data_ascii/`,
`data_injected/` and `config.sh`, and two parts of it are load-bearing because `slurm/m1_check.sh` builds
its byte-equality comparison from `data_ascii/` and the version 1 run under `results/runs/`. And the
cluster-path question is narrower than it reads: `git grep` matches 2 436 files under `results/`, all run
logs where the tool printed its own paths, and exactly four elsewhere -- two documents and two comments,
each quoting a path to explain something. **No code depends on one**, which was established by opening
the two comments rather than by counting them.

One near miss worth recording. `ref.nwk` was about to be written up as a file the document lists and the
directory does not have, on the strength of an `ls -la fold_000 | head -9` that cut the alphabetically
last entry. There are 25 of them.

**78. Three counts describing this report had drifted, and the command I was counting with was wrong
too.** `README.md` described this file as "Twenty findings, three of which had produced a wrong number
... and the six defects introduced or missed by the review itself". Three figures in one paragraph, all
stale, in the document that tells a reader what the review contains. That is the defect this report
records more often than any other, sitting in the description of the report.

The counts are gone, replaced by the two commands that produce them, which is the rule the clone section
of this file already states and this paragraph had not followed.

The pattern is the part worth keeping. `grep -cE '^\*\*[0-9]+\.' REVIEW.md` -- what I had been quoting
across several sessions -- returned 78 for 77 findings, because `**19.2 MB**` begins a line in finding 77
and `19.` matches. Tightening it to require a capital after the number returns 65, because many findings
open with a backtick or a digit. `^\*\*[0-9]+\. ` is the one that is right. It said **77, numbered 1 to 77,
no duplicates and no gaps** when the check was run, and this entry is the 78th -- a figure written into
the file it counts is stale as soon as the file grows, which is why the number is not in the prose and
the command is. The over-count had been live for exactly one session, since
`**19.2 MB**` was written an hour ago, and the figure I reported at the end of that session was wrong by
one.

**79. Every number in README checked against the record that produces it, and the headline speed
paragraph had drifted.** The review had audited the code that computes the figures and never the figures
themselves. Fourteen claims, read one at a time against `results/`.

Thirteen are exact. The paired table reproduces row for row -- +0.006/14/5/17/0.064, +0.240/34/0/2/1.2e-10,
+0.152/34/0/2/1.2e-10, +0.104/28/1/7/1.1e-07, +0.005/9/2/25/0.065 -- and so do its totals, 119 cells to
the fork, 8 to upstream, 53 tied, summing to 180. Recall 0.9348 at *k*=1 and 0.1316 at *k*=10 for the
fork, 0.9242 and 0.1218 for upstream, against README's 0.94/0.13 and 0.92/0.12. The ratio gradient 0.8666
to 0.0111 against "0.87 down to 0.01". The baseline churn: 93 flags un-injected, lost median 11 and max
21, gained median 29 and max 70. 847 identical-row groups, 54 conflicting, 52 of them identical unaligned
too. M1 at 135.8 s with a spread of 0.9 over three replicates, `a1aa0f35…`, 48 flags. Determinism at
`b41934ad…` and 161 flags on both an Intel Xeon and `cpu-node-123`.

**The speed paragraph was the exception, and it is the headline.** Against `results/resource_usage.txt`,
which reports medians and which `bin/analyses.sh` rebuilds: 262 s is 263.4, 2 950 s is 2 983.6, 11.2x is
11.3x -- and the 2 023-sequence pair, quoted as **19.3x and 35.3x, is 16.5x and 29.7x**. Those two come
from a single replicate taken before the others had run, 17 % and 19 % above the medians that replaced
them, in a paragraph whose own preamble says the numbers are medians over replicates. Corrected, with a
line saying to read the record rather than the paragraph if they ever disagree again.

Two smaller things. The determinism table's third row cannot be opened: `determinism.sh` clears its own
output directory, so the rerun wiped the 2 October run's `.mis`, and what survives is the trace at 1m 9s.
The cross-vendor claim does not rest on it -- the surviving record is the Intel one -- and the table now
says which rows are records and which is a trace. And the *k*-axis table had no producer at all: five
rows of donor-group counts, median sizes and shares relabelled, computed once by hand. `detection_law.py`
already had `group_size`, so it emits them now, and all five records gained the fields with every
pre-existing value unchanged.

That addition is where this entry nearly became a false finding. Computing the median over distinct donor
taxa gives 10 at *k*=5 where README says 9, and dividing *k* by that median gives 0.33/0.5/0.5/0.5/0.71
where README says 0.34/0.44/0.47/0.54/0.67 -- so README looked wrong in six places. It is not: the
statistic is weighted by injected sequence, median size per sequence and the mean of *k*/size over
injections, which reproduces all five rows exactly. The lesson is the one `ref.nwk` taught in finding 77
a few hours earlier: match the statistic before declaring a mismatch. The donor-group counts and the
eligibility figures, 319 taxa at *k*=1 and 31 at *k*=10, confirmed on the first attempt.

**80. I proposed deleting the largest thing in the repository on the strength of a search that excluded
the only directory depending on it.** Asked whether the project needs this many files, I measured: 7 277
lines of live code against `sativa_epang/`'s 10 685, nothing in `bin/`, `slurm/`, `modules/`, `conf/`,
`tests/`, `assets/`, `main.nf` or `nextflow.config` referencing it, and the plan saying it is deleted
because the tool comes from bioconda. I reported that as dead code and "risque nul".

The search omitted `scripts/`. `scripts/README.md:30` runs `(cd sativa_epang/raxml && make)` and lines
33-34 copy the binaries into both upstream checkouts, the tarball `sativa-RAxML-8.2.3.tar.gz` being
tracked there -- so those are the RAxML binaries both of version 1's conditions ran, and removing the
directory makes `RESULTS.md`'s figures unreproducible. A search over the live harness alone concludes
that version 1's code is unused, which is true and not the question.

`sativa_epang/NOT_WHAT_RUNS.md` says all of this already, in the directory I was about to delete, and
ends: "An earlier version of this file said it was scheduled for removal once the top-level README was
rewritten. That README has been rewritten, and the conclusion went the other way." So the question had
been examined and settled, in writing, and I reopened it without reading the file. Nothing was deleted.

Two things changed instead. `README.md` said the directory stays and why, next to where its size would
prompt the question, since the reason was one file deeper than anyone sizing up the repository would
look. And `bin/review_coverage.py` printed the version 1 tree as excluded on purpose rather than passing
over it -- 97 files, the same count as the reviewable set -- because that silence is what let the wrong
view form: a tool that reports coverage over the live harness invites the inference that what it omits is
not load-bearing.

**Overtaken within the hour, and on the owner's call rather than on the argument above.** Told that the
first benchmark's code and figures could go because better ones will be made, version 1 was removed
entirely: `scripts/`, `sativa_epang/`, `data_ascii/`, `data_injected/`, `config.sh`, `RESULTS.md`,
`results/runs/`, `results/runs_injected/`, `results/figures/` and the three ITS tables, 722 files. The
reproducibility argument that kept the directory was sound and stops applying once version 1's figures
are not being kept. What the episode still shows is unchanged: the recommendation to delete was right by
accident and wrong by method, reached from a search that excluded the dependent directory, and had the
answer been "no, keep it" the method would have destroyed the evidence.

**81. Two things Protocol.md requires and the repository did not have.** Asked to make the repository
fulfil exactly what the protocol defines, the inventory ran in both directions, and the more important
half was the protocol asking for more than was there. Sections 2.1 and 2.2 each name a deliverable
with nothing behind it.

**2.1's simulation control.** "We propose injection as the primary source and simulation as a sanity
check." `git grep -in simulat` over `bin/`, `slurm/`, `modules/` and `assets/` returned nothing.
`bin/simulate_reference.py` evolves sequences along a tree under Jukes-Cantor where the tree *is* the
taxonomy, so a label cannot be wrong unless it was made wrong, and `slurm/make_simulation.sh` builds
one un-injected reference plus twelve injected cells -- small, because 2.1 calls it a control and not a
second set of results. In pure python rather than behind another pinned container: 2.7's pinning rule
is for tools whose behaviour is being measured, and a simulator's model should be readable instead.
Checked rather than assumed to be realistic enough: mean identity runs 0.9923 within a species, 0.9715
to a sibling, then 0.9352, 0.8644, 0.7454, 0.5875 out to class, which is the gradient detection needs.

The control earns its place by giving the one number the injected grid cannot. 2.4 says of real data
that "a sequence we did not inject is not known to be correctly labelled ... so a flag on such a
sequence cannot be called a false positive", which is why the whole benchmark reports collateral flags
against a measured baseline. On the simulated reference it can be called one, and the un-injected cell
measures it.

**2.2's kind 3.** "Whole-clade mislabel: an entire taxon misannotated ... characterised, with the limit
stated", and Q7 adds that the cells would have to vary compactness and not just distance. Nothing
addressed it. `bin/inject_clade.py` relabels whole taxa, lifting by construction the donor-survivor
rule that `inject_mislabels.py` refuses to lift -- which is why it is a separate script and not a flag.
Compactness is measured as separation: identity within the clade minus identity to the recipient's
members, against the recipient rather than the whole database, because that is the comparison 2.2's
account is about and because all-against-all is 3 billion character comparisons in pure python.
`bin/clade_detection.py` reports detection per clade against it, which is what makes the
characterisation falsifiable. `slurm/make_clade.sh` builds the nine cells, three distances by three
seeds, and `slurm/kind3.sh` runs both tools over them; `slurm/simulation.sh` does the same for the
thirteen simulated ones. Both run untimed and declare it, since neither answers a timing question.

The separation range is itself a finding before either tool has run. At species distance -- "a wrong
label inside the correct genus", the hard case 2.2 names -- it reaches **−0.078**, clades whose members
resemble the taxon they have been mislabelled as more than they resemble each other. At phylum distance
it is always positive. So distance and compactness are not independent axes, which is the premise Q7
was asking about.

One defect caught in the making, and worth recording because it is the shape of several above. The
simulated reference first used three sequences per species; `inject_mislabels.py` needs *k*+1 members so
one stays correct, so every *k*=3 cell injected **zero** sequences and said so in a `warn.txt` that was
redirected and not read. Six per species fixed it. The warning existed; reading it did not.

**82. Kind 3's first measurement contradicts the mechanism Protocol.md gives for it, with the sign
reversed.** 2.2 says of a whole-clade mislabel: "Detectability therefore turns on whether the clade is
compact enough to anchor itself." `bin/clade_detection.py` was written to make that falsifiable --
"if detection does not track separation, compactness is not the variable and 2.2's account of the kind
is wrong" -- and on the fork over 54 clades and 226 sequences it does not track it, in the direction
that matters.

Recall against separation from the recipient, which is 2.2's variable: **0.188, 0.190, 0.000, 0.033**
from least separable to most. The six clades whose members resemble the taxon they were mislabelled as
more than they resemble each other -- the extreme of "cannot anchor itself" -- are the **best** detected,
0.273.

The variable is cohesion *within* the clade, and it runs the other way:

| | clades | sequences | recall |
|---|---|---|---|
| `within` >= 0.99, members nearly identical | 39 | 167 | **0.012** |
| `within` < 0.99, diffuse clade | 15 | 59 | **0.339** |

A twenty-eight-fold difference, and the gradient is monotone across four equal-count bins: 0.400 for
`within` from 0.757 to 0.982, then 0.000, 0.036, 0.000 as the clades tighten to identity.

**The reasoning 2.2 applies is right about compactness and wrong about what it buys.** A compact clade
can indeed be told apart from its recipient -- that is what the separation column shows, and separation
is high exactly where cohesion is high. But being distinguishable is not what produces a flag. The
clade's members are each other's nearest neighbours and all now carry the recipient's label, so removing
one leaves the rest confirming that label where the removed sequence belongs. That is kind 2's mechanism
with *k* equal to the whole taxon, which is why overall kind 3 recall is **0.097** here against the
grid's 0.13 at *k*=10. A compact clade does not anchor itself against the wrong label; it anchors the
wrong label.

So the limit 2.2 asks to state is sharper than the sentence it offers: whole-clade mislabels are
undetectable in proportion to how tight the clade is, and the case that escapes is the diffuse clade,
whose members cannot vouch for each other. Both halves of the protocol's own 2.2 reasoning survive
intact -- "a wrong label is only exposed by removing its support, and a right label is only confirmed by
keeping it" -- it is the application to kind 3 that has the sign backwards.

Upstream's nine cells were still running when this was written, so this is the fork alone. The mechanism
is a property of leave-one-out rather than of the placement engine, so it should hold for both, and that
is a prediction the pending arm tests rather than an assumption it is allowed to make.

**83. The simulation control returns both things 2.1 asks of it, and the second was not asked for.**
2.1 proposes simulation as a sanity check: "Simulation shows that the method works where the answer is
certain." On the fork, over 864 sequences whose taxonomy *is* the tree:

**Zero flags on the un-injected reference.** 864 certainly-correct sequences, `n_mislabels: 0`, the run
completing normally in 32 s. That is the number 2.4 says real data cannot give -- there, "a flag on such
a sequence cannot be called a false positive", which is why the whole benchmark reports collateral flags
against a measured baseline instead. The real archaeal sets flag 93 of 2 023 and 469 of 7 051, 4.6 % and
6.7 %, and those are not false positives. Here the strict rate is **0.00 %**.

**Recall 1.000 at k=1**, at species, genus and family distance alike, with zero collateral flags. The
real grid at the same point gives 0.746 with 133 collateral flags per cell. So the distance between
0.746 and 1.000 is the reference's own difficulty and not the method's ceiling, which is exactly the
calibration 2.1 wants and the reason it calls this a control rather than a second set of results.

**And the surviving-ratio law holds out of sample**, which was not among 2.1's stated purposes and is
the more useful half. 2.2's falsifiable prediction -- that what predicts detection is the share of a
sequence's surviving relatives carrying the wrong label, not *k* and not the fold count -- was fitted on
the archaeal grid. On simulated data it reproduces in shape and sits uniformly above:

| share carrying the wrong label | simulated | archaeal |
|---|---|---|
| 0.0-0.2 | **1.000** | 0.867 |
| 0.2-0.4 | **0.985** | 0.600 |
| 0.4-0.6 | **0.793** | 0.327 |
| 0.8-1.0 | **0.000** | 0.011 |

Monotone on both, collapsing to nothing at the top of the range on both. The offset is the heterogeneity
2.1 predicts a simple model cannot reproduce, and the agreement in shape is what makes the law a
statement about leave-one-out rather than about GTDB.

One design artefact to state rather than leave for a reader to find: the simulated cells have no
0.6-0.8 band at all. Six sequences per species and *k* in 1, 2, 3, 5 give surviving-wrong ratios of
exactly 0, 0.2, 0.4 and 0.8, so that band is empty by construction and not by measurement.

**84. Kind 4's whole deliverable was computed for every cell and thrown away at aggregation.**
Protocol.md 2.2 lists kind 4, "correct to genus, wrong at species only", with the note that it "tests
resolution rather than detection" -- so its deliverable is not recall but whether the tool names the
rank the injection actually moved. The previous session concluded that kind 4 was covered by the
species-distance cells without being named. That was half right: the cells exist, and the measurement
existed too.

`bin/score_injection.py` computes `recall_at_injected_rank` for every cell and every threshold, using
`mismatch_rank` against the cell's own declared lineage. `bin/aggregate_grid.py` never mentions the
field. So the one metric the protocol calls a separate error kind was computed 180 times per condition
and reached **no committed record**, which is the "computed but never reported" shape of finding 50 and
the counterpart of finding 73's "reported but never rebuilt".

Propagated, and it has a clean structure. Resolution -- the share of detections that name the right
rank -- rises monotonically with taxonomic distance: about **0.90 at species**, 0.95 at genus, 0.97 at
family, and **1.000 at phylum for every *k* >= 2**. So the rank-depth error costs roughly a tenth of the
detections at species distance and nothing at all at phylum, which is kind 4's limit stated in the terms
2.2 asks for. `None` for the foreign cells, where the reference holds no bacteria and no rank can be
named -- a condition `score_injection.py` had already reasoned through and which propagates with it.

Purely additive: eleven records gained the field with every pre-existing value unchanged.

And a defect of my own, introduced two sessions earlier and caught by running the thing. The kind 3 and
simulation steps added to `bin/analyses.sh` guarded on the experiment existing and then looped over both
conditions, so the whole analysis failed the moment one arm had been repatriated and the other was still
running -- which is the normal state while a comparator catches up, upstream taking sixteen times as long
per cell. Guarded per condition now, skipping the pending arm with a line that says so. The same loop
also had `grep -vc` on a file with no data rows failing the step under `set -e`, where zero flags on the
un-injected reference is the result the control exists to produce.

**85. The simulation control's comparison could not have reached significance, and the floor was the
design.** With the upstream arm finished, the control answers for both tools. **Neither flags anything on
the un-injected simulated reference**: 0 of 864 certainly-correct sequences for the fork and 0 for
upstream, where on the real 2 023-sequence set they flag 93 and 92, 4.6 % and 4.55 %, which 2.4 forbids
calling false positives. So the strict rate is 0.00 % for both, and the 4.6 % on real data is the
reference's own content rather than noise either method generates.

Recall where every label is certain reproduces the archaeal grid's central finding. Both tools are at or
near 1.000 at *k*=1 and *k*=2 and both at 0.000 at *k*=5, and **the fork leads in the middle**: +0.200 at
species, +0.133 at genus, +0.222 at family, all at *k*=3, and +0.186 in the 0.4-0.6 band of the
surviving-ratio law. That is the same shape as the real grid's +0.240 and +0.152 at *k*=2 and 3, on data
where the labels are certain -- so the advantage is not an artefact of GTDB's pre-existing errors.

**And then the paired test said p = 0.25 with three cells of three favouring the fork.** Not because the
evidence is weak: because a two-sided sign test over three non-tied pairs cannot report below
2 × (1/2)³ = **0.2500** however one-sided the data, and the control had one injection seed, so there were
three cells per *k*. The floor was the design and not the measurement, and it was invisible until the
statistic ran. The real grid has used three seeds throughout for exactly this reason; the control did not,
and nothing in building it said so.

Three seeds now, on the one simulated reference, which is the real grid's design -- one base, three seeds.
Nine cells per *k* puts the floor at 2 × (1/2)⁹ = **0.0039**, computed rather than assumed. 36 injected
cells against 12, all verified against their truth, and the 24 new ones byte-identical between macOS and
the cluster.

**86. Kind 3's prediction holds for both tools, and the comparison between them is underpowered by
construction.** Finding 82 reported the mechanism on the fork and committed to a prediction rather than
an assumption: that it is a property of leave-one-out and not of the placement engine, so upstream's
pending arm should show it too. Upstream finished, 36 tasks of 36, and it does -- **absolutely**:

| | fork | upstream |
|---|---|---|
| `within` >= 0.99, 39 clades, 167 sequences | 0.012 | **0.000** |
| `within` < 0.99, 15 clades, 59 sequences | 0.339 | 0.237 |

Not one of the 167 sequences in a cohesive clade is detected by upstream. Separation, 2.2's variable,
again fails to order anything: 0.146, 0.086, 0.000, 0.033 from least separable to most, highest where the
clade can least anchor itself. So the reversal finding 82 reported is the mechanism and not an engine
artefact, and it is *stricter* for upstream, which fits: strict leave-one-out removes one sequence at a
time, so a cohesive clade's remaining members always anchor the wrong label, where the fork's k-fold
batching can occasionally take several of them together.

Overall kind 3 recall is **0.097 for the fork against 0.062 for upstream**, 22 and 14 of 226 sequences.
The fork leads in 4 clades, upstream in none, and **50 of 54 tie at zero** -- which is what makes the
comparison unusable as a test: an exact two-sided sign test over 4 untied pairs cannot report below
2 × (1/2)⁴ = **0.1250**, and it returns exactly that. The floor is the design again, as in finding 85,
but for a different reason: there it was one seed where the grid uses three, here it is that kind 3 is so
near-undetectable that almost every clade ties. Reaching nine untied pairs would need about 120 clades,
twenty cells instead of nine.

Not run, and that is 2.2's own framing rather than a shortcut: kind 3 is listed as "characterised, with
the limit stated", not scored, and three hours of cluster time to put a p-value on a kind the protocol
does not ask to score buys less than saying plainly that the two tools differ by 8 sequences in 226 and
that the design cannot call it.

One mechanistic detail, consistent and not proven. The four clades the fork detects and upstream does not
are **all of size 3**, with the fork taking 2 or 3 of the 3 where upstream takes 0 or 1. Fold batching is
the only route by which the fork can differ here, and with 25 folds over 2 023 sequences a clade of 3 has
a modest chance of two members landing in one fold. Four cases is a consistent story, not evidence.

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
