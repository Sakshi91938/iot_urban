import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "urban_iot_project/traffic"


def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")
    client.subscribe(TOPIC)
    print("Subscribed to:", TOPIC)


def on_message(client, userdata, msg):
    print("Received MQTT message:")
    print(repr(msg.payload.decode()))


client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

client.loop_forever()