"""
Road-tunnel FDS input-deck calculator.

Python port of the "Road Tunnel FDS (Longitudinal / Transverse) Calculator"
(originally a single-file HTML/JavaScript tool).  All Korean text has been
translated to English.  This module is pure logic (no Qt) so it can be unit
tested and reused by the FDS tab UI.

Two modes:
  * "long"  - Longitudinal ventilation (general tunnels: 20 / 30 / 100 MW)
  * "trans" - Transverse ventilation; sub-mode "small" = small-car-only
              tunnels (5 / 10 / 15 / 20 MW) with a ceiling exhaust-duct array.

The main entry points are:
    compute_model(params)            -> TunnelModel
    duct_model(model, duct_params)   -> DuctModel        (transverse only)
    build_fds(model, cfg)            -> str  (a complete .fds deck)
    cfg_for_scenario(...)            -> dict (one matrix cell)
    generate_matrix(...)             -> writes the MW x traffic x scenario tree
"""

from __future__ import annotations

import math
import os
import re

# ----------------------------------------------------------------------------
# Constants  (translated 1:1 from the original tool)
# ----------------------------------------------------------------------------

# Fire-growth ramp: (time s, fraction of peak HRR).  t2 growth to 448 s.
FIRE_RAMP = [
    [10, 0.0005], [20, 0.002], [30, 0.0045], [40, 0.008], [50, 0.0125],
    [60, 0.0179], [70, 0.0244], [80, 0.0319], [90, 0.0404], [100, 0.0498],
    [110, 0.0603], [120, 0.0717], [130, 0.0842], [140, 0.0977], [150, 0.1121],
    [160, 0.1276], [170, 0.144], [180, 0.1614], [190, 0.1799], [200, 0.1993],
    [210, 0.2197], [220, 0.2412], [230, 0.2636], [240, 0.287], [250, 0.3114],
    [260, 0.3368], [270, 0.3632], [280, 0.3906], [290, 0.419], [300, 0.4484],
    [310, 0.4788], [320, 0.5102], [330, 0.5426], [340, 0.576], [350, 0.6104],
    [360, 0.6457], [370, 0.6821], [380, 0.7195], [390, 0.7578], [400, 0.7972],
    [410, 0.8376], [420, 0.8789], [430, 0.9213], [440, 0.9646], [448, 1],
]

# Default longitudinal velocity-ramp profile (time s, velocity m/s).
VR_PROFILE = [
    [0, 0.16], [20, 0.15], [40, 0.13], [60, 0.11], [80, 0.09], [100, 0.07],
    [120, 0.04], [140, 0.01], [160, -0.02], [180, -0.05], [200, -0.08],
    [220, -0.11], [240, -0.14], [260, -0.17], [280, -0.2], [300, -0.24],
    [320, -0.28], [340, -0.33], [360, -0.4], [380, -0.48], [400, -0.56],
    [420, -0.66], [440, -0.78], [460, -0.91], [480, -1.05], [500, -1.19],
    [520, -1.34], [540, -1.47], [560, -1.53], [580, -1.53], [600, -1.5],
    [620, -1.46], [640, -1.42], [660, -1.39], [680, -1.37], [700, -1.37],
    [720, -1.37], [740, -1.37], [760, -1.38], [780, -1.4], [800, -1.43],
    [820, -1.45], [840, -1.46], [860, -1.44], [880, -1.43], [900, -1.42],
]

# General-tunnel presets, keyed by MW:  [HRRPUA, half-length, burner z,
#                                        offset1, offset2]
PRESETS = {
    "20": [533.333, 3.75, 2.5, 1, 1],
    "30": [923.077, 3.75, 2.5, 1, 1],
    "100": [900.901, 9.25, 3, 1, 1.5],
}

# Small-car-only (transverse): HRRPUA per MW; fire geometry fixed
# (1000 m reference tunnel, fire centred at 500 m).
SMALLCAR_HRR = {"5": 400.06, "10": 800.06, "15": 1200.06, "20": 1600.06}
# VENT/OBST XB = Lh-2.17, Lh+2.17, 4.98415, 6.66415, 0, 1.44
SMALL_GEOM = {"hl": 2.17, "y1": 4.98415, "y2": 6.66415, "z2": 1.44}

# Ventilation scenarios produced by the matrix.
SCENARIOS = ["FV0", "FVM", "FVP", "NV0", "NVM", "NVP"]
# Traffic conditions:  key, folder name, label.
TRAFFIC = [
    {"key": "C", "dir": "cong", "label": "Congested"},
    {"key": "N", "dir": "norm", "label": "Normal"},
]

