# Dashboard

This folder contains the web dashboard used to visualize the refrigerated truck telemetry data stored in Azure CosmosDB.

## Features

- Display latest temperature, humidity and speed values.
- Show time-series charts for temperature and humidity.
- Display GPS location data.
- Highlight alerts when predefined thresholds are exceeded.
- Show historical telemetry records.
- Future improvement: export or print trip reports.

## Environment variables

Create a `.env` file based on `.env.example`:

```env
COSMOS_URL=
COSMOS_KEY=
COSMOS_DATABASE=
COSMOS_CONTAINER=
```

> **Important**: Do not commit the real `.env` file.