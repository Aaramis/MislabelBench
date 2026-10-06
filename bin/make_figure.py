#!/usr/bin/env python3
"""Build the Application Note's one multi-panel figure from the committed records.

Part 1 of Protocol.md allows the main text 2000 words plus one figure, and orders what it
carries: "Speed and scaling first; the exclusion column second; accuracy against injected
ground truth as the control that bounds both." The four panels are that sentence, with 2.8's
requirement that scaling be reported per stage rather than as one total.

  A  wall clock against reference size, both tools, log-log
  B  recall against the share of surviving relatives that carry the wrong label, both tools
  C  recall against k, both tools
  D  what the engine contributes and what the fold scheme contributes, against k

Each panel carries one sentence of the Evaluation section and no panel carries none. Two earlier
panels were dropped against that rule: the per-stage scaling bars, because the main text makes no
scaling claim, and the exclusion column's filtering curves, because that whole analysis moved to the
supplement. Both are still in results/ and can come back if the text changes.

Written as SVG by hand rather than with a plotting library, which is a reproducibility
choice and not an aesthetic one. Every other script in bin/ runs on the standard library
alone, so a reader clones the repository and rebuilds all of results/ with no environment to
install; one import of matplotlib would end that. And a library's output is not stable across
its own versions -- fonts, hinting and layout all move -- so a figure built that way could
never be checked byte for byte the way every other record here is. SVG is text: it is
diffable, it is identical on any machine with any python3, and it carries no timestamp.

Numbers are never recomputed where a committed record already holds them: panel A reads
results/resource_usage.txt, the record resource_usage.py writes, so the figure cannot
disagree with the table. Panels B, C and D read JSON records. Everything plotted is also
written to --values as a table, so a change in any upstream record shows up as a diff there
and not only as a change of ink, and the panel descriptions go to a caption file beside the SVG
rather than onto the panels, which is what this journal's own figures do.
"""

import argparse
import json
import math
import statistics as st
from pathlib import Path

# The extra 34 points at the bottom are the shared legend's strip. Three Bioinformatics figures were
# looked at to settle this: two of the three carry one legend for the whole figure, at the bottom or
# at the right, rather than repeating a box in every panel, which is what this did and what cost each
# panel a corner of its plotting area.
W, H = 760, 574
# Plot areas: two rows of two, left margin wide enough for a rotated y label.
PANELS = {"A": (62, 40), "B": (452, 40), "C": (62, 320), "D": (452, 320)}
PW, PH = 240, 180
# Black for the tool under test, colour for the comparator, taken from the script that produced
# this journal's gappa figure (lczech/genesis-gappa-paper, plot.py): their own library is plotted
# with colour "k" and a solid line, every competitor with a cycle colour and a (5,2) dash, and their
# own column is moved to the front of the legend. It survives greyscale printing, which two coloured
# lines of equal weight do not.
FORK, UP = "#000000", "#c1462c"
COMPARATOR_DASH = "5 2"
STAGE = {"reference_sec": "#b8c6d1", "loo_tasks_sec": "#8aa3b5",
         "loo_place_sec": "#1b6ca8", "loo_score_sec": "#4a5f6d"}


class Ax:
    """One panel's coordinate transform. Log axes take the log here, once."""

    def __init__(self, key, xlim, ylim, xlog=False, ylog=False):
        self.x0, self.y0 = PANELS[key]
        self.xlog, self.ylog = xlog, ylog
        self.xa, self.xb = [self._fx(v) for v in xlim]
        self.ya, self.yb = [self._fy(v) for v in ylim]

    def _fx(self, v):
        return math.log10(v) if self.xlog else v

    def _fy(self, v):
        return math.log10(v) if self.ylog else v

    def px(self, v):
        return self.x0 + (self._fx(v) - self.xa) / (self.xb - self.xa) * PW

    def py(self, v):
        return self.y0 + PH - (self._fy(v) - self.ya) / (self.yb - self.ya) * PH


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, size=9, anchor="middle", weight="normal", rot=None, fill="#000"):
    t = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot is not None else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}"{t}>{esc(s)}</text>')


# The panel titles and the sentences that used to be printed inside the panels. Three figures from
# the same lab in this journal were downloaded and looked at -- gappa figure 1, and figures 3 and 4
# of the multilevel placement paper -- and none of them writes a title or an explanatory sentence
# inside a panel. The caption carries all of it, and it is long. So the text is collected here and
# written beside the figure as a draft caption instead of being drawn on top of the data.
CAPTION = []


