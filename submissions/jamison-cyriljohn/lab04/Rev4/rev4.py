#!/usr/bin/env python3
"""
Rev4.py -- Revit 4 Solver.

Serves a single-file web app (Pyodide + NumPy + Plotly) at http://localhost:8000/
using only the Python standard library.  The solver is a full 3D space-frame
stiffness solver with Rev 4 load cases, member loads, thermal loads, a roof
diaphragm, NSCP LRFD/ASD combinations, and a user-defined CUSTOM load case.

Usage:
    python Rev4.py                   # port 8000, opens browser
    python Rev4.py --port 9000
    python Rev4.py --no-browser
    python Rev4.py --host 0.0.0.0
    python Rev4.py --verify          # headless validation, then exit
"""

import argparse
import http.server
import socket
import sys
import threading
import webbrowser


HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Revit 4 Solver</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js"></script>
<style>
  :root{--bg:#0b1220;--panel:#121b2e;--panel-2:#1a2540;--border:#2a3654;
        --text:#e2e8f0;--muted:#94a3b8;--accent:#38bdf8;--accent-2:#22c55e;
        --warn:#f59e0b;--danger:#ef4444;}
  *{box-sizing:border-box;} html,body{height:100%;}
  body{margin:0;background:var(--bg);color:var(--text);
       font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:14px;}
  header{display:flex;align-items:center;gap:12px;padding:12px 20px;
         background:var(--panel);border-bottom:1px solid var(--border);}
  header h1{margin:0;font-size:17px;letter-spacing:.3px;}
  header .subtitle{color:var(--muted);font-size:11px;}
  header .spacer{flex:1;}
  button{background:var(--panel-2);color:var(--text);border:1px solid var(--border);
         border-radius:6px;padding:8px 14px;cursor:pointer;font-size:13px;font-weight:500;}
  button:hover:not(:disabled){background:#24334f;border-color:#3d4d70;}
  button:disabled{opacity:.5;cursor:not-allowed;}
  button.primary{background:var(--accent);border-color:var(--accent);color:#06202f;font-weight:600;}
  button.primary:hover:not(:disabled){background:#5cc8fb;}
  input,select{background:var(--panel-2);color:var(--text);border:1px solid var(--border);
               border-radius:6px;padding:7px 9px;font-size:13px;width:100%;font-family:inherit;}
  input:focus,select:focus{outline:none;border-color:var(--accent);}
  .layout{display:grid;grid-template-columns:380px 1fr;height:calc(100vh - 58px);}
  .sidebar{overflow-y:auto;background:var(--panel);border-right:1px solid var(--border);padding:16px;}
  .main{overflow-y:auto;padding:16px 20px 40px;}
  .section-title{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;
                 color:var(--muted);margin:18px 0 8px;}
  .section-title:first-child{margin-top:0;}
  .field{margin-bottom:10px;}
  .field label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px;}
  .member-block{background:var(--panel-2);border:1px solid var(--border);
                border-radius:8px;padding:10px;margin-bottom:10px;}
  .member-block h4{margin:0 0 8px;font-size:13px;display:flex;align-items:center;gap:6px;}
  .swatch{width:10px;height:10px;border-radius:50%;display:inline-block;}
  .tabs{display:flex;gap:4px;border-bottom:1px solid var(--border);margin-bottom:12px;flex-wrap:wrap;}
  .tab{padding:8px 14px;border:none;background:transparent;color:var(--muted);
       border-bottom:2px solid transparent;border-radius:0;cursor:pointer;font-size:13px;font-weight:500;}
  .tab:hover:not(.active){color:var(--text);}
  .tab.active{color:var(--accent);border-bottom-color:var(--accent);}
  .tab-panel{display:none;} .tab-panel.active{display:block;}
  #plot{width:100%;height:620px;background:#0a101c;border-radius:8px;border:1px solid var(--border);}
  .status{padding:8px 12px;border-radius:6px;font-size:12px;margin-bottom:12px;
          background:var(--panel-2);border:1px solid var(--border);color:var(--muted);
          display:flex;align-items:center;gap:8px;}
  .status.ok{color:var(--accent-2);border-color:#1e3d2a;background:#0f2418;}
  .status.err{color:var(--danger);border-color:#4a1f24;background:#2a1114;}
  .status .dot{width:8px;height:8px;border-radius:50%;background:currentColor;
               animation:pulse 1.2s ease-in-out infinite;}
  @keyframes pulse{0%,100%{opacity:1;}50%{opacity:.3;}}
  table{width:100%;border-collapse:collapse;font-size:12px;
        font-family:ui-monospace,"SF Mono",Menlo,monospace;}
  th,td{padding:6px 10px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap;}
  th{color:var(--muted);font-weight:500;background:var(--panel-2);position:sticky;top:0;}
  th:first-child,td:first-child{text-align:left;}
  tr:hover td{background:rgba(56,189,248,.05);}
  .kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:16px;}
  .kpi{background:var(--panel-2);border:1px solid var(--border);border-radius:8px;padding:12px 14px;}
  .kpi .label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;}
  .kpi .value{font-size:18px;font-weight:600;margin-top:4px;font-family:ui-monospace,monospace;}
  .kpi .unit{font-size:12px;color:var(--muted);font-weight:400;}
  .card{background:var(--panel-2);border:1px solid var(--border);
        border-radius:8px;padding:12px;margin-bottom:14px;}
  .card h3{margin:0 0 8px;font-size:13px;color:var(--muted);
           text-transform:uppercase;letter-spacing:.8px;font-weight:500;}
  .help{color:var(--muted);font-size:12px;line-height:1.55;}
  code{background:var(--panel-2);padding:1px 5px;border-radius:3px;font-size:12px;color:var(--accent);}
  .checkbox-row{display:flex;align-items:center;gap:8px;margin:8px 0;}
  .checkbox-row input{width:auto;}
  .checkbox-row label{color:var(--text);font-size:13px;}
  .load-row{display:grid;grid-template-columns:60px 1fr 1fr 1fr 1fr 1fr 1fr 28px;gap:4px;align-items:center;margin-bottom:4px;}
  .load-row select,.load-row input{padding:5px 6px;font-size:12px;text-align:right;}
  .load-row select{text-align:center;}
  .load-head{display:grid;grid-template-columns:60px 1fr 1fr 1fr 1fr 1fr 1fr 28px;gap:4px;}
  .load-head span{font-size:10px;color:var(--muted);text-align:center;}
  .dist-row{display:grid;grid-template-columns:70px 60px 1fr 28px;gap:4px;align-items:center;margin-bottom:4px;}
  .point-row{display:grid;grid-template-columns:70px 60px 1fr 60px 28px;gap:4px;align-items:center;margin-bottom:4px;}
  .temp-row{display:grid;grid-template-columns:1fr 70px 28px;gap:4px;align-items:center;margin-bottom:4px;}
  .dist-row input,.dist-row select,.point-row input,.point-row select,.temp-row input{padding:5px 6px;font-size:12px;}
  .icon-btn{padding:4px 6px;font-size:12px;line-height:1;background:transparent;
            border:1px solid var(--border);border-radius:4px;cursor:pointer;color:var(--text);}
  .icon-btn.danger{color:var(--danger);border-color:#4a1f24;}
</style>
</head>
<body>

<header>
  <div>
    <h1>Revit 4 Solver</h1>
    <div class="subtitle">3D space-frame solver &middot; load cases, combinations, diaphragm, thermal</div>
  </div>
  <div class="spacer"></div>
  <div style="width:180px;">
    <select id="unit-system">
      <option value="metric" selected>Metric (m, kN, MPa)</option>
      <option value="imperial">Imperial (ft, kip, ksi)</option>
    </select>
  </div>
  <div style="width:230px;">
    <select id="case-select"></select>
  </div>
  <button id="run-btn" class="primary" disabled>Solve</button>
  <button id="download-btn" disabled>Download CSV</button>
</header>

<div class="layout">
  <aside class="sidebar">
    <div id="load-status" class="status">
      <span class="dot"></span><span id="status-text">Loading Python runtime&hellip;</span>
    </div>

    <div class="section-title">Active Load</div>
    <div id="case-info" class="help" style="margin-bottom:12px;white-space:pre-wrap;"></div>

    <div class="section-title">Diaphragm</div>
    <div id="diaphragm-info" class="help"></div>

    <div id="custom-loads" style="display:none;">
      <div class="section-title">Load Inputs (user-defined)</div>
      <div class="checkbox-row">
        <input type="checkbox" id="custom-sw" checked>
        <label for="custom-sw">Include self-weight</label>
      </div>
      <div class="section-title">Nodal Loads (kN, kN&middot;m)</div>
      <div class="load-head" style="margin-bottom:6px;">
        <span>Node</span><span>Fx</span><span>Fy</span><span>Fz</span>
        <span>Mx</span><span>My</span><span>Mz</span><span></span>
      </div>
      <div id="nodal-rows"></div>
      <button id="add-nodal-btn" style="width:100%;margin-top:6px;">+ Add nodal load</button>

      <div class="section-title">Member UDL (kN/m)</div>
      <div id="dist-rows"></div>
      <button id="add-dist-btn" style="width:100%;margin-top:6px;">+ Add distributed load</button>

      <div class="section-title">Member Point (kN, pos 0..1)</div>
      <div id="point-rows"></div>
      <button id="add-point-btn" style="width:100%;margin-top:6px;">+ Add point load</button>

      <div class="section-title">Temperature (&deg;C)</div>
      <div class="temp-row" style="grid-template-columns:1fr 70px;margin-bottom:4px;">
        <span class="help" style="font-size:11px;">Members (comma-sep)</span>
        <span class="help" style="font-size:11px;text-align:right;">&Delta;T</span>
      </div>
      <div id="temp-rows"></div>
      <button id="add-temp-btn" style="width:100%;margin-top:6px;">+ Add temperature load</button>
    </div>

    <div class="section-title">Member Assignment</div>
    <div id="member-assignments"></div>

    <div class="section-title">About</div>
    <div class="help">
      Rev 4: nine built-in load cases (LC1 self-weight &hellip; LC9 +15&deg;C
      thermal), NSCP 2015 LRFD &amp; ASD combinations, roof diaphragm, and a
      fully solved stiffness response.  Select <code>CUSTOM</code> to enter your
      own loads.  All computation runs in your browser via Pyodide.
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

<script type="text/x-python" id="python-source">
import json
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict
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
    Quantity.THERMAL: 1e-6,
}

VALID_SYSTEMS = ("imperial", "metric")


class UnitSystem:
    def __init__(self, system="metric"):
        self.set_system(system)

    def set_system(self, system):
        if not self.validate(system):
            raise ValueError("Invalid unit system %r." % (system,))
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
        raise ValueError("%s has no SI mapping." % (quantity,))
    metric_value = value if f.base_system == "metric" else value * f.to_metric
    return metric_value * adjust


def from_si(value, quantity):
    if value is None:
        return None
    f = _CONVERSION_TABLE[quantity]
    adjust = _SI_PREFIX_ADJUST[quantity]
    if adjust is None:
        raise ValueError("%s has no SI mapping." % (quantity,))
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
            raise ValueError("Unknown material %r." % (key,))
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
            raise ValueError("Unknown section %r." % (label,))
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
LOCAL_DOF_INDEX = {label: k for k, label in enumerate(DOF_LABELS)}

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
        self.diaphragms = [build_roof_diaphragm(self)]

    def _validate_assignment(self):
        for mtype, props in self.assignment.items():
            if mtype not in VALID_MEMBER_TYPES:
                raise ValueError("Unknown member type: %r" % (mtype,))
            if not self.materials.exists(props['material']):
                raise ValueError("%s: unknown material %r" % (mtype, props['material']))
            if not self.sections.exists(props['section']):
                raise ValueError("%s: unknown section %r" % (mtype, props['section']))

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
                self.support_conditions[n] = {'Type': 'Pinned',
                    'UX': 'Fixed', 'UY': 'Fixed', 'UZ': 'Fixed',
                    'RX': 'Free', 'RY': 'Free', 'RZ': 'Free'}
            else:
                self.support_conditions[n] = {'Type': 'Free (no support)',
                    'UX': 'Free', 'UY': 'Free', 'UZ': 'Free',
                    'RX': 'Free', 'RY': 'Free', 'RZ': 'Free'}

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


# =========================== Rev 4 load model ===========================
LOAD_CATEGORIES = ('Dead', 'Live', 'Roof Live', 'Wind', 'Seismic', 'Temperature', 'Custom')
DESIGN_METHODS = ('LRFD', 'ASD')

DIR_VECTORS = {
    '+X': ( 1.0,  0.0,  0.0), '-X': (-1.0,  0.0,  0.0),
    '+Y': ( 0.0,  1.0,  0.0), '-Y': ( 0.0, -1.0,  0.0),
    '+Z': ( 0.0,  0.0,  1.0), '-Z': ( 0.0,  0.0, -1.0),
}

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


@dataclass
class PointLoad:
    node: int
    Fx: float = 0.0
    Fy: float = 0.0
    Fz: float = 0.0
    Mx: float = 0.0
    My: float = 0.0
    Mz: float = 0.0


@dataclass
class MemberDistributedLoad:
    member_id: str
    magnitude: float
    direction: str
    distribution_type: str = 'uniform'


@dataclass
class MemberPointLoad:
    member_id: str
    magnitude: float
    direction: str
    location: float = 0.5


@dataclass
class TemperatureLoad:
    member_ids: List[str]
    delta_T: float
    alpha: Optional[float] = None
    reference_T: Optional[float] = None


@dataclass
class LoadCase:
    id: str
    name: str
    category: str = 'Dead'
    description: str = ''
    self_weight_factor: float = 0.0
    nodal_loads: List[PointLoad] = field(default_factory=list)
    dist_loads: List[MemberDistributedLoad] = field(default_factory=list)
    point_loads: List[MemberPointLoad] = field(default_factory=list)
    temp_loads: List[TemperatureLoad] = field(default_factory=list)


@dataclass
class Diaphragm:
    id: str
    name: str
    master_node: int
    constrained_nodes: List[int]
    dofs: List[str]


@dataclass
class LoadCombination:
    id: str
    name: str
    design_method: str
    factors: Dict[str, float]


@dataclass
class ResolvedLoadCase:
    id: str
    name: str
    point_loads_si: List[PointLoad]
    thermal_axial_si: List[tuple]
    meta: dict = field(default_factory=dict)


ROOF_BEAMS = ('M5', 'M6', 'M7', 'M8')
ROOF_NODES = (5, 6, 7, 8)


def build_rev4_load_cases(model):
    out = {}
    out['LC1'] = LoadCase('LC1', 'DEAD / SELF WEIGHT', 'Dead',
        description='Self-weight, direction -Y, generated from density x A x L.',
        self_weight_factor=1.0)

    lc2 = LoadCase('LC2', 'ROOF DEAD', 'Dead',
        description='5 kN/m downward on roof beams M5-M8 (UDL).')
    for m in ROOF_BEAMS:
        lc2.dist_loads.append(MemberDistributedLoad(m, 5.0, '-Y'))
    out['LC2'] = lc2

    lc3 = LoadCase('LC3', 'ROOF LIVE', 'Roof Live',
        description='3 kN/m downward on roof beams (true UDL).')
    for m in ROOF_BEAMS:
        lc3.dist_loads.append(MemberDistributedLoad(m, 3.0, '-Y'))
    out['LC3'] = lc3

    lc4 = LoadCase('LC4', 'ROOF BEAM CENTER LOAD', 'Roof Live',
        description='5 kN downward at member midpoint (location = 0.5).')
    for m in ROOF_BEAMS:
        lc4.point_loads.append(MemberPointLoad(m, 5.0, '-Y', 0.5))
    out['LC4'] = lc4

    lc5 = LoadCase('LC5', 'WIND X', 'Wind',
        description='10 kN total in +X, equally at roof nodes 5-8.')
    for n in ROOF_NODES:
        lc5.nodal_loads.append(PointLoad(node=n, Fx=2.5))
    out['LC5'] = lc5

    lc6 = LoadCase('LC6', 'WIND Z', 'Wind',
        description='10 kN total in +Z, equally at roof nodes 5-8.')
    for n in ROOF_NODES:
        lc6.nodal_loads.append(PointLoad(node=n, Fz=2.5))
    out['LC6'] = lc6

    lc7 = LoadCase('LC7', 'SEISMIC X', 'Seismic',
        description='15 kN total in +X, 3.75 kN per roof node.')
    for n in ROOF_NODES:
        lc7.nodal_loads.append(PointLoad(node=n, Fx=3.75))
    out['LC7'] = lc7

    lc8 = LoadCase('LC8', 'SEISMIC Z', 'Seismic',
        description='15 kN total in +Z, 3.75 kN per roof node.')
    for n in ROOF_NODES:
        lc8.nodal_loads.append(PointLoad(node=n, Fz=3.75))
    out['LC8'] = lc8

    out['LC9'] = LoadCase('LC9', 'TEMPERATURE +15 C', 'Temperature',
        description='+15 C uniform on roof beams M5-M8. Net axial force = 0.',
        temp_loads=[TemperatureLoad(list(ROOF_BEAMS), 15.0)])
    return out


def build_roof_diaphragm(model):
    roof = sorted(n for n, (x, y, z) in model.nodes.items() if abs(y - 6.0) < 1e-9)
    master = min(roof)
    slaves = [n for n in roof if n != master]
    return Diaphragm('D1', 'Roof diaphragm (Y=6), master N%d' % master,
                     master, slaves, ['UX', 'UZ', 'RY'])


def build_nscp_combinations():
    return [
        LoadCombination('C01', '1.4D',                   'LRFD', {'LC1':1.4, 'LC2':1.4}),
        LoadCombination('C02', '1.2D + 1.6L',            'LRFD', {'LC1':1.2, 'LC2':1.2, 'LC3':1.6, 'LC4':1.6}),
        LoadCombination('C03', '1.2D + 1.6Lr',           'LRFD', {'LC1':1.2, 'LC2':1.2, 'LC3':1.6}),
        LoadCombination('C04', '1.2D + 1.0W + 1.0L',     'LRFD', {'LC1':1.2, 'LC2':1.2, 'LC3':1.0, 'LC4':1.0, 'LC5':1.0}),
        LoadCombination('C05', '1.2D + 1.0W (Z)',        'LRFD', {'LC1':1.2, 'LC2':1.2, 'LC6':1.0}),
        LoadCombination('C06', '1.2D + 1.0E + 1.0L',     'LRFD', {'LC1':1.2, 'LC2':1.2, 'LC3':1.0, 'LC4':1.0, 'LC7':1.0}),
        LoadCombination('C07', '0.9D + 1.0W',            'LRFD', {'LC1':0.9, 'LC2':0.9, 'LC5':1.0}),
        LoadCombination('C08', '0.9D + 1.0E',            'LRFD', {'LC1':0.9, 'LC2':0.9, 'LC7':1.0}),
        LoadCombination('C09', '1.2D + 1.0T + 1.0L',     'LRFD', {'LC1':1.2, 'LC2':1.2, 'LC3':1.0, 'LC4':1.0, 'LC9':1.0}),
        LoadCombination('C10', '1.2D + 1.6T',            'LRFD', {'LC1':1.2, 'LC2':1.2, 'LC9':1.6}),
        LoadCombination('C11', '1.2D + 1.0T + 1.0W',     'LRFD', {'LC1':1.2, 'LC2':1.2, 'LC9':1.0, 'LC5':1.0}),
        LoadCombination('C12', '0.9D + 1.0T',            'LRFD', {'LC1':0.9, 'LC2':0.9, 'LC9':1.0}),
        LoadCombination('C13', 'D',                      'ASD',  {'LC1':1.0, 'LC2':1.0}),
        LoadCombination('C14', 'D + L',                  'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC3':1.0, 'LC4':1.0}),
        LoadCombination('C15', 'D + Lr',                 'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC3':1.0}),
        LoadCombination('C16', 'D + 0.75L + 0.75Lr',     'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC3':0.75, 'LC4':0.75}),
        LoadCombination('C17', 'D + 0.6W',               'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC5':0.6}),
        LoadCombination('C18', 'D + 0.75L + 0.75(0.6W)', 'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC3':0.75, 'LC4':0.75, 'LC5':0.45}),
        LoadCombination('C19', 'D + 0.7E',               'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC7':0.7}),
        LoadCombination('C20', 'D + 0.75L + 0.75(0.7E)', 'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC3':0.75, 'LC4':0.75, 'LC7':0.525}),
        LoadCombination('C21', '0.6D + 0.6W',            'ASD',  {'LC1':0.6, 'LC2':0.6, 'LC5':0.6}),
        LoadCombination('C22', '0.6D + 0.7E',            'ASD',  {'LC1':0.6, 'LC2':0.6, 'LC7':0.7}),
        LoadCombination('C23', 'D + 0.75T',              'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC9':0.75}),
        LoadCombination('C24', 'D + L + 0.75T',          'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC3':1.0, 'LC4':1.0, 'LC9':0.75}),
        LoadCombination('C25', 'D + 0.75T + 0.75(0.6W)', 'ASD',  {'LC1':1.0, 'LC2':1.0, 'LC9':0.75, 'LC5':0.45}),
        LoadCombination('C26', '0.6D + 0.6T',            'ASD',  {'LC1':0.6, 'LC2':0.6, 'LC9':0.6}),
    ]


