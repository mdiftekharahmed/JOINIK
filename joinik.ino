#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

// =========================
// Wi-Fi
// =========================
const char* WIFI_SSID = "Phone";
const char* WIFI_PASSWORD = "password?";

// =========================
// ThingsBoard
// =========================
const char* TB_URL =
  "http://100.82.190.70:8080/api/v1/"
  "kfmb4paxjs38aejylsw0/telemetry";

// =========================
// NTP
// Bangladesh = UTC+6
// =========================
const long GMT_OFFSET_SEC = 6 * 3600;
const int DAYLIGHT_OFFSET_SEC = 0;

// =========================
// Timing
// =========================
unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 2000;


void setup() {

  Serial.begin(115200);
  delay(1000);

  // -------------------------
  // Connect Wi-Fi
  // -------------------------
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to Wi-Fi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected");

  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());

  Serial.print("Gateway: ");
  Serial.println(WiFi.gatewayIP());

  Serial.print("RSSI: ");
  Serial.println(WiFi.RSSI());

  // -------------------------
  // MAC address
  // -------------------------
  Serial.print("MAC: ");
  Serial.println(WiFi.macAddress());

  // -------------------------
  // NTP time
  // -------------------------
  configTime(
    GMT_OFFSET_SEC,
    DAYLIGHT_OFFSET_SEC,
    "pool.ntp.org",
    "time.nist.gov"
  );

  Serial.println("Waiting for time synchronization...");

  struct tm timeinfo;

  while (!getLocalTime(&timeinfo)) {
    Serial.print(".");
    delay(500);
  }

  Serial.println();
  Serial.println("Time synchronized");
}


void loop() {

  // -------------------------
  // Reconnect if Wi-Fi drops
  // -------------------------
  if (WiFi.status() != WL_CONNECTED) {

    Serial.println("Wi-Fi disconnected. Reconnecting...");

    WiFi.reconnect();

    delay(5000);

    return;
  }

  // -------------------------
  // Send every 2 seconds
  // -------------------------
  if (millis() - lastSend >= SEND_INTERVAL) {

    lastSend = millis();

    sendDummyData();
  }
}


void sendDummyData() {

  // =========================================
  // Generate dynamic dummy sensor values
  // =========================================

  // Vibration intensity: 0 - 100
  int vibrationIntensity = random(0, 101);

  // Motion: 0 or 1
  int motion = random(0, 2);

  // Accelerometer: roughly -2 to +2 g
  float accelX = random(-200, 201) / 100.0;
  float accelY = random(-200, 201) / 100.0;
  float accelZ = random(-200, 201) / 100.0;

  // Gyroscope: roughly -250 to +250 dps
  float gyroX = random(-25000, 25001) / 100.0;
  float gyroY = random(-25000, 25001) / 100.0;
  float gyroZ = random(-25000, 25001) / 100.0;

  // Temperature: 20.0 - 40.0 °C
  float temperature = random(200, 401) / 10.0;

  // Humidity: 30.0 - 90.0 %
  float humidity = random(300, 901) / 10.0;

  // Power cut: 0 or 1
  int powerCut = random(0, 2);

  // CCTV cut: 0 or 1
  int cctvCut = random(0, 2);


  // =========================================
  // Get current timestamp
  // =========================================

  struct tm timeinfo;

  if (!getLocalTime(&timeinfo)) {

    Serial.println("Failed to get time");

    return;
  }

  char timestamp[25];

  strftime(
    timestamp,
    sizeof(timestamp),
    "%Y:%m:%d, %H:%M:%S",
    &timeinfo
  );


  // =========================================
  // Get MAC address
  // =========================================

  String mac = WiFi.macAddress();


  // =========================================
  // Create JSON
  // =========================================

  String payload = "{";

  payload += "\"timestamp\":\"";
  payload += timestamp;
  payload += "\",";

  payload += "\"device_mac\":\"";
  payload += mac;
  payload += "\",";

  payload += "\"vibration_intensity\":";
  payload += vibrationIntensity;
  payload += ",";

  payload += "\"motion\":";
  payload += motion;
  payload += ",";

  payload += "\"accel_x\":";
  payload += String(accelX, 2);
  payload += ",";

  payload += "\"accel_y\":";
  payload += String(accelY, 2);
  payload += ",";

  payload += "\"accel_z\":";
  payload += String(accelZ, 2);
  payload += ",";

  payload += "\"gyro_x\":";
  payload += String(gyroX, 2);
  payload += ",";

  payload += "\"gyro_y\":";
  payload += String(gyroY, 2);
  payload += ",";

  payload += "\"gyro_z\":";
  payload += String(gyroZ, 2);
  payload += ",";

  payload += "\"temperature\":";
  payload += String(temperature, 1);
  payload += ",";

  payload += "\"humidity\":";
  payload += String(humidity, 1);
  payload += ",";

  payload += "\"power_cut\":";
  payload += powerCut;
  payload += ",";

  payload += "\"cctv_cut\":";
  payload += cctvCut;

  payload += "}";


  // =========================================
  // Send to ThingsBoard
  // =========================================

  HTTPClient http;

  http.begin(TB_URL);

  http.addHeader(
    "Content-Type",
    "application/json"
  );

  Serial.println();
  Serial.println("=================================");
  Serial.println("Sending telemetry:");
  Serial.println(payload);

  int httpCode = http.POST(payload);

  Serial.print("HTTP response: ");
  Serial.println(httpCode);

  if (httpCode > 0) {

    String response = http.getString();

    Serial.print("Server response: ");
    Serial.println(response);

  } else {

    Serial.print("HTTP error: ");
    Serial.println(http.errorToString(httpCode));
  }

  http.end();
}