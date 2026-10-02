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

The fold scheme does help, and the effect can be switched on and off, which is how it was pinned
down. Comparing conditions cell by cell at *k*=10: five folds instead of twenty-five gains 0.035 and
is better in 17 of the 18 cells where the two differ; dealing the folds in tree order instead of by
sequence name removes 0.036 and is worse in 18 of 18. So fold co-removal is real and small, and only
at the highest *k*. At *k*=1 a larger fold costs accuracy instead, because it takes more of a
sequence's true relatives with it.

**Where those failures belong.** At *k*=10, 92 % of the sequences leave-one-out misses still have a
correctly labelled neighbour above 99 % identity, so a label conflict inside a cluster catches them
without any placement. That is a pipeline-level check rather than a tool-level one.

## Running it

Everything runs as a Nextflow workflow with each tool pinned by container and build string, and each
dataset by sha256 (`assets/datasets.yml`). There is no conda environment to build.

```bash
export BENCH_ROOT=/path/to/a/working/copy      # defaults to $HOME/bench
slurm/submit.sh slurm/baseline.sh              # both tools on the un-injected database, timed
bash slurm/make_grid.sh                        # the injection grid, 180 cells
slurm/submit.sh slurm/grid_fork.sh             # one condition over the grid
bin/analyses.sh                                # rebuild every table in results/ from the runs
python3 -m unittest discover -s tests          # the analysis layer's tests
```

`slurm/submit.sh` excludes the nodes recorded in `slurm/bad_nodes.txt`, which the jobs themselves
append to when they land on one without singularity. Every path in every job script hangs off
`BENCH_ROOT`, so a copy of this repo runs from anywhere.

Two rules the scripts enforce, both learned by getting them wrong first.

**A timed run pins the CPU model.** The cluster mixes four generations and the oldest is about half
the per-core speed of the newest, so `--constraint` is not optional and `cpu_model` goes into every
`run.json`. Untimed runs, which answer detection questions, do not pin and do not take the node:
`--exclusive` bills all 510 cores of a node against a 600-core quota and starves every other job.

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
results/                               the measured runs and the tables built from them
```

`results/` is tracked: the runs are the evidence, and the tables are rebuilt from them by
`bin/analyses.sh`, so a change to any script shows up as a diff rather than as a number nobody can
re-derive.

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