# =========================== Rev 4 load resolvers ===========================
def _direction_components_local(model, member_id, direction_global):
    g = np.array(DIR_VECTORS[direction_global], dtype=float)
    ax = model.member_local_axes[member_id]
    R = np.vstack([ax['local_x'], ax['local_y'], ax['local_z']])
    return R @ g


def _equivalent_udl_local(w, L):
    wx, wy, wz = w
    f = np.zeros(12)
    if abs(wx) > 0:
        f[0] += wx * L / 2.0
        f[6] += wx * L / 2.0
    if abs(wy) > 0:
        f[1] += wy * L / 2.0
        f[5] += wy * L * L / 12.0
        f[7] += wy * L / 2.0
        f[11] += -wy * L * L / 12.0
    if abs(wz) > 0:
        f[2] += wz * L / 2.0
        f[4] += -wz * L * L / 12.0
        f[8] += wz * L / 2.0
        f[10] += wz * L * L / 12.0
    return f


def _equivalent_point_local(p, L, a):
    px, py, pz = p
    b = 1.0 - a
    f = np.zeros(12)
    if abs(px) > 0:
        f[0] += px * b
        f[6] += px * a
    if abs(py) > 0:
        N1 = 1 - 3*a*a + 2*a*a*a
        N2 = L * (a - 2*a*a + a*a*a)
        N3 = 3*a*a - 2*a*a*a
        N4 = L * (-a*a + a*a*a)
        f[1] += py * N1
        f[5] += py * N2
        f[7] += py * N3
        f[11] += py * N4
    if abs(pz) > 0:
        N1 = 1 - 3*a*a + 2*a*a*a
        N2 = -L * (a - 2*a*a + a*a*a)
        N3 = 3*a*a - 2*a*a*a
        N4 = -L * (-a*a + a*a*a)
        f[2] += pz * N1
        f[4] += pz * N2
        f[8] += pz * N3
        f[10] += pz * N4
    return f


