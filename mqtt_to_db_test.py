import json
import psycopg2
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "urban_iot_project/traffic"


def save_to_database(data):
    password = "Jaishreemahakal@#$"

    connection = psycopg2.connect(
        host="localhost",
        port=5432,
        database="urban_mobility",
        user="postgres",
        password=password
    )

    cursor = connection.cursor()

    query = """
    INSERT INTO traffic_telemetry
    (timestamp, zone, queue_density, stop_density)
    VALUES (%s, %s, %s, %s)
    """

    cursor.execute(
        query,
        (
            data["timestamp"],
            data["zone"],
            data["queue_density"],
            data["stop_density"]
        )
    )

    connection.commit()

    cursor.close()
    connection.close()

    print("Saved to PostgreSQL")


def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")
    client.subscribe(TOPIC)
    print("Subscribed to:", TOPIC)


def on_message(client, userdata, msg):

    data = json.loads(msg.payload.decode())

    print("Received:", data)

    save_to_database(data)


client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

client.loop_forever()