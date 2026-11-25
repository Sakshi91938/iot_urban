"""Page 5: Methodology, Assumptions, Limitations & Data Export."""

import streamlit as st
from app.db import fetch_cluster_export_data

st.set_page_config(page_title="Method | Urban Mobility", layout="wide")

st.title("Methodology, Assumptions & Data Export")
st.caption("Technical architecture documentation, honest framing, constraints, and dataset export.")

st.subheader("1. Honest Framing & Operational Context")
st.markdown("""
* **Replay vs. Live Telemetry:** In the absence of real-world road sensor deployment, this system executes an **MQTT historical replay**. Telemetry is streamed sequentially over the `paho-mqtt` broker into PostgreSQL to simulate real-time ingestion.
* **Density Time-Series Analytics:** This project performs **traffic density pattern discovery**, not individual vehicle trajectory tracking.
* **Zero Fabricated Data:** The underlying Delhi Traffic Density Dataset provides second-level `QueueDensity` and `StopDensity` across 6 zones. It contains **no GPS coordinates, no vehicle speeds, and no individual vehicle identifiers**. No synthetic latitude, longitude, or speed was fabricated.
""")

st.markdown("---")
st.subheader("2. Machine Learning Rationale: DBSCAN")
st.markdown("""
* **Density-Based Grouping:** Traffic flow does not naturally form spherical clusters, rendering k-Means inappropriate. DBSCAN groups points based on density connectivity and does not require pre-specifying the number of clusters.
* **Separation of Anomalies:** Unlike k-Means which forces every point into a cluster, DBSCAN identifies points residing in sparse regions as noise (`cluster_id = -1`), providing built-in anomaly detection.
* **Feature Space:** Features incorporate scaled densities (`StandardScaler`), 24-hour cyclic time ($\sin$ and $\cos$ of the hour of the day), and one-hot encoded zone indicators.
* **Hyperparameter Justification:** Parameters $\text{eps} = 0.35$ and $\text{min\_samples} = 10$ were mathematically justified via a 10-NN k-distance elbow curve and an extensive sensitivity grid.
""")

st.markdown("---")
st.subheader("3. Limitations & Constraints")
st.markdown("""
1. **Temporal Coverage:** The dataset spans 40 discrete operating days between September and December 2020.
2. **Daytime Truncation:** Data logging in the source archive runs from 07:00 IST to 22:00 IST daily. Nighttime behavior (22:00 to 07:00) is absent from the raw data.
3. **Macro-Level Density:** Observations represent zone-wide density indices rather than per-lane or intersection-level precision.
""")

st.markdown("---")
st.subheader("4. Export Clustered Dataset")
st.markdown("Download the complete 43,440 clustered telemetry records exported directly from PostgreSQL:")

with st.spinner("Querying clustered dataset from PostgreSQL..."):
    df_export = fetch_cluster_export_data()

if not df_export.empty:
    csv_bytes = df_export.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Clustered Dataset (CSV)",
        data=csv_bytes,
        file_name="urban_mobility_clustered_telemetry.csv",
        mime="text/csv",
        help="Click to download all 43,440 records with cluster assignments from PostgreSQL",
    )
    st.caption(f"Ready for export: {len(df_export):,d} records queried directly from PostgreSQL.")
