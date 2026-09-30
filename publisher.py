import paho.mqtt.client as mqtt
import json
import time
import random

broker = "test.mosquitto.org"
port = 1883
topic = "urban_iot_project/vehicles"

client = mqtt.Client()

client.connect(broker, port, 60)

print("Connected to MQTT broker!")

# Three simulated traffic zones
zones = [
    (28.65, 77.20),
    (28.67, 77.21),
    (28.69, 77.19)
]

while True:

    # Select a random traffic zone
    center_lat, center_lon = random.choice(zones)

    vehicle_data = {
        "vehicle_id": "V001",

        # Generate vehicle near the selected zone
        "latitude": round(
            center_lat + random.uniform(-0.002, 0.002), 6
        ),

        "longitude": round(
            center_lon + random.uniform(-0.002, 0.002), 6
        ),

        "speed": round(random.uniform(20, 80), 2)
    }

    message = json.dumps(vehicle_data)

    client.publish(topic, message)

    print("Sent:", message)

    time.sleep(2)