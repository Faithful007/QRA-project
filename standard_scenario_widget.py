"""
standard_scenario_widget.py

Standalone PyQt5 widget that replicates the Excel Standard Scenario sheet
as an in-app module for QRA Tab6/Sub-tab4.

Key behavior:
- English-only UI labels.
- Tree diagram with percentages outside nodes and near control lines.
- Editable inputs and formula-based recalculation (worksheet-like references).
"""

from __future__ import annotations

import math
import os
import tempfile
import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class SubScenario:
    scenario_id: str
    smoke_control: str
    freq_per_yr: float
    return_yr: float
    freq_veh_km: float
    fatalities: List[float]
    vehicle_type: str
    traffic: str
    ventilation: str
    wind: str


@dataclass
class FireScenario:
    branch_label: str
    scenario_id: str
    probability: float
    freq_per_yr: float
    return_yr: float
    freq_veh_km: float
    sub_scenarios: List[SubScenario] = field(default_factory=list)


@dataclass
class VehicleFireType:
    label: str
    probability: float
    hrr_mw: Optional[int] = None
    display_acc: Optional[float] = None
    alias_to: Optional[tuple[str, int]] = None
    normal: Optional[FireScenario] = None
    congest: Optional[FireScenario] = None


@dataclass
class VehicleType:
    name: str
    code: str
    share: float
    accr: float
    acc_per_yr: float
    return_yr: float
    not_serious_prob: float
    not_serious_id: str
    not_serious_freq_yr: float
    not_serious_return_yr: float
    not_serious_freq_veh_km: float
    serious_prob: float
    fire_types: List[VehicleFireType] = field(default_factory=list)


@dataclass(frozen=True)
class FireSizeWorkbookFactors:
    base: float
    vk_pc: float
    vk_hrr: Dict[int, float]
    lfr: Dict[int, float]
    smoke_probs: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "FireSizeWorkbookFactors":
        # Smoke control distribution: NNVC/NNV0/NFF (D54/D55/D56) and CNVC/CNV0/CFF (D57/D58/D59)
        # WV0/WVR/WVP (D31/D30/D29) = 0.333 each by default.
        _nff, _cff, _wv = 0.1, 0.1, 0.333
        _smoke: Dict[str, float] = {
            "NNVC": 0.1, "NNV0": 0.8,
            "NFV0": _nff * _wv, "NFVM": _nff * _wv, "NFVP": _nff * _wv,
            "CNVC": 0.1, "CNV0": 0.8,
            "CFV0": _cff * _wv, "CFVM": _cff * _wv, "CFVP": _cff * _wv,
        }
        return cls(
            base=100000000.0,
            vk_pc=2759393.0649999999,
            vk_hrr={10: 2759393.0649999999, 20: 287594.45, 30: 70309.274749999997, 100: 2346.16525},
            lfr={10: 0.4, 20: 0.15, 30: 0.15, 100: 0.15},
            smoke_probs=_smoke,
        )

    @classmethod
    def from_workbook(cls, workbook_path: Path) -> "FireSizeWorkbookFactors":
        if not workbook_path.exists():
            return cls.default()

        try:
            with ZipFile(workbook_path) as zf:
                wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
                rel_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
                ns_main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                ns_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                ns = {"m": ns_main, "r": ns_rel}

                relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rel_root}
                sheet_targets = {}
                for sheet in wb_root.find("m:sheets", ns):
                    rid = sheet.attrib.get(f"{{{ns_rel}}}id")
                    target = relmap.get(rid)
                    if target:
                        sheet_targets[sheet.attrib.get("name", "")] = f"xl/{target}"

                defined_names = {}
                dn_root = wb_root.find("m:definedNames", ns)
                if dn_root is not None:
                    for dn in dn_root:
                        name = dn.attrib.get("name", "")
                        text = (dn.text or "").strip()
                        if name and text and "!" in text:
                            defined_names[name.upper()] = text

                cell_cache: Dict[str, Dict[str, float]] = {}

                def get_cell_value(sheet_name: str, cell_ref: str) -> float:
                    sheet_cache = cell_cache.setdefault(sheet_name, {})
                    if cell_ref in sheet_cache:
                        return sheet_cache[cell_ref]

                    target = sheet_targets[sheet_name]
                    root = ET.fromstring(zf.read(target))
                    value = 0.0
                    for cell in root.iter(f"{{{ns_main}}}c"):
                        if cell.attrib.get("r") != cell_ref:
                            continue
                        node = cell.find(f"{{{ns_main}}}v")
                        if node is not None and node.text:
                            value = float(node.text)
                        break
                    sheet_cache[cell_ref] = value
                    return value

                def resolve_defined_value(name: str) -> float:
                    ref = defined_names[name.upper()]
                    sheet_part, cell_ref = ref.split("!", 1)
                    return get_cell_value(sheet_part.strip("'"), cell_ref.replace("$", ""))

                # Smoke control probabilities from tunnel sheet (D29-D31, D54-D59)
                try:
                    _nnvc = resolve_defined_value("NNVC")
                    _nnv0 = resolve_defined_value("NNV0")
                    _nff  = resolve_defined_value("NFF")
                    _cnvc = resolve_defined_value("CNVC")
                    _cnv0 = resolve_defined_value("CNV0")
                    _cff  = resolve_defined_value("CFF")
                    _wv0  = resolve_defined_value("WV0")
                    _wvr  = resolve_defined_value("WVR")
                    _wvp  = resolve_defined_value("WVP")
                    _smoke: Dict[str, float] = {
                        "NNVC": _nnvc, "NNV0": _nnv0,
                        "NFV0": _nff * _wv0, "NFVM": _nff * _wvr, "NFVP": _nff * _wvp,
                        "CNVC": _cnvc, "CNV0": _cnv0,
                        "CFV0": _cff * _wv0, "CFVM": _cff * _wvr, "CFVP": _cff * _wvp,
                    }
                except Exception:
                    _smoke = cls.default().smoke_probs

                return cls(
                    base=resolve_defined_value("BASE"),
                    vk_pc=resolve_defined_value("VK.PC"),
                    vk_hrr={
                        10: resolve_defined_value("VK.HRR010"),
                        20: resolve_defined_value("VK.HRR020"),
                        30: resolve_defined_value("VK.HRR030"),
                        100: resolve_defined_value("VK.HRR100"),
                    },
                    lfr={
                        10: resolve_defined_value("LFR.010"),
                        20: resolve_defined_value("LFR.020"),
                        30: resolve_defined_value("LFR.030"),
                        100: resolve_defined_value("LFR.100"),
                    },
                    smoke_probs=_smoke,
                )
        except Exception:
            return cls.default()

    def total_vk_hrr(self, hrr_mw: int) -> float:
        if hrr_mw == 20:
            return self.vk_hrr[20] * self.lfr[20] + self.vk_hrr[30] * (1.0 - self.lfr[30])
        if hrr_mw == 30:
            return self.vk_hrr[30] * self.lfr[30] + self.vk_hrr[100] * (1.0 - self.lfr[100])
        if hrr_mw == 100:
            return self.vk_hrr[100] * self.lfr[100]
        return self.vk_pc

    def denominator_for_vehicle(self, vehicle_code: str) -> float:
        if vehicle_code == "PC":
            return self.vk_pc
        if vehicle_code == "BUS":
            # Spreadsheet S30: Q30/TOT.VK.HRR020 = Q / (VK.HRR020*LFR.020 + VK.HRR030*(1-LFR.030))
            return self.total_vk_hrr(20)
        if vehicle_code == "GV":
            # Spreadsheet S40: Q40/TOT.VK.HRR030 = Q / (VK.HRR030*LFR.030 + VK.HRR100*(1-LFR.100))
            return self.total_vk_hrr(30)
        if vehicle_code == "ST":
            # Spreadsheet S50: Q50/VK.HRR100 — uses raw VK.HRR100 (D47), NOT TOT.VK.HRR100
            return self.vk_hrr.get(100, 0.0)
        return 0.0

    def not_serious_denominator(self, vehicle_code: str) -> float:
        """Denominator for not-serious freq_veh_km.

        PC : VK.PC  (spreadsheet M7: K7/VK.PC)
        BUS: VK.HRR020 * (1 - LFR.020)  (= TOT.VK.HRR020.NOT.SER, M28: K28/TOT.VK.HRR020.NOT.SER)
        GV/ST: no not-serious branch
        """
        if vehicle_code == "PC":
            return self.vk_pc
        if vehicle_code == "BUS":
            return self.vk_hrr.get(20, 0.0) * (1.0 - self.lfr.get(20, 0.0))
        return 0.0

    def accident_rate_for_vehicle(self, vehicle_code: str, freq_per_yr: float) -> float:
        denominator = self.denominator_for_vehicle(vehicle_code)
        if denominator <= 0.0 or self.base <= 0.0:
            return 0.0
        return freq_per_yr * self.base / denominator


def _safe_return_year(freq_per_yr: float) -> float:
    return (1.0 / freq_per_yr) if freq_per_yr > 0 else 0.0


def _clone_branch_from_template(template: FireScenario, scenario_id: str, branch_freq_per_yr: float, vehicle_type: str) -> FireScenario:
    branch_factor = (template.freq_veh_km / template.freq_per_yr) if template.freq_per_yr > 0 else 0.0
    sub_scenarios: List[SubScenario] = []
    for src in template.sub_scenarios:
        weight = (src.freq_per_yr / template.freq_per_yr) if template.freq_per_yr > 0 else 0.0
        sub_freq = branch_freq_per_yr * weight
        sub_factor = (src.freq_veh_km / src.freq_per_yr) if src.freq_per_yr > 0 else 0.0
        sub_scenarios.append(
            SubScenario(
                scenario_id=src.scenario_id,
                smoke_control=src.smoke_control,
                freq_per_yr=sub_freq,
                return_yr=_safe_return_year(sub_freq),
                freq_veh_km=sub_freq * sub_factor,
                fatalities=list(src.fatalities),
                vehicle_type=vehicle_type,
                traffic=src.traffic,
                ventilation=src.ventilation,
                wind=src.wind,
            )
        )
    return FireScenario(
        branch_label=template.branch_label,
        scenario_id=scenario_id,
        probability=template.probability,
        freq_per_yr=branch_freq_per_yr,
        return_yr=_safe_return_year(branch_freq_per_yr),
        freq_veh_km=branch_freq_per_yr * branch_factor,
        sub_scenarios=sub_scenarios,
    )


