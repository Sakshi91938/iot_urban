import json
import time
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "urban_iot_project/traffic"

client = mqtt.Client()

client.connect(BROKER, PORT, 60)

message = {
    "timestamp": "2020-12-15 07:10:00",
    "zone": 1,
    "queue_density": 0.081189,
    "stop_density": 0.037368
}

payload = json.dumps(message)

client.publish(TOPIC, payload)

print("MQTT message sent:")
print(payload)

client.disconnect()