def resolve_load_case(model, lc):
    u = model.units
    metric = (u.system == 'metric')
    force_to_N = _FORCE_UNIT_TO_N['kN'] if metric else _FORCE_UNIT_TO_N['kip']
    moment_to_Nm = _MOMENT_UNIT_TO_NM['kN*m'] if metric else _MOMENT_UNIT_TO_NM['kip*ft']
    length_to_m = 1.0 if metric else _FT_TO_M
    dist_to_N_per_m = force_to_N / length_to_m

    pt_si = []

    if lc.self_weight_factor:
        totals = {n: 0.0 for n in model.nodes}
        for m, (i, j) in model.members.items():
            props = model.member_solver_properties(m)
            L = model.member_length(m)
            w_N = props['density'] * props['A'] * L * lc.self_weight_factor
            totals[i] += w_N / 2.0
            totals[j] += w_N / 2.0
        for n, w in totals.items():
            if w:
                pt_si.append(PointLoad(node=n, Fy=-w))

    for pl in lc.nodal_loads:
        pt_si.append(PointLoad(node=pl.node,
            Fx=pl.Fx * force_to_N, Fy=pl.Fy * force_to_N, Fz=pl.Fz * force_to_N,
            Mx=pl.Mx * moment_to_Nm, My=pl.My * moment_to_Nm, Mz=pl.Mz * moment_to_Nm))

    for dl in lc.dist_loads:
        m = dl.member_id
        L = model.member_length(m)
        w_N_per_m = dl.magnitude * dist_to_N_per_m
        comp = _direction_components_local(model, m, dl.direction)
        f_loc = _equivalent_udl_local(comp * w_N_per_m, L)
        ax = model.member_local_axes[m]
        T = transformation_matrix(ax['local_x'], ax['local_y'], ax['local_z'])
        f_glob = T.T @ f_loc
        i, j = model.members[m]
        for node, base in ((i, 0), (j, 6)):
            pt_si.append(PointLoad(node=node,
                Fx=float(f_glob[base+0]), Fy=float(f_glob[base+1]), Fz=float(f_glob[base+2]),
                Mx=float(f_glob[base+3]), My=float(f_glob[base+4]), Mz=float(f_glob[base+5])))

    for pl in lc.point_loads:
        m = pl.member_id
        L = model.member_length(m)
        P_N = pl.magnitude * force_to_N
        comp = _direction_components_local(model, m, pl.direction)
        f_loc = _equivalent_point_local(comp * P_N, L, pl.location)
        ax = model.member_local_axes[m]
        T = transformation_matrix(ax['local_x'], ax['local_y'], ax['local_z'])
        f_glob = T.T @ f_loc
        i, j = model.members[m]
        for node, base in ((i, 0), (j, 6)):
            pt_si.append(PointLoad(node=node,
                Fx=float(f_glob[base+0]), Fy=float(f_glob[base+1]), Fz=float(f_glob[base+2]),
                Mx=float(f_glob[base+3]), My=float(f_glob[base+4]), Mz=float(f_glob[base+5])))

    thermal = []
    for tl in lc.temp_loads:
        dT = tl.delta_T if metric else tl.delta_T * 1.8
        for m in tl.member_ids:
            mat = model.member_material(m)
            alpha = tl.alpha if tl.alpha is not None else to_si(mat.therm, Quantity.THERMAL)
            sec = model.member_section(m)
            E = to_si(mat.E, Quantity.STRESS)
            A = to_si(sec.A, Quantity.AREA)
            N_thermal = E * A * alpha * dT
            thermal.append((m, N_thermal))

    return ResolvedLoadCase(id=lc.id, name=lc.name,
                            point_loads_si=pt_si, thermal_axial_si=thermal,
                            meta={'category': lc.category, 'description': lc.description})


