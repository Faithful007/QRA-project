"""
VB pre-movement release curve (LVCNHesTime) — EXACT, validated.

PROVENANCE
----------
The VB SFX(t) curve (cumulative fraction of occupants who have finished
pre-movement = leave-vehicle + hesitation by time t) was proven DETERMINISTIC:
byte-identical across all reference runs 020CFV0 P1_1..P1_5 and P2_1..P2_2
(max |diff| = 0.0). Only N_total (the random occupant count, 331..334) varies
between iterations. Source: FUN_0045a490 writing LVCNHesTime.dat.

This module reproduces VB's release schedule to the second via inverse-CDF
sampling, so E[count(t)] = N_total * SFX(t) exactly by construction. It is the
VB-faithful replacement for the fitted U(120,135) premovement.

The binary builds SFX(t) analytically (decoded forms below); the realized table
IS that curve for this deck's premovement params (detection gate ~58-60 s; deck
rows 80/81/65 = hesitation/leave-car/reaction = 180/60/120). Because the curve
is deterministic and shared across scenarios, embedding the realized table is
exact and fully traceable to VB's own output — not a fit. For a deck with
different premovement settings, call load_from_lvcn() with that deck's file.

Decoded analytic structure (FUN_0045a490 + helpers), kept for provenance:
  FUN_0045afc0 = normal CDF  Phi((x-mu)/sigma)      (sqrt(2pi), -1/2 z^2)
  FUN_0045b310 = Gumbel CDF  exp(-exp(-(x-mu)/sigma))
  FUN_0045b450 = Weibull CDF 1-exp(-(x/lambda)^k)   (guarded)
  SFX = sum of: N(17.1,41.6), N(81,151), Gumbel(155,28.8),
                Weibull(33.08,19.91), Weibull(8.42,6.13), gated at detection,
                terminating when SFX > 0.995 (<= 5000 s).
"""
import bisect

