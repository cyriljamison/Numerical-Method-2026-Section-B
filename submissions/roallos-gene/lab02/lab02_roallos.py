#!/usr/bin/env python3
"""
NM-LAB-08252026  ·  Numerical Methods Laboratory Activity 02
Depth / reservoir-stage analysis: finite-difference derivatives,
nonlinear curve fit (Levenberg-Marquardt), residual diagnostics,
and integration of the fitted stage curve.

Produces a single self-contained HTML report with three tabs.
Requires: pandas, numpy, scipy, matplotlib, plotly
"""

import os
import textwrap
import base64
from io import BytesIO
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.integrate import quad
from scipy import stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

# ---------------------------------------------------------------------------
# 0. Data loader (carried forward from previous activity)
# ---------------------------------------------------------------------------
def load_depth_data(file_path: str) -> pd.DataFrame:
    """Load the Excel file and normalize its headers to a timestamp + depth table."""
    try:
        df = pd.read_excel(file_path, header=3)
    except Exception:
        df = pd.read_excel(file_path, header=None)

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "Date" in df.columns and "Time" in df.columns and "Depth (m)" in df.columns:
        df["Timestamp"] = pd.to_datetime(
            df["Date"].astype(str).str.strip()
            + " "
            + df["Time"].astype(str).str.strip(),
            errors="coerce",
        )
        ts_col = "Timestamp"
        depth_col = "Depth (m)"
    elif "Timestamp" in df.columns and "Depth (m)" in df.columns:
        ts_col = "Timestamp"
        depth_col = "Depth (m)"
    else:
        lower = {str(c).strip().lower(): c for c in df.columns}
        ts_col = None
        for key in ["timestamp", "date", "time"]:
            if key in lower:
                ts_col = lower[key]
                break
        if ts_col is None:
            for c in df.columns:
                c_lower = str(c).lower()
                if "time" in c_lower or "date" in c_lower:
                    ts_col = c
                    break

        depth_col = None
        for c in df.columns:
            c_lower = str(c).lower()
            if "depth" in c_lower:
                depth_col = c
                break

        if ts_col is None or depth_col is None:
            raise ValueError(f"Could not find timestamp and depth columns in: {list(df.columns)}")

        if "Date" in df.columns and "Time" in df.columns and ts_col in {"Date", "Time"}:
            df["Timestamp"] = pd.to_datetime(
                df["Date"].astype(str).str.strip() + " " + df["Time"].astype(str).str.strip()
            )
            ts_col = "Timestamp"
        elif "Date" in df.columns and ts_col == "Date":
            df["Timestamp"] = pd.to_datetime(df["Date"])
            ts_col = "Timestamp"

    df = df[[ts_col, depth_col]].copy()
    df[ts_col] = pd.to_datetime(df[ts_col])
    df = df.dropna(subset=[ts_col, depth_col]).reset_index(drop=True)
    df = df.sort_values(by=ts_col).reset_index(drop=True)
    df = df.rename(columns={ts_col: "Timestamp", depth_col: "Depth (m)"})
    return df


# ---------------------------------------------------------------------------
# 1. Load data and convert time axis to hours elapsed
# ---------------------------------------------------------------------------
file_path = r"C:\Users\lowelle\Downloads\Data 01.xlsx"
df = load_depth_data(file_path)

df["Timestamp"] = pd.to_datetime(df["Timestamp"])
df = df.dropna(subset=["Timestamp", "Depth (m)"]).reset_index(drop=True)
df = df.sort_values(by="Timestamp").reset_index(drop=True)

t_dates = df["Timestamp"]
t0 = t_dates.iloc[0]
t_hours = (t_dates - t0).dt.total_seconds().to_numpy(dtype=float) / 3600.0   # hours from first reading
h = df["Depth (m)"].to_numpy(dtype=float)
n = len(h)

print(f"Loaded {n} readings.  Time span: {t_hours[-1]:.2f} h  |  Depth range: {h.min():.3f} – {h.max():.3f} m")

# ---------------------------------------------------------------------------
# 2. TAB 1 – Finite-difference derivatives (hours axis, m/h)
#    Forward at start, backward at end, central in the interior.
# ---------------------------------------------------------------------------
dhdt = np.full(n, np.nan)          # first derivative (m/h)
d2hdt2 = np.full(n, np.nan)        # second derivative (m/h²)

# Central first derivative (interior)
for i in range(1, n - 1):
    dt = t_hours[i + 1] - t_hours[i - 1]
    if dt > 0:
        dhdt[i] = (h[i + 1] - h[i - 1]) / dt

# Forward at left end
if n > 1 and (t_hours[1] - t_hours[0]) > 0:
    dhdt[0] = (h[1] - h[0]) / (t_hours[1] - t_hours[0])

# Backward at right end
if n > 1 and (t_hours[-1] - t_hours[-2]) > 0:
    dhdt[-1] = (h[-1] - h[-2]) / (t_hours[-1] - t_hours[-2])