def resolve_combination(model, comb, load_cases):
    pt_all = []
    th_all = []
    for lc_id, factor in comb.factors.items():
        lc = load_cases[lc_id]
        r = resolve_load_case(model, lc)
        for p in r.point_loads_si:
            pt_all.append(PointLoad(node=p.node,
                Fx=p.Fx*factor, Fy=p.Fy*factor, Fz=p.Fz*factor,
                Mx=p.Mx*factor, My=p.My*factor, Mz=p.Mz*factor))
        for (m, N) in r.thermal_axial_si:
            th_all.append((m, N * factor))
    return ResolvedLoadCase(id=comb.id, name=comb.name,
                            point_loads_si=pt_all, thermal_axial_si=th_all,
                            meta={'category': comb.design_method, 'description': comb.name})


# =========================== solver.py ===========================
DOF_PER_NODE = 6


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
    def __init__(self, model, displacements, reactions, member_end_forces, name):
        self.model = model
        self.displacements = displacements
        self.reactions = reactions
        self.member_end_forces = member_end_forces
        self.load_case_name = name

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
        element_data[m] = dict(k_local=k_local_c, T=T, dof_map=dof_map,
                               f_thermal_local=np.zeros(12))

    F = np.zeros(n_dof)
    for load in load_case.point_loads_si:
        base = node_index[load.node] * DOF_PER_NODE
        F[base:base+6] += [load.Fx, load.Fy, load.Fz, load.Mx, load.My, load.Mz]

    for (m, N_thermal) in load_case.thermal_axial_si:
        i, j = model.members[m]
        axes = model.member_local_axes[m]
        T = transformation_matrix(axes['local_x'], axes['local_y'], axes['local_z'])
        f_loc = np.zeros(12)
        f_loc[0] = -N_thermal
        f_loc[6] = +N_thermal
        element_data[m]['f_thermal_local'] += f_loc
        f_glob = T.T @ f_loc
        bi = node_index[i] * DOF_PER_NODE
        bj = node_index[j] * DOF_PER_NODE
        F[bi:bi+6] += f_glob[0:6]
        F[bj:bj+6] += f_glob[6:12]

    master_of = {}
    for dg in getattr(model, 'diaphragms', []):
        m_base = node_index[dg.master_node] * DOF_PER_NODE
        for sn in dg.constrained_nodes:
            s_base = node_index[sn] * DOF_PER_NODE
            for lab in dg.dofs:
                master_of[s_base + LOCAL_DOF_INDEX[lab]] = m_base + LOCAL_DOF_INDEX[lab]

    restrained_base = set()
    for n in model.support_nodes:
        base = node_index[n] * DOF_PER_NODE
        restrained_base.update({base+0, base+1, base+2})

    if master_of:
        slave_dofs = set(master_of.keys())
        indep_dofs = [d for d in range(n_dof) if d not in slave_dofs]
        indep_index = {d: k for k, d in enumerate(indep_dofs)}
        T_red = np.zeros((n_dof, len(indep_dofs)))
        for k, d in enumerate(indep_dofs):
            T_red[d, k] = 1.0
        for s, mm in master_of.items():
            T_red[s, indep_index[mm]] += 1.0
        K_red = T_red.T @ K @ T_red
        F_red = T_red.T @ F
        restrained_red = {indep_index[d] for d in restrained_base if d in indep_index}
        free_red = [d for d in range(len(indep_dofs)) if d not in restrained_red]
        u_red = np.zeros(len(indep_dofs))
        if free_red:
            u_red[free_red] = np.linalg.solve(K_red[np.ix_(free_red, free_red)], F_red[free_red])
        u = T_red @ u_red
    else:
        free = [d for d in range(n_dof) if d not in restrained_base]
        u = np.zeros(n_dof)
        if free:
            u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])

    reaction_full = K @ u - F

    displacements, reactions = {}, {}
    for n, idx in node_index.items():
        base = idx * DOF_PER_NODE
        displacements[n] = {lab: float(u[base+k]) for k, lab in enumerate(DOF_LABELS)}
        if n in model.support_nodes:
            reactions[n] = {lab: float(reaction_full[base+k]) for k, lab in enumerate(DOF_LABELS)}

    member_end_forces = {}
    for m, data in element_data.items():
        u_elem_global = u[data['dof_map']]
        u_elem_local = data['T'] @ u_elem_global
        f_elem_local = data['k_local'] @ u_elem_local - data['f_thermal_local']
        member_end_forces[m] = {
            'i': dict(zip(DOF_LABELS, f_elem_local[0:6])),
            'j': dict(zip(DOF_LABELS, f_elem_local[6:12])),
        }
    return SolveResult(model, displacements, reactions, member_end_forces, load_case.name)


# =========================== Web API ===========================
_MATS = MaterialLibrary()
_SECS = SectionLibrary()


def api_options():
    model = StructuralModel()
    lcs = build_rev4_load_cases(model)
    return json.dumps({
        'materials': _MATS.keys(),
        'sections': _SECS.keys(),
        'member_types': ['column', 'roof_beam', 'tie_beam'],
        'nodes': sorted(NODES.keys()),
        'members': sorted(MEMBERS.keys()),
        'defaults': DEFAULT_ASSIGNMENT,
        'load_cases': [{'id': k, 'name': v.name, 'category': v.category}
                       for k, v in lcs.items()],
        'combinations': [{'id': c.id, 'name': c.name, 'method': c.design_method}
                         for c in build_nscp_combinations()],
    })


def build_custom_load_case(model, custom):
    """Turn the JS 'custom_loads' payload into a real LoadCase."""
    lc = LoadCase('CUSTOM', 'User-defined', 'Custom',
                  description='Entered in the sidebar.')
    if custom.get('self_weight'):
        lc.self_weight_factor = 1.0

    valid_nodes = set(model.nodes.keys())
    for r in custom.get('nodal', []):
        try:
            node = int(r.get('node'))
        except (TypeError, ValueError):
            continue
        if node not in valid_nodes:
            raise ValueError('Custom load: node %r not in model.' % (r.get('node'),))
        lc.nodal_loads.append(PointLoad(
            node=node,
            Fx=float(r.get('Fx', 0) or 0), Fy=float(r.get('Fy', 0) or 0),
            Fz=float(r.get('Fz', 0) or 0), Mx=float(r.get('Mx', 0) or 0),
            My=float(r.get('My', 0) or 0), Mz=float(r.get('Mz', 0) or 0)))

    valid_members = set(model.members.keys())
    valid_dirs = set(DIR_VECTORS.keys())
    for r in custom.get('distributed', []):
        m = str(r.get('member', ''))
        if m not in valid_members:
            raise ValueError('Custom UDL: unknown member %r.' % (m,))
        d = str(r.get('direction', '-Y'))
        if d not in valid_dirs:
            raise ValueError('Custom UDL: bad direction %r.' % (d,))
        lc.dist_loads.append(MemberDistributedLoad(
            m, float(r.get('magnitude', 0) or 0), d))

    for r in custom.get('point', []):
        m = str(r.get('member', ''))
        if m not in valid_members:
            raise ValueError('Custom point load: unknown member %r.' % (m,))
        d = str(r.get('direction', '-Y'))
        if d not in valid_dirs:
            raise ValueError('Custom point load: bad direction %r.' % (d,))
        loc = float(r.get('location', 0.5) or 0.5)
        if not (0.0 <= loc <= 1.0):
            raise ValueError('Custom point load: location must be 0..1.')
        lc.point_loads.append(MemberPointLoad(m, float(r.get('magnitude', 0) or 0), d, loc))

    for r in custom.get('temperature', []):
        members = r.get('members', [])
        if not isinstance(members, list):
            members = [members]
        members = [str(m) for m in members if str(m) in valid_members]
        if not members:
            continue
        lc.temp_loads.append(TemperatureLoad(members, float(r.get('delta_T', 0) or 0)))

    return lc


