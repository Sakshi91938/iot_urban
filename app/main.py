"""AI-Based Urban Mobility Pattern Discovery — Streamlit Dashboard.

Executive entrypoint and pipeline status monitoring.
Built strictly with Python, Altair, and PostgreSQL.
"""

import streamlit as st
from app.db import fetch_active_run, fetch_telemetry_totals, fetch_zone_summary

st.set_page_config(
    page_title="Urban Mobility Discovery",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("AI-Based Urban Mobility Pattern Discovery")
st.caption("Telemetry Pattern Discovery, Ingestion Pipeline & Anomaly Analytics")

# Top Notification / Status Banner
run_info = fetch_active_run()
totals = fetch_telemetry_totals()

if run_info and totals["total_observations"] > 0:
    st.info(
        f"Active Model Run: {run_info['run_id']} | "
        f"Algorithm: DBSCAN (eps={run_info['eps']}, min_samples={run_info['min_samples']}) | "
        f"Data Source: PostgreSQL ({totals['total_observations']:,} observations across {totals['total_zones']} zones)"
    )
else:
    st.warning("Database contains no active clustering run. Please verify Stage 4 replay and Stage 5 clustering.")

st.markdown("---")

# Executive Metric Cards
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(label="Total Observations", value=f"{totals['total_observations']:,}")
with c2:
    clusters_count = run_info["num_clusters"] if run_info else 0
    st.metric(label="Mobility Clusters", value=str(clusters_count))
with c3:
    anomalies_count = run_info["noise_points"] if run_info else 0
    st.metric(label="Detected Anomalies", value=str(anomalies_count))
with c4:
    anomaly_pct = run_info["noise_share"] if run_info else 0.0
    st.metric(label="Anomaly Share Ratio", value=f"{anomaly_pct:.2f}%")

st.markdown("---")

st.subheader("System Pipeline Architecture")
st.markdown("""
This system implements an end-to-end data pipeline discovering macro-mobility regimes and traffic anomalies 
from the Delhi Traffic Density Dataset:

1. **Replay Source:** 40 daily time-series CSVs (Sep–Dec 2020) capturing 6 road zones in 5-minute aggregations.
2. **Ingestion Engine:** Sequential MQTT replay published over topic `urban/traffic/zone/<id>/telemetry`.
3. **Database Layer:** PostgreSQL instance storing raw telemetry and cluster mappings with unique constraints on `(ts, zone)`.
4. **AI/ML Layer:** Standardized feature space (cyclic hour-of-day + scaled densities + one-hot zones) clustered via scikit-learn DBSCAN.
5. **Dashboards:** Provisioned Grafana dashboard and this minimal Streamlit reporting web application.

Use the left sidebar navigation to explore **Overview**, **Patterns**, **Zones**, **Anomalies**, and the **Method** page.
""")

st.markdown("---")
st.subheader("Zone Telemetry Baseline Overview")
df_zones = fetch_zone_summary()
if not df_zones.empty:
    st.dataframe(
        df_zones.rename(columns={
            "zone": "Zone",
            "total_records": "Total Records",
            "avg_queue_density": "Avg Queue Density",
            "max_queue_density": "Peak Queue Density",
            "avg_stop_density": "Avg Stop Density",
            "max_stop_density": "Peak Stop Density",
            "anomaly_count": "Anomaly Count",
            "anomaly_percentage": "Anomaly %"
        }),
        use_container_width=True,
        hide_index=True,
    )
