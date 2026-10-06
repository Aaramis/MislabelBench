#!/usr/bin/env python3
"""Candidate panels for the Application Note's figure, one file each, to be judged on sight.

Six ideas, each tied to one claim or one section of the benchmark plan, drawn standalone so a
reader can accept or reject them one at a time. Everything is read from committed records; the
helpers are make_figure's, so whatever is kept moves into it unchanged.
"""

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_figure as mf  # noqa: E402

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
OUT = ROOT / "results" / "candidates"
OUT.mkdir(parents=True, exist_ok=True)
GREY, LIGHT = "#8a8a8a", "#d5d5d5"


def num(n):
    return f"{n:,}".replace(",", " ")

# Every number drawn, as make_figure.py keeps for its own figure: a change in any upstream record
# shows up as a diff in this table and not only as a change of ink.
VALUES = ["panel\tseries\tx\ty"]
CAPTION = []


def place_label(ax, x, y, text, colour, dx=-6, dy=-6, size=7):
    """A point's label at its usual offset, flipped only when it would leave the frame.

    The first version of this flipped every label to a fixed inward side and so laid half of them on
    the curves. The default side is the one that reads best for the series; the flip is the
    exception, taken only when the text would cross an edge.
    """
    px, py = ax.px(x), ax.py(y)
    w = len(text) * size * 0.58
    if dx < 0 and px + dx - w < ax.x0 + 2:
        dx = -dx
    elif dx > 0 and px + dx + w > ax.x0 + mf.PW - 2:
        dx = -dx
    if dy > 0 and py + dy > ax.y0 + mf.PH - 3:
        dy = -6
    elif dy < 0 and py + dy < ax.y0 + 8:
        dy = 12
    anchor = "middle" if dx == 0 else ("end" if dx < 0 else "start")
    return mf.txt(px + dx, py + dy, text, size=size, anchor=anchor, fill=colour)


def canvas(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="Helvetica,Arial,sans-serif"><rect width="{w}" height="{h}" fill="#fff"/>'
            + "\n".join(body) + "</svg>\n")


def single(w=400, h=300, pw=280, ph=190, x0=72, y0=40, letter="A"):
    mf.PANELS[letter] = (x0, y0)
    mf.PW, mf.PH = pw, ph
    return w, h


def resource_blocks():
    """The size gradient (wall seconds) and the peak-memory table (child MB), by sequences."""
    lines = (ROOT / "results/resource_usage.txt").read_text().splitlines()
    wall, mem = {}, {}
    mode = None
    for ln in lines:
        if ln.startswith("size gradient"):
            mode = "wall"
        elif ln.startswith("peak memory, both tools"):
            mode = "mem"
        elif ln.startswith("peak memory on the thread"):
            mode = None
        parts = ln.split()
        if mode and parts and parts[0].isdigit():
            n = int(parts[0])
            if mode == "wall":
                wall[n] = (float(parts[1]), float(parts[2]))          # fork, upstream
            else:
                mem[n] = (float(parts[2]), float(parts[4]))           # fork child, up child
    return wall, mem


# 1. The workflow, standalone.
def fig_1():
    mf.CAPTION.clear()
    return 760, 240, mf.schematic()


