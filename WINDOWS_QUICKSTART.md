# QRA Program - Windows Quick Start Guide

This guide will help you set up and run the Quantitative Risk Analysis (QRA) Program on your Windows machine.

## Prerequisites

1.  **Python**: You must have Python 3.8 or newer installed.
    *   Download from [https://www.python.org/downloads/](https://www.python.org/downloads/)
    *   **CRITICAL**: During installation, make sure to check the box that says **"Add Python to PATH"**.
    *   Restart your computer after installing Python.

## Setup (Run Once)

1.  **Extract the ZIP file** to a folder of your choice (e.g., `C:\QRA-Program`).
2.  **Double-click `setup.bat`**.
    *   This script will automatically create a virtual environment (`venv`) and install all necessary Python dependencies (including PyQt6 and SQLAlchemy).
    *   Wait for the Command Prompt window to display **"Setup Complete!"**.
    *   Press any key to close the window.

## Running the Application

1.  **Double-click `run.bat`**.
    *   This script will activate the environment and launch the QRA Program.
    *   Two windows will open: the main **QRA Program** (with the tabs) and the **QRA Main Control** (the separate control panel).

## Troubleshooting

| Issue | Solution |
| :--- | :--- |
| `ERROR: Python not found` | Ensure Python is installed and added to your system's PATH environment variable. Re-run the Python installer and check the "Add Python to PATH" option. |
| `pip install` errors | Ensure you are connected to the internet. If the error persists, try running `setup.bat` again. |
| Application does not start | Open Command Prompt, navigate to the project folder, and manually run `venv\Scripts\activate` followed by `python main.py` to see the error message. |

## Key Files

*   `setup.bat`: Automated setup script (run once).
*   `run.bat`: Launches the application.
*   `main.py`: The main application file.
*   `qra_data.db`: The SQLite database file where all your configuration data is saved.
