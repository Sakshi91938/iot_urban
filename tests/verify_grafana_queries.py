"""Verifies that all SQL queries in the Grafana dashboard execute cleanly on PostgreSQL."""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2

load_dotenv()

dashboard_path = Path("grafana/dashboards/urban_mobility_dashboard.json")
if not dashboard_path.is_file():
    print(f"Error: Dashboard file not found at {dashboard_path}")
    sys.exit(1)

with open(dashboard_path, "r", encoding="utf-8") as f:
    dashboard = json.load(f)

print(f"Loaded Dashboard: '{dashboard['title']}' (UID: {dashboard.get('uid')})")
print(f"Total Panels Configured: {len(dashboard['panels'])}\n")

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("DB_NAME", "urban_mobility"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
)
cur = conn.cursor()

passed = 0
failed = 0

for panel in dashboard["panels"]:
    panel_id = panel.get("id")
    panel_title = panel.get("title", "Untitled")
    panel_type = panel.get("type", "unknown")

    if "targets" in panel and panel["targets"]:
        target = panel["targets"][0]
        raw_sql = target.get("rawSql")
        if raw_sql:
            try:
                cur.execute(raw_sql)
                rows = cur.fetchall()
                print(f"[OK] Panel {panel_id:>3} ({panel_type:<10}) '{panel_title}': {len(rows)} rows returned.")
                passed += 1
            except Exception as e:
                print(f"[FAIL] Panel {panel_id:>3} '{panel_title}': Query Failed -> {e}")
                conn.rollback()
                failed += 1

cur.close()
conn.close()

print(f"\nVerification Results: {passed} Passed, {failed} Failed.")
if failed > 0:
    sys.exit(1)