# 2. Runtime against peak memory: the plan's "time constrains the original, memory constrains ours".
def fig_2(L="A", g=(420, 320, 290, 200, 78, 40)):
    w, h = single(*g, L)
    wall, mem = resource_blocks()
    ax = mf.Ax(L, (5, 11000), (50, 20000), xlog=True, ylog=True)
    o = mf.frame(ax, L, "", "Runtime (seconds)", "Peak Memory (MB)",
                 [10, 100, 1000], [100, 1000, 10000],
                 xfmt=lambda v: f"{v:g}", yfmt=lambda v: f"{v:,}".replace(",", " "))
    for secs, label in ((60, "1 min"), (600, "10 min"), (3600, "1 h")):
        xx = ax.px(secs)
        o.append(f'<line x1="{xx:.1f}" y1="{ax.y0}" x2="{xx:.1f}" y2="{ax.y0 + mf.PH}" '
                 f'stroke="#c8c8c8" stroke-width="0.7" stroke-dasharray="3 2"/>')
        o.append(mf.txt(xx + 3, ax.y0 + 10, label, size=7, anchor="start", fill="#888"))
    sizes = sorted(wall)
    fork = [(wall[n][0], mem[n][0]) for n in sizes]
    up = [(wall[n][1], mem[n][1]) for n in sizes]
    o += mf.series(ax, up, mf.UP, dash=mf.COMPARATOR_DASH)
    o += mf.series(ax, fork, mf.FORK)
    for n, (x, y) in zip(sizes, fork):
        VALUES.append(f"{L}\tfork_wall_s_vs_child_mb\t{x}\t{y}")
    for n, (x, y) in zip(sizes, up):
        VALUES.append(f"{L}\tupstream_wall_s_vs_child_mb\t{x}\t{y}")
    CAPTION.append(f"({L.lower()}) Wall clock against peak memory, one point per reference size from "
                   f"{num(min(sizes))} to {num(max(sizes))} sequences, both tools at 8 threads.")
    for n, (x, y) in zip(sizes, fork):
        o.append(place_label(ax, x, y, num(n), mf.FORK, dx=-6, dy=-6))
    for i, (n, (x, y)) in enumerate(zip(sizes, up)):
        # A label offset sideways from a local minimum lands on the rising arm of its own curve.
        # Centred underneath, there is nothing to collide with; the same holds above a maximum.
        lo = 0 < i < len(up) - 1 and y < up[i - 1][1] and y < up[i + 1][1]
        o.append(place_label(ax, x, y, num(n), mf.UP, dx=0 if lo else 6, dy=14))
    o += mf.legend(ax.x0 + 8, ax.y0 + mf.PH - 24, [("sativa-epang", mf.FORK, None),
                                                     ("SATIVA", mf.UP, mf.COMPARATOR_DASH)], size=8)
    return w, h, o


# 3. The stages at one, two and four shards: only placement distributes.
# Read from the pipeline's own staged records, results/staged_scaling_f{25,13,7}.txt, and not from
# results/scaling/*/timing.json: those are the earlier srun fan-out, which threw one straggler per
# allocation at 124 to 258 s and showed four nodes no faster than one. The pipeline's shards finish
# within 0.6 s of each other and the straggler was the fan-out's, not the tool's. README's own table
# rests on these records, so the panel has to as well.
STAGE = {"ref": ("reference tree", LIGHT), "tasks": ("batch setup", "#b5b5b5"),
         "place": ("placement", mf.FORK), "score": ("scoring", GREY)}


def staged_rows():
    rows = []
    for fpj in (25, 13, 7):
        ln = (ROOT / f"results/staged_scaling_f{fpj}.txt").read_text().splitlines()[1].split()
        rows.append({"shards": int(ln[1]), "ref": float(ln[2]), "tasks": float(ln[3]),
                     "place": float(ln[4]), "spread": float(ln[5]), "score": float(ln[6])})
    return sorted(rows, key=lambda r: r["shards"])


