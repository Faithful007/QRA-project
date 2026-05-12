# main_gui.py

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter import font as tkFont
import math
import sys
import os
import webbrowser
import json
from datetime import datetime
from pathlib import Path
from vent_functions import (
    TunnelVentInputs,
    compute_all,
    JET_AREA_MAP,
)
from speed_grade_tables import get_all_overrides, set_table_override


class NumericValidator:
    """Helper class for numeric input validation across the GUI."""
    
    @staticmethod
    def validate_numeric(s, d):
        """Validate that input is numeric (int or float).
        s: string being inserted (single character)
        d: type of action (1=insert, 0=delete)
        """
        if d == 0:  # Allow deletion
            return True
        if s == "":  # Allow empty string
            return True
        # Allow digits, decimal point, and negative sign
        # s is a single character being typed
        if s in '0123456789.-':
            return True
        return False
    
    @staticmethod
    def clear_on_focus(event):
        """Clear entry widget on focus (click or tab)."""
        entry = event.widget
        entry.delete(0, tk.END)
        # Also clear the associated variable to prevent re-display
        try:
            var_name = entry.cget('textvariable')
            if var_name:
                entry.tk.setvar(var_name, '')
        except Exception:
            pass
    
    @staticmethod
    def default_to_zero_on_focusout(event):
        """Set field to 0 if empty when focus is lost."""
        entry = event.widget
        try:
            value = entry.get().strip()
            if value == "":
                entry.delete(0, tk.END)
                entry.insert(0, "0")
                # Update the associated variable
                var_name = entry.cget('textvariable')
                if var_name:
                    entry.tk.setvar(var_name, '0')
        except Exception:
            pass

    @staticmethod
    def check_valid_numbers(var_list, field_names=None):
        """Check if all variables contain valid numbers.
        Returns tuple (is_valid, invalid_fields_str)
        """
        invalid_fields = []
        for i, var in enumerate(var_list):
            try:
                val = var.get()
                if val and val.strip():  # If not empty
                    float(val)
            except (ValueError, AttributeError):
                if field_names and i < len(field_names):
                    invalid_fields.append(field_names[i])
                else:
                    invalid_fields.append(f"Field {i+1}")
        
        is_valid = len(invalid_fields) == 0
        invalid_str = ", ".join(invalid_fields)
        return is_valid, invalid_str


