# FDS Version Enforcement Feature

## Overview

The QRA System now includes **automatic FDS version enforcement** to prevent incompatible combinations of FDS input files and executables. This critical safety feature ensures that:

- **FDS6 input files** only run with **FDS6 executables**
- **FDS5 input files** only run with **FDS5 executables**

---

## Why This Matters

### **The Problem**

FDS5 and FDS6 have **incompatible input file formats**:

| Issue | Description |
|-------|-------------|
| **Syntax Differences** | FDS6 uses different namelist syntax than FDS5 |
| **New Features** | FDS6 has features not available in FDS5 |
| **Deprecated Features** | FDS5 features may not work in FDS6 |
| **Runtime Errors** | Running FDS5 input with FDS6 (or vice versa) causes crashes |

### **The Solution**

The system **automatically enforces version matching** based on your selection in Tab 2.

---

## How It Works

### **Step 1: Select FDS Version (Tab 2)**

When you select an FDS version in **Tab 2: Generate FDS**:

```
⚪ FDS 6  (default, recommended)
⚪ FDS 5  (legacy support)
```

The system immediately:
1. **Enables** the corresponding batch file field in Tab 3
2. **Disables** the incompatible batch file field
3. **Highlights** the active field with color coding
4. **Displays** status messages confirming the selection

---

### **Step 2: Visual Indicators (Tab 3)**

The batch file fields in **Tab 3: FDS Simulation** change appearance:

#### **When FDS6 is Selected**:

```
┌─ FDS Tools Configuration ─────────────────────┐
│                                                │
│ FDS6 Batch File: [___________________] [Browse...] │
│   ↑ GREEN highlight - ACTIVE                   │
│                                                │
│ FDS5 Batch File: [___________________] [Browse...] │
│   ↑ GRAY dimmed - DISABLED                     │
│                                                │
└────────────────────────────────────────────────┘
```

#### **When FDS5 is Selected**:

```
┌─ FDS Tools Configuration ─────────────────────┐
│                                                │
│ FDS6 Batch File: [___________________] [Browse...] │
│   ↑ GRAY dimmed - DISABLED                     │
│                                                │
│ FDS5 Batch File: [___________________] [Browse...] │
│   ↑ ORANGE highlight - ACTIVE                  │
│                                                │
└────────────────────────────────────────────────┘
```

---

### **Step 3: Automatic Enforcement (Runtime)**

When you click **"Run Simulations"**:

1. System checks FDS version from Tab 2
2. System uses **only** the matching batch file from Tab 3
3. If batch file not configured, shows version-specific error message

---

## Visual Color Coding

| State | Label Color | Field Background | Border | Meaning |
|-------|-------------|------------------|--------|---------|
| **FDS6 Active** | Green (bold) | Light green | Green | Ready to use FDS6 |
| **FDS5 Active** | Orange (bold) | Light orange | Orange | Ready to use FDS5 |
| **Disabled** | Gray | Light gray | None | Cannot be used |

---

## User Workflow

### **Typical Usage**

1. **Tab 2: Generate FDS**
   - Select **⚪ FDS 6** (or FDS 5)
   - Configure fire scenarios
   - Click "Generate FDS Files"
   - System creates FDS6 (or FDS5) input files

2. **Tab 3: FDS Simulation**
   - Notice **green-highlighted** FDS6 field (or orange FDS5)
   - Click "Browse..." next to the **highlighted** field
   - Select your batch file
   - Click "Run Simulations"
   - System automatically uses correct batch file

---

## Error Prevention

### **Scenario 1: FDS6 Selected, but FDS6 Batch File Not Configured**

**Error Message**:
```
FDS6 Not Found

Please specify either:

1. FDS6 Batch File (run_fds6.bat) - Recommended
2. FDS6 Executable (fds_openmp.exe)

The batch file method avoids conflicts with FDS5.
```

**Solution**: Configure FDS6 batch file in the **green-highlighted** field.

---

### **Scenario 2: FDS5 Selected, but FDS5 Batch File Not Configured**

**Error Message**:
```
FDS5 Not Found

Please specify either:

1. FDS5 Batch File (run_fds5.bat) - Recommended
2. FDS5 Executable (fds.exe)

The batch file method avoids conflicts with FDS6.
```

**Solution**: Configure FDS5 batch file in the **orange-highlighted** field.

---

### **Scenario 3: User Tries to Configure Wrong Batch File**

**Prevention**: The disabled field **cannot be edited** or browsed.

**Visual Feedback**: Grayed-out appearance makes it clear the field is inactive.

---

## Status Messages

### **Tab 2 (Generate FDS)**

When you select FDS version:

**FDS6 Selected**:
```
✓ FDS6 selected - Only FDS6 batch file will be used
```

**FDS5 Selected**:
```
✓ FDS5 selected - Only FDS5 batch file will be used
```

---

### **Tab 3 (FDS Simulation)**

When FDS version changes:

**FDS6 Mode**:
```
✓ FDS6 mode active - Configure FDS6 batch file
```

**FDS5 Mode**:
```
✓ FDS5 mode active - Configure FDS5 batch file
```

