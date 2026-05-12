# vent_functions.py
from dataclasses import dataclass, asdict
from typing import List, Dict
import math

# ---- 1. Data models ----

@dataclass
class TunnelVentInputs:
    # INPUTS (Un computed from V_kmh, traffic_volume computed from Imax)
    V_kmh: float          # 1. 주행속도 (km/h)
    Qtreq: float          # 2. 소요환기량 Qtreq (m3/s)
    Imax: float           # 3. 최대교통량 [PCU/hr·lane]
    road_type: int        # 4. 도로종류 (1=National Road/Expressway, 2=Downtown)
    lanes: int            # 5. 차로수
    Ar: float             # 6. 터널단면적 Ar (m2)
    Lr: float             # 7. 터널길이 Lr (m)
    rho: float            # 8. 공기밀도 ρ (kg/m3)
    xi: float             # 9. 입구손실계수 ξ
    lamb: float           # 10. 마찰손실계수 λ
    Dr: float             # 11. 대표직경 Dr (m)
    Ae: float             # 12. 등가저항면적 Ae (m2)
    jet_diameter: int     # 13. 젯트팬 직경 Φ (mm, e.g. 1030)
    high_efficiency: bool # 14. 고효율형 여부 (True→30 m/s, False→34 m/s)
    eta: float            # 15. 분류효율 η
    vehicle_hr_lane: float = 0.0  # Optional override for vehicles/hr per lane from volume tab

@dataclass
class TunnelVentResults:
    Vt: float
    Vr: float
    Un: float
    Aj: float
    Vj: float
    n: float
    Kj: float
    Pr: float
    Pm: float
    Pt: float
    Pq: float
    Pj: float
    Z_raw: float
    Z_applied: int


# ---- 2. Constant lookup tables ----

JET_AREA_MAP = {
    630: 0.27,
    710: 0.396,
    1030: 0.83,
    1250: 1.227,
    1530: 1.83
}

# Un values corresponding to V_kmh
Vt_MAP = {
    10: 2.78,
    20: 5.56,
    30: 8.33,
    40: 11.11,
    50: 13.89,
    60: 16.67,
    70: 19.44,
    80: 22.22
}

# Allowed speeds for traffic flow calculation
SPEED_OPTIONS_KMH = (10, 20, 30, 40, 50, 60, 70, 80)

# K_lim-1 values per speed (from traffic density analysis)
K_LIM1_BY_SPEED: Dict[int, float] = {
    10: 0.009,
    20: 0.007,
    30: 0.007,
    40: 0.007,
    50: 0.005,
    60: 0.005,
    70: 0.005,
    80: 0.005,
}


# ---- 3. Traffic flow calculation functions ----

def compute_traffic_flow(Imax: float, speed_kmh: float, road_type: int = None, *, K: float = None) -> int:
    """
    교통량 Q [PCU/hr·lane] for a given speed.
    
    If K is given it is used directly as the jam density constant.
    Otherwise road_type selects K  (1→150, 2→165).  Default K=150.
    """
    I = float(Imax)
    V = float(speed_kmh)

    if I <= 0 or V <= 0:
        return 0

    if K is not None:
        k_val = float(K)
    elif road_type == 1:
        k_val = 150.0
    elif road_type == 2:
        k_val = 165.0
    else:
        k_val = 150.0  # default

    numerator = k_val * I
    denominator = k_val * V + I * (1.0 - V / 60.0) ** 2

    q = numerator / denominator  # PCU/hr·lane
    return int(round(q))         # same as Excel ROUND(…,0)


def compute_traffic_density(Imax: float, speed_kmh: float, road_type: int = None, *, K: float = None) -> float:
    """
    교통밀도 k [PCU/km·lane]
    k = Q / V
    """
    flow = compute_traffic_flow(Imax, speed_kmh, road_type, K=K)
    V = float(speed_kmh)
    if V <= 0:
        return 0.0
    k = flow / V
    return round(k, 3)  # 3 decimal places