def fig_3(L="A", g=(400, 300, 260, 190, 72, 40)):
    w, h = single(*g, L)
    rows = staged_rows()
    # 320 and not 300: the total is written just above its bar, and at 288 s that put the label on
    # the 300 gridline. The ticks stay at the round hundreds.
    ax = mf.Ax(L, (0, 3), (0, 320))
    o = mf.frame(ax, L, "", "Placement Shards", "Runtime (seconds)", [], [0, 100, 200, 300])
    bw = 52
    for i, row in enumerate(rows):
        base, cx = 0.0, ax.px(i + 0.5)
        for key, (label, colour) in STAGE.items():
            v = row[key]
            VALUES.append(f"{L}\t{key}\t{row['shards']}\t{v}")
            y1, y0 = ax.py(base + v), ax.py(base)
            o.append(f'<rect x="{cx - bw / 2:.1f}" y="{y1:.1f}" width="{bw}" height="{y0 - y1:.1f}" '
                     f'fill="{colour}" stroke="#fff" stroke-width="0.6"/>')
            base += v
        o.append(mf.txt(cx, ax.y0 + mf.PH + 15, row["shards"], size=8))
        o.append(mf.txt(cx, ax.py(base) - 5, f"{base:.0f} s", size=8))
        o.append(mf.txt(cx, ax.py(row["ref"] + row["tasks"] + row["place"] / 2) + 3,
                        f"{row['place']:.0f}", size=7, fill="#fff"))
    by_shards = {r["shards"]: r["spread"] for r in rows}
    CAPTION.append(f"({L.lower()}) The four stages on 7 051 sequences with 25 folds, one node per shard. "
                   f"Only placement distributes. At four shards they finish within {by_shards[4]:.1f} s of "
                   f"each other; at two the spread is {by_shards[2]:.1f} s because 25 folds split 13 and 12.")
    lx, ly = ax.x0 + mf.PW + 6, ax.y0 + 8
    for key, (label, colour) in reversed(list(STAGE.items())):
        o.append(f'<rect x="{lx}" y="{ly - 7}" width="10" height="9" fill="{colour}"/>')
        o.append(mf.txt(lx + 14, ly, label, size=7, anchor="start"))
        ly += 13
    return w, h, o


# 4. How flags are counted, and what it gives, by taxonomic distance of the injected error.
DIST = ["species", "genus", "family", "order", "class", "phylum"]


def flag_counts():
    """Per distance: mean baseline kept, lost, collateral (gained), injected errors found, and the
    share of collateral flags inside a touched clade. From three committed records."""
    rows = [ln.split("\t") for ln in (ROOT / "results/background_stability.tsv").read_text().splitlines()[1:]]
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for cell, n_inj, base, kept, lost, gained in rows:
        d = cell.split("_")[1]
        for k, v in (("injected", n_inj), ("kept", kept), ("lost", lost), ("gained", gained)):
            by[d][k].append(float(v))
    grid = json.loads((ROOT / "results/grid_summary_epang_T8_K25.json").read_text())["rows"]
    rec = collections.defaultdict(list)
    for r in grid:
        if r["metric"] == "by_confidence" and r["threshold"] == 0.0:
            rec[r["distance"]].append(r["recall_mean"])
    local = {}
    for ln in (ROOT / "results/collateral_locality.txt").read_text().splitlines()[1:]:
        q = ln.split()
        if len(q) == 3:
            local[q[0]] = q[2]
    mean = lambda xs: sum(xs) / len(xs)
    out = {}
    for d in DIST:
        out[d] = {"kept": mean(by[d]["kept"]), "lost": mean(by[d]["lost"]), "gained": mean(by[d]["gained"]),
                  "found": mean(rec[d]) * mean(by[d]["injected"]), "local": local.get(d, "")}
    return out


HATCH = ('<defs><pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" '
         'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" stroke="#888" '
         'stroke-width="1.2"/></pattern></defs>')


