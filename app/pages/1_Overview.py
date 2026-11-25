"""Page 1: Telemetry Overview & Ingestion Metrics."""

import altair as alt
import streamlit as st
from app.db import fetch_cluster_distribution, fetch_telemetry_totals, fetch_zone_summary

st.set_page_config(page_title="Overview | Urban Mobility", layout="wide")

st.title("System Overview & High-Level Telemetry")
st.caption("Telemetry volume, density distributions, and zone baseline summaries.")

totals = fetch_telemetry_totals()
df_dist = fetch_cluster_distribution()
df_zones = fetch_zone_summary()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Mobility Cluster Membership Breakdown")
    if not df_dist.empty:
        chart_pie = (
            alt.Chart(df_dist)
            .mark_arc(innerRadius=50)
            .encode(
                theta=alt.Theta(field="observation_count", type="quantitative"),
                color=alt.Color(field="cluster_name", type="nominal", legend=alt.Legend(title="Cluster Classification")),
                tooltip=["cluster_name", "observation_count", "share_pct", "avg_queue_density"],
            )
            .properties(height=340)
        )
        st.altair_chart(chart_pie, use_container_width=True)

with col2:
    st.subheader("Zone Average Densities Comparison")
    if not df_zones.empty:
        chart_bars = (
            alt.Chart(df_zones)
            .mark_bar()
            .encode(
                x=alt.X("zone:O", title="Traffic Zone"),
                y=alt.Y("avg_queue_density:Q", title="Average Queue Density Ratio (0.0 - 1.0)"),
                color=alt.value("#2b5c8f"),
                tooltip=["zone", "avg_queue_density", "avg_stop_density", "anomaly_count"],
            )
            .properties(height=340)
        )
        st.altair_chart(chart_bars, use_container_width=True)

st.markdown("---")
st.subheader("Zone Density & Reliability Breakdown Table")

if not df_zones.empty:
    st.dataframe(
        df_zones.rename(columns={
            "zone": "Zone ID",
            "total_records": "Observations",
            "avg_queue_density": "Mean Queue Density",
            "max_queue_density": "Max Queue Density",
            "avg_stop_density": "Mean Stop Density",
            "max_stop_density": "Max Stop Density",
            "anomaly_count": "Anomalies",
            "anomaly_percentage": "Anomaly Rate (%)"
        }),
        use_container_width=True,
        hide_index=True,
    )