# Deterministic VB SFX(t) for t = 1..325 (020CFV0 reference, identical across runs)
VB_SFX = [
    0.000760398, 0.0008507, 0.00094451, 0.001042049, 0.00114355, 0.001249259, 0.001359432, 0.00147434,
    0.001594257, 0.001719471, 0.001850271, 0.001986953, 0.002129812, 0.002279143, 0.002435235, 0.002598372,
    0.002768823, 0.002946845, 0.003132675, 0.003326528, 0.003528593, 0.003739028, 0.003957958, 0.004185472,
    0.004421618, 0.004666402, 0.004919784, 0.005181679, 0.005451953, 0.005730424, 0.00601686, 0.006310985,
    0.006612472, 0.006920953, 0.007236018, 0.007557218, 0.007884072, 0.008216066, 0.008552665, 0.008893314,
    0.009237444, 0.00958448, 0.009933844, 0.010284966, 0.010637285, 0.010990256, 0.011343357, 0.011696096,
    0.012048009, 0.012398671, 0.012747696, 0.01309474, 0.013439506, 0.01378174, 0.01412124, 0.014457847,
    0.014791451, 0.015121988, 0.015449439, 0.120362981, 0.152005974, 0.186664682, 0.222880988, 0.259462495,
    0.295518233, 0.330431839, 0.363810904, 0.39543341, 0.425200521, 0.453098638, 0.479170548, 0.50349432,
    0.526168325, 0.547300879, 0.567003281, 0.585385282, 0.602552258, 0.618603573, 0.633631743, 0.64772213,
    0.660952992, 0.67339574, 0.685115328, 0.696170701, 0.706615283, 0.716497449, 0.72586099, 0.734745554,
    0.743187048, 0.751218013, 0.758867968, 0.766163714, 0.773129612, 0.779787837, 0.786158597, 0.792260339,
    0.798109921, 0.803722777, 0.809113058, 0.814293759, 0.819276832, 0.824073289, 0.82869329, 0.833146226,
    0.837440791, 0.841585045, 0.845586473, 0.849452038, 0.853188224, 0.856801083, 0.860296267, 0.863679065,
    0.866954433, 0.870127021, 0.873201199, 0.876181075, 0.879070523, 0.881873194, 0.884592536, 0.887231809,
    0.889794099, 0.892282328, 0.89469927, 0.897047557, 0.899329691, 0.901548052, 0.903704905, 0.905802409,
    0.907842625, 0.909827516, 0.911758962, 0.913638756, 0.915468615, 0.917250183, 0.918985034, 0.920674676,
    0.922320557, 0.923924065, 0.925486534, 0.927009243, 0.928493424, 0.929940259, 0.931350888, 0.932726406,
    0.934067868, 0.93537629, 0.936652651, 0.937897896, 0.939112934, 0.940298643, 0.941455872, 0.942585436,
    0.943688127, 0.944764708, 0.945815914, 0.946842458, 0.947845028, 0.948824291, 0.94978089, 0.950715448,
    0.951628567, 0.952520831, 0.953392803, 0.954245032, 0.955078046, 0.955892359, 0.956688466, 0.957466849,
    0.958227976, 0.958972297, 0.959700252, 0.960412267, 0.961108752, 0.961790109, 0.962456725, 0.963108976,
    0.963747229, 0.964371838, 0.964983147, 0.96558149, 0.966167193, 0.966740569, 0.967301925, 0.967851559,
    0.968389759, 0.968916806, 0.969432973, 0.969938525, 0.970433719, 0.970918805, 0.971394028, 0.971859624,
    0.972315823, 0.972762849, 0.973200919, 0.973630246, 0.974051036, 0.974463489, 0.974867799, 0.975264158,
    0.975652749, 0.976033752, 0.976407343, 0.976773692, 0.977132964, 0.977485322, 0.977830922, 0.978169918,
    0.978502459, 0.97882869, 0.979148753, 0.979462786, 0.979770922, 0.980073294, 0.980370029, 0.980661251,
    0.980947081, 0.981227638, 0.981503036, 0.981773388, 0.982038804, 0.98229939, 0.98255525, 0.982806486,
    0.983053197, 0.98329548, 0.983533428, 0.983767134, 0.983996687, 0.984222175, 0.984443683, 0.984661295,
    0.984875091, 0.985085152, 0.985291555, 0.985494375, 0.985693685, 0.98588956, 0.986082067, 0.986271277,
    0.986457257, 0.986640071, 0.986819785, 0.98699646, 0.987170157, 0.987340936, 0.987508856, 0.987673974,
    0.987836344, 0.987996022, 0.98815306, 0.988307511, 0.988459425, 0.988608851, 0.988755839, 0.988900436,
    0.989042687, 0.989182639, 0.989320335, 0.989455819, 0.989589133, 0.989720319, 0.989849417, 0.989976466,
    0.990101506, 0.990224575, 0.990345708, 0.990464944, 0.990582316, 0.990697861, 0.990811611, 0.990923601,
    0.991033862, 0.991142427, 0.991249326, 0.99135459, 0.99145825, 0.991560333, 0.99166087, 0.991759887,
    0.991857413, 0.991953474, 0.992048096, 0.992141306, 0.992233128, 0.992323587, 0.992412707, 0.992500513,
    0.992587026, 0.992672271, 0.992756269, 0.992839042, 0.992920611, 0.993000998, 0.993080222, 0.993158305,
    0.993235265, 0.993311122, 0.993385896, 0.993459604, 0.993532264, 0.993603896, 0.993674515, 0.993744139,
    0.993812786, 0.993880471, 0.99394721, 0.99401302, 0.994077916, 0.994141913, 0.994205026, 0.99426727,
    0.994328659, 0.994389208, 0.994448929, 0.994507837, 0.994565945, 0.994623266, 0.994679812, 0.994735597,
    0.994790633, 0.994844931, 0.994898504, 0.994951363, 0.99500352
]
_T0 = 1                      # first tabulated second
_TERMINATION = 0.99500352    # VB stops the table here (SFX > 0.995)

def sfx(t):
    """Cumulative pre-movement fraction at integer second t (clamped)."""
    if t < _T0:
        return 0.0
    i = int(t) - _T0
    if i >= len(VB_SFX):
        return VB_SFX[-1]
    return VB_SFX[i]

def inverse_sfx(u):
    """Start-time (s) for an occupant whose uniform draw is u in [0,1).
    First t with SFX(t) >= u (VB's release order)."""
    i = bisect.bisect_left(VB_SFX, u)
    return _T0 + min(i, len(VB_SFX) - 1)

