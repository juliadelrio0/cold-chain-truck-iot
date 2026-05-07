const { CosmosClient } = require("@azure/cosmos");
const { ServiceBusClient } = require("@azure/service-bus");

const COSMOS_URL = process.env.COSMOS_URL;
const COSMOS_KEY = process.env.COSMOS_KEY;
const DATABASE_NAME = "camion-db";
const CONTAINER_NAME = "telemetria";
const SERVICE_BUS_CONNECTION = process.env.SERVICE_BUS_CONNECTION;
const QUEUE_NAME = "alerts";

const cosmosClient = new CosmosClient({ endpoint: COSMOS_URL, key: COSMOS_KEY });
const container = cosmosClient.database(DATABASE_NAME).container(CONTAINER_NAME);

const TEMP_MIN = -5.0, TEMP_MAX = 4.0, SPEED_MAX = 90.0, ACCEL_MAX = 0.8;

function checkAlerts(data) {
    const alerts = [];
    if (data.temperature < TEMP_MIN || data.temperature > TEMP_MAX)
        alerts.push(`Temperature alert: ${data.temperature}°C`);
    if (data.linear_speed > SPEED_MAX)
        alerts.push(`Speed alert: ${data.linear_speed} km/h`);
    
    // Check acceleration array [x, y, z]
    const acc = data.acceleration;
    if (Array.isArray(acc)) {
        if (Math.abs(acc[0]) > ACCEL_MAX || Math.abs(acc[1]) > ACCEL_MAX)
            alerts.push(`Brutal acceleration detected! X:${acc[0]} Y:${acc[1]}`);
    } else if (acc && typeof acc === 'object') {
        if (Math.abs(acc.x) > ACCEL_MAX || Math.abs(acc.y) > ACCEL_MAX)
            alerts.push(`Brutal acceleration detected! X:${acc.x} Y:${acc.y}`);
    }
    return alerts;
}

module.exports = async function (context, req) {
    try {
        const data = req.body;
        data.id = require("crypto").randomUUID();
        data.deviceId = "esp32-camion";
        data.timestamp = new Date().toISOString();

        await container.items.upsert(data);
        context.log("[CosmosDB] Data saved!");

        const alerts = checkAlerts(data);
        
        if (alerts.length > 0 && SERVICE_BUS_CONNECTION) {
            const sbClient = new ServiceBusClient(SERVICE_BUS_CONNECTION);
            const sender = sbClient.createSender(QUEUE_NAME);
            const alertPayload = {
                deviceId: data.deviceId,
                temperature: data.temperature,
                linear_speed: data.linear_speed,
                acceleration: data.acceleration,
                alerts: alerts,
                moment: data.timestamp
            };
            await sender.sendMessages({ body: JSON.stringify(alertPayload) });
            await sender.close();
            await sbClient.close();
            context.log(`[ALERT] Sent to Service Bus: ${alerts.join(', ')}`);
        }

        context.res = {
            status: 200,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "ok", alerts })
        };
    } catch (e) {
        context.log.error(`[ERROR] ${e.message}`);
        context.res = { status: 500, body: e.message };
    }
};