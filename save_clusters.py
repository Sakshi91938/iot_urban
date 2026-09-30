import pandas as pd
import psycopg2

DB_PASSWORD = "Jaishreemahakal@#$"

# Load DBSCAN results
df = pd.read_csv("dbscan_results.csv")

print("DBSCAN records loaded:", len(df))

# Connect to PostgreSQL
connection = psycopg2.connect(
    host="localhost",
    port=5432,
    database="urban_mobility",
    user="postgres",
    password=DB_PASSWORD
)

cursor = connection.cursor()

# Create table
cursor.execute("""
    DROP TABLE IF EXISTS traffic_clusters;

    CREATE TABLE traffic_clusters (
        id INTEGER PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL,
        zone INTEGER NOT NULL,
        queue_density DOUBLE PRECISION,
        stop_density DOUBLE PRECISION,
        cluster INTEGER
    );
""")

# Insert data
insert_query = """
    INSERT INTO traffic_clusters
    (id, timestamp, zone, queue_density, stop_density, cluster)
    VALUES (%s, %s, %s, %s, %s, %s)
"""

records = [
    (
        int(row["id"]),
        row["timestamp"],
        int(row["zone"]),
        float(row["queue_density"]),
        float(row["stop_density"]),
        int(row["cluster"])
    )
    for _, row in df.iterrows()
]

cursor.executemany(insert_query, records)

connection.commit()

print("Records inserted:", len(records))

# Verify
cursor.execute("SELECT COUNT(*) FROM traffic_clusters;")
count = cursor.fetchone()[0]

print("PostgreSQL traffic_clusters count:", count)

cursor.close()
connection.close()

print("DBSCAN results successfully saved to PostgreSQL.")