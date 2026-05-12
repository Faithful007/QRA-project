# FDS Project Setup GUI - User Guide

## Overview

The **FDS Project Setup GUI** is an interactive PyQt5 application that creates an organized directory structure for FDS (Fire Dynamics Simulator) projects. It provides a user-friendly interface for setting up the complete folder hierarchy needed for tunnel fire risk assessment and QRA analysis.

## Features

✅ **Interactive Interface**
- Clean, modern PyQt5 GUI
- Real-time directory structure preview
- Progress tracking during creation
- Error handling and validation

✅ **Customizable Setup**
- Enter custom project name
- Select any home directory location
- Preview full project path before creation
- Confirmation for existing directories

✅ **Complete Directory Structure**
```
project_name/
├── fds_inputs/          # Generated FDS input files
│   ├── 020/            # 20 MW scenarios
│   ├── 030/            # 30 MW scenarios
│   └── 100/            # 100 MW scenarios
├── fds_outputs/         # FDS simulation outputs (.smv, .out, etc.)
├── fdb_files/           # Converted FDB files for EVC
├── logs/                # Workflow logs
└── run_all_simulations.bat  # Batch script for manual execution
```

✅ **Convenience Features**
- Open project folder button
- Status messages and progress bar
- Tree view of directory structure
- Cross-platform support (Windows, Linux, macOS)

## Installation

### Prerequisites

```bash
pip install PyQt5
```

### Files Required

- `project_setup_gui.py` - Main GUI module
- `launch_project_setup.py` - Launcher script (optional)

## Usage

### Method 1: Run Directly

```bash
python project_setup_gui.py
```

### Method 2: Use Launcher

```bash
python launch_project_setup.py
```

### Method 3: Import in Code

```python
from project_setup_gui import ProjectSetupGUI
from PyQt5.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
window = ProjectSetupGUI()
window.show()
sys.exit(app.exec_())
```

## Step-by-Step Guide

### 1. Launch the Application

Run the GUI using one of the methods above. The main window will appear with the following sections:

- **Project Configuration** - Input fields
- **Directory Structure Preview** - Tree view
- **Creation Progress** - Status and progress bar
- **Action Buttons** - Create, Open, Close

### 2. Enter Project Name

In the "Project Name" field, enter a descriptive name for your project.

**Examples:**
- `TunnelFireQRA_2026`
- `Highway_Tunnel_Risk_Assessment`
- `Metro_Tunnel_FDS_Study`

**Tips:**
- Use alphanumeric characters and underscores
- Avoid spaces and special characters
- Be descriptive for easy identification

### 3. Select Home Directory

Click the **"Browse..."** button to open a directory selection dialog.

**Recommended Locations:**
- Windows: `C:\Users\YourName\Documents\FDS_Projects`
- Linux: `/home/username/fds_projects`
- macOS: `/Users/username/Documents/FDS_Projects`

Or manually enter the path in the text field.

### 4. Preview Structure

As you enter the project name and home directory, the **Directory Structure Preview** updates in real-time, showing:

- Complete folder hierarchy
- Comments explaining each directory's purpose
- Full project path display

### 5. Create Project Structure

Click the **"Create Project Structure"** button.

The application will:
1. Validate inputs
2. Check if directory exists (asks for confirmation if it does)
3. Create all directories
4. Generate batch script template
5. Show progress in real-time
6. Display success message

### 6. Open Project Folder

After successful creation, the **"Open Project Folder"** button becomes enabled.

Click it to open the newly created project directory in your system's file explorer.

## GUI Components

### Project Configuration Section

| Field | Description | Required |
|-------|-------------|----------|
| **Project Name** | Name of your FDS project | Yes |
| **Home Directory** | Parent directory location | Yes |
| **Full Project Path** | Auto-calculated full path | Read-only |

### Directory Structure Preview

- **Tree Widget** showing complete folder hierarchy
- **Expandable nodes** for nested directories
- **Comments** explaining each directory's purpose

### Creation Progress Section

- **Progress Bar** - Visual progress indicator (0-100%)
- **Status Text** - Detailed log of creation steps
- **Auto-scrolling** to show latest messages

### Action Buttons

| Button | Function | When Enabled |
|--------|----------|--------------|
| **Create Project Structure** | Creates directories | When name and path are valid |
| **Open Project Folder** | Opens folder in explorer | After successful creation |
| **Close** | Exits application | Always |

## Directory Structure Details

### fds_inputs/

Contains generated FDS input files organized by HRR (Heat Release Rate):

