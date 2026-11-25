"""Database Access Layer for Streamlit Web Application.

Enforces the strict requirement that all dashboard pages load from PostgreSQL only
with zero runtime CSV reads. Implements st.cache_data for high performance.
"""

import os
from typing import Dict, List, Optional
from dotenv import load_dotenv
import pandas as pd
import psycopg2
import streamlit as st

load_dotenv()


def get_db_connection():
    """Opens a PostgreSQL connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "urban_mobility"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


@st.cache_data(ttl=60)
def fetch_active_run() -> Optional[Dict]:
    """Fetches metadata for the currently active DBSCAN clustering run."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT run_id, eps, min_samples, total_points, num_clusters, 
               noise_points, noise_share, silhouette_score, created_at, notes
        FROM cluster_runs 
        WHERE is_active = TRUE 
        LIMIT 1;
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None

    return {
        "run_id": row[0],
        "eps": row[1],
        "min_samples": row[2],
        "total_points": row[3],
        "num_clusters": row[4],
        "noise_points": row[5],
        "noise_share": row[6],
        "silhouette_score": row[7],
        "created_at": row[8],
        "notes": row[9],
    }


@st.cache_data(ttl=60)
def fetch_telemetry_totals() -> Dict[str, int]:
    """Fetches total row count and zone count directly from traffic_telemetry."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT zone) FROM traffic_telemetry;")
    total_obs, zone_count = cur.fetchone()
    cur.close()
    conn.close()
    return {"total_observations": total_obs, "total_zones": zone_count}


@st.cache_data(ttl=60)
def fetch_zone_summary() -> pd.DataFrame:
    """Fetches aggregated statistics per zone from v_zone_summary view."""
    conn = get_db_connection()
    query = """
        SELECT zone, total_records, avg_queue_density, max_queue_density,
               avg_stop_density, max_stop_density, anomaly_count, anomaly_percentage
        FROM v_zone_summary
        ORDER BY zone ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=60)
def fetch_cluster_distribution() -> pd.DataFrame:
    """Fetches point counts and percentage shares per cluster from active telemetry."""
    conn = get_db_connection()
    query = """
        SELECT cluster_id, cluster_name, COUNT(*) as observation_count,
               ROUND(COUNT(*)::numeric / (SELECT COUNT(*) FROM traffic_telemetry) * 100, 2) as share_pct,
               ROUND(AVG(queue_density)::numeric, 4) as avg_queue_density,
               ROUND(AVG(stop_density)::numeric, 4) as avg_stop_density
        FROM v_active_telemetry_clusters
        GROUP BY cluster_id, cluster_name
        ORDER BY cluster_id ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=60)
def fetch_hourly_profiles() -> pd.DataFrame:
    """Fetches 24-hour cycle hourly averages per cluster from v_hourly_cluster_profile."""
    conn = get_db_connection()
    query = """
        SELECT cluster_id, cluster_name, hour_of_day, 
               avg_queue_density, avg_stop_density, observation_count
        FROM v_hourly_cluster_profile
        ORDER BY cluster_id ASC, hour_of_day ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=60)
def fetch_anomalies(limit: int = 1000) -> pd.DataFrame:
    """Fetches noise anomalies from v_anomalies view."""
    conn = get_db_connection()
    query = f"""
        SELECT id, ts, zone, queue_density, stop_density,
               cluster_name, hour_of_day, day_name, day_type
        FROM v_anomalies
        ORDER BY ts DESC
        LIMIT {limit};
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=60)
def fetch_cluster_export_data() -> pd.DataFrame:
    """Fetches complete clustered records from PostgreSQL for CSV download."""
    conn = get_db_connection()
    query = """
        SELECT id, ts, zone, queue_density, stop_density, cluster_id, cluster_name, day_name, day_type
        FROM v_active_telemetry_clusters
        ORDER BY ts ASC, zone ASC;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
