// Formula
#include "HX711.h"
#include "DHT.h"

// --- Pin Map (MAIN REGISTRY) ---
const int LED_GREEN = 22;
const int LED_YELLOW = 24;
const int LED_RED = 26;
const int BUZZER = 28;

const int PUMP1 = 30;
const int PUMP2 = 32;
const int PUMP3 = 34;

const int DHTPIN = 36;

const int LC1_DT = 40; const int LC1_SCK = 41;
const int LC2_DT = 42; const int LC2_SCK = 43;
const int LC3_DT = 44; const int LC3_SCK = 45;

const int EMERGENCY_BUTTON = 18; // Interrupt Pin

// --- Objects & States ---
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);
HX711 scale1, scale2, scale3;

volatile bool emergencyActive = false;
bool p1State = false, p2State = false, p3State = false;
bool isAutomatedTask = false;

// Interrupt Service Routine
void triggerEmergency() {
  emergencyActive = true;
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  // Pin Modes
  pinMode(LED_GREEN, OUTPUT); pinMode(LED_YELLOW, OUTPUT); 
  pinMode(LED_RED, OUTPUT);   pinMode(BUZZER, OUTPUT);
  pinMode(PUMP1, OUTPUT);      pinMode(PUMP2, OUTPUT); 
  pinMode(PUMP3, OUTPUT);
  
  pinMode(EMERGENCY_BUTTON, INPUT_PULLUP);

  // Initial State: All OFF (Active Low: HIGH = OFF)
  updateHardware();

  // Load Cell Init
  scale1.begin(LC1_DT, LC1_SCK);
  scale2.begin(LC2_DT, LC2_SCK);
  scale3.begin(LC3_DT, LC3_SCK);

  // Calibration and Taring
  scale1.set_scale(2280.f); scale1.tare();
  scale2.set_scale(2280.f); scale2.tare();
  scale3.set_scale(2280.f); scale3.tare();

  // Enable Emergency Stop
  attachInterrupt(digitalPinToInterrupt(EMERGENCY_BUTTON), triggerEmergency, FALLING);

  Serial.println("SYSTEM READY");
}

void loop() {
  // --- EMERGENCY CHECK ---
  if (emergencyActive) {
    handleEmergencyState();
    return;
  }

  // --- 1. SERIAL COMMAND PROCESSING ---
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    // Check if it's a Formula (e.g., A10B5C20)
    if (input.startsWith("A")) {
      handleFormula(input);
    } 
    // Check if it's a single character toggle or reset
    else if (input.length() == 1) {
      char key = input[0];
      if (key == '1') p1State = !p1State;
      if (key == '2') p2State = !p2State;
      if (key == '3') p3State = !p3State;
      if (key == 'r') {
        scale1.tare(); scale2.tare(); scale3.tare();
        Serial.println("SYSTEM RESET");
      }
      updateHardware();
    }
  }

  // --- 2. SENSOR DATA STREAMING ---
  // We use scale1 (LC1) as the primary weight check for dispensing
  float w1 = scale1.get_units(1); 
  float w2 = scale2.get_units(1);
  float w3 = scale3.get_units(1);
  float temp = dht.readTemperature();

  // Python Regex expects this format
  Serial.print("LC1: "); Serial.print(w1, 2); Serial.print("kg | ");
  Serial.print("LC2: "); Serial.print(w2, 2); Serial.print("kg | ");
  Serial.print("LC3: "); Serial.print(w3, 2); Serial.print("kg | ");
  Serial.print("Temp: "); Serial.print(temp); Serial.print("C | ");
  Serial.print("Pumps: "); Serial.print(p1State); Serial.print(p2State); Serial.println(p3State);

  // --- 3. TOWER LIGHT LOGIC ---
  if (p1State || p2State || p3State || isAutomatedTask) {
    digitalWrite(LED_GREEN, LOW);
    digitalWrite(LED_YELLOW, HIGH); // Processing
  } else {
    digitalWrite(LED_GREEN, HIGH);  // Ready
    digitalWrite(LED_YELLOW, LOW);
  }

  delay(100); 
}

// --- AUTOMATED FORMULA LOGIC ---
void handleFormula(String cmd) {
  // Safety: Check if container is on LC1 (> 50g)
  if (scale1.get_units(5) < 0.05) {
    Serial.println("STATUS: ERROR_NO_CONTAINER");
    return;
  }

  isAutomatedTask = true;
  Serial.println("STATUS: DISPENSING_START");

  // Parse A10B20C30
  int targetA = cmd.substring(cmd.indexOf('A') + 1, cmd.indexOf('B')).toInt();
  int targetB = cmd.substring(cmd.indexOf('B') + 1, cmd.indexOf('C')).toInt();
  int targetC = cmd.substring(cmd.indexOf('C') + 1).toInt();

  // Dispense sequentially using LC1 as the master scale
  dispense(PUMP1, targetA);
  dispense(PUMP2, targetB);
  dispense(PUMP3, targetC);

  isAutomatedTask = false;
  p1State = p2State = p3State = false;
  updateHardware();
  Serial.println("STATUS: FINISHED");
}

void dispense(int pumpPin, int ml) {
  if (ml <= 0 || emergencyActive) return;

  float startWeight = scale1.get_units(5);
  float targetWeight = startWeight + (ml / 1000.0); // 1ml ≈ 0.001kg

  digitalWrite(pumpPin, LOW); // ON
  while (scale1.get_units(1) < targetWeight) {
    if (emergencyActive) break; // Break if button pressed
    delay(10);
  }
  digitalWrite(pumpPin, HIGH); // OFF
  delay(500); // Settle
}

// --- HELPER FUNCTIONS ---

void updateHardware() {
  digitalWrite(PUMP1, p1State ? LOW : HIGH);
  digitalWrite(PUMP2, p2State ? LOW : HIGH);
  digitalWrite(PUMP3, p3State ? LOW : HIGH);
}

void handleEmergencyState() {
  p1State = p2State = p3State = isAutomatedTask = false;
  updateHardware();
  
  digitalWrite(LED_RED, HIGH);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_YELLOW, LOW);
  tone(BUZZER, 2000);

  Serial.println("!!! EMERGENCY STOP ACTIVE !!! Type 'r' to reset.");
  
  while (emergencyActive) {
    if (Serial.available() > 0) {
      if (Serial.read() == 'r') {
        emergencyActive = false;
        noTone(BUZZER);
        digitalWrite(LED_RED, LOW);
        Serial.println("SYSTEM RESET");
      }
    }
  }
}
