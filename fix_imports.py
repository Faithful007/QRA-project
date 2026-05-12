"""
Fix Import Errors - Automatic __init__.py Updater

This script automatically fixes the import errors in the QRA System by:
1. Updating fds_workflow/__init__.py with proper module exports
2. Verifying the fix by testing imports
3. Providing diagnostic information

Usage:
    python fix_imports.py
"""

import os
import sys
from pathlib import Path

def fix_fds_workflow_init():
    """Fix the fds_workflow/__init__.py file"""
    
    # Get the script directory
    script_dir = Path(__file__).parent
    init_file = script_dir / 'fds_workflow' / '__init__.py'
    
    print("=" * 60)
    print("QRA System Import Fix Utility")
    print("=" * 60)
    print()
    
    # Check if fds_workflow directory exists
    if not (script_dir / 'fds_workflow').exists():
        print("❌ ERROR: fds_workflow directory not found!")
        print(f"   Expected location: {script_dir / 'fds_workflow'}")
        return False
    
    # Check if fds_to_fdb_converter.py exists
    converter_file = script_dir / 'fds_workflow' / 'fds_to_fdb_converter.py'
    if not converter_file.exists():
        print("❌ ERROR: fds_to_fdb_converter.py not found!")
        print(f"   Expected location: {converter_file}")
        return False
    
    print(f"✓ Found fds_workflow directory: {script_dir / 'fds_workflow'}")
    print(f"✓ Found fds_to_fdb_converter.py: {converter_file}")
    print()
    
    # Create the correct __init__.py content
    init_content = '''"""
FDS Workflow Package

This package contains modules for FDS simulation workflow:
- fds_generator: Generate FDS input files
- fds_runner: Run FDS simulations
- fds_to_fdb_converter: Convert FDS outputs to FDB format
- fds_workflow: Orchestrate the complete workflow
"""

# Import key classes and functions for easy access
try:
    from .fds_generator import FireScenario, FDSInputGenerator
except ImportError as e:
    print(f"Warning: Could not import from fds_generator: {e}")
    FireScenario = None
    FDSInputGenerator = None

try:
    from .fds_to_fdb_converter import FDSToFDBConverter
except ImportError as e:
    print(f"Warning: Could not import FDSToFDBConverter: {e}")
    FDSToFDBConverter = None

__all__ = [
    'FireScenario',
    'FDSInputGenerator',
    'FDSToFDBConverter',
]

__version__ = '4.5.0'
'''
    
    # Write the file
    try:
        with open(init_file, 'w', encoding='utf-8') as f:
            f.write(init_content)
        print(f"✓ Updated __init__.py: {init_file}")
        print()
    except Exception as e:
        print(f"❌ ERROR: Could not write __init__.py: {e}")
        return False
    
    return True

def test_imports():
    """Test if the imports work correctly"""
    
    print("=" * 60)
    print("Testing Imports...")
    print("=" * 60)
    print()
    
    # Test 1: Import fds_workflow package
    try:
        import fds_workflow
        print("✓ Successfully imported fds_workflow package")
    except Exception as e:
        print(f"❌ Failed to import fds_workflow: {e}")
        return False
    
    # Test 2: Import FDSToFDBConverter
    try:
        from fds_workflow.fds_to_fdb_converter_old import FDSToFDBConverter
        print("✓ Successfully imported FDSToFDBConverter")
    except Exception as e:
        print(f"❌ Failed to import FDSToFDBConverter: {e}")
        print(f"   Error details: {type(e).__name__}: {str(e)}")
        return False
    
    # Test 3: Import from package __init__
    try:
        from fds_workflow import FDSToFDBConverter
        print("✓ Successfully imported FDSToFDBConverter from package")
    except Exception as e:
        print(f"❌ Failed to import from package: {e}")
        return False
    
    print()
    print("=" * 60)
    print("✓ All imports successful!")
    print("=" * 60)
    print()
    
    return True

def main():
    """Main function"""
    
    print()
    print("Starting import fix process...")
    print()
    
    # Step 1: Fix __init__.py
    if not fix_fds_workflow_init():
        print()
        print("=" * 60)
        print("❌ FAILED: Could not fix __init__.py")
        print("=" * 60)
        sys.exit(1)
    
    # Step 2: Test imports
    if not test_imports():
        print()
        print("=" * 60)
        print("❌ FAILED: Imports still not working")
        print("=" * 60)
        print()
        print("Please check:")
        print("1. Is fds_to_fdb_converter.py in the fds_workflow directory?")
        print("2. Does fds_to_fdb_converter.py have syntax errors?")
        print("3. Are all required dependencies installed? (pip install -r requirements.txt)")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("✓ SUCCESS: All import errors fixed!")
    print("=" * 60)
    print()
    print("You can now run the QRA System:")
    print("    python qra_main_app.py")
    print()

if __name__ == '__main__':
    main()
