-- FDB Conversions Table Schema
-- Tracks FDS to FDB conversions for QRA System

CREATE TABLE IF NOT EXISTS fdb_conversions (
    -- Primary key
    conversion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Foreign key to FDS simulations
    simulation_id INTEGER,
    
    -- File paths
    fds_output_dir TEXT NOT NULL,
    fdb_file_path TEXT NOT NULL,
    config_file_path TEXT,
    
    -- Conversion parameters
    fds_id TEXT,
    axis_direction TEXT,
    vert_direction TEXT,
    time_step INTEGER,
    temp_skip INTEGER,
    
    -- Conversion factors (JSON string)
    conversion_factors TEXT,
    
    -- Variables processed (JSON array)
    variables_processed TEXT,
    
    -- Status
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed
    error_message TEXT,
    
    -- Timestamps
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds REAL,
    
    -- Metadata
    fdb_file_size_bytes INTEGER,
    num_time_steps INTEGER,
    num_variables INTEGER,
    mesh_dimensions TEXT,  -- JSON: {nx, ny, nz}
    
    -- Created/Modified
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    FOREIGN KEY (simulation_id) REFERENCES fds_simulations(simulation_id)
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_fdb_conversions_simulation 
ON fdb_conversions(simulation_id);

CREATE INDEX IF NOT EXISTS idx_fdb_conversions_status 
ON fdb_conversions(status);

CREATE INDEX IF NOT EXISTS idx_fdb_conversions_created 
ON fdb_conversions(created_at);

-- Trigger to update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_fdb_conversions_timestamp 
AFTER UPDATE ON fdb_conversions
BEGIN
    UPDATE fdb_conversions 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE conversion_id = NEW.conversion_id;
END;
