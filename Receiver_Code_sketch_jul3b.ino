#include <SPI.h>
#include <LoRa.h>

#define NSS 4
#define RST 5
#define DIO0 2

String LoRaData;
const String authKey = "KEY123";

void setup() {
  Serial.begin(115200);
  LoRa.setPins(NSS, RST, DIO0);
  while (!LoRa.begin(433E6)) {
    Serial.print(".");
    delay(500);
  }
  LoRa.setSyncWord(0xD3);
  Serial.println("✅ LoRa Receiver Initialized");
}

void loop() {
  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    LoRaData = "";
    while (LoRa.available()) {
      LoRaData += (char)LoRa.read();
    }

    if (LoRaData.startsWith(authKey + "|")) {
      String dataOnly = LoRaData.substring(authKey.length() + 1);
      Serial.println("---------------------------");
      String labels[] = {"Latitude", "Longitude", "Altitude (m)", "Speed (km/h)", "Step Count", "Acc_X", "Acc_Y", "Acc_Z"};
      int idx = 0;
      int lastIndex = 0;
      for (int i = 0; i < dataOnly.length(); i++) {
        if (dataOnly[i] == ',' || i == dataOnly.length() - 1) {
          String value = dataOnly.substring(lastIndex, i == dataOnly.length() - 1 ? i + 1 : i);
          if (idx < 8) {
            Serial.print(labels[idx]);
            Serial.print(": ");
            Serial.println(value);
            idx++;
          }
          lastIndex = i + 1;
        }
      }
      Serial.println("---------------------------");
    } else {
      Serial.print("⚠ Ignored Packet: ");
      Serial.println(LoRaData);
    }
  }
}
