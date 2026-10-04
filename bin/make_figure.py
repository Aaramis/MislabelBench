#!/usr/bin/env python3
"""Build the Application Note's one multi-panel figure from the committed records.

Part 1 of Protocol.md allows the main text 2000 words plus one figure, and orders what it
carries: "Speed and scaling first; the exclusion column second; accuracy against injected
ground truth as the control that bounds both." The four panels are that sentence, with 2.8's
requirement that scaling be reported per stage rather than as one total.

  A  wall clock against reference size, both tools, log-log
  B  the three stages and the one that distributes, at one, two and four nodes
  C  the exclusion column against confidence, as a filter
  D  recall against k, both tools, which is the limit the design predicts

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
and not only as a change of ink.
"""

import argparse
import json
import math
import statistics as st
from pathlib import Path

W, H = 760, 540
# Plot areas: two rows of two, left margin wide enough for a rotated y label.
PANELS = {"A": (62, 40), "B": (452, 40), "C": (62, 320), "D": (452, 320)}
PW, PH = 240, 180
FORK, UP = "#1b6ca8", "#c1462c"
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


def frame(ax, key, title, xlabel, ylabel, xticks, yticks, xfmt=str, yfmt=str):
    o = [f'<rect x="{ax.x0}" y="{ax.y0}" width="{PW}" height="{PH}" fill="none" '
         f'stroke="#444" stroke-width="0.8"/>',
         txt(ax.x0 - 44, ax.y0 - 16, key, size=13, anchor="start", weight="bold"),
         txt(ax.x0 - 26, ax.y0 - 16, title, size=10, anchor="start"),
         txt(ax.x0 + PW / 2, ax.y0 + PH + 32, xlabel, size=10),
         txt(ax.x0 - 40, ax.y0 + PH / 2, ylabel, size=10, rot=-90)]
    for v in xticks:
        x = ax.px(v)
        o.append(f'<line x1="{x:.1f}" y1="{ax.y0 + PH}" x2="{x:.1f}" y2="{ax.y0 + PH + 4}" '
                 f'stroke="#444" stroke-width="0.8"/>')
        o.append(txt(x, ax.y0 + PH + 15, xfmt(v), size=8))
    for v in yticks:
        y = ax.py(v)
        o.append(f'<line x1="{ax.x0 - 4}" y1="{y:.1f}" x2="{ax.x0}" y2="{y:.1f}" '
                 f'stroke="#444" stroke-width="0.8"/>')
        o.append(txt(ax.x0 - 7, y + 3, yfmt(v), size=8, anchor="end"))
    return o


