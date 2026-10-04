# Publishing this folder

> **Version 1 is already public, and this file used to open by saying nothing was.** `origin` is
> `https://github.com/Aaramis/sativa-epang-benchmark`, `origin/main` holds 8 commits of the first
> benchmark, and GitHub's default branch is `main`. So what is public is the version that has since
> been removed from this branch.
>
> **One published claim is refuted and the refutation is not public.** `RESULTS.md` on `main` reports
> that unmodified SATIVA finds 28 of 33 injected mislabels and the EPA-ng version 33 of 33, and
> explains the gap by shared wrong labels that "a strict leave-one-out cannot see and a fold can". The
> 180-cell grid with three seeds does not bear that out: recall falls with the number of carriers for
> both tools alike, 0.94 at *k*=1 to 0.13 at *k*=10, and the fold scheme is worth 0.035 and only at
> *k*=10. README on this branch says so; `main` does not, so a reader of the public repository sees the
> refuted claim and no correction beside it.
>
> **This cannot be fixed from here.** The fix is a push, and nothing in this repository is pushed
> without explicit agreement. `nextflow` contains all of `origin/main`'s history, so moving `main` to it
> is a fast-forward and not a rewrite — and it would replace the refuted report with the work that
> refuted it, since version 1 is no longer in the tree to contradict.

## What is where

| | |
|---|---|
| `origin/main`, public | the first benchmark: ITS measurements, `scripts/`, the vendored `sativa_epang/`, `RESULTS.md` |
| `nextflow`, local only | the Nextflow harness, the GTDB grid, `REVIEW.md`, and none of the above |

## What removing version 1 settled

Three of the four questions this file used to ask were about version 1, and they are closed because
what raised them is gone.

**Sequence redistribution.** `data_ascii/` and `data_injected/` held about 5 MB of ITS sequences drawn
from the curated database, and whether they could be redistributed was open. They are removed. Every
dataset the harness now uses is public and recorded in `assets/datasets.yml` with its DOI, URL and
sha256: GTDB r226, UNITE v10.0, Rfam RF01959.

**Licence.** `LICENSE` is GPL 3, which SATIVA required because `sativa_epang/` was a modified copy of
GPL 3 code. That copy is gone and the harness vendors nothing — it calls `bioconda::sativa 0.9.3` and
`bioconda::sativa-epang 0.10.2` in pinned containers. So the obligation that chose the licence no longer
applies, and whether to keep GPL 3 anyway is now a free choice rather than a requirement. Left as it is,
since nothing forces a change and a licence is not something to alter in passing.

**Site-specific paths.** `config.local.sh`, `env/` and `scripts/10_sanitise_paths.py` are all gone.
What remains is narrower than it reads: `git grep -l '/shared/home\|/home/agardette'` matches run logs
where the tool printed its own absolute paths, plus a handful of documents and comments that quote one
to explain something. No code depends on one — checked by opening them, not by counting. So this is a
decision about whether published logs should carry the cluster's layout, not a portability bug.

## The fork

Prepared in `../sativa-epang`. Fork `amkozlov/sativa` on GitHub first, then:

```bash
cd ../sativa-epang
git remote add fork git@github.com:Aaramis/sativa-epang.git
git push fork epa-ng
```

The branch holds one commit on top of v0.9.3 (`68284c2`), so GitHub shows the whole modification as a
single readable diff: two hunks in `sativa.py`, one in `epac/config.py`, one new `epac/epang_l1o.py`,
one config line. `CHANGES-epa-ng.md` at the root of the branch explains it and links back to this
benchmark. Whether that is still accurate has not been rechecked: the fork is a separate repository and
outside the review this file sits next to. It matters more now than it did, because the copy of the
modified code that used to live here has been removed, so the fork's own branch is the only record of
what differs from upstream.

## Repository description and topics

The public description names only what the first benchmark measured. What this one adds: distribution
across jobs, which upstream cannot do at any price, and what the fork's `OriginalLabelExclusion` column
is worth — it explains a third of the calls and does not rank them.

Description: *Does replacing SATIVA's placement engine with EPA-ng change its answers? Speed,
agreement, a ground-truth mislabel grid, distribution across jobs, and what the new confidence column
is worth.*

Topics: `sativa`, `epa-ng`, `phylogenetic-placement`, `taxonomy`, `benchmark`, `reference-database`,
`nextflow`.
