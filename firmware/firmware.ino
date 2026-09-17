

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <time.h>
#include <sys/time.h>

// ============================================================
// WIFI / THINGSBOARD
// ============================================================

const char* WIFI_SSID = "Phone";
const char* WIFI_PASSWORD = "password?";

const char* THINGSBOARD_URL =
  "http://100.82.190.70:8080/api/v1/doc8zepo10wesn88qnid/telemetry";

// ============================================================
// PINS
// ============================================================

#define VIBRATION_PIN 27
#define PIR_PIN       25
#define RED_LED_PIN   26
#define LED_PIN       33

#define POWERCUT_PIN  34
#define CCTV_PIN      35

#define MPU_SDA       21
#define MPU_SCL       22


// ============================================================
// MPU6050
// ============================================================

#define MPU6050_ADDR 0x68

TwoWire MPUWire = TwoWire(0);

const float ACCEL_SCALE = 16384.0;
const float GYRO_SCALE  = 131.0;


// ============================================================
// SENSOR COLLECTION
// ============================================================

const unsigned long SCAN_TIME = 1000;


// ============================================================
// VIBRATION
// ============================================================

// Number of HIGH/LOW transitions during the current 1-second scan.
volatile unsigned long vibrationTransitions = 0;

int previousVibrationState = LOW;


// ============================================================
// BUFFER SYSTEM
// ============================================================

#define BUFFER_COUNT 2

enum BufferState
{
  BUFFER_FREE,
  BUFFER_COLLECTING,
  BUFFER_READY,
  BUFFER_SENDING
};

struct SensorBuffer
{
  BufferState state;

  float accel_x;
  float accel_y;
  float accel_z;

  float gyro_x;
  float gyro_y;
  float gyro_z;

  int motion;
  int cctv_cut;
  int powercut;

  unsigned long hardness;

  char device_mac[18];
  char scan_timestamp[32];

  unsigned long startMillis;
  unsigned long endMillis;
};

SensorBuffer buffers[BUFFER_COUNT];

int collectingBuffer = -1;


// ============================================================
// MUTEX
// ============================================================

SemaphoreHandle_t bufferMutex;


// ============================================================
// DEVICE MAC
// ============================================================

String deviceMAC;


// ============================================================
// MPU6050 LOW LEVEL FUNCTIONS
// ============================================================

void mpuWriteByte(uint8_t reg, uint8_t value)
{
  MPUWire.beginTransmission(MPU6050_ADDR);
  MPUWire.write(reg);
  MPUWire.write(value);
  MPUWire.endTransmission();
}


bool mpuReadBytes(uint8_t reg, uint8_t* data, uint8_t length)
{
  MPUWire.beginTransmission(MPU6050_ADDR);
  MPUWire.write(reg);

  if (MPUWire.endTransmission(false) != 0)
  {
    return false;
  }

  uint8_t received =
    MPUWire.requestFrom(MPU6050_ADDR, length, true);

  if (received != length)
  {
    return false;
  }

  for (uint8_t i = 0; i < length; i++)
  {
    data[i] = MPUWire.read();
  }

  return true;
}


bool readMPU6050(
  float &ax,
  float &ay,
  float &az,
  float &gx,
  float &gy,
  float &gz
)
{
  uint8_t data[14];

  if (!mpuReadBytes(0x3B, data, 14))
  {
    return false;
  }

  int16_t rawAx =
    ((int16_t)data[0] << 8) | data[1];

  int16_t rawAy =
    ((int16_t)data[2] << 8) | data[3];

  int16_t rawAz =
    ((int16_t)data[4] << 8) | data[5];

  int16_t rawGx =
    ((int16_t)data[8] << 8) | data[9];

  int16_t rawGy =
    ((int16_t)data[10] << 8) | data[11];

  int16_t rawGz =
    ((int16_t)data[12] << 8) | data[13];


  ax = rawAx / ACCEL_SCALE;
  ay = rawAy / ACCEL_SCALE;
  az = rawAz / ACCEL_SCALE;

  gx = rawGx / GYRO_SCALE;
  gy = rawGy / GYRO_SCALE;
  gz = rawGz / GYRO_SCALE;

  return true;
}


// ============================================================
// MPU6050 SETUP
// ============================================================

