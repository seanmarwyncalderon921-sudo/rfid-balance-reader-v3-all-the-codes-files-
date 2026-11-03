#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd27(0x27, 16, 2);
LiquidCrystal_I2C lcd3F(0x3F, 16, 2);
LiquidCrystal_I2C* activeLcd = &lcd27;

unsigned long lastDisplayActivity = 0;
bool readyScreenVisible = false;

bool initLcd() {
  byte addresses[] = {0x27, 0x3F, 0x20};

  for (byte address : addresses) {
    Wire.beginTransmission(address);
    byte error = Wire.endTransmission();

    if (error == 0) {
      if (address == 0x27) {
        activeLcd = &lcd27;
      } else if (address == 0x3F) {
        activeLcd = &lcd3F;
      } else {
        activeLcd = &lcd27;
      }

      activeLcd->init();
      activeLcd->backlight();
      return true;
    }
  }

  return false;
}

void showReadyScreen() {
  if (activeLcd == nullptr) {
    return;
  }

  readyScreenVisible = true;
  activeLcd->clear();
  activeLcd->setCursor(0, 0);
  activeLcd->print("PADUA RFID");
  activeLcd->setCursor(0, 1);
  activeLcd->print("BALANCE CHECKER");
}

void showMessage(const String &message) {
  if (activeLcd == nullptr) {
    return;
  }

  String cleanMessage = message;
  cleanMessage.replace("\r", "");
  cleanMessage.trim();

  if (cleanMessage.length() == 0) {
    return;
  }

  lastDisplayActivity = millis();
  readyScreenVisible = false;
  activeLcd->clear();

  int separator = cleanMessage.indexOf('|');
  if (separator == -1) {
    separator = cleanMessage.indexOf('\n');
  }

  if (separator != -1) {
    String line1 = cleanMessage.substring(0, separator);
    String line2 = cleanMessage.substring(separator + 1);

    activeLcd->setCursor(0, 0);
    activeLcd->print(line1.substring(0, 16));

    activeLcd->setCursor(0, 1);
    activeLcd->print(line2.substring(0, 16));
  } else {
    activeLcd->setCursor(0, 0);
    activeLcd->print(cleanMessage.substring(0, 16));
  }
}

void setup() {
  Serial.begin(9600);
  Wire.begin();

  bool found = initLcd();
  if (!found) {
    Serial.println("No LCD found on I2C bus.");
    return;
  }

  showReadyScreen();
  lastDisplayActivity = millis();
}

void loop() {
  if (Serial.available() > 0) {
    String message = Serial.readStringUntil('\n');
    if (message.length() > 0) {
      showMessage(message);
    }
  }

  if (!readyScreenVisible && millis() - lastDisplayActivity > 5000) {
    showReadyScreen();
  }
}