def _build_standard_scenario_data() -> List[VehicleType]:
    # Passenger Car (PC)
    pc_p1n_subs = [
        SubScenario("PC1N", "NNVC", 7.99e-4, 1251.1, 2.8967e-10, [0] * 6, "PC Single", "Normal", "Vent OK", "0 m/s"),
        SubScenario("PC1N", "NNV0", 6.39e-3, 156.4, 2.3174e-9, [0] * 6, "PC Single", "Normal", "Vent OK", "Critical wind"),
        SubScenario("PC1N", "NFV0", 2.66e-4, 3756.9, 9.646e-11, [0] * 6, "PC Single", "Normal", "Vent Fail", "Natural wind: 0"),
        SubScenario("PC1N", "NFVM", 2.66e-4, 3756.9, 9.646e-11, [0] * 6, "PC Single", "Normal", "Vent Fail", "Natural wind: -"),
        SubScenario("PC1N", "NFVP", 2.66e-4, 3756.9, 9.646e-11, [0] * 6, "PC Single", "Normal", "Vent Fail", "Natural wind: +"),
    ]
    pc_p1c_subs = [
        SubScenario("PC1C", "CNVC", 8.07e-6, 123854.6, 2.926e-12, [0] * 6, "PC Single", "Congested", "Vent OK", "0 m/s"),
        SubScenario("PC1C", "CNV0", 6.46e-5, 15481.8, 2.341e-11, [0] * 6, "PC Single", "Congested", "Vent OK", "Critical wind"),
        SubScenario("PC1C", "CFV0", 2.69e-6, 371935.7, 9.744e-13, [0] * 6, "PC Single", "Congested", "Vent Fail", "Natural wind: 0"),
        SubScenario("PC1C", "CFVM", 2.69e-6, 371935.7, 9.744e-13, [0] * 6, "PC Single", "Congested", "Vent Fail", "Natural wind: -"),
        SubScenario("PC1C", "CFVP", 2.69e-6, 371935.7, 9.744e-13, [0] * 6, "PC Single", "Congested", "Vent Fail", "Natural wind: +"),
    ]
    pc_p2n_subs = [
        SubScenario("PC2N", "NNVC", 4.207e-5, 23770.1, 1.5246e-11, [0] * 6, "PC Chain", "Normal", "Vent OK", "0 m/s"),
        SubScenario("PC2N", "NNV0", 3.366e-4, 2971.3, 1.2197e-10, [0] * 6, "PC Chain", "Normal", "Vent OK", "Critical wind"),
        SubScenario("PC2N", "NFV0", 1.401e-5, 71381.6, 5.077e-12, [0] * 6, "PC Chain", "Normal", "Vent Fail", "Natural wind: 0"),
        SubScenario("PC2N", "NFVM", 1.401e-5, 71381.6, 5.077e-12, [0] * 6, "PC Chain", "Normal", "Vent Fail", "Natural wind: -"),
        SubScenario("PC2N", "NFVP", 1.401e-5, 71381.6, 5.077e-12, [0] * 6, "PC Chain", "Normal", "Vent Fail", "Natural wind: +"),
    ]
    pc_p2c_subs = [
        SubScenario("PC2C", "CNVC", 4.249e-7, 2353237.2, 1.54e-13, [0] * 6, "PC Chain", "Congested", "Vent OK", "0 m/s"),
        SubScenario("PC2C", "CNV0", 3.4e-6, 294154.7, 1.232e-12, [0] * 6, "PC Chain", "Congested", "Vent OK", "Critical wind"),
        SubScenario("PC2C", "CFV0", 1.415e-7, 7066778.5, 5.128e-14, [0] * 6, "PC Chain", "Congested", "Vent Fail", "Natural wind: 0"),
        SubScenario("PC2C", "CFVM", 1.415e-7, 7066778.5, 5.128e-14, [0] * 6, "PC Chain", "Congested", "Vent Fail", "Natural wind: -"),
        SubScenario("PC2C", "CFVP", 1.415e-7, 7066778.5, 5.128e-14, [0] * 6, "PC Chain", "Congested", "Vent Fail", "Natural wind: +"),
    ]

    pc = VehicleType(
        name="Passenger Car",
        code="PC",
        share=0.77,
        accr=0.8748,
        acc_per_yr=0.02125,
        return_yr=47.06,
        not_serious_prob=0.60,
        not_serious_id="B1",
        not_serious_freq_yr=0.01275,
        not_serious_return_yr=78.44,
        not_serious_freq_veh_km=4.62e-9,
        serious_prob=0.40,
        fire_types=[
            VehicleFireType(
                "Single Fire\n5 MW",
                0.95,
                normal=FireScenario("Normal", "P1N", 0.2897, 7.99e-3, 125.1, 2.897e-9, pc_p1n_subs),
                congest=FireScenario("Congested", "P1C", 0.0029, 8.07e-5, 12385.5, 2.926e-11, pc_p1c_subs),
            ),
            VehicleFireType(
                "Chain Fire\n10 MW",
                0.05,
                normal=FireScenario("Normal", "P2N", 0.01525, 4.207e-4, 2377.0, 1.525e-10, pc_p2n_subs),
                congest=FireScenario("Congested", "P2C", 1.54e-4, 4.249e-6, 235323.7, 1.54e-12, pc_p2c_subs),
            ),
        ],
    )

    # Bus
    bus_bn_subs = [
        SubScenario("020N", "NNVC", 2.010e-4, 4975.2, 1.953e-9, [0] * 6, "Bus", "Normal", "Vent OK", "0 m/s"),
        SubScenario("020N", "NNV0", 1.608e-3, 621.9, 1.563e-8, [0] * 6, "Bus", "Normal", "Vent OK", "Critical wind"),
        SubScenario("020N", "NFV0", 6.693e-5, 14940.6, 6.504e-10, [0] * 6, "Bus", "Normal", "Vent Fail", "Natural wind: 0"),
        SubScenario("020N", "NFVM", 6.693e-5, 14940.6, 6.504e-10, [0] * 6, "Bus", "Normal", "Vent Fail", "Natural wind: -"),
        SubScenario("020N", "NFVP", 6.693e-5, 14940.6, 6.504e-10, [0.117, 0, 0, 0, 0, 0.1], "Bus", "Normal", "Vent Fail", "Natural wind: +"),
    ]
    bus_bc_subs = [
        SubScenario("020C", "CNVC", 2.030e-6, 492547.3, 1.973e-11, [0] * 6, "Bus", "Congested", "Vent OK", "0 m/s"),
        SubScenario("020C", "CNV0", 1.624e-5, 61568.4, 1.578e-10, [0] * 6, "Bus", "Congested", "Vent OK", "Critical wind"),
        SubScenario("020C", "CFV0", 6.761e-7, 1479121.2, 6.570e-12, [5.934, 30.2, 4.1, 1.1, 0, 0], "Bus", "Congested", "Vent Fail", "Natural wind: 0"),
        SubScenario("020C", "CFVM", 6.761e-7, 1479121.2, 6.570e-12, [0.654, 1.3, 0.4, 0, 0, 0.2], "Bus", "Congested", "Vent Fail", "Natural wind: -"),
        SubScenario("020C", "CFVP", 6.761e-7, 1479121.2, 6.570e-12, [0.151, 0, 0, 0, 0, 0.1], "Bus", "Congested", "Vent Fail", "Natural wind: +"),
    ]

    bus_normal = FireScenario("Normal", "BN", 0.2257, 2.010e-3, 497.5, 1.953e-8, bus_bn_subs)
    bus_congest = FireScenario("Congested", "BC", 0.00228, 2.030e-5, 49254.7, 1.973e-10, bus_bc_subs)

    bus = VehicleType(
        name="Bus",
        code="BUS",
        share=0.15,
        accr=1.52,
        acc_per_yr=0.004371,
        return_yr=228.8,
        not_serious_prob=0.85,
        not_serious_id="BS1",
        not_serious_freq_yr=0.003158,
        not_serious_return_yr=316.6,
        not_serious_freq_veh_km=1.292e-8,
        serious_prob=0.15,
        fire_types=[
            VehicleFireType(
                "Bus Fire\n<= 20 MW",
                1.0,
                hrr_mw=20,
                normal=bus_normal,
                congest=bus_congest,
            )
        ],
    )

    # General Cargo Truck (GV)
    gv_gvn_subs = [
        SubScenario("030N", "NNVC", 2.856e-5, 35020.1, 2.277e-9, [9.287, 0, 0, 0.7, 7.4, 28], "General Truck", "Normal", "Vent OK", "0 m/s"),
        SubScenario("030N", "NNV0", 2.284e-4, 4377.5, 1.822e-8, [2.649, 15.3, 0.5, 0, 0, 0], "General Truck", "Normal", "Vent OK", "Critical wind"),
        SubScenario("030N", "NFV0", 9.509e-6, 105165.5, 7.582e-10, [0] * 6, "General Truck", "Normal", "Vent Fail", "Natural wind: 0"),
        SubScenario("030N", "NFVM", 9.509e-6, 105165.5, 7.582e-10, [0] * 6, "General Truck", "Normal", "Vent Fail", "Natural wind: -"),
        SubScenario("030N", "NFVP", 9.509e-6, 105165.5, 7.582e-10, [2.833, 0, 0, 0, 0, 5.5], "General Truck", "Normal", "Vent Fail", "Natural wind: +"),
    ]
    gv_gvc_subs = [
        SubScenario("030C", "CNVC", 2.884e-7, 3466991.3, 2.30e-11, [6.672, 0, 0, 0.1, 2, 17.2], "General Truck", "Congested", "Vent OK", "0 m/s"),
        SubScenario("030C", "CNV0", 2.307e-6, 433373.9, 1.840e-10, [0] * 6, "General Truck", "Congested", "Vent OK", "Critical wind"),
        SubScenario("030C", "CFV0", 9.605e-8, 10411385.3, 7.659e-12, [42.66, 140.1, 85.6, 27.7, 1.1, 0], "General Truck", "Congested", "Vent Fail", "Natural wind: 0"),
        SubScenario("030C", "CFVM", 9.605e-8, 10411385.3, 7.659e-12, [7.510, 21.9, 4.9, 0.3, 0.1, 3.5], "General Truck", "Congested", "Vent Fail", "Natural wind: -"),
        SubScenario("030C", "CFVP", 9.605e-8, 10411385.3, 7.659e-12, [3.554, 0, 0, 0, 0.1, 6.3], "General Truck", "Congested", "Vent Fail", "Natural wind: +"),
    ]

    gv_30_normal = FireScenario("Normal", "GVN", 0.3415, 2.856e-4, 3502.0, 2.277e-8, gv_gvn_subs)
    gv_30_congest = FireScenario("Congested", "GVC", 0.00345, 2.884e-6, 346699.1, 2.30e-10, gv_gvc_subs)
    gv_20_total_freq = 1.168e-3
    gv_20_branch_total = bus_normal.freq_per_yr + bus_congest.freq_per_yr
    gv_20_normal = _clone_branch_from_template(
        bus_normal,
        "GVN",
        gv_20_total_freq * (bus_normal.freq_per_yr / gv_20_branch_total),
        "General Truck",
    )
    gv_20_congest = _clone_branch_from_template(
        bus_congest,
        "GVC",
        gv_20_total_freq * (bus_congest.freq_per_yr / gv_20_branch_total),
        "General Truck",
    )

    gv = VehicleType(
        name="General Cargo Truck",
        code="GV",
        share=0.15,
        accr=2.3,
        acc_per_yr=0.001617,
        return_yr=618.4,
        not_serious_prob=0.0,
        not_serious_id="GVB1",
        not_serious_freq_yr=0.0,
        not_serious_return_yr=0.0,
        not_serious_freq_veh_km=0.0,
        serious_prob=1.0,
        fire_types=[
            VehicleFireType(
                "General Cargo Fire\n20 MW",
                0.85,
                hrr_mw=20,
                display_acc=2.3 * 0.85,
                alias_to=("BUS", 20),
                normal=gv_20_normal,
                congest=gv_20_congest,
            ),
            VehicleFireType(
                "Large Cargo Fire\n30 MW",
                0.15,
                hrr_mw=30,
                display_acc=2.3 * 0.15,
                normal=gv_30_normal,
                congest=gv_30_congest,
            )
        ],
    )

    # Special / Hazardous Cargo Truck (ST)
    st_stn_subs = [
        SubScenario("100N", "NNVC", 8.013e-7, 1247921.1, 3.415e-10, [3.713, 2.1, 0.9, 0.5, 0.2, 0.9], "Special Truck", "Normal", "Vent OK", "0 m/s"),
        SubScenario("100N", "NNV0", 6.411e-6, 155990.1, 2.732e-9, [0] * 6, "Special Truck", "Normal", "Vent OK", "Critical wind"),
        SubScenario("100N", "NFV0", 2.668e-7, 3747510.7, 1.137e-10, [0] * 6, "Special Truck", "Normal", "Vent Fail", "Natural wind: 0"),
        SubScenario("100N", "NFVM", 2.668e-7, 3747510.7, 1.137e-10, [0] * 6, "Special Truck", "Normal", "Vent Fail", "Natural wind: -"),
        SubScenario("100N", "NFVP", 2.668e-7, 3747510.7, 1.137e-10, [35.92, 0, 0, 3.0, 19, 67.6], "Special Truck", "Normal", "Vent Fail", "Natural wind: +"),
    ]
    st_stc_subs = [
        SubScenario("100C", "CNVC", 8.094e-9, 123544184.5, 3.45e-12, [9.181, 8.3, 2.2, 0.9, 1.0, 1.6], "Special Truck", "Congested", "Vent OK", "0 m/s"),
        SubScenario("100C", "CNV0", 6.475e-8, 15443023.1, 2.76e-11, [6.052, 0, 0, 0.5, 3.3, 10.9], "Special Truck", "Congested", "Vent OK", "Critical wind"),
        SubScenario("100C", "CFV0", 2.695e-9, 371003557.0, 1.149e-12, [135.0, 309.2, 222.3, 173.2, 86.8, 14.1], "Special Truck", "Congested", "Vent Fail", "Natural wind: 0"),
        SubScenario("100C", "CFVM", 2.695e-9, 371003557.0, 1.149e-12, [94.66, 119.2, 114, 78.9, 75.6, 85], "Special Truck", "Congested", "Vent Fail", "Natural wind: -"),
        SubScenario("100C", "CFVP", 2.695e-9, 371003557.0, 1.149e-12, [54.33, 0, 0, 2, 49.3, 128.4], "Special Truck", "Congested", "Vent Fail", "Natural wind: +"),
    ]

    st_100_normal = FireScenario("Normal", "STN", 0.3415, 8.013e-6, 124792.1, 2.277e-8, st_stn_subs)
    st_100_congest = FireScenario("Congested", "STC", 0.00345, 8.094e-8, 12354418.4, 2.30e-10, st_stc_subs)
    st_30_total_freq = 4.587e-5
    st_30_branch_total = gv_30_normal.freq_per_yr + gv_30_congest.freq_per_yr
    st_30_normal = _clone_branch_from_template(
        gv_30_normal,
        "STN",
        st_30_total_freq * (gv_30_normal.freq_per_yr / st_30_branch_total),
        "Special Truck",
    )
    st_30_congest = _clone_branch_from_template(
        gv_30_congest,
        "STC",
        st_30_total_freq * (gv_30_congest.freq_per_yr / st_30_branch_total),
        "Special Truck",
    )

    st = VehicleType(
        name="Special / Hazardous Cargo",
        code="ST",
        share=0.08,
        accr=2.3,
        acc_per_yr=5.396e-5,
        return_yr=18531.6,
        not_serious_prob=0.0,
        not_serious_id="STB1",
        not_serious_freq_yr=0.0,
        not_serious_return_yr=0.0,
        not_serious_freq_veh_km=0.0,
        serious_prob=1.0,
        fire_types=[
            VehicleFireType(
                "Hazardous Cargo Fire\n30 MW",
                0.85,
                hrr_mw=30,
                display_acc=2.3 * 0.85,
                alias_to=("GV", 30),
                normal=st_30_normal,
                congest=st_30_congest,
            ),
            VehicleFireType(
                "Special Cargo Fire\n100 MW",
                0.15,
                hrr_mw=100,
                display_acc=2.3 * 0.15,
                normal=st_100_normal,
                congest=st_100_congest,
            )
        ],
    )

    return [pc, bus, gv, st]


