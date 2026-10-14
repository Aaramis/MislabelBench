#!/usr/bin/env python3
"""Supplement figures drawn in the main figure's style (figure_style.py primitives).

One SVG per figure in results/supplement_figures/, and every number drawn in
results/supplement_figures_values.tsv. Everything is read from committed records.
"""
import json
import random
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_style as mf  # noqa: E402

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
RES = ROOT / "results"
OUT = RES / "supplement_figures"
OUT.mkdir(parents=True, exist_ok=True)
GREY, LIGHT = "#8a8a8a", "#d5d5d5"
VALUES = ["figure\tpanel\tseries\tx\ty"]
mf.LABEL_STYLE = "upper"


def load(name):
    return json.loads((RES / name).read_text())


def canvas(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="Helvetica,Arial,sans-serif"><rect width="{w}" height="{h}" fill="#fff"/>'
            + "\n".join(body) + "</svg>\n")


EP, UPS = "epang_T8_K25", "upstream_raxml_T8"
TOOLS = ((EP, "SATIVA-epang", mf.FORK), (UPS, "SATIVA", mf.UP))


def MEAN(v):
    return sum(v) / len(v)


def paired_stats():
    """results/paired_stats.tsv by family, written by paired_stats.py."""
    rows = (RES / "paired_stats.tsv").read_text().splitlines()
    head = rows[0].split("\t")
    return {r.split("\t")[0]: dict(zip(head, r.split("\t"))) for r in rows[1:]}


def flagged(path):
    return {l.split("\t")[0] for l in path.read_text(errors="replace").splitlines()
            if l.strip() and not l.startswith(";")}



def grid(tool):
    """One recall per dataset (distance, k, rate, seed) at confidence zero."""
    out = []
    for score in sorted((RES / "grid_fork/runs").glob(f"*__{tool}__rep1/score.json")):
        s = json.loads(score.read_text())
        row = next(r for r in s["by_confidence"] if r["threshold"] == 0.0)
        out.append({"distance": s["distance"], "k": s["k"], "rate": s["rate"], "seed": s["seed"],
                    "name": score.parent.name.split("__")[0], "recall": row["recall"]})
    return out


def per_dataset(root_dir, data_dir, tool):
    out = []
    for truth in sorted((ROOT / data_dir).glob("*/*.truth.json")):
        name = truth.parent.name
        run = RES / root_dir / "runs" / f"{name}__{tool}__rep1"
        mis = run / f"{name}__{tool}__rep1.mis"
        if mis.exists():
            t = json.loads(truth.read_text())
            out.append(len(flagged(mis) & set(t["injected"])) / len(t["injected"]))
    return out


def clade_cells(tool):
    cells = {}
    for c in load(f"clade_detection_{tool}.json")["per_clade"]:
        d, n = cells.setdefault(c["cell"], [0, 0]), c
        d[0] += c["detected"]
        d[1] += c["size"]
    return [d / n for d, n in cells.values()]


def iqr(vals):
    q = st.quantiles(vals, n=4, method="inclusive")
    return q[0], q[2]


def dots(px, cy, vals, colour, rng, spread=3.6, r=1.9):
    return [f'<circle cx="{px(v):.1f}" cy="{cy + rng.uniform(-spread, spread):.1f}" r="{r}" '
            f'fill="{colour}" fill-opacity="0.6" stroke="#fff" stroke-width="0.35"/>' for v in vals]


def diamond(x, y, colour, r=4.6):
    return (f'<path d="M{x:.1f},{y - r:.1f} L{x + r:.1f},{y:.1f} L{x:.1f},{y + r:.1f} L{x - r:.1f},{y:.1f} Z" '
            f'fill="{colour}" stroke="#fff" stroke-width="1.1"/>')


def dot_legend(x, y, entries, size=8):
    """entries are (label, colour, shape, x offset)."""
    o = []
    for label, colour, shape, dx in entries:
        cx = x + dx
        if shape == "diamond":
            o.append(diamond(cx, y, colour, 4.2))
        elif shape == "bar":
            o.append(f'<line x1="{cx - 6}" y1="{y}" x2="{cx + 6}" y2="{y}" stroke="{colour}" '
                     f'stroke-width="7" stroke-linecap="round"/>')
        else:
            o.append(f'<circle cx="{cx}" cy="{y}" r="3.2" fill="{colour}" fill-opacity="0.75"/>')
        o.append(mf.txt(cx + (12 if shape == "bar" else 8), y + 3, label, size=size, anchor="start"))
    return o


def box(x, y, w, h):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="#444" stroke-width="0.8"/>')


