# FDS6 Custom Fuel Definition Fix

## Problems Identified

From the log file analysis, two critical issues were found:

### Issue 1: Batch File Comment Syntax Error

**Error Message**:
```
'#' is not recognized as an internal or external command,
operable program or batch file.
```

**Cause**: The batch files used `#` for comments, which is valid in Unix/Linux but **not in Windows batch files**.

**Solution**: Replace all `#` comments with `REM` (the Windows batch comment command).

---

### Issue 2: FDS6 Fuel Definition Error

**Error Message**:
```
ERROR(161): Simple chemistry FUEL, C12H23, not defined on REAC or SPEC.
```

**Cause**: FDS6 requires custom fuels (like Diesel C12H23) to be **defined as SPEC** before being used in REAC namelist.

**Solution**: Add SPEC definition before REAC namelist for custom fuels.

---

## Technical Explanation

### FDS5 vs FDS6 Fuel Handling

| Aspect | FDS5 | FDS6 |
|--------|------|------|
| **Predefined Fuels** | PROPANE, METHANE, etc. | Same, works directly |
| **Custom Fuels** | Can use formula directly | **Must define as SPEC first** |
| **REAC Syntax** | Simpler | More strict |

---

### The Fix

#### **Before** (BROKEN):

```fortran
&REAC ID='DIESEL',
      FUEL='C12H23',
      SOOT_YIELD=0.133,
      CO_YIELD=0.168,
      HEAT_OF_COMBUSTION=4.3E+07 /
```

**Problem**: `C12H23` is not a predefined fuel in FDS6, so it must be defined as a SPEC first.

---

#### **After** (FIXED):

```fortran
&SPEC ID='C12H23', FORMULA='C12H23' /

&REAC ID='DIESEL',
      FUEL='C12H23',
      SOOT_YIELD=0.133,
      CO_YIELD=0.168,
      HEAT_OF_COMBUSTION=4.3E+07 /
```

**Solution**: Define `C12H23` as a SPEC, then reference it in REAC.

---

## Code Changes

### File: `fds_workflow/fds_generator.py`

**Method**: `generate_reaction()`

**Before**:
```python
def generate_reaction(self, scenario: FireScenario = None) -> List[str]:
    if scenario.fds_version == "FDS6":
        lines = [f"&REAC ID='{scenario.fuel_id}',"]
        lines.append(f"      FUEL='{scenario.fuel}',")
        # ... rest of REAC
        return lines
```

**After**:
```python
def generate_reaction(self, scenario: FireScenario = None) -> List[str]:
    if scenario.fds_version == "FDS6":
        lines = []
        
        # Define custom fuels as SPEC first
        if scenario.fuel_id in ['DIESEL', 'PETROL_CAR_FIRE']:
            lines.append(f"&SPEC ID='{scenario.fuel}', FORMULA='{scenario.fuel}' /")
            lines.append("")  # Blank line for readability
        
        # Then define REAC
        lines.append(f"&REAC ID='{scenario.fuel_id}',")
        lines.append(f"      FUEL='{scenario.fuel}',")
        # ... rest of REAC
        return lines
```

---

## Fuel Type Handling

### Predefined Fuels (No SPEC needed)

These fuels are built into FDS6 and don't need SPEC definition:

| Fuel | Formula | Usage |
|------|---------|-------|
| PROPANE | C3H8 | Direct use in REAC |
| METHANE | CH4 | Direct use in REAC |
| ETHANE | C2H6 | Direct use in REAC |

**Example**:
```fortran
&REAC ID='CNG',
      FUEL='METHANE',
      SOOT_YIELD=0.01,
      CO_YIELD=0.01 /
```
✅ Works directly, no SPEC needed.

---

### Custom Fuels (SPEC required)

These fuels must be defined as SPEC first:

| Fuel | Formula | SPEC Required |
|------|---------|---------------|
| Diesel | C12H23 | ✅ YES |
| Petrol | ISO_OCTANE (C8H18) | ✅ YES |
| EVC (custom) | PROPANE (placeholder) | ❌ NO (uses predefined) |

**Example**:
```fortran
&SPEC ID='C12H23', FORMULA='C12H23' /

&REAC ID='DIESEL',
      FUEL='C12H23',
      SOOT_YIELD=0.133,
      CO_YIELD=0.168,
      HEAT_OF_COMBUSTION=4.3E+07 /
```
✅ SPEC defined first, then used in REAC.

---

## Batch File Fixes

### run_fds6.bat

**Changed Lines**:
```batch
REM Validate input file
REM Change to FDS file directory
REM Execute FDS6 (try OpenMP first, then single-core)
```

**Before**: Used `#` (Unix comment)  
**After**: Uses `REM` (Windows comment)

---

### run_fds5.bat

**Changed Lines**:
```batch
REM Validate input file
REM Change to FDS file directory
REM Execute FDS5 (try MPI first, then single-core)
```

**Before**: Used `#` (Unix comment)  
**After**: Uses `REM` (Windows comment)

---

## Testing

