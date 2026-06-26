#!/usr/bin/env python3
"""
run_qra.py
====================================================================
Single entry point for the Quantitative Risk Assessment System that
loads ALL tabs, with the new "General Input Information" tab added as
the first tab.

It does this WITHOUT modifying qra_main_app.py: it subclasses the
existing main window, inserts the General Input Information tab at the
front in init_ui(), and shifts the EVC/FED tab-change guard by one so
the auto directory-creation still fires on the right tab.

USAGE
-----
Put this file in the SAME directory as qra_main_app.py and
general_input_tab.py, then run:

    python run_qra.py

Resulting tab order:
    0  General Input Information      <-- new
    1  Directory Setup
    2  Generate FDS
    3  FDS Simulation
    4  EVC/FED Analysis               (was index 3, now index 4)
    5  Visual Simulation
    6  Results
    7  Risk Calculations
"""

import os
import sys

# Make sure the app's own directory is importable no matter where this
# launcher is invoked from.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog

# The big existing application (defines QRAMainWindow + main()).
import qra_main_app as qra

# The new tab.  If it can't be imported we still launch the original
# 7-tab app rather than failing outright.
try:
    from general_input_tab import GeneralInputTab
    _HAS_GENERAL_TAB = True
    _GENERAL_TAB_ERR = ""
except Exception as exc:  # pragma: no cover
    GeneralInputTab = None
    _HAS_GENERAL_TAB = False
    _GENERAL_TAB_ERR = str(exc)


