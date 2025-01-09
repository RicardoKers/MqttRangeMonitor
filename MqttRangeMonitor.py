#!/usr/bin/env python3
# MqttRangeMonitor Version 0.2
#
# This program monitors MQTT topics for numeric values, checks whether
# the values are within acceptable ranges (with hysteresis), and sends
# alerts via Telegram when values go out of range or return to normal.
# It reads configuration from a JSON file (config.json).

import json
import paho.mqtt.client as mqtt
import logging
import random
import requests
from threading import Lock

# Program version constant
VERSION = "0.2"

# Configure Python logging (only changes log messages, not the logic)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Global lock to protect shared dictionaries if needed
userdata_lock = Lock()

def load_config(file_path):
    """
    Loads JSON configuration from a specified file path.
    Returns a dict on success, or None if the file is missing/invalid.
    """
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        log.error(f"Config file '{file_path}' not found.")
        return None
    except json.JSONDecodeError:
        log.error(f"Error decoding JSON in '{file_path}'.")
        return None

def send_telegram_message(bot_token, chat_id, text):
    """
    Sends a Telegram message using the Bot API.
    This function uses an HTTP POST request to the Telegram endpoint:
      https://api.telegram.org/bot<bot_token>/sendMessage
    """
    if not bot_token or not chat_id:
        log.error("Telegram bot token or chat_id not configured.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            log.error(f"Telegram sendMessage failed: {response.text}")
        else:
            log.info(f"Telegram message sent: {text}")
    except requests.exceptions.RequestException as e:
        log.error(f"Exception sending Telegram message: {str(e)}")

def on_connect(client, userdata, flags, rc):
    """
    Callback invoked by paho-mqtt upon connecting to the MQTT broker.
    If rc == 0, the connection is successful, so we subscribe to each topic.
    Otherwise, logs the error code.
    """
    if rc == 0:
        log.info("Connected to MQTT Broker!")
        for tinfo in userdata["topics_info"]:
            topic_name = tinfo["topic"]
            client.subscribe(topic_name)
            log.info(f"Subscribed to topic: {topic_name}")
    else:
        log.error(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    """
    Callback invoked whenever an MQTT message arrives.
    - Decodes the payload as float.
    - Uses hysteresis to check whether the value is in or out of range.
    - Sends alerts accordingly:
      * If going out of range (and not already alerted), send ALERT.
      * If returning to range (and was previously out), send INFO.
    """
    topic = msg.topic
    payload_str = msg.payload.decode().strip()
    log.info(f"Message received on topic {topic}: {payload_str}")

    with userdata_lock:
        # Find the settings for this topic
        topics_info = userdata["topics_info"]
        topic_alert_state = userdata["topic_alert_state"]  # bool: True if currently out-of-range

        # Locate topic settings
        match = next((t for t in topics_info if t["topic"] == topic), None)
        if match is None:
            log.warning(f"Topic '{topic}' not found in configuration. Ignoring...")
            return

        min_val = match["min_value"]
        max_val = match["max_value"]
        hysteresis = match["hysteresis"]

        # Attempt to parse the value as float
        try:
            current_value = float(payload_str)
        except ValueError:
            log.warning(f"Failed to parse '{payload_str}' as float for topic '{topic}'.")
            return

        # Define thresholds for out-of-range
        # e.g. out_of_range if current_value >= (max_val + hysteresis) or <= (min_val - hysteresis)
        high_out_threshold = max_val + hysteresis
        low_out_threshold  = min_val - hysteresis

        # Define thresholds for in-range
        # e.g. to return to normal, current_value must be within [min_val + hysteresis, max_val - hysteresis]
        high_in_threshold = max_val - hysteresis
        low_in_threshold  = min_val + hysteresis

        # Current state: out_of_range or in_range
        currently_out_of_range = topic_alert_state[topic]

        if not currently_out_of_range:
            # We are in range, check if we crossed outside
            if (current_value >= high_out_threshold) or (current_value <= low_out_threshold):
                # Value is out of range
                topic_alert_state[topic] = True
                alert_text = (f"[ALERT] Topic '{topic}' is out of range "
                              f"[{min_val}, {max_val}] with hysteresis={hysteresis}. "
                              f"Current value: {current_value}")
                send_telegram_message(userdata["telegram_bot_token"], userdata["telegram_chat_id"], alert_text)
        else:
            # We are out of range, check if we've returned to normal
            in_range_now = (
                (current_value <= high_in_threshold) and
                (current_value >= low_in_threshold)
            )
            if in_range_now:
                topic_alert_state[topic] = False
                normal_text = (f"[INFO] Topic '{topic}' is back to normal range "
                               f"[{min_val}, {max_val}] with hysteresis={hysteresis}. "
                               f"Current value: {current_value}")
                send_telegram_message(userdata["telegram_bot_token"], userdata["telegram_chat_id"], normal_text)

def main():
    """
    Main function:
      1. Loads config.json
      2. Connects to the MQTT broker
      3. Subscribes to specified topics
      4. Monitors values in on_message callback and sends Telegram alerts
         with hysteresis logic.
    """
    # Load config
    config = load_config("config.json")
    if not config:
        log.error("Configuration could not be loaded. Exiting.")
        return

    # Required fields
    broker = config.get("broker", "")
    port = config.get("port", 1883)
    username = config.get("username", "")
    password = config.get("password", "")
    client_id = config.get("client_id", "mqtt_client")
    topics_list = config.get("topics", [])
    telegram_bot_token = config.get("telegram_bot_token", "")
    telegram_chat_id = config.get("telegram_chat_id", "")

    # Basic config validations
    if not broker:
        log.error("Broker address is missing in config.json.")
        return
    if not isinstance(topics_list, list) or len(topics_list) == 0:
        log.error("Topics list is missing or empty in config.json.")
        return

    # Parse topics info, ensuring each has 'topic', 'max_value', 'min_value', 'hysteresis'
    topics_info = []
    for tinfo in topics_list:
        # We expect a dictionary with 'topic', 'max_value', 'min_value', 'hysteresis'
        if (
            "topic" not in tinfo or
            "max_value" not in tinfo or
            "min_value" not in tinfo or
            "hysteresis" not in tinfo
        ):
            log.error("One of the topics in config.json is missing required fields (topic, max_value, min_value, hysteresis).")
            return

        topics_info.append({
            "topic": tinfo["topic"],
            "max_value": tinfo["max_value"],
            "min_value": tinfo["min_value"],
            "hysteresis": tinfo["hysteresis"]
        })

    # Append random suffix to avoid potential client_id collisions
    random_suffix = random.randint(1000, 99999)
    client_id = f"{client_id}-{random_suffix}"
    log.info(f"Using client_id: {client_id}")

    # Prepare user data for MQTT callbacks
    # Initialize a dictionary to track alert states (True = out_of_range)
    topic_alert_state = {}
    for t in topics_info:
        topic_alert_state[t["topic"]] = False

    userdata = {
        "topics_info": topics_info,
        "topic_alert_state": topic_alert_state,
        "telegram_bot_token": telegram_bot_token,
        "telegram_chat_id": telegram_chat_id
    }

    # Create MQTT client and attach callbacks
    client = mqtt.Client(client_id=client_id, transport="tcp")
    client.on_connect = on_connect
    client.on_message = on_message
    client.user_data_set(userdata)

    # Set MQTT username & password if provided
    if username and password:
        client.username_pw_set(username, password)

    # Connect to the broker
    try:
        client.connect(broker, port, 60)
    except Exception as e:
        log.error(f"Could not connect to broker: {e}")
        return

    log.info("Starting MQTT loop...")
    # Blocks forever, receiving messages
    client.loop_forever()

if __name__ == "__main__":
    main()
