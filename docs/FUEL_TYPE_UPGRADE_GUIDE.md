# QRA System v4.5.0 - Fuel Type & FDS Version Upgrade Guide

## Overview

The QRA System has been upgraded to support **FDS version selection** (FDS5/FDS6) and **advanced fuel type configuration** with editable properties. This upgrade provides more accurate fire modeling for different vehicle types and fuel scenarios.

---

## New Features

### 1. FDS Version Selection

Users can now choose between **FDS5** and **FDS6** input file formats:

- **FDS6 (Default)**: Modern format with advanced fuel chemistry modeling
- **FDS5**: Legacy format for compatibility with older FDS installations

**Location**: Generate FDS tab → FDS Version Selection group

---

### 2. Fuel Type Configuration

Five fuel types are now supported:

| Fuel Type | Application | Fuel Formula | Editable |
|-----------|-------------|--------------|----------|
| **Petrol** | Passenger cars, light vehicles | ISO_OCTANE | ✅ Yes |
| **Diesel** | Buses, trucks, heavy vehicles | C12H23 | ✅ Yes |
| **CNG** | Compressed Natural Gas vehicles | METHANE | ❌ No |
| **LPG** | Liquefied Petroleum Gas vehicles | PROPANE | ❌ No |
| **EVC** | Electric Vehicle (battery fire) | PROPANE* | ❌ No |

*Placeholder fuel for EV battery chemistry

**Location**: Generate FDS tab → Fire Specifications → Fuel Type

---

### 3. Editable Fuel Properties

For **Petrol** and **Diesel** fuels, the following properties can be customized:

#### Diesel (Default for ≥20MW scenarios)
```
FUEL ID: DIESEL
FUEL: C12H23
SOOT_YIELD: 0.133
CO_YIELD: 0.168
HEAT_OF_COMBUSTION: 4.3E+07 J/kg
```

#### Petrol (Default for <20MW scenarios)
```
FUEL ID: PETROL_CAR_FIRE
FUEL: ISO_OCTANE
SOOT_YIELD: 0.08
CO_YIELD: 0.025
HEAT_OF_COMBUSTION: 4.4E+07 J/kg
```

**Location**: Generate FDS tab → Fire Specifications → Fuel Properties

---

## Automatic Fuel Selection

The system **automatically selects** the appropriate fuel type based on HRR (Heat Release Rate):

- **HRR ≥ 20 MW**: Diesel (buses, trucks)
- **HRR < 20 MW**: Petrol (passenger cars)

### How It Works:

1. When you check/uncheck HRR values (5MW, 10MW, 20MW, etc.)
2. The system finds the **maximum HRR** selected
3. Automatically switches between Petrol ↔ Diesel
4. Updates fuel properties accordingly

**Note**: Auto-selection only applies to Petrol/Diesel. If you manually select CNG/LPG/EVC, the system won't override your choice.

---

## Usage Examples

### Example 1: Passenger Car Fire (10 MW)

1. Select HRR: **10 MW** ✓
2. Fuel Type: **Petrol** (auto-selected)
3. Properties: Editable (adjust if needed)
4. FDS Version: **FDS6** (default)

**Generated REAC Namelist**:
```fortran
&REAC ID='PETROL_CAR_FIRE',
      FUEL='ISO_OCTANE',
      SOOT_YIELD=0.080,
      CO_YIELD=0.025,
      HEAT_OF_COMBUSTION=4.4E+07 /
```

---

### Example 2: Bus Fire (30 MW)

1. Select HRR: **30 MW** ✓
2. Fuel Type: **Diesel** (auto-selected)
3. Properties: Editable (adjust if needed)
4. FDS Version: **FDS6** (default)

**Generated REAC Namelist**:
```fortran
&REAC ID='DIESEL',
      FUEL='C12H23',
      SOOT_YIELD=0.133,
      CO_YIELD=0.168,
      HEAT_OF_COMBUSTION=4.3E+07 /
```

---

### Example 3: CNG Bus (50 MW)

1. Select HRR: **50 MW** ✓
2. Fuel Type: **CNG** (manually select)
3. Properties: Fixed (not editable)
4. FDS Version: **FDS6** (default)