bool setupMPU6050()
{
  MPUWire.begin(MPU_SDA, MPU_SCL, 400000);

  delay(50);

  // Wake MPU6050
  mpuWriteByte(0x6B, 0x00);

  // DLPF
  mpuWriteByte(0x1A, 0x03);

  // Sample rate divider
  mpuWriteByte(0x19, 0x04);

  // Accelerometer ±2g
  mpuWriteByte(0x1C, 0x00);

  // Gyroscope ±250 dps
  mpuWriteByte(0x1B, 0x00);

  delay(50);

  uint8_t whoAmI;

  if (!mpuReadBytes(0x75, &whoAmI, 1))
  {
    Serial.println("MPU6050 not responding");
    return false;
  }

  Serial.print("MPU6050 WHO_AM_I: 0x");
  Serial.println(whoAmI, HEX);

  return true;
}


// ============================================================
// TIME
// ============================================================

void setupTime()
{
  configTime(
    0,
    0,
    "pool.ntp.org",
    "time.nist.gov",
    "time.google.com"
  );

  setenv("TZ", "Asia/Dhaka", 1);
  tzset();

  Serial.println("Waiting for NTP...");

  struct tm timeinfo;

  for (int i = 0; i < 30; i++)
  {
    if (getLocalTime(&timeinfo, 500))
    {
      Serial.println("Time synchronized");
      return;
    }

    delay(100);
  }

  Serial.println("NTP synchronization failed");
}


// ============================================================
// TIMESTAMP
// ============================================================

void getTimestamp(char* output, size_t size)
{
  struct timeval tv;

  gettimeofday(&tv, NULL);

  time_t now = tv.tv_sec;

  struct tm timeinfo;

  localtime_r(&now, &timeinfo);

  int milliseconds =
    tv.tv_usec / 1000;

  snprintf(
    output,
    size,
    "%04d-%02d-%02d %02d:%02d:%02d.%03d",

    timeinfo.tm_year + 1900,
    timeinfo.tm_mon + 1,
    timeinfo.tm_mday,

    timeinfo.tm_hour,
    timeinfo.tm_min,
    timeinfo.tm_sec,

    milliseconds
  );
}


// ============================================================
// WIFI
// ============================================================

void connectWiFi()
{
  Serial.println();
  Serial.println("Connecting WiFi...");

  WiFi.mode(WIFI_STA);

  WiFi.disconnect(true);
  delay(100);

  WiFi.begin(
    WIFI_SSID,
    WIFI_PASSWORD
  );

  unsigned long start = millis();

  while (
    WiFi.status() != WL_CONNECTED &&
    millis() - start < 15000
  )
  {
    delay(250);

    Serial.print(".");
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED)
  {
    Serial.println("WiFi connected");

    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());

    Serial.print("Gateway: ");
    Serial.println(WiFi.gatewayIP());
  }
  else
  {
    Serial.println("WiFi connection failed");
  }
}


// ============================================================
// VIBRATION
// ============================================================

void resetVibration()
{
  vibrationTransitions = 0;

  previousVibrationState =
    digitalRead(VIBRATION_PIN);
}


void updateVibration()
{
  int currentState =
    digitalRead(VIBRATION_PIN);

  /*
     Count ONLY transitions.

     Example:

     LOW -> HIGH = 1
     HIGH -> LOW = 2
     LOW -> HIGH = 3

     This means hardness represents actual vibration
     activity instead of the number of times GPIO was sampled.
  */

  if (currentState != previousVibrationState)
  {
    vibrationTransitions++;

    previousVibrationState =
      currentState;
  }
}


// ============================================================
// BUFFER HELPERS
// ============================================================

int findFreeBuffer()
{
  for (int i = 0; i < BUFFER_COUNT; i++)
  {
    if (buffers[i].state == BUFFER_FREE)
    {
      return i;
    }
  }

  return -1;
}


int findReadyBuffer()
{
  for (int i = 0; i < BUFFER_COUNT; i++)
  {
    if (buffers[i].state == BUFFER_READY)
    {
      return i;
    }
  }

  return -1;
}


// ============================================================
// START COLLECTION
// ============================================================

// bool startCollection()
// {
//   if (xSemaphoreTake(bufferMutex, portMAX_DELAY) != pdTRUE)
//   {
//     return false;
//   }

