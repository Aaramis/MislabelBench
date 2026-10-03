# Distributing the leave-one-out, and why it is not in the harness yet

The one thing upstream SATIVA cannot do at any price is place folds outside its own process. The
fork splits the leave-one-out into four stages — `reference`, `loo-tasks`, `loo-place`, `loo-score` —
and only the third distributes. Protocol.md claims "a mode that distributes across jobs", and the
evidence for it comes from `slurm/scaling.sh`, which drives the tool directly with `srun`. The
pipeline has no staged mode: `grep -rn "folds_per_job\|loo-place\|taskdir\|stage" main.nf modules/
nextflow.config conf/` returns nothing.

This is what the design has to account for, measured rather than assumed.

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

## The one thing that has to be checked first

`-folds i/N` is a stride over the fold list in `manifest.json`, and the manifest names all 25 folds
whatever the taskdir holds. **Does `-stage loo-place -taskdir X -folds i/25` work when X contains
`manifest.json`, `model` and only `fold_i`?** If it does, the design above stands as written. If the
tool insists on finding every fold the manifest lists, the fold directories have to be staged
together and the choice is between the 275 MB-per-shard copy and patching the manifest per task.

That is a two-minute test on the cluster and it has not been run, because a one-core job landing on
the node of a timed scaling run would contaminate the measurement it is there to support.

## What this does not change

The claim itself is about the tool and `slurm/scaling.sh` measures it. What is missing is the claim
being reproducible *through the harness*, which is what the rest of this repository is for.
