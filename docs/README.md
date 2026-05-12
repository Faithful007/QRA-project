# QRA System v4.5.0 - Quantitative Risk Assessment System

**Tunnel Fire Risk Assessment: FDS Simulation → EVC/FED Analysis → Risk Calculation**

---

## 📋 Overview

The QRA System is a comprehensive tool for quantitative risk assessment of tunnel fire scenarios. It integrates:

- **FDS (Fire Dynamics Simulator)** - CFD fire simulations
- **FED (Fractional Effective Dose)** - Toxicity and heat exposure calculations
- **EVC (Evacuation)** - Occupant evacuation modeling
- **Risk Analysis** - F-N curves, risk indices, fatalities/year

---

## ✨ Features

### **1. FDS Input Generation (Tab 2)**
- ✅ Generate FDS5 and FDS6 input files
- ✅ Multiple HRR values (5MW, 8MW, 10MW, 15MW, 20MW, 30MW, 50MW, 100MW)
- ✅ Fuel types: Petrol, Diesel, CNG, LPG, EVC
- ✅ Editable fuel properties (SOOT_YIELD, CO_YIELD, HEAT_OF_COMBUSTION)
- ✅ Auto fuel selection based on HRR (Diesel ≥20MW, Petrol <20MW)
- ✅ Congestion levels (Normal, Congested)
- ✅ Ventilation scenarios (5 types)
- ✅ Multiple fire positions

### **2. FDS Simulation (Tab 3)**
- ✅ Parallel processing (multi-core support)
- ✅ Dual FDS5/FDS6 support via batch files
- ✅ Real-time simulation status
- ✅ Automatic output organization
- ✅ Simulation time estimation
- ✅ Error handling and logging

### **3. FDS to FDB Conversion (Tab 3)**
- ✅ **Pure Python converter** (no external .exe needed)
- ✅ Reads FDS slice files (.slcf)
- ✅ Writes FDB database format
- ✅ **Database tracking** of all conversions
- ✅ Supports both FDS5 and FDS6
- ✅ Cross-platform (Windows/Linux/Mac)
- ✅ One-click conversion from UI

### **4. EVC/FED Analysis (Tab 4)**
- ✅ FED calculations from FDB files
- ✅ Evacuation simulation integration
- ✅ Monte Carlo averaging
- ✅ Fatality estimation

### **5. Statistics & Risk Calculation (Tabs 5-7)**
- ✅ Scenario statistics
- ✅ F-N curve generation
- ✅ Risk indices
- ✅ Fatalities per year
- ✅ Return periods

---

## 🚀 Quick Start

### **Prerequisites**

- **Python 3.8+**
- **PyQt6**
- **numpy**
- **FDS6** (C:\FDS6\FDS6\bin\fds_openmp.exe)
- **FDS5** (optional, C:\FDS5\fds5_mpi.exe)

### **Installation**

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure FDS batch files**:
   - Copy `run_fds6.bat` to `C:\run_fds6.bat`
   - Copy `run_fds5.bat` to `C:\run_fds5.bat` (if using FDS5)
   - Edit batch files to match your FDS installation paths

3. **Run the application**:
   ```bash
   python qra_main_app.py
   ```

---

## 📁 Project Structure

```
qra_system_v2/
├── qra_main_app.py                      # Main application (PyQt6 GUI)
├── requirements.txt                     # Python dependencies
├── README.md                            # This file
│
├── database/                            # Database management
│   ├── __init__.py
│   ├── fdb_conversion_db.py            # FDB conversion tracking
│   └── fdb_conversions_schema.sql      # Database schema
│
├── fds_workflow/                        # FDS workflow modules
│   ├── __init__.py
│   ├── fds_generator.py                # FDS input file generator
│   ├── fds_runner.py                   # FDS simulation runner
│   ├── fds_to_fdb_converter.py         # Python FDS to FDB converter
│   └── fds_workflow.py                 # Workflow orchestration
│
├── run_fds6.bat                         # FDS6 batch file (copy to C:\)
├── run_fds5.bat                         # FDS5 batch file (copy to C:\)
│
└── docs/                                # Documentation
    ├── FUEL_TYPE_UPGRADE_GUIDE.md
    ├── FDS_VERSION_ENFORCEMENT.md
    ├── FDS_TO_FDB_INTEGRATION_GUIDE.md
    ├── DUAL_FDS_INSTALLATION_GUIDE.md
    └── ...
```