**Generated REAC Namelist**:
```fortran
&REAC ID='CNG',
      FUEL='METHANE',
      SOOT_YIELD=0.010,
      CO_YIELD=0.010,
      HEAT_OF_COMBUSTION=5.0E+07 /
```

---

### Example 4: Legacy FDS5 Format

1. Select HRR: **20 MW** ✓
2. FDS Version: **FDS 5** (select)
3. Fuel Type: Any (ignored in FDS5)

**Generated REAC Namelist** (FDS5 uses generic polyurethane):
```fortran
&REAC ID='POLYURETHANE',
      FYI='Polyurethane, GM27',
      FUEL='PROPANE',
      SOOT_YIELD=0.10,
      CO_YIELD=0.042 /
```

---

## Technical Details

### File Structure Changes

#### Modified Files:
1. **qra_main_app.py**
   - Added FDS version radio buttons (FDS5/FDS6)
   - Added fuel type dropdown (Petrol/Diesel/CNG/LPG/EVC)
   - Added editable fuel property inputs (SOOT_YIELD, CO_YIELD, HEAT_OF_COMBUSTION)
   - Implemented auto-selection logic based on HRR
   - Updated `generate_fds_files()` to pass fuel properties to generator

2. **fds_workflow/fds_generator.py**
   - Updated `FireScenario` dataclass with fuel properties
   - Modified `generate_reaction()` to support FDS5/FDS6 formats
   - Added fuel-specific REAC namelist generation

---

### Data Flow

```
User Input (UI)
    ↓
HRR Selection → Auto-select Fuel Type (Petrol/Diesel)
    ↓
Fuel Type Selection → Load Default Properties
    ↓
User Edits Properties (if Petrol/Diesel)
    ↓
Generate FDS Files → Pass to FireScenario
    ↓
FDSInputGenerator → generate_reaction()
    ↓
FDS Input File (.fds)
```

---

## Testing

A test script is provided to verify the implementation:

```bash
cd /home/ubuntu/qra_system_v2
python3 test_fuel_types.py
```

**Expected Output**:
- ✅ FDS6 with Diesel (30MW)
- ✅ FDS6 with Petrol (10MW)
- ✅ FDS5 format

---

## Best Practices

### 1. **Use Default Values**
   - The system provides scientifically validated default values
   - Only modify if you have specific experimental data

### 2. **HRR-Fuel Matching**
   - Follow the automatic recommendations:
     - Small fires (<20MW) → Petrol
     - Large fires (≥20MW) → Diesel

### 3. **FDS Version Selection**
   - Use **FDS6** for new projects (more accurate)
   - Use **FDS5** only for compatibility with legacy systems

### 4. **Documentation**
   - Document any custom fuel property changes
   - Include references to experimental data sources

---

## Troubleshooting

### Issue: Fuel properties are grayed out
**Solution**: You've selected CNG/LPG/EVC. These fuels have fixed properties. Switch to Petrol or Diesel to enable editing.

### Issue: Fuel type keeps changing automatically
**Solution**: This is the auto-selection feature. If you want to use a specific fuel (e.g., CNG), select it AFTER choosing HRR values.

### Issue: FDS5 files look different
**Solution**: FDS5 uses a generic POLYURETHANE reaction model. This is expected behavior for legacy compatibility.

---

## Future Enhancements

Planned for future versions:
- [ ] Custom fuel formula input
- [ ] Import fuel properties from database
- [ ] Fuel mixture modeling (e.g., Diesel + Plastics)
- [ ] Electric vehicle battery chemistry models

---

## References

1. NFPA 502 (2020) - Standard for Road Tunnels
2. ISO 13571:2012 - Life-threatening components of fire
3. FDS User Guide - Reaction Chemistry
4. Vehicle Fire Test Data (NIST, RISE, etc.)

---

## Support

For questions or issues:
- Check the main QRA System documentation
- Review test examples in `test_fuel_types.py`
- Contact the development team

---

**Version**: 4.5.0  
**Last Updated**: February 2026  
**Author**: QRA System Development Team
