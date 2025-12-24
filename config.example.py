"""
Configuration file template for FED Calculator
Copy this file to config.py and update with your settings
"""

# Database Configuration
# Options: 'sqlite', 'mysql', 'postgresql'
DATABASE_TYPE = 'sqlite'

# SQLite Configuration (default)
SQLITE_DB_PATH = 'fed_calculator.db'

# MySQL Configuration
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'password'
MYSQL_DATABASE = 'fed_calculator'

# PostgreSQL Configuration
POSTGRES_HOST = 'localhost'
POSTGRES_PORT = 5432
POSTGRES_USER = 'postgres'
POSTGRES_PASSWORD = 'password'
POSTGRES_DATABASE = 'fed_calculator'

# Application Settings
APP_TITLE = 'FED Calculator - Fire and Explosion Damage Analysis'
APP_WIDTH = 1200
APP_HEIGHT = 800

# Calculation Parameters
# Default values for calculations
DEFAULT_TUNNEL_LENGTH = 410  # km
DEFAULT_LANE_WIDTH = 3.25    # meters
DEFAULT_WALL_AREA = 54.11    # square meters

# Traffic Parameters
DEFAULT_TRAFFIC_MODE = 'One-way'
DEFAULT_GROWTH_RATE = 4.34   # percent
DEFAULT_OCCUPANCY = 3        # persons per vehicle

# Logging Configuration
LOG_LEVEL = 'INFO'
LOG_FILE = 'fed_calculator.log'

# Feature Flags
ENABLE_SIMULATION = True
ENABLE_RESULT_ANALYSIS = True
ENABLE_EXPORT = True
ENABLE_IMPORT = True

# Database Connection Pool Settings
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_POOL_RECYCLE = 3600