---

## 🔧 Configuration

### **Tab 1: Directory Setup**

1. **Project Directory**: Root directory for all project files
2. **FDS Inputs Directory**: Where FDS input files (.fds) are generated
3. **FDS Outputs Directory**: Where FDS simulation results are stored
4. **EVC Directory**: Where evacuation simulation files are stored

### **Tab 2: Generate FDS**

1. **Select FDS Version**: FDS6 (recommended) or FDS5
2. **Select Fuel Type**: Petrol, Diesel, CNG, LPG, or EVC
3. **Adjust Fuel Properties**: (if Petrol/Diesel)
   - SOOT_YIELD
   - CO_YIELD
   - HEAT_OF_COMBUSTION
4. **Select HRR Values**: Check desired heat release rates
5. **Select Congestion**: Normal, Congested, or both
6. **Select Ventilation**: Choose ventilation scenarios
7. **Set Fire Positions**: Specify fire locations
8. **Click "Generate FDS Files"**

### **Tab 3: FDS Simulation**

1. **Configure FDS Tools**:
   - **FDS6 Batch File**: C:/run_fds6.bat
   - **FDS5 Batch File**: C:/run_fds5.bat (if using FDS5)
   - **FDS Executable (Direct)**: C:/FDS6/FDS6/bin/fds_openmp.exe
   - **fds2ascii Tool**: C:/FDS6/FDS6/bin/fds2ascii.exe

2. **Run Simulations**:
   - Click "▶ Run FDS Simulations"
   - Monitor progress in status area
   - Wait for completion

3. **Convert to FDB**:
   - Click "🔄 Convert SMV to FDB"
   - Confirm dialog
   - Wait for conversion
   - FDB files created in fds_outputs/ subdirectories

---

## 🎯 Workflow

```
1. Directory Setup (Tab 1)
   ↓
2. Generate FDS Files (Tab 2)
   • Select FDS version (FDS5/FDS6)
   • Select fuel type and properties
   • Select scenarios (HRR, congestion, ventilation, positions)
   • Generate input files
   ↓
3. Run FDS Simulations (Tab 3)
   • Configure FDS tools (batch files)
   • Run simulations (parallel processing)
   • Wait for completion
   ↓
4. Convert SMV to FDB (Tab 3)
   • Python converter reads slice files
   • Writes FDB database format
   • Tracks conversions in database
   ↓
5. EVC/FED Analysis (Tab 4)
   • Load FDB files
   • Calculate FED
   • Run evacuation simulations
   ↓
6. Statistics & Risk (Tabs 5-7)
   • Analyze results
   • Generate F-N curves
   • Calculate risk indices
```

---

## 📊 Database Tracking

All FDS-to-FDB conversions are tracked in the project database (`qra_database.db`).

**Table**: `fdb_conversions`

**Tracked Information**:
- Conversion ID
- File paths (FDS output dir, FDB file, config file)
- Conversion parameters (FDS_ID, axis, time step, conversion factors)
- Variables processed (SOOT, CO2, CO, TEMP, RADI, OXYGEN)
- Status (pending, running, completed, failed)
- Error messages (if failed)
- Timestamps (start, end, duration)
- File metadata (size, time steps, variables, mesh dimensions)

**Query Conversions**:
```python
from pathlib import Path
from database.fdb_conversion_db import get_fdb_conversion_db

db = get_fdb_conversion_db(Path("C:/Projects/MyQRAProject"))
recent = db.get_recent_conversions(limit=10)
stats = db.get_conversion_statistics()
db.close()
```

---

## 🔥 FDS Version Support

### **FDS6 (Recommended)**

- Modern FDS version
- Better performance
- Enhanced features
- Requires SPEC definitions for custom fuels

**Batch File**: `run_fds6.bat`
```batch
@echo off
set PATH=C:\FDS6\FDS6\bin;C:\FDS6\SMV6;%PATH%
cd /d "%~dp1"
if exist "C:\FDS6\FDS6\bin\fds_openmp.exe" (
    "C:\FDS6\FDS6\bin\fds_openmp.exe" "%~1"
) else (
    "C:\FDS6\FDS6\bin\fds.exe" "%~1"
)
exit /b %ERRORLEVEL%
```

### **FDS5 (Legacy)**

- Older FDS version
- Backward compatibility
- Simpler fuel definitions