//   int index = findFreeBuffer();

//   if (index < 0)
//   {
//     xSemaphoreGive(bufferMutex);

//     Serial.println(
//       "WARNING: No free sensor buffer"
//     );

//     return false;
//   }

//   buffers[index].state =
//     BUFFER_COLLECTING;

//   buffers[index].startMillis =
//     millis();

//   collectingBuffer = index;

//   xSemaphoreGive(bufferMutex);


//   // Reset vibration counter for this scan.
//   resetVibration();

//   return true;
// }

bool startCollection()
{
    static bool bufferWarningShown = false;

    if (xSemaphoreTake(bufferMutex, portMAX_DELAY) != pdTRUE)
    {
        return false;
    }

    int index = findFreeBuffer();

    if (index < 0)
    {
        xSemaphoreGive(bufferMutex);

        // Print only once while buffers remain unavailable
        if (!bufferWarningShown)
        {
            Serial.println(
                "WARNING: No free sensor buffer..."
            );

            bufferWarningShown = true;
        }

        return false;
    }

    // A buffer is available again
    if (bufferWarningShown)
    {
        Serial.println(
            "Sensor buffer available. Resuming collection."
        );

        bufferWarningShown = false;
    }

    buffers[index].state =
        BUFFER_COLLECTING;

    buffers[index].startMillis =
        millis();

    collectingBuffer = index;

    xSemaphoreGive(bufferMutex);

    resetVibration();

    return true;
}


// ============================================================
// FINISH COLLECTION
// ============================================================

void finishCollection()
{
  if (collectingBuffer < 0)
  {
    return;
  }

  int index =
    collectingBuffer;


  /*
     Capture the final vibration state before
     finishing the scan.
  */
  updateVibration();


  if (xSemaphoreTake(bufferMutex, portMAX_DELAY) != pdTRUE)
  {
    return;
  }


  buffers[index].hardness =
    vibrationTransitions;


  getTimestamp(
    buffers[index].scan_timestamp,
    sizeof(buffers[index].scan_timestamp)
  );


  buffers[index].endMillis =
    millis();


  buffers[index].state =
    BUFFER_READY;


  collectingBuffer = -1;


  xSemaphoreGive(bufferMutex);


  Serial.println();
  Serial.println("===== SCAN COMPLETE =====");

  Serial.print("Buffer: ");
  Serial.println(index);

  Serial.print("Hardness / vibration transitions: ");
  Serial.println(vibrationTransitions);

  Serial.println("=========================");
}


// ============================================================
// SENSOR TASK
// CORE 0
// ============================================================

void sensorTask(void* parameter)
{
  Serial.println("Sensor task started on Core 0");

  unsigned long lastSensorPrint = 0;

  while (true)
  {
    /*
       If we don't currently have a collection buffer,
       try to obtain one.
    */

    if (collectingBuffer < 0)
    {
      startCollection();
    }


    /*
       CONTINUOUS VIBRATION MONITORING

       This is intentionally called every loop.
       There is NO delay here.
    */

    updateVibration();


    /*
       Read all other sensors.

       They are sampled continuously in the same
       acquisition loop.
    */

    if (collectingBuffer >= 0)
    {
      int index =
        collectingBuffer;


      // -----------------------------
      // MPU6050
      // -----------------------------

      float ax, ay, az;
      float gx, gy, gz;

      if (
        readMPU6050(
          ax,
          ay,
          az,
          gx,
          gy,
          gz
        )
      )
      {
        buffers[index].accel_x = ax;
        buffers[index].accel_y = ay;
        buffers[index].accel_z = az;

        buffers[index].gyro_x = gx;
        buffers[index].gyro_y = gy;
        buffers[index].gyro_z = gz;
      }


      // -----------------------------
      // PIR / MOTION
      // -----------------------------

      buffers[index].motion =
        digitalRead(PIR_PIN);


      // -----------------------------
      // CCTV CUT
      // -----------------------------

      buffers[index].cctv_cut =
        digitalRead(CCTV_PIN);


      // -----------------------------
      // POWERCUT
      // -----------------------------

      buffers[index].powercut =
        digitalRead(POWERCUT_PIN);


      /*
         Check whether this 1-second scan
         has completed.
      */

      if (
        millis() -
        buffers[index].startMillis >=
        SCAN_TIME
      )
      {
        finishCollection();
      }
    }


    /*
       Small task yield.

       This is NOT a sensor delay.

       It allows FreeRTOS to schedule other
       tasks while immediately returning to
       the sensor loop.

       1 ms is small enough that GPIO27
       monitoring remains very frequent.
    */

    taskYIELD();
  }
}