@dataclass
class TrafficDensityRow:
    """Traffic density table row for hourly traffic volume calculation."""
    speed_kmh: float                 # 속도 V [km/h]
    flow_pcu_per_hr_lane: int        # Q [PCU/hr·lane]
    density_pcu_per_km_lane: float   # k [PCU/km·lane]
    k_lim1: float                    # K_lim-1 at this speed
    density_to_limit_ratio: float    # k / K_lim1 (dimensionless)


def build_traffic_density_table(
    Imax: float,
    road_type: int = None,
    speeds_kmh: List[float] = None,
    *,
    K: float = None
) -> List[TrafficDensityRow]:
    """
    Build traffic density table for hourly traffic volume (n) calculation.
    
    Parameters
    ----------
    Imax : float
        최대교통량 Imax [PCU/hr·lane].
    road_type : int, optional
        Legacy selector: 1 → K=150, 2 → K=165.  Ignored when *K* is given.
    K : float, optional
        Jam-density constant used directly when provided.
    speeds_kmh : list of float, optional
        Speeds to use. If None, default to SPEED_OPTIONS_KMH.
    
    Returns
    -------
    List[TrafficDensityRow]
        One row per speed with flow, density, and limit analysis.
    """
    if speeds_kmh is None:
        speeds_kmh = list(SPEED_OPTIONS_KMH)
    
    table: List[TrafficDensityRow] = []
    
    for V in speeds_kmh:
        Q = compute_traffic_flow(Imax, V, road_type, K=K)
        k = compute_traffic_density(Imax, V, road_type, K=K)
        k_lim = K_LIM1_BY_SPEED.get(int(V), 0.0)
        
        ratio = 0.0
        if k_lim > 0:
            ratio = round(k / k_lim, 3)
        
        row = TrafficDensityRow(
            speed_kmh=V,
            flow_pcu_per_hr_lane=Q,
            density_pcu_per_km_lane=k,
            k_lim1=k_lim,
            density_to_limit_ratio=ratio,
        )
        table.append(row)
    
    return table


# ---- 4. Small functions for each quantity ----

def compute_Un(_V_kmh: float) -> float:
    """자연풍속 Un is treated as a constant for Jet Fan calc."""
    return 2.5


# Removed compute_Vt; Driving speed (m/s) Vt is taken from Vt_MAP based on V_kmh


def compute_Vr(inp: TunnelVentInputs) -> float:
    """차도내풍속 Vr = ROUND(Qtreq / Ar, 4)"""
    return round(inp.Qtreq / inp.Ar, 4)


def compute_Aj(inp: TunnelVentInputs) -> float:
    """젯트팬 면적 Aj : Φ 값에 따른 lookup"""
    if inp.jet_diameter not in JET_AREA_MAP:
        raise ValueError(f"Unsupported jet fan diameter Φ={inp.jet_diameter}")
    return JET_AREA_MAP[inp.jet_diameter]


def compute_Vj(inp: TunnelVentInputs) -> float:
    """젯트팬 토출속도 Vj = IF(high_efficiency, 30, 34)"""
    return 30.0 if inp.high_efficiency else 34.0


def compute_n(inp: TunnelVentInputs, Vt: float) -> float:
    """
    터널내 자동차 수 n
        Preferred formula (if vehicle/hr per lane provided from volume tab):
            n = ROUND((Vehicle/hr, lane × lanes × Lr / (3600 × Vt) + 0.4), 0)

    Fallback (when vehicle/hr per lane is not provided):
      use flow Q [PCU/hr·lane] as before.
    """
    if Vt <= 0:
        return 0.0

    # vehicle_hr_lane is vehicles/hour per lane; multiply by lanes for total vehicles/hour in tunnel
    if inp.vehicle_hr_lane and inp.vehicle_hr_lane > 0:
        n_val = inp.vehicle_hr_lane * inp.lanes * inp.Lr / (3600.0 * Vt)
        return round(n_val + 0.4, 0)

    # Fallback to legacy flow-based calculation
    Q = compute_traffic_flow(inp.Imax, inp.V_kmh, inp.road_type)
    n_val = Q * inp.lanes * inp.Lr / (3600.0 * Vt)
    return round(n_val + 0.4, 0)


