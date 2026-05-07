import time
import random
import json
import threading
from azure.iot.device import IoTHubDeviceClient, Message

CONNECTION_STRING = "YOUR_IOT_HUB_CONNECTION_STRING"

GPS = {
    "latitude": 36.7213,
    "longitude": -4.4214,
    "heading": 90.0
}

period = 5

def send_telemetry(client):
    while True:
        payload = {
            "id": "AA:BB:CC:DD:EE:FF",
            "temperature": round(random.uniform(-8, 8), 2),
            "humidity": round(random.uniform(70, 95), 2),
            "acceleration": {
                "x": round(random.uniform(-1, 1), 3),
                "y": round(random.uniform(-1, 1), 3),
                "z": round(random.uniform(9, 10), 3)
            },
            "angular_speed": {
                "x": round(random.uniform(-5, 5), 3),
                "y": round(random.uniform(-5, 5), 3),
                "z": round(random.uniform(-5, 5), 3)
            },
            "linear_speed": round(random.uniform(0, 120), 1)
        }
        msg = Message(json.dumps(payload))
        msg.content_type = "application/json"
        msg.content_encoding = "utf-8"
        client.send_message(msg)
        print(f"[TELEMETRY] Sent: {payload}")
        time.sleep(period)

def main():
    client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
    client.connect()
    print("[INFO] Connected to IoT Hub!")

    t1 = threading.Thread(target=send_telemetry, args=(client,), daemon=True)
    t1.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[INFO] Stopping...")
        client.disconnect()

if __name__ == "__main__":
    main()
