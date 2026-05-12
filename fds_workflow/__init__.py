"""
FDS Workflow Package
This package contains modules for FDS simulation workflow:
- fds_generator: Generate FDS input files
- fds_runner: Run FDS simulations
- fds_to_fdb_converter: Convert FDS outputs to FDB format
- fds_workflow: Orchestrate the complete workflow
"""

# Import key classes and functions for easy access
try:
    from .fds_generator import TunnelGeometry, FireScenario, FDSInputGenerator
except ImportError as e:
    print(f"Warning: Could not import from fds_generator: {e}")
    TunnelGeometry = None
    FireScenario = None
    FDSInputGenerator = None

try:
    from .fds_to_fdb_converter import FDSToFDBConverter, convert_fds_to_fdb
except ImportError as e:
    print(f"Warning: Could not import from fds_to_fdb_converter: {e}")
    FDSToFDBConverter = None
    convert_fds_to_fdb = None

try:
    from .fds_workflow import FDSWorkflow
except ImportError as e:
    print(f"Warning: Could not import FDSWorkflow: {e}")
    FDSWorkflow = None

__all__ = [
    'TunnelGeometry',
    'FireScenario',
    'FDSInputGenerator',
    'FDSToFDBConverter',
    'convert_fds_to_fdb',
    'FDSWorkflow',
]

__version__ = '4.5.0'
