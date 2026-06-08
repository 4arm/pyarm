import serial
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import json
import re
import time
import datetime
import threading
from queue import Queue

from wisepaasdatahubedgesdk.EdgeAgent import EdgeAgent
import wisepaasdatahubedgesdk.Common.Constants as constant
from wisepaasdatahubedgesdk.Model.Edge import (
    EdgeAgentOptions, 
    DCCSOptions, 
    EdgeData, 
    EdgeTag, 
    EdgeConfig, 
    DeviceConfig, 
    AnalogTagConfig, 
    TextTagConfig
)

# =========================================================
# ===================== CONFIGURATION =====================
# =========================================================

SERIAL_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 115200
ser = None

MQTT_BROKER = "robot.thedilution.my"
MQTT_PORT = 1883
MQTT_USER = "Easeham"
MQTT_PASS = "Muhdizham2003@"

DATA_TOPIC = "sensors/loadcell/data"
CONTROL_TOPIC = "sensors/loadcell/control"
CLIENT_ID = "python_serial_bridge_kktm"

DEVICE_NAME = 'Device1'
WISE_NODE_ID = '9a52456d-04bf-4905-bea0-557c74531bf8'
WISE_DCCS_URL = 'https://api-dccs-ensaas.education.wise-paas.com/'
WISE_CREDENTIAL_KEY = 'f497ae3affd76a250448d707z6da7z6'

is_config_uploaded = False
data_queue = Queue()

# =========================================================
# =============== WISE-PAAS AGENT LOGIC ===================
# =========================================================

_edgeAgent = None

def on_wise_connected(edgeAgent, isConnected):
    global is_config_uploaded
    print("✅ Connected to Wise-PaaS DataHub!")
    
    if not is_config_uploaded:
        config = __generateWiseConfig()
        edgeAgent.uploadConfig(action=constant.ActionType['Update'], edgeConfig=config)
        print("🚀 Wise-PaaS Device Configuration synchronized.")
        is_config_uploaded = True

def on_wise_disconnected(edgeAgent, isDisconnected):
    print("⚠️ Disconnected from Wise-PaaS DataHub.")

def edgeAgent_on_message(agent, messageReceivedEventArgs):
    pass

def __generateWiseConfig():
    config = EdgeConfig()
    deviceConfig = DeviceConfig(
        id=DEVICE_NAME, name=DEVICE_NAME, description='Robot Arm Telemetry', deviceType='SmartGate', retentionPolicyName=''
    )
    
    analog_tags = ['LC1', 'LC2', 'LC3', 'Temperature']
    for tag_name in analog_tags:
        deviceConfig.analogTagList.append(
            AnalogTagConfig(
                name=tag_name, description=tag_name, readOnly=False, arraySize=0,
                spanHigh=1000, spanLow=-100, engineerUnit='kg' if 'LC' in tag_name else 'C',
                integerDisplayFormat=4, fractionDisplayFormat=2
            )
        )

    deviceConfig.textTagList.append(TextTagConfig(name='PumpsStatus', description='Pump Output states', readOnly=False, arraySize=0))
    deviceConfig.textTagList.append(TextTagConfig(name='SystemEvent', description='Operational Status logs', readOnly=False, arraySize=0))

    config.node.deviceList.append(deviceConfig)
    return config

# =========================================================
# ================= CLOUD BATCH WORKER ====================
# =========================================================

def cloud_dispatcher_thread():
    """Consolidates fast queues into a high-speed real-time batch array."""
    global _edgeAgent
    print("🧠 Real-time Cloud Batch Engine Engine Active.")
    
    while True:
        batch_items = []
        # Gather all items accumulated inside the 100ms window
        while not data_queue.empty():
            batch_items.append(data_queue.get())
            if len(batch_items) >= 20:  # Cap the batch size per cycle
                break
                
        if batch_items:
            for item in batch_items:
                edgeData = EdgeData()
                # Maintain precise time tracking for accurate graphs
                edgeData.timestamp = item['ts']
                
                if item['type'] == 'EVENT':
                    edgeData.tagList.append(EdgeTag(DEVICE_NAME, 'SystemEvent', item['value']))
                else:
                    p = item['data']
                    edgeData.tagList.append(EdgeTag(DEVICE_NAME, 'LC1', p[0]))
                    edgeData.tagList.append(EdgeTag(DEVICE_NAME, 'LC2', p[1]))
                    edgeData.tagList.append(EdgeTag(DEVICE_NAME, 'LC3', p[2]))
                    edgeData.tagList.append(EdgeTag(DEVICE_NAME, 'Temperature', p[3]))
                    edgeData.tagList.append(EdgeTag(DEVICE_NAME, 'PumpsStatus', p[4]))
                    edgeData.tagList.append(EdgeTag(DEVICE_NAME, 'SystemEvent', 'OPERATIONAL'))
                
                try:
                    _edgeAgent.sendData(edgeData)
                except Exception as e:
                    print(f"⚠️ Batch dispatch drop: {e}")
                    
        # 100ms collection window = Stable, ultra-fast 10Hz stream
        time.sleep(0.1)

