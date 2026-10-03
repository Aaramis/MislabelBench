# Distributing the leave-one-out

The one thing upstream SATIVA cannot do at any price is place folds outside its own process. The
fork splits the leave-one-out into four stages — `reference`, `loo-tasks`, `loo-place`, `loo-score` —
and only the third distributes. Protocol.md claims "a mode that distributes across jobs".

The pipeline now has the staged mode: `STAGEDREFERENCE`, `STAGEDLOOTASKS`, `STAGEDLOOPLACE` and
`STAGEDLOOSCORE`, behind `--staged`, with `--folds_per_job` setting the shard size and the `ifb`
profile putting each task in its own Slurm job. `slurm/scaling.sh` keeps the `srun` version, because
it is the measurement the pipeline has to match.

The rest of this file is what the design had to account for, measured rather than assumed.

## What `loo-tasks` actually produces

On gtdb_arc1200, 7 051 sequences, 25 folds:

```
run.l1o_tasks/           275 MB, 146 files
  manifest.json          folds, leaves, the epang args, the command
  model
  fold_000/
    ref.fasta            10 MB   the alignment minus this fold's leaves
    ref.nwk              384 KB
    query.fasta          430 KB
    model                2.7 KB
    epa_result.jplace    760 KB  written by loo-place
    epa_info.log, epang.log
  fold_001 … fold_024
```

**246 of the 275 MB is the 25 per-fold copies of the reference alignment.** The queries total 11 MB
and the placements the stage produces total 8.9 MB.

## What that rules out

`scaling.sh` fans out with one `srun` per node, each running `-folds i/N` against **one shared
taskdir on a POSIX filesystem**. Nothing is staged; the tasks write into the same directory. That is
why it measures 73 % parallel efficiency at N=2, and it is a number the pipeline cannot simply
inherit: Nextflow gives each task its own directory and does not assume a shared filesystem, which
is the point of it.

A shard-shaped fan-out — N tasks, each receiving the whole taskdir — would stage **275 MB per shard
to produce 9 MB**. At N=4 that is 1.1 GB of copying for a placement step of a few minutes. Wrong
shape.

## The design that fits

**One task per fold, or per group of folds**, which is also what `--folds_per_job` should mean:

```
SEREFERENCE   fasta, tax            -> run.refjson, run.model
SELOOTASKS    refjson               -> manifest.json, model, and fold_000 … fold_024 as 25
                                       separate channel elements
SELOOPLACE    manifest, model, k folds -> the jplace and logs for those folds
SELOOSCORE    refjson, all folds    -> the .mis
```

Staging is then 11 MB per fold and 275 MB in total however many tasks there are, instead of 275 MB
multiplied by the shard count. `--folds_per_job` becomes the group size, Nextflow's own scheduler
replaces the `srun` loop, and the Slurm executor places the tasks.

## Checked: a one-fold task directory is enough

`-folds i/N` is a stride over the fold list in `manifest.json`, and the manifest names all 25 folds
whatever the taskdir holds, so it was not obvious that a subset would work. `slurm/fold_subset_probe.sh`
builds a directory holding `manifest.json`, `model` and `fold_007` only and runs
`-stage loo-place -folds 7/25` against it:

```
staged for fold_007: 12M against 284M for the whole directory
[epang-l1o] placed 1/1 folds (1 at a time, 8 threads each, 22.1s)
exit status: 0
jplace: 786803 bytes
```

So the design above stands as written, with **12 MB staged per fold**.

## What the shard-shaped version actually measures

The `srun` fan-out was run on this dataset, three replicates per node count:

| N | placement | total |
|---|---|---|
| 1 | 195.59 ± 0.67 | 265.93 |
| 2 | 123.93 ± 27.14 | 193.95 |
| 4 | 197.57 ± 134.08 | 267.99 |

**N=4 is no faster than N=1**, and the per-shard logs say why: in all three replicates three shards
finish in 56 to 62 s, which is what six folds at 9.3 s each predicts, and one takes 124, 207 or
258 s. One straggling node per allocation sets the step time. At 140 of a node's ~510 cores the
other 370 go to other tenants, and `--exclusive` on four nodes is 2 040 CPUs against a 600-CPU
quota, so this is not fixable by asking for the nodes.

That is an argument *for* splitting the work finer rather than against it: Nextflow reschedules a
task that lands on a slow node, where a shard holds the whole step. It is not an argument that the
pipeline will beat 1.58x at N=2, which remains the number to match.

## One task per fold is too fine, and the logs say how fine is fine

The tool reports its own concurrency, and at eight threads it is always the same:

```
placed 25/25 folds (4 at a time, 2 threads each, 194.4s)    7.8 s per fold
placed  6/6  folds (4 at a time, 2 threads each,  55.9s)    9.3 s per fold
placed  1/1  fold  (1 at a time, 8 threads each,  22.1s)   22.1 s per fold
```

**EPA-ng parallelises badly across threads and well across folds.** Given eight threads it runs four
placements of two threads each; given one fold it can only run one placement on eight threads, and
that costs **2.4 to 2.8 times more per fold**. So a task holding a single fold is the worst possible
granularity, and `--folds_per_job` has a floor rather than being free to choose: at eight threads it
should be at least four, which is the tool's own internal concurrency.

Nothing here says what that internal number is at other thread counts — every run in this repository
places with `-T 8`. That is the first thing the staged pipeline should measure.

## The tool does not fail when folds fail

An OOM-killed run logged `[epang-l1o] EPA-ng FAIL fold 18:`, with nothing after the colon, then
`placed 7/12 folds`, and carried on. The only symptom was the scoring stage crashing later on an
empty jplace. The fold count in the log is the sole signal, so `scaling.sh` now counts the
placements itself before scoring — every fold must have one and none may be empty — and the staged
pipeline needs the same check between its placement and scoring stages.

## What this does not change

The claim itself is about the tool and `slurm/scaling.sh` measures it. What is missing is the claim
being reproducible *through the harness*, which is what the rest of this repository is for.
