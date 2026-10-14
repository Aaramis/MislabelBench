# Running SATIVA-epang

The benchmark runs `sativa-epang` exactly as shown here. The commands come from `modules/local/*/main.nf`.
`ext.args`, the same for every condition, is `-m ultrafast -C 0.4 -x BAC -p 42 -S`.

## In one process

This is upstream SATIVA's interface, with environment variables to choose the engine.

```bash
export SATIVA_L1O_ENGINE=epang      # or raxml, to drive the same code with the old engine
export SATIVA_EPANG_FOLDS=25        # sequences are removed and placed 25 at a time
export SATIVA_EPANG_FOLD_ORDER=tree # optional, the default is 'name'
sativa-epang -s aln.fasta -t taxonomy.tax -T 8 -n myrun -m ultrafast -C 0.4 -x BAC -p 42 -S
```

`SATIVA_EPANG_FOLDS` is capped at the number of leaves. Any value above the number of sequences gives
one sequence per fold, which is the strict leave-one-out and what the `epang_T8_Kexact` condition uses.
`SATIVA_EPANG_FOLD_ORDER=tree` deals the folds by tree traversal instead of by name.

## In four stages

The same run split in four processes, which lets the placement cross machines. The first three stages
write what the next one reads.

```bash
sativa-epang -s aln.fasta -t taxonomy.tax -T 8 -n run -o . <args> -stage reference
sativa-epang -r run.refjson -T 8 -n run -o . -stage loo-tasks
sativa-epang -stage loo-place -taskdir $PWD/run.l1o_tasks -T 8 -folds 0/4   # and 1/4, 2/4, 3/4
sativa-epang -r run.refjson -T 8 -n run -o . <args> -stage loo-score -taskdir $PWD/run.l1o_tasks
```

Only `loo-place` divides. `-folds i/N` takes every N-th fold of the list in the task directory's
`manifest.json`, so the N invocations partition the folds and can run anywhere that reads the directory.
The reference build does not divide, which bounds the gain. [distribution.md](distribution.md) gives the
costs and where distributing stops paying.

## Output

The output is upstream's `.mis` with one more column, `OriginalLabelExclusion`. It is one minus the
placement weight that fell inside the declared taxon. `Confidence` says how much evidence supports the
proposed label, and this column says how much evidence is against the declared one. The supplement of
the paper discusses when it helps.