def compute_Kj(Vr: float) -> float:
    """제트팬 승압계수 Kj = IF(Vr<4,0.99, IF(Vr<8,0.92,0.9))"""
    if Vr < 4:
        return 0.99
    elif Vr < 8:
        return 0.92
    return 0.9


def compute_common_factor(inp: TunnelVentInputs) -> float:
    """공통계수 (1+ξ+λ*Lr/Dr) * ρ / 2"""
    return (1 + inp.xi + inp.lamb * inp.Lr / inp.Dr) * inp.rho / 2.0 


def compute_Pr(inp: TunnelVentInputs, Vr: float) -> float:
    """ΔPr = common_factor * Vr^2, formatted to 4 decimals"""
    cf = compute_common_factor(inp)
    return float(f"{cf * (Vr ** 2):.4f}")


def compute_Pm(inp: TunnelVentInputs, Un: float) -> float:
    """ΔPm = common_factor * Un^2"""
    cf = compute_common_factor(inp)
    return round(cf * (Un ** 2), 4)


def compute_Pt(inp: TunnelVentInputs, Vt: float, Vr: float, n: int) -> float:
    """
    ΔPt = sign(Vt−Vr) × ρ/2 × (Ae/Ar) × n × (Vt−Vr)^2
    where sign(Vt−Vr) = +1 if Vt>Vr, -1 if Vt<Vr.
    """
    if Vt == Vr:
        return 0.0

    sign = 1.0 if Vt > Vr else -1.0
    base = inp.rho / 2.0 * inp.Ae / inp.Ar * n * (Vt - Vr) ** 2
    return round(sign * base, 4)


def compute_Pq(Pr: float, Pm: float, Pt: float) -> float:
    """ΔPq = Pr + Pm - Pt"""
    return round(Pr + Pm - Pt, 4)


def compute_Pj(inp: TunnelVentInputs, Vr: float, Aj: float, Vj: float, Kj: float) -> float:
    """
    ΔPj = Kj * ρ * Vj^2 * Aj/Ar * (1 - Vr/Vj) * η
    """
    return round(Kj * inp.rho * Vj ** 2 * Aj / inp.Ar * (1 - Vr / Vj) * inp.eta, 4)


def compute_Z_raw(Pq: float, Pj: float) -> float:
    """소요 젯트팬 수 Z = ROUND(Pq / Pj, 2)"""
    if Pj == 0:
        return math.inf
    return round(Pq / Pj, 2)


def compute_Z_applied(Z_raw: float) -> int:
    """적용 수량 Z대 = IF(Z<0,0, CEIL(Z,0)) - Round up when > 0, else 0"""
    if Z_raw <= 0 or math.isinf(Z_raw):
        return 0
    return math.ceil(Z_raw)


# ---- 4. Helper that runs everything ----

def compute_all(inp: TunnelVentInputs) -> TunnelVentResults:
    # Driving speed (m/s) Vt from map keyed by V_kmh
    try:
        key = int(inp.V_kmh)
    except Exception:
        key = int(round(inp.V_kmh))
    Vt = Vt_MAP.get(key, Vt_MAP.get(10))
    Vr = compute_Vr(inp)
    Un = compute_Un(inp.V_kmh)
    Aj = compute_Aj(inp)
    Vj = compute_Vj(inp)
    n = compute_n(inp, Vt)
    Kj = compute_Kj(Vr)
    Pr = compute_Pr(inp, Vr)
    Pm = compute_Pm(inp, Un)
    Pt = compute_Pt(inp, Vt, Vr, n)
    Pq = compute_Pq(Pr, Pm, Pt)
    Pj = compute_Pj(inp, Vr, Aj, Vj, Kj)
    Z_raw = compute_Z_raw(Pq, Pj)
    Z_applied = compute_Z_applied(Z_raw)

    return TunnelVentResults(
        Vt=Vt, Vr=Vr, Un=Un, Aj=Aj, Vj=Vj, n=n, Kj=Kj,
        Pr=Pr, Pm=Pm, Pt=Pt, Pq=Pq, Pj=Pj,
        Z_raw=Z_raw, Z_applied=Z_applied
    )
