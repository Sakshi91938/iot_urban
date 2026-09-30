import paho.mqtt.client as mqtt
import json
import csv
import os

broker = "test.mosquitto.org"
port = 1883
topic = "urban_iot_project/vehicles"

file_name = "vehicle_data.csv"

# Create CSV file if it doesn't exist
if not os.path.exists(file_name):
    with open(file_name, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["vehicle_id", "latitude", "longitude", "speed"])


def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker!")
    client.subscribe(topic)
    print("Subscribed to:", topic)


def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())

    print("Received:", data)

    with open(file_name, "a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            data["vehicle_id"],
            data["latitude"],
            data["longitude"],
            data["speed"]
        ])

    print("Saved to CSV!")


client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, port, 60)

client.loop_forever()