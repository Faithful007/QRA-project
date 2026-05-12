# Python FDS to FDB Converter

## Overview

This is a **pure Python implementation** that replaces the `FDS2FDB.exe` executable for converting FDS simulation outputs to FDB database format. It provides a cross-platform, integrated solution for the QRA System workflow.

---

## ✅ Advantages Over FDS2FDB.exe

| Feature | FDS2FDB.exe | Python Solution |
|---------|-------------|-----------------|
| **Platform** | Windows only | Cross-platform (Windows/Linux/Mac) |
| **FDS Version** | FDS5 only | FDS5 + FDS6 |
| **Integration** | External process | Native Python integration |
| **Customization** | Recompile Fortran | Edit Python code |
| **Dependencies** | Fortran runtime | Python + numpy |
| **Automation** | Manual execution | Automated in workflow |
| **Error Handling** | Limited | Comprehensive logging |

---

## 📦 Installation

### Required Packages

```bash
# Core dependencies (required)
pip install numpy

# Optional (for better FDS file reading)
pip install fdsreader
```

**Note**: The converter works without `fdsreader` using a fallback binary reader, but `fdsreader` provides better compatibility with FDS6.

---

## 🚀 Usage

### Method 1: Command Line

```bash
python fds_to_fdb_converter.py <simulation_dir> [config_file] [output_file]
```

**Example**:
```bash
python fds_to_fdb_converter.py C:/FDS_Outputs/030_N_NVC_pos500 C:/CONVERT.DES
```

---

### Method 2: Python Script

```python
from pathlib import Path
from fds_workflow.fds_to_fdb_converter import convert_fds_to_fdb

# Convert FDS output to FDB
simulation_dir = Path("C:/FDS_Outputs/030_N_NVC_pos500")
config_file = Path("C:/CONVERT.DES")  # Optional

fdb_file = convert_fds_to_fdb(
    simulation_dir=simulation_dir,
    config_file=config_file,
    output_file=None  # Auto-generate filename
)

print(f"FDB file created: {fdb_file}")
```

---

### Method 3: Integrated in QRA System

The converter is automatically called after FDS simulations complete (see Integration section below).

---

## 📋 Configuration File (CONVERT.DES)

The converter uses the same configuration format as FDS2FDB.exe:

```
FDS_ID  AxisDir  VertDir  TimeDtep iTempSkip  FDS_SLC_File_Number(SOOT,CO2,CO,TEMP,RADI,OXYGEN)
TN      X        Z        30       6          1  2  3  4  5  6 0 0 0 0 0 0
Convertion Factor
SOOT       CO2       CO        TEMP      RADI      OXYGEN 
1000000.0  100.0     1000000.0 1.0       0.25      100.0
```

### Parameters Explained

| Parameter | Description | Example |
|-----------|-------------|---------|
| **FDS_ID** | Simulation identifier (prefix for slice files) | TN |
| **AxisDir** | Primary axis direction (X, Y, or Z) | X |
| **VertDir** | Vertical direction (X, Y, or Z) | Z |
| **TimeDtep** | Time step interval for extraction | 30 |
| **iTempSkip** | Temporal skip (process every Nth frame) | 6 |
| **FDS_SLC_File_Number** | Slice file numbers for each variable | 1 2 3 4 5 6 |

### Conversion Factors

| Variable | Factor | Purpose |
|----------|--------|---------|
| **SOOT** | 1,000,000 | Convert mass fraction to ppm |
| **CO2** | 100 | Convert fraction to percentage |
| **CO** | 1,000,000 | Convert mass fraction to ppm |
| **TEMP** | 1.0 | No conversion (Celsius) |
| **RADI** | 0.25 | Radiation scaling |
| **OXYGEN** | 100 | Convert fraction to percentage |

---

## 🔧 How It Works

### Step 1: Read Configuration

```python
config = ConversionConfig(config_file)
# Loads FDS_ID, conversion factors, slice file mapping
```

### Step 2: Find Slice Files

The converter searches for slice files using patterns:
- `TN_01.slcf` (SOOT)
- `TN_02.slcf` (CO2)
- `TN_03.slcf` (CO)
- `TN_04.slcf` (TEMP)
- `TN_05.slcf` (RADI)
- `TN_06.slcf` (OXYGEN)

### Step 3: Read Binary Data

Two methods are supported:

**Method A: Using fdsreader** (recommended for FDS6):
```python
import fdsreader as fds
sim = fds.Simulation(simulation_dir)
slice_data = sim.slices[0].to_global()
```

**Method B: Fallback Binary Reader** (works without fdsreader):
```python
# Reads FDS binary format directly
# Compatible with both FDS5 and FDS6
```