def fig_4b(L="D", g=(760, 300, 420, 150, 58, 40)):
    """The flag count with the lost baseline flags hatched on the baseline itself.

    Grey plus hatching is the baseline before injection; everything above it is what injection
    added. Drawn stacked above zero so the bar reads without the legend, which a box below zero
    did not. The lost segment sits on the grey and not on top of the stack, because those flags are
    gone after injection and do not belong in the after-total.
    """
    w, h = single(*g, L)
    data = flag_counts()
    top = max(v["kept"] + v["lost"] + v["found"] + v["gained"] for v in data.values())
    # Headroom for the legend above the tallest bars, and ticks all the way up: a y axis labelled
    # to 150 under a frame reaching 235 reads as a plotting error.
    import math
    ymax = math.ceil(top * 1.45 / 50) * 50
    ax = mf.Ax(L, (0, 6), (0, ymax))
    o = [HATCH]
    o += mf.frame(ax, L, "", "Taxonomic Distance of the Injected Error", "Flags per Dataset",
                  [], list(range(0, ymax + 1, 50)), yfmt=lambda v: f"{v:g}")
    bw = 40
    for i, d in enumerate(DIST):
        v, cx, base = data[d], ax.px(i + 0.5), 0.0
        for name, fill in (("kept", LIGHT), ("lost", "url(#hatch)"), ("found", mf.FORK), ("gained", mf.UP)):
            y1, y0 = ax.py(base + v[name]), ax.py(base)
            o.append(f'<rect x="{cx - bw / 2:.1f}" y="{y1:.1f}" width="{bw}" height="{y0 - y1:.1f}" '
                     f'fill="{fill}" stroke="#fff" stroke-width="0.6"/>')
            VALUES.append(f"{L}\t{name}\t{d}\t{v[name]:.2f}")
            base += v[name]
        VALUES.append(f"{L}\tcollateral_local_share\t{d}\t{v['local']}")
        o.append(mf.txt(cx, ax.y0 + mf.PH + 15, d.capitalize(), size=7.5))
        o.append(mf.txt(cx, ax.py(base) - 4, v["local"], size=6.5, fill=mf.UP))
    entries = (("baseline flags retained", LIGHT), ("baseline flags lost", "url(#hatch)"),
               ("injected errors found", mf.FORK), ("new collateral flags", mf.UP))
    for i, (label, fill) in enumerate(entries):
        lx = ax.x0 + 10 + (i % 2) * 150
        ly = ax.y0 + 12 + (i // 2) * 12
        o.append(f'<rect x="{lx}" y="{ly - 7}" width="10" height="9" fill="{fill}" stroke="{GREY}" stroke-width="0.6"/>')
        o.append(mf.txt(lx + 14, ly, label, size=7, anchor="start"))
    CAPTION.append(f"({L.lower()}) Flags per dataset by the taxonomic distance of the injected error. Grey and "
                   "hatched together are the baseline before injection, the hatched part being the baseline "
                   "flags that disappear after it; above them, the injected errors found and the collateral "
                   "flags on untouched sequences. The percentage is the share of collateral flags inside a "
                   "clade the injection touched. Untouched sequences are not known negatives.")
    return w, h, o


def fig_4(L="A", g=(660, 320, 300, 190, 232, 40), key=True):
    w, h = single(*g, L)
    rows = [ln.split("\t") for ln in (ROOT / "results/background_stability.tsv").read_text().splitlines()[1:]]
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for cell, n_inj, base, kept, lost, gained in rows:
        d = cell.split("_")[1]
        for k, v in (("injected", n_inj), ("kept", kept), ("lost", lost), ("gained", gained)):
            by[d][k].append(float(v))
    grid = json.loads((ROOT / "results/grid_summary_epang_T8_K25.json").read_text())["rows"]
    rec = collections.defaultdict(list)
    for r in grid:
        if r["metric"] == "by_confidence" and r["threshold"] == 0.0:
            rec[r["distance"]].append(r["recall_mean"])
    local = {}
    for ln in (ROOT / "results/collateral_locality.txt").read_text().splitlines()[1:]:
        p = ln.split()
        if len(p) == 3:
            local[p[0]] = p[2]
    mean = lambda xs: sum(xs) / len(xs)
    ax = mf.Ax(L, (0, 6), (-25, 160 if key else 330))
    o = mf.frame(ax, L, "", "Taxonomic Distance of the Injected Error", "Flags per Dataset (mean)",
                 [], [0, 50, 100, 150], yfmt=lambda v: f"{v:g}")
    o.append(f'<line x1="{ax.x0}" y1="{ax.py(0):.1f}" x2="{ax.x0 + mf.PW}" y2="{ax.py(0):.1f}" '
             f'stroke="#444" stroke-width="0.8"/>')
    bw = 30
    for i, d in enumerate(DIST):
        cx = ax.px(i + 0.5)
        found = mean(rec[d]) * mean(by[d]["injected"])
        segs = (("kept", mean(by[d]["kept"]), LIGHT), ("found", found, mf.FORK),
                ("gained", mean(by[d]["gained"]), mf.UP))
        for name, v, _ in segs:
            VALUES.append(f"{L}\t{name}\t{d}\t{v:.2f}")
        VALUES.append(f"{L}\tlost\t{d}\t{mean(by[d]['lost']):.2f}")
        VALUES.append(f"{L}\tcollateral_local_share\t{d}\t{local.get(d, '')}")
        base = 0.0
        for name, v, colour in segs:
            y1, y0 = ax.py(base + v), ax.py(base)
            o.append(f'<rect x="{cx - bw / 2:.1f}" y="{y1:.1f}" width="{bw}" height="{y0 - y1:.1f}" '
                     f'fill="{colour}" stroke="#fff" stroke-width="0.6"/>')
            base += v
        lost = mean(by[d]["lost"])
        o.append(f'<rect x="{cx - bw / 2:.1f}" y="{ax.py(0):.1f}" width="{bw}" height="{ax.py(-lost) - ax.py(0):.1f}" '
                 f'fill="#fff" stroke="{GREY}" stroke-width="0.8" stroke-dasharray="2 1"/>')
        o.append(mf.txt(cx, ax.y0 + mf.PH + 15, d, size=7))
        o.append(mf.txt(cx, ax.py(base) - 4, local.get(d, ""), size=6.5, fill=mf.UP))
    CAPTION.append(f"({L.lower()}) Flags per dataset by the taxonomic distance of the injected error: "
                   "baseline flags kept, injected errors found, collateral flags on untouched sequences, "
                   "and baseline flags lost, drawn below zero. The percentage is the share of collateral "
                   "flags inside a clade the injection touched. Untouched sequences are not known negatives.")
    entries = (("baseline flags kept", LIGHT, False), ("injected errors found", mf.FORK, False),
               ("collateral flags, with the", mf.UP, False), ("baseline flags lost", "#fff", True))
    if key:
        lx, ly = ax.x0 + mf.PW + 8, ax.y0 + 10
        for label, colour, dashed in entries:
            o.append(f'<rect x="{lx}" y="{ly - 7}" width="10" height="9" fill="{colour}" stroke="{GREY}" '
                     f'stroke-width="0.8"{" stroke-dasharray=\"2 1\"" if dashed else ""}/>')
            o.append(mf.txt(lx + 14, ly, label, size=7, anchor="start"))
            ly += 12
            if label.startswith("collateral"):
                o.append(mf.txt(lx + 14, ly, "share inside a touched clade", size=7, anchor="start"))
                ly += 12
    else:
        # Two columns in the headroom above the bars; the collateral entry on one line.
        short = (("baseline kept", LIGHT, False), ("injected found", mf.FORK, False),
                 ("collateral (% in a touched clade)", mf.UP, False), ("baseline lost", "#fff", True))
        for i, (label, colour, dashed) in enumerate(short):
            lx = ax.x0 + 6 + (i % 2) * 88 if i < 2 else ax.x0 + 6
            ly = ax.y0 + 10 + (0 if i < 2 else 12 * (i - 1))
            o.append(f'<rect x="{lx}" y="{ly - 7}" width="9" height="8" fill="{colour}" stroke="{GREY}" '
                     f'stroke-width="0.8"{" stroke-dasharray=\"2 1\"" if dashed else ""}/>')
            o.append(mf.txt(lx + 12, ly, label, size=6.5, anchor="start"))
    # The three-box key on the left: what is done, then how each flag is classed.
    bx, by0 = 20, 60
    for i, (lines, fill) in enumerate(() if not key else ((["Inject errors", "at a chosen rank"], "#f0f0f0"),
                                       (["Run both tools", "before and after"], "#e3eef7"),
                                       (["Class every flag:", "kept, lost, found,", "collateral"], "#e8f3e8"))):
        o += mf.box(bx, by0 + i * 62, 150, 48, fill, [(t, "normal", "#000") for t in lines], size=7.5)
        if i < 2:
            o += mf.arrow(bx + 75, by0 + i * 62 + 50, bx + 75, by0 + (i + 1) * 62 - 3)
    return w, h, o


# 5. The limit: recall against the share of surviving relatives carrying the wrong label.
def fig_5(L="A", g=(400, 300, 260, 190, 72, 40)):
    w, h = single(*g, L)
    ax = mf.Ax(L, (0, 1), (0, 1))
    o = mf.frame(ax, L, "", "Surviving Relatives Carrying the Wrong Label (%)", "Recall",
                 [], [0, 0.25, 0.5, 0.75, 1], yfmt=lambda v: f"{v:g}")
    for cond, colour, dash in (("epang_T8_K25", mf.FORK, None), ("upstream_raxml_T8", mf.UP, mf.COMPARATOR_DASH)):
        bands = json.loads((ROOT / f"results/detection_law_{cond}.json").read_text())["by_ratio"]
        pts = [((b["low"] + b["high"]) / 2, b["recall"]) for b in bands]
        o += mf.series(ax, pts, colour, dash=dash)
        VALUES.extend(f"{L}\t{cond}\t{x}\t{y}" for x, y in pts)
        if cond == "epang_T8_K25":
            for x, y in pts:
                o.append(place_label(ax, x, y, f"{y:.2f}", mf.FORK, dx=6, dy=-8))
    CAPTION.append(f"({L.lower()}) Recall against the share of a sequence's surviving relatives that already "
                   "carry the wrong label, both tools. Both follow the same curve, which is why half of every "
                   "injected mislabel is found by neither.")
    for b in bands:
        x = ax.px((b["low"] + b["high"]) / 2)
        o.append(mf.txt(x, ax.y0 + mf.PH + 15, f"{b['low'] * 100:.0f}-{b['high'] * 100:.0f}", size=7))
    o += mf.legend(ax.x0 + mf.PW - 90, ax.y0 + 12, [("sativa-epang", mf.FORK, None),
                                                     ("SATIVA", mf.UP, mf.COMPARATOR_DASH)], size=8)
    return w, h, o


# 6. The confidence histogram: the point mass at 0.510, and the column that explains it.
def fig_6(L="A", g=(420, 300, 290, 190, 72, 40)):
    w, h = single(*g, L)
    conf, excl = [], []
    for mis in sorted((ROOT / "results/grid_fork/runs").glob("*__epang_T8_K25__rep1/*.mis")):
        for ln in mis.read_text().splitlines():
            if ln.startswith(";") or not ln.strip():
                continue
            f = ln.split("\t")
            conf.append(float(f[4]))
            excl.append(float(f[8]) if len(f) > 8 else None)
    bins = collections.defaultdict(lambda: [0, 0])
    for c, e in zip(conf, excl):
        b = min(int(c * 50) / 50, 0.98)                  # 0.02-wide bins from 0.50
        bins[b][0 if (e is not None and e >= 0.99) else 1] += 1
    top = max(sum(v) for v in bins.values())
    ax = mf.Ax(L, (0.49, 1.01), (0, top * 1.12))
    o = mf.frame(ax, L, "", "Confidence", "Flags",
                 [0.5, 0.6, 0.7, 0.8, 0.9, 1.0], list(range(0, int(top * 1.12), 4000)),
                 xfmt=lambda v: f"{v:.1f}", yfmt=lambda v: f"{v:,}".replace(",", " "))
    bw = ax.px(0.52) - ax.px(0.50) - 1
    for b, (hi, lo) in sorted(bins.items()):
        VALUES.append(f"{L}\texclusion_ge_0.99\t{b:.2f}\t{hi}")
        VALUES.append(f"{L}\texclusion_lt_0.99\t{b:.2f}\t{lo}")
        x = ax.px(b)
        y_lo, y_hi = ax.py(lo), ax.py(lo + hi)
        o.append(f'<rect x="{x:.1f}" y="{y_lo:.1f}" width="{bw:.1f}" height="{ax.py(0) - y_lo:.1f}" fill="{LIGHT}"/>')
        o.append(f'<rect x="{x:.1f}" y="{y_hi:.1f}" width="{bw:.1f}" height="{y_lo - y_hi:.1f}" fill="{mf.FORK}"/>')
    n_stem = sum(1 for c in conf if abs(c - 0.510) < 0.0005)
    o.append(mf.txt(ax.px(0.54), ax.py(top * 0.62), f"{n_stem:,} flags at".replace(",", " "),
                    size=7, anchor="start"))
    o.append(mf.txt(ax.px(0.54), ax.py(top * 0.62) + 10, "exactly 0.510,", size=7, anchor="start"))
    o.append(mf.txt(ax.px(0.54), ax.py(top * 0.62) + 20, f"{n_stem / len(conf) * 100:.0f} % of {len(conf):,}".replace(",", " "),
                    size=7, anchor="start"))
    CAPTION.append(f"({L.lower()}) Confidence of every flag in the 180-dataset grid, sativa-epang: "
                   f"{num(n_stem)} of {num(len(conf))} sit at exactly 0.510, the value the scoring rule "
                   "gives a placement on the stem of the declared taxon, and all of them carry exclusion "
                   "at or above 0.99.")
    o += mf.legend(ax.x0 + mf.PW - 118, ax.y0 + 12, [("exclusion >= 0.99", mf.FORK, None),
                                                      ("exclusion < 0.99", LIGHT, None)], size=7.5)
    return w, h, o


def figure2(write=False):
    """The six candidates on one canvas, in the order the paper makes its claims.

    The workflow across the top; the two performance claims side by side; then the evaluation in
    three panels across, FastDup's layout: how flags are counted, the law both tools obey, and the
    one usage instruction. 760 wide, which is a double column, and about 700 tall.
    """
    o = []
    o += fig_1()[2]
    o += fig_2("B", (0, 0, 270, 170, 72, 262))[2]
    o += fig_3("C", (0, 0, 236, 170, 452, 262))[2]
    o += fig_4("D", (0, 0, 180, 150, 58, 512), key=False)[2]
    o += fig_5("E", (0, 0, 180, 150, 318, 512))[2]
    o += fig_6("F", (0, 0, 180, 150, 578, 512))[2]
    if write:
        (OUT / "figure2_values.tsv").write_text("\n".join(VALUES) + "\n")
        kept = [c for c in mf.CAPTION if not c.endswith(") .")]
        (OUT / "figure2_caption.txt").write_text(" ".join(kept + CAPTION) + "\n")
    return canvas(760, 712, o)


def figure3(write=False):
    """The four-panel composition proposed on 2026-10-06, with two corrections.

    A workflow across the top; B and C the two performance claims; then D the flag count on three
    fifths of the width and E the law on the rest. The sketch it answers had no recall curve at all,
    and the law is the paper's detection result, so E stays. The lost baseline flags are hatched on
    the baseline and not on top of the stack. Letters bare and upper-case, mapache's style.
    """
    mf.LABEL_STYLE = "upper"
    o = []
    o += fig_1()[2]
    o += fig_2("B", (0, 0, 270, 158, 72, 232))[2]
    o += fig_3("C", (0, 0, 236, 158, 452, 232))[2]
    o += fig_4b("D", (0, 0, 390, 140, 58, 450))[2]
    o += fig_5("E", (0, 0, 212, 140, 536, 450))[2]
    mf.LABEL_STYLE = "paren-lower"
    if write:
        (OUT / "figure3_values.tsv").write_text("\n".join(VALUES) + "\n")
        kept = [c for c in mf.CAPTION if not c.endswith(") .")]
        (OUT / "figure3_caption.txt").write_text(" ".join(kept + CAPTION) + "\n")
    return canvas(760, 632, o)


if __name__ == "__main__":
    for i, fn in enumerate((fig_1, fig_2, fig_3, fig_4, fig_5, fig_6), 1):
        w, h, body = fn()
        (OUT / f"figure1_{i}.svg").write_text(canvas(w, h, body))
    VALUES[:] = VALUES[:1]
    CAPTION.clear()
    (OUT / "figure2.svg").write_text(figure2(write=True))
    n2 = len(VALUES) - 1
    VALUES[:] = VALUES[:1]
    CAPTION.clear()
    (OUT / "figure3.svg").write_text(figure3(write=True))
    print(f"6 candidates, figure2 ({n2} values) and figure3 ({len(VALUES) - 1} values) written to {OUT}")
