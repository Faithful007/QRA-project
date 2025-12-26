# QRA Program - Multi-Language Support System

## Overview

The QRA Program now includes a complete multi-language support system that allows users to switch between 7 languages dynamically. All UI labels, buttons, and group titles update automatically across the entire application when a language is selected.

## Supported Languages

| Code | Language | Native Name |
|------|----------|-------------|
| en | English | English |
| ko | Korean | 한국어 |
| ja | Japanese | 日本語 |
| de | German | Deutsch |
| it | Italian | Italiano |
| fr | French | Français |
| nl | Dutch | Nederlands |

## Architecture

### Core Components

#### 1. **src/translations.py**
- Contains all translation dictionaries for 7 languages
- 117 UI strings translated in each language
- Covers all buttons, labels, group titles, and menu items
- Functions:
  - `get_translation(text, language)`: Get translation for a string
  - `get_available_languages()`: Get available languages with display names

#### 2. **src/language_manager.py**
- Central language management with PyQt6 signals
- **LanguageManager class** features:
  - `set_language(language_code)`: Change language and emit signal
  - `get_language()`: Get current language code
  - `translate(text, default="")`: Translate text to current language
  - `language_changed` signal: Emitted when language changes
- Global instance via `get_language_manager()`
- Convenience function `translate(text, default="")`

### UI Components

#### Main Control Window (src/ui/main_window.py)
- **Language Selector**: Dropdown in "Language" group box
- **Language Options**: All 7 languages available
- **Features**:
  - Connects language change to all components
  - Updates window title and all button labels
  - Updates group box titles dynamically
  - Emits signal to update main window tabs

#### Tab-based Interface (src/ui/tabs/)
- All tabs subscribe to `language_changed` signal
- Implement `_on_language_changed(language_code)` method
- Tabs updated:
  - `tunnel_settings.py` - Tunnel Basic Settings
  - `traffic_management.py` - Traffic Management
  - `har_evac.py` - HAR EVAC Analysis
  - `simulation.py` - Simulation Settings
  - `mdb_create.py` - MDB Database Creation

#### Main Application Window (QRACalculatorApp)
- Subscribes to language changes
- Updates all tab titles when language changes
- Updates window title and status bar messages

## How It Works

### 1. User Selects Language
```
User selects language from dropdown in Main Control
↓
_on_language_changed() triggered
↓
language_combo.currentData() gets language code
↓
language_manager.set_language(language_code)
```

### 2. Language Manager Emits Signal
```
set_language() updates internal state
↓
language_changed signal emitted with language code
↓
All connected components receive signal
```

### 3. Components Update UI
```
Each component's _on_language_changed() handler called
↓
Component calls lm.translate(text) for each UI element
↓
UI labels, titles, buttons updated with new language
↓
User sees translated interface
```

## Usage Example

### In Main Control Window
```python
# Language selector automatically created and connected
# When user changes selection:
def _on_language_changed(self):
    language_code = self.language_combo.currentData()
    self.language_manager.set_language(language_code)
    self._update_ui_text()

# All UI text updates
def _update_ui_text(self):
    lm = self.language_manager
    self.setWindowTitle(lm.translate("QRA Main Control"))
    self.sim_btn.setText(lm.translate("Simulation"))
    # ... update more labels
```

### In Tab Components
```python
class TrafficManagementTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.language_manager = get_language_manager()
        # Connect to language change signal
        self.language_manager.language_changed.connect(self._on_language_changed)
    
    def _on_language_changed(self, language_code: str):
        """Handle language change - update all UI text"""
        lm = self.language_manager
        # Update group box titles
        group_box.setTitle(lm.translate("Traffic Volume"))
        # Update button labels
        button.setText(lm.translate("Calculate"))
```

### Using Translation Function
```python
# Get current translation
from src.language_manager import translate

text = translate("QRA Main Control")  # Uses current language
text = translate("Simulation", default="Run Simulation")  # With fallback
```

## Components Integrated

### Main Control Window
- ✅ Window title
- ✅ All buttons (Simulation, Result Analysis, Data_MDB File Set)
- ✅ All group boxes (Top Controls, Simulation Control, Analysis Control, Graph Control, Language)
- ✅ All labels and status messages

### Main Window (Tab Interface)
- ✅ Window title
- ✅ Tab titles (5 tabs)
- ✅ Bottom control buttons
- ✅ Status messages

### Tab Contents
- ✅ Tunnel Basic Settings tab
- ✅ Traffic Management tab
- ✅ HAR EVAC Analysis tab
- ✅ Simulation Settings tab
- ✅ MDB Database Creation tab

## Translation Statistics

- **Total unique English strings**: 117
- **Languages supported**: 7
- **Total translations**: 819 (117 × 7)

### Coverage by Category
- Main Control: 20 strings
- Main Window: 11 strings
- Traffic Management: 14 strings
- HAR EVAC Analysis: 21 strings
- Simulation Settings: 18 strings
- MDB Database: 19 strings
- Shared/Common: 14 strings

## Testing

Run the language system test:
```bash
python test_language_system.py
```

Expected output:
- Lists all 7 available languages
- Shows sample translations for key strings
- Displays translation statistics
- Confirms 117 translations per language

## Future Enhancements

1. **Persistence**: Save user's language preference to config file
2. **Additional Languages**: Add more languages by extending TRANSLATIONS dictionary
3. **Dynamic Translation Files**: Load translations from JSON/YAML files
4. **RTL Support**: Add right-to-left language support (Arabic, Hebrew, etc.)
5. **Date/Number Formatting**: Locale-specific number and date formats
6. **Help System**: Translate help text and tooltips

## Implementation Checklist

- ✅ Created translations.py with 117 strings in 7 languages
- ✅ Created language_manager.py with signal-based architecture
- ✅ Added language selector to Main Control Window
- ✅ Updated all 5 tab classes to support language changes
- ✅ Updated main application window to update tab titles
- ✅ Verified all 819 translations load correctly
- ✅ Tested language switching mechanism
- ✅ Created test script for translation verification

## Notes

- Language selection is per-session (not saved between app restarts) - can be enhanced with config persistence
- All translations are hardcoded in the module for performance (no file I/O needed)
- Signal-based architecture allows easy addition of new UI components
- Translation strings use English as keys for consistency
