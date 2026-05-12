"""
QRA Database Module
SQLite-based database for project metadata, scenario tracking, and results storage
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


class QRADatabase:
    """SQLite database for QRA project management"""
    
    def __init__(self, db_path: str):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Connect to database and create tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        
        # Projects table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT NOT NULL,
                description TEXT,
                home_directory TEXT,
                project_directory TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Scenarios table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                scenario_name TEXT NOT NULL,
                chid TEXT NOT NULL,
                hrr_mw REAL,
                fire_position REAL,
                ventilation TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        
        # Simulations table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL,
                simulation_type TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT DEFAULT 'pending',
                output_path TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
            )
        """)
        
        # FED Results table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS fed_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL,
                max_fed REAL,
                final_fed REAL,
                fatalities INTEGER,
                n_people INTEGER,
                analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                results_json TEXT,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
            )
        """)
        
        # Monte Carlo Results table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS monte_carlo_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                n_iterations INTEGER,
                trim_percentage REAL,
                mean_fatalities REAL,
                median_fatalities REAL,
                std_fatalities REAL,
                p5_fatalities REAL,
                p95_fatalities REAL,
                analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                results_json TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        
        # Configuration table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                config_key TEXT NOT NULL,
                config_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                UNIQUE(project_id, config_key)
            )
        """)
        
        self.conn.commit()
    
    # ==================== Project Methods ====================
    
    def add_project(self, project_name: str, description: str = "", 
                    home_directory: str = "", project_directory: str = "") -> int:
        """
        Add a new project
        
        Args:
            project_name: Name of the project
            description: Project description
            home_directory: Home directory path
            project_directory: Full project directory path
            
        Returns:
            Project ID
        """
        self.cursor.execute("""
            INSERT INTO projects (project_name, description, home_directory, project_directory)
            VALUES (?, ?, ?, ?)
        """, (project_name, description, home_directory, project_directory))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects"""
        self.cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific project by ID"""
        self.cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def update_project(self, project_id: int, **kwargs):
        """Update project fields"""
        fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [project_id]
        self.cursor.execute(f"""
            UPDATE projects 
            SET {fields}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, values)
        self.conn.commit()
    
    # ==================== Scenario Methods ====================
    
    def add_scenario(self, project_id: int, scenario_name: str, chid: str,
                     hrr_mw: float = 0, fire_position: float = 0, 
                     ventilation: str = "N") -> int:
        """
        Add a new scenario
        
        Args:
            project_id: Parent project ID
            scenario_name: Scenario name
            chid: CHID (scenario identifier)
            hrr_mw: Heat release rate in MW
            fire_position: Fire position in meters
            ventilation: Ventilation type (N/NVC/V)
            
        Returns:
            Scenario ID
        """
        self.cursor.execute("""
            INSERT INTO scenarios 
            (project_id, scenario_name, chid, hrr_mw, fire_position, ventilation)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (project_id, scenario_name, chid, hrr_mw, fire_position, ventilation))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_scenarios(self, project_id: int) -> List[Dict[str, Any]]:
        """Get all scenarios for a project"""
        self.cursor.execute("""
            SELECT * FROM scenarios 
            WHERE project_id = ? 
            ORDER BY created_at DESC
        """, (project_id,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_scenario_by_chid(self, chid: str) -> Optional[Dict[str, Any]]:
        """Get scenario by CHID"""
        self.cursor.execute("SELECT * FROM scenarios WHERE chid = ?", (chid,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def update_scenario_status(self, scenario_id: int, status: str):
        """Update scenario status"""
        self.cursor.execute("""
            UPDATE scenarios 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, scenario_id))
        self.conn.commit()
    
    # ==================== Simulation Methods ====================
    
    def add_simulation(self, scenario_id: int, simulation_type: str = "FDS") -> int:
        """Add a new simulation record"""
        self.cursor.execute("""
            INSERT INTO simulations (scenario_id, simulation_type, start_time, status)
            VALUES (?, ?, CURRENT_TIMESTAMP, 'running')
        """, (scenario_id, simulation_type))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def update_simulation(self, simulation_id: int, status: str, 
                         output_path: str = "", error_message: str = ""):
        """Update simulation status"""
        self.cursor.execute("""
            UPDATE simulations 
            SET status = ?, end_time = CURRENT_TIMESTAMP, 
                output_path = ?, error_message = ?
            WHERE id = ?
        """, (status, output_path, error_message, simulation_id))
        self.conn.commit()
    
    def get_simulations(self, scenario_id: int) -> List[Dict[str, Any]]:
        """Get all simulations for a scenario"""
        self.cursor.execute("""
            SELECT * FROM simulations 
            WHERE scenario_id = ? 
            ORDER BY start_time DESC
        """, (scenario_id,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    # ==================== FED Results Methods ====================
    
    def add_fed_result(self, scenario_id: int, max_fed: float, final_fed: float,
                       fatalities: int, n_people: int, results_dict: Dict = None) -> int:
        """Add FED analysis results"""
        results_json = json.dumps(results_dict) if results_dict else None
        self.cursor.execute("""
            INSERT INTO fed_results 
            (scenario_id, max_fed, final_fed, fatalities, n_people, results_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (scenario_id, max_fed, final_fed, fatalities, n_people, results_json))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_fed_results(self, scenario_id: int) -> List[Dict[str, Any]]:
        """Get FED results for a scenario"""
        self.cursor.execute("""
            SELECT * FROM fed_results 
            WHERE scenario_id = ? 
            ORDER BY analysis_time DESC
        """, (scenario_id,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    # ==================== Monte Carlo Methods ====================
    
    def add_monte_carlo_result(self, project_id: int, n_iterations: int,
                               trim_percentage: float, stats: Dict,
                               results_dict: Dict = None) -> int:
        """Add Monte Carlo analysis results"""
        results_json = json.dumps(results_dict) if results_dict else None
        self.cursor.execute("""
            INSERT INTO monte_carlo_results 
            (project_id, n_iterations, trim_percentage, 
             mean_fatalities, median_fatalities, std_fatalities,
             p5_fatalities, p95_fatalities, results_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project_id, n_iterations, trim_percentage,
              stats.get('mean', 0), stats.get('median', 0), stats.get('std', 0),
              stats.get('p5', 0), stats.get('p95', 0), results_json))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_monte_carlo_results(self, project_id: int) -> List[Dict[str, Any]]:
        """Get Monte Carlo results for a project"""
        self.cursor.execute("""
            SELECT * FROM monte_carlo_results 
            WHERE project_id = ? 
            ORDER BY analysis_time DESC
        """, (project_id,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    # ==================== Configuration Methods ====================
    
    def set_config(self, project_id: int, config_key: str, config_value: str):
        """Set configuration value"""
        self.cursor.execute("""
            INSERT OR REPLACE INTO configuration 
            (project_id, config_key, config_value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (project_id, config_key, config_value))
        self.conn.commit()
    
    def get_config(self, project_id: int, config_key: str) -> Optional[str]:
        """Get configuration value"""
        self.cursor.execute("""
            SELECT config_value FROM configuration 
            WHERE project_id = ? AND config_key = ?
        """, (project_id, config_key))
        row = self.cursor.fetchone()
        return row['config_value'] if row else None
    
    def get_all_config(self, project_id: int) -> Dict[str, str]:
        """Get all configuration for a project"""
        self.cursor.execute("""
            SELECT config_key, config_value FROM configuration 
            WHERE project_id = ?
        """, (project_id,))
        return {row['config_key']: row['config_value'] for row in self.cursor.fetchall()}
    
    # ==================== Statistics Methods ====================
    
    def get_project_statistics(self, project_id: int) -> Dict[str, Any]:
        """Get project statistics summary"""
        stats = {}
        
        # Total scenarios
        self.cursor.execute("""
            SELECT COUNT(*) as count FROM scenarios WHERE project_id = ?
        """, (project_id,))
        stats['total_scenarios'] = self.cursor.fetchone()['count']
        
        # Completed simulations
        self.cursor.execute("""
            SELECT COUNT(*) as count FROM simulations s
            JOIN scenarios sc ON s.scenario_id = sc.id
            WHERE sc.project_id = ? AND s.status = 'completed'
        """, (project_id,))
        stats['completed_simulations'] = self.cursor.fetchone()['count']
        
        # Total fatalities from FED analysis
        self.cursor.execute("""
            SELECT SUM(fatalities) as total FROM fed_results f
            JOIN scenarios sc ON f.scenario_id = sc.id
            WHERE sc.project_id = ?
        """, (project_id,))
        result = self.cursor.fetchone()
        stats['total_fatalities'] = result['total'] if result['total'] else 0
        
        # Latest Monte Carlo result
        self.cursor.execute("""
            SELECT mean_fatalities, median_fatalities 
            FROM monte_carlo_results 
            WHERE project_id = ? 
            ORDER BY analysis_time DESC LIMIT 1
        """, (project_id,))
        mc_result = self.cursor.fetchone()
        if mc_result:
            stats['mc_mean_fatalities'] = mc_result['mean_fatalities']
            stats['mc_median_fatalities'] = mc_result['median_fatalities']
        
        return stats


# ==================== Utility Functions ====================

def create_database(db_path: str) -> QRADatabase:
    """
    Create and initialize a new database
    
    Args:
        db_path: Path to database file
        
    Returns:
        QRADatabase instance
    """
    db = QRADatabase(db_path)
    db.connect()
    return db


if __name__ == "__main__":
    # Test database creation
    import tempfile
    import os
    
    # Create temporary database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_qra.db")
    
    print(f"Creating test database: {db_path}")
    db = create_database(db_path)
    
    # Add test project
    project_id = db.add_project(
        project_name="Test Project",
        description="Test QRA project",
        home_directory="/home/test",
        project_directory="/home/test/test_project"
    )
    print(f"✓ Created project ID: {project_id}")
    
    # Add test scenario
    scenario_id = db.add_scenario(
        project_id=project_id,
        scenario_name="020_N_NVC_pos1000",
        chid="020_N_NVC_pos1000",
        hrr_mw=20,
        fire_position=1000,
        ventilation="NVC"
    )
    print(f"✓ Created scenario ID: {scenario_id}")
    
    # Get projects
    projects = db.get_projects()
    print(f"✓ Retrieved {len(projects)} projects")
    
    # Get scenarios
    scenarios = db.get_scenarios(project_id)
    print(f"✓ Retrieved {len(scenarios)} scenarios")
    
    # Get statistics
    stats = db.get_project_statistics(project_id)
    print(f"✓ Project statistics: {stats}")
    
    db.close()
    print("✓ Database test completed successfully!")
    
    # Cleanup
    os.remove(db_path)
    os.rmdir(temp_dir)
    print("✓ Test database cleaned up")
