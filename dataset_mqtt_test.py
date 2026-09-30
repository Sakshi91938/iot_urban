import pandas as pd
import json
import time
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "urban_iot_project/traffic"

FILE = "dataset/DelhiTrafficDensityDataset/Dec15.csv"

# Read first 10 records from real dataset
df = pd.read_csv(FILE, nrows=10)

client = mqtt.Client()

client.connect(BROKER, PORT, 60)

for _, row in df.iterrows():

    message = {
        "timestamp": pd.to_datetime(
            row["EpochTime"], unit="s"
        ).strftime("%Y-%m-%d %H:%M:%S"),

        "zone": 1,

        "queue_density": float(row["QueueDensity1"]),

        "stop_density": float(row["StopDensity1"])
    }

    payload = json.dumps(message)

    client.publish(TOPIC, payload)

    print("Sent:", payload)

    time.sleep(1)

client.disconnect()

print("10 real dataset records sent successfully.")