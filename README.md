# AI-Based Urban Mobility Pattern Discovery

[![CI](https://github.com/Sakshi91938/iot_urban/actions/workflows/ci.yml/badge.svg)](https://github.com/Sakshi91938/iot_urban/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 1. Project Purpose & Scope

This project implements an end-to-end telemetry and machine learning pipeline for discovering recurring traffic patterns and detecting congestion anomalies across urban zones.

### Honest Framing & Data Constraints
* **Replay vs. Live:** In the absence of physical road sensors, this system operates an **MQTT replay** of historical telemetry. It simulates real-time ingestion by streaming recorded traffic data sequentially over MQTT.
* **Telemetry Modality:** The underlying dataset contains second-by-second aggregated density measurements (`QueueDensity` and `StopDensity`) across 6 designated zones from the Delhi Traffic Density Dataset (Sep–Dec 2020).
* **No Fabricated Data:** The dataset contains **no GPS coordinates, no vehicle trajectories, no speeds, and no individual vehicle identifiers**. This project performs **density time-series pattern discovery**, not individual vehicle tracking.

---

## 2. Pipeline Architecture

```
[ Delhi Traffic CSVs (Sep-Dec 2020) ]
                 │
                 ▼
     [ pipeline/prepare.py ]
   (Cleaning & 5-min aggregation)
                 │
                 ▼
    [ pipeline/publisher.py ]
                 │ (MQTT JSON payloads: urban/traffic/zone/<id>/telemetry)
                 ▼
      [ Mosquitto MQTT Broker ]
                 │
                 ▼
   [ pipeline/subscriber.py ]
                 │ (Idempotent batch ingestion ON CONFLICT DO NOTHING)
                 ▼
       [ PostgreSQL Database ]
                 │
                 ▼
   [ pipeline/features.py & cluster.py ]
                 │ (Cyclic hours + Density scaling -> DBSCAN)
                 ▼
     [ PostgreSQL Cluster Tables & Views ]
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
 [ Grafana Dashboard ]   [ Streamlit App ]
   (Port 3000)             (Port 8501)
```

---

## 3. Technology Stack

| Layer | Component | Description |
|---|---|---|
| **Language** | Python 3.11 | Core runtime for data processing and applications |
| **Broker** | Mosquitto (MQTT) | Pub/Sub messaging engine for telemetry stream |
| **Database** | PostgreSQL | Relational storage for telemetry, clusters, and runs |
| **Machine Learning**| scikit-learn (DBSCAN) | Density-based spatial clustering of applications with noise |
| **Analytics** | pandas, numpy | Data cleaning, 5-minute bucket aggregation, feature engineering |
| **Dashboards** | Grafana & Streamlit | Automated visualization (Grafana as code + Streamlit web app) |
| **Containerization**| Docker & Docker Compose | Multi-container orchestration |
| **CI/CD** | GitHub Actions & GHCR | Automated linting, testing, and container deployment |
| **Quality** | pytest, ruff | Unit testing and PEP8 code quality standards |

---

## 4. Repository Structure

```
urban-mobility/
├── app/                  # Streamlit multi-page web application
├── pipeline/             # Data cleaning, MQTT replay, DBSCAN clustering, analytics
├── db/                   # PostgreSQL schema and analytical views
├── grafana/              # Provisioning configs and pre-built dashboard JSON
├── mosquitto/            # Local Mosquitto broker configuration
├── tests/                # Automated pytest unit test suite
├── data/
│   └── raw/              # Raw dataset archive (gitignored)
├── .github/workflows/    # CI (test & lint) and CD (GHCR publish) pipelines
├── docker-compose.yml    # Complete stack container composition
├── Dockerfile            # Container image specification
├── requirements.txt      # Pinned Python package dependencies
├── .env.example          # Environment variables template
├── .gitignore            # Git exclusion rules
└── README.md             # Project documentation and demo guide
```

---

## 5. Quick Start (Windows / PowerShell)

### Prerequisites
* Python 3.11+
* Docker Desktop (or local PostgreSQL and Mosquitto services)
* Git

### Step-by-Step Execution

1. **Clone repository & prepare environment:**
   ```powershell
   git clone https://github.com/Sakshi91938/iot_urban.git
   cd iot_urban
   Copy-Item .env.example .env
   ```
2. **Install Python dependencies:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. **Start Services via Docker Compose:**
   ```powershell
   docker compose up -d postgres mosquitto grafana
   ```
4. **Run Data Preparation & Pipeline Replay:**
   ```powershell
   python pipeline/prepare.py
   python pipeline/subscriber.py
   python pipeline/publisher.py
   python pipeline/cluster.py
   ```
5. **Launch Applications:**
   * **Streamlit App:** `http://localhost:8501` (`streamlit run app/main.py`)
   * **Grafana Dashboard:** `http://localhost:3000` (User: `admin`, Pass: `admin`)

---

## 6. Key Pattern Discovery Findings (Data-Backed)

Every finding below is directly backed by queries against PostgreSQL analytical views:

1. **Persistent High-Density Corridors in Zones 1 & 2:**
   * *Finding:* Zone 1 (avg queue `0.5687`) and Zone 2 (avg queue `0.4939`) sustain the highest baseline congestion across Delhi, significantly outpacing Zones 3 and 5 (`0.3470` and `0.3878`).
   * *Backing Query:* `SELECT zone, avg_queue_density, avg_stop_density FROM v_zone_summary ORDER BY avg_queue_density DESC;`

2. **Identification of Localized Afternoon Congestion Surges:**
   * *Finding:* DBSCAN separated 297 acute congestion episodes: Cluster 6 isolates 142 severe afternoon congestion spikes in Zone 3 (avg queue `0.6288`, avg stop `0.6223`), while Cluster 7 isolates 155 afternoon gridlock spikes in Zone 1 (avg queue `0.6202`, avg stop `0.6152`).
   * *Backing Query:* `SELECT cluster_id, cluster_name, zone, occurrences, avg_queue, avg_stop, start_hour, end_hour FROM v_active_telemetry_clusters WHERE cluster_id IN (6, 7) GROUP BY cluster_id, cluster_name, zone, avg_queue, avg_stop, start_hour, end_hour;`

3. **Evening Boundary Concentration of Traffic Anomalies:**
   * *Finding:* 75 of 95 detected anomaly points (78.9%) occur precisely at 22:00 IST (10:00 PM), where traffic volume abruptly deviates from the regular daytime profile. Midday anomalies (11:00–17:00 IST) exhibit extreme queue densities exceeding `0.70` to `0.78`.
   * *Backing Query:* `SELECT hour_of_day, COUNT(*) as anomaly_count, ROUND(COUNT(*)::numeric / 95 * 100, 1) as pct FROM v_anomalies GROUP BY hour_of_day ORDER BY anomaly_count DESC;`

4. **Insignificant Variance Between Weekday and Weekend Traffic:**
   * *Finding:* Delhi arterial corridors exhibit remarkable day-to-day consistency: Weekday average queue density is `0.4559` compared to `0.4495` on weekends (a negligible 1.4% differential), reflecting continuous commercial transit demand across all seven days.
   * *Backing Query:* `SELECT day_type, COUNT(*) as obs, ROUND(AVG(queue_density)::numeric, 4) as avg_q FROM v_active_telemetry_clusters GROUP BY day_type;`