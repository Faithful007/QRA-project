"""
traffic_calculations.py

Pure Python translation of src/modules/trafficEstimation/calculations.js
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List


# Excel logic: passenger cars split 60% gasoline / 40% diesel
PASSENGER_SPLIT: Dict[str, float] = {
    "gasoline": 0.6,
    "diesel": 0.4,
}

# Order aligned with Excel columns (C..J) – same as VEHICLE_KEYS in JS
VEHICLE_KEYS: List[str] = [
    "passengerGasoline",  # C
    "passengerDiesel",    # D
    "busSmall",           # E
    "busLarge",           # F
    "truckSmall",         # G
    "truckMedium",        # H
    "truckLarge",         # I
    "truckSpecial",       # J
]


@dataclass
class TrafficInput:
    """
    Input for compute_estimated_traffic, mirroring the JS object.
    All values are AADT (vehicles/day).
    """
    passenger_aadt: float = 0.0
    bus_small: float = 0.0
    bus_large: float = 0.0
    truck_small: float = 0.0
    truck_medium: float = 0.0
    truck_large: float = 0.0
    truck_special: float = 0.0


@dataclass
class TrafficResult:
    """
    Output of compute_estimated_traffic.
    """
    counts: Dict[str, float]
    total_aadt: float
    mix_percents: Dict[str, float]
    mix_percent_sum: float
    heavy_vehicle_mix_pt: float
    # Pressure calculations (optional, computed if tunnel parameters provided)
    delta_Pr: float = 0.0  # Roadway wind pressure loss [Pa]
    delta_Pm: float = 0.0  # Natural wind pressure loss [Pa]
    delta_Pt: float = 0.0  # Vehicle traffic pressure [Pa]
    delta_Pq: float = 0.0  # Required pressure [Pa]


def compute_estimated_traffic(params: TrafficInput) -> TrafficResult:
    """
    Compute estimated daily traffic (추정교통량 / 정교통량),
    translated from computeEstimatedTraffic in calculations.js.

    :param params: TrafficInput with AADT values.
    :return: TrafficResult
    """
    passenger_aadt = float(params.passenger_aadt or 0.0)
    bus_small = float(params.bus_small or 0.0)
    bus_large = float(params.bus_large or 0.0)
    truck_small = float(params.truck_small or 0.0)
    truck_medium = float(params.truck_medium or 0.0)
    truck_large = float(params.truck_large or 0.0)
    truck_special = float(params.truck_special or 0.0)

    # 1) Counts (row 38 / 55 equivalents)
    counts: Dict[str, float] = {
        "passengerGasoline": passenger_aadt * PASSENGER_SPLIT["gasoline"],
        "passengerDiesel": passenger_aadt * PASSENGER_SPLIT["diesel"],
        "busSmall": bus_small,
        "busLarge": bus_large,
        "truckSmall": truck_small,
        "truckMedium": truck_medium,
        "truckLarge": truck_large,
        "truckSpecial": truck_special,
    }

    # 2) Total AADT (K38 / K55)
    total_aadt = 0.0
    for key in VEHICLE_KEYS:
        v = counts.get(key, 0.0)
        total_aadt += float(v or 0.0)

    # 3) Mix ratios (%) per vehicle type
    mix_percents: Dict[str, float] = {}
    if total_aadt > 0:
        for key in VEHICLE_KEYS:
            v = float(counts.get(key, 0.0) or 0.0)
            mix_percents[key] = round((v / total_aadt) * 100.0, 2)
    else:
        for key in VEHICLE_KEYS:
            mix_percents[key] = 0.0

    # 4) Heavy-vehicle mix Pt = F39 + H39 + I39 + J39
    heavy_vehicle_mix_pt = round(
        (mix_percents.get("busLarge", 0.0)
         + mix_percents.get("truckMedium", 0.0)
         + mix_percents.get("truckLarge", 0.0)
         + mix_percents.get("truckSpecial", 0.0)),
        2,
    )

    # 5) Sum of mix (%) – for check (should be ~100)
    mix_percent_sum = 0.0
    for key in VEHICLE_KEYS:
        mix_percent_sum += mix_percents.get(key, 0.0)

    return TrafficResult(
        counts=counts,
        total_aadt=total_aadt,
        mix_percents=mix_percents,
        mix_percent_sum=mix_percent_sum,
        heavy_vehicle_mix_pt=heavy_vehicle_mix_pt,
    )


def compute_pressure_values(
    result: TrafficResult,
    Qtreq: float,
    Ar: float,
    Lr: float,
    Dr: float,
    rho: float,
    xi: float,
    lamb: float,
    Ae: float,
    Vt: float,
    lanes: int,
    vehicle_hr_lane: float = 0.0
) -> TrafficResult:
    """
    Compute pressure values (ΔPr, ΔPm, ΔPt, ΔPq) for traffic estimation results.
    
    Parameters match those in vent_functions for pressure calculations.
    Uses formulas from compute_Pr, compute_Pm, compute_Pt, compute_Pq in vent_functions.py
    
    :param result: TrafficResult to update with pressure values
    :param Qtreq: Required ventilation flow rate [m³/s]
    :param Ar: Tunnel cross-sectional area [m²]
    :param Lr: Tunnel length [m]
    :param Dr: Representative diameter [m]
    :param rho: Air density [kg/m³]
    :param xi: Entrance loss coefficient
    :param lamb: Friction loss coefficient λ
    :param Ae: Equivalent resistance area [m²]
    :param Vt: Driving speed [m/s]
    :param lanes: Number of lanes
    :param vehicle_hr_lane: Vehicles per hour per lane (computed from traffic data)
    :return: Updated TrafficResult with pressure values
    """
    # Compute Vr: roadway wind speed
    Vr = round(Qtreq / Ar, 4) if Ar > 0 else 0.0
    
    # Un: natural wind speed (constant for jet fan calc)
    Un = 2.5
    
    # Compute n: number of vehicles in tunnel
    # Use vehicle_hr_lane if provided, otherwise compute from AADT
    if vehicle_hr_lane > 0 and Vt > 0:
        n = round(vehicle_hr_lane * lanes * Lr / (3600.0 * Vt) + 0.4, 0)
    elif result.total_aadt > 0 and Vt > 0:
        # Convert AADT to hourly traffic (AADT / 24 hours as approximation)
        hourly_per_lane = result.total_aadt / 24.0
        n = round(hourly_per_lane * lanes * Lr / (3600.0 * Vt) + 0.4, 0)
    else:
        n = 0.0
    
    # Common factor for pressure calculations: (1 + ξ + λ*Lr/Dr) * ρ / 2
    common_factor = (1 + xi + lamb * Lr / Dr) * rho / 2.0 if Dr > 0 else 0.0
    
    # ΔPr = common_factor * Vr²
    delta_Pr = round(common_factor * (Vr ** 2), 4)
    
    # ΔPm = common_factor * Un²
    delta_Pm = round(common_factor * (Un ** 2), 4)
    
    # ΔPt = sign(Vt−Vr) × ρ/2 × (Ae/Ar) × n × (Vt−Vr)²
    if Vt == Vr:
        delta_Pt = 0.0
    else:
        sign = 1.0 if Vt > Vr else -1.0
        if Ar > 0:
            delta_Pt = round(sign * rho / 2.0 * Ae / Ar * n * (Vt - Vr) ** 2, 4)
        else:
            delta_Pt = 0.0
    
    # ΔPq = ΔPr + ΔPm - ΔPt
    delta_Pq = round(delta_Pr + delta_Pm - delta_Pt, 4)
    
    # Update result with pressure values
    result.delta_Pr = delta_Pr
    result.delta_Pm = delta_Pm
    result.delta_Pt = delta_Pt
    result.delta_Pq = delta_Pq
    
    return result
