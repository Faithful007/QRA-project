"""
Full PyQt5 port of the road-tunnel FDS (Longitudinal / Transverse) calculator,
used as the FDS tab's "Generate FDS" sub-tab.  All Korean text translated to
English.

Sections (matching the original tool):
    01  Tunnel section / grid           (shared by all files)
    --  derived quantities + cross-section preview
    02  Wall-cell coordinates           (+ auto-symmetry, DXF import)
    03  Transverse exhaust duct         (transverse mode only)
    04  Fire scenario / fire vehicle
    06  FDS output                      (Copy / Save .fds / Save All ZIP / Reset)
"""

from __future__ import annotations

import io
import os
import zipfile

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton, QPlainTextEdit,
    QRadioButton, QButtonGroup, QFrame, QScrollArea, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QApplication, QSizePolicy,
)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QLinearGradient

import fds_calculator as F


# ---------------------------------------------------------------------------
# Cross-section preview  (port of the original draw() canvas)
# ---------------------------------------------------------------------------
class CrossSectionView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(330)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._m = None
        self._fire = (1.0, 1.0, 2.5)   # bo1, bo2, bz
        self._duct = None
        self._poly = None
        self._dxf_w = None
        self._dxf_h = None

    def set_data(self, m, fire, duct=None, poly=None):
        self._m, self._fire, self._duct, self._poly = m, fire, duct, poly
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#0c121b"))
        m = self._m
        if not m:
            return
        nW, nH = m["nW"], m["nH"]
        pad_l, pad_r, pad_t, pad_b = 46, 18, 18, 34
        gw = max(10, self.width() - pad_l - pad_r)
        gh = max(10, self.height() - pad_t - pad_b)
        cx, cy = gw / nW, gh / nH

        def px(i):
            return pad_l + i * cx

        def py(j):
            return pad_t + gh - (j + 1) * cy

        p.fillRect(QRectF(pad_l, pad_t, gw, gh), QColor("#0f1722"))

        # wall cells
        occ = [[False] * nH for _ in range(nW)]
        for c in (m["left"] + m["right"]):
            if all(v == 0 for v in c):
                continue
            for i in range(max(0, c[0]), min(nW, c[1])):
                for j in range(max(0, c[2]), min(nH, c[3])):
                    occ[i][j] = True
        p.setPen(QPen(QColor("#404b59"), 0.6))
        p.setBrush(QColor("#5b6675"))
        for i in range(nW):
            for j in range(nH):
                if occ[i][j]:
                    p.drawRect(QRectF(px(i), py(j), cx, cy))

        # grid lines
        for i in range(nW + 1):
            p.setPen(QPen(QColor("#1f3b52"), 1 if i % 5 == 0 else 0.4))
            p.drawLine(int(px(i)), pad_t, int(px(i)), pad_t + gh)
        for j in range(nH + 1):
            p.setPen(QPen(QColor("#1f3b52"), 1 if j % 5 == 0 else 0.4))
            yy = pad_t + gh - j * cy
            p.drawLine(pad_l, int(yy), pad_l + gw, int(yy))

        # centre line
        p.setPen(QPen(QColor("#2f6285"), 0.8, Qt.DashLine))
        p.drawLine(int(pad_l + gw / 2), pad_t, int(pad_l + gw / 2), pad_t + gh)

        # fire (embankment gradient)
        bo1, bo2, bz = self._fire
        fy1, fy2 = m["W"] / 2 - bo1, m["W"] / 2 + bo2
        bx1 = pad_l + (fy1 / m["W"]) * gw
        bx2 = pad_l + (fy2 / m["W"]) * gw
        bz_px = (bz / m["H"]) * gh
        grad = QLinearGradient(0, pad_t + gh, 0, pad_t + gh - bz_px)
        grad.setColorAt(0, QColor("#c2410c"))
        grad.setColorAt(1, QColor("#ffb347"))
        p.setPen(QPen(QColor("#c2410c"), 1))
        p.setBrush(QBrush(grad))
        p.drawRect(QRectF(bx1, pad_t + gh - bz_px, bx2 - bx1, bz_px))

        # DXF overlay
        if self._poly and len(self._poly) > 1:
            ow = self._dxf_w or m["W"]
            oh = self._dxf_h or m["H"]
            p.setPen(QPen(QColor("#ffb347"), 2))
            p.setBrush(Qt.NoBrush)
            pts = [(pad_l + (q["x"] / ow) * gw, pad_t + gh - (q["y"] / oh) * gh)
                   for q in self._poly]
            for a, b in zip(pts, pts[1:] + pts[:1]):
                p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))

        # transverse duct columns (top band)
        if self._duct:
            p.setPen(QPen(QColor("#2c8262"), 1))
            p.setBrush(QColor("#3fb98a"))
            for yc in self._duct["cols"]:
                x1 = pad_l + ((yc - self._duct["wy"] / 2) / m["W"]) * gw
                x2 = pad_l + ((yc + self._duct["wy"] / 2) / m["W"]) * gw
                p.drawRect(QRectF(x1, pad_t, max(2, x2 - x1), 7))

        # labels
        p.setPen(QColor("#8aa0b8"))
        p.setFont(QFont("monospace", 8))
        p.drawText(pad_l, pad_t + gh + 16, "0")
        p.drawText(pad_l + gw - 70, pad_t + gh + 16, "W = %s m" % F.fmt(m["W"]))
        p.drawText(2, pad_t + 10, "H=%s" % F.fmt(m["H"]))
        p.setPen(QColor("#ffb347"))
        p.drawText(int(pad_l + gw / 2 - 10),
                   int(pad_t + gh - bz_px - 6), "fire")
        p.end()


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
class FDSDeckBuilderPanel(QWidget):
    N_ROWS = 30

    def __init__(self, project_dir_getter=None, parent=None):
        super().__init__(parent)
        self._get_project_dir = project_dir_getter
        self._spins = {}
        self._symmetric = True
        self._dxf = None
        self._fv_profiles = {}
        self._build_ui()
        self._load_default_cells()
        self._refresh()

    # ---- input helpers ----
    def _dspin(self, key, lo, hi, step, dec, val):
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi); sb.setSingleStep(step); sb.setDecimals(dec)
        sb.setValue(val); sb.valueChanged.connect(self._on_change)
        self._spins[key] = sb
        return sb

    def _ispin(self, key, lo, hi, val):
        sb = QSpinBox()
        sb.setRange(lo, hi); sb.setValue(val)
        sb.valueChanged.connect(self._on_change)
        self._spins[key] = sb
        return sb

    @staticmethod
    def _grid_row(form, r, c, label, w):
        form.addWidget(QLabel(label), r, c)
        form.addWidget(w, r, c + 1)

    # ---- build ----
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("Road-Tunnel FDS Deck Builder")
        title.setStyleSheet("font-size:15px;font-weight:bold;color:#2c3e50;")
        top.addWidget(title)
        top.addSpacing(20)
        top.addWidget(QLabel("Ventilation:"))
        self.rb_long = QRadioButton("Longitudinal (20/30/100 MW)")
        self.rb_trans = QRadioButton("Transverse small-car (5/10/15/20 MW)")
        self.rb_long.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.rb_long, 0)
        grp.addButton(self.rb_trans, 1)
        grp.idToggled.connect(lambda *_: self._on_mode())
        top.addWidget(self.rb_long)
        top.addWidget(self.rb_trans)
        top.addStretch(1)
        outer.addLayout(top)

        cols = QHBoxLayout()
        cols.setSpacing(10)
        outer.addLayout(cols, 1)

        # ===== LEFT COLUMN (scrollable) =====
        left_host = QWidget()
        left = QVBoxLayout(left_host)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(10)
        lscroll = QScrollArea()
        lscroll.setWidgetResizable(True)
        lscroll.setFrameShape(QFrame.NoFrame)
        lscroll.setWidget(left_host)
        lscroll.setMinimumWidth(500)
        cols.addWidget(lscroll, 1)            # inputs ~50%

        # 01 grid
        g01 = QGroupBox("01  Tunnel section / grid  (shared by all files)")
        gf = QGridLayout(g01)
        gf.setVerticalSpacing(6)
        self._grid_row(gf, 0, 0, "Width (W) m",
                       self._dspin("W", 0.1, 100, 0.01, 2, 10.86))
        self._grid_row(gf, 0, 2, "Width cell count (J)",
                       self._ispin("nW", 1, 400, 20))
        self._grid_row(gf, 1, 0, "Height (H) m",
                       self._dspin("H", 0.1, 60, 0.01, 2, 6.73))
        self._grid_row(gf, 1, 2, "Height cell count (K)",
                       self._ispin("nH", 1, 400, 15))
        self._grid_row(gf, 2, 0, "Half tunnel length m",
                       self._dspin("Lh", 1, 100000, 1, 1, 720))
        self._grid_row(gf, 2, 2, "Length cell size dx m",
                       self._dspin("dxLen", 0.1, 50, 0.1, 2, 1))
        self._grid_row(gf, 3, 0, "Breath line (SLCF) m",
                       self._dspin("breath", 0.1, 30, 0.1, 2, 1.8))
        self.breath_snap = QLineEdit(); self.breath_snap.setReadOnly(True)
        self._grid_row(gf, 3, 2, "Breath cell snap m", self.breath_snap)
        left.addWidget(g01)

        self.derived = QLabel()
        self.derived.setWordWrap(True)
        self.derived.setStyleSheet(
            "background:#0f1722;color:#cfe3f2;border:1px solid #1f3b52;"
            "border-radius:6px;padding:8px;font-family:monospace;font-size:11px;")
        left.addWidget(self.derived)

        # 02 wall cells
        g02 = QGroupBox("02  Wall-cell coordinates  (all-zero rows skipped)")
        v02 = QVBoxLayout(g02)
        symbar = QHBoxLayout()
        self.btn_sym = QPushButton("Left -> Right auto-symmetry")
        self.btn_free = QPushButton("Edit left / right independently")
        for b in (self.btn_sym, self.btn_free):
            b.setCheckable(True)
        self.btn_sym.setChecked(True)
        self.btn_sym.clicked.connect(lambda: self._set_sym(True))
        self.btn_free.clicked.connect(lambda: self._set_sym(False))
        symbar.addWidget(self.btn_sym)
        symbar.addWidget(self.btn_free)
        symbar.addStretch(1)
        v02.addLayout(symbar)

        self.cells = QTableWidget(self.N_ROWS, 8)
        self.cells.setHorizontalHeaderLabels(
            ["L-X1", "L-X2", "L-Y1", "L-Y2", "R-X1", "R-X2", "R-Y1", "R-Y2"])
        self.cells.verticalHeader().setDefaultSectionSize(22)
        self.cells.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cells.setMaximumHeight(260)
        self.cells.cellChanged.connect(self._on_cell_edit)
        v02.addWidget(self.cells)

        dxfbar = QHBoxLayout()
        self.btn_dxf = QPushButton("Load DXF section...")
        self.btn_dxf.clicked.connect(self._load_dxf)
        self.btn_dxf_clear = QPushButton("Clear DXF")
        self.btn_dxf_clear.clicked.connect(self._clear_dxf)
        self.btn_dxf_clear.setVisible(False)
        dxfbar.addWidget(self.btn_dxf)
        dxfbar.addWidget(self.btn_dxf_clear)
        dxfbar.addStretch(1)
        v02.addLayout(dxfbar)
        self.dxf_info = QLabel("Import a closed cross-section polyline "
                               "(LWPOLYLINE / POLYLINE). Sets W*H and fills "
                               "wall cells by point-in-polygon.")
        self.dxf_info.setWordWrap(True)
        self.dxf_info.setStyleSheet("color:#558877;font-size:11px;")
        v02.addWidget(self.dxf_info)
        left.addWidget(g02)

        # 03 transverse duct
        self.g03 = QGroupBox("03  Transverse exhaust duct (ceiling)")
        df = QGridLayout(self.g03)
        df.setVerticalSpacing(6)
        self.d_rows = QComboBox()
        self.d_rows.addItems(["1 column (centre)", "2 columns (L/R)",
                              "3 columns (even)"])
        self.d_rows.currentIndexChanged.connect(self._on_change)
        self._grid_row(df, 0, 0, "Duct layout", self.d_rows)
        self._grid_row(df, 1, 0, "Damper width w m",
                       self._dspin("dLx", 0.1, 30, 0.5, 2, 2))
        self._grid_row(df, 1, 2, "Damper length L m",
                       self._dspin("dWy", 0.1, 60, 0.05, 2, 4.15))
        self._grid_row(df, 2, 0, "Pitch m",
                       self._dspin("dPitch", 0.1, 1000, 1, 1, 52))
        self._grid_row(df, 2, 2, "Active range (fire +/-) m",
                       self._dspin("dWin", 0, 100000, 10, 1, 250))
        self._grid_row(df, 3, 0, "Position offset m",
                       self._dspin("dOffset", -100000, 100000, 1, 1, 0))
        self._grid_row(df, 3, 2, "Total exhaust flow m3/s",
                       self._dspin("dFlow", 0, 100000, 0.1, 2, 132.7))
        left.addWidget(self.g03)

        # 04 fire scenario
        g04 = QGroupBox("04  Fire scenario / fire vehicle")
        ff = QGridLayout(g04)
        ff.setVerticalSpacing(6)
        self.preset = QComboBox()
        self._grid_row(ff, 0, 0, "Preset", self.preset)
        self.cmb_bc = QComboBox()
        self.cmb_bc.addItems(["CASE 1 - initial velocity + OPEN BC",
                              "CASE 2 - Pressure Dynamic BC",
                              "CASE 3 - Velocity Profile (Vr_Ramp)",
                              "CASE 4 - Velocity Profile (-)"])
        self.cmb_bc.setCurrentIndex(2)
        self.cmb_bc.currentIndexChanged.connect(self._on_change)
        self._grid_row(ff, 0, 2, "Active CASE", self.cmb_bc)
        self._grid_row(ff, 1, 0, "HRRPUA kW/m2",
                       self._dspin("hrr", 0, 100000, 0.001, 3, 533.333))
        self._grid_row(ff, 1, 2, "Fire-car half-length m",
                       self._dspin("bhl", 0.05, 100, 0.05, 2, 3.75))
        self._grid_row(ff, 2, 0, "Fire-car height Z2 m",
                       self._dspin("bz", 0.1, 30, 0.1, 2, 2.5))
        self._grid_row(ff, 2, 2, "Width offset -",
                       self._dspin("bo1", 0, 50, 0.5, 2, 1))
        self._grid_row(ff, 3, 0, "Width offset +",
                       self._dspin("bo2", 0, 50, 0.5, 2, 1))
        self._grid_row(ff, 3, 2, "TWFIN s",
                       self._dspin("twfin", 10, 100000, 10, 1, 1200))
        self._grid_row(ff, 4, 0, "Initial velocity V0 m/s",
                       self._dspin("v0", -50, 50, 0.01, 2, 6.02))
        self.preset.currentIndexChanged.connect(self._on_preset)
        left.addWidget(g04)
        left.addStretch(1)

        # ===== RIGHT COLUMN =====
        right = QVBoxLayout()
        right.setSpacing(8)
        cols.addLayout(right, 1)              # cross-section preview + output ~50%

        prev_lbl = QLabel("Cross-section preview")
        prev_lbl.setStyleSheet("font-weight:bold;color:#2c3e50;")
        right.addWidget(prev_lbl)
        self.view = CrossSectionView()
        right.addWidget(self.view, 1)

        out_lbl = QLabel("06  FDS output")
        out_lbl.setStyleSheet("font-weight:bold;color:#2c3e50;")
        right.addWidget(out_lbl)

        sel = QHBoxLayout()
        sel.addWidget(QLabel("MW"))
        self.cmb_mw = QComboBox()
        self.cmb_mw.currentIndexChanged.connect(self._refresh)
        sel.addWidget(self.cmb_mw)
        sel.addWidget(QLabel("Traffic"))
        self.cmb_traffic = QComboBox()
        self.cmb_traffic.addItems(["Congested (C)", "Normal (N)"])
        self.cmb_traffic.currentIndexChanged.connect(self._refresh)
        sel.addWidget(self.cmb_traffic)
        sel.addWidget(QLabel("Scenario"))
        self.cmb_scen = QComboBox()
        self.cmb_scen.addItems(F.SCENARIOS)
        self.cmb_scen.currentIndexChanged.connect(self._refresh)
        sel.addWidget(self.cmb_scen)
        sel.addStretch(1)
        right.addLayout(sel)

        btns = QHBoxLayout()
        self.btn_copy = QPushButton("Copy")
        self.btn_save = QPushButton("Save .fds")
        self.btn_zip = QPushButton("Save All (ZIP)")
        self.btn_gen = QPushButton("Generate to project")
        self.btn_reset = QPushButton("Reset")
        self.btn_zip.setStyleSheet(
            "QPushButton{background:#2d8f5f;color:white;font-weight:bold;"
            "padding:5px 12px;border-radius:4px;}")
        self.btn_gen.setStyleSheet(
            "QPushButton{background:#2563a8;color:white;font-weight:bold;"
            "padding:5px 12px;border-radius:4px;}")
        self.btn_copy.clicked.connect(self._copy)
        self.btn_save.clicked.connect(self._save_one)
        self.btn_zip.clicked.connect(self._save_zip)
        self.btn_gen.clicked.connect(self._generate_project)
        self.btn_reset.clicked.connect(self._reset)
        for b in (self.btn_copy, self.btn_save, self.btn_zip, self.btn_gen,
                  self.btn_reset):
            btns.addWidget(b)
        btns.addStretch(1)
        right.addLayout(btns)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("monospace", 9))
        self.preview.setStyleSheet(
            "background:#0f1722;color:#cfe3f2;border:1px solid #1f3b52;")
        self.preview.setMinimumHeight(240)
        right.addWidget(self.preview, 2)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#34495e;")
        right.addWidget(self.status)

        self._sync_presets()
        self._on_mode()

    # ---- mode / presets ----
    def _mode(self):
        return "trans" if self.rb_trans.isChecked() else "long"

    def _submode(self):
        return "small" if self.rb_trans.isChecked() else "general"

    def _sync_presets(self):
        mws = F.current_mw_set(self._mode(), self._submode())
        self.preset.blockSignals(True)
        self.preset.clear()
        self.preset.addItems(["%d MW" % x for x in mws] + ["Custom"])
        self.preset.blockSignals(False)
        self.cmb_mw.blockSignals(True)
        self.cmb_mw.clear()
        self.cmb_mw.addItems([str(x) for x in mws])
        self.cmb_mw.blockSignals(False)

    def _on_mode(self):
        self.g03.setVisible(self._mode() == "trans")
        self._sync_presets()
        self._on_preset()

    def _on_preset(self, *_):
        idx = self.preset.currentIndex()
        mws = F.current_mw_set(self._mode(), self._submode())
        if 0 <= idx < len(mws):       # not "Custom"
            pre = F.preset_for(mws[idx], self._mode(), self._submode())
            self._spins["hrr"].blockSignals(True)
            self._spins["hrr"].setValue(pre["hrr"])
            self._spins["hrr"].blockSignals(False)
            if not pre.get("small_car"):
                for k, v in (("bhl", pre["hl"]), ("bz", pre["bz"]),
                             ("bo1", pre["o1"]), ("bo2", pre["o2"])):
                    self._spins[k].blockSignals(True)
                    self._spins[k].setValue(v)
                    self._spins[k].blockSignals(False)
            self.cmb_mw.setCurrentIndex(idx)
        self._refresh()

    # ---- wall-cell table ----
    def _load_default_cells(self):
        self.cells.blockSignals(True)
        for i in range(self.N_ROWS):
            d = F.DEFAULT_CELLS[i] if i < len(F.DEFAULT_CELLS) else [0, 0, 0, 0]
            for k in range(4):
                self._set_cell(i, k, d[k])
            for k in range(4):
                self._set_cell(i, 4 + k, 0)
        self.cells.blockSignals(False)
        self._recompute_symmetry()

    def _set_cell(self, r, c, val):
        it = QTableWidgetItem(str(int(val)))
        it.setTextAlignment(Qt.AlignCenter)
        if c >= 4 and self._symmetric:
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setForeground(QColor("#90a0b0"))
        self.cells.setItem(r, c, it)

    def _cell_val(self, r, c):
        it = self.cells.item(r, c)
        try:
            return int(round(float(it.text()))) if it and it.text() else 0
        except ValueError:
            return 0

    def _set_sym(self, on):
        self._symmetric = on
        self.btn_sym.setChecked(on)
        self.btn_free.setChecked(not on)
        self._recompute_symmetry()
        self._refresh()

    def _recompute_symmetry(self):
        nW = self._spins["nW"].value()
        self.cells.blockSignals(True)
        for i in range(self.N_ROWS):
            x1, x2 = self._cell_val(i, 0), self._cell_val(i, 1)
            y1, y2 = self._cell_val(i, 2), self._cell_val(i, 3)
            if self._symmetric:
                for c, v in ((4, nW - x2), (5, nW - x1), (6, y1), (7, y2)):
                    self._set_cell(i, c, v)
            else:
                for c in range(4, 8):
                    it = self.cells.item(i, c)
                    if it:
                        it.setFlags(it.flags() | Qt.ItemIsEditable)
                        it.setForeground(QColor("#1a252f"))
        self.cells.blockSignals(False)

    def _on_cell_edit(self, row, col):
        if self._symmetric and col < 4:
            self._recompute_symmetry()
        self._refresh()

    def _read_cells(self):
        left, right = [], []
        for i in range(self.N_ROWS):
            left.append([self._cell_val(i, k) for k in range(4)])
            right.append([self._cell_val(i, 4 + k) for k in range(4)])
        return left, right

    # ---- model / cfg ----
    def _ui(self):
        return {"twfin": self._spins["twfin"].value(),
                "v0": self._spins["v0"].value(),
                "breath": self._spins["breath"].value(),
                "sign": 1, "bc": str(self.cmb_bc.currentIndex() + 1)}

    def _model(self):
        left, right = self._read_cells()
        p = {k: self._spins[k].value()
             for k in ("W", "nW", "H", "nH", "Lh", "dxLen", "breath")}
        p["left"] = left
        p["right"] = right
        p["symmetric"] = self._symmetric
        return F.compute_model(p)

    def _duct(self, m):
        if self._mode() != "trans":
            return None
        return F.duct_model(m, {
            "rows": self.d_rows.currentIndex() + 1,
            "lx": self._spins["dLx"].value(), "wy": self._spins["dWy"].value(),
            "pitch": self._spins["dPitch"].value(),
            "win": self._spins["dWin"].value(),
            "offset": self._spins["dOffset"].value(),
            "flow": self._spins["dFlow"].value()})

    def _current_cfg(self, m):
        mw = int(self.cmb_mw.currentText() or "20")
        scen = self.cmb_scen.currentText()
        traffic = (F.TRAFFIC[0] if self.cmb_traffic.currentIndex() == 0
                   else F.TRAFFIC[1])
        profile = None
        if scen.startswith("FV"):
            profile = self._fv_profiles.get(
                "%s|%s|%s" % (mw, traffic["key"], scen)) or F.VR_PROFILE
        cfg = F.cfg_for_scenario(mw, traffic, scen, profile, self._ui(),
                                 self._mode(), self._submode())
        if not cfg.get("small_car"):     # honour live fire-scenario fields
            cfg["hrr"] = self._spins["hrr"].value()
            cfg["hl"] = self._spins["bhl"].value()
            cfg["bz"] = self._spins["bz"].value()
            cfg["o1"] = self._spins["bo1"].value()
            cfg["o2"] = self._spins["bo2"].value()
        d = self._duct(m)
        if d:
            cfg["duct"] = d
        return cfg

    # ---- refresh ----
    def _on_change(self, *_):
        if self._symmetric:
            self._recompute_symmetry()
        self._refresh()

    def _refresh(self, *_):
        try:
            m = self._model()
        except Exception as exc:
            self.preview.setPlainText("// model error: %s" % exc)
            return
        ca = F.clear_area(m)
        self.breath_snap.setText("%s  (cell %d, target %s m)"
                                 % (F.fmt(m["breathSnap"]), m["kBreath"],
                                    F.fmt(m["breath"])))
        rows = ["Cell width: %s m" % F.fmt(m["cW"]),
                "Cell height: %s m" % F.fmt(m["cH"]),
                "Length dx: %s m" % F.fmt(m["dxLen"]),
                "Full length: %s m" % F.fmt(m["Lfull"]),
                "MESH cells: %d.%d.%d" % (m["nLen"], m["nW"], m["nH"]),
                "Total cells: {:,}".format(m["nLen"] * m["nW"] * m["nH"]),
                "Gross area: %s m2" % F.fmt(ca["gross"]),
                "Clear area: %s m2" % F.fmt(ca["clear"])]
        d = self._duct(m)
        if d:
            rows.append("Dampers active: %d (vel %s m/s)"
                        % (d["totalActive"], F.fmt(d["vel"])))
        self.derived.setText("    ".join(rows))
        fire = (self._spins["bo1"].value(), self._spins["bo2"].value(),
                self._spins["bz"].value())
        self.view._dxf_w = self._dxf["W"] if self._dxf else None
        self.view._dxf_h = self._dxf["H"] if self._dxf else None
        self.view.set_data(m, fire, d, self._dxf["poly"] if self._dxf else None)
        try:
            self.preview.setPlainText(F.build_fds(m, self._current_cfg(m)))
        except Exception as exc:
            self.preview.setPlainText("// preview error: %s" % exc)

    # ---- DXF ----
    def _load_dxf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load DXF section", "",
                                              "DXF files (*.dxf);;All (*)")
        if not path:
            return
        try:
            with open(path, "r", errors="ignore") as fh:
                txt = fh.read()
            res = F.load_dxf_section(txt, self._spins["nW"].value(),
                                     self._spins["nH"].value())
        except Exception as exc:
            self.dxf_info.setText("DXF read failed: %s" % exc)
            return
        if not res:
            self.dxf_info.setText("No closed section polyline found "
                                  "(check LWPOLYLINE).")
            return
        self._dxf = res
        self._symmetric = res["symmetric"]
        self.btn_sym.setChecked(res["symmetric"])
        self.btn_free.setChecked(not res["symmetric"])
        self._spins["W"].blockSignals(True); self._spins["W"].setValue(res["W"])
        self._spins["W"].blockSignals(False)
        self._spins["H"].blockSignals(True); self._spins["H"].setValue(res["H"])
        self._spins["H"].blockSignals(False)
        self.cells.blockSignals(True)
        for i in range(self.N_ROWS):
            for k in range(8):
                self._set_cell(i, k, 0)
        for i, c in enumerate(res["left"][:self.N_ROWS]):
            for k in range(4):
                self._set_cell(i, k, c[k])
        if not res["symmetric"]:
            for i, c in enumerate(res["right"][:self.N_ROWS]):
                for k in range(4):
                    self._set_cell(i, 4 + k, c[k])
        self.cells.blockSignals(False)
        if res["symmetric"]:
            self._recompute_symmetry()
        self.btn_dxf_clear.setVisible(True)
        self.dxf_info.setText("Loaded: W %s * H %s m * %d band(s)"
                              % (F.fmt(res["W"]), F.fmt(res["H"]),
                                 len(res["left"])))
        self._refresh()

    def _clear_dxf(self):
        self._dxf = None
        self.btn_dxf_clear.setVisible(False)
        self.dxf_info.setText("Import a closed cross-section polyline "
                              "(LWPOLYLINE / POLYLINE).")
        self._refresh()

    # ---- output actions ----
    def _copy(self):
        QApplication.clipboard().setText(self.preview.toPlainText())
        self.status.setText("Copied deck to clipboard.")

    def _save_one(self):
        m = self._model()
        cfg = self._current_cfg(m)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save .fds", cfg["title"] + ".fds", "FDS (*.fds)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(F.build_fds(m, cfg))
        self.status.setText("Saved %s" % os.path.basename(path))

    def _build_all(self, m):
        d = self._duct(m)
        out, missing = {}, []
        for mw in F.current_mw_set(self._mode(), self._submode()):
            for tr in F.TRAFFIC:
                for scen in F.SCENARIOS:
                    title = F.mw3(mw) + tr["key"] + scen
                    profile = None
                    if scen.startswith("FV"):
                        profile = self._fv_profiles.get(
                            "%s|%s|%s" % (mw, tr["key"], scen))
                        if not profile:
                            missing.append(title)
                            continue
                    cfg = F.cfg_for_scenario(mw, tr, scen, profile, self._ui(),
                                             self._mode(), self._submode())
                    if d:
                        cfg["duct"] = d
                    folder = "%s/%s/%s" % (F.mw3(mw), tr["dir"], scen)
                    out["%s/%s.fds" % (folder, title)] = F.build_fds(m, cfg)
        return out, missing

    def _save_zip(self):
        m = self._model()
        decks, missing = self._build_all(m)
        if not decks:
            self.status.setText("Nothing to zip (FV scenarios need .VRR).")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save All (ZIP)", "road_tunnel_scenarios.zip", "ZIP (*.zip)")
        if not path:
            return
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for rel, txt in decks.items():
                z.writestr(rel, txt)
        with open(path, "wb") as fh:
            fh.write(buf.getvalue())
        self.status.setText("Saved %d decks to %s%s"
                            % (len(decks), os.path.basename(path),
                               (" (%d FV skipped)" % len(missing))
                               if missing else ""))

    def _generate_project(self):
        out_root = None
        if self._get_project_dir:
            try:
                pd = self._get_project_dir()
            except Exception:
                pd = None
            if pd:
                out_root = os.path.join(pd, "fds_inputs")
        if not out_root:
            chosen = QFileDialog.getExistingDirectory(self, "Choose folder")
            if not chosen:
                return
            out_root = os.path.join(chosen, "fds_inputs")
        m = self._model()
        decks, missing = self._build_all(m)
        for rel, txt in decks.items():
            fp = os.path.join(out_root, rel)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(txt)
        self.status.setText("Generated %d FDS files in %s%s"
                            % (len(decks), out_root,
                               (" (%d FV skipped)" % len(missing))
                               if missing else ""))

    def _reset(self):
        for k, v in F.DEFAULT_UI.items():
            if k in self._spins:
                self._spins[k].blockSignals(True)
                self._spins[k].setValue(v)
                self._spins[k].blockSignals(False)
        self.rb_long.setChecked(True)
        self._symmetric = True
        self.btn_sym.setChecked(True)
        self.btn_free.setChecked(False)
        self._clear_dxf()
        self._load_default_cells()
        self._on_mode()
        self.status.setText("Reset to defaults.")