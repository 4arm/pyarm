// Arduino Mega: Load Cells, LEDs, Buzzer, DHT11, E-Stop
#include "HX711.h"
#include "DHT.h"

// DHT11 Setup
#define DHTPIN 2
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// HX711 Load Cell Pins (DT, SCK)
HX711 scale1;
HX711 scale2;
HX711 scale3;
const int LC1_DT = 3, LC1_SCK = 4;
const int LC2_DT = 5, LC2_SCK = 6;
const int LC3_DT = 7, LC3_SCK = 8;

// Actuators
const int LED_R = 9;
const int LED_Y = 10;
const int LED_G = 11;
const int BUZZER = 12;

// Emergency Stop Button
const int ESTOP_PIN = 13;
bool estop_active = false;

unsigned long lastSend = 0;

void setup() {
  Serial.begin(9600);
  
  dht.begin();
  
  scale1.begin(LC1_DT, LC1_SCK);
  scale2.begin(LC2_DT, LC2_SCK);
  scale3.begin(LC3_DT, LC3_SCK);
  
  // TODO: Add your scale.set_scale(calibration_factor) here if calibrated
  scale1.set_scale(); scale1.tare();
  scale2.set_scale(); scale2.tare();
  scale3.set_scale(); scale3.tare();

  pinMode(LED_R, OUTPUT);
  pinMode(LED_Y, OUTPUT);
  pinMode(LED_G, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  
  // Using INPUT_PULLUP: Button connects pin to GND when pressed
  pinMode(ESTOP_PIN, INPUT_PULLUP); 
}

void loop() {
  // 1. Check Emergency Stop Button immediately
  if (digitalRead(ESTOP_PIN) == LOW) { // Button pressed
    if (!estop_active) {
      estop_active = true;
      Serial.println("ESTOP:PRESSED");
      // Safety shutdown
      digitalWrite(LED_R, HIGH);
      digitalWrite(LED_Y, LOW);
      digitalWrite(LED_G, LOW);
      digitalWrite(BUZZER, HIGH);
    }
  }

  // 2. Handle Incoming Serial Commands from Python
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "reset") {
      estop_active = false;
      digitalWrite(LED_R, LOW);
      digitalWrite(LED_Y, LOW);
      digitalWrite(LED_G, LOW);
      digitalWrite(BUZZER, LOW);
      Serial.println("ESTOP:RESET");
    } 
    else if (!estop_active) { // Only process commands if E-stop isn't active
      if (cmd == "r") digitalWrite(LED_R, !digitalRead(LED_R));
      if (cmd == "y") digitalWrite(LED_Y, !digitalRead(LED_Y));
      if (cmd == "g") digitalWrite(LED_G, !digitalRead(LED_G));
      if (cmd == "b") digitalWrite(BUZZER, !digitalRead(BUZZER));
    }
  }

  // 3. Periodically send sensor data to Python (every 2 seconds)
  if (millis() - lastSend > 2000) {
    lastSend = millis();
    
    long w1 = scale1.get_units(5);
    long w2 = scale2.get_units(5);
    long w3 = scale3.get_units(5);
    
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    // Format data as a clean CSV string for Python to parse
    Serial.print("DATA,");
    Serial.print(w1); Serial.print(",");
    Serial.print(w2); Serial.print(",");
    Serial.print(w3); Serial.print(",");
    Serial.print(t); Serial.print(",");
    Serial.println(h);
  }
}
