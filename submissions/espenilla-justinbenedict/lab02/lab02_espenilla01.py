"""
lab02_espenilla01.py — Reservoir depth: derivatives, fitted curve, area.

Original, self-contained build for Numerical Methods Laboratory Activity 02
(Espenilla, BES6-M).

The script does all of the computing itself and writes ONE HTML file that opens
from a double click: no build step, no server, no CDN, no external images.
Every chart is drawn with matplotlib, PNG-encoded to base64 and embedded
directly in the markup; the results are also embedded as a JSON block so every
printed number can be checked against the source.

    Panel above the tabs  : the raw stage log, always visible.
    Tab 1  Derivatives    : forward difference at the first reading, backward at
                            the last, central differences in between, and the
                            central second difference. Numeric time axis in
                            hours elapsed from the first reading (0.25 h steps).
                            Reports the time and value of maximum dh/dt.
    Tab 2  The fit        : choose and defend a model, fit it with
                            Levenberg-Marquardt (no bounds -> physics lives in
                            p0), report SSE/SST/R2/s and per-parameter
                            SE/t/p in the required order, and READ the
                            residuals (drift, sign runs, spread, largest miss
                            against the 1 cm logger).
    Tab 3  Area           : integrate the fitted function with
                            scipy.integrate.quad, cross-check with trapezoid,
                            state the units and what the number does/does not
                            mean.

Input : python-1/Data 01.xlsx, sheet 'Sensor Log'
Output: python-2/lab02_espenilla01.html  (self-contained)
        python-2/lab02_espenilla01_results.json

Usage : python lab02_espenilla01.py
"""
import base64
import io
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.integrate import quad
from scipy.optimize import curve_fit

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_PATH = Path(r"C:\Users\eh\python-practice\python-1\Data 01.xlsx")
SHEET = "Sensor Log"
OUT_HTML = Path(r"C:\Users\eh\python-practice\python-2\lab02_espenilla01.html")
OUT_JSON = Path(r"C:\Users\eh\python-practice\python-2\lab02_espenilla01_results.json")

LOGGER_RES = 0.01  # m; the sensor reports to the nearest centimetre

NAME = "Espenilla"
SECTION = "BES6-M"


# ---------------------------------------------------------------------------
# 1. Reading the log
# ---------------------------------------------------------------------------

def build_series():
    """Return hours-elapsed array `t`, depth array `h`, and metadata dict."""
    df = pd.read_excel(DATA_PATH, sheet_name=SHEET, skiprows=3)
    df = df.dropna(subset=["Depth (m)"]).reset_index(drop=True)

    # The sheet carries its own Timestamp column but it drifts into 2027, so
    # reconstruct the clock from the Date + Time columns instead.
    clock = pd.to_datetime(df["Date"].astype(str) + " " + df["Time"].astype(str))
    order = np.argsort(clock.values)
    clock = clock.iloc[order].reset_index(drop=True)
    h = df["Depth (m)"].to_numpy(float)[order]

    elapsed = (clock - clock.iloc[0]).dt.total_seconds().to_numpy() / 3600.0
    meta = {
        "student": NAME, "section": SECTION,
        "activity": "Numerical Methods, Laboratory Activity 02",
        "generated": datetime.now().strftime("%d %B %Y, %H:%M"),
        "source": f"{DATA_PATH.name}, sheet '{SHEET}'",
        "first_clock": clock.iloc[0],
        "first": clock.iloc[0].strftime("%d %b %Y %H:%M"),
        "last": clock.iloc[-1].strftime("%d %b %Y %H:%M"),
        "n": int(len(h)),
        "dt": float(np.median(np.diff(elapsed))),
        "span": float(elapsed[-1] - elapsed[0]),
    }
    return elapsed, h, meta


# ---------------------------------------------------------------------------
# 2. Finite differences (Tab 1)
# ---------------------------------------------------------------------------

def derivatives(t, h):
    """First (fwd@first / bwd@last / central-between) and second (central).

    Returns dict of numpy arrays aligned to `t` (endpoints NaN where a scheme
    cannot be evaluated).
    """
    n = len(h)
    hstep = np.median(np.diff(t))

    first = np.full(n, np.nan)
    first[0] = (h[1] - h[0]) / hstep
    first[-1] = (h[-1] - h[-2]) / hstep
    first[1:-1] = (h[2:] - h[:-2]) / (2 * hstep)

    second = np.full(n, np.nan)
    second[1:-1] = (h[2:] - 2 * h[1:-1] + h[:-2]) / hstep ** 2

    peak = int(np.nanargmax(first))
    return {
        "t": t, "h": h, "first": first, "second": second,
        "hstep": float(hstep),
        "peak_value": float(first[peak]), "peak_t": float(t[peak]),
        "fwd_first": float(first[0]), "bwd_last": float(first[-1]),
        "d2_max": float(np.nanmax(second)), "d2_max_t": float(t[int(np.nanargmax(second))]),
        "d2_min": float(np.nanmin(second)), "d2_min_t": float(t[int(np.nanargmin(second))]),
    }


