"""Page 2: Mobility Pattern Discovery & Cluster Profiles."""

import altair as alt
import streamlit as st
from app.db import fetch_cluster_distribution, fetch_hourly_profiles

st.set_page_config(page_title="Patterns | Urban Mobility", layout="wide")

st.title("Discovered Urban Mobility Patterns")
st.caption("Temporal regimes, 24-hour progression cycles, and recurring density clusters.")

df_profiles = fetch_hourly_profiles()
df_dist = fetch_cluster_distribution()

st.subheader("24-Hour Hourly Progression by Mobility Cluster")
if not df_profiles.empty:
    chart_line = (
        alt.Chart(df_profiles)
        .mark_line(point=True)
        .encode(
            x=alt.X("hour_of_day:Q", title="Hour of Day (IST, 0-23)", scale=alt.Scale(domain=[0, 23])),
            y=alt.Y("avg_queue_density:Q", title="Average Queue Density (Ratio 0.0 - 1.0)"),
            color=alt.Color("cluster_name:N", legend=alt.Legend(title="Mobility Cluster")),
            tooltip=["cluster_name", "hour_of_day", "avg_queue_density", "observation_count"],
        )
        .properties(height=380)
        .interactive()
    )
    st.altair_chart(chart_line, use_container_width=True)

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Cluster Profile Characteristics")
    if not df_dist.empty:
        st.dataframe(
            df_dist.rename(columns={
                "cluster_id": "Cluster ID",
                "cluster_name": "Cluster Designation",
                "observation_count": "Count",
                "share_pct": "Share (%)",
                "avg_queue_density": "Avg Queue",
                "avg_stop_density": "Avg Stop",
            }),
            use_container_width=True,
            hide_index=True,
        )

with col2:
    st.subheader("Key Recurring Discoveries")
    st.markdown("""
    * **Daytime Stability:** Clusters 0 through 5 capture standard daytime mobility between 07:00 and 22:00 IST across each zone, reflecting predictable baseline movement.
    * **Midday Congestion Spikes:** Clusters 6 and 7 represent localized acute bottlenecks:
      - **Cluster 6 (Zone 3):** Sustains elevated queue density (`0.6288`) between 10:00 and 22:00 IST.
      - **Cluster 7 (Zone 1):** Gridlock surges (`0.6202`) between 09:00 and 22:00 IST.
    * **Temporal Invariance:** Weekday traffic (`0.4559`) differs from weekend traffic (`0.4495`) by only 1.4%, revealing that Delhi arterial corridors operate under near-constant transit demand 7 days a week.
    """)
