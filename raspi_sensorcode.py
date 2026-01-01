import serial
import time
import json

# ===========================
# FIREBASE CONFIGURATION
# ===========================
FIREBASE_URL = "https://jal-mahakal-shakti-default-rtdb.asia-southeast1.firebasedatabase.app"
FIREBASE_SECRET = "SItfk9tDQSOfISqZCUHRzJpZeQH7q2GtGnxk1OmE"
DEVICE_ID = "ESP32_TANK_001"  # Change to your device ID

# ===========================
# SERIAL PORT CONFIGURATION
# ===========================
SENSOR_PORT = '/dev/serial0'
SENSOR_BAUDRATE = 115200
EC200U_PORT = '/dev/ttyUSB0'
EC200U_BAUDRATE = 115200

# ===========================
# EC200U FUNCTIONS
# ===========================
def send_at_command(ser, command, wait_time=1, debug=False):
    """Send AT command to EC200U and return response"""
    ser.write((command + '\r\n').encode())
    time.sleep(wait_time)
    response = ser.read(ser.in_waiting or 1000).decode('utf-8', errors='ignore')
    if debug:
        print(f"CMD: {command} -> {response[:100]}")
    return response

def initialize_ec200u(ec200u_ser):
    """Initialize EC200U module and activate data connection"""
    print("🔧 Initializing EC200U...")
    
    # Basic AT test
    send_at_command(ec200u_ser, 'AT')
    
    # Deactivate any existing connection
    send_at_command(ec200u_ser, 'AT+QIDEACT=1', 2)
    
    # Configure APN (change for your carrier)
    send_at_command(ec200u_ser, 'AT+QICSGP=1,1,"airtelgprs.com","","",1', 2)
    
    # Activate PDP context
    send_at_command(ec200u_ser, 'AT+QIACT=1', 5)
    
    # Check IP address
    ip_response = send_at_command(ec200u_ser, 'AT+QIACT?', 1)
    
    if '+QIACT:' in ip_response:
        print("✅ EC200U connected to network")
        return True
    else:
        print("❌ EC200U connection failed")
        return False

def send_to_firebase_via_ec200u(ec200u_ser, device_id, distance_cm):
    """Send distance data to Firebase using EC200U"""
    try:
        print(f"📤 Attempting to send {distance_cm} cm to Firebase...")
        
        # Prepare data
        payload = {
            "distance": distance_cm,
            "timestamp": int(time.time() * 1000)
        }
        json_data = json.dumps(payload)
        
        # Firebase endpoint
        firebase_path = f"/devices/{device_id}.json?auth={FIREBASE_SECRET}"
        host = "jal-mahakal-shakti-default-rtdb.asia-southeast1.firebasedatabase.app"
        full_url = f"https://{host}{firebase_path}"
        
        print(f"   URL: {full_url[:80]}...")
        
        # Configure HTTP URL
        cmd_response = send_at_command(ec200u_ser, f'AT+QHTTPURL={len(full_url)},80', 1)
        ec200u_ser.write(full_url.encode())
        time.sleep(1)
        url_response = ec200u_ser.read(ec200u_ser.in_waiting or 1000).decode('utf-8', errors='ignore')
        
        print(f"   URL Setup: {url_response[:50]}")
        
        if 'OK' not in url_response and 'CONNECT' not in url_response:
            print(f"❌ URL setup failed")
            return False
        
        # Send PUT request with data
        print(f"   Sending data: {json_data}")
        put_response = send_at_command(ec200u_ser, f'AT+QHTTPPUT={len(json_data)},80,80', 1)
        ec200u_ser.write(json_data.encode())
        time.sleep(4)
        
        # Read response
        read_response = send_at_command(ec200u_ser, 'AT+QHTTPREAD=80', 3)
        
        print(f"   Response: {read_response[:100]}")
        
        if '200' in read_response or 'OK' in read_response:
            print(f"✅ Firebase: {distance_cm} cm sent successfully via EC200U!")
            return True
        else:
            print(f"❌ Firebase send failed")
            return False
            
    except Exception as e:
        print(f"❌ EC200U error: {str(e)}")
        return False

def is_valid_distance(distance_mm):
    """Validate sensor reading - only numbers in valid range"""
    if distance_mm is None:
        return False
    if not isinstance(distance_mm, (int, float)):
        return False
    if distance_mm < 200 or distance_mm > 4500:  # 20cm to 450cm
        return False
    return True

# ===========================
# MAIN LOOP
# ===========================
def main():
    """Read sensor and send to Firebase via EC200U"""
    print("=" * 60)
    print("🚀 Ultrasonic Sensor → EC200U → Firebase")
    print(f"📡 Device ID: {DEVICE_ID}")
    print(f"🔥 Firebase: {FIREBASE_URL}")
    print(f"📟 Sensor: {SENSOR_PORT}")
    print(f"📱 EC200U: {EC200U_PORT}")
    print("=" * 60)
    
    sensor_ser = None
    ec200u_ser = None
    
    try:
        # Open sensor serial port (EXACTLY like your working code)
        sensor_ser = serial.Serial(
            port=SENSOR_PORT,
            baudrate=SENSOR_BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        print("✅ Sensor connected")
        
        # Open EC200U serial port
        ec200u_ser = serial.Serial(
            port=EC200U_PORT,
            baudrate=EC200U_BAUDRATE,
            timeout=5
        )
        print("✅ EC200U connected")
        
        # Initialize EC200U
        if not initialize_ec200u(ec200u_ser):
            print("❌ Failed to initialize EC200U. Exiting...")
            return
        
        print("\n📡 Starting real-time monitoring...")
        print("   (Sensor readings appear below)\n")
        
        reading_count = 0
        last_distance = None  # Track last sent distance
        
        # EXACTLY LIKE YOUR WORKING SENSOR CODE
        while True:
            if sensor_ser.in_waiting >= 4:
                b0 = sensor_ser.read(1)[0]
                if b0 == 0xFF:
                    b1 = sensor_ser.read(1)[0]
                    b2 = sensor_ser.read(1)[0]
                    b3 = sensor_ser.read(1)[0]
                    checksum = (b0 + b1 + b2) & 0xFF
                    
                    if b3 == checksum:
                        distance_mm = (b1 << 8) | b2
                        distance_cm = distance_mm / 10.0
                        reading_count += 1
                        
                        print(f"📏 [{reading_count}] Distance: {distance_mm} mm ({distance_cm:.1f} cm)")
                        
                        # Send EVERY valid reading to Firebase (LIVE DATA!)
                        if is_valid_distance(distance_mm):
                            # Only send if distance changed (avoid spamming same value)
                            if last_distance is None or abs(distance_cm - last_distance) >= 0.5:
                                print(f"\n{'='*50}")
                                send_to_firebase_via_ec200u(ec200u_ser, DEVICE_ID, distance_cm)
                                print(f"{'='*50}\n")
                                last_distance = distance_cm
                        else:
                            print(f"⚠️  Invalid distance: {distance_mm} mm (not in 200-4500mm range)")
                    else:
                        print("❌ Checksum error")
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping...")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        if sensor_ser and sensor_ser.is_open:
            sensor_ser.close()
            print("✅ Sensor port closed")
        if ec200u_ser and ec200u_ser.is_open:
            ec200u_ser.close()
            print("✅ EC200U port closed")

# ===========================
# RUN PROGRAM
# ===========================
if __name__ == "__main__":
    main()
