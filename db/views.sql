-- Analytical views for Grafana dashboards and Streamlit web application
-- Read from traffic_telemetry, traffic_clusters, and cluster_runs

-- Drop views if existing
DROP VIEW IF EXISTS v_anomalies CASCADE;
DROP VIEW IF EXISTS v_hourly_cluster_profile CASCADE;
DROP VIEW IF EXISTS v_zone_summary CASCADE;
DROP VIEW IF EXISTS v_active_telemetry_clusters CASCADE;

-- 1. Active clustered telemetry: Combines telemetry with active run and human-reviewed names
CREATE OR REPLACE VIEW v_active_telemetry_clusters AS
SELECT 
    t.id,
    t.ts,
    t.zone,
    t.queue_density,
    t.stop_density,
    c.cluster_id,
    CASE 
        WHEN c.cluster_id = -1 THEN 'Severe Traffic Anomalies / Late-Night Spikes'
        WHEN c.cluster_id = 0 THEN 'Zone 1 Central Arterial Normal Flow'
        WHEN c.cluster_id = 1 THEN 'Zone 2 Commercial Spine Normal Flow'
        WHEN c.cluster_id = 2 THEN 'Zone 3 Low-Congestion Steady Corridor'
        WHEN c.cluster_id = 3 THEN 'Zone 4 Moderate Mixed Arterial Flow'
        WHEN c.cluster_id = 4 THEN 'Zone 5 Fluid Low-Queue Transit Flow'
        WHEN c.cluster_id = 5 THEN 'Zone 6 Balanced Urban Corridor Flow'
        WHEN c.cluster_id = 6 THEN 'Zone 3 Afternoon Congestion Surge'
        WHEN c.cluster_id = 7 THEN 'Zone 1 Afternoon Gridlock Spike'
        ELSE 'Cluster ' || c.cluster_id::text
    END AS cluster_name,
    CASE 
        WHEN c.cluster_id = -1 THEN 'Anomaly (Noise)'
        ELSE 'Cluster ' || c.cluster_id::text
    END AS cluster_label,
    r.run_id,
    EXTRACT(HOUR FROM t.ts)::INTEGER AS hour_of_day,
    EXTRACT(DOW FROM t.ts)::INTEGER AS day_of_week,
    TRIM(TO_CHAR(t.ts, 'Day')) AS day_name,
    CASE 
        WHEN EXTRACT(DOW FROM t.ts) IN (0, 6) THEN 'Weekend'
        ELSE 'Weekday'
    END AS day_type
FROM traffic_telemetry t
INNER JOIN traffic_clusters c ON t.id = c.telemetry_id
INNER JOIN cluster_runs r ON c.run_id = r.run_id
WHERE r.is_active = TRUE;

-- 2. Hourly Profile per Cluster: Used by Grafana and Streamlit Patterns page
CREATE OR REPLACE VIEW v_hourly_cluster_profile AS
SELECT 
    cluster_id,
    cluster_name,
    cluster_label,
    hour_of_day,
    ROUND(AVG(queue_density)::numeric, 4) AS avg_queue_density,
    ROUND(AVG(stop_density)::numeric, 4) AS avg_stop_density,
    COUNT(*) AS observation_count
FROM v_active_telemetry_clusters
GROUP BY cluster_id, cluster_name, cluster_label, hour_of_day
ORDER BY cluster_id, hour_of_day;

-- 3. Zone Summary View: Aggregates metrics and anomaly rate per zone
CREATE OR REPLACE VIEW v_zone_summary AS
SELECT 
    t.zone,
    COUNT(t.id) AS total_records,
    ROUND(AVG(t.queue_density)::numeric, 4) AS avg_queue_density,
    ROUND(MAX(t.queue_density)::numeric, 4) AS max_queue_density,
    ROUND(AVG(t.stop_density)::numeric, 4) AS avg_stop_density,
    ROUND(MAX(t.stop_density)::numeric, 4) AS max_stop_density,
    COUNT(CASE WHEN c.cluster_id = -1 THEN 1 END) AS anomaly_count,
    ROUND(
        (COUNT(CASE WHEN c.cluster_id = -1 THEN 1 END)::numeric / NULLIF(COUNT(t.id), 0) * 100), 
        2
    ) AS anomaly_percentage
FROM traffic_telemetry t
LEFT JOIN traffic_clusters c ON t.id = c.telemetry_id
LEFT JOIN cluster_runs r ON c.run_id = r.run_id AND r.is_active = TRUE
GROUP BY t.zone
ORDER BY t.zone;

-- 4. Anomalies View: Noise points flagged by DBSCAN (cluster_id = -1)
CREATE OR REPLACE VIEW v_anomalies AS
SELECT 
    id,
    ts,
    zone,
    queue_density,
    stop_density,
    cluster_name,
    hour_of_day,
    day_name,
    day_type,
    run_id
FROM v_active_telemetry_clusters
WHERE cluster_id = -1
ORDER BY ts DESC;
