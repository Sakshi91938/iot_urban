import pandas as pd
import psycopg2
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN


# -----------------------------
# PostgreSQL connection
# -----------------------------

DB_PASSWORD = "Jaishreemahakal@#$"

connection = psycopg2.connect(
    host="localhost",
    port=5432,
    database="urban_mobility",
    user="postgres",
    password=DB_PASSWORD
)


# -----------------------------
# Read traffic data
# -----------------------------

query = """
SELECT
    id,
    timestamp,
    zone,
    queue_density,
    stop_density
FROM traffic_telemetry
ORDER BY timestamp, zone;
"""

df = pd.read_sql_query(query, connection)

connection.close()

print("Records loaded:", len(df))


# -----------------------------
# Prepare DBSCAN features
# -----------------------------

features = df[
    [
        "queue_density",
        "stop_density"
    ]
].copy()

# Standardize the two traffic-density features
scaler = StandardScaler()

X = scaler.fit_transform(features)


# -----------------------------
# DBSCAN
# -----------------------------

model = DBSCAN(
    eps=0.35,
    min_samples=10
)

df["cluster"] = model.fit_predict(X)


# -----------------------------
# Cluster summary
# -----------------------------

print("\nCluster counts:")
print(df["cluster"].value_counts().sort_index())


print("\nCluster characteristics:")
print(
    df.groupby("cluster")[
        ["queue_density", "stop_density"]
    ].mean().round(4)
)


# -----------------------------
# Save results
# -----------------------------

df.to_csv(
    "dbscan_results.csv",
    index=False
)

print("\nDBSCAN analysis complete.")
print("Results saved to: dbscan_results.csv")