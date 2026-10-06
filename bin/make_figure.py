#!/usr/bin/env python3
"""Build the Application Note's one multi-panel figure from the committed records.

Part 1 of Protocol.md allows the main text 2000 words plus one figure, and orders what it
carries: "Speed and scaling first; the exclusion column second; accuracy against injected
ground truth as the control that bounds both." The four panels are that sentence, with 2.8's
requirement that scaling be reported per stage rather than as one total.

  A  the method, drawn, one row per version, converging on the scoring they share
  B  wall clock against reference size, both tools, log-log, seconds at the points
  C  recall against the share of surviving relatives that carry the wrong label, both tools
  D  what an injected error is, drawn: k sequences of one group given a neighbour's label

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
W, H = 760, 512
# Plot areas: two rows of two, left margin wide enough for a rotated y label.
# One schematic across the top and three data panels in a row beneath it, which is the layout of
# the FastDup figure in this journal and, less strictly, of SigProfilerAssignment's: the method is
# drawn before any curve is shown. Three panels across a double column is tight, and FastDup does it.
# A two-row schematic on top, one row per version, converging on the box they share; three panels
# beneath it, FastDup's layout. Recall against k is not among them: the law panel already shows the
# fork above upstream in every band, which is the "finds more" claim. The decomposition is, because
# it carries two sentences of the text at once -- the advantage peaks at k=2 and vanishes at both
# ends, and all of it is the engine -- and without it neither had a picture.
PANELS = {"B": (58, 282), "C": (308, 282), "D": (558, 282)}
PW, PH = 190, 160
SCHEMATIC = (24, 30, 736, 170)   # x, y, width, height
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
# "(a)" is what two of the three published figures looked at use; "A", bold and bare, is the third's
# (mapache). Both occur in this journal, so the choice is a flag rather than a rule.
LABEL_STYLE = "paren-lower"


def panel_label(key):
    return key.upper() if LABEL_STYLE == "upper" else f"({key.lower()})"


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
    """What the tool does, drawn before any result is shown, one row per version.

    The two rows share their first box and their last two, and differ in the one between: SATIVA
    removes and places one sequence at a time with RAxML-EPA, sativa-epang places K at once with
    EPA-ng. Drawing the shared scoring box once, where both rows converge, is what says that only
    the engine changed. Nothing here is measured; it is the reader's map for the two panels below.
    """
    X, Y, Wd, Hd = SCHEMATIC
    o = ['<defs><marker id="head" markerWidth="7" markerHeight="7" refX="6" refY="3.5" '
         'orient="auto"><path d="M0,0 L7,3.5 L0,7 z" fill="#444"/></marker></defs>',
         txt(X - 2, Y + 2, panel_label("a"), size=12, anchor="start", weight="bold")]
    bh = 46
    y1, y2 = Y + 18, Y + 98                   # the two rows
    xref, xeng, xscore, xflag = X + 96, X + 206, X + 430, X + 592
    wref, weng, wscore, wflag = 86, 190, 128, 134
    # Row labels, in the figure's colour code.
    o.append(txt(X + 44, y1 + bh / 2 + 4, "SATIVA", size=10, weight="bold", fill=UP))
    o.append(txt(X + 44, y2 + bh / 2 + 4, "sativa-epang", size=10, weight="bold", fill=FORK))
    for y in (y1, y2):
        o += box(xref, y, wref, bh, "#f0f0f0", [("Reference tree", "normal", "#000")])
    o += box(xeng, y1, weng, bh, "#f7e9e6",
             [("Remove and place", "normal", "#000"), ("one sequence (RAxML-EPA)", "normal", UP)])
    # Stacked cards for the batches: the same box drawn three times, offset, back to front.
    for d in (8, 4, 0):
        o += box(xeng + d, y2 - d, weng, bh, "#ececec" if d else "#e8e8e8",
                 [] if d else [("Remove and place", "normal", "#000"),
                               ("K sequences at once (EPA-ng)", "normal", FORK)],
                 stroke="#999")
    ymid = (y1 + y2 + bh) / 2
    o += box(xscore, ymid - 34, wscore, 68, "#e3eef7",
             [("Same label and", "normal", "#000"), ("confidence scoring", "normal", "#000"),
              ("as SATIVA", "normal", "#000")])
    o += box(xflag, y1, wflag, bh, "#f7e9e6", [("Flagged sequences", "normal", UP)])
    o += box(xflag, y2, wflag, bh, "#e8e8e8", [("Flagged sequences", "normal", FORK)])
    for y in (y1, y2):
        o += arrow(xref + wref + 3, y + bh / 2, xeng - 4, y + bh / 2)
        # Into the shared box, then out of it to the row's own result.
        o += arrow(xeng + weng + 3, y + bh / 2, xscore - 4, ymid + (y - ymid) * 0.35)
        o += arrow(xscore + wscore + 3, ymid + (y - ymid) * 0.35, xflag - 4, y + bh / 2)
    CAPTION.append("(a) The method, one row per version. Only the placement step differs: n "
                   "placements against n/K.")
    return o


def frame(ax, key, title, xlabel, ylabel, xticks, yticks, xfmt=str, yfmt=str):
    CAPTION.append(f"({key.lower()}) {title}.")
    o = [f'<rect x="{ax.x0}" y="{ax.y0}" width="{PW}" height="{PH}" fill="none" '
         f'stroke="#444" stroke-width="0.8"/>',
         txt(ax.x0 - 44, ax.y0 - 16, panel_label(key), size=12, anchor="start", weight="bold")]
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

    # B. Speed, which is the claim the paper leads with. The seconds are written beside the points
    # and the speedup once, as a range, between the curves: five "Nx" labels said the same thing
    # five times and a reader had to read a log axis to get a single runtime.
    grad = read_gradient(root / "results/resource_usage.txt")
    ax = Ax("B", (330, 9000), (5, 6000), xlog=True, ylog=True)
    o += frame(ax, "B", "runtime against reference size, both tools", "Reference Sequences",
               "Runtime (seconds)", [400, 1000, 2000, 4000, 7000], [10, 100, 1000],
               xfmt=lambda v: f"{v:,}".replace(",", " "))
    # Each rule's label goes to whichever end of the rule no point label occupies: the hour rule
    # ends under the largest runtime's label on the right, the minute rule starts under the
    # smallest upstream runtime's on the left.
    for secs, label, at_right in ((60, "1 min", True), (600, "10 min", True), (3600, "1 h", False)):
        yy = ax.py(secs)
        o.append(f'<line x1="{ax.x0}" y1="{yy:.1f}" x2="{ax.x0 + PW}" y2="{yy:.1f}" '
                 f'stroke="#c8c8c8" stroke-width="0.7" stroke-dasharray="3 2"/>')
        o.append(txt(ax.x0 + PW - 4 if at_right else ax.x0 + 4, yy - 4, label, size=7,
                     anchor="end" if at_right else "start", fill="#888"))
    o += series(ax, [(r["n"], r["upstream"]) for r in grad], UP, dash=COMPARATOR_DASH)
    o += series(ax, [(r["n"], r["fork"]) for r in grad], FORK)
    for r in grad:
        o.append(txt(ax.px(r["n"]), ax.py(r["upstream"]) - 7, f"{r['upstream']:,.0f}".replace(",", " "),
                     size=7, fill=UP))
        o.append(txt(ax.px(r["n"]), ax.py(r["fork"]) + 14, f"{r['fork']:,.0f}".replace(",", " "),
                     size=7, fill=FORK))
        vals += [f"B\tupstream\t{r['n']}\t{r['upstream']}", f"B\tfork\t{r['n']}\t{r['fork']}",
                 f"B\twall_speedup\t{r['n']}\t{r['wall_speedup']}"]
    # The bracket at the largest reference, where the two curves are farthest apart on the page.
    # Between the third and fourth reference sizes, whatever they are: the sizes are read from the
    # record and the subset is 2 023 sequences, not 2 000, so they are not to be spelled here.
    by_n = sorted(grad, key=lambda r: r["n"])
    left, right = by_n[2], by_n[3]
    bx = ax.px((left["n"] * right["n"]) ** 0.5)
    y_up = ax.py((left["upstream"] * right["upstream"]) ** 0.5)
    y_fk = ax.py((left["fork"] * right["fork"]) ** 0.5)
    o.append(f'<line x1="{bx:.1f}" y1="{y_up + 7:.1f}" x2="{bx:.1f}" y2="{y_fk - 7:.1f}" '
             f'stroke="#444" stroke-width="1" marker-end="url(#head)" marker-start="url(#head)"/>')
    lo, hi = min(r["wall_speedup"] for r in grad), max(r["wall_speedup"] for r in grad)
    o.append(txt(bx - 6, (y_up + y_fk) / 2 + 3, f"{lo:.0f} to {hi:.0f}x faster", size=8,
                 anchor="end"))

    # C. The law the whole detection result rests on: what predicts detection is not k and not the
    # fold count but how much of a sequence's surviving neighbourhood already carries the wrong
    # label. Both tools obey it, which is why both curves are drawn, and the fork's sits above
    # upstream's in every band, which is the "finds more" claim. The bands are named on the axis
    # as the ranges they are, which a midpoint of 0.3 does not say.
    ax = Ax("C", (0, 1), (0, 1))
    o += frame(ax, "C", "recall against the share of surviving relatives carrying the wrong label",
               "Surviving Relatives Carrying the Wrong Label (%)", "Recall",
               [], [0, 0.25, 0.5, 0.75, 1], yfmt=lambda v: f"{v:g}")
    for cond, colour, dash in (("epang_T8_K25", FORK, None),
                               ("upstream_raxml_T8", UP, COMPARATOR_DASH)):
        bands = json.loads(Path(root, f"results/detection_law_{cond}.json").read_text())["by_ratio"]
        pts = [((b["low"] + b["high"]) / 2, b["recall"]) for b in bands]
        o += series(ax, pts, colour, dash=dash)
        vals += [f"C\t{cond}\t{x}\t{y}" for x, y in pts]
        if cond == "epang_T8_K25":
            for (x, y), b in zip(pts, bands):
                o.append(txt(ax.px(x), ax.py(y) - 8, f"{y:.2f}", size=7, fill=FORK))
    for b in bands:
        x = ax.px((b["low"] + b["high"]) / 2)
        o.append(f'<line x1="{x:.1f}" y1="{ax.y0 + PH}" x2="{x:.1f}" y2="{ax.y0 + PH + 4}" '
                 f'stroke="#444" stroke-width="0.8"/>')
        o.append(txt(x, ax.y0 + PH + 15, f"{b['low'] * 100:.0f}-{b['high'] * 100:.0f}", size=7))

    # D. What an injected error is. Panel (c) speaks of relatives carrying the wrong label and the
    # text of 180 datasets built from distance, rate, k and seed, and nothing showed what any of
    # that looks like. A small tree does: a group of sequences, k of them given a neighbouring
    # taxon's label at a chosen rank, the rest keeping theirs. The rank is the distance, k is how
    # many move together, and those k are exactly the "relatives carrying the wrong label" that
    # the leave-one-out in (c) then has to see past. Not measured; the reader's key to (c).
    x0, y0 = PANELS["D"]
    o.append(txt(x0 - 44, y0 - 16, "(d)", size=12, anchor="start", weight="bold"))
    CAPTION.append("(d) What an injected error is: k sequences of one group given a neighbouring "
                   "taxon's label at a chosen rank.")
    # A tree: a root splitting into two clades, A with four leaves and B with three.
    rx, ry = x0 + 6, y0 + 76                # root
    ax_, ay_ = x0 + 46, y0 + 40             # clade A node
    bx_, by_ = x0 + 46, y0 + 118            # clade B node
    stroke = 'stroke="#444" stroke-width="1"'
    o.append(f'<path d="M{rx},{ry} V{ay_} H{ax_} M{rx},{ry} V{by_} H{bx_}" fill="none" {stroke}/>')
    leaves_a = [y0 + 16, y0 + 32, y0 + 48, y0 + 64]
    leaves_b = [y0 + 104, y0 + 118, y0 + 132]
    lx = x0 + 86
    o.append(f'<path d="M{ax_},{leaves_a[0]} V{leaves_a[-1]}" fill="none" {stroke}/>')
    o.append(f'<path d="M{bx_},{leaves_b[0]} V{leaves_b[-1]}" fill="none" {stroke}/>')
    for yy in leaves_a + leaves_b:
        o.append(f'<line x1="{ax_}" y1="{yy}" x2="{lx}" y2="{yy}" {stroke}/>')
    # Clade labels, true taxonomy.
    o.append(txt(ax_ - 4, ay_ - 30, "family A", size=8, anchor="end", fill="#444"))
    o.append(txt(bx_ - 4, by_ + 30, "family B", size=8, anchor="end", fill="#444"))
    # Leaf labels: every leaf carries its declared family. Two of A's carry B's, in red.
    for i, yy in enumerate(leaves_a):
        wrong = i in (1, 2)
        o.append(txt(lx + 5, yy + 3, "B" if wrong else "A", size=8, anchor="start",
                     fill=UP if wrong else "#000", weight="bold" if wrong else "normal"))
    for yy in leaves_b:
        o.append(txt(lx + 5, yy + 3, "B", size=8, anchor="start"))
    # The two moved labels bracketed as k.
    bxk = lx + 18
    o.append(f'<path d="M{bxk},{leaves_a[1] - 5} H{bxk + 5} V{leaves_a[2] + 5} H{bxk}" '
             f'fill="none" stroke="{UP}" stroke-width="1"/>')
    o.append(txt(bxk + 10, (leaves_a[1] + leaves_a[2]) / 2 + 3, "k = 2 relabelled", size=8,
                 anchor="start", fill=UP))
    o.append(txt(bxk + 10, (leaves_a[1] + leaves_a[2]) / 2 + 14, "to the neighbour", size=8,
                 anchor="start", fill=UP))
    # The distance: the rank at which the true and the written label part.
    o.append(txt(x0 + 100, y0 + 92, "distance = family", size=8, anchor="start", fill="#444"))
    o.append(txt(x0 + 100, y0 + 104, "(species to phylum)", size=7, anchor="start", fill="#888"))
    # The remaining A leaves are the surviving relatives (c) counts; here half of A carries B's label.
    o.append(txt(x0 + PW / 2, y0 + PH + 15, "6 ranks  x  4 rates  x  5 k  x  3 seeds", size=7,
                 fill="#444"))
    o.append(txt(x0 + PW / 2, y0 + PH + 26, "= 180 datasets, truth known for every label", size=7,
                 fill="#444"))

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