def api_validate(config_json):
    cfg = json.loads(config_json) if config_json else {}
    model = StructuralModel(cfg.get('unit', 'metric'), cfg.get('assignment'))
    lcs = build_rev4_load_cases(model)
    out = []
    for lc_id, lc in lcs.items():
        r = resolve_load_case(model, lc)
        out.append({
            'id': lc_id, 'name': lc.name, 'category': lc.category,
            'nodes_loaded': sorted({p.node for p in r.point_loads_si}),
            'total_Fx': sum(p.Fx for p in r.point_loads_si),
            'total_Fy': sum(p.Fy for p in r.point_loads_si),
            'total_Fz': sum(p.Fz for p in r.point_loads_si),
            'net_thermal_force': sum(N for _, N in r.thermal_axial_si),
            'n_points': len(r.point_loads_si),
            'n_thermal': len(r.thermal_axial_si),
        })
    return json.dumps(out)


def api_solve(config_json):
    cfg = json.loads(config_json)
    unit_system = cfg.get('unit', 'metric')
    assignment = cfg.get('assignment', DEFAULT_ASSIGNMENT)
    selected = cfg.get('selected', 'LC1')

    model = StructuralModel(unit_system=unit_system, assignment=assignment)
    u = model.units
    lcs = build_rev4_load_cases(model)
    combos = {c.id: c for c in build_nscp_combinations()}

    if selected == 'CUSTOM':
        custom_cfg = cfg.get('custom_loads', {})
        custom_lc = build_custom_load_case(model, custom_cfg)
        resolved = resolve_load_case(model, custom_lc)
        label = 'CUSTOM \u00b7 user-defined'
        kind = 'custom'
    elif selected in lcs:
        resolved = resolve_load_case(model, lcs[selected])
        label = resolved.name
        kind = 'case'
    elif selected in combos:
        resolved = resolve_combination(model, combos[selected], lcs)
        label = combos[selected].name + ' (' + combos[selected].design_method + ')'
        kind = 'combination'
    else:
        raise ValueError("Unknown selection %r." % (selected,))

    result = solve(model, resolved)

    fu = u.label(Quantity.FORCE); mu = u.label(Quantity.MOMENT); lu = u.label(Quantity.LENGTH_GEOM)
    nodes_out = {str(n): list(map(float, c)) for n, c in model.nodes.items()}
    members_out = []
    for name, (i, j) in model.members.items():
        members_out.append({
            'name': name, 'i': i, 'j': j,
            'type': model.member_type[name],
            'material': model.assignment[model.member_type[name]]['material'],
            'section':  model.assignment[model.member_type[name]]['section'],
            'length':   model.member_length_display(name),
            'pinned':   model.member_releases[name]['Pinned'],
            'axes': {k: model.member_local_axes[name]['local_'+k].tolist() for k in ('x','y','z')},
        })

    load_arrows = {}
    for p in resolved.point_loads_si:
        v = load_arrows.setdefault(p.node, [0.0, 0.0, 0.0])
        v[0] += p.Fx; v[1] += p.Fy; v[2] += p.Fz

    disp_rows = []
    for n in sorted(result.displacements):
        d = result.displacements[n]
        disp_rows.append([n,
            u.convert(from_si(d['UX'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
            u.convert(from_si(d['UY'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
            u.convert(from_si(d['UZ'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
            d['RX'], d['RY'], d['RZ']])
    disp_tbl = {'headers': ['Node', 'UX ('+lu+')', 'UY ('+lu+')', 'UZ ('+lu+')',
                             'RX (rad)', 'RY (rad)', 'RZ (rad)'], 'rows': disp_rows}

    react_rows = []
    for n in sorted(result.reactions):
        r = result.reactions[n]
        react_rows.append([n,
            u.convert(from_si(r['UX'], Quantity.FORCE), Quantity.FORCE),
            u.convert(from_si(r['UY'], Quantity.FORCE), Quantity.FORCE),
            u.convert(from_si(r['UZ'], Quantity.FORCE), Quantity.FORCE),
            u.convert(from_si(r['RX'], Quantity.MOMENT), Quantity.MOMENT),
            u.convert(from_si(r['RY'], Quantity.MOMENT), Quantity.MOMENT),
            u.convert(from_si(r['RZ'], Quantity.MOMENT), Quantity.MOMENT)])
    react_tbl = {'headers': ['Node', 'Rx ('+fu+')', 'Ry ('+fu+')', 'Rz ('+fu+')',
                              'Mx ('+mu+')', 'My ('+mu+')', 'Mz ('+mu+')'], 'rows': react_rows}

    force_rows = []
    for m in model.members:
        for end in ('i', 'j'):
            f = result.member_end_forces[m][end]
            force_rows.append([m, end,
                u.convert(from_si(f['UX'], Quantity.FORCE), Quantity.FORCE),
                u.convert(from_si(f['UY'], Quantity.FORCE), Quantity.FORCE),
                u.convert(from_si(f['UZ'], Quantity.FORCE), Quantity.FORCE),
                u.convert(from_si(f['RX'], Quantity.MOMENT), Quantity.MOMENT),
                u.convert(from_si(f['RY'], Quantity.MOMENT), Quantity.MOMENT),
                u.convert(from_si(f['RZ'], Quantity.MOMENT), Quantity.MOMENT)])
    forces_tbl = {'headers': ['Member', 'End', 'Axial ('+fu+')', 'Shear-y ('+fu+')',
                              'Shear-z ('+fu+')', 'Torsion ('+mu+')',
                              'Moment-y ('+mu+')', 'Moment-z ('+mu+')'], 'rows': force_rows}

    members_tbl = {'headers': ['Member', 'i', 'j', 'Type', 'Material', 'Section', 'Length ('+lu+')'],
                   'rows': [[m['name'], m['i'], m['j'], m['type'], m['material'],
                             m['section'], m['length']] for m in members_out]}

    total_fy_applied  = u.convert(from_si(sum(p.Fy for p in resolved.point_loads_si),
                                          Quantity.FORCE), Quantity.FORCE)
    total_fy_reaction = u.convert(from_si(result.reaction_sum_Y(), Quantity.FORCE), Quantity.FORCE)
    worst_node = None; worst_mag = -1.0; wd = None
    for n, d in result.displacements.items():
        mag = (d['UX']**2 + d['UY']**2 + d['UZ']**2) ** 0.5
        if mag > worst_mag:
            worst_mag, worst_node, wd = mag, n, d
    worst_disp = {
        'node': worst_node,
        'UX': u.convert(from_si(wd['UX'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
        'UY': u.convert(from_si(wd['UY'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
        'UZ': u.convert(from_si(wd['UZ'], Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
        'mag': u.convert(from_si(worst_mag, Quantity.LENGTH_GEOM), Quantity.LENGTH_GEOM),
    }

    return json.dumps({
        'unit_system': unit_system,
        'selected': {'id': resolved.id, 'name': label, 'kind': kind,
                     'meta': resolved.meta},
        'labels': {'force': fu, 'moment': mu, 'length': lu},
        'nodes': nodes_out, 'members': members_out,
        'support_nodes': list(model.support_nodes),
        'pinned_members': list(model.pinned_members),
        'diaphragms': [{'id': d.id, 'master': d.master_node,
                        'slaves': d.constrained_nodes, 'dofs': d.dofs}
                       for d in model.diaphragms],
        'load_arrows': {str(k): v for k, v in load_arrows.items()},
        'tables': {'displacements': disp_tbl, 'reactions': react_tbl,
                   'member_forces': forces_tbl, 'members': members_tbl},
        'kpi': {
            'load_case': label,
            'n_loads': len(resolved.point_loads_si),
            'n_thermal': len(resolved.thermal_axial_si),
            'total_fy_applied': total_fy_applied,
            'total_fy_reaction': total_fy_reaction,
            'residual': total_fy_applied + total_fy_reaction,
            'worst_disp': worst_disp,
        },
    })
</script>

<script>
(function() {
  const statusEl   = document.getElementById('load-status');
  const statusText = document.getElementById('status-text');
  const runBtn     = document.getElementById('run-btn');
  const dlBtn      = document.getElementById('download-btn');
  const unitSel    = document.getElementById('unit-system');
  const caseSel    = document.getElementById('case-select');
  const memberDiv  = document.getElementById('member-assignments');
  const kpiDiv     = document.getElementById('kpis');
  const caseInfo   = document.getElementById('case-info');
  const diaInfo    = document.getElementById('diaphragm-info');

  let pyodide = null;
  let options = null;
  let lastResult = null;

  const COLOR = {column:'#f59e0b', roof_beam:'#22c55e', tie_beam:'#3b82f6'};
  const TYPE_LABEL = {column:'Column', roof_beam:'Roof Beam', tie_beam:'Tie Beam'};

  function setStatus(msg, cls) {
    statusText.textContent = msg;
    statusEl.className = 'status' + (cls ? ' ' + cls : '');
  }

  async function boot() {
    try {
      setStatus('Loading Python runtime\u2026');
      pyodide = await loadPyodide();
      setStatus('Loading NumPy\u2026');
      await pyodide.loadPackage(['numpy']);
      setStatus('Compiling solver\u2026');
      const src = document.getElementById('python-source').textContent;
      pyodide.runPython(src);

      options = JSON.parse(pyodide.runPython('api_options()'));
      buildCaseDropdown();
      buildMemberAssignmentUI();
      buildCustomLoadUI();
      toggleCustomVisibility();

      const dg = {id:'D1', master:5, slaves:[6,7,8], dofs:['UX','UZ','RY']};
      diaInfo.textContent = 'D1 \u2014 master N' + dg.master +
        ', slaves N' + dg.slaves.join(', N') +
        '.\nCoupled DOFs: ' + dg.dofs.join(', ') +
        '.\nFree: UY, RX, RZ.';

      setStatus('Ready. Select a load case, then Solve.', 'ok');
      runBtn.disabled = false;
      runBtn.click();
    } catch (e) {
      console.error(e);
      setStatus('Failed to load: ' + (e.message || e), 'err');
    }
  }

  function buildCaseDropdown() {
    caseSel.innerHTML = '';
    const custom = document.createElement('option');
    custom.value = 'CUSTOM';
    custom.textContent = 'CUSTOM \u00b7 user-defined';
    caseSel.appendChild(custom);

    const og1 = document.createElement('optgroup'); og1.label = 'Load Cases';
    for (const lc of options.load_cases) {
      const o = document.createElement('option');
      o.value = lc.id; o.textContent = lc.id + ' \u00b7 ' + lc.name;
      og1.appendChild(o);
    }
    caseSel.appendChild(og1);

    const og2 = document.createElement('optgroup'); og2.label = 'NSCP Combinations';
    for (const c of options.combinations) {
      const o = document.createElement('option');
      o.value = c.id; o.textContent = c.id + ' \u00b7 ' + c.name + ' [' + c.method + ']';
      og2.appendChild(o);
    }
    caseSel.appendChild(og2);

    caseSel.addEventListener('change', function() {
      toggleCustomVisibility();
      runSolve();
    });
  }

  function buildMemberAssignmentUI() {
    memberDiv.innerHTML = '';
    for (const mtype of options.member_types) {
      const block = document.createElement('div');
      block.className = 'member-block';
      block.innerHTML =
        '<h4><span class="swatch" style="background:' + COLOR[mtype] + '"></span>' +
        TYPE_LABEL[mtype] + '</h4>' +
        '<div class="field"><label>Material</label>' +
        '<select data-mtype="' + mtype + '" data-field="material"></select></div>' +
        '<div class="field" style="margin-bottom:0"><label>Section</label>' +
        '<select data-mtype="' + mtype + '" data-field="section"></select></div>';
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

  function addNodalRow(vals) {
    vals = vals || {};
    const row = document.createElement('div');
    row.className = 'load-row';
    const nodeOpts = options.nodes.map(function(n) {
      return '<option value="' + n + '"' + (Number(vals.node) === n ? ' selected' : '') +
             '>N' + n + '</option>';
    }).join('');
    row.innerHTML =
      '<select data-field="node">' + nodeOpts + '</select>' +
      ['Fx','Fy','Fz','Mx','My','Mz'].map(function(f) {
        return '<input data-field="' + f + '" type="text" value="' +
               (vals[f] !== undefined ? vals[f] : 0) + '" inputmode="decimal">';
      }).join('') +
      '<button class="icon-btn danger" title="Remove">&times;</button>';
    row.querySelector('button').onclick = function(){ row.remove(); };
    document.getElementById('nodal-rows').appendChild(row);
  }

  function addDistRow(vals) {
    vals = vals || {};
    const mOpts = options.members.map(function(m) {
      return '<option value="' + m + '"' + (vals.member === m ? ' selected' : '') +
             '>' + m + '</option>';
    }).join('');
    const dOpts = ['+X','-X','+Y','-Y','+Z','-Z'].map(function(d) {
      return '<option value="' + d + '"' + (vals.direction === d ? ' selected' : '') +
             '>' + d + '</option>';
    }).join('');
    const row = document.createElement('div');
    row.className = 'dist-row';
    row.innerHTML =
      '<select data-field="member">' + mOpts + '</select>' +
      '<select data-field="direction">' + dOpts + '</select>' +
      '<input data-field="magnitude" type="text" value="' +
      (vals.magnitude !== undefined ? vals.magnitude : 5) + '" inputmode="decimal">' +
      '<button class="icon-btn danger" title="Remove">&times;</button>';
    row.querySelector('button').onclick = function(){ row.remove(); };
    document.getElementById('dist-rows').appendChild(row);
  }

  function addPointRow(vals) {
    vals = vals || {};
    const mOpts = options.members.map(function(m) {
      return '<option value="' + m + '"' + (vals.member === m ? ' selected' : '') +
             '>' + m + '</option>';
    }).join('');
    const dOpts = ['+X','-X','+Y','-Y','+Z','-Z'].map(function(d) {
      return '<option value="' + d + '"' + (vals.direction === d ? ' selected' : '') +
             '>' + d + '</option>';
    }).join('');
    const row = document.createElement('div');
    row.className = 'point-row';
    row.innerHTML =
      '<select data-field="member">' + mOpts + '</select>' +
      '<select data-field="direction">' + dOpts + '</select>' +
      '<input data-field="magnitude" type="text" value="' +
      (vals.magnitude !== undefined ? vals.magnitude : 5) + '" inputmode="decimal">' +
      '<input data-field="location" type="text" value="' +
      (vals.location !== undefined ? vals.location : 0.5) + '" inputmode="decimal">' +
      '<button class="icon-btn danger" title="Remove">&times;</button>';
    row.querySelector('button').onclick = function(){ row.remove(); };
    document.getElementById('point-rows').appendChild(row);
  }

  function addTempRow(vals) {
    vals = vals || {};
    const row = document.createElement('div');
    row.className = 'temp-row';
    row.innerHTML =
      '<input data-field="members" type="text" value="' +
      (vals.members || 'M5,M6,M7,M8') + '" title="Comma-separated member IDs">' +
      '<input data-field="delta_T" type="text" value="' +
      (vals.delta_T !== undefined ? vals.delta_T : 15) + '" inputmode="decimal">' +
      '<button class="icon-btn danger" title="Remove">&times;</button>';
    row.querySelector('button').onclick = function(){ row.remove(); };
    document.getElementById('temp-rows').appendChild(row);
  }

  function buildCustomLoadUI() {
    document.getElementById('add-nodal-btn').onclick = function(){ addNodalRow(); };
    document.getElementById('add-dist-btn').onclick  = function(){ addDistRow(); };
    document.getElementById('add-point-btn').onclick = function(){ addPointRow(); };
    document.getElementById('add-temp-btn').onclick  = function(){ addTempRow(); };
    addNodalRow({node: options.nodes[5] || options.nodes[0], Fx: 10});
    addDistRow({member: 'M5', direction: '-Y', magnitude: 5});
    addPointRow({member: 'M5', direction: '-Y', magnitude: 5, location: 0.5});
    addTempRow({members: 'M5,M6,M7,M8', delta_T: 15});
  }

  function toggleCustomVisibility() {
    document.getElementById('custom-loads').style.display =
      (caseSel.value === 'CUSTOM') ? 'block' : 'none';
  }

  function collectCustomLoads() {
    const nodal = [];
    document.querySelectorAll('#nodal-rows .load-row').forEach(function(row) {
      const nodeEl = row.querySelector('[data-field="node"]');
      if (!nodeEl) return;
      const obj = {node: parseInt(nodeEl.value, 10)};
      row.querySelectorAll('input').forEach(function(inp) {
        const v = inp.value.trim();
        obj[inp.dataset.field] = v === '' ? 0 : (parseFloat(v) || 0);
      });
      nodal.push(obj);
    });
    const distributed = [];
    document.querySelectorAll('#dist-rows .dist-row').forEach(function(row) {
      distributed.push({
        member: row.querySelector('[data-field="member"]').value,
        direction: row.querySelector('[data-field="direction"]').value,
        magnitude: parseFloat(row.querySelector('[data-field="magnitude"]').value) || 0,
      });
    });
    const point = [];
    document.querySelectorAll('#point-rows .point-row').forEach(function(row) {
      point.push({
        member: row.querySelector('[data-field="member"]').value,
        direction: row.querySelector('[data-field="direction"]').value,
        magnitude: parseFloat(row.querySelector('[data-field="magnitude"]').value) || 0,
        location: parseFloat(row.querySelector('[data-field="location"]').value) || 0.5,
      });
    });
    const temperature = [];
    document.querySelectorAll('#temp-rows .temp-row').forEach(function(row) {
      const memStr = row.querySelector('[data-field="members"]').value || '';
      temperature.push({
        members: memStr.split(',').map(function(s){return s.trim();}).filter(Boolean),
        delta_T: parseFloat(row.querySelector('[data-field="delta_T"]').value) || 0,
      });
    });
    return {
      self_weight: document.getElementById('custom-sw').checked,
      nodal: nodal, distributed: distributed,
      point: point, temperature: temperature,
    };
  }

  document.querySelectorAll('.tab').forEach(function(t) {
    t.addEventListener('click', function() {
      document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('active');});
      document.querySelectorAll('.tab-panel').forEach(function(x){x.classList.remove('active');});
      t.classList.add('active');
      document.getElementById('panel-' + t.dataset.tab).classList.add('active');
      if (t.dataset.tab === 'view') setTimeout(function(){ Plotly.Plots.resize('plot'); }, 30);
    });
  });

  function collectConfig() {
    const assignment = {};
    for (const mtype of options.member_types) {
      const mat = memberDiv.querySelector('[data-mtype="' + mtype + '"][data-field="material"]').value;
      const sec = memberDiv.querySelector('[data-mtype="' + mtype + '"][data-field="section"]').value;
      assignment[mtype] = {material: mat, section: sec};
    }
    const cfg = {unit: unitSel.value, assignment: assignment, selected: caseSel.value};
    if (caseSel.value === 'CUSTOM') {
      cfg.custom_loads = collectCustomLoads();
    }
    return cfg;
  }

  function fmt(v, digits) {
    digits = digits === undefined ? 4 : digits;
    if (v === null || v === undefined) return '\u2014';
    if (typeof v !== 'number') return String(v);
    if (Math.abs(v) < 1e-9) return '0';
    const abs = Math.abs(v);
    if (abs >= 1e5 || abs < 1e-3) return v.toExponential(3);
    return v.toFixed(digits);
  }

  function renderTable(container, tbl) {
    const html = ['<table><thead><tr>'];
    for (const h of tbl.headers) html.push('<th>' + h + '</th>');
    html.push('</tr></thead><tbody>');
    for (const row of tbl.rows) {
      html.push('<tr>');
      for (const c of row) html.push('<td>' + (typeof c === 'number' ? fmt(c) : c) + '</td>');
      html.push('</tr>');
    }
    html.push('</tbody></table>');
    container.innerHTML = html.join('');
  }

  function renderKPIs(kpi, labels, sel) {
    const wd = kpi.worst_disp;
    const residual = kpi.residual;
    const okCls = Math.abs(residual) < 1e-3 ? 'ok' : '';
    caseInfo.textContent = sel.id + ' \u2014 ' + sel.name +
      '\nCategory: ' + sel.meta.category +
      '\n' + (sel.meta.description || '');
    kpiDiv.innerHTML =
      '<div class="kpi"><div class="label">Active selection</div>' +
      '<div class="value" style="font-size:13px;font-weight:500">' + sel.name + '</div>' +
      '<div class="unit">' + kpi.n_loads + ' nodal / ' + kpi.n_thermal + ' thermal</div></div>' +
      '<div class="kpi"><div class="label">Total applied Fy</div>' +
      '<div class="value">' + fmt(kpi.total_fy_applied) +
      ' <span class="unit">' + labels.force + '</span></div></div>' +
      '<div class="kpi"><div class="label">Sum of reactions Fy</div>' +
      '<div class="value">' + fmt(kpi.total_fy_reaction) +
      ' <span class="unit">' + labels.force + '</span></div></div>' +
      '<div class="kpi ' + okCls + '"><div class="label">Equilibrium residual</div>' +
      '<div class="value">' + fmt(residual) +
      ' <span class="unit">' + labels.force + '</span></div>' +
      '<div class="unit">' + (Math.abs(residual) < 1e-3 ? '\u2713 balanced' : '\u26a0 check') + '</div></div>' +
      '<div class="kpi"><div class="label">Max |displacement|</div>' +
      '<div class="value">' + fmt(wd.mag) +
      ' <span class="unit">' + labels.length + '</span></div>' +
      '<div class="unit">at node N' + wd.node + '</div></div>';
  }

  function render3D(res) {
    const nodes = res.nodes;
    const nodeIds = Object.keys(nodes).map(Number).sort(function(a,b){return a-b;});
    const traces = [];

    const typeGroups = {column:[], roof_beam:[], tie_beam:[]};
    for (const m of res.members) {
      const a = nodes[m.i], b = nodes[m.j];
      typeGroups[m.type].push({x:[a[0],b[0]], y:[a[1],b[1]], z:[a[2],b[2]]});
    }
    for (const type of ['column','roof_beam','tie_beam']) {
      const group = typeGroups[type];
      if (!group.length) continue;
      const xs=[], ys=[], zs=[];
      for (const seg of group) {
        xs.push(seg.x[0], seg.x[1], null);
        ys.push(seg.y[0], seg.y[1], null);
        zs.push(seg.z[0], seg.z[1], null);
      }
      traces.push({type:'scatter3d', mode:'lines', name:TYPE_LABEL[type],
        x:xs, y:ys, z:zs, line:{color:COLOR[type], width:8}, hoverinfo:'name'});
    }

    traces.push({type:'scatter3d', mode:'markers+text', name:'Nodes',
      x:nodeIds.map(function(n){return nodes[n][0];}),
      y:nodeIds.map(function(n){return nodes[n][1];}),
      z:nodeIds.map(function(n){return nodes[n][2];}),
      marker:{color:'#ef4444', size:6, symbol:'circle', line:{color:'#fff', width:1}},
      text:nodeIds.map(function(n){return 'N'+n;}), textposition:'top center',
      textfont:{color:'#fca5a5', size:11}, hoverinfo:'text'});

    const supX=[], supY=[], supZ=[];
    for (const n of res.support_nodes) {
      const c = nodes[n]; supX.push(c[0]); supY.push(c[1]); supZ.push(c[2]);
    }
    traces.push({type:'scatter3d', mode:'markers', name:'Pinned Support',
      x:supX, y:supY, z:supZ,
      marker:{color:'#f59e0b', size:10, symbol:'diamond', line:{color:'#000', width:1}},
      hoverinfo:'name'});

    if (res.diaphragms) {
      for (const dg of res.diaphragms) {
        const ring = [dg.master].concat(dg.slaves);
        const rx=[], ry=[], rz=[];
        for (const n of ring) { const c=nodes[n]; rx.push(c[0]); ry.push(c[1]); rz.push(c[2]); }
        rx.push(rx[0]); ry.push(ry[0]); rz.push(rz[0]);
        traces.push({type:'scatter3d', mode:'lines', name:'Diaphragm (D1)',
          x:rx, y:ry, z:rz,
          line:{color:'#ec4899', width:3, dash:'dash'}, hoverinfo:'name'});
      }
    }

    const la = res.load_arrows;
    const laIds = Object.keys(la).map(Number);
    if (laIds.length) {
      let maxMag = 0;
      for (const n of laIds) {
        const v = la[n]; maxMag = Math.max(maxMag, Math.hypot(v[0], v[1], v[2]));
      }
      if (maxMag > 0) {
        const arrowLen = 1.6;
        const lx=[], ly=[], lz=[];
        for (const n of laIds) {
          const v = la[n];
          const mag = Math.hypot(v[0], v[1], v[2]);
          if (mag < 1e-9) continue;
          const s = arrowLen / maxMag;
          const c = nodes[n];
          const dx = v[0]*s, dy = v[1]*s, dz = v[2]*s;
          lx.push(c[0]-dx, c[0], null);
          ly.push(c[1]-dy, c[1], null);
          lz.push(c[2]-dz, c[2], null);
        }
        traces.push({type:'scatter3d', mode:'lines', name:'Applied Load (resultant)',
          x:lx, y:ly, z:lz, line:{color:'#e11d48', width:5}, hoverinfo:'name'});
      }
    }

    const origin = [-1.5, -1.5, -0.5];
    const gLen = 2.0;
    const axisDefs = [
      [[gLen,0,0], 'X (global)', '#f87171'],
      [[0,gLen,0], 'Y (global) - vertical', '#4ade80'],
      [[0,0,gLen], 'Z (global)', '#60a5fa'],
    ];
    for (const ad of axisDefs) {
      const vec = ad[0], label = ad[1], color = ad[2];
      traces.push({type:'scatter3d', mode:'lines+text', name:label,
        x:[origin[0], origin[0]+vec[0]],
        y:[origin[1], origin[1]+vec[1]],
        z:[origin[2], origin[2]+vec[2]],
        line:{color:color, width:4}, text:['', label], textposition:'top center',
        textfont:{color:color, size:11}, hoverinfo:'name'});
    }

    const layout = {
      margin:{l:0,r:0,t:30,b:0},
      paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
      font:{color:'#e2e8f0', size:11},
      scene:{
        xaxis:{title:'X ('+res.labels.length+')', gridcolor:'#2a3654', zerolinecolor:'#3d4d70', color:'#94a3b8'},
        yaxis:{title:'Y ('+res.labels.length+') - Vertical', gridcolor:'#2a3654', zerolinecolor:'#3d4d70', color:'#94a3b8'},
        zaxis:{title:'Z ('+res.labels.length+')', gridcolor:'#2a3654', zerolinecolor:'#3d4d70', color:'#94a3b8'},
        aspectmode:'cube', bgcolor:'rgba(0,0,0,0)',
        camera:{eye:{x:1.6, y:1.3, z:1.1}}
      },
      legend:{x:0, y:1, bgcolor:'rgba(18,27,46,0.85)',
              bordercolor:'#2a3654', borderwidth:1,
              font:{size:10, color:'#e2e8f0'}},
      showlegend:true
    };
    Plotly.react('plot', traces, layout, {responsive:true, displaylogo:false});
  }

  async function runSolve() {
    if (!pyodide) return;
    runBtn.disabled = true;
    setStatus('Solving\u2026');
    try {
      const cfg = collectConfig();
      const t0 = performance.now();
      const raw = pyodide.runPython('api_solve(' + JSON.stringify(JSON.stringify(cfg)) + ')');
      const dt = (performance.now() - t0).toFixed(1);
      const res = JSON.parse(raw);
      lastResult = res;
      renderKPIs(res.kpi, res.labels, res.selected);
      renderTable(document.getElementById('tbl-disp'),   res.tables.displacements);
      renderTable(document.getElementById('tbl-react'),  res.tables.reactions);
      renderTable(document.getElementById('tbl-forces'), res.tables.member_forces);
      renderTable(document.getElementById('tbl-members'),res.tables.members);
      render3D(res);
      setStatus('Solved in ' + dt + ' ms. Residual = ' + res.kpi.residual.toExponential(2), 'ok');
      dlBtn.disabled = false;
    } catch (e) {
      const msg = (e && e.message) ? e.message : String(e);
      const lastLine = msg.split('\n').filter(Boolean).pop();
      setStatus('Solver error: ' + lastLine, 'err');
      console.error(e);
    } finally {
      runBtn.disabled = false;
    }
  }

  runBtn.addEventListener('click', runSolve);

  dlBtn.addEventListener('click', function() {
    if (!lastResult) return;
    const tables = lastResult.tables;
    const sections = [
      ['Displacements', tables.displacements],
      ['Reactions',     tables.reactions],
      ['Member End Forces', tables.member_forces],
      ['Members',       tables.members],
    ];
    const lines = [];
    for (const s of sections) {
      lines.push('### ' + s[0]);
      lines.push(s[1].headers.join(','));
      for (const row of s[1].rows) {
        lines.push(row.map(function(c) {
          return typeof c === 'number' ? c.toPrecision(10) : '"' + c + '"';
        }).join(','));
      }
      lines.push('');
    }
    const blob = new Blob([lines.join('\n')], {type:'text/csv'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'revit4_results.csv';
    a.click();
  });

  boot();
})();
</script>
</body>
</html>
'''


class SolverRequestHandler(http.server.BaseHTTPRequestHandler):
    server_version = "Revit4Solver/4.0"

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path in ('/', '/index.html', '/revit4_solver.html'):
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
        sys.stderr.write("[revit4] %s - %s\n" % (self.address_string(), fmt % args))


def find_free_port(host, start_port, max_tries=20):
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found in range %d-%d." %
                       (start_port, start_port + max_tries - 1))


def run_verify():
    """Headless validation: extract embedded Python and run api_validate."""
    import re
    import json as _json
    m = re.search(r'<script type="text/x-python"[^>]*>(.*?)</script>', HTML, re.DOTALL)
    if not m:
        print("ERROR: could not extract embedded Python source.")
        sys.exit(1)
    ns = {}
    exec(compile(m.group(1), "<embedded>", "exec"), ns)
    validate = ns['api_validate']
    solve_fn = ns['api_solve']

    print("=" * 78)
    print("  Rev 4 -- Headless Validation")
    print("=" * 78)
    print()
    rows = _json.loads(validate('{}'))
    print("%-5s %-26s %-11s %11s %11s %11s %10s" % (
        "id", "name", "category", "SumFx(kN)", "SumFy(kN)", "SumFz(kN)", "N_thermal"))
    print("-" * 78)
    for r in rows:
        print("%-5s %-26s %-11s %11.3f %11.3f %11.3f %10d" % (
            r['id'], r['name'][:26], r['category'][:11],
            r['total_Fx']/1e3, r['total_Fy']/1e3, r['total_Fz']/1e3, r['n_thermal']))
    print()
    for label, sel in [('LC1 (self-weight)', 'LC1'),
                       ('LC2 (5 kN/m roof dead)', 'LC2'),
                       ('LC9 (thermal +15 C)', 'LC9'),
                       ('C02 (1.2D + 1.6L)', 'C02')]:
        res = _json.loads(solve_fn(_json.dumps({'unit': 'metric', 'selected': sel})))
        print("-- Solve %s --" % label)
        print("   total_Fy_applied  = %.4f kN" % res['kpi']['total_fy_applied'])
        print("   total_Fy_reaction = %.4f kN" % res['kpi']['total_fy_reaction'])
        print("   residual          = %.4e kN" % res['kpi']['residual'])
        print("   worst |u|         = %.4e m at N%d" % (
            res['kpi']['worst_disp']['mag'], res['kpi']['worst_disp']['node']))
    print()
    print("-- Custom load smoke test (10 kN at N6, no self-weight) --")
    cfg = {'unit': 'metric', 'selected': 'CUSTOM',
           'custom_loads': {
               'self_weight': False,
               'nodal': [{'node': 6, 'Fx': 10}],
               'distributed': [], 'point': [], 'temperature': []}}
    res = _json.loads(solve_fn(_json.dumps(cfg)))
    print("   total_Fy_applied  = %.4f kN" % res['kpi']['total_fy_applied'])
    print("   worst |u|         = %.4e m at N%d" % (
        res['kpi']['worst_disp']['mag'], res['kpi']['worst_disp']['node']))
    print()
    print("=" * 78)
    print("  Validation complete.  Launch web app with:  python Rev4.py")
    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(description="Serve the Rev 4 Solver web app.")
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--no-auto-port', action='store_true')
    parser.add_argument('--verify', action='store_true',
                        help="Run headless validation, print results, exit.")
    args = parser.parse_args()

    if args.verify:
        run_verify()
        return

    if args.no_auto_port:
        port = args.port
    else:
        port = find_free_port(args.host, args.port)

    url = "http://%s:%d/" % (args.host, port)

    with http.server.ThreadingHTTPServer((args.host, port), SolverRequestHandler) as httpd:
        print("=" * 70)
        print("  Revit 4 Solver")
        print("=" * 70)
        print("  Serving at:   %s" % url)
        print("  Health check: %shealth" % url)
        print("  Stop with:    Ctrl+C")
        print("=" * 70)
        if args.host == '0.0.0.0':
            print("  Note: bound to all interfaces.")
            print("=" * 70)
        if not args.no_browser:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[revit4] Shutting down.")
            httpd.shutdown()


if __name__ == '__main__':
    main()