def frame(ax, key, title, xlabel, ylabel, xticks, yticks, xfmt=str, yfmt=str):
    CAPTION.append(f"({key.lower()}) {title}.")
    o = [f'<rect x="{ax.x0}" y="{ax.y0}" width="{PW}" height="{PH}" fill="none" '
         f'stroke="#444" stroke-width="0.8"/>',
         txt(ax.x0 - 44, ax.y0 - 16, f"({key.lower()})", size=12, anchor="start", weight="bold")]
    o += [txt(ax.x0 + PW / 2, ax.y0 + PH + 32, xlabel, size=10),
          txt(ax.x0 - 40, ax.y0 + PH / 2, ylabel, size=10, rot=-90)]
    for v in xticks:
        x = ax.px(v)
        o.append(f'<line x1="{x:.1f}" y1="{ax.y0 + PH}" x2="{x:.1f}" y2="{ax.y0 + PH + 4}" '
                 f'stroke="#444" stroke-width="0.8"/>')
        o.append(txt(x, ax.y0 + PH + 15, xfmt(v), size=8))
    for v in yticks:
        y = ax.py(v)
        # Horizontal only. Their script calls ax.yaxis.grid(True) and never touches the x grid, and
        # the published figure has no vertical rules; a first pass here drew both.
        o.append(f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0 + PW}" y2="{y:.1f}" '
                 f'stroke="#e8e8e8" stroke-width="0.6"/>')
        o.append(f'<line x1="{ax.x0 - 4}" y1="{y:.1f}" x2="{ax.x0}" y2="{y:.1f}" '
                 f'stroke="#444" stroke-width="0.8"/>')
        o.append(txt(ax.x0 - 7, y + 3, yfmt(v), size=8, anchor="end"))
    return o


def series(ax, pts, colour, dash=None, marker="o", line=True):
    # line=False for a series whose points are separate measurements rather than one trajectory.
    # The decomposition has two cells at k=2, and joining them drew a vertical spike that reads as
    # a sudden change where there are only two seeds of the same condition.
    o = []
    if line:
        d = " ".join(f"{'M' if i == 0 else 'L'}{ax.px(x):.1f},{ax.py(y):.1f}"
                     for i, (x, y) in enumerate(pts))
        st = f' stroke-dasharray="{dash}"' if dash else ""
        o = [f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.6"{st}/>']
    for x, y in pts:
        if marker == "o":
            o.append(f'<circle cx="{ax.px(x):.1f}" cy="{ax.py(y):.1f}" r="2.6" '
                     f'fill="{colour}"/>')
    return o


def legend(x, y, entries, size=9):
    o = []
    for i, (label, colour, dash) in enumerate(entries):
        yy = y + i * 13
        s = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<line x1="{x}" y1="{yy}" x2="{x + 18}" y2="{yy}" stroke="{colour}" '
                 f'stroke-width="1.6"{s}/>')
        o.append(txt(x + 23, yy + 3, label, size=size, anchor="start"))
    return o


def read_gradient(path):
    """The size-gradient block of resource_usage.txt: sequences, fork, upstream, speedups."""
    lines = Path(path).read_text().splitlines()
    i = next(i for i, l in enumerate(lines) if l.startswith("size gradient"))
    rows = []
    for l in lines[i + 2:]:
        if not l.strip():
            break
        f = l.split()
        rows.append({"n": int(f[0]), "fork": float(f[1]), "upstream": float(f[2]),
                     "wall_speedup": float(f[3]), "cpu_speedup": float(f[4])})
    # Five sizes were run. A silent change to the table's layout would otherwise plot a
    # shorter curve rather than fail, which is the failure mode this repository keeps finding.
    if len(rows) != 5:
        raise SystemExit(f"{path}: expected 5 size-gradient rows, parsed {len(rows)}")
    return rows


def read_stages(root):
    """Per-stage seconds at each node count, averaged over replicates, on gtdb_arc1200."""
    by_n = {}
    for p in sorted(Path(root, "results/scaling").glob("*/timing.json")):
        d = json.loads(p.read_text())
        if d.get("dataset") != "gtdb_arc1200" or d.get("cores_requested_per_node") != 140:
            continue
        by_n.setdefault(d["nodes"], []).append(d)
    out = []
    for n in sorted(by_n):
        reps = by_n[n]
        out.append({"nodes": n, "reps": len(reps),
                    **{k: st.mean(r[k] for r in reps) for k in STAGE}})
    if {r["nodes"] for r in out} != {1, 2, 4}:
        raise SystemExit(f"scaling: expected node counts 1, 2 and 4, found "
                         f"{sorted(r['nodes'] for r in out)}")
    return out


