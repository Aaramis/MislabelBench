# sativa-epang-benchmark

Does replacing SATIVA's placement engine with EPA-ng change its answers, and what does it cost?

SATIVA (Kozlov *et al.* 2016) finds mislabelled sequences in a taxonomic reference by removing each
one and placing it back into a tree built without it. Its leave-one-out uses RAxML, which bounds it
to a few thousand sequences. [sativa-epang](https://github.com/Aaramis/sativa-epang) replaces the
placement engine with EPA-ng (Barbera *et al.* 2019) and splits the leave-one-out into stages a
workflow manager can distribute. The classification rule is upstream's, unchanged.

This is a benchmark of that modification, not a new method.

## What it measures, and what it found

Numbers below are medians over replicates on one pinned CPU model. GTDB r226 archaeal 16S, 7 051
sequences for the headline and a 2 023-sequence subset drawn by whole taxa for the grid.

**Speed.** 262 s against 2 950 s on the full set: 11.2x in wall clock. The more useful figure is
16.2x in **CPU time**, because upstream saturates the eight threads it is given, 7.97 of 8, while the
fork uses 5.5. On the 2 023-sequence subset the pair is 19.3x and 35.3x. At 402 sequences the fork
uses 3.1 of 8 threads, so on a small reference it should be given fewer.

**Determinism, across CPU architectures and not only across runs.** The same cell and the same seed
produce a byte-identical `.mis` on hardware nine years apart. Three independent productions of
`inj_species_r0.05_k3_s1` under `epang_T8_K25`, each a separate Slurm job with its own work
directory:

| run | node | CPU | wall | md5 of the `.mis` |
|---|---|---|---|---|
| grid cell | cpu-node-123 | AMD EPYC 9754 | 38.0 s | `b41934ad…` |
| determinism, 2 Oct | cpu-node-37 | Intel Xeon E5-2695 v3 | 66.0 s | `b41934ad…` |
| determinism, rerun | cpu-node-16 | Intel Xeon E5-2695 v3 | 56.3 s | `b41934ad…` |

A 1.7-fold spread in seconds and the same 161 flags to the byte. `slurm/determinism.sh` is what
re-runs it, and it is also the only check that exercises the pipeline rather than the analysis layer:
`bin/analyses.sh` rebuilds every number from the run directories and never invokes Nextflow.

**Reproducibility of the timings themselves.** The fork varies by 1 % across two nodes of the same
model. Upstream agrees to 0.7 s on one node and differs by a third between two, which is why every
number here is a median over replicates and why `run.json` records the CPU model.

**Detection, and a claim this version of the benchmark does not support.** Version 1 reported that
upstream found 28 of 33 injected mislabels and the fork 33, and attributed every miss to several
sequences sharing one wrong label, which "a strict leave-one-out cannot see and a fold can". A
180-cell grid does not bear that out. Recall falls with the number of sequences sharing the wrong
label, *k*, for both tools alike: 0.94 at *k*=1 to 0.13 at *k*=10. What predicts detection is not *k*
and not the fold count but the proportion of a sequence's surviving relatives that carry the wrong
label, and recall runs 0.87 down to 0.01 across that range.

**What the fork does find, which version 1 missed.** On the complete 180-cell grid the fork detects
more than upstream at intermediate *k*:

| *k* | cells | mean difference | fork better | upstream better | tied | sign test |
|---|---|---|---|---|---|---|
| 1 | 36 | +0.006 | 14 | 5 | 17 | 0.064 |
| 2 | 36 | **+0.240** | 34 | **0** | 2 | 1.2e-10 |
| 3 | 36 | +0.152 | 34 | **0** | 2 | 1.2e-10 |
| 5 | 36 | +0.104 | 28 | 1 | 7 | 1.1e-07 |
| 10 | 36 | +0.005 | 9 | 2 | 25 | 0.065 |

At *k*=2 and *k*=3 no cell of the 36 favours upstream. Over the whole grid the fork is better in
119 cells, upstream in 8, and the two tie in 53.

Both ends are flat for opposite reasons: *k*=1 is a ceiling, where one relabelled sequence per group
leaves the rest of the group correct and both tools detect 0.92 and 0.94, and *k*=10 is a floor,
0.12 and 0.13.

Where the two disagree on an injected sequence, across all 11 178 injections, the fork alone is
right 1 243 times against upstream's 115. That ratio is the wrong thing to quote alone, so: both
tools find 4 203, **neither finds 5 617 — half of every mislabel injected**. The fork finds 48.7 %
of them and upstream 38.6 %. The gap between the tools is real and smaller than the gap between
either tool and the truth.

**And the cause is the engine, not the fold scheme.** `epang_T8_Kexact` places one sequence per
fold, which is upstream's own leave-one-out protocol run through EPA-ng, so it separates the two
changes. On two *k*=2 cells the engine with the folds removed is worth +0.284 and +0.177, while the
fold scheme with the engine held fixed is worth −0.020 and 0.000.

The fold scheme does something, but only at the highest *k* and only a little. Comparing conditions
cell by cell at *k*=10: five folds instead of twenty-five gains 0.035 and is better in 17 of the 18
cells where the two differ; dealing the folds in tree order instead of by sequence name removes 0.036
and is worse in 18 of 18. At *k*=1 a larger fold costs accuracy instead, because it takes more of a
sequence's true relatives with it.

**Distribution, which is the one thing upstream cannot do at any price.** Upstream places folds only
inside its own process. The fork splits the leave-one-out into four stages and the harness runs them
as separate Slurm jobs, one per group of folds. On 7 051 sequences, 25 folds, one replicate each:

| shards | placement | speedup | efficiency | end-to-end span |
|---|---|---|---|---|
| 1 | 194.5 s | 1.00 | — | 374 s |
| 2 | 111.2 s | 1.75 | 87 % | 320 s |
| 4 | 56.4 s | 3.45 | 86 % | 314 s |

Two things have to be said together. The placement step distributes at about 86 % efficiency, and
the end-to-end wall clock saturates near 314 s because Nextflow's scheduling and staging grow with
the task count, reaching 163 s at four shards. At one shard the pipeline agrees with the `srun`
version to 0.6 %, which is what shows it does the same work.

**Where those failures belong.** At *k*=10, 92 % of the sequences leave-one-out misses still have a
correctly labelled neighbour above 99 % identity, so a label conflict inside a cluster catches them
without any placement. That is a pipeline-level check rather than a tool-level one.

## Running it

Everything runs as a Nextflow workflow with each tool pinned by container and build string, and each
dataset by sha256 (`assets/datasets.yml`). There is no conda environment to build.

```bash
export BENCH_ROOT=/path/to/a/working/copy      # defaults to $HOME/bench
bash slurm/make_grid.sh                        # the injection grid, 180 cells, from their seeds
slurm/submit.sh slurm/baseline.sh              # both tools on the un-injected database, timed
slurm/submit.sh slurm/grid_fork.sh             # one condition over the grid
bin/analyses.sh                                # rebuild every table in results/ from the runs
python3 -m unittest discover -s tests          # the analysis layer's tests
```

`make_grid.sh` comes first because the injected cells are not in the repository: they are the base
taxonomy with a few hundred labels rewritten, and rebuilding all 180 from their seeds takes under a
minute and needs neither cluster nor container. [`data/README.md`](data/README.md) says what is kept
and what is regenerated, with the check that the regenerated cells come back byte-identical.

`slurm/submit.sh` excludes the nodes recorded in `slurm/bad_nodes.txt`, which the jobs themselves
append to when they land on one without singularity. Every path in every job script hangs off
`BENCH_ROOT`, so a copy of this repo runs from anywhere.

Two rules the scripts enforce, both learned by getting them wrong first.

**A timed run pins the CPU model.** The cluster mixes four generations and the oldest is about half
the per-core speed of the newest, so `--constraint` is not optional and `cpu_model` goes into
`run.json` — into 641 of the 949 records, the rest predating the field. Five of those are trusted
runs, and `verify_runs.py` says so every time it runs; the four baselines among them are on
`cpu-node-123`, which Slurm reports as `epyc-9754`, the model their script asked for. Untimed runs,
which answer detection questions, do not pin and do not take the node: `--exclusive` bills all 510
cores of a node against a 600-core quota and starves every other job.

**A timed run has the machine to itself.** `executor.queueSize = 1` when `params.timed`, which is
the only cap Nextflow applies across processes: `maxForks` is per process, so setting it through a
label let one SATIVA and one SATIVAEPANG run side by side, as the baseline trace shows them doing
for 38 seconds. The allocation was six times larger than the two of them needed, so no published
number moved, which is luck and not a guarantee.

**A run that is not trusted says so.** `--timing_trusted false` is recorded in `run.json`, and no
figure reads seconds from a run that carries it.

## Layout

```
main.nf  nextflow.config  conf/        the harness: grid as channel combines, one container per tool
modules/local/                         sativa, sativaepang, collectrun, alignssu
bin/                                   preparation, injection, scoring, analysis; analyses.sh runs them all
slurm/                                 one script per measurement, plus prelude.sh and submit.sh
tests/                                 unittest over the scripts that turn runs into numbers
assets/datasets.yml                    every source with version, DOI, URL, date and sha256
data/                                  the base datasets and the injected ground truth; see data/README.md
results/                               the measured runs and the tables built from them
```

`results/` is tracked: the runs are the evidence, and the tables are rebuilt from them by
`bin/analyses.sh`, so a change to any script shows up as a diff rather than as a number nobody can
re-derive. That sentence was false until the 949 run directories behind the version 2 tables were
brought back from the cluster — only `run.json` had been kept for them, and every detection number
is computed from the `.mis` beside it. `results/pipeline_info/` holds one Nextflow trace per
submission, with its gaps listed.

**[`DISTRIBUTION.md`](DISTRIBUTION.md)** is the distributed leave-one-out: what a fold task
directory actually contains, why the fan-out is one task per group of folds and not per shard or per
fold, and the measurements on both the `srun` version and the pipeline.

**[`REVIEW.md`](REVIEW.md)** is a pass over every part of this repository looking for defects rather
than confirming that it works. Twenty findings, three of which had produced a wrong number, with how
each was found and how the fix was checked. It also lists what was checked and found correct, and the
six defects introduced or missed by the review itself.

## Version 1

`RESULTS.md`, `scripts/`, `data_ascii/`, `data_injected/` and `results/runs_injected/` are the earlier
benchmark, on ITS data, driven by shell scripts over four hand-built conda environments. They are
kept because `RESULTS.md` cites their numbers, and its setup instructions are in `scripts/README.md`.
Where version 1 and this one disagree, as on detection above, this one supersedes it: it has three
seeds, 180 cells and replicated timings where version 1 had one run per condition.

`sativa_epang/` is version 1's copy of the modified tool and **is not what runs here** — see
`sativa_epang/NOT_WHAT_RUNS.md`. The harness installs `bioconda::sativa-epang` in a container.