class EventTreeDiagram(QWidget):
    # UI spacing conversion assumes ~96 DPI: 1 cm ~= 38 px.
    CM_TO_PX = 38
    EXTRA_NODE_GAP_CM = 2.0
    EXTRA_NODE_GAP_PX = int(CM_TO_PX * EXTRA_NODE_GAP_CM)
    MIN_NODE_GAP_PX = EXTRA_NODE_GAP_PX

    # Add +2 cm for each successive node column to improve readability.
    CX = {
        "total": 65,
        "vehicle": 189 + (1 * EXTRA_NODE_GAP_PX),
        "severity": 316 + (2 * EXTRA_NODE_GAP_PX),
        "fire": 448 + (3 * EXTRA_NODE_GAP_PX),
        "branch": 679 + (4 * EXTRA_NODE_GAP_PX),
        "scenario": 803 + (5 * EXTRA_NODE_GAP_PX),
        "freq_yr": 922 + (6 * EXTRA_NODE_GAP_PX),
        "return_yr": 1041 + (7 * EXTRA_NODE_GAP_PX),
        "freq_vkm": 1170 + (8 * EXTRA_NODE_GAP_PX),
    }
    COL_W = {
        "total": 90,
        "vehicle": 155,
        "severity": 95,
        "fire": 165,
        "branch": 105,
        "scenario": 95,
        "freq_yr": 95,
        "return_yr": 95,
        "freq_vkm": 115,
    }
    HEADER_H = 52
    ROW_H = 20
    BOX_H = 20
    HEADER_GAP = 24
    SCENARIO_BOX_H = 38
    # Keep at least 2 cm center-to-center spacing for branch/scenario nodes.
    SCENARIO_ROW_STEP = max(63, MIN_NODE_GAP_PX)
    BRANCH_BOX_H = 38
    VEHICLE_BOX_H = 96
    FIRE_BOX_H = 96

    def __init__(self, data: List[VehicleType], fire_size_factors: Optional[FireSizeWorkbookFactors] = None, parent=None):
        super().__init__(parent)
        self._data = data
        self._fire_size_factors = fire_size_factors or FireSizeWorkbookFactors.default()
        self._compute_layout()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        min_w = int(self.CX["freq_vkm"] + (self.COL_W["freq_vkm"] / 2) + 24)
        self.setMinimumWidth(max(1210, min_w))

    def _fire_node_metrics(self, vt: VehicleType, ft: VehicleFireType) -> Dict[str, float]:
        freq_per_yr = sum(br.freq_per_yr for br in (ft.normal, ft.congest) if br is not None)
        serious_total = 0.0
        for fire_type in vt.fire_types:
            serious_total += sum(br.freq_per_yr for br in (fire_type.normal, fire_type.congest) if br is not None)

        def _vt_accr(code: str) -> float:
            found = next((x for x in self._data if x.code == code), None)
            return float(found.accr) if found is not None else 0.0

        base = float(self._fire_size_factors.base) if self._fire_size_factors.base else 0.0
        vk20 = float(self._fire_size_factors.vk_hrr.get(20, 0.0))
        vk30 = float(self._fire_size_factors.vk_hrr.get(30, 0.0))
        vk100 = float(self._fire_size_factors.vk_hrr.get(100, 0.0))
        lfr20 = float(self._fire_size_factors.lfr.get(20, 0.0))
        lfr30 = float(self._fire_size_factors.lfr.get(30, 0.0))
        lfr100 = float(self._fire_size_factors.lfr.get(100, 0.0))

        if vt.code == "BUS" and ft.hrr_mw == 20 and base > 0.0:
            # ACCR = C32 * LFR.020
            acc = vt.accr * lfr20 * ft.probability
            # Case/Yr = VK.HRR020/BASE*F32 + C42*vk.hrr030.dn/BASE
            # where F32 is ACCR at this node and vk.hrr030.dn = VK.HRR030*(1-LFR.030)
            gv_accr = _vt_accr("GV")
            vk30_dn = vk30 * (1.0 - lfr30)
            freq_per_yr = ((vk20 / base) * acc + (gv_accr * vk30_dn / base)) * ft.probability
        elif vt.code == "GV" and ft.hrr_mw == 30 and base > 0.0:
            # ACCR = C42 * LFR.030  (spreadsheet F42 = C42*LFR.030, no extra probability)
            acc = vt.accr * lfr30
            # Case/Yr = VK.HRR030/BASE*F42 + C52*vk.hrr100.dn/BASE
            # where F42 is ACCR at this node and vk.hrr100.dn = VK.HRR100*(1-LFR.100)
            st_accr = _vt_accr("ST")
            vk100_dn = vk100 * (1.0 - lfr100)
            freq_per_yr = (vk30 / base) * acc + (st_accr * vk100_dn / base)
        elif vt.code == "ST" and ft.hrr_mw == 100 and base > 0.0:
            # ACCR = Hazardous cargo probability (0.15 default) * C52
            acc = vt.accr * ft.probability
            # Case/Yr = VK.HRR100/BASE*F52 where F52 is ACCR at this node
            freq_per_yr = (vk100 / base) * acc
        elif ft.display_acc is not None:
            acc = ft.display_acc
        elif vt.code == "PC":
            acc = vt.accr * ft.probability * self._fire_size_factors.lfr[10]
        elif ft.hrr_mw in self._fire_size_factors.lfr:
            acc = vt.accr * self._fire_size_factors.lfr[ft.hrr_mw]
        else:
            acc = self._fire_size_factors.accident_rate_for_vehicle(vt.code, freq_per_yr)
        return {
            "acc": acc,
            "prob": (freq_per_yr / serious_total) if serious_total > 0 else 0.0,
            "freq_per_yr": freq_per_yr,
            "return_yr": _safe_return_year(freq_per_yr),
        }

    def _font(self, size=8, bold=False):
        f = QFont("Malgun Gothic", size)
        f.setBold(bold)
        return f

    def _compute_layout(self):
        self._leaves: List[dict] = []
        y = self.HEADER_H + 14
        for vt in self._data:
            if vt.not_serious_prob > 0.0:
                self._leaves.append({"kind": "not_serious", "vt": vt, "y": y})
                y += self.ROW_H * 2
            for ft in vt.fire_types:
                if ft.alias_to is not None:
                    continue
                for br in (ft.normal, ft.congest):
                    if br is None:
                        continue
                    self._leaves.append({"kind": "branch", "vt": vt, "ft": ft, "branch": br, "y": y})
                    y += self.SCENARIO_ROW_STEP
                y += 10
            y += 14
        self.setMinimumHeight(int(y + 20))

    def refresh(self, data: List[VehicleType]):
        self._data = data
        self._compute_layout()
        self.update()

    def _mid(self, leaves: List[dict]) -> float:
        ys = [x["y"] for x in leaves]
        return (min(ys) + max(ys)) / 2.0

    def _fmt_e(self, v: float) -> str:
        if v == 0:
            return "0.0000"
        exp = int(math.floor(math.log10(abs(v))))
        mant = v / (10 ** exp)
        return f"{mant:.4f}E{exp:+d}"

    def _fmt_ret(self, v: float) -> str:
        if v == 0:
            return "-"
        return f"{v:,.4f}"

    def _fmt_pct(self, v: float, decimals: int = 4) -> str:
        """Format percentage and trim trailing zeros (e.g., 60.0000 -> 60)."""
        text = f"{v:.{decimals}f}".rstrip('0').rstrip('.')
        if text == "":
            text = "0"
        return f"{text}%"

    def _box(self, p: QPainter, cx: float, cy: float, w: float, h: float, text: str, fill: QColor, border: QColor, txt: QColor, bold=False, fs=8):
        r = QRectF(cx - w / 2, cy - h / 2, w, h)
        p.setBrush(QBrush(fill))
        p.setPen(QPen(border, 0.8))
        p.drawRoundedRect(r, 3, 3)
        p.setPen(QPen(txt))
        p.setFont(self._font(fs, bold))
        p.drawText(r, Qt.AlignCenter | Qt.TextWordWrap, text)

    def _connector(self, p: QPainter, x1: float, y1: float, x2: float, y2: float, color: QColor):
        mid_x = (x1 + x2) / 2.0
        arrow_len = 7.0
        arrow_half = 3.5
        line_end_x = max(mid_x, x2 - arrow_len)
        p.setPen(QPen(color, 0.9))
        p.drawLine(int(x1), int(y1), int(mid_x), int(y1))
        p.drawLine(int(mid_x), int(y1), int(mid_x), int(y2))
        p.drawLine(int(mid_x), int(y2), int(line_end_x), int(y2))
        p.drawLine(int(x2 - arrow_len), int(y2 - arrow_half), int(x2), int(y2))
        p.drawLine(int(x2 - arrow_len), int(y2 + arrow_half), int(x2), int(y2))
        return mid_x

    def _connector_routed(self, p: QPainter, x1: float, y1: float, x2: float, y2: float, color: QColor, lane_x: float):
        arrow_len = 7.0
        arrow_half = 3.5
        lane_x = max(x1 + 6.0, min(lane_x, x2 - arrow_len - 2.0))
        line_end_x = x2 - arrow_len
        p.setPen(QPen(color, 0.9))
        p.drawLine(int(x1), int(y1), int(lane_x), int(y1))
        p.drawLine(int(lane_x), int(y1), int(lane_x), int(y2))
        p.drawLine(int(lane_x), int(y2), int(line_end_x), int(y2))
        p.drawLine(int(x2 - arrow_len), int(y2 - arrow_half), int(x2), int(y2))
        p.drawLine(int(x2 - arrow_len), int(y2 + arrow_half), int(x2), int(y2))
        return lane_x

    def _draw_percent_label(self, p: QPainter, text: str, x: float, y: float, color: QColor):
        p.setFont(self._font(8, True))
        p.setPen(QPen(color))
        p.drawText(QRectF(x - 34, y - 14, 68, 14), Qt.AlignCenter, text)

    def _vehicle_box(self, p: QPainter, cx: float, cy: float, w: float, h: float, vt: VehicleType):
        r = QRectF(cx - w / 2, cy - h / 2, w, h)
        fill = QColor("#E8F4FD")
        border = QColor("#2980B9")
        text_color = QColor("#1A5276")

        p.setBrush(QBrush(fill))
        p.setPen(QPen(border, 0.9))
        p.drawRoundedRect(r, 3, 3)

        # Title row gets the remaining height after 3 data rows of 20 px each
        data_h = 20.0
        title_h = h - 3 * data_h
        title_y = r.top() + title_h
        # Dividers
        p.setPen(QPen(border, 0.9))
        p.drawLine(int(r.left()), int(title_y), int(r.right()), int(title_y))
        for i in (1, 2):
            y = title_y + data_h * i
            p.drawLine(int(r.left()), int(y), int(r.right()), int(y))

        # Title row — word-wrap so the full name is always visible
        title_rect = QRectF(r.left() + 2, r.top(), r.width() - 4, title_h)
        p.setPen(QPen(text_color))
        p.setFont(self._font(8, True))
        p.drawText(title_rect, Qt.AlignCenter | Qt.AlignVCenter | Qt.TextWordWrap,
                   f"{vt.name} ({vt.code})")

        # Data rows
        data_rows = [
            f"ACCR  {vt.accr:.4f}",
            f"Case/Yr  {self._fmt_e(vt.acc_per_yr)}",
            f"RY  {self._fmt_ret(vt.return_yr)}",
        ]
        p.setFont(self._font(8, False))
        for idx, text in enumerate(data_rows):
            rr = QRectF(r.left(), title_y + data_h * idx, r.width(), data_h)
            p.setPen(QPen(text_color))
            p.drawText(rr, Qt.AlignCenter, text)

    def _fire_box(self, p: QPainter, cx: float, cy: float, w: float, h: float, vt: VehicleType, ft: VehicleFireType):
        r = QRectF(cx - w / 2, cy - h / 2, w, h)
        fill = QColor("#F5EEF8")
        border = QColor("#8E44AD")
        text_color = QColor("#6C3483")

        p.setBrush(QBrush(fill))
        p.setPen(QPen(border, 0.9))
        p.drawRoundedRect(r, 3, 3)

        # Title row gets the remaining height after 3 data rows of 20 px each
        data_h = 20.0
        title_h = h - 3 * data_h
        title_y = r.top() + title_h
        # Dividers
        p.setPen(QPen(border, 0.9))
        p.drawLine(int(r.left()), int(title_y), int(r.right()), int(title_y))
        for i in (1, 2):
            y = title_y + data_h * i
            p.drawLine(int(r.left()), int(y), int(r.right()), int(y))

        metrics = self._fire_node_metrics(vt, ft)

        # Title row — keep the embedded newline so Qt word-wraps at the right place
        title_rect = QRectF(r.left() + 2, r.top(), r.width() - 4, title_h)
        p.setPen(QPen(text_color))
        p.setFont(self._font(8, True))
        p.drawText(title_rect, Qt.AlignCenter | Qt.AlignVCenter | Qt.TextWordWrap,
                   ft.label)

        # Data rows
        data_rows = [
            f"ACC  {metrics['acc']:.4f}",
            f"Case/Yr  {self._fmt_e(metrics['freq_per_yr'])}",
            f"RY  {self._fmt_ret(metrics['return_yr'])}",
        ]
        p.setFont(self._font(8, False))
        for idx, text in enumerate(data_rows):
            rr = QRectF(r.left(), title_y + data_h * idx, r.width(), data_h)
            p.setPen(QPen(text_color))
            p.drawText(rr, Qt.AlignCenter, text)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#F8F9FA"))

        headers = [
            ("All Types", "total"),
            ("Vehicle Type", "vehicle"),
            ("Severity", "severity"),
            ("Fire Size", "fire"),
            ("Traffic", "branch"),
            ("Scenario", "scenario"),
            ("Frequency\nper Yr", "freq_yr"),
            ("Return\nYear", "return_yr"),
            ("Frequency\n/yrVeh-km", "freq_vkm"),
        ]
        for text, key in headers:
            cx = self.CX[key]
            w = self.COL_W[key]
            r = QRectF(cx - w / 2, 2, w, self.HEADER_H - 4)
            p.fillRect(r, QColor("#2980B9"))
            p.setPen(QPen(QColor("white")))
            p.setFont(self._font(8, True))
            p.drawText(r, Qt.AlignCenter | Qt.TextWordWrap, text)

        all_y = [x["y"] for x in self._leaves]
        if not all_y:
            p.end()
            return

        total_cy = (min(all_y) + max(all_y)) / 2.0
        self._box(p, self.CX["total"], total_cy, self.COL_W["total"] - 4, self.BOX_H * 2,
                  "All\nTypes", QColor("#D5E8F8"), QColor("#2980B9"), QColor("#1A5276"), True, 9)
        fire_node_centers: Dict[tuple[str, int], float] = {}
        alias_lane_x = {
            ("GV", 20): self.CX["vehicle"] + self.COL_W["vehicle"] / 2 + 26,
            ("ST", 30): self.CX["vehicle"] + self.COL_W["vehicle"] / 2 + 52,
        }

        for vt in self._data:
            vt_leaves = [x for x in self._leaves if x.get("vt") is vt]
            vt_cy = self._mid(vt_leaves)

            mx = self._connector(
                p,
                self.CX["total"] + self.COL_W["total"] / 2,
                total_cy,
                self.CX["vehicle"] - self.COL_W["vehicle"] / 2,
                vt_cy,
                QColor("#2980B9"),
            )

            self._vehicle_box(p, self.CX["vehicle"], vt_cy, self.COL_W["vehicle"] - 4, self.VEHICLE_BOX_H, vt)

            ns_leaves = [x for x in vt_leaves if x["kind"] == "not_serious"]
            branch_leaves = [x for x in vt_leaves if x["kind"] == "branch"]
            if ns_leaves:
                ns_cy = ns_leaves[0]["y"]
                mx = self._connector(
                    p,
                    self.CX["vehicle"] + self.COL_W["vehicle"] / 2,
                    vt_cy,
                    self.CX["severity"] - self.COL_W["severity"] / 2,
                    ns_cy,
                    QColor("#27AE60"),
                )
                self._draw_percent_label(p, self._fmt_pct(vt.not_serious_prob * 100), mx, (vt_cy + ns_cy) / 2.0, QColor("#1E8449"))

                self._box(
                    p,
                    self.CX["severity"],
                    ns_cy,
                    self.COL_W["severity"] - 4,
                    self.BOX_H,
                    "Not Serious",
                    QColor("#E8F8F5"),
                    QColor("#27AE60"),
                    QColor("#1E8449"),
                )

                ns_traffic = vt.accr * vt.not_serious_prob
                self._connector(
                    p,
                    self.CX["severity"] + self.COL_W["severity"] / 2,
                    ns_cy,
                    self.CX["branch"] - self.COL_W["branch"] / 2,
                    ns_cy,
                    QColor("#27AE60"),
                )
                self._box(
                    p,
                    self.CX["branch"],
                    ns_cy,
                    self.COL_W["branch"] - 4,
                    self.BOX_H,
                    f"{ns_traffic:.4f}",
                    QColor("#D5F5E3"),
                    QColor("#27AE60"),
                    QColor("#1E8449"),
                )

                self._connector(
                    p,
                    self.CX["branch"] + self.COL_W["branch"] / 2,
                    ns_cy,
                    self.CX["scenario"] - self.COL_W["scenario"] / 2,
                    ns_cy,
                    QColor("#27AE60"),
                )
                self._box(
                    p,
                    self.CX["scenario"],
                    ns_cy,
                    self.COL_W["scenario"] - 4,
                    self.BOX_H,
                    vt.not_serious_id,
                    QColor("#D5F5E3"),
                    QColor("#27AE60"),
                    QColor("#1E8449"),
                    True,
                )

                for col, value in (
                    ("freq_yr", self._fmt_e(vt.not_serious_freq_yr)),
                    ("return_yr", self._fmt_ret(vt.not_serious_return_yr)),
                    ("freq_vkm", self._fmt_e(vt.not_serious_freq_veh_km)),
                ):
                    p.setPen(QPen(QColor("#2C3E50")))
                    p.setFont(self._font(8))
                    p.drawText(
                        QRectF(self.CX[col] - self.COL_W[col] / 2, ns_cy - self.BOX_H / 2, self.COL_W[col], self.BOX_H),
                        Qt.AlignCenter,
                        value,
                    )

            if not branch_leaves:
                continue

            # Count fire-size paths from the vehicle (including alias-linked ones).
            fire_split_count = len(vt.fire_types)
            serious_centers: List[float] = []
            for ft in vt.fire_types:
                ft_branches = [x for x in branch_leaves if x.get("ft") is ft]
                if ft_branches:
                    serious_centers.append(self._mid(ft_branches))

            # Show the Serious trunk split only when there are multiple downstream paths
            # and the split is meaningful (avoid showing 100%).
            if fire_split_count > 1 and 0.0 < vt.serious_prob < 1.0 and serious_centers:
                serious_cy = (min(serious_centers) + max(serious_centers)) / 2.0
                serious_label_x = self.CX["vehicle"] + self.COL_W["vehicle"] / 2 + 26
                serious_label_y = (vt_cy + serious_cy) / 2.0 + 8
                self._draw_percent_label(
                    p,
                    self._fmt_pct(vt.serious_prob * 100, 2),
                    serious_label_x,
                    serious_label_y,
                    QColor("#6C3483"),
                )

            for ft in vt.fire_types:
                if ft.alias_to is not None:
                    target_cy = fire_node_centers.get(ft.alias_to)
                    if target_cy is None:
                        continue
                    target_y = target_cy + (self.FIRE_BOX_H * 0.24)
                    lane_x = alias_lane_x.get((vt.code, ft.hrr_mw), self.CX["vehicle"] + self.COL_W["vehicle"] / 2 + 38)
                    mx = self._connector_routed(
                        p,
                        self.CX["vehicle"] + self.COL_W["vehicle"] / 2,
                        vt_cy,
                        self.CX["fire"] - self.COL_W["fire"] / 2,
                        target_y,
                        QColor("#8E44AD"),
                        lane_x,
                    )
                    # Single-fire vehicles should display the Serious split (e.g., 15%),
                    # while multi-fire vehicles display fire-group split (e.g., 95/5).
                    split_pct = (vt.serious_prob * 100.0) if fire_split_count == 1 else (ft.probability * 100.0)
                    self._draw_percent_label(p, self._fmt_pct(split_pct, 2), mx, (vt_cy + target_y) / 2.0, QColor("#6C3483"))
                    continue

                ft_branches = [x for x in branch_leaves if x.get("ft") is ft]
                if not ft_branches:
                    continue
                ft_cy = self._mid(ft_branches)
                ft_metrics = self._fire_node_metrics(vt, ft)
                if ft.hrr_mw is not None:
                    fire_node_centers[(vt.code, ft.hrr_mw)] = ft_cy

                mx = self._connector(
                    p,
                    self.CX["vehicle"] + self.COL_W["vehicle"] / 2,
                    vt_cy,
                    self.CX["fire"] - self.COL_W["fire"] / 2,
                    ft_cy,
                    QColor("#8E44AD"),
                )
                # Single-fire vehicles should display the Serious split (e.g., 15%),
                # while multi-fire vehicles display fire-group split (e.g., 95/5).
                split_pct = (vt.serious_prob * 100.0) if fire_split_count == 1 else (ft.probability * 100.0)
                self._draw_percent_label(p, self._fmt_pct(split_pct, 2), mx, (vt_cy + ft_cy) / 2.0, QColor("#6C3483"))

                self._box(
                    p,
                    self.CX["fire"],
                    ft_cy,
                    self.COL_W["fire"] - 4,
                    self.FIRE_BOX_H,
                    "",
                    QColor("#F5EEF8"),
                    QColor("#8E44AD"),
                    QColor("#6C3483"),
                )
                self._fire_box(p, self.CX["fire"], ft_cy, self.COL_W["fire"] - 4, self.FIRE_BOX_H, vt, ft)

                for br in (ft.normal, ft.congest):
                    if br is None:
                        continue
                    br_leaf = next((x for x in ft_branches if x.get("branch") is br), None)
                    if br_leaf is None:
                        continue
                    br_cy = br_leaf["y"]
                    br_color = QColor("#1565C0") if br.branch_label == "Normal" else QColor("#B71C1C")
                    br_fill = QColor("#E3F2FD") if br.branch_label == "Normal" else QColor("#FFEBEE")

                    mx = self._connector(
                        p,
                        self.CX["fire"] + self.COL_W["fire"] / 2,
                        ft_cy,
                        self.CX["branch"] - self.COL_W["branch"] / 2,
                        br_cy,
                        br_color,
                    )

                    self._box(
                        p,
                        self.CX["branch"],
                        br_cy,
                        self.COL_W["branch"] - 4,
                        self.BRANCH_BOX_H,
                        f"{br.branch_label}\n{br.probability:.4f}",
                        br_fill,
                        br_color,
                        br_color,
                        True,
                    )

                    self._connector(
                        p,
                        self.CX["branch"] + self.COL_W["branch"] / 2,
                        br_cy,
                        self.CX["scenario"] - self.COL_W["scenario"] / 2,
                        br_cy,
                        br_color,
                    )

                    self._box(
                        p,
                        self.CX["scenario"],
                        br_cy,
                        self.COL_W["scenario"] - 4,
                        self.BOX_H,
                        br.scenario_id,
                        QColor("#FDFEFE"),
                        QColor("#7F8C8D"),
                        QColor("#2C3E50"),
                        True,
                    )

                    for col, value in (
                        ("freq_yr", self._fmt_e(br.freq_per_yr)),
                        ("return_yr", self._fmt_ret(br.return_yr)),
                        ("freq_vkm", self._fmt_e(br.freq_veh_km)),
                    ):
                        p.setPen(QPen(QColor("#2C3E50")))
                        p.setFont(self._font(8))
                        p.drawText(
                            QRectF(self.CX[col] - self.COL_W[col] / 2, br_cy - self.BOX_H / 2, self.COL_W[col], self.BOX_H),
                            Qt.AlignCenter,
                            value,
                        )

        p.end()

    def sizeHint(self):
        return QSize(self.minimumWidth(), self.minimumHeight())


class DiagramGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setAlignment(Qt.AlignCenter)
        self.setBackgroundBrush(QColor("white"))
        self.setFrameShape(QFrame.NoFrame)

    def wheelEvent(self, event):
        zoom_in = 1.15
        zoom_out = 1.0 / zoom_in
        factor = zoom_in if event.angleDelta().y() > 0 else zoom_out
        self.scale(factor, factor)


class DiagramViewerWindow(QWidget):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Heirachy Diagram")
        self.resize(1200, 800)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.addStretch(1)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(
            "QPushButton{background:#7f8c8d;color:white;font-weight:bold;border-radius:3px;padding:4px 12px;}"
            "QPushButton:hover{background:#6c7a7d;}"
        )
        top.addWidget(btn_close)
        root.addLayout(top)

        self._scene = QGraphicsScene(self)
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self._view = DiagramGraphicsView(self)
        self._view.setScene(self._scene)
        root.addWidget(self._view, 1)

        btn_close.clicked.connect(self.close)
        self._fit_to_window()

    def _fit_to_window(self):
        self._view.resetTransform()
        self._view.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)


class ScenarioDetailTable(QTableWidget):
    HEADERS = [
        "Scenario ID",
        "Smoke",
        "Frequency/Yr",
        "Return Year",
        "Freq /yrVeh-km",
        "P1",
        "P2",
        "P3",
        "P4",
        "P5",
        "P6",
    ]

    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setStretchLastSection(False)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setStyleSheet(
            "QTableWidget { font-size: 10px; }"
            "QHeaderView::section { background: #2980b9; color: white; font-weight: bold; padding: 4px; border: none; }"
        )

    def min_height_for_rows(self, row_count: int) -> int:
        # Header + N body rows + table frame
        return (
            self.horizontalHeader().height()
            + self.verticalHeader().defaultSectionSize() * max(1, row_count)
            + self.frameWidth() * 2
        )

    def _ci(self, value, bg=None, bold=False, align=Qt.AlignCenter):
        item = QTableWidgetItem(str(value))
        item.setTextAlignment(align)
        if bg is not None:
            item.setBackground(bg)
        if bold:
            f = item.font()
            f.setBold(True)
            item.setFont(f)
        return item

    def _fmt(self, v: float) -> str:
        if v == 0:
            return "0.0000"
        return f"{v:.4E}"

    def repopulate(self, data: List[VehicleType]):
        self.setRowCount(0)
        row = 0
        smoke_colors = {
            "NNVC": QColor("#E8F5E9"),
            "NNV0": QColor("#C8E6C9"),
            "NFV0": QColor("#FFF9C4"),
            "NFVM": QColor("#FFF176"),
            "NFVP": QColor("#FFEE58"),
            "CNVC": QColor("#E3F2FD"),
            "CNV0": QColor("#BBDEFB"),
            "CFV0": QColor("#FCE4EC"),
            "CFVM": QColor("#F8BBD0"),
            "CFVP": QColor("#F48FB1"),
        }

        for vt in data:
            if vt.not_serious_prob > 0.0:
                self.insertRow(row)
                bg = QColor("#F5F5F5")
                self.setItem(row, 0, self._ci(vt.not_serious_id, bg, True))
                self.setItem(row, 1, self._ci("Not Serious", bg))
                self.setItem(row, 2, self._ci(self._fmt(vt.not_serious_freq_yr), bg))
                self.setItem(row, 3, self._ci(f"{vt.not_serious_return_yr:.4f}" if vt.not_serious_return_yr > 0 else "-", bg))
                self.setItem(row, 4, self._ci(self._fmt(vt.not_serious_freq_veh_km), bg))
                for i in range(6):
                    self.setItem(row, 5 + i, self._ci("0.0000", bg))
                row += 1

            for ft in vt.fire_types:
                for br in (ft.normal, ft.congest):
                    if br is None:
                        continue
                    grouped: List[List[SubScenario]] = []
                    for ss in br.sub_scenarios:
                        if not grouped or grouped[-1][0].scenario_id != ss.scenario_id:
                            grouped.append([ss])
                        else:
                            grouped[-1].append(ss)

                    for ss_group in grouped:
                        group_start_row = row
                        for idx_in_group, ss in enumerate(ss_group):
                            self.insertRow(row)
                            bg = smoke_colors.get(ss.smoke_control, QColor("white"))
                            # Scenario ID is a parent row label; smoke controls are sub-rows beneath it.
                            sid_text = ss.scenario_id if idx_in_group == 0 else ""
                            self.setItem(row, 0, self._ci(sid_text, bg, True))
                            self.setItem(row, 1, self._ci(ss.smoke_control, bg))
                            self.setItem(row, 2, self._ci(self._fmt(ss.freq_per_yr), bg))
                            self.setItem(row, 3, self._ci(f"{ss.return_yr:.4f}" if ss.return_yr > 0 else "-", bg))
                            self.setItem(row, 4, self._ci(self._fmt(ss.freq_veh_km), bg))
                            for fidx, fv in enumerate(ss.fatalities):
                                hi = fv > 0
                                cell_bg = QColor("#FFCDD2") if hi else bg
                                self.setItem(row, 5 + fidx, self._ci(f"{fv:.4f}" if hi else "0.0000", cell_bg, hi))
                            row += 1

                        if len(ss_group) > 1:
                            self.setSpan(group_start_row, 0, len(ss_group), 1)


class ScenarioSummaryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setSpacing(6)

    def repopulate(self, data: List[VehicleType]):
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        hdr_style = "font-weight:bold;font-size:11px;color:white;background:#2980b9;padding:3px 6px;border-radius:2px;"
        row_style = "font-size:11px;padding:3px 6px;"

        headers = ["Vehicle Type", "ACCR /10^8 veh-km", "Accidents per Year", "Return Year"]
        for col, text in enumerate(headers):
            lbl = QLabel(text)
            lbl.setStyleSheet(hdr_style)
            lbl.setAlignment(Qt.AlignCenter)
            self._layout.addWidget(lbl, 0, col)

        row = 1
        for vt in data:
            values = [vt.name, f"{vt.accr:.4f}", f"{vt.acc_per_yr:.4f}", f"{vt.return_yr:.4f}" if vt.return_yr > 0 else "-"]
            for col, value in enumerate(values):
                lbl = QLabel(value)
                lbl.setStyleSheet(row_style)
                lbl.setAlignment(Qt.AlignCenter)
                self._layout.addWidget(lbl, row, col)
            row += 1

        total_accr = sum(vt.accr * vt.share for vt in data)
        total_acc_yr = sum(vt.acc_per_yr for vt in data)
        totals = ["Total", f"{total_accr:.4f}", f"{total_acc_yr:.4f}", "-"]
        for col, value in enumerate(totals):
            lbl = QLabel(value)
            lbl.setStyleSheet("font-weight:bold;font-size:11px;color:#c0392b;padding:3px 6px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._layout.addWidget(lbl, row, col)

        self._layout.setColumnStretch(0, 2)
        for c in range(1, 4):
            self._layout.setColumnStretch(c, 1)


class StandardScenarioWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = _build_standard_scenario_data()
        self._fire_size_factors = FireSizeWorkbookFactors.from_workbook(Path(__file__).with_name("FNCV_ROAD.xlsm"))
        self._delay_frequency = 0.01
        self._viewer_window: Optional[DiagramViewerWindow] = None
        self._coeff: Dict[str, Dict[int, float]] = {}
        self._controls: Dict[str, Dict[int, QDoubleSpinBox]] = {}
        self._syncing_fire_groups = False
        self._capture_reference_coefficients()
        self._build_ui()
        self._refresh_views()

    def set_fire_size_factors_from_tunnel(self, factor_payload: Dict[str, object]):
        """Update fire-size factors from Tunnel Traffic pre-calculated values.

        Expected payload keys: base, vk_pc, vk_hrr{10,20,30,100}, lfr{10,20,30,100}
        """
        if not isinstance(factor_payload, dict):
            return

        try:
            base = float(factor_payload.get("base", self._fire_size_factors.base))
            vk_pc = float(factor_payload.get("vk_pc", self._fire_size_factors.vk_pc))

            src_vk_hrr = factor_payload.get("vk_hrr") or {}
            src_vk_named = factor_payload.get("vk_named") or {}
            src_lfr = factor_payload.get("lfr") or {}

            vk_hrr = {
                10: float(src_vk_hrr.get(10, src_vk_hrr.get("10", src_vk_named.get("VK.HRR010", self._fire_size_factors.vk_hrr[10])))),
                20: float(src_vk_hrr.get(20, src_vk_hrr.get("20", src_vk_named.get("VK.HRR020", self._fire_size_factors.vk_hrr[20])))),
                30: float(src_vk_hrr.get(30, src_vk_hrr.get("30", src_vk_named.get("VK.HRR030", self._fire_size_factors.vk_hrr[30])))),
                100: float(src_vk_hrr.get(100, src_vk_hrr.get("100", src_vk_named.get("VK.HRR100", self._fire_size_factors.vk_hrr[100])))),
            }
            lfr = {
                10: float(src_lfr.get(10, src_lfr.get("10", self._fire_size_factors.lfr[10]))),
                20: float(src_lfr.get(20, src_lfr.get("20", self._fire_size_factors.lfr[20]))),
                30: float(src_lfr.get(30, src_lfr.get("30", self._fire_size_factors.lfr[30]))),
                100: float(src_lfr.get(100, src_lfr.get("100", self._fire_size_factors.lfr[100]))),
            }

            # Smoke control probabilities — accept from payload, else preserve existing.
            src_smoke = factor_payload.get("smoke_probs") or {}
            _smoke = dict(src_smoke) if src_smoke else dict(self._fire_size_factors.smoke_probs)

            self._fire_size_factors = FireSizeWorkbookFactors(
                base=base,
                vk_pc=vk_pc,
                vk_hrr=vk_hrr,
                lfr=lfr,
                smoke_probs=_smoke,
            )

            # Delay Frequency from Tunnel Traffic Volume tab (e.g. D22 / 지체빈도)
            _df = factor_payload.get("delay_frequency", None)
            if _df is None:
                nv = factor_payload.get("named_values") or {}
                for _k in ("DELAY.FREQUENCY", "DELAY_FREQUENCY", "지체빈도", "정체빈도"):
                    if _k in nv:
                        _df = nv.get(_k)
                        break
            if _df is not None:
                _df_val = float(_df)
                if _df_val > 1.0:
                    _df_val = _df_val / 100.0
                self._delay_frequency = max(0.0, min(1.0, _df_val))

            if hasattr(self, "_diagram") and self._diagram is not None:
                self._diagram._fire_size_factors = self._fire_size_factors

            # Recalculate with current controls so Case/Yr tracks new BASE/VK/LFR factors.
            self._apply_controls_and_recalculate()
        except Exception:
            return

    def _case_per_year_factor(self, vt: VehicleType) -> float:
        """Case/Yr per ACCR based on workbook equations.

        PC  = ACCR * VK.PC     / BASE
        BUS = ACCR * VK.HRR020 / BASE
        GV  = ACCR * VK.HRR030 / BASE
        ST  = ACCR * VK.HRR100 / BASE
        """
        base = self._fire_size_factors.base
        if base > 0.0:
            if vt.code == "PC":
                return self._fire_size_factors.vk_pc / base
            if vt.code == "BUS":
                return self._fire_size_factors.vk_hrr.get(20, 0.0) / base
            if vt.code == "GV":
                return self._fire_size_factors.vk_hrr.get(30, 0.0) / base
            if vt.code == "ST":
                return self._fire_size_factors.vk_hrr.get(100, 0.0) / base
        return self._coeff["vt_accyr_per_accr"].get(id(vt), 0.0)

    def _sync_fire_group_partner(self, vt_id: int, source_group: str, value: float):
        """Keep Fire Group 1/2 controls complementary (sum to 100)."""
        if self._syncing_fire_groups:
            return
        if vt_id not in self._controls.get("fire_1", {}) or vt_id not in self._controls.get("fire_2", {}):
            return

        v = max(0.0, min(100.0, float(value)))
        partner_value = max(0.0, min(100.0, 100.0 - v))
        partner = self._controls["fire_2"][vt_id] if source_group == "fire_1" else self._controls["fire_1"][vt_id]

        self._syncing_fire_groups = True
        try:
            partner.blockSignals(True)
            partner.setValue(partner_value)
            partner.blockSignals(False)
        finally:
            self._syncing_fire_groups = False

    def _capture_reference_coefficients(self):
        self._coeff = {
            "vt_accyr_per_accr": {},
            "vt_ns_vehkm_factor": {},
            "ft_branch_normal_ratio": {},
            "branch_vehkm_factor": {},
            "sub_weight": {},
            "sub_vehkm_factor": {},
        }

        for vt in self._data:
            acc_factor = (vt.acc_per_yr / vt.accr) if vt.accr > 0 else 0.0
            self._coeff["vt_accyr_per_accr"][id(vt)] = acc_factor
            ns_factor = (vt.not_serious_freq_veh_km / vt.not_serious_freq_yr) if vt.not_serious_freq_yr > 0 else 0.0
            self._coeff["vt_ns_vehkm_factor"][id(vt)] = ns_factor
            for ft in vt.fire_types:
                n = ft.normal.freq_per_yr if ft.normal else 0.0
                c = ft.congest.freq_per_yr if ft.congest else 0.0
                total = n + c
                nr = (n / total) if total > 0 else 0.99
                self._coeff["ft_branch_normal_ratio"][id(ft)] = nr

                for br in (ft.normal, ft.congest):
                    if br is None:
                        continue
                    b_factor = (br.freq_veh_km / br.freq_per_yr) if br.freq_per_yr > 0 else 0.0
                    self._coeff["branch_vehkm_factor"][id(br)] = b_factor
                    for ss in br.sub_scenarios:
                        w = (ss.freq_per_yr / br.freq_per_yr) if br.freq_per_yr > 0 else (1.0 / len(br.sub_scenarios))
                        k = (ss.freq_veh_km / ss.freq_per_yr) if ss.freq_per_yr > 0 else 0.0
                        self._coeff["sub_weight"][id(ss)] = w
                        self._coeff["sub_vehkm_factor"][id(ss)] = k

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        title_row = QHBoxLayout()
        title = QLabel("Standard Scenario - FNCV_ROAD.xlsm Replica")
        title.setStyleSheet(
            "font-size:13px;font-weight:bold;color:#1a5276;padding:4px 8px;background:#d5e8f8;border-radius:4px;"
        )
        title_row.addWidget(title, 1)

        btn_recalc = QPushButton("Recalculate")
        btn_recalc.setStyleSheet(
            "QPushButton{background:#1f78b4;color:white;font-weight:bold;border-radius:3px;padding:4px 10px;}"
            "QPushButton:hover{background:#16618f;}"
        )
        btn_recalc.clicked.connect(self._apply_controls_and_recalculate)
        title_row.addWidget(btn_recalc)

        btn_reset = QPushButton("Reset Defaults")
        btn_reset.setStyleSheet(
            "QPushButton{background:#7f8c8d;color:white;font-weight:bold;border-radius:3px;padding:4px 10px;}"
            "QPushButton:hover{background:#6c7a7d;}"
        )
        btn_reset.clicked.connect(self._reset_defaults)
        title_row.addWidget(btn_reset)
        root.addLayout(title_row)

        root.addWidget(self._build_editable_panel())

        action_row = QHBoxLayout()
        action_row.addStretch(1)

        btn_view = QPushButton("View Diagram")
        btn_view.setStyleSheet(
            "QPushButton{background:#16a085;color:white;font-weight:bold;border-radius:3px;padding:4px 10px;}"
            "QPushButton:hover{background:#138d75;}"
        )
        btn_view.clicked.connect(self._open_diagram_viewer)
        action_row.addWidget(btn_view)

        btn_export = QToolButton()
        btn_export.setText("Export Diagram")
        btn_export.setPopupMode(QToolButton.InstantPopup)
        btn_export.setStyleSheet(
            "QToolButton{background:#8e44ad;color:white;font-weight:bold;border-radius:3px;padding:4px 10px;}"
            "QToolButton:hover{background:#7d3c98;}"
            "QToolButton::menu-indicator{subcontrol-origin:padding;subcontrol-position:right center;}"
        )
        export_menu = QMenu(btn_export)
        export_menu.addAction("Download PDF", lambda: self._export_diagram("pdf"))
        export_menu.addAction("Download Picture", lambda: self._export_diagram("png"))
        export_menu.addAction("Download Excel", lambda: self._export_diagram("xlsx"))
        btn_export.setMenu(export_menu)
        action_row.addWidget(btn_export)

        root.addLayout(action_row)

        splitter = QSplitter(Qt.Vertical)

        tree_scroll = QScrollArea()
        tree_scroll.setWidgetResizable(True)
        tree_scroll.setStyleSheet("QScrollArea{border:1px solid #bdc3c7;}")
        self._diagram = EventTreeDiagram(self._data, self._fire_size_factors)
        tree_scroll.setWidget(self._diagram)
        tree_scroll.setMinimumHeight(380)
        splitter.addWidget(tree_scroll)

        detail_frame = QFrame()
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(2, 2, 2, 2)
        detail_hdr = QLabel("Scenario Detail Table")
        detail_hdr.setStyleSheet(
            "font-size:11px;font-weight:bold;color:#2c3e50;padding:3px 6px;background:#ecf0f1;border-radius:2px;"
        )
        detail_layout.addWidget(detail_hdr)
        self._detail_tbl = ScenarioDetailTable()
        min_table_h = self._detail_tbl.min_height_for_rows(8)
        self._detail_tbl.setMinimumHeight(min_table_h)
        detail_layout.addWidget(self._detail_tbl, 1)
        detail_frame.setMinimumHeight(min_table_h + detail_hdr.sizeHint().height() + 12)
        splitter.addWidget(detail_frame)

        splitter.setSizes([440, 560])
        root.addWidget(splitter, 1)

        summary_frame = QFrame()
        summary_frame.setStyleSheet("QFrame{background:#f8f9fa;border-radius:3px;}")
        summary_layout = QVBoxLayout(summary_frame)
        summary_layout.setContentsMargins(4, 4, 4, 4)
        summary_hdr = QLabel("Overall Accident Rate Summary")
        summary_hdr.setStyleSheet("font-size:11px;font-weight:bold;color:#2c3e50;padding:2px 4px;border-bottom:1px solid #dee2e6;")
        summary_layout.addWidget(summary_hdr)
        self._summary = ScenarioSummaryWidget()
        summary_layout.addWidget(self._summary)
        root.addWidget(summary_frame)

    def _render_diagram_pixmap(self, scale: float = 1.0) -> Optional[QPixmap]:
        if not hasattr(self, "_diagram") or self._diagram is None:
            return None

        self._diagram.update()
        self._diagram.repaint()
        w = max(1, int(self._diagram.width() * scale))
        h = max(1, int(self._diagram.height() * scale))

        pixmap = QPixmap(w, h)
        pixmap.fill(Qt.white)
        painter = QPainter(pixmap)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        if scale != 1.0:
            painter.scale(scale, scale)
        self._diagram.render(painter)
        painter.end()
        return pixmap

    def _open_diagram_viewer(self):
        pixmap = self._render_diagram_pixmap(scale=2.0)
        if pixmap is None:
            QMessageBox.warning(self, "View Diagram", "Unable to render the hierarchy diagram.")
            return

        self._viewer_window = DiagramViewerWindow(pixmap, self)
        self._viewer_window.show()
        self._viewer_window.raise_()
        self._viewer_window.activateWindow()

    def _export_diagram(self, export_format: str):
        format_map = {
            "png": ("hierarchy_diagram.png", "PNG Image (*.png)", ".png"),
            "pdf": ("hierarchy_diagram.pdf", "PDF File (*.pdf)", ".pdf"),
            "xlsx": ("hierarchy_diagram.xlsx", "Excel Workbook (*.xlsx)", ".xlsx"),
        }
        default_name, file_filter, ext = format_map.get(export_format, format_map["png"])
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Hierarchy Diagram",
            default_name,
            file_filter,
        )
        if not file_path:
            return

        chosen_ext = Path(file_path).suffix.lower()
        if not chosen_ext:
            file_path += ext
            chosen_ext = ext

        pixmap = self._render_diagram_pixmap(scale=3.0)
        if pixmap is None:
            QMessageBox.warning(self, "Export Diagram", "Unable to render the hierarchy diagram.")
            return

        if chosen_ext == ".pdf":
            ok = self._export_pixmap_pdf(file_path, pixmap)
        elif chosen_ext == ".xlsx":
            ok = self._export_pixmap_excel(file_path, pixmap)
        else:
            ok = pixmap.save(file_path, "PNG")

        if ok:
            QMessageBox.information(self, "Export Diagram", f"Diagram exported successfully:\n{file_path}")
        else:
            QMessageBox.warning(self, "Export Diagram", "Export failed. Please try again.")

    def _export_pixmap_pdf(self, file_path: str, pixmap: QPixmap) -> bool:
        try:
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(file_path)
            printer.setOrientation(QPrinter.Landscape)

            painter = QPainter(printer)
            target = printer.pageRect()
            if target.width() <= 0 or target.height() <= 0:
                painter.end()
                return False

            scale = min(target.width() / pixmap.width(), target.height() / pixmap.height())
            draw_w = int(pixmap.width() * scale)
            draw_h = int(pixmap.height() * scale)
            x = int((target.width() - draw_w) / 2)
            y = int((target.height() - draw_h) / 2)
            painter.drawPixmap(x, y, draw_w, draw_h, pixmap)
            painter.end()
            return True
        except Exception:
            return False

    def _export_pixmap_excel(self, file_path: str, pixmap: QPixmap) -> bool:
        try:
            openpyxl_mod = importlib.import_module("openpyxl")
            xl_image_mod = importlib.import_module("openpyxl.drawing.image")
            Workbook = openpyxl_mod.Workbook
            XLImage = xl_image_mod.Image
        except Exception:
            QMessageBox.warning(
                self,
                "Export Diagram",
                "Excel export requires openpyxl. Install it with: pip install openpyxl",
            )
            return False

        tmp_path = ""
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)

            if not pixmap.save(tmp_path, "PNG"):
                return False

            wb = Workbook()
            ws = wb.active
            ws.title = "Hierarchy Diagram"

            image = XLImage(tmp_path)
            image.anchor = "B2"
            ws.add_image(image)
            ws.column_dimensions["A"].width = 4
            ws.column_dimensions["B"].width = 24
            ws.row_dimensions[1].height = 12
            wb.save(file_path)
            return True
        except Exception:
            return False
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _copy_sub_scenario(self, dst: SubScenario, src: SubScenario):
        dst.scenario_id = src.scenario_id
        dst.smoke_control = src.smoke_control
        dst.freq_per_yr = src.freq_per_yr
        dst.return_yr = src.return_yr
        dst.freq_veh_km = src.freq_veh_km
        dst.fatalities = list(src.fatalities)
        dst.vehicle_type = src.vehicle_type
        dst.traffic = src.traffic
        dst.ventilation = src.ventilation
        dst.wind = src.wind

    def _copy_fire_scenario(self, dst: FireScenario, src: FireScenario):
        dst.branch_label = src.branch_label
        dst.scenario_id = src.scenario_id
        dst.probability = src.probability
        dst.freq_per_yr = src.freq_per_yr
        dst.return_yr = src.return_yr
        dst.freq_veh_km = src.freq_veh_km
        if len(dst.sub_scenarios) == len(src.sub_scenarios):
            for dss, sss in zip(dst.sub_scenarios, src.sub_scenarios):
                self._copy_sub_scenario(dss, sss)

    def _copy_vehicle_fire_type(self, dst: VehicleFireType, src: VehicleFireType):
        dst.label = src.label
        dst.probability = src.probability
        if dst.normal and src.normal:
            self._copy_fire_scenario(dst.normal, src.normal)
        if dst.congest and src.congest:
            self._copy_fire_scenario(dst.congest, src.congest)

    def _copy_vehicle_type(self, dst: VehicleType, src: VehicleType):
        dst.name = src.name
        dst.code = src.code
        dst.share = src.share
        dst.accr = src.accr
        dst.acc_per_yr = src.acc_per_yr
        dst.return_yr = src.return_yr
        dst.not_serious_prob = src.not_serious_prob
        dst.not_serious_id = src.not_serious_id
        dst.not_serious_freq_yr = src.not_serious_freq_yr
        dst.not_serious_return_yr = src.not_serious_return_yr
        dst.not_serious_freq_veh_km = src.not_serious_freq_veh_km
        dst.serious_prob = src.serious_prob
        if len(dst.fire_types) == len(src.fire_types):
            for dft, sft in zip(dst.fire_types, src.fire_types):
                self._copy_vehicle_fire_type(dft, sft)

    def _sync_controls_from_data(self):
        for vt in self._data:
            vt_id = id(vt)
            if vt_id in self._controls["accr"]:
                self._controls["accr"][vt_id].setValue(vt.accr)
            if vt_id in self._controls["not_serious"]:
                self._controls["not_serious"][vt_id].setValue(vt.not_serious_prob * 100.0)

            fts = vt.fire_types
            if vt_id in self._controls["fire_1"]:
                self._controls["fire_1"][vt_id].setValue(fts[0].probability * 100.0 if len(fts) > 0 else 0.0)
            if vt_id in self._controls["fire_2"]:
                if len(fts) > 1:
                    self._controls["fire_2"][vt_id].setValue(fts[1].probability * 100.0)
                elif len(fts) == 1:
                    self._controls["fire_2"][vt_id].setValue(max(0.0, 100.0 - (fts[0].probability * 100.0)))
                else:
                    self._controls["fire_2"][vt_id].setValue(0.0)

    def _build_editable_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet("QFrame{background:#f7fbff;border:1px solid #dbe8f2;border-radius:4px;}")
        layout = QGridLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(4)

        headers = [
            "Vehicle",
            "ACCR",
            "Not Serious %",
            "Fire Group 1 %",
            "Fire Group 2 %",
        ]
        for c, text in enumerate(headers):
            h = QLabel(text)
            h.setStyleSheet("font-weight:bold;font-size:10px;color:#2c3e50;")
            layout.addWidget(h, 0, c)

        self._controls = {"accr": {}, "not_serious": {}, "fire_1": {}, "fire_2": {}}

        for r, vt in enumerate(self._data, start=1):
            layout.addWidget(QLabel(f"{vt.name} ({vt.code})"), r, 0)

            sp_accr = QDoubleSpinBox()
            sp_accr.setDecimals(4)
            sp_accr.setRange(0.0, 100.0)
            sp_accr.setSingleStep(0.01)
            sp_accr.setValue(vt.accr)
            layout.addWidget(sp_accr, r, 1)
            self._controls["accr"][id(vt)] = sp_accr

            sp_ns = QDoubleSpinBox()
            sp_ns.setDecimals(4)
            sp_ns.setRange(0.0, 100.0)
            sp_ns.setSingleStep(1.0)
            sp_ns.setValue(vt.not_serious_prob * 100.0)
            if vt.code in {"GV", "ST"}:
                sp_ns.setValue(0.0)
                sp_ns.setEnabled(False)
                sp_ns.setToolTip("Not Serious branch is disabled for GV/ST")
            layout.addWidget(sp_ns, r, 2)
            self._controls["not_serious"][id(vt)] = sp_ns

            fts = vt.fire_types
            sp_f1 = QDoubleSpinBox()
            sp_f1.setDecimals(4)
            sp_f1.setRange(0.0, 100.0)
            sp_f1.setSingleStep(1.0)
            sp_f1.setValue(fts[0].probability * 100.0 if len(fts) > 0 else 0.0)
            layout.addWidget(sp_f1, r, 3)
            self._controls["fire_1"][id(vt)] = sp_f1

            sp_f2 = QDoubleSpinBox()
            sp_f2.setDecimals(4)
            sp_f2.setRange(0.0, 100.0)
            sp_f2.setSingleStep(1.0)
            sp_f2.setValue(fts[1].probability * 100.0 if len(fts) > 1 else 0.0)
            sp_f2.setEnabled(len(fts) > 1)
            layout.addWidget(sp_f2, r, 4)
            self._controls["fire_2"][id(vt)] = sp_f2

            vt_id = id(vt)
            sp_f1.valueChanged.connect(lambda val, _vt_id=vt_id: self._sync_fire_group_partner(_vt_id, "fire_1", val))
            if len(fts) > 1:
                sp_f2.valueChanged.connect(lambda val, _vt_id=vt_id: self._sync_fire_group_partner(_vt_id, "fire_2", val))

        note = QLabel("References: ACCR and percentages are editable. Case/Yr, return year, and downstream frequencies are recalculated from worksheet-based reference factors.")
        note.setWordWrap(True)
        note.setStyleSheet("font-size:10px;color:#555;")
        layout.addWidget(note, len(self._data) + 1, 0, 1, len(headers))
        return panel

    def _apply_controls_and_recalculate(self):
        for vt in self._data:
            vt.accr = self._controls["accr"][id(vt)].value()
            acc_factor = self._case_per_year_factor(vt)
            vt.acc_per_yr = vt.accr * acc_factor
            vt.return_yr = _safe_return_year(vt.acc_per_yr)

            if vt.code in {"GV", "ST"}:
                ns = 0.0
            else:
                ns = self._controls["not_serious"][id(vt)].value() / 100.0
            vt.not_serious_prob = max(0.0, min(1.0, ns))
            vt.serious_prob = max(0.0, 1.0 - vt.not_serious_prob)

            f1 = self._controls["fire_1"][id(vt)].value() / 100.0
            f2 = self._controls["fire_2"][id(vt)].value() / 100.0 if len(vt.fire_types) > 1 else 0.0
            total_fire = f1 + f2
            if len(vt.fire_types) == 1:
                vt.fire_types[0].probability = max(0.0, min(1.0, f1))
                if id(vt) in self._controls.get("fire_2", {}):
                    self._controls["fire_2"][id(vt)].blockSignals(True)
                    self._controls["fire_2"][id(vt)].setValue(max(0.0, 100.0 - (vt.fire_types[0].probability * 100.0)))
                    self._controls["fire_2"][id(vt)].blockSignals(False)
            elif total_fire > 0:
                vt.fire_types[0].probability = f1 / total_fire
                vt.fire_types[1].probability = f2 / total_fire
            else:
                vt.fire_types[0].probability = 0.5
                vt.fire_types[1].probability = 0.5

            vt.not_serious_freq_yr = vt.acc_per_yr * vt.not_serious_prob
            vt.not_serious_return_yr = _safe_return_year(vt.not_serious_freq_yr)
            ns_denom = self._fire_size_factors.not_serious_denominator(vt.code)
            vt.not_serious_freq_veh_km = (vt.not_serious_freq_yr / ns_denom) if ns_denom > 0.0 else 0.0

            for ft in vt.fire_types:
                normal_ratio = max(0.0, min(1.0, 1.0 - self._delay_frequency))
                congest_ratio = max(0.0, min(1.0, self._delay_frequency))

                base = float(self._fire_size_factors.base) if self._fire_size_factors.base else 0.0
                vk20 = float(self._fire_size_factors.vk_hrr.get(20, 0.0))
                vk30 = float(self._fire_size_factors.vk_hrr.get(30, 0.0))
                vk100 = float(self._fire_size_factors.vk_hrr.get(100, 0.0))
                lfr20 = float(self._fire_size_factors.lfr.get(20, 0.0))
                lfr30 = float(self._fire_size_factors.lfr.get(30, 0.0))
                lfr100 = float(self._fire_size_factors.lfr.get(100, 0.0))

                def _vt_accr(code: str) -> float:
                    found = next((x for x in self._data if x.code == code), None)
                    return float(found.accr) if found is not None else 0.0

                if vt.code == "BUS" and ft.hrr_mw == 20 and base > 0.0:
                    # 20MW node formulas
                    ft_acc = vt.accr * lfr20 * ft.probability
                    vk30_dn = vk30 * (1.0 - lfr30)
                    total_fire_freq = ((vk20 / base) * ft_acc + (_vt_accr("GV") * vk30_dn / base)) * ft.probability
                elif vt.code == "GV" and ft.hrr_mw == 30 and base > 0.0:
                    # 30MW node: ft_acc = ACCR * LFR.030 (spreadsheet F42 = C42*LFR.030)
                    ft_acc = vt.accr * lfr30
                    vk100_dn = vk100 * (1.0 - lfr100)
                    # Case/Yr = VK.HRR030/BASE*F42 + C52*vk.hrr100.dn/BASE (spreadsheet F43)
                    total_fire_freq = (vk30 / base) * ft_acc + (_vt_accr("ST") * vk100_dn / base)
                elif vt.code == "ST" and ft.hrr_mw == 100 and base > 0.0:
                    # 100MW node formulas
                    ft_acc = vt.accr * ft.probability
                    total_fire_freq = (vk100 / base) * ft_acc
                elif ft.display_acc is not None:
                    ft_acc = float(ft.display_acc)
                    total_fire_freq = vt.acc_per_yr * vt.serious_prob * ft.probability
                elif vt.code == "PC":
                    ft_acc = vt.accr * ft.probability * self._fire_size_factors.lfr.get(10, 0.4)
                    # PC Case/Yr at 5MW/10MW uses node ACCR * (Tunnel Traffic D35 / BASE).
                    vk_pc = float(self._fire_size_factors.vk_pc)
                    total_fire_freq = ((vk_pc / base) * ft_acc) if base > 0.0 else 0.0
                else:
                    ft_acc = vt.accr * self._fire_size_factors.lfr.get(ft.hrr_mw or 0, 0.0)
                    total_fire_freq = vt.acc_per_yr * vt.serious_prob * ft.probability

                vk_denom = self._fire_size_factors.denominator_for_vehicle(vt.code)
                for br in (ft.normal, ft.congest):
                    if br is None:
                        continue
                    split = normal_ratio if br is ft.normal else congest_ratio
                    # Traffic node value (sheet style): fire-node ACCR split by delay frequency.
                    br.probability = ft_acc * split
                    br.freq_per_yr = total_fire_freq * split
                    br.return_yr = _safe_return_year(br.freq_per_yr)
                    # Spreadsheet: freq_veh_km = freq_per_yr / denominator
                    # PC→VK.PC, BUS→TOT.VK.HRR020, GV→TOT.VK.HRR030, ST→VK.HRR100
                    br.freq_veh_km = (br.freq_per_yr / vk_denom) if vk_denom > 0.0 else 0.0

                    for ss in br.sub_scenarios:
                        # Spreadsheet Q column: sub_freq = branch_K * NNVC/NNV0/NFF*WVx etc.
                        sp = self._fire_size_factors.smoke_probs.get(ss.smoke_control, 0.0)
                        ss.freq_per_yr = br.freq_per_yr * sp
                        ss.return_yr = _safe_return_year(ss.freq_per_yr)
                        ss.freq_veh_km = (ss.freq_per_yr / vk_denom) if vk_denom > 0.0 else 0.0

        self._refresh_views()

    def _refresh_views(self):
        self._diagram.refresh(self._data)
        self._detail_tbl.repopulate(self._data)
        self._summary.repopulate(self._data)

    def _reset_defaults(self):
        defaults = _build_standard_scenario_data()
        if len(self._data) == len(defaults):
            for dst_vt, src_vt in zip(self._data, defaults):
                self._copy_vehicle_type(dst_vt, src_vt)
        else:
            self._data = defaults
        self._capture_reference_coefficients()
        self._sync_controls_from_data()
        self._refresh_views()


def main():
    import sys

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = StandardScenarioWidget()
    win.setWindowTitle("Standard Scenario - QRA")
    win.resize(1360, 920)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
