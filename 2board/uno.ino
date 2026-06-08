// Arduino Uno: 3 Water Pumps Control

const int pump1 = 2;
const int pump2 = 3;
const int pump3 = 4;

// Track states (false = off, true = on)
bool state1 = false;
bool state2 = false;
bool state3 = false;

void setup() {
  Serial.begin(9600);
  
  pinMode(pump1, OUTPUT);
  pinMode(pump2, OUTPUT);
  pinMode(pump3, OUTPUT);
  
  // Start with pumps off (Assuming active-high relay, change to HIGH if active-low)
  digitalWrite(pump1, LOW);
  digitalWrite(pump2, LOW);
  digitalWrite(pump3, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    if (cmd == '1') {
      state1 = !state1;
      digitalWrite(pump1, state1 ? HIGH : LOW);
    } else if (cmd == '2') {
      state2 = !state2;
      digitalWrite(pump2, state2 ? HIGH : LOW);
    } else if (cmd == '3') {
      state3 = !state3;
      digitalWrite(pump3, state3 ? HIGH : LOW);
    }
  }
}