- **020/** - 20 MW fire scenarios
- **030/** - 30 MW fire scenarios
- **100/** - 100 MW fire scenarios

Each HRR directory will contain subdirectories for:
- Traffic conditions (Normal/Congested)
- Ventilation conditions (NVC/NV0/FV0)

### fds_outputs/

Stores FDS simulation output files:
- `.smv` - Smokeview files
- `.out` - Text output logs
- `_devc.csv` - Device output data
- `_*.sf` - Slice files
- `_hrr.csv` - Heat release rate data

### fdb_files/

Contains converted FDB (Fire Database) files:
- Binary format files
- Time-series environmental data
- Input for EVC evacuation simulation

### logs/

Workflow execution logs:
- JSON format logs
- Timestamp-based filenames
- Complete workflow history

### run_all_simulations.bat

Batch script for running FDS simulations:
- Auto-generated template
- Populated when input files are created
- Manual execution option

## Error Handling

### Common Issues

**Issue:** "Missing Information" warning

**Solution:** Ensure both project name and home directory are filled in.

---

**Issue:** "Directory Exists" warning

**Solution:** Choose to continue (merge) or cancel and use a different name.

---

**Issue:** "Failed to create directory structure"

**Possible Causes:**
- Insufficient permissions
- Invalid path characters
- Disk space full

**Solution:** Check permissions, use valid path, ensure disk space.

---

**Issue:** GUI doesn't start

**Solution:**
```bash
# Check PyQt5 installation
pip install --upgrade PyQt5

# Test import
python -c "from PyQt5.QtWidgets import QApplication"
```

## Integration with FDS Workflow

After creating the project structure, use it with the FDS workflow system:

```python
from fds_workflow import FDSWorkflow

# Use the created project directory
workflow = FDSWorkflow(
    project_dir="/path/to/your/project_name",
    fds_executable="fds"
)

# Define scenarios
workflow.define_scenarios(...)

# Generate inputs (will use fds_inputs/ directory)
workflow.generate_inputs()

# Run simulations (outputs to fds_outputs/)
workflow.run_simulations()

# Convert to FDB (saves to fdb_files/)
workflow.convert_to_fdb()
```

## Customization

### Modify Directory Structure

Edit the `DirectoryCreationThread.run()` method in `project_setup_gui.py`:

```python
directories = [
    "fds_inputs/020",
    "fds_inputs/030",
    "fds_inputs/100",
    "fds_outputs",
    "fdb_files",
    "logs",
    # Add your custom directories here
    "custom_dir",
    "another_dir/subdir"
]
```

### Change GUI Appearance

Modify the stylesheet in `init_ui()`:

```python
self.create_btn.setStyleSheet("""
    QPushButton {
        background-color: #your_color;
        color: white;
        font-size: 14px;
    }
""")
```

### Add Additional Features

Extend the `ProjectSetupGUI` class:

```python
def your_custom_method(self):
    # Add custom functionality
    pass
```

## Screenshots

### Main Window
- Project configuration inputs
- Directory structure preview
- Progress tracking

### Directory Browser
- System file dialog
- Navigate to desired location
- Select home directory

### Success Message
- Confirmation dialog
- Project location display
- Open folder option

## Tips and Best Practices

1. **Naming Convention**
   - Use descriptive project names
   - Include year or version number
   - Avoid spaces and special characters

2. **Location Selection**
   - Choose a location with sufficient disk space
   - Use a backed-up drive
   - Consider network drives for team projects

3. **Organization**
   - Create one project per tunnel/study
   - Group related projects in parent folder
   - Document project purpose in README

4. **Workflow Integration**
   - Create structure before generating FDS inputs
   - Use consistent naming across projects
   - Keep logs for reproducibility

## Troubleshooting

### GUI Doesn't Display Correctly

**Windows:**
```bash
# Set Qt platform plugin
set QT_QPA_PLATFORM=windows
python project_setup_gui.py
```

**Linux:**
```bash
# Install Qt dependencies
sudo apt-get install python3-pyqt5
```

### Permission Errors

**Windows:** Run as Administrator

**Linux/Mac:**
```bash
chmod +x project_setup_gui.py
chmod +x launch_project_setup.py
```

### Import Errors

```bash
# Reinstall PyQt5
pip uninstall PyQt5
pip install PyQt5
```

## Advanced Usage

### Batch Creation

Create multiple projects programmatically:

```python
from project_setup_gui import DirectoryCreationThread
from PyQt5.QtCore import QCoreApplication

app = QCoreApplication([])

projects = [
    ("Tunnel_A", "/home/user/projects"),
    ("Tunnel_B", "/home/user/projects"),
    ("Tunnel_C", "/home/user/projects")
]

for name, path in projects:
    thread = DirectoryCreationThread(path, name)
    thread.run()  # Synchronous execution
    print(f"Created: {name}")
```

### Command-Line Interface

Create a CLI wrapper:

```python
import argparse
from pathlib import Path
from project_setup_gui import DirectoryCreationThread

parser = argparse.ArgumentParser()
parser.add_argument("name", help="Project name")
parser.add_argument("path", help="Home directory")
args = parser.parse_args()

thread = DirectoryCreationThread(args.path, args.name)
thread.run()
```

Usage:
```bash
python cli_setup.py "MyProject" "/home/user/projects"
```

## Support

For issues or questions:
1. Check this documentation
2. Review error messages in status text
3. Verify PyQt5 installation
4. Check file permissions

## Version History

**v1.0.0** (February 2026)
- Initial release
- Interactive GUI
- Real-time preview
- Progress tracking
- Cross-platform support

## License

This software is provided for educational and research purposes.

---

**Module:** project_setup_gui.py  
**Lines of Code:** ~400  
**Dependencies:** PyQt5  
**Platform:** Windows, Linux, macOS