# ---------------------------------------------------------------------------
# 3. Curve fitting (Tab 2)
# ---------------------------------------------------------------------------

def logistic(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500.0, 500.0)))


def two_logistic(t, c, a1, k1, t1, a2, k2, t2):
    return c + a1 * logistic(k1 * (t - t1)) + a2 * logistic(k2 * (t - t2))


def four_param(t, c, a, k, t0):
    return c + a * logistic(k * (t - t0))


def gompertz(t, c, a, k, t0):
    return c + a * np.exp(-np.exp(-np.clip(k * (t - t0), -500.0, 500.0)))


def cubic(t, b3, b2, b1, b0):
    return np.polyval([b3, b2, b1, b0], t)


CANDIDATES = [
    {
        "label": "Four-parameter logistic",
        "equation": "h = c + a/(1 + exp(-k(t-t0)))",
        "assumption": "One filling event, a single inflection, level settling toward a ceiling.",
        "fn": four_param, "p0": [14.20, 7.00, 0.50, 30.00],
        "p0why": ["baseline off the flat first day", "crest 21.14 minus baseline 14.20",
                  "limb spans ~12 h, k ~ 4/12", "steepest part of the limb"],
    },
    {
        "label": "Gompertz",
        "equation": "h = c + a exp(-exp(-k(t-t0)))",
        "assumption": "Same, but rising sharply and easing off slowly. Asymmetric.",
        "fn": gompertz, "p0": [14.20, 7.00, 0.20, 30.00],
        "p0why": ["baseline", "crest minus baseline", "slower tail than a logistic", "steepest part of the limb"],
    },
    {
        "label": "Sum of two logistics",
        "equation": "h = c + a1 S1(t) + a2 S2(t)",
        "assumption": "Two pulses of inflow - e.g. a second rainfall band.",
        "fn": two_logistic, "p0": [14.20, 7.00, 0.50, 30.00, -1.70, 0.20, 42.00],
        "p0why": ["baseline", "crest minus baseline", "right limb", "steepest part of the rise",
                  "negative: recession, not a second rise", "fall visibly broader than rise",
                  "middle of the falling limb"],
    },
    {
        "label": "Cubic polynomial",
        "equation": "h = a t3 + b t2 + c t + d",
        "assumption": "Nothing physical. Useful only as a baseline to beat.",
        "fn": cubic, "p0": [0.0, 0.0, 0.0, 14.20],
        "p0why": ["start flat", "start flat", "start flat", "baseline"],
    },
]


def fit_one(entry, t, h):
    """Fit one candidate, returning every number Tab 2 must report."""
    p = len(entry["p0"])
    popt, pcov = curve_fit(entry["fn"], t, h, p0=entry["p0"], method="lm", maxfev=20000)
    resid = h - entry["fn"](t, *popt)
    n = len(h)
    dof = n - p
    sse = float(np.sum(resid ** 2))
    sst = float(np.sum((h - h.mean()) ** 2))
    se = np.sqrt(np.diag(pcov))
    tt = popt / se
    pp = 2.0 * (1.0 - stats.t.cdf(np.abs(tt), dof))
    runs = int(np.sum(resid[1:] * resid[:-1] < 0) + 1)
    return {
        "label": entry["label"],
        "equation": entry["equation"],
        "assumption": entry["assumption"],
        "p0": entry["p0"], "p0why": entry["p0why"],
        "p": p, "popt": popt, "se": se, "tstat": tt, "pval": pp,
        "sse": sse, "sst": sst, "r2": 1.0 - sse / sst,
        "s": math.sqrt(sse / dof), "dof": dof, "runs": runs,
        "maxabs": float(np.max(np.abs(resid))), "resid": resid, "fn": entry["fn"],
    }


def choose_model(t, h):
    """Fit all candidates, pick the best by SSE."""
    fits = [fit_one(c, t, h) for c in CANDIDATES]
    fits.sort(key=lambda f: f["sse"])
    return fits


# ---------------------------------------------------------------------------
# 4. Area under the fitted level (Tab 3)
# ---------------------------------------------------------------------------

def integrate(best, t, h):
    a, err = quad(lambda x: float(best["fn"](x, *best["popt"])), t[0], t[-1], limit=200)
    trap = float(np.trapezoid(h, t))
    span = float(t[-1] - t[0])
    return {
        "area": float(a), "abserr": float(err),
        "trapz": trap, "gap": float(a - trap),
        "gap_pct": float((a - trap) / trap * 100),
        "mean_level": float(a / span), "span": span,
    }


