import serial
import time
import paho.mqtt.client as mqtt

# --- CONFIGURATION ---
# Change these ports to match your system's detected ports
COM_UNO = 'COM3'     
COM_MEGA = 'COM4'    
BAUD_RATE = 9600

MQTT_BROKER = "robot.thedilution.my"
MQTT_USER = "Easeham"
MQTT_PASS = "Muhdizham2003@"
MQTT_TOPIC = "sensors/loadcell/control"

# --- INITIALIZE SERIAL CONNECTIONS ---
try:
    ser_uno = serial.Serial(COM_UNO, BAUD_RATE, timeout=1)
    print(f"Connected to Uno on {COM_UNO}")
except Exception as e:
    print(f"Failed to connect to Uno: {e}")
    ser_uno = None

try:
    ser_mega = serial.Serial(COM_MEGA, BAUD_RATE, timeout=1)
    print(f"Connected to Mega on {COM_MEGA}")
except Exception as e:
    print(f"Failed to connect to Mega: {e}")
    ser_mega = None

time.sleep(2) # Allow Arduinos time to reset after plug-in

# --- MQTT CALLBACKS ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected successfully to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8').strip()
    print(f"Received MQTT command: [{payload}] on topic {msg.topic}")

    # Route logic based on commands
    if payload in ['1', '2', '3']:
        if ser_uno and ser_uno.is_open:
            ser_uno.write(payload.encode())
            print(f"Forwarded '{payload}' to Uno (Pumps)")
        else:
            print("Uno serial connection is unavailable.")
            
    elif payload in ['r', 'y', 'g', 'b', 'reset']:
        if ser_mega and ser_mega.is_open:
            # Send with newline character as Mega expects readStringUntil('\n')
            ser_mega.write(f"{payload}\n".encode())
            print(f"Forwarded '{payload}' to Mega (Actuators)")
        else:
            print("Mega serial connection is unavailable.")
    else:
        print("Unknown command received.")

# --- MAIN RUNTIME ---
client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, 1883, 60)
except Exception as e:
    print(f"Could not connect to MQTT broker: {e}")
    exit(1)

# Start background network thread for MQTT
client.loop_start()

print("System running. Reading data from Mega and waiting for MQTT messages...")

try:
    while True:
        # Read sensor incoming logs from Arduino Mega
        if ser_mega and ser_mega.in_central > 0:
            try:
                line = ser_mega.readline().decode('utf-8').strip()
                if line:
                    if line.startswith("DATA"):
                        # Structure: DATA,w1,w2,w3,temp,hum
                        parts = line.split(',')
                        print(f"[MEGA SENSORS] LoadCells: {parts[1]}, {parts[2]}, {parts[3]} | Temp: {parts[4]}°C | Hum: {parts[5]}%")
                    elif line.startswith("ESTOP"):
                        print(f"[ALERT] {line}")
            except Exception as e:
                print(f"Error reading from Mega: {e}")
                
        time.sleep(0.1) # Prevent CPU hogging

except KeyboardInterrupt:
    print("\nDisconnecting and exiting application...")
finally:
    if ser_uno: ser_uno.close()
    if ser_mega: ser_mega.close()
    client.loop_stop()
    client.disconnect()
