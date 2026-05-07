#  COLD CHAIN TRUCK: ESP32-C3 IoT Project – Sensor Monitoring & Azure Integration

This project implements an IoT system based on an ESP32-C3 that reads data from multiple sensors and sends it to Azure IoT Hub using MQTT. It also supports receiving remote commands to dynamically modify its behavior.

---

## Project Structure

* `descubrirID_sin_param.ino`: Sketch used to obtain the device identifier (DEVICE_ID). This is the same as the device MAC.

* `sensorFrigorifico_azure_sin_param.ino`: Main sketch responsible for:

  * Reading sensor data
  * Connecting to WiFi
  * Sending data to Azure IoT Hub
  * Receiving remote commands

---

## Hardware Components

* ESP32-C3 Mini
* DS18B20 (temperature sensor)
* DHT11 (humidity sensor)
* GY-521 (MPU6050, inertial sensor)
* NEO6M (GPS module)
* Resistors:
  * Minimum 4.7kΩ (5.1kΩ used in this setup)

---

## Connections

### Power Supply

* All sensors operate at 3.3V

### DS18B20

* Requires a pull-up resistor (~4.7kΩ) between VCC and DATA

### GY-521 (I2C)

* SDA → GPIO8
* SCL → GPIO9

### Other Sensors

* Can be connected to standard GPIO pins (configured in code)

---

## Configuration Parameters

Before running the main code, define the following values:

```
const char* WIFI_SSID = "..."
const char* WIFI_PASSWORD = "..."
const char* IOT_HUB_HOST = "..."
const char* MQTT_USERNAME = "..."
const char* SAS_TOKEN = "..."
const char* ROOT_CA = "..."
```

### Description

| Parameter | How to obtain it |
|-----------|------------------|
| WIFI_SSID and WIFI_PASSWORD | WiFi credentials |
| IOT_HUB_HOST | "<hub-name>.azure-devices.net" |
| SAS_TOKEN | Generated using Azure CLI |
| MQTT_USERNAME | "<hub-name>.azure-devices.net/<DEVICE_ID>/?api-version=2021-04-12" |
| ROOT_CA | DigiCert Global Root G2 certificate. Obtained from this [link](https://cacerts.digicert.com/DigiCertGlobalRootG2.crt.pem) |

Example command to generate SAS token:

```
az iot hub generate-sas-token \
  --hub-name YOURHUB \
  --device-id YOURDEVICE \
  --duration 86400
```

---

## System Workflow

1. Initialize sensors (GPS module has a slow start)
2. Establish WiFi connection. Initialize `DEVICE_ID` parameter with the MAC
3. Synchronize time using NTP
4. Create MQTT connection to Azure
5. Periodically send sensor data
6. Listen for incoming commands

---

## Data Format (Telemetry)

```
{
  "id": "...",
  "temperature": 0.0, // ºC
  "humidity": 0.0, // %
  "acceleration": [x, y, z],
  "angular_speed": [x, y, z],
  "linear_speed": 0.0, // km/h
  "when": "timestamp"
}
```

or

```
{
  "id": "...",
  "temperature": 0.0, // ºC
  "humidity": 0.0, // %
  "acceleration": [x, y, z],
  "angular_speed": [x, y, z],
  "linear_speed": 0.0, // km/h
  "gps":{
    "longitude": ...,
    "latitude": ...,
    "course": ... // degree
  }
  "when": "timestamp"
}
```

---

## Remote Commands

### Toggle GPS Data in Telemetry

```
{
  "gps": True
  "message": "text"
}
```

* Updates the internal variable `send_gps`
* When `send_gps` is true, GPS data (longitude, latitude, course) is included in the periodic telemetry
* When `send_gps` is false, GPS data is not sent

---

### Change Publishing Period

```
{
  "period": 10
  "message": "text"
}
```

* Updates the telemetry sending interval (in seconds)

---

### Display Message

```
{
  "message": "text"
}
```

* Printed in the Serial Monitor

---

### Command Acknowledgement

* Every received command generates a confirmation message from the device.
* The confirmation is sent back through MQTT.
* A format of the message sent could be:

```
{
  "id": "...",
  "new_gps": send_gps,
  "new_period": periodo,
  "when": "timestamp"
}
```


---

## Software Architecture

The system uses RTOS tasks to separate responsibilities:

* taskMQTTService → Maintains MQTT connection
* taskPublisher → Handles periodic data publishing

---

## Synchronization

Two semaphores are used:

* semMqttReady → Ensures data is not sent before MQTT connection is established
* mqttMutex → Prevents simultaneous message publishing

---

## Getting DEVICE_ID

Use the sketch:

```
descubrirID.ino
```

This retrieves the device ID using:

```
WiFi.getHostname()
```