### Step 4: Apply Conversion Factors

```python
converted_data = raw_data * conversion_factor
# Example: SOOT * 1,000,000 → ppm
```

### Step 5: Write FDB File

```python
fdb_writer = FDBWriter(output_file)
fdb_writer.add_variable('SOOT', soot_data, 1000000.0)
fdb_writer.add_variable('CO', co_data, 1000000.0)
# ... add all variables
fdb_writer.write()
```

---

## 📁 FDB File Format

The FDB file is a binary format with the following structure:

```
[Header]
- Magic number: 'FDB1' (4 bytes)
- Version: 1 (4 bytes)
- Number of variables: N (4 bytes)
- Number of time steps: T (4 bytes)

[Time Array]
- T × 4 bytes (float32 array)

[Mesh Information]
- Extents: 6 × 4 bytes (x1, x2, y1, y2, z1, z2)
- Dimensions: 3 × 4 bytes (nx, ny, nz)

[Variable 1]
- Name length: 4 bytes
- Name: N bytes (UTF-8)
- Data shape: rank + rank×4 bytes
- Data: shape[0]×shape[1]×...×4 bytes (float32)

[Variable 2]
...
[Variable N]
```

---

## 🔄 Integration with QRA System

### Automatic Conversion After FDS Simulation

The converter can be integrated into the QRA System workflow to automatically convert FDS outputs after simulations complete.

**Add to `qra_main_app.py`**:

```python
from fds_workflow.fds_to_fdb_converter import convert_fds_to_fdb

class FDSSimulationThread(QThread):
    def run(self):
        # ... existing FDS simulation code ...
        
        # After simulations complete
        if self.auto_convert_to_fdb:
            self.status_signal.emit("Converting FDS outputs to FDB...")
            
            for fds_output_dir in self.completed_simulations:
                try:
                    fdb_file = convert_fds_to_fdb(
                        simulation_dir=fds_output_dir,
                        config_file=self.convert_config_file
                    )
                    self.status_signal.emit(f"✓ Created: {fdb_file.name}")
                except Exception as e:
                    self.status_signal.emit(f"✗ Conversion failed: {e}")
```

### UI Integration (Tab 3)

Add checkbox and configuration in the FDS Simulation tab:

```python
# Auto-convert to FDB checkbox
self.auto_convert_checkbox = QCheckBox("Auto-convert to FDB after simulation")
self.auto_convert_checkbox.setChecked(True)

# CONVERT.DES file selector
self.convert_config_input = QLineEdit()
self.convert_config_browse = QPushButton("Browse...")
```

---

## 🧪 Testing

### Test Script

```python
from pathlib import Path
from fds_workflow.fds_to_fdb_converter import (
    ConversionConfig, 
    FDSToFDBConverter
)

# Test configuration loading
config = ConversionConfig(Path("CONVERT.DES"))
print(f"FDS ID: {config.fds_id}")
print(f"Conversion factors: {config.conversion_factors}")

# Test conversion
converter = FDSToFDBConverter(
    simulation_dir=Path("test_data/fds_output"),
    config=config
)
fdb_file = converter.convert()
print(f"FDB file created: {fdb_file}")
```

---

## 📊 Example Output

```
2026-02-12 10:30:15 - INFO - Starting FDS to FDB conversion
2026-02-12 10:30:15 - INFO - Simulation directory: C:\FDS_Outputs\030_N_NVC_pos500
2026-02-12 10:30:15 - INFO - Output file: C:\FDS_Outputs\030_N_NVC_pos500\TN.fdb
2026-02-12 10:30:16 - INFO - Processing SOOT (file 1)
2026-02-12 10:30:17 - INFO - Successfully processed SOOT
2026-02-12 10:30:17 - INFO - Processing CO2 (file 2)
2026-02-12 10:30:18 - INFO - Successfully processed CO2
2026-02-12 10:30:18 - INFO - Processing CO (file 3)
2026-02-12 10:30:19 - INFO - Successfully processed CO
2026-02-12 10:30:19 - INFO - Processing TEMP (file 4)
2026-02-12 10:30:20 - INFO - Successfully processed TEMP
2026-02-12 10:30:20 - INFO - Processing RADI (file 5)
2026-02-12 10:30:21 - INFO - Successfully processed RADI
2026-02-12 10:30:21 - INFO - Processing OXYGEN (file 6)
2026-02-12 10:30:22 - INFO - Successfully processed OXYGEN
2026-02-12 10:30:22 - INFO - Successfully wrote FDB file: C:\FDS_Outputs\030_N_NVC_pos500\TN.fdb
2026-02-12 10:30:22 - INFO - Conversion complete: C:\FDS_Outputs\030_N_NVC_pos500\TN.fdb
```