class JetFanTab(ttk.Frame):
    """
    First tab: 'Number of Jet Fan'
    - V_kmh: selectable from [10, 20, 30, 40, 50, 60, 70, 80] (Un computed from this)
    - Qtreq, Ar, Lr, Dr: user-editable variables
    - Un (computed), Vr (computed), rho, xi, lamb, Ae, eta: constants (shown but not editable)
    - jet_diameter: dropdown based on JET_AREA_MAP keys
    - high_efficiency: dropdown (High efficiency / Standard)
    """

    def __init__(self, parent, result_tab=None, volume_tab=None):
        super().__init__(parent)
        self.result_tab = result_tab
        self.volume_tab = volume_tab
        self._build_variables()
        self._build_layout()
        self._wire_volume_sources()
        self._recompute_dynamic()

    # ----------------------------
    # 1) Variables for widgets
    # ----------------------------
    def _build_variables(self):
        # V_kmh as a selectable value (combobox) - SHARED ACROSS BOTH DIRECTIONS
        self.v_kmh_var = tk.DoubleVar(value=10.0)   # set to least selectable 10 km/h

        # Jet diameter and high efficiency - SHARED ACROSS BOTH DIRECTIONS
        jet_keys = sorted(JET_AREA_MAP.keys())
        self.jet_choices = [str(k) for k in jet_keys]
        smallest_jet = self.jet_choices[0]
        self.jet_diameter_var = tk.StringVar(value=smallest_jet)

        self.high_eff_choices = [
            "High efficiency (30 m/s)",   # True
            "Standard (34 m/s)",          # False
        ]
        self.high_eff_var = tk.StringVar(value=self.high_eff_choices[0])

        # Constants (shared)
        self.un_var = tk.DoubleVar(value=2.5)       # Un is constant for Jet Fan calc
        from vent_functions import Vt_MAP
        initial_key = int(self.v_kmh_var.get())
        self.vt_var = tk.DoubleVar(value=Vt_MAP.get(initial_key, Vt_MAP.get(10)))
        self.rho_var = tk.DoubleVar(value=1.2)      # constant rho
        self.xi_var = tk.DoubleVar(value=0.6)      # constant xi
        self.lamb_var = tk.DoubleVar(value=0.025)   # constant lamb
        self.ae_var = tk.DoubleVar(value=1.0751)    # constant Ae
        self.eta_var = tk.DoubleVar(value=0.95)     # constant eta

        # Direction 1 (FROM→TO, Destination) variables
        self.qtreq_dir1_var = tk.DoubleVar(value=0.0)
        self.lanes_dir1_var = tk.IntVar(value=1)
        self.ar_dir1_var = tk.DoubleVar(value=1.0)
        self.lr_dir1_var = tk.DoubleVar(value=1.0)
        self.dr_dir1_var = tk.DoubleVar(value=1.0)
        self.imax_dir1_var = tk.DoubleVar(value=0.0)
        self.exact_z_dir1_var = tk.StringVar(value="-")
        self.approx_z_dir1_var = tk.StringVar(value="-")

        # Direction 2 (TO→FROM, Destination) variables
        self.qtreq_dir2_var = tk.DoubleVar(value=0.0)
        self.lanes_dir2_var = tk.IntVar(value=1)
        self.ar_dir2_var = tk.DoubleVar(value=1.0)
        self.lr_dir2_var = tk.DoubleVar(value=1.0)
        self.dr_dir2_var = tk.DoubleVar(value=1.0)
        self.imax_dir2_var = tk.DoubleVar(value=0.0)
        self.exact_z_dir2_var = tk.StringVar(value="-")
        self.approx_z_dir2_var = tk.StringVar(value="-")

        # Legacy variables for backward compatibility (can be removed later)
        self.result_var = tk.StringVar(value="")
        
        # References to LabelFrame widgets for dynamic title updates
        self.dir1_labelframe = None
        self.dir2_labelframe = None

    # ----------------------------
    # 2) Layout / widgets
    # ----------------------------
    def _build_layout(self):
        # Create a main container with padding
        main_container = ttk.Frame(self, padding="20 20 20 20")
        main_container.pack(fill="both", expand=True)
        
        # Get direction names from volume_tab if available
        dir1_name = "FROM"
        dir2_name = "TO"
        if self.volume_tab:
            try:
                dir1_name = self.volume_tab.dir1Name.get()
                dir2_name = self.volume_tab.dir2Name.get()
            except:
                pass
        
        pad = 6
        
        # ============ TOP SECTION: Shared controls (V_kmh, jet_diameter, high_eff) ============
        top_frame = ttk.LabelFrame(main_container, text="Shared Parameters", padding="10 10 10 10")
        top_frame.pack(fill="x", padx=0, pady=(0, pad * 3))
        
        # Row 0: Driving speed V_kmh
        ttk.Label(top_frame, text="Driving speed, V_kmh [km/h]:").grid(
            row=0, column=0, sticky="e", padx=pad, pady=pad
        )
        v_kmh_cb = ttk.Combobox(
            top_frame,
            textvariable=self.v_kmh_var,
            values=[10, 20, 30, 40, 50, 60, 70, 80],
            state="readonly",
            width=10,
        )
        v_kmh_cb.bind("<<ComboboxSelected>>", self._on_vkmh_changed)
        v_kmh_cb.grid(row=0, column=1, sticky="w", padx=pad, pady=pad)
        
        # Row 0: Jet fan diameter (continuing on same row)
        ttk.Label(top_frame, text="Jet fan diameter, Φ [mm]:").grid(
            row=0, column=2, sticky="e", padx=pad, pady=pad
        )
        jet_cb = ttk.Combobox(
            top_frame,
            textvariable=self.jet_diameter_var,
            values=self.jet_choices,
            state="readonly",
            width=12,
        )
        jet_cb.grid(row=0, column=3, sticky="w", padx=pad, pady=pad)
        
        # Row 1: Jet fan type
        ttk.Label(top_frame, text="Jet fan type:").grid(
            row=1, column=0, sticky="e", padx=pad, pady=pad
        )
        eff_cb = ttk.Combobox(
            top_frame,
            textvariable=self.high_eff_var,
            values=self.high_eff_choices,
            state="readonly",
            width=22,
        )
        eff_cb.grid(row=1, column=1, columnspan=3, sticky="w", padx=pad, pady=pad)
        
        # Configure columns for top frame
        top_frame.columnconfigure(0, weight=0)
        top_frame.columnconfigure(1, weight=1)
        top_frame.columnconfigure(2, weight=0)
        top_frame.columnconfigure(3, weight=1)
        
        # ============ TWO-COLUMN SECTION: Direction 1 and Direction 2 ============
        columns_frame = ttk.Frame(main_container)
        columns_frame.pack(fill="both", expand=True)
        
        # Left column (DIR1): FROM → TO
        self._build_direction_column(columns_frame, 0, dir1_name, dir2_name, 
                                     self.qtreq_dir1_var, self.lanes_dir1_var, 
                                     self.ar_dir1_var, self.lr_dir1_var, self.dr_dir1_var,
                                     self.exact_z_dir1_var, self.approx_z_dir1_var,
                                     self.imax_dir1_var)
        
        # Right column (DIR2): TO → FROM
        self._build_direction_column(columns_frame, 1, dir2_name, dir1_name, 
                                     self.qtreq_dir2_var, self.lanes_dir2_var, 
                                     self.ar_dir2_var, self.lr_dir2_var, self.dr_dir2_var,
                                     self.exact_z_dir2_var, self.approx_z_dir2_var,
                                     self.imax_dir2_var)
        
        # Configure column weights for two-column layout
        columns_frame.columnconfigure(0, weight=1)
        columns_frame.columnconfigure(1, weight=1)
        
        # ============ BOTTOM SECTION: Constants ============
        bottom_frame = ttk.LabelFrame(main_container, text="Jet Fan Constants", padding="10 10 10 10")
        bottom_frame.pack(fill="x", padx=0, pady=(pad * 3, 0))
        
        # Row 0: Un, Vt
        ttk.Label(bottom_frame, text="Natural wind speed Un (m/s):").grid(
            row=0, column=0, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(bottom_frame, textvariable=self.un_var, width=12, state="readonly").grid(
            row=0, column=1, sticky="w", padx=pad, pady=pad
        )
        
        ttk.Label(bottom_frame, text="Driving speed Vt (m/s):").grid(
            row=0, column=2, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(bottom_frame, textvariable=self.vt_var, width=12, state="readonly").grid(
            row=0, column=3, sticky="w", padx=pad, pady=pad
        )
        
        # Row 1: ρ, ξ
        ttk.Label(bottom_frame, text="Air density ρ (kg/m³):").grid(
            row=1, column=0, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(bottom_frame, textvariable=self.rho_var, width=12, state="readonly").grid(
            row=1, column=1, sticky="w", padx=pad, pady=pad
        )
        
        ttk.Label(bottom_frame, text="Entrance loss ξ:").grid(
            row=1, column=2, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(bottom_frame, textvariable=self.xi_var, width=12, state="readonly").grid(
            row=1, column=3, sticky="w", padx=pad, pady=pad
        )
        
        # Row 2: λ, Ae
        ttk.Label(bottom_frame, text="Friction loss λ:").grid(
            row=2, column=0, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(bottom_frame, textvariable=self.lamb_var, width=12, state="readonly").grid(
            row=2, column=1, sticky="w", padx=pad, pady=pad
        )
        
        ttk.Label(bottom_frame, text="Equivalent resistance Ae (m²):").grid(
            row=2, column=2, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(bottom_frame, textvariable=self.ae_var, width=12, state="readonly").grid(
            row=2, column=3, sticky="w", padx=pad, pady=pad
        )
        
        # Row 3: η
        ttk.Label(bottom_frame, text="Jet fan efficiency η:").grid(
            row=3, column=0, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(bottom_frame, textvariable=self.eta_var, width=12, state="readonly").grid(
            row=3, column=1, sticky="w", padx=pad, pady=pad
        )
        
        # Configure columns for bottom frame
        bottom_frame.columnconfigure(0, weight=0)
        bottom_frame.columnconfigure(1, weight=1)
        bottom_frame.columnconfigure(2, weight=0)
        bottom_frame.columnconfigure(3, weight=1)

    def _build_direction_column(self, parent, col_idx, dir_from, dir_to,
                                 qtreq_var, lanes_var, ar_var, lr_var, dr_var,
                                 exact_z_var, approx_z_var, imax_var):
        """Build a single direction column for bidirectional layout.
        
        Args:
            parent: Parent frame
            col_idx: Column index for this direction (0 or 1)
            dir_from: Direction label (e.g., "FROM" or "TO")
            dir_to: Opposite direction label
            qtreq_var, lanes_var, ar_var, lr_var, dr_var: Variables for this direction
            exact_z_var, approx_z_var: Result variables
            imax_var: Capacity variable
        """
        pad = 6
        
        # Create frame for this column
        col_frame = ttk.LabelFrame(parent, text=f"Calculate number needed from {dir_from} to {dir_to}", 
                                   padding="10 10 10 10")
        col_frame.grid(row=0, column=col_idx, sticky="nsew", padx=pad, pady=0)
        
        # Store reference for dynamic title updates
        if col_idx == 0:
            self.dir1_labelframe = col_frame
        else:
            self.dir2_labelframe = col_frame
        
        # Register numeric validation
        vcmd = (self.register(NumericValidator.validate_numeric), '%S', '%d')
        
        row = 0
        
        # Required ventilation Qtreq
        ttk.Label(col_frame, text="Required ventilation Qtreq (m³/s):").grid(
            row=row, column=0, sticky="e", padx=pad, pady=pad
        )
        entry_qtreq = ttk.Entry(col_frame, textvariable=qtreq_var, width=12,
                 validate="key", validatecommand=vcmd)
        entry_qtreq.grid(row=row, column=1, sticky="w", padx=pad, pady=pad)
        entry_qtreq.bind('<FocusIn>', NumericValidator.clear_on_focus)
        entry_qtreq.bind('<FocusOut>', NumericValidator.default_to_zero_on_focusout)
        row += 1
        
        # Number of lanes
        ttk.Label(col_frame, text="Number of lanes:").grid(
            row=row, column=0, sticky="e", padx=pad, pady=pad
        )
        entry_lanes = ttk.Entry(col_frame, textvariable=lanes_var, width=12,
                 validate="key", validatecommand=vcmd)
        entry_lanes.grid(row=row, column=1, sticky="w", padx=pad, pady=pad)
        entry_lanes.bind('<FocusIn>', NumericValidator.clear_on_focus)
        entry_lanes.bind('<FocusOut>', NumericValidator.default_to_zero_on_focusout)
        row += 1
        
        # Tunnel cross-sectional area Ar
        ttk.Label(col_frame, text="Tunnel cross-sectional area Ar (m²):").grid(
            row=row, column=0, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(col_frame, textvariable=ar_var, width=12, state="readonly").grid(
            row=row, column=1, sticky="w", padx=pad, pady=pad
        )
        row += 1
        
        # Tunnel length Lr
        ttk.Label(col_frame, text="Tunnel length Lr (m):").grid(
            row=row, column=0, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(col_frame, textvariable=lr_var, width=12, state="readonly").grid(
            row=row, column=1, sticky="w", padx=pad, pady=pad
        )
        row += 1
        
        # Representative diameter Dr
        ttk.Label(col_frame, text="Representative diameter Dr (m):").grid(
            row=row, column=0, sticky="e", padx=pad, pady=pad
        )
        ttk.Entry(col_frame, textvariable=dr_var, width=12, state="readonly").grid(
            row=row, column=1, sticky="w", padx=pad, pady=pad
        )
        row += 1
        
        # Separator
        ttk.Separator(col_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(pad * 3, pad * 2)
        )
        row += 1
        
        # Results
        ttk.Label(col_frame, text="Exact number of Jet Fans required:").grid(
            row=row, column=0, sticky="e", padx=pad, pady=(pad, 0)
        )
        ttk.Label(col_frame, textvariable=exact_z_var, foreground="#004080", font=("Arial", 11, "bold")).grid(
            row=row, column=1, sticky="w", padx=pad, pady=(pad, 0)
        )
        row += 1
        
        ttk.Label(col_frame, text="Approximated number required:").grid(
            row=row, column=0, sticky="e", padx=pad, pady=(0, pad)
        )
        ttk.Label(col_frame, textvariable=approx_z_var, foreground="#004080", font=("Arial", 11, "bold")).grid(
            row=row, column=1, sticky="w", padx=pad, pady=(0, pad)
        )
        
        # Configure columns
        col_frame.columnconfigure(0, weight=0)
        col_frame.columnconfigure(1, weight=1)

        # Traces for dynamic recompute
        # Traces update constants only; jet fan count computed on Summary click
        for var in [self.v_kmh_var, qtreq_var, lanes_var, self.rho_var, self.xi_var, 
                    self.lamb_var, self.ae_var, self.eta_var, self.jet_diameter_var, self.high_eff_var]:
            try:
                var.trace_add("write", lambda *a: self._recompute_dynamic())
            except Exception:
                pass

    # ----------------------------
    # 3) Data extraction + compute
    # ----------------------------
    def _build_inputs_object(self, direction=1) -> TunnelVentInputs:
        """Build TunnelVentInputs from the widget variables for a specific direction.
        
        Args:
            direction: 1 for FROM→TO (dir1), 2 for TO→FROM (dir2)
        """
        # Map high_eff dropdown to bool
        high_eff_str = self.high_eff_var.get()
        high_eff_bool = high_eff_str.startswith("High")

        # Select variables based on direction
        if direction == 1:
            qtreq_var = self.qtreq_dir1_var
            lanes_var = self.lanes_dir1_var
            ar_var = self.ar_dir1_var
            lr_var = self.lr_dir1_var
            dr_var = self.dr_dir1_var
            imax_var = self.imax_dir1_var
            direction_str = "FromToTo"
        else:
            qtreq_var = self.qtreq_dir2_var
            lanes_var = self.lanes_dir2_var
            ar_var = self.ar_dir2_var
            lr_var = self.lr_dir2_var
            dr_var = self.dr_dir2_var
            imax_var = self.imax_dir2_var
            direction_str = "ToToFrom"

        vehicle_hr_lane = None
        try:
            if self.volume_tab:
                vehicle_hr_lane = self.volume_tab.get_vehicle_hr_lane(
                    direction=direction_str,
                    speed_kmh=float(self.v_kmh_var.get()),
                )
        except Exception:
            vehicle_hr_lane = None

        return TunnelVentInputs(
            V_kmh=float(self.v_kmh_var.get()),
            Qtreq=float(qtreq_var.get()),
            Imax=float(imax_var.get()),
            road_type=1,
            lanes=int(lanes_var.get()),
            Ar=float(ar_var.get()),
            Lr=float(lr_var.get()),
            rho=float(self.rho_var.get()),
            xi=float(self.xi_var.get()),
            lamb=float(self.lamb_var.get()),
            Dr=float(dr_var.get()),
            Ae=float(self.ae_var.get()),
            jet_diameter=int(self.jet_diameter_var.get()),
            high_efficiency=high_eff_bool,
            eta=float(self.eta_var.get()),
            vehicle_hr_lane=float(vehicle_hr_lane) if vehicle_hr_lane is not None else 0.0,
        )

    def _on_vkmh_changed(self, event=None):
        """Driving speed change: Un remains constant (2.5)."""
        self.un_var.set(2.5)
        # Update Vt based on map
        try:
            from vent_functions import Vt_MAP
            key = int(self.v_kmh_var.get())
            self.vt_var.set(Vt_MAP.get(key, Vt_MAP.get(10)))
        except Exception:
            pass
        self._recompute_dynamic()

    def _on_compute(self):
        """Callback for 'Compute jet fan number' button - compute for both directions."""
        try:
            # Compute Direction 1 (FROM→TO)
            inp_dir1 = self._build_inputs_object(direction=1)
            results_dir1 = compute_all(inp_dir1)
            self.exact_z_dir1_var.set(f"{results_dir1.Z_raw:.2f}")
            self.approx_z_dir1_var.set(f"{results_dir1.Z_applied}")
            
            # Compute Direction 2 (TO→FROM)
            inp_dir2 = self._build_inputs_object(direction=2)
            results_dir2 = compute_all(inp_dir2)
            self.exact_z_dir2_var.set(f"{results_dir2.Z_raw:.2f}")
            self.approx_z_dir2_var.set(f"{results_dir2.Z_applied}")

            # Send both directions results to result tab if available
            if self.result_tab and self.volume_tab:
                try:
                    dir1_label = self.volume_tab.dir1Name.get()
                    dir2_label = self.volume_tab.dir2Name.get()
                except Exception:
                    dir1_label = "FROM"
                    dir2_label = "TO"
                    
                self.result_tab.display_results_dual(
                    dir1_label, dir2_label,
                    inp_dir1, results_dir1, inp_dir2, results_dir2,
                    None, None  # No traffic logic from this button
                )
            elif self.result_tab:
                # Fallback to single direction if volume_tab not available
                self.result_tab.display_results(inp_dir1, results_dir1)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _recompute_dynamic(self):
        # Do not compute jet fan count dynamically; only update constants
        self.exact_z_dir1_var.set("-")
        self.approx_z_dir1_var.set("-")
        self.exact_z_dir2_var.set("-")
        self.approx_z_dir2_var.set("-")
        self.result_var.set("")

    def _wire_volume_sources(self):
        if not self.volume_tab:
            return
        
        # Sync for Direction 1 (FROM→TO, FromToTo)
        def sync_dir1(*_):
            try:
                params = self.volume_tab.get_params_for_jet(direction="FromToTo")
                volsum = self.volume_tab.get_volume_summary(direction="FromToTo")
                # Geometry - use Average values from TunnelGeometry
                self.ar_dir1_var.set(params.get("Ar", self.ar_dir1_var.get()))
                self.lr_dir1_var.set(params.get("Lr_m", self.lr_dir1_var.get()))
                self.dr_dir1_var.set(params.get("Dr", self.dr_dir1_var.get()))
                # Capacity and lanes (Imax is capacity per lane from volume tab)
                self.imax_dir1_var.set(volsum.get("cap_per_lane", self.imax_dir1_var.get()))
                # Default lanes from volume summary if available
                lanes_from_volume = volsum.get("lanes")
                if isinstance(lanes_from_volume, int) and lanes_from_volume >= 1:
                    self.lanes_dir1_var.set(lanes_from_volume)
                self._recompute_dynamic()
            except Exception as e:
                pass
        
        # Sync for Direction 2 (TO→FROM, ToToFrom)
        def sync_dir2(*_):
            try:
                params = self.volume_tab.get_params_for_jet(direction="ToToFrom")
                volsum = self.volume_tab.get_volume_summary(direction="ToToFrom")
                # Geometry - use Average values from TunnelGeometry
                self.ar_dir2_var.set(params.get("Ar", self.ar_dir2_var.get()))
                self.lr_dir2_var.set(params.get("Lr_m", self.lr_dir2_var.get()))
                self.dr_dir2_var.set(params.get("Dr", self.dr_dir2_var.get()))
                # Capacity and lanes (Imax is capacity per lane from volume tab)
                self.imax_dir2_var.set(volsum.get("cap_per_lane", self.imax_dir2_var.get()))
                # Default lanes from volume summary if available
                lanes_from_volume = volsum.get("lanes")
                if isinstance(lanes_from_volume, int) and lanes_from_volume >= 1:
                    self.lanes_dir2_var.set(lanes_from_volume)
                self._recompute_dynamic()
            except Exception as e:
                pass
        
        # Trace Direction 1 (FromToTo)
        try:
            if hasattr(self.volume_tab, 'tunnelGeometryFromToTo'):
                self.volume_tab.tunnelGeometryFromToTo.avg_ar_var.trace_add("write", sync_dir1)
                self.volume_tab.tunnelGeometryFromToTo.avg_lp_var.trace_add("write", sync_dir1)
                self.volume_tab.tunnelGeometryFromToTo.dr_var.trace_add("write", sync_dir1)
            self.volume_tab.totalLengthFromToTo_m.trace_add("write", sync_dir1)
            self.volume_tab.designSpeedFromToTo.trace_add("write", sync_dir1)
        except Exception as e:
            pass
        
        # Trace Direction 2 (ToToFrom)
        try:
            if hasattr(self.volume_tab, 'tunnelGeometryToToFrom'):
                self.volume_tab.tunnelGeometryToToFrom.avg_ar_var.trace_add("write", sync_dir2)
                self.volume_tab.tunnelGeometryToToFrom.avg_lp_var.trace_add("write", sync_dir2)
                self.volume_tab.tunnelGeometryToToFrom.dr_var.trace_add("write", sync_dir2)
            self.volume_tab.totalLengthToToFrom_m.trace_add("write", sync_dir2)
            self.volume_tab.designSpeedToToFrom.trace_add("write", sync_dir2)
        except Exception as e:
            pass
        
        # Schedule initial sync after a short delay to ensure TunnelGeometry is created
        def delayed_sync():
            try:
                # Re-register traces in case TunnelGeometry wasn't ready earlier
                if hasattr(self.volume_tab, 'tunnelGeometryFromToTo'):
                    try:
                        self.volume_tab.tunnelGeometryFromToTo.avg_ar_var.trace_add("write", sync_dir1)
                        self.volume_tab.tunnelGeometryFromToTo.avg_lp_var.trace_add("write", sync_dir1)
                        self.volume_tab.tunnelGeometryFromToTo.dr_var.trace_add("write", sync_dir1)
                    except:
                        pass
                if hasattr(self.volume_tab, 'tunnelGeometryToToFrom'):
                    try:
                        self.volume_tab.tunnelGeometryToToFrom.avg_ar_var.trace_add("write", sync_dir2)
                        self.volume_tab.tunnelGeometryToToFrom.avg_lp_var.trace_add("write", sync_dir2)
                        self.volume_tab.tunnelGeometryToToFrom.dr_var.trace_add("write", sync_dir2)
                    except:
                        pass
                sync_dir1()
                sync_dir2()
            except Exception:
                pass
        
        # Use after() to delay initial sync by 100ms
        self.after(100, delayed_sync)
        
        # Trace direction name changes to update LabelFrame titles
        try:
            if hasattr(self.volume_tab, 'dir1Name') and hasattr(self.volume_tab, 'dir2Name'):
                def update_labels(*_):
                    try:
                        dir1 = self.volume_tab.dir1Name.get()
                        dir2 = self.volume_tab.dir2Name.get()
                        if self.dir1_labelframe:
                            self.dir1_labelframe.config(text=f"Calculate number needed from {dir1} to {dir2}")
                        if self.dir2_labelframe:
                            self.dir2_labelframe.config(text=f"Calculate number needed from {dir2} to {dir1}")
                    except Exception:
                        pass
                
                self.volume_tab.dir1Name.trace_add("write", update_labels)
                self.volume_tab.dir2Name.trace_add("write", update_labels)
        except Exception:
            pass

    def compute_and_publish(self):
        """Compute jet fan numbers for both directions."""
        # Pre-compute validation: check all VentilationCapacityTab entries for valid numeric values
        invalid_entries = []
        try:
            for direction in [1, 2]:
                if direction == 1:
                    pairs = [
                        ("Qtreq (Dir 1)", self.qtreq_dir1_var),
                        ("Vr (Dir 1)", self.vr_dir1_var),
                        ("Lr (Dir 1)", self.lr_dir1_var),
                        ("Lp (Dir 1)", self.lp_dir1_var),
                        ("Ar (Dir 1)", self.ar_dir1_var),
                    ]
                else:
                    pairs = [
                        ("Qtreq (Dir 2)", self.qtreq_dir2_var),
                        ("Vr (Dir 2)", self.vr_dir2_var),
                        ("Lr (Dir 2)", self.lr_dir2_var),
                        ("Lp (Dir 2)", self.lp_dir2_var),
                        ("Ar (Dir 2)", self.ar_dir2_var),
                    ]
                
                for field_name, var in pairs:
                    try:
                        val_str = var.get().strip() if isinstance(var.get(), str) else str(var.get()).strip()
                        if val_str:
                            float(val_str)  # Try to convert to float
                    except (ValueError, AttributeError):
                        invalid_entries.append(f"{field_name}: '{val_str}'")
        except Exception:
            pass  # If attribute doesn't exist, skip this check
        
        if invalid_entries:
            error_msg = "Found non-numeric values in Ventilation Capacity tab:\n\n" + "\n".join(invalid_entries[:5])
            if len(invalid_entries) > 5:
                error_msg += f"\n... and {len(invalid_entries) - 5} more"
            error_msg += "\n\nPlease remove alphabetic or special characters from numeric fields."
            messagebox.showerror("Invalid Input", error_msg)
            return None, None, None, None
        
        try:
            # Compute Direction 1 (FROM→TO)
            inp_dir1 = self._build_inputs_object(direction=1)
            results_dir1 = compute_all(inp_dir1)
            self.exact_z_dir1_var.set(f"{results_dir1.Z_raw:.2f}")
            self.approx_z_dir1_var.set(f"{results_dir1.Z_applied}")
            
            # Compute Direction 2 (TO→FROM)
            inp_dir2 = self._build_inputs_object(direction=2)
            results_dir2 = compute_all(inp_dir2)
            self.exact_z_dir2_var.set(f"{results_dir2.Z_raw:.2f}")
            self.approx_z_dir2_var.set(f"{results_dir2.Z_applied}")
            
            return inp_dir1, results_dir1, inp_dir2, results_dir2
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return None, None, None, None


class ResultsTab(ttk.Frame):
    """Tab to display detailed calculation results with formulas."""

    def __init__(self, parent):
        super().__init__(parent)
        self._build_layout()

    def _build_layout(self):
        # Create a scrollable text widget
        scroll_frame = ttk.Frame(self, padding="10 10 10 10")
        scroll_frame.pack(fill="both", expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(scroll_frame)
        scrollbar.pack(side="right", fill="y")

        # Text widget for results
        self.text_widget = tk.Text(
            scroll_frame,
            wrap="word",
            yscrollcommand=scrollbar.set,
            font=("Courier New", 10),
            padx=10,
            pady=10
        )
        self.text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.text_widget.yview)

        # Configure tags for formatting
        self.text_widget.tag_configure("heading", font=("Courier New", 12, "bold"), foreground="#004080")
        self.text_widget.tag_configure("subheading", font=("Courier New", 10, "bold"), foreground="#006600")
        self.text_widget.tag_configure("formula", font=("Courier New", 9, "italic"), foreground="#800080")
        self.text_widget.tag_configure("result", font=("Courier New", 10, "bold"), foreground="#CC0000")

    def display_results(self, inp, results):
        """Display calculation results with formulas."""
        self.text_widget.config(state="normal")
        self.text_widget.delete(1.0, "end")


        # Spacer
        ttk.Label(diesel_frame, text="").pack(pady=10)

        # Second table: Standard application value of emission by vehicle type (정확한 구조)
        table_container_2 = ttk.Frame(diesel_frame)
        table_container_2.pack(fill="x", pady=10)
        for col in range(6):
            table_container_2.columnconfigure(col, weight=1, minsize=180)
        # ...existing code for table_container_2...

        # --- Insert 표고 보정계수 [fh] table here ---
        fh_title = ttk.Label(
            diesel_frame,
            text="표고 보정계수 [fh]",
            font=("Arial", 11, "bold"),
            background="#e0e0e0",
            borderwidth=1,
            relief="solid",
            anchor="center",
            justify="center",
            padding=5,
        )
        fh_title.pack(fill="x", pady=(10, 0))

        fh_table = ttk.Frame(diesel_frame)
        fh_table.pack(fill="x", pady=(0, 10))

        # Table headers
        headers = ["구분", "FROM→TO", "TO→FROM"]
        for col, header in enumerate(headers):
            ttk.Label(
                fh_table,
                text=header,
                font=("Arial", 9, "bold"),
                borderwidth=1,
                relief="solid",
                padding=5,
                background="#e0e0e0",
                anchor="center",
                justify="center",
            ).grid(row=0, column=col, sticky="nsew")
            fh_table.columnconfigure(col, weight=1, minsize=80)

        # Table data
        fh_data = [
            ["1구간", "1.00", "1.00"],
            ["2구간", "0.98", "1.02"],
            ["3구간", "0.96", "1.04"],
            ["4구간", "0.94", "1.06"],
            ["5구간", "0.92", "1.08"],
            ["6구간", "0.90", "1.10"],
            ["7구간", "0.88", "1.12"],
            ["8구간", "0.86", "1.14"],
            ["9구간", "0.84", "1.16"],
            ["10구간", "0.82", "1.18"],
        ]
        for r, row in enumerate(fh_data, start=1):
            for c, val in enumerate(row):
                ttk.Label(
                    fh_table,
                    text=val,
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background="#ffffff" if r % 2 == 1 else "#f9f9f9",
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r, column=c, sticky="nsew")

        # --- New table: 매연의 총배출량 Qs[m2/h] ---
        qs_title = ttk.Label(
            diesel_tab,
            text="매연의 총배출량 Qs[m2/h]",
            font=("Arial", 11, "bold"),
            background="#e0e0e0",
            borderwidth=1,
            relief="solid",
            anchor="center",
            justify="center",
            padding=5,
        )
        qs_title.grid(row=2, column=0, sticky="nsew", padx=40, pady=(30, 0))

        qs_table = ttk.Frame(diesel_tab)
        qs_table.grid(row=3, column=0, sticky="nsew", padx=40, pady=(0, 30))
        qs_headers = [
            "직주", "속도 (km/h)", "구분", "승용차-휘발유", "승용차-경유", "버스-소형", "버스-대형", "트럭-소형", "트럭-중형", "트럭-대형", "트럭-특수", "합계"
        ]
        for col, header in enumerate(qs_headers):
            ttk.Label(
                qs_table,
                text=header,
                font=("Arial", 9, "bold"),
                borderwidth=1,
                relief="solid",
                padding=5,
                background="#e0e0e0",
                anchor="center",
                justify="center",
            ).grid(row=0, column=col, sticky="nsew")
            qs_table.columnconfigure(col, weight=1, minsize=70)

        qs_data = [
            ["", "10", "1구간", "0.0", "50.9", "0.8712", "7.7917", "0.8712", "3.2693", "8.6191", "11.1532", "162.47"],
            ["", "10", "2구간", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.00"],
            ["", "20", "1구간", "67.8", "62.4", "9.4", "26.9", "27.7", "3.4", "10.2", "205.92"],
            ["", "30", "1구간", "82.4", "68.3", "9.7", "29.5", "30.7", "4.1", "11.6", "236.10"],
            ["", "40", "1구간", "84.0", "69.0", "9.9", "29.6", "31.5", "4.0", "11.8", "239.73"],
            ["", "50", "1구간", "85.0", "67.8", "10.0", "30.0", "31.3", "4.0", "11.7", "239.83"],
            ["", "60", "1구간", "85.0", "67.8", "10.0", "30.0", "31.3", "4.0", "11.7", "239.83"],
            ["", "70", "1구간", "85.0", "67.8", "10.0", "30.0", "31.3", "4.0", "11.7", "239.83"],
            ["", "80", "1구간", "85.8", "68.7", "10.0", "31.2", "32.5", "4.5", "12.2", "245.10"],
        ]
        for r, row in enumerate(qs_data, start=1):
            for c, val in enumerate(row):
                ttk.Label(
                    qs_table,
                    text=val,
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background="#ffffff" if r % 2 == 1 else "#f9f9f9",
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r, column=c, sticky="nsew")
        # Imax and road type inputs removed from UI; omitted from display
        self._add_text(f"Number of lanes:                  {inp.lanes}\n")
        self._add_text(f"Tunnel cross-sectional area, Ar:   {inp.Ar} [m²]\n")
        self._add_text(f"Tunnel length, Lr:                 {inp.Lr} [m]\n")
        self._add_text(f"Air density, ρ (rho):              {inp.rho} [kg/m³]\n")
        self._add_text(f"Entrance loss, ξ (xi):             {inp.xi}\n")
        self._add_text(f"Friction loss, λ (lambda):         {inp.lamb}\n")
        self._add_text(f"Representative diameter, Dr:       {inp.Dr} [m]\n")
        self._add_text(f"Equivalent resistance area, Ae:    {inp.Ae} [m²]\n")
        self._add_text(f"Jet fan diameter, Φ (phi):         {inp.jet_diameter} [mm]\n")
        self._add_text(f"Jet fan type:                     {'High efficiency' if inp.high_efficiency else 'Standard'}\n")
        self._add_text(f"Jet fan efficiency η (eta):       {inp.eta}\n\n")

        # Calculations
        self._add_text("CALCULATION STEPS\n", "subheading")
        self._add_text("="*80 + "\n\n")

        # 1. Vt
        self._add_text("1. Driving speed (Vt - velocity in tunnel)\n", "subheading")
        self._add_text("   Formula: ", "formula")
        self._add_text("Vt = Vt_MAP[V_kmh] (lookup table)\n", "formula")
        self._add_text(f"   Selected V_kmh = {inp.V_kmh} [km/h]\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"Vt = {results.Vt} [m/s]\n\n", "result")

        # 2. Vr
        self._add_text("2. Roadway wind speed, (Vr)\n", "subheading")
        self._add_text("   Formula: ", "formula")
        self._add_text("Vr = Qtreq / Ar\n", "formula")
        self._add_text(f"   Calculation: Vr = {inp.Qtreq} / {inp.Ar}\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"Vr = {results.Vr} [m/s]\n\n", "result")

        # 3. Un
        self._add_text("3. Natural wind speed (Un - constant)\n", "subheading")
        self._add_text("   Formula: ", "formula")
        self._add_text("Un = 2.5 (constant for jet fan calculation)\n", "formula")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"Un = {results.Un} [m/s]\n\n", "result")

        # 4. Aj
        self._add_text("4. Jet fan area (Aj - cross-sectional area)\n", "subheading")
        self._add_text("   Formula: ", "formula")
        self._add_text("Aj = Lookup from jet diameter map\n", "formula")
        self._add_text(f"   Jet diameter, Φ (phi) = {inp.jet_diameter} [mm]\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"Aj = {results.Aj} [m²]\n\n", "result")

        # 5. Vj
        self._add_text("5. Jet fan discharge speed (Vj)\n", "subheading")
        self._add_text("   Formula: ", "formula")
        self._add_text("Vj = 30 [m/s] (High efficiency) or 34 [m/s] (Standard)\n", "formula")
        self._add_text(f"   Type: {'High efficiency' if inp.high_efficiency else 'Standard'}\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"Vj = {results.Vj} [m/s]\n\n", "result")

        # 6. n
        self._add_text("6. Number of vehicles in tunnel (n)\n", "subheading")
        use_vehicle_override = inp.vehicle_hr_lane and inp.vehicle_hr_lane > 0
        if use_vehicle_override:
            self._add_text("   Formula: ", "formula")
            self._add_text("n = ROUND((Vehicle/hr, lane × lanes × Lr) / (3600 × Vt) + 0.4)\n", "formula")
            self._add_text(
                f"   Calculation: n = ROUND(({inp.vehicle_hr_lane} × {inp.lanes} × {inp.Lr}) / (3600 × {results.Vt}) + 0.4)\n"
            )
        else:
            self._add_text("   Formula: ", "formula")
            self._add_text("n = ROUND(Q × lanes × Lr / (3600 × Vt) + 0.4)\n", "formula")
            self._add_text(f"   where Q is traffic flow computed from Imax = {inp.Imax} [PCU/hr·lane]\n")
            self._add_text(f"   Calculation: n = ROUND(Q × {inp.lanes} × {inp.Lr} / (3600 × {results.Vt}) + 0.4)\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"n = {results.n} [vehicles]\n\n", "result")

        # 7. Kj
        self._add_text("7. Jet fan pressure coefficient (Kj - effectiveness)\n", "subheading")
        self._add_text("   Formula: ", "formula")
        self._add_text("Kj = 0.99 (if Vr<4), 0.92 (if 4≤Vr<8), 0.9 (if Vr≥8)\n", "formula")
        self._add_text(f"   Vr = {results.Vr} [m/s]\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"Kj = {results.Kj} (dimensionless)\n\n", "result")

        # Common factor
        common_factor = (1 + inp.xi + inp.lamb * inp.Lr / inp.Dr) * inp.rho / 2.0
        self._add_text("Common factor for pressure calculations (CF):\n", "subheading")
        self._add_text("   Formula: ", "formula")
        self._add_text("CF = (1 + ξ + λ × Lr / Dr) × ρ / 2\n", "formula")
        self._add_text(f"   Calculation: CF = (1 + {inp.xi} + {inp.lamb} × {inp.Lr} / {inp.Dr}) × {inp.rho} / 2\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"CF = {common_factor:.4f}\n\n", "result")

        # 8. Pr
        self._add_text("8. Roadway wind pressure loss (ΔPr - pressure drop)\n", "subheading")
        self._add_text("   Formula: ", "formula")
        self._add_text("ΔPr = CF × Vr²\n", "formula")
        self._add_text(f"   Calculation: ΔPr = {common_factor:.4f} × {results.Vr}²\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"ΔPr = {results.Pr} [Pa]\n\n", "result")

        # 9. Pm
        self._add_text("9. Natural wind pressure loss (ΔPm - pressure drop)\n", "subheading")
        self._add_text("   Formula: ", "formula")
        self._add_text("ΔPm = CF × Un²\n", "formula")
        self._add_text(f"   Calculation: ΔPm = {common_factor:.4f} × {results.Un}²\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"ΔPm = {results.Pm} [Pa]\n\n", "result")

        # 10. Pt
        self._add_text("10. Vehicle traffic pressure (ΔPt - traffic effect)\n", "subheading")
        self._add_text("   Formula: ", "formula")
        if results.Vt > results.Vr:
            self._add_text("ΔPt = (ρ/2) × (Ae/Ar) × n × (Vt-Vr)² (when Vt>Vr)\n", "formula")
            self._add_text(f"   Calculation: ΔPt = ({inp.rho}/2) × ({inp.Ae}/{inp.Ar}) × {results.n} × ({results.Vt}-{results.Vr})²\n")
        else:
            self._add_text("ΔPt = -(ρ/2) × (Ae/Ar) × n × (Vt-Vr)² (when Vt<Vr)\n", "formula")
            self._add_text(f"   Calculation: ΔPt = -({inp.rho}/2) × ({inp.Ae}/{inp.Ar}) × {results.n} × ({results.Vt}-{results.Vr})²\n")
        self._add_text(f"   Result: ", "result")
        self._add_text(f"ΔPt = {results.Pt} [Pa]\n\n", "result")

        # 11. Pq
        self._add_text("11. Required pressure (ΔPq - needed for fan)\n", "subheading")
        self._add_text("    Formula: ", "formula")
        self._add_text("ΔPq = ΔPr + ΔPm - ΔPt\n", "formula")
        self._add_text(f"    Calculation: ΔPq = {results.Pr} + {results.Pm} - {results.Pt}\n")
        self._add_text(f"    Result: ", "result")
        self._add_text(f"ΔPq = {results.Pq} [Pa]\n\n", "result")

        # 12. Pj
        self._add_text("12. Jet fan pressure (ΔPj - per fan)\n", "subheading")
        self._add_text("    Formula: ", "formula")
        self._add_text("ΔPj = Kj × ρ/2 × Vj² × (Aj/Ar) × (1 - Vr/Vj) × η\n", "formula")
        self._add_text(f"    Calculation: ΔPj = {results.Kj} × {inp.rho}/2 × {results.Vj}² × ({results.Aj}/{inp.Ar}) × (1 - {results.Vr}/{results.Vj}) × {inp.eta}\n")
        self._add_text(f"    Result: ", "result")
        self._add_text(f"ΔPj = {results.Pj} [Pa]\n\n", "result")

        # 13. Z_raw
        self._add_text("13. Required number of jet fans (Z_raw)\n", "subheading")
        self._add_text("    Formula: ", "formula")
        self._add_text("Z_raw = ΔPq / ΔPj\n", "formula")
        self._add_text(f"    Calculation: Z_raw = {results.Pq} / {results.Pj}\n")
        self._add_text(f"    Result: ", "result")
        self._add_text(f"Z_raw = {results.Z_raw} [fans]\n\n", "result")

        # 14. Z_applied
        self._add_text("14. Applied number of jet fans (Z_applied - rounded up)\n", "subheading")
        self._add_text("    Formula: ", "formula")
        self._add_text("Z_applied = CEIL(Z_raw) if Z_raw > 0, else 0\n", "formula")
        self._add_text(f"    Calculation: Z_applied = CEIL({results.Z_raw})\n")
        self._add_text(f"    Result: ", "result")
        self._add_text(f"Z_applied = {results.Z_applied} [fans]\n\n", "result")

        # Final summary
        self._add_text("="*80 + "\n", "heading")
        self._add_text("FINAL RESULT\n", "heading")
        self._add_text("="*80 + "\n", "heading")
        self._add_text(f"Required jet fan count (calculated): {results.Z_raw}\n", "result")
        self._add_text(f"Applied jet fan count (rounded up): {results.Z_applied} fans\n\n", "result")

        self.text_widget.config(state="disabled")

    def display_results_dual(self, dir1_label, dir2_label, inp1, res1, inp2, res2, 
                           traffic_logic_dir1=None, traffic_logic_dir2=None):
        """Display full formulas/calculations for both directions with traffic estimation."""
        self.text_widget.config(state="normal")
        self.text_widget.delete(1.0, "end")

        def _render_full_calc(title, inp, results, traffic_logic=None):
            self._add_text(f"\n{title}\n", "heading")
            self._add_text("="*80 + "\n\n")
            
            # INPUT PARAMETERS
            self._add_text("INPUT PARAMETERS\n", "subheading")
            self._add_text("-"*80 + "\n")
            self._add_text(f"Driving speed V_kmh (velocity):   {inp.V_kmh} [km/h]\n")
            self._add_text(f"Required ventilation Qtreq:       {inp.Qtreq} [m³/s]\n")
            self._add_text(f"Natural wind speed Un (computed): {results.Un} [m/s]\n")
            self._add_text(f"Number of lanes:                  {inp.lanes}\n")
            self._add_text(f"Tunnel cross-sectional area Ar:   {inp.Ar} [m²]\n")
            self._add_text(f"Tunnel length Lr:                 {inp.Lr} [m]\n")
            self._add_text(f"Air density ρ (rho):              {inp.rho} [kg/m³]\n")
            self._add_text(f"Entrance loss ξ (xi):             {inp.xi}\n")
            self._add_text(f"Friction loss λ (lambda):         {inp.lamb}\n")
            self._add_text(f"Representative diameter Dr:       {inp.Dr} [m]\n")
            self._add_text(f"Equivalent resistance area Ae:    {inp.Ae} [m²]\n")
            self._add_text(f"Jet fan diameter Φ (phi):         {inp.jet_diameter} [mm]\n")
            self._add_text(f"Jet fan type:                     {'High efficiency' if inp.high_efficiency else 'Standard'}\n")
            self._add_text(f"Jet fan efficiency η (eta):       {inp.eta}\n\n")

            # CALCULATION STEPS
            self._add_text("CALCULATION STEPS\n", "subheading")
            self._add_text("="*80 + "\n\n")

            # 1. Vt
            self._add_text("1. Driving speed (Vt)\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("Vt = Vt_MAP[V_kmh] (lookup)\n", "formula")
            self._add_text(f"   Selected V_kmh = {inp.V_kmh} km/h\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"Vt = {results.Vt} m/s\n\n", "result")

            # 2. Vr
            self._add_text("2. Roadway wind speed (Vr)\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("Vr = Qtreq / Ar\n", "formula")
            self._add_text(f"   Calculation: Vr = {inp.Qtreq} / {inp.Ar}\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"Vr = {results.Vr} m/s\n\n", "result")

            # 3. Un
            self._add_text("3. Natural wind speed (Un)\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("Un = 2.5 (constant for Jet Fan calc)\n", "formula")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"Un = {results.Un} m/s\n\n", "result")

            # 4. Aj
            self._add_text("4. Jet fan area (Aj)\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("Aj = Lookup from jet diameter map\n", "formula")
            self._add_text(f"   Jet diameter, Φ (phi) = {inp.jet_diameter} [mm]\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"Aj = {results.Aj} m²\n\n", "result")

            # 5. Vj
            self._add_text("5. Jet fan discharge speed, Vj\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("Vj = 30 m/s (High efficiency) or 34 m/s (Standard)\n", "formula")
            self._add_text(f"   Type: {'High efficiency' if inp.high_efficiency else 'Standard'}\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"Vj = {results.Vj} m/s\n\n", "result")

            # 6. n
            self._add_text("6. Number of vehicles in tunnel (n)\n", "subheading")
            use_vehicle_override = inp.vehicle_hr_lane and inp.vehicle_hr_lane > 0
            if use_vehicle_override:
                self._add_text("   Formula: ", "formula")
                self._add_text("n = ROUND((Vehicle/hr, lane × lanes × Lr) / (3600 × Vt) + 0.4)\n", "formula")
                self._add_text(
                    f"   Calculation: n = ROUND(({inp.vehicle_hr_lane} × {inp.lanes} × {inp.Lr}) / (3600 × {results.Vt}) + 0.4)\n"
                )
            else:
                self._add_text("   Formula: ", "formula")
                self._add_text("n = ROUND(Q × lanes × Lr / (3600 × Vt) + 0.4)\n", "formula")
                self._add_text(f"   Calculation: n = ROUND(Q × {inp.lanes} × {inp.Lr} / (3600 × {results.Vt}) + 0.4)\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"n = {results.n} vehicles\n\n", "result")

            # 7. Kj
            self._add_text("7. Jet fan pressure coefficient, Kj\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("Kj = 0.99 (Vr<4), 0.92 (4≤Vr<8), 0.9 (Vr≥8)\n", "formula")
            self._add_text(f"   Vr = {results.Vr} m/s\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"Kj = {results.Kj}\n\n", "result")

            # Common factor
            common_factor = (1 + inp.xi + inp.lamb * inp.Lr / inp.Dr) * inp.rho / 2.0
            self._add_text("Common factor for pressure calculations:\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("CF = (1 + ξ + λ × Lr / Dr) × ρ / 2\n", "formula")
            self._add_text(f"   Calculation: CF = (1 + {inp.xi} + {inp.lamb} × {inp.Lr} / {inp.Dr}) × {inp.rho} / 2\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"CF = {common_factor:.4f}\n\n", "result")

            # 8. Pr
            self._add_text("8. Roadway wind pressure loss, ΔPr\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("ΔPr = CF × Vr²\n", "formula")
            self._add_text(f"   Calculation: ΔPr = {common_factor:.4f} × {results.Vr}²\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"ΔPr = {results.Pr} Pa\n\n", "result")

            # 9. Pm
            self._add_text("9. Natural wind pressure loss, ΔPm\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("ΔPm = CF × Un²\n", "formula")
            self._add_text(f"   Calculation: ΔPm = {common_factor:.4f} × {results.Un}²\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"ΔPm = {results.Pm} Pa\n\n", "result")

            # 10. Pt
            self._add_text("10. Vehicle traffic pressure, ΔPt\n", "subheading")
            self._add_text("   Formula: ", "formula")
            if results.Vt > results.Vr:
                self._add_text("ΔPt = (ρ/2) × (Ae/Ar) × n × (Vt-Vr)² (Vt>Vr)\n", "formula")
                self._add_text(f"   Calculation: ΔPt = ({inp.rho}/2) × ({inp.Ae}/{inp.Ar}) × {results.n} × ({results.Vt}-{results.Vr})²\n")
            else:
                self._add_text("ΔPt = -(ρ/2) × (Ae/Ar) × n × (Vt-Vr)² (Vt<Vr)\n", "formula")
                self._add_text(f"   Calculation: ΔPt = -({inp.rho}/2) × ({inp.Ae}/{inp.Ar}) × {results.n} × ({results.Vt}-{results.Vr})²\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"ΔPt = {results.Pt} Pa\n\n", "result")

            # 11. Pq (Required pressure)
            self._add_text("11. Required pressure, ΔPq\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("ΔPq = ΔPr + ΔPm - ΔPt\n", "formula")
            self._add_text(f"   Calculation: ΔPq = {results.Pr} + {results.Pm} - ({results.Pt})\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"ΔPq = {results.Pq} Pa\n\n", "result")

            # 12. Pj (Jet fan pressure per fan)
            self._add_text("12. Jet fan pressure (per fan), ΔPj\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("ΔPj = Kj × ρ × Vj² × (Aj/Ar) × (1 - Vr/Vj) × η\n", "formula")
            self._add_text(f"   Calculation: ΔPj = {results.Kj} × {inp.rho}/2 × {results.Vj}² × ({results.Aj}/{inp.Ar}) × (1 - {results.Vr}/{results.Vj}) × {inp.eta}\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"ΔPj = {results.Pj} Pa\n\n", "result")
    
            # 13. Z_raw
            self._add_text("13. Required number of jet fans, Z_raw\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("Z_raw = ΔPq / ΔPj\n", "formula")
            self._add_text(f"   Calculation: Z_raw = round({results.Pq} / {results.Pj}, 2)\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"Z_raw = {results.Z_raw}\n\n", "result")

            # 14. Z_applied
            self._add_text("14. Applied number of jet fans, (Z_applied)\n", "subheading")
            self._add_text("   Formula: ", "formula")
            self._add_text("Z_applied = CEIL(Z_raw) if Z_raw > 0, else 0\n", "formula")
            self._add_text(f"   Calculation: Z_applied = CEIL({results.Z_raw})\n")
            self._add_text(f"   Result: ", "result")
            self._add_text(f"Z_applied = {results.Z_applied} fans\n\n", "result")

            # Final summary
            self._add_text("-"*80 + "\n", "heading")
            self._add_text("FINAL RESULT\n", "heading")
            self._add_text("-"*80 + "\n", "heading")
            self._add_text(f"Required jet fan count, (calculated): {results.Z_raw}\n", "result")
            self._add_text(f"Applied jet fan count, (rounded up): {results.Z_applied} fans\n\n", "result")

            # Traffic Estimation Section (if data available)
            if traffic_logic and traffic_logic.batch:
                self._add_text("\n")
                self._add_text("-"*80 + "\n", "heading")
                self._add_text("TRAFFIC ESTIMATION RESULTS\n", "heading")
                self._add_text("-"*80 + "\n\n", "heading")
                
                for entry in traffic_logic.batch:
                    if not entry.result:
                        continue
                    res = entry.result
                    inp_traffic = entry.inputs
                    
                    self._add_text(f"Year: {entry.year}\n", "subheading")
                    self._add_text("-"*60 + "\n")
                    self._add_text("Vehicle Breakdown:\n", "subheading")
                    self._add_text(f"  Passenger Vehicles:       {inp_traffic.passenger_aadt:,.0f}\n")
                    self._add_text(f"    - Gasoline (60%):       {res.counts.get('passengerGasoline', 0):,.0f}\n")
                    self._add_text(f"    - Diesel (40%):         {res.counts.get('passengerDiesel', 0):,.0f}\n")
                    self._add_text(f"  Bus Small:                {inp_traffic.bus_small:,.0f}\n")
                    self._add_text(f"  Bus Large:                {inp_traffic.bus_large:,.0f}\n")
                    self._add_text(f"  Truck Small:              {inp_traffic.truck_small:,.0f}\n")
                    self._add_text(f"  Truck Medium:             {inp_traffic.truck_medium:,.0f}\n")
                    self._add_text(f"  Truck Large:              {inp_traffic.truck_large:,.0f}\n")
                    self._add_text(f"  Truck Special:            {inp_traffic.truck_special:,.0f}\n\n")
                    
                    self._add_text("Summary Statistics:\n", "subheading")
                    self._add_text(f"  Total AADT:               ", "result")
                    self._add_text(f"{res.total_aadt:,.0f} vehicles/day\n", "result")
                    self._add_text(f"  Heavy Vehicle Mix:        ", "result")
                    self._add_text(f"{res.heavy_vehicle_mix_pt:.2f}%\n", "result")
                    
                    # Add emission volumes if available
                    if hasattr(res, 'total_emissions') and res.total_emissions:
                        self._add_text(f"\nTotal Emissions:\n", "subheading")
                        for pollutant, value in res.total_emissions.items():
                            self._add_text(f"  {pollutant}: {value:.4f} g/km·hr\n")
                    
                    self._add_text("\n")

        # Header
        self._add_text("="*80 + "\n", "heading")
        self._add_text("TUNNEL VENTILATION CALCULATION RESULTS (BOTH DIRECTIONS)\n", "heading")
        self._add_text("="*80 + "\n\n", "heading")

        _render_full_calc(f"DIRECTION: {dir1_label} → {dir2_label}", inp1, res1, traffic_logic_dir1)
        _render_full_calc(f"DIRECTION: {dir2_label} → {dir1_label}", inp2, res2, traffic_logic_dir2)

        # Add summary section for both directions in table form
        self._add_text("\n" + "="*80 + "\n", "heading")
        self._add_text("RESULT SUMMARY (BOTH DIRECTIONS)\n", "heading")
        self._add_text("="*80 + "\n\n", "heading")

        # Simple text table for quick comparison
        header = f"{'Direction':<28}{'Z_raw (calc)':>16}{'Z_applied (ceil)':>22}\n"
        divider = "-" * (28 + 16 + 22) + "\n"
        row1 = f"{dir1_label} → {dir2_label:<20}{res1.Z_raw:>16.2f}{res1.Z_applied:>22}\n"
        row2 = f"{dir2_label} → {dir1_label:<20}{res2.Z_raw:>16.2f}{res2.Z_applied:>22}\n"

        self._add_text(header, "subheading")
        self._add_text(divider)
        self._add_text(row1, "result")
        self._add_text(row2, "result")
        self._add_text("\n")

        self.text_widget.config(state="disabled")

    def _add_text(self, text, tag=None):
        """Helper to add text with optional tag."""
        if tag:
            self.text_widget.insert("end", text, tag)
        else:
            self.text_widget.insert("end", text)

    def append_volume_summary(self, volume_infos):
        """Append ventilation volume summaries. volume_infos: list of dicts."""
        self.text_widget.config(state="normal")
        self._add_text("\n" + "-"*80 + "\n", "heading")
        self._add_text("VENTILATION VOLUME SUMMARY\n", "heading")
        self._add_text("-"*80 + "\n\n")
        for info in volume_infos:
            self._add_text(f"Direction: {info.get('direction','')}\n", "subheading")
            self._add_text(f"Design speed: {info.get('design_speed', '')} km/h\n")
            self._add_text(f"Length: {info.get('length_km', info.get('Lr_m',0)/1000):.3f} km\n")
            self._add_text(f"Max gradient: {info.get('max_gradient', 0)} %\n")
            self._add_text(f"Lanes: {info.get('lanes', 1)}\n")
            self._add_text(f"Capacity per lane: {info.get('cap_per_lane', 0)} PCU/hr\n")
            self._add_text(f"Total capacity: {info.get('total_capacity', 0)} PCU/hr\n")
            self._add_text(f"Ar: {info.get('Ar', 0)} m², Lp: {info.get('Lp', 0)} m, Dr: {info.get('Dr', 0):.4f} m\n\n")
        self.text_widget.config(state="disabled")
    
    def append_traffic_summary(self, traffic_logic_From_To, traffic_logic_To_From, volume_tab=None):
        """Append traffic estimation summary for both directions."""
        self.text_widget.config(state="normal")
        self._add_text("\n" + "-"*80 + "\n", "heading")
        self._add_text("ESTIMATED TRAFFIC VOLUME SUMMARY\n", "heading")
        self._add_text("-"*80 + "\n\n")
        
        # Get dynamic direction names from volume tab
        dir1_name = "From"
        dir2_name = "To"
        if volume_tab:
            try:
                dir1_name = volume_tab.dir1Name.get()
                dir2_name = volume_tab.dir2Name.get()
            except:
                pass
        
        # Display Direction 1 (dir1_name → dir2_name)
        self._add_text(f"Direction: {dir1_name} → {dir2_name}\n", "subheading")
        self._add_text("-"*60 + "\n")
        if not traffic_logic_From_To.batch:
            self._add_text("No traffic data computed.\n\n")
        else:
            for entry in traffic_logic_From_To.batch:
                if not entry.result:
                    continue
                res = entry.result
                inp = entry.inputs
                
                self._add_text(f"Year: {entry.year}\n", "subheading")
                self._add_text(f"  Passenger Vehicles:       {inp.passenger_aadt:,.0f}\n")
                self._add_text(f"    - Gasoline (60%):       {res.counts.get('passengerGasoline', 0):,.0f}\n")
                self._add_text(f"    - Diesel (40%):         {res.counts.get('passengerDiesel', 0):,.0f}\n")
                self._add_text(f"  Bus Small:                {inp.bus_small:,.0f}\n")
                self._add_text(f"  Bus Large:                {inp.bus_large:,.0f}\n")
                self._add_text(f"  Truck Small:              {inp.truck_small:,.0f}\n")
                self._add_text(f"  Truck Medium:             {inp.truck_medium:,.0f}\n")
                self._add_text(f"  Truck Large:              {inp.truck_large:,.0f}\n")
                self._add_text(f"  Truck Special:            {inp.truck_special:,.0f}\n")
                self._add_text(f"  Total AADT:               ", "result")
                self._add_text(f"{res.total_aadt:,.0f}\n", "result")
                self._add_text(f"  Heavy Vehicle Mix:        ", "result")
                self._add_text(f"{res.heavy_vehicle_mix_pt:.2f}%\n\n", "result")
        
        # Display Direction 2 (dir2_name → dir1_name)
        self._add_text(f"Direction: {dir2_name} → {dir1_name}\n", "subheading")
        self._add_text("-"*60 + "\n")
        if not traffic_logic_To_From.batch:
            self._add_text("No traffic data computed.\n\n")
        else:
            for entry in traffic_logic_To_From.batch:
                if not entry.result:
                    continue
                res = entry.result
                inp = entry.inputs
                
                self._add_text(f"Year: {entry.year}\n", "subheading")
                self._add_text(f"  Passenger Vehicles:       {inp.passenger_aadt:,.0f}\n")
                self._add_text(f"    - Gasoline (60%):       {res.counts.get('passengerGasoline', 0):,.0f}\n")
                self._add_text(f"    - Diesel (40%):         {res.counts.get('passengerDiesel', 0):,.0f}\n")
                self._add_text(f"  Bus Small:                {inp.bus_small:,.0f}\n")
                self._add_text(f"  Bus Large:                {inp.bus_large:,.0f}\n")
                self._add_text(f"  Truck Small:              {inp.truck_small:,.0f}\n")
                self._add_text(f"  Truck Medium:             {inp.truck_medium:,.0f}\n")
                self._add_text(f"  Truck Large:              {inp.truck_large:,.0f}\n")
                self._add_text(f"  Truck Special:            {inp.truck_special:,.0f}\n")
                self._add_text(f"  Total AADT:               ", "result")
                self._add_text(f"{res.total_aadt:,.0f}\n", "result")
                self._add_text(f"  Heavy Vehicle Mix:        ", "result")
                self._add_text(f"{res.heavy_vehicle_mix_pt:.2f}%\n\n", "result")
        
        self.text_widget.config(state="disabled")


class VentilationCapacityTab(ttk.Frame):
    """Tab for displaying Ventilation Capacity calculations based on Jet Fan parameters."""

    def __init__(self, parent, jet_fan_tab=None, volume_tab=None):
        super().__init__(parent)
        self.jet_fan_tab = jet_fan_tab
        self.volume_tab = volume_tab
        self.configure(padding="10 10 10 10")
        
        # Create scrollable text widget
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Main content frame
        self.content_frame = scrollable_frame
        
        # Initialize data cells dictionary once
        self.data_cells = {}
        # Road type vars per direction
        self.road_type_vars = {}
        # One-time prompt guard when Vehicle/hr per lane is missing
        self._traffic_prompt_shown = False
        # Guard to prevent multiple prompts
        self._jet_fan_selection_prompted = False
        
        # Initialize dropdown variables for each direction
        if jet_fan_tab:
            jet_keys = sorted(JET_AREA_MAP.keys())
            jet_choices = [str(k) for k in jet_keys]
            
            eff_choices = [
                "High efficiency (30 m/s)",
                "Standard (34 m/s)",
            ]
        else:
            jet_choices = ["630", "710", "1030", "1250", "1530"]
            eff_choices = ["High efficiency (30 m/s)", "Standard (34 m/s)"]
        
        # Initialize with placeholder values - user must explicitly select both
        placeholder_jet = "-- Select Jet Fan Diameter (mm) --"
        placeholder_eff = "-- Select Efficiency --"
        
        # Add placeholders to choices
        jet_choices_with_placeholder = [placeholder_jet] + jet_choices
        eff_choices_with_placeholder = [placeholder_eff] + eff_choices
        
        self.jet_diameter_dir1_var = tk.StringVar(value=placeholder_jet)
        self.high_eff_dir1_var = tk.StringVar(value=placeholder_eff)
        self.jet_diameter_dir2_var = tk.StringVar(value=placeholder_jet)
        self.high_eff_dir2_var = tk.StringVar(value=placeholder_eff)
        
        self.jet_choices = jet_choices_with_placeholder
        self.eff_choices = eff_choices_with_placeholder
        
        # Add traces to jet fan selection dropdowns to enable/disable inputs
        self.jet_diameter_dir1_var.trace_add("write", lambda *a: self._check_jet_fan_selection(1))
        self.high_eff_dir1_var.trace_add("write", lambda *a: self._check_jet_fan_selection(1))
        self.jet_diameter_dir2_var.trace_add("write", lambda *a: self._check_jet_fan_selection(2))
        self.high_eff_dir2_var.trace_add("write", lambda *a: self._check_jet_fan_selection(2))
        
        # Register numeric validation for Entry widgets
        self.numeric_vcmd = (self.register(self._validate_numeric), '%S', '%d')
        
        self._build_layout()
        # Keep direction labels in sync with Calculate Ventilation tab
        self._attach_dirname_traces()
        self._update_card_titles()

    @staticmethod
    def _safe_float(var, default=0.0):
        """Convert tk variable to float, returning default on blank/invalid."""
        try:
            val = var.get()
            return float(val) if val not in (None, "", " ") else default
        except Exception:
            return default

    @staticmethod
    def _parse_road_type(var, default=1):
        """Return 1 or 2 from road type StringVar like '1 - ...' or '2 - ...'."""
        try:
            text = str(var.get()) if var else ""
            first = text.strip().split(" ")[0]
            if first in {"1", "2"}:
                return int(first)
        except Exception:
            pass
        return default

    @staticmethod
    def _validate_numeric(s, d):
        """Validate that input is numeric (int or float).
        s: string being inserted
        d: type of action (1=insert, 0=delete)
        """
        if d == 0:  # Allow deletion
            return True
        if s == "":  # Allow empty string
            return True
        # Allow digits, decimal point, and minus sign (per-character)
        return all(ch in "0123456789.-" for ch in s)

    def _get_dir_labels(self):
        """Return direction labels from volume tab (calculate ventilation) with fallbacks."""
        dir1_label, dir2_label = "FROM", "TO"
        try:
            if self.volume_tab:
                if hasattr(self.volume_tab, "dir1Name"):
                    val = self.volume_tab.dir1Name.get()
                    dir1_label = val if val else dir1_label
                if hasattr(self.volume_tab, "dir2Name"):
                    val = self.volume_tab.dir2Name.get()
                    dir2_label = val if val else dir2_label
        except Exception:
            pass
        return dir1_label, dir2_label

    def _update_card_titles(self):
        """Update capacity card titles to reflect current direction labels."""
        dir1_label, dir2_label = self._get_dir_labels()
        try:
            if hasattr(self, "card1"):
                self.card1.configure(text=f"Capacity: {dir1_label} → {dir2_label}")
            if hasattr(self, "card2"):
                self.card2.configure(text=f"Capacity: {dir2_label} → {dir1_label}")
        except Exception:
            pass

    def _attach_dirname_traces(self):
        """Attach traces to volume tab direction names to keep titles in sync."""
        if not self.volume_tab:
            return
        try:
            if hasattr(self.volume_tab, "dir1Name"):
                self.volume_tab.dir1Name.trace_add("write", lambda *a: self._update_card_titles())
            if hasattr(self.volume_tab, "dir2Name"):
                self.volume_tab.dir2Name.trace_add("write", lambda *a: self._update_card_titles())
        except Exception:
            pass

    def _build_layout(self):
        """Build the ventilation capacity calculation display."""
        dir1_label, dir2_label = self._get_dir_labels()
        # Title
        title = ttk.Label(self.content_frame, text="Ventilation Capacity Analysis", 
                         font=("Arial", 14, "bold"))
        title.pack(anchor="w", pady=(0, 10))
        
        # Direction 1 card
        self.card1 = ttk.LabelFrame(self.content_frame, text=f"Capacity: {dir1_label} → {dir2_label}", padding="10 10 10 10")
        self.card1.pack(fill="x", pady=5)
        self._build_direction_card(self.card1, direction=1)
        
        # Direction 2 card
        self.card2 = ttk.LabelFrame(self.content_frame, text=f"Capacity: {dir2_label} → {dir1_label}", padding="10 10 10 10")
        self.card2.pack(fill="x", pady=5)
        self._build_direction_card(self.card2, direction=2)
        
        # Buttons
        button_frame = ttk.Frame(self.content_frame)
        button_frame.pack(fill="x", pady=10)
        ttk.Button(button_frame, text="Calculate All", command=self._calculate_all).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Export Results", command=self._export_results).pack(side="left", padx=5)

    def _build_direction_card(self, parent, direction):
        """Build calculation table for a direction."""
        # Add dropdowns above table
        dropdown_frame = ttk.Frame(parent)
        dropdown_frame.pack(fill="x", pady=(0, 10))
        
        # Jet diameter dropdown
        ttk.Label(dropdown_frame, text="Jet Fan Diameter (mm):").pack(side="left", padx=(0, 5))
        jet_var = self.jet_diameter_dir1_var if direction == 1 else self.jet_diameter_dir2_var
        jet_combo = ttk.Combobox(dropdown_frame, textvariable=jet_var, 
                                 values=self.jet_choices, state="readonly", width=10)
        jet_combo.pack(side="left", padx=(0, 20))
        
        # Efficiency dropdown
        ttk.Label(dropdown_frame, text="Efficiency:").pack(side="left", padx=(0, 5))
        eff_var = self.high_eff_dir1_var if direction == 1 else self.high_eff_dir2_var
        eff_combo = ttk.Combobox(dropdown_frame, textvariable=eff_var,
                                values=self.eff_choices, state="readonly", width=25)
        eff_combo.pack(side="left")
        
        # Create a separate frame for the grid table
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill="both", expand=True)
        
        # Simplified header - Lr is tunnel length (editable), Lp is segment length (variable), ρ is air density (constant 1.2)
        simplified_headers = [
            "V(km/h)",
            "Vt (m/s)",
            "Qtreq(m³/s)",
            "Vr(m/s)",
            "Kj",
            "Un(m/s)",
            "λ",
            "ξ",
            "ρ(kg/m³)",
            "Ae(m²)",
            "Lr(m)",
            "Lp(m)",
            "Ar(m²)",
            "η",
            "Dr(m)",
            "Q(vehicles/hr)",
            "n(vehicles)",
            "ΔPr(Pa)",
            "ΔPm(Pa)",
            "ΔPt(Pa)",
            "ΔPq(Pa)",
            "Z_raw",
            "Z(fans)"
        ]
        
        # Create grid display
        for col, header in enumerate(simplified_headers):
            label = ttk.Label(table_frame, text=header, font=("Arial", 9, "bold"),
                            borderwidth=1, relief="solid", padding=5, background="#e0e0e0")
            label.grid(row=0, column=col, sticky="nsew")
        
        # Add sample data rows (8 speeds: 10, 20, 30, 40, 50, 60, 70, 80)
        speeds = [10, 20, 30, 40, 50, 60, 70, 80]
        
        # Initialize this direction's data cells if not already done
        if direction not in self.data_cells:
            self.data_cells[direction] = {}
        
        for row_idx, speed in enumerate(speeds, start=1):
            self.data_cells[direction][speed] = {}
            
            # Speed column
            ttk.Label(table_frame, text=str(speed), borderwidth=1, relief="solid", padding=5).grid(
                row=row_idx, column=0, sticky="nsew")
            
            # Other columns - constants are readonly, others are normal
            # Columns: 0-Speed, 1-Vt, 2-Qtreq, 3-Vr, 4-Kj, 5-Un, 6-λ, 7-ξ, 8-ρ, 9-Ae, 10-Lr, 11-Lp, 12-Ar, 13-η, 14-Dr, 15-Q, 16-n, 17-ΔPr, 18-ΔPm, 19-ΔPt, 20-ΔPq, 21-Z
            # Constants (readonly): cols 1, 4-9, 13-15 (Vt, Kj, Un, λ, ξ, ρ, Ae, η, Dr, Q)
            # Editable variables: cols 2, 3, 10, 11, 12 (Qtreq, Vr, Lr, Lp, Ar)
            # Calculated columns (readonly): 4, 14, 15, 16, 17-20 (Kj, Dr, Q, n, ΔPr, ΔPm, ΔPt, ΔPq)
            constant_columns = [1, 4, 5, 6, 7, 8, 9, 13, 14, 15, 16, 17, 18, 19, 20]
            
            # Columns: 0-Speed, 1-Vt, 2-Qtreq, 3-Vr, 4-Kj, 5-Un, 6-λ, 7-ξ, 8-ρ, 9-Ae, 10-Lr, 11-Lp, 12-Ar, 13-η, 14-Dr, 15-Q, 16-n, 17-ΔPr, 18-ΔPm, 19-ΔPt, 20-ΔPq, 21-Z_raw, 22-Z
            # Constants (readonly): cols 1, 4-9, 13-21 (Vt, Kj, Un, λ, ξ, ρ, Ae, η, Dr, Q, n, ΔPr, ΔPm, ΔPt, ΔPq, Z_raw, Z)
            # Editable variables: cols 2, 3, 10, 11, 12 (Qtreq, Vr, Lr, Lp, Ar)
            constant_columns = [1, 4, 5, 6, 7, 8, 9, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
            
            for col in range(1, len(simplified_headers)):
                var = tk.StringVar(value="0.0")
                is_constant = col in constant_columns
                # Add validation for editable, non-constant columns
                editable_cols = [2, 3, 10, 11, 12]
                use_validation = col in editable_cols and col not in constant_columns
                
                entry = ttk.Entry(table_frame, textvariable=var, width=10, 
                                 state="readonly" if is_constant else "disabled",
                                 justify="center",
                                 validate="key" if use_validation else "none",
                                 validatecommand=self.numeric_vcmd if use_validation else "")
                entry.grid(row=row_idx, column=col, sticky="nsew")
                self.data_cells[direction][speed][col] = {"entry": entry, "var": var}
                
                # For editable columns, bind focus event to show prompt if disabled
                editable_cols = [2, 3, 10, 11, 12]
                if col in editable_cols:
                    entry.bind("<FocusIn>", lambda e, d=direction, c=col: self._on_cell_focus(e, d, c))
                    entry.bind("<FocusOut>", NumericValidator.default_to_zero_on_focusout)
                
                # Add trace for Vr (col 3) to auto-update Kj (col 4) and pressure values
                if col == 3:  # Vr column
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_kj(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_n(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_pressures(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_jet_fans(d, s))
                # Add trace for Lr (col 10) to auto-update Dr, n, and pressure values
                elif col == 10:  # Lr column
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_dr(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_n(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_pressures(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_jet_fans(d, s))
                # Add trace for Lp (col 11) to auto-update Dr and pressure values
                elif col == 11:  # Lp column
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_dr(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_pressures(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_jet_fans(d, s))
                # Add trace for Ar (col 12) to auto-update Dr and pressure values
                elif col == 12:  # Ar column
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_dr(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_pressures(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_jet_fans(d, s))
                # Add trace for Qtreq (col 2) to auto-update n and pressure values
                elif col == 2:  # Qtreq column
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_n(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_pressures(d, s))
                    var.trace_add("write", lambda *a, d=direction, s=speed: self._update_jet_fans(d, s))
        
        # Initialize with default constant values
        self._initialize_default_values(direction)
    
    def _on_cell_focus(self, event, direction, col):
        """Handle focus event on editable cells - show prompt if cell is disabled."""
        entry = event.widget
        if entry.cget("state") == "disabled":
            # Show prompt if not yet shown
            if not self._jet_fan_selection_prompted:
                messagebox.showinfo(
                    "Jet Fan Configuration Required",
                    "Please select both Jet Fan Diameter and Efficiency for each direction\n\n"
                    "- Jet Fan Diameter (mm): Select from available options\n"
                    "- Efficiency: Choose between High efficiency (30 m/s) or Standard (34 m/s)\n\n"
                    "Input cells will be enabled once both parameters are selected."
                )
                self._jet_fan_selection_prompted = True
        else:
            # Clear field when focused (click or tab) so new value can be entered fresh
            entry.delete(0, tk.END)
    
    def _check_jet_fan_selection(self, direction):
        """Check if jet fan diameter and efficiency are selected. Enable/disable inputs accordingly."""
        try:
            jet_var = self.jet_diameter_dir1_var if direction == 1 else self.jet_diameter_dir2_var
            eff_var = self.high_eff_dir1_var if direction == 1 else self.high_eff_dir2_var
            
            jet_val = jet_var.get()
            eff_val = eff_var.get()
            
            # Check if selections are valid (not placeholders)
            placeholder_jet = "-- Select Jet Fan Diameter (mm) --"
            placeholder_eff = "-- Select Efficiency --"
            
            is_valid = (jet_val and jet_val != placeholder_jet and 
                       eff_val and eff_val != placeholder_eff)
            
            # Enable/disable all editable input cells for this direction
            editable_cols = [2, 3, 10, 11, 12]  # Qtreq, Vr, Lr, Lp, Ar
            
            if direction in self.data_cells:
                for speed in self.data_cells[direction]:
                    for col in editable_cols:
                        if col in self.data_cells[direction][speed]:
                            entry = self.data_cells[direction][speed][col]["entry"]
                            entry.configure(state="normal" if is_valid else "disabled")
        
        except Exception as e:
            print(f"Error checking jet fan selection: {e}")
    
    def _initialize_default_values(self, direction):
        """Initialize cells with default constant values (no syncing from other tabs)."""
        try:
            from vent_functions import Vt_MAP
            speeds = [10, 20, 30, 40, 50, 60, 70, 80]
            
            for row_idx, speed in enumerate(speeds, start=1):
                cells = self.data_cells[direction][speed]
                
                # Get speed-dependent Vt from Vt_MAP
                vt_speed = Vt_MAP.get(int(speed), 0.0)
                
                # Initialize with default constant values (user will enter their own values)
                # Map to columns: 0-Speed, 1-Vt, 2-Qtreq, 3-Vr, 4-Kj, 5-Un, 6-λ, 7-ξ, 8-ρ, 9-Ae, 10-Lr, 11-Lp, 12-Ar, 13-η, 14-Dr, 15-Q, 16-n, 17-ΔPr, 18-ΔPm, 19-ΔPt, 20-ΔPq, 21-Z_raw, 22-Z
                defaults = {
                    1: f"{vt_speed:.2f}",  # Col 1 - Vt from speed map (constant)
                    2: "0.0",  # Col 2 - Qtreq (editable)
                    3: "0.0",  # Col 3 - Vr (editable)
                    4: "0.0",  # Col 4 - Kj (calculated from Vr)
                    5: "2.5",  # Col 5 - Un = 2.5 m/s (constant)
                    6: "0.025",  # Col 6 - λ = 0.025 (constant)
                    7: "0.6",  # Col 7 - ξ = 0.6 (constant)
                    8: "1.2",  # Col 8 - ρ = 1.2 kg/m³ (constant)
                    9: "1.0751",  # Col 9 - Ae = 1.0751 m² (constant)
                    10: "0.0",  # Col 10 - Lr (editable)
                    11: "0.0",  # Col 11 - Lp (editable)
                    12: "0.0",  # Col 12 - Ar (editable)
                    13: "0.95",  # Col 13 - η = 0.95 (constant)
                    14: "0.0",  # Col 14 - Dr (calculated from Ar, Lp)
                    15: "0.0",  # Col 15 - Q (constant, from traffic)
                    16: "0.0",  # Col 16 - n (calculated, from traffic)
                    17: "0.0",  # Col 17 - ΔPr (calculated)
                    18: "0.0",  # Col 18 - ΔPm (calculated)
                    19: "0.0",  # Col 19 - ΔPt (calculated)
                    20: "0.0",  # Col 20 - ΔPq (calculated)
                    21: "0.0",  # Col 21 - Z_raw (calculated)
                    22: "0",  # Col 22 - Z (calculated)
                }
                
                for col, value in defaults.items():
                    if col in cells:
                        cells[col]["var"].set(value)
                
                # Only update n from traffic estimation (Q is also from traffic)
                self._update_q(direction, speed)
                self._update_n(direction, speed)
        
        except Exception as e:
            print(f"Error initializing default values: {e}")
    
    def _update_kj(self, direction, speed):
        """Update Kj value based on Vr value for a specific row.
        Kj = 0.99 if Vr<4, 0.92 if 4≤Vr<8, 0.9 if Vr≥8
        """
        try:
            cells = self.data_cells[direction][speed]
            # Get Vr (col 3)
            vr = float(cells[3]["var"].get())
            
            # Calculate Kj based on Vr
            if vr < 4:
                kj = 0.99
            elif vr < 8:
                kj = 0.92
            else:
                kj = 0.9
            
            # Update Kj (col 4)
            cells[4]["var"].set(f"{kj:.2f}")
        except Exception as e:
            print(f"Error updating Kj: {e}")
    
    def _update_dr(self, direction, speed):
        """Update Dr value based on Lp and Ar values for a specific row."""
        try:
            cells = self.data_cells[direction][speed]
            # Get Lp (col 11) and Ar (col 12)
            lp = float(cells[11]["var"].get())
            ar = float(cells[12]["var"].get())
            
            # Calculate Dr = (4 * Ar) / Lp
            dr = (4.0 * ar / lp) if lp not in (0, 0.0) else 0.0
            
            # Update Dr (col 14)
            cells[14]["var"].set(f"{dr:.4f}")
        except Exception as e:
            print(f"Error updating Dr: {e}")
    
    def _update_q(self, direction, speed):
        """Update Q value from traffic estimation results (actual Vehicle/hr, lane).
        Q is the actual vehicle count per hour per lane from traffic estimation.
        """
        try:
            cells = self.data_cells[direction][speed]
            
            # Get actual Vehicle/hr, lane from traffic estimation cache
            direction_key = "From_To" if direction == 1 else "To_From"
            cache = self.volume_tab.vehicle_hr_lane_cache if self.volume_tab else {}
            vehicle_hr_lane = cache.get(direction_key, {}).get(int(speed), 0.0)
            
            # Update Q (col 15) with the actual Vehicle/hr, lane value from traffic estimation
            cells[15]["var"].set(f"{vehicle_hr_lane:.1f}")

            # Cascade updates so n, pressures, and jet fans refresh immediately
            self._update_n(direction, speed)
            self._update_pressures(direction, speed)
            self._update_jet_fans(direction, speed)
        except Exception as e:
            print(f"Error updating Q: {e}")
    
    def _update_n(self, direction, speed):
        """Update n using compute_n with Vehicle/hr·lane from Traffic Estimation when available."""
        try:
            cells = self.data_cells[direction][speed]
            
            # Get values from cells
            vt = self._safe_float(cells[1]["var"])  # Vt (col 1)
            qtreq = self._safe_float(cells[2]["var"])  # Qtreq (col 2)
            ar = self._safe_float(cells[12]["var"])  # Ar (col 12)
            lr = self._safe_float(cells[10]["var"])  # Lr (col 10)
            rho = self._safe_float(cells[8]["var"])  # ρ (col 8)
            xi = self._safe_float(cells[7]["var"])  # ξ (col 7)
            lamb = self._safe_float(cells[6]["var"])  # λ (col 6)
            dr = self._safe_float(cells[14]["var"])  # Dr (col 14)
            ae = self._safe_float(cells[9]["var"])  # Ae (col 9)
            eta = self._safe_float(cells[13]["var"])  # η (col 13)
            
            # Get direction-specific parameters
            if not self.jet_fan_tab:
                return
            
            lanes = int(self._safe_float(self.jet_fan_tab.lanes_dir1_var if direction == 1 else self.jet_fan_tab.lanes_dir2_var, 0))
            imax = self._safe_float(self.jet_fan_tab.imax_dir1_var if direction == 1 else self.jet_fan_tab.imax_dir2_var, 0)
            road_type_var = self.road_type_vars.get(direction)
            road_type = self._parse_road_type(road_type_var, default=1)
            
            # Prefer current Q value in the table; fallback to cached traffic estimation
            vehicle_hr_lane = self._safe_float(cells[15]["var"], 0.0)  # Q column (vehicles/hr·lane)
            if vehicle_hr_lane <= 0 and self.volume_tab:
                direction_key = "From_To" if direction == 1 else "To_From"
                cache = self.volume_tab.vehicle_hr_lane_cache if self.volume_tab else {}
                vehicle_hr_lane = cache.get(direction_key, {}).get(int(speed), 0.0)
            
            # Use compute_n from vent_functions to calculate number of vehicles
            from vent_functions import TunnelVentInputs, compute_n
            inp = TunnelVentInputs(
                V_kmh=speed,
                Qtreq=qtreq,
                Imax=imax,
                road_type=road_type,
                lanes=lanes,
                Ar=ar,
                Lr=lr,
                rho=rho,
                xi=xi,
                lamb=lamb,
                Dr=dr,
                Ae=ae,
                jet_diameter=1030,  # Default (not used in compute_n)
                high_efficiency=False,  # Default (not used in compute_n)
                eta=eta,
                vehicle_hr_lane=vehicle_hr_lane
            )
            
            n = compute_n(inp, vt)
            
            # Update n column (col 16)
            cells[16]["var"].set(f"{n:.0f}")

            # Refresh pressures to reflect new n value
            self._update_pressures(direction, speed)
            self._update_jet_fans(direction, speed)
            
        except Exception as e:
            print(f"Error updating n: {e}")
    
    def _recalc_all_rows(self, direction):
        """Recompute Kj, Dr, Q, n, pressures and jet fans for all speeds in a direction."""
        try:
            if direction not in self.data_cells:
                return
            for speed in self.data_cells[direction].keys():
                self._update_kj(direction, speed)
                self._update_dr(direction, speed)
                self._update_q(direction, speed)
                self._update_n(direction, speed)
                self._update_pressures(direction, speed)
                self._update_jet_fans(direction, speed)
        except Exception as e:
            print(f"Error recalculating rows: {e}")

    def _update_pressures(self, direction, speed):
        """Update pressure values (ΔPr, ΔPm, ΔPt, ΔPq) based on current values."""
        try:
            cells = self.data_cells[direction][speed]
            
            # Get values from cells
            vt = self._safe_float(cells[1]["var"])  # Vt (col 1)
            qtreq = self._safe_float(cells[2]["var"])  # Qtreq (col 2)
            vr = self._safe_float(cells[3]["var"])  # Vr (col 3)
            un = self._safe_float(cells[5]["var"])  # Un (col 5)
            lamb = self._safe_float(cells[6]["var"])  # λ (col 6)
            xi = self._safe_float(cells[7]["var"])  # ξ (col 7)
            rho = self._safe_float(cells[8]["var"])  # ρ (col 8)
            ae = self._safe_float(cells[9]["var"])  # Ae (col 9)
            lr = self._safe_float(cells[10]["var"])  # Lr - Tunnel length (col 10)
            lp = self._safe_float(cells[11]["var"])  # Lp - Segment length (col 11)
            ar = self._safe_float(cells[12]["var"])  # Ar (col 12)
            dr = self._safe_float(cells[14]["var"])  # Dr (col 14)
            n = self._safe_float(cells[16]["var"])  # n - Number of vehicles (col 16)
            
            # Calculate common factor: (1 + ξ + λ*Lr/Dr) * ρ / 2
            # Use Lr (tunnel length) for this calculation
            if dr > 0:
                common_factor = (1 + xi + lamb * lr / dr) * rho / 2.0
            else:
                common_factor = 0.0
            
            # ΔPr = common_factor * Vr²
            delta_pr = common_factor * (vr ** 2)
            
            # ΔPm = common_factor * Un²
            delta_pm = common_factor * (un ** 2)
            
            # ΔPt = sign(Vt−Vr) × ρ/2 × (Ae/Ar) × n × (Vt−Vr)²
            # where n is the number of vehicles in tunnel
            if vt == vr:
                delta_pt = 0.0
            else:
                sign = 1.0 if vt > vr else -1.0
                if ar > 0:
                    delta_pt = sign * rho / 2.0 * ae / ar * n * (vt - vr) ** 2
                else:
                    delta_pt = 0.0
            
            # ΔPq = ΔPr + ΔPm - ΔPt
            delta_pq = delta_pr + delta_pm - delta_pt
            
            # Update pressure cells (cols 17-20)
            cells[17]["var"].set(f"{delta_pr:.4f}")  # ΔPr (col 17)
            cells[18]["var"].set(f"{delta_pm:.4f}")  # ΔPm (col 18)
            cells[19]["var"].set(f"{delta_pt:.4f}")  # ΔPt (col 19)
            cells[20]["var"].set(f"{delta_pq:.4f}")  # ΔPq (col 20)
            
        except Exception as e:
            print(f"Error updating pressures: {e}")

    def _update_jet_fans(self, direction, speed):
        """Update Z_raw and Z (Z_applied) using independent jet fan parameters."""
        try:
            # Check if jet fan selection is valid (not placeholder)
            placeholder_jet = "-- Select Jet Fan Diameter (mm) --"
            placeholder_eff = "-- Select Efficiency --"
            
            jet_var = self.jet_diameter_dir1_var if direction == 1 else self.jet_diameter_dir2_var
            eff_var = self.high_eff_dir1_var if direction == 1 else self.high_eff_dir2_var
            
            jet_val = jet_var.get()
            eff_val = eff_var.get()
            
            # Skip calculation if placeholders are still selected
            if jet_val == placeholder_jet or eff_val == placeholder_eff:
                # Clear the Z values
                cells = self.data_cells[direction][speed]
                cells[21]["var"].set("0.00")
                cells[22]["var"].set("0")
                return
            
            cells = self.data_cells[direction][speed]
        
            # Get all required values
            vt = self._safe_float(cells[1]["var"])  # Vt (col 1)
            vr = self._safe_float(cells[3]["var"])  # Vr (col 3)
            kj = self._safe_float(cells[4]["var"])  # Kj (col 4)
            rho = self._safe_float(cells[8]["var"])  # ρ (col 8)
            ae = self._safe_float(cells[9]["var"])  # Ae (col 9)
            ar = self._safe_float(cells[12]["var"])  # Ar (col 12)
            eta = self._safe_float(cells[13]["var"])  # η (col 13)
            delta_pq = self._safe_float(cells[20]["var"])  # ΔPq (col 20)
        
            # Get jet fan parameters from dropdowns in this tab
            jet_diameter = int(jet_val)
            high_eff_str = eff_val
            high_efficiency = "High efficiency" in high_eff_str
        
            # Import from vent_functions
            from vent_functions import JET_AREA_MAP
        
            # Get Aj from lookup
            if jet_diameter not in JET_AREA_MAP:
                aj = 0.83  # Default to 1030mm
            else:
                aj = JET_AREA_MAP[jet_diameter]
        
            # Calculate Vj
            vj = 30.0 if high_efficiency else 34.0
        
            # Calculate ΔPj using the formula from vent_functions
            # ΔPj = Kj * ρ * Vj^2 * Aj/Ar * (1 - Vr/Vj) * η
            if vj > 0 and ar > 0 and vj != vr:
                delta_pj = round(kj * rho * vj ** 2 * aj / ar * (1 - vr / vj) * eta, 4)
            else:
                delta_pj = 0.0
        
            # Calculate Z_raw = ΔPq / ΔPj
            if delta_pj > 0:
                z_raw = round(delta_pq / delta_pj, 2)
            else:
                z_raw = 0.0 if delta_pq == 0 else float('inf')
        
            # Calculate Z_applied (ceiling of z_raw if > 0, else 0)
            if z_raw <= 0 or z_raw == float('inf') or z_raw != z_raw:  # NaN check
                z_applied = 0
            else:
                import math
                z_applied = math.ceil(z_raw)
        
            # Update Z_raw (col 21) and Z (col 22)
            cells[21]["var"].set(f"{z_raw:.2f}" if z_raw != float('inf') else "inf")
            cells[22]["var"].set(str(z_applied))
        
        except Exception as e:
            print(f"Error updating jet fans: {e}")

    def _calculate_all(self):
        """Calculate ventilation capacity for both directions. Requires traffic estimation first."""
        # Check if traffic estimation results are available
        cache = self.volume_tab.vehicle_hr_lane_cache if self.volume_tab else {}
        has_from_to_data = bool(cache.get("From_To", {}))
        has_to_from_data = bool(cache.get("To_From", {}))
        
        if not (has_from_to_data or has_to_from_data):
            messagebox.showwarning(
                "Traffic Estimation Required",
                "Please compute traffic estimation results first (Estimate Traffic Volume tab).\n\n"
                "The ventilation capacity calculations require Vehicle/hr per lane values\n"
                "from the traffic estimation results."
            )
            return
        
        if not self.jet_fan_tab:
            messagebox.showwarning("Warning", "Jet Fan tab not available")
            return
        
        try:
            # Get constants from Jet Fan tab
            v_kmh = float(self.jet_fan_tab.v_kmh_var.get())
            rho = float(self.jet_fan_tab.rho_var.get())
            xi = float(self.jet_fan_tab.xi_var.get())
            lamb = float(self.jet_fan_tab.lamb_var.get())
            ae = float(self.jet_fan_tab.ae_var.get())
            eta = float(self.jet_fan_tab.eta_var.get())
            jet_diameter = int(self.jet_fan_tab.jet_diameter_var.get())
            un = float(self.jet_fan_tab.un_var.get())
            
            # Build detailed message with all constants
            msg = "Loaded Constants:\n\n"
            msg += f"V (design speed) = {v_kmh} km/h\n"
            msg += f"ρ (air density) = {rho} kg/m³\n"
            msg += f"ξ (entrance loss) = {xi}\n"
            msg += f"λ (friction loss) = {lamb}\n"
            msg += f"Ae (equivalent area) = {ae} m²\n"
            msg += f"η (efficiency) = {eta}\n"
            msg += f"Un (natural wind) = {un} m/s\n"
            msg += f"Jet Diameter = {jet_diameter} mm\n\n"
            msg += "Tables updated with all calculations.\n"
            msg += "Road type can be changed per direction to recalculate Q and dependent values."
            
            messagebox.showinfo("Calculation Complete", msg)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _refresh_q_values_in_tables(self, direction_key):
        """Refresh Q (and subsequently n, pressures and jet fans) in Ventilation Capacity tables after traffic estimation."""
        try:
            direction = 1 if direction_key == "From_To" else 2
            
            # Check if data_cells exists and has data for this direction
            if not hasattr(self, 'data_cells') or direction not in self.data_cells:
                print(f"DEBUG: No data_cells for direction {direction}")
                return
            
            # Get cache from volume_tab
            if not self.volume_tab:
                print("DEBUG: No volume_tab reference")
                return
                
            cache = self.volume_tab.vehicle_hr_lane_cache
            cache_data = cache.get(direction_key, {})
            print(f"DEBUG: Refreshing Q for direction {direction} ({direction_key}), cache: {cache_data}")
            
            # Update Q and dependent calculations for all speeds
            for speed in list(self.data_cells[direction].keys()):
                cached_value = cache_data.get(int(speed), 0.0)
                print(f"DEBUG: Speed {speed} - cached Q value: {cached_value}")
                self._update_q(direction, speed)
                self._update_n(direction, speed)
                self._update_pressures(direction, speed)
                self._update_jet_fans(direction, speed)
                
            print(f"DEBUG: Finished refreshing Q values for direction {direction}")
        except Exception as e:
            import traceback
            print(f"Error refreshing Q values in tables: {e}")
            traceback.print_exc()

    def _export_results(self):
        """Export ventilation capacity results to file."""
        try:
            filename = filedialog.asksaveasfilename(
                title="Export Ventilation Capacity",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if filename:
                messagebox.showinfo("Success", f"Exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


class JetFanCalculatorWindow(tk.Toplevel):
    """Separate window for Jet Fan calculations."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Jet Fan Calculator")
        self.geometry("800x700")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)


        # Create result tab first
        result_tab = ResultsTab(notebook)

        # First tab: Number of Jet Fan (pass result_tab reference)
        jet_fan_tab = JetFanTab(notebook, result_tab=result_tab)
        notebook.add(jet_fan_tab, text="Number of Jet Fan")

        # Results tab
        notebook.add(result_tab, text="Results (summary)")

        # Ventilation Capacity tab
        ventilation_capacity_tab = VentilationCapacityTab(notebook, jet_fan_tab=jet_fan_tab)
        notebook.add(ventilation_capacity_tab, text="Ventilation Capacity")

        # --- Add Data Catalog tab with 표고 보정계수 [fh] table ---
        data_catalog_tab = ttk.Frame(notebook)
        notebook.add(data_catalog_tab, text="Data Catalog")

        pad = 10
        main_frame = ttk.Frame(data_catalog_tab, padding="20 20 20 20")
        main_frame.pack(fill="both", expand=True)

        # Section: Emission by vehicle type (placeholder for context)
        ttk.Label(main_frame, text="Emission by vehicle type table (placeholder)", font=("Arial", 11, "bold"), background="#e0e0e0").pack(fill="x", pady=(0, pad))

        # --- New table: 표고 보정계수 [fh] ---
        # Get direction names dynamically if available
        dir1 = "FROM"
        dir2 = "TO"
        try:
            if hasattr(jet_fan_tab, 'volume_tab') and jet_fan_tab.volume_tab:
                dir1 = jet_fan_tab.volume_tab.dir1Name.get()
                dir2 = jet_fan_tab.volume_tab.dir2Name.get()
        except Exception:
            pass

        fh_title = ttk.Label(
            main_frame,
            text="표고 보정계수 [fh]",
            font=("Arial", 11, "bold"),
            background="#e0e0e0",
            borderwidth=1,
            relief="solid",
            anchor="center",
            justify="center",
            padding=5,
        )
        fh_title.pack(fill="x", pady=(pad, 0))

        fh_table = ttk.Frame(main_frame)
        fh_table.pack(fill="x", pady=(0, pad))

        # Table headers with dynamic direction names
        headers = [
            "구분", f"{dir1}→{dir2}", f"{dir2}→{dir1}"
        ]
        for col, header in enumerate(headers):
            ttk.Label(
                fh_table,
                text=header,
                font=("Arial", 9, "bold"),
                borderwidth=1,
                relief="solid",
                padding=5,
                background="#e0e0e0",
                anchor="center",
                justify="center",
            ).grid(row=0, column=col, sticky="nsew")
            fh_table.columnconfigure(col, weight=1, minsize=80)

        # Table data (static values from user-provided table)
        fh_data = [
            ["1구간", "1.00", "1.00"],
            ["2구간", "0.98", "1.02"],
            ["3구간", "0.96", "1.04"],
            ["4구간", "0.94", "1.06"],
            ["5구간", "0.92", "1.08"],
            ["6구간", "0.90", "1.10"],
            ["7구간", "0.88", "1.12"],
            ["8구간", "0.86", "1.14"],
            ["9구간", "0.84", "1.16"],
            ["10구간", "0.82", "1.18"],
        ]
        for r, row in enumerate(fh_data, start=1):
            for c, val in enumerate(row):
                ttk.Label(
                    fh_table,
                    text=val,
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background="#ffffff" if r % 2 == 1 else "#f9f9f9",
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r, column=c, sticky="nsew")


# ----------------------------
# Ventilation Volume window and helper components
# ----------------------------
class SegmentsTableTransposed(ttk.Frame):
    """Placeholder for a segments table (direction-specific)."""
    def __init__(self, master, direction, segments, on_change, t, **kwargs):
        super().__init__(master, **kwargs)
        # ttk.Label(self, text=f"Segments table ({direction})").pack(anchor="w", padx=4, pady=4)
        # Future: implement real editable segments table.


class TunnelGeometry(ttk.LabelFrame):
    """Geometry section with adjustable per-section inputs + Ar/Lp.

    Adds a transposed grid (rows: items; columns: Section 1..N) above the Ar/Lp inputs:
      - Tunnel gradient [%]
      - Tunnel length [m]
      - Number of lane(s) [N]

    Parameters:
      ar_var, lp_var: tk variables for Ar and Lp entries
      count_var: tk.IntVar controlling number of sections (columns)
      segments: list of dicts per section with keys: gradient, length, lanes
      on_segments_change: optional callback(direction, segments)
      on_ar_change, on_lp_change: callbacks for Ar/Lp changes
    """
    def __init__(self, master, ar_var, lp_var, count_var, segments, on_segments_change, on_ar_change, on_lp_change, t, **kwargs):
        super().__init__(master, text="Tunnel Geometry", **kwargs)

        self.count_var = count_var
        self.segments = segments
        self.on_segments_change = on_segments_change

        # Container for the transposed grid
        self.grid_frame = ttk.Frame(self)
        self.grid_frame.grid(row=0, column=0, columnspan=4, sticky="nsew", padx=4, pady=(4, 8))

        # Build initial grid
        self._build_segments_grid()

        # Rebuild grid when section count changes
        self.count_var.trace_add("write", lambda *a: self._build_segments_grid())

        # Separator
        ttk.Separator(self, orient="horizontal").grid(row=1, column=0, columnspan=4, sticky="ew", pady=(2, 6))

        # Computed average Ar/Lp (read-only)
        ttk.Label(self, text="Average Tunnel Cross-Section Area, Ar [m²]:").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.avg_ar_var = tk.DoubleVar(value=0.0)
        ttk.Entry(self, textvariable=self.avg_ar_var, width=14, state="readonly").grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(self, text="Average Tunnel Perimeter, Lp [m]:").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        self.avg_lp_var = tk.DoubleVar(value=0.0)
        ttk.Entry(self, textvariable=self.avg_lp_var, width=14, state="readonly").grid(row=3, column=1, sticky="w", padx=4, pady=4)

        # Computed Dr = (4 * Ar) / Lp (read-only)
        self.dr_var = tk.DoubleVar(value=0.0)
        ttk.Label(self, text="Tunnel Representative Diameter, Dr [m]:").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(self, textvariable=self.dr_var, width=14, state="readonly").grid(row=4, column=1, sticky="w", padx=4, pady=4)

        if on_ar_change is not None:
            ar_var.trace_add("write", lambda *args: on_ar_change(ar_var.get()))
        if on_lp_change is not None:
            lp_var.trace_add("write", lambda *args: on_lp_change(lp_var.get()))

        # Always recompute Dr when Ar or Lp changes
        ar_var.trace_add("write", lambda *args: self._recompute_dr_and_averages(ar_var, lp_var))
        lp_var.trace_add("write", lambda *args: self._recompute_dr_and_averages(ar_var, lp_var))

        # Initial averages and Dr compute from segments
        self._recompute_dr_and_averages(self.avg_ar_var, self.avg_lp_var)

        # Keep label/entry columns anchored left; let a right filler stretch
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=1)

    def _recompute_dr(self, ar_var, lp_var):
        try:
            ar = float(ar_var.get())
        except Exception:
            ar = 0.0
        try:
            lp = float(lp_var.get())
        except Exception:
            lp = 0.0
        dr = (4.0 * ar / lp) if lp not in (0, 0.0) else 0.0
        self.dr_var.set(round(dr, 4))

    def _recompute_dr_and_averages(self, ar_var, lp_var):
        """Compute average Ar, Lp from segments (excluding zero/empty entries) and update Dr."""
        # Compute averages from segments, excluding empty cells (value = 0.0)
        if self.segments:
            # Filter out zero values for Ar
            ar_values = [float(seg.get("ar", 0.0) or 0.0) for seg in self.segments if float(seg.get("ar", 0.0) or 0.0) > 0]
            avg_ar = sum(ar_values) / len(ar_values) if ar_values else 0.0
            
            # Filter out zero values for Lp
            lp_values = [float(seg.get("lp", 0.0) or 0.0) for seg in self.segments if float(seg.get("lp", 0.0) or 0.0) > 0]
            avg_lp = sum(lp_values) / len(lp_values) if lp_values else 0.0
        else:
            avg_ar = 0.0
            avg_lp = 0.0
        
        self.avg_ar_var.set(round(avg_ar, 4))
        self.avg_lp_var.set(round(avg_lp, 4))
        
        # Compute Dr using averages
        dr = (4.0 * avg_ar / avg_lp) if avg_lp not in (0, 0.0) else 0.0
        self.dr_var.set(round(dr, 4))

    def _build_segments_grid(self):
        # Clear previous grid
        for w in self.grid_frame.winfo_children():
            w.destroy()

        n = self._safe_int(self.count_var.get(), 1)
        n = max(1, min(50, n))

        # Ensure segments storage size and initialize new keys
        while len(self.segments) < n:
            self.segments.append({"gradient": 0.0, "length": 0.0, "lanes": 1, "ar": 0.0, "lp": 0.0})
        while len(self.segments) > n:
            self.segments.pop()
        
        # Ensure segments storage has new keys
        for seg in self.segments:
            if "ar" not in seg:
                seg["ar"] = 0.0
            if "lp" not in seg:
                seg["lp"] = 0.0

        header_style = {"padx": 6, "pady": 2}
        item_style = {"padx": 4, "pady": 2}

        # Header row: Item | Section 1 | Section 2 | ...
        ttk.Label(self.grid_frame, text="Item", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", **header_style)
        for i in range(n):
            ttk.Label(self.grid_frame, text=f"Sec. {i+1}", font=("Arial", 10, "bold")).grid(row=0, column=i+1, sticky="w", **header_style)

        # Rows: Gradient, Length, Lanes, Ar, Lp
        # Use StringVar for all editable cells so empty values are allowed
        # and won't raise TclError on get(). Convert safely on write.
        rows = [
            ("Tunnel gradient [%]", "gradient", tk.StringVar),
            ("Tunnel length [m]", "length", tk.StringVar),
            ("Number of lanes, N", "lanes", tk.StringVar),
            ("Tunnel Cross-Section Area, Ar [m²]", "ar", tk.StringVar),
            ("Tunnel Perimeter, Lp [m]", "lp", tk.StringVar),
        ]

        # Keep strong refs to vars to prevent GC
        self._cell_vars = []

        for r_index, (label, key, VarType) in enumerate(rows, start=1):
            ttk.Label(self.grid_frame, text=label).grid(row=r_index, column=0, sticky="w", **item_style)
            row_vars = []
            for i in range(n):
                default = self.segments[i].get(key, 0 if key == "lanes" else 0.0)
                var = VarType(value=default)
                # Add numeric validation for numeric fields (ar and lp)
                if key in ("ar", "lp"):
                    vcmd = (self.register(NumericValidator.validate_numeric), '%S', '%d')
                    ent = ttk.Entry(self.grid_frame, textvariable=var, width=14, validate="key", validatecommand=vcmd)
                else:
                    ent = ttk.Entry(self.grid_frame, textvariable=var, width=14)
                # Add clear-on-focus binding for ALL entry fields
                ent.bind('<FocusIn>', NumericValidator.clear_on_focus)
                ent.bind('<FocusOut>', NumericValidator.default_to_zero_on_focusout)
                ent.grid(row=r_index, column=i+1, sticky="w", **item_style)

                # attach trace to update storage
                if key == "lanes":
                    var.trace_add("write", lambda *a, idx=i, v=var, k=key: self._update_segment(idx, k, self._sanitize_lanes(v.get())))
                else:
                    # Get the value from the variable (string) and convert to float safely
                    var.trace_add("write", lambda *a, idx=i, v=var, k=key: self._update_segment(idx, k, self._safe_float(v.get(), 0.0)))

                row_vars.append(var)
            self._cell_vars.append(row_vars)

        # Column weights: keep 'Item' fixed; let section columns stretch
        self.grid_frame.columnconfigure(0, weight=0)
        for c in range(1, n+1):
            self.grid_frame.columnconfigure(c, weight=1)
        
        # Recompute averages after grid rebuild (only if variables are initialized)
        if hasattr(self, 'avg_ar_var') and hasattr(self, 'avg_lp_var'):
            self._recompute_dr_and_averages(self.avg_ar_var, self.avg_lp_var)

    def _update_segment(self, idx, key, value):
        if 0 <= idx < len(self.segments):
            self.segments[idx][key] = value
            if key == "lanes" and (not isinstance(value, int) or value < 1):
                self.segments[idx][key] = 1
        if callable(self.on_segments_change):
            try:
                self.on_segments_change("segments", self.segments)
            except Exception:
                pass
        # Recompute averages after any segment change, especially for Ar/Lp
        if key in ("ar", "lp"):
            try:
                self._recompute_dr_and_averages(self.avg_ar_var, self.avg_lp_var)
            except Exception:
                pass

    @staticmethod
    def _safe_int(v, default=0):
        try:
            return int(v)
        except Exception:
            return default

    @staticmethod
    def _safe_float(v, default=0.0):
        try:
            if v == "" or v is None:
                return default
            return float(v)
        except Exception:
            return default

    @staticmethod
    def _sanitize_lanes(v):
        try:
            val = int(v)
        except Exception:
            val = 1
        return max(1, val)


class SummaryRow(ttk.Frame):
    """Displays provided stats dictionary in one row and allows refresh."""
    def __init__(self, master, stats, traffic, t, **kwargs):
        super().__init__(master, **kwargs)
        self._stats = stats
        self._traffic = traffic
        self._stat_labels = {}

        col = 0
        ttk.Label(self, text="Stats:", font=("Arial", 10, "bold")).grid(row=0, column=col, sticky="w", padx=4, pady=2)
        col += 1
        for key, value in self._stats.items():
            lbl = ttk.Label(self, text=f"{key}: {value}")
            lbl.grid(row=0, column=col, sticky="w", padx=4, pady=2)
            self._stat_labels[key] = lbl
            col += 1

    def set_data(self, stats=None, traffic=None):
        if stats is not None:
            self._stats.update(stats)
            for key, value in stats.items():
                if key in self._stat_labels:
                    self._stat_labels[key].configure(text=f"{key}: {value}")


class VentilationVolumeTab(ttk.Frame):
    """Tab for Calculate Ventilation Volume functionality."""
    def __init__(self, parent, jet_fan_tab=None):
        super().__init__(parent)
        self.jet_fan_tab = jet_fan_tab
        # Cache for Vehicle/hr, lane values keyed by direction and speed
        self.vehicle_hr_lane_cache = {"From_To": {}, "To_From": {}}
        self._build_interface()

    def _build_interface(self):
        # Speed capacity per lane table (PCU/hr·lane)
        self.SPEED_CAPACITY_TABLE = {80: 2000, 100: 2200, 120: 2300}

        # Direction name variables (editable)
        self.dir1Name = tk.StringVar(value="FROM")
        self.dir2Name = tk.StringVar(value="TO")

        # Translation-like dict
        t = {
            "dir1Title": self.dir1Name,
            "dir2Title": self.dir2Name,
            "numberOfSectionsLabel": "Number of sections",
            "averageElevationLabel": "Average elevation",
        }

        # State variables
        self.sectionCountFromToTo = tk.IntVar(value=10)
        self.sectionCountToToFrom = tk.IntVar(value=10)
        self.avgElevationFromToTo = tk.DoubleVar(value=0.0)
        self.avgElevationToToFrom = tk.DoubleVar(value=0.0)
        # Ventilation design speeds (80/100/120)
        self.designSpeedFromToTo = tk.IntVar(value=80)
        self.designSpeedToToFrom = tk.IntVar(value=80)
        self.tunnelArFromToTo = tk.DoubleVar(value=0.0)
        self.tunnelLpFromToTo = tk.DoubleVar(value=0.0)
        self.tunnelArToToFrom = tk.DoubleVar(value=0.0)
        self.tunnelLpToToFrom = tk.DoubleVar(value=0.0)
        # Total length by direction (m)
        self.totalLengthFromToTo_m = tk.DoubleVar(value=0.0)
        self.totalLengthToToFrom_m = tk.DoubleVar(value=0.0)
        
        # Road type for traffic flow calculation (1=National/Expressway, 2=Downtown)
        self.roadTypeFromToTo = tk.StringVar(value="1 - National/Expressway (K=150)")
        self.roadTypeToToFrom = tk.StringVar(value="1 - National/Expressway (K=150)")

        # Example data containers
        self.statsFromToTo = {"length_km": 0.0, "max_gradient": 0.0, "lanes": 1, "cap_per_lane": 0, "total_capacity": 0}
        self.statsToToFrom = {"length_km": 0.0, "max_gradient": 0.0, "lanes": 1, "cap_per_lane": 0, "total_capacity": 0}
        self.trafficFromToTo = {"AADT": 0, "trucks_pct": 0}
        self.trafficToToFrom = {"AADT": 0, "trucks_pct": 0}
        self.segmentsFromToTo = []
        self.segmentsToToFrom = []

        def handleSectionCountChange(direction, value):
            try:
                v = int(value)
            except ValueError:
                return
            v = max(1, min(50, v))
            if direction == "FromToTo":
                self.sectionCountFromToTo.set(v)
                self._update_summary("FromToTo")
            elif direction == "ToToFrom":
                self.sectionCountToToFrom.set(v)
                self._update_summary("ToToFrom")

        # Geometry callbacks (placeholders)
        def onArChangeFrom(val):
            pass
        def onLpChangeFrom(val):
            pass
        def onArChangeTo(val):
            pass
        def onLpChangeTo(val):
            pass

        # Create scrollable frame
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        card_padding = {"padx": 15, "pady": 10}

        # Direction 1 card
        card1 = ttk.Frame(scrollable_frame, relief="raised", borderwidth=1, padding="10 10 10 10")
        card1.pack(fill="x", **card_padding)
        header1 = ttk.Frame(card1)
        header1.pack(fill="x", pady=(0, 10))
        
        # Editable direction name
        dir_name_frame1 = ttk.Frame(header1)
        dir_name_frame1.pack(side="left", padx=(0, 10))
        ttk.Entry(dir_name_frame1, textvariable=self.dir1Name, width=15, font=("Arial", 14, "bold")).pack(side="left", padx=(0, 5))
        ttk.Label(dir_name_frame1, text="→", font=("Arial", 14, "bold")).pack(side="left", padx=(0, 5))
        ttk.Entry(dir_name_frame1, textvariable=self.dir2Name, width=15, font=("Arial", 14, "bold")).pack(side="left")
        controls1 = ttk.Frame(header1)
        controls1.pack(side="right", padx=(10, 0))
        sections_group1 = ttk.Frame(controls1)
        sections_group1.pack(side="left", padx=8)
        ttk.Label(sections_group1, text=t["numberOfSectionsLabel"] + ":").pack(side="left")
        tk.Spinbox(
            sections_group1,
            from_=1,
            to=50,
            textvariable=self.sectionCountFromToTo,
            width=5,
            command=lambda: handleSectionCountChange("FromToTo", self.sectionCountFromToTo.get()),
        ).pack(side="left")
        elevation_group1 = ttk.Frame(controls1)
        elevation_group1.pack(side="left", padx=8)
        ttk.Label(elevation_group1, text=t["averageElevationLabel"] + ":").pack(side="left")
        vcmd_elevation1 = (self.register(NumericValidator.validate_numeric), '%S', '%d')
        elev_entry1 = ttk.Entry(elevation_group1, textvariable=self.avgElevationFromToTo, width=10, validate="key", validatecommand=vcmd_elevation1)
        elev_entry1.pack(side="left")
        elev_entry1.bind('<FocusIn>', NumericValidator.clear_on_focus)
        elev_entry1.bind('<FocusOut>', NumericValidator.default_to_zero_on_focusout)

        # Ventilation Design Speed (80/100/120)
        speed_group1 = ttk.Frame(controls1)
        speed_group1.pack(side="left", padx=8)
        ttk.Label(speed_group1, text="Ventilation Design Speed:").pack(side="left")
        ttk.Combobox(
            speed_group1,
            textvariable=self.designSpeedFromToTo,
            values=[80, 100, 120],
            state="readonly",
            width=6,
        ).pack(side="left")
        SegmentsTableTransposed(card1, "FromToTo", self.segmentsFromToTo, lambda *_: self._update_summary("FromToTo"), t).pack(fill="x", pady=4)
        self.tunnelGeometryFromToTo = TunnelGeometry(
            card1,
            self.tunnelArFromToTo,
            self.tunnelLpFromToTo,
            self.sectionCountFromToTo,
            self.segmentsFromToTo,
            lambda *a: self._update_summary("FromToTo"),
            onArChangeFrom,
            onLpChangeFrom,
            t,
        )
        self.tunnelGeometryFromToTo.pack(fill="x", pady=4)
        self.summaryRowFromToTo = SummaryRow(card1, self.statsFromToTo, self.trafficFromToTo, t)
        self.summaryRowFromToTo.pack(fill="x", pady=4)

        # Direction 2 card
        card2 = ttk.Frame(scrollable_frame, relief="raised", borderwidth=1, padding="10 10 10 10")
        card2.pack(fill="x", **card_padding)
        header2 = ttk.Frame(card2)
        header2.pack(fill="x", pady=(0, 10))
        
        # Editable direction name (reverse order)
        dir_name_frame2 = ttk.Frame(header2)
        dir_name_frame2.pack(side="left", padx=(0, 10))
        ttk.Entry(dir_name_frame2, textvariable=self.dir2Name, width=15, font=("Arial", 14, "bold")).pack(side="left", padx=(0, 5))
        ttk.Label(dir_name_frame2, text="→", font=("Arial", 14, "bold")).pack(side="left", padx=(0, 5))
        ttk.Entry(dir_name_frame2, textvariable=self.dir1Name, width=15, font=("Arial", 14, "bold")).pack(side="left")
        controls2 = ttk.Frame(header2)
        controls2.pack(side="right", padx=(10, 0))
        sections_group2 = ttk.Frame(controls2)
        sections_group2.pack(side="left", padx=8)
        ttk.Label(sections_group2, text=t["numberOfSectionsLabel"] + ":").pack(side="left")
        tk.Spinbox(
            sections_group2,
            from_=1,
            to=50,
            textvariable=self.sectionCountToToFrom,
            width=5,
            command=lambda: handleSectionCountChange("ToToFrom", self.sectionCountToToFrom.get()),
        ).pack(side="left")
        elevation_group2 = ttk.Frame(controls2)
        elevation_group2.pack(side="left", padx=8)
        ttk.Label(elevation_group2, text=t["averageElevationLabel"] + ":").pack(side="left")
        vcmd_elevation2 = (self.register(NumericValidator.validate_numeric), '%S', '%d')
        elev_entry2 = ttk.Entry(elevation_group2, textvariable=self.avgElevationToToFrom, width=10, validate="key", validatecommand=vcmd_elevation2)
        elev_entry2.pack(side="left")
        elev_entry2.bind('<FocusIn>', NumericValidator.clear_on_focus)
        elev_entry2.bind('<FocusOut>', NumericValidator.default_to_zero_on_focusout)

        # Ventilation Design Speed (80/100/120)
        speed_group2 = ttk.Frame(controls2)
        speed_group2.pack(side="left", padx=8)
        ttk.Label(speed_group2, text="Ventilation Design Speed:").pack(side="left")
        ttk.Combobox(
            speed_group2,
            textvariable=self.designSpeedToToFrom,
            values=[80, 100, 120],
            state="readonly",
            width=6,
        ).pack(side="left")
        SegmentsTableTransposed(card2, "ToToFrom", self.segmentsToToFrom, lambda *_: self._update_summary("ToToFrom"), t).pack(fill="x", pady=4)
        self.tunnelGeometryToToFrom = TunnelGeometry(
            card2,
            self.tunnelArToToFrom,
            self.tunnelLpToToFrom,
            self.sectionCountToToFrom,
            self.segmentsToToFrom,
            lambda *a: self._update_summary("ToToFrom"),
            onArChangeTo,
            onLpChangeTo,
            t,
        )
        self.tunnelGeometryToToFrom.pack(fill="x", pady=4)
        self.summaryRowToToFrom = SummaryRow(card2, self.statsToToFrom, self.trafficToToFrom, t)
        self.summaryRowToToFrom.pack(fill="x", pady=4)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Store references to traffic card frames for later updates
        self.traffic_card1_frame = None
        self.traffic_card2_frame = None
        
        # Trace design speed changes to refresh summary
        self.designSpeedFromToTo.trace_add("write", lambda *a: self._update_summary("FromToTo"))
        self.designSpeedToToFrom.trace_add("write", lambda *a: self._update_summary("ToToFrom"))

        # Trace direction name changes to update traffic panel labels
        self.dir1Name.trace_add("write", lambda *a: self._update_traffic_labels())
        self.dir2Name.trace_add("write", lambda *a: self._update_traffic_labels())

        # Initial compute
        self._update_summary("FromToTo")
        self._update_summary("ToToFrom")

        # Add traffic estimation panel after direction cards
        self._add_traffic_estimation_panel(scrollable_frame)
        
        # Add merged FIV Correction Coefficient Table Panel (FROM on top, TO below)
        self._add_fiv_correction_panel(scrollable_frame)

    def _update_summary(self, direction):
        if direction == "FromToTo":
            segments = self.segmentsFromToTo
            design_speed = int(self.designSpeedFromToTo.get())
            stats = self.statsFromToTo
            row = self.summaryRowFromToTo
            count = int(self.sectionCountFromToTo.get())
        else:
            segments = self.segmentsToToFrom
            design_speed = int(self.designSpeedToToFrom.get())
            stats = self.statsToToFrom
            row = self.summaryRowToToFrom
            count = int(self.sectionCountToToFrom.get())

        # Ensure segment list has desired size
        while len(segments) < max(1, count):
            segments.append({"gradient": 0.0, "length": 0.0, "lanes": 1})
        if len(segments) > count:
            segments[:] = segments[:count]

        total_length_m = sum(float(s.get("length", 0.0) or 0.0) for s in segments)
        max_gradient = max(float(s.get("gradient", 0.0) or 0.0) for s in segments) if segments else 0.0
        max_lanes = max(int(s.get("lanes", 1) or 1) for s in segments) if segments else 1

        cap_per_lane = self.SPEED_CAPACITY_TABLE.get(design_speed, 2000)
        total_capacity = cap_per_lane * max_lanes

        stats_update = {
            "length_km": round(total_length_m / 1000.0, 3),
            "max_gradient": round(max_gradient, 2),
            "lanes": max_lanes,
            "cap_per_lane": cap_per_lane,
            "total_capacity": total_capacity,
        }

        stats.update(stats_update)
        row.set_data(stats=stats_update)
        # update total length variable for external consumers
        if direction == "FromToTo":
            self.totalLengthFromToTo_m.set(total_length_m)
        else:
            self.totalLengthToToFrom_m.set(total_length_m)

    def get_params_for_jet(self, direction="FromToTo"):
        if direction == "FromToTo":
            # Use average Ar and Lp from segments
            ar_avg = float(self.tunnelGeometryFromToTo.avg_ar_var.get()) if hasattr(self, 'tunnelGeometryFromToTo') else 0.0
            lp_avg = float(self.tunnelGeometryFromToTo.avg_lp_var.get()) if hasattr(self, 'tunnelGeometryFromToTo') else 0.0
            dr = float(self.tunnelGeometryFromToTo.dr_var.get()) if hasattr(self, 'tunnelGeometryFromToTo') else 0.0
            Lr_m = float(self.totalLengthFromToTo_m.get())
        else:
            # Use average Ar and Lp from segments
            ar_avg = float(self.tunnelGeometryToToFrom.avg_ar_var.get()) if hasattr(self, 'tunnelGeometryToToFrom') else 0.0
            lp_avg = float(self.tunnelGeometryToToFrom.avg_lp_var.get()) if hasattr(self, 'tunnelGeometryToToFrom') else 0.0
            dr = float(self.tunnelGeometryToToFrom.dr_var.get()) if hasattr(self, 'tunnelGeometryToToFrom') else 0.0
            Lr_m = float(self.totalLengthToToFrom_m.get())
        return {"Ar": ar_avg, "Lp": lp_avg, "Lr_m": Lr_m, "Dr": dr}

    def get_vehicle_hr_lane(self, direction="FromToTo", speed_kmh=None):
        """Return cached Vehicle/hr, lane for a given direction and speed."""
        key = "From_To" if direction == "FromToTo" else "To_From"
        cache = self.vehicle_hr_lane_cache.get(key, {})
        if speed_kmh is None:
            return None
        try:
            speed_int = int(round(float(speed_kmh)))
            return cache.get(speed_int)
        except Exception:
            return None

    def get_volume_summary(self, direction="FromToTo"):
        if direction == "FromToTo":
            stats = dict(self.statsFromToTo)
            design_speed = int(self.designSpeedFromToTo.get())
            params = self.get_params_for_jet(direction)
            dir_label = f"{self.dir1Name.get()} → {self.dir2Name.get()}"
        else:
            stats = dict(self.statsToToFrom)
            design_speed = int(self.designSpeedToToFrom.get())
            params = self.get_params_for_jet(direction)
            dir_label = f"{self.dir2Name.get()} → {self.dir1Name.get()}"
        stats.update({
            "direction": dir_label,
            "design_speed": design_speed,
            "Ar": params["Ar"],
            "Lp": params["Lp"],
            "Dr": params["Dr"],
            "Lr_m": params["Lr_m"],
        })
        return stats

    def _update_traffic_labels(self):
        """Update traffic panel labels when direction names change."""
        dir1_name = self.dir1Name.get()
        dir2_name = self.dir2Name.get()
        
        # Update traffic card labels if they exist
        if hasattr(self, 'traffic_card1_label'):
            self.traffic_card1_label.config(text=f"{dir1_name} → {dir2_name}")
        if hasattr(self, 'traffic_card2_label'):
            self.traffic_card2_label.config(text=f"{dir2_name} → {dir1_name}")
        
        # Update logic direction labels
        if hasattr(self, 'traffic_logic_From_To'):
            self.traffic_logic_From_To.direction = f"{dir1_name} → {dir2_name}"
        if hasattr(self, 'traffic_logic_To_From'):
            self.traffic_logic_To_From.direction = f"{dir2_name} → {dir1_name}"

    def _add_traffic_estimation_panel(self, parent):
        """Add traffic estimation module panels for both directions."""
        from traffic_estimation_module import TrafficEstimationLogic

        # Get dynamic direction names
        dir1_name = self.dir1Name.get()
        dir2_name = self.dir2Name.get()
        
        # Initialize traffic estimation logic for both directions
        self.traffic_logic_From_To = TrafficEstimationLogic(direction=f"{dir1_name} → {dir2_name}")
        self.traffic_logic_To_From = TrafficEstimationLogic(direction=f"{dir2_name} → {dir1_name}")
        self.traffic_rows_From_To = []
        self.traffic_rows_To_From = []

        # Create Direction 1 card
        self._create_direction_traffic_card(
            parent, 
            f"{dir1_name} → {dir2_name}", 
            "From_To",
            self.traffic_logic_From_To,
            self.traffic_rows_From_To
        )

        # Create Direction 2 card
        self._create_direction_traffic_card(
            parent, 
            f"{dir2_name} → {dir1_name}", 
            "To_From",
            self.traffic_logic_To_From,
            self.traffic_rows_To_From
        )

    def _add_fiv_correction_panel(self, parent):
        """Add merged FIV Correction Coefficient Table panel with FROM on top and TO below."""
        # Create FIV panel frame
        fiv_panel_frame = ttk.LabelFrame(parent, text="속도경사보정계수 [ fiv ]", padding="10 10 10 10")
        fiv_panel_frame.pack(fill="x", padx=15, pady=10)
        
        # Control row with toggle button
        control_frame = ttk.Frame(fiv_panel_frame)
        control_frame.pack(fill="x", padx=5, pady=2)
        
        # Toggle button for FIV table visibility
        fiv_visible = tk.BooleanVar(value=False)
        toggle_btn = ttk.Button(
            control_frame,
            text="▶ Show FIV Table",
            command=lambda: self._toggle_fiv_table(fiv_visible, toggle_btn, fiv_table_frame)
        )
        toggle_btn.pack(side="left", padx=(0, 10))
        
        # Pollutant selector
        ttk.Label(control_frame, text="Pollutant:").pack(side="left", padx=(0, 5))
        pollutant_var = tk.StringVar(value="PM")
        
        # Define complete option mapping for all pollutants and vehicle types
        # Format: {pollutant: {display_label: (from_table_id, to_table_id)}}
        fiv_complete_map = {
            "PM": {
                "휘발유 승용차": ("(1.1-1)", "(1.2-1)"),
                "경유 승용차": ("(1.1-2)", "(1.2-2)"),
                "소형버스, 소형트럭": ("(1.1-3)", "(1.2-3)"),
                "대형버스, 중형, 대형, 특수트럭": ("(1.1-4)", "(1.2-4)"),
            },
            "CO": {
                "휘발유 승용차": ("(2.1-1)", "(2.2-1)"),
                "경유 승용차": ("(2.1-2)", "(2.2-2)"),
                "소형버스, 소형트럭": ("(2.1-3)", "(2.2-3)"),
                "대형버스, 중형, 대형, 특수트럭": ("(2.1-4)", "(2.2-4)"),
            },
            "NOx": {
                "휘발유 승용차": ("(3.1-1)", "(3.2-1)"),
                "경유 승용차": ("(3.1-2)", "(3.2-2)"),
                "소형버스, 소형트럭": ("(3.1-3)", "(3.2-3)"),
                "대형버스, 중형, 대형, 특수트럭": ("(3.1-4)", "(3.2-4)"),
            }
        }
        
        pollutant_combo = ttk.Combobox(
            control_frame,
            textvariable=pollutant_var,
            values=["PM", "CO", "NOx"],
            state="readonly",
            width=10,
        )
        pollutant_combo.pack(side="left", padx=(0, 15))
        
        # FIV option selector
        ttk.Label(control_frame, text="Vehicle Type:").pack(side="left", padx=(0, 5))
        fiv_option_var = tk.StringVar(value="휘발유 승용차")
        fiv_option_combo = ttk.Combobox(
            control_frame,
            textvariable=fiv_option_var,
            values=list(fiv_complete_map["PM"].keys()),
            state="readonly",
            width=40,
        )
        fiv_option_combo.pack(side="left", padx=(0, 10))
        
        # Internal variables for pollutant and table selection
        from_table_var = tk.StringVar(value="(1.1-1)")
        to_table_var = tk.StringVar(value="(1.2-1)")
        
        # Collapsible FIV table frame
        fiv_table_frame = ttk.Frame(fiv_panel_frame)
        # Don't pack initially (hidden by default)
        
        speed_columns = ["10", "20", "30", "40", "50", "60", "70", "80"]
        
        # ===== FROM Table (Top) =====
        # Header row
        ttk.Label(fiv_table_frame, text="구분(km/h)", font=("Arial", 9, "bold"), 
                 borderwidth=1, relief="solid", padding=5, background="#e0e0e0").grid(
                     row=0, column=0, columnspan=2, sticky="nsew")
        
        # Speed headers
        for col, speed in enumerate(speed_columns, start=2):
            ttk.Label(fiv_table_frame, text=speed, font=("Arial", 9, "bold"), 
                     borderwidth=1, relief="solid", padding=5, background="#e0e0e0").grid(
                         row=0, column=col, sticky="nsew")
        
        # FROM direction label (merged for 10 rows)
        from_location = "FROM"
        merged_from = ttk.Label(fiv_table_frame, text=from_location, font=("Arial", 9), 
                               borderwidth=1, relief="solid", padding=5, background="#f0f0f0")
        merged_from.grid(row=1, column=0, rowspan=10, sticky="nsew")
        
        # FROM section rows with section labels in column 1
        section_list = ["1구간", "2구간", "3구간", "4구간", "5구간", "6구간", "7구간", "8구간", "9구간", "10구간"]
        self.fiv_from_data_cells = {}
        
        for row_idx, section in enumerate(section_list, start=1):
            # Section column
            section_label = ttk.Label(fiv_table_frame, text=section, font=("Arial", 9), 
                                      borderwidth=1, relief="solid", padding=5, background="#f9f9f9")
            section_label.grid(row=row_idx, column=1, sticky="nsew")
            
            # Data cells for speeds
            for col in range(2, len(speed_columns) + 2):
                cell = ttk.Label(fiv_table_frame, text="0.500", borderwidth=1, 
                               relief="solid", padding=5, background="white")
                cell.grid(row=row_idx, column=col, sticky="nsew")
                self.fiv_from_data_cells[(row_idx, col)] = cell
        
        # Separator row
        separator = ttk.Separator(fiv_table_frame, orient="horizontal")
        separator.grid(row=11, column=0, columnspan=10, sticky="ew", pady=5)
        
        # ===== TO Table (Bottom) =====
        # Header row for TO table
        ttk.Label(fiv_table_frame, text="구분(km/h)", font=("Arial", 9, "bold"), 
                 borderwidth=1, relief="solid", padding=5, background="#e0e0e0").grid(
                     row=12, column=0, columnspan=2, sticky="nsew")
        
        # Speed headers for TO
        for col, speed in enumerate(speed_columns, start=2):
            ttk.Label(fiv_table_frame, text=speed, font=("Arial", 9, "bold"), 
                     borderwidth=1, relief="solid", padding=5, background="#e0e0e0").grid(
                         row=12, column=col, sticky="nsew")
        
        # TO direction label (merged for 10 rows)
        to_location = "TO"
        merged_to = ttk.Label(fiv_table_frame, text=to_location, font=("Arial", 9), 
                             borderwidth=1, relief="solid", padding=5, background="#f0f0f0")
        merged_to.grid(row=13, column=0, rowspan=10, sticky="nsew")
        
        # TO section rows with section labels in column 1
        self.fiv_to_data_cells = {}
        
        for row_offset, section in enumerate(section_list):
            row_num = 13 + row_offset
            # Section column
            section_label = ttk.Label(fiv_table_frame, text=section, font=("Arial", 9), 
                                      borderwidth=1, relief="solid", padding=5, background="#f9f9f9")
            section_label.grid(row=row_num, column=1, sticky="nsew")
            
            # Data cells for speeds
            for col in range(2, len(speed_columns) + 2):
                cell = ttk.Label(fiv_table_frame, text="0.500", borderwidth=1, 
                               relief="solid", padding=5, background="white")
                cell.grid(row=row_num, column=col, sticky="nsew")
                self.fiv_to_data_cells[(row_num, col)] = cell
        
        # Callbacks to update direction labels
        def update_from_label(*args):
            try:
                if hasattr(self, 'dir1Name'):
                    merged_from.config(text=self.dir1Name.get())
            except:
                pass
        
        def update_to_label(*args):
            try:
                if hasattr(self, 'dir2Name'):
                    merged_to.config(text=self.dir2Name.get())
            except:
                pass
        
        # Callback to update vehicle type options when pollutant changes
        def on_pollutant_changed(*args):
            """Update vehicle type options when pollutant is changed."""
            selected_pollutant = pollutant_var.get()
            vehicle_options = list(fiv_complete_map[selected_pollutant].keys())
            fiv_option_combo['values'] = vehicle_options
            fiv_option_var.set(vehicle_options[0])  # Set to first option
        
        # Callback to update table selection based on FIV option
        def on_fiv_option_changed(*args):
            """Update table IDs based on selected FIV option."""
            selected_option = fiv_option_var.get()
            selected_pollutant = pollutant_var.get()
            if selected_pollutant in fiv_complete_map and selected_option in fiv_complete_map[selected_pollutant]:
                from_table, to_table = fiv_complete_map[selected_pollutant][selected_option]
                from_table_var.set(from_table)
                to_table_var.set(to_table)
        
        # Register callbacks
        if hasattr(self, 'dir1Name'):
            self.dir1Name.trace_add("write", update_from_label)
        if hasattr(self, 'dir2Name'):
            self.dir2Name.trace_add("write", update_to_label)
        
        # Store references
        self.fiv_table_frame = fiv_table_frame
        self.fiv_visible = fiv_visible
        self.fiv_merged_from_label = merged_from
        self.fiv_merged_to_label = merged_to
        self.fiv_option_var = fiv_option_var
        self.fiv_complete_map = fiv_complete_map
        self.fiv_pollutant_var = pollutant_var
        self.fiv_from_table_var = from_table_var
        self.fiv_to_table_var = to_table_var
        self.fiv_toggle_btn = toggle_btn
        self.fiv_option_combo = fiv_option_combo
        
        # Add callbacks for pollutant, FIV option and table selection changes
        pollutant_var.trace_add("write", on_pollutant_changed)
        fiv_option_var.trace_add("write", on_fiv_option_changed)
        from_table_var.trace_add("write", lambda *args: self._populate_fiv_tables())
        to_table_var.trace_add("write", lambda *args: self._populate_fiv_tables())

        # Load default data on initialization
        self._populate_fiv_tables()
    
    def _populate_fiv_tables(self):
        """Populate both FROM and TO FIV tables with data from JSON."""
        try:
            from speed_grade_tables import get_table_override
            
            # Get selected values
            pollutant = self.fiv_pollutant_var.get()
            from_table_id = self.fiv_from_table_var.get()
            to_table_id = self.fiv_to_table_var.get()
            
            # Get data for the pollutant
            data = get_table_override(pollutant)
            if not data:
                return
            
            # Speed columns in the FIV table
            speed_columns = [10, 20, 30, 40, 50, 60, 70, 80]
            segment_list = ["1구간", "2구간", "3구간", "4구간", "5구간", "6구간", "7구간", "8구간", "9구간", "10구간"]
            
            # Populate FROM table
            self._populate_single_fiv_table(
                data, from_table_id, speed_columns, segment_list,
                self.fiv_from_data_cells, is_from=True
            )
            
            # Populate TO table
            self._populate_single_fiv_table(
                data, to_table_id, speed_columns, segment_list,
                self.fiv_to_data_cells, is_from=False
            )
        except Exception as e:
            print(f"Error populating FIV tables: {e}")
    
    def _populate_single_fiv_table(self, data, table_id, speed_columns, segment_list, data_cells, is_from=True):
        """Populate a single FIV table (FROM or TO) with data from JSON."""
        try:
            # Find the matching segment table in JSON
            segment_tables = data.get("segment_speed_grade_tables", [])
            selected_table = None
            
            for table in segment_tables:
                if table.get("table_id") == table_id:
                    selected_table = table
                    break
            
            if not selected_table:
                return
            
            # Get rows from the table
            rows = selected_table.get("rows", [])
            
            # Create a mapping of segment to row data for easier lookup
            segment_data_map = {}
            for row in rows:
                segment = row.get("segment", "")
                segment_data_map[segment] = row
            
            # Determine row offset based on table type
            row_offset = 0 if is_from else 12  # FROM starts at row 1, TO starts at row 13
            
            # Populate cells for each segment and speed
            for seg_idx, segment in enumerate(segment_list, start=1):
                if segment not in segment_data_map:
                    continue
                
                row_data = segment_data_map[segment]
                values = row_data.get("values", {})
                
                # Calculate actual row number for the grid
                actual_row = row_offset + seg_idx
                
                # For each speed column
                for col_idx, speed in enumerate(speed_columns, start=2):
                    # Get the value from JSON
                    value = values.get(str(speed), "0.500")
                    
                    # Format the value
                    if isinstance(value, (int, float)):
                        value_str = f"{value:.3f}"
                    else:
                        value_str = str(value)
                    
                    # Update the cell in the grid
                    cell_key = (actual_row, col_idx)
                    if cell_key in data_cells:
                        data_cells[cell_key].config(text=value_str)
        except Exception as e:
            print(f"Error populating single FIV table: {e}")

    def _toggle_fiv_table(self, visible_var, toggle_btn, table_frame):
        """Toggle visibility of FIV correction table."""
        is_visible = visible_var.get()
        
        if is_visible:
            # Hide table
            table_frame.pack_forget()
            toggle_btn.config(text="▶ Show FIV Table")
            visible_var.set(False)
        else:
            # Show table
            table_frame.pack(fill="x", pady=5)
            toggle_btn.config(text="▼ Hide FIV Table")
            visible_var.set(True)
            # Populate table data here if needed
    
    def _create_direction_traffic_card(self, parent, direction_title, direction_key, traffic_logic, traffic_rows_list):
        """Create a traffic estimation card for a specific direction."""
        # Create card for traffic estimation
        traffic_card = ttk.Frame(parent, relief="raised", borderwidth=1, padding="10 10 10 10")
        traffic_card.pack(fill="x", padx=15, pady=10)

        # Header
        header = ttk.Frame(traffic_card)
        header.pack(fill="x", pady=(0, 10))
        
        # Main title
        ttk.Label(header, text="Estimated Traffic Volume", font=("Arial", 14, "bold")).pack(anchor="w")
        
        # Direction label (editable via parent variables)
        header_label = ttk.Label(header, text=f"{direction_title}", font=("Arial", 12))
        header_label.pack(anchor="w", pady=(2, 0))
        
        # Store reference to label for updates
        if direction_key == "From_To":
            self.traffic_card1_label = header_label
        else:
            self.traffic_card2_label = header_label

        # Input frame for AADT values
        input_frame = ttk.LabelFrame(traffic_card, text="AADT Input (Annual Average Daily Traffic)", padding="10 10 10 10")
        input_frame.pack(fill="x", pady=5)

        # Create scrollable frame for rows
        canvas = tk.Canvas(input_frame, height=200)
        scrollbar = ttk.Scrollbar(input_frame, orient="vertical", command=canvas.yview)
        traffic_rows_frame = ttk.Frame(canvas)

        traffic_rows_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=traffic_rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Store references based on direction
        if direction_key == "From_To":
            self.traffic_rows_frame_From_To = traffic_rows_frame
        else:
            self.traffic_rows_frame_To_From = traffic_rows_frame

        # Header row with column labels
        header_labels = ["Year", "Passenger Vehicles", "Bus Small", "Bus Large", "Truck Small", "Truck Medium", "Truck Large", "Truck Special", "Action"]
        for col, label in enumerate(header_labels):
            ttk.Label(traffic_rows_frame, text=label, font=("Arial", 9, "bold")).grid(row=0, column=col, padx=5, pady=5, sticky="w")

        # Add Row button
        add_row_btn_frame = ttk.Frame(traffic_card)
        add_row_btn_frame.pack(fill="x", pady=5)
        ttk.Button(add_row_btn_frame, text="+ Add Row", command=lambda: self._add_traffic_row(direction_key)).pack(side="left", padx=5)

        # Add first row by default
        self._add_traffic_row(direction_key)

        # Buttons frame
        button_frame = ttk.Frame(traffic_card)
        button_frame.pack(fill="x", pady=5)

        ttk.Button(button_frame, text="Import CSV", command=lambda: self._import_traffic_csv(direction_key)).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Compute All", command=lambda: self._compute_all_traffic(direction_key)).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Export CSV", command=lambda: self._export_traffic_csv(direction_key)).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Export PDF", command=lambda: self._export_traffic_pdf(direction_key)).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Clear All", command=lambda: self._clear_traffic(direction_key)).pack(side="left", padx=5)

        # Traffic Density Table (collapsible)
        density_frame = ttk.Frame(traffic_card)
        density_frame.pack(fill="x", pady=5)
        
        # Control row with toggle button and road type selector
        density_control_frame = ttk.Frame(density_frame)
        density_control_frame.pack(fill="x", padx=5, pady=2)
        
        # Toggle button for density table
        density_visible = tk.BooleanVar(value=False)
        toggle_btn = ttk.Button(
            density_control_frame, 
            text="▶ Show Traffic Density Table",
            command=lambda: self._toggle_density_table(direction_key, density_visible, toggle_btn, density_table_frame)
        )
        toggle_btn.pack(side="left", padx=(0, 10))
        
        # Road Type selector next to toggle button
        ttk.Label(density_control_frame, text="Road Type:").pack(side="left", padx=(0, 5))
        road_type_var = self.roadTypeFromToTo if direction_key == "From_To" else self.roadTypeToToFrom
        road_type_combo = ttk.Combobox(
            density_control_frame,
            textvariable=road_type_var,
            values=["1 - National/Expressway (K=150)", "2 - Downtown (K=165)"],
            state="readonly",
            width=25,
        )
        road_type_combo.pack(side="left")
        
        # Trace road type changes to auto-update table if visible
        def on_road_type_change(*args):
            if density_visible.get():
                self._populate_density_table(direction_key)
        road_type_var.trace_add("write", on_road_type_change)
        
        # Collapsible density table frame
        density_table_frame = ttk.Frame(density_frame)
        # Don't pack initially (hidden by default)
        
        # Create table with headers
        headers = ["Speed\n(km/h)", "Traffic Volume\n(PCU/km·lane)", "K_lim-1"]
        for col, header in enumerate(headers):
            ttk.Label(density_table_frame, text=header, font=("Arial", 9, "bold"), borderwidth=1, relief="solid", padding=5).grid(row=0, column=col, sticky="nsew")
        
        # Store reference to populate later
        if direction_key == "From_To":
            self.density_table_frame_From_To = density_table_frame
            self.density_visible_From_To = density_visible
        else:
            self.density_table_frame_To_From = density_table_frame
            self.density_visible_To_From = density_visible

        # Results frame
        results_frame = ttk.LabelFrame(traffic_card, text="Traffic Estimation Results", padding="10 10 10 10")
        results_frame.pack(fill="both", expand=True, pady=5)

        # Results text widget with scroll only when container is full
        result_scroll = ttk.Scrollbar(results_frame)
        result_scroll.pack(side="right", fill="y")

        traffic_result_text = tk.Text(results_frame, wrap="word", height=10, font=("Courier New", 9))
        traffic_result_text.pack(side="left", fill="both", expand=True)
        
        # Custom scroll command that disables scrollbar when content fits
        def custom_yscrollcommand(*args):
            try:
                result_scroll.set(*args)
                # Disable scrollbar buttons if all content is visible (container not full)
                if len(args) >= 2 and args[0] == 0.0 and args[1] == 1.0:
                    # Content fits - disable scrollbar
                    result_scroll.pack_forget()
                else:
                    # Content exceeds - show scrollbar
                    if not result_scroll.winfo_ismapped():
                        result_scroll.pack(side="right", fill="y")
            except:
                pass
        
        traffic_result_text.config(yscrollcommand=custom_yscrollcommand)
        result_scroll.config(command=traffic_result_text.yview)

        # Store text widget reference
        if direction_key == "From_To":
            self.traffic_result_text_From_To = traffic_result_text
        else:
            self.traffic_result_text_To_From = traffic_result_text

    def _toggle_density_table(self, direction_key, visible_var, toggle_btn, table_frame):
        """Toggle visibility of traffic density table."""
        is_visible = visible_var.get()
        
        if is_visible:
            # Hide table
            table_frame.pack_forget()
            toggle_btn.config(text="▶ Show Traffic Density Table")
            visible_var.set(False)
        else:
            # Show and populate table
            table_frame.pack(fill="x", pady=5)
            toggle_btn.config(text="▼ Hide Traffic Density Table")
            visible_var.set(True)
            self._populate_density_table(direction_key)

    def _populate_density_table(self, direction_key):
        """Populate the traffic density table with current parameters."""
        from vent_functions import build_traffic_density_table
        
        # Get table frame
        if direction_key == "From_To":
            table_frame = self.density_table_frame_From_To
            design_speed = int(self.designSpeedFromToTo.get())
        else:
            table_frame = self.density_table_frame_To_From
            design_speed = int(self.designSpeedToToFrom.get())
        
        # Get current parameters from volume summary
        volume_summary = self.get_volume_summary(direction="FromToTo" if direction_key == "From_To" else "ToToFrom")
        Imax = volume_summary.get("cap_per_lane", 2000)
        
        # Get road_type from user selection (extract integer from string like "1 - National/...")
        if direction_key == "From_To":
            road_type_str = str(self.roadTypeFromToTo.get())
        else:
            road_type_str = str(self.roadTypeToToFrom.get())
        
        # Parse the integer from the string (handle both "1" and "1 - National/...")
        try:
            road_type = int(road_type_str.split()[0]) if ' ' in road_type_str else int(road_type_str)
        except (ValueError, AttributeError):
            road_type = 1  # Default to National/Expressway
        
        # Build density table
        density_rows = build_traffic_density_table(Imax, road_type)
        
        # Clear existing data rows (keep header row 0)
        for widget in table_frame.grid_slaves():
            row = widget.grid_info().get('row', 0)
            if row > 0:
                widget.destroy()
        
        # Populate data rows
        for idx, row_data in enumerate(density_rows, start=1):
            ttk.Label(table_frame, text=f"{row_data.speed_kmh:.0f}", borderwidth=1, relief="solid", padding=5).grid(row=idx, column=0, sticky="nsew")
            ttk.Label(table_frame, text=f"{row_data.flow_pcu_per_hr_lane}", borderwidth=1, relief="solid", padding=5).grid(row=idx, column=1, sticky="nsew")
            ttk.Label(table_frame, text=f"{row_data.k_lim1:.3f}", borderwidth=1, relief="solid", padding=5).grid(row=idx, column=2, sticky="nsew")

    def _add_traffic_row(self, direction_key):
        """Add a new row for traffic input."""
        rows_frame = self.traffic_rows_frame_From_To if direction_key == "From_To" else self.traffic_rows_frame_To_From
        rows_list = self.traffic_rows_From_To if direction_key == "From_To" else self.traffic_rows_To_From
        
        row_num = len(rows_list) + 1
        
        # Create variables for this row
        # Use StringVar for all row fields so they can be blank while editing
        row_vars = {
            'year': tk.StringVar(value="2024"),
            'passenger_vehicles': tk.StringVar(value="0.0"),
            'bus_small': tk.StringVar(value="0.0"),
            'bus_large': tk.StringVar(value="0.0"),
            'truck_small': tk.StringVar(value="0.0"),
            'truck_medium': tk.StringVar(value="0.0"),
            'truck_large': tk.StringVar(value="0.0"),
            'truck_special': tk.StringVar(value="0.0"),
        }
        
        # Create entries
        entries = []
        vcmd_int = (self.register(NumericValidator.validate_numeric), '%S', '%d')
        
        entry_year = ttk.Entry(rows_frame, textvariable=row_vars['year'], width=8, validate="key", validatecommand=vcmd_int)
        entry_year.grid(row=row_num, column=0, padx=5, pady=2)
        entries.append(entry_year)
        
        entry_pv = ttk.Entry(rows_frame, textvariable=row_vars['passenger_vehicles'], width=10, validate="key", validatecommand=vcmd_int)
        entry_pv.grid(row=row_num, column=1, padx=5, pady=2)
        entries.append(entry_pv)
        
        entry_bs = ttk.Entry(rows_frame, textvariable=row_vars['bus_small'], width=10, validate="key", validatecommand=vcmd_int)
        entry_bs.grid(row=row_num, column=2, padx=5, pady=2)
        entries.append(entry_bs)
        
        entry_bl = ttk.Entry(rows_frame, textvariable=row_vars['bus_large'], width=10, validate="key", validatecommand=vcmd_int)
        entry_bl.grid(row=row_num, column=3, padx=5, pady=2)
        entries.append(entry_bl)
        
        entry_ts = ttk.Entry(rows_frame, textvariable=row_vars['truck_small'], width=10, validate="key", validatecommand=vcmd_int)
        entry_ts.grid(row=row_num, column=4, padx=5, pady=2)
        entries.append(entry_ts)
        
        entry_tm = ttk.Entry(rows_frame, textvariable=row_vars['truck_medium'], width=10, validate="key", validatecommand=vcmd_int)
        entry_tm.grid(row=row_num, column=5, padx=5, pady=2)
        entries.append(entry_tm)
        
        entry_tl = ttk.Entry(rows_frame, textvariable=row_vars['truck_large'], width=10, validate="key", validatecommand=vcmd_int)
        entry_tl.grid(row=row_num, column=6, padx=5, pady=2)
        entries.append(entry_tl)
        
        entry_tsp = ttk.Entry(rows_frame, textvariable=row_vars['truck_special'], width=10, validate="key", validatecommand=vcmd_int)
        entry_tsp.grid(row=row_num, column=7, padx=5, pady=2)
        entries.append(entry_tsp)
        
        # Bind paste functionality to all entries
        for entry in entries:
            entry.bind('<FocusIn>', NumericValidator.clear_on_focus)
            entry.bind('<FocusOut>', NumericValidator.default_to_zero_on_focusout)
            entry.bind('<Control-v>', lambda e, rv=row_vars, dk=direction_key: self._handle_paste(e, rv, dk))
            entry.bind('<Button-3>', lambda e, rv=row_vars, dk=direction_key: self._show_paste_menu(e, rv, dk))
        
        # Delete button
        delete_btn = ttk.Button(rows_frame, text="Delete", command=lambda: self._delete_traffic_row(row_num - 1, direction_key))
        delete_btn.grid(row=row_num, column=8, padx=5, pady=2)
        
        rows_list.append({'vars': row_vars, 'widgets': entries, 'delete_btn': delete_btn})
    
    def _handle_paste(self, event, row_vars, direction_key):
        """Handle paste event from clipboard (Ctrl+V)."""
        try:
            # Get clipboard content
            clipboard_text = self.clipboard_get()
            
            # Determine which field has focus
            focused_widget = event.widget
            field_keys = ['year', 'passenger_vehicles', 'bus_small', 'bus_large', 
                          'truck_small', 'truck_medium', 'truck_large', 'truck_special']
            
            # Find starting column based on focused widget
            start_col = 0
            for i, key in enumerate(field_keys):
                if str(row_vars[key]) in str(focused_widget.cget('textvariable')):
                    start_col = i
                    break
            
            # Parse clipboard data (try tab first, then comma)
            values = []
            if '\t' in clipboard_text:
                values = clipboard_text.strip().split('\t')
            elif ',' in clipboard_text:
                values = clipboard_text.strip().split(',')
            else:
                values = clipboard_text.strip().split()
            
            # Fill values starting from focused column
            for i, value in enumerate(values):
                col_index = start_col + i
                if col_index >= len(field_keys):
                    break
                
                try:
                    clean_value = value.strip().replace(',', '')
                    if col_index == 0:  # Year field
                        row_vars[field_keys[col_index]].set(int(clean_value))
                    else:  # Numeric fields
                        row_vars[field_keys[col_index]].set(float(clean_value))
                except (ValueError, tk.TclError):
                    continue
            
            return 'break'  # Prevent default paste behavior
        except tk.TclError:
            pass  # Clipboard empty or unavailable
        except Exception as e:
            messagebox.showerror("Paste Error", f"Error pasting data: {str(e)}")
        return 'break'
    
    def _show_paste_menu(self, event, row_vars, direction_key):
        """Show right-click context menu for paste."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Paste Row Data", command=lambda: self._handle_paste(event, row_vars, direction_key))
        menu.post(event.x_root, event.y_root)
    
    def _delete_traffic_row(self, index, direction_key):
        """Delete a traffic row."""
        rows_frame = self.traffic_rows_frame_From_To if direction_key == "From_To" else self.traffic_rows_frame_To_From
        rows_list = self.traffic_rows_From_To if direction_key == "From_To" else self.traffic_rows_To_From
        
        if len(rows_list) <= 1:
            messagebox.showwarning("Cannot Delete", "At least one row must remain.")
            return
        
        # Destroy widgets for this row
        for widget in rows_frame.grid_slaves(row=index + 1):
            widget.destroy()
        
        # Remove from list
        rows_list.pop(index)
        
        # Rebuild the grid to fix row numbers
        self._rebuild_traffic_grid(direction_key)
    
    def _rebuild_traffic_grid(self, direction_key):
        """Rebuild the traffic input grid after deletion."""
        rows_frame = self.traffic_rows_frame_From_To if direction_key == "From_To" else self.traffic_rows_frame_To_From
        rows_list = self.traffic_rows_From_To if direction_key == "From_To" else self.traffic_rows_To_From
        
        # Clear all widgets except header
        for widget in rows_frame.grid_slaves():
            row = widget.grid_info().get('row', 0)
            if row > 0:
                widget.destroy()
        
        # Recreate rows
        temp_rows = rows_list[:]
        rows_list.clear()
        
        vcmd_int = (self.register(NumericValidator.validate_numeric), '%S', '%d')
        for row_data in temp_rows:
            row_num = len(rows_list) + 1
            vars_dict = row_data['vars']
            
            ttk.Entry(rows_frame, textvariable=vars_dict['year'], width=8, validate="key", validatecommand=vcmd_int).grid(row=row_num, column=0, padx=5, pady=2)
            ttk.Entry(rows_frame, textvariable=vars_dict['passenger_vehicles'], width=10, validate="key", validatecommand=vcmd_int).grid(row=row_num, column=1, padx=5, pady=2)
            ttk.Entry(rows_frame, textvariable=vars_dict['bus_small'], width=10, validate="key", validatecommand=vcmd_int).grid(row=row_num, column=2, padx=5, pady=2)
            ttk.Entry(rows_frame, textvariable=vars_dict['bus_large'], width=10, validate="key", validatecommand=vcmd_int).grid(row=row_num, column=3, padx=5, pady=2)
            ttk.Entry(rows_frame, textvariable=vars_dict['truck_small'], width=10, validate="key", validatecommand=vcmd_int).grid(row=row_num, column=4, padx=5, pady=2)
            ttk.Entry(rows_frame, textvariable=vars_dict['truck_medium'], width=10, validate="key", validatecommand=vcmd_int).grid(row=row_num, column=5, padx=5, pady=2)
            ttk.Entry(rows_frame, textvariable=vars_dict['truck_large'], width=10, validate="key", validatecommand=vcmd_int).grid(row=row_num, column=6, padx=5, pady=2)
            ttk.Entry(rows_frame, textvariable=vars_dict['truck_special'], width=10, validate="key", validatecommand=vcmd_int).grid(row=row_num, column=7, padx=5, pady=2)
            
            delete_btn = ttk.Button(rows_frame, text="Delete", command=lambda idx=len(rows_list): self._delete_traffic_row(idx, direction_key))
            delete_btn.grid(row=row_num, column=8, padx=5, pady=2)
            
            rows_list.append({'vars': vars_dict, 'widgets': [], 'delete_btn': delete_btn})

    def _import_traffic_csv(self, direction_key):
        """Import traffic data from CSV."""
        traffic_logic = self.traffic_logic_From_To if direction_key == "From_To" else self.traffic_logic_To_From
        
        filename = filedialog.askopenfilename(
            title="Import Traffic CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                csv_text = f.read()
            traffic_logic.import_csv_data(csv_text)
            self._display_traffic_results(direction_key)
            messagebox.showinfo("Success", f"Imported {len(traffic_logic.batch)} traffic records")
        except Exception as e:
            messagebox.showerror("Import Error", str(e))

    def _compute_all_traffic(self, direction_key):
        """Compute traffic estimation for all rows."""
        traffic_logic = self.traffic_logic_From_To if direction_key == "From_To" else self.traffic_logic_To_From
        rows_list = self.traffic_rows_From_To if direction_key == "From_To" else self.traffic_rows_To_From
        
        # Validate all input fields have numeric values before computing
        invalid_fields = []
        for idx, row_data in enumerate(rows_list, start=1):
            vars_dict = row_data['vars']
            for field_name, var in vars_dict.items():
                value_str = "<error>"  # Default if we can't get the value
                try:
                    value_str = str(var.get()).strip()
                    # Treat empty as invalid to prevent compute errors
                    if value_str == "":
                        invalid_fields.append(f"Row {idx}: {field_name} is blank")
                        continue
                    # Try to convert to appropriate type (int for year, float for others)
                    if field_name == 'year':
                        int(value_str)
                    else:
                        float(value_str)
                except (ValueError, AttributeError, TypeError):
                    invalid_fields.append(f"Row {idx}: {field_name} = '{value_str}'")
        
        if invalid_fields:
            error_msg = "Found non-numeric values in traffic data:\n\n" + "\n".join(invalid_fields[:10])
            if len(invalid_fields) > 10:
                error_msg += f"\n... and {len(invalid_fields) - 10} more invalid fields"
            error_msg += "\n\nPlease remove alphabetic or special characters from numeric fields."
            messagebox.showerror("Invalid Input", error_msg)
            return
        
        try:
            # Clear previous batch
            traffic_logic.clear_batch()
            
            # Get tunnel parameters from jet fan tab for pressure calculations
            Qtreq = Ar = Lr = Dr = rho = xi = lamb = Ae = Vt = lanes = 0
            V_kmh = 10.0
            if self.jet_fan_tab:
                try:
                    Qtreq = float(self.jet_fan_tab.qtreq_dir1_var.get() if direction_key == "From_To" else self.jet_fan_tab.qtreq_dir2_var.get())
                    Ar = float(self.jet_fan_tab.ar_dir1_var.get() if direction_key == "From_To" else self.jet_fan_tab.ar_dir2_var.get())
                    Lr = float(self.jet_fan_tab.lr_dir1_var.get() if direction_key == "From_To" else self.jet_fan_tab.lr_dir2_var.get())
                    Dr = float(self.jet_fan_tab.dr_dir1_var.get() if direction_key == "From_To" else self.jet_fan_tab.dr_dir2_var.get())
                    rho = float(self.jet_fan_tab.rho_var.get())
                    xi = float(self.jet_fan_tab.xi_var.get())
                    lamb = float(self.jet_fan_tab.lamb_var.get())
                    Ae = float(self.jet_fan_tab.ae_var.get())
                    lanes = int(self.jet_fan_tab.lanes_dir1_var.get() if direction_key == "From_To" else self.jet_fan_tab.lanes_dir2_var.get())
                    V_kmh = float(self.jet_fan_tab.v_kmh_var.get())
                    from vent_functions import Vt_MAP
                    Vt = Vt_MAP.get(int(V_kmh), Vt_MAP.get(10))
                except Exception:
                    Vt = 0.0
            
            for row_data in rows_list:
                vars_dict = row_data['vars']
                year = int(vars_dict['year'].get())
                passenger_vehicles = float(vars_dict['passenger_vehicles'].get())
                bus_small = float(vars_dict['bus_small'].get())
                bus_large = float(vars_dict['bus_large'].get())
                truck_small = float(vars_dict['truck_small'].get())
                truck_medium = float(vars_dict['truck_medium'].get())
                truck_large = float(vars_dict['truck_large'].get())
                truck_special = float(vars_dict['truck_special'].get())
                
                # Calculate passenger split: 60% Gasoline, 40% Diesel
                passenger_gasoline = passenger_vehicles * 0.60
                passenger_diesel = passenger_vehicles * 0.40
                passenger_aadt = passenger_vehicles
                
                # Get vehicle/hr per lane from cache (if available from density table)
                vehicle_hr_lane = 0.0
                if hasattr(self, 'vehicle_hr_lane_cache'):
                    direction_cache = self.vehicle_hr_lane_cache.get(direction_key, {})
                    vehicle_hr_lane = direction_cache.get(int(V_kmh), 0.0)
                
                result = traffic_logic.add_manual_entry(
                    year=year,
                    passenger_aadt=passenger_aadt,
                    bus_small=bus_small,
                    bus_large=bus_large,
                    truck_small=truck_small,
                    truck_medium=truck_medium,
                    truck_large=truck_large,
                    truck_special=truck_special,
                    Qtreq=Qtreq,
                    Ar=Ar,
                    Lr=Lr,
                    Dr=Dr,
                    rho=rho,
                    xi=xi,
                    lamb=lamb,
                    Ae=Ae,
                    Vt=Vt,
                    lanes=lanes,
                    vehicle_hr_lane=vehicle_hr_lane,
                )
            
            self._display_traffic_results(direction_key)
            messagebox.showinfo("Success", f"Computed {len(rows_list)} traffic entries")
        except Exception as e:
            messagebox.showerror("Computation Error", str(e))

    def _export_traffic_csv(self, direction_key):
        """Export traffic data to CSV."""
        traffic_logic = self.traffic_logic_From_To if direction_key == "From_To" else self.traffic_logic_To_From
        
        if not traffic_logic.batch:
            messagebox.showwarning("No Data", "No traffic data to export")
            return
        filename = filedialog.asksaveasfilename(
            title="Export Traffic CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return
        try:
            csv_content = traffic_logic.export_csv()
            from traffic_data_io import save_csv_to_file
            save_csv_to_file(csv_content, filename)
            messagebox.showinfo("Success", f"Exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _export_traffic_pdf(self, direction_key):
        """Export traffic data to PDF (via HTML browser preview)."""
        traffic_logic = self.traffic_logic_From_To if direction_key == "From_To" else self.traffic_logic_To_From
        
        if not traffic_logic.batch:
            messagebox.showwarning("No Data", "No traffic data to export")
            return
        try:
            filename = traffic_logic.open_pdf_preview(title="Traffic Estimation Results")
            messagebox.showinfo("Success", f"PDF preview opened: {filename}\nUse browser Print to save as PDF")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _clear_traffic(self, direction_key):
        """Clear all traffic estimation data."""
        traffic_logic = self.traffic_logic_From_To if direction_key == "From_To" else self.traffic_logic_To_From
        text_widget = self.traffic_result_text_From_To if direction_key == "From_To" else self.traffic_result_text_To_From
        rows_frame = self.traffic_rows_frame_From_To if direction_key == "From_To" else self.traffic_rows_frame_To_From
        rows_list = self.traffic_rows_From_To if direction_key == "From_To" else self.traffic_rows_To_From
        
        traffic_logic.clear_batch()
        text_widget.delete(1.0, "end")
        text_widget.insert("end", "Traffic data cleared.\n")
        
        # Clear all rows and add one fresh row
        for row_data in rows_list:
            for widget in rows_frame.grid_slaves():
                if widget.grid_info().get('row', 0) > 0:
                    widget.destroy()
        rows_list.clear()
        self._add_traffic_row(direction_key)

    def _display_traffic_results(self, direction_key):
        """Display traffic estimation results in the text widget."""
        traffic_logic = self.traffic_logic_From_To if direction_key == "From_To" else self.traffic_logic_To_From
        text_widget = self.traffic_result_text_From_To if direction_key == "From_To" else self.traffic_result_text_To_From
        
        text_widget.delete(1.0, "end")
        if not traffic_logic.batch:
            text_widget.insert("end", "No traffic data.\n")
            return

        text_widget.insert("end", "="*80 + "\n")
        text_widget.insert("end", "ESTIMATED TRAFFIC VOLUME RESULTS\n")
        text_widget.insert("end", "="*80 + "\n\n")

        for entry in traffic_logic.batch:
            if not entry.result:
                continue
            res = entry.result
            inp = entry.inputs

            # Helper for 4 significant figures
            def fmt_sig2(val):
                try:
                    return f"{float(val):.4g}"
                except Exception:
                    return str(val)

            # Determine road type for PCU/car mapping
            if direction_key == "From_To":
                road_type_str = str(self.roadTypeFromToTo.get()) if hasattr(self, "roadTypeFromToTo") else "1"
            else:
                road_type_str = str(self.roadTypeToToFrom.get()) if hasattr(self, "roadTypeToToFrom") else "1"
            try:
                road_type_val = int(road_type_str.split()[0])
            except (ValueError, AttributeError):
                road_type_val = 1

            # PCU/car mapping by road type
            pcu_per_car = {
                "gasoline": 1.0,
                "diesel": 1.0,
                "bus_small": 1.0,
                "bus_large": 1.5,
                "truck_small": 1.0,
                "truck_medium": 1.5,
                "truck_large": 1.5,
                "truck_special": 2.0, #if road_type_val == 1 else 1.9,
            }

            # Aggregate passenger mix percent (gasoline + diesel)
            passenger_mix = (
                res.mix_percents.get("passengerGasoline", 0) + res.mix_percents.get("passengerDiesel", 0)
            )

            text_widget.insert("end", f"Year: {entry.year}\n")
            text_widget.insert("end", f"Direction: {entry.direction}\n")
            text_widget.insert("end", "-"*60 + "\n")
            
            # Calculate gasoline and diesel split
            passenger_gasoline = inp.passenger_aadt * 0.60
            passenger_diesel = inp.passenger_aadt * 0.40
            
            # Get mix percentages for gasoline and diesel
            passenger_gasoline_mix = res.mix_percents.get("passengerGasoline", 0)
            passenger_diesel_mix = res.mix_percents.get("passengerDiesel", 0)
            
            # Calculate total AADT for AADT row
            total_aadt = int(passenger_gasoline) + int(passenger_diesel) + int(inp.bus_small) + int(inp.bus_large) + int(inp.truck_small) + int(inp.truck_medium) + int(inp.truck_large) + int(inp.truck_special)
            
            # Calculate total mix percentage (should be 100%)
            total_mix_percent = passenger_gasoline_mix + passenger_diesel_mix + res.mix_percents.get('busSmall', 0) + res.mix_percents.get('busLarge', 0) + res.mix_percents.get('truckSmall', 0) + res.mix_percents.get('truckMedium', 0) + res.mix_percents.get('truckLarge', 0) + res.mix_percents.get('truckSpecial', 0)
            total_mix_percent = min(100.0, total_mix_percent)
            
            # Table: Estimated Traffic Result(s)
            text_widget.insert("end", f"\nTable: Estimated Traffic Result(s) ({entry.year})\n\n")
            traffic_headers = [
                "",
                "GASOLINE",
                "DIESEL",
                "BUS SMALL",
                "BUS LARGE",
                "TRUCK SMALL",
                "TRUCK MEDIUM",
                "TRUCK LARGE",
                "TRUCK SPECIAL",
                "TOTAL",
                "HEAVY VEH MIX RATE (%)",
            ]
            traffic_col_widths = [12, 12, 12, 12, 12, 12, 12, 12, 14, 12, 18]
            
            def format_traffic_row(values):
                return " ".join(str(val).ljust(width) for val, width in zip(values, traffic_col_widths))
            
            text_widget.insert("end", format_traffic_row(traffic_headers) + "\n")
            text_widget.insert("end", format_traffic_row(["-" * (w - 1) for w in traffic_col_widths]) + "\n")
            
            # Traffic counts row
            traffic_data_row = [
                "AADT",
                f"{int(passenger_gasoline):,}",
                f"{int(passenger_diesel):,}",
                f"{int(inp.bus_small):,}",
                f"{int(inp.bus_large):,}",
                f"{int(inp.truck_small):,}",
                f"{int(inp.truck_medium):,}",
                f"{int(inp.truck_large):,}",
                f"{int(inp.truck_special):,}",
                f"{total_aadt:,}",
                f"{res.heavy_vehicle_mix_pt:.2f}%",
            ]
            text_widget.insert("end", format_traffic_row(traffic_data_row) + "\n")
            
            # Mix percentages row
            mix_percent_row = [
                "Mix Rate %",
                f"{passenger_gasoline_mix:.2f}",
                f"{passenger_diesel_mix:.2f}",
                f"{res.mix_percents.get('busSmall', 0):.2f}",
                f"{res.mix_percents.get('busLarge', 0):.2f}",
                f"{res.mix_percents.get('truckSmall', 0):.2f}",
                f"{res.mix_percents.get('truckMedium', 0):.2f}",
                f"{res.mix_percents.get('truckLarge', 0):.2f}",
                f"{res.mix_percents.get('truckSpecial', 0):.2f}",
                f"{round(total_mix_percent,2):.2f}",
                "",
            ]
            text_widget.insert("end", format_traffic_row(mix_percent_row) + "\n")
            
            # PCU/car row
            pcu_car_row = [
                "PCU/car",
                f"{pcu_per_car['gasoline']:.1f}",
                f"{pcu_per_car['diesel']:.1f}",
                f"{pcu_per_car['bus_small']:.1f}",
                f"{pcu_per_car['bus_large']:.1f}",
                f"{pcu_per_car['truck_small']:.1f}",
                f"{pcu_per_car['truck_medium']:.1f}",
                f"{pcu_per_car['truck_large']:.1f}",
                f"{pcu_per_car['truck_special']:.1f}",
                "",
                "",
            ]
            text_widget.insert("end", format_traffic_row(pcu_car_row) + "\n")
            
            # Mix*PCU/100 row
            mix_pcu_100_row = [
                "Mix*PCU",
                f"{(passenger_gasoline_mix * pcu_per_car['gasoline']):.4g}",
                f"{(passenger_diesel_mix * pcu_per_car['diesel'] / 100):.4g}",
                f"{(res.mix_percents.get('busSmall', 0) * pcu_per_car['bus_small']):.4g}",
                f"{(res.mix_percents.get('busLarge', 0) * pcu_per_car['bus_large'] ):.4g}",
                f"{(res.mix_percents.get('truckSmall', 0) * pcu_per_car['truck_small'] ):.4g}",
                f"{(res.mix_percents.get('truckMedium', 0) * pcu_per_car['truck_medium'] ):.4g}",
                f"{(res.mix_percents.get('truckLarge', 0) * pcu_per_car['truck_large'] ):.4g}",
                f"{(res.mix_percents.get('truckSpecial', 0) * pcu_per_car['truck_special'] ):.4g}",
                "",
                "",
            ]
            text_widget.insert("end", format_traffic_row(mix_pcu_100_row) + "\n\n")

            # Mix * PCU / 100 row (individual contributions) for PCU total calculation
            mix_pcu_row_values = {
                "gasoline": res.mix_percents.get('passengerGasoline', 0),
                "diesel": res.mix_percents.get('passengerDiesel', 0),
                "bus_small": res.mix_percents.get('busSmall', 0),
                "bus_large": res.mix_percents.get('busLarge', 0),
                "truck_small": res.mix_percents.get('truckSmall', 0),
                "truck_medium": res.mix_percents.get('truckMedium', 0),
                "truck_large": res.mix_percents.get('truckLarge', 0),
                "truck_special": res.mix_percents.get('truckSpecial', 0),
            }
            # Calculate individual Mix*PCU/100 values with 4 significant figures
            mix_pcu_values = {
                'gasoline': float(fmt_sig2(mix_pcu_row_values['gasoline'] * pcu_per_car['gasoline'] / 100)),
                'diesel': float(fmt_sig2(mix_pcu_row_values['diesel'] * pcu_per_car['diesel'] / 100)),
                'bus_small': float(fmt_sig2(mix_pcu_row_values['bus_small'] * pcu_per_car['bus_small'] / 100)),
                'bus_large': float(fmt_sig2(mix_pcu_row_values['bus_large'] * pcu_per_car['bus_large'] / 100)),
                'truck_small': float(fmt_sig2(mix_pcu_row_values['truck_small'] * pcu_per_car['truck_small'] / 100)),
                'truck_medium': float(fmt_sig2(mix_pcu_row_values['truck_medium'] * pcu_per_car['truck_medium'] / 100)),
                'truck_large': float(fmt_sig2(mix_pcu_row_values['truck_large'] * pcu_per_car['truck_large'] / 100)),
                'truck_special': float(fmt_sig2(mix_pcu_row_values['truck_special'] * pcu_per_car['truck_special'] / 100)),
            }
            
            # Calculate PCU(%)/Number of Units (%)
            pcu_weighted_total = (
                mix_pcu_values['gasoline'] +
                mix_pcu_values['diesel'] +
                mix_pcu_values['bus_small'] +
                mix_pcu_values['bus_large'] +
                mix_pcu_values['truck_small'] +
                mix_pcu_values['truck_medium'] +
                mix_pcu_values['truck_large'] +
                mix_pcu_values['truck_special']
            )
            
            text_widget.insert("end", f"PCU(%)/Units(%) = {math.ceil(pcu_weighted_total*10000)/10000:.4f}\n\n")

            # Generate Vehicles/km,lane table using traffic density data
            try:
                from vent_functions import build_traffic_density_table
                
                # Get traffic density table for this entry
                volume_summary = self.get_volume_summary(direction="FromToTo" if direction_key == "From_To" else "ToToFrom")
                Imax = volume_summary.get("cap_per_lane", 2000)
                
                # Build density table
                density_rows = build_traffic_density_table(Imax, K=K_val)
                
                # Display Vehicles/km,lane table
                text_widget.insert("end", "Table: Vehicles/km,lane Estimation\n\n")
                density_headers = [
                    "Speed (km/h)",
                    "Traffic Volume (PCU/km·lane)",
                    "Vehicles/km,lane",
                    "Vehicle/hr, lane",
                ]
                density_col_widths = [15, 30, 20, 20]
                
                def format_density_row(values):
                    return " ".join(str(val).ljust(width) for val, width in zip(values, density_col_widths))
                
                text_widget.insert("end", format_density_row(density_headers) + "\n")
                text_widget.insert("end", format_density_row(["-" * (w - 1) for w in density_col_widths]) + "\n")
                
                # Calculate vehicles/km,lane and Vehicle/hr, lane for each speed
                lanes = volume_summary.get("lanes", 1)
                # Reset cache for this direction on each render
                direction_cache = self.vehicle_hr_lane_cache.get(direction_key, {})
                direction_cache.clear()
                self.vehicle_hr_lane_cache[direction_key] = direction_cache
                for row_data in density_rows:
                    speed = f"{row_data.speed_kmh:.0f}"
                    traffic_vol = f"{row_data.flow_pcu_per_hr_lane}"
                    # Vehicles/km,lane = Traffic Volume / PCU(%)/Units(%)
                    if pcu_weighted_total > 0:
                        vehicles_km_lane = row_data.flow_pcu_per_hr_lane / pcu_weighted_total
                        vehicles_km_lane_str = f"{vehicles_km_lane:.2f}"  # 2 decimal places
                    else:
                        vehicles_km_lane = 0.0
                        vehicles_km_lane_str = "0.00"
                    # Vehicles/hr per lane = speed × vehicles/km,lane
                    vehicles_hr_lane = round(row_data.speed_kmh * vehicles_km_lane, 0)
                    vehicles_hr_lane_str = f"{vehicles_hr_lane:.0f}"

                    try:
                        direction_cache[int(row_data.speed_kmh)] = float(vehicles_hr_lane)
                        print(f"DEBUG: Cached Q for {direction_key} speed {int(row_data.speed_kmh)}: {vehicles_hr_lane}")
                    except Exception as e:
                        print(f"DEBUG: Failed to cache Q: {e}")
                    
                    density_data_row = [
                        speed,
                        traffic_vol,
                        vehicles_km_lane_str,
                        vehicles_hr_lane_str,
                    ]
                    text_widget.insert("end", format_density_row(density_data_row) + "\n")
                
                text_widget.insert("end", "\n")
            except Exception as e:
                text_widget.insert("end", f"Error generating Vehicles/km,lane table: {str(e)}\n\n")


        # Force scroll to the top so first information is visible
        text_widget.yview_moveto(0.0)
        
        # Refresh Q values in Ventilation Capacity tables after cache is populated
        if hasattr(self, 'ventilation_capacity_tab') and self.ventilation_capacity_tab:
            self.ventilation_capacity_tab._refresh_q_values_in_tables(direction_key)



class DataCatalog(ttk.Frame):
    """Data Catalog tab with 표고 보정계수 [fh] table display."""
    def __init__(self, parent, volume_tab=None):
        super().__init__(parent)
        self.volume_tab = volume_tab
        self._build_layout()

    def _build_layout(self):
        pad = 10
        main_frame = ttk.Frame(self, padding="20 20 20 20")
        main_frame.pack(fill="both", expand=True)

        # Section: Emission by vehicle type (placeholder for context)
        ttk.Label(main_frame, text="Emission by vehicle type table (placeholder)", font=("Arial", 11, "bold"), background="#e0e0e0").pack(fill="x", pady=(0, pad))

        # --- 표고 보정계수 [fh] table (ALWAYS VISIBLE, between main tables) ---
        fh_frame = ttk.Frame(main_frame)
        fh_frame.pack(fill="x", pady=(0, pad))
        fh_title = ttk.Label(
            fh_frame,
            text="표고 보정계수 [fh]",
            font=("Arial", 11, "bold"),
            background="#e0e0e0",
            borderwidth=1,
            relief="solid",
            anchor="center",
            justify="center",
            padding=5,
        )
        fh_title.pack(fill="x", pady=(0, 0))
        fh_table = ttk.Frame(fh_frame)
        fh_table.pack(fill="x", pady=(0, 0))
        headers = ["구분", "FROM→TO", "TO→FROM"]
        for col, header in enumerate(headers):
            ttk.Label(
                fh_table,
                text=header,
                font=("Arial", 9, "bold"),
                borderwidth=1,
                relief="solid",
                padding=5,
                background="#e0e0e0",
                anchor="center",
                justify="center",
            ).grid(row=0, column=col, sticky="nsew")
            fh_table.columnconfigure(col, weight=1, minsize=80)
        fh_data = [
            ["1구간", "1.00", "1.00"],
            ["2구간", "0.98", "1.02"],
            ["3구간", "0.96", "1.04"],
            ["4구간", "0.94", "1.06"],
            ["5구간", "0.92", "1.08"],
            ["6구간", "0.90", "1.10"],
            ["7구간", "0.88", "1.12"],
            ["8구간", "0.86", "1.14"],
            ["9구간", "0.84", "1.16"],
            ["10구간", "0.82", "1.18"],
        ]
        for r, row in enumerate(fh_data, start=1):
            for c, val in enumerate(row):
                ttk.Label(
                    fh_table,
                    text=val,
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background="#ffffff" if r % 2 == 1 else "#f9f9f9",
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r, column=c, sticky="nsew")


class TableViewer:
    """Placeholder for Table Viewer class."""
    pass


class VentilationVolumeWindow(tk.Toplevel):
    """Window implementing the 'Calculate Ventilation Volume' placeholder layout."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Calculate Ventilation Volume")
        self.geometry("900x600")

        # Translation-like dict
        t = {
            "dir1Title": "From → To",
            "dir2Title": "To → From",
            "numberOfSectionsLabel": "Number of sections",
            "averageElevationLabel": "Average elevation",
        }

        # State variables
        self.sectionCountFromToTo = tk.IntVar(value=10)
        self.sectionCountToToFrom = tk.IntVar(value=10)
        self.avgElevationFromToTo = tk.DoubleVar(value=0.0)
        self.avgElevationToToFrom = tk.DoubleVar(value=0.0)
        # Ventilation design speeds (80/100/120)
        self.designSpeedFromToTo = tk.IntVar(value=80)
        self.designSpeedToToFrom = tk.IntVar(value=80)
        self.tunnelArFromToTo = tk.DoubleVar(value=0.0)
        self.tunnelLpFromToTo = tk.DoubleVar(value=0.0)
        self.tunnelArToToFrom = tk.DoubleVar(value=0.0)
        self.tunnelLpToToFrom = tk.DoubleVar(value=0.0)

        # Example data containers
        self.statsFromToTo = {"length_km": 0, "max_gradient": 0}
        self.statsToToFrom = {"length_km": 0, "max_gradient": 0}
        self.trafficFromToTo = {"AADT": 0, "trucks_pct": 0}
        self.trafficToToFrom = {"AADT": 0, "trucks_pct": 0}
        self.segmentsFromToTo = []
        self.segmentsToToFrom = []

        def handleSectionCountChange(direction, value):
            try:
                v = int(value)
            except ValueError:
                return
            v = max(1, min(50, v))
            if direction == "FromToTo":
                self.sectionCountFromToTo.set(v)
            elif direction == "ToToFrom":
                self.sectionCountToToFrom.set(v)

        # Geometry callbacks (placeholders)
        def onArChangeFrom(val):
            pass
        def onLpChangeFrom(val):
            pass
        def onArChangeTo(val):
            pass
        def onLpChangeTo(val):
            pass

        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        card_padding = {"padx": 10, "pady": 10}

        # Direction 1 card
        card1 = ttk.Frame(main_frame, relief="raised", borderwidth=1)
        card1.pack(fill="x", **card_padding)
        header1 = ttk.Frame(card1)
        header1.pack(fill="x", pady=(0, 8))
        ttk.Label(header1, text=t["dir1Title"], font=("Arial", 14, "bold")).pack(side="left")
        controls1 = ttk.Frame(header1)
        controls1.pack(side="right")
        sections_group1 = ttk.Frame(controls1)
        sections_group1.pack(side="left", padx=8)
        ttk.Label(sections_group1, text=t["numberOfSectionsLabel"] + ":").pack(side="left")
        tk.Spinbox(
            sections_group1,
            from_=1,
            to=50,
            textvariable=self.sectionCountFromToTo,
            width=5,
            command=lambda: handleSectionCountChange("FromToTo", self.sectionCountFromToTo.get()),
        ).pack(side="left")
        elevation_group1 = ttk.Frame(controls1)
        elevation_group1.pack(side="left", padx=8)
        ttk.Label(elevation_group1, text=t["averageElevationLabel"] + ":").pack(side="left")
        ttk.Entry(elevation_group1, textvariable=self.avgElevationFromToTo, width=10).pack(side="left")

        # Ventilation Design Speed (80/100/120)
        speed_group1 = ttk.Frame(controls1)
        speed_group1.pack(side="left", padx=8)
        ttk.Label(speed_group1, text="Ventilation Design Speed:").pack(side="left")
        ttk.Combobox(
            speed_group1,
            textvariable=self.designSpeedFromToTo,
            values=[80, 100, 120],
            state="readonly",
            width=6,
        ).pack(side="left")
        SegmentsTableTransposed(card1, "FromToTo", self.segmentsFromToTo, None, t).pack(fill="x", pady=4)
        TunnelGeometry(
            card1,
            self.tunnelArFromToTo,
            self.tunnelLpFromToTo,
            self.sectionCountFromToTo,
            self.segmentsFromToTo,
            None,
            onArChangeFrom,
            onLpChangeFrom,
            t,
        ).pack(fill="x", pady=4)
        SummaryRow(card1, self.statsFromToTo, self.trafficFromToTo, t).pack(fill="x", pady=4)

        # Direction 2 card
        card2 = ttk.Frame(main_frame, relief="raised", borderwidth=1)
        card2.pack(fill="x", **card_padding)
        header2 = ttk.Frame(card2)
        header2.pack(fill="x", pady=(0, 8))
        ttk.Label(header2, text=t["dir2Title"], font=("Arial", 14, "bold")).pack(side="left")
        controls2 = ttk.Frame(header2)
        controls2.pack(side="right")
        sections_group2 = ttk.Frame(controls2)
        sections_group2.pack(side="left", padx=8)
        ttk.Label(sections_group2, text=t["numberOfSectionsLabel"] + ":").pack(side="left")
        tk.Spinbox(
            sections_group2,
            from_=1,
            to=50,
            textvariable=self.sectionCountToToFrom,
            width=5,
            command=lambda: handleSectionCountChange("ToToFrom", self.sectionCountToToFrom.get()),
        ).pack(side="left")
        elevation_group2 = ttk.Frame(controls2)
        elevation_group2.pack(side="left", padx=8)
        ttk.Label(elevation_group2, text=t["averageElevationLabel"] + ":").pack(side="left")
        ttk.Entry(elevation_group2, textvariable=self.avgElevationToToFrom, width=10).pack(side="left")

        # Ventilation Design Speed (80/100/120)
        speed_group2 = ttk.Frame(controls2)
        speed_group2.pack(side="left", padx=8)
        ttk.Label(speed_group2, text="Ventilation Design Speed:").pack(side="left")
        ttk.Combobox(
            speed_group2,
            textvariable=self.designSpeedToToFrom,
            values=[80, 100, 120],
            state="readonly",
            width=6,
        ).pack(side="left")
        SegmentsTableTransposed(card2, "ToToFrom", self.segmentsToToFrom, None, t).pack(fill="x", pady=4)
        TunnelGeometry(
            card2,
            self.tunnelArToToFrom,
            self.tunnelLpToToFrom,
            self.sectionCountToToFrom,
            self.segmentsToToFrom,
            None,
            onArChangeTo,
            onLpChangeTo,
            t,
        ).pack(fill="x", pady=4)
        SummaryRow(card2, self.statsToToFrom, self.trafficToToFrom, t).pack(fill="x", pady=4)

        # Pack main frame
        main_frame.pack(fill="both", expand=True)


if __name__ == "__main__":
    # Load JSON data from Data folder into speed_grade_tables
    data_folder = Path(__file__).parent / "Data"
    
    # Load PM, CO, NOx JSON files
    json_files = {
        "PM": data_folder / "pmSpeedGradeFiv.json",
        "CO": data_folder / "coSpeedGradeFiv.json",
        "NOx": data_folder / "noxSpeedGradeFiv.json"
    }
    
    for pollutant, file_path in json_files.items():
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    set_table_override(pollutant, data)
                    print(f"Loaded {pollutant} data from {file_path.name}")
            except Exception as e:
                print(f"Error loading {pollutant} data: {e}")
        else:
            print(f"Warning: {file_path.name} not found")
    
    root = tk.Tk()
    root.title("Jet Fan Calculator")
    root.geometry("1000x800")
    
    # Create a button frame at the top
    button_frame = ttk.Frame(root)
    button_frame.pack(fill="x", padx=10, pady=10)
    
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    # Create result tab first
    result_tab = ResultsTab(notebook)
    
    # Add Ventilation Volume tab first
    ventilation_volume_tab = VentilationVolumeTab(notebook)
    notebook.add(ventilation_volume_tab, text="Calculate Ventilation")
    result_tab.volume_tab = ventilation_volume_tab

    # Second tab: Number of Jet Fan (pass result_tab and volume_tab references)
    jet_fan_tab = JetFanTab(notebook, result_tab=result_tab, volume_tab=ventilation_volume_tab)
    notebook.add(jet_fan_tab, text="Number of Jet Fan")
    
    # Store jet_fan_tab reference in ventilation_volume_tab for pressure calculations
    ventilation_volume_tab.jet_fan_tab = jet_fan_tab

    # Results tab
    notebook.add(result_tab, text="Results (summary)")
    
    # Ventilation Capacity tab
    ventilation_capacity_tab = VentilationCapacityTab(notebook, jet_fan_tab=jet_fan_tab, volume_tab=ventilation_volume_tab)
    notebook.add(ventilation_capacity_tab, text="Ventilation Capacity")
    
    # Store reference in volume_tab so it can refresh capacity tab when traffic estimation runs
    ventilation_volume_tab.ventilation_capacity_tab = ventilation_capacity_tab
    
    # Add tab change event handler to check traffic volume estimation for Ventilation Capacity tab
    def on_notebook_tab_change(event=None):
        """Check if user is trying to access Ventilation Capacity tab before traffic estimation is done."""
        selected_tab = notebook.index(notebook.select())
        # Ventilation Capacity tab is at index 3 (0: Ventilation, 1: Jet Fan, 2: Results, 3: Capacity)
        if selected_tab == 3:
            # Check if traffic volume is estimated
            cache = ventilation_volume_tab.vehicle_hr_lane_cache if ventilation_volume_tab else {}
            has_from_to_data = bool(cache.get("From_To", {}))
            has_to_from_data = bool(cache.get("To_From", {}))
            
            if not (has_from_to_data or has_to_from_data):
                messagebox.showwarning(
                    "Traffic Estimation Required",
                    "Traffic Volume Estimation must be completed first!\n\n"
                    "Please:\n"
                    "1. Go to 'Calculate Ventilation' tab\n"
                    "2. Enter tunnel geometry and sections\n"
                    "3. Enter traffic data (AADT, trucks percentage)\n"
                    "4. Click 'Estimate Traffic Volume' button\n\n"
                    "After traffic estimation is complete, you can use the Ventilation Capacity tab."
                )
                # Switch back to Ventilation Volume tab
                notebook.select(0)
    
    notebook.bind("<<NotebookTabChanged>>", on_notebook_tab_change)
    
    # Add buttons to button frame
    def compute_summary():
        """Compute and display summary in results tab."""
        inp1, results1, inp2, results2 = jet_fan_tab.compute_and_publish()
        dir1_label = "FROM"
        dir2_label = "TO"
        try:
            dir1_label = ventilation_volume_tab.dir1Name.get()
            dir2_label = ventilation_volume_tab.dir2Name.get()
        except Exception:
            pass
        if inp1 and results1 and inp2 and results2:
            # Pass traffic logic data to display_results_dual
            result_tab.display_results_dual(
                dir1_label, dir2_label, 
                inp1, results1, inp2, results2,
                ventilation_volume_tab.traffic_logic_From_To,
                ventilation_volume_tab.traffic_logic_To_From
            )
        # Append Ventilation Volume summaries for both directions
        infos = [
            ventilation_volume_tab.get_volume_summary("FromToTo"),
            ventilation_volume_tab.get_volume_summary("ToToFrom"),
        ]
        result_tab.append_volume_summary(infos)
        # Note: Traffic summary is now integrated into display_results_dual
        # Switch to Results tab
        notebook.select(2)
    
    def show_data_catalog():
        """Show Data Catalog dialog with comprehensive pollutant table viewer."""
        from data_catalog import DataCatalog, DATA_OPTIONS
        from table_viewer import TableViewer
        from speed_grade_tables import get_all_overrides
        
        dialog = tk.Toplevel(root)
        dialog.title("Data Catalog - Pollutant Tables")
        dialog.geometry("1200x800")

        # Tabbed catalog; FIV tables live on their own tab
        catalog_notebook = ttk.Notebook(dialog)
        catalog_notebook.pack(fill="both", expand=True)

        fiv_tab = ttk.Frame(catalog_notebook)
        catalog_notebook.add(fiv_tab, text="Speed-Grade Correction Factor (fiv)")

        diesel_tab = ttk.Frame(catalog_notebook)
        catalog_notebook.add(diesel_tab, text="Standard application value of smoke emission")
        
        main_frame = ttk.Frame(fiv_tab, padding="10 10 10 10")
        main_frame.pack(fill="both", expand=True)

        # --- Diesel truck/bus qo* static table tab ---
        # Make diesel tab scrollable
        diesel_canvas = tk.Canvas(diesel_tab, bg="white")
        diesel_v_scrollbar = ttk.Scrollbar(diesel_tab, orient="vertical", command=diesel_canvas.yview)
        diesel_h_scrollbar = ttk.Scrollbar(diesel_tab, orient="horizontal", command=diesel_canvas.xview)
        diesel_canvas.configure(yscrollcommand=diesel_v_scrollbar.set, xscrollcommand=diesel_h_scrollbar.set)
        diesel_v_scrollbar.pack(side="right", fill="y")
        diesel_h_scrollbar.pack(side="bottom", fill="x")
        diesel_canvas.pack(side="left", fill="both", expand=True)

        diesel_scrollable_frame = ttk.Frame(diesel_canvas, padding="10 10 10 10")
        diesel_scrollable_frame.bind(
            "<Configure>",
            lambda e: diesel_canvas.configure(scrollregion=diesel_canvas.bbox("all"))
        )
        diesel_canvas.create_window((0, 0), window=diesel_scrollable_frame, anchor="nw")

        # Title row spanning all columns
        table_container = ttk.Frame(diesel_scrollable_frame)
        table_container.pack(anchor="center", pady=10)
        for col in range(6):
            table_container.columnconfigure(col, weight=1, minsize=100)  # Reduced width

        ttk.Label(
            table_container,
            text="Truck, Bus with diesel motors (m > 3.5 ton)",
            font=("Arial", 10, "bold"),
            borderwidth=1,
            relief="solid",
            padding=5,
            background="#e0e0e0",
            anchor="center",
            justify="center",
        ).grid(row=0, column=0, columnspan=6, sticky="nsew")

        # Multi-row header
        ttk.Label(
            table_container,
            text="Emission Law",
            font=("Arial", 9, "bold"),
            borderwidth=1,
            relief="solid",
            padding=5,
            background="#e0e0e0",
            anchor="center",
            justify="center",
        ).grid(row=1, column=0, rowspan=4, sticky="nsew")

        ttk.Label(
            table_container,
            text="Control",
            font=("Arial", 9, "bold"),
            borderwidth=1,
            relief="solid",
            padding=5,
            background="#e0e0e0",
            anchor="center",
            justify="center",
        ).grid(row=1, column=1, rowspan=4, sticky="nsew")

        ttk.Label(
            table_container,
            text="qo* (m3/h·veh)   V = 60 km/h",
            font=("Arial", 9, "bold"),
            borderwidth=1,
            relief="solid",
            padding=5,
            background="#e0e0e0",
            anchor="center",
            justify="center",
        ).grid(row=1, column=2, columnspan=4, sticky="nsew")

        ttk.Label(
            table_container,
            text="Truck weight (ton)",
            font=("Arial", 9, "bold"),
            borderwidth=1,
            relief="solid",
            padding=5,
            background="#e0e0e0",
            anchor="center",
            justify="center",
        ).grid(row=2, column=2, columnspan=4, sticky="nsew")

        for c_idx, speed in enumerate(["5", "10", "20", "40"], start=2):
            ttk.Label(
                table_container,
                text=speed,
                font=("Arial", 9, "bold"),
                borderwidth=1,
                relief="solid",
                padding=5,
                background="#e0e0e0",
                anchor="center",
                justify="center",
            ).grid(row=3, column=c_idx, sticky="nsew")

        for c_idx, rng in enumerate(["80-130", "160-250", "300-400", "400-600"], start=2):
            ttk.Label(
                table_container,
                text=rng,
                font=("Arial", 9, "bold"),
                borderwidth=1,
                relief="solid",
                padding=5,
                background="#f2f2f2",
                anchor="center",
                justify="center",
            ).grid(row=4, column=c_idx, sticky="nsew")

        rows = [
            ("한국 육성제 기준", "no", 72, 160, 235, 275),
            ("EEC R 49 + 24", "no", 80, 160, 240, 280),
            ("EEC R 49 + 24 EEC 88/77", "yes", 65, 155, 220, 240),
            ("US Transient 88", "yes", 50, 100, 150, 200),
            ("US Transient 91", "yes", 30, 60, 100, 140),
            ("US Transient 94", "yes", 20, 40, 70, 110),
        ]

        for r_idx, (law, control, v5, v10, v20, v40) in enumerate(rows, start=5):
            row_bg = "#ffffff" if (r_idx % 2 == 1) else "#f7f7f7"
            ttk.Label(
                table_container,
                text=law,
                borderwidth=1,
                relief="solid",
                padding=5,
                background=row_bg,
                anchor="w",
            ).grid(row=r_idx, column=0, sticky="nsew")
            ttk.Label(
                table_container,
                text=control,
                borderwidth=1,
                relief="solid",
                padding=5,
                background=row_bg,
                anchor="center",
            ).grid(row=r_idx, column=1, sticky="nsew")

            for c_idx, val in enumerate([v5, v10, v20, v40], start=2):
                ttk.Label(
                    table_container,
                    text=str(val),
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background=row_bg,
                    anchor="center",
                ).grid(row=r_idx, column=c_idx, sticky="nsew")
        
        # Spacer
        ttk.Label(diesel_scrollable_frame, text="").pack(pady=10)
        
        # Second table: Standard application value of emission by vehicle type (정확한 구조)
        table_container_2 = ttk.Frame(diesel_scrollable_frame)
        table_container_2.pack(fill="x", pady=10)
        for col in range(6):
            table_container_2.columnconfigure(col, weight=1, minsize=80)  # Reduced width

        # Precompute 기준배출량 values from the Standard Application table
        fuel_rows = ["휘발유", "경유"]
        other_classifications = [
            "소형버스",
            "소형트럭",
            "중형트럭",
            "대형버스",
            "대형트럭",
            "특수트럭",
            "합계/공차",
        ]
        total_rows = fuel_rows + other_classifications

        mid1 = ["", "", "", "", "111", "226", "250", "323.5", "75"]
        mid2 = ["0", "0.0045", "0.0045", "0.0045", "PS", "PS", "PS", "PS", "V (%) ="]
        mid3 = ["이하", "이하", "이하", "이하", "", "0.01", "[ g/kw*h ]", "이하", "41.3"]

        from decimal import Decimal, ROUND_HALF_UP

        def _safe_decimal(value):
            try:
                return Decimal(str(value))
            except Exception:
                return None

        v_percent = _safe_decimal(mid1[-1])
        speed_factor = _safe_decimal(mid3[-1])
        g_per_kwh = _safe_decimal(mid3[5])
        k_hp = Decimal("0.7355")
        k_base = Decimal("6.25")

        emissions = []
        for i in range(len(total_rows)):
            if i == len(total_rows) - 1:
                emissions.append("km/h")
                continue

            m2_val = _safe_decimal(mid2[i])
            if m2_val is not None and v_percent is not None and speed_factor is not None:
                val = k_base * m2_val * (v_percent / Decimal("100")) * speed_factor
                emissions.append(str(val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)))
                continue

            m1_val = _safe_decimal(mid1[i])
            if m1_val is not None and g_per_kwh is not None and v_percent is not None:
                val = k_base * g_per_kwh * m1_val * (v_percent / Decimal("100")) * k_hp
                emissions.append(str(val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)))
            else:
                emissions.append("ERR")
        # --- Table 3: 매연의 총배출량 Qs[m2/h] ---
        qs_table = ttk.Frame(diesel_scrollable_frame)
        qs_table.pack(fill="x", pady=(20, 20), anchor="center")

        qs_title = ttk.Label(
            qs_table,
            text="매연의 총배출량 Qs[m2/h]",
            font=("Arial", 11, "bold"),
            background="#e0e0e0",
            borderwidth=1,
            relief="solid",
            anchor="center",
            justify="center",
            padding=5,
        )
        qs_title.grid(row=0, column=0, columnspan=11, sticky="nsew")


        # --- Updated header to match specified structure and expand header/subheader rows ---
        header_font = ("Arial", 10, "bold")
        subheader_font = ("Arial", 9)
        header_pad = 6
        subheader_pad = 4
        # Row 0: Main categories (merged cells)
        ttk.Label(qs_table, text="진주", font=header_font, borderwidth=1, relief="solid", padding=header_pad, background="#e0e0e0", anchor="center").grid(row=1, column=0, sticky="nsew")
        ttk.Label(qs_table, text="구분", font=header_font, borderwidth=1, relief="solid", padding=header_pad, background="#e0e0e0", anchor="center").grid(row=1, column=1, rowspan=3, sticky="nsew")
        ttk.Label(qs_table, text="승용차", font=header_font, borderwidth=1, relief="solid", padding=header_pad, background="#e0e0e0", anchor="center").grid(row=1, column=2, columnspan=2, sticky="nsew")
        ttk.Label(qs_table, text="버스", font=header_font, borderwidth=1, relief="solid", padding=header_pad, background="#e0e0e0", anchor="center").grid(row=1, column=4, columnspan=2, sticky="nsew")
        ttk.Label(qs_table, text="트럭", font=header_font, borderwidth=1, relief="solid", padding=header_pad, background="#e0e0e0", anchor="center").grid(row=1, column=6, columnspan=4, sticky="nsew")
        ttk.Label(qs_table, text="합계", font=header_font, borderwidth=1, relief="solid", padding=header_pad, background="#e0e0e0", anchor="center").grid(row=1, column=10, rowspan=3, sticky="nsew")

        # Row 1: Subheaders (aligned under merged columns)
        # Subheader row: column 0 is '속도 (km/h)', column 1 is blank (for '구분' header above)
        ttk.Label(qs_table, text="속도 (km/h)", font=subheader_font, borderwidth=1, relief="solid", padding=subheader_pad, background="#f5f5f5", anchor="center").grid(row=2, column=0, rowspan=2, sticky="nsew")
        ttk.Label(qs_table, text="휘발유", font=subheader_font, borderwidth=1, relief="solid", padding=subheader_pad, background="#f5f5f5", anchor="center").grid(row=2, column=2, sticky="nsew")
        ttk.Label(qs_table, text="경유", font=subheader_font, borderwidth=1, relief="solid", padding=subheader_pad, background="#f5f5f5", anchor="center").grid(row=2, column=3, sticky="nsew")
        ttk.Label(qs_table, text="소형", font=subheader_font, borderwidth=1, relief="solid", padding=subheader_pad, background="#f5f5f5", anchor="center").grid(row=2, column=4, sticky="nsew")
        ttk.Label(qs_table, text="대형", font=subheader_font, borderwidth=1, relief="solid", padding=subheader_pad, background="#f5f5f5", anchor="center").grid(row=2, column=5, sticky="nsew")
        ttk.Label(qs_table, text="소형", font=subheader_font, borderwidth=1, relief="solid", padding=subheader_pad, background="#f5f5f5", anchor="center").grid(row=2, column=6, sticky="nsew")
        ttk.Label(qs_table, text="중형", font=subheader_font, borderwidth=1, relief="solid", padding=subheader_pad, background="#f5f5f5", anchor="center").grid(row=2, column=7, sticky="nsew")
        ttk.Label(qs_table, text="대형", font=subheader_font, borderwidth=1, relief="solid", padding=subheader_pad, background="#f5f5f5", anchor="center").grid(row=2, column=8, sticky="nsew")
        ttk.Label(qs_table, text="특수", font=subheader_font, borderwidth=1, relief="solid", padding=subheader_pad, background="#f5f5f5", anchor="center").grid(row=2, column=9, sticky="nsew")

        # Explicitly set row minsize for header and subheader rows
        qs_table.rowconfigure(0, minsize=32)
        qs_table.rowconfigure(1, minsize=40)
        qs_table.rowconfigure(2, minsize=30)
        qs_table.rowconfigure(3, minsize=26)
        

        # Column config - set minsize for each column only once
        wider_col_widths = [110, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90]
        for col in range(11):
            qs_table.columnconfigure(col, weight=1, minsize=wider_col_widths[col])

        # Row 2: Subheader values from 기준배출량 column
        qs_subheader_values = emissions[:8]
        qs_subheader_labels = []
        for idx, val in enumerate(qs_subheader_values, start=2):
            lbl = ttk.Label(
                qs_table,
                text=val,
                font=subheader_font,
                borderwidth=1,
                relief="solid",
                padding=subheader_pad,
                background="#f5f5f5",
                anchor="center",
            )
            lbl.grid(row=3, column=idx, sticky="nsew")
            qs_subheader_labels.append(lbl)

        speeds = [10, 20, 30, 40, 50, 60, 70, 80]
        section_names = ["1구간", "2구간", "3구간"]
        # Example data for each speed and section (fill with zeros except for 1구간)
        # All vehicle cells after the section column are set to '0.0' by default
        qs_values = {speed: ["0.0"] * 9 for speed in speeds}
        row_idx = 4
        # Store references to Entry widgets and sum labels for updating
        qs_entries = []
        for speed in speeds:
            ttk.Label(qs_table, text=str(speed), borderwidth=1, relief="solid", padding=3, background="#f0f0f0", anchor="center", font=("Arial", 8)).grid(row=row_idx, column=0, rowspan=3, sticky="nsew")
            for i, section in enumerate(section_names):
                ttk.Label(qs_table, text=section, borderwidth=1, relief="solid", padding=3, background="#f0f0f0", anchor="center", font=("Arial", 8)).grid(row=row_idx, column=1, sticky="nsew")
                entry_vars = [tk.StringVar(value="0.0") for _ in range(8)]
                entry_widgets = []
                sum_label = ttk.Label(qs_table, text="0.0", borderwidth=1, relief="solid", padding=3, background="#e8f8e8", anchor="center", font=("Arial", 8))
                sum_label.grid(row=row_idx, column=10, sticky="nsew")
                def make_update_sum(entry_vars=entry_vars, sum_label=sum_label):
                    def update_sum(*args):
                        vals = []
                        for var in entry_vars:
                            try:
                                vals.append(float(var.get()))
                            except Exception:
                                vals.append(0.0)
                        sum_val = str(round(sum(vals), 2))
                        sum_label.config(text=sum_val)
                    return update_sum
                # Create Entry widgets for 8 vehicle columns
                for c in range(8):
                    entry = ttk.Entry(qs_table, textvariable=entry_vars[c], width=7, font=("Arial", 8), justify="center")
                    entry.grid(row=row_idx, column=c+2, sticky="nsew")
                    entry_widgets.append(entry)
                    entry_vars[c].trace_add("write", make_update_sum(entry_vars, sum_label))
                # Initialize sum
                make_update_sum(entry_vars, sum_label)()
                qs_entries.append((entry_vars, entry_widgets, sum_label))
                row_idx += 1

        # Main title row (centered)
        ttk.Label(
            table_container_2,
            text="Standard Application Value of Emission by Vehicle Type",
            font=("Arial", 11, "bold"),
            borderwidth=1,
            justify="center",
            anchor="center",
            relief="solid",
            padding=5,
            background="#e0e0e0",
        ).grid(row=0, column=0, columnspan=6, sticky="nsew")

        # Header row with main columns
        # Split '구 분' into two subcolumns (col 0 and col 1)
        ttk.Label(
            table_container_2,
            text="구 분",
            font=("Arial", 9, "bold"),
            borderwidth=1,
            relief="solid",
            padding=5,
            background="#e0e0e0",
            anchor="center",
        ).grid(row=1, column=0, columnspan=2, sticky="nsew")

        # Empty sub-headers under '구 분' to create the two-column split
        ttk.Label(
            table_container_2,
            text="",
            borderwidth=1,
            relief="solid",
            padding=3,
            background="#e0e0e0",
        ).grid(row=2, column=0, sticky="nsew")
        ttk.Label(
            table_container_2,
            text="",
            borderwidth=1,
            relief="solid",
            padding=3,
            background="#e0e0e0",
        ).grid(row=2, column=1, sticky="nsew")

        ttk.Label(
            table_container_2,
            text="배출 허용 허용기준\n[g/km]",
            font=("Arial", 8, "bold"),
            borderwidth=1,
            relief="solid",
            padding=3,
            background="#e0e0e0",
            anchor="center",
            justify="center",
        ).grid(row=1, column=2, columnspan=2, sticky="nsew")

        ttk.Label(
            table_container_2,
            text="",
            font=("Arial", 8, "bold"),
            borderwidth=1,
            relief="solid",
            padding=3,
            background="#e0e0e0",
            anchor="center",
        ).grid(row=1, column=4, sticky="nsew")  # Header for mid3

        ttk.Label(
            table_container_2,
            text="기준배출량\n[m³/h·대]",
            font=("Arial", 8, "bold"),
            borderwidth=1,
            relief="solid",
            padding=3,
            background="#e0e0e0",
            anchor="center",
            justify="center",
        ).grid(row=1, column=5, rowspan=2, sticky="nsew")

       

        # Rebuild data rows into 5 columns: Classification group split into two subcolumns
        # Top two rows are fuel types under a merged '승용차' label


        def _is_numeric_text(value):
            try:
                text = str(value).strip()
                if text == "":
                    return False
                float(text)
                return True
            except Exception:
                return False

        mid_entry_vars = {"mid1": [], "mid2": [], "mid3": []}
        mid_entry_vars_by_idx = {"mid1": {}, "mid2": {}, "mid3": {}}
        table_container_2._mid_entry_vars = mid_entry_vars
        table_container_2._mid_entry_vars_by_idx = mid_entry_vars_by_idx
        table_container_2._qs_subheader_labels = qs_subheader_labels

        vcmd_mid = (dialog.register(NumericValidator.validate_numeric), "%S", "%d")

        for idx in range(len(total_rows)):
            r_idx = 3 + idx
            row_bg = "#ffffff" if (r_idx % 2 == 1) else "#f9f9f9"

            # First two rows: merged '승용차' on left (col 0), fuel type on right (col 1)
            if idx == 0:
                # Merged classification cell '승용차' spanning the two fuel rows
                ttk.Label(
                    table_container_2,
                    text="승   용   차",
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background=row_bg,
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=0, rowspan=2, sticky="nsew")

                # Right subcell for first fuel row
                ttk.Label(
                    table_container_2,
                    text=total_rows[idx],
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background=row_bg,
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=1, sticky="nsew")

            elif idx == 1:
                # Second fuel row: occupy right subcolumn only
                ttk.Label(
                    table_container_2,
                    text=total_rows[idx],
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background=row_bg,
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=1, sticky="nsew")

            else:
                # Other classifications span both subcolumns under '구 분'
                ttk.Label(
                    table_container_2,
                    text=total_rows[idx],
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background=row_bg,
                    anchor="w",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=0, columnspan=2, sticky="nsew")

            # Mid1 (column 2) - numeric values editable
            if _is_numeric_text(mid1[idx]):
                mid1_var = tk.StringVar(value=str(mid1[idx]))
                mid_entry_vars["mid1"].append(mid1_var)
                mid_entry_vars_by_idx["mid1"][idx] = mid1_var
                ttk.Entry(
                    table_container_2,
                    textvariable=mid1_var,
                    validate="key",
                    validatecommand=vcmd_mid,
                    width=10,
                    justify="center",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=2, sticky="nsew")
            else:
                ttk.Label(
                    table_container_2,
                    text=mid1[idx],
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background=row_bg,
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=2, sticky="nsew")

            # Mid2 (column 3) - numeric values editable
            if _is_numeric_text(mid2[idx]):
                mid2_var = tk.StringVar(value=str(mid2[idx]))
                mid_entry_vars["mid2"].append(mid2_var)
                mid_entry_vars_by_idx["mid2"][idx] = mid2_var
                ttk.Entry(
                    table_container_2,
                    textvariable=mid2_var,
                    validate="key",
                    validatecommand=vcmd_mid,
                    width=10,
                    justify="center",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=3, sticky="nsew")
            else:
                ttk.Label(
                    table_container_2,
                    text=mid2[idx],
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background=row_bg,
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=3, sticky="nsew")

            # Mid3 (column 4) - numeric values editable
            if _is_numeric_text(mid3[idx]):
                mid3_var = tk.StringVar(value=str(mid3[idx]))
                mid_entry_vars["mid3"].append(mid3_var)
                mid_entry_vars_by_idx["mid3"][idx] = mid3_var
                ttk.Entry(
                    table_container_2,
                    textvariable=mid3_var,
                    validate="key",
                    validatecommand=vcmd_mid,
                    width=10,
                    justify="center",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=4, sticky="nsew")
            else:
                ttk.Label(
                    table_container_2,
                    text=mid3[idx],
                    borderwidth=1,
                    relief="solid",
                    padding=5,
                    background=row_bg,
                    anchor="center",
                    font=("Arial", 8),
                ).grid(row=r_idx, column=4, sticky="nsew")

            # Emission (column 5)
            if "emission_labels" not in locals():
                emission_labels = []
            emission_label = ttk.Label(
                table_container_2,
                text=emissions[idx],
                borderwidth=1,
                relief="solid",
                padding=5,
                background=row_bg,
                anchor="center",
                font=("Arial", 8),
            )
            emission_label.grid(row=r_idx, column=5, sticky="nsew")
            emission_labels.append(emission_label)

        table_container_2._emission_labels = emission_labels

        def _get_mid_value(values, var_map, idx):
            if idx in var_map:
                return var_map[idx].get()
            return values[idx]

        def _recalc_emissions(*_args):
            v_percent_local = _safe_decimal(_get_mid_value(mid1, mid_entry_vars_by_idx["mid1"], len(mid1) - 1))
            speed_factor_local = _safe_decimal(_get_mid_value(mid3, mid_entry_vars_by_idx["mid3"], len(mid3) - 1))
            g_per_kwh_local = _safe_decimal(_get_mid_value(mid3, mid_entry_vars_by_idx["mid3"], 5))

            new_emissions = []
            for i in range(len(total_rows)):
                if i == len(total_rows) - 1:
                    new_emissions.append("km/h")
                    continue

                m2_val = _safe_decimal(_get_mid_value(mid2, mid_entry_vars_by_idx["mid2"], i))
                if m2_val is not None and v_percent_local is not None and speed_factor_local is not None:
                    val = k_base * m2_val * (v_percent_local / Decimal("100")) * speed_factor_local
                    new_emissions.append(str(val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)))
                    continue

                m1_val = _safe_decimal(_get_mid_value(mid1, mid_entry_vars_by_idx["mid1"], i))
                if m1_val is not None and g_per_kwh_local is not None and v_percent_local is not None:
                    val = k_base * g_per_kwh_local * m1_val * (v_percent_local / Decimal("100")) * k_hp
                    new_emissions.append(str(val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)))
                else:
                    new_emissions.append("")

            for i, label in enumerate(table_container_2._emission_labels):
                label.config(text=new_emissions[i])

            for i, label in enumerate(table_container_2._qs_subheader_labels):
                if i < len(new_emissions):
                    label.config(text=new_emissions[i])

        for vars_by_idx in mid_entry_vars_by_idx.values():
            for var in vars_by_idx.values():
                var.trace_add("write", _recalc_emissions)
        
        # Title
        title_label = ttk.Label(main_frame, text="Speed-Grade Correction Factor Tables (fiv)", 
                    font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Control panel
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill="x", pady=10)
        
        # Pollutant selector
        ttk.Label(control_frame, text="Select Pollutant:").pack(side="left", padx=5)
        pollutant_var = tk.StringVar(value="PM")
        pollutant_combo = ttk.Combobox(
            control_frame,
            textvariable=pollutant_var,
            values=["PM", "CO", "NOx"],
            state="readonly",
            width=10
        )
        pollutant_combo.pack(side="left", padx=5)
        
        # Table selector
        ttk.Label(control_frame, text="Table:").pack(side="left", padx=(20, 5))
        table_var = tk.StringVar(value="")
        table_combo = ttk.Combobox(
            control_frame,
            textvariable=table_var,
            values=[],
            state="readonly",
            width=40
        )
        table_combo.pack(side="left", padx=5)
        
        # Import button
        def import_all():
            catalog = DataCatalog()
            catalog.import_option({"pollutant": "ALL", "file": "all"})
            status_label.config(text="✓ All pollutants imported successfully")
            load_table_list()
        
        ttk.Button(control_frame, text="Import All Pollutants", 
                  command=import_all).pack(side="left", padx=20)
        
        # Status label
        status_label = ttk.Label(control_frame, text="", foreground="green")
        status_label.pack(side="left", padx=10)
        
        # Table display frame with scrollbar
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill="both", expand=True, pady=10)
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(table_frame, bg="white")
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=canvas.xview)
        
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        
        def load_table_list():
            """Load available tables for selected pollutant."""
            pollutant = pollutant_var.get()
            all_overrides = get_all_overrides()
            
            if pollutant in all_overrides:
                data = all_overrides[pollutant]
                table_options = []
                
                # Add base speed-grade tables
                base_tables = data.get("base_speed_grade_tables", [])
                for t in base_tables:
                    table_options.append(f"{t['table_id']} - {t['title']}")
                
                # Add segment speed-grade tables
                segment_tables = data.get("segment_speed_grade_tables", [])
                for t in segment_tables:
                    table_options.append(f"{t['table_id']} - {t['title']}")
                
                table_combo['values'] = table_options
                if table_options:
                    table_var.set(table_options[0])
                    display_table()
            else:
                table_combo['values'] = []
                table_var.set("")
                clear_table_display()
        
        def clear_table_display():
            """Clear the table display."""
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
        
        def display_table():
            """Display the selected table in grid format."""
            clear_table_display()
            
            pollutant = pollutant_var.get()
            table_selection = table_var.get()
            
            if not table_selection:
                return
            
            all_overrides = get_all_overrides()
            if pollutant not in all_overrides:
                return
            
            data = all_overrides[pollutant]
            table_id = table_selection.split(" - ")[0]
            
            # Find the selected table in base_speed_grade_tables
            selected_table = None
            table_type = None
            
            for table in data.get("base_speed_grade_tables", []):
                if table.get("table_id") == table_id:
                    selected_table = table
                    table_type = "base"
                    break
            
            # If not found, check segment_speed_grade_tables
            if not selected_table:
                for table in data.get("segment_speed_grade_tables", []):
                    if table.get("table_id") == table_id:
                        selected_table = table
                        table_type = "segment"
                        break
            
            if not selected_table:
                return
            
            # Display table title
            title = ttk.Label(scrollable_frame, text=selected_table.get("title", ""), 
                            font=("Arial", 12, "bold"))
            title.grid(row=0, column=0, columnspan=20, pady=10, sticky="w")
            
            if table_type == "base":
                # Display base speed-grade table (speed x grade)
                display_base_table(selected_table)
            else:
                # Display segment speed-grade table (segment x speed)
                display_segment_table(selected_table)
        
        def display_base_table(selected_table):
            """Display base speed-grade table format."""
            # Get grades and rows
            grades = selected_table.get("grades", [])
            rows = selected_table.get("rows", [])
            
            # Create headers
            row_header = selected_table.get("row_header", "Speed")
            col_header = selected_table.get("column_header", "Grade")
            
            # Header corner cell
            header_label = ttk.Label(scrollable_frame, text=f"{row_header}\\{col_header}", 
                                    font=("Arial", 9, "bold"), borderwidth=1, relief="solid", 
                                    padding=5, background="#e0e0e0")
            header_label.grid(row=1, column=0, sticky="nsew")
            
            # Column headers (grades)
            for col_idx, grade in enumerate(grades, start=1):
                grade_label = ttk.Label(scrollable_frame, text=str(grade), 
                                       font=("Arial", 9, "bold"), borderwidth=1, 
                                       relief="solid", padding=5, background="#e0e0e0")
                grade_label.grid(row=1, column=col_idx, sticky="nsew")
            
            # Data rows
            for row_idx, row_data in enumerate(rows, start=2):
                speed = row_data.get("speed_kmh", 0)
                values = row_data.get("values", {})
                
                # Row header (speed)
                speed_label = ttk.Label(scrollable_frame, text=str(speed), 
                                       font=("Arial", 9, "bold"), borderwidth=1, 
                                       relief="solid", padding=5, background="#f0f0f0")
                speed_label.grid(row=row_idx, column=0, sticky="nsew")
                
                # Data cells
                for col_idx, grade in enumerate(grades, start=1):
                    value = values.get(str(grade), "-")
                    if isinstance(value, (int, float)):
                        value = f"{value:.3f}"
                    
                    cell_label = ttk.Label(scrollable_frame, text=str(value), 
                                          borderwidth=1, relief="solid", padding=5,
                                          background="white")
                    cell_label.grid(row=row_idx, column=col_idx, sticky="nsew")
        
        def display_segment_table(selected_table):
            """Display segment speed-grade table format."""
            # Get speeds and rows
            speeds = selected_table.get("speeds", [])
            rows = selected_table.get("rows", [])
            
            # Create headers
            row_header = selected_table.get("row_header", "Segment")
            col_header = "Speed (km/h)"
            
            # Header row 1: Merged cell for row_header and "Grade"
            header_label = ttk.Label(scrollable_frame, text=row_header, 
                                    font=("Arial", 9, "bold"), borderwidth=1, relief="solid", 
                                    padding=5, background="#e0e0e0")
            header_label.grid(row=1, column=0, sticky="nsew")
            
            grade_label = ttk.Label(scrollable_frame, text="Grade (%)", 
                                   font=("Arial", 9, "bold"), borderwidth=1, relief="solid", 
                                   padding=5, background="#e0e0e0")
            grade_label.grid(row=1, column=1, sticky="nsew")
            
            # Column headers (speeds)
            for col_idx, speed in enumerate(speeds, start=2):
                speed_label = ttk.Label(scrollable_frame, text=str(speed), 
                                       font=("Arial", 9, "bold"), borderwidth=1, 
                                       relief="solid", padding=5, background="#e0e0e0")
                speed_label.grid(row=1, column=col_idx, sticky="nsew")
            
            # Data rows
            for row_idx, row_data in enumerate(rows, start=2):
                segment = row_data.get("segment", "")
                grade = row_data.get("grade_percent", 0)
                values = row_data.get("values", {})
                
                # Row header (segment)
                segment_label = ttk.Label(scrollable_frame, text=str(segment), 
                                         font=("Arial", 9, "bold"), borderwidth=1, 
                                         relief="solid", padding=5, background="#f0f0f0")
                segment_label.grid(row=row_idx, column=0, sticky="nsew")
                
                # Grade column
                grade_label = ttk.Label(scrollable_frame, text=f"{grade:.1f}", 
                                       borderwidth=1, relief="solid", padding=5,
                                       background="#f0f0f0")
                grade_label.grid(row=row_idx, column=1, sticky="nsew")
                
                # Data cells
                for col_idx, speed in enumerate(speeds, start=2):
                    value = values.get(str(speed), "-")
                    if isinstance(value, (int, float)):
                        value = f"{value:.3f}"
                    
                    cell_label = ttk.Label(scrollable_frame, text=str(value), 
                                          borderwidth=1, relief="solid", padding=5,
                                          background="white")
                    cell_label.grid(row=row_idx, column=col_idx, sticky="nsew")
        
        # Bind events
        pollutant_var.trace_add("write", lambda *args: load_table_list())
        table_var.trace_add("write", lambda *args: display_table())
        
        # Close button
        close_btn = ttk.Button(main_frame, text="Close", command=dialog.destroy)
        close_btn.pack(pady=10)
        
        # Auto-import on open
        import_all()
    
    ttk.Button(button_frame, text="Compute Summary", command=compute_summary).pack(side="right", padx=5)
    ttk.Button(button_frame, text="Data Catalog", command=show_data_catalog).pack(side="right", padx=5)
    
    root.mainloop()