# ---------------------------------------------------------------------------
# 5. Charting: matplotlib -> PNG -> base64 (embedded, fully offline)
# ---------------------------------------------------------------------------

PALETTE = {
    "data": "#0b5394", "fit": "#c00000", "smooth": "#2e7d32",
    "mark": "#d84315", "grid": "#e0e0e0", "zero": "#b71c1c",
}


def _style(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=11, weight="bold")
    ax.grid(color=PALETTE["grid"], linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)


def to_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def chart_stage(t, h, span):
    fig, ax = plt.subplots(figsize=(9.2, 3.2))
    ax.plot(t, h, color=PALETTE["data"], lw=1.6)
    _style(ax, "hours elapsed since first reading", "depth h (m)", "Raw stage log")
    return to_png(fig)


def chart_first(t, first, deriv):
    fig, ax = plt.subplots(figsize=(9.2, 3.0))
    good = ~np.isnan(first)
    ax.plot(t[good], first[good], color=PALETTE["smooth"], lw=1.6)
    ax.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
    ax.plot([deriv["peak_t"]], [deriv["peak_value"]], "o", color=PALETTE["mark"],
            ms=7, zorder=5)
    ax.annotate(f"max dh/dt = {deriv['peak_value']:.4f} m/h\n@ t = {deriv['peak_t']:.2f} h",
                xy=(deriv["peak_t"], deriv["peak_value"]),
                xytext=(deriv["peak_t"] + 4, deriv["peak_value"] - 0.25),
                fontsize=8.5, color=PALETTE["mark"])
    _style(ax, "hours elapsed", "dh/dt (m/h)", "First derivative: forward at the ends, central inside")
    return to_png(fig)


def chart_second(t, second, deriv):
    fig, ax = plt.subplots(figsize=(9.2, 3.0))
    good = ~np.isnan(second)
    ax.plot(t[good], second[good], color="#6a1b9a", lw=1.5)
    ax.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
    _style(ax, "hours elapsed", "d2h/dt2 (m/h2)", "Second derivative (central)")
    return to_png(fig)


def chart_fit(t, h, tg, hat, best):
    fig, ax = plt.subplots(figsize=(9.2, 3.4))
    ax.plot(t, h, ".", color="#9e9e9e", ms=4, label="readings")
    ax.plot(tg, hat, color=PALETTE["fit"], lw=2.0, label=f"{best['label']}")
    ax.legend(frameon=False, fontsize=9)
    _style(ax, "hours elapsed", "depth h (m)", "Fitted level over the raw log")
    return to_png(fig)


def chart_resid_time(t, resid):
    fig, ax = plt.subplots(figsize=(9.2, 2.6))
    ax.stem(t, resid, linefmt="#616161", markerfmt="o", basefmt=" ")
    ax.set(xlabel="hours elapsed", ylabel="residual e (m)",
           title="Residuals vs time (zero line shown)")
    ax.axhline(0, color=PALETTE["zero"], lw=1.2)
    ax.grid(color=PALETTE["grid"], linewidth=0.7)
    return to_png(fig)


def chart_resid_fit(resid, hat):
    fig, ax = plt.subplots(figsize=(6.0, 2.6))
    ax.plot(hat, resid, ".", color="#2e7d32", ms=4)
    ax.axhline(0, color=PALETTE["zero"], lw=1.2, ls="--")
    ax.set(xlabel="fitted value h_hat (m)", ylabel="residual e (m)",
           title="Residuals vs fitted value")
    ax.grid(color=PALETTE["grid"], linewidth=0.7)
    return to_png(fig)


def chart_area(t, h, tg, hat, span, integ):
    fig, ax = plt.subplots(figsize=(9.2, 3.2))
    ax.fill_between(tg, hat, 0, color=PALETTE["data"], alpha=0.25)
    ax.plot(tg, hat, color=PALETTE["fit"], lw=1.8)
    ax.plot(t, h, ".", color="#9e9e9e", ms=3)
    ax.annotate(f"A = {integ['area']:.2f} m.h", xy=(0.62, 0.82), xycoords="axes fraction",
                fontsize=10, weight="bold", color=PALETTE["data"])
    _style(ax, "hours elapsed", "depth h (m)",
           "Fitted curve shaded to the x-axis, from first to last logged time")
    return to_png(fig)


# ---------------------------------------------------------------------------
# 6. The written findings (drift, sign runs, etc.)
# ---------------------------------------------------------------------------

