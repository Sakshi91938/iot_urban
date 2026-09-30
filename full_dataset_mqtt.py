import os
import time
import json
import pandas as pd
import paho.mqtt.client as mqtt

DATASET_FOLDER = r"C:\Users\PC\OneDrive\urban_iot_project\dataset\DelhiTrafficDensityDataset"

BROKER = "localhost"
PORT = 1883
TOPIC = "urban_iot_project/traffic"


def create_mqtt_client():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="full_dataset_publisher"
    )

    client.connect(BROKER, PORT, 60)
    client.loop_start()

    return client


def process_file(file_path, client):
    print("\nProcessing:", os.path.basename(file_path))

    df = pd.read_csv(file_path)

    # Convert Unix timestamp to datetime
    df["timestamp"] = pd.to_datetime(df["EpochTime"], unit="s")

    # Convert to 5-minute windows
    df["time_window"] = df["timestamp"].dt.floor("5min")

    total_sent = 0

    # Six traffic zones
    for zone in range(1, 7):

        queue_column = f"QueueDensity{zone}"
        stop_column = f"StopDensity{zone}"

        grouped = (
            df.groupby("time_window")[[queue_column, stop_column]]
            .mean()
            .reset_index()
        )

        for _, row in grouped.iterrows():

            message = {
                "timestamp": row["time_window"].strftime("%Y-%m-%d %H:%M:%S"),
                "zone": zone,
                "queue_density": round(float(row[queue_column]), 6),
                "stop_density": round(float(row[stop_column]), 6)
            }

            client.publish(
                TOPIC,
                json.dumps(message),
                qos=1
            ).wait_for_publish()

            total_sent += 1

            # Small delay to behave like an IoT stream
            time.sleep(0.005)

    print("Messages sent from this file:", total_sent)

    return total_sent


def main():

    print("Starting full dataset MQTT publisher...")
    print("Dataset folder:", DATASET_FOLDER)

    files = sorted(
        [
            os.path.join(DATASET_FOLDER, file)
            for file in os.listdir(DATASET_FOLDER)
            if file.lower().endswith(".csv")
        ]
    )

    print("CSV files found:", len(files))

    if len(files) == 0:
        print("ERROR: No CSV files found.")
        return

    client = create_mqtt_client()

    total_messages = 0

    try:

        for file_path in files:
            total_messages += process_file(file_path, client)

    finally:

        client.loop_stop()
        client.disconnect()

    print("\n====================================")
    print("FULL DATASET MQTT PUBLISH COMPLETE")
    print("Total messages sent:", total_messages)
    print("====================================")


if __name__ == "__main__":
    main()