#include "DHTesp.h"
#include <TinyGPS++.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// --- GPIO ---
#define PIN_DS18b20 4
#define PIN_DHT11 5
#define PIN_RX_NEO6M 7
#define PIN_TX_NEO6M 6
#define PIN_SDA_GY521 8
#define PIN_SCL_GY521 9


// definimos macro para indicar tarea, función y línea de código en los mensajes
#define DEBUG_STRING "["+String(pcTaskGetName(NULL))+" - "+String(__FUNCTION__)+"():"+String(__LINE__)+"]   "


// --- FreeRTOS ---
SemaphoreHandle_t semMqttReady;
SemaphoreHandle_t mqttMutex;
int periodo = 30;

// ------ SENSORES -------------
// Sensor DS18b20: Temperatura --> GPIO4
OneWire oneWire(PIN_DS18b20);
DallasTemperature sensors(&oneWire);
float temp;

// Sensor DHT11: Humedad --> GPIO5
DHTesp dht;
float hum;

// Sensor GY-521: Giroscopio (Aceleración/eje, Rotación/eje) --> GPIO6 Y 7 
const int MPU_ADDR = 0x68; // Despertar MPU6050
int16_t AccX, AccY, AccZ;
int16_t GyroX, GyroY, GyroZ;

// Sensor Neo6M: GPS (Latitud, Longitud, Velocidad lineal, Rumbo) --> GPIO8 Y 9
TinyGPSPlus gps;

// ------------- COMUNICACION --------------------------
const char* WIFI_SSID     = "<SIID-YOUR-WIFI>";
const char* WIFI_PASSWORD = "<PASSWORD>";

const char* IOT_HUB_HOST  = "<IOT-HUB-NAME>.azure-devices.net";
const char* SAS_TOKEN     = "SharedAccessSignature sr=<TOKEN-GENERATED>";
const int   MQTT_PORT     = 8883;
const char* MQTT_USERNAME = "<IOT-HUB-NAME>.azure-devices.net/<DEVICE_ID>/?api-version=2021-04-12";
String DEVICE_ID     = "YOURDEVICE"; // EL ID SERÁ EL String(WiFi.getHostname());

char telemetryTopic[128];
char c2dTopic[128];

const char* ROOT_CA =
"-----BEGIN CERTIFICATE-----\n"
"...DIGICERT CERTIFICATE...\n"
"-----END CERTIFICATE-----\n";

WiFiClientSecure wifiClient;
PubSubClient     mqttClient(wifiClient);

//=====================================================================================================

//-----------------------------------------------------
// muestra información de la tarea
//-----------------------------------------------------
inline void info_tarea_actual() { 
 Serial.println(DEBUG_STRING+"Prioridad de tarea "+ String(pcTaskGetName(NULL))+": "+String(uxTaskPriorityGet(NULL)));
}

//------------------------------------------------------------------------------------------------------
//                                   INICIALIZACIÓN Y LECTURA TIMESTAMP
//--------------------------------------------------------------------------------------------------------
// Timestamp via NTP
void syncNTP() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print(DEBUG_STRING+"Sincronizando NTP");
  time_t now = time(nullptr);
  while (now < 1000000000L) { delay(500); Serial.print("."); now = time(nullptr); }
  Serial.println(" OK");
}

void getTimestamp(char* buf, size_t len) {
  time_t now = time(nullptr);
  struct tm* t = gmtime(&now);
  strftime(buf, len, "%Y-%m-%dT%H:%M:%SZ", t);
}


