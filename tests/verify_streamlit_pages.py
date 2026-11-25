"""Verifies that all Streamlit database loader functions query PostgreSQL successfully and CSV download works."""

import io
import sys
from pathlib import Path
import pandas as pd

# Add project root to sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.db import (
    fetch_active_run,
    fetch_telemetry_totals,
    fetch_zone_summary,
    fetch_cluster_distribution,
    fetch_hourly_profiles,
    fetch_anomalies,
    fetch_cluster_export_data,
)

print("=" * 60)
print("STAGE 8 STREAMLIT DATA ACCESS VERIFICATION (POSTGRESQL ONLY)")
print("=" * 60)

# 1. Main Page / Executive Data
run_info = fetch_active_run()
totals = fetch_telemetry_totals()
print(f"[OK] Main Entrypoint: Active Run='{run_info.get('run_id')}', Observations={totals['total_observations']:,}")

# 2. Page 1: Overview Data
df_dist = fetch_cluster_distribution()
df_zones = fetch_zone_summary()
print(f"[OK] Page 1 (Overview): Clusters={len(df_dist)}, Zones={len(df_zones)}")

# 3. Page 2: Patterns Data
df_profiles = fetch_hourly_profiles()
print(f"[OK] Page 2 (Patterns): Hourly Profiles={len(df_profiles)} records")

# 4. Page 3: Zones Data
print(f"[OK] Page 3 (Zones): Summary Table={len(df_zones)} zones loaded")

# 5. Page 4: Anomalies Data
df_anomalies = fetch_anomalies(limit=2000)
print(f"[OK] Page 4 (Anomalies): Loaded {len(df_anomalies)} noise points from v_anomalies")

# 6. Page 5: Method & CSV Export
df_export = fetch_cluster_export_data()
csv_data = df_export.to_csv(index=False).encode("utf-8")
print(f"[OK] Page 5 (Method): CSV Export generated directly from PostgreSQL -> {len(df_export):,} rows, {len(csv_data):,} bytes")

print("=" * 60)
print("ALL STREAMLIT PAGE LOADER FUNCTIONS VERIFIED VIA POSTGRESQL")
print("=" * 60)
