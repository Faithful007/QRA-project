# QRA Multi-Language Support - Quick Start Guide

## How to Use Language Selection

### Step 1: Start the Application
```bash
python main.py
# or
run.bat
```

### Step 2: Locate Language Selector
- Look for the **"Language"** section at the bottom of the Main Control window
- You'll see a dropdown menu with language options

### Step 3: Select Your Language
Click the dropdown and choose from:
- **English** - English (default)
- **한국어 (Korean)** - 한국어
- **日本語 (Japanese)** - 日本語
- **Deutsch (German)** - Deutsch
- **Italiano (Italian)** - Italiano
- **Français (French)** - Français
- **Nederlands (Dutch)** - Nederlands

### Step 4: Instant Translation
As soon as you select a language:
- ✅ Main Control window title and labels update
- ✅ All buttons change to the new language
- ✅ All tabs in the main application window change
- ✅ Tab titles update to the new language
- ✅ All group box titles update
- ✅ All buttons within tabs update

## Example: Switching to Korean

**Before (English):**
```
QRA Main Control
┌─────────────────────────┐
│ Simulation | Result ... │
│─────────────────────────│
│ Simulation Status: Idle │
│ Risk Status: N/A        │
│─────────────────────────│
│ Language: [English ▼]   │
└─────────────────────────┘
```

**After (Select 한국어):**
```
QRA 메인 제어
┌─────────────────────────┐
│ 시뮬레이션 | 결과 분석... │
│─────────────────────────│
│ 시뮬레이션 상태: 대기   │
│ 위험 상태: N/A          │
│─────────────────────────│
│ 언어: [한국어 ▼]        │
└─────────────────────────┘
```

## What Gets Translated

### Main Control Window
- Window title
- All buttons
- All group box titles
- All labels
- Status messages

### Main Application Window
- Window title
- All 5 tab titles:
  - Tunnel Basic Settings
  - Traffic Management
  - HAR EVAC Analysis
  - Simulation Settings
  - MDB Database Creation
- Bottom control buttons
- Status bar messages

### Each Tab
- Group box titles
- Label text
- Button text
- Table headers (where applicable)

## Languages Available

| Code | Display Name | Native Name |
|------|-------------|-------------|
| en | English | English |
| ko | Korean | 한국어 |
| ja | Japanese | 日本語 |
| de | German | Deutsch |
| it | Italian | Italiano |
| fr | French | Français |
| nl | Dutch | Nederlands |

## Key Features

✅ **Instant Translation** - All UI text updates immediately when you change language
✅ **Complete Coverage** - 117 UI strings translated in each language
✅ **No Data Loss** - Changing language doesn't affect your data or settings
✅ **Easy to Switch** - Just click the dropdown to change language
✅ **Consistent** - All parts of the application speak the same language

## Troubleshooting

### Language selector not showing?
- Make sure you're in the Main Control window (separate from the tab window)
- Scroll down in the Main Control window if needed
- Look for "Language" group box at the bottom

### Text not updating?
- Make sure you've released the language dropdown (clicked away from it)
- Try switching to a different language and back
- Restart the application if the issue persists

### Some text still in English?
- This is normal for tooltips and help text (not yet translated)
- Main UI elements are fully translated
- Tables and dynamic content will update when they're populated

## Tips

1. **Default Language**: The application starts in English
2. **Language Preference**: Currently doesn't persist between sessions (starts fresh each time)
3. **Adding Languages**: Contact development team to add new languages
4. **Reporting Issues**: If you find untranslated text, report it along with the location

## Supported Languages

### Asian Languages
- **Korean (한국어)** - Complete 117-string translation
- **Japanese (日本語)** - Complete 117-string translation

### European Languages
- **German (Deutsch)** - Complete 117-string translation
- **Italian (Italiano)** - Complete 117-string translation
- **French (Français)** - Complete 117-string translation
- **Dutch (Nederlands)** - Complete 117-string translation

### Default
- **English** - 117 strings (reference language)

## Translation Coverage

**Total Translations: 819**
- 7 languages × 117 strings = 819 total translations

**Categories Translated:**
- Window titles (2)
- Button labels (28)
- Group box titles (17)
- Label text (32)
- Status messages (8)
- Menu items (4)
- Tab titles (5)
- Group/dialog headers (14)
- Form field labels (6)

## For System Administrators

If you want to add a new language:

1. Open `src/translations.py`
2. Add new language code to TRANSLATIONS dictionary
3. Copy all 117 English strings and translate them
4. Save and test with `python test_language_system.py`
5. New language automatically appears in dropdown

## Performance Notes

- ✅ **Fast**: All translations loaded in memory (no file I/O)
- ✅ **Efficient**: Language change is instantaneous
- ✅ **Lightweight**: Translation system adds minimal overhead
- ✅ **Scalable**: Can easily support 20+ languages

## Need Help?

For issues or questions about the language system:
1. Check LANGUAGE_SYSTEM.md for technical details
2. Review LANGUAGE_IMPLEMENTATION.md for architecture
3. Run test_language_system.py to verify all translations
4. Contact the development team
