# FDS Workflow System - Installation Guide

## 📦 System Requirements

### Software Requirements

1. **Python 3.8 or higher**
   - Download: https://www.python.org/downloads/

2. **NumPy** (Python package)
   ```bash
   pip install numpy
   ```

3. **FDS (Fire Dynamics Simulator)** - Optional but recommended
   - Download: https://pages.nist.gov/fds-smv/
   - Version 6.7.5 or higher recommended

### Hardware Requirements

- **CPU:** Multi-core processor (4+ cores recommended for parallel simulations)
- **RAM:** 8 GB minimum, 16 GB+ recommended
- **Disk Space:** 10 GB+ for simulation outputs
- **OS:** Windows, Linux, or macOS

## 🚀 Installation Steps

### Step 1: Extract Package

```bash
# Extract the archive
tar -xzf fds_workflow_system.tar.gz

# Navigate to directory
cd fds_workflow
```

### Step 2: Install Python Dependencies

```bash
pip install numpy
```

Or if you have a `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Step 3: Install FDS (Optional)

**Windows:**
1. Download FDS installer from https://pages.nist.gov/fds-smv/
2. Run installer and follow instructions
3. Add FDS to system PATH or note installation directory

**Linux:**
```bash
# Download FDS
wget https://github.com/firemodels/fds/releases/download/FDS6.7.7/FDS6.7.7_linux.tar.gz

# Extract
tar -xzf FDS6.7.7_linux.tar.gz

# Add to PATH
export PATH=$PATH:/path/to/fds/bin
```

**macOS:**
```bash
# Download and install from https://pages.nist.gov/fds-smv/
# Or use Homebrew (if available)
```

### Step 4: Verify Installation

```bash
# Test Python modules
python3 -c "import numpy; print('NumPy OK')"

# Test FDS (if installed)
fds

# Test workflow
python3 test_workflow.py
```

## 🔧 Configuration

### Configure FDS Executable Path

If FDS is not in your system PATH, edit the workflow script:

```python
# In fds_workflow.py or your script
workflow = FDSWorkflow(
    project_dir="./my_project",
    fds_executable="/full/path/to/fds"  # Specify full path
)
```

**Windows example:**
```python
fds_executable="C:/Program Files/FDS/FDS6/bin/fds.exe"
```

**Linux example:**
```python
fds_executable="/opt/fds/bin/fds"
```

### Configure Tunnel Geometry

Edit `fds_generator.py` to customize tunnel parameters:

```python
@dataclass
class TunnelGeometry:
    name: str = "YOUR_TUNNEL_NAME"
    radius: float = 7.2  # meters
    length: float = 2000.0  # meters
    # ... other parameters
```

## 📝 Quick Start After Installation

### 1. Generate FDS Input Files

```python
from fds_workflow import FDSWorkflow

workflow = FDSWorkflow("./my_project")
workflow.define_scenarios(
    hrr_types=[("020", 20000)],
    fire_positions=[1000],
    traffic_conditions=["Normal"],
    ventilation_conditions=["NVC"]
)
workflow.generate_inputs()
```

### 2. Run Simulations

**Option A: Using Python (if FDS installed)**
```python
workflow.run_simulations()
```

**Option B: Using Batch Script**
```bash
# Batch script is auto-generated
./run_all_simulations.bat  # Windows
# or
bash run_all_simulations.sh  # Linux/Mac
```

### 3. Convert Outputs

```python
workflow.convert_to_fdb()
```

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'numpy'"

**Solution:**
```bash
pip install numpy
```

### Issue: "FDS executable not found"

**Solution:**
1. Install FDS from https://pages.nist.gov/fds-smv/
2. Add FDS to PATH, or
3. Specify full path in configuration

### Issue: "Permission denied" on Linux/Mac

**Solution:**
```bash
chmod +x *.py
```

### Issue: Import errors between modules

**Solution:**
Ensure all Python files are in the same directory:
```
fds_workflow/
├── fds_generator.py
├── fds_runner.py
├── smv_to_fdb_converter.py
├── fds_workflow.py
└── test_workflow.py
```

## 📚 Next Steps

1. Read `README.md` for detailed usage instructions
2. Run `test_workflow.py` to verify installation
3. Customize scenarios for your project
4. Integrate with QRA application (`qra_app/`)

## 🆘 Support

For issues or questions:
1. Check `README.md` for detailed documentation
2. Review example scripts in the package
3. Consult FDS documentation: https://pages.nist.gov/fds-smv/

## 📄 License

This software is provided for educational and research purposes.

---

**Version:** 1.0.0  
**Last Updated:** February 2026