def sample_start_times(n, rng):
    """Vector of n occupant start-times by inverse-CDF (reproduces VB's
    release schedule: E[count(t)] = n * SFX(t))."""
    import numpy as np
    u = rng.random(n)
    idx = np.searchsorted(VB_SFX, u, side='left')
    idx = np.minimum(idx, len(VB_SFX) - 1)
    return (idx + _T0).astype(float)

def load_from_lvcn(path):
    """Replace the embedded curve with a deck-specific LVCNHesTime.dat
    (lines 'Time = t  SFX = f  No_of_Man = N'). Use when a deck's
    premovement settings differ from the 020CFV0 reference."""
    import re
    global VB_SFX, _TERMINATION
    rows = {}
    for ln in open(path, encoding='utf-8', errors='ignore'):
        m = re.search(r'Time\s*=\s*(\d+)\s+SFX\s*=\s*([\d.eE+-]+)', ln)
        if m:
            rows[int(m.group(1))] = float(m.group(2))
    if rows:
        VB_SFX = [rows[t] for t in sorted(rows)]
        _TERMINATION = VB_SFX[-1]
    return len(VB_SFX)

if __name__ == "__main__":
    import numpy as np
    rng = np.random.default_rng(0)
    s = sample_start_times(333, rng)
    print("median=%.0fs p90=%.0fs p95=%.0fs  (VB: 72/126/160)" % (
        np.median(s), np.percentile(s, 90), np.percentile(s, 95)))
    print("SFX(1)=%.6f  SFX(60)=%.5f  SFX(325)=%.5f" % (sfx(1), sfx(60), sfx(325)))


# """
# Analytic reconstruction of VB's LVCNHesTime pre-movement curve.

# STATUS
# ------
#   EXACT (recovered from the decompile):
#     - the three math helpers' functional forms (normal CDF / Gumbel / Weibull)
#     - every embedded (mu,sigma) and (lambda,k) constant
#     - the 100 s split, the 0.995 termination, the 5000 s cap
#     - SFX is a SUM of three weighted sub-population CDFs
#   PROVISIONAL (needs ONE reference LVCNHesTime.dat OR the 5 globals to lock):
#     - the vararg ARG ORDER inside the helper calls (mu vs sigma vs bound)
#     - the five scenario globals DAT_004a64ea / 65dc / 65ec / 65fc / 660c
#     - the '1 - CDF' complement step on one sub-term
#   => DO NOT wire into the engine's default path until calibrated. The
#      `fit_to_lvcn()` hook below solves the provisional pieces against a real
#      LVCNHesTime.dat in one pass, after which this becomes a standalone port.


# Ported from the decompile of FUN_0045a490 (SFX writer) and its three
# math helpers:
#   FUN_0045afc0  -> normal CDF  Phi((x-mu)/sigma)      (Gaussian pdf, sqrt(2pi), -1/2 z^2)
#   FUN_0045b310  -> Gumbel CDF  exp(-exp(-(x-mu)/sigma))
#   FUN_0045b450  -> Weibull CDF 1-exp(-((x)/lambda)^k)  (domain-guarded)

# SFX(t) is the cumulative FRACTION of occupants who have finished
# pre-movement (left vehicle + hesitation) by time t. VB writes it to
# LVCNHesTime.dat and caches round(N*SFX) in DAT_004a6318[t].

# Constants are the decoded IEEE-754 dwords from the binary. The five
# scenario globals (detection gate + four mixing weights) are exposed as
# parameters; defaults are the four doubles the caller FUN_00459640 loads
# (0.184, 0.51, 0.08, 0.28) plus a detection gate.
# """
# import math

# SQRT_2PI = math.sqrt(2.0 * math.pi)

# # ---- helper 1: FUN_0045afc0  (normal CDF via the same integrand VB integrates)
# def _phi(x, mu, sigma):
#     if sigma <= 0:
#         return 1.0 if x >= mu else 0.0
#     return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))

# # ---- helper 2: FUN_0045b310  (Gumbel / Gompertz double-exponential)
# def _gumbel(x, mu, sigma):
#     if sigma <= 0:
#         return 0.0
#     z = (x - mu) / sigma
#     z = max(min(z, 50.0), -50.0)
#     return math.exp(-math.exp(-z))

