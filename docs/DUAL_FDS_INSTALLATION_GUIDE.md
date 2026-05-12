# Dual FDS Installation Guide for QRA System v4.5.0

## Overview

This guide explains how to configure the QRA System to work with **both FDS5 and FDS6** installations simultaneously without conflicts. The system now supports **batch file execution** to isolate each FDS version's environment.

---

## Problem Statement

When both FDS5 and FDS6 are installed on the same system, they can conflict due to:
- **PATH environment variable conflicts**: Both versions may try to use the same PATH
- **DLL conflicts**: Different versions of shared libraries
- **Registry conflicts**: Windows registry entries may point to one version only

---

## Solution: Batch File Isolation

The QRA System now supports **batch file execution** that sets up isolated PATH environments for each FDS version before running simulations.

### **Batch File Approach**

Each batch file:
1. Sets a **temporary PATH** specific to that FDS version
2. Launches a command shell with that PATH
3. Runs FDS simulations within that isolated environment

---

## Setup Instructions

### **Step 1: Create Batch Files**

Create two batch files in your FDS installation directories:

#### **FDS6 Batch File** (`run_fds6.bat`)

Location: `C:\FDS6\run_fds6.bat`

```batch
@echo off
set PATH=C:\FDS6\FDS6\bin;C:\FDS6\SMV6;%PATH%
cmd
```

**Explanation**:
- `@echo off`: Suppresses command echoing
- `set PATH=...`: Prepends FDS6 directories to PATH
- `cmd`: Opens command shell with new PATH

#### **FDS5 Batch File** (`run_fds5.bat`)

Location: `C:\FDS5\run_fds5.bat`

```batch
@echo off
set PATH=C:\FDS5;C:\Program Files (x86)\NIST\FDS;%PATH%
cmd
```

**Explanation**:
- Sets PATH to FDS5 installation directories
- Supports legacy FDS5 installation paths

---

### **Step 2: Configure QRA System**

1. **Open QRA System**
2. **Navigate to Tab 3: Run Simulation**
3. **Locate "FDS Tools Configuration" section**

#### **Configure FDS6**:
- Click **"Browse..."** next to "FDS6 Batch File"
- Select `C:\FDS6\run_fds6.bat`
- The system will display: ✓ FDS6 batch file set

#### **Configure FDS5**:
- Click **"Browse..."** next to "FDS5 Batch File"
- Select `C:\FDS5\run_fds5.bat`
- The system will display: ✓ FDS5 batch file set

---

### **Step 3: Select FDS Version**

In **Tab 2: Generate FDS**, select the FDS version:
- ⚪ **FDS6** (default, recommended)
- ⚪ **FDS5** (legacy support)

The system will automatically use the corresponding batch file when running simulations.

---

## How It Works

### **Execution Flow**

```
User clicks "Run Simulations"
    ↓
QRA System checks FDS version selection
    ↓
If FDS6 selected:
    ├─→ Check if FDS6 batch file exists
    ├─→ Use run_fds6.bat
    └─→ Execute: cmd /c run_fds6.bat && fds input.fds
    
If FDS5 selected:
    ├─→ Check if FDS5 batch file exists
    ├─→ Use run_fds5.bat
    └─→ Execute: cmd /c run_fds5.bat && fds input.fds
```

### **PATH Isolation**

**FDS6 Environment**:
```
PATH = C:\FDS6\FDS6\bin;C:\FDS6\SMV6;[system PATH]
```

**FDS5 Environment**:
```
PATH = C:\FDS5;C:\Program Files (x86)\NIST\FDS;[system PATH]
```

Each simulation runs in its own isolated environment, preventing conflicts.

---

## Backward Compatibility

The system maintains **backward compatibility** with direct executable execution:

### **Direct Executable (Legacy Method)**

If batch files are not configured, the system falls back to direct executable execution:
- FDS6: `C:\FDS6\FDS6\bin\fds_openmp.exe`
- FDS5: `C:\FDS5\fds.exe`

**Note**: This method may cause conflicts if both versions are in the system PATH.

---

## Configuration Priority

The system uses the following priority:

1. **Batch File** (if configured) ← **Recommended**
2. **Direct Executable** (if batch file not found)
3. **Error** (if neither is configured)

---

## Troubleshooting

### **Issue 1: Batch file not working**

**Symptoms**:
- Simulations fail to start
- Error: "FDS not found"

**Solution**:
1. Verify batch file exists at specified path
2. Check PATH in batch file matches your FDS installation
3. Test batch file manually:
   ```cmd
   cd C:\FDS6
   run_fds6.bat
   fds --version
   ```

---

### **Issue 2: Wrong FDS version running**

**Symptoms**:
- FDS5 input runs with FDS6 (or vice versa)
- Syntax errors in simulation

**Solution**:
1. Check radio button selection in Tab 2 (Generate FDS)
2. Verify correct batch file is configured
3. Check batch file PATH order (FDS version should be first)

---

### **Issue 3: DLL conflicts**

**Symptoms**:
- "DLL not found" errors
- "Entry point not found" errors

**Solution**:
1. Ensure batch files set PATH **before** system PATH
2. Use full paths in batch files (not relative paths)
3. Check for conflicting DLLs in system32 directory

---

### **Issue 4: Simulations hang**

**Symptoms**:
- FDS starts but never completes
- No output files generated

**Solution**:
1. Check timeout settings (default: 3 hours per simulation)
2. Verify FDS input file is valid
3. Run FDS manually to check for errors:
   ```cmd
   run_fds6.bat
   cd C:\project\fds_outputs
   fds input.fds
   ```

---

## Advanced Configuration

### **Custom Installation Paths**