// ============================================================
// CREATE JSON
// ============================================================

String createJSON(int index)
{
  String json;

  json.reserve(700);

  json += "{";

  json += "\"accel_x\":";
  json += String(buffers[index].accel_x, 4);

  json += ",\"accel_y\":";
  json += String(buffers[index].accel_y, 4);

  json += ",\"accel_z\":";
  json += String(buffers[index].accel_z, 4);

  json += ",\"gyro_x\":";
  json += String(buffers[index].gyro_x, 4);

  json += ",\"gyro_y\":";
  json += String(buffers[index].gyro_y, 4);

  json += ",\"gyro_z\":";
  json += String(buffers[index].gyro_z, 4);

  json += ",\"motion\":";
  json += String(buffers[index].motion);

  json += ",\"cctv_cut\":";
  json += String(buffers[index].cctv_cut);

  json += ",\"powercut\":";
  json += String(buffers[index].powercut);

  json += ",\"hardness\":";
  json += String(buffers[index].hardness);

  json += ",\"device_mac\":\"";
  json += String(buffers[index].device_mac);
  json += "\"";

  json += ",\"scan_timestamp\":\"";
  json += String(buffers[index].scan_timestamp);
  json += "\"";

  json += "}";

  return json;
}


// ============================================================
// SEND BUFFER
// CORE 1
// ============================================================

bool sendBuffer(int index)
{
  if (WiFi.status() != WL_CONNECTED)
  {
    Serial.println(
      "WiFi disconnected. Cannot send."
    );

    return false;
  }


  String payload =
    createJSON(index);


  Serial.println();
  Serial.println("Sending telemetry:");

  Serial.println(payload);


  HTTPClient http;

  http.setConnectTimeout(3000);
  http.setTimeout(5000);

  http.begin(THINGSBOARD_URL);

  http.addHeader(
    "Content-Type",
    "application/json"
  );


  int responseCode =
    http.POST(payload);


  Serial.print("HTTP response: ");
  Serial.println(responseCode);


  if (responseCode > 0)
  {
    String response =
      http.getString();

    Serial.print("Response: ");
    Serial.println(response);
  }
  else
  {
    Serial.print("HTTP error: ");
    Serial.println(
      http.errorToString(responseCode)
    );
  }


  http.end();


  return responseCode >= 200 &&
         responseCode < 300;
}


// ============================================================
// TRANSMISSION TASK
// CORE 1
// ============================================================

