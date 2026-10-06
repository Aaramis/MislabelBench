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


def canvas(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="Helvetica,Arial,sans-serif"><rect width="{w}" height="{h}" fill="#fff"/>'
            + "\n".join(body) + "</svg>\n")


def single(w=400, h=300, pw=280, ph=190, x0=72, y0=40):
    mf.PANELS["A"] = (x0, y0)
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
    body = mf.schematic()
    x, y, w, h = mf.SCHEMATIC
    return canvas(760, 240, body)


# 2. Runtime against peak memory: the plan's "time constrains the original, memory constrains ours".
def fig_2():
    w, h = single(420, 320, 290, 200, 78, 40)
    wall, mem = resource_blocks()
    ax = mf.Ax("A", (5, 6000), (50, 20000), xlog=True, ylog=True)
    o = mf.frame(ax, "A", "", "Runtime (seconds)", "Peak Memory (MB)",
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
        o.append(mf.txt(ax.px(x) - 6, ax.py(y) - 6, f"{n:,}".replace(",", " "), size=7, anchor="end",
                        fill=mf.FORK))
    for n, (x, y) in zip(sizes, up):
        o.append(mf.txt(ax.px(x) + 6, ax.py(y) + 11, f"{n:,}".replace(",", " "), size=7, anchor="start",
                        fill=mf.UP))
    o += mf.legend(ax.x0 + 8, ax.y0 + mf.PH - 24, [("sativa-epang", mf.FORK, None),
                                                     ("SATIVA", mf.UP, mf.COMPARATOR_DASH)], size=8)
    o.append(mf.txt(ax.x0 + mf.PW / 2, h - 6, "one point per reference size, 402 to 7 051 sequences",
                    size=7, fill="#666"))
    return canvas(w, h, o)


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


def fig_3():
    w, h = single(400, 300, 260, 190, 72, 40)
    rows = staged_rows()
    ax = mf.Ax("A", (0, 3), (0, 300))
    o = mf.frame(ax, "A", "", "Placement Shards", "Runtime (seconds)", [], [0, 100, 200, 300])
    bw = 52
    for i, row in enumerate(rows):
        base, cx = 0.0, ax.px(i + 0.5)
        for key, (label, colour) in STAGE.items():
            v = row[key]
            y1, y0 = ax.py(base + v), ax.py(base)
            o.append(f'<rect x="{cx - bw / 2:.1f}" y="{y1:.1f}" width="{bw}" height="{y0 - y1:.1f}" '
                     f'fill="{colour}" stroke="#fff" stroke-width="0.6"/>')
            base += v
        o.append(mf.txt(cx, ax.y0 + mf.PH + 15, row["shards"], size=8))
        o.append(mf.txt(cx, ax.py(base) - 5, f"{base:.0f} s", size=8))
        o.append(mf.txt(cx, ax.py(row["ref"] + row["tasks"] + row["place"] / 2) + 3,
                        f"{row['place']:.0f}", size=7, fill="#fff"))
    lx, ly = ax.x0 + mf.PW + 6, ax.y0 + 8
    for key, (label, colour) in reversed(list(STAGE.items())):
        o.append(f'<rect x="{lx}" y="{ly - 7}" width="10" height="9" fill="{colour}"/>')
        o.append(mf.txt(lx + 14, ly, label, size=7, anchor="start"))
        ly += 13
    o.append(mf.txt(ax.x0 + mf.PW / 2, h - 6, "7 051 sequences, 25 folds, one node per shard, 8 threads",
                    size=7, fill="#666"))
    return canvas(w, h, o)


# 4. How flags are counted, and what it gives, by taxonomic distance of the injected error.
DIST = ["species", "genus", "family", "order", "class", "phylum"]


def fig_4():
    w, h = single(660, 320, 300, 190, 232, 40)
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
    ax = mf.Ax("A", (0, 6), (-25, 160))
    o = mf.frame(ax, "A", "", "Taxonomic Distance of the Injected Error", "Flags per Dataset (mean)",
                 [], [0, 50, 100, 150], yfmt=lambda v: f"{v:g}")
    o.append(f'<line x1="{ax.x0}" y1="{ax.py(0):.1f}" x2="{ax.x0 + mf.PW}" y2="{ax.py(0):.1f}" '
             f'stroke="#444" stroke-width="0.8"/>')
    bw = 30
    for i, d in enumerate(DIST):
        cx = ax.px(i + 0.5)
        found = mean(rec[d]) * mean(by[d]["injected"])
        segs = (("kept", mean(by[d]["kept"]), LIGHT), ("found", found, mf.FORK),
                ("gained", mean(by[d]["gained"]), mf.UP))
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
    lx, ly = ax.x0 + mf.PW + 8, ax.y0 + 10
    for label, colour, dashed in (("baseline flags kept", LIGHT, False), ("injected errors found", mf.FORK, False),
                                  ("collateral flags, with the", mf.UP, False),
                                  ("baseline flags lost", "#fff", True)):
        o.append(f'<rect x="{lx}" y="{ly - 7}" width="10" height="9" fill="{colour}" stroke="{GREY}" '
                 f'stroke-width="0.8"{" stroke-dasharray=\"2 1\"" if dashed else ""}/>')
        o.append(mf.txt(lx + 14, ly, label, size=7, anchor="start"))
        ly += 12
        if label.startswith("collateral"):
            o.append(mf.txt(lx + 14, ly, "share inside a touched clade", size=7, anchor="start"))
            ly += 12
    # The three-box key on the left: what is done, then how each flag is classed.
    bx, by0 = 20, 60
    for i, (lines, fill) in enumerate(((["Inject errors", "at a chosen rank"], "#f0f0f0"),
                                       (["Run both tools", "before and after"], "#e3eef7"),
                                       (["Class every flag:", "kept, lost, found,", "collateral"], "#e8f3e8"))):
        o += mf.box(bx, by0 + i * 62, 150, 48, fill, [(t, "normal", "#000") for t in lines], size=7.5)
        if i < 2:
            o += mf.arrow(bx + 75, by0 + i * 62 + 50, bx + 75, by0 + (i + 1) * 62 - 3)
    return canvas(w, h, o)


# 5. The limit: recall against the share of surviving relatives carrying the wrong label.
def fig_5():
    w, h = single(400, 300, 260, 190, 72, 40)
    ax = mf.Ax("A", (0, 1), (0, 1))
    o = mf.frame(ax, "A", "", "Surviving Relatives Carrying the Wrong Label (%)", "Recall",
                 [], [0, 0.25, 0.5, 0.75, 1], yfmt=lambda v: f"{v:g}")
    for cond, colour, dash in (("epang_T8_K25", mf.FORK, None), ("upstream_raxml_T8", mf.UP, mf.COMPARATOR_DASH)):
        bands = json.loads((ROOT / f"results/detection_law_{cond}.json").read_text())["by_ratio"]
        pts = [((b["low"] + b["high"]) / 2, b["recall"]) for b in bands]
        o += mf.series(ax, pts, colour, dash=dash)
        if cond == "epang_T8_K25":
            for x, y in pts:
                o.append(mf.txt(ax.px(x), ax.py(y) - 8, f"{y:.2f}", size=7, fill=mf.FORK))
    for b in bands:
        x = ax.px((b["low"] + b["high"]) / 2)
        o.append(mf.txt(x, ax.y0 + mf.PH + 15, f"{b['low'] * 100:.0f}-{b['high'] * 100:.0f}", size=7))
    o += mf.legend(ax.x0 + mf.PW - 90, ax.y0 + 12, [("sativa-epang", mf.FORK, None),
                                                     ("SATIVA", mf.UP, mf.COMPARATOR_DASH)], size=8)
    return canvas(w, h, o)


# 6. The confidence histogram: the point mass at 0.510, and the column that explains it.
def fig_6():
    w, h = single(420, 300, 290, 190, 72, 40)
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
    ax = mf.Ax("A", (0.49, 1.01), (0, top * 1.12))
    o = mf.frame(ax, "A", "", "Confidence", "Flags",
                 [0.5, 0.6, 0.7, 0.8, 0.9, 1.0], list(range(0, int(top * 1.12), 4000)),
                 xfmt=lambda v: f"{v:.1f}", yfmt=lambda v: f"{v:,}".replace(",", " "))
    bw = ax.px(0.52) - ax.px(0.50) - 1
    for b, (hi, lo) in sorted(bins.items()):
        x = ax.px(b)
        y_lo, y_hi = ax.py(lo), ax.py(lo + hi)
        o.append(f'<rect x="{x:.1f}" y="{y_lo:.1f}" width="{bw:.1f}" height="{ax.py(0) - y_lo:.1f}" fill="{LIGHT}"/>')
        o.append(f'<rect x="{x:.1f}" y="{y_hi:.1f}" width="{bw:.1f}" height="{y_lo - y_hi:.1f}" fill="{mf.FORK}"/>')
    n_stem = sum(1 for c in conf if abs(c - 0.510) < 0.0005)
    o.append(mf.txt(ax.px(0.53), ax.py(top) + 4, f"{n_stem:,} flags at exactly 0.510,".replace(",", " "),
                    size=7.5, anchor="start"))
    o.append(mf.txt(ax.px(0.53), ax.py(top) + 15, f"{n_stem / len(conf) * 100:.0f} % of {len(conf):,}".replace(",", " "),
                    size=7.5, anchor="start"))
    o += mf.legend(ax.x0 + mf.PW - 118, ax.y0 + 12, [("exclusion >= 0.99", mf.FORK, None),
                                                      ("exclusion < 0.99", LIGHT, None)], size=7.5)
    o.append(mf.txt(ax.x0 + mf.PW / 2, h - 6, "every flag of the 180-dataset grid, sativa-epang",
                    size=7, fill="#666"))
    return canvas(w, h, o)


if __name__ == "__main__":
    for i, fn in enumerate((fig_1, fig_2, fig_3, fig_4, fig_5, fig_6), 1):
        (OUT / f"figure1_{i}.svg").write_text(fn())
    print(f"6 candidates written to {OUT}")