class QRAMainWindowPlus(qra.QRAMainWindow):
    """QRAMainWindow with the General Input Information tab prepended."""

    def init_ui(self):
        # Build every original tab exactly as before.
        super().init_ui()

        if not _HAS_GENERAL_TAB:
            return

        # Insert the new tab at the very front (index 0).  Every original
        # tab is therefore shifted one place to the right.
        self.general_input_tab = GeneralInputTab()
        self.tabs.insertTab(0, self.general_input_tab, "General Input Information")

        # Move the EVC/FED "Tunnel Basic Specifications" group plus the
        # Simulation sub-tab's fire-location / fire-placement / fire-point
        # mapping controls into the new "Basic Tunnel Information" panel.
        self._relocate_basic_tunnel_info()
        # Move the Traffic Volume table + pre-fire driving-state control into
        # the new full-width "Traffic Information" panel (control 20%, table 80%).
        self._relocate_traffic_info()
        # Move the Directory-Setup "Project Configuration" and "Directory
        # Structure Preview" groups into the new "Project Directory" panel.
        self._relocate_project_directory()
        # Remove the "Estimated Traffic Split" table and merge its AADT /
        # PCU% / Heavy% / Clavg / Spacing rows into the Traffic Volume table.
        self._merge_split_into_traffic_volume()
        # Add a 'Total' column (first column) summing the vehicle columns.
        self._add_traffic_total_column()
        # Make "Tunnel Basic Specifications" the single source of truth: push
        # its values to the mirror fields the rest of the program reads.
        self._bind_tunnel_spec_sources()
        # The tunnel name is the project's default name.
        self._bind_project_name_default()
        # Move the "Scenario Configuration" group under the Scenario panel's
        # Control, renamed "Traffic Ventilation".
        self._relocate_scenario_config()
        # Add the NVP ventilation option (before NVC).
        self._add_nvp_vent()
        # Remove the Fire Positions, Simulation Time T_END and Total Scenarios
        # rows from the Traffic Ventilation panel.
        self._trim_traffic_ventilation()
        # Selecting a Scenario sets the HRR + traffic / ventilation folders.
        self._bind_scenario_hrr()
        # Fire Positions are read from the Fire Point Mapping (Fire pt. X).
        self._bind_fire_positions()
        # Re-brand the landing header (company name + QRA, drop the subtitle).
        self._brand_header()

        # Put "Risk Calculations" second (right after General Input), then
        # keep the app's step-advance navigation pointing at the right tabs.
        self._reorder_tabs()
        # Move the FDS-calculator section into its own "FDS" tab, placed
        # right after Risk Calculations.
        self._create_fds_tab()
        self._install_tab_nav_fix()
        # Drop the now-relocated Directory Setup and Generate FDS tabs.
        self._remove_relocated_tabs()
        self.tabs.setCurrentWidget(self.general_input_tab)

    def _remove_relocated_tabs(self):
        """Remove the Directory Setup and Generate FDS tabs.  Their content was
        already relocated (Project Configuration / Directory Structure Preview /
        Setup Progress / buttons into the General Input 'Project Directory'
        panel; 'Scenario Configuration' into the Scenario panel's 'Traffic
        Ventilation').  removeTab only detaches the page from the tab bar -- the
        underlying widgets (and their signals / backend wiring) stay alive, so
        nothing the rest of the app reads is lost."""
        for title in ("Directory Setup", "Generate FDS"):
            try:
                for i in range(self.tabs.count() - 1, -1, -1):
                    if self.tabs.tabText(i).strip() == title:
                        self.tabs.removeTab(i)
                        break
            except Exception as exc:
                print(f"[warning] could not remove '{title}' tab: {exc}")

    def _create_fds_tab(self):
        """Turn the 'FDS' tab into a two-sub-tab container:
          * 'Generate FDS'   = the General Input tab's FDS-calculator section
          * 'FDS Simulation' = the (moved) top-level FDS Simulation page
        placed right after 'Risk Calculations'."""
        if getattr(self, "general_input_tab", None) is None:
            return
        try:
            fds_box = self.general_input_tab.take_fds_section()
        except Exception as exc:
            print(f"[warning] could not extract FDS section: {exc}")
            return
        if fds_box is None:
            return
        from PyQt5.QtWidgets import QScrollArea, QTabWidget
        gen_scroll = QScrollArea()
        gen_scroll.setWidgetResizable(True)
        gen_scroll.setWidget(fds_box)

        # pull the existing top-level "FDS Simulation" page out of the tab bar
        sim_page = None
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "FDS Simulation":
                sim_page = self.tabs.widget(i)
                self.tabs.removeTab(i)
                break

        self._fds_subtabs = QTabWidget()
        self._fds_subtabs.setDocumentMode(True)
        self._fds_subtabs.addTab(gen_scroll, "Generate FDS")
        self._fds_sim_subindex = None
        if sim_page is not None:
            self._fds_sim_subindex = self._fds_subtabs.addTab(
                sim_page, "FDS Simulation")

        pos = self.tabs.count()
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "Risk Calculations":
                pos = i + 1
                break
        self.tabs.insertTab(pos, self._fds_subtabs, "FDS")

    def _bind_tunnel_spec_sources(self):
        """Make 'Tunnel Basic Specifications' the single source of truth.

        The app already cascades tbi_length -> evc_tunnel_length and
        tbi_lanes -> evc_num_lanes (with downstream recalcs) and pushes
        length / gradient / perimeter to the Tunnel Traffic Volume sheet.
        Here we propagate the remaining genuinely-shared quantities the app
        does not already wire: tunnel height, cross-sectional area, tunnel
        name and traffic direction.  Propagation is one-way (spec -> mirrors)
        with the targets' signals blocked, so editing the specification
        updates everywhere it is needed without feedback loops.

        (The Generate-FDS tab's tunnel_*_input fields are a separate FDS
        model geometry with unrelated scales, so they are left independent.)"""
        g = lambda n: getattr(self, n, None)
        mappings = [
            (g("tbi_height"), [g("evc_tunnel_height")]),
            (g("tbi_area"),   [g("evc_cross_area")]),
            (g("tbi_tunnel_name"), [g("tunnel_name_input")]),
        ]
        for src, targets in mappings:
            targets = [t for t in targets if t is not None]
            if src is not None and targets:
                self._wire_spec_field(src, targets)
        self._wire_traffic_direction()

    def _wire_spec_field(self, src, targets):
        def push(*_):
            try:
                txt = src.text().strip()
            except Exception:
                return
            for t in targets:
                self._set_mirror_value(t, txt)
        try:
            src.textChanged.connect(push)
        except Exception:
            return
        push()   # initial sync

    @staticmethod
    def _set_mirror_value(widget, txt):
        from PyQt5.QtWidgets import QLineEdit, QDoubleSpinBox, QSpinBox
        try:
            if isinstance(widget, QLineEdit):
                widget.blockSignals(True)
                widget.setText(txt)
                widget.blockSignals(False)
            elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.blockSignals(True)
                widget.setValue(float(txt))
                widget.blockSignals(False)
        except (ValueError, TypeError):
            pass
        except Exception:
            pass

    def _wire_traffic_direction(self):
        from PyQt5.QtWidgets import QComboBox
        combo = getattr(self, "evc_traffic_dir", None)
        rb_two = getattr(self, "tbi_radio_twoway", None)
        grp = getattr(self, "tbi_traffic_btn_group", None)
        if not isinstance(combo, QComboBox) or rb_two is None:
            return

        def push(*_):
            try:
                idx = 1 if rb_two.isChecked() else 0
                combo.blockSignals(True)
                combo.setCurrentIndex(idx)
                combo.blockSignals(False)
            except Exception:
                pass
        try:
            rb_two.toggled.connect(lambda _on: push())
            if grp is not None:
                grp.idClicked.connect(lambda _id: push())
        except Exception:
            pass
        push()   # initial sync

    def _reorder_tabs(self):
        """Place 'Risk Calculations' as the second tab (after General Input)."""
        try:
            bar = self.tabs.tabBar()
            ric = -1
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == "Risk Calculations":
                    ric = i
                    break
            if ric > 1:
                bar.moveTab(ric, 1)
        except Exception as exc:
            print(f"[warning] could not reorder Risk Calculations tab: {exc}")

    def _install_tab_nav_fix(self):
        """The original app calls self.tabs.setCurrentIndex(1)/(2) using the
        ORIGINAL 7-tab numbering (Directory Setup=0) to advance after project
        creation / FDS generation.  After inserting the General Input tab and
        reordering, those integers point at the wrong tabs.  Translate the
        original-layout index to the current position by title so the
        step-advance still lands on the intended tab.  (Qt's own tab clicks
        bypass this Python override, so only the app's explicit calls are
        affected.)"""
        orig_titles = {
            0: "Directory Setup", 1: "Generate FDS", 2: "FDS Simulation",
            3: "EVC/FED Analysis", 4: "Visual Simulation", 5: "Results",
            6: "Risk Calculations",
        }
        tabs = self.tabs
        _real = tabs.setCurrentIndex

        def _translated(i):
            title = orig_titles.get(i)
            # FDS Simulation is now a sub-tab of the FDS tab
            if title == "FDS Simulation" and getattr(self, "_fds_subtabs", None) is not None:
                for j in range(tabs.count()):
                    if tabs.tabText(j) == "FDS":
                        _real(j)
                        sub = getattr(self, "_fds_sim_subindex", None)
                        if sub is not None:
                            try:
                                self._fds_subtabs.setCurrentIndex(sub)
                            except Exception:
                                pass
                        return
            if title is not None:
                for j in range(tabs.count()):
                    if tabs.tabText(j) == title:
                        return _real(j)
            return _real(i)

        try:
            tabs.setCurrentIndex = _translated
        except Exception as exc:
            print(f"[warning] tab-nav fix not installed: {exc}")

    # rows merged from the split table -> Traffic Volume:  (label, split_row)
    _SPLIT_MERGE_ROWS = [
        ("AADT", 8),
        ("PCU%/Units%", 9),
        ("Heavy Veh %", 10),
        ("Avg Veh Len (Clavg)", 11),
        ("Spacing (LTH)", 12),
    ]

    @staticmethod
    def _merge_car(petrol, diesel):
        """Collapse the split table's Car(Petrol) + Car(Diesel) columns into
        a single Car value.  Both numeric -> sum (keeping a % suffix); only
        one populated -> that value verbatim (preserves '12.34 %', '2.33')."""
        p = (petrol or "").strip()
        d = (diesel or "").strip()

        def parse(s):
            pct = s.endswith("%")
            try:
                return float(s.replace("%", "").strip()), pct
            except Exception:
                return None, pct

        pv, pp = parse(p)
        dv, dp = parse(d)
        if pv is not None and dv is not None:
            tot = pv + dv
            suf = " %" if (pp or dp) else ""
            if abs(tot - round(tot)) < 1e-9:
                return f"{int(round(tot))}{suf}"
            return f"{tot:.4f}".rstrip("0").rstrip(".") + suf
        if p and p != "\u2014":
            return p
        if d and d != "\u2014":
            return d
        return ""

    def _merge_split_into_traffic_volume(self):
        """Hide the Estimated Traffic Split table and append its aggregate
        rows (AADT / PCU% / Heavy% / Clavg / Spacing) to the Traffic Volume
        table, with Car = Car(Petrol)+Car(Diesel).  Keeps the split table
        object alive so the backend keeps computing/reading from it."""
        from PyQt5.QtWidgets import QLabel, QTableWidgetItem
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QColor
        veh = getattr(self, "tbi_veh_table", None)
        split = getattr(self, "tbi_veh_split_table", None)
        if veh is None or split is None:
            return
        try:
            # (a) take the split label + table out of view (objects stay alive)
            for lab in self.findChildren(QLabel):
                if "Estimated Traffic Split" in lab.text():
                    self._detach_widget(lab)
                    lab.hide()
                    break
            self._detach_widget(split)
            split.hide()

            # (b) append the merged rows to the Traffic Volume table
            self._merge_base = veh.rowCount()
            ncol = veh.columnCount()
            veh.setRowCount(self._merge_base + len(self._SPLIT_MERGE_ROWS))
            _bg = QColor(234, 244, 251)          # light blue, derived
            _bg_edit = QColor("white")
            for k, (label, _sr) in enumerate(self._SPLIT_MERGE_ROWS):
                r = self._merge_base + k
                veh.setVerticalHeaderItem(r, QTableWidgetItem(label))
                for c in range(ncol):
                    it = QTableWidgetItem("")
                    it.setTextAlignment(Qt.AlignCenter)
                    editable = (label.startswith("Spacing") and c == 0)
                    if editable:
                        it.setBackground(_bg_edit)
                        it.setToolTip("Vehicle spacing LTH (m) — editable")
                    else:
                        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                        it.setBackground(_bg)
                    veh.setItem(r, c, it)
            try:
                vh = veh.horizontalHeader().height()
                rh = veh.verticalHeader().defaultSectionSize() or 28
                veh.setFixedHeight(rh * veh.rowCount() + vh + 4)
            except Exception:
                pass

            # (c) initial mirror, then mirror after every split recompute
            self._merging = False
            self._mirror_split_into_volume()
            if hasattr(self, "_update_split_table"):
                _orig = self._update_split_table

                def _wrapped(*a, **k):
                    res = _orig(*a, **k)
                    self._mirror_split_into_volume()
                    return res
                self._update_split_table = _wrapped

            # (d) Spacing edits in the merged table write back to the split table
            veh.cellChanged.connect(self._on_merged_cell_changed)
        except Exception as exc:
            print(f"[warning] split->traffic merge failed: {exc}")

    def _mirror_split_into_volume(self):
        veh = getattr(self, "tbi_veh_table", None)
        split = getattr(self, "tbi_veh_split_table", None)
        if veh is None or split is None or not hasattr(self, "_merge_base"):
            return

        def stext(r, c):
            it = split.item(r, c)
            return it.text() if it is not None else ""

        def put(r, c, text):
            it = veh.item(r, c)
            if it is not None and it.text() != text:
                it.setText(text)

        veh.blockSignals(True)
        try:
            tc = getattr(self, "_veh_total_col", None)
            agg = self._traffic_total_agg_rows()
            for k, (_label, sr) in enumerate(self._SPLIT_MERGE_ROWS):
                r = self._merge_base + k
                if r in agg and tc is not None:
                    # single UI aggregate (AADT / PCU% / Heavy% / Clavg) ->
                    # show it in the Total column, leave the vehicle cells blank
                    put(r, tc, self._merge_car(stext(sr, 0), stext(sr, 1)))
                    for vc in range(7):
                        put(r, vc, "")
                else:
                    put(r, 0, self._merge_car(stext(sr, 0), stext(sr, 1)))  # Car
                    for vc, sc in zip(range(1, 7), range(2, 8)):            # rest 1:1
                        put(r, vc, stext(sr, sc))
        finally:
            veh.blockSignals(False)

    def _on_merged_cell_changed(self, row, col):
        if getattr(self, "_merging", False):
            return
        base = getattr(self, "_merge_base", None)
        if base is None:
            return
        spacing_row = base + 4   # "Spacing (LTH)" is the 5th merged row
        if row != spacing_row or col != 0:
            return
        veh = self.tbi_veh_table
        split = self.tbi_veh_split_table
        it = veh.item(row, 0)
        val = it.text().strip() if it is not None else ""
        self._merging = True
        try:
            sit = split.item(12, 0)
            if sit is not None:
                sit.setText(val)
            if hasattr(self, "_update_split_table"):
                self._update_split_table()   # recompute dependents + re-mirror
        finally:
            self._merging = False

    def _add_traffic_total_column(self):
        """Add a 'Total' column to the Traffic Volume table as the first data
        column (visually before 'Car'); each cell is the row-sum of the seven
        vehicle columns to its right.  The column is appended as the last
        *logical* column (so every existing index-based read in the app keeps
        working) and only moved into the first *visual* position; columnCount()
        is shadowed so the app's per-vehicle loops still see just 7 columns."""
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        tbl = getattr(self, "tbi_veh_table", None)
        if tbl is None or getattr(self, "_veh_total_col", None) is not None:
            return
        try:
            real_cols = QTableWidget.columnCount(tbl)      # 7 vehicle columns
            total_idx = real_cols
            tbl.insertColumn(total_idx)                    # logical last column
            tbl.setHorizontalHeaderItem(total_idx, QTableWidgetItem("Total"))
            self._veh_total_col = total_idx
            self._recompute_traffic_totals()
            hdr = tbl.horizontalHeader()
            hdr.moveSection(hdr.visualIndex(total_idx), 0)  # show it first
            hdr.setSectionResizeMode(total_idx, QHeaderView.Stretch)
            # hide the Total column from the app's range(columnCount()) reads
            tbl.columnCount = (lambda rc=real_cols: rc)
            tbl.cellChanged.connect(self._on_veh_total_recalc)
            # populate the aggregate rows' Total cells now that the column exists
            if hasattr(self, "_mirror_split_into_volume"):
                self._mirror_split_into_volume()
        except Exception as exc:
            print(f"[warning] could not add Traffic Total column: {exc}")

    def _recompute_traffic_totals(self):
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QColor
        tbl = getattr(self, "tbi_veh_table", None)
        tc = getattr(self, "_veh_total_col", None)
        if tbl is None or tc is None:
            return
        agg = self._traffic_total_agg_rows()
        tbl.blockSignals(True)
        try:
            for r in range(tbl.rowCount()):
                ti = QTableWidget.item(tbl, r, tc)
                if ti is None:
                    ti = QTableWidgetItem()
                    QTableWidget.setItem(tbl, r, tc, ti)
                ti.setTextAlignment(Qt.AlignCenter)
                ti.setFlags(ti.flags() & ~Qt.ItemIsEditable)
                ti.setBackground(QColor("#eef2f7"))
                if r in agg:
                    continue          # value comes from the UI aggregate (mirror)
                s = 0.0
                seen = False
                for c in range(tc):           # logical vehicle columns 0..tc-1
                    it = QTableWidget.item(tbl, r, c)
                    if it is None:
                        continue
                    txt = (it.text() or "").strip()
                    try:
                        s += float(txt)
                        seen = True
                    except ValueError:
                        pass
                ti.setText(("%g" % s) if seen else "")
        finally:
            tbl.blockSignals(False)

    def _traffic_total_agg_rows(self):
        """Row indices of the aggregate merged rows (AADT, PCU%/Units%,
        Heavy Veh %, Avg Veh Len (Clavg)) whose Total cell holds the single UI
        aggregate value rather than a per-vehicle sum.  Spacing stays editable
        in its own cell and is summed normally."""
        base = getattr(self, "_merge_base", None)
        if base is None:
            return set()
        return {base + 0, base + 1, base + 2, base + 3}

    def _on_veh_total_recalc(self, row, col):
        tc = getattr(self, "_veh_total_col", None)
        if tc is not None and col < tc:       # a vehicle cell changed
            self._recompute_traffic_totals()

    def _relocate_traffic_info(self):
        """Move the 'Traffic Volume & Vehicle Specs' group (renamed
        'Traffic Volume') and the pre-fire driving-state control frame into
        the General Input tab's Traffic Information panel, side by side."""
        gtab = self.general_input_tab
        try:
            veh = self._find_group("Traffic Volume & Vehicle Specs")
            if veh is not None:
                veh.setTitle("Traffic Volume")
                self._detach_widget(veh)
            # the control frame is the parent QFrame of evc_max_vehicles
            control = None
            anchor = getattr(self, "evc_max_vehicles", None)
            if anchor is not None:
                control = anchor.parentWidget()
                if control is not None:
                    self._detach_widget(control)
            gtab.mount_traffic_info(control, veh)
        except Exception as exc:
            print(f"[warning] traffic-info relocation failed: {exc}")

    # -- helpers for moving widgets out of (possibly nested) layouts --------
    @staticmethod
    def _find_layout_with(root_layout, w):
        if root_layout is None:
            return None
        for i in range(root_layout.count()):
            item = root_layout.itemAt(i)
            if item is None:
                continue
            if item.widget() is w:
                return root_layout
            sub = item.layout()
            if sub is not None:
                found = QRAMainWindowPlus._find_layout_with(sub, w)
                if found is not None:
                    return found
        return None

    def _detach_widget(self, w):
        """Remove w from whatever (possibly nested) layout currently holds
        it, so it can be re-added elsewhere without leaving a dangling item."""
        if w is None:
            return
        parent = w.parentWidget()
        top = parent.layout() if parent is not None else None
        lay = self._find_layout_with(top, w)
        if lay is not None:
            lay.removeWidget(w)

    def _find_group(self, title):
        from PyQt5.QtWidgets import QGroupBox
        for g in self.findChildren(QGroupBox):
            if g.title().strip() == title:
                return g
        return None

    def _relocate_basic_tunnel_info(self):
        """Reparent (not rebuild) the EVC/FED basic-spec and fire controls
        into the General Input tab's Basic Tunnel Information panel.  Every
        self.tbi_* / self.evc_* reference and signal connection stays valid."""
        from PyQt5.QtWidgets import (
            QGroupBox, QVBoxLayout, QHBoxLayout, QLabel)
        gtab = self.general_input_tab

        # 1) Tunnel Basic Specifications -> first column (keep its title) ----
        try:
            grp = self._find_group("Tunnel Basic Specifications")
            if grp is not None:
                gtab.mount_basic_info(grp)
        except Exception as exc:
            print(f"[warning] basic-spec relocation failed: {exc}")

        # 2) Fire Location, Evacuation Zone -> second column ----------------
        try:
            fz = self._find_group("Fire Location, Evacuation Zone")
            if fz is not None:
                self._detach_widget(fz)
                gtab.add_basic_info_widget(fz)
        except Exception as exc:
            print(f"[warning] fire-location relocation failed: {exc}")

        # 3) Fire Placement Mode controls (loose widgets) -> a new group,
        #    stacked above Fire Point Mapping as the third column -----------
        try:
            fp_grp = None
            rb_sym = getattr(self, "evc_fp_symmetric_rb", None)
            rb_asym = getattr(self, "evc_fp_asymmetric_rb", None)
            num_fp = getattr(self, "evc_num_fp_s4", None)
            est_btn = getattr(self, "evc_estimate_fp_btn", None)
            if any(w is not None for w in (rb_sym, rb_asym, num_fp, est_btn)):
                fp_grp = QGroupBox("Fire Placement")
                fp_grp.setStyleSheet("QGroupBox{font-weight:bold;}")
                fpv = QVBoxLayout(fp_grp)
                fpv.setContentsMargins(8, 6, 8, 8)
                fpv.setSpacing(4)
                r1 = QHBoxLayout()
                r1.addWidget(QLabel("Fire Placement Mode:"))
                for w in (rb_sym, rb_asym):
                    if w is not None:
                        self._detach_widget(w)
                        r1.addWidget(w)
                r1.addStretch()
                fpv.addLayout(r1)
                r2 = QHBoxLayout()
                r2.addWidget(QLabel("No. of Fire Points (per zone):"))
                for w in (num_fp, est_btn):
                    if w is not None:
                        self._detach_widget(w)
                        r2.addWidget(w)
                r2.addStretch()
                fpv.addLayout(r2)

            fpm = self._find_group("Fire Point Mapping")
            if fpm is not None:
                self._detach_widget(fpm)
            stack = [w for w in (fp_grp, fpm) if w is not None]
            if stack:
                gtab.add_basic_info_stack(stack)
        except Exception as exc:
            print(f"[warning] fire-placement relocation failed: {exc}")

    def _trim_traffic_ventilation(self):
        """Hide the 'Fire Positions (m)', 'Simulation Time T_END (s)' and
        'Total Scenarios' rows from the Traffic Ventilation panel.  The widgets
        are only hidden, not deleted -- the FDS writer still reads
        self.fire_positions_input.text() and self.tend_input.value(), and the
        Fire-Point-Mapping poll still keeps fire_positions_input current."""
        for anchor in (getattr(self, "fire_positions_input", None),
                       getattr(self, "tend_input", None),
                       getattr(self, "scenario_count_label", None)):
            if anchor is None:
                continue
            try:
                parent = anchor.parentWidget()
                top = parent.layout() if parent is not None else None
                row = self._find_layout_with(top, anchor)
                if row is None:
                    anchor.hide()
                    continue
                for i in range(row.count()):
                    it = row.itemAt(i)
                    w = it.widget() if it is not None else None
                    if w is not None:
                        w.hide()
                if top is not None:
                    top.removeItem(row)
            except Exception as exc:
                print(f"[warning] could not trim Traffic Ventilation row: {exc}")

    def _add_nvp_vent(self):
        """Add an 'NVP' ventilation check-box to the Traffic Ventilation panel,
        placed just before NVC.  Toggling it refreshes the folder preview."""
        from PyQt5.QtWidgets import QCheckBox
        nvc = getattr(self, "vent_nvc_check", None)
        if nvc is None or getattr(self, "vent_nvp_check", None) is not None:
            return
        try:
            parent = nvc.parentWidget()
            top = parent.layout() if parent is not None else None
            lay = self._find_layout_with(top, nvc)
            self.vent_nvp_check = QCheckBox("NVP")
            self.vent_nvp_check.setChecked(False)
            if lay is not None:
                lay.insertWidget(lay.indexOf(nvc), self.vent_nvp_check)
            self.vent_nvp_check.toggled.connect(
                lambda *_: self._safe_update_preview())
            # also refresh when the existing traffic / vent boxes change
            for attr in ("traffic_normal_check", "traffic_congested_check",
                         "vent_nvc_check", "vent_nv0_check", "vent_fvp_check",
                         "vent_fv0_check", "vent_fvm_check"):
                cb = getattr(self, attr, None)
                if cb is not None:
                    try:
                        cb.toggled.connect(lambda *_: self._safe_update_preview())
                    except Exception:
                        pass
        except Exception as exc:
            print(f"[warning] could not add NVP ventilation box: {exc}")

    def _safe_update_preview(self):
        try:
            self.update_directory_preview()
        except Exception:
            pass

    # ventilation order as it appears in the panel (NVP first, transverse only)
    _VENT_ORDER = [("vent_nvp_check", "NVP"), ("vent_nvc_check", "NVC"),
                   ("vent_nv0_check", "NV0"), ("vent_fvp_check", "FVP"),
                   ("vent_fv0_check", "FV0"), ("vent_fvm_check", "FVM")]

    def _traffic_folders(self):
        """Checked traffic conditions as folder names (app convention)."""
        out = []
        n = getattr(self, "traffic_normal_check", None)
        c = getattr(self, "traffic_congested_check", None)
        if n is not None and n.isChecked():
            out.append("Norm")
        if c is not None and c.isChecked():
            out.append("Cong")
        return out

    def _vent_folders(self):
        """Checked ventilation conditions, in panel order."""
        out = []
        for attr, code in self._VENT_ORDER:
            cb = getattr(self, attr, None)
            if cb is not None and cb.isChecked():
                out.append(code)
        return out

    def _apply_scenario_ventilation(self):
        """Set the ventilation defaults for the selected scenario: every
        standard option (NVC, NV0, FVP, FV0, FVM) is checked; NVP is checked
        only for the Transverse-Small-Vehicle scenario."""
        gtab = getattr(self, "general_input_tab", None)
        sp = getattr(gtab, "scenario_panel", None) if gtab else None
        sheet = (getattr(sp, "_sheet_name", "") or "").lower() if sp else ""
        transverse = "transverse" in sheet
        wanted = {
            "vent_nvp_check": transverse,
            "vent_nvc_check": True, "vent_nv0_check": True,
            "vent_fvp_check": True, "vent_fv0_check": True,
            "vent_fvm_check": True,
        }
        for attr, state in wanted.items():
            cb = getattr(self, attr, None)
            if cb is not None:
                try:
                    cb.blockSignals(True)
                    cb.setChecked(state)
                    cb.blockSignals(False)
                except Exception:
                    pass

    def _relocate_scenario_config(self):
        """Reparent (not rebuild) the app's 'Scenario Configuration' group
        (Fire Positions, Traffic, Ventilation, Flashover, T_END, scenario
        count) into the Scenario panel under the Control, renamed 'Traffic
        Ventilation'.  All self.fire_positions_input / vent_* / traffic_*
        references and signals stay valid."""
        gtab = getattr(self, "general_input_tab", None)
        sp = getattr(gtab, "scenario_panel", None) if gtab else None
        if sp is None:
            return
        try:
            grp = self._find_group("Scenario Configuration")
            if grp is not None:
                self._detach_widget(grp)
                grp.setTitle("Traffic Ventilation")
                sp.mount_traffic_ventilation(grp)
        except Exception as exc:
            print(f"[warning] scenario-config relocation failed: {exc}")

    def _bind_fire_positions(self):
        """Drive the Traffic-Ventilation 'Fire Positions (m)' field from the
        Fire Point Mapping table's 'Fire pt. X' column (col 1) above it, and
        hide the 'MDB pt. X' column.  The table is often bulk-filled with its
        signals blocked, so a light poll (not just itemChanged) keeps the field
        in sync.  MDB pt. X is only hidden -- the engine still reads col 2 for
        smoke-field anchoring."""
        from PyQt5.QtCore import QTimer
        tbl = getattr(self, "evc_fpm_table_s4", None)
        inp = getattr(self, "fire_positions_input", None)
        if tbl is None or inp is None:
            return
        try:
            tbl.setColumnHidden(2, True)        # hide MDB pt. X (kept for engine)
        except Exception:
            pass
        try:
            inp.setReadOnly(True)
            inp.setToolTip("Read from Fire Point Mapping (Fire pt. X)")
            inp.setStyleSheet("background:#eef2f7;")
        except Exception:
            pass
        self._fp_last = None

        def pull(*_):
            vals = []
            for r in range(tbl.rowCount()):
                it = tbl.item(r, 1)            # "Fire pt. X"
                if it is None:
                    continue
                t = (it.text() or "").strip()
                if not t:
                    continue
                try:
                    vals.append("%g" % float(t))
                except ValueError:
                    continue
            s = ", ".join(vals)
            if s and s != self._fp_last:
                self._fp_last = s
                inp.setText(s)

        for sig in ("itemChanged", "cellChanged"):
            s = getattr(tbl, sig, None)
            if s is not None:
                try:
                    s.connect(pull)
                except Exception:
                    pass
        # poll for the bulk, signal-blocked fills (estimate / autofill / clear)
        self._fp_timer = QTimer(self)
        self._fp_timer.setInterval(400)
        self._fp_timer.timeout.connect(pull)
        self._fp_timer.start()
        pull()

    def _brand_header(self):
        """Re-brand the landing header: add 'Bumchang Engineering Co. LTD' in
        black above the centred title, insert '(QRA)' into the title, and drop
        the 'Tunnel Fire Risk Assessment ...' subtitle."""
        from PyQt5.QtWidgets import QLabel
        from PyQt5.QtGui import QFont
        from PyQt5.QtCore import Qt
        try:
            title = subtitle = None
            for lbl in self.findChildren(QLabel):
                t = lbl.text()
                if t == "Quantitative Risk Assessment System":
                    title = lbl
                elif t.startswith("Tunnel Fire Risk Assessment"):
                    subtitle = lbl
            if title is not None:
                title.setText("Quantitative Risk Assessment (QRA) System")
                lay = title.parentWidget().layout()
                if lay is not None and getattr(self, "_brand_done", False) is False:
                    company = QLabel("Bumchang Engineering Co. LTD")
                    cf = QFont(); cf.setPointSize(14); cf.setBold(True)
                    company.setFont(cf)
                    company.setAlignment(Qt.AlignCenter)
                    company.setStyleSheet("color: #000000; margin-top: 8px;")
                    lay.insertWidget(lay.indexOf(title), company)
                    self._brand_done = True
            if subtitle is not None:
                lay = subtitle.parentWidget().layout()
                if lay is not None:
                    lay.removeWidget(subtitle)
                subtitle.hide()
                subtitle.deleteLater()
        except Exception as exc:
            print(f"[warning] header re-brand failed: {exc}")

    def _relocate_project_directory(self):
        """Reparent (not rebuild) the Directory-Setup tab's 'Project
        Configuration' and 'Directory Structure Preview' group boxes into the
        General Input tab's 'Project Directory' panel, side by side.  The
        'Setup Progress' group and the Create / Open-Existing-Project buttons
        are tucked inside the Project Configuration group, beneath its fields.
        Every self.project_name_input / self.dir_tree / self.dir_progress_bar
        / self.create_project_btn reference and signal stays valid."""
        from PyQt5.QtWidgets import QHBoxLayout
        gtab = getattr(self, "general_input_tab", None)
        if gtab is None:
            return
        try:
            cfg = self._find_group("Project Configuration")
            prev = self._find_group("Directory Structure Preview")

            # 1) Setup Progress + buttons -> inside Project Configuration ----
            if cfg is not None and cfg.layout() is not None:
                clay = cfg.layout()
                prog = self._find_group("Setup Progress")
                if prog is not None:
                    self._detach_widget(prog)
                    clay.addWidget(prog)
                btn_row = QHBoxLayout()
                for b in (getattr(self, "create_project_btn", None),
                          getattr(self, "open_project_btn", None)):
                    if b is not None:
                        self._detach_widget(b)
                        btn_row.addWidget(b)
                if btn_row.count():
                    clay.addLayout(btn_row)

            # 2) the two groups -> the Project Directory panel --------------
            for g in (cfg, prev):
                if g is not None:
                    self._detach_widget(g)
            gtab.mount_project_directory(cfg, prev)
        except Exception as exc:
            print(f"[warning] project-directory relocation failed: {exc}")

    def _bind_project_name_default(self):
        """Use the Basic Tunnel Information tunnel name as the project's
        default name: prefill 'Project Name' from the tunnel name and keep it
        in sync until the user types a custom project name of their own."""
        src = getattr(self, "tbi_tunnel_name", None)
        dst = getattr(self, "project_name_input", None)
        if src is None or dst is None:
            return
        self._last_pushed_pname = ""

        def push(*_):
            try:
                name = src.text().strip()
            except Exception:
                return
            if not name:
                return
            cur = dst.text().strip()
            if cur == "" or cur == self._last_pushed_pname:
                dst.setText(name)        # fires update_directory_preview
                self._last_pushed_pname = name
        try:
            src.textChanged.connect(push)
        except Exception:
            return
        push()   # initial default

    def _bind_scenario_hrr(self):
        """Selecting a Scenario drives the HRR used to build the fdb / evc /
        fds files: the scenario's distinct fire sizes become the FDS HRR
        selection (standard check-boxes + custom list) and the EVC peak-HRR
        fields, replacing the manual basic-information selection."""
        gtab = getattr(self, "general_input_tab", None)
        sp = getattr(gtab, "scenario_panel", None) if gtab else None
        if sp is None or not hasattr(sp, "scenarioSelected"):
            return
        try:
            sp.scenarioSelected.connect(self._apply_scenario_hrr)
        except Exception:
            return
        self._apply_scenario_hrr()   # initial sync

    _STD_HRR = {5: "hrr_005_check", 10: "hrr_010_check", 20: "hrr_020_check",
                30: "hrr_030_check", 50: "hrr_050_check", 100: "hrr_100_check"}

    def _apply_scenario_hrr(self):
        gtab = getattr(self, "general_input_tab", None)
        sp = getattr(gtab, "scenario_panel", None) if gtab else None
        if sp is None:
            return
        try:
            hrrs = sp.selected_hrr_mw()
        except Exception:
            return
        if not hrrs:
            return
        want = set(int(round(h)) for h in hrrs)

        # FDS standard HRR check-boxes
        for mw, attr in self._STD_HRR.items():
            cb = getattr(self, attr, None)
            if cb is None:
                continue
            try:
                cb.blockSignals(True)
                cb.setChecked(mw in want)
                cb.blockSignals(False)
            except Exception:
                pass

        # non-standard sizes (e.g. 15 MW) become custom HRR entries
        custom = getattr(self, "custom_hrr_list", None)
        lw = getattr(self, "custom_hrr_list_widget", None)
        extras = sorted(want - set(self._STD_HRR.keys()))
        if isinstance(custom, list) and lw is not None:
            try:
                custom.clear()
                lw.clear()
                for mw in extras:
                    custom.append(mw)
                    lw.addItem(f"{mw} MW")
            except Exception:
                pass

        # EVC peak-HRR fields -> governing (largest) fire of the scenario
        peak = float(max(want))
        for attr in ("evc_peak_hrr", "evc_peak_hrr_s4"):
            sb = getattr(self, attr, None)
            if sb is None:
                continue
            try:
                sb.blockSignals(True)
                sb.setValue(peak)
                sb.blockSignals(False)
            except Exception:
                pass

        # ventilation defaults for this scenario (NVP only for Transverse)
        self._apply_scenario_ventilation()

        # let the app refresh fuel auto-selection / scenario count
        for fn in ("on_hrr_selection_changed", "calculate_scenario_count"):
            f = getattr(self, fn, None)
            if callable(f):
                try:
                    f()
                except Exception:
                    pass

        # refresh the Directory Structure Preview so the fds_inputs HRR
        # sub-folders reflect the scenario fire sizes.
        try:
            self.update_directory_preview()
        except Exception:
            pass

    def _scenario_hrr_codes(self):
        """3-digit fds_inputs sub-folder codes (e.g. '005','010','020','030',
        '100') from the fire sizes of the *currently selected* scenario --
        the fire nodes shown in the Node Connection Diagram.  Changes whenever
        another scenario is selected.  Falls back to the app default if the
        panel is unavailable."""
        gtab = getattr(self, "general_input_tab", None)
        sp = getattr(gtab, "scenario_panel", None) if gtab else None
        sizes = []
        if sp is not None:
            try:
                sizes = sp.selected_hrr_mw()
            except Exception:
                sizes = []
        if not sizes:
            return ["020", "030", "100"]
        return [f"{int(round(s)):03d}" for s in sizes]

    def update_directory_preview(self):
        """Base preview, then rebuild the fds_inputs sub-tree as
        {HRR}/{traffic}/{ventilation} from the scenario + Traffic-Ventilation
        selections."""
        try:
            super().update_directory_preview()
        except Exception:
            return
        try:
            from PyQt5.QtWidgets import QTreeWidgetItem
            tree = getattr(self, "dir_tree", None)
            if tree is None or tree.topLevelItemCount() == 0:
                return
            root = tree.topLevelItem(0)
            codes = self._scenario_hrr_codes()
            traffic = self._traffic_folders() or ["Norm"]
            vents = self._vent_folders() or ["NVC"]
            for i in range(root.childCount()):
                node = root.child(i)
                if "fds_inputs" in node.text(0):
                    node.takeChildren()
                    for c in codes:
                        cnode = QTreeWidgetItem(node); cnode.setText(0, f"  {c}/")
                        for t in traffic:
                            tnode = QTreeWidgetItem(cnode); tnode.setText(0, f"  {t}/")
                            for v in vents:
                                vnode = QTreeWidgetItem(tnode)
                                vnode.setText(0, f"  {v}/")
                            tnode.setExpanded(True)
                        cnode.setExpanded(True)
                    node.setExpanded(True)
                    break
        except Exception:
            pass

    def create_project(self):
        """Create the project as usual, then build the
        fds_inputs/{HRR}/{traffic}/{ventilation}/ folder tree from the scenario
        and the Traffic-Ventilation selections."""
        try:
            super().create_project()
        except Exception:
            raise
        try:
            from pathlib import Path
            pd = getattr(self, "project_dir", None)
            if pd:
                base = Path(pd) / "fds_inputs"
                codes = self._scenario_hrr_codes()
                # drop the base's hardcoded empty HRR placeholders (e.g.
                # 020/030/100) that aren't part of this scenario
                if base.exists():
                    for child in list(base.iterdir()):
                        if child.is_dir() and child.name not in codes:
                            try:
                                child.rmdir()      # only succeeds if empty
                            except OSError:
                                pass
                traffic = self._traffic_folders() or ["Norm"]
                vents = self._vent_folders() or ["NVC"]
                made = 0
                for c in codes:
                    for t in traffic:
                        for v in vents:
                            (base / c / t / v).mkdir(parents=True, exist_ok=True)
                            made += 1
                status = getattr(self, "dir_status_text", None)
                if status is not None:
                    status.append(
                        "✓ fds_inputs tree: %d HRR x %d traffic x %d vent = %d "
                        "leaf folders (%s / %s)" % (
                            len(codes), len(traffic), len(vents), made,
                            ", ".join(traffic), ", ".join(vents)))
        except Exception as exc:
            print(f"[warning] scenario folder-tree creation failed: {exc}")

    # -- NVP support for the app's built-in .fds writer --------------------
    def generate_fds_files(self):
        """Run the app's standard generation (NVC/NV0/FVP/FV0/FVM), then add
        an NVP pass -- the base writer's vent list doesn't include NVP."""
        super().generate_fds_files()
        try:
            self._generate_nvp_fds_files()
        except Exception as exc:
            st = getattr(self, "fds_status_text", None)
            (st.append if st is not None else print)(
                f"⚠️ NVP FDS generation failed: {exc}")

    @staticmethod
    def _load_fds_gen_classes():
        """Load FDSInputGenerator / TunnelGeometry / FireScenario the same way
        the base app does (import, else load the root-level file directly)."""
        import importlib.util, types
        from pathlib import Path
        try:
            from fds_generator import (FDSInputGenerator, TunnelGeometry,
                                        FireScenario)
            return FDSInputGenerator, TunnelGeometry, FireScenario
        except Exception:
            pass
        try:
            gp = Path(__file__).parent / "fds_generator.py"
            spec = importlib.util.spec_from_file_location("fds_generator_root", gp)
            mod = types.ModuleType("fds_generator_root")
            spec.loader.exec_module(mod)
            return (getattr(mod, "FDSInputGenerator", None),
                    getattr(mod, "TunnelGeometry", None),
                    getattr(mod, "FireScenario", None))
        except Exception:
            return None, None, None

    def _generate_nvp_fds_files(self):
        """Write the NVP ventilation .fds files into
        fds_inputs/{HRR}/{Norm|Cong}/NVP/, mirroring the base loop but for the
        NVP condition only.  Runs only when the NVP box is ticked (i.e. the
        Transverse-Small-Vehicle scenario)."""
        nvp = getattr(self, "vent_nvp_check", None)
        if nvp is None or not nvp.isChecked():
            return
        if not getattr(self, "project_dir", None):
            return
        st = getattr(self, "fds_status_text", None)
        Gen, Geo, Scn = self._load_fds_gen_classes()
        if not all((Gen, Geo, Scn)):
            if st is not None:
                st.append("⚠️ NVP skipped: fds_generator classes unavailable.")
            return
        from pathlib import Path

        hrr_map = [("hrr_005_check", "005", 5000), ("hrr_010_check", "010", 10000),
                   ("hrr_020_check", "020", 20000), ("hrr_030_check", "030", 30000),
                   ("hrr_050_check", "050", 50000), ("hrr_100_check", "100", 100000)]
        hrr_list = [(c, v) for a, c, v in hrr_map
                    if getattr(self, a, None) is not None and getattr(self, a).isChecked()]
        for hrr_val in (getattr(self, "custom_hrr_list", None) or []):
            try:
                hrr_list.append(("%03d" % int(hrr_val), int(hrr_val) * 1000))
            except (ValueError, TypeError):
                pass
        traffic_list = []
        if self.traffic_normal_check.isChecked():
            traffic_list.append("Normal")
        if self.traffic_congested_check.isChecked():
            traffic_list.append("Congested")
        pos_txt = self.fire_positions_input.text().strip()
        if not (hrr_list and traffic_list and pos_txt):
            return
        try:
            fire_positions = [float(p.strip()) for p in pos_txt.split(",") if p.strip()]
        except ValueError:
            return

        fds_version = "FDS6" if self.fds6_radio.isChecked() else "FDS5"
        fuel_type = self.fuel_type_combo.currentText()
        fp = {"Petrol": {"fuel_id": "PETROL_CAR_FIRE", "fuel": "ISO_OCTANE"},
              "Diesel": {"fuel_id": "DIESEL", "fuel": "N-DODECANE"},
              "CNG": {"fuel_id": "CNG", "fuel": "METHANE"},
              "LPG": {"fuel_id": "LPG", "fuel": "PROPANE"},
              "EVC": {"fuel_id": "EVC", "fuel": "PROPANE"}}.get(
                  fuel_type, {"fuel_id": "DIESEL", "fuel": "N-DODECANE"})
        soot = self.soot_yield_input.value()
        co = self.co_yield_input.value()
        hoc = self.heat_of_combustion_input.value()
        radius = self.tunnel_radius_input.value()
        tunnel = Geo(length=self.tunnel_length_input.value(),
                     width=radius * 2, height=radius * 2)
        gen = Gen(tunnel)

        vent = "NVP"
        made = 0
        for hrr_code, hrr_val in hrr_list:
            for traffic in traffic_list:
                tcode = traffic[0]
                tfolder = "Norm" if traffic == "Normal" else "Cong"
                vdir = Path(self.project_dir) / "fds_inputs" / hrr_code / tfolder / vent
                vdir.mkdir(parents=True, exist_ok=True)
                for pos in fire_positions:
                    fname = f"{hrr_code}_{tcode}_{vent}_pos{int(pos)}.fds"
                    scenario = Scn(
                        hrr_type=hrr_code, hrr_value=hrr_val, fire_position=pos,
                        flashover_time=self.flashover_input.value(),
                        traffic_condition=traffic, ventilation_condition=vent,
                        t_end=self.tend_input.value(), fuel_type=fuel_type,
                        fuel_id=fp["fuel_id"], fuel=fp["fuel"], soot_yield=soot,
                        co_yield=co, heat_of_combustion=hoc, fds_version=fds_version)
                    gen.generate_fds_input(scenario, str(vdir / fname))
                    made += 1
        if st is not None:
            st.append("✅ Generated %d NVP FDS files "
                      "(ventilation_condition='NVP')." % made)

    def _on_main_tab_changed(self, index: int):
        """The original handler creates EVC/FED directories only when the
        EVC/FED tab is shown (originally index 3).  Because tabs were
        inserted and reordered, locate that tab by title and map it to the
        original index 3 so the directory auto-creation still fires; pass a
        no-op index otherwise."""
        if not _HAS_GENERAL_TAB:
            return super()._on_main_tab_changed(index)
        try:
            evc_idx = -1
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == "EVC/FED Analysis":
                    evc_idx = i
                    break
            super()._on_main_tab_changed(3 if index == evc_idx else -1)
        except Exception:
            # Never let a tab-change side effect crash the UI.
            pass


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Surface the module-load log the original app prints, if present.
    app_dir = getattr(qra, "app_dir", _HERE)
    print(f"QRA System  |  {app_dir}")
    _log = getattr(qra, "_import_log", None)
    if _log:
        print("Module status:")
        for _msg in _log:
            print(_msg)
    if not _HAS_GENERAL_TAB:
        print(f"[warning] General Input Information tab not loaded: {_GENERAL_TAB_ERR}")

    # ---- authentication ------------------------------------------
    try:
        import qra_auth
    except Exception as exc:
        # Auth module missing -> fall back to the app with no login.
        print(f"[warning] qra_auth unavailable, launching without login: {exc}")
        window = QRAMainWindowPlus()
        window.show()
        sys.exit(app.exec_())

    store = qra_auth.AuthStore(os.path.join(_HERE, "qra_users.json"))

    # quick loading signal before the login page
    qra_auth.SplashScreen(message="Starting up\u2026").run(app, duration_ms=800)

    # login -> load loop (supports Sign Out)
    while True:
        login = qra_auth.LoginDialog(store)
        if login.exec_() != QDialog.Accepted:
            return 0                      # user cancelled -> exit

        # short loading splash, then build the main window
        splash = qra_auth.SplashScreen(message="Loading General Input Information\u2026")
        splash.show()
        app.processEvents()
        splash.run(app, duration_ms=700)

        window = QRAMainWindowPlus()
        window._signed_out = False

        def _sign_out(win=window):
            win._signed_out = True
            win.close()

        qra_auth.install_account_menu(
            window, store, login.username, login.role, on_sign_out=_sign_out)

        # land on the General Input Information tab
        try:
            if getattr(window, "general_input_tab", None) is not None:
                window.tabs.setCurrentWidget(window.general_input_tab)
            else:
                window.tabs.setCurrentIndex(0)
        except Exception:
            pass

        splash.close()
        window.show()

        if not _HAS_GENERAL_TAB:
            QMessageBox.warning(
                window, "General Input tab unavailable",
                "The app started without the General Input Information tab.\n\n"
                f"Reason: {_GENERAL_TAB_ERR}\n\n"
                "Make sure general_input_tab.py is in the same folder as "
                "qra_main_app.py.")

        app.exec_()                       # blocks until the window closes

        if not getattr(window, "_signed_out", False):
            return 0                      # window closed normally -> exit
        # else loop back to the login page


if __name__ == "__main__":
    main()