---

## 🐛 Troubleshooting

### Issue: "fdsreader not installed"

**Solution**: Install fdsreader (optional but recommended):
```bash
pip install fdsreader
```

Or use the fallback binary reader (already included).

---

### Issue: "No .smv file found"

**Cause**: fdsreader requires an .smv file to locate slice files

**Solution**: Ensure FDS simulation completed successfully and generated .smv file

---

### Issue: "Slice file not found"

**Possible Causes**:
1. Incorrect FDS_ID in CONVERT.DES
2. Slice files not generated by FDS
3. Wrong file numbering

**Solution**: 
- Check FDS_ID matches your simulation
- Verify slice files exist: `TN_01.slcf`, `TN_02.slcf`, etc.
- Update file numbers in CONVERT.DES

---

### Issue: "Error reading binary slice file"

**Cause**: Incompatible slice file format

**Solution**: Install fdsreader for better compatibility:
```bash
pip install fdsreader
```

---

## 🔬 Advanced Usage

### Custom Conversion Factors

```python
from fds_workflow.fds_to_fdb_converter import ConversionConfig

config = ConversionConfig()
config.conversion_factors['CO'] = 500000.0  # Custom CO scaling
config.conversion_factors['TEMP'] = 1.8  # Convert to Fahrenheit
```

### Process Specific Variables Only

```python
config = ConversionConfig()
config.slice_files = {
    'CO': 3,
    'TEMP': 4,
    'OXYGEN': 6
}
# Only process CO, TEMP, OXYGEN
```

### Custom Time Filtering

```python
config = ConversionConfig()
config.time_step = 60  # Extract every 60 time steps
config.temp_skip = 10  # Process every 10th frame
```

---

## 📚 API Reference

### `ConversionConfig`

**Constructor**:
```python
ConversionConfig(config_file: Optional[Path] = None)
```

**Attributes**:
- `fds_id`: Simulation identifier
- `axis_dir`: Primary axis direction
- `vert_dir`: Vertical direction
- `time_step`: Time step interval
- `temp_skip`: Temporal skip interval
- `slice_files`: Dict mapping variable names to file numbers
- `conversion_factors`: Dict mapping variable names to scaling factors

**Methods**:
- `load_from_file(config_file: Path)`: Load configuration from CONVERT.DES

---

### `FDSSliceReader`

**Constructor**:
```python
FDSSliceReader(slice_file: Path)
```

**Methods**:
- `read() -> Tuple[np.ndarray, np.ndarray, Dict]`: Read slice file data
  - Returns: (data_array, time_array, metadata_dict)

---

### `FDBWriter`

**Constructor**:
```python
FDBWriter(output_file: Path)
```

**Methods**:
- `add_variable(name: str, data: np.ndarray, conversion_factor: float)`: Add variable
- `set_times(times: np.ndarray)`: Set time array
- `set_mesh_info(mesh_info: Dict)`: Set mesh information
- `write()`: Write FDB file

---

### `FDSToFDBConverter`

**Constructor**:
```python
FDSToFDBConverter(simulation_dir: Path, config: Optional[ConversionConfig] = None)
```

**Methods**:
- `convert(output_file: Optional[Path] = None) -> Path`: Convert FDS to FDB
  - Returns: Path to generated FDB file

---

### `convert_fds_to_fdb()` (Convenience Function)

```python
convert_fds_to_fdb(
    simulation_dir: Path,
    config_file: Optional[Path] = None,
    output_file: Optional[Path] = None
) -> Path
```

**Parameters**:
- `simulation_dir`: Directory containing FDS output files
- `config_file`: Path to CONVERT.DES (optional)
- `output_file`: Output .fdb file path (optional, auto-generated if not provided)

**Returns**: Path to generated FDB file

---

## 🎯 Summary

### Key Features

✅ **Pure Python** - No compiled executables needed
✅ **Cross-platform** - Works on Windows, Linux, Mac
✅ **FDS5 + FDS6** - Supports both versions
✅ **Flexible** - Customizable conversion factors and filtering
✅ **Integrated** - Seamless QRA System workflow
✅ **Robust** - Comprehensive error handling and logging
✅ **Fast** - Efficient binary file processing with numpy

### Workflow

```
FDS Simulation
    ↓
Slice Files (.slcf)
    ↓
Python Converter (fds_to_fdb_converter.py)
    ↓
FDB Database (.fdb)
    ↓
EVC Simulation / Analysis
```

---

**Status**: ✅ **READY TO USE**

The Python FDS to FDB converter is a complete replacement for FDS2FDB.exe with enhanced features and better integration!
