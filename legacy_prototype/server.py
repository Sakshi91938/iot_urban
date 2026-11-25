"""
Urban Mobility Pattern Discovery & IoT Telemetry Intelligence Server
Production-grade REST API and Static Asset Server.
Integrates PostgreSQL database telemetry, pre-processed DBSCAN spatial clusters,
dynamic on-the-fly scikit-learn DBSCAN re-clustering, and real-time IoT stream simulation.
"""

import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import time
import math
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data paths
DBSCAN_RESULTS_FILE = os.path.join(BASE_DIR, "dbscan_results.csv")
VEHICLE_CLUSTERED_FILE = os.path.join(BASE_DIR, "clustered_vehicle_data.csv")
TRAFFIC_SUMMARY_FILE = os.path.join(BASE_DIR, "traffic_summary.csv")
DATASET_FOLDER = os.path.join(BASE_DIR, "dataset", "DelhiTrafficDensityDataset")

# PostgreSQL Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "urban_mobility")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Jaishreemahakal@#$")

# Zone definitions with authentic Delhi geographical metadata
ZONE_METADATA = {
    1: {
        "name": "Zone 1 - Connaught Place Radial",
        "short_name": "Connaught Place",
        "description": "Central business district & radial arterial corridor",
        "lat": 28.6315,
        "lon": 77.2167,
        "speed_limit": 50,
        "corridor_length_km": 4.8
    },
    2: {
        "name": "Zone 2 - Karol Bagh Commercial Arterial",
        "short_name": "Karol Bagh",
        "description": "Dense mixed-use market & Pusa Road transit spine",
        "lat": 28.6514,
        "lon": 77.1907,
        "speed_limit": 45,
        "corridor_length_km": 5.2
    },
    3: {
        "name": "Zone 3 - Kashmere Gate Inter-modal Hub",
        "short_name": "Kashmere Gate",
        "description": "Major ISBT terminal & northern metro interchange corridor",
        "lat": 28.6675,
        "lon": 77.2285,
        "speed_limit": 50,
        "corridor_length_km": 6.1
    },
    4: {
        "name": "Zone 4 - Ring Road (AIIMS - South Ext.)",
        "short_name": "Ring Road (South)",
        "description": "Heavy arterial beltway with major hospital and retail access",
        "lat": 28.5672,
        "lon": 77.2100,
        "speed_limit": 60,
        "corridor_length_km": 8.4
    },
    5: {
        "name": "Zone 5 - Vikas Marg / ITO Trans-Yamuna",
        "short_name": "ITO - Vikas Marg",
        "description": "Critical bridge bottleneck connecting East Delhi & Central Secretariat",
        "lat": 28.6289,
        "lon": 77.2415,
        "speed_limit": 50,
        "corridor_length_km": 5.7
    },
    6: {
        "name": "Zone 6 - Outer Ring Road / Dhaula Kuan",
        "short_name": "Dhaula Kuan",
        "description": "Strategic interchange connecting Airport Express & South-West corridors",
        "lat": 28.5921,
        "lon": 77.1563,
        "speed_limit": 70,
        "corridor_length_km": 9.2
    }
}

# In-memory datasets
df_telemetry = None
df_vehicles = None
df_summary = None
db_connected = False
stream_cursor_idx = 0

def init_database():
    """Attempt connecting to PostgreSQL and return status."""
    global db_connected
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            connect_timeout=3
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM traffic_telemetry;")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"[Database] Connected to PostgreSQL 'urban_mobility' ({count:,} records).")
        db_connected = True
        return True
    except Exception as e:
        print(f"[Database] PostgreSQL unavailable ({e}). Using high-speed CSV storage engine.")
        db_connected = False
        return False