**Batch File**: `run_fds5.bat`
```batch
@echo off
set PATH=C:\FDS5;C:\Program Files (x86)\NIST\FDS;%PATH%
cd /d "%~dp1"
if exist "C:\FDS5\fds5_mpi.exe" (
    "C:\FDS5\fds5_mpi.exe" "%~1"
) else (
    "C:\FDS5\fds5.exe" "%~1"
)
exit /b %ERRORLEVEL%
```

---

## 🛠️ Troubleshooting

### **Issue: FDS simulations fail with "Return code 1"**

**Cause**: Batch file not receiving input file parameter

**Solution**:
1. Ensure batch files are in `C:\` directory
2. Verify batch file paths in Tab 3 configuration
3. Check FDS executable paths in batch files

---

### **Issue: "ERROR(161): Simple chemistry FUEL not defined"**

**Cause**: FDS6 requires SPEC definitions for custom fuels

**Solution**:
1. Ensure you're using the latest `fds_generator.py`
2. Regenerate FDS files (Tab 2)
3. Verify SPEC definitions in generated .fds files

---

### **Issue: "No FDS simulation outputs found"**

**Cause**: No .smv files in fds_outputs directory

**Solution**:
1. Run FDS simulations first (Tab 3)
2. Wait for simulations to complete
3. Verify .smv files exist in fds_outputs/ subdirectories

---

### **Issue: "Failed to import FDS to FDB converter"**

**Cause**: Module not found

**Solution**:
1. Ensure `fds_to_fdb_converter.py` is in `fds_workflow/` directory
2. Ensure `fdb_conversion_db.py` is in `database/` directory
3. Check that `__init__.py` files exist in both directories

---

## 📚 Documentation

Comprehensive documentation is available in the `docs/` directory:

- **FUEL_TYPE_UPGRADE_GUIDE.md** - Fuel type configuration guide
- **FDS_VERSION_ENFORCEMENT.md** - FDS version enforcement documentation
- **FDS_TO_FDB_INTEGRATION_GUIDE.md** - FDS to FDB conversion integration
- **DUAL_FDS_INSTALLATION_GUIDE.md** - Dual FDS5/FDS6 installation guide
- **FDS6_FUEL_FIX_GUIDE.md** - FDS6 custom fuel fix documentation

---

## 🎉 Key Features

### **1. Dual FDS Support**

✅ **FDS5 and FDS6** coexistence via batch files
✅ **Version enforcement** - FDS6 input only runs with FDS6
✅ **Visual indicators** - Color-coded batch file fields
✅ **Auto-detection** - System uses correct batch file based on version

### **2. Advanced Fuel Configuration**

✅ **5 Fuel Types**: Petrol, Diesel, CNG, LPG, EVC
✅ **Editable Properties**: SOOT_YIELD, CO_YIELD, HEAT_OF_COMBUSTION
✅ **Smart Auto-Selection**: Diesel for ≥20MW, Petrol for <20MW
✅ **FDS6 SPEC Definitions**: Automatic generation for custom fuels

### **3. Python FDS to FDB Converter**

✅ **Pure Python** - No external .exe needed
✅ **Cross-Platform** - Windows, Linux, Mac
✅ **Database Tracking** - All conversions recorded
✅ **FDS5 + FDS6 Support** - Works with both versions
✅ **One-Click Conversion** - Integrated into UI

### **4. Parallel Processing**

✅ **Multi-Core Support** - Utilize all CPU cores
✅ **Batch Processing** - Run multiple simulations simultaneously
✅ **Time Estimation** - Predict simulation completion time
✅ **Progress Tracking** - Real-time status updates

---

## 🔐 License

Copyright © 2026 QRA System Development Team

---

## 📧 Support

For issues, questions, or feature requests, please contact the development team.

---

## 🚀 Version History

### **v4.5.0** (February 2026)
- ✅ Added Python FDS to FDB converter with database tracking
- ✅ Implemented dual FDS5/FDS6 support via batch files
- ✅ Added FDS version enforcement
- ✅ Implemented advanced fuel type configuration (5 fuel types)
- ✅ Added auto fuel selection based on HRR
- ✅ Improved parallel processing
- ✅ Enhanced error handling and logging
- ✅ Added comprehensive documentation

### **v4.0.0** (January 2026)
- Initial release with FDS integration

---

## ✅ Status

**Version**: 4.5.0
**Status**: Production Ready
**Last Updated**: February 12, 2026

---

**Happy Risk Assessment! 🔥🚇**