# Second derivative – central stencil on interior points
# (h[i+1] - 2*h[i] + h[i-1]) / ((Δt_half)^2) where Δt = t[i+1]-t[i-1]
for i in range(1, n - 1):
    dt = t_hours[i + 1] - t_hours[i - 1]
    if dt > 0:
        d2hdt2[i] = (h[i + 1] - 2.0 * h[i] + h[i - 1]) / ((dt / 2.0) ** 2)

# Forward / backward second differences near ends (same stencil shifted)
if n > 2:
    dt = t_hours[2] - t_hours[0]
    if dt > 0:
        d2hdt2[0] = (h[2] - 2.0 * h[1] + h[0]) / ((dt / 2.0) ** 2)
    dt = t_hours[-1] - t_hours[-3]
    if dt > 0:
        d2hdt2[-1] = (h[-1] - 2.0 * h[-2] + h[-3]) / ((dt / 2.0) ** 2)

# Maximum rate of rise
valid = ~np.isnan(dhdt)
idx_max = np.nanargmax(dhdt)
t_max_dhdt = t_hours[idx_max]
val_max_dhdt = dhdt[idx_max]
time_of_max = t0 + pd.Timedelta(hours=float(t_max_dhdt))

# Simple interpretation of the second derivative near the peak
# Look at the sign of d²h/dt² after the location of maximum dh/dt
post_peak = d2hdt2[idx_max:]
neg_frac = np.nanmean(post_peak < 0) if np.any(~np.isnan(post_peak)) else 0.0
if neg_frac > 0.6:
    d2_sentence = (
        "After the peak rate of rise the second derivative is predominantly negative, "
        "showing that inflow is decelerating as the reservoir approaches a new equilibrium level."
    )
elif neg_frac < 0.4:
    d2_sentence = (
        "After the peak rate of rise the second derivative remains largely positive, "
        "indicating that inflow is still accelerating and the filling event has not yet begun to ease."
    )
else:
    d2_sentence = (
        "The second derivative changes sign repeatedly after the peak rate of rise, "
        "suggesting that the inflow is unsteady and contains more than a single smooth pulse."
    )

print(f"Max dh/dt = {val_max_dhdt:.4f} m/h at t = {t_max_dhdt:.2f} h  ({time_of_max})")

# ---------------------------------------------------------------------------
# 3. TAB 2 – Model selection, Levenberg-Marquardt fit, statistics
# ---------------------------------------------------------------------------
# Model choice (stated before any fitting)
MODEL_DEFENSE = (
    "The four-parameter logistic is chosen because a single reservoir-filling event "
    "typically produces a sigmoidal stage curve that rises from a lower level toward "
    "an asymptotic ceiling after one clear inflection. "
    "This functional form captures the saturating behaviour without imposing the "
    "extra asymmetry of the Gompertz or the unnecessary flexibility of a sum of two logistics."
)

def logistic4(t, c, a, k, t0_):
    """Four-parameter logistic: h = c + a / (1 + exp(-k (t - t0)))"""
    return c + a / (1.0 + np.exp(-k * (t - t0_)))


# Initial guess derived from the data (not the default ones)
h_min, h_max = float(np.nanmin(h)), float(np.nanmax(h))
c0 = h_min                                          # lower asymptote ≈ minimum observed stage
a0 = h_max - h_min                                  # amplitude ≈ observed rise
# inflection near the time of maximum first derivative
t0_0 = float(t_max_dhdt)
# rough scale for k: the rise occurs over a few hours; start with k ≈ 1 h⁻¹
k0 = 1.0
p0 = [c0, a0, k0, t0_0]
print(f"Initial guess p0 = {p0}")

# Levenberg-Marquardt fit (no bounds)
popt, pcov = curve_fit(
    logistic4, t_hours, h,
    p0=p0,
    method="lm",
    maxfev=20000,
)
c_fit, a_fit, k_fit, t0_fit = popt
p = len(popt)                                       # number of parameters

# Fitted curve
h_hat = logistic4(t_hours, *popt)
resid = h - h_hat

# Required quantities (exact order requested)
sse = float(np.sum(resid ** 2))
sst = float(np.sum((h - h.mean()) ** 2))
r2 = 1.0 - sse / sst if sst > 0 else np.nan
s_est = float(np.sqrt(sse / (n - p)))               # standard error of the estimate
se = np.sqrt(np.diag(pcov))                         # SE of each parameter
tj = popt / se                                      # t-statistics
pval = 2.0 * (1.0 - stats.t.cdf(np.abs(tj), n - p)) # two-tailed p-values

param_names = ["c (lower asymptote)", "a (amplitude)", "k (growth rate)", "t0 (inflection time)"]
param_units = ["m", "m", "1/h", "h"]

print(f"R² = {r2:.4f}   SSE = {sse:.6f}   s = {s_est:.4f} m")

# Residual diagnostics (text answers)
mean_resid = float(np.mean(resid))
max_abs_resid = float(np.max(np.abs(resid)))
# simple run-length: count consecutive same-sign residuals
signs = np.sign(resid)
runs = 1
for i in range(1, len(signs)):
    if signs[i] != signs[i - 1] and signs[i] != 0 and signs[i - 1] != 0:
        runs += 1
