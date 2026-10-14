# Adding your own method

MislabelBench scores any tool that flags sequences whose taxonomic label looks wrong. A method needs
no Nextflow module to be scored. It needs to read one alignment and one taxonomy and write one table.

## The contract

**Input.** One dataset cell, for example `data/injected/inj_class_r0.01_k1_s1/`:

| file | content |
|---|---|
| `<cell>.fasta` | the alignment, 1478 columns, Infernal against Rfam RF01959 |
| `<cell>.tax` | `SeqID<TAB>d__...;p__...;c__...;o__...;f__...;g__...;s__...`, with the injected errors in it |
| `<cell>.truth.json` | what was injected, for the scorer only. A method must not read it |

A cell with injected errors is a copy of the base taxonomy with some labels changed. The kinds of error
and where each lives are listed in the [README](../README.md#the-seven-error-types).

**Output.** A tab-separated file in SATIVA's `.mis` layout. Lines starting with `;` are a header and
are ignored. One line per flagged sequence, eight columns:

```
SeqID  MislabeledLevel  OriginalLabel  ProposedLabel  Confidence  OriginalTaxonomyPath  ProposedTaxonomyPath  PerRankConfidence
```

Only the first, fifth and the two paths matter for the numbers. `Confidence` is a score in [0, 1]
where larger means more sure the label is wrong. A method without such a score writes 1.0. A ninth
column, `OriginalLabelExclusion`, is read when present.

## Score it

```bash
python3 bin/analysis/score_injection.py \
  --truth data/injected/inj_class_r0.01_k1_s1/inj_class_r0.01_k1_s1.truth.json \
  --mis   my_method.mis \
  --baseline-mis my_method_on_unmodified_database.mis \
  --out   score.json
```

`score.json` gives recall of the injected errors at each confidence threshold, and the number of other
sequences flagged. Those other flags are not called false positives, because a real database is not
guaranteed clean. They are counted against the flags the same method raises on the unmodified
database (`--baseline-mis`), which is why you also run the method once on `data/gtdb/gtdb_arc2k.fasta`
with `data/gtdb/gtdb_arc2k.tax`.

To score the 180 cells with the aggregation the article uses, put each cell's `.mis` in
`results/<experiment>/runs/<cell>__<condition>__rep1/<cell>__<condition>__rep1.mis` and run
`bin/analysis/aggregate_grid.py`, or follow how `slurm/detection/grid_fork.sh` does it.

## Run it inside the workflow

For timing and for a reproducible container, add a process next to `modules/local/sativa/main.nf`:

1. Copy `modules/local/sativa/main.nf` to `modules/local/<yourtool>/main.nf`. Keep the outputs
   `mis`, `timing`, `inputs`, `log` and the `_timeit.py` wrapper, which records wall time and peak
   memory. Pin your tool by container tag.
2. In `main.nf`, include the module and add a `branch` on a new `impl` value next to `upstream` and `fork`.
3. In `nextflow.config`, add a line to `params.condition_specs`, for example
   `'mytool_T8': [impl: 'mytool', threads: 8]`.
4. Check the plumbing without running the tool:
   `nextflow run . -stub-run -profile stub_test --datasets_json data/gtdb/datasets2k.json --datasets gtdb_arc2k --conditions mytool_T8`.

Timing runs follow the rules in [cluster.md](cluster.md): one CPU model, nothing else on the node.

## Please report

Run on the 180 injected cells and on the control with a simulated reference
(`data/grove_sim`), and report recall at a stated threshold together with the extra
flags on the unmodified database. Recall alone rewards a tool that flags everything.
