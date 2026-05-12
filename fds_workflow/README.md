# FDS Workflow System

A comprehensive Python-based workflow system for generating FDS (Fire Dynamics Simulator) input files, running simulations, and converting outputs to FDB format for QRA (Quantitative Risk Assessment) analysis.

## 📋 Overview

This system automates the complete workflow for tunnel fire risk assessment:

```
1. FDS Input Generation → 2. FDS Simulation → 3. SMV to FDB Conversion → 4. QRA Analysis
```

## 🏗️ System Architecture

### Components

1. **fds_generator.py** - Generates FDS input files for various fire scenarios
2. **fds_runner.py** - Executes FDS simulations and monitors progress
3. **smv_to_fdb_converter.py** - Converts SMV output files to FDB format
4. **fds_workflow.py** - Orchestrates the complete workflow

### Directory Structure

```
project_dir/
├── fds_inputs/          # Generated FDS input files
│   ├── 020/            # 20 MW scenarios
│   ├── 030/            # 30 MW scenarios
│   └── 100/            # 100 MW scenarios
├── fds_outputs/         # FDS simulation outputs (.smv, .out, etc.)
├── fdb_files/           # Converted FDB files for EVC
├── logs/                # Workflow logs
└── run_all_simulations.bat  # Batch script for manual execution
```

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+** with required packages:
   ```bash
   pip install numpy
   ```

2. **FDS (Fire Dynamics Simulator)** installed and in PATH
   - Download from: https://pages.nist.gov/fds-smv/
   - Or specify full path in configuration

### Basic Usage

```python
from fds_workflow import FDSWorkflow

# Create workflow
workflow = FDSWorkflow(
    project_dir="./my_qra_project",
    fds_executable="fds"  # or full path to fds.exe
)

# Define scenarios
workflow.define_scenarios(
    hrr_types=[("020", 20000), ("030", 30000), ("100", 100000)],
    fire_positions=[500, 1000, 1500],
    traffic_conditions=["Normal", "Congested"],
    ventilation_conditions=["NVC", "NV0", "FV0"]
)

# Run complete workflow
workflow.run_complete_workflow()
```

### Command Line Usage

```bash
# Run complete workflow
python fds_workflow.py

# Generate input files only
python fds_generator.py

# Run simulations only
python fds_runner.py

# Convert SMV to FDB
python smv_to_fdb_converter.py
```

## 📖 Detailed Usage

### 1. FDS Input Generation

Generate FDS input files for tunnel fire scenarios:

```python
from fds_generator import FDSInputGenerator, TunnelGeometry, FireScenario

# Define tunnel geometry
tunnel = TunnelGeometry(
    name="GUMOK",
    radius=7.2,
    length=2000.0,
    ix=2500,  # Grid cells in X
    iy=36,    # Grid cells in Y
    iz=26     # Grid cells in Z
)

# Create generator
generator = FDSInputGenerator(tunnel)

# Define a fire scenario
scenario = FireScenario(
    hrr_type="020",
    hrr_value=20000,  # kW
    fire_position=1000,  # meters
    flashover_time=450,  # seconds
    traffic_condition="Normal",
    ventilation_condition="NVC"
)

# Generate FDS input file
generator.generate_fds_input(scenario, "output.fds")
```

**Scenario Parameters:**

| Parameter | Description | Options |
|-----------|-------------|---------|
| `hrr_type` | Fire size code | "020", "030", "100" |
| `hrr_value` | Heat release rate | 20000, 30000, 100000 kW |
| `fire_position` | Location along tunnel | 0 to 2000 meters |
| `flashover_time` | Time to full HRR | 360 or 450 seconds |
| `traffic_condition` | Traffic density | "Normal", "Congested" |
| `ventilation_condition` | Ventilation state | "NVC", "NV0", "FV0", "FVM", "FVP" |

### 2. Running FDS Simulations

Execute FDS simulations:

```python
from fds_runner import FDSRunner

# Create runner
runner = FDSRunner(fds_executable="fds")

# Check if FDS is available
if runner.check_fds_available():
    # Run single simulation
    result = runner.run_simulation("input.fds")
    
    # Run batch of simulations
    input_files = ["sim1.fds", "sim2.fds", "sim3.fds"]
    results = runner.run_batch(input_files)
```

**Batch Script Generation:**

```python
from fds_runner import create_batch_script

input_files = glob.glob("./fds_inputs/**/*.fds", recursive=True)
create_batch_script(input_files, "run_all.bat")
```

### 3. SMV to FDB Conversion

Convert FDS outputs to FDB format:

```python
from smv_to_fdb_converter import SMVtoFDBConverter

# Convert single file
converter = SMVtoFDBConverter("simulation.smv", "output.fdb")
converter.convert(sample_height=1.7)

# Convert entire directory
from smv_to_fdb_converter import convert_directory
convert_directory("./fds_outputs", "./fdb_files")
```

**FDB File Format:**

The FDB file contains time-series data at a specified height (default 1.7m):
- Temperature (°C)
- CO concentration (ppm)
- CO₂ concentration (%)
- O₂ concentration (%)
- Visibility (m)

### 4. Complete Workflow

Run the entire workflow automatically:

