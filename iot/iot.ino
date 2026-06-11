#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <DHT.h>
#include <HardwareSerial.h>

// ============ WIFI — same network as PC ============
const char* ssid = "M.khaled";
const char* password = "01002147742M";

// PC IPv4 from Windows ipconfig (Wi-Fi adapter)
static const char IOT_HOST[] = "192.168.1.2";
static const uint16_t IOT_PORT = 5000;
static const char IOT_PATH[] = "/api/iot/upload";
const int UPLOAD_USER_ID = 4;

#define SOIL_AO 35
#define RAIN_AO 34
#define PH_PIN 33
#define DHTPIN 5
#define DHTTYPE DHT22
#define RS485_RX 16
#define RS485_TX 17
#define RS485_RE 18
#define RS485_DE 19

DHT dht(DHTPIN, DHTTYPE);
HardwareSerial npkSerial(2);
WebServer server(80);
WiFiClient wifiClient;

char iotUploadUrl[128];
char sensorsPageUrl[64];

const int SOIL_DRY = 3110;
const int SOIL_WET = 1450;
const int RAIN_DRY = 4095;
const int RAIN_WET = 1200;
float neutralVoltage = 1.16;
float slope = -5.7;

const byte nitroCmd[] = {0x01,0x03,0x00,0x00,0x00,0x01,0x84,0x0A};
const byte phosCmd[]  = {0x01,0x03,0x00,0x01,0x00,0x01,0xD5,0xCA};
const byte potaCmd[]  = {0x01,0x03,0x00,0x02,0x00,0x01,0x25,0xCA};

struct SensorData {
  float temperature, humidity, rainfall, ph;
  int soilHumidity, nitrogen, phosphorus, potassium;
};

void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.println("WiFi reconnecting...");
  WiFi.disconnect();
  WiFi.begin(ssid, password);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());
    snprintf(sensorsPageUrl, sizeof(sensorsPageUrl), "http://%s/sensors", WiFi.localIP().toString().c_str());
    Serial.print("Live sensors URL: ");
    Serial.println(sensorsPageUrl);
  }
}

int getSoilHumidity() {
  long sum = 0;
  for (int i = 0; i < 15; i++) {
    sum += analogRead(SOIL_AO);
    delay(5);
  }
  return constrain(map((int)(sum / 15), SOIL_DRY, SOIL_WET, 0, 100), 0, 100);
}

float rainfallMMFromADC(int adc) {
  return constrain(map(adc, RAIN_DRY, RAIN_WET, 20, 299), 20.0f, 299.0f);
}

float readPH() {
  long sum = 0;
  for (int i = 0; i < 20; i++) {
    sum += analogRead(PH_PIN);
    delay(10);
  }
  float voltage = (sum / 20.0f) * (3.3f / 4095.0f);
  return 7.0f + ((voltage - neutralVoltage) * slope);
}

int readNPK(const byte *cmd, int size) {
  byte buf[32];
  int len = 0;
  while (npkSerial.available()) npkSerial.read();

  digitalWrite(RS485_RE, HIGH);
  digitalWrite(RS485_DE, HIGH);
  delay(10);
  npkSerial.write(cmd, size);
  npkSerial.flush();
  digitalWrite(RS485_DE, LOW);
  digitalWrite(RS485_RE, LOW);
  delay(30);

  unsigned long start = millis();
  while (millis() - start < 1000 && len < 32) {
    if (npkSerial.available()) buf[len++] = npkSerial.read();
  }
  for (int i = 0; i <= len - 7; i++) {
    if (buf[i] == cmd[0] && buf[i+1] == 0x03 && buf[i+2] == 0x02) {
      return (buf[i+3] << 8) | buf[i+4];
    }
  }
  return -1;
}

SensorData readAllSensors() {
  SensorData s = {};
  s.humidity = dht.readHumidity();
  s.temperature = dht.readTemperature();
  if (isnan(s.humidity) || isnan(s.temperature)) {
    s.humidity = 0;
    s.temperature = 0;
  }
  s.soilHumidity = getSoilHumidity();
  s.rainfall = rainfallMMFromADC(analogRead(RAIN_AO));
  s.ph = readPH();
  s.nitrogen = readNPK(nitroCmd, sizeof(nitroCmd));
  delay(200);
  s.phosphorus = readNPK(phosCmd, sizeof(phosCmd));
  delay(200);
  s.potassium = readNPK(potaCmd, sizeof(potaCmd));
  return s;
}

String buildJson(const SensorData& s) {
  String json = "{";
  if (UPLOAD_USER_ID > 0) json += "\"user_id\":" + String(UPLOAD_USER_ID) + ",";
  json += "\"temperature\":" + String(s.temperature, 1) + ",";
  json += "\"humidity\":" + String(s.humidity, 1) + ",";
  json += "\"rainfall\":" + String(s.rainfall, 1) + ",";
  json += "\"soilHumidity\":" + String(s.soilHumidity) + ",";
  json += "\"ph\":" + String(s.ph, 2) + ",";
  json += "\"nitrogen\":" + String(s.nitrogen) + ",";
  json += "\"phosphorus\":" + String(s.phosphorus) + ",";
  json += "\"potassium\":" + String(s.potassium);
  json += "}";
  return json;
}

void printSerial(const SensorData& s) {
  Serial.println("=================================");
  Serial.printf("Temp: %.1fC | Hum: %.1f%%\n", s.temperature, s.humidity);
  Serial.printf("Soil Humidity: %d%%\n", s.soilHumidity);
  Serial.printf("Rain: %.1f mm\n", s.rainfall);
  Serial.printf("pH: %.2f\n", s.ph);
  Serial.printf("NPK: %d-%d-%d\n", s.nitrogen, s.phosphorus, s.potassium);
}

void sendJsonResponse(const String& json) {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

void handleSensors() {
  SensorData s = readAllSensors();
  printSerial(s);
  sendJsonResponse(buildJson(s));
}

void handleOptions() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
  server.send(204);
}

bool postToServer(const SensorData& s) {
  ensureWiFi();
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  http.begin(wifiClient, iotUploadUrl);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(8000);

  String json = buildJson(s);
  int code = http.POST(json);
  Serial.print("POST ");
  Serial.print(iotUploadUrl);
  Serial.print(" -> HTTP ");
  Serial.println(code);
  if (code != 200) Serial.println(http.getString());
  http.end();
  return code == 200;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  dht.begin();
  pinMode(RS485_RE, OUTPUT);
  pinMode(RS485_DE, OUTPUT);
  digitalWrite(RS485_RE, LOW);
  digitalWrite(RS485_DE, LOW);
  npkSerial.begin(9600, SERIAL_8N1, RS485_RX, RS485_TX);

  ensureWiFi();

  snprintf(iotUploadUrl, sizeof(iotUploadUrl), "http://%s:%u%s", IOT_HOST, (unsigned)IOT_PORT, IOT_PATH);
  Serial.println(iotUploadUrl);

  server.on("/sensors", HTTP_GET, handleSensors);
  server.on("/sensors", HTTP_OPTIONS, handleOptions);
  server.begin();
}

void loop() {
  server.handleClient();
  ensureWiFi();

  static unsigned long lastPost = 0;
  if (millis() - lastPost >= 10000) {
    lastPost = millis();
    SensorData s = readAllSensors();
    printSerial(s);
    postToServer(s);
  }
}
