"""
Database package for QRA System

Note: QRADatabase is in database.py (root level), not in this package.
This package contains FDB conversion database functionality.
"""

from .fdb_conversion_db import FDBConversionDB, get_fdb_conversion_db

__all__ = [
    'FDBConversionDB',
    'get_fdb_conversion_db',
]

__version__ = '4.5.0'
