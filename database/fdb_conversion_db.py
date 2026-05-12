"""
FDB Conversion Database Manager
================================

Manages database operations for FDS to FDB conversions in the QRA System.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any


class FDBConversionDB:
    """Database manager for FDB conversions"""
    
    def __init__(self, db_path: Path):
        """
        Initialize FDB conversion database manager
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    
    def _create_tables(self):
        """Create FDB conversions table if it doesn't exist"""
        schema_file = Path(__file__).parent / "fdb_conversions_schema.sql"
        
        if schema_file.exists():
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            self.conn.executescript(schema_sql)
            self.conn.commit()
        else:
            # Fallback: create table directly
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS fdb_conversions (
                    conversion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    simulation_id INTEGER,
                    fds_output_dir TEXT NOT NULL,
                    fdb_file_path TEXT NOT NULL,
                    config_file_path TEXT,
                    fds_id TEXT,
                    axis_direction TEXT,
                    vert_direction TEXT,
                    time_step INTEGER,
                    temp_skip INTEGER,
                    conversion_factors TEXT,
                    variables_processed TEXT,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration_seconds REAL,
                    fdb_file_size_bytes INTEGER,
                    num_time_steps INTEGER,
                    num_variables INTEGER,
                    mesh_dimensions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.conn.commit()
    
    def create_conversion(
        self,
        fds_output_dir: Path,
        simulation_id: Optional[int] = None,
        config_file_path: Optional[Path] = None
    ) -> int:
        """
        Create a new FDB conversion record
        
        Args:
            fds_output_dir: Directory containing FDS output files
            simulation_id: Optional ID of related FDS simulation
            config_file_path: Optional path to CONVERT.DES file
        
        Returns:
            conversion_id: ID of created conversion record
        """
        cursor = self.conn.execute("""
            INSERT INTO fdb_conversions (
                simulation_id,
                fds_output_dir,
                fdb_file_path,
                config_file_path,
                status,
                start_time
            ) VALUES (?, ?, ?, ?, 'pending', ?)
        """, (
            simulation_id,
            str(fds_output_dir),
            "",  # Will be updated when conversion completes
            str(config_file_path) if config_file_path else None,
            datetime.now().isoformat()
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def update_conversion_status(
        self,
        conversion_id: int,
        status: str,
        error_message: Optional[str] = None
    ):
        """
        Update conversion status
        
        Args:
            conversion_id: ID of conversion record
            status: New status (pending, running, completed, failed)
            error_message: Optional error message if failed
        """
        self.conn.execute("""
            UPDATE fdb_conversions
            SET status = ?,
                error_message = ?,
                updated_at = ?
            WHERE conversion_id = ?
        """, (status, error_message, datetime.now().isoformat(), conversion_id))
        
        self.conn.commit()
    
    def update_conversion_complete(
        self,
        conversion_id: int,
        fdb_file_path,  # Can be str or Path
        config: Dict[str, Any],
        metadata: Dict[str, Any]
    ):
        """
        Update conversion record upon completion
        
        Args:
            conversion_id: ID of conversion record
            fdb_file_path: Path to generated FDB file (str or Path)
            config: Conversion configuration
            metadata: Conversion metadata (time steps, variables, etc.)
        """
        # Convert to Path object if string
        if isinstance(fdb_file_path, str):
            fdb_file_path = Path(fdb_file_path)
        
        # Get file size
        fdb_size = fdb_file_path.stat().st_size if fdb_file_path.exists() else 0
        
        # Calculate duration
        cursor = self.conn.execute("""
            SELECT start_time FROM fdb_conversions WHERE conversion_id = ?
        """, (conversion_id,))
        row = cursor.fetchone()
        
        duration = 0.0
        if row and row['start_time']:
            start = datetime.fromisoformat(row['start_time'])
            end = datetime.now()
            duration = (end - start).total_seconds()
        
        # Update record
        self.conn.execute("""
            UPDATE fdb_conversions
            SET fdb_file_path = ?,
                fds_id = ?,
                axis_direction = ?,
                vert_direction = ?,
                time_step = ?,
                temp_skip = ?,
                conversion_factors = ?,
                variables_processed = ?,
                status = 'completed',
                end_time = ?,
                duration_seconds = ?,
                fdb_file_size_bytes = ?,
                num_time_steps = ?,
                num_variables = ?,
                mesh_dimensions = ?,
                updated_at = ?
            WHERE conversion_id = ?
        """, (
            str(fdb_file_path),
            config.get('fds_id'),
            config.get('axis_dir'),
            config.get('vert_dir'),
            config.get('time_step'),
            config.get('temp_skip'),
            json.dumps(config.get('conversion_factors', {})),
            json.dumps(metadata.get('variables', [])),
            datetime.now().isoformat(),
            duration,
            fdb_size,
            metadata.get('num_time_steps'),
            metadata.get('num_variables'),
            json.dumps(metadata.get('mesh_dimensions', {})),
            datetime.now().isoformat(),
            conversion_id
        ))
        
        self.conn.commit()
    
    def get_conversion(self, conversion_id: int) -> Optional[Dict]:
        """
        Get conversion record by ID
        
        Args:
            conversion_id: ID of conversion record
        
        Returns:
            Dictionary with conversion data, or None if not found
        """
        cursor = self.conn.execute("""
            SELECT * FROM fdb_conversions WHERE conversion_id = ?
        """, (conversion_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_conversions_by_simulation(self, simulation_id: int) -> List[Dict]:
        """
        Get all conversions for a simulation
        
        Args:
            simulation_id: ID of FDS simulation
        
        Returns:
            List of conversion records
        """
        cursor = self.conn.execute("""
            SELECT * FROM fdb_conversions 
            WHERE simulation_id = ?
            ORDER BY created_at DESC
        """, (simulation_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_conversions_by_directory(self, fds_output_dir: Path) -> List[Dict]:
        """
        Get all conversions for an FDS output directory
        
        Args:
            fds_output_dir: Directory containing FDS output files
        
        Returns:
            List of conversion records
        """
        cursor = self.conn.execute("""
            SELECT * FROM fdb_conversions 
            WHERE fds_output_dir = ?
            ORDER BY created_at DESC
        """, (str(fds_output_dir),))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_conversions(self, limit: int = 10) -> List[Dict]:
        """
        Get recent conversions
        
        Args:
            limit: Maximum number of records to return
        
        Returns:
            List of recent conversion records
        """
        cursor = self.conn.execute("""
            SELECT * FROM fdb_conversions 
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_conversion_by_fdb_path(self, fdb_file_path: Path) -> Optional[Dict]:
        """
        Get conversion record by FDB file path
        
        Args:
            fdb_file_path: Path to FDB file
        
        Returns:
            Dictionary with conversion data, or None if not found
        """
        cursor = self.conn.execute("""
            SELECT * FROM fdb_conversions 
            WHERE fdb_file_path = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (str(fdb_file_path),))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def delete_conversion(self, conversion_id: int):
        """
        Delete a conversion record
        
        Args:
            conversion_id: ID of conversion record to delete
        """
        self.conn.execute("""
            DELETE FROM fdb_conversions WHERE conversion_id = ?
        """, (conversion_id,))
        
        self.conn.commit()
    
    def get_conversion_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about conversions
        
        Returns:
            Dictionary with statistics
        """
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as total_conversions,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                AVG(duration_seconds) as avg_duration,
                SUM(fdb_file_size_bytes) as total_fdb_size
            FROM fdb_conversions
        """)
        
        row = cursor.fetchone()
        return dict(row) if row else {}
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Convenience function for getting database instance
def get_fdb_conversion_db(project_dir: Path) -> FDBConversionDB:
    """
    Get FDB conversion database instance for a project
    
    Args:
        project_dir: Project directory
    
    Returns:
        FDBConversionDB instance
    """
    db_path = project_dir / "qra_database.db"
    return FDBConversionDB(db_path)
