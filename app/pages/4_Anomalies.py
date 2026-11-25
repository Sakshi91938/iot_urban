"""Page 4: Anomaly Detection & Noise Analysis."""

import altair as alt
import streamlit as st
from app.db import fetch_anomalies

st.set_page_config(page_title="Anomalies | Urban Mobility", layout="wide")

st.title("Traffic Anomaly & Congestion Spike Detection")
st.caption("Noise points isolated by DBSCAN (cluster_id = -1) representing severe deviations from standard flow.")

df_anomalies = fetch_anomalies(limit=2000)

if not df_anomalies.empty:
    total_anomalies = len(df_anomalies)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Anomaly Distribution by Hour of Day (IST)")
        hourly_counts = df_anomalies["hour_of_day"].value_counts().reset_index()
        hourly_counts.columns = ["hour_of_day", "count"]

        chart_hour = (
            alt.Chart(hourly_counts)
            .mark_bar()
            .encode(
                x=alt.X("hour_of_day:O", title="Hour of Day (IST)"),
                y=alt.Y("count:Q", title="Number of Anomalies"),
                color=alt.value("#d9534f"),
                tooltip=["hour_of_day", "count"],
            )
            .properties(height=280)
        )
        st.altair_chart(chart_hour, use_container_width=True)

    with col2:
        st.subheader("Anomaly Occurrence by Zone")
        zone_counts = df_anomalies["zone"].value_counts().reset_index()
        zone_counts.columns = ["zone", "count"]

        chart_zone = (
            alt.Chart(zone_counts)
            .mark_bar()
            .encode(
                x=alt.X("zone:O", title="Traffic Zone"),
                y=alt.Y("count:Q", title="Number of Anomalies"),
                color=alt.value("#2b5c8f"),
                tooltip=["zone", "count"],
            )
            .properties(height=280)
        )
        st.altair_chart(chart_zone, use_container_width=True)

    st.markdown("---")
    st.subheader(f"Detailed Anomaly Observation Log ({total_anomalies} records)")

    # Optional zone filter for table
    filter_zone = st.multiselect(
        "Filter by Zone",
        options=sorted(df_anomalies["zone"].unique().tolist()),
        default=sorted(df_anomalies["zone"].unique().tolist()),
    )
    df_table = df_anomalies[df_anomalies["zone"].isin(filter_zone)]

    st.dataframe(
        df_table[[
            "ts", "zone", "queue_density", "stop_density", "hour_of_day", "day_name", "day_type"
        ]].rename(columns={
            "ts": "Timestamp (IST)",
            "zone": "Zone",
            "queue_density": "Queue Density",
            "stop_density": "Stop Density",
            "hour_of_day": "Hour",
            "day_name": "Day",
            "day_type": "Schedule",
        }),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No anomalies found in database.")