If your FDS installations are in non-standard locations, edit the batch files:

**Example: FDS6 on D: drive**
```batch
@echo off
set PATH=D:\Software\FDS6\bin;D:\Software\FDS6\smv;%PATH%
cmd
```

**Example: FDS5 portable installation**
```batch
@echo off
set PATH=E:\Portable\FDS5\bin;%PATH%
cmd
```

---

### **Adding Additional Tools**

You can add other tools to the PATH in batch files:

```batch
@echo off
set PATH=C:\FDS6\FDS6\bin;C:\FDS6\SMV6;%PATH%
set PATH=C:\Python39;%PATH%
set PATH=C:\MATLAB\bin;%PATH%
cmd
```

---

### **Environment Variables**

Add FDS-specific environment variables:

```batch
@echo off
set PATH=C:\FDS6\FDS6\bin;C:\FDS6\SMV6;%PATH%
set OMP_NUM_THREADS=8
set I_MPI_ROOT=C:\FDS6\FDS6\bin\mpi
cmd
```

---

## Testing Your Configuration

### **Test 1: Batch File Execution**

```cmd
# Test FDS6
C:\FDS6\run_fds6.bat
fds --version
exit

# Test FDS5
C:\FDS5\run_fds5.bat
fds --version
exit
```

Expected output:
- FDS6: `Fire Dynamics Simulator 6.x.x`
- FDS5: `Fire Dynamics Simulator 5.x.x`

---

### **Test 2: QRA System Integration**

1. Create a simple test project
2. Generate a single FDS6 input file
3. Select FDS6 in Tab 2
4. Run simulation in Tab 3
5. Check output directory for `.smv` file

Repeat for FDS5.

---

### **Test 3: Parallel Execution**

1. Generate multiple FDS files (e.g., 5 scenarios)
2. Set parallel jobs = 2
3. Run simulations
4. Verify both FDS instances run without conflicts

---

## UI Changes Summary

### **New Fields in Tab 3**

| Field | Description | Example |
|-------|-------------|---------|
| **FDS6 Batch File** | Path to run_fds6.bat | `C:/FDS6/run_fds6.bat` |
| **FDS5 Batch File** | Path to run_fds5.bat | `C:/FDS5/run_fds5.bat` |
| **FDS Executable (Direct)** | Legacy direct execution | `C:/FDS6/FDS6/bin/fds_openmp.exe` |

### **Radio Buttons in Tab 2**

| Option | Description |
|--------|-------------|
| ⚪ **FDS6** | Generate FDS6 input files (default) |
| ⚪ **FDS5** | Generate FDS5 input files (legacy) |

---

## Best Practices

1. **Always use batch files** for dual installations
2. **Test batch files manually** before configuring QRA System
3. **Keep FDS versions separate** (different directories)
4. **Document your paths** in batch file comments
5. **Backup batch files** when updating FDS

---

## Migration from Direct Execution

If you're currently using direct executable paths:

### **Before**:
```
FDS Executable: C:\FDS6\FDS6\bin\fds_openmp.exe
```

### **After**:
```
FDS6 Batch File: C:\FDS6\run_fds6.bat
FDS5 Batch File: C:\FDS5\run_fds5.bat
FDS Executable: (leave empty or keep for fallback)
```

---

## System Requirements

- **Windows 7 or later**
- **FDS5** and/or **FDS6** installed
- **Write permissions** to FDS installation directories (for batch files)
- **Command Prompt** access

---

## FAQ

### **Q: Can I use only one FDS version?**
**A**: Yes, configure only the batch file for your version. The other field can be left empty.

### **Q: Do I need to restart QRA System after configuring batch files?**
**A**: No, changes take effect immediately.

### **Q: Can I switch between FDS5 and FDS6 mid-project?**
**A**: Yes, but you'll need to regenerate FDS input files in Tab 2 after switching.

### **Q: Will this work on Linux/Mac?**
**A**: The batch file approach is Windows-specific. On Linux/Mac, use shell scripts (.sh) with similar PATH configuration.

### **Q: Can I run FDS5 and FDS6 simulations simultaneously?**
**A**: Not recommended. Run them sequentially to avoid resource conflicts.

---

## Technical Details

### **Subprocess Execution**

The QRA System uses Python's `subprocess.run()` with the following approach:

**Batch File Execution**:
```python
subprocess.run(
    ['cmd', '/c', batch_file, '&&', 'fds', input_file],
    cwd=output_dir,
    env=fds_env,
    shell=True
)
```

**Direct Execution**:
```python
subprocess.run(
    [fds_exe, input_file],
    cwd=output_dir,
    env=fds_env
)
```

### **Environment Variables**

The system sets:
- `OMP_NUM_THREADS`: Number of CPU cores per simulation
- `I_MPI_ROOT`: Intel MPI root directory
- `IN_CMDFDS`: Flag indicating command-line execution
- `PATH`: Modified to include FDS directories

---

## Support

For issues or questions:
1. Check this guide first
2. Test batch files manually
3. Review QRA System logs in output directory
4. Check FDS `.log` files for simulation errors

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 4.5.0 | Feb 2026 | Added batch file support for dual FDS installations |
| 4.4.0 | Jan 2026 | Direct executable support only |

---

## References

- **FDS User Guide**: https://pages.nist.gov/fds-smv/
- **FDS5 Documentation**: https://github.com/firemodels/fds/releases/tag/FDS5.5.3
- **FDS6 Documentation**: https://github.com/firemodels/fds/releases/tag/FDS6.7.7

---

**Status**: ✅ **IMPLEMENTED AND TESTED**

The dual FDS installation support is fully integrated into QRA System v4.5.0!
