# Tunnel Traffic Volume Sheet — User Guide

**Location:** Risk Calculations tab → Tunnel Traffic Volume sub-tab

---

## 1. Interface Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  🔒 Unlock Formula Cells   Reset Formula Overrides       Save Changes    │
├──────────────────────────────────────────────────────────────────────────┤
│  D8  │ fx │  =SUM(E8:K8)                                                │  ← Formula bar
├──────────────────────────────────────────────────────────────────────────┤
│     A    │    B    │    C    │    D    │    E    │   F  │  ...           │
│  1. General Tunnel Specifications                                         │
│          │ Tunnel  │         │ Tunnel  │ Cross-  │      │                │
│          │ Name    │         │ Length  │ section │      │                │
│          │         │         │  (km)   │  (m2)   │      │                │
│          │  QRA1   │         │  4.147  │  54.25  │      │                │
│ ...      │         │         │  [BLUE] │ [YELLW] │      │                │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Cell Colour Meanings

| Colour | Meaning | Password Required? | Can Enter Formulas? |
|--------|---------|-------------------|---------------------|
| 🔵 **Blue** | Primary input cells — your main data entry points | No | Yes |
| ⬜ **White** (no formula) | Free-entry annotation or scratch cells | No | Yes |
| 🟡 **Yellow** | Auto-calculated formula results | Yes (`admin123`) | Yes (after unlock) |
| 🟢 **Green** | Derived summary totals | Yes (`admin123`) | Yes (after unlock) |
| 🔴 **Red** | Fixed reference constants (read-only intent) | Yes (`admin123`) | Yes (after unlock) |

> **Rule of thumb:** If a cell is coloured (anything other than white), it came from the Excel workbook and is protected. Only blue cells are designed for daily data entry.

---

## 3. Sheet Sections

The sheet is divided into 6 numbered sections:

| Row | Section | What to Enter |
|-----|---------|---------------|
| 1–5 | **1. General Tunnel Specifications** | Tunnel name, length (km), cross-section, height, slope, diameter, spacing |
| 6–13 | **2. Tunnel Traffic Volume** | AADT by vehicle type, occupancy, daily throughput |
| 14–32 | **3. Fire Occurrence Scenario** | Closure time, broadcast time, travel speed, congestion frequency |
| 33–52 | **4. Traffic Performance** | Vehicle-km by vehicle type and fire intensity (10/20/30/100 MW) |
| 53–67 | **5. Fan Operation Conditions** | Critical wind speeds under normal/congested/delay conditions |
| 68–75 | **6. Escape Cross-Passage Location** | Location coordinates of each cross-passage point |

---

## 4. The Formula Bar

The formula bar sits directly above the table, between the toolbar buttons and the column headers.

```
┌────────┬────┬──────────────────────────────────────────────────┐
│  D8    │ fx │  =SUM(E8:K8)                                     │
└────────┴────┴──────────────────────────────────────────────────┘
  ▲ Cell      ▲ Type here, press Enter to commit
  reference
```

- **Left box** — shows the coordinate of the currently selected cell (e.g. `D8`)
- **Right box** — shows either the raw formula or the plain value; type here and press **Enter** to apply

---

## 5. Entering Data — Step by Step

### 5.1 Editing a Blue Cell (no password)

Blue cells are the primary inputs — tunnel dimensions, AADT counts, frequency values, etc.

1. **Click** any blue cell (e.g. `D3` — Tunnel Length)
2. The formula bar shows the current value, e.g. `4.147`
3. **Type** a new number directly in the cell **or** in the formula bar
4. Press **Enter**
5. All yellow formula cells that depend on it update instantly

**Example — change AADT passenger car count:**
```
Click E8  →  formula bar shows: 238
Type: 1823
Press Enter  →  D8 (Total AADT =SUM(E8:K8)) updates automatically
```

### 5.2 Entering a Formula into a Blue Cell (no password)

You can replace a plain value in any blue cell with a live formula:

1. Click a blue cell (e.g. `E8`)
2. In the formula bar, type a formula starting with `=`
   ```
   =1823*1.1
   ```
3. Press **Enter** — the cell shows the computed result (`2005.3`), and all dependents cascade

**More formula examples for blue cells:**
```
=SUM(F8:K8)           → sum a range
=D3*365*E8            → cross-cell arithmetic
=TL*365*2000          → use a named range (TL = tunnel length)
=IF(D3>4, 500, 300)   → conditional value
=ROUND(D8*0.88, 0)    → rounded result
```

### 5.3 Editing a White Cell (no password)

White cells without formulas are free scratch space — no restrictions:

1. Click any white cell (e.g. `B3`, `N5`, `O4`)
2. Type a number, text, or formula
3. Press **Enter**

White cells with formulas are protected the same as yellow cells — the formula bar will show the formula string and they require the admin password to edit.

### 5.4 Editing a Yellow or Green Cell (password required)

Yellow cells hold auto-calculated values (formulas like `=SUM(E8:K8)`). Green cells are summary totals. Both are locked by default.

**Step 1 — Unlock:**

