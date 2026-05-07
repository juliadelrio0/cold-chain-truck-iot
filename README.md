# Cold Chain Truck IoT

Cold Chain Truck IoT is a university IoT project focused on monitoring a refrigerated truck during the transport of fresh products.

The system collects telemetry data from an ESP32-based device, sends it to Azure, stores it in a cloud database, and visualizes the information through a web dashboard. The main goal is to help detect issues that could affect the cold chain, such as abnormal temperature values, high humidity, sudden movements, excessive speed, or missing location information.

## Main idea

The project is divided into three main parts:

1. **ESP32 device**: Responsible for collecting data from the physical sensors and publishing telemetry messages.

2. **Cloud infrastructure**: Responsible for receiving the telemetry, processing it, storing it in Azure CosmosDB, and managing alerts.

3. **Dashboard**: Responsible for displaying the data in a clear web interface, allowing the user to monitor the truck, check alerts, view historical records, send commands, and export reports.

## Repository structure

```text
cold-chain-truck-iot/
│
├── esp32c3/
│   ├── descubrirID/
│   │   ├── descubrirID.ino
│   ├── sensorFrigorifico_azure/
│   │   ├── sensorFrigorifico_azure.ino
│   └── README.md
│
├── cloud-code/
│   ├── host.json
│   ├── index.js
│   ├── mock_sensor.py
│   └── package.json
│
├── dashboard/
│   ├── .dockerignore
│   ├── .env.example
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── .gitignore
├── report.pdf
└── README.md
```

## Folders description

### `esp32/`

This folder contains the code related to the ESP32 device and the sensors used in the project.

It includes the firmware used to collect and publish telemetry data such as:

- temperature
- humidity
- acceleration
- angular speed
- linear speed
- GPS-related data

This folder also includes the code used to identify the device before registering it in Azure IoT Hub.

More details are available in:

```text
esp32/README.md
```

### `cloud-code/`

This folder contains the cloud-side components of the project.

It includes the logic used to receive telemetry data, store it in Azure CosmosDB, and manage alerts when abnormal values are detected.

The cloud part is responsible for connecting the device layer with the dashboard layer.

### `dashboard/`

This folder contains the web dashboard developed with Python and Streamlit.

The dashboard connects to Azure CosmosDB and displays the telemetry data in a visual and user-friendly way. It includes:

- device selection
- latest sensor readings
- active alerts
- device commands
- temperature and humidity charts
- GPS map
- telemetry history
- report export

More details are available in:

```text
dashboard/README.md
```

## Specifications

### Technologies used

- ESP32-C3
- DS18B20 temperature sensor
- DHT22 humidity sensor
- MPU6050 / GY-521 accelerometer and gyroscope
- NEO-6M GPS module
- Azure IoT Hub
- Azure CosmosDB
- Azure Functions
- Azure Service Bus
- Python
- Streamlit
- Docker

### Security note

Sensitive information such as connection strings, access keys, WiFi credentials, SAS tokens, and CosmosDB keys must not be committed to the repository.

Environment variables should be configured locally using `.env` files and documented through `.env.example` files when needed.

### General workflow

The complete system follows this data flow:

```text
Sensors → ESP32 → Azure IoT Hub → Cloud processing → Azure CosmosDB → Streamlit Dashboard
```

The ESP32 collects sensor data and sends it to Azure IoT Hub. The cloud layer processes and stores the information. Finally, the dashboard retrieves the stored telemetry and presents it to the user through a web interface.