# Fixed natural-ventilation ramps (fan operation).
NVM_RAMP = [[0, -2.50], [1200, -2.50]]   # XMAX RIGHT_PORTAL
NVP_RAMP = [[0, 2.50], [1200, 2.50]]     # XMIN LEFT_PORTAL

# Default wall (OBST) cells of the cross-section, as [y0, y1, z0, z1] in cells.
DEFAULT_CELLS = [
    [0, 2, 0, 1], [0, 1, 0, 1], [0, 1, 7, 9], [0, 2, 9, 11],
    [0, 3, 11, 12], [0, 4, 12, 13], [0, 5, 13, 14], [0, 8, 14, 15],
]


# ----------------------------------------------------------------------------
# Small numeric / string helpers
# ----------------------------------------------------------------------------

def fmt(x) -> str:
    """Format like the original tool: integers without a decimal, otherwise up
    to four significant decimals, snapping tiny values to 0."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        x = 0.0
    if not math.isfinite(x):
        x = 0.0
    if abs(x) < 1e-9:
        x = 0.0
    if round(x * 1e6) / 1e6 == round(x):
        return str(int(round(x)))
    return str(round(x * 1e4) / 1e4)


def mw3(mw) -> str:
    """Three-digit zero-padded MW code, e.g. 5 -> '005', 100 -> '100'."""
    return str(int(mw)).zfill(3)


def safe_name(s) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "_", str(s))


def safe_file(s) -> str:
    return re.sub(r"\s+", "_", re.sub(r'[\\/:*?"<>|]+', "_", str(s))).strip()


def is_small(mode: str, submode: str) -> bool:
    return mode == "trans" and submode == "small"


def current_mw_set(mode: str, submode: str):
    return [5, 10, 15, 20] if is_small(mode, submode) else [20, 30, 100]


def preset_for(mw, mode: str, submode: str) -> dict:
    """Geometry / HRR preset for a given MW and mode."""
    if is_small(mode, submode):
        h = SMALLCAR_HRR.get(str(int(mw)), SMALLCAR_HRR["5"])
        return {"small_car": True, "hrr": h, "hl": SMALL_GEOM["hl"],
                "y1": SMALL_GEOM["y1"], "y2": SMALL_GEOM["y2"],
                "bz": SMALL_GEOM["z2"]}
    p = PRESETS.get(str(int(mw)), PRESETS["20"])
    return {"small_car": False, "hrr": p[0], "hl": p[1], "bz": p[2],
            "o1": p[3], "o2": p[4]}


# ----------------------------------------------------------------------------
# Tunnel model (cross-section + grid)
# ----------------------------------------------------------------------------

def compute_model(params: dict) -> dict:
    """Build the geometry/grid model from raw inputs.

    params keys: W, H, nW, nH, Lh, dxLen, breath, left, right, symmetric.
      left / right : list of up to 30 wall cells, each [y0, y1, z0, z1] (cells)
      symmetric    : if True, mirror the left wall cells onto the right.
    """
    W = float(params.get("W", 10.86))
    H = float(params.get("H", 6.73))
    nW = max(1, int(round(params.get("nW", 20))))
    nH = max(1, int(round(params.get("nH", 15))))
    Lh = float(params.get("Lh", 720))
    Lfull = Lh * 2
    dxLen = float(params.get("dxLen", 1)) or 1
    nLen = max(1, int(round(Lfull / dxLen)))
    cW, cH = W / nW, H / nH

    left = [list(map(lambda v: int(round(v or 0)), c[:4]))
            for c in (params.get("left") or [])]
    right = [list(map(lambda v: int(round(v or 0)), c[:4]))
             for c in (params.get("right") or [])]
    if params.get("symmetric", True):
        right = [[nW - c[1], nW - c[0], c[2], c[3]] for c in left]

    breath = float(params.get("breath", 1.8)) or 1.8
    k_breath = max(0, round(breath / cH)) if cH > 0 else 0
    breath_snap = k_breath * cH if cH > 0 else breath
    return {"W": W, "H": H, "nW": nW, "nH": nH, "Lh": Lh, "Lfull": Lfull,
            "dxLen": dxLen, "nLen": nLen, "cW": cW, "cH": cH, "breath": breath,
            "kBreath": k_breath, "breathSnap": breath_snap,
            "left": left, "right": right}


def clear_area(m: dict) -> dict:
    """Clear (ventilated) cross-section area = grid area minus wall (OBST)
    cells."""
    nW, nH = m["nW"], m["nH"]
    if not (nW > 0 and nH > 0):
        return {"clear": m["W"] * m["H"], "gross": m["W"] * m["H"], "wall": 0}
    grid = bytearray(nW * nH)

    def mark(arr):
        for c in arr:
            if c[0] == c[1] or c[2] == c[3]:
                continue
            y0, y1 = max(0, min(nW, int(c[0]))), max(0, min(nW, int(c[1])))
            z0, z1 = max(0, min(nH, int(c[2]))), max(0, min(nH, int(c[3])))
            for z in range(z0, z1):
                for y in range(y0, y1):
                    grid[z * nW + y] = 1

    mark(m["left"])
    mark(m["right"])
    wall = sum(grid)
    cell = m["cW"] * m["cH"]
    gross = nW * nH * cell
    return {"clear": (nW * nH - wall) * cell, "gross": gross,
            "wall": wall * cell}


# ----------------------------------------------------------------------------
# Transverse exhaust-duct geometry
# ----------------------------------------------------------------------------

def duct_model(m: dict, duct: dict) -> dict:
    """Ceiling exhaust-duct (damper) lattice for transverse ventilation.

    duct keys: rows, lx (damper width, travel dir), wy (damper length, width
    dir), pitch, win (active range about the fire +/-), offset, flow (total
    exhaust m3/s).
    """
    rows = max(1, min(3, int(round(duct.get("rows", 1) or 1))))
    lx = max(0.1, float(duct.get("lx", 2) or 2))
    wy = max(0.1, float(duct.get("wy", 4) or 4))
    pitch = max(lx, float(duct.get("pitch", 52) or 52))
    win = max(0, float(duct.get("win", 250) or 250))
    offset = float(duct.get("offset", 0) or 0)
    flow = float(duct.get("flow", 0) or 0)
    fire = m["Lh"]                       # fire-vehicle centre X
    cols = [m["W"] * (2 * k - 1) / (2 * rows) for k in range(1, rows + 1)]

    half = lx / 2
    lo, hi, base = half, m["Lfull"] - half, fire + offset
    cx = []
    i = math.ceil((lo - base) / pitch)
    while base + i * pitch <= hi + 1e-6:
        c = base + i * pitch
        if c >= lo - 1e-6:
            cx.append(c)
        i += 1
    cx.sort()

    active_set = set()
    for i, c in enumerate(cx):
        if abs(c - fire) <= win + 1e-6:
            active_set.add(i)
    area = lx * wy
    total_active = len(active_set) * rows
    vel = flow / total_active / area if total_active > 0 else 0
    return {"rows": rows, "lx": lx, "wy": wy, "pitch": pitch, "win": win,
            "offset": offset, "flow": flow, "cols": cols, "cx": cx,
            "activeSet": active_set, "area": area,
            "totalActive": total_active, "vel": vel}


# ----------------------------------------------------------------------------
# Deck fragments
# ----------------------------------------------------------------------------

def obst_line(m: dict, c, tag: str) -> str:
    return ("&OBST XB= 0.0000, %s, %s, %s, %s, %s, COLOR='GRAY' / %s"
            % (fmt(m["Lfull"]), fmt(m["cW"] * c[0]), fmt(m["cW"] * c[1]),
               fmt(m["cH"] * c[2]), fmt(m["cH"] * c[3]), tag))


def decide_case(data) -> str:
    """First non-zero velocity sign decides the case: positive -> '3',
    negative -> '4'."""
    for p in data:
        if abs(p[1]) > 1e-9:
            return "3" if p[1] > 0 else "4"
    return "3"


def duct_block(m: dict, d: dict):
    """&VENT lines for the ceiling exhaust dampers."""
    out = [
        "/ Transverse exhaust duct (ceiling) - %d columns, pitch %sm, "
        "%d active (fire +/-%sm)" % (d["rows"], fmt(d["pitch"]),
                                     d["totalActive"], fmt(d["win"])),
        "/ Damper area = %s x %s = %s m2 (width w x length L)"
        % (fmt(d["lx"]), fmt(d["wy"]), fmt(d["area"])),
        "/ Total exhaust %s m3/s / %d active / area %s = damper velocity %s m/s"
        % (fmt(d["flow"]), d["totalActive"], fmt(d["area"]), fmt(d["vel"])),
        "&SURF ID='VENT_SURF', VEL=%s, COLOR='GREEN'/ , PART_ID='smoke' /"
        % fmt(d["vel"]),
        "",
    ]
    for k, yc in enumerate(d["cols"]):
        y1, y2 = yc - d["wy"] / 2, yc + d["wy"] / 2
        for i, c in enumerate(d["cx"]):
            cm = "" if i in d["activeSet"] else "/"
            x1, x2 = c - d["lx"] / 2, c + d["lx"] / 2
            tag = "EXH%d-%s" % (k + 1, str(i + 1).zfill(2))
            out.append("%s&VENT XB= %s, %s, %s, %s, %s, %s, "
                       "SURF_ID='VENT_SURF'/ %s"
                       % (cm, fmt(x1), fmt(x2), fmt(y1), fmt(y2),
                          fmt(m["H"]), fmt(m["H"]), tag))
        out.append("")
    return out


# ----------------------------------------------------------------------------
# Full deck
# ----------------------------------------------------------------------------

def build_fds(m: dict, cfg: dict) -> str:
    """Return a complete FDS input deck (string) for one configuration.

    cfg keys: title, small_car, hrr, hl, bz, (o1,o2 | y1,y2), profile|None,
              scenario, bc, twfin, v0, breath, sign, duct(optional).
    """
    T = cfg.get("twfin") or 1200
    hrr, hl, bz = cfg["hrr"], cfg["hl"], cfg["bz"]
    o1, o2 = cfg.get("o1"), cfg.get("o2")
    v0 = cfg.get("v0")
    sg = cfg.get("sign") or 1
    prof = ([[t, v * sg] for t, v in cfg["profile"]]
            if cfg.get("profile") else None)

    # fire-vehicle coordinates
    fx1, fx2 = m["Lh"] - hl, m["Lh"] + hl
    if cfg.get("small_car"):
        fy1, fy2 = cfg["y1"], cfg["y2"]
        pby = (cfg["y1"] + cfg["y2"]) / 2
    else:
        fy1, fy2 = m["W"] / 2 - o1, m["W"] / 2 + o2
        pby = m["W"] / 2
    pbz = (max(0, round((cfg.get("breath") or 1.8) / m["cH"])) * m["cH"]
           if m["cH"] > 0 else (cfg.get("breath") or 1.8))

    # scenario -> inlet boundary condition
    sc = cfg.get("scenario")
    ramp_data = None
    vel3, vel4 = "-1.00", "1.00"
    no_v0 = False
    sc_label = ""
    if sc == "NV0":
        bc = "1"
        no_v0 = True
        sc_label = "NV0 - fan operation - both portals OPEN"
    elif sc == "NVM":
        bc = "4"
        ramp_data = NVM_RAMP
        vel4 = "1.00"
        sc_label = "NVM - fan operation - RIGHT_PORTAL Vr=-2.50"
    elif sc == "NVP":
        bc = "3"
        ramp_data = NVP_RAMP
        vel3 = "-1.00"
        sc_label = "NVP - fan operation - LEFT_PORTAL Vr=+2.50"
    elif prof:
        bc = decide_case(prof)
        ramp_data = prof
        vel3, vel4 = "1.00", "1.00"
        sc_label = (((cfg["title"] + " - ") if sc == "FV" else "")
                    + "fan failure (VRR) - CASE" + bc)
    else:
        bc = cfg.get("bc")
        ramp_data = VR_PROFILE
        vel3, vel4 = "-1.00", "1.00"

    def cm(case):
        return "" if case == bc else "/"

    L = []
    L += ["&HEAD CHID='%s', TITLE='%s' /" % (safe_name(cfg["title"]),
                                             cfg["title"]), ""]
    L += ["&MESH IJK=%d,%d,%d,XB=0.000,%s,0.0000,%s,0.0000,%s,"
          "SYNCHRONIZE=.TRUE./" % (m["nLen"], m["nW"], m["nH"],
                                   fmt(m["Lfull"]), fmt(m["W"]), fmt(m["H"])),
          ""]
    L += ["&TIME TWFIN = %.1f/" % T, ""]
    L += ["&MISC TMPA= 20.0, GVEC=1.0, 0.0, 1.0, RAMP_GX='X GRADE', "
          "RAMP_GZ='Z GRADE' /"]
    L += ["&RAMP ID='X GRADE', X=    0.0, F=0.0/",
          "&RAMP ID='X GRADE', X= %s, F=0.0 /" % fmt(m["Lfull"])]
    L += ["&RAMP ID='Z GRADE', X=0.0, F=-9.81/",
          "&RAMP ID='Z GRADE', X=%s, F=-9.81/" % fmt(m["Lfull"]), ""]
    L += ["&REAC ID='FIRE', SOOT_YIELD=0.133, CO_YIELD=0.168, "
          "MASS_EXTINCTION_COEFFICIENT=8700. /"]
    L += ["&RADI RADIATIVE_FRACTION = 0.3/", ""]
    L += ["/**********TUNNELBLOCK**********/"]
    for i, c in enumerate(m["left"]):
        if c[0] != c[1] and c[2] != c[3]:
            L.append(obst_line(m, c, "*L%d" % (i + 1)))
    for i, c in enumerate(m["right"]):
        if c[0] != c[1] and c[2] != c[3]:
            L.append(obst_line(m, c, "*R%d" % (i + 1)))
    L.append("")
    L.append("&SURF ID='BURNER1', HRRPUA=%s, RAMP_Q='Fire_Ramp', "
             "COLOR='RASPBERRY'/, PART_ID='smoke' /" % fmt(hrr))
    L.append("&SURF ID='BURNER2', HRRPUA=%s, RAMP_Q='Fire_Ramp', "
             "COLOR='RASPBERRY'/, PART_ID='smoke' /" % fmt(hrr))
    L.append("")

    def fY(x):
        # small-car Y coordinates keep 5 decimals
        return (str(round(x * 1e5) / 1e5) if cfg.get("small_car") else fmt(x))

    L.append("&VENT XB= %s, %s, %s, %s, 0.0, %s, SURF_ID='BURNER1'/ fire"
             % (fmt(fx1), fmt(fx2), fY(fy1), fY(fy1), fmt(bz)))
    L.append("&VENT XB= %s, %s, %s, %s, 0.0, %s, SURF_ID='BURNER2'/ fire"
             % (fmt(fx1), fmt(fx2), fY(fy2), fY(fy2), fmt(bz)))
    L.append("&OBST XB= %s, %s, %s, %s, 0.0, %s, COLOR='FIREBRICK'/ fire car"
             % (fmt(fx1), fmt(fx2), fY(fy1), fY(fy2), fmt(bz)))
    L.append("")
    if cfg.get("duct"):
        L += duct_block(m, cfg["duct"])

    L.append("/ Fire-intensity RAMP (Fire_Ramp)")
    full = [list(p) for p in FIRE_RAMP]
    for t in range(458, 1509, 10):
        full.append([t, 1])
    full.append([1800, 1])
    for t, f in full:
        L.append("&RAMP ID='Fire_Ramp',T=%s,F=%s/"
                 % (("%.1f" % t).rjust(7), ("%.4f" % f).rjust(7)))
    L.append("")

    L.append("///Tunnel Inlet Definition%s"
             % (("  (%s)" % sc_label) if sc_label else ""))
    L.append("//CASE 1 ***** initial velocity + OPEN BC *****")
    if not no_v0:
        L.append("%s&MISC V0 = %s " % (cm("1"), fmt(v0)))
    L.append("%s&VENT MB='XMAX', SURF_ID='OPEN'/ RIGHT" % cm("1"))
    L.append("%s&VENT MB='XMIN', SURF_ID='OPEN'/ LEFT" % cm("1"))
    L.append("")
    L.append("//CASE 2 ***** Pressure Dynamic BC *****")
    L.append("%s&VENT MB='YMAX', SURF_ID='OPEN'/ RIGHT" % cm("2"))
    L.append("%s&VENT MB='XMIN', SURF_ID='OPEN', DYNAMIC_PRESSURE=1.000, "
             "PRESSURE_RAMP='Wind'/ LEFT" % cm("2"))
    L.append("%s&RAMP ID='Wind',T=    0,   F= 116.64450 /" % cm("2"))
    L.append("%s&RAMP ID='Wind',T=  300,   F= 116.64450 /" % cm("2"))
    L.append("")
    L.append("//CASE 3 ***** Velocity Profile (Vr_Ramp) *****")
    L.append("%s&VENT MB='XMIN', SURF_ID='LEFT_PORTAL'/ LEFT" % cm("3"))
    L.append("%s&SURF ID='LEFT_PORTAL', VEL = %s, RGB=1,0,0, "
             "RAMP_V ='Vr_Ramp'/" % (cm("3"), vel3))
    L.append("%s&VENT MB='XMAX', SURF_ID='OPEN' /" % cm("3"))
    if bc == "3" and ramp_data:
        for t, v in ramp_data:
            L.append("&RAMP ID='Vr_Ramp', T= %s , F= %s/" % (fmt(t), fmt(v)))
    L.append("")
    L.append("//CASE 4 ***** Velocity Profile (-) *****")
    L.append("%s&VENT MB='XMIN', SURF_ID='OPEN' /" % cm("4"))
    L.append("%s&VENT MB='XMAX', SURF_ID='RIGHT_PORTAL'/ RIGHT" % cm("4"))
    L.append("%s&SURF ID='RIGHT_PORTAL', VEL = %s, RGB=1,0,0, "
             "RAMP_V ='Vr_Ramp'/" % (cm("4"), vel4))
    if bc == "4" and ramp_data:
        for t, v in ramp_data:
            L.append("&RAMP ID='Vr_Ramp', T= %s , F= %s/" % (fmt(t), fmt(v)))
    L.append("")
    L.append("///Tunnel Inlet Definition - END")
    L.append("")
    L.append("&DUMP DT_PL3D=30.0, DT_BNDF=30, DT_SLCF=30.0, "
             "PLOT3D_QUANTITY(2)='VELOCITY', "
             "PLOT3D_QUANTITY(3)='carbon monoxide', "
             "PLOT3D_QUANTITY(4)='carbon dioxide', "
             "PLOT3D_QUANTITY(5)='soot density', WRITE_XYZ=.TRUE./")
    L.append("")
    for i, q in enumerate(["soot density", "carbon dioxide",
                           "carbon monoxide", "TEMPERATURE",
                           "INTEGRATED INTENSITY", "oxygen"]):
        L.append("&SLCF PBZ = %s, QUANTITY='%s'/%s"
                 % (fmt(pbz), q, " breath level" if i == 0 else ""))
    L.append("")
    for i, q in enumerate(["soot density", "carbon dioxide",
                           "carbon monoxide", "TEMPERATURE",
                           "INTEGRATED INTENSITY"]):
        L.append("&SLCF PBY = %s, QUANTITY='%s'/%s"
                 % (fmt(pby), q, " tunnel center" if i == 0 else ""))
    L += ["", "&TAIL /"]
    return "\n".join(L)


# ----------------------------------------------------------------------------
# Configurations
# ----------------------------------------------------------------------------

def cfg_for_scenario(mw, traffic, scen, profile, ui, mode, submode) -> dict:
    """One matrix cell (MW x traffic x scenario)."""
    pre = preset_for(mw, mode, submode)
    cfg = dict(pre)
    cfg.update({
        "title": mw3(mw) + traffic["key"] + scen,
        "profile": None, "scenario": scen, "bc": "3",
        "twfin": ui.get("twfin", 1200), "v0": ui.get("v0", 6.02),
        "breath": ui.get("breath", 1.8), "sign": ui.get("sign", 1),
    })
    if scen.startswith("FV"):
        cfg["scenario"] = "FV"
        cfg["profile"] = profile or None
    return cfg


def cfg_manual(mw, ui, mode, submode) -> dict:
    """Single live-preview configuration."""
    pre = preset_for(mw, mode, submode)
    cfg = dict(pre)
    cfg.update({
        "title": mw3(mw) + "_preview", "profile": None, "scenario": "manual",
        "bc": str(ui.get("bc", "3")), "twfin": ui.get("twfin", 1200),
        "v0": ui.get("v0", 6.02), "breath": ui.get("breath", 1.8), "sign": 1,
    })
    return cfg


def fds_folder_path(title: str) -> str:
    """Folder path for a deck title, e.g. '020CFV0' -> '020/cong/FV0'."""
    t = str(title)
    m = re.match(r"^(020|030|100)", t)
    if not m:
        return "other"
    top = m.group(1)
    m2 = re.match(r"^(?:020|030|100)([CN])(FV0|FVM|FVP|NV0|NVC)", t, re.I)
    if m2:
        mid = "cong" if m2.group(1).upper() == "C" else "norm"
        return "%s/%s/%s" % (top, mid, m2.group(2).upper())
    return top


# ----------------------------------------------------------------------------
# Matrix generation -> writes the folder tree of .fds files
# ----------------------------------------------------------------------------

def generate_matrix(model: dict, ui: dict, out_dir: str, mode: str,
                    submode: str, duct: dict = None,
                    fv_profiles: dict = None) -> dict:
    """Write fds files for every MW x traffic x scenario combination under
    out_dir as {mw3}/{cong|norm}/{scenario}/{title}.fds.

    fv_profiles: optional {"<mw>|<C|N>|<scen>": [[t, v], ...]} velocity ramps
    for the FV (fan-failure) scenarios; combinations without a profile are
    skipped and reported in 'missing'.
    """
    fv_profiles = fv_profiles or {}
    mws = current_mw_set(mode, submode)
    written, missing = [], []
    for mw in mws:
        for tr in TRAFFIC:
            for scen in SCENARIOS:
                title = mw3(mw) + tr["key"] + scen
                folder = "%s/%s/%s" % (mw3(mw), tr["dir"], scen)
                profile = None
                if scen.startswith("FV"):
                    profile = fv_profiles.get("%s|%s|%s"
                                              % (mw, tr["key"], scen))
                    if not profile:
                        missing.append(title)
                        continue
                cfg = cfg_for_scenario(mw, tr, scen, profile, ui, mode,
                                       submode)
                if duct:
                    cfg["duct"] = duct
                path = os.path.join(out_dir, folder)
                os.makedirs(path, exist_ok=True)
                fpath = os.path.join(path, title + ".fds")
                with open(fpath, "w", encoding="utf-8") as fh:
                    fh.write(build_fds(model, cfg))
                written.append(fpath)
    return {"written": written, "missing": missing}


# ----------------------------------------------------------------------------
# VRR (velocity-ramp) file parsing  (for FV fan-failure scenarios)
# ----------------------------------------------------------------------------

def _is_num(v):
    return isinstance(v, (int, float)) and math.isfinite(v)


def _parse_text(text: str):
    rows = []
    for line in str(text).splitlines():
        cells = re.split(r"[\t,;]+|\s{2,}|\s+", line.strip())
        row = []
        for c in cells:
            c = c.strip()
            if c == "":
                continue
            try:
                row.append(float(c))
            except ValueError:
                row.append(c)
        if row:
            rows.append(row)
    return rows


def vrr_to_profile(text: str, dt: float = 20.0) -> dict:
    """Parse a velocity-ramp file into [[t, v], ...].  If a single numeric
    column is found, times are synthesised at the given dt."""
    aoa = _parse_text(text)
    rows = [r for r in aoa if any(_is_num(x) for x in r)]
    if not rows:
        return {"pairs": None, "single": False}
    maxc = max(len(r) for r in rows)
    num_cols = [c for c in range(maxc)
                if sum(1 for r in rows if c < len(r) and _is_num(r[c]))
                >= max(2, len(rows) * 0.5)]
    if len(num_cols) >= 2:
        tc, vc = num_cols[0], num_cols[1]
        pairs = [[r[tc], r[vc]] for r in rows
                 if tc < len(r) and vc < len(r)
                 and _is_num(r[tc]) and _is_num(r[vc])]
        return {"pairs": pairs, "single": False}
    if len(num_cols) == 1:
        vc = num_cols[0]
        pairs = [[i * dt, r[vc]] for i, r in enumerate(
            [r for r in rows if vc < len(r) and _is_num(r[vc])])]
        return {"pairs": pairs, "single": True}
    return {"pairs": None, "single": False}


# default UI values (match the original tool)
DEFAULT_UI = {"W": 10.86, "nW": 20, "H": 6.73, "nH": 15, "Lh": 720,
              "dxLen": 1, "breath": 1.8, "twfin": 1200, "v0": 6.02, "sign": 1,
              "bc": "3", "dRows": 1, "dLx": 2, "dWy": 4.15, "dPitch": 52,
              "dWin": 250, "dOffset": 0, "dFlow": 132.7}


# ----------------------------------------------------------------------------
# DXF cross-section import  (closed LWPOLYLINE / POLYLINE -> wall cells)
# ----------------------------------------------------------------------------

def dxf_bulge_arc(p0, p1, b, seg=24):
    dx, dy = p1["x"] - p0["x"], p1["y"] - p0["y"]
    chord = math.hypot(dx, dy)
    if chord < 1e-9:
        return [{"x": p0["x"], "y": p0["y"]}]
    ang = 4 * math.atan(b)
    R = chord / (2 * math.sin(ang / 2))
    mx, my = (p0["x"] + p1["x"]) / 2, (p0["y"] + p1["y"]) / 2
    h = R * math.cos(ang / 2)
    ux, uy = dx / chord, dy / chord
    nx, ny = -uy, ux
    cx, cy = mx + nx * h, my + ny * h
    rr = math.hypot(p0["x"] - cx, p0["y"] - cy)
    a0 = math.atan2(p0["y"] - cy, p0["x"] - cx)
    a1 = math.atan2(p1["y"] - cy, p1["x"] - cx)
    if b > 0:
        if a1 < a0:
            a1 += 2 * math.pi
    else:
        if a1 > a0:
            a1 -= 2 * math.pi
    return [{"x": cx + rr * math.cos(a0 + (a1 - a0) * k / seg),
             "y": cy + rr * math.sin(a0 + (a1 - a0) * k / seg)}
            for k in range(seg)]


def dxf_flatten(pl):
    v = pl["verts"]
    n = len(v)
    if n < 2:
        return []
    ring = []
    segs = n if pl["closed"] else n - 1
    for i in range(segs):
        p0, p1 = v[i], v[(i + 1) % n]
        if abs(p0.get("b", 0)) > 1e-9:
            ring.extend(dxf_bulge_arc(p0, p1, p0["b"], 24))
        else:
            ring.append({"x": p0["x"], "y": p0["y"]})
    if not pl["closed"]:
        ring.append({"x": v[n - 1]["x"], "y": v[n - 1]["y"]})
    return ring


def dxf_parse(text):
    """Return the largest closed polyline ring as
    {ring, x0, x1, y0, y1} or None."""
    lines = re.split(r"\r\n|\r|\n", text)
    pairs = []
    i = 0
    while i + 1 < len(lines):
        try:
            code = int(lines[i].strip())
            pairs.append((code, lines[i + 1]))
        except ValueError:
            pass
        i += 2
    section, expect_name = None, False
    cur = pending = None
    polys = []

    def flush():
        nonlocal cur, pending
        if cur:
            if pending and pending.get("x") is not None and \
                    pending.get("y") is not None:
                cur["verts"].append(pending)
            if len(cur["verts"]) >= 2:
                polys.append(cur)
        cur = pending = None

    for code, raw in pairs:
        val = (raw or "").strip()
        if code == 0:
            if val == "SECTION":
                flush(); expect_name = True; continue
            if val == "ENDSEC":
                flush(); section = None; continue
            if section != "ENTITIES":
                flush(); continue
            if val == "LWPOLYLINE":
                flush(); cur = {"verts": [], "closed": False, "kind": "lw",
                                "_x": None}
            elif val == "POLYLINE":
                flush(); cur = {"verts": [], "closed": False, "kind": "poly"}
            elif val == "VERTEX" and cur and cur["kind"] == "poly":
                if pending and pending.get("x") is not None:
                    cur["verts"].append(pending)
                pending = {"x": None, "y": None, "b": 0}
            elif val == "SEQEND":
                flush()
            else:
                flush()
            continue
        if code == 2 and expect_name:
            section = val; expect_name = False; continue
        if not cur:
            continue
        if cur["kind"] == "lw":
            if code == 10:
                cur["_x"] = float(val)
            elif code == 20:
                if cur["_x"] is not None:
                    cur["verts"].append({"x": cur["_x"], "y": float(val),
                                         "b": 0})
                    cur["_x"] = None
            elif code == 42:
                if cur["verts"]:
                    cur["verts"][-1]["b"] = float(val)
            elif code == 70:
                cur["closed"] = (int(val) & 1) == 1
        else:
            if code == 70:
                cur["closed"] = (int(val) & 1) == 1
            elif pending is not None:
                if code == 10:
                    pending["x"] = float(val)
                elif code == 20:
                    pending["y"] = float(val)
                elif code == 42:
                    pending["b"] = float(val)
    flush()
    best, best_area = None, -1
    for pl in polys:
        ring = dxf_flatten(pl)
        if len(ring) < 3:
            continue
        xs = [p["x"] for p in ring]
        ys = [p["y"] for p in ring]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area > best_area:
            best_area = area
            best = {"ring": ring, "x0": min(xs), "x1": max(xs),
                    "y0": min(ys), "y1": max(ys)}
    return best


def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]["x"], poly[i]["y"]
        xj, yj = poly[j]["x"], poly[j]["y"]
        if ((yi > y) != (yj > y)) and \
                (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def merge_bands(arr, nH):
    bands, j = [], 0
    while j < nH:
        nL, k = arr[j], j
        while k + 1 < nH and arr[k + 1] == nL:
            k += 1
        if nL > 0:
            bands.append([nL, j, k + 1])
        j = k + 1
    return bands


def apply_dxf_bands(poly, W, H, nW, nH):
    """From an imported DXF polygon (origin-shifted to 0,0), return
    (left_cells, right_cells, symmetric) wall-cell rows for the grid."""
    cW, cH = W / nW, H / nH
    Lc, Rc = [], []
    for j in range(nH):
        first = last = -1
        for i in range(nW):
            if point_in_poly((i + 0.5) * cW, (j + 0.5) * cH, poly):
                if first < 0:
                    first = i
                last = i
        Lc.append(nW if first < 0 else first)
        Rc.append(nW if first < 0 else (nW - 1 - last))
    sym = all(Lc[i] == Rc[i] for i in range(nH))
    left = [[0, b[0], b[1], b[2]] for b in merge_bands(Lc, nH)]
    right = []
    if not sym:
        right = [[nW - b[0], nW, b[1], b[2]] for b in merge_bands(Rc, nH)]
    return left, right, sym


def load_dxf_section(text, nW, nH):
    """Parse DXF text and return {W, H, poly, left, right, symmetric} or None.
    poly coordinates are origin-shifted to (0,0)."""
    best = dxf_parse(text)
    if not best:
        return None
    W = best["x1"] - best["x0"]
    H = best["y1"] - best["y0"]
    poly = [{"x": p["x"] - best["x0"], "y": p["y"] - best["y0"]}
            for p in best["ring"]]
    left, right, sym = apply_dxf_bands(poly, W, H, nW, nH)
    return {"W": round(W * 1e4) / 1e4, "H": round(H * 1e4) / 1e4,
            "poly": poly, "left": left, "right": right, "symmetric": sym}