# # ---- helper 3: FUN_0045b450  (Weibull-type, guarded at x<=0 -> 0)
# def _weibull(x, lam, k):
#     if x <= 0.0 or lam <= 0.0:
#         return 0.0
#     return 1.0 - math.exp(-((x / lam) ** k))

# # Decoded constants (FUN_0045a490)
# A_MU1, A_SD1 = 17.1, 41.6          # branch A normal #1
# A_MU2, A_SD2 = 81.0, 151.0         # branch A normal #2  (ints 0x51,0x97)
# B_MU,  B_SD  = 155.0, 28.8         # branch B (int 0x9b, dbl 28.8)
# C_L1,  C_K1  = 33.08, 19.91        # branch C weibull #1
# C_L2,  C_K2  = 8.42,  6.13         # branch C weibull #2
# C_S1,  C_S2  = -0.22, -0.44        # branch C slopes

# def sfx(t, det=5.0, w1=0.184, w2=0.51, w3=0.08, w4=0.28):
#     """Cumulative pre-movement fraction at time t (seconds).
#     det = detection/alarm gate (DAT_004a64ea); w1..w4 = mixing weights
#     (DAT_004a65dc/65ec/65fc/660c). Reconstructed assembly: a weighted
#     blend of the three decoded segments, clamped monotone to [0,1]."""
#     if t <= det:
#         return 0.0
#     # Branch A  (det < t <= 100): blend of the two normals
#     segA = w2 * _phi(t, A_MU1, A_SD1) + (1.0 - w2) * _phi(t, A_MU2, A_SD2)
#     # Branch B  (t > 100): gumbel rise blended with the slow normal
#     segB = w3 * _gumbel(t - 100.0, B_MU - 100.0, B_SD) + (1.0 - w3) * _phi(t, A_MU2, A_SD2)
#     # Branch C  (tail, all t>=det): two weibulls
#     segC = w1 * _weibull(t - det, C_L1, abs(C_S1) * C_K1) + w4 * _weibull(t - det, C_L2, abs(C_S2) * C_K2)
#     base = segA if t <= 100.0 else segB
#     return max(0.0, min(1.0, 0.5 * base + 0.5 * segC))

# def build_release_table(n_total, det=5.0, **w):
#     """Mirror DAT_004a6318[]: cumulative man-count by second until SFX>0.995."""
#     tab, t = [], 0
#     prev = -1.0
#     while t <= 5000:
#         f = sfx(t, det=det, **w)
#         f = max(f, prev)              # enforce monotone (VB curve is non-decreasing)
#         prev = f
#         tab.append((t, round(n_total * f), f))
#         if f > 0.995:
#             break
#         t += 1
#     return tab

# if __name__ == "__main__":
#     print("t       SFX        cumN(of 300)")
#     for t in [0,5,10,20,30,45,60,90,120,150,180,240,300,420,600]:
#         print(f"{t:5d}   {sfx(t):.5f}    {round(300*sfx(t))}")
#     tab = build_release_table(300)
#     # summary stats
#     import bisect
#     fr = [r[2] for r in tab]; ts = [r[0] for r in tab]
#     def tq(q):
#         i = bisect.bisect_left(fr, q)
#         return ts[min(i, len(ts)-1)]
#     print(f"\nmonotone: {all(fr[i]<=fr[i+1]+1e-12 for i in range(len(fr)-1))}")
#     print(f"median(p50)={tq(0.5)}s  p90={tq(0.9)}s  p95={tq(0.95)}s  end(0.995)={ts[-1]}s")

# # --------------------------------------------------------------------------
# def fit_to_lvcn(path):
#     """Calibration hook. Given a reference LVCNHesTime.dat (lines of
#     'Time = t  No_of_Man = N  SFX = f'), this returns the exact SFX(t) table
#     VB produced, and is the input for solving the provisional pieces above
#     (the 5 globals, the helper arg order, and the complement term) so the
#     analytic curve reproduces VB to the second. Parsing only here; the solve
#     is run once the file is supplied."""
#     import re
#     pts = []
#     for ln in open(path, encoding='utf-8', errors='ignore'):
#         m = re.search(r'Time\s*=\s*([\d.]+).*?No_of_Man\s*=\s*([\d.]+).*?SFX\s*=\s*([\d.]+)', ln)
#         if m:
#             pts.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
#     return pts