void transmissionTask(void* parameter)
{
  Serial.println(
    "Transmission task started on Core 1"
  );


  while (true)
  {
    int index = -1;


    /*
       Find a READY buffer.
    */

    if (
      xSemaphoreTake(
        bufferMutex,
        portMAX_DELAY
      ) == pdTRUE
    )
    {
      index = findReadyBuffer();

      if (index >= 0)
      {
        buffers[index].state =
          BUFFER_SENDING;
      }

      xSemaphoreGive(bufferMutex);
    }


    /*
       Nothing ready.
       Yield instead of blocking sensor acquisition.
    */

    if (index < 0)
    {
      vTaskDelay(
        pdMS_TO_TICKS(2)
      );

      continue;
    }


    /*
       Send completed buffer.

       Core 0 continues collecting sensors
       while this happens.
    */

    bool success =
      sendBuffer(index);


    /*
       ALWAYS free the buffer after transmission
       attempt.

       This is important.

       A failed HTTP request must not leave the
       buffer permanently stuck in SENDING.
    */

    if (
      xSemaphoreTake(
        bufferMutex,
        portMAX_DELAY
      ) == pdTRUE
    )
    {
      buffers[index].state =
        BUFFER_FREE;

      xSemaphoreGive(bufferMutex);
    }


    if (success)
    {
      Serial.print(
        "Buffer "
      );

      Serial.print(index);

      Serial.println(
        " transmitted successfully."
      );
    }
    else
    {
      Serial.print(
        "Buffer "
      );

      Serial.print(index);

      Serial.println(
        " transmission failed. Buffer released."
      );
    }
  }
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
  Serial.begin(115200);

  delay(500);

  Serial.println();
  Serial.println(
    "================================"
  );
  Serial.println(
    "JOINIK SENSOR NODE"
  );
  Serial.println(
    "================================"
  );


  // ==========================================================
  // GPIO
  // ==========================================================

  pinMode(
    VIBRATION_PIN,
    INPUT
  );

  pinMode(
    PIR_PIN,
    INPUT
  );

  pinMode(
    RED_LED_PIN,
    OUTPUT
  );

  pinMode(
    LED_PIN,
    OUTPUT
  );

  pinMode(
    POWERCUT_PIN,
    INPUT
  );

  pinMode(
    CCTV_PIN,
    INPUT
  );


  // ==========================================================
  // DEVICE MAC
  // ==========================================================

  // deviceMAC =
  //   WiFi.macAddress();

  uint64_t mac = ESP.getEfuseMac();

char macString[18];

snprintf(
    macString,
    sizeof(macString),
    "%02X:%02X:%02X:%02X:%02X:%02X",
    (uint8_t)(mac >> 40),
    (uint8_t)(mac >> 32),
    (uint8_t)(mac >> 24),
    (uint8_t)(mac >> 16),
    (uint8_t)(mac >> 8),
    (uint8_t)mac
);

deviceMAC = String(macString);

Serial.print("Device MAC: ");
Serial.println(deviceMAC);

  Serial.print(
    "Device MAC: "
  );

  Serial.println(
    deviceMAC
  );


  // ==========================================================
  // INITIALIZE BUFFERS
  // ==========================================================

  bufferMutex =
    xSemaphoreCreateMutex();


  for (int i = 0; i < BUFFER_COUNT; i++)
  {
    buffers[i].state =
      BUFFER_FREE;

    buffers[i].accel_x = 0;
    buffers[i].accel_y = 0;
    buffers[i].accel_z = 0;

    buffers[i].gyro_x = 0;
    buffers[i].gyro_y = 0;
    buffers[i].gyro_z = 0;

    buffers[i].motion = 0;
    buffers[i].cctv_cut = 0;
    buffers[i].powercut = 0;

    buffers[i].hardness = 0;

    strncpy(
      buffers[i].device_mac,
      deviceMAC.c_str(),
      sizeof(buffers[i].device_mac) - 1
    );

    buffers[i].device_mac[
      sizeof(buffers[i].device_mac) - 1
    ] = '\0';

    buffers[i].scan_timestamp[0] =
      '\0';
  }


  // ==========================================================
  // MPU6050
  // ==========================================================

  if (setupMPU6050())
  {
    Serial.println(
      "MPU6050 initialized"
    );
  }


  // ==========================================================
  // INITIAL VIBRATION STATE
  // ==========================================================

  previousVibrationState =
    digitalRead(VIBRATION_PIN);


  Serial.print(
    "Initial vibration state: "
  );

  Serial.println(
    previousVibrationState
  );


  // ==========================================================
  // WIFI
  // ==========================================================

  connectWiFi();


  // ==========================================================
  // TIME
  // ==========================================================

  if (WiFi.status() == WL_CONNECTED)
  {
    setupTime();
  }


  // ==========================================================
  // TASKS
  // ==========================================================

  xTaskCreatePinnedToCore(
    sensorTask,
    "SensorTask",
    8192,
    NULL,
    3,
    NULL,
    0
  );


  xTaskCreatePinnedToCore(
    transmissionTask,
    "TransmissionTask",
    8192,
    NULL,
    2,
    NULL,
    1
  );


  Serial.println();
  Serial.println(
    "System started."
  );

  Serial.println(
    "Sensor acquisition: Core 0"
  );

  Serial.println(
    "Transmission: Core 1"
  );

  Serial.println(
    "Vibration monitoring: continuous"
  );
}


// ============================================================
// LOOP
// ============================================================

void loop()
{
  /*
     Everything is handled by FreeRTOS tasks.

     Keep Arduino loop alive without doing sensor
     acquisition here.
  */

  vTaskDelay(
    pdMS_TO_TICKS(1000)
  );
}