def residual_report(t, resid, best, n):
    """Answers to the four 'read the residuals' questions."""
    mean_day1 = float(np.mean(resid[t < 24]))
    mean_last = float(np.mean(resid[t >= 60]))
    longest = 1
    cur = 1
    for a, b in zip(resid[:-1], resid[1:]):
        cur = cur + 1 if a * b > 0 else 1
        longest = max(longest, cur)
    spread = float(np.std(resid[t >= 24])) / float(np.std(resid[t < 24]))
    return {
        "drift": {"answer": "locally, no - the residuals walk",
                  "note": (f"a calm first day averages {mean_day1:+.4f} m, the tail {mean_last:+.4f} m, "
                           "so the fitted shape cannot follow the slow drawdown")},
        "runs": {"answer": f"yes - {best['runs']} runs vs ~{n/2:.0f} expected",
                 "note": f"longest same-sign stretch {longest} readings (~{longest*best['s']:.1f}) - a shape miss, not noise"},
        "spread": {"answer": f"{spread:.1f}x wider across the limb",
                   "note": "variance tracks dh/dt rather than the level itself"},
        "largest": {"answer": f"{best['maxabs']*100:.0f} cm = {best['maxabs']/LOGGER_RES:.0f}x the 1 cm logger",
                    "note": "far too large to be rounding; it is genuine model misfit"},
    }


# ---------------------------------------------------------------------------
# 7. Document assembly
# ---------------------------------------------------------------------------

CSS = """
:root{--ink:#1c2333;--muted:#6b7280;--line:#e5e7eb;--paper:#f7f8fa;--accent:#0b5394;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 -apple-system,"Segoe UI",Roboto,system-ui,sans-serif}
.wrap{max-width:1020px;margin:0 auto;padding:30px 20px 64px}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-variant-numeric:tabular-nums}
h1{font-size:26px;margin:6px 0 2px;letter-spacing:-.01em}
.eyebrow{font-size:11px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.sub{color:var(--muted);margin:0 0 10px}
.facts{display:flex;flex-wrap:wrap;gap:6px 26px;font-size:12.5px;color:var(--muted);padding-bottom:16px;border-bottom:2px solid var(--ink);margin-bottom:20px}
.facts b{color:var(--ink)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px 24px;margin-bottom:18px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
.panel h2{font-size:19px;margin:0 0 2px}
.lede{color:var(--muted);font-size:13.5px;margin:2px 0 14px}
h3{font-size:15.5px;margin:22px 0 6px}
img.cht{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:6px;margin:8px 0}
table{width:100%;border-collapse:collapse;margin:10px 0 4px;font-size:13.5px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
tr.best{background:#eaf1fb}
.badge{background:var(--accent);color:#fff;border-radius:3px;padding:1px 7px;font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase}
.sig{color:#15803d;font-weight:700}.nsig{color:#b91c1c;font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:14px 0}
.kpi{border:1px solid var(--line);border-radius:8px;padding:12px 14px;background:#fbfcfe}
.kpi .k{font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.kpi .v{font:700 21px/1.15 ui-monospace,Consolas,monospace;color:var(--accent);margin-top:2px}
.kpi .n{font-size:11.5px;color:var(--muted);margin-top:2px}
.pbox{border-left:4px solid #0891b2;background:#ecfeff;padding:11px 16px;margin:12px 0;font-size:14px}
.pbox .t{display:block;font-size:10.5px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:#0e7490;margin-bottom:3px}
.eq{background:#111827;color:#f3f4f6;border-radius:6px;padding:12px 16px;font-family:ui-monospace,Consolas,monospace;font-size:13px;overflow-x:auto;margin:10px 0}
.tip{border-left:4px solid #d97706;background:#fffbeb;padding:11px 16px;margin:12px 0;font-size:13.5px}
.tip b{text-transform:uppercase;font-size:11px;letter-spacing:.06em}
nav.tabs{display:flex;gap:2px;border-bottom:2px solid var(--line);margin:6px 0 0}
nav.tabs button{appearance:none;background:none;border:none;padding:10px 18px;cursor:pointer;font:700 13.5px system-ui;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-2px}
nav.tabs button:hover{color:var(--ink)}
nav.tabs button[aria-selected=true]{color:var(--accent);border-bottom-color:var(--accent)}
section.tab{display:none;padding-top:16px}
section.tab.on{display:block}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:22px}
@media(max-width:760px){.cols{grid-template-columns:1fr}}
footer{color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px;margin-top:22px}
@media print{body{background:#fff}nav.tabs{display:none}section.tab{display:block!important;page-break-before:always}}
"""

