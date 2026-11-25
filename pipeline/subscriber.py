"""MQTT Telemetry Subscriber and Batch Database Ingestion.

Subscribes to topic 'urban/traffic/zone/+/telemetry', buffers messages,
and performs batch inserts into PostgreSQL with ON CONFLICT (ts, zone) DO NOTHING.
Uses paho-mqtt CallbackAPIVersion.VERSION2 and maintains a single resilient DB connection.
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("subscriber")


class TelemetrySubscriber:
    def __init__(
        self,
        db_config: dict,
        mqtt_config: dict,
        batch_size: int = 500,
        expected_rows: int = 0,
        max_idle_seconds: float = 0.0,
    ):
        self.db_config = db_config
        self.mqtt_config = mqtt_config
        self.batch_size = batch_size
        self.expected_rows = expected_rows
        self.max_idle_seconds = max_idle_seconds

        self.db_conn = None
        self.db_cursor = None
        self.buffer = []
        self.total_received = 0
        self.total_inserted = 0
        self.last_msg_time = time.time()
        self.running = True

        self._init_db_connection()
        self._init_mqtt_client()

    def _init_db_connection(self):
        """Initializes and keeps open a single database connection."""
        try:
            logger.info("Connecting to PostgreSQL at %s:%s...", self.db_config["host"], self.db_config["port"])
            self.db_conn = psycopg2.connect(
                host=self.db_config["host"],
                port=self.db_config["port"],
                dbname=self.db_config["dbname"],
                user=self.db_config["user"],
                password=self.db_config["password"],
            )
            self.db_cursor = self.db_conn.cursor()
            logger.info("PostgreSQL connection established.")
        except Exception as e:
            logger.error("Failed to connect to database: %s", e)
            raise

    def _ensure_db_connection(self):
        """Ensures the single DB connection is healthy, reconnecting if needed."""
        try:
            if self.db_conn is None or self.db_conn.closed != 0:
                self._init_db_connection()
            else:
                self.db_cursor.execute("SELECT 1;")
        except Exception:
            logger.warning("DB connection lost. Attempting reconnect...")
            try:
                if self.db_conn:
                    self.db_conn.close()
            except Exception:
                pass
            self._init_db_connection()

    def _init_mqtt_client(self):
        """Initializes MQTT client with CallbackAPIVersion.VERSION2."""
        self.client = mqtt.Client(
            CallbackAPIVersion.VERSION2,
            client_id="telemetry_subscriber",
            clean_session=True,
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            topic = f"{self.mqtt_config['topic_prefix']}/+/telemetry"
            logger.info("Connected to MQTT broker at %s:%s. Subscribing to: %s", 
                        self.mqtt_config["host"], self.mqtt_config["port"], topic)
            client.subscribe(topic, qos=1)
        else:
            logger.error("MQTT connection failed with reason code: %s", reason_code)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        logger.warning("Disconnected from MQTT broker (code: %s).", reason_code)

    def on_message(self, client, userdata, message):
        """Receives and buffers JSON telemetry messages."""
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            ts = payload["ts"]
            zone = int(payload["zone"])
            queue_density = float(payload["queue_density"])
            stop_density = float(payload["stop_density"])

            self.buffer.append((ts, zone, queue_density, stop_density))
            self.total_received += 1
            self.last_msg_time = time.time()

            if len(self.buffer) >= self.batch_size:
                self.flush_buffer()

        except Exception as e:
            logger.error("Error parsing message payload: %s | Payload: %s", e, message.payload)

    def flush_buffer(self):
        """Executes batch insert using ON CONFLICT DO NOTHING."""
        if not self.buffer:
            return

        self._ensure_db_connection()
        records_to_insert = list(self.buffer)
        self.buffer.clear()

        query = """
            INSERT INTO traffic_telemetry (ts, zone, queue_density, stop_density)
            VALUES %s
            ON CONFLICT (ts, zone) DO NOTHING;
        """
        try:
            execute_values(self.db_cursor, query, records_to_insert)
            self.db_conn.commit()
            self.total_inserted += len(records_to_insert)
            if self.total_inserted % 5000 == 0 or self.total_inserted == self.expected_rows:
                logger.info("Batch inserted %d records. Total processed: %d", 
                            len(records_to_insert), self.total_inserted)
        except Exception as e:
            logger.error("Database batch insert failed: %s", e)
            try:
                self.db_conn.rollback()
            except Exception:
                pass

    def run(self):
        """Main subscriber loop."""
        try:
            self.client.connect(
                self.mqtt_config["host"],
                self.mqtt_config["port"],
                keepalive=60,
            )
            self.client.loop_start()

            logger.info("Telemetry subscriber active. Listening for telemetry...")
            while self.running:
                time.sleep(0.2)

                # Periodic flush if buffer has items and idle for > 0.5s
                if self.buffer and (time.time() - self.last_msg_time > 0.5):
                    self.flush_buffer()

                # Check if expected rows reached
                if self.expected_rows > 0 and self.total_received >= self.expected_rows:
                    self.flush_buffer()
                    logger.info("Reached expected message count (%d).", self.expected_rows)
                    break

                # Check max idle timeout
                if self.max_idle_seconds > 0 and (time.time() - self.last_msg_time > self.max_idle_seconds):
                    if self.total_received > 0:
                        self.flush_buffer()
                        logger.info("Idle timeout of %.1fs reached after receiving messages. Stopping.", self.max_idle_seconds)
                        break

        except KeyboardInterrupt:
            logger.info("Shutdown signal received.")
        finally:
            self.stop()

    def stop(self):
        """Flushes remaining items and closes connections."""
        self.running = False
        self.flush_buffer()
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        try:
            if self.db_cursor:
                self.db_cursor.close()
            if self.db_conn:
                self.db_conn.close()
        except Exception:
            pass
        logger.info("Subscriber stopped cleanly. Total received: %d, Flushed: %d", 
                    self.total_received, self.total_inserted)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT Telemetry Subscriber for Urban Mobility")
    parser.add_argument("--batch-size", type=int, default=500, help="DB insert batch size (default: 500)")
    parser.add_argument("--expected-rows", type=int, default=0, help="Stop after receiving N rows (default: 0 = indefinite)")
    parser.add_argument("--max-idle-seconds", type=float, default=0.0, help="Stop if idle for N seconds (default: 0 = indefinite)")
    args = parser.parse_args()

    db_cfg = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "dbname": os.getenv("DB_NAME", "urban_mobility"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }

    mqtt_cfg = {
        "host": os.getenv("MQTT_BROKER", "localhost"),
        "port": int(os.getenv("MQTT_PORT", 1883)),
        "topic_prefix": os.getenv("MQTT_TOPIC_PREFIX", "urban/traffic/zone"),
    }

    sub = TelemetrySubscriber(
        db_config=db_cfg,
        mqtt_config=mqtt_cfg,
        batch_size=args.batch_size,
        expected_rows=args.expected_rows,
        max_idle_seconds=args.max_idle_seconds,
    )
    sub.run()