//------------------------------------------------------------------------------------------------------
//                                   MANEJADOR COMANDOS
//--------------------------------------------------------------------------------------------------------
// Handler C2D
// Espera: 
//     -> {"period": 5, "message": "period changed"}
//     -> {"gps": True, "message": "GPS required"}
//     -> {"period": 5, "gps": False, "message": "period changed and gps required"}
void message_handler(char* topic, byte* payload, unsigned int length) {
  
  Serial.println("-------------------------------------------------------------------------");
  Serial.println(DEBUG_STRING+"Mensaje recibido desde la nube");

  char message[256];
  memcpy(message, payload, min(length, sizeof(message) - 1));
  message[length] = '\0';

  StaticJsonDocument<256> doc;
  if (deserializeJson(doc, message)) {
    Serial.println(DEBUG_STRING+"Error al parsear JSON");
    return;
  }

  send_gps = doc["gps"] | send_gps;
  periodo = doc["period"] | periodo;          // actualiza periodo si viene el campo
  const char* msg = doc["message"] | "";    // imprime el mensaje si viene
  if (strlen(msg) > 0) Serial.println(DEBUG_STRING+msg);

  // Creamos JSON de confirmación
  StaticJsonDocument<200> docConfirm;
  char when[32];
  getTimestamp(when, sizeof(when));

  docConfirm["id"] = DEVICE_ID;
  // Comprobamos qué datos hemos cambiado
  if (doc.containsKey("gps")){
    Serial.println(DEBUG_STRING+"Solicitud de cambio en ubicación recibida. Nuevo estado: " + send_gps);
    docConfirm["new_gps"] = send_gps;
  }
  if(doc.containsKey("period")){
    Serial.println(DEBUG_STRING+"Solicitud de cambio en el periodo. Publicación cada: " + periodo);
    docConfirm["new_period"] = periodo;
  }
  docConfirm["when"] = when;

  char payloadConf[200];
  serializeJson(docConfirm, payloadConf);

  Serial.println(DEBUG_STRING+" Mensaje de confirmación a enviar: " + payloadConf);

  Serial.println(DEBUG_STRING+"Publicando, esperando semáforo...");
  xSemaphoreTake(mqttMutex, portMAX_DELAY);
  mqttClient.publish(telemetryTopic, payloadConf);
  xSemaphoreGive(mqttMutex);
  Serial.println(DEBUG_STRING+"Mensaje publicado");


  Serial.println("-------------------------------------------------------------------------");
}


//------------------------------------------------------------------------------------------------------
//                                        LECTURA DE SENSORES
//--------------------------------------------------------------------------------------------------------

// DS18B20
void read_temp(bool verbose){
  sensors.requestTemperatures(); // Pedir medición
  temp = sensors.getTempCByIndex(0);

  if(verbose){
    if (temp == DEVICE_DISCONNECTED_C) {
      Serial.println(DEBUG_STRING+"Error: sensor DS18B20 no conectado");
    } else {
      Serial.println(DEBUG_STRING+"Temperatura: " + String(temp) + " ºC");
    }
  }
}


// DHT11 
void read_hum(bool verbose){
  hum = dht.getHumidity();

  if(verbose){
    if(isnan(hum)){
      Serial.println(DEBUG_STRING+"Error: humedad nula");
    }else{
      Serial.println(DEBUG_STRING+"Humedad: " + String(hum) + " %");
    }
  }
}


// GY-521
void read_girosc(bool verbose){
  // Comenzamos comunicación por I2C
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);

  // Solicitamos los datos. 8 bytes por lectura
  Wire.requestFrom(MPU_ADDR, 14, true);

  AccX = Wire.read() << 8 | Wire.read(); 
  AccY = Wire.read() << 8 | Wire.read();
  AccZ = Wire.read() << 8 | Wire.read();

  Wire.read(); Wire.read(); // temperatura

  GyroX = Wire.read() << 8 | Wire.read();
  GyroY = Wire.read() << 8 | Wire.read();
  GyroZ = Wire.read() << 8 | Wire.read();

  if(verbose){
    Serial.println(DEBUG_STRING+"Acc: " + String(AccX) + " | " + String(AccY) + " | " + String(AccZ));
    Serial.println(DEBUG_STRING+"Gyro: "+ String(GyroX) + " | " + String(GyroY) + " | " + String(GyroZ));
  }
}


// NEO6M 
void read_gps(bool verbose){
  while (Serial1.available()) {
    int read = Serial1.read();
    gps.encode(read);
  }

  if(verbose){
    if(gps.location.isValid()){
      Serial.println(DEBUG_STRING+"----- DATOS GPS -----");

      Serial.print(DEBUG_STRING+"Latitud: ");
      Serial.println(gps.location.lat(), 6);

      Serial.print(DEBUG_STRING+"Longitud: ");
      Serial.println(gps.location.lng(), 6);

      Serial.print(DEBUG_STRING+"Velocidad (km/h): ");
      Serial.println(gps.speed.kmph());

      Serial.print(DEBUG_STRING+"Rumbo (grados): ");
      Serial.println(gps.course.deg());

      Serial.print(DEBUG_STRING+"Satélites: ");
      Serial.println(gps.satellites.value());

    }else{
      Serial.println("Buscando señal GPS...");
    }
  }
    

}