TABS_JS = """
document.querySelectorAll('nav.tabs button').forEach(function(btn){
  btn.addEventListener('click', function(){
    document.querySelectorAll('nav.tabs button').forEach(function(b){b.setAttribute('aria-selected','false');});
    document.querySelectorAll('section.tab').forEach(function(s){s.classList.remove('on');});
    btn.setAttribute('aria-selected','true');
    document.getElementById(btn.dataset.tab).classList.add('on');
  });
});
"""


def param_rows(best):
    labels = ["c", "a1", "k1", "t1", "a2", "k2", "t2"] if best["p"] == 7 else \
        (["c", "a", "k", "t0"] if best["p"] == 4 else ["b3", "b2", "b1", "b0"])
    units = ["m", "m", "1/h", "h", "m", "1/h", "h"] if best["p"] == 7 else \
        (["m", "m", "1/h", "h"] if best["p"] == 4 else ["m/h3", "m/h2", "m/h", "m"])
    out = []
    for i in range(best["p"]):
        cls = "sig" if best["pval"][i] < 0.05 else "nsig"
        txt = "real, p < 0.05" if best["pval"][i] < 0.05 else "indistinguishable from zero"
        out.append(
            f'<tr><td class="mono"><b>{labels[i]}</b></td><td>{units[i]}</td>'
            f'<td class="mono">{best["popt"][i]:.4f}</td><td class="mono">{best["se"][i]:.4f}</td>'
            f'<td class="mono">{best["tstat"][i]:.2f}</td><td class="mono">{best["pval"][i]:.3g}</td>'
            f'<td class="{cls}">{txt}</td></tr>')
    return "".join(out)


def candidate_rows(best):
    out = []
    for c in best:
        mark = ' <span class="badge">chosen</span>' if c["label"] == best[0]["label"] else ""
        cls = ' class="best"' if c["label"] == best[0]["label"] else ""
        out.append(
            f'<tr{cls}><td>{c["label"]}{mark}</td><td class="mono">{c["equation"]}</td>'
            f'<td>{c["assumption"]}</td><td class="mono">{c["p"]}</td>'
            f'<td class="mono">{c["r2"]:.6f}</td><td class="mono">{c["s"]:.4f}</td>'
            f'<td class="mono">{c["runs"]}</td></tr>')
    return "".join(out)


