import os
from datetime import datetime
import pandas as pd
import plotly.express as px
import streamlit as st
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
import json
from azure.iot.hub import IoTHubRegistryManager


load_dotenv()


COSMOS_URL = os.getenv("COSMOS_URL")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER")
IOT_HUB_CONNECTION_STRING = os.getenv("IOT_HUB_CONNECTION_STRING")


def send_cloud_to_device_message(device_id: str, payload: dict):
    if not IOT_HUB_CONNECTION_STRING:
        raise ValueError("IOT_HUB_CONNECTION_STRING is not configured.")

    registry_manager = IoTHubRegistryManager(IOT_HUB_CONNECTION_STRING)
    message = json.dumps(payload)
    registry_manager.send_c2d_message(device_id, message)

COSMOS_INTERNAL_FIELDS = {"_rid", "_self", "_etag", "_attachments", "_ts"}

# Thresholds match the Azure Function (index.js) in feature/cloud
TEMP_HIGH     = 4.0   # °C
TEMP_LOW      = -5.0  # °C
HUMIDITY_HIGH = 90    # %
SPEED_LIMIT   = 90    # km/h
ACCEL_LIMIT = 0.8

st.set_page_config(
    page_title="Cold Chain Truck -- Operations Dashboard",
    page_icon="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Background ── */
    .stApp {
        background-color: #f4f6f9;
    }

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Top navigation bar ── */
    .topbar {
        background: linear-gradient(100deg, #0a1e3d 0%, #0f2f5c 60%, #0d3d5e 100%);
        border-radius: 12px;
        border-bottom: 3px solid #1e88e5;
        padding: 1.5rem 2.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 0 0 2.5rem 0;
    }
    .topbar-brand {
        color: #ffffff;
        font-size: 1.65rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        line-height: 1.15;
    }
    .topbar-brand span {
        color: #64b5f6;
    }
    .topbar-sub {
        color: rgba(255,255,255,0.5);
        font-size: 0.8rem;
        font-weight: 400;
        margin-top: 0.25rem;
        letter-spacing: 0.2px;
    }
    .topbar-meta {
        text-align: right;
        color: rgba(255,255,255,0.55);
        font-size: 0.78rem;
        line-height: 1.8;
    }
    .topbar-meta strong {
        color: #90caf9;
        font-weight: 600;
        font-size: 0.92rem;
    }

    /* ── Section headings ── */
    .section-heading {
        color: #0f2544;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        margin: 2rem 0 0.85rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #1565c0;
        display: inline-block;
    }

    /* ── Metric cards ── */
    .metric-card {
        background: #ffffff;
        border-radius: 8px;
        padding: 1.4rem 1.6rem 1.2rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        border: 1px solid #dde3ed;
        height: 100%;
    }
    .metric-label {
        color: #607d8b;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.55rem;
    }
    .metric-value {
        color: #0f2544;
        font-size: 1.75rem;
        font-weight: 700;
        line-height: 1.1;
    }
    .metric-value.no-data {
        color: #b0bec5;
        font-size: 1rem;
        font-weight: 400;
        font-style: italic;
    }
    .metric-unit {
        color: #90a4ae;
        font-size: 0.85rem;
        font-weight: 400;
        margin-left: 0.2rem;
    }

    /* ── Divider ── */
    .divider {
        border: none;
        border-top: 1px solid #dde3ed;
        margin: 1.5rem 0;
    }

    /* ── Alert rows ── */
    .alert-row {
        background: #fff8e1;
        border: 1px solid #ffe082;
        border-left: 4px solid #f9a825;
        border-radius: 6px;
        padding: 0.65rem 1rem;
        margin-bottom: 0.45rem;
        color: #6d4c00;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .alert-row.critical {
        background: #fce4ec;
        border-color: #f48fb1;
        border-left-color: #b71c1c;
        color: #7b1a1a;
    }
    .alert-ok {
        background: #e8f5e9;
        border: 1px solid #a5d6a7;
        border-left: 4px solid #2e7d32;
        border-radius: 6px;
        padding: 0.65rem 1rem;
        color: #1b5e20;
        font-size: 0.85rem;
        font-weight: 500;
    }

    /* ── Empty state ── */
    .empty-state {
        text-align: center;
        padding: 2.5rem 1rem;
        color: #90a4ae;
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid #dde3ed;
        font-size: 0.9rem;
        line-height: 1.7;
    }

    /* ── Chart card wrapper ── */
    .chart-card {
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid #dde3ed;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        padding: 1rem;
    }

    /* ── Data table ── */
    .stDataFrame {
        border-radius: 8px !important;
        overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
        border: 1px solid #dde3ed !important;
    }

    /* ── Footer ── */
    .page-footer {
        text-align: center;
        color: #90a4ae;
        font-size: 0.75rem;
        padding: 1.5rem 0 0.5rem;
        border-top: 1px solid #dde3ed;
        margin-top: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_container():
    client = CosmosClient(COSMOS_URL, credential=COSMOS_KEY)
    database = client.get_database_client(COSMOS_DATABASE)
    container = database.get_container_client(COSMOS_CONTAINER)
    return container


@st.cache_data(ttl=10)
def load_telemetry_data():
    container = get_container()
    query = """
    SELECT TOP 200 *
    FROM c
    ORDER BY c._ts DESC
    """
    items = list(
        container.query_items(query=query, enable_cross_partition_query=True)
    )
    return pd.DataFrame(items)


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # ──── Extract body field ──────────────────────────────────────────────────
    if "Body" in df.columns:

        body_fields = [
            "id",
            "temperature",
            "humidity",
            "linear_speed",
            "lineal_speed",
            "gps",
            "acceleration",
            "angular_speed",
            "when",
            "timestamp",
            "new_gps",
            "new_period"
        ]

        for field in body_fields:
            if field not in df.columns:
                df[field] = df["Body"].apply(
                    lambda body: body.get(field, None)
                )
            elif field == "id":
                df[field] = df["Body"].apply(
                    lambda body: body.get(field, None)
                )
        
        # ──── Handling GPS ────
        df["latitude"] = df["Body"].apply(lambda b: b.get("gps", {}).get("latitude"))
        df["longitude"] = df["Body"].apply(lambda b: b.get("gps", {}).get("longitude"))
        df["course"] = df["Body"].apply(
            lambda b: (
                b.get("gps", {}).get("course") or
                b.get("gps", {}).get("heading") or
                b.get("gps", {}).get("bearing")
            )
        )



    # ──── Extract real device id ──────────────────────────────────────────────────
    if "SystemProperties" in df.columns:
        
        df["deviceId"] = df["SystemProperties"].apply(
            lambda props: props.get("iothub-connection-device-id", None)
        )

    # ── Unify timestamp field ────────────────────────────────────────────────
    # The Azure Function (index.js) stores the field as 'timestamp'.
    # Older documents or mock data may use 'when'.
    # We normalise everything to 'when' so the rest of the dashboard is uniform.
    if "timestamp" in df.columns and "when" not in df.columns:
        df["when"] = df["timestamp"]
    elif "timestamp" in df.columns and "when" in df.columns:
        # Fill gaps: prefer 'timestamp' where 'when' is missing
        df["when"] = df["when"].fillna(df["timestamp"])

    if "when" in df.columns:
        df["when"] = pd.to_datetime(df["when"], errors="coerce")

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    if "when" not in df.columns and "timestamp" in df.columns:
        df["when"] = df["timestamp"]

    # ── Use CosmosDB _ts (unix epoch) as fallback sort key ───────────────────
    if "_ts" in df.columns:
        df["_ts"] = pd.to_numeric(df["_ts"], errors="coerce")

    numeric_columns = [
        "temperature", "humidity", "linear_speed", "lineal_speed",
        "latitude", "longitude", "course",
    ]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "linear_speed" not in df.columns and "lineal_speed" in df.columns:
        df["linear_speed"] = df["lineal_speed"]

    # ── Sort by most recent first using best available key ───────────────────
    if "when" in df.columns and df["when"].notna().any():
        df = df.sort_values("when", ascending=False).reset_index(drop=True)
    elif "_ts" in df.columns:
        df = df.sort_values("_ts", ascending=False).reset_index(drop=True)

    return df


def get_latest_value(df: pd.DataFrame, column: str):
    """Return the value of *column* from the most recent document.

    The dataframe is already sorted most-recent-first by prepare_dataframe,
    so we just take the first non-null row.
    """
    if column not in df.columns:
        return None
    valid = df.dropna(subset=[column])
    if valid.empty:
        return None
    return valid.iloc[0][column]


def detect_alerts(df: pd.DataFrame) -> list[dict]:
    alerts = []
    temp    = get_latest_value(df, "temperature")
    humidity = get_latest_value(df, "humidity")
    speed   = get_latest_value(df, "linear_speed")
    acceleration = get_latest_value(df, "acceleration")

    if temp is not None and temp > TEMP_HIGH:
        alerts.append({
            "text": f"Temperature above threshold: {temp:.2f} °C (limit: {TEMP_HIGH} °C)",
            "critical": True,
        })
    if temp is not None and temp < TEMP_LOW:
        alerts.append({
            "text": f"Temperature below threshold: {temp:.2f} °C (limit: {TEMP_LOW} °C)",
            "critical": True,
        })
    if humidity is not None and humidity > HUMIDITY_HIGH:
        alerts.append({
            "text": f"Humidity above threshold: {humidity:.2f} % (limit: {HUMIDITY_HIGH} %)",
            "critical": False,
        })
    if speed is not None and speed > SPEED_LIMIT:
        alerts.append({
            "text": f"Speed limit exceeded: {speed:.2f} km/h (limit: {SPEED_LIMIT} km/h)",
            "critical": True,
        })
    if acceleration is not None:
        try:
            if isinstance(acceleration, dict):
                acc_x = abs(float(acceleration.get("x", 0)))
                acc_y = abs(float(acceleration.get("y", 0)))
            elif isinstance(acceleration, list) and len(acceleration) >= 2:
                acc_x = abs(float(acceleration[0]))
                acc_y = abs(float(acceleration[1]))
            else:
                acc_x = acc_y = 0

            if acc_x > ACCEL_LIMIT or acc_y > ACCEL_LIMIT:
                alerts.append({
                    "text": f"Brutal acceleration detected: X={acc_x:.2f}, Y={acc_y:.2f} (limit: {ACCEL_LIMIT})",
                    "critical": True,
                })
        except Exception:
            pass
    return alerts


def render_metric_card(label: str, value, unit: str = ""):
    if value is None:
        value_html = '<span class="metric-value no-data">No data available</span>'
    elif isinstance(value, (int, float)):
        value_html = (
            f'<span class="metric-value">{value:.2f}'
            f'<span class="metric-unit">{unit}</span></span>'
        )
    elif hasattr(value, "strftime"):
        formatted = value.strftime("%d %b %Y  %H:%M:%S")
        value_html = (
            f'<span class="metric-value" style="font-size:1rem;'
            f'letter-spacing:-0.3px;">{formatted}</span>'
        )
    else:
        value_html = (
            f'<span class="metric-value" style="font-size:1.1rem;">'
            f'{value}{unit}</span>'
        )

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            {value_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


now_str  = datetime.now().strftime("%d %b %Y")
time_str = datetime.now().strftime("%H:%M")

st.markdown(
    f"""
    <div class="topbar">
        <div>
            <div class="topbar-brand">Cold Chain Truck &nbsp;<span>&mdash;</span>&nbsp; Operations Dashboard</div>
            <div class="topbar-sub">Refrigerated transport monitoring &nbsp;&bull;&nbsp; Azure IoT Hub &nbsp;&bull;&nbsp; Azure CosmosDB</div>
        </div>
        <div class="topbar-meta">
            <strong>{now_str}</strong><br>
            {time_str} &nbsp;&bull;&nbsp; Auto-refresh every 10 s
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


try:
    df = load_telemetry_data()
    df = prepare_dataframe(df)
except Exception as error:
    st.error("Unable to retrieve telemetry data from Azure CosmosDB. "
             "Please verify your connection settings.")
    st.exception(error)
    st.stop()

if df.empty:
    st.markdown(
        """
        <div class="empty-state">
            <strong>No telemetry records found.</strong><br>
            Ensure that the data ingestion pipeline is active
            (<code>mocksensor.py</code> or the physical ESP32 device)
            and that the correct CosmosDB container is configured.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


st.markdown('<span class="section-heading">Current Readings</span>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    render_metric_card("Temperature", get_latest_value(df, "temperature"), " °C")
with col2:
    render_metric_card("Relative Humidity", get_latest_value(df, "humidity"), " %")
with col3:
    render_metric_card("Vehicle Speed", get_latest_value(df, "linear_speed"), " km/h")
with col4:
    render_metric_card("Last Record", get_latest_value(df, "when"))

st.markdown('<hr class="divider">', unsafe_allow_html=True)


st.markdown('<span class="section-heading">Active Alerts</span>', unsafe_allow_html=True)

alerts = detect_alerts(df)

if alerts:
    for alert in alerts:
        css = "alert-row critical" if alert["critical"] else "alert-row"
        severity = "CRITICAL" if alert["critical"] else "WARNING"
        st.markdown(
            f'<div class="{css}"><strong>{severity}</strong> &mdash; {alert["text"]}</div>',
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        '<div class="alert-ok">All parameters are within defined thresholds. '
        'No active alerts.</div>',
        unsafe_allow_html=True,
    )

st.markdown('<hr class="divider">', unsafe_allow_html=True)


st.markdown('<span class="section-heading">Device Commands</span>', unsafe_allow_html=True)

available_devices = []

if "deviceId" in df.columns:
    available_devices = sorted(df["deviceId"].dropna().unique().tolist())
elif "id" in df.columns:
    available_devices = sorted(df["id"].dropna().unique().tolist())

if not IOT_HUB_CONNECTION_STRING:
    st.markdown(
        """
        <div class="empty-state">
            <strong>Device commands are not configured yet.</strong><br>
            Add <code>IOT_HUB_CONNECTION_STRING</code> to the local <code>.env</code> file
            to enable cloud-to-device commands through Azure IoT Hub.
        </div>
        """,
        unsafe_allow_html=True,
    )

elif not available_devices:
    st.markdown(
        """
        <div class="empty-state">
            <strong>No target devices found.</strong><br>
            The dashboard needs at least one device identifier from telemetry records
            to send commands.
        </div>
        """,
        unsafe_allow_html=True,
    )

else:
    st.write(
        "Send manual commands to the selected ESP32 device. "
        "This is useful for testing the telemetry period and requesting GPS data during the demo."
    )

    selected_device = st.selectbox(
        "Target device",
        available_devices,
        help="This value must match the device ID registered in Azure IoT Hub.",
    )

    command_col1, command_col2 = st.columns(2)

    with command_col1:
        st.markdown("**Update telemetry period**")

        new_period = st.number_input(
            "New period in seconds",
            min_value=1,
            max_value=3600,
            value=10,
            step=1,
        )

        if st.button("Send period command", width='stretch'):
            try:
                send_cloud_to_device_message(
                    selected_device,
                    {
                        "period": int(new_period),
                        "message": f"Update telemetry period to {new_period} seconds",
                    },
                )
                st.success(f"Period command sent to {selected_device}.")
            except Exception as error:
                st.error("Could not send period command.")
                st.exception(error)

    with command_col2:
        st.markdown("**GPS telemetry**")

        st.write(
            "Enable or disable GPS telemetry from the ESP32 device."
        )

        gps_enabled = st.toggle(
            "Enable GPS telemetry",
            value=False,
            help="When enabled, the dashboard sends gps:true. When disabled, it sends gps:false.",
        )

        if st.button("Send GPS command", width='stretch'):
            try:
                send_cloud_to_device_message(
                    selected_device,
                    {
                        "gps": bool(gps_enabled),
                        "message": (
                            "Enable GPS telemetry"
                            if gps_enabled
                            else "Disable GPS telemetry"
                        ),
                    },
                )

                if gps_enabled:
                    st.success(f"GPS telemetry enabled for {selected_device}.")
                else:
                    st.success(f"GPS telemetry disabled for {selected_device}.")

            except Exception as error:
                st.error("Could not send GPS command.")
                st.exception(error)

st.markdown('<hr class="divider">', unsafe_allow_html=True)


st.markdown('<span class="section-heading">Sensor Trends</span>', unsafe_allow_html=True)

df_time = df.copy()
if "when" in df_time.columns:
    df_time = df_time.dropna(subset=["when"]).sort_values("when")

_layout = dict(
    paper_bgcolor="#ffffff",
    plot_bgcolor="#ffffff",
    font=dict(family="Inter, sans-serif", size=12, color="#455a64"),
    margin=dict(l=10, r=16, t=44, b=10),
    xaxis=dict(
        showgrid=True, gridcolor="#eef0f5", zeroline=False,
        linecolor="#dde3ed", title_text="",
    ),
    yaxis=dict(
        showgrid=True, gridcolor="#eef0f5", zeroline=False,
        linecolor="#dde3ed",
    ),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    if "temperature" in df_time.columns and not df_time["temperature"].dropna().empty:
        fig_temp = px.line(
            df_time, x="when", y="temperature",
            title="Temperature (°C)",
            markers=True,
            color_discrete_sequence=["#1565c0"],
        )
        fig_temp.update_traces(
            line=dict(width=2),
            marker=dict(size=6, symbol="circle"),
            fill="tozeroy",
            fillcolor="rgba(21,101,192,0.06)",
        )
        fig_temp.update_layout(**_layout)
        fig_temp.add_hline(
            y=TEMP_HIGH, line_dash="dot", line_color="#b71c1c", line_width=1.5,
            annotation_text=f"Max threshold ({TEMP_HIGH} °C)",
            annotation_position="top right",
            annotation_font_size=11,
            annotation_font_color="#b71c1c",
        )
        st.plotly_chart(fig_temp, width='stretch')
    else:
        st.markdown(
            '<div class="empty-state">No temperature readings available.</div>',
            unsafe_allow_html=True,
        )

with chart_col2:
    if "humidity" in df_time.columns and not df_time["humidity"].dropna().empty:
        fig_hum = px.line(
            df_time, x="when", y="humidity",
            title="Relative Humidity (%)",
            markers=True,
            color_discrete_sequence=["#00695c"],
        )
        fig_hum.update_traces(
            line=dict(width=2),
            marker=dict(size=6, symbol="circle"),
            fill="tozeroy",
            fillcolor="rgba(0,105,92,0.06)",
        )
        fig_hum.update_layout(**_layout)
        fig_hum.add_hline(
            y=HUMIDITY_HIGH, line_dash="dot", line_color="#e65100", line_width=1.5,
            annotation_text=f"Max threshold ({HUMIDITY_HIGH} %)",
            annotation_position="top right",
            annotation_font_size=11,
            annotation_font_color="#e65100",
        )
        st.plotly_chart(fig_hum, width='stretch')
    else:
        st.markdown(
            '<div class="empty-state">No humidity readings available.</div>',
            unsafe_allow_html=True,
        )

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown('<span class="section-heading">Vehicle Location</span>', unsafe_allow_html=True)

if "latitude" in df.columns and "longitude" in df.columns:
    gps_df = df.dropna(subset=["latitude", "longitude"]).copy()

    if not gps_df.empty:
        gps_df = gps_df.rename(columns={"latitude": "lat", "longitude": "lon"})

        hover_cols = {
            col: True
            for col in ["when", "temperature", "humidity", "linear_speed"]
            if col in gps_df.columns
        }

        fig_map = px.scatter_map(
            gps_df,
            lat="lat", lon="lon",
            hover_data=hover_cols,
            color_discrete_sequence=["#1565c0"],
            zoom=10,
            height=400,
            title="Route - GPS Coordinates",
        )
        fig_map.update_traces(marker=dict(size=9))
        fig_map.update_layout(
            mapbox_style="open-street-map",
            paper_bgcolor="#ffffff",
            margin=dict(l=0, r=0, t=44, b=0),
            font=dict(family="Inter, sans-serif", size=12),
            title_font=dict(size=13, color="#0f2544"),
        )
        st.plotly_chart(fig_map, width='stretch')

    else:
        st.markdown(
            '<div class="empty-state">'
            'GPS fields are present in the schema but no valid coordinates have been received yet.'
            '</div>',
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        '<div class="empty-state">'
        'GPS telemetry fields are not present in the current data set.<br>'
        '<small>Location data will appear once the full telemetry pipeline is active.</small>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown('<hr class="divider">', unsafe_allow_html=True)


st.markdown('<span class="section-heading">Telemetry Records</span>', unsafe_allow_html=True)

preferred_columns = [
    "when", "timestamp", "deviceId", "id",
    "temperature", "humidity",
    "linear_speed", "lineal_speed",
    "latitude", "longitude", "course",
    "acceleration", "angular_speed", "new_gps", "new_period"
]

columns_to_show = [
    col for col in preferred_columns
    if col in df.columns and col not in COSMOS_INTERNAL_FIELDS
]

if not columns_to_show:
    columns_to_show = [
        col for col in df.columns if col not in COSMOS_INTERNAL_FIELDS
    ]

display_df = df[columns_to_show].copy()

if "when" in display_df.columns:
    display_df = display_df.sort_values("when", ascending=False)

if "acceleration" in display_df.columns:
    display_df["acc_x"] = display_df["acceleration"].apply(
        lambda a: a[0] if isinstance(a, list) and len(a) > 0 else None
    )
    display_df["acc_y"] = display_df["acceleration"].apply(
        lambda a: a[1] if isinstance(a, list) and len(a) > 1 else None
    )
    display_df = display_df.drop(columns=["acceleration"])


if "angular_speed" in display_df.columns:
    display_df["ang_rot_x"] = display_df["angular_speed"].apply(
        lambda a: a[0] if isinstance(a, list) and len(a) > 0 else None
    )
    display_df["ang_rot_y"] = display_df["angular_speed"].apply(
        lambda a: a[1] if isinstance(a, list) and len(a) > 1 else None
    )
    display_df["ang_rot_z"] = display_df["angular_speed"].apply(
        lambda a: a[2] if isinstance(a, list) and len(a) > 2 else None
    )
    display_df = display_df.drop(columns=["angular_speed"])
st.dataframe(display_df, width='stretch', hide_index=True)


st.markdown(
    """
    <div class="page-footer">
        Cold Chain Truck &mdash; Operations Dashboard &nbsp;&bull;&nbsp;
        Data source: Azure CosmosDB &nbsp;&bull;&nbsp;
        Refresh interval: 10 s
    </div>
    """,
    unsafe_allow_html=True,
)