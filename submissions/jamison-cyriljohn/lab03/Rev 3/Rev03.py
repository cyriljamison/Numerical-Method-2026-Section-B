#!/usr/bin/env python3
"""
rev3.py
================================================================================
Revit 3 Solver -- local web server.

Serves the single-file web app (Pyodide + Plotly + the full 3D space-frame
stiffness solver) on http://localhost:<port>/ using only the Python standard
library.

Usage
-----
    python rev3.py                  # port 8000, opens browser
    python rev3.py --port 9000      # custom port
    python rev3.py --no-browser     # don't auto-open browser
    python rev3.py --host 0.0.0.0   # bind all interfaces (LAN access)

Press Ctrl+C to stop the server.
"""

import argparse
import http.server
import socket
import sys
import threading
import webbrowser


# =============================================================================
# The complete single-file web application.
# NOTE: the outer delimiter is ''' (single-quote triple) on purpose -- the
# embedded Pyodide Python source contains """ docstrings, which would
# otherwise terminate this string early and cause a SyntaxError.
# =============================================================================
HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Revit 3 Solver — Web Edition</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js"></script>
<style>
  :root {
    --bg: #0b1220;
    --panel: #121b2e;
    --panel-2: #1a2540;
    --border: #2a3654;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --accent-2: #22c55e;
    --warn: #f59e0b;
    --danger: #ef4444;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
  }
  header {
    display: flex; align-items: center; gap: 16px;
    padding: 12px 20px; background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  header h1 { margin: 0; font-size: 18px; letter-spacing: .3px; }
  header .subtitle { color: var(--muted); font-size: 12px; }
  header .spacer { flex: 1; }

  button {
    background: var(--panel-2); color: var(--text);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 8px 14px; cursor: pointer; font-size: 13px; font-weight: 500;
    transition: background .15s, border-color .15s;
  }
  button:hover:not(:disabled) { background: #24334f; border-color: #3d4d70; }
  button:disabled { opacity: .5; cursor: not-allowed; }
  button.primary {
    background: var(--accent); border-color: var(--accent); color: #06202f;
    font-weight: 600;
  }
  button.primary:hover:not(:disabled) { background: #5cc8fb; border-color: #5cc8fb; }
  button.danger { color: var(--danger); border-color: #4a1f24; }
  button.danger:hover:not(:disabled) { background: #2a1114; }

  input, select {
    background: var(--panel-2); color: var(--text);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 7px 9px; font-size: 13px; width: 100%;
    font-family: inherit;
  }
  input:focus, select:focus { outline: none; border-color: var(--accent); }

  .layout {
    display: grid; grid-template-columns: 380px 1fr;
    height: calc(100vh - 58px);
  }
  .sidebar { overflow-y: auto; background: var(--panel); border-right: 1px solid var(--border); padding: 16px; }
  .main { overflow-y: auto; padding: 16px 20px 40px; }

  .section-title {
    font-size: 11px; letter-spacing: 1.2px; text-transform: uppercase;
    color: var(--muted); margin: 18px 0 8px;
  }
  .section-title:first-child { margin-top: 0; }

  .field { margin-bottom: 10px; }
  .field label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }

  .member-block {
    background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 8px; padding: 10px; margin-bottom: 10px;
  }
  .member-block h4 {
    margin: 0 0 8px; font-size: 13px; display: flex; align-items: center; gap: 6px;
  }
  .swatch { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }

  .load-row {
    display: grid; grid-template-columns: 60px 1fr 1fr 1fr 1fr 1fr 1fr 28px;
    gap: 4px; align-items: center; margin-bottom: 4px;
  }
  .load-row input, .load-row select { padding: 5px 6px; font-size: 12px; text-align: right; }
  .load-row select { text-align: center; }
  .load-head { display: grid; grid-template-columns: 60px 1fr 1fr 1fr 1fr 1fr 1fr 28px; gap: 4px; }
  .load-head span { font-size: 10px; color: var(--muted); text-align: center; }
  .icon-btn {
    padding: 4px 6px; font-size: 12px; line-height: 1;
    background: transparent; border: 1px solid var(--border); border-radius: 4px;
  }

  .tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 12px; }
  .tab {
    padding: 8px 14px; border: none; background: transparent; color: var(--muted);
    border-bottom: 2px solid transparent; border-radius: 0; cursor: pointer;
    font-size: 13px; font-weight: 500;
  }
  .tab:hover:not(.active) { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  #plot { width: 100%; height: 620px; background: #0a101c; border-radius: 8px;
           border: 1px solid var(--border); }

  .status {
    padding: 8px 12px; border-radius: 6px; font-size: 12px; margin-bottom: 12px;
    background: var(--panel-2); border: 1px solid var(--border); color: var(--muted);
    display: flex; align-items: center; gap: 8px;
  }
  .status.ok { color: var(--accent-2); border-color: #1e3d2a; background: #0f2418; }
  .status.err { color: var(--danger); border-color: #4a1f24; background: #2a1114; }
  .status .dot {
    width: 8px; height: 8px; border-radius: 50%; background: currentColor;
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .3; } }

  table {
    width: 100%; border-collapse: collapse; font-size: 12px;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
  }
  th, td {
    padding: 6px 10px; text-align: right; border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }
  th { color: var(--muted); font-weight: 500; background: var(--panel-2);
       position: sticky; top: 0; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
  tr:hover td { background: rgba(56, 189, 248, .05); }

  .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 16px; }
  .kpi {
    background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 8px; padding: 12px 14px;
  }
  .kpi .label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
  .kpi .value { font-size: 18px; font-weight: 600; margin-top: 4px;
                font-family: ui-monospace, monospace; }
  .kpi .unit { font-size: 12px; color: var(--muted); font-weight: 400; }

  .card {
    background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 8px; padding: 12px; margin-bottom: 14px;
  }
  .card h3 { margin: 0 0 8px; font-size: 13px; color: var(--muted);
             text-transform: uppercase; letter-spacing: .8px; font-weight: 500; }

  .checkbox-row { display: flex; align-items: center; gap: 8px; margin: 8px 0; }
  .checkbox-row input { width: auto; }
  .checkbox-row label { color: var(--text); font-size: 13px; }

  .help { color: var(--muted); font-size: 12px; line-height: 1.6; }
  code { background: var(--panel-2); padding: 1px 5px; border-radius: 3px;
         font-size: 12px; color: var(--accent); }

  .btn-row { display: flex; gap: 8px; margin-top: 8px; }
</style>
</head>
<body>

<header>
  <div>
    <h1>Revit 3 Solver — Web Edition</h1>
    <div class="subtitle">3D space-frame stiffness solver · runs entirely in your browser</div>
  </div>
  <div class="spacer"></div>
  <div style="width:170px;">
    <select id="unit-system">
      <option value="metric" selected>Metric (m, kN, MPa)</option>
      <option value="imperial">Imperial (ft, kip, ksi)</option>
    </select>
  </div>
  <button id="run-btn" class="primary" disabled>Solve</button>
  <button id="download-btn" disabled>Download CSV</button>
</header>

<div class="layout">
  <aside class="sidebar">
    <div id="load-status" class="status">
      <span class="dot"></span><span id="status-text">Loading Python runtime…</span>
    </div>

    <div class="section-title">Member Assignment</div>
    <div id="member-assignments"></div>

    <div class="section-title">Loads</div>
    <div class="checkbox-row">
      <input type="checkbox" id="self-weight" checked>
      <label for="self-weight">Include self-weight (computed from section + density)</label>
    </div>
    <div class="card">
      <div class="load-head" style="margin-bottom:6px;">
        <span>Node</span><span>Fx</span><span>Fy</span><span>Fz</span>
        <span>Mx</span><span>My</span><span>Mz</span><span></span>
      </div>
      <div id="load-rows"></div>
      <div class="btn-row">
        <button id="add-load-btn" style="flex:1;">+ Add load</button>
      </div>
      <div class="help" style="margin-top:8px;">
        Force unit: kN (metric) / kip (imperial). Moments auto-matched.
      </div>
    </div>

    <div class="section-title">About</div>
    <div class="help">
      This app embeds the solver from <code>solver.py</code> and runs it via
      Pyodide (Python → WebAssembly). All computation happens locally — nothing
      is uploaded. Change an assignment or a load and re-solve to see the
      stiffness matrix respond.
    </div>
  </aside>

  <main class="main">
    <div id="kpis" class="kpi-row"></div>

    <div class="tabs">
      <button class="tab active" data-tab="view">3D View</button>
      <button class="tab" data-tab="disp">Displacements</button>
      <button class="tab" data-tab="react">Reactions</button>
      <button class="tab" data-tab="forces">Member End Forces</button>
      <button class="tab" data-tab="members">Members</button>
    </div>

    <div class="tab-panel active" id="panel-view"><div id="plot"></div></div>
    <div class="tab-panel" id="panel-disp"><div class="card"><h3>Nodal Displacements</h3><div id="tbl-disp"></div></div></div>
    <div class="tab-panel" id="panel-react"><div class="card"><h3>Support Reactions</h3><div id="tbl-react"></div></div></div>
    <div class="tab-panel" id="panel-forces"><div class="card"><h3>Member End Forces (local axes)</h3><div id="tbl-forces"></div></div></div>
    <div class="tab-panel" id="panel-members"><div class="card"><h3>Member Schedule</h3><div id="tbl-members"></div></div></div>
  </main>
</div>

<!-- ============================================================================
     Python source, run inside Pyodide.
     ============================================================================ -->
<script type="text/x-python" id="python-source">
# ---------------------------------------------------------------------------
# Combined solver source (units.py + materials.py + sections.py + model.py +
# loads.py + solver.py), with thin JSON wrappers for the JS UI.
# ---------------------------------------------------------------------------
import json
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


# =========================== units.py ===========================
class Quantity(Enum):
    LENGTH_GEOM = "length_geom"
    LENGTH_SECTION = "length_section"
    AREA = "area"
    INERTIA = "inertia"
    SECTION_MODULUS = "section_modulus"
    FORCE = "force"
    MOMENT = "moment"
    STRESS = "stress"
    UNIT_WEIGHT = "unit_weight"
    THERMAL = "thermal"


@dataclass(frozen=True)
class _Factor:
    to_metric: float
    base_system: str
    imperial_label: str
    metric_label: str


_KIP_TO_KN = 4.4482216152605
_FT_TO_M = 0.3048

_CONVERSION_TABLE = {
    Quantity.LENGTH_GEOM:     _Factor(_FT_TO_M,              "metric",   "ft",      "m"),
    Quantity.LENGTH_SECTION:  _Factor(25.4,                  "imperial", "in",      "mm"),
    Quantity.AREA:            _Factor(645.16,                "imperial", "in^2",    "mm^2"),
    Quantity.INERTIA:         _Factor(416231.4256,           "imperial", "in^4",    "mm^4"),
    Quantity.SECTION_MODULUS: _Factor(16387.064,             "imperial", "in^3",    "mm^3"),
    Quantity.FORCE:           _Factor(_KIP_TO_KN,             "imperial", "kip",     "kN"),
    Quantity.MOMENT:          _Factor(_KIP_TO_KN * _FT_TO_M,  "imperial", "kip*ft",  "kN*m"),
    Quantity.STRESS:          _Factor(6.894757293168361,      "imperial", "ksi",     "MPa"),
    Quantity.UNIT_WEIGHT:     _Factor(157.08746384624624,     "imperial", "k/ft^3",  "kN/m^3"),
    Quantity.THERMAL:         _Factor(18.0,                   "imperial", "1e-5/F",  "1e-6/C"),
}

_SI_PREFIX_ADJUST = {
    Quantity.LENGTH_GEOM: 1.0,
    Quantity.LENGTH_SECTION: 1e-3,
    Quantity.AREA: 1e-6,
    Quantity.INERTIA: 1e-12,
    Quantity.SECTION_MODULUS: 1e-9,
    Quantity.FORCE: 1e3,
    Quantity.MOMENT: 1e3,
    Quantity.STRESS: 1e6,
    Quantity.UNIT_WEIGHT: 1e3,
    Quantity.THERMAL: None,
}

VALID_SYSTEMS = ("imperial", "metric")


class UnitSystem:
    def __init__(self, system="metric"):
        self.set_system(system)

    def set_system(self, system):
        if not self.validate(system):
            raise ValueError(f"Invalid unit system {system!r}.")
        self.system = system

    def convert(self, value, quantity):
        if value is None:
            return None
        f = _CONVERSION_TABLE[quantity]
        if self.system == f.base_system:
            return value
        if f.base_system == "imperial" and self.system == "metric":
            return value * f.to_metric
        if f.base_system == "metric" and self.system == "imperial":
            return value / f.to_metric
        return value

    def label(self, quantity):
        f = _CONVERSION_TABLE[quantity]
        return f.metric_label if self.system == "metric" else f.imperial_label

    @staticmethod
    def validate(system):
        return system in VALID_SYSTEMS


def to_si(value, quantity):
    if value is None:
        return None
    f = _CONVERSION_TABLE[quantity]
    adjust = _SI_PREFIX_ADJUST[quantity]
    if adjust is None:
        raise ValueError(f"{quantity} has no SI mapping.")
    metric_value = value if f.base_system == "metric" else value * f.to_metric
    return metric_value * adjust


def from_si(value, quantity):
    if value is None:
        return None
    f = _CONVERSION_TABLE[quantity]
    adjust = _SI_PREFIX_ADJUST[quantity]
    if adjust is None:
        raise ValueError(f"{quantity} has no SI mapping.")
    metric_value = value / adjust
    return metric_value if f.base_system == "metric" else metric_value / f.to_metric


# =========================== materials.py ===========================
@dataclass(frozen=True)
class Material:
    key: str
    category: str
    E: float
    G: float
    nu: float
    Fy: float
    Fu: Optional[float]
    density: float
    therm: float


class MaterialLibrary:
    def __init__(self):
        self._materials = {
            "A36 Gr.36":  Material("A36 Gr.36",  "Hot Rolled", 29000, 11154, 0.30, 36, 58,   0.49,  0.65),
            "A992":       Material("A992",       "Hot Rolled", 29000, 11154, 0.30, 50, 58,   0.49,  0.65),
            "A572 Gr.50": Material("A572 Gr.50", "Hot Rolled", 29000, 11154, 0.30, 50, 58,   0.49,  0.65),
            "Conc4000NW": Material("Conc4000NW", "Concrete",   3644,  1584,  0.15, 4,  None, 0.145, 0.60),
            "6061-T6":    Material("6061-T6",    "Aluminum",   10100, 3787.5, 0.33, 35, 38,  0.173, 1.30),
        }

    def get(self, key):
        if key not in self._materials:
            raise ValueError(f"Unknown material {key!r}. Available: {self.keys()}")
        return self._materials[key]

    def exists(self, key):
        return key in self._materials

    def keys(self):
        return sorted(self._materials.keys())


# =========================== sections.py ===========================
@dataclass(frozen=True)
class Section:
    label: str
    A: float
    d: float
    Ix: float
    Zx: float
    Sx: float
    rx: float
    Iy: float
    Zy: float
    Sy: float
    ry: float
    J: float


class SectionLibrary:
    def __init__(self):
        self._sections = {
            "W6X9":   Section("W6X9",   2.68, 5.90, 16.4, 6.23, 5.56, 2.47, 2.20, 1.72, 1.11, 0.905, 0.0405),
            "W6X12":  Section("W6X12",  3.55, 6.03, 22.1, 8.30, 7.31, 2.49, 2.99, 2.32, 1.50, 0.918, 0.0903),
            "W6X15":  Section("W6X15",  4.43, 5.99, 29.1, 10.8, 9.72, 2.56, 9.32, 4.75, 3.11, 1.45,  0.101),
            "W6X20":  Section("W6X20",  5.87, 6.20, 41.4, 14.9, 13.4, 2.66, 13.3, 6.72, 4.41, 1.50,  0.240),
            "W8X10":  Section("W8X10",  2.96, 7.89, 30.8, 8.87, 7.81, 3.22, 2.09, 1.66, 1.06, 0.841, 0.0426),
            "W8X13":  Section("W8X13",  3.84, 7.99, 39.6, 11.4, 9.91, 3.21, 2.73, 2.15, 1.37, 0.843, 0.0871),
            "W8X18":  Section("W8X18",  5.26, 8.14, 61.9, 17.0, 15.2, 3.43, 7.97, 4.66, 3.04, 1.23,  0.172),
            "W8X24":  Section("W8X24",  7.08, 7.93, 82.7, 23.1, 20.9, 3.42, 18.3, 8.57, 5.63, 1.61,  0.346),
            "W8X31":  Section("W8X31",  9.13, 8.00, 110,  30.4, 27.5, 3.47, 37.1, 14.1, 9.27, 2.02,  0.536),
            "W10X12": Section("W10X12", 3.54, 9.87, 53.8, 12.6, 10.9, 3.90, 2.18, 1.74, 1.10, 0.785, 0.0547),
            "W10X19": Section("W10X19", 5.62, 10.2, 96.3, 21.6, 18.8, 4.14, 4.29, 3.35, 2.14, 0.874, 0.233),
            "W10X26": Section("W10X26", 7.61, 10.3, 144,  31.3, 27.9, 4.35, 14.1, 7.50, 4.89, 1.36,  0.402),
            "W12X14": Section("W12X14", 4.16, 11.9, 88.6, 17.4, 14.9, 4.62, 2.36, 1.90, 1.19, 0.753, 0.0704),
            "W12X26": Section("W12X26", 7.65, 12.2, 204,  37.2, 33.4, 5.17, 17.3, 8.17, 5.34, 1.51,  0.300),
            "W12X40": Section("W12X40", 11.7, 11.9, 307,  57.0, 51.5, 5.13, 44.1, 16.8, 11.0, 1.94,  0.906),
            "W14X22": Section("W14X22", 6.49, 13.7, 199,  33.2, 29.0, 5.54, 7.00, 4.39, 2.80, 1.04,  0.208),
            "W14X30": Section("W14X30", 8.85, 13.8, 291,  47.3, 42.0, 5.73, 19.6, 8.99, 5.82, 1.49,  0.380),
        }

    def get(self, label):
        if label not in self._sections:
            raise ValueError(f"Unknown section {label!r}. Available: {self.keys()}")
        return self._sections[label]

    def exists(self, label):
        return label in self._sections

    def keys(self):
        return sorted(self._sections.keys())


# =========================== model.py ===========================
NODES = {
    1: [0, 0, 0], 2: [6, 0, 0], 3: [6, 0, 6], 4: [0, 0, 6],
    5: [0, 6, 0], 6: [6, 6, 0], 7: [6, 6, 6], 8: [0, 6, 6],
}

MEMBERS = {
    'M1': [1, 2], 'M2': [2, 3], 'M3': [3, 4], 'M4': [4, 1],
    'M5': [5, 6], 'M6': [6, 7], 'M7': [7, 8], 'M8': [8, 5],
    'M9': [1, 5], 'M10': [2, 6], 'M11': [3, 7], 'M12': [4, 8],
}

MEMBER_TYPE = {}
for _m in MEMBERS:
    if _m in ('M9', 'M10', 'M11', 'M12'):
        MEMBER_TYPE[_m] = 'column'
    elif _m in ('M5', 'M6', 'M7', 'M8'):
        MEMBER_TYPE[_m] = 'roof_beam'
    else:
        MEMBER_TYPE[_m] = 'tie_beam'

VALID_MEMBER_TYPES = {'column', 'roof_beam', 'tie_beam'}

DEFAULT_ASSIGNMENT = {
    'column':    {'material': 'A36 Gr.36', 'section': 'W8X24'},
    'roof_beam': {'material': 'A36 Gr.36', 'section': 'W10X19'},
    'tie_beam':  {'material': 'A36 Gr.36', 'section': 'W8X13'},
}

SUPPORT_NODES = [n for n, (x, y, z) in NODES.items() if y == 0]

BETA_ANGLE = {m: 0.0 for m in MEMBERS}
for _m in ('M9', 'M10', 'M11', 'M12'):
    BETA_ANGLE[_m] = 45.0

PINNED_MEMBERS = ['M5', 'M6', 'M7', 'M8']

DOF_LABELS = ['UX', 'UY', 'UZ', 'RX', 'RY', 'RZ']

GLOBAL_VERTICAL = np.array([0.0, 1.0, 0.0])
GLOBAL_Z_REF = np.array([0.0, 0.0, 1.0])


def rotate_about_axis(vec, axis, angle_deg):
    theta = np.radians(angle_deg)
    axis = axis / np.linalg.norm(axis)
    return (vec * np.cos(theta)
            + np.cross(axis, vec) * np.sin(theta)
            + axis * np.dot(axis, vec) * (1 - np.cos(theta)))


def compute_local_axes(i_coord, j_coord, beta_deg):
    p_i, p_j = np.array(i_coord, dtype=float), np.array(j_coord, dtype=float)
    local_x = p_j - p_i
    local_x = local_x / np.linalg.norm(local_x)
    ref = GLOBAL_Z_REF if abs(np.dot(local_x, GLOBAL_VERTICAL)) > 0.999 else GLOBAL_VERTICAL
    local_z = np.cross(local_x, ref)
    local_z = local_z / np.linalg.norm(local_z)
    local_y = np.cross(local_z, local_x)
    local_y = local_y / np.linalg.norm(local_y)
    if beta_deg:
        local_y = rotate_about_axis(local_y, local_x, beta_deg)
        local_z = rotate_about_axis(local_z, local_x, beta_deg)
    return local_x, local_y, local_z


class StructuralModel:
    def __init__(self, unit_system="metric", assignment=None):
        self.units = UnitSystem(unit_system)
        self.materials = MaterialLibrary()
        self.sections = SectionLibrary()
        self.assignment = {k: dict(v) for k, v in (assignment or DEFAULT_ASSIGNMENT).items()}

        self.nodes = NODES
        self.members = MEMBERS
        self.member_type = MEMBER_TYPE
        self.support_nodes = SUPPORT_NODES
        self.beta_angle = BETA_ANGLE
        self.pinned_members = PINNED_MEMBERS

        self._validate_assignment()
        self._build_support_conditions()
        self._build_dof_table()
        self._build_member_releases()
        self._build_local_axes()

    def _validate_assignment(self):
        for mtype, props in self.assignment.items():
            if mtype not in VALID_MEMBER_TYPES:
                raise ValueError(f"Unknown member type: {mtype!r}")
            if not self.materials.exists(props['material']):
                raise ValueError(f"{mtype}: unknown material {props['material']!r}")
            if not self.sections.exists(props['section']):
                raise ValueError(f"{mtype}: unknown section {props['section']!r}")

    def set_assignment(self, member_type, material=None, section=None):
        if member_type not in VALID_MEMBER_TYPES:
            raise ValueError(f"Unknown member type: {member_type!r}")
        if material is not None:
            self.assignment[member_type]['material'] = material
        if section is not None:
            self.assignment[member_type]['section'] = section
        self._validate_assignment()

    def member_material(self, member_name):
        mtype = self.member_type[member_name]
        return self.materials.get(self.assignment[mtype]['material'])

    def member_section(self, member_name):
        mtype = self.member_type[member_name]
        return self.sections.get(self.assignment[mtype]['section'])

    def member_solver_properties(self, member_name):
        mat = self.member_material(member_name)
        sec = self.member_section(member_name)
        return {
            'E': to_si(mat.E, Quantity.STRESS),
            'G': to_si(mat.G, Quantity.STRESS),
            'A': to_si(sec.A, Quantity.AREA),
            'Iz': to_si(sec.Ix, Quantity.INERTIA),
            'Iy': to_si(sec.Iy, Quantity.INERTIA),
            'J': to_si(sec.J, Quantity.INERTIA),
            'density': to_si(mat.density, Quantity.UNIT_WEIGHT),
        }

    def _build_support_conditions(self):
        self.support_conditions = {}
        for n in self.nodes:
            if n in self.support_nodes:
                self.support_conditions[n] = {
                    'Type': 'Pinned',
                    'UX': 'Fixed', 'UY': 'Fixed', 'UZ': 'Fixed',
                    'RX': 'Free', 'RY': 'Free', 'RZ': 'Free',
                }
            else:
                self.support_conditions[n] = {
                    'Type': 'Free (no support)',
                    'UX': 'Free', 'UY': 'Free', 'UZ': 'Free',
                    'RX': 'Free', 'RY': 'Free', 'RZ': 'Free',
                }

    def _build_dof_table(self):
        self.node_dof = {}
        for n in sorted(self.nodes.keys()):
            base = (n - 1) * 6
            self.node_dof[n] = {label: base + k + 1 for k, label in enumerate(DOF_LABELS)}

    def _build_member_releases(self):
        self.member_releases = {}
        for m in self.members:
            if m in self.pinned_members:
                self.member_releases[m] = {'Pinned': True, 'i_release': {'RX'}, 'j_release': {'RZ'}}
            else:
                self.member_releases[m] = {'Pinned': False, 'i_release': set(), 'j_release': set()}

    def _build_local_axes(self):
        self.member_local_axes = {}
        for m, (i, j) in self.members.items():
            lx, ly, lz = compute_local_axes(self.nodes[i], self.nodes[j], self.beta_angle[m])
            self.member_local_axes[m] = {'local_x': lx, 'local_y': ly, 'local_z': lz}

    def member_length(self, member_name):
        i, j = self.members[member_name]
        p_i, p_j = np.array(self.nodes[i], dtype=float), np.array(self.nodes[j], dtype=float)
        return float(np.linalg.norm(p_j - p_i))

    def member_length_display(self, member_name):
        return self.units.convert(self.member_length(member_name), Quantity.LENGTH_GEOM)


# =========================== loads.py ===========================
_FORCE_UNIT_TO_N = {
    'N': 1.0,
    'kN': 1e3,
    'kip': to_si(1.0, Quantity.FORCE),
}
_MOMENT_UNIT_TO_NM = {
    'N*m': 1.0,
    'kN*m': 1e3,
    'kip*ft': to_si(1.0, Quantity.MOMENT),
}
_DEFAULT_MOMENT_UNIT = {'N': 'N*m', 'kN': 'kN*m', 'kip': 'kip*ft'}


@dataclass
class PointLoad:
    node: int
    Fx: float = 0.0
    Fy: float = 0.0
    Fz: float = 0.0
    Mx: float = 0.0
    My: float = 0.0
    Mz: float = 0.0

    @classmethod
    def from_units(cls, node, Fx=0.0, Fy=0.0, Fz=0.0, Mx=0.0, My=0.0, Mz=0.0,
                    force_unit='kN', moment_unit=None):
        if force_unit not in _FORCE_UNIT_TO_N:
            raise ValueError(f"Unknown force unit {force_unit!r}.")
        if moment_unit is None:
            moment_unit = _DEFAULT_MOMENT_UNIT[force_unit]
        if moment_unit not in _MOMENT_UNIT_TO_NM:
            raise ValueError(f"Unknown moment unit {moment_unit!r}.")
        ff = _FORCE_UNIT_TO_N[force_unit]
        fm = _MOMENT_UNIT_TO_NM[moment_unit]
        return cls(node, Fx * ff, Fy * ff, Fz * ff, Mx * fm, My * fm, Mz * fm)


@dataclass
class LoadCase:
    name: str
    loads: List[PointLoad] = field(default_factory=list)

    def add(self, load):
        self.loads.append(load)
        return self

    def total_force_Y(self):
        return sum(l.Fy for l in self.loads)


def self_weight_load_case(model, name="Self-Weight"):
    lc = LoadCase(name)
    totals = {n: 0.0 for n in model.nodes}
    for m, (i, j) in model.members.items():
        props = model.member_solver_properties(m)
        length_m = model.member_length(m)
        weight_N = props['density'] * props['A'] * length_m
        totals[i] += weight_N / 2.0
        totals[j] += weight_N / 2.0
    for n, w in totals.items():
        if w:
            lc.add(PointLoad(node=n, Fy=-w))
    return lc


def combine_load_cases(*cases, name="Combined"):
    combined = LoadCase(name)
    for case in cases:
        combined.loads.extend(case.loads)
    return combined


# =========================== solver.py ===========================
DOF_PER_NODE = 6
LOCAL_DOF_INDEX = {label: k for k, label in enumerate(DOF_LABELS)}


def local_stiffness_matrix(E, G, A, Iz, Iy, J, L):
    k = np.zeros((12, 12))
    EA_L = E * A / L
    GJ_L = G * J / L
    EIz = E * Iz
    EIy = E * Iy

    k[0, 0] = k[6, 6] = EA_L
    k[0, 6] = k[6, 0] = -EA_L
    k[3, 3] = k[9, 9] = GJ_L
    k[3, 9] = k[9, 3] = -GJ_L

    k[1, 1] = k[7, 7] = 12 * EIz / L**3
    k[1, 7] = k[7, 1] = -12 * EIz / L**3
    k[1, 5] = k[5, 1] = 6 * EIz / L**2
    k[1, 11] = k[11, 1] = 6 * EIz / L**2
    k[5, 7] = k[7, 5] = -6 * EIz / L**2
    k[7, 11] = k[11, 7] = -6 * EIz / L**2
    k[5, 5] = k[11, 11] = 4 * EIz / L
    k[5, 11] = k[11, 5] = 2 * EIz / L

    k[2, 2] = k[8, 8] = 12 * EIy / L**3
    k[2, 8] = k[8, 2] = -12 * EIy / L**3
    k[2, 4] = k[4, 2] = -6 * EIy / L**2
    k[2, 10] = k[10, 2] = -6 * EIy / L**2
    k[4, 8] = k[8, 4] = 6 * EIy / L**2
    k[8, 10] = k[10, 8] = 6 * EIy / L**2
    k[4, 4] = k[10, 10] = 4 * EIy / L
    k[4, 10] = k[10, 4] = 2 * EIy / L
    return k


def transformation_matrix(local_x, local_y, local_z):
    R = np.vstack([local_x, local_y, local_z])
    T = np.zeros((12, 12))
    for b in range(4):
        T[b*3:(b+1)*3, b*3:(b+1)*3] = R
    return T


def condense_released_dof(k_local, released_indices):
    if not released_indices:
        return k_local
    all_idx = list(range(12))
    free_idx = [i for i in all_idx if i not in released_indices]
    Kff = k_local[np.ix_(free_idx, free_idx)]
    Kfr = k_local[np.ix_(free_idx, released_indices)]
    Krf = k_local[np.ix_(released_indices, free_idx)]
    Krr = k_local[np.ix_(released_indices, released_indices)]
    Kff_c = Kff - Kfr @ np.linalg.inv(Krr) @ Krf
    k_new = np.zeros((12, 12))
    for a, ia in enumerate(free_idx):
        for b, ib in enumerate(free_idx):
            k_new[ia, ib] = Kff_c[a, b]
    return k_new


class SolveResult:
    def __init__(self, model, displacements, reactions, member_end_forces, load_case_name):
        self.model = model
        self.displacements = displacements
        self.reactions = reactions
        self.member_end_forces = member_end_forces
        self.load_case_name = load_case_name

    def reaction_sum_Y(self):
        return sum(r['UY'] for r in self.reactions.values())


def solve(model, load_case):
    node_ids = sorted(model.nodes.keys())
    node_index = {n: idx for idx, n in enumerate(node_ids)}
    n_dof = len(node_ids) * DOF_PER_NODE
    K = np.zeros((n_dof, n_dof))

    element_data = {}
    for m, (i, j) in model.members.items():
        L = model.member_length(m)
        props = model.member_solver_properties(m)
        k_local = local_stiffness_matrix(props['E'], props['G'], props['A'],
                                          props['Iz'], props['Iy'], props['J'], L)
        rel = model.member_releases[m]
        released = ([LOCAL_DOF_INDEX[d] for d in rel['i_release']] +
                    [6 + LOCAL_DOF_INDEX[d] for d in rel['j_release']])
        k_local_c = condense_released_dof(k_local, released)
        axes = model.member_local_axes[m]
        T = transformation_matrix(axes['local_x'], axes['local_y'], axes['local_z'])
        k_global = T.T @ k_local_c @ T

        dof_map = []
        for node in (i, j):
            base = node_index[node] * DOF_PER_NODE
            dof_map.extend(range(base, base + DOF_PER_NODE))
        for a in range(12):
            for b in range(12):
                K[dof_map[a], dof_map[b]] += k_global[a, b]
        element_data[m] = dict(k_local=k_local_c, T=T, dof_map=dof_map)

    F = np.zeros(n_dof)
    for load in load_case.loads:
        base = node_index[load.node] * DOF_PER_NODE
        F[base:base + 6] += [load.Fx, load.Fy, load.Fz, load.Mx, load.My, load.Mz]

    restrained = set()
    for n in model.support_nodes:
        base = node_index[n] * DOF_PER_NODE
        restrained.update({base + 0, base + 1, base + 2})
    free = [d for d in range(n_dof) if d not in restrained]

    u = np.zeros(n_dof)
    K_ff = K[np.ix_(free, free)]
    F_f = F[free]
    u[free] = np.linalg.solve(K_ff, F_f)
    reaction_full = K @ u - F

    displacements, reactions = {}, {}
    for n, idx in node_index.items():
        base = idx * DOF_PER_NODE
        displacements[n] = {lab: u[base + k] for k, lab in enumerate(DOF_LABELS)}
        if n in model.support_nodes:
            reactions[n] = {lab: reaction_full[base + k] for k, lab in enumerate(DOF_LABELS)}

    member_end_forces = {}
    for m, data in element_data.items():
        u_elem_global = u[data['dof_map']]
        u_elem_local = data['T'] @ u_elem_global
        f_elem_local = data['k_local'] @ u_elem_local
        member_end_forces[m] = {
            'i': dict(zip(DOF_LABELS, f_elem_local[0:6])),
            'j': dict(zip(DOF_LABELS, f_elem_local[6:12])),
        }
    return SolveResult(model, displacements, reactions, member_end_forces, load_case.name)


# =========================== Web API ===========================
_MATS = MaterialLibrary()
_SECS = SectionLibrary()


def api_options():
    return json.dumps({
        'materials': _MATS.keys(),
        'sections': _SECS.keys(),
        'member_types': ['column', 'roof_beam', 'tie_beam'],
        'nodes': sorted(NODES.keys()),
        'defaults': DEFAULT_ASSIGNMENT,
    })


def _fmt_table(headers, rows):
    return {'headers': headers, 'rows': rows}


def api_solve(config_json):
    # Take a JSON config from JS, run the solver, return JSON results.
    cfg = json.loads(config_json)
    unit_system = cfg.get('unit', 'metric')
    assignment = cfg['assignment']
    force_unit = cfg.get('force_unit', 'kN')
    self_weight = cfg.get('self_weight', True)
    raw_loads = cfg.get('loads', [])

    model = StructuralModel(unit_system=unit_system, assignment=assignment)
    u = model.units

    cases = []
    if self_weight:
        cases.append(self_weight_load_case(model))

    custom = LoadCase("User Loads")
    valid_node_ids = set(model.nodes.keys())          # {1, 2, 3, 4, 5, 6, 7, 8}
    for row in raw_loads:
        if not row.get('node'):
            continue
        try:
            node_id = int(row['node'])
        except (TypeError, ValueError):
            raise ValueError(f"Load node id must be an integer, got {row['node']!r}.")
        if node_id not in valid_node_ids:
            raise ValueError(
                f"Load references node {node_id}, but this model only has nodes "
                f"{sorted(valid_node_ids)}."
            )
        custom.add(PointLoad.from_units(
            node=node_id,
            Fx=float(row.get('Fx', 0) or 0),
            Fy=float(row.get('Fy', 0) or 0),
            Fz=float(row.get('Fz', 0) or 0),
            Mx=float(row.get('Mx', 0) or 0),
            My=float(row.get('My', 0) or 0),
            Mz=float(row.get('Mz', 0) or 0),
            force_unit=force_unit,
        ))
    if custom.loads:
        cases.append(custom)
    if not cases:
        cases = [LoadCase("Empty")]
    combined = combine_load_cases(*cases, name="+".join(c.name for c in cases))

    result = solve(model, combined)

    fu = u.label(Quantity.FORCE)
    mu = u.label(Quantity.MOMENT)
    lu = u.label(Quantity.LENGTH_GEOM)

    # --- geometry for 3D view ---
    nodes_out = {str(n): list(map(float, coords)) for n, coords in model.nodes.items()}
    members_out = []
    for name, (i, j) in model.members.items():
        members_out.append({
            'name': name,
            'i': i, 'j': j,
            'type': model.member_type[name],
            'material': model.assignment[model.member_type[name]]['material'],
            'section': model.assignment[model.member_type[name]]['section'],
            'length': model.member_length_display(name),
            'pinned': model.member_releases[name]['Pinned'],
            'axes': {
                'x': model.member_local_axes[name]['local_x'].tolist(),
                'y': model.member_local_axes[name]['local_y'].tolist(),
                'z': model.member_local_axes[name]['local_z'].tolist(),
            },
        })

    # --- loads for diagram (combined node loads, SI -> display) ---
    load_arrows = {}
    for l in combined.loads:
        v = load_arrows.setdefault(l.node, [0.0, 0.0, 0.0])
        v[0] += l.Fx; v[1] += l.Fy; v[2] += l.Fz

    # --- tables ---
    disp_rows = []
    for n in sorted(result.displacements):
        d = result.displacements[n]
        disp_rows.append([
            n,
            u.convert(from_si(d['UX'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
            u.convert(from_si(d['UY'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
            u.convert(from_si(d['UZ'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
            d['RX'], d['RY'], d['RZ'],
        ])
    disp_tbl = _fmt_table(
        ['Node', f'UX ({lu})', f'UY ({lu})', f'UZ ({lu})', 'RX (rad)', 'RY (rad)', 'RZ (rad)'],
        disp_rows)

    react_rows = []
    for n in sorted(result.reactions):
        r = result.reactions[n]
        react_rows.append([
            n,
            u.convert(from_si(r['UX'], Quantity.FORCE), Quantity.FORCE),
            u.convert(from_si(r['UY'], Quantity.FORCE), Quantity.FORCE),
            u.convert(from_si(r['UZ'], Quantity.FORCE), Quantity.FORCE),
            u.convert(from_si(r['RX'], Quantity.MOMENT), Quantity.MOMENT),
            u.convert(from_si(r['RY'], Quantity.MOMENT), Quantity.MOMENT),
            u.convert(from_si(r['RZ'], Quantity.MOMENT), Quantity.MOMENT),
        ])
    react_tbl = _fmt_table(
        ['Node', f'Rx ({fu})', f'Ry ({fu})', f'Rz ({fu})',
         f'Mx ({mu})', f'My ({mu})', f'Mz ({mu})'],
        react_rows)

    force_rows = []
    for m in model.members:
        for end in ('i', 'j'):
            f = result.member_end_forces[m][end]
            force_rows.append([
                m, end,
                u.convert(from_si(f['UX'], Quantity.FORCE), Quantity.FORCE),
                u.convert(from_si(f['UY'], Quantity.FORCE), Quantity.FORCE),
                u.convert(from_si(f['UZ'], Quantity.FORCE), Quantity.FORCE),
                u.convert(from_si(f['RX'], Quantity.MOMENT), Quantity.MOMENT),
                u.convert(from_si(f['RY'], Quantity.MOMENT), Quantity.MOMENT),
                u.convert(from_si(f['RZ'], Quantity.MOMENT), Quantity.MOMENT),
            ])
    forces_tbl = _fmt_table(
        ['Member', 'End', f'Axial ({fu})', f'Shear-y ({fu})', f'Shear-z ({fu})',
         f'Torsion ({mu})', f'Moment-y ({mu})', f'Moment-z ({mu})'],
        force_rows)

    members_tbl = _fmt_table(
        ['Member', 'i', 'j', 'Type', 'Material', 'Section', f'Length ({lu})'],
        [[m['name'], m['i'], m['j'], m['type'], m['material'], m['section'], m['length']]
         for m in members_out])

    # --- equilibrium / KPI ---
    total_fy_applied = u.convert(from_si(combined.total_force_Y(), Quantity.FORCE), Quantity.FORCE)
    total_fy_reaction = u.convert(from_si(result.reaction_sum_Y(), Quantity.FORCE), Quantity.FORCE)

    worst_node, worst_mag = None, -1.0
    worst_components = None
    for n, d in result.displacements.items():
        mag = (d['UX']**2 + d['UY']**2 + d['UZ']**2) ** 0.5
        if mag > worst_mag:
            worst_mag, worst_node, worst_components = mag, n, d
    worst_disp_display = {
        'node': worst_node,
        'UX': u.convert(from_si(worst_components['UX'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
        'UY': u.convert(from_si(worst_components['UY'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
        'UZ': u.convert(from_si(worst_components['UZ'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
        'mag': u.convert(from_si(worst_mag, Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
    }

    return json.dumps({
        'unit_system': unit_system,
        'labels': {'force': fu, 'moment': mu, 'length': lu},
        'nodes': nodes_out,
        'members': members_out,
        'support_nodes': list(model.support_nodes),
        'pinned_members': list(model.pinned_members),
        'load_arrows': {str(k): v for k, v in load_arrows.items()},
        'tables': {
            'displacements': disp_tbl,
            'reactions': react_tbl,
            'member_forces': forces_tbl,
            'members': members_tbl,
        },
        'kpi': {
            'load_case': combined.name,
            'n_loads': len(combined.loads),
            'total_fy_applied': total_fy_applied,
            'total_fy_reaction': total_fy_reaction,
            'residual': total_fy_applied + total_fy_reaction,
            'worst_disp': worst_disp_display,
        },
    })
</script>

<!-- ============================================================================
     JavaScript glue code.
     ============================================================================ -->
<script>
(function() {
  const statusEl   = document.getElementById('load-status');
  const statusText = document.getElementById('status-text');
  const runBtn     = document.getElementById('run-btn');
  const dlBtn      = document.getElementById('download-btn');
  const unitSel    = document.getElementById('unit-system');
  const swChk      = document.getElementById('self-weight');
  const memberDiv  = document.getElementById('member-assignments');
  const loadRows   = document.getElementById('load-rows');
  const addLoadBtn = document.getElementById('add-load-btn');
  const kpiDiv     = document.getElementById('kpis');

  let pyodide = null;
  let options = null;
  let lastResult = null;
  let loadRowCounter = 0;

  const COLOR = {
    column:    '#f59e0b',
    roof_beam: '#22c55e',
    tie_beam:  '#3b82f6',
  };
  const TYPE_LABEL = {
    column: 'Column', roof_beam: 'Roof Beam', tie_beam: 'Tie Beam'
  };

  function setStatus(msg, cls='') {
    statusText.textContent = msg;
    statusEl.className = 'status' + (cls ? ' ' + cls : '');
  }

  async function boot() {
    try {
      setStatus('Loading Python runtime…');
      pyodide = await loadPyodide();
      setStatus('Loading NumPy…');
      await pyodide.loadPackage(['numpy']);
      setStatus('Compiling solver…');
      const src = document.getElementById('python-source').textContent;
      pyodide.runPython(src);

      options = JSON.parse(pyodide.runPython('api_options()'));
      buildMemberAssignmentUI();
      addLoadRow({ node: options.nodes.includes(6) ? 6 : options.nodes[0], Fx: 10 });
      setStatus('Ready. Click Solve to run.', 'ok');
      runBtn.disabled = false;
      runBtn.click();
    } catch (e) {
      console.error(e);
      setStatus('Failed to load: ' + e.message, 'err');
    }
  }

  function buildMemberAssignmentUI() {
    memberDiv.innerHTML = '';
    for (const mtype of options.member_types) {
      const block = document.createElement('div');
      block.className = 'member-block';
      block.innerHTML = `
        <h4><span class="swatch" style="background:${COLOR[mtype]}"></span>${TYPE_LABEL[mtype]}</h4>
        <div class="field"><label>Material</label>
          <select data-mtype="${mtype}" data-field="material"></select>
        </div>
        <div class="field" style="margin-bottom:0"><label>Section</label>
          <select data-mtype="${mtype}" data-field="section"></select>
        </div>`;
      memberDiv.appendChild(block);
      const matSel = block.querySelector('[data-field="material"]');
      const secSel = block.querySelector('[data-field="section"]');
      for (const m of options.materials) {
        const o = document.createElement('option');
        o.value = m; o.textContent = m;
        if (m === options.defaults[mtype].material) o.selected = true;
        matSel.appendChild(o);
      }
      for (const s of options.sections) {
        const o = document.createElement('option');
        o.value = s; o.textContent = s;
        if (s === options.defaults[mtype].section) o.selected = true;
        secSel.appendChild(o);
      }
    }
  }

  function addLoadRow(vals = {}) {
    loadRowCounter++;
    const row = document.createElement('div');
    row.className = 'load-row';
    row.dataset.id = loadRowCounter;
    const fields = ['node', 'Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz'];

    const selectedNode = Number(vals.node);
    const nodeOpts = options.nodes.map(n =>
      `<option value="${n}"${selectedNode === n ? ' selected' : ''}>N${n}</option>`
    ).join('');

    row.innerHTML = fields.map(f => {
      if (f === 'node') {
        return `<select data-field="node" title="Load node">${nodeOpts}</select>`;
      }
      const val = vals[f] !== undefined ? vals[f] : 0;
      return `<input data-field="${f}" type="text" value="${val}" inputmode="decimal" />`;
    }).join('') + `<button class="icon-btn danger" title="Remove">×</button>`;
    row.querySelector('button').addEventListener('click', () => row.remove());
    loadRows.appendChild(row);
  }

  addLoadBtn.addEventListener('click', () => addLoadRow());

  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      document.getElementById('panel-' + t.dataset.tab).classList.add('active');
      if (t.dataset.tab === 'view') setTimeout(() => Plotly.Plots.resize('plot'), 30);
    });
  });

  function collectConfig() {
    const unit = unitSel.value;
    const force_unit = unit === 'imperial' ? 'kip' : 'kN';
    const assignment = {};
    for (const mtype of options.member_types) {
      const mat = memberDiv.querySelector(`[data-mtype="${mtype}"][data-field="material"]`).value;
      const sec = memberDiv.querySelector(`[data-mtype="${mtype}"][data-field="section"]`).value;
      assignment[mtype] = { material: mat, section: sec };
    }
    const loads = [];
    for (const row of loadRows.querySelectorAll('.load-row')) {
      const nodeEl = row.querySelector('[data-field="node"]');
      if (!nodeEl) continue;
      const obj = { node: parseInt(nodeEl.value, 10) };
      for (const inp of row.querySelectorAll('input')) {
        const f = inp.dataset.field;
        const v = inp.value.trim();
        const num = v === '' ? 0 : parseFloat(v);
        obj[f] = Number.isFinite(num) ? num : 0;
      }
      if (Number.isInteger(obj.node)) loads.push(obj);
    }
    return {
      unit, force_unit,
      assignment,
      self_weight: swChk.checked,
      loads,
    };
  }

  function fmt(v, digits = 4) {
    if (v === null || v === undefined) return '—';
    if (typeof v !== 'number') return String(v);
    if (Math.abs(v) < 1e-9) return '0';
    const abs = Math.abs(v);
    if (abs >= 1e5 || abs < 1e-3) return v.toExponential(3);
    return v.toFixed(digits);
  }

  function renderTable(container, tbl) {
    const html = ['<table><thead><tr>'];
    for (const h of tbl.headers) html.push(`<th>${h}</th>`);
    html.push('</tr></thead><tbody>');
    for (const row of tbl.rows) {
      html.push('<tr>');
      for (const c of row) html.push(`<td>${typeof c === 'number' ? fmt(c) : c}</td>`);
      html.push('</tr>');
    }
    html.push('</tbody></table>');
    container.innerHTML = html.join('');
  }

  function renderKPIs(kpi, labels) {
    const k = kpi;
    const wd = k.worst_disp;
    const residual = k.residual;
    const okCls = Math.abs(residual) < 1e-3 ? 'ok' : '';
    kpiDiv.innerHTML = `
      <div class="kpi"><div class="label">Load case</div>
        <div class="value" style="font-size:14px;font-weight:500">${k.load_case}</div>
        <div class="unit">${k.n_loads} applied load(s)</div></div>
      <div class="kpi"><div class="label">Total applied Fy</div>
        <div class="value">${fmt(k.total_fy_applied)} <span class="unit">${labels.force}</span></div></div>
      <div class="kpi"><div class="label">Sum of reactions Fy</div>
        <div class="value">${fmt(k.total_fy_reaction)} <span class="unit">${labels.force}</span></div></div>
      <div class="kpi ${okCls}"><div class="label">Equilibrium residual</div>
        <div class="value">${fmt(residual)} <span class="unit">${labels.force}</span></div>
        <div class="unit">${Math.abs(residual) < 1e-3 ? '✓ balanced' : '⚠ check'}</div></div>
      <div class="kpi"><div class="label">Max |displacement|</div>
        <div class="value">${fmt(wd.mag)} <span class="unit">${labels.length}</span></div>
        <div class="unit">at node N${wd.node}</div></div>`;
  }

  function render3D(res) {
    const nodes = res.nodes;
    const nodeIds = Object.keys(nodes).map(Number).sort((a,b)=>a-b);
    const traces = [];

    const typeGroups = { column: [], roof_beam: [], tie_beam: [] };
    for (const m of res.members) {
      const [x1, y1, z1] = nodes[m.i];
      const [x2, y2, z2] = nodes[m.j];
      typeGroups[m.type].push({ x: [x1, x2], y: [y1, y2], z: [z1, z2] });
    }
    for (const type of ['column', 'roof_beam', 'tie_beam']) {
      const group = typeGroups[type];
      if (!group.length) continue;
      const xs = [], ys = [], zs = [];
      for (const seg of group) {
        xs.push(seg.x[0], seg.x[1], null);
        ys.push(seg.y[0], seg.y[1], null);
        zs.push(seg.z[0], seg.z[1], null);
      }
      traces.push({
        type: 'scatter3d', mode: 'lines',
        name: TYPE_LABEL[type],
        x: xs, y: ys, z: zs,
        line: { color: COLOR[type], width: 8 },
        hoverinfo: 'name',
      });
    }

    traces.push({
      type: 'scatter3d', mode: 'markers+text',
      name: 'Nodes',
      x: nodeIds.map(n => nodes[n][0]),
      y: nodeIds.map(n => nodes[n][1]),
      z: nodeIds.map(n => nodes[n][2]),
      marker: { color: '#ef4444', size: 6, symbol: 'circle',
                line: { color: '#fff', width: 1 } },
      text: nodeIds.map(n => `N${n}`),
      textposition: 'top center',
      textfont: { color: '#fca5a5', size: 11 },
      hoverinfo: 'text',
    });

    const supX = [], supY = [], supZ = [];
    for (const n of res.support_nodes) {
      const [x, y, z] = nodes[n];
      supX.push(x); supY.push(y); supZ.push(z);
    }
    traces.push({
      type: 'scatter3d', mode: 'markers',
      name: 'Pinned Support',
      x: supX, y: supY, z: supZ,
      marker: { color: '#f59e0b', size: 10, symbol: 'diamond',
                line: { color: '#000', width: 1 } },
      hoverinfo: 'name',
    });

    const pinX = [], pinY = [], pinZ = [];
    for (const m of res.members) {
      if (!m.pinned) continue;
      const [xi, yi, zi] = nodes[m.i];
      const [xj, yj, zj] = nodes[m.j];
      const dx = xj - xi, dy = yj - yi, dz = zj - zi;
      const L = Math.hypot(dx, dy, dz);
      const off = 0.5;
      pinX.push(xi + dx/L * off, xj - dx/L * off);
      pinY.push(yi + dy/L * off, yj - dy/L * off);
      pinZ.push(zi + dz/L * off, zj - dz/L * off);
    }
    if (pinX.length) {
      traces.push({
        type: 'scatter3d', mode: 'markers',
        name: 'Pinned (moment release)',
        x: pinX, y: pinY, z: pinZ,
        marker: { color: '#ec4899', size: 6, symbol: 'circle-open',
                  line: { color: '#ec4899', width: 2 } },
        hoverinfo: 'name',
      });
    }

    const axX = { x: [], y: [], z: [] }, axY = { x: [], y: [], z: [] }, axZ = { x: [], y: [], z: [] };
    const axisLen = 1.0;
    for (const m of res.members) {
      const [xi, yi, zi] = nodes[m.i];
      const [xj, yj, zj] = nodes[m.j];
      const cx = (xi + xj)/2, cy = (yi + yj)/2, cz = (zi + zj)/2;
      for (const [arr, key] of [[axX, 'x'], [axY, 'y'], [axZ, 'z']]) {
        const v = m.axes[key];
        arr.x.push(cx, cx + v[0]*axisLen, null);
        arr.y.push(cy, cy + v[1]*axisLen, null);
        arr.z.push(cz, cz + v[2]*axisLen, null);
      }
    }
    traces.push({ type: 'scatter3d', mode: 'lines', name: 'Local X',
                  x: axX.x, y: axX.y, z: axX.z,
                  line: { color: '#ef4444', width: 3 }, opacity: 0.7, hoverinfo: 'name' });
    traces.push({ type: 'scatter3d', mode: 'lines', name: 'Local Y',
                  x: axY.x, y: axY.y, z: axY.z,
                  line: { color: '#22c55e', width: 3 }, opacity: 0.7, hoverinfo: 'name' });
    traces.push({ type: 'scatter3d', mode: 'lines', name: 'Local Z',
                  x: axZ.x, y: axZ.y, z: axZ.z,
                  line: { color: '#a855f7', width: 3 }, opacity: 0.7, hoverinfo: 'name' });

    const la = res.load_arrows;
    const laIds = Object.keys(la).map(Number);
    if (laIds.length) {
      let maxMag = 0;
      for (const n of laIds) {
        const v = la[n];
        maxMag = Math.max(maxMag, Math.hypot(v[0], v[1], v[2]));
      }
      if (maxMag > 0) {
        const arrowLen = 1.6;
        const lx = [], ly = [], lz = [];
        for (const n of laIds) {
          const v = la[n];
          const mag = Math.hypot(v[0], v[1], v[2]);
          if (mag < 1e-9) continue;
          const s = arrowLen / maxMag;
          const [x, y, z] = nodes[n];
          const dx = v[0] * s, dy = v[1] * s, dz = v[2] * s;
          lx.push(x - dx, x, null);
          ly.push(y - dy, y, null);
          lz.push(z - dz, z, null);
        }
        traces.push({
          type: 'scatter3d', mode: 'lines',
          name: 'Applied Load',
          x: lx, y: ly, z: lz,
          line: { color: '#e11d48', width: 5 },
          hoverinfo: 'name',
        });
      }
    }

    const origin = [-1.5, -1.5, -0.5];
    const gLen = 2.0;
    for (const [vec, label, color] of [
      [[gLen,0,0], 'X (global)', '#f87171'],
      [[0,gLen,0], 'Y (global) — vertical', '#4ade80'],
      [[0,0,gLen], 'Z (global)', '#60a5fa'],
    ]) {
      traces.push({
        type: 'scatter3d', mode: 'lines+text',
        name: label,
        x: [origin[0], origin[0] + vec[0]],
        y: [origin[1], origin[1] + vec[1]],
        z: [origin[2], origin[2] + vec[2]],
        line: { color, width: 4 },
        text: ['', label],
        textposition: 'top center',
        textfont: { color, size: 11 },
        hoverinfo: 'name',
      });
    }

    const layout = {
      margin: { l: 0, r: 0, t: 30, b: 0 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#e2e8f0', size: 11 },
      scene: {
        xaxis: { title: `X (${res.labels.length})`, gridcolor: '#2a3654', zerolinecolor: '#3d4d70', color: '#94a3b8' },
        yaxis: { title: `Y (${res.labels.length}) — Vertical`, gridcolor: '#2a3654', zerolinecolor: '#3d4d70', color: '#94a3b8' },
        zaxis: { title: `Z (${res.labels.length})`, gridcolor: '#2a3654', zerolinecolor: '#3d4d70', color: '#94a3b8' },
        aspectmode: 'cube',
        bgcolor: 'rgba(0,0,0,0)',
        camera: { eye: { x: 1.6, y: 1.3, z: 1.1 } },
      },
      legend: {
        x: 0, y: 1,
        bgcolor: 'rgba(18,27,46,0.85)',
        bordercolor: '#2a3654', borderwidth: 1,
        font: { size: 10, color: '#e2e8f0' },
      },
      showlegend: true,
    };
    Plotly.react('plot', traces, layout, { responsive: true, displaylogo: false });
  }

  async function runSolve() {
    if (!pyodide) return;
    runBtn.disabled = true;
    setStatus('Solving…');
    try {
      const cfg = collectConfig();
      const t0 = performance.now();
      const raw = pyodide.runPython(`api_solve(${JSON.stringify(JSON.stringify(cfg))})`);
      const dt = (performance.now() - t0).toFixed(1);
      const res = JSON.parse(raw);
      lastResult = res;

      renderKPIs(res.kpi, res.labels);
      renderTable(document.getElementById('tbl-disp'),   res.tables.displacements);
      renderTable(document.getElementById('tbl-react'),  res.tables.reactions);
      renderTable(document.getElementById('tbl-forces'), res.tables.member_forces);
      renderTable(document.getElementById('tbl-members'),res.tables.members);
      render3D(res);

      setStatus(`Solved in ${dt} ms. Equilibrium residual: ${res.kpi.residual.toExponential(2)}`, 'ok');
      dlBtn.disabled = false;
    } catch (e) {
      const msg = (e && e.message ? e.message : String(e));
      const lastLine = msg.split('\n').filter(Boolean).pop();
      setStatus('Solver error: ' + lastLine, 'err');
      console.error(e);
    } finally {
      runBtn.disabled = false;
    }
  }

  runBtn.addEventListener('click', runSolve);

  dlBtn.addEventListener('click', () => {
    if (!lastResult) return;
    const tables = lastResult.tables;
    const sections = [
      ['Displacements', tables.displacements],
      ['Reactions',     tables.reactions],
      ['Member End Forces', tables.member_forces],
      ['Members',       tables.members],
    ];
    const lines = [];
    for (const [name, tbl] of sections) {
      lines.push(`### ${name}`);
      lines.push(tbl.headers.join(','));
      for (const row of tbl.rows) {
        lines.push(row.map(c => typeof c === 'number' ? c.toPrecision(10) : `"${c}"`).join(','));
      }
      lines.push('');
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'revit3_solver_results.csv';
    a.click();
  });

  boot();
})();
</script>
</body>
</html>
'''


# =============================================================================
# HTTP handler
# =============================================================================
class SolverRequestHandler(http.server.BaseHTTPRequestHandler):
    """Serves the embedded HTML on '/', a small health check on '/health',
    and 404s everything else."""

    server_version = "Revit3Solver/1.0"

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path in ('/', '/index.html', '/revit3_solver.html'):
            body = HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        elif path == '/health':
            body = b'ok'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        else:
            body = b'Not found'
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("[revit3] %s - %s\n" % (self.address_string(), fmt % args))


# =============================================================================
# Entry point
# =============================================================================
def find_free_port(host, start_port, max_tries=20):
    """Return `start_port` if it's free, else scan upward."""
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(
        f"No free port found in range {start_port}-{start_port + max_tries - 1}."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Serve the Revit 3 Solver web app on a local HTTP server."
    )
    parser.add_argument('--host', default='127.0.0.1',
                        help="Bind address (default: 127.0.0.1, localhost only).")
    parser.add_argument('--port', type=int, default=8000,
                        help="Starting port (default: 8000). Scans upward if taken.")
    parser.add_argument('--no-browser', action='store_true',
                        help="Do not auto-open the browser.")
    parser.add_argument('--no-auto-port', action='store_true',
                        help="Fail instead of scanning upward if the port is taken.")
    args = parser.parse_args()

    if args.no_auto_port:
        port = args.port
    else:
        port = find_free_port(args.host, args.port)

    url = f"http://{args.host}:{port}/"

    with http.server.ThreadingHTTPServer((args.host, port), SolverRequestHandler) as httpd:
        print("=" * 70)
        print("  Revit 3 Solver — Web Edition")
        print("=" * 70)
        print(f"  Serving at:   {url}")
        print(f"  Health check: {url}health")
        print(f"  Stop with:    Ctrl+C")
        print("=" * 70)
        if args.host == '0.0.0.0':
            print("  Note: bound to all interfaces — accessible from other")
            print("  machines on your network at http://<your-lan-ip>:%d/" % port)
            print("=" * 70)

        if not args.no_browser:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[revit3] Shutting down…")
            httpd.shutdown()


if __name__ == '__main__':
    main()