def load_data():
    """Load local telemetry and vehicle datasets into memory."""
    global df_telemetry, df_vehicles, df_summary
    print("[Data Engine] Loading telemetry and spatial datasets...")
    
    # 1. Main Telemetry & DBSCAN Results (43,440 records)
    if os.path.exists(DBSCAN_RESULTS_FILE):
        df_telemetry = pd.read_csv(DBSCAN_RESULTS_FILE)
        df_telemetry["timestamp"] = pd.to_datetime(df_telemetry["timestamp"])
        df_telemetry["hour"] = df_telemetry["timestamp"].dt.hour
        print(f"[Data Engine] Loaded {len(df_telemetry):,} telemetry records from dbscan_results.csv")
    else:
        print("[Data Engine] ERROR: dbscan_results.csv not found!")
        df_telemetry = pd.DataFrame()

    # 2. Clustered Vehicle GPS Data
    if os.path.exists(VEHICLE_CLUSTERED_FILE):
        df_vehicles = pd.read_csv(VEHICLE_CLUSTERED_FILE)
        print(f"[Data Engine] Loaded {len(df_vehicles)} vehicle GPS probe points.")
    else:
        print("[Data Engine] Warning: clustered_vehicle_data.csv not found.")
        df_vehicles = pd.DataFrame()

    # 3. Traffic Summary
    if os.path.exists(TRAFFIC_SUMMARY_FILE):
        df_summary = pd.read_csv(TRAFFIC_SUMMARY_FILE)
    else:
        df_summary = pd.DataFrame()

class UrbanIoTRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Production REST API & Static File Server for Urban IoT Platform."""

    def end_headers(self):
        # Enable CORS and disable caching for API endpoints
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # API routing
        if path == "/api/overview":
            self.handle_api_overview()
        elif path == "/api/zones":
            self.handle_api_zones()
        elif path == "/api/diurnal":
            self.handle_api_diurnal()
        elif path == "/api/clusters":
            self.handle_api_clusters()
        elif path == "/api/vehicles":
            self.handle_api_vehicles()
        elif path == "/api/anomalies":
            self.handle_api_anomalies(query)
        elif path == "/api/scatter-sample":
            self.handle_api_scatter_sample(query)
        elif path == "/api/stream-next":
            self.handle_api_stream_next()
        elif path == "/api/export":
            self.handle_api_export()
        else:
            # Fallback to static web files
            if path == "/" or path == "":
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == "/api/dbscan-tune":
            self.handle_api_dbscan_tune()
        else:
            self.send_json({"error": "Endpoint not found"}, status_code=404)

    def send_json(self, data, status_code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    # -----------------------------
    # API ENDPOINT IMPLEMENTATIONS
    # -----------------------------

    def handle_api_overview(self):
        """High-level system KPIs and pipeline health."""
        if df_telemetry is None or df_telemetry.empty:
            self.send_json({"error": "Telemetry data unavailable"}, status_code=500)
            return

        total_records = len(df_telemetry)
        active_zones = int(df_telemetry["zone"].nunique())
        anomalies_count = int((df_telemetry["cluster"] == -1).sum())
        mean_queue = round(float(df_telemetry["queue_density"].mean()), 4)
        max_queue = round(float(df_telemetry["queue_density"].max()), 4)
        mean_stop = round(float(df_telemetry["stop_density"].mean()), 4)
        max_stop = round(float(df_telemetry["stop_density"].max()), 4)

        avg_speed = 46.85
        if df_vehicles is not None and not df_vehicles.empty:
            avg_speed = round(float(df_vehicles["speed"].mean()), 2)

        payload = {
            "status": "OPERATIONAL",
            "database_connected": db_connected,
            "database_type": "PostgreSQL" if db_connected else "High-Speed Memory Cache",
            "mqtt_broker": "localhost:1883 / test.mosquitto.org",
            "mqtt_topic": "urban_iot_project/traffic",
            "telemetry_window": "5-Minute Quantized Windows",
            "total_records": total_records,
            "active_zones": active_zones,
            "anomalies_detected": anomalies_count,
            "mean_queue_density": mean_queue,
            "max_queue_density": max_queue,
            "mean_stop_density": mean_stop,
            "max_stop_density": max_stop,
            "average_fleet_speed": avg_speed,
            "time_range": {
                "start": str(df_telemetry["timestamp"].min()),
                "end": str(df_telemetry["timestamp"].max())
            }
        }
        self.send_json(payload)

    def handle_api_zones(self):
        """Corridor breakdown across all 6 monitoring zones."""
        if df_telemetry is None or df_telemetry.empty:
            self.send_json({"error": "Telemetry data unavailable"}, status_code=500)
            return

        zones_list = []
        for zone_id in sorted(df_telemetry["zone"].unique()):
            zone_df = df_telemetry[df_telemetry["zone"] == zone_id]
            meta = ZONE_METADATA.get(int(zone_id), {
                "name": f"Corridor {zone_id}",
                "short_name": f"Zone {zone_id}",
                "description": "Urban traffic segment",
                "lat": 28.65,
                "lon": 77.20,
                "speed_limit": 50,
                "corridor_length_km": 5.0
            })

            mean_q = float(zone_df["queue_density"].mean())
            max_q = float(zone_df["queue_density"].max())
            mean_s = float(zone_df["stop_density"].mean())
            max_s = float(zone_df["stop_density"].max())
            anomalies = int((zone_df["cluster"] == -1).sum())

            # Congestion index score (0-100)
            congestion_score = round((mean_q * 0.6 + mean_s * 0.4) * 100, 1)

            if congestion_score >= 60:
                traffic_status = "Critical Bottleneck"
                status_color = "#ef4444"
            elif congestion_score >= 40:
                traffic_status = "Moderate Flow"
                status_color = "#f59e0b"
            else:
                traffic_status = "Free Flow"
                status_color = "#10b981"

            zones_list.append({
                "zone_id": int(zone_id),
                "name": meta["name"],
                "short_name": meta["short_name"],
                "description": meta["description"],
                "lat": meta["lat"],
                "lon": meta["lon"],
                "speed_limit": meta["speed_limit"],
                "corridor_length_km": meta["corridor_length_km"],
                "total_records": len(zone_df),
                "mean_queue_density": round(mean_q, 4),
                "max_queue_density": round(max_q, 4),
                "mean_stop_density": round(mean_s, 4),
                "max_stop_density": round(max_s, 4),
                "congestion_score": congestion_score,
                "traffic_status": traffic_status,
                "status_color": status_color,
                "anomaly_count": anomalies
            })

        self.send_json({"zones": zones_list})

    def handle_api_diurnal(self):
        """24-Hour Diurnal congestion profiles showing morning and evening peak hours."""
        if df_telemetry is None or df_telemetry.empty:
            self.send_json({"error": "Telemetry data unavailable"}, status_code=500)
            return

        hourly_all = df_telemetry.groupby("hour").agg({
            "queue_density": "mean",
            "stop_density": "mean"
        }).reset_index()

        hourly_data = []
        for _, row in hourly_all.iterrows():
            hour_val = int(row["hour"])
            hourly_data.append({
                "hour": hour_val,
                "hour_label": f"{hour_val:02d}:00",
                "queue_density": round(float(row["queue_density"]), 4),
                "stop_density": round(float(row["stop_density"]), 4)
            })

        # Also provide zone-specific diurnal matrices
        zone_diurnals = {}
        for z in sorted(df_telemetry["zone"].unique()):
            z_df = df_telemetry[df_telemetry["zone"] == z]
            z_grp = z_df.groupby("hour")["queue_density"].mean().to_dict()
            zone_diurnals[int(z)] = {int(h): round(float(val), 4) for h, val in z_grp.items()}

        self.send_json({
            "network_diurnal": hourly_data,
            "zone_diurnals": zone_diurnals
        })

    def handle_api_clusters(self):
        """Micro-mobility GPS clusters discovered via spatial DBSCAN."""
        if df_vehicles is None or df_vehicles.empty:
            self.send_json({"error": "Vehicle data unavailable"}, status_code=500)
            return

        clusters_info = []
        for cluster_id in sorted(df_vehicles["cluster"].unique()):
            c_df = df_vehicles[df_vehicles["cluster"] == cluster_id]
            mean_lat = float(c_df["latitude"].mean())
            mean_lon = float(c_df["longitude"].mean())
            mean_spd = float(c_df["speed"].mean())
            min_spd = float(c_df["speed"].min())
            max_spd = float(c_df["speed"].max())
            v_count = len(c_df)

            if mean_spd < 40:
                status = "High Traffic"
                badge_color = "#ef4444"
            elif mean_spd < 55:
                status = "Medium Traffic"
                badge_color = "#f59e0b"
            else:
                status = "Low Traffic"
                badge_color = "#10b981"

            # Associate with nearest neighborhood
            if cluster_id == 0:
                neighborhood = "Kashmere Gate / Tis Hazari Corridor"
            elif cluster_id == 1:
                neighborhood = "Karol Bagh / Jhandewalan Corridor"
            elif cluster_id == 2:
                neighborhood = "Model Town / Azadpur Corridor"
            else:
                neighborhood = f"Discovered Cluster {cluster_id}"

            clusters_info.append({
                "cluster_id": int(cluster_id),
                "neighborhood": neighborhood,
                "centroid": {"lat": round(mean_lat, 6), "lon": round(mean_lon, 6)},
                "vehicle_count": v_count,
                "mean_speed_kmh": round(mean_spd, 2),
                "min_speed_kmh": round(min_spd, 2),
                "max_speed_kmh": round(max_spd, 2),
                "traffic_status": status,
                "badge_color": badge_color
            })

        self.send_json({"clusters": clusters_info})

    def handle_api_vehicles(self):
        """Raw vehicle probe GPS coordinates for map layers."""
        if df_vehicles is None or df_vehicles.empty:
            self.send_json({"vehicles": []})
            return

        records = df_vehicles.to_dict(orient="records")
        self.send_json({"vehicles": records})

    def handle_api_anomalies(self, query):
        """Return the DBSCAN cluster == -1 anomaly points with context."""
        if df_telemetry is None or df_telemetry.empty:
            self.send_json({"anomalies": []})
            return

        anomalies_df = df_telemetry[df_telemetry["cluster"] == -1].copy()
        
        # Sort by queue density descending
        anomalies_df = anomalies_df.sort_values(by="queue_density", ascending=False)

        anomalies_list = []
        for _, row in anomalies_df.iterrows():
            zone_id = int(row["zone"])
            meta = ZONE_METADATA.get(zone_id, {
                "name": f"Zone {zone_id}",
                "short_name": f"Zone {zone_id}",
                "lat": 28.65,
                "lon": 77.20
            })
            
            # Severity computation based on deviation from norm
            q_val = float(row["queue_density"])
            s_val = float(row["stop_density"])
            severity = round((q_val * 0.7 + s_val * 0.3) * 100, 1)

            anomalies_list.append({
                "id": int(row["id"]),
                "timestamp": str(row["timestamp"]),
                "zone_id": zone_id,
                "zone_name": meta["name"],
                "short_name": meta["short_name"],
                "lat": meta["lat"],
                "lon": meta["lon"],
                "queue_density": round(q_val, 6),
                "stop_density": round(s_val, 6),
                "cluster": -1,
                "severity_index": severity,
                "status_tag": "CRITICAL SPIKE" if severity > 80 else "SEVERE ANOMALY"
            })

        self.send_json({"anomalies": anomalies_list})

    def handle_api_scatter_sample(self, query):
        """Downsampled points for the Queue vs Stop density scatter plot."""
        if df_telemetry is None or df_telemetry.empty:
            self.send_json({"points": []})
            return

        limit = int(query.get("limit", [1200])[0])
        zone_filter = query.get("zone", [None])[0]

        filtered_df = df_telemetry
        if zone_filter and zone_filter.isdigit():
            filtered_df = filtered_df[filtered_df["zone"] == int(zone_filter)]

        # Sample stratified by cluster so all anomalies are guaranteed to be included
        anomalies_sample = filtered_df[filtered_df["cluster"] == -1]
        normal_pool = filtered_df[filtered_df["cluster"] != -1]

        normal_sample = normal_pool.sample(min(limit, len(normal_pool)), random_state=42)
        combined = pd.concat([normal_sample, anomalies_sample]).drop_duplicates(subset=["id"])

        points = []
        for _, row in combined.iterrows():
            points.append({
                "id": int(row["id"]),
                "z": int(row["zone"]),
                "q": round(float(row["queue_density"]), 4),
                "s": round(float(row["stop_density"]), 4),
                "c": int(row["cluster"])
            })

        self.send_json({"points": points, "total_rendered": len(points)})

    def handle_api_dbscan_tune(self):
        """Dynamic DBSCAN Re-clustering API with user-specified eps and min_samples."""
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_len)
            params = json.loads(body_bytes.decode("utf-8"))

            eps = float(params.get("eps", 0.35))
            min_samples = int(params.get("min_samples", 10))

            if eps <= 0 or min_samples < 2:
                self.send_json({"error": "Invalid DBSCAN parameters"}, status_code=400)
                return

            if df_telemetry is None or df_telemetry.empty:
                self.send_json({"error": "Dataset not available"}, status_code=500)
                return

            # Perform DBSCAN on standardized features
            start_time = time.time()
            features = df_telemetry[["queue_density", "stop_density"]].copy()
            scaler = StandardScaler()
            X = scaler.fit_transform(features)

            db = DBSCAN(eps=eps, min_samples=min_samples)
            clusters = db.fit_predict(X)
            elapsed = round((time.time() - start_time) * 1000, 1)

            # Analyze output distribution
            unique_clusters, counts = np.unique(clusters, return_counts=True)
            dist = {int(k): int(v) for k, v in zip(unique_clusters, counts)}

            num_clusters = len([c for c in unique_clusters if c != -1])
            anomaly_count = int(dist.get(-1, 0))
            anomaly_ratio = round((anomaly_count / len(clusters)) * 100, 3)

            # Extract sample of new anomaly points
            anomaly_indices = np.where(clusters == -1)[0]
            sample_size = min(50, len(anomaly_indices))
            sampled_anomalies = []
            if sample_size > 0:
                sample_idx = np.random.choice(anomaly_indices, sample_size, replace=False)
                for idx in sample_idx:
                    row = df_telemetry.iloc[idx]
                    sampled_anomalies.append({
                        "id": int(row["id"]),
                        "timestamp": str(row["timestamp"]),
                        "zone": int(row["zone"]),
                        "queue_density": round(float(row["queue_density"]), 4),
                        "stop_density": round(float(row["stop_density"]), 4)
                    })

            response_data = {
                "eps": eps,
                "min_samples": min_samples,
                "computation_time_ms": elapsed,
                "total_records": len(clusters),
                "num_clusters_found": num_clusters,
                "anomaly_count": anomaly_count,
                "anomaly_ratio_pct": anomaly_ratio,
                "cluster_distribution": dist,
                "sample_anomalies": sampled_anomalies
            }
            self.send_json(response_data)

        except Exception as e:
            self.send_json({"error": f"DBSCAN execution failed: {str(e)}"}, status_code=500)

    def handle_api_stream_next(self):
        """Simulate real-time IoT MQTT packet arrival from dataset."""
        global stream_cursor_idx
        if df_telemetry is None or df_telemetry.empty:
            self.send_json({"error": "No data"}, status_code=500)
            return

        row = df_telemetry.iloc[stream_cursor_idx % len(df_telemetry)]
        stream_cursor_idx += 1

        zone_id = int(row["zone"])
        meta = ZONE_METADATA.get(zone_id, {
            "name": f"Zone {zone_id}",
            "short_name": f"Zone {zone_id}",
            "lat": 28.65,
            "lon": 77.20
        })

        q = float(row["queue_density"])
        s = float(row["stop_density"])
        c = int(row["cluster"])

        packet = {
            "packet_id": f"PKT-{int(row['id']):06d}",
            "topic": "urban_iot_project/traffic",
            "timestamp": str(row["timestamp"]),
            "zone_id": zone_id,
            "corridor": meta["short_name"],
            "lat": meta["lat"],
            "lon": meta["lon"],
            "queue_density": round(q, 6),
            "stop_density": round(s, 6),
            "cluster_flag": c,
            "is_anomaly": (c == -1),
            "qos": 1,
            "broker": "MQTT-UrbanIoT-Gateway"
        }
        self.send_json(packet)

    def handle_api_export(self):
        """Export telemetry analysis report as CSV."""
        if df_telemetry is None or df_telemetry.empty:
            self.send_json({"error": "No data"}, status_code=500)
            return

        csv_str = df_telemetry.head(2000).to_csv(index=False)
        body = csv_str.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Disposition", "attachment; filename=\"urban_traffic_telemetry_export.csv\"")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def run_server():
    """Start the multi-threaded HTTP server."""
    # Step 1: Initialize DB connection
    init_database()

    # Step 2: Load data
    load_data()

    # Step 3: Start HTTP Server
    handler = UrbanIoTRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), handler) as httpd:
        print("\n" + "=" * 70)
        print("  URBAN MOBILITY INTELLIGENCE PLATFORM (IoT & DBSCAN)")
        print(f"  Server listening on: http://localhost:{PORT}")
        print("  API Overview:       http://localhost:{PORT}/api/overview")
        print("  Zones Telemetry:    http://localhost:{PORT}/api/zones")
        print("  Anomalies Feed:     http://localhost:{PORT}/api/anomalies")
        print("  Interactive Web UI: http://localhost:{PORT}")
        print("=" * 70 + "\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Urban IoT server cleanly...")
            httpd.shutdown()

if __name__ == "__main__":
    run_server()
