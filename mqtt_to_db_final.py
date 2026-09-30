import json
import psycopg2
from psycopg2.extras import execute_values
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "urban_iot_project/traffic"

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "urban_mobility"
DB_USER = "postgres"
DB_PASSWORD = "Jaishreemahakal@#$"

BATCH_SIZE = 100

db_connection = None
db_cursor = None
message_batch = []


def save_batch():

    global message_batch

    if not message_batch:
        return

    query = """
        INSERT INTO traffic_telemetry
        (timestamp, zone, queue_density, stop_density)
        VALUES %s
    """

    execute_values(
        db_cursor,
        query,
        message_batch
    )

    db_connection.commit()

    print("Saved batch:", len(message_batch))

    message_batch.clear()


def on_connect(client, userdata, flags, reason_code, properties):

    print("Connected to MQTT broker")

    client.subscribe(TOPIC)

    print("Subscribed to:", TOPIC)


def on_message(client, userdata, msg):

    global message_batch

    try:

        data = json.loads(msg.payload.decode())

        message_batch.append(
            (
                data["timestamp"],
                data["zone"],
                data["queue_density"],
                data["stop_density"]
            )
        )

        if len(message_batch) >= BATCH_SIZE:
            save_batch()

    except Exception as error:

        print("ERROR:", error)


db_connection = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

db_cursor = db_connection.cursor()

print("PostgreSQL connected")

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="database_subscriber_final"
)

client.on_connect = on_connect
client.on_message = on_message

print("Connecting to MQTT broker...")

client.connect(BROKER, PORT, 60)

try:

    client.loop_forever()

except KeyboardInterrupt:

    print("\nStopping subscriber...")

finally:

    save_batch()

    db_cursor.close()
    db_connection.close()

    client.disconnect()

    print("Subscriber stopped cleanly.")