def fig_kinds():
    rng = random.Random(7)
    g = {t: grid(t) for t, _, _ in TOOLS}
    rows = [("Sequence from another domain",
             {t: per_dataset("foreign", "data/foreign", t) for t, _, _ in TOOLS}),
            ("Single mislabelled sequence",
             {t: [r["recall"] for r in g[t] if r["k"] == 1] for t, _, _ in TOOLS}),
            ("Right genus, wrong species",
             {t: [r["recall"] for r in g[t] if r["distance"] == "species"] for t, _, _ in TOOLS}),
            ("Lineage stopping early",
             {t: per_dataset("ragged", "data/ragged", t) for t, _, _ in TOOLS}),
            ("Whole taxon misnamed", {t: clade_cells(t) for t, _, _ in TOOLS}),
            ("Chimeras", {t: per_dataset("chimera", "data/chimera", t) for t, _, _ in TOOLS})]
    stats = paired_stats()
    stat_name = {"Single mislabelled sequence": "Single mislabelled sequence (k = 1)", "Chimeras": "Chimeras, all"}
    w, x0, pw, y0, pitch = 960, 210, 300, 56, 46
    fx0, fpw = x0 + pw + 40, 130
    fx = lambda v: fx0 + (v + 0.04) / 0.18 * fpw
    h = y0 + pitch * len(rows) + 52
    px = lambda v: x0 + (v + 0.035) / 1.07 * pw
    o = [f'<rect x="{x0}" y="{y0}" width="{pw}" height="{pitch * len(rows)}" fill="#fafafa"/>']
    for v in (0, 0.25, 0.5, 0.75, 1):
        o.append(f'<line x1="{px(v):.1f}" y1="{y0}" x2="{px(v):.1f}" y2="{y0 + pitch * len(rows)}" '
                 f'stroke="#e4e4e4" stroke-width="0.6"/>')
        o.append(f'<line x1="{px(v):.1f}" y1="{y0 + pitch * len(rows)}" x2="{px(v):.1f}" '
                 f'y2="{y0 + pitch * len(rows) + 4}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(px(v), y0 + pitch * len(rows) + 16, f"{v:g}", size=8))
    o.append(f'<rect x="{fx0}" y="{y0}" width="{fpw}" height="{pitch * len(rows)}" fill="#fafafa"/>')
    for v in (0.05, 0.1):
        o.append(f'<line x1="{fx(v):.1f}" y1="{y0}" x2="{fx(v):.1f}" y2="{y0 + pitch * len(rows)}" stroke="#e4e4e4" stroke-width="0.6"/>')
    for i in range(1, len(rows)):
        o.append(f'<line x1="{fx0}" y1="{y0 + pitch * i}" x2="{fx0 + fpw}" y2="{y0 + pitch * i}" stroke="#d5d5d5" stroke-width="0.6"/>')
    o.append(f'<line x1="{fx(0):.1f}" y1="{y0}" x2="{fx(0):.1f}" y2="{y0 + pitch * len(rows)}" stroke="#666" stroke-width="0.9" stroke-dasharray="3 2"/>')
    for v, lab in ((0, "0"), (0.1, "0.10")):
        o.append(f'<line x1="{fx(v):.1f}" y1="{y0 + pitch * len(rows)}" x2="{fx(v):.1f}" y2="{y0 + pitch * len(rows) + 4}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(fx(v), y0 + pitch * len(rows) + 16, lab, size=8))
    for i, (name, vals) in enumerate(rows):
        yc = y0 + pitch * i + pitch / 2
        if i:
            o.append(f'<line x1="{x0}" y1="{y0 + pitch * i}" x2="{x0 + pw}" y2="{y0 + pitch * i}" '
                     f'stroke="#d5d5d5" stroke-width="0.6"/>')
        o.append(mf.txt(x0 - 10, yc - 2, name, size=8, anchor="end"))
        o.append(mf.txt(x0 - 10, yc + 9, f"{len(vals[EP])} datasets", size=6.6, anchor="end", fill="#777"))
        st_ = stats[stat_name.get(name, name)]
        m, lo_, hi_ = (float(st_[k]) for k in ("mean_diff", "ci_low", "ci_high"))
        o.append(f'<line x1="{fx(lo_):.1f}" y1="{yc:.1f}" x2="{fx(hi_):.1f}" y2="{yc:.1f}" stroke="#222" stroke-width="1.3"/>')
        for e in (lo_, hi_):
            o.append(f'<line x1="{fx(e):.1f}" y1="{yc - 4:.1f}" x2="{fx(e):.1f}" y2="{yc + 4:.1f}" stroke="#222" stroke-width="1.3"/>')
        o.append(f'<circle cx="{fx(m):.1f}" cy="{yc:.1f}" r="3.4" fill="#222"/>')
        o.append(mf.txt(fx0 + fpw + 72, yc + 3, f"{st_['epang_better']} / {st_['sativa_better']} / {st_['ties']}", size=8))
        ph = float(st_["wilcoxon_p_holm"])
        ptxt = "n.s." if ph >= 0.05 else (f"{ph:.2g}" if ph >= 0.001 else "< 0.001")
        o.append(mf.txt(fx0 + fpw + 178, yc + 3, ptxt, size=8, fill="#111" if ph < 0.05 else "#888"))
        VALUES.append(f"kinds\tgain\t{name} | mean, ci low, ci high, p\t{st_['mean_diff']}\t{st_['ci_low']}\t{st_['ci_high']}\t{st_['wilcoxon_p']}")
        for (t, label, colour), up in zip(TOOLS, (True, False)):
            v = vals[t]
            band = yc - 6 if up else yc + 6
            q1, q3 = iqr(v)
            o.append(f'<line x1="{px(q1):.1f}" y1="{band:.1f}" x2="{px(q3):.1f}" y2="{band:.1f}" '
                     f'stroke="{colour}" stroke-opacity="0.22" stroke-width="9" stroke-linecap="round"/>')
            o += dots(px, band, v, colour, rng)
            o.append(diamond(px(MEAN(v)), band, colour))
            VALUES.append(f"kinds\tA\t{label} | {name} | mean\t{MEAN(v):.4f}\t{len(v)}")
    o.append(box(x0, y0, pw, pitch * len(rows)))
    o.append(box(fx0, y0, fpw, pitch * len(rows)))
    o.append(mf.txt(fx0 + fpw / 2, y0 + pitch * len(rows) + 38, "Gain of SATIVA-epang", size=9.5))
    o.append(mf.txt(fx0 + fpw / 2, y0 - 10, "mean and 95 % interval", size=7.5, fill="#555"))
    for cx, l1, l2 in ((fx0 + fpw + 72, "better / worse / tie", "(number of datasets)"),
                       (fx0 + fpw + 178, "adjusted p", "(Holm)")):
        o.append(mf.txt(cx, y0 - 22, l1, size=7.5, fill="#555"))
        o.append(mf.txt(cx, y0 - 11, l2, size=7, fill="#777"))
    o.append(f'<line x1="{fx0 + fpw + 20}" y1="{y0 - 28}" x2="{fx0 + fpw + 20}" y2="{y0 + pitch * len(rows)}" '
             f'stroke="#e4e4e4" stroke-width="0.8"/>')
    o.append(mf.txt(x0 + pw / 2, y0 + pitch * len(rows) + 38, "Recall (share of injected errors found)", size=9.5))
    o += dot_legend(x0 - 130, 22, [("SATIVA-epang", mf.FORK, "dot", 0), ("SATIVA", mf.UP, "dot", 100),
                                   ("mean", "#666", "diamond", 170), ("middle half of the datasets", "#bbb", "bar", 230)])
    return canvas(w, h, o)


def fig_chimera():
    w, h = 660, 272
    cw, ch = 60, 40
    names = [("genus", "Genus"), ("family", "Family"), ("order", "Order"), ("phylum", "Phylum")]
    cuts = [0.25, 0.5, 0.75]
    o = []
    for letter, tool, title, colour, ox in (("A", EP, "SATIVA-epang", mf.FORK, 110),
                                            ("B", UPS, "SATIVA", mf.UP, 385)):
        data = {(r["distance"], r["breakpoint"]): r["detected"] / r["injected"]
                for r in load(f"chimera_detection_{tool}.json")["rows"]}
        oy = 64
        o.append(mf.txt(ox - 44 if letter == "A" else ox - 22, 24, letter, size=12, anchor="start", weight="bold"))
        o.append(mf.txt(ox + cw * 1.5, 40, title, size=10, weight="bold", fill=colour))
        for j, c in enumerate(cuts):
            o.append(mf.txt(ox + j * cw + cw / 2, oy - 6, f"{c:g}", size=8))
        for i, (d, label) in enumerate(names):
            if letter == "A":
                o.append(mf.txt(ox - 8, oy + i * ch + ch / 2 + 3, label, size=8, anchor="end"))
            for j, c in enumerate(cuts):
                v = data[(d, c)]
                x, y = ox + j * cw, oy + i * ch
                o.append(f'<rect x="{x}" y="{y}" width="{cw - 2}" height="{ch - 2}" fill="{colour}" '
                         f'fill-opacity="{0.06 + 0.94 * v:.2f}" stroke="#444" stroke-width="0.5"/>')
                o.append(mf.txt(x + cw / 2 - 1, y + ch / 2 + 2, f"{round(v * 100)}%", size=8.5,
                                fill="#fff" if v > 0.5 else "#000"))
                VALUES.append(f"chimera\t{letter}\t{title} | {names[i][1]}\t{c}\t{v:.4f}")
    o.append(mf.txt(337, 64 + 4 * 40 + 30, "Share of the sequence from the labelled parent", size=9))
    o.append(mf.txt(44, 64 + 2 * 40, "How far apart the parents are", size=9, rot=-90))
    return canvas(w, h, o)



def fig_k():
    rng = random.Random(11)
    stats = paired_stats()
    g = {t: grid(t) for t, _, _ in TOOLS}
    ks = [1, 2, 3, 5, 10]
    w, h = 830, 330
    pa = dict(x0=62, pw=340, y0=56, ph=210)
    pb = dict(x0=470, pw=330, y0=56, ph=210)
    o = []
    for p, letter in ((pa, "A"), (pb, "B")):
        o.append(mf.txt(p["x0"] - 46, 30, letter, size=12, anchor="start", weight="bold"))
    # panel A: recall of each tool, one dot per dataset, side by side at each k
    py = lambda v: pa["y0"] + pa["ph"] - (v + 0.04) / 1.08 * pa["ph"]
    cx = lambda i: pa["x0"] + pa["pw"] * (i + 0.5) / len(ks)
    o.append(f'<rect x="{pa["x0"]}" y="{pa["y0"]}" width="{pa["pw"]}" height="{pa["ph"]}" fill="#fafafa"/>')
    for v in (0, 0.25, 0.5, 0.75, 1):
        o.append(f'<line x1="{pa["x0"]}" y1="{py(v):.1f}" x2="{pa["x0"] + pa["pw"]}" y2="{py(v):.1f}" '
                 f'stroke="#e4e4e4" stroke-width="0.6"/>')
        o.append(f'<line x1="{pa["x0"] - 4}" y1="{py(v):.1f}" x2="{pa["x0"]}" y2="{py(v):.1f}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(pa["x0"] - 7, py(v) + 3, f"{v:g}", size=8, anchor="end"))
    off = 17
    for i in range(len(ks)):
        bx = pa["x0"] + pa["pw"] * i / len(ks)
        if i % 2:
            o.append(f'<rect x="{bx:.1f}" y="{pa["y0"]}" width="{pa["pw"] / len(ks):.1f}" height="{pa["ph"]}" fill="#efefef"/>')
        if i:
            o.append(f'<line x1="{bx:.1f}" y1="{pa["y0"]}" x2="{bx:.1f}" y2="{pa["y0"] + pa["ph"]}" stroke="#cfcfcf" stroke-width="0.8"/>')
    means = {t: [] for t, _, _ in TOOLS}
    for i, k in enumerate(ks):
        o.append(f'<line x1="{cx(i):.1f}" y1="{pa["y0"] + pa["ph"]}" x2="{cx(i):.1f}" y2="{pa["y0"] + pa["ph"] + 4}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(cx(i), pa["y0"] + pa["ph"] + 16, str(k), size=8))
        for (t, label, colour), sgn in zip(TOOLS, (1, -1)):
            v = [r["recall"] for r in g[t] if r["k"] == k]
            means[t].append((cx(i) + sgn * off, py(MEAN(v))))
            xc = cx(i) + sgn * off
            q1, q3 = iqr(v)
            o.append(f'<line x1="{xc:.1f}" y1="{py(q1):.1f}" x2="{xc:.1f}" y2="{py(q3):.1f}" stroke="{colour}" '
                     f'stroke-opacity="0.22" stroke-width="12" stroke-linecap="round"/>')
            for val in v:
                o.append(f'<circle cx="{xc + rng.uniform(-5, 5):.1f}" cy="{py(val):.1f}" r="1.8" '
                         f'fill="{colour}" fill-opacity="0.55" stroke="#fff" stroke-width="0.3"/>')
            VALUES.append(f"recall_by_k\tA\t{label}\t{k}\t{MEAN(v):.4f}")
    for (t, label, colour), dash in zip(TOOLS, (None, mf.COMPARATOR_DASH)):
        pts = means[t]
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        o.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.4"'
                 + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
        for x, y in pts:
            o.append(diamond(x, y, colour, 4.2))
    o.append(box(pa["x0"], pa["y0"], pa["pw"], pa["ph"]))
    o.append(mf.txt(pa["x0"] + pa["pw"] / 2, pa["y0"] + pa["ph"] + 36, "k (sequences per wrong label)", size=9.5))
    o.append(mf.txt(pa["x0"] - 38, pa["y0"] + pa["ph"] / 2, "Recall", size=9.5, rot=-90))
    # panel B: the same datasets, paired. One dot is epang minus SATIVA on one dataset.
    lo, hi, band = -0.2, 0.6, 50
    qy = lambda v: pb["y0"] + pb["ph"] - (v - lo) / (hi - lo) * (pb["ph"] - band)
    qx = lambda i: pb["x0"] + pb["pw"] * (i + 0.5) / len(ks)
    o.append(f'<rect x="{pb["x0"]}" y="{pb["y0"]}" width="{pb["pw"]}" height="{pb["ph"]}" fill="#fafafa"/>')
    for i in range(len(ks)):
        bx = pb["x0"] + pb["pw"] * i / len(ks)
        if i % 2:
            o.append(f'<rect x="{bx:.1f}" y="{pb["y0"]}" width="{pb["pw"] / len(ks):.1f}" height="{pb["ph"]}" fill="#efefef"/>')
        if i:
            o.append(f'<line x1="{bx:.1f}" y1="{pb["y0"]}" x2="{bx:.1f}" y2="{pb["y0"] + pb["ph"]}" stroke="#cfcfcf" stroke-width="0.8"/>')
    for v in (-0.2, 0, 0.2, 0.4, 0.6):
        o.append(f'<line x1="{pb["x0"]}" y1="{qy(v):.1f}" x2="{pb["x0"] + pb["pw"]}" y2="{qy(v):.1f}" '
                 f'stroke="{"#666" if v == 0 else "#e4e4e4"}" stroke-width="{0.9 if v == 0 else 0.6}"/>')
        o.append(f'<line x1="{pb["x0"] - 4}" y1="{qy(v):.1f}" x2="{pb["x0"]}" y2="{qy(v):.1f}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(pb["x0"] - 7, qy(v) + 3, f"{v:+g}" if v else "0", size=8, anchor="end"))
    for i, k in enumerate(ks):
        ep = {r["name"]: r["recall"] for r in g[EP] if r["k"] == k}
        up = {r["name"]: r["recall"] for r in g[UPS] if r["k"] == k}
        diff = [ep[n] - up[n] for n in sorted(ep)]
        o.append(f'<line x1="{qx(i):.1f}" y1="{pb["y0"] + pb["ph"]}" x2="{qx(i):.1f}" y2="{pb["y0"] + pb["ph"] + 4}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(qx(i), pb["y0"] + pb["ph"] + 16, str(k), size=8))
        for dv in diff:
            c = mf.FORK if dv > 1e-9 else mf.UP if dv < -1e-9 else "#9a9a9a"
            o.append(f'<circle cx="{qx(i) + rng.uniform(-13, 13):.1f}" cy="{qy(dv):.1f}" r="1.9" fill="{c}" '
                     f'fill-opacity="0.6" stroke="#fff" stroke-width="0.3"/>')
        o.append(f'<line x1="{qx(i) - 17:.1f}" y1="{qy(MEAN(diff)):.1f}" x2="{qx(i) + 17:.1f}" y2="{qy(MEAN(diff)):.1f}" '
                 f'stroke="#222" stroke-width="2"/>')
        sk = stats[f"Recall by k, k = {k}"]
        lo_, hi_ = float(sk["ci_low"]), float(sk["ci_high"])
        o.append(f'<line x1="{qx(i):.1f}" y1="{qy(lo_):.1f}" x2="{qx(i):.1f}" y2="{qy(hi_):.1f}" stroke="#222" stroke-width="1.1"/>')
        for e in (lo_, hi_):
            o.append(f'<line x1="{qx(i) - 5:.1f}" y1="{qy(e):.1f}" x2="{qx(i) + 5:.1f}" y2="{qy(e):.1f}" stroke="#222" stroke-width="1.1"/>')
        VALUES.append(f"recall_by_k\tB\tci low, ci high\t{k}\t{lo_:.4f}\t{hi_:.4f}")
        VALUES.append(f"recall_by_k\tB\tmean difference\t{k}\t{MEAN(diff):.4f}")
        o.append(mf.txt(qx(i), pb["y0"] + 16, f"{MEAN(diff):+.3f}", size=8, weight="bold"))
        nb, nw = sum(d > 1e-9 for d in diff), sum(d < -1e-9 for d in diff)
        parts = ((nb, mf.FORK), (nw, mf.UP), (len(diff) - nb - nw, "#8a8a8a"))
        tsp = '<tspan fill="#888"> / </tspan>'.join(f'<tspan fill="{c}">{n}</tspan>' for n, c in parts)
        o.append(f'<text x="{qx(i):.1f}" y="{pb["y0"] + 31:.1f}" font-size="{7.5 * mf.FONT_SCALE:.1f}" '
                 f'text-anchor="middle">{tsp}</text>')
        ph = float(sk["wilcoxon_p_holm"])
        o.append(mf.txt(qx(i), pb["y0"] + 46, "n.s." if ph >= 0.05 else "p < 0.001" if ph < 0.001 else f"p = {ph:.2g}",
                        size=7.5, fill="#111" if ph < 0.05 else "#888"))
        if i == 0:
            o.append(f'<line x1="{pb["x0"]}" y1="{pb["y0"] + band}" x2="{pb["x0"] + pb["pw"]}" y2="{pb["y0"] + band}" '
                     f'stroke="#cfcfcf" stroke-width="0.8"/>')
    o.append(box(pb["x0"], pb["y0"], pb["pw"], pb["ph"]))
    o.append(mf.txt(pb["x0"] + pb["pw"] / 2, pb["y0"] + pb["ph"] + 36, "k (sequences per wrong label)", size=9.5))
    o.append(mf.txt(pb["x0"] - 38, pb["y0"] + pb["ph"] / 2, "Recall gain of SATIVA-epang", size=9.5, rot=-90))
    o += dot_legend(pa["x0"], 26, [("SATIVA-epang", mf.FORK, "dot", 0), ("SATIVA", mf.UP, "dot", 100),
                                   ("mean", "#666", "diamond", 170)])
    o += dot_legend(pb["x0"] + 4, 26, [("epang better", mf.FORK, "dot", 0), ("SATIVA better", mf.UP, "dot", 82),
                                   ("tie", "#9a9a9a", "dot", 172)], size=7.5)
    return canvas(w, h, o)


def fig_simulated():
    rng = random.Random(5)
    data = {}
    for t, _, _ in TOOLS:
        for score in sorted((RES / "grove_simulated/runs").glob(f"*__{t}__rep1/score.json")):
            sc = json.loads(score.read_text())
            for r in sc["by_confidence"]:
                if r["threshold"] in (0.0, 0.511):
                    data.setdefault((t, r["threshold"], sc["distance"], sc["k"]), []).append(r["recall"])
    ks, dists = [1, 2, 3, 5], ["family", "genus", "species"]
    thr = [(0.0, "no confidence threshold"), (0.511, "threshold 0.511")]
    pw, ph, gx, gy = 150, 100, 26, 44
    x0, y0 = 70, 52
    w, h = x0 + 3 * pw + 2 * gx + 20, y0 + 2 * ph + gy + 52
    px = lambda i, c: x0 + c * (pw + gx) + pw * (i + 0.5) / len(ks)
    py = lambda v, r: y0 + r * (ph + gy) + ph - (v + 0.04) / 1.08 * ph
    o = []
    for r, (tv, tl) in enumerate(thr):
        for c, dist in enumerate(dists):
            bx, by = x0 + c * (pw + gx), y0 + r * (ph + gy)
            o.append(f'<rect x="{bx}" y="{by}" width="{pw}" height="{ph}" fill="#fafafa"/>')
            for v in (0, 0.5, 1):
                o.append(f'<line x1="{bx}" y1="{py(v, r):.1f}" x2="{bx + pw}" y2="{py(v, r):.1f}" stroke="#e4e4e4" stroke-width="0.6"/>')
                if c == 0:
                    o.append(f'<line x1="{bx - 4}" y1="{py(v, r):.1f}" x2="{bx}" y2="{py(v, r):.1f}" stroke="#444" stroke-width="0.8"/>')
                    o.append(mf.txt(bx - 7, py(v, r) + 3, f"{v:g}", size=8, anchor="end"))
            for i in range(len(ks)):
                cxb = bx + pw * i / len(ks)
                if i % 2:
                    o.append(f'<rect x="{cxb:.1f}" y="{by}" width="{pw / len(ks):.1f}" height="{ph}" fill="#efefef"/>')
                if i:
                    o.append(f'<line x1="{cxb:.1f}" y1="{by}" x2="{cxb:.1f}" y2="{by + ph}" stroke="#cfcfcf" stroke-width="0.8"/>')
            means = {}
            for (t, label, colour), sgn in zip(TOOLS, (1, -1)):
                pts = []
                for i, k in enumerate(ks):
                    v = data[(t, tv, dist, k)]
                    xc = px(i, c) + sgn * 8
                    for val in v:
                        o.append(f'<circle cx="{xc + rng.uniform(-3, 3):.1f}" cy="{py(val, r):.1f}" r="1.9" fill="{colour}" fill-opacity="0.55" stroke="#fff" stroke-width="0.3"/>')
                    pts.append((xc, py(MEAN(v), r)))
                    VALUES.append(f"simulated\t{tl} | {dist}\t{label} | k={k}\t{MEAN(v):.4f}")
                means[t] = pts
            for (t, label, colour), dash in zip(TOOLS, (None, mf.COMPARATOR_DASH)):
                d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in means[t])
                o.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.3"' + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
                for x, y in means[t]:
                    o.append(diamond(x, y, colour, 3.6))
            o.append(box(bx, by, pw, ph))
            for i, k in enumerate(ks):
                o.append(f'<line x1="{px(i, c):.1f}" y1="{by + ph}" x2="{px(i, c):.1f}" y2="{by + ph + 4}" stroke="#444" stroke-width="0.8"/>')
                if r == 1:
                    o.append(mf.txt(px(i, c), by + ph + 16, str(k), size=8))
            if r == 0:
                o.append(mf.txt(bx + pw / 2, by - 8, f"different {dist}", size=8.5))
        o.append(mf.txt(26, y0 + r * (ph + gy) + ph / 2, tl, size=8, rot=-90))
    o.append(mf.txt(x0 + (3 * pw + 2 * gx) / 2, h - 12, "k (sequences per wrong label)", size=9.5))
    o += dot_legend(x0, 22, [("SATIVA-epang", mf.FORK, "dot", 0), ("SATIVA", mf.UP, "dot", 100),
                             ("mean of three seeds", "#666", "diamond", 170)])
    return canvas(w, h, o)


def fig_bacterial():
    rng = random.Random(7)
    ks = [1, 2, 3, 5, 10]
    g = {t: {} for t, _, _ in TOOLS}
    for t, _, _ in TOOLS:
        for score in sorted((RES / "grid_bac/runs").glob(f"*__{t}__rep1/score.json")):
            sc = json.loads(score.read_text())
            g[t][score.parent.name.split("__")[0]] = (sc["k"], next(
                r["recall"] for r in sc["by_confidence"] if r["threshold"] == 0.0))
    arch = {t: grid(t) for t, _, _ in TOOLS}
    w, h = 830, 330
    pa, pb = dict(x0=62, pw=340, y0=56, ph=210), dict(x0=470, pw=330, y0=56, ph=210)
    o = [mf.txt(p["x0"] - 46, 30, c, size=12, anchor="start", weight="bold") for p, c in ((pa, "A"), (pb, "B"))]

    def frame(p, ticks, y, fmt):
        o.append(f'<rect x="{p["x0"]}" y="{p["y0"]}" width="{p["pw"]}" height="{p["ph"]}" fill="#fafafa"/>')
        for i in range(len(ks)):
            bx = p["x0"] + p["pw"] * i / len(ks)
            if i % 2:
                o.append(f'<rect x="{bx:.1f}" y="{p["y0"]}" width="{p["pw"] / len(ks):.1f}" height="{p["ph"]}" fill="#efefef"/>')
            if i:
                o.append(f'<line x1="{bx:.1f}" y1="{p["y0"]}" x2="{bx:.1f}" y2="{p["y0"] + p["ph"]}" stroke="#cfcfcf" stroke-width="0.8"/>')
            xc = p["x0"] + p["pw"] * (i + 0.5) / len(ks)
            o.append(f'<line x1="{xc:.1f}" y1="{p["y0"] + p["ph"]}" x2="{xc:.1f}" y2="{p["y0"] + p["ph"] + 4}" stroke="#444" stroke-width="0.8"/>')
            o.append(mf.txt(xc, p["y0"] + p["ph"] + 16, str(ks[i]), size=8))
        for v in ticks:
            o.append(f'<line x1="{p["x0"]}" y1="{y(v):.1f}" x2="{p["x0"] + p["pw"]}" y2="{y(v):.1f}" '
                     f'stroke="{"#666" if v == 0 and p is pb else "#e4e4e4"}" stroke-width="0.6"/>')
            o.append(f'<line x1="{p["x0"] - 4}" y1="{y(v):.1f}" x2="{p["x0"]}" y2="{y(v):.1f}" stroke="#444" stroke-width="0.8"/>')
            o.append(mf.txt(p["x0"] - 7, y(v) + 3, fmt(v), size=8, anchor="end"))
        o.append(mf.txt(p["x0"] + p["pw"] / 2, p["y0"] + p["ph"] + 36, "k (sequences per wrong label)", size=9.5))

    cx = lambda p, i: p["x0"] + p["pw"] * (i + 0.5) / len(ks)
    ya = lambda v: pa["y0"] + pa["ph"] - (v + 0.04) / 1.08 * pa["ph"]
    frame(pa, (0, 0.25, 0.5, 0.75, 1), ya, lambda v: f"{v:g}")
    means = {t: [] for t, _, _ in TOOLS}
    for i, k in enumerate(ks):
        for (t, label, colour), sgn in zip(TOOLS, (1, -1)):
            v = [r for kk, r in g[t].values() if kk == k]
            xc = cx(pa, i) + sgn * 17
            means[t].append((xc, ya(MEAN(v))))
            for val in v:
                o.append(f'<circle cx="{xc + rng.uniform(-5, 5):.1f}" cy="{ya(val):.1f}" r="1.9" fill="{colour}" '
                         f'fill-opacity="0.6" stroke="#fff" stroke-width="0.3"/>')
            VALUES.append(f"bacterial\tA\t{label}\t{k}\t{MEAN(v):.4f}")
    for (t, label, colour), dash in zip(TOOLS, (None, mf.COMPARATOR_DASH)):
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in means[t])
        o.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.4"' + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
        o += [diamond(x, y, colour, 4.2) for x, y in means[t]]
    o.append(box(pa["x0"], pa["y0"], pa["pw"], pa["ph"]))
    o.append(mf.txt(pa["x0"] - 38, pa["y0"] + pa["ph"] / 2, "Recall", size=9.5, rot=-90))

    lo, hi, band = -0.2, 0.6, 40
    yb = lambda v: pb["y0"] + pb["ph"] - (v - lo) / (hi - lo) * (pb["ph"] - band)
    frame(pb, (-0.2, 0, 0.2, 0.4, 0.6), yb, lambda v: f"{v:+g}" if v else "0")
    o.append(f'<line x1="{pb["x0"]}" y1="{pb["y0"] + band}" x2="{pb["x0"] + pb["pw"]}" y2="{pb["y0"] + band}" stroke="#cfcfcf" stroke-width="0.8"/>')
    for i, k in enumerate(ks):
        diff = [g[EP][n][1] - g[UPS][n][1] for n in sorted(g[EP]) if g[EP][n][0] == k]
        for dv in diff:
            c = mf.FORK if dv > 1e-9 else mf.UP if dv < -1e-9 else "#9a9a9a"
            o.append(f'<circle cx="{cx(pb, i) + rng.uniform(-13, 13):.1f}" cy="{yb(dv):.1f}" r="1.9" fill="{c}" '
                     f'fill-opacity="0.6" stroke="#fff" stroke-width="0.3"/>')
        o.append(f'<line x1="{cx(pb, i) - 17:.1f}" y1="{yb(MEAN(diff)):.1f}" x2="{cx(pb, i) + 17:.1f}" y2="{yb(MEAN(diff)):.1f}" stroke="#222" stroke-width="2"/>')
        ref = MEAN([a["recall"] - b["recall"] for a in arch[EP] for b in arch[UPS] if a["name"] == b["name"] and a["k"] == k])
        o.append(f'<circle cx="{cx(pb, i) + 24:.1f}" cy="{yb(ref):.1f}" r="3.6" fill="#fff" stroke="#444" stroke-width="1.1"/>')
        VALUES.append(f"bacterial\tB\tmean difference | archaea mean difference\t{k}\t{MEAN(diff):.4f}\t{ref:.4f}")
        o.append(mf.txt(cx(pb, i), pb["y0"] + 16, f"{MEAN(diff):+.3f}", size=8, weight="bold"))
        nb, nw = sum(d > 1e-9 for d in diff), sum(d < -1e-9 for d in diff)
        parts = ((nb, mf.FORK), (nw, mf.UP), (len(diff) - nb - nw, "#8a8a8a"))
        tsp = '<tspan fill="#888"> / </tspan>'.join(f'<tspan fill="{c}">{n}</tspan>' for n, c in parts)
        o.append(f'<text x="{cx(pb, i):.1f}" y="{pb["y0"] + 31:.1f}" font-size="{7.5 * mf.FONT_SCALE:.1f}" text-anchor="middle">{tsp}</text>')
    o.append(box(pb["x0"], pb["y0"], pb["pw"], pb["ph"]))
    o.append(mf.txt(pb["x0"] - 38, pb["y0"] + pb["ph"] / 2, "Recall gain", size=9.5, rot=-90))
    o += dot_legend(pa["x0"], 26, [("SATIVA-epang", mf.FORK, "dot", 0), ("SATIVA", mf.UP, "dot", 100), ("mean", "#666", "diamond", 170)])
    o += dot_legend(pb["x0"] + 4, 26, [("epang better", mf.FORK, "dot", 0), ("SATIVA better", mf.UP, "dot", 82), ("tie", "#9a9a9a", "dot", 172)], size=7.5)
    o.append(f'<circle cx="{pb["x0"] + 236}" cy="26" r="3.6" fill="#fff" stroke="#444" stroke-width="1.1"/>')
    o.append(mf.txt(pb["x0"] + 244, 29, "archaea, mean", size=7.5, anchor="start"))
    return canvas(w, h, o)


def fig_distance():
    sec = (RES / "upset_tables.txt").read_text().split("confidence >= 0.511")[1].splitlines()
    head = next(l for l in sec if l.startswith("group")).split("\t")
    rows = {l.split("\t")[0]: dict(zip(head, l.split("\t"))) for l in sec if l.startswith("r0.05_")}
    dists = ["species", "genus", "family", "order", "class", "phylum"]

    def f(d, key):
        return float(rows[f"r0.05_{d}"][key])

    # keys read as SATIVA flag / SATIVA-epang flag
    series = {
        "found": {EP: [100 * (f(d, "injected/1/1") + f(d, "injected/0/1")) / f(d, "injected") for d in dists],
                  UPS: [100 * (f(d, "injected/1/1") + f(d, "injected/1/0")) / f(d, "injected") for d in dists]},
        "collateral": {EP: [f(d, "collateral/1/1") + f(d, "collateral/0/1") for d in dists],
                       UPS: [f(d, "collateral/1/1") + f(d, "collateral/1/0") for d in dists]},
    }
    w, h = 830, 330
    pa, pb = dict(x0=62, pw=340, y0=56, ph=210), dict(x0=470, pw=330, y0=56, ph=210)
    o = [mf.txt(p["x0"] - 46, 30, c, size=12, anchor="start", weight="bold") for p, c in ((pa, "A"), (pb, "B"))]
    n = len(dists)
    for p, key, top, ticks, label in ((pa, "found", 60, (0, 20, 40, 60), "Wrong labels found (%)"),
                                     (pb, "collateral", 40, (0, 10, 20, 30, 40), "Collateral flags per dataset")):
        y = lambda v: p["y0"] + p["ph"] - v / top * p["ph"]
        o.append(f'<rect x="{p["x0"]}" y="{p["y0"]}" width="{p["pw"]}" height="{p["ph"]}" fill="#fafafa"/>')
        for i, d in enumerate(dists):
            bx = p["x0"] + p["pw"] * i / n
            if i % 2:
                o.append(f'<rect x="{bx:.1f}" y="{p["y0"]}" width="{p["pw"] / n:.1f}" height="{p["ph"]}" fill="#efefef"/>')
            if i:
                o.append(f'<line x1="{bx:.1f}" y1="{p["y0"]}" x2="{bx:.1f}" y2="{p["y0"] + p["ph"]}" stroke="#cfcfcf" stroke-width="0.8"/>')
            xc = p["x0"] + p["pw"] * (i + 0.5) / n
            o.append(f'<line x1="{xc:.1f}" y1="{p["y0"] + p["ph"]}" x2="{xc:.1f}" y2="{p["y0"] + p["ph"] + 4}" stroke="#444" stroke-width="0.8"/>')
            o.append(mf.txt(xc, p["y0"] + p["ph"] + 16, d, size=8))
        for v in ticks:
            o.append(f'<line x1="{p["x0"]}" y1="{y(v):.1f}" x2="{p["x0"] + p["pw"]}" y2="{y(v):.1f}" stroke="#e4e4e4" stroke-width="0.6"/>')
            o.append(f'<line x1="{p["x0"] - 4}" y1="{y(v):.1f}" x2="{p["x0"]}" y2="{y(v):.1f}" stroke="#444" stroke-width="0.8"/>')
            o.append(mf.txt(p["x0"] - 7, y(v) + 3, f"{v:g}", size=8, anchor="end"))
        o.append(mf.txt(p["x0"] + p["pw"] / 2, p["y0"] + p["ph"] + 36, "Distance of the wrong label", size=9.5))
        for (t, name, colour), dash, dx in zip(TOOLS, (None, mf.COMPARATOR_DASH), (-6, 6)):
            pts = [(p["x0"] + p["pw"] * (i + 0.5) / n + dx, y(v)) for i, v in enumerate(series[key][t])]
            d = "M" + " L".join(f"{x:.1f},{yy:.1f}" for x, yy in pts)
            o.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.4"' + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
            o += [diamond(x, yy, colour, 4.2) for x, yy in pts]
            for dname, v in zip(dists, series[key][t]):
                VALUES.append(f"distance\t{'A' if key == 'found' else 'B'}\t{name}\t{dname}\t{v:.2f}")
        o.append(box(p["x0"], p["y0"], p["pw"], p["ph"]))
        o.append(mf.txt(p["x0"] - 38, p["y0"] + p["ph"] / 2, label, size=9.5, rot=-90))
    o += dot_legend(pa["x0"], 26, [("SATIVA-epang", mf.FORK, "diamond", 0), ("SATIVA", mf.UP, "diamond", 100)])
    return canvas(w, h, o)


def fig_staged():
    rows, ceiling = [], None
    for line in (RES / "staged_rounds.txt").read_text().splitlines():
        f = line.split()
        if len(f) == 14 and f[0] in ("1", "2", "4"):
            rows.append(dict(n=int(f[0]), tree=float(f[2]), place=float(f[4]), score=float(f[6]), total=float(f[7]),
                             sp_place=float(f[8].rstrip("x")), ef_place=f[11], sp_total=float(f[12].rstrip("x")), ef_total=f[13]))
        if "cannot beat" in line:
            ceiling = float(line.split("cannot beat ")[1].split("x")[0])
    w, h = 440, 330
    pb = dict(x0=62, pw=340, y0=56, ph=210)
    o = []

    def frame(p, ticks, y, fmt, ylab):
        o.append(f'<rect x="{p["x0"]}" y="{p["y0"]}" width="{p["pw"]}" height="{p["ph"]}" fill="#fafafa"/>')
        for i, r in enumerate(rows):
            bx = p["x0"] + p["pw"] * i / 3
            if i % 2:
                o.append(f'<rect x="{bx:.1f}" y="{p["y0"]}" width="{p["pw"] / 3:.1f}" height="{p["ph"]}" fill="#efefef"/>')
            if i:
                o.append(f'<line x1="{bx:.1f}" y1="{p["y0"]}" x2="{bx:.1f}" y2="{p["y0"] + p["ph"]}" stroke="#cfcfcf" stroke-width="0.8"/>')
            xc = p["x0"] + p["pw"] * (i + 0.5) / 3
            o.append(f'<line x1="{xc:.1f}" y1="{p["y0"] + p["ph"]}" x2="{xc:.1f}" y2="{p["y0"] + p["ph"] + 4}" stroke="#444" stroke-width="0.8"/>')
            o.append(mf.txt(xc, p["y0"] + p["ph"] + 16, str(r["n"]), size=8))
        for v in ticks:
            o.append(f'<line x1="{p["x0"]}" y1="{y(v):.1f}" x2="{p["x0"] + p["pw"]}" y2="{y(v):.1f}" stroke="#e4e4e4" stroke-width="0.6"/>')
            o.append(f'<line x1="{p["x0"] - 4}" y1="{y(v):.1f}" x2="{p["x0"]}" y2="{y(v):.1f}" stroke="#444" stroke-width="0.8"/>')
            o.append(mf.txt(p["x0"] - 7, y(v) + 3, fmt(v), size=8, anchor="end"))
        o.append(mf.txt(p["x0"] + p["pw"] / 2, p["y0"] + p["ph"] + 36, "Number of batches", size=9.5))
        o.append(mf.txt(p["x0"] - 38, p["y0"] + p["ph"] / 2, ylab, size=9.5, rot=-90))

    cx = lambda p, i: p["x0"] + p["pw"] * (i + 0.5) / 3
    yb = lambda v: pb["y0"] + pb["ph"] - v / 4.8 * pb["ph"]
    frame(pb, (0, 1, 2, 3, 4), yb, lambda v: f"{v:g}", "Speedup")
    o.append(f'<line x1="{pb["x0"]}" y1="{yb(ceiling):.1f}" x2="{pb["x0"] + pb["pw"]}" y2="{yb(ceiling):.1f}" stroke="#666" stroke-width="1" stroke-dasharray="4 3"/>')
    o.append(mf.txt(pb["x0"] + pb["pw"] - 6, yb(ceiling) - 5, f"limit of the whole run, {ceiling:.2f}", size=7.5, anchor="end", fill="#555"))
    ideal = [(cx(pb, i), yb(r["n"])) for i, r in enumerate(rows)]
    o.append("<path d=\"M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in ideal) + "\" fill=\"none\" stroke=\"#b0b0b0\" stroke-width=\"1.2\"/>")
    o += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="#fff" stroke="#999" stroke-width="1"/>' for x, y in ideal]
    for key, ef, colour, dash in (("sp_place", "ef_place", mf.FORK, None), ("sp_total", "ef_total", "#8a8a8a", None)):
        pts = [(cx(pb, i), yb(r[key])) for i, r in enumerate(rows)]
        o.append("<path d=\"M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f"\" fill=\"none\" stroke=\"{colour}\" stroke-width=\"1.4\"/>")
        for (x, y), r in zip(pts, rows):
            o.append(diamond(x, y, colour, 4.2))
            if r["n"] > 1:
                left = key == "sp_place" and r["n"] == 2
                o.append(mf.txt(x + (-9 if left else 8), y + (-9 if left else -6 if key == "sp_place" else 14), f"{r[key]:.2f} ({r[ef]})", size=7.5, anchor="end" if left else "start", fill=colour if key == "sp_place" else "#666"))
            VALUES.append(f"staged\\tspeedup\\t{key}\\t{r['n']}\\t{r[key]:.2f}")
    o.append(box(pb["x0"], pb["y0"], pb["pw"], pb["ph"]))
    o += dot_legend(pb["x0"] + 4, 26, [("placement", mf.FORK, "diamond", 0), ("whole run", "#8a8a8a", "diamond", 82), ("ideal", "#999", "dot", 160)], size=7.5)
    return canvas(w, h, o)


def fig_width():
    mem = load("memory_width.json")
    w, h = 530, 340
    x0, pw, y0, ph = 80, 400, 30, 240
    xlim, lim = (200, 1800), (0, 3000)
    px = lambda c: x0 + (c - xlim[0]) / (xlim[1] - xlim[0]) * pw
    py = lambda v: y0 + ph - (v - lim[0]) / (lim[1] - lim[0]) * ph
    o = [f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="#fafafa"/>']
    for v in (0, 500, 1000, 1500, 2000, 2500, 3000):
        o.append(f'<line x1="{x0}" y1="{py(v):.1f}" x2="{x0 + pw}" y2="{py(v):.1f}" stroke="#e4e4e4" stroke-width="0.6"/>')
        o.append(f'<line x1="{x0 - 4}" y1="{py(v):.1f}" x2="{x0}" y2="{py(v):.1f}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(x0 - 7, py(v) + 3, f"{v:,}".replace(",", " "), size=8, anchor="end"))
    for c in (300, 600, 900, 1200, 1500):
        o.append(f'<line x1="{px(c):.1f}" y1="{y0 + ph}" x2="{px(c):.1f}" y2="{y0 + ph + 4}" stroke="#444" stroke-width="0.8"/>')
        o.append(mf.txt(px(c), y0 + ph + 16, str(c), size=8))
    fits = {}
    for key, title in (("epang_T8_K25", "8 threads"), ("epang_T1_K25", "1 thread")):
        m = mem[key]
        a, b = m["intercept_mb"], m["kb_per_seq_per_column"] * 2023 / 1000
        c0, c1 = m["rows"][0]["columns"], m["rows"][-1]["columns"]
        fits[key] = (a, b, c0, c1)
        # measured range only: the part that does not depend on width, and the part that grows with it
        o.append(f'<path d="M{px(c0):.1f},{py(0):.1f} L{px(c0):.1f},{py(a):.1f} L{px(c1):.1f},{py(a):.1f} '
                 f'L{px(c1):.1f},{py(0):.1f} Z" fill="#cfcfcf" fill-opacity="0.55"/>')
        o.append(f'<path d="M{px(c0):.1f},{py(a):.1f} L{px(c1):.1f},{py(a):.1f} L{px(c1):.1f},{py(a + b * c1):.1f} '
                 f'L{px(c0):.1f},{py(a + b * c0):.1f} Z" fill="#6f8fa8" fill-opacity="0.30"/>')
    for key, title, colour, dash in (("epang_T1_K25", "1 thread", GREY, mf.COMPARATOR_DASH),
                                     ("epang_T8_K25", "8 threads", mf.FORK, None)):
        a, b, c0, c1 = fits[key]
        o.append(f'<line x1="{px(c0):.1f}" y1="{py(a + b * c0):.1f}" x2="{px(c1):.1f}" y2="{py(a + b * c1):.1f}" '
                 f'stroke="{colour}" stroke-width="1.5"' + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
        for r in mem[key]["rows"]:
            o.append(f'<circle cx="{px(r["columns"]):.1f}" cy="{py(r["max_rss_mb"]):.1f}" r="3.3" fill="{colour}" '
                     f'stroke="#fff" stroke-width="0.8"/>')
            VALUES.append(f"memory_width\tA\t{title}\t{r['columns']}\t{r['max_rss_mb']}")
        o.append(mf.txt(px(c1) + 8, py(a + b * c1) + 3, title, size=8.5, anchor="start", fill=colour))
    a1, a8 = fits["epang_T1_K25"][0], fits["epang_T8_K25"][0]
    o.append(mf.txt(px(900), py(min(a1, a8) / 2) + 3, f"independent of width, about {round((a1 + a8) / 2, -1):.0f} MB",
                    size=8.5))
    o.append(mf.txt(px(700), py(1280) + 3, "grows with width", size=8.5, fill="#34566e"))
    o.append(box(x0, y0, pw, ph))
    o.append(mf.txt(x0 + pw / 2, y0 + ph + 36, "Alignment width (columns)", size=9.5))
    o.append(mf.txt(x0 - 52, y0 + ph / 2, "Peak memory (MB)", size=9.5, rot=-90))
    return canvas(w, h, o)


FIGURES = (("kinds", fig_kinds), ("chimera", fig_chimera), ("recall_k", fig_k), ("simulated", fig_simulated), ("bacterial", fig_bacterial), ("distance", fig_distance), ("staged", fig_staged),
           ("memory_width", fig_width))
for name, fn in FIGURES:
    (OUT / f"supp_{name}.svg").write_text(fn())
(RES / "supplement_figures_values.tsv").write_text("\n".join(VALUES) + "\n")
print(f"wrote {len(VALUES) - 1} values and {len(FIGURES)} figures to {OUT}")
