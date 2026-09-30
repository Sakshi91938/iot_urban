import psycopg2

password = input("Enter PostgreSQL password: ")

connection = psycopg2.connect(
    host="localhost",
    port=5432,
    database="urban_mobility",
    user="postgres",
    password=password
)

cursor = connection.cursor()

create_table_query = """
CREATE TABLE IF NOT EXISTS traffic_telemetry (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    zone INTEGER NOT NULL,
    queue_density DOUBLE PRECISION,
    stop_density DOUBLE PRECISION
);
"""

cursor.execute(create_table_query)

connection.commit()

print("TRAFFIC TELEMETRY TABLE CREATED SUCCESSFULLY")

cursor.close()
connection.close()