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

**It is already published.** `github.com/Aaramis/sativa-epang` is public, its default branch is
`epa-ng`, it carries `CHANGES-epa-ng.md` at the root and it is GPL-3.0 — checked by fetching the page,
because this file used to give instructions for publishing it as though that were still to do. So
Protocol.md's Availability line holds as written. That matters more than it looks: the copy of the
modified code that used to live in this repository has been removed, so the fork's branch is the only
record of what differs from upstream.

There is **no checkout of it on this machine**, which is the other half of why the instructions below
were stale. Anything that needs the source itself has to start by cloning it.

**What the branch actually holds**, from a clone rather than from memory. `epa-ng` is **27 commits
ahead of `master` and none behind**, and those commits are the work: the EPA-ng placement in both
passes, the staged leave-one-out, `-folds` taking a subset, the `OriginalLabelExclusion` column, and
the releases 0.10.0 to 0.10.2. This file used to say "one commit on top of v0.9.3 (`68284c2`)", which
was wrong three ways: there is no tag `v0.9.3` — the tags are `v0.9.3.1` to `v0.9.3.6` and `v0.10.0` to
`v0.10.2` — and `68284c2` is an *upstream* commit, "fix gcc version check". **`v0.10.2` exists as a
tag**, so the exact source of the version this benchmark ran is identifiable.

The modification a reviewer should read is **22 files and 2 239 lines**, led by `epac/epang_l1o.py`
(1 150), `sativa.py` (303) and `CHANGES-epa-ng.md` (258) — larger than the "two hunks and a new file"
this section used to describe, which was an early state.

**And 80 % of the diff is not the modification.** Twelve files under `tmp/` — SATIVA's own scratch
directory, with alignments, trees and 2 400-line FASTAs — are committed on the branch: **8 809 lines**
against the modification's 2 239. A reviewer following Protocol.md's Availability line meets them first.
Removing them from the branch would make the diff say what the work is; that is a change to a separate
repository and is not made from here.

## Repository description and topics

The public description names only what the first benchmark measured. What this one adds: distribution
across jobs, which upstream cannot do at any price, and what the fork's `OriginalLabelExclusion` column
is worth — it explains a third of the calls and does not rank them.

Description: *Does replacing SATIVA's placement engine with EPA-ng change its answers? Speed,
agreement, a ground-truth mislabel grid, distribution across jobs, and what the new confidence column
is worth.*

Topics: `sativa`, `epa-ng`, `phylogenetic-placement`, `taxonomy`, `benchmark`, `reference-database`,
`nextflow`.
