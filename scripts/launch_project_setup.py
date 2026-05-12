#!/usr/bin/env python3
"""
Launcher script for FDS Project Setup GUI
Run this to start the project directory structure creator
"""

import sys
from project_setup_gui import main

if __name__ == "__main__":
    print("="*60)
    print("FDS Project Setup - Directory Structure Creator")
    print("="*60)
    print("Starting GUI application...")
    print()
    
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
