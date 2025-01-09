# MqttRangeMonitor

**MqttRangeMonitor** is a Python application that subscribes to one or more MQTT topics and checks incoming numeric values against specified **minimum** and **maximum** ranges, with an optional **hysteresis** for each topic. If a value goes out of range, the application sends an **alert** message via Telegram. When it returns to the acceptable range (after applying hysteresis logic), it sends an **informational** message notifying that it’s back to normal.

This application can be used to monitor sensor data (e.g., temperature, humidity, pressure) in industrial or home automation scenarios, helping operators respond to out-of-range conditions quickly.

---

## Features

1. **MQTT Subscription**  
    Subscribes to multiple MQTT topics specified in `config.json`.
    
2. **Range Checking**  
    Each topic has a minimum and maximum value. An alert is raised if the value falls below or exceeds these bounds (plus hysteresis).
    
3. **Hysteresis**  
    Prevents excessive alerts when the value is near the boundary. For example, if `max_value` is 35.0 and `hysteresis` is 0.5, the system triggers an out-of-range alert at 35.5 and a “back-to-normal” message once the value goes below 34.5.
    
4. **Telegram Alerts**  
    Sends messages to a specified Telegram chat ID via a bot token whenever a topic goes out of range or comes back to normal.
    
5. **Ease of Configuration**  
    All settings (broker address, topics, min/max, hysteresis, Telegram credentials) are stored in a single `config.json`.
    

---

## Requirements

- **Python 3.7** (or later)
- **paho-mqtt** (`pip install paho-mqtt`)
- **requests** (`pip install requests`)
- A valid **Telegram Bot** token (see below for how to create one)
- A **Telegram Chat ID** (your personal chat ID, group ID, channel ID, etc.)

---

## Installation

1. **Clone** this repository or download the files.
2. **Install** the required Python packages:
    
~~~ bash
pip install paho-mqtt requests
~~~

3. **Edit** `config.json` with your own broker settings, topics, and Telegram credentials1. .

---

## Configuration

A sample `config.json` might look like this:
~~~ json
{
  "broker": "test.mosquitto.org",
  "port": 1883,
  "username": "",
  "password": "",
  "client_id": "mqtt_client",
  "topics": [
    {
      "topic": "/my/temperature/",
      "max_value": 35.00,
      "min_value": 10.00,
      "hysteresis": 0.2
    },
    {
      "topic": "/my/humidity/",
      "max_value": 90.00,
      "min_value": 20.00,
      "hysteresis": 1.0
    }
  ],
  "telegram_bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
  "telegram_chat_id": "987654321"
}

~~~

Explanation of each field:

- **broker**: Your MQTT broker hostname or IP (e.g., `test.mosquitto.org`, `mqtt.myserver.com`).
- **port**: The MQTT broker port (default is `1883` for unencrypted MQTT).
- **username / password**: If your broker requires authentication, set these. Otherwise, leave them blank.
- **client_id**: The base client ID used to connect to the MQTT broker. A random numeric suffix is appended at runtime to avoid collisions.
- **topics**: An array of topic dictionaries. Each entry must have:
    - **topic**: The MQTT topic string (e.g., `/my/temperature/`).
    - **max_value**: The upper limit for normal values.
    - **min_value**: The lower limit for normal values.
    - **hysteresis**: The hysteresis value to apply on both boundaries.
- **telegram_bot_token**: The token for your Telegram bot (see instructions below).
- **telegram_chat_id**: The chat ID where notifications will be sent.

---

## How to Create a Telegram Bot

1. Open the **Telegram** app (mobile or desktop).
2. Search for **@BotFather** and click **Start** (or use the `/start` command if you’ve previously interacted with BotFather).
3. Send the command `/newbot` to BotFather. It will ask you for a **name** and **username** for your bot.
4. Once the bot is created, BotFather will give you a **token** in the format `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`.
    - Place this **token** it in `telegram_bot_token` in `config.json`.


> [!IMPORTANT]
> This token must be kept **private**. Do not share this token with anyone.

---

## How to Get Your Telegram Chat ID

There are multiple ways to obtain your chat ID. One of the simplest methods:

1. Search for a user called `@userinfobot` or `@RawDataBot` in Telegram.
2. Start a chat with it and send any message (for example, “Hello”).
3. The bot will respond with your user information, including your **chat ID**.
    - Copy that numeric ID and place it in `telegram_chat_id` in `config.json`.

Alternatively, you can invite your bot to a group and request the group’s chat ID if you prefer group notifications.

---

## How it Works

1. **MQTT Connection**  
    `MqttRangeMonitor.py` reads `config.json` and connects to the MQTT broker using **paho-mqtt**.
    
2. **Topic Subscription**  
    Once connected, it subscribes to all topics listed in the `topics` array.
    
3. **Processing Incoming Messages**
    
    - Each time an MQTT message arrives, the payload is interpreted as a numeric value.
    - If parsing fails (e.g., non-numeric data), the message is ignored.
4. **Range + Hysteresis Check**
    
    - The program computes extended boundaries:
        - **Out-of-range (upper)** if `current_value >= (max_value + hysteresis)`
        - **Out-of-range (lower)** if `current_value <= (min_value - hysteresis)`
    - Once a topic is flagged “out-of-range”, it remains in that state until the value goes back **within**  
        ‘minvalue+hysteresis‘,‘maxvalue−hysteresis‘`min_value + hysteresis`, `max_value - hysteresis`‘minv​alue+hysteresis‘,‘maxv​alue−hysteresis‘.
    - An **alert** (`[ALERT]`) is sent when a topic transitions from normal to out-of-range.
    - An **informational** message (`[INFO]`) is sent when it transitions back to the normal range.
5. **Telegram Notification**
    
    - The bot token and chat ID are used to send the message via the official Telegram Bot API, using an HTTP `POST` request.
    - You will see the notifications in real-time in your chosen Telegram account or group.

---

## Usage

1. **Configure** `config.json` as described above.
2. **Run** the script:

~~~ bash
python3 MqttRangeMonitor.py
~~~

2. The script will display logs in the console. Look for messages such as “Connected to MQTT Broker!” and “Subscribed to topic: …”.

---

## Example

Suppose you have `config.json` with:
~~~ json
{
  "broker": "test.mosquitto.org",
  "port": 1883,
  "client_id": "mqtt_client",
  "topics": [
    {
      "topic": "/my/temperature/",
      "max_value": 35.0,
      "min_value": 10.0,
      "hysteresis": 0.2
    }
  ],
  "telegram_bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
  "telegram_chat_id": "987654321"
}

~~~

- When `/my/temperature/` publishes a value of `35.3`, the system sees `35.3 >= 35.0 + 0.2` and sends an **out-of-range** alert.
- When it drops back down to `34.8`, the system sees `34.8 <= 35.0 - 0.2` and sends a **back-to-normal** message.

---

## Contributing

Feel free to open an issue or submit a pull request if you have suggestions, bug reports, or feature requests. We welcome community contributions!