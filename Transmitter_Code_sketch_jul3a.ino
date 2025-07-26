#include <SPI.h>
#include <LoRa.h>
#include <TinyGPS++.h>
#include <HardwareSerial.h>
#include <Wire.h>
#include <Adafruit_BNO08x.h>

// ==== LoRa Pins ====
#define NSS 4
#define RST 5
#define DIO0 2

// ==== GPS Pins ====
#define RX_GPS 16
#define TX_GPS 17
static const uint32_t GPSBaud = 9600;
HardwareSerial GPS_Serial(1);
TinyGPSPlus gps;

// ==== FSR ====
#define FSR_PIN 34
int fsrThreshold = 4080;
bool stepDetected = false;
unsigned long stepCount = 0;

// ==== BNO08x ====
Adafruit_BNO08x bno08x(BNO08X_RESET);
sh2_SensorValue_t sensorValue;

// ==== Auth ====
const String authKey = "KEY123";

void setup() {
  Serial.begin(115200);
  GPS_Serial.begin(GPSBaud, SERIAL_8N1, RX_GPS, TX_GPS);
  pinMode(FSR_PIN, INPUT);

  // LoRa setup
  LoRa.setPins(NSS, RST, DIO0);
  while (!LoRa.begin(433E6)) {
    Serial.print(".");
    delay(500);
  }
  LoRa.setSyncWord(0xD3);
  Serial.println(" LoRa Initialized");

  // BNO08x setup
  if (!bno08x.begin_I2C()) {
    Serial.println("❌ BNO08x not found");
    while (1);
  }
  bno08x.enableReport(SH2_LINEAR_ACCELERATION);
}

void loop() {
  // ===== GPS Read =====
  while (GPS_Serial.available() > 0)
    gps.encode(GPS_Serial.read());

  // ===== Step Detection via FSR =====
  int fsrValue = analogRead(FSR_PIN);
  if (fsrValue > fsrThreshold && !stepDetected) {
    stepDetected = true;
    stepCount++;
  } else if (fsrValue < fsrThreshold - 200) {
    stepDetected = false;
  }

  // ===== BNO08x Read =====
  float ax = 0, ay = 0, az = 0;
  if (bno08x.getSensorEvent(&sensorValue)) {
    if (sensorValue.sensorId == SH2_LINEAR_ACCELERATION) {
      ax = sensorValue.un.linearAcceleration.x;
      ay = sensorValue.un.linearAcceleration.y;
      az = sensorValue.un.linearAcceleration.z;
    }
  }

  // ===== Send if GPS updated =====
  if (gps.location.isUpdated()) {
    String message = authKey + "|";
    message += String(gps.location.lat(), 6) + ",";
    message += String(gps.location.lng(), 6) + ",";
    message += String(gps.altitude.meters(), 1) + ",";
    message += String(gps.speed.kmph(), 1) + ",";
    message += String(stepCount) + ",";
    message += String(ax, 3) + "," + String(ay, 3) + "," + String(az, 3);

    LoRa.beginPacket();
    LoRa.print(message);
    LoRa.endPacket();

    Serial.println("📤 Sent: " + message);
    delay(1000);
  }
}
