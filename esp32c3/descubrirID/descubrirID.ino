#include <WiFi.h>

const char* WIFI_SSID     = "<SSID-YOUR-WIFI>";
const char* WIFI_PASSWORD = "<PASSWORD>";

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("Conectando a WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi conectado");

  String deviceId = WiFi.getHostname();

  Serial.print("DEVICE_ID: ");
  Serial.println(deviceId);
}

void loop() {
  // Nada
}