# =========================================================
# =============== MQTT LOCAL CONTROL LOGIC ================
# =========================================================

def on_mqtt_message(client, userdata, msg):
    try:
        command = msg.payload.decode('utf-8').strip().lower()
        if command in ['1', '2', '3', 'r'] and ser and ser.is_open:
            ser.write(command.encode())
            print(f"➡️ Command forwarded to Arduino: {command}")
    except Exception as e:
        print(f"❌ Local MQTT Error: {e}")

def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(CONTROL_TOPIC)

# =========================================================
# ================= SERIAL CONN MANAGER ===================
# =========================================================

def connect_serial():
    global ser
    while True:
        try:
            print(f"🔌 Initializing serial connection on {SERIAL_PORT}...")
            # Set a low serial timeout to prevent the main thread from blocking
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.005)
            time.sleep(2) 
            ser.reset_input_buffer()
            print("✅ Serial communications active.")
            return True
        except Exception as e:
            print(f"❌ Serial failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# =========================================================
# ================== RUNTIME INITIALIZER ==================
# =========================================================

edgeAgentOptions = EdgeAgentOptions(nodeId=WISE_NODE_ID)
edgeAgentOptions.connectType = constant.ConnectType['DCCS']
edgeAgentOptions.DCCS = DCCSOptions(apiUrl=WISE_DCCS_URL, credentialKey=WISE_CREDENTIAL_KEY)

_edgeAgent = EdgeAgent(edgeAgentOptions)
_edgeAgent.on_connected = on_wise_connected
_edgeAgent.on_disconnected = on_wise_disconnected
_edgeAgent.on_message = edgeAgent_on_message
_edgeAgent.connect()

# Set keepalive to 15 seconds so the client quickly catches and fixes network drops
client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_mqtt_connect
client.on_message = on_mqtt_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=15)
    client.loop_start() 
except Exception as e:
    print(f"❌ MQTT Initialization Fault: {e}")
    exit()

connect_serial()

# Start the background batch processing thread
dispatcher = threading.Thread(target=cloud_dispatcher_thread, daemon=True)
dispatcher.start()

compiled_pattern = re.compile(r"LC1:\s*([\d\.-]+)kg\s*\|\s*LC2:\s*([\d\.-]+)kg\s*\|\s*LC3:\s*([\d\.-]+)kg\s*\|\s*Temp:\s*([\d\.-]+)C\s*\|\s*Pumps:\s*(\d+)")

print("📊 High-frequency real-time pipeline active...")

# =========================================================
# ==================== MAIN EXEC LOOP =====================
# =========================================================
try:
    while True:
        try:
            if ser and ser.is_open:
                # Instantly drop any backlog larger than 2 complete output lines
                if ser.in_waiting > 150:
                    ser.reset_input_buffer()
                
                raw_data = ser.readline()
                if not raw_data:
                    continue
                
                line = raw_data.decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                now_ts = datetime.datetime.now(datetime.timezone.utc)

                if "EMERGENCY STOP ACTIVE" in line:
                    print("🚨 ALERT: Emergency Active!")
                    data_queue.put({'type': 'EVENT', 'value': 'EMERGENCY_STOP', 'ts': now_ts})
                    client.publish(DATA_TOPIC, json.dumps({"status": "EMERGENCY_STOP", "timestamp": time.time()}))
                    continue 
                
                if "SYSTEM RESET" in line:
                    print("🔄 System Reset Detected.")
                    data_queue.put({'type': 'EVENT', 'value': 'READY', 'ts': now_ts})
                    client.publish(DATA_TOPIC, json.dumps({"status": "READY", "timestamp": time.time()}))
                    continue

                match = compiled_pattern.search(line)
                if match:
                    lc1 = float(match.group(1))
                    lc2 = float(match.group(2))
                    lc3 = float(match.group(3))
                    temp = float(match.group(4))
                    pumps = match.group(5)

                    # Add parsed data to the thread queue for batch processing
                    data_queue.put({
                        'type': 'DATA',
                        'data': (lc1, lc2, lc3, temp, pumps),
                        'ts': now_ts
                    })

                    # Keep your local MQTT topics updated instantly
                    payload = {
                        "status": "OPERATIONAL", "lc1_kg": lc1, "lc2_kg": lc2, 
                        "lc3_kg": lc3, "temp_c": temp, "pumps_status": pumps, "timestamp": time.time()
                    }
                    client.publish(DATA_TOPIC, json.dumps(payload), qos=0)
            else:
                connect_serial()

        except (serial.SerialException, OSError):
            if ser:
                try: ser.close()
                except Exception: pass
            connect_serial()
        except Exception as e:
            print(f"❌ Processing anomaly: {e}")
            
        # Give the CPU a tiny 1ms break to keep thread operations balanced
        time.sleep(0.001)
            
except KeyboardInterrupt:
    print("\n👋 Deactivating real-time agent...")
finally:
    if ser and ser.is_open:
        ser.close()
    client.loop_stop()
    client.disconnect()
    if _edgeAgent:
        _edgeAgent.disconnect()