When simulation starts:

**Using FDS6**:
```
✓ Using FDS6 batch file: C:/FDS6/run_fds6.bat
```

**Using FDS5**:
```
✓ Using FDS5 batch file: C:/FDS5/run_fds5.bat
```

---

## Technical Implementation

### **Signal Connections**

```python
# Tab 2: Connect radio buttons to version change handler
self.fds6_radio.toggled.connect(self.on_fds_version_changed)
self.fds5_radio.toggled.connect(self.on_fds_version_changed)
```

### **Version Change Handler**

```python
def on_fds_version_changed(self):
    if self.fds6_radio.isChecked():
        # Enable FDS6, disable FDS5
        self.fds6_batch_path.setEnabled(True)
        self.fds5_batch_path.setEnabled(False)
        # Apply visual styling
        self.fds6_batch_path.setStyleSheet("background-color: #eafaf1; border: 2px solid #27ae60;")
        self.fds5_batch_path.setStyleSheet("background-color: #ecf0f1; color: #95a5a6;")
    else:
        # Enable FDS5, disable FDS6
        self.fds5_batch_path.setEnabled(True)
        self.fds6_batch_path.setEnabled(False)
        # Apply visual styling
        self.fds5_batch_path.setStyleSheet("background-color: #fef5e7; border: 2px solid #e67e22;")
        self.fds6_batch_path.setStyleSheet("background-color: #ecf0f1; color: #95a5a6;")
```

### **Runtime Enforcement**

```python
def run_fds_simulations(self):
    # Get version from Tab 2
    fds_version = "FDS6" if self.fds6_radio.isChecked() else "FDS5"
    
    # Use only the matching batch file
    if fds_version == "FDS6":
        fds_batch = self.fds6_batch_path.text().strip()
        # Only FDS6 batch file is checked
    else:
        fds_batch = self.fds5_batch_path.text().strip()
        # Only FDS5 batch file is checked
```

---

## Benefits

### **For Users**

✅ **Prevents Errors**: Cannot accidentally run FDS5 input with FDS6  
✅ **Clear Guidance**: Visual indicators show which field to configure  
✅ **Automatic**: No manual version checking required  
✅ **Foolproof**: Disabled fields prevent wrong configuration  

### **For System**

✅ **Data Integrity**: Ensures compatible input/executable pairs  
✅ **Error Reduction**: Eliminates version mismatch errors  
✅ **User Experience**: Clear, intuitive interface  
✅ **Maintainability**: Centralized version control logic  

---

## FAQ

### **Q: Can I switch FDS versions mid-project?**

**A**: Yes, but you must:
1. Regenerate FDS input files in Tab 2 with new version
2. Configure the corresponding batch file in Tab 3
3. Run simulations with the new version

### **Q: What if I only have FDS6 installed?**

**A**: 
- Select **FDS 6** in Tab 2
- Configure only the FDS6 batch file in Tab 3
- The FDS5 field will remain disabled (grayed out)

### **Q: What if I only have FDS5 installed?**

**A**: 
- Select **FDS 5** in Tab 2
- Configure only the FDS5 batch file in Tab 3
- The FDS6 field will remain disabled (grayed out)

### **Q: Can I use direct executables instead of batch files?**

**A**: Yes, the system falls back to direct executables if batch files are not configured. However, batch files are **strongly recommended** to avoid version conflicts.

### **Q: What happens if I configure both batch files?**

**A**: The system will use **only** the batch file that matches your Tab 2 selection. The other batch file is ignored.

### **Q: Can I override the version enforcement?**

**A**: No, this is a safety feature. You must select the correct version in Tab 2 to use the corresponding batch file in Tab 3.

---

## Troubleshooting

### **Issue: Both fields are grayed out**

**Cause**: UI initialization error

**Solution**: 
1. Close and restart QRA System
2. Select FDS version in Tab 2
3. Check that one field becomes highlighted

---

### **Issue: Wrong field is highlighted**

**Cause**: Tab 2 selection doesn't match expectation

**Solution**:
1. Go to Tab 2
2. Verify FDS version radio button selection
3. Change selection if needed
4. Return to Tab 3 to see updated highlighting

---

### **Issue: Simulation fails with "FDS Not Found"**

**Cause**: Batch file not configured for selected version

**Solution**:
1. Check which field is highlighted in Tab 3
2. Click "Browse..." next to the highlighted field
3. Select the appropriate batch file
4. Retry simulation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 4.5.0 | Feb 2026 | Added FDS version enforcement with visual indicators |
| 4.4.0 | Jan 2026 | Basic FDS version selection (no enforcement) |

---

## Related Documentation

- **DUAL_FDS_INSTALLATION_GUIDE.md** - How to set up dual FDS installations
- **DUAL_FDS_QUICK_START.txt** - Quick setup guide
- **FDS_VERSION_ENFORCEMENT.md** - This document

---

**Status**: ✅ **ACTIVE AND ENFORCED**

The FDS version enforcement feature is fully implemented and active in QRA System v4.5.0!
