#!/usr/bin/env python3
"""Build the Application Note's one multi-panel figure from the committed records.

Part 1 of Protocol.md allows the main text 2000 words plus one figure, and orders what it
carries: "Speed and scaling first; the exclusion column second; accuracy against injected
ground truth as the control that bounds both." The four panels are that sentence, with 2.8's
requirement that scaling be reported per stage rather than as one total.

  A  the method, drawn: four stages and the two lines where the versions differ
  B  wall clock against reference size, both tools, log-log
  C  recall against k, both tools
  D  recall against the share of surviving relatives that carry the wrong label, both tools

Each panel carries one sentence of the Evaluation section and no panel carries none. Three earlier
panels were dropped against that rule: the per-stage scaling bars, because the main text makes no
scaling claim; the exclusion column's filtering curves, because that whole analysis moved to the
supplement; and the engine-versus-fold-scheme decomposition, which is the argument a developer wants
and a user does not, and which one sentence and a supplementary table carry. All three are still in
results/ and can come back if the text changes. The schematic took the place of the third: two of
three published figures looked at in this journal draw the method before showing a curve.

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
W, H = 760, 446
# Plot areas: two rows of two, left margin wide enough for a rotated y label.
# One schematic across the top and three data panels in a row beneath it, which is the layout of
# the FastDup figure in this journal and, less strictly, of SigProfilerAssignment's: the method is
# drawn before any curve is shown. Three panels across a double column is tight, and FastDup does it.
PANELS = {"B": (58, 212), "C": (318, 212), "D": (578, 212)}
PW, PH = 170, 150
SCHEMATIC = (24, 34, 736, 130)   # x, y, width, height
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


def box(x, y, w, h, fill, lines, size=8, stroke="#888"):
    o = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" '
         f'stroke="{stroke}" stroke-width="0.8"/>']
    top = y + h / 2 - (len(lines) - 1) * (size + 3) / 2 + size / 3
    for i, (text, weight, colour) in enumerate(lines):
        o.append(txt(x + w / 2, top + i * (size + 3), text, size=size, weight=weight, fill=colour))
    return o


def arrow(x1, y1, x2, y2, colour="#444", dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return [f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{colour}" '
            f'stroke-width="1.1"{d} marker-end="url(#head)"/>']


def schematic():
    """What the tool does, drawn before any result is shown.

    Four stages left to right, and in the placement stage the two lines that are the whole subject
    of the note, in the figure's own colour code: SATIVA's loop in the comparator's red dash and
    sativa-epang's in black. The return arrow is FastDup's device for 'loop until every block is
    processed'. Nothing here is measured; it is the reader's map for the three panels below.
    """
    X, Y, Wd, Hd = SCHEMATIC
    o = ['<defs><marker id="head" markerWidth="7" markerHeight="7" refX="6" refY="3.5" '
         'orient="auto"><path d="M0,0 L7,3.5 L0,7 z" fill="#444"/></marker></defs>',
         txt(X - 2, Y - 10, "(a)", size=12, anchor="start", weight="bold")]
    bw, bh, gap = 150, 58, 36
    y = Y + 22
    xs = [X + 10 + i * (bw + gap) for i in range(4)]
    o += box(xs[0], y, bw, bh, "#f0f0f0",
             [("Alignment", "bold", "#000"), ("and declared taxonomy", "normal", "#000")])
    o += box(xs[1], y, bw, bh, "#e3eef7",
             [("Reference tree", "bold", "#000"), ("RAxML-NG, constrained", "normal", "#000"),
              ("by the taxonomy", "normal", "#000")])
    o += box(xs[2], y - 10, bw, bh + 20, "#e8f3e8",
             [("Leave-one-out placement", "bold", "#000"),
              ("SATIVA: one sequence, RAxML-EPA", "normal", UP),
              ("sativa-epang: K sequences, EPA-ng", "normal", FORK)])
    o += box(xs[3], y, bw, bh, "#fbeedf",
             [("Flag mislabels", "bold", "#000"), ("placement against the", "normal", "#000"),
              ("declared label, with a confidence", "normal", "#000")])
    for i in range(3):
        o += arrow(xs[i] + bw + 3, y + bh / 2, xs[i + 1] - 4, y + bh / 2)
    # The loop: from the flagging stage back to the placement stage, below the boxes.
    ly = y + bh + 26
    o.append(f'<path d="M{xs[3] + bw / 2:.1f},{y + bh + 2} V{ly} H{xs[2] + bw / 2:.1f} '
             f'V{y + bh + 12}" fill="none" stroke="#444" stroke-width="1.1" '
             f'marker-end="url(#head)"/>')
    o.append(txt((xs[2] + xs[3] + bw) / 2, ly + 11, "until every sequence has been placed",
                 size=8, fill="#444"))
    # The cost difference, n placements against n/K, is said in the caption: beside the arrow it
    # collided with it, and the two lines in the box already carry the idea.
    CAPTION.append("(a) The method, and where the two versions differ: n placements against n/K.")
    return o


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

    o += schematic()

    # B. Speed, which is the claim the paper leads with.
    grad = read_gradient(root / "results/resource_usage.txt")
    ax = Ax("B", (350, 8000), (5, 4000), xlog=True, ylog=True)
    o += frame(ax, "B", "wall clock, both tools", "Reference Sequences", "Runtime (seconds)",
               [400, 1000, 2000, 4000, 7000], [10, 100, 1000],
               xfmt=lambda v: f"{v:,}".replace(",", " "))
    # Labelled rules at round durations, so a log axis can be read without counting decades. The
    # same device carries the performance panel of the SigProfilerAssignment figure in this journal.
    for secs, label in ((60, "1 min"), (600, "10 min")):
        yy = ax.py(secs)
        o.append(f'<line x1="{ax.x0}" y1="{yy:.1f}" x2="{ax.x0 + PW}" y2="{yy:.1f}" '
                 f'stroke="#c8c8c8" stroke-width="0.7" stroke-dasharray="3 2"/>')
        o.append(txt(ax.x0 + PW - 4, yy - 4, label, size=7, anchor="end", fill="#888"))
    o += series(ax, [(r["n"], r["upstream"]) for r in grad], UP, dash=COMPARATOR_DASH)
    o += series(ax, [(r["n"], r["fork"]) for r in grad], FORK)
    # The speedup is the point of the panel and is not readable off two log curves.
    for r in grad:
        o.append(txt(ax.px(r["n"]), ax.py(r["fork"]) - 8, f"{r['wall_speedup']:.0f}x",
                     size=7, fill=FORK))
        vals += [f"B\tupstream\t{r['n']}\t{r['upstream']}", f"B\tfork\t{r['n']}\t{r['fork']}",
                 f"B\twall_speedup\t{r['n']}\t{r['wall_speedup']}"]

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
    o += legend(ax.x0 + PW - 46, ax.y0 + 12, [("5 %", "#555", None), ("1 %", "#555", "4 2")], size=8)

    # D. The law the whole detection result rests on: what predicts detection is not k and not the
    # fold count but how much of a sequence's surviving neighbourhood already carries the wrong
    # label. Both tools obey it, which is why both curves are drawn and why half of every injected
    # mislabel is found by neither.
    ax = Ax("D", (0, 1), (0, 1))
    o += frame(ax, "D", "recall against the share of surviving relatives carrying the wrong label",
               "Relatives Carrying the Wrong Label", "Recall",
               [0, 0.25, 0.5, 0.75, 1], [0, 0.25, 0.5, 0.75, 1],
               xfmt=lambda v: f"{v:g}", yfmt=lambda v: f"{v:g}")
    for cond, colour, dash in (("epang_T8_K25", FORK, None),
                               ("upstream_raxml_T8", UP, COMPARATOR_DASH)):
        bands = json.loads(Path(root, f"results/detection_law_{cond}.json").read_text())["by_ratio"]
        pts = [((b["low"] + b["high"]) / 2, b["recall"]) for b in bands]
        o += series(ax, pts, colour, dash=dash)
        vals += [f"D\t{cond}\t{x}\t{y}" for x, y in pts]

    # One legend for the whole figure, centred under the panels.
    o += legend(W / 2 - 110, H - 16, [("sativa-epang", FORK, None)], size=9)
    o += legend(W / 2 + 20, H - 16, [("SATIVA", UP, COMPARATOR_DASH)], size=9)

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
