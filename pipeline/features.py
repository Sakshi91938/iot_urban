"""Feature Engineering for DBSCAN Traffic Clustering.

Transforms 5-minute traffic telemetry into a standardized feature space:
- Standardized queue_density and stop_density (StandardScaler)
- Cyclic hour-of-day encoding (sin/cos on 24-hour cycle)
- One-hot encoded zone indicators (zone 1 to 6)
"""

import logging
import os
import sys
from typing import Tuple
from dotenv import load_dotenv
import numpy as np
import pandas as pd
import psycopg2
from sklearn.preprocessing import StandardScaler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("features")


def load_telemetry_from_db(conn=None) -> pd.DataFrame:
    """Loads all records from traffic_telemetry ordered by (ts, zone)."""
    close_conn = False
    if conn is None:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 5432)),
            dbname=os.getenv("DB_NAME", "urban_mobility"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        close_conn = True

    query = """
        SELECT id, ts, zone, queue_density, stop_density
        FROM traffic_telemetry
        ORDER BY ts ASC, zone ASC;
    """
    df = pd.read_sql_query(query, conn)
    if close_conn:
        conn.close()

    df["ts"] = pd.to_datetime(df["ts"])
    logger.info("Loaded %d telemetry records from database.", len(df))
    return df


def extract_features(
    df: pd.DataFrame,
    scaler: StandardScaler = None,
) -> Tuple[np.ndarray, list, StandardScaler]:
    """Builds the standardized feature matrix from traffic telemetry.

    Features:
    1. queue_density (StandardScaled)
    2. stop_density (StandardScaled)
    3. sin_hour = sin(2*pi*hour/24)
    4. cos_hour = cos(2*pi*hour/24)
    5. zone_1 .. zone_6 (one-hot binary indicators)

    Args:
        df: Telemetry DataFrame containing ts, zone, queue_density, stop_density.
        scaler: Optional fitted StandardScaler. If None, fits a new scaler.

    Returns:
        tuple of (X_matrix, feature_names, fitted_scaler)
    """
    # 1. Cyclic Hour of Day Encoding
    hour_float = df["ts"].dt.hour + (df["ts"].dt.minute / 60.0)
    sin_hour = np.sin(2.0 * np.pi * hour_float / 24.0).values.reshape(-1, 1)
    cos_hour = np.cos(2.0 * np.pi * hour_float / 24.0).values.reshape(-1, 1)

    # 2. Standardized Density Scaling
    density_cols = df[["queue_density", "stop_density"]].values
    if scaler is None:
        scaler = StandardScaler()
        densities_scaled = scaler.fit_transform(density_cols)
    else:
        densities_scaled = scaler.transform(density_cols)

    # 3. One-hot Zone Representation (fixed across zones 1 to 6)
    zone_arrays = []
    zone_names = []
    for z in range(1, 7):
        col_name = f"zone_{z}"
        zone_mask = (df["zone"] == z).astype(float).values.reshape(-1, 1)
        zone_arrays.append(zone_mask)
        zone_names.append(col_name)

    zone_matrix = np.hstack(zone_arrays)

    # 4. Assemble Final Matrix
    feature_names = ["scaled_queue_density", "scaled_stop_density", "sin_hour", "cos_hour"] + zone_names
    X = np.hstack([densities_scaled, sin_hour, cos_hour, zone_matrix])

    logger.info("Constructed feature matrix: shape=%s, features=%s", X.shape, feature_names)
    return X, feature_names, scaler


if __name__ == "__main__":
    df_telemetry = load_telemetry_from_db()
    X_mat, feat_names, _ = extract_features(df_telemetry)
    print("Extracted Features Matrix:", X_mat.shape)
    print("Features:", feat_names)