Click **🔒 Unlock Formula Cells** → a password dialog appears → enter:
```
admin123
```
The button turns green: **🔓 Lock Formula Cells**

**Step 2 — Edit:**

1. Click the yellow or green cell you want to change
2. The formula bar shows its current formula, e.g. `=SUM(E8:K8)`
3. Edit the formula or type a plain number
4. Press **Enter** — result updates immediately

**Example — override D8 formula:**
```
Click D8  →  formula bar shows: =SUM(E8:K8)
Type: =SUM(E8:J8)      (exclude column K)
Press Enter  →  D8 now sums only E8 through J8
```

**Step 3 — Lock again:**

Click **🔓 Lock Formula Cells** → all yellow/green cells are locked and changes are auto-saved.

> ⚠️ **Important:** Locking saves formula-cell edits automatically. Always lock before closing the tab.

---

## 6. Supported Formula Functions

The sheet evaluates the following Excel-style functions in real time:

| Function | Syntax | Example |
|----------|--------|---------|
| `SUM` | `=SUM(range)` or `=SUM(a,b,c)` | `=SUM(E8:K8)` |
| `IF` | `=IF(condition, true, false)` | `=IF(D3>4, 500, 300)` |
| `MIN` | `=MIN(a, b, ...)` | `=MIN(D8, E8)` |
| `MAX` | `=MAX(a, b, ...)` | `=MAX(D44, D45)` |
| `ROUND` | `=ROUND(value, digits)` | `=ROUND(D8*0.1, 2)` |
| `ABS` | `=ABS(value)` | `=ABS(G3)` |
| `AVERAGE` | `=AVERAGE(a, b, ...)` | `=AVERAGE(E8:K8)` |
| `AND` | `=AND(cond1, cond2)` | `=AND(D3>0, E3>0)` |
| `OR` | `=OR(cond1, cond2)` | `=OR(D3>5, E3>60)` |
| `NOT` | `=NOT(condition)` | `=NOT(D3=0)` |

Arithmetic operators: `+  -  *  /  ^` (power)

---

## 7. Named Ranges

These names can be used directly in any formula instead of cell coordinates:

| Name | Cell | Description |
|------|------|-------------|
| `TL` | D3 | Tunnel length (km) |
| `BASE` | F49 | Base vehicle-km reference (10^8) |
| `VK.PC` | D44 | Vehicle-km for passenger cars (10 MW scenario) |
| `VK.HRR010` | D44 | VK for 10 MW fire |
| `VK.HRR020` | D45 | VK for 20 MW fire |
| `VK.HRR030` | D46 | VK for 30 MW fire |
| `VK.HRR100` | D47 | VK for 100 MW fire |
| `LGVK` | D48 | Heavy vehicle VK total |
| `TOTALVK` | D49 | Total all-vehicle VK |
| `LFR.010` | J46 | Local fire rate, 10 MW |
| `LFR.020` | K46 | Local fire rate, 20 MW |
| `LFR.030` | L46 | Local fire rate, 30 MW |
| `LFR.100` | M46 | Local fire rate, 100 MW |
| `CongRate` | D22 | Congestion frequency |
| `FireRate` | D24 | Fire accident rate |
| `RATE_HZV` | J44 | Hazmat vehicle rate |
| `WVP` | D29 | Natural wind — tailwind frequency |
| `WVR` | D30 | Natural wind — headwind frequency |
| `WV0` | D31 | Natural wind — calm frequency |

**Example using named ranges:**
```
=TL * 365 * D8          → annual vehicle-km for AADT in D8
=SUM(VK.HRR010, LGVK)   → combine named range totals
=BASE / TOTALVK          → ratio calculation
```

---

## 8. Resetting Formula Overrides

If you changed a yellow/green cell and want to revert it back to its original Excel formula:

1. Unlock with **🔒 Unlock Formula Cells** → `admin123`
2. Click **Reset Formula Overrides**
3. Confirm the dialog
4. All manually overridden formula cells revert to their computed values

---

## 9. Saving Your Changes

Click **Save Changes** at any time to write your edits to `tunnel_traffic_sheet.json`.

> The file persists between sessions — values you enter today will still be there when you reopen the application.

**What is saved:**
- All blue cell values you typed
- All white cell values/formulas you typed
- Any yellow/green cell overrides made in admin mode

**What is NOT affected by Save:**
- The original `FNCV_ROAD.xlsm` Excel file is never modified

---

## 10. Quick Reference

| Task | How |
|------|-----|
| Change a tunnel parameter | Click blue cell → type value → Enter |
| Enter a live formula | Click blue (or white) cell → type `=formula` → Enter |
| See what formula a yellow cell uses | Click yellow cell → read formula bar |
| Override a yellow formula | Unlock (`admin123`) → click cell → edit → Enter → Lock |
| Restore original yellow formula | Unlock → Reset Formula Overrides → confirm |
| Use tunnel length in a formula | Type `=TL*something` |
| Add up a range | `=SUM(E8:K8)` |
| Save to disk | Click **Save Changes** |