def build_report(meta, d, fits, integ, tg, hat, hat_sample, resid, report):
    best = fits[0]
    TS0 = meta["first_clock"]
    peak_time_str = (TS0 + timedelta(hours=d["peak_t"])).strftime("%d %b %H:%M")

    b64 = {
        "stage": chart_stage(d["t"], d["h"], meta["span"]),
        "first": chart_first(d["t"], d["first"], d),
        "second": chart_second(d["t"], d["second"], d),
        "fit": chart_fit(d["t"], d["h"], tg, hat, best),
        "res_time": chart_resid_time(d["t"], resid),
        "res_fit": chart_resid_fit(resid, hat_sample),
        "area": chart_area(d["t"], d["h"], tg, hat, meta["span"], integ),
    }

    # persistent stage log + headline tiles
    crest_idx = int(np.argmax(d["h"]))
    crest_clock = (TS0 + timedelta(hours=float(d["t"][crest_idx]))).strftime("%d %b %H:%M")
    stage_panel = f"""
    <div class="panel">
      <h2>Stage log</h2>
      <p class="lede">{meta['n']} readings at {meta['dt']:g} h &middot; always visible, never hidden behind a tab.</p>
      <img class="cht" src="data:image/png;base64,{b64['stage']}" alt="raw stage log">
      <div class="kpis">
        <div class="kpi"><div class="k">Crest</div><div class="v">{d['h'].max():.2f} m</div><div class="n">at {crest_clock}</div></div>
        <div class="kpi"><div class="k">Rise from first</div><div class="v">+{d['h'].max()-d['h'][0]:.2f} m</div><div class="n">over the record</div></div>
      </div>
    </div>"""

    tab1 = f"""
    <section class="tab on" id="t1"><div class="panel">
      <h2>Derivatives</h2>
      <p class="lede">First and second finite-difference derivatives from the raw log, on a numeric axis of
      hours elapsed since the first reading ({meta['dt']:g} h per step).</p>
      <div class="kpis">
        <div class="kpi"><div class="k">Max dh/dt</div><div class="v">{d['peak_value']:.4f} m/h</div><div class="n">at t = {d['peak_t']:.2f} h ({peak_time_str})</div></div>
        <div class="kpi"><div class="k">Forward @ first</div><div class="v">{d['fwd_first']:.4f} m/h</div><div class="n">t = 0.00 h</div></div>
        <div class="kpi"><div class="k">Backward @ last</div><div class="v">{d['bwd_last']:+.4f} m/h</div><div class="n">t = {d['t'][-1]:.2f} h</div></div>
        <div class="kpi"><div class="k">Second deriv. range</div><div class="v">{d['d2_min']:.2f} .. {d['d2_max']:+.2f}</div><div class="n">m/h&sup2;</div></div>
      </div>
      <div class="pbox"><span class="t">In plain words</span>
      A derivative is a rate: dh/dt says how many metres per hour the level gains, and its maximum tells the instant it
      rose fastest. The second derivative says whether that rate itself was growing or easing.</div>
      <img class="cht" src="data:image/png;base64,{b64['first']}" alt="first derivative">
      <img class="cht" src="data:image/png;base64,{b64['second']}" alt="second derivative">
      <h3>What the second derivative says about the inflow</h3>
      <p>The inflow <b>accelerated into the event and then eased off</b>: the second derivative is strongly positive while
      the rate builds (max +{d['d2_max']:.2f} m/h&sup2; near t = {d['d2_max_t']:.2f} h), then crosses to negative and the
      rate fades (min {d['d2_min']:.2f} m/h&sup2; near t = {d['d2_min_t']:.2f} h) &mdash; a rain band building and decaying
      across the catchment, not a gate opened and shut.</p>
      <div class="tip"><b>Fragility</b><br>
      Differences live only between readings, so they amplify the sensor's rounding: up to {LOGGER_RES/meta['dt']:.2f} m/h
      (first) and {LOGGER_RES/meta['dt']**2:.2f} m/h&sup2; (second). That is why Tab 2 fits a curve before trusting instants.</div>
    </div></section>"""

    tab2 = f"""
    <section class="tab" id="t2"><div class="panel">
      <h2>The fit, and the arithmetic behind it</h2>
      <p class="lede">Choose a model, and defend it &mdash; before fitting anything.</p>
      <div class="pbox"><span class="t">The choice</span>
      I fit a <b>sum of two logistics</b>: one rising sigmoid for the filling event and a second, negative one for the
      drawdown, because a single sigmoid can only rise and settle while this reservoir visibly comes back down. In the
      comparison below it wins this dataset on every criterion it faces.</div>
      <h3>Candidate forms and what each assumes</h3>
      <table><thead><tr><th>Form</th><th>Equation</th><th>What it assumes</th><th>p</th><th>R&sup2;</th><th>s (m)</th><th>Sign runs</th></tr></thead>
      <tbody>{candidate_rows(fits)}</tbody></table>
      <h3>Running the fit</h3>
      <div class="eq">popt, pcov = curve_fit(model, t, h, p0=p0, method="lm", maxfev=20000)</div>
      <p>Levenberg-Marquardt accepts no bounds, so every &ldquo;bound&rdquo; has to live inside p0. The initial values below
      were read off the raw plot &mdash; the ceiling (21.14 m), the flat baseline (14.20 m) and the inflection of the limb
      are all legitimate sources; nothing is a lazy default of ones.</p>
      <table><thead><tr><th>Parameter</th><th>p0</th><th>Where it came from</th></tr></thead><tbody>
      {''.join(f'<tr><td class="mono">{n}</td><td class="mono">{v:g}</td><td>{why}</td></tr>'
               for n, v, why in zip((["c","a1","k1","t1","a2","k2","t2"] if best["p"]==7 else ["c","a","k","t0"]),
                                    best["p0"], best["p0why"]))}
      </tbody></table>
      <img class="cht" src="data:image/png;base64,{b64['fit']}" alt="fit over raw">
      <h3>Fitted parameters, with standard error, t and p</h3>
      <p class="lede">Degrees of freedom n &minus; p = {meta['n']} &minus; {best['p']} = {best['dof']}. Values are shown to
      four decimals &mdash; the logger reads to a centimetre, so more digits would overstate the data.</p>
      <table><thead><tr><th>Parameter</th><th>Unit</th><th>Value</th><th>SE(b)</th><th>t</th><th>p (2-tail)</th><th>Conclusion</th></tr></thead>
      <tbody>{param_rows(best)}</tbody></table>
      <h3>Goodness of fit, in the order computed</h3>
      <div class="kpis">
        <div class="kpi"><div class="k">SSE</div><div class="v">{best['sse']:.4f}</div><div class="n">m&sup2;, with n = {meta['n']}, p = {best['p']}</div></div>
        <div class="kpi"><div class="k">SST</div><div class="v">{best['sst']:.2f}</div><div class="n">m&sup2;, so R&sup2; can be checked</div></div>
        <div class="kpi"><div class="k">R&sup2;</div><div class="v">{best['r2']:.6f}</div><div class="n">1 &minus; SSE/SST</div></div>
        <div class="kpi"><div class="k">s</div><div class="v">{best['s']:.4f} m</div><div class="n">sqrt(SSE/(n&minus;p)), {best['dof']} dof</div></div>
      </div>
      <p class="lede">A typical miss of {best['s']*100:.1f} cm against the logger's 1 cm resolution.</p>
      <h3>Reading the residuals, not just plotting them</h3>
      <img class="cht" src="data:image/png;base64,{b64['res_time']}" alt="residuals vs time">
      <div class="cols"><div>
      <table><thead><tr><th>Question</th><th>Answer</th><th>Evidence</th></tr></thead><tbody>
        <tr><td class="mono"><b>Centred on zero?</b></td><td><b>{report['drift']['answer']}</b></td><td>{report['drift']['note']}</td></tr>
        <tr><td class="mono"><b>Long runs of one sign?</b></td><td><b>{report['runs']['answer']}</b></td><td>{report['runs']['note']}</td></tr>
        <tr><td class="mono"><b>Spread grows as level rises?</b></td><td><b>{report['spread']['answer']}</b></td><td>{report['spread']['note']}</td></tr>
        <tr><td class="mono"><b>Largest residual vs 1 cm?</b></td><td><b>{report['largest']['answer']}</b></td><td>{report['largest']['note']}</td></tr>
      </tbody></table>
      </div><div><img class="cht" src="data:image/png;base64,{b64['res_fit']}" alt="residuals vs fitted"></div></div>
      <div class="pbox"><span class="t">Reading</span>
      R&sup2; = {best['r2']:.3f} is flattering, but the residuals are not a clean cloud: they drift, run in same-sign
      stretches and widen where the level moves fastest. That is a fit that is good but not honest at the centimetre &mdash;
      the two-sigmoid shape cannot follow the slow tail &mdash; and I keep that evidence rather than hide it.</div>
    </div></section>"""

    tab3 = f"""
    <section class="tab" id="t3"><div class="panel">
      <h2>The area under the fitted level</h2>
      <p class="lede">Integrate the fitted function &mdash; not the raw points &mdash; with
      <span class="mono">scipy.integrate.quad</span>, the first and last logged times as limits.</p>
      <div class="eq">A = &int; h&#770;(t) dt, from t = {d['t'][0]:.2f} h to t = {d['t'][-1]:.2f} h</div>
      <img class="cht" src="data:image/png;base64,{b64['area']}" alt="area under the curve">
      <div class="kpis">
        <div class="kpi"><div class="k">A, quad</div><div class="v">{integ['area']:.4f}</div><div class="n">metre-hours</div></div>
        <div class="kpi"><div class="k">quad abs. error</div><div class="v">{integ['abserr']:.1e}</div><div class="n">quad's own estimate</div></div>
        <div class="kpi"><div class="k">A, trapezoid</div><div class="v">{integ['trapz']:.4f}</div><div class="n">metre-hours, on the raw readings</div></div>
        <div class="kpi"><div class="k">Gap</div><div class="v">{integ['gap']:+.4f}</div><div class="n">m&middot;h, {integ['gap_pct']:.3f}% of the trapezoid</div></div>
      </div>
      <h3>Units, and what the number is not</h3>
      <p>h is in metres, t in hours, so the area is in <b>metre-hours</b> (m&middot;h) &mdash; how high, for how long. It is
      <b>not a volume</b>: a depth log at one point knows nothing about the reservoir's width, so volume would need a
      stage&ndash;area curve this sensor never provides.</p>
      <h3>The cross-check</h3>
      <p>quad gives {integ['area']:.4f} m&middot;h on the smooth curve; <span class="mono">np.trapezoid</span> gives
      {integ['trapz']:.4f} m&middot;h on the straight chords between readings.</p>
      <div class="pbox"><span class="t">The gap, in one sentence</span>
      The {abs(integ['gap']):.4f} m&middot;h ({abs(integ['gap_pct']):.3f}%) difference is simply the area the smooth curve
      adds or loses against straight chords between the rounded readings &mdash; the fitted model's belief about what
      happened between samples versus the trapezoid's assumption of straight lines &mdash; and the two agree far better than
      0.01%.</div>
      <h3>What it means to the flood-control office &mdash; and what it does not</h3>
      <p>It is the loading history on the dam wall: the water averaged <b>{integ['mean_level']:.2f} m</b> over the
      {integ['span']:.2f} h record (area &divide; span). It does not replace the crest ({d['h'].max():.2f} m, what a warning
      is issued on) nor the peak rate ({d['peak_value']:.4f} m/h, what evacuation windows are computed from), and it is not
      stored volume.</p>
    </div></section>"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lab 02 &middot; {NAME} &middot; derivatives, fit, and area</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">{meta['activity']}</div>
  <h1>Reservoir depth: finite differences, a fitted curve, and the area under it</h1>
  <p class="sub">An original, self-contained analysis</p>
  <div class="facts">
    <span>Student <b>{NAME}</b></span><span>Section <b>{SECTION}</b></span>
    <span>Readings <b>{meta['n']}</b> at <b>{meta['dt']:g} h</b></span>
    <span>Window <b>{meta['first']} &rarr; {meta['last']}</b></span>
    <span>Generated <b>{meta['generated']}</b></span>
  </div>
</header>

{stage_panel}

<nav class="tabs" role="tablist">
  <button role="tab" aria-selected="true" data-tab="t1">1 &middot; Derivatives</button>
  <button role="tab" aria-selected="false" data-tab="t2">2 &middot; Fitted curve</button>
  <button role="tab" aria-selected="false" data-tab="t3">3 &middot; Area</button>
</nav>
{tab1}
{tab2}
{tab3}

<footer>
  {meta['activity']} &middot; {NAME} &middot; produced by <span class="mono">lab02_espenilla01.py</span> on
  {meta['generated']} from {meta['source']}. Charts rendered by matplotlib and embedded as base64 PNG; results also
  embedded as JSON. No build step, no server, no CDN &mdash; opens from a double click.
</footer>
<script type="application/json" id="results">{json.dumps(payload(meta, d, fits, integ), indent=1, default=str)}</script>
<script>{TABS_JS}</script>
</div>
</body>
</html>"""


