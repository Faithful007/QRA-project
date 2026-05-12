# Quick Start Guide - FDS Project Setup GUI

## 🚀 Get Started in 3 Steps

### Step 1: Install PyQt5

```bash
pip install PyQt5
```

### Step 2: Run the GUI

```bash
python project_setup_gui.py
```

Or use the launcher:

```bash
python launch_project_setup.py
```

### Step 3: Create Your Project

1. **Enter Project Name** (e.g., "TunnelFireQRA_2026")
2. **Click "Browse..."** and select home directory
3. **Click "Create Project Structure"**
4. **Done!** Click "Open Project Folder" to view

## 📁 What Gets Created

```
your_project_name/
├── fds_inputs/
│   ├── 020/          # 20 MW scenarios
│   ├── 030/          # 30 MW scenarios
│   └── 100/          # 100 MW scenarios
├── fds_outputs/      # Simulation results
├── fdb_files/        # Converted FDB files
├── logs/             # Workflow logs
└── run_all_simulations.bat
```

## 💡 Tips

- Use descriptive project names
- Choose a location with plenty of disk space
- The directory structure is ready for FDS workflow integration

## 🔗 Next Steps

After creating the project structure:

```python
from fds_workflow import FDSWorkflow

# Use your new project directory
workflow = FDSWorkflow(
    project_dir="/path/to/your_project_name"
)

# Continue with FDS workflow...
workflow.define_scenarios(...)
workflow.generate_inputs()
```

## 📖 Full Documentation

See `PROJECT_SETUP_GUI.md` for complete documentation.

## ❓ Troubleshooting

**GUI doesn't start?**
```bash
pip install --upgrade PyQt5
```

**Permission error?**
- Windows: Run as Administrator
- Linux/Mac: Check folder permissions

## 🎯 Example

```bash
# 1. Launch GUI
python project_setup_gui.py

# 2. In the GUI:
#    - Project Name: "Highway_Tunnel_Study"
#    - Home Directory: "C:\Users\YourName\Documents"
#    - Click "Create Project Structure"

# 3. Result:
#    C:\Users\YourName\Documents\Highway_Tunnel_Study\
#    (with complete directory structure)
```

That's it! Your FDS project is ready to go! 🎉
