#!/usr/bin/env python3
"""The Application Note's figure: the evaluation protocol, runtime and memory against the number
of sequences, the four stages across placement shards, the flags by tool, and recall against the
share of surviving relatives. Everything is read from the committed records (figure_data.py and
results/). Writes results/figure3.svg and results/figure3_values.tsv, which lists every drawn value.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_style as mf  # noqa: E402
import figure_data as fd  # noqa: E402

ROOT = fd.ROOT
OUT = ROOT / "results"
GREY, MID, PALE = "#8a8a8a", "#aaaaaa", "#e4e4e4"
FLOOR = 0.511
W = 760
VALUES = ["panel\tseries\tx\ty"]
mf.LABEL_STYLE = "upper"


class Ax:
    def __init__(self, x0, y0, pw, ph, xr, yr, xlog=False, ylog=False):
        self.x0, self.y0, self.pw, self.ph, self.xr, self.yr = x0, y0, pw, ph, xr, yr
        self.xlog, self.ylog = xlog, ylog

    @staticmethod
    def _t(v, log):
        return math.log10(v) if log else v

    def px(self, v):
        a, b = (self._t(r, self.xlog) for r in self.xr)
        return self.x0 + (self._t(v, self.xlog) - a) / (b - a) * self.pw

    def py(self, v):
        a, b = (self._t(r, self.ylog) for r in self.yr)
        return self.y0 + self.ph - (self._t(v, self.ylog) - a) / (b - a) * self.ph


def spaced(n):
    return f"{n:,}".replace(",", " ")


def frame(ax, xticks, yticks, xlabel, ylabel, xfmt=str, yfmt=spaced, letter=None, grid=True, ydx=40):
    o = [f'<rect x="{ax.x0}" y="{ax.y0}" width="{ax.pw}" height="{ax.ph}" fill="#fafafa"/>']
    for v in yticks:
        y = ax.py(v)
        if grid:
            o.append(f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0 + ax.pw}" y2="{y:.1f}" stroke="#e4e4e4" stroke-width="0.6"/>')
        o.append(f'<line x1="{ax.x0 - 4}" y1="{y:.1f}" x2="{ax.x0}" y2="{y:.1f}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(ax.x0 - 7, y + 3, yfmt(v), size=7, anchor="end"))
    for v in xticks:
        x = ax.px(v)
        o.append(f'<line x1="{x:.1f}" y1="{ax.y0 + ax.ph}" x2="{x:.1f}" y2="{ax.y0 + ax.ph + 4}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(x, ax.y0 + ax.ph + 15, xfmt(v), size=7))
    o.append(f'<rect x="{ax.x0}" y="{ax.y0}" width="{ax.pw}" height="{ax.ph}" fill="none" stroke="#444" stroke-width="0.8"/>')
    if xlabel:
        o.append(mf.txt(ax.x0 + ax.pw / 2, ax.y0 + ax.ph + 32, xlabel, size=8))
    o.append(mf.txt(ax.x0 - ydx, ax.y0 + ax.ph / 2, ylabel, size=8, rot=-90))
    if letter:
        o.append(mf.txt(letter[0], ax.y0 - 14, letter[1], size=12, anchor="start", weight="bold"))
    return o


def line(ax, pts, colour, dash=None, r=2.6):
    d = "M" + " L".join(f"{ax.px(x):.1f},{ax.py(y):.1f}" for x, y in pts)
    o = [f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.4"'
         + (f' stroke-dasharray="{dash}"' if dash else "") + "/>"]
    o += [f'<circle cx="{ax.px(x):.1f}" cy="{ax.py(y):.1f}" r="{r}" fill="{colour}" stroke="#fff" stroke-width="0.6"/>'
          for x, y in pts]
    return o


def swatch(x, y, fill, label, edge=None, size=7):
    return [f'<rect x="{x}" y="{y - 7}" width="10" height="9" fill="{fill}" stroke="{edge or fill}" stroke-width="0.9"/>',
            mf.txt(x + 14, y, label, size=size, anchor="start")]


def line_key(x, y, colour, dash, label, size=7):
    return [f'<line x1="{x}" y1="{y - 3}" x2="{x + 20}" y2="{y - 3}" stroke="{colour}" stroke-width="1.4"'
            + (f' stroke-dasharray="{dash}"' if dash else "") + "/>",
            f'<circle cx="{x + 10}" cy="{y - 3}" r="2.6" fill="{colour}" stroke="#fff" stroke-width="0.6"/>',
            mf.txt(x + 26, y, label, size=size, anchor="start", fill=colour if colour != mf.FORK else "#000")]


TAXA = ["#4f7fa8", "#c9902f", "#6a9a6b"]
SUB = "#555"


def dot_grid(x0, y0, relabelled, gap=14):
    o = []
    for r in range(5):
        for c in range(9):
            x, y = x0 + c * gap, y0 + r * gap
            o.append(f'<circle cx="{x}" cy="{y}" r="3.3" fill="{TAXA[relabelled.get((r, c), c // 3)]}" '
                     f'stroke="#fff" stroke-width="0.6"/>')
            if (r, c) in relabelled:
                o.append(f'<circle cx="{x}" cy="{y}" r="5.6" fill="none" stroke="#000" stroke-width="1.2"/>')
    return o


def scale(x0, y, label, ticks, width=132):
    n = len(ticks)
    xs = [x0 + 3 + i * (width - 6) / (n - 1) if n > 2 else x0 + 3 + i * 34 for i in range(n)]
    ya = y + 10
    o = [mf.txt(x0, y, label, size=6.6, anchor="start", weight="bold", fill=SUB),
         f'<line x1="{xs[0]:.1f}" y1="{ya}" x2="{xs[-1]:.1f}" y2="{ya}" stroke="#bbb" stroke-width="1"/>']
    for i, (x, t) in enumerate(zip(xs, ticks)):
        o.append(f'<circle cx="{x:.1f}" cy="{ya}" r="2.5" fill="#444" stroke="#fff" stroke-width="0.6"/>')
        if t:
            anchor = "start" if i == 0 else "end" if i == n - 1 else "middle"
            o.append(mf.txt(x + (-3 if i == 0 else 3 if i == n - 1 else 0), ya + 11, t, size=5.9, fill=SUB,
                            anchor=anchor))
    return o


def step_arrow(x, y, n=24):
    return [f'<path d="M{x},{y} H{x + n} M{x + n - 5},{y - 4.5} L{x + n},{y} L{x + n - 5},{y + 4.5}" fill="none" '
            'stroke="#8a8a8a" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>']


def panel_tag(x, y, letters):
    w = 12 * len(letters) + 4
    return [f'<rect x="{x}" y="{y - 8}" width="{w}" height="12" rx="3" fill="#fff" stroke="#888" stroke-width="0.9"/>',
            mf.txt(x + w / 2, y + 1.2, " ".join(letters), size=6.6, weight="bold")]


def panel_a():
    o = [mf.txt(14, 20, "A", size=12, anchor="start", weight="bold")]
    cx = (40, 202, 372, 556)
    for x, h in zip(cx, ("1  Real reference", "2  Wrong labels added", "3  Varied over 180 datasets",
                         "4  Run both tools, count")):
        o.append(mf.txt(x, 20, h, size=7.5, anchor="start", weight="bold", fill=SUB))
    note = lambda x, y, t: mf.txt(x, y, t, size=6.5, anchor="start", fill=SUB)
    o += dot_grid(cx[0] + 6, 40, {})
    for i, t in enumerate(("Archaea 16S rRNA, GTDB r226", "Real sequences, real labels", "Dot colour is the taxon")):
        o.append(note(cx[0], 120 + 11 * i, t))
    changed = {(1, 1): 1, (2, 1): 1, (2, 2): 1, (3, 7): 0}
    o += dot_grid(cx[1] + 6, 40, changed)
    o += [note(cx[1], 120, "Rings mark the changed labels"), note(cx[1], 131, "Their number is known")]
    x = cx[2]
    o += scale(x, 42, "How far the wrong label is", ["species", "", "", "", "", "phylum"])
    o += scale(x, 82, "How many sequences share it", ["1", "2", "3", "5", "10"])
    o += scale(x, 122, "Share of the reference changed", ["1 %", "5 %"])
    o.append(note(x, 165, "and 3 random draws of each"))
    x = cx[3]
    o += line_key(x, 46, mf.UP, "4 3", "SATIVA", size=7)
    o += line_key(x + 90, 46, mf.FORK, None, "SATIVA-epang", size=7)
    o.append(note(x, 66, "Same data, same threshold"))
    for y, letters, bold, sub in ((94, "BC", "Time and memory", "references of 402 to 7 051"),
                                  (124, "DE", "Injected errors found", "their number is known"),
                                  (154, "D", "Other sequences flagged", "not changed by us")):
        o += panel_tag(x, y, letters)
        o += [mf.txt(x + 36, y, bold, size=6.9, anchor="start", weight="bold"),
              mf.txt(x + 36, y + 11.5, sub, size=6.3, anchor="start", fill=SUB)]
    for xa in (cx[0] + 134, cx[1] + 138, cx[2] + 146):
        o += step_arrow(xa, 68)
    return o


def panel_b(y0=222, ph=118):
    wall, mem = fd.resource_blocks()
    sizes = sorted(wall)
    o = []
    specs = ((62, "Runtime (seconds)", 0, (4, 6000), [10, 100, 1000], (1, 8)),
             (300, "Peak memory (MB)", 1, (70, 60000), [100, 1000, 10000], (0, 7)))
    for i, (x0, ylabel, which, yr, yticks, _) in enumerate(specs):
        ax = Ax(x0, y0, 140, ph, (330, 9000), yr, xlog=True, ylog=True)
        o += frame(ax, [402, 2023, 7051], yticks, "", ylabel, letter=(14, "B") if i == 0 else None, ydx=40 if i == 0 else 52)
        for n in sizes:
            o.append(f'<line x1="{ax.px(n):.1f}" y1="{ax.y0 + ax.ph}" x2="{ax.px(n):.1f}" y2="{ax.y0 + ax.ph + 2.5}" stroke="#444" stroke-width="0.8"/>')
        src = wall if which == 0 else mem
        up = [(n, src[n][1]) for n in sizes]
        fk = [(n, src[n][0]) for n in sizes]
        o += line(ax, up, mf.UP, mf.COMPARATOR_DASH)
        o += line(ax, fk, mf.FORK)
        for n, (f, u) in zip(sizes, zip((v for _, v in fk), (v for _, v in up))):
            VALUES.append(f"B\t{'runtime_s' if which == 0 else 'peak_mb'}_SATIVA-epang\t{n}\t{f}")
            VALUES.append(f"B\t{'runtime_s' if which == 0 else 'peak_mb'}_SATIVA\t{n}\t{u}")
    o += line_key(52, y0 - 14, mf.FORK, None, "SATIVA-epang")
    o += line_key(52 + 130, y0 - 14, mf.UP, mf.COMPARATOR_DASH, "SATIVA")
    o.append(mf.txt(62 + 140 + 49 + 20, y0 + ph + 32, "Sequences in the reference (log scale)", size=8))
    return o


def panel_c(y0=222, ph=118):
    rows = fd.staged_rows()
    ax = Ax(505, y0, 230, ph, (0, 3), (0, 385))
    o = frame(ax, [], [0, 100, 200, 300], "Placement batches", "Runtime (seconds)", letter=(458, "C"))
    stages = (("ref", "tree", PALE), ("tasks", "setup", MID), ("place", "placement", mf.FORK), ("score", "scoring", GREY))
    bw = 50
    for i, row in enumerate(rows):
        cx, base = ax.px(i + 0.5), 0.0
        for key, label, colour in stages:
            v = row[key]
            VALUES.append(f"C\t{key}\t{row['shards']}\t{v}")
            o.append(f'<rect x="{cx - bw / 2:.1f}" y="{ax.py(base + v):.1f}" width="{bw}" height="{ax.py(base) - ax.py(base + v):.1f}" '
                     f'fill="{colour}" stroke="#fff" stroke-width="0.7"/>')
            base += v
        o.append(mf.txt(cx, ax.y0 + ax.ph + 15, row["shards"], size=7))
        lo, hi = ax.py(row["total_min"]), ax.py(row["total_max"])
        o.append(f'<path d="M{cx:.1f} {lo:.1f}V{hi:.1f}M{cx - 5:.1f} {lo:.1f}h10M{cx - 5:.1f} {hi:.1f}h10" stroke="#000" stroke-width="0.9" fill="none"/>')
        o.append(mf.txt(cx, hi - 5, f"{base:.0f} s", size=7.5))
        o.append(mf.txt(cx, ax.py(row["ref"] + row["tasks"] + row["place"] / 2) + 3, f"{row['place']:.0f}", size=7, fill="#fff"))
    lx, ly = ax.x0 + ax.pw - 160, ax.y0 + 14
    for i, (key, label, colour) in enumerate(reversed(stages)):
        o += swatch(lx + (i % 2) * 80, ly + (i // 2) * 15, colour, label, edge=GREY if colour == PALE else None)
    return o


def panel_d(y0=424, ph=118):
    counts, quart = fd.upset_counts(FLOOR)
    groups = (("baseline", "Initial flags"), ("injected", "Injected errors"), ("collateral", "Collateral flags"))
    order = ((True, True, GREY, "both"), (False, True, mf.FORK, "SATIVA-epang only"),
             (True, False, mf.UP, "SATIVA only"), (False, False, "#fff", "neither"))
    x0, pitch, bw, gap = 62, 30, 22, 12
    pw = 11 * pitch + 3 * gap
    ax = Ax(x0, y0, pw, ph, (0, 1), (0, 70))
    o = frame(ax, [], [0, 20, 40, 60], "", "Sequences per dataset", letter=(14, "D"))
    x = x0 + gap / 2
    for kind, title in groups:
        gx0 = x
        for ts, es, colour, label in (order[:3] if kind == "collateral" else order):
            v = counts.get((kind, ts, es), 0.0)
            q1, q3 = quart.get((kind, ts, es), (0, 0))
            cx = x + pitch / 2
            hollow = colour == "#fff"
            o.append(f'<rect x="{cx - bw / 2:.1f}" y="{ax.py(v):.1f}" width="{bw}" height="{ax.py(0) - ax.py(v):.1f}" '
                     f'fill="{colour}" stroke="{mf.FORK if hollow else "#fff"}" stroke-width="{1.1 if hollow else 0.6}"/>')
            o.append(f'<path d="M{cx:.1f} {ax.py(q1):.1f}V{ax.py(q3):.1f}M{cx - 3:.1f} {ax.py(q1):.1f}h6M{cx - 3:.1f} {ax.py(q3):.1f}h6" stroke="#000" stroke-width="0.8" fill="none"/>')
            o.append(mf.txt(cx, ax.py(max(v, q3)) - 4, "<1" if 0 < v < 1 else f"{v:.0f}", size=7))
            VALUES.append(f"D\t{kind}_{label}\t{FLOOR}\t{v:.2f}")
            x += pitch
        o.append(f'<line x1="{gx0 + 4}" y1="{ax.y0 + ph + 8}" x2="{x - 4}" y2="{ax.y0 + ph + 8}" stroke="{GREY}" stroke-width="1.6"/>')
        o.append(mf.txt((gx0 + x) / 2, ax.y0 + ph + 22, title, size=7.5))
        x += gap
    lx = x0
    for label, colour in (("both tools", GREY), ("SATIVA-epang only", mf.FORK), ("SATIVA only", mf.UP), ("neither", "#fff")):
        o += swatch(lx, y0 - 14, colour, label, edge=mf.FORK if colour == "#fff" else None)
        lx += 14 + len(label) * 7 * mf.FONT_SCALE * 0.5 + 14
    return o


def panel_e(y0=424, ph=118):
    import json
    ax = Ax(505, y0, 230, ph, (0, 5.35), (0, 1))
    o = frame(ax, [], [0, 0.25, 0.5, 0.75, 1], "Surviving relatives with the wrong label (%)", "Recall",
              yfmt=lambda v: f"{v:g}", letter=(458, "E"))
    for cond, colour, dash in (("upstream_raxml_T8", mf.UP, mf.COMPARATOR_DASH), ("epang_T8_K25", mf.FORK, None)):
        bands = json.loads((ROOT / f"results/detection_law_{cond}.json").read_text())["by_ratio"]
        pts = [(i + 0.5, b["recall"]) for i, b in enumerate(bands)]
        o += line(ax, pts, colour, dash)
        for i, b in enumerate(bands):
            VALUES.append(f"E\t{cond}\t{(b['low'] + b['high']) / 2}\t{b['recall']}")
            if colour == mf.FORK:
                o.append(mf.txt(ax.px(i + 0.5) + 5, ax.py(b["recall"]) - 7, f"{b['recall']:.2f}", size=7, anchor="start"))
    for i, b in enumerate(bands):
        o.append(mf.txt(ax.px(i + 0.5), ax.y0 + ph + 15, f"{b['low'] * 100:.0f}-{b['high'] * 100:.0f}", size=7))
        o.append(f'<line x1="{ax.px(i + 0.5):.1f}" y1="{ax.y0 + ph}" x2="{ax.px(i + 0.5):.1f}" y2="{ax.y0 + ph + 4}" stroke="#444" stroke-width="0.8"/>')
    o += line_key(ax.x0 + ax.pw - 110, ax.y0 - 8, mf.FORK, None, "SATIVA-epang")
    o += line_key(ax.x0 + ax.pw - 110 - 90 + 6, ax.y0 - 8, mf.UP, mf.COMPARATOR_DASH, "SATIVA")
    return o


def figure():
    o = panel_a() + panel_b() + panel_c() + panel_d() + panel_e()
    h = 578
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
           f'font-family="Helvetica,Arial,sans-serif"><rect width="{W}" height="{h}" fill="#fff"/>'
           + "\n".join(o) + "</svg>\n")
    return svg.replace("sativa-epang", "SATIVA-epang")


if __name__ == "__main__":
    (OUT / "figure3.svg").write_text(figure())
    (OUT / "figure3_values.tsv").write_text("\n".join(VALUES) + "\n")
    print(f"wrote {OUT / 'figure3.svg'} ({len(VALUES) - 1} values)")