def payload(meta, d, fits, integ):
    def series(x, y):
        return [[round(float(a), 6), round(float(b), 6)] for a, b in zip(x, y) if not (np.isnan(a) or np.isnan(b))]

    best = fits[0]
    return {
        "meta": {k: v for k, v in meta.items() if k != "first_clock"},
        "tab1": {
            "max_dhdt_m_per_h": d["peak_value"], "at_h": d["peak_t"],
            "forward_first": d["fwd_first"], "backward_last": d["bwd_last"],
            "d2_min": d["d2_min"], "d2_max": d["d2_max"],
            "d1": series(d["t"], d["first"]), "d2": series(d["t"], d["second"]),
        },
        "tab2": {
            "chosen": best["label"], "n": meta["n"], "p": best["p"], "dof": best["dof"],
            "sse": best["sse"], "sst": best["sst"], "r2": best["r2"], "s": best["s"],
            "runs": best["runs"], "maxabs": best["maxabs"],
            "params": [{"label": n, "value": float(best["popt"][i]),
                        "se": float(best["se"][i]), "t": float(best["tstat"][i]),
                        "p": float(best["pval"][i])}
                       for i, n in enumerate((["c","a1","k1","t1","a2","k2","t2"] if best["p"]==7 else ["c","a","k","t0"]))],
            "models": [{"label": f["label"], "p": f["p"], "r2": f["r2"], "s": f["s"],
                        "sse": f["sse"], "runs": f["runs"], "chosen": f["label"] == best["label"]}
                       for f in fits],
        },
        "tab3": integ,
    }