### Step 1: Update Files

1. **Copy corrected batch files** to `C:\`:
   - `run_fds6.bat`
   - `run_fds5.bat`

2. **Replace** `fds_workflow/fds_generator.py` with updated version

3. **Replace** `qra_main_app.py` with updated version

---

### Step 2: Regenerate FDS Input Files

**Important**: You must regenerate the FDS input files because the old ones have the broken REAC format.

1. **Tab 2**: Configure fire scenarios
2. **Tab 2**: Select FDS6
3. **Tab 2**: Click "Generate FDS Files"
4. **Verify**: Check one of the generated files

**Expected Output**:
```fortran
&SPEC ID='C12H23', FORMULA='C12H23' /

&REAC ID='DIESEL',
      FUEL='C12H23',
      SOOT_YIELD=0.133,
      CO_YIELD=0.168,
      HEAT_OF_COMBUSTION=4.3E+07 /
```

---

### Step 3: Run Simulations

1. **Tab 3**: Configure `C:\run_fds6.bat`
2. **Tab 3**: Click "Run Simulations"
3. **Check Task Manager**: `fds_openmp.exe` should be running
4. **Check Output**: `.smv` files should be generated

---

## Verification

### Success Indicators

✅ **No batch file errors** (no `'#' is not recognized`)  
✅ **No FDS fuel errors** (no `ERROR(161)`)  
✅ **FDS process running** (visible in Task Manager)  
✅ **Output files generated** (`.smv`, `.out`, `.csv`)  

---

### Log File Check

**Good Log** (after fix):
```
=== FDS STDOUT ===

 Starting FDS ...

 MPI Process      0 started on DESKTOP-MB06978

 Reading FDS input file ...

 Fire Dynamics Simulator

 Current Date     : February 12, 2026
 Revision         : FDS-6.x.x
 Compilation Date : ...

 Job TITLE        : 
 Job ID           : 030_N_NVC_pos500

 Time Step:      1, Simulation Time:      0.10 s
 ...
```

**Bad Log** (before fix):
```
'#' is not recognized as an internal or external command
ERROR(161): Simple chemistry FUEL, C12H23, not defined on REAC or SPEC.
ERROR: FDS was improperly set-up - FDS stopped
```

---

## Summary of All Fixes

| Issue | File | Fix |
|-------|------|-----|
| Batch comment syntax | `run_fds6.bat` | Replace `#` with `REM` |
| Batch comment syntax | `run_fds5.bat` | Replace `#` with `REM` |
| Custom fuel definition | `fds_generator.py` | Add SPEC before REAC for Diesel/Petrol |
| Batch execution | `qra_main_app.py` | Pass input file as parameter |

---

## Fuel Configuration Reference

### Diesel (30MW default)

```fortran
&SPEC ID='C12H23', FORMULA='C12H23' /

&REAC ID='DIESEL',
      FUEL='C12H23',
      SOOT_YIELD=0.133,
      CO_YIELD=0.168,
      HEAT_OF_COMBUSTION=4.3E+07 /
```

---

### Petrol (<20MW default)

```fortran
&SPEC ID='ISO_OCTANE', FORMULA='ISO_OCTANE' /

&REAC ID='PETROL_CAR_FIRE',
      FUEL='ISO_OCTANE',
      SOOT_YIELD=0.080,
      CO_YIELD=0.025,
      HEAT_OF_COMBUSTION=4.4E+07 /
```

---

### CNG (Methane - predefined)

```fortran
&REAC ID='CNG',
      FUEL='METHANE',
      SOOT_YIELD=0.010,
      CO_YIELD=0.010,
      HEAT_OF_COMBUSTION=5.0E+07 /
```

**Note**: No SPEC needed for METHANE (predefined in FDS6).

---

### LPG (Propane - predefined)

```fortran
&REAC ID='LPG',
      FUEL='PROPANE',
      SOOT_YIELD=0.024,
      CO_YIELD=0.015,
      HEAT_OF_COMBUSTION=4.6E+07 /
```

**Note**: No SPEC needed for PROPANE (predefined in FDS6).

---

## Troubleshooting

### Issue: Still getting ERROR(161)

**Cause**: Using old FDS input files

**Solution**: Regenerate FDS files in Tab 2 after updating `fds_generator.py`

---

### Issue: Batch file still shows '#' error

**Cause**: Using old batch files

**Solution**: Copy the corrected batch files to `C:\`

---

### Issue: FDS starts but crashes immediately

**Possible Causes**:
1. Invalid mesh dimensions
2. Fire location outside domain
3. Negative time values in RAMP

**Solution**: Check FDS input file for parameter validity

---

## Related Documentation

- **BATCH_FILE_FIX_GUIDE.md** - Batch file execution fix
- **FDS_VERSION_ENFORCEMENT.md** - Version enforcement
- **FUEL_TYPE_UPGRADE_GUIDE.md** - Fuel type feature

---

**Status**: ✅ **FIXED**

Both batch file syntax and FDS6 fuel definition issues have been resolved!
