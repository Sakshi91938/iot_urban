-- Schema for AI-Based Urban Mobility Pattern Discovery
-- Supports idempotent MQTT telemetry ingestion and traceable DBSCAN runs

-- Drop existing tables to establish clean state
DROP TABLE IF EXISTS traffic_clusters CASCADE;
DROP TABLE IF EXISTS cluster_runs CASCADE;
DROP TABLE IF EXISTS traffic_telemetry CASCADE;

-- 1. Telemetry table storing 5-minute bucketed density time series
CREATE TABLE traffic_telemetry (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    zone INTEGER NOT NULL,
    queue_density DOUBLE PRECISION NOT NULL,
    stop_density DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_telemetry_ts_zone UNIQUE (ts, zone)
);

-- Indexes for time-range and zone filtering
CREATE INDEX idx_telemetry_ts ON traffic_telemetry (ts);
CREATE INDEX idx_telemetry_zone ON traffic_telemetry (zone);
CREATE INDEX idx_telemetry_zone_ts ON traffic_telemetry (zone, ts);

-- 2. Traceable DBSCAN clustering runs table
CREATE TABLE cluster_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    eps DOUBLE PRECISION NOT NULL,
    min_samples INTEGER NOT NULL,
    features_used TEXT NOT NULL,
    total_points INTEGER NOT NULL,
    num_clusters INTEGER NOT NULL,
    noise_points INTEGER NOT NULL,
    noise_share DOUBLE PRECISION NOT NULL,
    silhouette_score DOUBLE PRECISION,
    is_active BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Traffic clusters mapping table
CREATE TABLE traffic_clusters (
    telemetry_id INTEGER NOT NULL REFERENCES traffic_telemetry(id) ON DELETE CASCADE,
    cluster_id INTEGER NOT NULL,
    run_id VARCHAR(64) NOT NULL REFERENCES cluster_runs(run_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (telemetry_id, run_id)
);

-- Indexes for cluster analytics
CREATE INDEX idx_clusters_cluster_id ON traffic_clusters (cluster_id);
CREATE INDEX idx_clusters_run_id ON traffic_clusters (run_id);