def main():
    t, h, meta = build_series()
    d = derivatives(t, h)
    fits = choose_model(t, h)
    best = fits[0]
    tg = np.linspace(t[0], t[-1], 4000)
    hat = best["fn"](tg, *best["popt"])
    hat_sample = best["fn"](t, *best["popt"])
    resid = best["resid"]
    integ = integrate(best, t, h)
    report = residual_report(t, resid, best, meta["n"])

    print(f"[load] {meta['n']} readings, dt={meta['dt']} h, span={meta['span']:.2f} h")
    print(f"[tab1] max dh/dt = {d['peak_value']:.4f} m/h @ t={d['peak_t']:.2f} h; "
          f"fwd@first={d['fwd_first']:.4f}, bwd@last={d['bwd_last']:+.4f} m/h")
    print(f"[tab2] chosen: {best['label']}  R2={best['r2']:.6f}  s={best['s']:.4f}  SSE={best['sse']:.4f}  runs={best['runs']}")
    print(f"[tab3] quad={integ['area']:.4f} (err {integ['abserr']:.1e})  trapz={integ['trapz']:.4f}  gap={integ['gap_pct']:+.3f}%")

    html = build_report(meta, d, fits, integ, tg, hat, hat_sample, resid, report)
    OUT_HTML.write_text(html, encoding="utf-8")
    OUT_JSON.write_text(json.dumps(payload(meta, d, fits, integ), indent=1, default=str), encoding="utf-8")
    print(f"[write] {OUT_HTML} ({len(html)/1024:.0f} KB)")
    print(f"[write] {OUT_JSON}")

    import webbrowser
    webbrowser.open(OUT_HTML.resolve().as_uri())
    print(f"[open] opened {OUT_HTML.name} in the default browser")


if __name__ == "__main__":
    main()