//----------------------------------------------------------------------------------------------------------
//                                              INICIALIZAR SENSORES
//-----------------------------------------------------------------------------------------------------------

void ini_temp(){
  Serial.println(DEBUG_STRING+"...Iniciando DS18B20...");
  sensors.begin();
  read_temp(false); // Obtenemos primera lectura para evitar valores nulo inicial
  Serial.println(DEBUG_STRING+"...Finalizado DS18B20...");
}


void ini_hum(){
  Serial.println(DEBUG_STRING+"...Iniciando DHT11...");
  dht.setup(PIN_DHT11, DHTesp::DHT11);
  read_hum(false); // Obtenemos primera lectura para evitar valores nulo inicial
  Serial.println(DEBUG_STRING+"...Finalizado DHT11...");
  
}


void ini_giroscopio(){
  Serial.println(DEBUG_STRING+"...Iniciando GY-521...");
  Wire.begin(PIN_SDA_GY521, PIN_SCL_GY521);
  // Despertar MPU6050
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0);
  Wire.endTransmission(true);

  read_girosc(false);
  Serial.println(DEBUG_STRING+"...Finalizado GY-521...");
}


void ini_gps(){
  Serial.println(DEBUG_STRING+"...Iniciando NEO6M...");
  Serial1.begin(9600, SERIAL_8N1, PIN_TX_NEO6M, PIN_RX_NEO6M);

  // Leemos hasta que obtengamos señal de gps
  do{
    delay(5000);
    Serial.println(DEBUG_STRING+"...Buscando señal gps (cada 5 segundos)...");
    read_gps(false);
  }while(!gps.location.isValid());
  Serial.println(DEBUG_STRING+"...Finalizado NEO6M...");
}


void inicializarSensores(){
  ini_temp();
  ini_hum();
  ini_giroscopio();
  ini_gps();
}

//--------------------------------------------------------------------------------------------------
//                              INICIALIZAR CONEXIONES
//--------------------------------------------------------------------------------------------------