def read_recall(root, condition, rate, metric="by_confidence", threshold=0.0):
    """Mean recall over the six distances, per k.

    The statistic is named here and in the axis label because a different one gives a
    different answer: pooling detections over sequences rather than averaging the six cell
    means would weight distances by how many sequences each injection happened to touch.
    At rate 0.05 the cells hold the same number of injections by construction, so the two
    agree closely, but the figure says which it is.
    """
    d = json.loads(Path(root, f"results/grid_summary_{condition}.json").read_text())
    by_k = {}
    for r in d["rows"]:
        if r["metric"] == metric and r["threshold"] == threshold and r["rate"] == rate:
            by_k.setdefault(r["k"], []).append(r["recall_mean"])
    out = {}
    for k, vals in by_k.items():
        if len(vals) != 6:
            raise SystemExit(f"{condition}: k={k} rate={rate} has {len(vals)} distances, not 6")
        out[k] = st.mean(vals)
    return dict(sorted(out.items()))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--out", required=True, help="the SVG")
    p.add_argument("--values", required=True, help="every number plotted, as a table")
    args = p.parse_args()
    root = Path(args.root)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="Helvetica,Arial,sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#fff"/>']
    vals = ["panel\tseries\tx\ty"]

    # A. Speed, which is the claim the paper leads with.
    grad = read_gradient(root / "results/resource_usage.txt")
    ax = Ax("A", (350, 8000), (5, 4000), xlog=True, ylog=True)
    o += frame(ax, "A", "wall clock, both tools", "Reference Sequences", "Runtime (seconds)",
               [400, 1000, 2000, 4000, 7000], [10, 100, 1000],
               xfmt=lambda v: f"{v:,}".replace(",", " "))
    o += series(ax, [(r["n"], r["upstream"]) for r in grad], UP, dash=COMPARATOR_DASH)
    o += series(ax, [(r["n"], r["fork"]) for r in grad], FORK)
    # Labelled rules at round durations, so a log axis can be read without counting decades. The
    # same device carries the performance panel of the SigProfilerAssignment figure in this journal.
    for secs, label in ((60, "1 min"), (600, "10 min")):
        y = ax.py(secs)
        o.append(f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0 + PW}" y2="{y:.1f}" '
                 f'stroke="#c8c8c8" stroke-width="0.7" stroke-dasharray="3 2"/>')
        o.append(txt(ax.x0 + PW - 4, y - 4, label, size=7, anchor="end", fill="#888"))
    # The speedup is the point of the panel and is not readable off two log curves.
    for r in grad:
        o.append(txt(ax.px(r["n"]), ax.py(r["fork"]) - 9, f"{r['wall_speedup']:.0f}x",
                     size=7, fill=FORK))
    for r in grad:
        vals += [f"A\tupstream\t{r['n']}\t{r['upstream']}", f"A\tfork\t{r['n']}\t{r['fork']}",
                 f"A\twall_speedup\t{r['n']}\t{r['wall_speedup']}"]

    # B. The law the whole detection result rests on: what predicts detection is not k and not the
    # fold count but how much of a sequence's surviving neighbourhood already carries the wrong
    # label. Both tools obey it, which is why both curves are drawn.
    ax = Ax("B", (0, 1), (0, 1))
    o += frame(ax, "B", "recall against the share of surviving relatives carrying the wrong label",
               "Relatives Carrying the Wrong Label", "Recall",
               [0, 0.25, 0.5, 0.75, 1], [0, 0.25, 0.5, 0.75, 1],
               xfmt=lambda v: f"{v:g}", yfmt=lambda v: f"{v:g}")
    for cond, colour, dash in (("epang_T8_K25", FORK, None),
                               ("upstream_raxml_T8", UP, COMPARATOR_DASH)):
        bands = json.loads(Path(root, f"results/detection_law_{cond}.json").read_text())["by_ratio"]
        pts = [((b["low"] + b["high"]) / 2, b["recall"]) for b in bands]
        o += series(ax, pts, colour, dash=dash)
        vals += [f"B\t{cond}\t{x}\t{y}" for x, y in pts]

    # C. The comparison itself. Both ends are flat for opposite reasons, a ceiling at k=1 where
    # the rest of the group keeps the right label and a floor at k=10 where it does not, so the
    # fork's advantage lives in between and the panel has to show the whole range to say so.
    ax = Ax("C", (0.8, 10.5), (0, 1), xlog=True)
    o += frame(ax, "C", "recall against the number of sequences sharing the wrong label",
               "Sequences Sharing the Wrong Label", "Recall",
               [1, 2, 3, 5, 10], [0, 0.25, 0.5, 0.75, 1],
               xfmt=lambda v: f"{v:g}", yfmt=lambda v: f"{v:g}")
    for cond, colour in (("epang_T8_K25", FORK), ("upstream_raxml_T8", UP)):
        for rate, dash in ((0.05, None), (0.01, "4 2")):
            r = read_recall(root, cond, rate)
            o += series(ax, sorted(r.items()), colour, dash=dash)
            vals += [f"C\t{cond}_r{rate}\t{k}\t{v:.4f}" for k, v in sorted(r.items())]
    # Colour is the tool and is in the shared legend, so this one only has to say what the dash is.
    o += legend(ax.x0 + PW - 58, ax.y0 + 14,
                [("5 %", "#555", None), ("1 %", "#555", "4 2")], size=8)

    # D. Where the advantage comes from. Running EPA-ng with one sequence per fold is upstream's own
    # protocol with the other engine, so the gap it leaves is the engine alone and what remains is
    # the fold scheme. Both seeds at k=2 are plotted rather than averaged: two cells are two
    # measurements and a mean of two would look like a point estimate.
    cells = json.loads(Path(root, "results/kexact_decomposition.json").read_text())["cells"]
    cells = [c for c in cells if c.get("engine_at_0") is not None]
    ax = Ax("D", (0.8, 10.5), (-0.05, 0.32), xlog=True)
    o += frame(ax, "D", "what the engine contributes and what the fold scheme contributes",
               "Sequences Sharing the Wrong Label", "Difference in Recall",
               [1, 2, 3, 5, 10], [0, 0.1, 0.2, 0.3],
               xfmt=lambda v: f"{v:g}", yfmt=lambda v: f"{v:g}")
    o.append(f'<line x1="{ax.x0}" y1="{ax.py(0):.1f}" x2="{ax.x0 + PW}" y2="{ax.py(0):.1f}" '
             f'stroke="#999" stroke-width="0.7"/>')
    for field, colour, dash, label in (("engine_at_0", FORK, None, "engine"),
                                       ("folds_at_0", UP, COMPARATOR_DASH, "fold scheme")):
        pts = sorted((c["k"], c[field]) for c in cells if c.get(field) is not None)
        o += series(ax, pts, colour, dash=dash, line=False)
        # The eye still needs the shape, so the mean per k is drawn through the points.
        means = sorted({k: sum(v for kk, v in pts if kk == k) / sum(1 for kk, _ in pts if kk == k)
                        for k, _ in pts}.items())
        o += series(ax, means, colour, dash=dash, marker=None)
        vals += [f"D\t{field}\t{k}\t{v}" for k, v in pts]
    # Labelled on the curves. A box here would sit on the only part of the panel that carries data.
    o.append(txt(ax.px(3.4), ax.py(0.20), "engine", size=8, anchor="start", fill=FORK))
    o.append(txt(ax.px(3.4), ax.py(0.035), "fold scheme", size=8, anchor="start", fill=UP))

    # One legend for the whole figure, centred under the panels.
    o += legend(W / 2 - 110, H - 20, [("sativa-epang", FORK, None)], size=9)
    o += legend(W / 2 + 20, H - 20, [("SATIVA", UP, COMPARATOR_DASH)], size=9)

    o.append("</svg>")
    Path(args.out).write_text("\n".join(o) + "\n")
    Path(args.values).write_text("\n".join(vals) + "\n")
    # The caption beside the figure, because the text it holds used to be drawn on the panels and
    # the journal's own figures put it in the caption instead. It is a draft: it names each panel
    # and carries the one sentence panel (c) cannot do without, and the prose around it is written
    # by hand in the manuscript.
    Path(args.out).with_name(Path(args.out).stem + "_caption.txt").write_text(
        " ".join(CAPTION) + "\n")
    print(f"{args.out}: 4 panels, {len(vals) - 1} values, from committed records only")


if __name__ == "__main__":
    main()