# expected runs under randomness ≈ (2 n+ /n- )/n + 1 ; we just report qualitative
spread_early = float(np.std(resid[: n // 3]))
spread_late = float(np.std(resid[2 * n // 3 :]))

resid_text = []
if abs(mean_resid) < 0.005:
    resid_text.append("The residuals are centred on zero throughout; there is no systematic vertical bias.")
else:
    resid_text.append(f"The residuals have a mean of {mean_resid:.4f} m, indicating a small overall bias.")

if runs < n / 4:
    resid_text.append(
        "Long runs of the same sign are present, which means the shape of the logistic model "
        "does not fully capture the curvature of the data (the model form is inadequate)."
    )
else:
    resid_text.append("Runs of consecutive same-sign residuals are not unusually long; the model shape is acceptable.")

if spread_late > 1.5 * spread_early:
    resid_text.append("The residual spread widens as stage rises, suggesting mild heteroscedasticity.")
else:
    resid_text.append("The residual spread does not increase markedly with stage.")

if max_abs_resid > 0.01:
    resid_text.append(
        f"The largest residual is {max_abs_resid:.3f} m, which is {max_abs_resid / 0.01:.1f} times "
        "the logger’s 1 cm resolution; the discrepancy is therefore larger than measurement noise."
    )
else:
    resid_text.append(
        f"The largest residual is {max_abs_resid:.3f} m, comparable to the logger’s 1 cm resolution."
    )

if r2 > 0.98 and runs < n / 4:
    resid_text.append(
        "A high R² coexists with patterned residuals; this is therefore a failed fit in the sense "
        "required by the laboratory brief—an honest failure is reported rather than a flattering number."
    )

# ---------------------------------------------------------------------------
# 4. TAB 3 – Integration of the fitted stage
# ---------------------------------------------------------------------------
def integrand(t):
    return logistic4(t, *popt)

A_quad, abserr = quad(integrand, t_hours[0], t_hours[-1], epsabs=1e-6)
A_trap = float(np.trapezoid(h, t_hours))            # cross-check on raw readings

gap_sentence = (
    f"The analytic integral of the smooth logistic ({A_quad:.3f} m·h) differs from the "
    f"trapezoidal sum on the raw points ({A_trap:.3f} m·h) by {abs(A_quad - A_trap):.3f} m·h "
    "because the fitted curve ignores high-frequency logger noise and any small non-logistic wiggles "
    "that the trapezoidal rule still captures."
)

meaning_sentence = (
    "To the flood-control office the number is the time-integral of stage (meter-hours); "
    "it is a convenient scalar summary of how long and how high the water stood, useful for "
    "comparing events, but it is not a volume of water and cannot be converted to discharge "
    "without a stage-discharge rating and a storage-area curve."
)

print(f"∫ ĥ dt = {A_quad:.4f} ± {abserr:.2e} m·h   |   trapezoid raw = {A_trap:.4f} m·h")

# ---------------------------------------------------------------------------
# 5. Build interactive Plotly figures
# ---------------------------------------------------------------------------
# Colour palette
c_dark = "#0b4674"
c_med = "#176b57"
c_light = "#b7791f"
c_fit = "#b7791f"
c_resid = "#176b57"
plot_font = "Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"
plot_grid = "#dfe6dd"
plot_paper = "#fffdf7"
plot_background = "#fbfaf4"
plot_config = {
  "displaylogo": False,
  "responsive": True,
  "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}

# --- Tab 1 figures ---
fig1 = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    subplot_titles=(
        "Original stage (raw logger readings)",
        "First derivative dh/dt (m/h) – forward / central / backward",
        "Second derivative d²h/dt² (m/h²)",
    ),
)
fig1.add_trace(go.Scatter(x=t_hours, y=h, mode="lines", name="Raw depth",
                          line=dict(color=c_dark, width=2),
                          hovertemplate="t = %{x:.2f} h<br>depth = %{y:.3f} m<extra></extra>"), row=1, col=1)
fig1.add_trace(go.Scatter(x=t_hours, y=dhdt, mode="lines", name="dh/dt",
                          line=dict(color=c_med, width=2),
                          hovertemplate="t = %{x:.2f} h<br>dh/dt = %{y:.4f} m/h<extra></extra>"), row=2, col=1)
fig1.add_trace(go.Scatter(x=[t_max_dhdt], y=[val_max_dhdt], mode="markers",
                          name="Max dh/dt",
                          marker=dict(color=c_light, size=11, symbol="diamond"),
                          hovertemplate="peak = %{y:.4f} m/h<br>t = %{x:.2f} h<extra></extra>"), row=2, col=1)
fig1.add_trace(go.Scatter(x=t_hours, y=d2hdt2, mode="lines", name="d²h/dt²",
                          line=dict(color=c_light, width=2),
                          hovertemplate="t = %{x:.2f} h<br>d²h/dt² = %{y:.4f} m/h²<extra></extra>"), row=3, col=1)

fig1.update_layout(
    height=780, showlegend=False,
    margin=dict(l=72, r=28, t=54, b=48),
    title=dict(text="Raw log and finite-difference derivatives", x=0.02, xanchor="left",
           font=dict(size=18, color="#17231d")),
    paper_bgcolor=plot_paper, plot_bgcolor=plot_background,
    font=dict(family=plot_font, size=12, color="#405047"),
)
fig1.update_xaxes(showgrid=True, gridcolor=plot_grid, zeroline=False, fixedrange=False)
fig1.update_yaxes(showgrid=True, gridcolor=plot_grid, zeroline=False, fixedrange=False)
fig1.update_xaxes(title_text="Hours elapsed from first reading", row=3, col=1)
fig1.update_yaxes(title_text="Depth (m)", row=1, col=1)
fig1.update_yaxes(title_text="dh/dt (m/h)", row=2, col=1)
fig1.update_yaxes(title_text="d²h/dt² (m/h²)", row=3, col=1)

# --- Tab 2 figures ---
fig2a = go.Figure()
fig2a.add_trace(go.Scatter(x=t_hours, y=h, mode="markers", name="Observed",
               marker=dict(color=c_dark, size=5, opacity=0.72),
               hovertemplate="t = %{x:.2f} h<br>observed = %{y:.3f} m<extra></extra>"))
fig2a.add_trace(go.Scatter(x=t_hours, y=h_hat, mode="lines", name="Fitted logistic",
               line=dict(color=c_fit, width=3),
               hovertemplate="t = %{x:.2f} h<br>fit = %{y:.3f} m<extra></extra>"))
fig2a.update_layout(
    title="Observed stage and four-parameter logistic fit",
    xaxis_title="Hours elapsed from first reading",
    yaxis_title="Depth (m)",
  height=420, margin=dict(l=72, r=28, t=58, b=52),
  paper_bgcolor=plot_paper, plot_bgcolor=plot_background,
  font=dict(family=plot_font, size=12, color="#405047"),
  legend=dict(x=0.02, y=0.98, bgcolor="rgba(255,253,247,.82)", bordercolor=plot_grid, borderwidth=1),
)
fig2a.update_xaxes(showgrid=True, gridcolor=plot_grid, zeroline=False)
fig2a.update_yaxes(showgrid=True, gridcolor=plot_grid, zeroline=False)

fig2b = make_subplots(rows=1, cols=2, subplot_titles=("Residuals vs time", "Residuals vs fitted value"),
                      horizontal_spacing=0.12)
fig2b.add_trace(go.Scatter(x=t_hours, y=resid, mode="markers",
                           marker=dict(color=c_resid, size=5, opacity=0.72),
                           hovertemplate="t = %{x:.2f} h<br>residual = %{y:.4f} m<extra></extra>",
                           name="eᵢ"), row=1, col=1)
fig2b.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
fig2b.add_trace(go.Scatter(x=h_hat, y=resid, mode="markers",
                           marker=dict(color=c_resid, size=5, opacity=0.72),
                           hovertemplate="fit = %{x:.3f} m<br>residual = %{y:.4f} m<extra></extra>",
                           name="eᵢ"), row=1, col=2)
fig2b.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=2)
fig2b.update_layout(height=380, showlegend=False, margin=dict(l=72, r=28, t=58, b=52),
                    paper_bgcolor=plot_paper, plot_bgcolor=plot_background,
                    font=dict(family=plot_font, size=12, color="#405047"))
fig2b.update_xaxes(showgrid=True, gridcolor=plot_grid, zeroline=False)
fig2b.update_yaxes(showgrid=True, gridcolor=plot_grid, zeroline=False)
fig2b.update_xaxes(title_text="Hours elapsed", row=1, col=1)
fig2b.update_xaxes(title_text="Fitted depth ĥ (m)", row=1, col=2)
fig2b.update_yaxes(title_text="Residual eᵢ (m)", row=1, col=1)

# --- Tab 3 figure ---
t_fine = np.linspace(t_hours[0], t_hours[-1], 500)
h_fine = logistic4(t_fine, *popt)
fig3 = go.Figure()
fig3.add_trace(go.Scatter(x=t_fine, y=h_fine, mode="lines", name="Fitted ĥ(t)",
                          line=dict(color=c_fit, width=3),
                          fill="tozeroy", fillcolor="rgba(23,107,87,0.18)",
                          hovertemplate="t = %{x:.2f} h<br>fit = %{y:.3f} m<extra></extra>"))
fig3.add_trace(go.Scatter(x=t_hours, y=h, mode="markers", name="Raw readings",
                          marker=dict(color=c_dark, size=5, opacity=0.65),
                          hovertemplate="t = %{x:.2f} h<br>observed = %{y:.3f} m<extra></extra>"))
fig3.update_layout(
    title=f"Area under the fitted curve  A = ∫ ĥ(t) dt = {A_quad:.3f} m·h",
    xaxis_title="Hours elapsed from first reading",
    yaxis_title="Depth (m)",
    height=420, margin=dict(l=72, r=28, t=58, b=52),
    paper_bgcolor=plot_paper, plot_bgcolor=plot_background,
    font=dict(family=plot_font, size=12, color="#405047"),
    legend=dict(x=0.02, y=0.98, bgcolor="rgba(255,253,247,.82)", bordercolor=plot_grid, borderwidth=1),
)
fig3.update_xaxes(showgrid=True, gridcolor=plot_grid, zeroline=False)
fig3.update_yaxes(showgrid=True, gridcolor=plot_grid, zeroline=False)

# Convert figures to HTML divs (no full page, no repeated plotly.js)
fig_stage = go.Figure()
fig_stage.add_trace(go.Scatter(x=t_hours, y=h, mode="lines", name="Depth",
                 line=dict(color=c_dark, width=2)))
fig_stage.update_layout(
  height=300, showlegend=False,
  margin=dict(l=60, r=30, t=42, b=45),
  title="Stage log",
  xaxis_title="Hours elapsed from first reading",
  yaxis_title="Depth (m)",
)
div_stage = fig_stage.to_html(full_html=False, include_plotlyjs=True, config=plot_config)
div1 = fig1.to_html(full_html=False, include_plotlyjs=False, config=plot_config)
div2a = fig2a.to_html(full_html=False, include_plotlyjs=False, config=plot_config)
div2b = fig2b.to_html(full_html=False, include_plotlyjs=False, config=plot_config)
div3 = fig3.to_html(full_html=False, include_plotlyjs=False, config=plot_config)

# ---------------------------------------------------------------------------
# 6. Assemble the three-tab HTML report
# ---------------------------------------------------------------------------
# Parameter table rows
param_rows = ""
for name, unit, val, se_j, t_j, p_j in zip(param_names, param_units, popt, se, tj, pval):
    # quote to a sensible number of decimals given the logger resolution
    if unit == "m":
        val_str = f"{val:.3f}"
        se_str = f"{se_j:.3f}"
    elif unit == "1/h":
        val_str = f"{val:.3f}"
        se_str = f"{se_j:.3f}"
    else:  # hours
        val_str = f"{val:.2f}"
        se_str = f"{se_j:.2f}"
    param_rows += f"""
    <tr>
      <td>{name}</td>
      <td>{val_str} {unit}</td>
      <td>{se_str}</td>
      <td>{t_j:.2f}</td>
      <td>{p_j:.2e}</td>
    </tr>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lab 02 · Fitting a curve to the dam</title>
<style>
  :root {{ --bg:#f5f2e8; --panel:#fffdf7; --ink:#17231d; --dim:#65736b;
    --line:#d9dfd5; --blue:#176b57; --orange:#b7791f; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.62 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif; }}
  .navbar {{ max-width:1120px; margin:0 auto; padding:34px 26px 16px;
    border-bottom:2px solid var(--ink); background:transparent !important; }}
  .navbar .container-fluid {{ display:block; padding:0; }}
  .navbar-brand {{ display:block; color:var(--orange) !important; font:600 11px/1 ui-sans-serif,system-ui,sans-serif;
    letter-spacing:.16em; text-transform:uppercase; }}
  .navbar .small {{ display:block; color:var(--ink) !important; font:31px/1.2 Georgia,serif; margin-top:10px; }}
  .facts {{ display:flex; flex-wrap:wrap; gap:0 30px; margin-top:14px;
    font:12.5px/1.5 ui-sans-serif,system-ui,sans-serif; color:var(--dim); }}
  .facts b {{ color:var(--ink); font-weight:600; }}
  .container-fluid {{ max-width:1120px; margin:0 auto; padding:22px 26px 90px; }}
  .nav-tabs {{ display:flex; flex-wrap:wrap; gap:7px; margin:0 0 20px; padding:0;
    border-bottom:2px solid var(--orange); list-style:none; }}
  .nav-item {{ list-style:none; }}
  .nav-link {{ appearance:none; background:#e6ebe3; color:#405047; border:1px solid #cbd6ca;
    border-bottom:0; border-radius:7px 7px 0 0; padding:12px 22px; cursor:pointer;
    font:600 14px ui-sans-serif,system-ui,sans-serif; }}
  .nav-link:hover {{ background:#f8f6ee; color:var(--ink); }}
  .nav-link.active {{ background:var(--orange); color:#fff; border-color:var(--orange); }}
  .tab-pane {{ display:none; padding-top:0; }}
  .tab-pane.active {{ display:block; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:5px;
    box-shadow:none; margin-bottom:20px; }}
  .card-header {{ background:transparent; border-bottom:0; padding:20px 22px 2px;
    font-size:19px; font-weight:600; color:var(--ink); }}
  .card-body {{ padding:0 22px 20px; }}
  .stage-log {{ margin-bottom:22px; }}
  .stage-log .card-body {{ padding-top:0; }}
  .stage-log .lede {{ color:var(--dim); margin:0 0 10px; font-size:14px; }}
  .headline {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:0;
    border:1px solid var(--line); border-radius:5px; overflow:hidden; background:var(--panel); margin:18px 0 22px; }}
  .hl {{ padding:13px 16px; border-right:1px solid var(--line); }}
  .hl:last-child {{ border-right:0; }}
  .hlv {{ font:700 25px/1.1 "SFMono-Regular",Consolas,monospace; color:var(--blue); }}
  .hlu {{ font-size:13px; font-weight:600; color:var(--dim); }}
  .hll {{ font:11.5px/1.35 ui-sans-serif,system-ui,sans-serif; color:var(--dim); margin-top:4px; }}
  .tabhint {{ font:600 10.5px ui-sans-serif,system-ui,sans-serif; letter-spacing:.11em;
    text-transform:uppercase; color:var(--dim); margin:30px 0 7px; }}
  .metric {{ font:700 25px/1.2 "SFMono-Regular",Consolas,monospace; color:var(--blue); }}
  .unit {{ font-size:13px; font-weight:600; color:var(--dim); }}
  .sentence {{ background:#fff8e7; border-left:3px solid var(--orange); padding:12px 16px; margin:16px 0; }}
  .defense {{ background:#edf7f1; border-left:3px solid var(--blue); padding:12px 16px; margin:16px 0; }}
  table.table {{ width:100%; border-collapse:collapse; margin:10px 0 4px; }}
  table.table td, table.table th {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:middle; font-size:.92rem; }}
  table.table th {{ color:var(--dim); font:600 11px ui-sans-serif,system-ui,sans-serif; text-transform:uppercase; }}
  .table-responsive {{ overflow-x:auto; }}
  code {{ background:#18352b; color:#f4f0e5; border-radius:4px; padding:2px 5px; }}
  footer {{ color:var(--dim); font-size:12.5px; border-top:1px solid var(--line); padding-top:14px; margin-top:26px; }}
  @media (max-width:700px) {{ .navbar,.container-fluid {{ padding-left:16px; padding-right:16px; }}
    .navbar .small {{ font-size:25px; }} .nav-link {{ padding:10px 13px; }} }}
</style>
</head>
<body>
<nav class="navbar">
  <div class="container-fluid">
    <span class="navbar-brand">Numerical Methods · Laboratory Activity 02</span>
    <span class="small">Fitting a curve to the dam</span>
    <span style="display:block;color:#6c7280;font-size:15px;">Levenberg-Marquardt, residuals, and the area under the level</span>
    <div class="facts">
      <span>Student <b>Roallos, Gene Lowelle</b></span>
      <span>Section <b>BES6-M</b></span>
      <span>Dataset <b>{os.path.basename(file_path)}</b></span>
      <span>Readings <b>{n}</b> at <b>0.25 h</b></span>
      <span>Window <b>{t_hours[-1]:.2f} h</b></span>
    </div>
  </div>
</nav>

<div class="container-fluid py-3">
  <div class="card stage-log">
    <div class="card-header">Stage log</div>
    <div class="card-body">
      <p class="lede">{n} readings at approximately 0.25 h, {t_hours[-1]:.2f} h of record. Always visible, never behind a tab.</p>
      {div_stage}
    </div>
  </div>
  <div class="headline">
    <div class="hl"><div class="hlv">{h.max():.2f}<span class="hlu"> m</span></div><div class="hll">Observed crest</div></div>
    <div class="hl"><div class="hlv">+{h.max() - h.min():.2f}<span class="hlu"> m</span></div><div class="hll">Total observed rise</div></div>
    <div class="hl"><div class="hlv">{val_max_dhdt:.4f}<span class="hlu"> m/h</span></div><div class="hll">Peak finite difference</div></div>
    <div class="hl"><div class="hlv">{r2:.4f}</div><div class="hll">R² of fitted level</div></div>
    <div class="hl"><div class="hlv">{A_quad:.1f}<span class="hlu"> m·h</span></div><div class="hll">Area under fitted level</div></div>
  </div>
  <p class="tabhint">Three panels · click a tab to switch</p>
  <ul class="nav nav-tabs" id="labTabs" role="tablist">
    <li class="nav-item" role="presentation">
      <button class="nav-link active" id="tab1-btn" data-bs-toggle="tab" data-bs-target="#tab1"
              type="button" role="tab">1 · Derivatives</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="tab2-btn" data-bs-toggle="tab" data-bs-target="#tab2"
              type="button" role="tab">2 · Fitted curve</button>
    </li>
    <li class="nav-item" role="presentation">
      <button class="nav-link" id="tab3-btn" data-bs-toggle="tab" data-bs-target="#tab3"
              type="button" role="tab">3 · Area under the curve</button>
    </li>
  </ul>

  <div class="tab-content" id="labTabContent">

    <!-- ===================== TAB 1 ===================== -->
    <div class="tab-pane fade show active" id="tab1" role="tabpanel">
      <div class="card">
        <div class="card-header">Finite-difference derivatives (carried forward from previous activity)</div>
        <div class="card-body">
          <p>
            Timestamps were converted to a numeric axis of <strong>hours elapsed from the first reading</strong>.
            The sampling interval is approximately 0.25 h; all derivatives are therefore expressed in
            metres per hour (m/h) and metres per hour squared (m/h²).  Forward differences are used at the
            left endpoint, backward differences at the right endpoint, and central differences everywhere
            in between.  The same time origin and units are retained for the remainder of the activity.
          </p>
          <div class="row text-center mb-3">
            <div class="col-md-4">
              <div class="metric">{val_max_dhdt:.4f} <span class="unit">m/h</span></div>
              <div>Maximum dh/dt</div>
            </div>
            <div class="col-md-4">
              <div class="metric">{t_max_dhdt:.2f} <span class="unit">h</span></div>
              <div>Time of maximum (from first reading)</div>
            </div>
            <div class="col-md-4">
              <div class="metric" style="font-size:1.05rem;">{time_of_max.strftime('%Y-%m-%d %H:%M')}</div>
              <div>Clock time of maximum</div>
            </div>
          </div>
          <div class="sentence">
            <strong>Second-derivative interpretation:</strong> {d2_sentence}
          </div>
        </div>
      </div>
      {div1}
    </div>

    <!-- ===================== TAB 2 ===================== -->
    <div class="tab-pane fade" id="tab2" role="tabpanel">
      <div class="card">
        <div class="card-header">Model choice &amp; defence (stated before any fitting)</div>
        <div class="card-body">
          <div class="defense">{MODEL_DEFENSE}</div>
          <p class="mb-1"><strong>Initial guess p₀</strong> (derived from the data, not the default ones):</p>
          <ul>
            <li>c₀ = {c0:.3f} m &nbsp;– lower asymptote taken as the minimum observed stage;</li>
            <li>a₀ = {a0:.3f} m &nbsp;– amplitude taken as the observed rise (max − min);</li>
            <li>k₀ = {k0:.1f} h⁻¹ &nbsp;– order-of-magnitude growth-rate scale;</li>
            <li>t₀₀ = {t0_0:.2f} h &nbsp;– inflection placed at the already-computed time of maximum dh/dt.</li>
          </ul>
        </div>
      </div>

      <div class="card">
        <div class="card-header">Fitted parameters, standard errors, t-statistics and p-values</div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table table-sm table-striped">
              <thead class="table-light">
                <tr>
                  <th>Parameter</th>
                  <th>Estimate</th>
                  <th>SE</th>
                  <th>t-statistic</th>
                  <th>p-value (two-tailed)</th>
                </tr>
              </thead>
              <tbody>
                {param_rows}
              </tbody>
            </table>
          </div>
          <div class="row text-center mt-3">
            <div class="col-md-3"><div class="metric">{r2:.4f}</div><div>R²</div></div>
            <div class="col-md-3"><div class="metric">{sse:.5f}</div><div>SSE (m²)</div></div>
            <div class="col-md-3"><div class="metric">{s_est:.4f}</div><div>s (m)</div></div>
            <div class="col-md-3"><div class="metric">{n} / {p}</div><div>n / p</div></div>
          </div>
        </div>
      </div>

      {div2a}
      {div2b}

      <div class="card mt-3">
        <div class="card-header">Residual diagnostics (required written answers)</div>
        <div class="card-body">
          <ul>
            {"".join(f"<li>{s}</li>" for s in resid_text)}
          </ul>
        </div>
      </div>
    </div>

    <!-- ===================== TAB 3 ===================== -->
    <div class="tab-pane fade" id="tab3" role="tabpanel">
      <div class="card">
        <div class="card-header">Definite integral of the fitted stage</div>
        <div class="card-body">
          <p>
            The fitted logistic is integrated analytically with <code>scipy.integrate.quad</code>
            from the first to the last logged time.  The reference line is the time axis (h = 0).
          </p>
          <div class="row text-center my-3">
            <div class="col-md-4">
              <div class="metric">{A_quad:.3f}</div>
              <div>∫ ĥ(t) dt &nbsp;<span class="unit">m·h</span></div>
            </div>
            <div class="col-md-4">
              <div class="metric">{abserr:.2e}</div>
              <div>Absolute error estimate (quad)</div>
            </div>
            <div class="col-md-4">
              <div class="metric">{A_trap:.3f}</div>
              <div>Trapezoidal (raw points) &nbsp;<span class="unit">m·h</span></div>
            </div>
          </div>
          <div class="sentence">
            <strong>Why the two numbers differ:</strong> {gap_sentence}
          </div>
          <div class="sentence">
            <strong>Meaning for the flood-control office:</strong> {meaning_sentence}
          </div>
        </div>
      </div>
      {div3}
    </div>

  </div><!-- /tab-content -->

  <footer class="text-center">
    Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} · Data file: {os.path.basename(file_path)} ·
    Time origin = first reading · All derivatives and integrals use hours elapsed
  </footer>
</div>

<script>
  document.querySelectorAll('#labTabs .nav-link').forEach(function (button) {{
    button.addEventListener('click', function () {{
      document.querySelectorAll('#labTabs .nav-link').forEach(function (item) {{ item.classList.remove('active'); }});
      document.querySelectorAll('#labTabContent .tab-pane').forEach(function (panel) {{ panel.classList.remove('active'); }});
      button.classList.add('active');
      document.querySelector(button.dataset.bsTarget).classList.add('active');
    }});
  }});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# 7. Write the HTML file
# ---------------------------------------------------------------------------
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else ".",
                        "Lab02_Reservoir_Stage_Report.html")
# Prefer current working directory for the user’s convenience
out_path = "Lab02_Reservoir_Stage_Report.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nHTML report written to: {os.path.abspath(out_path)}")
print("Open the file in any modern browser to view the three interactive tabs.")

# ---------------------------------------------------------------------------
# 8. Export a concise one-page results sheet
# ---------------------------------------------------------------------------
desktop_candidates = [
  os.path.join(os.path.expanduser("~"), "Desktop"),
  os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
]
desktop_path = next((path for path in desktop_candidates if os.path.isdir(path)), desktop_candidates[0])
pdf_path = os.path.join(desktop_path, "lab02_roallos_results.pdf")
pdf_fig = plt.figure(figsize=(8.27, 11.69), facecolor="#f5f2e8")
pdf_ax = pdf_fig.add_axes([0.09, 0.06, 0.82, 0.88])
pdf_ax.axis("off")

pdf_fig.text(0.09, 0.95, "LABORATORY ACTIVITY 02", fontsize=10, fontweight="bold",
             color="#b7791f", va="top")
pdf_fig.text(0.09, 0.915, "Fitted curve results", fontsize=25, fontweight="bold",
             color="#17231d", va="top")
pdf_fig.text(0.09, 0.875, "Roallos, Gene Lowelle  |  Four-parameter logistic model",
             fontsize=11, color="#65736b", va="top")
pdf_fig.lines.append(plt.Line2D([0.09, 0.91], [0.845, 0.845], color="#17231d", linewidth=1.5,
                                transform=pdf_fig.transFigure))

pdf_fig.text(0.09, 0.81, "Fitted parameters", fontsize=15, fontweight="bold",
             color="#17231d", va="top")
table_data = [["Parameter", "Estimate", "Standard error", "t-statistic", "p-value"]]
for name, unit, value, se_j, t_j, p_j in zip(param_names, param_units, popt, se, tj, pval):
  value_fmt = f"{value:.2f}" if unit == "h" else f"{value:.3f}"
  se_fmt = f"{se_j:.2f}" if unit == "h" else f"{se_j:.3f}"
  table_data.append([name, f"{value_fmt} {unit}", se_fmt, f"{t_j:.2f}", f"{p_j:.2e}"])
pdf_table = pdf_ax.table(cellText=table_data, cellLoc="left", colWidths=[0.31, 0.17, 0.19, 0.17, 0.16],
             bbox=[0, 0.64, 1, 0.14])
pdf_table.auto_set_font_size(False)
pdf_table.set_fontsize(9)
for (row, col), cell in pdf_table.get_celld().items():
  cell.set_edgecolor("#d9dfd5")
  cell.set_facecolor("#e7eee5" if row == 0 else "#fffdf7")
  cell.set_text_props(color="#17231d", weight="bold" if row == 0 else "normal")

pdf_fig.text(0.09, 0.60, "Fit statistics and integration", fontsize=15, fontweight="bold",
             color="#17231d", va="top")
stat_data = [
  ["SSE", f"{sse:.6f} m²", "R²", f"{r2:.4f}"],
  ["s", f"{s_est:.4f} m", "Degrees of freedom", f"{n - p}"],
  ["Area under fitted curve", f"{A_quad:.4f} m·h", "Quadrature error", f"{abserr:.2e} m·h"],
]
stat_table = pdf_ax.table(cellText=stat_data, cellLoc="left", colWidths=[0.27, 0.23, 0.27, 0.23],
                          bbox=[0, 0.45, 1, 0.11])
stat_table.auto_set_font_size(False)
stat_table.set_fontsize(10)
for (row, col), cell in stat_table.get_celld().items():
  cell.set_edgecolor("#d9dfd5")
  cell.set_facecolor("#fffdf7")
  if col in (0, 2):
    cell.set_text_props(color="#176b57", weight="bold")

pdf_fig.text(0.09, 0.37, "Reading of the residuals", fontsize=15, fontweight="bold",
             color="#17231d", va="top")
residual_paragraph = " ".join(resid_text)
wrapped_residuals = "\n".join(textwrap.wrap(residual_paragraph, width=92))
pdf_fig.text(0.09, 0.335, wrapped_residuals, fontsize=9.5, color="#17231d",
             va="top", linespacing=1.35,
             bbox=dict(facecolor="#edf7f1", edgecolor="#176b57", linewidth=1,
                       boxstyle="square,pad=0.8"))
pdf_fig.text(0.09, 0.06, "Data: " + os.path.basename(file_path) +
             "  |  Time axis: hours elapsed from first reading",
             fontsize=8.5, color="#65736b", va="bottom")
pdf_fig.savefig(pdf_path, format="pdf", facecolor=pdf_fig.get_facecolor())
plt.close(pdf_fig)
print(f"One-page PDF results written to: {pdf_path}")