// --- WIFI -----
void connectWiFi() {
  Serial.println(DEBUG_STRING+"Conectando a WiFi " + WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println();
  Serial.println(DEBUG_STRING+"WiFi conectado, IP address: " + WiFi.localIP().toString());
}

// ----- MQTT -----
void conectaMQTT() {
  while (!mqttClient.connected()) {
    Serial.print(DEBUG_STRING+"Conectando a IoT Hub");
    if (mqttClient.connect(DEVICE_ID.c_str(), MQTT_USERNAME, SAS_TOKEN)) {
      Serial.println(" OK");
      mqttClient.subscribe(c2dTopic);
    } else {
      Serial.print(" Error: "); Serial.println(mqttClient.state());
      Serial.println(DEBUG_STRING+"Reintentando en 5 segundos..."); 
      delay(5000);
    }
  }
}

void inic_MQTT(){
  wifiClient.setCACert(ROOT_CA);
  mqttClient.setServer(IOT_HUB_HOST, MQTT_PORT);
  mqttClient.setCallback(message_handler); // FUNCIÓN QUE EMPLEA CUANDO RECIBE MENSAJES
  mqttClient.setBufferSize(1024);

  snprintf(telemetryTopic, sizeof(telemetryTopic),
    "devices/%s/messages/events/$.ct=application%%2Fjson&$.ce=utf-8", DEVICE_ID.c_str());
  snprintf(c2dTopic, sizeof(c2dTopic),
    "devices/%s/messages/devicebound/#", DEVICE_ID.c_str());

  conectaMQTT();
}

//-------------------------------------------------------------------------------------------------------------------
//                                                    TAREAS FreeRTOS
//------------------------------------------------------------------------------------------------------------------

// Publicar cada "periodo" s
void taskPublisher(void *pvParameters) {
  info_tarea_actual();
  Serial.println(DEBUG_STRING+"Tarea publicadora esperando en semáforo...");

  // Esperar a que MQTT esté listo
  xSemaphoreTake(semMqttReady, portMAX_DELAY);
  Serial.println(DEBUG_STRING+"Tarea publicadora supera el semáforo");



  while(true) {
    Serial.println("===========================================================================");
    read_temp(true);
    read_hum(true);
    read_girosc(true);
    read_gps(true);

    char when[32];
    getTimestamp(when, sizeof(when));

    // ---- TRANSFORMAMOS A JSON ---- 
    StaticJsonDocument<200> doc;
    doc["id"] = DEVICE_ID;
    doc["temperature"]    = temp;
    doc["humidity"]       = hum;

    JsonArray acc = doc.createNestedArray("acceleration");
    acc.add(AccX);
    acc.add(AccY);
    acc.add(AccZ);

    JsonArray gyro = doc.createNestedArray("angular_speed");
    gyro.add(GyroX);
    gyro.add(GyroY);
    gyro.add(GyroZ);

    doc["lineal_speed"]   = gps.speed.kmph();

    // Si solicitan enviar información gps a tiempo real
    if(send_gps){
      StaticJsonDocument<200> docGPS;
      if (gps.location.isValid()){
        docGPS["longitude"]  = gps.location.lng();
        docGPS["latitude"]   = gps.location.lat();
      }else{
        docGPS["longitude"]  = NULL;
        docGPS["latitude"]   = NULL;
      }
      docGPS["course"]     = gps.course.deg();

      //Agregamos en un campo GPS
      doc["gps"] = docGPS.as<JsonObject>();
    }

    doc["when"]        = when;

    char payload[200];
    serializeJson(doc, payload);

    Serial.println(DEBUG_STRING+" Mensaje periódico a enviar: " + payload);

    Serial.println(DEBUG_STRING+"Publicando, esperando semáforo...");
    xSemaphoreTake(mqttMutex, portMAX_DELAY);
    mqttClient.publish(telemetryTopic, payload);
    xSemaphoreGive(mqttMutex);

    Serial.println(DEBUG_STRING+"Mensaje publicado");
    Serial.println("===========================================================================");
    vTaskDelay(pdMS_TO_TICKS(periodo*1000));
  }
}

// ----------- Mantener conexión y ejecutar loop MQTT
void taskMQTTService(void *pvParameters) {
  info_tarea_actual();
  
  // Inicialización de WiFi
  connectWiFi();
  syncNTP();

  // Preparar identificadores
  DEVICE_ID = WiFi.getHostname();
  Serial.println(DEBUG_STRING+DEVICE_ID);
  
  // Inicializarr conexión MQTT
  inic_MQTT();

  // Conectarse a MQTT
  conectaMQTT();

  Serial.println(DEBUG_STRING+"Semaforo abierto...");

  // Señalizar que MQTT ya está listo
  xSemaphoreGive(semMqttReady);

  // Bucle principal de servicio MQTT
  while(true) {
    if (!mqttClient.connected()) conectaMQTT();
    mqttClient.loop();
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}


//--------------------------------------------------------------------------------------------------
//                                            SETUP
//--------------------------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  // Para evitar retrasos con la conexión del monitor serial
  delay(1000);

  Serial.println();

  // Crear semáforo
  semMqttReady = xSemaphoreCreateBinary();
  mqttMutex = xSemaphoreCreateBinary();
  xSemaphoreGive(mqttMutex);
  info_tarea_actual();

  // Inicializamos primero los sensores, dado que el GPS eslo que más tarda en inicializar
  Serial.println(DEBUG_STRING+" Inicializando sensores...");
  inicializarSensores();

  // Inicializamos la conexión WiFi y MQTT
  Serial.println(DEBUG_STRING+" Inicializando conexiones...");
  xTaskCreate(taskMQTTService, "MQTT Service", 4096, NULL, 2, NULL);


  // Arrancar la otra tarea (esperará al semáforo de MQTT para publicar)
  xTaskCreate(taskPublisher,   "Publisher",   4096, NULL, 1, NULL);

  Serial.println(DEBUG_STRING+"Setup terminado, esperando lectura periodica...");

  // --- Terminar la tarea loopTask ---
  vTaskDelete(NULL);
}

//-----------------------------------------------------
void loop() {
  // vacío: todo lo hacen las tareas FreeRTOS
}
