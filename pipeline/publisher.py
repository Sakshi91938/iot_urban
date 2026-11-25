"""MQTT Telemetry Replay Publisher.

Reads 5-minute aggregated Delhi traffic density dataset from CSV,
serializes each observation into JSON, and publishes sequentially to
MQTT topic 'urban/traffic/zone/<zone_id>/telemetry'.
Supports instant replay or throttled delay for visual live demonstration.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("publisher")


class TelemetryPublisher:
    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        topic_prefix: str = "urban/traffic/zone",
    ):
        self.broker = broker
        self.port = port
        self.topic_prefix = topic_prefix

        self.client = mqtt.Client(
            CallbackAPIVersion.VERSION2,
            client_id="telemetry_publisher",
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.connected = False

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self.connected = True
            logger.info("Publisher connected to MQTT broker at %s:%d.", self.broker, self.port)
        else:
            logger.error("Publisher failed to connect to broker (reason code: %s).", reason_code)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        self.connected = False
        logger.warning("Publisher disconnected from MQTT broker.")

    def replay(
        self,
        csv_path: str = "data/processed/clean_traffic_5min.csv",
        speed: str = "instant",
        delay: float = 0.0,
        limit: int = 0,
    ):
        """Streams records from clean CSV to MQTT broker."""
        data_file = Path(csv_path)
        if not data_file.is_file():
            raise FileNotFoundError(
                f"Processed data file not found at: {csv_path}. Please run pipeline/prepare.py first."
            )

        logger.info("Loading telemetry dataset from %s...", csv_path)
        df = pd.read_csv(data_file)
        if limit > 0:
            df = df.iloc[:limit]
            logger.info("Limiting replay to first %d records.", limit)

        total_rows = len(df)
        logger.info("Connecting to MQTT broker at %s:%d...", self.broker, self.port)
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()

        # Wait briefly for connection handshake
        for _ in range(30):
            if self.connected:
                break
            time.sleep(0.1)

        if not self.connected:
            self.client.loop_stop()
            raise ConnectionError(f"Could not establish MQTT connection to {self.broker}:{self.port}")

        # Determine inter-message sleep interval
        if speed == "instant":
            sleep_interval = 0.0001
        elif speed == "demo":
            sleep_interval = delay if delay > 0 else 0.02
        else:
            sleep_interval = delay

        logger.info("Starting replay of %d records (speed=%s, delay=%.4fs)...", 
                    total_rows, speed, sleep_interval)
        start_time = time.time()

        for idx, row in enumerate(df.itertuples(index=False), start=1):
            zone_id = int(row.zone)
            topic = f"{self.topic_prefix}/{zone_id}/telemetry"

            payload = json.dumps({
                "ts": str(row.ts),
                "zone": zone_id,
                "queue_density": float(row.queue_density),
                "stop_density": float(row.stop_density),
            })

            # Publish with QoS 1 for reliable delivery
            inf = self.client.publish(topic, payload, qos=1)

            if idx % 5000 == 0 or idx == total_rows:
                inf.wait_for_publish(timeout=5)
                logger.info("Replayed %d / %d records (%.1f%%)...", 
                            idx, total_rows, (idx / total_rows) * 100)

            if sleep_interval > 0:
                time.sleep(sleep_interval)

        elapsed = time.time() - start_time
        logger.info("Completed MQTT replay of %d records in %.2f seconds (%.1f msg/sec).",
                    total_rows, elapsed, total_rows / max(elapsed, 0.001))

        self.client.loop_stop()
        self.client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT Telemetry Replay Publisher")
    parser.add_argument("--csv-path", default="data/processed/clean_traffic_5min.csv", help="Path to clean CSV")
    parser.add_argument("--speed", choices=["instant", "demo"], default="instant", help="Replay mode (instant or demo)")
    parser.add_argument("--delay", type=float, default=0.0, help="Per-record delay in seconds")
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit for test replays")
    args = parser.parse_args()

    broker = os.getenv("MQTT_BROKER", "localhost")
    port = int(os.getenv("MQTT_PORT", 1883))
    topic_prefix = os.getenv("MQTT_TOPIC_PREFIX", "urban/traffic/zone")

    pub = TelemetryPublisher(broker=broker, port=port, topic_prefix=topic_prefix)
    pub.replay(csv_path=args.csv_path, speed=args.speed, delay=args.delay, limit=args.limit)
