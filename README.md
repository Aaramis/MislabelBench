# sativa-epang-benchmark

Does replacing SATIVA's placement engine with EPA-ng change its answers, and what does it cost?

SATIVA (Kozlov *et al.* 2016) finds mislabelled sequences in a taxonomic reference by removing each
one and placing it back into a tree built without it. Its leave-one-out uses RAxML, which bounds it
to a few thousand sequences. [sativa-epang](https://github.com/Aaramis/sativa-epang) replaces the
placement engine with EPA-ng (Barbera *et al.* 2019) and splits the leave-one-out into stages a
workflow manager can distribute. The classification rule is upstream's, unchanged.

This is a benchmark of that modification, not a new method.

The paper's figure is `results/figure1.svg`, built by `bin/make_figure.py` from the committed tables:
wall clock against reference size for both tools, the stages at one, two and four nodes, the exclusion
column against confidence as a filter, and recall against *k*. It is written as SVG directly rather than
with a plotting library, so that the analysis layer keeps importing nothing outside the standard library
and so that the figure can be checked byte for byte like every other record here. Every value it draws is
also in `results/figure1_values.tsv`.

## What it measures, and what it found

Numbers below are medians over replicates on one pinned CPU model. GTDB r226 archaeal 16S, 7 051
sequences for the headline and a 2 023-sequence subset drawn by whole taxa for the grid.

**Speed.** 263.4 s against 2 983.6 s on the full set: **11.3x** in wall clock, medians over 7 fork
replicates and 4 upstream. The more useful figure is **16.2x** in **CPU time**, because upstream
saturates the eight threads it is given, 7.97 of 8, while the fork uses 5.57. On the 2 023-sequence
subset, 7 replicates each, the pair is **16.5x and 29.7x**. At 402 sequences the fork uses 3.09 of 8
threads, so on a small reference it should be given fewer. Every figure here is a row or a line of
`results/resource_usage.txt`, which `bin/analyses.sh` rebuilds; read it rather than this paragraph if
the two ever disagree. They did: this said 262, 2 950, 11.2x, and **19.3x and 35.3x** for the subset,
the last pair taken from one replicate before the others had run and 17 % and 19 % above the medians
that replaced it.

**The harness was validated against version 1, which has since been removed.** The plan's first
milestone asked for the new harness to land on version 1's figure of ~109 s for upstream at one thread.
It did not: on an exclusive epyc-9754 with the model pinned it measured **135.8 s, spread 0.9 s over
three replicates**, against 109.0 s on a 32-core workstation. The measurement is tight, so the 24 % was
the hardware and not the harness — single-threaded RAxML is bound by per-core speed and a 128-core part
is not where that is found.

Seconds from two machines cannot be compared; the answer can, and it was identical: `a1aa0f35…`, 48
flags, in all three replicates and in all three of version 1's. Version 1 ran sativa 0.9.3 from a
hand-built conda environment, this runs bioconda sativa 0.9.3 in a container pinned by build string, and
the two produced the same `.mis` to the byte.

Version 1 and its ITS datasets have since been removed, so this is a measurement that was performed and
recorded here, not a check that still stands: the job script, the n800 dataset it ran on and the version 1
runs it compared against are all gone. Its three run records went with them rather than being left for a
gate to report as belonging to no script, which is what `bin/verify_timing_flags.py` had begun doing.

**Determinism, across CPU architectures and not only across runs.** The same cell and the same seed
produce a byte-identical `.mis` on hardware nine years apart. Three independent productions of
`inj_species_r0.05_k3_s1` under `epang_T8_K25`, each a separate Slurm job with its own work
directory:

| run | node | CPU | wall | md5 of the `.mis` |
|---|---|---|---|---|
| grid cell | cpu-node-123 | AMD EPYC 9754 | 38.0 s | `b41934ad…` |
| determinism, 2 Oct | cpu-node-37 | Intel Xeon E5-2695 v3 | 66.0 s | `b41934ad…` |
| determinism, rerun | cpu-node-16 | Intel Xeon E5-2695 v3 | 56.3 s | `b41934ad…` |

And 42 more cells, which were run twice before anyone thought to compare them. `results/kaxis` and
`results/ksweep` are earlier, smaller runs of cells the 180-cell grid also covers, so each of their 42
run directories has a counterpart computed by a different Slurm job at a different time. All 42 `.mis`
are byte-identical to that counterpart, and **no pair shares a wall time** -- the widest is 731.8 s
against 526.2 s, 39 % apart -- so they are separate executions and not copies.
`bin/verify_duplicate_runs.py` is the check; it is not a separate result, and the grid is where those
cells' numbers are reported.

A 1.7-fold spread in seconds and the same 161 flags to the byte. Two of the three rows are records you
can open: the grid cell and the rerun. The 2 October row is not -- `determinism.sh` opens by clearing
its own output directory, so its successor wiped that run's `.mis`, and what survives is
`results/pipeline_info/trace-determinism.txt` giving the task 1m 9s against the rerun's 58.7 s. The
cross-vendor claim does not rest on it: the surviving determinism record is the Intel one,
`cpu-node-16`, and the grid cell is `cpu-node-123`, which Slurm reports as `epyc-9754`. That record
carries no `cpu_model` of its own, which is the gap `bin/verify_runs.py` reports on every run. `slurm/determinism.sh` is what
re-runs it, and it is also the only check that exercises the pipeline rather than the analysis layer:
`bin/analyses.sh` rebuilds every number from the run directories and never invokes Nextflow.

**Reproducibility of the timings themselves.** The fork varies by 1 % across two nodes of the same
model. Upstream agrees to 0.7 s on one node and differs by a third between two, which is why every
number here is a median over replicates and why `run.json` records the CPU model.

**Detection, and a claim an earlier version of this benchmark does not support.** The first version,
on ITS data with one replicate per scenario, reported that upstream found 28 of 33 injected mislabels
and the fork 33, and attributed every miss to several
sequences sharing one wrong label, which "a strict leave-one-out cannot see and a fold can". A
180-cell grid does not bear that out. Recall falls with the number of sequences sharing the wrong
label, *k*, for both tools alike: 0.94 at *k*=1 to 0.13 at *k*=10. What predicts detection is not *k*
and not the fold count but the proportion of a sequence's surviving relatives that carry the wrong
label, and recall runs 0.87 down to 0.01 across that range.

**What the fork does find, which the first version missed.** On the complete 180-cell grid the fork detects
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

Two checks stand behind those two sentences. The fold-order conditions differ from their base
conditions in **180 cells of 180** -- the `.mis` files are not byte-identical anywhere -- so
`SATIVA_EPANG_FOLD_ORDER` does reach the container and the comparison is not a condition against
itself, which `run.json` could not have told you since it records what was declared. And the three
paired comparisons of this family are 15 tests together, so the two claims above are stated at
p = 0.000145 and p = 7.6e-06 against a Bonferroni threshold of 0.05/15 = 0.0033, which both clear by
more than an order of magnitude. The *k*=3 effects in the same family, p = 0.0064 and 0.0025, do not
clear it as decisively and are not claimed here.

**The baseline is not a fixed reference point.** Reporting flags added above the un-injected
baseline assumes the pre-existing flags stay put. They do not: injecting a wrong label moves a
sequence in the tree and changes the placement of its neighbours. Over the 180 cells, against a
baseline of 93 flags, a typical cell **loses 11 of them** (12 %, up to 21) while gaining 29 (31 %, up
to 70). So the churn is about 40 flags where the net change is 18, and a count of added flags
describes the smaller half of what injection does to the background.

**And they fall where the injection landed.** 2.4 asks for a locality measure beside the collateral
count, because scattered collateral would mean injection destabilises the whole tree rather than its
neighbourhood. Of 5 917 collateral flags, **4 623, or 78.1 %, lie in a clade the injection touched**, and
the share tracks the distance injected: 95.4 % at phylum down to 58.0 % at species. So the effect is
local and explainable, more so the coarser the error. `results/collateral_locality.txt`.

That is the measurement behind Q6 of the protocol, which asks whether reporting both directions is
the right rule. It is reported in both directions here, `results/background_stability.tsv`, because
the answer turned out to matter: 12 % is not a rounding error on a baseline.

**What the fork's new column is worth, which is not what it looks like.** `OriginalLabelExclusion` is
the ninth `.mis` column and the fork's own addition, and the protocol asks for recall against it as well
as against `Confidence`. It is not a better score and the paper must not claim it is. **99.0 % of the
grid's 25 772 flags have exclusion >= 0.99**, so the column is saturated: no threshold on it brings the
calls on untouched sequences below 19 809 of 20 326, where a threshold on confidence reaches 10 320.
One column filters and the other does not.

What it does settle is a third of the calls. **8 057 flags, 31.3 % of them, sit at confidence exactly
0.510** — a point mass, not a cluster: 305 flags lie at 0.509 and 85 at 0.511, against a background two
orders of magnitude below. That value is what `parent_lhw_coeff` produces when the declared taxon holds
no placement weight at all, and **every one of the 8 057 carries exclusion >= 0.99**, which is the column
saying so independently. Without it a user reading confidence alone down-weights a third of the fork's
calls because of a stem geometry rather than because of the evidence. Both readings are right about
different questions, and that is the honest claim about the column: it explains calls, it does not rank
them. Every figure here is in `results/column_comparison.json`, with
`results/stem_flags.txt` and `results/threshold_holdout.json` beside it.

The practical consequence is to run with `-C` above 0.51, and a held-out selection reaches it without
being told: fitting on seed 1's 60 cells and reporting on the other 120, the tightest reachable budget
picks **0.511** — immediately above the stem value — and held-out collateral falls from 3 960 to 1 656,
a 58 % cut, for 4.0 points of recall. At the same budgets the exclusion column has no threshold to offer
at all: "budget unreachable" at 27.9 collateral flags per cell and below, where confidence still has one.
That is the same conclusion as the saturation above, by a route that never looks at the column's
distribution.

**What the marker cannot be asked, and where that bites.** The 7 051-sequence set contains 847
groups of byte-identical alignment rows, and **54 of them carry conflicting labels** — 7 disagreeing
first at phylum, 6 at class, 1 at order, 2 at family, 5 at genus, 33 at species, with 52 of the 54
identical in the unaligned release too. An identical 16S under two phylum labels means the marker
cannot separate those organisms, so no method placing it can either. That is a ceiling on
detectability and it belongs to the database, not to either tool.

It bounds the agreement figures above, which are measured on that set. It does **not** bound the
grid: the 2 023-sequence subset the grid runs on has 241 identical groups and **3 conflicting, none
above genus**. Three is what chance gives — 54 groups surviving a 29 % subsample at both members is
4.4 expected — so the recall figures are not limited by this, and the ceiling has to be quoted
against the set it was measured on.

**Distribution, which is the one thing upstream cannot do at any price.** Upstream places folds only
inside its own process. The fork splits the leave-one-out into four stages and the harness runs them
as separate Slurm jobs, one per group of folds. On 7 051 sequences, 25 folds, one replicate each:

| shards | folds per shard | placement | speedup | vs shards | ceiling | vs ceiling | end-to-end span |
|---|---|---|---|---|---|---|---|
| 1 | 25 | 194.5 s | 1.00 | — | 1.00 | — | 374 s |
| 2 | 13, 12 | 111.2 s | 1.75 | 87 % | 1.92 | 90.9 % | 320 s |
| 4 | 7, 6, 6, 6 | 56.4 s | 3.45 | 86 % | 3.57 | 96.5 % | 314 s |

Efficiency against the shard count is the conventional figure and it is the wrong one to read alone
here. 25 folds over 4 shards split 7, 6, 6, 6, the step ends when the shard holding 7 ends, and no
distribution however free beats 25/7 = 3.57. So the 86 % is mostly the arithmetic of 25 not dividing
by 4: against what the split allows the placement distributes at 96.5 %, and the shards finish within
0.6 s of each other where the `srun` version produced one straggler per allocation at 124 to 258 s
against its own 56 to 62. Three things then have to be said together: the distribution is very nearly
free, the fold count caps what it can buy, and the end-to-end wall clock saturates near 314 s because
Nextflow's scheduling and staging grow with the task count, reaching 163 s at four shards. At one
shard the pipeline agrees with the `srun` version to 0.6 %, which is what shows it does the same work.

**Why the *k* axis is not an independent variable.** Injecting *k* sequences from one taxon needs a
taxon with at least *k*+1 members, so raising *k* shrinks the eligible pool and shifts it towards
large taxa: at species distance 319 taxa qualify at *k*=1 and 31 at *k*=10. The donor groups actually
used follow:

| *k* | donor groups | median size | share of the group relabelled |
|---|---|---|---|
| 1 | 2 178 | 3 | 0.34 |
| 2 | 1 098 | 4 | 0.44 |
| 3 | 738 | 6 | 0.47 |
| 5 | 450 | 9 | 0.54 |
| 10 | 234 | 14 | **0.67** |

Every column of that table is in `by_k` of `results/detection_law_*.json`, weighted by injected
sequence and not by taxon: at *k*=5 the median donor group holds 9 members per injected sequence and 10
per distinct taxon, and the share is the mean of *k*/size over injections.

So *k* is a proxy for the share of a sequence's relatives that carry the wrong label, which is the
quantity that predicts detection. The two cannot be separated in this design — holding group size
fixed while varying *k* would leave 31 taxa to draw from — and that is why the result is reported
against the surviving-label ratio and not against *k*. The *k* table above is the same axis seen
twice, which is also why recall falls from 0.92 to 0.13 along it.

**Where those failures belong.** At *k*=10, 92 % of the sequences leave-one-out misses still have a
correctly labelled neighbour above 99 % identity, so a label conflict inside a cluster catches them
without any placement. That is a pipeline-level check rather than a tool-level one.

**The other four error kinds, which the typology asks for separately.** Kinds 1 and 2 are the grid
above. The protocol lists four more, each failing for a different reason, and each is reported here
rather than left in the decision log.

**Kind 3, a whole taxon misannotated**, removes leave-one-out's usual handle: with every member
relabelled, nothing correct remains to confirm the label. Over 54 clades and 226 sequences recall is
**0.097 for the fork and 0.062 for upstream**, and what governs it is not what the protocol expected. A
clade that can be told apart from the taxon it was mislabelled as is *not* the detectable case — the
variable is cohesion within the clade, and it runs the other way:

| | fork | upstream |
|---|---|---|
| members nearly identical, 39 clades, 167 sequences | 0.012 | **0.000** |
| diffuse clade, 15 clades, 59 sequences | 0.339 | 0.237 |

Not one of upstream's 167 sequences in a cohesive clade is detected. The reason is that the clade's
members are each other's nearest neighbours and all now carry the wrong label, so removing one leaves the
rest confirming it — kind 2's mechanism with *k* equal to the whole taxon. A compact clade does not anchor
itself against a wrong label; it anchors the wrong label. The two tools differ by 8 sequences in 226,
which this design cannot call: 50 of 54 clades tie at zero and a sign test over the 4 untied pairs cannot
report below 0.125. `results/clade_detection_*.json`.

**Kind 4 tests resolution rather than detection** — correct to genus, wrong at species only — and the
question is whether a detected mislabel is named at the rank the injection moved. It is, increasingly with
distance, pooled over the grid's sequences:

| distance | detected | named at the right rank | resolution |
|---|---|---|---|
| species | 690 | 619 | **0.897** |
| genus | 917 | 863 | 0.941 |
| family | 971 | 948 | 0.976 |
| order | 975 | 948 | 0.972 |
| class | 962 | 932 | 0.969 |
| phylum | 931 | 927 | **0.996** |

So a rank-depth error costs about a tenth of the detections at the shallowest distance and almost nothing
at the deepest, and at phylum every detection names phylum for every *k* >= 2.

Pooled over sequences, and the statistic is worth naming because the obvious alternative disagrees:
averaging each cell's ratio gives 0.82 at species rather than 0.897, since it weights a rate-0.01 cell
with a handful of detections the same as a rate-0.05 cell with ten times as many.
`recall_at_injected_rank_mean` in every grid summary carries the per-cell figure.

**Kind 5, incomplete lineages**, is a robustness case rather than a detection one, and it splits. Lineages
of unequal depth are accepted: a file with a quarter truncated to genus and a quarter to family runs
through and flags 11. An **empty** lineage is not: it raises `IndexError` in
`epac/taxonomy_util.py` line 337 while loading the taxonomy, before any placement. Both of the untrimmed
forms a placeholder-only lineage used to take — `d__;p__;…` and `;;;;;;` — run and flag 14, so what
breaks the tool is the trimming rather than the missing information. That matters for
nf-core/taxmarker#40, which produces the trimmed form. `results/ragged_check/`, `results/before_after/`.

**Kind 6, a foreign sequence under a plausible label**, is detected almost always: bacterial donors given
archaeal lineages are flagged at **1.000, 0.967 and 0.941** by the fork across the three injection rates
and 1.000, 0.933 and 0.957 by upstream. The protocol's caveat was that poor alignment rather than
placement might be doing the work, and it is not: within the donor pool the alignment score does not
separate the flagged from the escaped, medians 1009.14 against 1009.16 bits, and below the 5th percentile
of score 20 donors are flagged and 0 escape where 19.0 flagged is what independence predicts. The
escapees are not the badly aligned ones; they are the ones whose archaeal label happens to be shared with
another donor, which is kind 2 arriving by accident. `results/foreign_summary_*.json`,
`results/foreign_score_vs_flag_*.json`.

**A control where every label is certain.** Injection leaves one hole in itself: the sequences it did not
touch are only assumed correct, so a flag on one of them cannot be called a false positive. A simulated
reference closes it — sequences evolved along a tree that *is* the taxonomy, 864 of them — and the answer
is that **neither tool flags anything**: 0 of 864 for the fork and 0 for upstream, against 93 and 92 of
2 023 on the real set. So the 4.6 % on real data is the reference's own content and not noise the method
generates.

Recall there is **1.000 at *k*=1** at every distance with no collateral flags, against 0.746 and 133
collateral on the real grid, so that gap is the reference's difficulty rather than the method's ceiling.
And the surviving-ratio law reproduces out of sample, which is the stronger result: **1.000, 0.990, 0.822,
0.000** across the ratio bands against the archaeal **0.867, 0.600, 0.327, 0.110, 0.011** — monotone on
both, collapsing to nothing at the top of the range on both, offset by exactly the heterogeneity a simple
model cannot reproduce. The law is therefore a statement about leave-one-out and not about GTDB.

**And it is here, where every label is certain, that the two tools separate.** With upstream's arm now
complete at three seeds, the paired comparison has nine cells per *k* instead of three, and at *k*=3 --
half of each group relabelled together -- the fork detects more in **9 cells of 9**, recall 0.822 against
0.657, exact sign test **p = 0.0039**. That is the floor of the test at nine pairs, which is the point:
at three pairs the floor was 0.25 and no outcome could have been significant, which is why the control
was given three seeds rather than one. At *k*=1 and *k*=2 both tools are near perfect and the difference
is not testable; at *k*=5 neither detects anything. So the protocol's claim in 2.2 -- that the fork finds
shared mislabels upstream misses -- holds in the one setting where the ground truth is not an assumption,
and it holds at exactly the *k* where the design predicts the margin is visible.
`results/simulated_summary_*.json`, `results/detection_law_simulated_*.json`,
`results/paired_simulated_upstream_vs_epang_T8_K25.json`.

**Whether the fork's extra flags are better or noisier**, which the agreement control raises and cannot
settle. The un-injected set offers one piece of truth: 54 groups of byte-identical sequences carrying
conflicting labels, 265 sequences of which at least one member must be wrong, 3.76 % of the database.
Calls the two tools agree on are enriched **1.9-fold** in those groups, p = 0.002, so both are finding
something real. Upstream's 51 unique calls are enriched **4.2-fold**, p = 0.0006. The fork's 119 unique
calls sit at **0.89**, 4 observed against 4.5 expected, p = 0.66 — the background rate, and a tight null
rather than a small-sample shrug. On this measure upstream's extra flags are the better targeted. The
evidence is weak per sequence, since group membership says one member is wrong and not which, but it is
weak in the same way for both tools. `results/conflict_enrichment.json`.

## Running it

Everything runs as a Nextflow workflow with each tool pinned by container and build string, and each
dataset by sha256 (`assets/datasets.yml`). There is no conda environment to build.

```bash
export BENCH_ROOT=/path/to/a/working/copy      # defaults to $HOME/bench
bash slurm/make_grid.sh                        # the injection grid, 180 cells, from their seeds
bash slurm/make_foreign.sh                     # error kind 6, nine cells of foreign sequences
bash slurm/make_clade.sh                       # error kind 3, nine whole-taxon relabellings
bash slurm/make_simulation.sh                  # 2.1's control, 37 cells on a simulated reference
slurm/submit.sh slurm/baseline.sh              # both tools on the un-injected database, timed
slurm/submit.sh slurm/grid_fork.sh             # one condition over the grid
bin/analyses.sh                                # rebuild every table in results/ from the runs
python3 -m unittest discover -s tests          # the analysis layer's tests
```

The four generators come first because the cells they make are not in the repository: they are the
base taxonomy with a few hundred labels rewritten, or the same alignment with donors added, and
rebuilding every one from its seed takes a couple of minutes and needs neither cluster nor container
nor network. All four are listed because running only the first is not enough and does not fail
gracefully: `bin/analyses.sh` reaches its truth checks and exits 1 on nine foreign datasets whose
`.fasta` was never built, after doing twenty-three steps of work. [`data/README.md`](data/README.md) says what is kept
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
modules/local/                         sativa, sativaepang, collectrun, alignssu, and the four
                                       staged stages: reference, lootasks, looplace, looscore
bin/                                   preparation, injection, scoring, analysis; analyses.sh runs them all
slurm/                                 one script per measurement, plus prelude.sh and submit.sh
tests/                                 unittest over the scripts that turn runs into numbers
assets/datasets.yml                    every source with version, DOI, URL, date and sha256
data/                                  the base datasets and the injected ground truth; see data/README.md
results/                               the measured runs and the tables built from them
results/figure1.svg                    the Application Note's figure, and figure1_values.tsv behind it
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
than confirming that it works. Each finding says how it was found and how the fix was checked, grouped
by whether it had produced a wrong number, was latent, or was introduced by the review itself. It also
lists what was checked and found correct, and what it does not cover.

No count is quoted here. There were three in this paragraph -- findings, those that moved a number, and
defects the review introduced -- and all three had drifted, which is the defect the report records most
often. `bin/review_coverage.py` prints which files it never names, and
`grep -cE '^\*\*[0-9]+\. ' REVIEW.md` counts the findings. The pattern matters: a looser one counts
`**19.2 MB**` as a finding and a stricter one misses every finding whose first word is in backticks.

