# This is not the code the benchmark runs

This directory is the modified SATIVA that **version 1** of this benchmark measured, kept for the
provenance of the v1 numbers that `RESULTS.md` reports. See `PROVENANCE.md` for the modifications
and the licence obligation they carry.

The Nextflow harness on this branch installs `bioconda::sativa-epang 0.10.2`
(`py314hab16a5f_0`) in a pinned container and never touches this copy. The two differ in code, not
only in version. One difference matters enough to name, because it was mistaken for the other
once already:

| | this copy | released 0.10.2 |
|---|---|---|
| fold assignment | `run_epang_l1o` in `epac/epang_l1o.py`, `sorted(leaves)` then `ordered[i::K]` | `_l1o_folds` in the same file, with `SATIVA_EPANG_FOLD_ORDER` selecting name or tree order |

So read the container, not this directory, when the question is what produced a result:

```
IMG=$(ls ~/.singularity_cache/*sativa-epang*0.10.2*)
singularity exec "$IMG" sed -n '710,732p' /usr/local/share/sativa-epang-0.10.2-0/epac/epang_l1o.py
```

This directory is scheduled for removal once `README.md` is rewritten for the Nextflow harness;
git history keeps it either way.
