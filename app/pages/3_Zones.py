"""Page 3: Zone Comparative Analysis & Corridor Breakdown."""

import altair as alt
import streamlit as st
from app.db import fetch_zone_summary

st.set_page_config(page_title="Zones | Urban Mobility", layout="wide")

st.title("Urban Zone Density Analysis")
st.caption("Cross-zone congestion comparison, peak density thresholds, and corridor profiles.")

df_zones = fetch_zone_summary()

if not df_zones.empty:
    # Zone selector filter
    selected_zone = st.selectbox(
        "Select Zone for Deep Inspection",
        options=["All Zones"] + [f"Zone {z}" for z in df_zones["zone"].tolist()],
        index=0,
    )

    if selected_zone != "All Zones":
        z_id = int(selected_zone.replace("Zone ", ""))
        df_filtered = df_zones[df_zones["zone"] == z_id]
    else:
        df_filtered = df_zones

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Queue Density vs. Stop Density (Zone Comparison)")
        chart_bars = (
            alt.Chart(df_zones)
            .transform_fold(["avg_queue_density", "avg_stop_density"], as_=["Metric", "Density"])
            .mark_bar()
            .encode(
                x=alt.X("zone:O", title="Traffic Zone"),
                y=alt.Y("Density:Q", title="Density Ratio (0.0 - 1.0)"),
                color=alt.Color("Metric:N", scale=alt.Scale(range=["#2b5c8f", "#d9534f"]), 
                                legend=alt.Legend(title="Metric Type", labelExpr="datum.label == 'avg_queue_density' ? 'Average Queue' : 'Average Stop'")),
                xOffset="Metric:N",
                tooltip=["zone:O", "Metric:N", "Density:Q"],
            )
            .properties(height=340)
        )
        st.altair_chart(chart_bars, use_container_width=True)

    with col2:
        st.subheader("Peak Bottleneck Densities by Zone")
        chart_peak = (
            alt.Chart(df_zones)
            .mark_bar()
            .encode(
                x=alt.X("zone:O", title="Traffic Zone"),
                y=alt.Y("max_queue_density:Q", title="Peak Observed Queue Density (0.0 - 1.0)"),
                color=alt.value("#6c757d"),
                tooltip=["zone", "max_queue_density", "max_stop_density"],
            )
            .properties(height=340)
        )
        st.altair_chart(chart_peak, use_container_width=True)

    st.markdown("---")
    st.subheader(f"Metrics Table — {selected_zone}")
    st.dataframe(
        df_filtered.rename(columns={
            "zone": "Zone",
            "total_records": "Observations",
            "avg_queue_density": "Avg Queue",
            "max_queue_density": "Peak Queue",
            "avg_stop_density": "Avg Stop",
            "max_stop_density": "Peak Stop",
            "anomaly_count": "Anomalies",
            "anomaly_percentage": "Anomaly Rate (%)"
        }),
        use_container_width=True,
        hide_index=True,
    )
