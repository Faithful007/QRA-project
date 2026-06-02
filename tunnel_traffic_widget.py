"""
tunnel_traffic_widget.py

PyQt5 widget that displays the "터널교통량등제원" sheet from FNCV_ROAD.xlsm
as an editable spreadsheet with color preservation.

Features:
- Displays sheet data in a QTableWidget
- Retains all cell colors from Excel
- Makes blue (FF00B0F0) cells editable
- Translates Korean labels/text to English
- Evaluates formulas and refreshes computed cells after input edits
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QPushButton,
    QAbstractItemView,
    QMessageBox,
    QInputDialog,
    QLineEdit,
    QColorDialog,
    QMenu,
    QAction,
)


# Color mapping from Excel RGB hex to QColor
COLOR_MAP = {
    'FF00B050': QColor(0, 176, 80),      # Green
    'FF00B0F0': QColor(0, 176, 240),     # Blue (editable)
    'FF92D050': QColor(146, 208, 80),    # Light green
    'FFFF0000': QColor(255, 0, 0),       # Red
    'FFFFFF00': QColor(255, 255, 0),     # Yellow
}

HANGUL_RE = re.compile(r"[가-힣]")
CELL_REF_RE = re.compile(r"\$?[A-Z]{1,3}\$?\d+")
NAME_RE = re.compile(r"\b[A-Z_]+\b")

# Phrase-level translation map for the Tunnel Traffic Volume sheet.
KR_TO_EN: Dict[str, str] = {
    "(비정체시)": "(Non-congested)",
    "(정체시)": "(Congested)",
    "(터널중앙부)": "(Tunnel Center)",
    "* 없어짐": "* Removed",
    "0 m/s제연": "0 m/s Smoke Control",
    "0 은 넣으면 안됨": "Do not enter 0",
    "1 섹션거리": "Section Distance 1",
    "1. 터널일반제원": "1. General Tunnel Specifications",
    "108Veh-km에 도달하는데 소요되는 기간 :": "Time required to reach 10^8 Veh-km:",
    "10MW이하": "10 MW or less",
    "2. 터널교통량": "2. Tunnel Traffic Volume",
    "3. 화재발생시나리오": "3. Fire Occurrence Scenario",
    "4. Traffic Performance (차량종별 주행킬로)": "4. Traffic Performance (Vehicle-km by Vehicle Type)",
    "5. 교통조건에 따른 팬가동조건": "5. Fan Operation by Traffic Condition",
    "6. 피난연결통로 위치": "6. Escape Cross-Passage Location",
    "Jet Fan댓수": "Jet Fan Count",
    "« 참고": "« Reference",
    "개소": "Locations",
    "경고방송시간": "Warning Broadcast Time",
    "경사도": "Slope",
    "년": "Year",
    "년간Veh-km": "Annual Veh-km",
    "년간발생건수": "Annual Occurrences",
    "높이": "Height",
    "단면적(㎡)": "Cross-sectional Area (m2)",
    "대피통로\n설치간격\n(m)": "Evacuation Passage\nSpacing\n(m)",
    "대형버스": "Large Bus",
    "대형차량합계": "Heavy Vehicle Total",
    "대형차혼입율": "Heavy Vehicle Share",
    "대형차화재중 차종별 가중치": "Vehicle Type Weights in Heavy-Vehicle Fires",
    "대형트럭": "Large Truck",
    "둘레길이": "Perimeter Length",
    "명": "Persons",
    "명칭": "Name",
    "미풍(0 근접)": "Light Wind (near 0)",
    "버스": "Bus",
    "버스+트럭(소)": "Bus + Truck (Small)",
    "분": "min",
    "분기비": "Branch Ratio",
    "사고발생률(건/1억VK)": "Accident Rate (cases/10^8 VK)",
    "사폐산": "Sapaesan",
    "소형버스": "Small Bus",
    "소형트럭": "Small Truck",
    "순풍": "Tailwind",
    "승용차": "Passenger Car",
    "승용차 화재중 2대연속 발전할 비율": "Rate of 2-vehicle consecutive escalation in passenger car fires",
    "승용차화재중 경미한 화재비율": "Minor fire ratio in passenger car fires",
    "승차인원": "Occupants",
    "역풍": "Headwind",
    "연간통과인원": "Annual Throughput Persons",
    "연결통로 근접화재범위 :": "Cross-passage Near-fire Range:",
    "연결통로간 \n간격": "Cross-passage\nSpacing",
    "연결통로위치": "Cross-passage Location",
    "연번": "No.",
    "외국의 자료인용(ELB tunnel": "Cited from foreign data (ELB tunnel",
    "위험물수송차량 비율": "Hazmat Transport Vehicle Ratio",
    "일반사고중 화재사고 비율": "Fire Accident Ratio in General Accidents",
    "일방향": "One-way",
    "일통과인원": "Daily Throughput Persons",
    "임계풍속": "Critical Wind Speed",
    "입구": "Entrance",
    "자연풍 빈도": "Natural Wind Frequency",
    "전차종": "All Vehicle Types",
    "정상": "Normal",
    "정상소통시": "Normal Flow",
    "정채빈도": "Congestion Frequency",
    "정체시": "Congested",
    "제연팬불능": "Smoke Control Fan Failure",
    "주행거리계 (108Veh-km/Yr)": "Vehicle-km Meter (10^8 Veh-km/Yr)",
    "중형트럭": "Medium Truck",
    "지체": "Delay",
    "지체빈도": "Delay Frequency",
    "지침은 2.0%": "Guideline is 2.0%",
    "차단시간": "Closure Time",
    "차량수": "Number of Vehicles",
    "차종": "Vehicle Type",
    "차종별": "By Vehicle Type",
    "참조": "Reference",
    "첫마믈 방음터널": "Cheotmamul Noise Barrier Tunnel",
    "최대 6": "Maximum 6",
    "출구": "Exit",
    "터널명": "Tunnel Name",
    "터널연장\n(km)": "Tunnel Length\n(km)",
    "터널직경": "Tunnel Diameter",
    "트럭": "Truck",
    "트럭(중대)": "Truck (Medium/Large)",
    "트럭특수": "Special Truck",
    "특수트럭": "Special Truck",
    "피난연결통로": "Evacuation Cross-passage",
    "피난연결통로 지점 p6->p4로 변경 그에 따라 발생빈도도 변경": "Escape cross-passage changed from p6 to p4; occurrence frequency updated accordingly",
    "합계": "Total",
    "해당 화재강도의 주행거리계 + 상급화재에서 경미한 화재로 분류된 것을 포함함": "Vehicle-km for this fire intensity + includes downgraded minor fires from higher intensities",
    "해당차종에 대한 경미한 화재의 주행거리계": "Vehicle-km of minor fires for this vehicle type",
    "해당차종의 차량에 대한  Traffic Performance": "Traffic performance for this vehicle type",
    "혼입율(%)": "Mixing Ratio (%)",
    "화재강도별": "By Fire Intensity",
    "화재사고중 화재확대확률": "Fire Escalation Probability in Fire Accidents",
    "화재시 \n대피인원": "Evacuees\nDuring Fire",
    "화재시 \n주행속도": "Driving Speed\nDuring Fire",
    "화재위치": "Fire Location",
    "화재지점 수 :": "Number of Fire Points:",
    "회귀기간": "Return Period",
}


class TunnelTrafficWidget(QWidget):
    """Widget displaying the Tunnel Traffic Volume sheet from Excel."""

    precalculatedValuesChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sheet_data: Dict = {}
        self.cells_by_coord: Dict[str, Dict[str, Any]] = {}
        self.named_values: Dict[str, Any] = {}
        self.named_refs: Dict[str, Dict[str, str]] = {}  # name -> {sheet, ref}
        self.merged_cells_info: List[Dict] = []
        self.col_widths: Dict[int, float] = {}  # 1-based col index -> Excel width
        self.formula_cells: List[str] = []
        self._updating_table = False
        self._admin_mode = False  # Admin unlock state for formula cells
        self._admin_password = self._resolve_admin_password()
        self.init_ui()
        self.load_sheet_data()

    @staticmethod
    def _resolve_admin_password() -> str:
        """Resolve admin password from env/config, then fallback default."""
        env_password = (os.getenv("QRA_ADMIN_PASSWORD") or "").strip()
        if env_password:
            return env_password

        config_path = Path(__file__).with_name("admin_config.json")
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                cfg_password = str(config.get("admin_password", "")).strip()
                if cfg_password:
                    return cfg_password
            except Exception:
                pass

        return "admin123"

    @staticmethod
    def _build_cell_map(cells: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Build coordinate-indexed map from cell list."""
        return {c['coordinate']: c for c in cells}

    @staticmethod
    def _excel_col_label(col_index_zero_based: int) -> str:
        """Convert a zero-based column index to Excel-style label (A, B, ..., AA)."""
        n = col_index_zero_based + 1
        letters = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            letters = chr(65 + rem) + letters
        return letters

    def _set_alphabetical_headers(self):
        """Apply Excel-style alphabetical headers to the table columns."""
        labels = [self._excel_col_label(i) for i in range(self.table.columnCount())]
        self.table.setHorizontalHeaderLabels(labels)

    def _apply_merged_cell_spans(self):
        """Apply QTableWidget cell spans for all merged regions from the JSON."""
        for mc in self.merged_cells_info:
            r0 = mc['min_row'] - 1   # 0-based
            c0 = mc['min_col'] - 1
            row_span = mc['row_span']
            col_span = mc['col_span']
            # Guard: skip if spans are trivial or outside table bounds
            if row_span < 1 or col_span < 1:
                continue
            if r0 < 0 or c0 < 0:
                continue
            if r0 >= self.table.rowCount() or c0 >= self.table.columnCount():
                continue
            self.table.setSpan(r0, c0, row_span, col_span)

    @staticmethod
    def _apply_formula_overrides(cells: List[Dict[str, Any]], table_values: Dict[str, Any]) -> bool:
        """Apply formula-cell overrides from table values.

        Returns True if any cell value/override flag changed.
        """
        changed = False
        for cell in cells:
            formula = cell.get('formula')
            is_formula = isinstance(formula, str) and formula.startswith('=')
            coord = cell.get('coordinate')
            if not is_formula or not coord or coord not in table_values:
                continue

            new_value = table_values.get(coord)
            old_value = cell.get('value')
            old_override = bool(cell.get('manual_override', False))

            if new_value != old_value or not old_override:
                cell['value'] = new_value
                cell['manual_override'] = True
                changed = True

        return changed
    
    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header label
        header = QLabel("Tunnel Traffic Volume Data")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        header.setMargin(8)
        layout.addWidget(header)
        
        # Add button layout for save functionality (BEFORE table so it's always visible)
        button_layout = QHBoxLayout()
        
        # Admin unlock button
        self.admin_button = QPushButton("🔒 Unlock Formula Cells")
        self.admin_button.setMaximumWidth(200)
        self.admin_button.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 5px;")
        self.admin_button.clicked.connect(self._prompt_admin_password)
        button_layout.addWidget(self.admin_button)

        # Reset formula override button
        self.reset_override_button = QPushButton("Reset Formula Overrides")
        self.reset_override_button.setMaximumWidth(180)
        self.reset_override_button.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 5px;")
        self.reset_override_button.clicked.connect(self._reset_formula_overrides)
        button_layout.addWidget(self.reset_override_button)
        
        # Cell color button
        self.color_button = QPushButton("🎨 Cell Color")
        self.color_button.setMaximumWidth(120)
        self.color_button.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 5px;")
        self.color_button.clicked.connect(self._change_cell_color)
        button_layout.addWidget(self.color_button)

        # Clear color button
        self.clear_color_button = QPushButton("✕ Clear Color")
        self.clear_color_button.setMaximumWidth(110)
        self.clear_color_button.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; padding: 5px;")
        self.clear_color_button.clicked.connect(self._clear_cell_color)
        button_layout.addWidget(self.clear_color_button)

        button_layout.addStretch()
        
        # Save button
        save_button = QPushButton("Save Changes")
        save_button.setMaximumWidth(150)
        save_button.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px;")
        save_button.clicked.connect(self.save_changes)
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)

        # ── Formula bar (Excel-style) ────────────────────────────────────────
        formula_bar_layout = QHBoxLayout()
        self._cell_ref_label = QLabel("")
        self._cell_ref_label.setFixedWidth(50)
        self._cell_ref_label.setStyleSheet(
            "font-weight: bold; font-family: monospace; font-size: 12px;"
            "border: 1px solid #bdc3c7; padding: 2px 4px; background: #ecf0f1;"
        )
        formula_bar_layout.addWidget(self._cell_ref_label)

        fx_label = QLabel("fx")
        fx_label.setFixedWidth(22)
        fx_label.setStyleSheet("font-style: italic; color: #7f8c8d; font-size: 12px;")
        formula_bar_layout.addWidget(fx_label)

        self._formula_bar = QLineEdit()
        self._formula_bar.setPlaceholderText("Select a cell to view or type a formula (e.g. =SUM(E8:K8))")
        self._formula_bar.setStyleSheet(
            "font-family: monospace; font-size: 12px;"
            "border: 1px solid #bdc3c7; padding: 2px 6px;"
        )
        self._formula_bar.returnPressed.connect(self._commit_formula_bar)
        formula_bar_layout.addWidget(self._formula_bar)
        layout.addLayout(formula_bar_layout)
        # ─────────────────────────────────────────────────────────────────────
        
        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(26)  # Support up to Z column
        self.table.setRowCount(340)
        self.table.setWordWrap(True)
        self._set_alphabetical_headers()
        
        # Set column widths
        for i in range(26):
            self.table.setColumnWidth(i, 100)
        
        # Set selection behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.currentCellChanged.connect(self._on_current_cell_changed)

        # Override keyPressEvent to intercept Delete / Backspace
        _original_kpe = self.table.keyPressEvent
        def _table_key_press(event, _orig=_original_kpe):
            if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                self._delete_selected_cells()
            else:
                _orig(event)
        self.table.keyPressEvent = _table_key_press

        # Right-click context menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)

        layout.addWidget(self.table)
    
    def load_sheet_data(self):
        """Load sheet data from JSON file."""
        json_path = Path(__file__).with_name("tunnel_traffic_sheet.json")
        
        if not json_path.exists():
            self.table.setItem(0, 0, QTableWidgetItem("❌ Sheet data not found"))
            return
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.sheet_data = json.load(f)
            self.cells_by_coord = {c['coordinate']: c for c in self.sheet_data.get('cells', [])}
            self.named_values = self.sheet_data.get('named_values', {}) or {}
            self.named_refs   = self.sheet_data.get('named_refs', {}) or {}
            self.merged_cells_info = self.sheet_data.get('merged_cells', []) or []
            self.col_widths = {int(k): v for k, v in (self.sheet_data.get('col_widths', {}) or {}).items()}
            self.formula_cells = [
                c['coordinate']
                for c in self.sheet_data.get('cells', [])
                if isinstance(c.get('formula'), str) and c['formula'].startswith('=')
            ]
            
            # Populate table
            cells = self.sheet_data.get('cells', [])
            max_row = self.sheet_data.get('max_row', 0)
            max_col = self.sheet_data.get('max_col', 0)
            
            # Ensure table is large enough
            self.table.setRowCount(max(max_row, 340))
            self.table.setColumnCount(max(max_col, 26))
            self._set_alphabetical_headers()

            # Apply column widths from Excel (convert Excel units to pixels ~7px per unit)
            for col_1idx, excel_w in self.col_widths.items():
                px = max(int(excel_w * 7), 50)
                self.table.setColumnWidth(col_1idx - 1, px)
            
            # Populate cells
            self._updating_table = True
            for cell in cells:
                row = cell['row'] - 1  # Convert to 0-indexed
                col = cell['col'] - 1
                color = cell['color']
                is_editable = cell['is_editable']
                
                # Create table item
                item = QTableWidgetItem()

                # Set display value (formula cells show computed values)
                item.setText(self._display_value_for_cell(cell['coordinate']))
                
                # Set color — is_editable=True cells are always rendered blue
                # regardless of the color stored in JSON (handles regen resets).
                if is_editable:
                    item.setBackground(QBrush(QColor(0, 176, 240)))   # FF00B0F0 blue
                    item.setForeground(QBrush(QColor(255, 255, 255)))
                elif color and color in COLOR_MAP:
                    bg_color = COLOR_MAP[color]
                    item.setBackground(QBrush(bg_color))
                    
                    # Adjust text color for readability
                    if color in ['FFFFFF00', 'FF92D050']:  # Light colors
                        item.setForeground(QBrush(QColor(0, 0, 0)))
                    else:
                        item.setForeground(QBrush(QColor(255, 255, 255)))
                else:
                    # Default white background
                    item.setBackground(QBrush(QColor(255, 255, 255)))
                    item.setForeground(QBrush(QColor(0, 0, 0)))
                
                # Set editability rules:
                #   1. Blue  (is_editable=True)   → always editable
                #   2. White (color=None)          → always editable (regardless of formula)
                #   3. Yellow/Green/Red (colored)  → editable only in admin mode
                formula = cell.get('formula')
                is_formula = isinstance(formula, str) and formula.startswith('=')
                is_colored = color is not None
                if is_editable or (color is None) or (is_colored and self._admin_mode):
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                
                self.table.setItem(row, col, item)

            # Apply merged cell spans (do this AFTER populating items)
            self._apply_merged_cell_spans()
            
            # Set row heights
            for row in range(max_row):
                self.table.setRowHeight(row, 25)

            # Fit row heights for wrapped long text/sentences.
            self.table.resizeRowsToContents()
            for row in range(self.table.rowCount()):
                self.table.setRowHeight(row, min(max(self.table.rowHeight(row), 25), 120))
            self._updating_table = False
            self._refresh_formula_cells()
            self._emit_precalculated_values()
            
        except Exception as e:
            error_item = QTableWidgetItem(f"❌ Error loading sheet: {e}")
            self.table.setItem(0, 0, error_item)
            self._updating_table = False

    def _display_value_for_cell(self, coord: str) -> str:
        """Return translated/computed display text for a cell."""
        cell = self.cells_by_coord.get(coord)
        if not cell:
            return ""

        formula = cell.get('formula')
        manual_override = bool(cell.get('manual_override', False))
        if isinstance(formula, str) and formula.startswith('=') and not manual_override:
            value = self._evaluate_formula_cell(coord, set())
            if value is None:
                value = cell.get('cached_value')
            return self._format_value(value)

        return self._format_cell_text(cell.get('value'))

    def _format_cell_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return self._translate_text(value)
        return self._format_value(value)

    def _format_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if abs(value - round(value)) < 1e-12:
                return str(int(round(value)))
            return f"{value:.12g}"
        return str(value)

    def _translate_text(self, text: str) -> str:
        """Translate all Korean labels to English for this sheet UI."""
        if not isinstance(text, str) or not HANGUL_RE.search(text):
            return text

        if text in KR_TO_EN:
            return KR_TO_EN[text]

        translated = text
        for kr, en in sorted(KR_TO_EN.items(), key=lambda kv: len(kv[0]), reverse=True):
            if kr in translated:
                translated = translated.replace(kr, en)

        if HANGUL_RE.search(translated):
            translated = HANGUL_RE.sub("", translated).strip()
            if not translated:
                translated = "(Translated)"
        return translated

    def _on_current_cell_changed(self, row: int, col: int, _prev_row: int, _prev_col: int):
        """Update the formula bar when the selected cell changes."""
        if row < 0 or col < 0:
            self._cell_ref_label.setText("")
            self._formula_bar.setText("")
            return
        coord = self._coord_from_row_col(row, col)
        self._cell_ref_label.setText(coord)
        cell = self.cells_by_coord.get(coord)
        if cell:
            formula = cell.get('formula')
            # Always show formula string in bar when formula exists (regardless of
            # manual_override — user should see what formula is assigned to the cell)
            if isinstance(formula, str) and formula.startswith('='):
                self._formula_bar.setText(formula)
            else:
                item = self.table.item(row, col)
                self._formula_bar.setText(item.text() if item else "")
        else:
            item = self.table.item(row, col)
            self._formula_bar.setText(item.text() if item else "")

    def _commit_formula_bar(self):
        """Apply the formula bar content to the currently selected cell."""
        row = self.table.currentRow()
        col = self.table.currentColumn()
        if row < 0 or col < 0:
            return
        coord = self._coord_from_row_col(row, col)
        cell = self.cells_by_coord.get(coord)
        text = self._formula_bar.text().strip()

        # Determine whether this cell is writeable
        existing_formula = cell.get('formula') if cell else None
        existing_is_formula = isinstance(existing_formula, str) and existing_formula.startswith('=')
        is_editable_cell = cell.get('is_editable', False) if cell else False
        cell_color = cell.get('color') if cell else None
        is_white = (cell_color is None) if cell else True
        is_colored = cell_color is not None if cell else False

        # White (any) → always writable (no password needed)
        # Blue          → always writable
        # Yellow/Green  → requires admin mode
        can_write = is_editable_cell or is_white or (is_colored and self._admin_mode)

        if not can_write:
            return

        self._apply_cell_text(coord, text)

    def _apply_cell_text(self, coord: str, text: str):
        """Write a value or formula string into a cell and refresh dependents."""
        cell = self.cells_by_coord.get(coord)
        if cell is None:
            # Cell not in JSON yet — create a transient entry
            col_str = ''.join(c for c in coord if c.isalpha())
            row_num = int(''.join(c for c in coord if c.isdigit()))
            col_num = 0
            for ch in col_str:
                col_num = col_num * 26 + (ord(ch) - ord('A') + 1)
            cell = {
                'row': row_num, 'col': col_num, 'coordinate': coord,
                'value': None, 'formula': None, 'cached_value': None,
                'color': None, 'is_editable': True, 'in_merge': False,
            }
            self.sheet_data.setdefault('cells', []).append(cell)
            self.cells_by_coord[coord] = cell

        if text.startswith('='):
            # User typed a formula — store it and evaluate immediately
            cell['formula'] = text
            cell['manual_override'] = False  # let evaluator compute it
            result = self._evaluate_formula(text, set())
            cell['value'] = result if result is not None else 0
        else:
            # Plain value — clear any formula, store literal
            cell['formula'] = None
            cell['manual_override'] = False
            cell['value'] = self._coerce_user_value(text)

        self.cells_by_coord[coord] = cell

        # Update the table item display
        self._updating_table = True
        try:
            row_0 = cell['row'] - 1
            col_0 = cell['col'] - 1
            item = self.table.item(row_0, col_0)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.table.setItem(row_0, col_0, item)
            item.setText(self._display_value_for_cell(coord))
        finally:
            self._updating_table = False

        # Add to formula_cells tracking if a formula was entered
        if text.startswith('=') and coord not in self.formula_cells:
            self.formula_cells.append(coord)
        elif not text.startswith('=') and coord in self.formula_cells:
            self.formula_cells.remove(coord)

        self._refresh_formula_cells()
        self._emit_precalculated_values()

        # Keep formula bar up to date
        self._cell_ref_label.setText(coord)
        self._formula_bar.setText(cell.get('formula') or self._display_value_for_cell(coord))

    def _on_item_changed(self, item: QTableWidgetItem):
        """Recalculate formula cells when editable source cells change."""
        if self._updating_table:
            return

        coord = self._coord_from_row_col(item.row(), item.column())
        cell = self.cells_by_coord.get(coord)

        # ── Determine what kind of cell this is ──────────────────────────────
        if cell is not None:
            existing_formula = cell.get('formula')
            existing_is_formula = isinstance(existing_formula, str) and existing_formula.startswith('=')
            is_editable_cell = cell.get('is_editable', False)
            cell_color = cell.get('color')
            is_white = (cell_color is None)   # white cells always editable
            is_colored = cell_color is not None
            # White (any) → always accept, Blue → always accept,
            # Yellow/Green (colored) → only in admin mode.
            if not is_editable_cell and not is_white and not (is_colored and self._admin_mode):
                return
        else:
            # Cell not in sheet data at all — treat as a free white cell.
            # Delegate fully to _apply_cell_text which creates the entry.
            typed = item.text()
            if typed:
                self._apply_cell_text(coord, typed)
            return

        typed = item.text()

        if typed.startswith('='):
            # User typed a new formula directly in the cell
            cell['formula'] = typed
            cell['manual_override'] = False
            result = self._evaluate_formula(typed, set())
            cell['value'] = result if result is not None else 0
            if coord not in self.formula_cells:
                self.formula_cells.append(coord)
            # Update cell item to show computed result, not raw formula string
            self._updating_table = True
            try:
                item.setText(self._display_value_for_cell(coord))
            finally:
                self._updating_table = False
        else:
            if existing_is_formula and self._admin_mode:
                cell['manual_override'] = True
            elif existing_is_formula and not self._admin_mode:
                # Typed a plain value into a previously-formula white cell
                cell['formula'] = None
                cell['manual_override'] = False
                if coord in self.formula_cells:
                    self.formula_cells.remove(coord)
            cell['value'] = self._coerce_user_value(typed)

        self.cells_by_coord[coord] = cell

        # Update formula bar to reflect change
        self._cell_ref_label.setText(coord)
        self._formula_bar.setText(cell.get('formula') or typed)

        self._refresh_formula_cells()
        self._emit_precalculated_values()

    def _prompt_admin_password(self):
        """Prompt user for admin password to unlock formula cells."""
        password, ok = QInputDialog.getText(
            self,
            "Admin Password",
            "Enter admin password to unlock formula cells:",
            QLineEdit.Password
        )
        
        if ok:
            if password == self._admin_password:
                self._admin_mode = True
                self.admin_button.setText("🔓 Formula Cells Unlocked")
                self.admin_button.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px;")
                self._refresh_cell_editability()
                QMessageBox.information(
                    self,
                    "Admin Mode Enabled",
                    "✓ Formula cells are now editable.\n\nClick 'Lock Formula Cells' to lock again."
                )
                # Change button to lock
                self.admin_button.setText("🔓 Lock Formula Cells")
                self.admin_button.clicked.disconnect()
                self.admin_button.clicked.connect(self._lock_formula_cells)
            else:
                QMessageBox.warning(
                    self,
                    "Incorrect Password",
                    "✗ The password is incorrect.\n\nFormula cells remain locked."
                )

    def _lock_formula_cells(self):
        """Lock formula cells (toggle back to locked state)."""
        # Save changes BEFORE locking
        self._save_formula_cell_changes()
        
        self._admin_mode = False
        self.admin_button.setText("🔒 Unlock Formula Cells")
        self.admin_button.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 5px;")
        self._refresh_cell_editability()
        self.admin_button.clicked.disconnect()
        self.admin_button.clicked.connect(self._prompt_admin_password)
        QMessageBox.information(
            self,
            "Formula Cells Locked",
            "🔒 Formula cells are now locked and changes have been saved.\n\nEnter password to unlock again."
        )

    def _save_formula_cell_changes(self):
        """Save any formula cells that were edited in admin mode."""
        try:
            json_path = Path(__file__).with_name("tunnel_traffic_sheet.json")
            cells = self.sheet_data.get('cells', [])
            table_values: Dict[str, Any] = {}
            
            # Update formula cells with current table values (while admin mode is still True)
            for cell in cells:
                formula = cell.get('formula')
                is_formula = isinstance(formula, str) and formula.startswith('=')
                
                if is_formula:
                    row = cell['row'] - 1
                    col = cell['col'] - 1
                    
                    if row >= 0 and row < self.table.rowCount() and col >= 0 and col < self.table.columnCount():
                        item = self.table.item(row, col)
                        if item is not None:
                            table_values[cell['coordinate']] = self._coerce_user_value(item.text())

            self._apply_formula_overrides(cells, table_values)
            self.cells_by_coord = self._build_cell_map(cells)
            
            # Always write back to JSON so in-memory admin edits are persisted
            # even when the value was already updated by itemChanged.
            json_data_str = json.dumps(self.sheet_data, ensure_ascii=False, indent=2)
            with open(json_path, 'w', encoding='utf-8') as f:
                f.write(json_data_str)
                f.flush()
        except Exception as e:
            print(f"Warning: Could not save formula cell changes: {e}")

    def _reset_formula_overrides(self):
        """Reset all formula manual overrides and restore computed display."""
        if not self._admin_mode:
            QMessageBox.warning(
                self,
                "Admin Mode Required",
                "Unlock formula cells first to reset overrides."
            )
            return

        reply = QMessageBox.question(
            self,
            "Reset Formula Overrides",
            "Reset all manual formula overrides and return to computed values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            cells = self.sheet_data.get('cells', [])
            changed = False
            for cell in cells:
                formula = cell.get('formula')
                is_formula = isinstance(formula, str) and formula.startswith('=')
                if is_formula and cell.get('manual_override', False):
                    cell['manual_override'] = False
                    changed = True

            if changed:
                self.cells_by_coord = self._build_cell_map(cells)
                json_path = Path(__file__).with_name("tunnel_traffic_sheet.json")
                json_data_str = json.dumps(self.sheet_data, ensure_ascii=False, indent=2)
                with open(json_path, 'w', encoding='utf-8') as f:
                    f.write(json_data_str)
                    f.flush()

                self._refresh_formula_cells()
                self._emit_precalculated_values()
                QMessageBox.information(self, "Reset Complete", "Formula overrides were reset.")
            else:
                QMessageBox.information(self, "No Overrides", "No formula overrides found to reset.")
        except Exception as e:
            QMessageBox.critical(self, "Reset Error", f"Failed to reset overrides:\n\n{e}")

    # ── Cell color ─────────────────────────────────────────────────────────

    def _show_table_context_menu(self, pos):
        """Show right-click context menu on the table."""
        menu = QMenu(self)
        color_action = QAction("🎨 Change Cell Color", self)
        color_action.triggered.connect(self._change_cell_color)
        menu.addAction(color_action)

        clear_action = QAction("✕ Clear Cell Color", self)
        clear_action.triggered.connect(self._clear_cell_color)
        menu.addAction(clear_action)

        menu.addSeparator()

        delete_action = QAction("✕ Delete Cell Content", self)
        delete_action.triggered.connect(self._delete_selected_cells)
        menu.addAction(delete_action)

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    @staticmethod
    def _auto_text_color(bg: QColor) -> QColor:
        """Return black or white foreground for best contrast against *bg*."""
        luminance = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
        return QColor(0, 0, 0) if luminance > 128 else QColor(255, 255, 255)

    def _apply_color_to_items(self, color: Optional[QColor]):
        """Apply *color* (or reset to white if None) to all selected cells."""
        items = self.table.selectedItems()
        if not items:
            return

        if color is not None:
            hex_key = f"FF{color.red():02X}{color.green():02X}{color.blue():02X}"
            fg = self._auto_text_color(color)
        else:
            hex_key = None
            fg = QColor(0, 0, 0)

        self._updating_table = True
        try:
            for item in items:
                coord = self._coord_from_row_col(item.row(), item.column())
                if color is not None:
                    item.setBackground(QBrush(color))
                else:
                    item.setBackground(QBrush(QColor(255, 255, 255)))
                item.setForeground(QBrush(fg))

                # Persist into the data model
                cell = self.cells_by_coord.get(coord)
                if cell is not None:
                    cell['color'] = hex_key
                    # Update editability: colored cells are protected unless admin
                    is_editable = cell.get('is_editable', False)
                    is_colored = hex_key is not None
                    if is_editable or (not is_colored) or (is_colored and self._admin_mode):
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        finally:
            self._updating_table = False

    def _change_cell_color(self):
        """Open a color picker and apply the chosen color to all selected cells."""
        if not self.table.selectedItems():
            QMessageBox.information(self, "No Selection", "Select one or more cells first.")
            return

        # Use the current cell's background as the initial color
        current = self.table.currentItem()
        initial = current.background().color() if current else QColor(255, 255, 255)

        color = QColorDialog.getColor(
            initial, self, "Choose Cell Background Color",
            QColorDialog.ShowAlphaChannel,
        )
        if not color.isValid():
            return
        # Ignore the alpha channel — use fully opaque
        color.setAlpha(255)
        self._apply_color_to_items(color)

    def _clear_cell_color(self):
        """Remove the background color from all selected cells (reset to white)."""
        if not self.table.selectedItems():
            QMessageBox.information(self, "No Selection", "Select one or more cells first.")
            return
        self._apply_color_to_items(None)

    # ── Cell deletion ─────────────────────────────────────────────────────

    def _delete_selected_cells(self):
        """Clear all selected cells (supports range / multi-selection).

        Free cells (blue or white-without-formula) are cleared immediately.
        Protected cells require admin mode or a password prompt (asked once
        for the whole batch).
        """
        items = self.table.selectedItems()
        if not items:
            return

        free_items: List[Tuple[str, QTableWidgetItem]] = []
        protected_items: List[Tuple[str, QTableWidgetItem]] = []

        for item in items:
            coord = self._coord_from_row_col(item.row(), item.column())
            cell = self.cells_by_coord.get(coord)
            is_editable_cell = cell.get('is_editable', False) if cell else False
            cell_color = cell.get('color') if cell else None
            has_formula = (
                isinstance(cell.get('formula'), str) and cell['formula'].startswith('=')
                if cell else False
            )
            is_white_no_formula = (cell_color is None and not has_formula)

            if is_editable_cell or is_white_no_formula or self._admin_mode:
                free_items.append((coord, item))
            else:
                protected_items.append((coord, item))

        # Clear free items right away
        for coord, item in free_items:
            self._clear_cell(coord, item)

        if not protected_items:
            return

        # Ask for password once for all protected cells
        coords_label = ", ".join(c for c, _ in protected_items[:5])
        if len(protected_items) > 5:
            coords_label += f" … (+{len(protected_items) - 5} more)"
        password, ok = QInputDialog.getText(
            self,
            "Password Required",
            f"Enter admin password to delete protected cell(s):\n{coords_label}",
            QLineEdit.Password,
        )
        if not ok:
            return
        if password == self._admin_password:
            for coord, item in protected_items:
                self._clear_cell(coord, item)
        else:
            QMessageBox.warning(self, "Incorrect Password",
                                "✗ Incorrect password — protected cells not deleted.")

    def _clear_cell(self, coord: str, item: QTableWidgetItem):
        """Wipe the value/formula stored for *coord* and blank the table cell."""
        cell = self.cells_by_coord.get(coord)
        if cell is not None:
            cell['formula'] = None
            cell['value'] = None
            cell['manual_override'] = False
            self.cells_by_coord[coord] = cell
        if coord in self.formula_cells:
            self.formula_cells.remove(coord)
        self._updating_table = True
        try:
            item.setText('')
        finally:
            self._updating_table = False
        self._formula_bar.setText('')
        self._refresh_formula_cells()
        self._emit_precalculated_values()

    # ─────────────────────────────────────────────────────────────────────────

    def _refresh_cell_editability(self):
        """Refresh all cell editability based on current admin mode."""
        self._updating_table = True
        try:
            for row in range(self.table.rowCount()):
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        # Find matching cell in sheet_data
                        coord = self._coord_from_row_col(row, col)
                        cell = self.cells_by_coord.get(coord)
                        if cell:
                            is_editable = cell.get('is_editable', False)
                            color = cell.get('color')
                            formula = cell.get('formula')
                            is_formula = isinstance(formula, str) and formula.startswith('=')
                            
                            # Update flags based on current admin mode
                            is_colored = color is not None
                            if is_editable or (color is None) or (is_colored and self._admin_mode):
                                item.setFlags(item.flags() | Qt.ItemIsEditable)
                            else:
                                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        finally:
            self._updating_table = False

    def _refresh_formula_cells(self):
        """Update all formula cells to reflect current editable inputs."""
        if not self.formula_cells:
            return

        self._updating_table = True
        try:
            for coord in self.formula_cells:
                cell = self.cells_by_coord.get(coord)
                if not cell:
                    continue
                row = cell['row'] - 1
                col = cell['col'] - 1
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row, col, item)
                item.setText(self._display_value_for_cell(coord))
        finally:
            self._updating_table = False

    def _evaluate_formula_cell(self, coord: str, visiting: Set[str]) -> Any:
        if coord in visiting:
            return self.cells_by_coord.get(coord, {}).get('cached_value')

        cell = self.cells_by_coord.get(coord)
        if not cell:
            return None

        if cell.get('manual_override', False):
            return self._coerce_number(cell.get('value'))

        formula = cell.get('formula')
        if not isinstance(formula, str) or not formula.startswith('='):
            return self._coerce_number(cell.get('value'))

        visiting.add(coord)
        try:
            value = self._evaluate_formula(formula, visiting)
            if value is None:
                value = cell.get('cached_value')
            return value
        finally:
            visiting.discard(coord)

    def _resolve_named_value(self, name: str, visiting: Set[str]) -> Any:
        """Resolve a named range to its current numeric value.

        Priority:
        1. If the name maps to a cell coord via named_refs, evaluate that cell live.
        2. Fall back to the snapshot in named_values.
        """
        info = self.named_refs.get(name)
        if info:
            coord = info.get('ref', '')
            if coord and coord in self.cells_by_coord:
                return self._coerce_number(self._value_from_coord(coord, visiting)) or 0
        snap = self.named_values.get(name)
        return self._coerce_number(snap) or 0

    def _evaluate_formula(self, formula: str, visiting: Set[str]) -> Any:
        expr = formula[1:].replace('$', '')

        # Handle SUM(...) calls before generic expression evaluation.
        expr = self._replace_sum_calls(expr, visiting)

        # Replace named constants/ranges — use ALL known names from named_refs
        # and named_values, sorted longest-first to avoid partial replacements.
        all_names = set(self.named_refs.keys()) | set(self.named_values.keys())
        for name in sorted(all_names, key=len, reverse=True):
            if re.search(rf'\b{re.escape(name)}\b', expr):
                val = self._resolve_named_value(name, visiting)
                expr = re.sub(rf'\b{re.escape(name)}\b', str(val), expr)

        # Replace cell references with their numeric values.
        expr = CELL_REF_RE.sub(lambda m: str(self._coerce_number(self._value_from_coord(m.group(0), visiting)) or 0), expr)
        expr = expr.replace('^', '**')

        # Support additional Excel-style functions.
        expr = self._replace_supported_functions(expr)

        try:
            return eval(expr, {"__builtins__": {}}, {})
        except Exception:
            return None

    def _split_formula_args(self, content: str) -> List[str]:
        """Split a function argument list by top-level commas."""
        args: List[str] = []
        depth = 0
        current: List[str] = []
        for ch in content:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth = max(0, depth - 1)

            if ch == ',' and depth == 0:
                args.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)

        tail = ''.join(current).strip()
        if tail:
            args.append(tail)
        return args

    def _eval_scalar_expr(self, expr: str) -> float:
        """Evaluate a scalar numeric/boolean expression safely."""
        text = (expr or '').strip()
        if text == '':
            return 0.0
        try:
            value = eval(text, {"__builtins__": {}}, {})
            if isinstance(value, bool):
                return 1.0 if value else 0.0
            return float(self._coerce_number(value) or 0.0)
        except Exception:
            return float(self._coerce_number(text) or 0.0)

    def _replace_supported_functions(self, expr: str) -> str:
        """Replace supported Excel-style function calls with numeric results."""
        function_pattern = re.compile(r"\b(IF|MIN|MAX|ROUND|ABS|AVERAGE|AND|OR|NOT)\(([^()]*)\)", re.IGNORECASE)

        def _replace_one(match: re.Match) -> str:
            func = match.group(1).upper()
            args = self._split_formula_args(match.group(2))

            try:
                if func == 'IF':
                    if len(args) != 3:
                        return '0'
                    cond = self._eval_scalar_expr(args[0])
                    return str(self._eval_scalar_expr(args[1] if cond != 0 else args[2]))

                if func == 'MIN':
                    vals = [self._eval_scalar_expr(a) for a in args] if args else [0.0]
                    return str(min(vals))

                if func == 'MAX':
                    vals = [self._eval_scalar_expr(a) for a in args] if args else [0.0]
                    return str(max(vals))

                if func == 'ROUND':
                    if not args:
                        return '0'
                    number = self._eval_scalar_expr(args[0])
                    digits = int(self._eval_scalar_expr(args[1])) if len(args) > 1 else 0
                    return str(round(number, digits))

                if func == 'ABS':
                    return str(abs(self._eval_scalar_expr(args[0])) if args else 0.0)

                if func == 'AVERAGE':
                    vals = [self._eval_scalar_expr(a) for a in args]
                    return str((sum(vals) / len(vals)) if vals else 0.0)

                if func == 'AND':
                    vals = [self._eval_scalar_expr(a) != 0 for a in args]
                    return '1' if (all(vals) if vals else False) else '0'

                if func == 'OR':
                    vals = [self._eval_scalar_expr(a) != 0 for a in args]
                    return '1' if (any(vals) if vals else False) else '0'

                if func == 'NOT':
                    val = self._eval_scalar_expr(args[0]) if args else 0.0
                    return '1' if val == 0 else '0'

            except Exception:
                return '0'

            return '0'

        prev = None
        current = expr
        while prev != current:
            prev = current
            current = function_pattern.sub(_replace_one, current)
        return current

    _COORD_RE = re.compile(r'^[A-Z]{1,3}\d+$', re.IGNORECASE)

    def _resolve_sum_part(self, part: str, visiting: Set[str]) -> float:
        """Resolve a single SUM argument (cell ref, range, or named range)."""
        clean = part.strip().replace('$', '')
        if ':' in clean:
            start, end = [x.strip() for x in clean.split(':', 1)]
            total = 0.0
            for coord in self._iter_range_coords(start, end):
                total += self._coerce_number(self._value_from_coord(coord, visiting)) or 0.0
            return total
        # Named range?
        if clean in self.named_refs or clean in self.named_values:
            return float(self._resolve_named_value(clean, visiting) or 0.0)
        # Cell coordinate?
        if self._COORD_RE.match(clean):
            return float(self._coerce_number(self._value_from_coord(clean, visiting)) or 0.0)
        # Numeric literal?
        try:
            return float(clean)
        except ValueError:
            return 0.0

    def _replace_sum_calls(self, expr: str, visiting: Set[str]) -> str:
        sum_re = re.compile(r"SUM\(([^\)]*)\)")

        def _sum_repl(match: re.Match) -> str:
            content = match.group(1)
            total = sum(
                self._resolve_sum_part(p, visiting)
                for p in content.split(',') if p.strip()
            )
            return str(total)

        return sum_re.sub(_sum_repl, expr)

    def _value_from_coord(self, coord: str, visiting: Set[str]) -> Any:
        clean = coord.replace('$', '')
        cell = self.cells_by_coord.get(clean)
        if not cell:
            return 0
        if isinstance(cell.get('formula'), str) and cell['formula'].startswith('=') and not cell.get('manual_override', False):
            return self._evaluate_formula_cell(clean, visiting)
        return self._coerce_number(cell.get('value'))

    def _iter_range_coords(self, start: str, end: str) -> List[str]:
        s_col, s_row = self._split_coord(start)
        e_col, e_row = self._split_coord(end)
        if s_col > e_col:
            s_col, e_col = e_col, s_col
        if s_row > e_row:
            s_row, e_row = e_row, s_row

        coords: List[str] = []
        for row in range(s_row, e_row + 1):
            for col in range(s_col, e_col + 1):
                coords.append(self._coord_from_col_row(col, row))
        return coords

    def _split_coord(self, coord: str) -> Tuple[int, int]:
        clean = coord.replace('$', '')
        match = re.match(r"([A-Z]{1,3})(\d+)", clean)
        if not match:
            return 1, 1
        col_text, row_text = match.groups()
        col = 0
        for ch in col_text:
            col = col * 26 + (ord(ch) - ord('A') + 1)
        return col, int(row_text)

    def _coord_from_col_row(self, col: int, row: int) -> str:
        letters = ""
        c = col
        while c > 0:
            c, rem = divmod(c - 1, 26)
            letters = chr(65 + rem) + letters
        return f"{letters}{row}"

    def _coord_from_row_col(self, row: int, col: int) -> str:
        return self._coord_from_col_row(col + 1, row + 1)

    def _coerce_user_value(self, text: str) -> Any:
        stripped = (text or "").strip()
        if stripped == "":
            return ""
        try:
            if any(ch in stripped for ch in ('.', 'e', 'E')):
                return float(stripped)
            return int(stripped)
        except ValueError:
            return stripped

    def _coerce_number(self, value: Any) -> Any:
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            s = value.strip().replace(',', '')
            if s == "":
                return 0
            try:
                if any(ch in s for ch in ('.', 'e', 'E')):
                    return float(s)
                return int(s)
            except ValueError:
                return 0
        return value

    def _numeric_cell_value(self, coord: str) -> float:
        """Return numeric value of a cell, evaluating formulas as needed."""
        cell = self.cells_by_coord.get(coord)
        if not cell:
            return 0.0

        if isinstance(cell.get("formula"), str) and cell["formula"].startswith("=") and not cell.get('manual_override', False):
            value = self._evaluate_formula_cell(coord, set())
            if value is None:
                value = cell.get("cached_value")
            return float(self._coerce_number(value) or 0.0)

        return float(self._coerce_number(cell.get("value")) or 0.0)

    def set_traffic_volume_cells(self, plus_dir: List[Any], occupants: List[Any]) -> None:
        """Auto-populate E8:K8 (+Dir) and E11:K11 (Occupants) from the
        Traffic Volume & Vehicle Specs table in EVC/FED Analysis → Tunnel Info.

        Both arguments must be 7-element sequences ordered by vehicle type
        (Car, Small Bus, Large Bus, Small Truck, Med Truck, Large Truck, Special)
        matching columns E through K of the tunnel traffic sheet.
        """
        COORDS_ROW8  = ['E8',  'F8',  'G8',  'H8',  'I8',  'J8',  'K8']
        COORDS_ROW11 = ['E11', 'F11', 'G11', 'H11', 'I11', 'J11', 'K11']

        def _coerce(v: Any) -> float:
            try:
                return float(str(v).strip())
            except (TypeError, ValueError):
                return 0.0

        updates: Dict[str, float] = {}
        for coord, val in zip(COORDS_ROW8,  plus_dir):
            updates[coord] = _coerce(val)
        for coord, val in zip(COORDS_ROW11, occupants):
            updates[coord] = _coerce(val)

        self._updating_table = True
        try:
            for coord, val in updates.items():
                cell = self.cells_by_coord.get(coord)
                if cell is None:
                    continue
                cell['value'] = val
                cell['manual_override'] = True
                row_idx = cell['row'] - 1
                col_idx = cell['col'] - 1
                item = self.table.item(row_idx, col_idx)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row_idx, col_idx, item)
                item.setText(self._format_value(val))
        finally:
            self._updating_table = False

        self._refresh_formula_cells()
        self._emit_precalculated_values()

    def set_tunnel_info_cells(self, length_m: float, gradient: float, perimeter: float) -> None:
        """Auto-populate tunnel geometry cells from the Tunnel Info panel.

        Mappings:
          D3 ← length_m / 1000  (tunnel length in km)
          G3 ← gradient         (slope %)
          J3 ← perimeter        (cross-section perimeter, m)
        """
        try:
            length_km = round(float(length_m) / 1000.0, 6) if length_m else 0.0
        except (TypeError, ValueError):
            length_km = 0.0
        try:
            grad_val = float(gradient)
        except (TypeError, ValueError):
            grad_val = 0.0
        try:
            perim_val = float(perimeter)
        except (TypeError, ValueError):
            perim_val = 0.0

        updates = {'D3': length_km, 'G3': grad_val, 'J3': perim_val}

        self._updating_table = True
        try:
            for coord, val in updates.items():
                cell = self.cells_by_coord.get(coord)
                if cell is None:
                    continue
                cell['value'] = val
                cell['manual_override'] = True
                row_idx = cell['row'] - 1
                col_idx = cell['col'] - 1
                item = self.table.item(row_idx, col_idx)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row_idx, col_idx, item)
                item.setText(self._format_value(val))
        finally:
            self._updating_table = False

        self._refresh_formula_cells()
        self._emit_precalculated_values()

    def get_standard_scenario_factors(self) -> Dict[str, Any]:
        """Build Standard Scenario fire-size factors from tunnel-sheet calculated cells.

        Workbook cue mapping (터널교통량등제원):
        - VK.HRR010/020/030/100: D44/D45/D46/D47
        - LFR.010/020/030/100: J46/K46/L46/M46
        - BASE: F49 (fallback to named BASE)
        """
        base = self._numeric_cell_value("F49")
        if base <= 0:
            base = float(self._coerce_number((self.named_values or {}).get("BASE")) or 100000000.0)

        vk_pc = self._numeric_cell_value("D44")
        vk_hrr20 = self._numeric_cell_value("D45")
        vk_hrr30 = self._numeric_cell_value("D46")
        vk_hrr100 = self._numeric_cell_value("D47")
        delay_raw = self._numeric_cell_value("D22")
        # Accept either fraction (0.01) or percent-style entry (1, 2, ... => 1%, 2%, ...).
        delay_frequency = (delay_raw / 100.0) if delay_raw > 1.0 else delay_raw
        delay_frequency = max(0.0, min(1.0, delay_frequency))

        # Smoke control distribution (터널교통량등제원 D29-D31, D54-D59)
        nnvc = self._numeric_cell_value("D54")
        nnv0 = self._numeric_cell_value("D55")
        nff  = self._numeric_cell_value("D56")
        cnvc = self._numeric_cell_value("D57")
        cnv0 = self._numeric_cell_value("D58")
        cff  = self._numeric_cell_value("D59")
        wv0  = self._numeric_cell_value("D31")
        wvr  = self._numeric_cell_value("D30")
        wvp  = self._numeric_cell_value("D29")
        smoke_probs = {
            "NNVC": nnvc, "NNV0": nnv0,
            "NFV0": nff * wv0, "NFVM": nff * wvr, "NFVP": nff * wvp,
            "CNVC": cnvc, "CNV0": cnv0,
            "CFV0": cff * wv0, "CFVM": cff * wvr, "CFVP": cff * wvp,
        }

        # Tunnel geometry for asymmetric fire placement formula (_rp weights)
        tunnel_length_km = self._numeric_cell_value("D3")
        tunnel_length_m = tunnel_length_km * 1000.0 if tunnel_length_km > 0 else 0.0
        n_fire = int(self._numeric_cell_value("G68") or 6)
        ran_evc_fire = self._numeric_cell_value("K68") or 25.0

        factors = {
            "base": base,
            "vk_pc": vk_pc,
            "delay_frequency": delay_frequency,
            "tunnel_length_m": tunnel_length_m,
            "n_fire": n_fire,
            "ran_evc_fire": ran_evc_fire,
            "vk_hrr": {
                10: vk_pc,
                20: vk_hrr20,
                30: vk_hrr30,
                100: vk_hrr100,
            },
            "lfr": {
                10: self._numeric_cell_value("J46"),
                20: self._numeric_cell_value("K46"),
                30: self._numeric_cell_value("L46"),
                100: self._numeric_cell_value("M46"),
            },
            # Explicit aliases matching workbook-style names for consumers.
            "vk_named": {
                "VK.PC": vk_pc,
                "VK.HRR010": vk_pc,
                "VK.HRR020": vk_hrr20,
                "VK.HRR030": vk_hrr30,
                "VK.HRR100": vk_hrr100,
            },
            "named_values": {
                **dict(self.named_values or {}),
                "VK.PC": vk_pc,
                "VK.HRR010": vk_pc,
                "VK.HRR020": vk_hrr20,
                "VK.HRR030": vk_hrr30,
                "VK.HRR100": vk_hrr100,
            },
            # Smoke control probabilities (NNVC, NNV0, NFF×WVx, CNVC, CNV0, CFF×WVx)
            "smoke_probs": smoke_probs,
        }
        return factors

    def _emit_precalculated_values(self):
        """Emit pre-calculated values for consumers like Standard Scenario."""
        try:
            self.precalculatedValuesChanged.emit(self.get_standard_scenario_factors())
        except Exception:
            pass
    
    def get_modified_cells(self) -> Dict[str, Any]:
        """Get all modified cells with their new values."""
        modified = {}
        cells = self.sheet_data.get('cells', [])
        
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and item.text():
                    # Find matching cell in sheet_data
                    for cell in cells:
                        if cell['row'] - 1 == row and cell['col'] - 1 == col:
                            # Check if cell is editable (is_editable=true) or white (color=None, non-formula)
                            # or if it's a formula cell and admin mode is enabled
                            is_editable_cell = cell.get('is_editable', False)
                            is_white_cell = cell.get('color') is None
                            formula = cell.get('formula')
                            is_formula = isinstance(formula, str) and formula.startswith('=')
                            can_modify = ((is_editable_cell or (is_white_cell and not is_formula)) or 
                                         (is_formula and self._admin_mode))
                            if can_modify and str(cell.get('value')) != item.text():
                                modified[cell['coordinate']] = item.text()
                            break
        
        return modified
    
    def save_changes(self):
        """Save all modified cells back to the JSON file."""
        try:
            json_path = Path(__file__).with_name("tunnel_traffic_sheet.json")
            
            # Track changes
            changes_made = False
            
            # Update cells with current table values
            cells = self.sheet_data.get('cells', [])
            for cell in cells:
                row = cell['row'] - 1  # Convert to 0-indexed
                col = cell['col'] - 1
                
                # Determine if cell is saveable
                is_editable_cell = cell.get('is_editable', False)
                is_white_cell = cell.get('color') is None
                formula = cell.get('formula')
                is_formula = isinstance(formula, str) and formula.startswith('=')
                manual_override = bool(cell.get('manual_override', False))
                
                # Save cells if:
                #   1. Marked as is_editable, OR
                #   2. White non-formula cells, OR
                #   3. Formula cells in admin mode, OR
                #   4. Formula cells already set as manual override.
                can_save = is_editable_cell or (is_white_cell and not is_formula) or (is_formula and (self._admin_mode or manual_override))
                
                if can_save:
                    if row >= 0 and row < self.table.rowCount() and col >= 0 and col < self.table.columnCount():
                        item = self.table.item(row, col)
                        if item is not None:
                            new_value = self._coerce_user_value(item.text())
                            old_value = cell.get('value')
                            
                            # Check if value changed
                            if new_value != old_value:
                                cell['value'] = new_value
                                if is_formula and self._admin_mode:
                                    cell['manual_override'] = True
                                self.cells_by_coord[cell['coordinate']] = cell
                                changes_made = True

            # Persist color changes for every cell regardless of editability
            for cell in cells:
                row = cell['row'] - 1
                col = cell['col'] - 1
                if 0 <= row < self.table.rowCount() and 0 <= col < self.table.columnCount():
                    item = self.table.item(row, col)
                    if item is not None:
                        bg = item.background().color()
                        if bg.isValid() and bg != QColor(255, 255, 255):
                            new_hex = f"FF{bg.red():02X}{bg.green():02X}{bg.blue():02X}"
                        else:
                            new_hex = None
                        if cell.get('color') != new_hex:
                            cell['color'] = new_hex
                            self.cells_by_coord[cell['coordinate']] = cell
                            changes_made = True
            
            # Write back to JSON file
            json_data_str = json.dumps(self.sheet_data, ensure_ascii=False, indent=2)
            with open(json_path, 'w', encoding='utf-8') as f:
                f.write(json_data_str)
                f.flush()  # Explicitly flush to disk
            
            # Verify file was written by reading it back
            with open(json_path, 'r', encoding='utf-8') as f:
                verify_data = json.load(f)
            
            if verify_data == self.sheet_data:
                if changes_made:
                    QMessageBox.information(
                        self, 
                        "Save Successful", 
                        f"✓ Changes saved successfully!\n\nPath: {json_path}\n\nFile will be loaded on next program restart."
                    )
                else:
                    QMessageBox.information(
                        self,
                        "No Changes",
                        "No changes detected to save."
                    )
            else:
                QMessageBox.critical(
                    self,
                    "Save Verification Failed",
                    f"File was written but verification failed.\nPlease check file permissions.\n\nPath: {json_path}"
                )
            
        except PermissionError as e:
            QMessageBox.critical(
                self,
                "Permission Denied",
                f"Cannot save file - permission denied.\n\nPlease check if the file is read-only or locked.\n\nError: {str(e)}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Error",
                f"Error saving changes:\n\n{str(e)}\n\nPlease ensure tunnel_traffic_sheet.json is not locked by another program."
            )
