# Tunnel Traffic Volume Sub-Tab Implementation Guide

## Overview
A new sub-tab called "Tunnel Traffic Volume" has been added to the "Risk Calculations" (Tab7) with the "터널교통량등제원" (Tunnel Traffic Volume Data) sheet from the FNCV_ROAD.xlsm workbook.

## What's New

### Files Created
1. **tunnel_traffic_widget.py** - PyQt5 widget that displays the tunnel traffic data as an editable spreadsheet
2. **tunnel_traffic_sheet.json** - Extracted sheet data from FNCV_ROAD.xlsm with all cell values and colors preserved

### Files Modified
1. **qra_main_app.py** - Modified `create_tab7_results()` method to use sub-tabs instead of a single content area

## Features

### Data Display
- **Sheet Source**: "터널교통량등제원" (Tunnel Traffic Volume Data) from FNCV_ROAD.xlsm
- **Dimensions**: 336 rows × 25 columns
- **Total Cells with Data**: 887

### Color Preservation
All original Excel cell colors are retained:
- 🟦 **Blue (FF00B0F0)**: 61 cells - **EDITABLE**
- 🟨 **Yellow (FFFFFF00)**: 66 cells - Read-only
- 🟩 **Green (FF00B050)**: 2 cells - Read-only
- 🟢 **Light Green (FF92D050)**: 4 cells - Read-only
- 🔴 **Red (FFFF0000)**: 11 cells - Read-only
- ⬜ **White/No Color**: 743 cells - Read-only

### Editability
- Blue cells (61 total) are **fully editable** - users can modify values directly
- All other cells are **read-only** to prevent accidental data corruption
- Modified values are tracked and can be exported

## Tab Structure (Risk Calculations)

```
Tab 7: Risk Calculations
├── Sub-tab 1: Tunnel Traffic Volume ← NEW
│   └── Editable spreadsheet with 336 rows × 25 columns
│       - Blue cells are editable
│       - All colors from Excel are preserved
│
├── Sub-tab 2: Standard Scenario
│   └── Fire scenario tree diagram
│
├── Results Summary
│   └── QRA results display area
│
└── Buttons
    - View F-N Curve
    - Export to Excel
    - Export to PDF
```

## Technical Details

### TunnelTrafficWidget Class
**File**: `tunnel_traffic_widget.py`

**Key Features**:
- Extends QWidget with QTableWidget for spreadsheet display
- Loads data from `tunnel_traffic_sheet.json`
- Applies colors using QColor and QBrush
- Sets cell editability flags based on color
- Method `get_modified_cells()` returns a dict of changed values

**Color Mapping**:
```python
COLOR_MAP = {
    'FF00B050': QColor(0, 176, 80),      # Green
    'FF00B0F0': QColor(0, 176, 240),     # Blue (editable)
    'FF92D050': QColor(146, 208, 80),    # Light Green
    'FFFF0000': QColor(255, 0, 0),       # Red
    'FFFFFF00': QColor(255, 255, 0),     # Yellow
}
```

### Data Structure (tunnel_traffic_sheet.json)
```json
{
  "sheet_name": "터널교통량등제원",
  "max_row": 336,
  "max_col": 25,
  "cells": [
    {
      "row": 1,
      "col": 1,
      "coordinate": "A1",
      "value": "1. 터널일반제원",
      "color": null,
      "is_editable": false
    },
    {
      "row": 3,
      "col": 4,
      "coordinate": "D3",
      "value": 4.147,
      "color": "FF00B0F0",
      "is_editable": true
    },
    ...
  ]
}
```

## How to Use

### Viewing the Data
1. Launch the QRA application (`main_gui.py` or `qra_main_app.py`)
2. Navigate to Tab 7 "Risk Calculations"
3. Click the "Tunnel Traffic Volume" sub-tab
4. View the spreadsheet with color-coded cells

### Editing Data
1. Click on a **blue cell** to edit its value
2. Type the new value
3. Press Enter or click another cell to confirm
4. Changes are automatically tracked

### Exporting Changes
The modified values can be exported using the "Export to Excel" button at the bottom of Tab 7.

## Data Source Reference

The "터널교통량등제원" sheet contains:
- **Section 1**: Tunnel General Specifications (터널일반제원)
  - Tunnel name, length, cross-sectional area, height, slope, etc.
- **Section 2**: Tunnel Traffic Volume (터널교통량)
  - Traffic volume data by vehicle type and time period
- **Additional Columns**: Various calculation parameters and derived values

### Editable Cells (Blue)
The blue cells (61 total) are typically:
- Tunnel length (터널연장) values
- Traffic volume inputs for specific conditions
- Key parameters that affect QRA calculations

## Troubleshooting

### Widget Not Loading
If you see an error message "⚠ Could not load TunnelTrafficWidget", ensure:
1. `tunnel_traffic_widget.py` exists in the same directory as `qra_main_app.py`
2. `tunnel_traffic_sheet.json` exists in the same directory
3. Both files have read permissions
4. PyQt5 is properly installed

### Data Not Displaying
1. Check that `tunnel_traffic_sheet.json` is valid JSON (use a JSON validator)
2. Verify the file size is ~146 KB
3. Ensure the file encoding is UTF-8
4. Restart the application

### Colors Not Showing Correctly
The colors are hardcoded in the `COLOR_MAP` dictionary in `tunnel_traffic_widget.py`. If colors don't match Excel:
1. Check the RGB values in COLOR_MAP
2. The hex colors from Excel are ARGB format (e.g., FF00B0F0 = opaque blue)
3. Update the QColor values if needed

## Future Enhancements

Possible improvements:
- [ ] Add "Save to Excel" button within the widget
- [ ] Implement undo/redo functionality
- [ ] Add search and filter capabilities
- [ ] Implement cell validation rules
- [ ] Add formula support for calculated cells
- [ ] Multi-cell selection and bulk editing
- [ ] Cell change history tracking

## Integration with QRA Workflow

The "Tunnel Traffic Volume" sheet provides input data for:
1. Calculating accident rates based on tunnel characteristics
2. Determining traffic flow patterns
3. Estimating fatality frequencies
4. Running scenario analyses in the Standard Scenario tab

Changes to blue cells in the Tunnel Traffic Volume sub-tab will affect:
- Fire size calculations in the Standard Scenario
- Accident rate calculations
- Final F-N curve generation
- QRA results summary

## Support

For issues or questions:
1. Check the error messages displayed in the widget
2. Verify all required files are present
3. Review the console output for Python errors
4. Check that the FNCV_ROAD.xlsm file is in the same directory

---

**Created**: April 2026
**Version**: 1.0
**Status**: Production Ready