```python
from fds_workflow import FDSWorkflow

workflow = FDSWorkflow("./project")

# Define scenarios
workflow.define_scenarios(
    hrr_types=[("020", 20000), ("030", 30000)],
    fire_positions=[500, 1000, 1500],
    traffic_conditions=["Normal", "Congested"],
    ventilation_conditions=["NVC", "NV0"]
)

# Generate inputs
workflow.generate_inputs()

# Run simulations (creates batch script if FDS not available)
workflow.run_simulations(create_batch=True)

# Convert to FDB
workflow.convert_to_fdb()
```

## 🔧 Configuration

### Tunnel Geometry

Modify tunnel parameters in `fds_generator.py`:

```python
@dataclass
class TunnelGeometry:
    name: str = "GUMOK"
    radius: float = 7.2  # meters
    length: float = 2000.0  # meters
    ix: int = 2500  # X grid cells
    iy: int = 36    # Y grid cells
    iz: int = 26    # Z grid cells
```

### Fire Scenarios

Customize fire parameters:

```python
@dataclass
class FireScenario:
    hrr_type: str
    hrr_value: float  # kW
    fire_position: float  # meters
    flashover_time: int  # seconds
    traffic_condition: str
    ventilation_condition: str
    bus_length: float = 12.0  # meters
    bus_width: float = 2.8  # meters
    bus_height: float = 3.5  # meters
```

## 📊 Output Files

### FDS Input Files (.fds)

Generated FDS input files contain:
- Mesh definition
- Tunnel geometry (arched roof)
- Fire source with growth ramp
- Material properties
- Output devices

### FDS Output Files

FDS generates:
- `.smv` - Smokeview file (metadata)
- `.out` - Text output with simulation progress
- `_devc.csv` - Device output data
- `_*.sf` - Slice files (3D data)
- `_hrr.csv` - Heat release rate data

### FDB Files (.fdb)

Binary files containing:
- Header with grid information
- Time-series data for:
  - Temperature
  - CO, CO₂, O₂ concentrations
  - Visibility

## 🔍 Monitoring and Logging

### Simulation Progress

Monitor running simulations:

```python
runner = FDSRunner()
status = runner.monitor_simulation(working_dir, chid)
print(f"Progress: {status['progress']}%")
```

### Workflow Logs

Workflow logs are saved in JSON format:

```json
{
  "project_dir": "./project",
  "fds_executable": "fds",
  "scenario_count": 108,
  "events": [
    {
      "timestamp": "2026-02-04T10:30:00",
      "event": "scenarios_defined",
      "data": {"count": 108}
    },
    ...
  ]
}
```

## 🎯 Example Scenarios

### Minimal Test (2 scenarios)

```python
workflow.define_scenarios(
    hrr_types=[("020", 20000)],
    fire_positions=[1000],
    flashover_times=[450],
    traffic_conditions=["Normal"],
    ventilation_conditions=["NVC"]
)
```

### Standard QRA (108 scenarios)

```python
workflow.define_scenarios(
    hrr_types=[("020", 20000), ("030", 30000), ("100", 100000)],
    fire_positions=[500, 750, 1000, 1250, 1500, 1750],
    flashover_times=[450],
    traffic_conditions=["Normal", "Congested"],
    ventilation_conditions=["NVC", "NV0", "FV0"]
)
# 3 HRR × 6 positions × 2 traffic × 3 ventilation = 108 scenarios
```

### Comprehensive Study (216 scenarios)

```python
workflow.define_scenarios(
    hrr_types=[("020", 20000), ("030", 30000), ("100", 100000)],
    fire_positions=[500, 750, 1000, 1250, 1500, 1750],
    flashover_times=[360, 450],  # Fast and medium growth
    traffic_conditions=["Normal", "Congested"],
    ventilation_conditions=["NVC", "NV0", "FV0"]
)
# 3 HRR × 6 positions × 2 flashover × 2 traffic × 3 ventilation = 216 scenarios
```

## 🐛 Troubleshooting

### FDS Not Found

```
⚠ FDS executable not found
```

**Solution:** 
- Install FDS from https://pages.nist.gov/fds-smv/
- Add FDS to system PATH
- Or specify full path: `FDSRunner(fds_executable="C:/Program Files/FDS/fds.exe")`

### Simulation Fails

Check the `.out` file in the output directory for error messages.

Common issues:
- Grid too coarse/fine
- Time step too large
- Memory issues

### SMV Files Not Found

Ensure FDS simulations completed successfully before conversion.

Check:
- `.out` file ends with "STOP: FDS completed successfully"
- `.smv` file exists in output directory

### FDB Conversion Errors

The SMV to FDB converter is a simplified implementation. For production use:
- Use the original `FDSCFDB.EXE` utility
- Or implement full binary SMV file parser

## 📚 References

1. **FDS Documentation:** https://pages.nist.gov/fds-smv/
2. **FDS User Guide:** NIST Special Publication 1019
3. **FDS Technical Reference:** NIST Special Publication 1018
4. **QRA Methodology:** See `QRA_System_Analysis_Report.md`

## 🤝 Integration with QRA System

The FDB files generated by this workflow are used as inputs to the EVC (Evacuation) simulation:

```
FDS → FDB → EVC → FED → QRA
```

See the PyQt5 QRA application (`qra_app/`) for the complete risk analysis workflow.

## 📝 License

This software is provided for educational and research purposes.

## 👥 Author

Manus AI - February 2026

## 🔄 Version

Version 1.0.0 - Initial Release