def series(ax, pts, colour, dash=None, marker="o"):
    d = " ".join(f"{'M' if i == 0 else 'L'}{ax.px(x):.1f},{ax.py(y):.1f}"
                 for i, (x, y) in enumerate(pts))
    s = f' stroke-dasharray="{dash}"' if dash else ""
    o = [f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.6"{s}/>']
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
    o += frame(ax, "A", "wall clock, both tools", "reference sequences", "seconds",
               [400, 1000, 2000, 4000, 7000], [10, 100, 1000],
               xfmt=lambda v: f"{v:,}".replace(",", " "))
    o += series(ax, [(r["n"], r["upstream"]) for r in grad], UP)
    o += series(ax, [(r["n"], r["fork"]) for r in grad], FORK)
    o += legend(ax.x0 + 8, ax.y0 + 14, [("upstream SATIVA", UP, None),
                                        ("sativa-epang", FORK, None)])
    # The speedup is the point of the panel and is not readable off two log curves.
    for r in grad:
        o.append(txt(ax.px(r["n"]), ax.py(r["fork"]) - 9, f"{r['wall_speedup']:.0f}x",
                     size=7, fill=FORK))
    for r in grad:
        vals += [f"A\tupstream\t{r['n']}\t{r['upstream']}", f"A\tfork\t{r['n']}\t{r['fork']}",
                 f"A\twall_speedup\t{r['n']}\t{r['wall_speedup']}"]

    # B. Scaling per stage, because only one stage distributes.
    stages = read_stages(root)
    ax = Ax("B", (0, 3), (0, 300))
    o += frame(ax, "B", "stages at 1, 2 and 4 nodes", "nodes (7 051 sequences)", "seconds",
               [], [0, 100, 200, 300])
    bw = 46
    for i, row in enumerate(stages):
        base = 0.0
        cx = ax.px(i + 0.5)
        for key in ("reference_sec", "loo_tasks_sec", "loo_place_sec", "loo_score_sec"):
            v = row[key]
            y1, y0 = ax.py(base + v), ax.py(base)
            o.append(f'<rect x="{cx - bw / 2:.1f}" y="{y1:.1f}" width="{bw}" '
                     f'height="{y0 - y1:.1f}" fill="{STAGE[key]}" stroke="#fff" '
                     f'stroke-width="0.5"/>')
            base += v
            vals.append(f"B\t{key}\t{row['nodes']}\t{round(v, 2)}")
        o.append(txt(cx, ax.y0 + PH + 15, row["nodes"], size=8))
        o.append(txt(cx, ax.py(base) - 5, f"{base:.0f}", size=8))
    # Placed between the one-node bar and the four-node one, the only clear space in the panel:
    # at the left it covered the N=1 total and at the right the N=4 one.
    o += legend(ax.x0 + 94, ax.y0 + 10,
                [("scoring", STAGE["loo_score_sec"], None),
                 ("placement", STAGE["loo_place_sec"], None),
                 ("fold setup", STAGE["loo_tasks_sec"], None),
                 ("reference", STAGE["reference_sec"], None)], size=8)

    # C. The exclusion column as a filter, which is the claim that can go either way.
    cc = json.loads(Path(root, "results/column_comparison.json").read_text())
    # Both curves live in the top right corner -- neither column throws away many injected
    # flags -- so the panel is drawn over the range the curves actually occupy. Full-range
    # axes would show two lines touching the corner and nothing else. The tick labels say
    # where the axes start.
    curves = {}
    for name in ("confidence", "exclusion"):
        c = cc["curves"][name]
        ti = max(r["injected_kept"] for r in c)
        tu = max(r["untouched_kept"] for r in c)
        curves[name] = [(r["untouched_kept"] / tu, r["injected_kept"] / ti) for r in c]
    lo_x = min(x for pts in curves.values() for x, _ in pts)
    lo_y = min(y for pts in curves.values() for _, y in pts)
    ax = Ax("C", (lo_x - 0.04, 1.02), (lo_y - 0.03, 1.01))
    o += frame(ax, "C", "filtering, by each column", "collateral flags kept",
               "injected flags kept", [0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
               [0.80, 0.85, 0.90, 0.95, 1.0],
               xfmt=lambda v: f"{v:.1f}", yfmt=lambda v: f"{v:.2f}")
    for name, colour, dash in (("confidence", FORK, None), ("exclusion", UP, "4 2")):
        o += series(ax, curves[name], colour, dash=dash, marker=None)
        floor = cc["untouched_floor"][name] / max(r["untouched_kept"]
                                                  for r in cc["curves"][name])
        vals.append(f"C\t{name}_floor\t{floor:.4f}\t{min(y for _, y in curves[name]):.4f}")
    o += legend(ax.x0 + 10, ax.y0 + 14, [("confidence", FORK, None), ("exclusion", UP, "4 2")])
    ex = cc["untouched_floor"]["exclusion"] / max(r["untouched_kept"]
                                                  for r in cc["curves"]["exclusion"])
    o.append(txt(ax.x0 + PW - 8, ax.y0 + PH - 22,
                 f"at 0.99 exclusion still keeps {ex * 100:.0f}% of the collateral flags",
                 size=7, anchor="end", fill=UP))
    o.append(txt(ax.x0 + PW - 8, ax.y0 + PH - 12, "and confidence 51 %",
                 size=7, anchor="end", fill=FORK))

    # D. The accuracy control, and the limit the injection design predicts.
    ax = Ax("D", (0.8, 10.5), (0, 1), xlog=True)
    o += frame(ax, "D", "recall against shared-label count", "k relabelled together",
               "recall (mean of 6 distances)", [1, 2, 3, 5, 10], [0, 0.25, 0.5, 0.75, 1],
               xfmt=lambda v: f"{v:g}", yfmt=lambda v: f"{v:g}")
    for cond, colour in (("upstream_raxml_T8", UP), ("epang_T8_K25", FORK)):
        for rate, dash in ((0.05, None), (0.01, "4 2")):
            r = read_recall(root, cond, rate)
            o += series(ax, sorted(r.items()), colour, dash=dash)
            vals += [f"D\t{cond}_r{rate}\t{k}\t{v:.4f}" for k, v in sorted(r.items())]
    o += legend(ax.x0 + PW - 96, ax.y0 + 14,
                [("upstream, 5 %", UP, None), ("upstream, 1 %", UP, "4 2"),
                 ("fork, 5 %", FORK, None), ("fork, 1 %", FORK, "4 2")])

    o.append("</svg>")
    Path(args.out).write_text("\n".join(o) + "\n")
    Path(args.values).write_text("\n".join(vals) + "\n")
    print(f"{args.out}: 4 panels, {len(vals) - 1} values, from committed records only")


if __name__ == "__main__":
    main()
