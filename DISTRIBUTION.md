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
run.l1o_tasks/           284 MB, 177 files   (2 at the top, 25 folds of 7)
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

**257 of the 284 MB is the 25 per-fold copies of the reference alignment.** The queries total 10.7 MB
and the placements the stage produces total 19.2 MB.

Those four aggregates were 275 MB, 146 files, 246 MB and 8.9 MB here until they were measured against a
real `run.l1o_tasks` on gtdb_arc1200 rather than carried forward. The per-fold figures above were right;
only the sums were not, and the placements were out by a factor of two.

## What that rules out

`scaling.sh` fans out with one `srun` per node, each running `-folds i/N` against **one shared
taskdir on a POSIX filesystem**. Nothing is staged; the tasks write into the same directory. That is
why it measures 79 % parallel efficiency at N=2 -- 195.59 s against 123.93 s in the table below is
1.58x, and the 73 % that stood here is 1.47x from the superseded gtdb_arc2k round (D82), and it is a number the pipeline cannot simply
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

Staging is then 12 MB per fold and 284 MB in total however many tasks there are, instead of 284 MB
multiplied by the shard count. 11 MB is the total of all 25 queries, not what one fold costs; a fold
carries its own copy of the alignment and that is what makes it 12. `--folds_per_job` becomes the group size, Nextflow's own scheduler
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

The `srun` fan-out was run on this dataset, three replicates per node count. Every spread quoted
here and in `results/scaling_summary.txt` is max minus min over those three, not a standard
deviation — `bin/scaling_summary.py` computes the range, and printing it after a plus-or-minus sign
invited the other reading until it was relabelled.

| N | placement, mean and spread | total |
|---|---|---|
| 1 | 195.59 (spread 0.67) | 265.93 |
| 2 | 123.93 (spread 27.14) | 193.95 |
| 4 | 197.57 (spread 134.08) | 267.99 |

**N=4 is no faster than N=1**, and the per-shard logs say why: in all three replicates three shards
finish in 56 to 62 s, which is what six folds at 9.3 s each predicts, and one takes 124, 207 or
258 s. One straggling node per allocation sets the step time. At 140 of a node's ~510 cores the
other 370 go to other tenants, and `--exclusive` on four nodes is 2 040 CPUs against a 600-CPU
quota, so this is not fixable by asking for the nodes.

That is an argument *for* splitting the work finer rather than against it: Nextflow reschedules a
task that lands on a slow node, where a shard holds the whole step.

## And the pipeline beats it

One replicate per shard count, `gtdb_arc1200`, `-profile ifb`, every stage its own Slurm job:

| shards | folds per shard | placement | speedup | vs shards | ceiling | vs ceiling | the `srun` version | its speedup |
|---|---|---|---|---|---|---|---|---|
| 1 | 25 | 194.5 | 1.00 | — | 1.00 | — | 195.59 (spread 0.67) | 1.00 |
| 2 | 13, 12 | 111.2 | **1.75** | 87 % | 1.92 | 91.0 % | 123.93 (spread 27.14) | 1.58 |
| 4 | 7, 6, 6, 6 | **56.4** | **3.45** | 86 % | 3.57 | **96.6 %** | 197.57 (spread 134.08) | 0.99 |

25 folds over 4 shards split 7, 6, 6, 6, the step ends when the shard holding 7 ends, and no
distribution however free beats 25/7 = 3.57. So the 86 % is mostly the arithmetic of 25 not dividing by
4; against what the split allows the placement runs at 96.6 %. Both columns are here because they answer
different questions and only one of them is about overhead.

**At one shard the two agree to 0.6 %** — 194.5 s against 195.59 with a spread of 0.67 over three replicates — which is the check that
the staged pipeline does the same placement work as the `srun` version rather than something
cheaper.

**At four shards the pipeline's spread is 0.6 s** (55.8, 56.2, 56.3, 56.4) where the `srun`
version's was 134 s. That is the whole difference and it has one cause: each task is its own Slurm
allocation of eight cores, so a shard cannot lose cores to another tenant the way a shard sharing one
140-core allocation can. The expectation written here first — that a pipeline fan-out would land below
1.58x because of staging — was wrong, and wrong for an interesting reason: the staging it pays for is
less than the contention it avoids.

**The four shards were on one node, not four.** `slurm/shard_nodes.sh` resolves each shard's Slurm job
through accounting, since Nextflow's `hostname` trace field is empty under the Slurm executor here, and
the answer for this round is `cpu-node-121` four times; `pipeline_info/shard_nodes.tsv` records it, and
the two-shard round is the same. So what these numbers measure is a split into independently scheduled
jobs, each with its own cores and its own staged inputs, that the scheduler happened to place together
on one 512-core machine. Separate machines are what the mode allows and not what was measured, and the
difference is memory bandwidth rather than cores: four shards on one node share it, so a run on four
nodes should be no slower than this and the speedup here is a floor. Nothing forces the spread, because
`--exclusive` is the mechanism that would and the QOS refuses it at two shards, let alone four.

**What does not scale is the end-to-end wall clock.**

| shards | stage sum | trace span | Nextflow's share |
|---|---|---|---|
| 1 | 288.2 | 374.3 | 86.1 |
| 2 | 205.4 | 320.0 | 114.6 |
| 4 | 151.1 | 314.2 | 163.1 |

The placement step falls 194.5 → 56.4 and the span only 374 → 314, because scheduling and staging
grow with the task count and reach 163 s at four shards. So the honest form of the claim is that
the *placement step* reaches 96.6 % of what its fold split allows, 86 % measured against the shard count,
and that a user's wall clock saturates near 314 s on this dataset however many shards are used. Reporting the stages separately, which the
protocol already promises, is what makes that visible.

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
empty jplace. The fold count in the log is the sole signal, so `scaling.sh` counts the
placements itself before scoring — every fold must have one and none may be empty — and the staged
pipeline has the same check twice over, which this file asked for and then did not record as done:
`stagedlooplace` counts its shard's placements against its fold directories and refuses an empty one,
and `stagedlooscore` counts the folds it collected against `n_folds` in the manifest, so a lost shard
fails there rather than scoring part of the database. Both compare with `-eq` and not `=`, because
`wc -l` pads its output on some platforms.

## What this does not change

The claim itself is about the tool and `slurm/scaling.sh` measures it. What is missing is the claim
being reproducible *through the harness*, which is what the rest of this repository is for.
