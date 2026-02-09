#!/usr/bin/env python3
"""
GAGAN NETRA - Phase 2
UAV-based Fire/Smoke Detection System with AWS Integration
Intelligent Fire Source Classification using BME688 + PMS7003
"""

import cv2
import time
import csv
import os
import serial
import smbus2
import bme680
from datetime import datetime
from ultralytics import YOLO
import boto3
import uuid
from botocore.exceptions import ClientError
from decimal import Decimal
from gps_reader import CubeOrangeGPS

# ============================================================
# AWS CONFIGURATION
# ============================================================
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
s3_client = boto3.client('s3', region_name='ap-south-1')
table = dynamodb.Table('GaganNetraIncidents')
S3_BUCKET = 'gagan-netra-evidence'

# ============================================================
# CONFIGURATION
# ============================================================
HEADLESS_MODE = False  # Set to True for UAV flight (no display)
VIDEO_DEVICE = "/dev/video42"
PMS7003_PORT = "/dev/ttyTHS1"
BME688_BUS = 7
VIDEO_SAVE_PATH = "/home/aigen/gagan_netra/flight_recordings"
RECORD_VIDEO = True
# Create the directory if it doesn't exist
if not os.path.exists(VIDEO_SAVE_PATH):
    os.makedirs(VIDEO_SAVE_PATH, exist_ok=True)
FIRE_MODEL = "ml/smoke fire detection/models/best_nano_111.engine"
HUMAN_MODEL = "ml/human detection/model/best.engine"
OBJECT_MODEL = "ml/object detection/model/best.engine"
CSV_FILE = "gagan_netra_flight_log.csv"
EVIDENCE_DIR = "evidence"
COOLDOWN = 5  # seconds between logs
FIRE_CONFIDENCE_THRESHOLD = 0.4
FIRE_PM25_THRESHOLD = 35
BASELINE_TEMPERATURE = 25.0  # Baseline for temperature rise calculation

# ============================================================
# SENSOR INITIALIZATION
# ============================================================
print("=" * 60)
print("GAGAN NETRA - PHASE 2")
print("Intelligent Fire/Smoke Detection with Sensor Fusion")
print("=" * 60)

# PMS7003 Air Quality Sensor
try:
    pms_sensor = serial.Serial(PMS7003_PORT, baudrate=9600, timeout=1)
    print("? UART: PMS7003")
except Exception as e:
    print(f"?? UART: PMS7003 failed - {e}")
    pms_sensor = None

# BME688 Gas Sensor
try:
    i2c = smbus2.SMBus(BME688_BUS)
    bme = bme680.BME680(i2c_addr=0x76, i2c_device=i2c)
    bme.set_gas_status(bme680.ENABLE_GAS_MEAS)
    bme.set_filter(bme680.FILTER_SIZE_3)
    bme.set_gas_heater_temperature(320)
    bme.set_gas_heater_duration(150)
    bme.select_gas_heater_profile(0)
    print("? I2C: BME688")
except Exception as e:
    print(f"?? I2C: BME688 failed - {e}")
    bme = None

# GPS - Cube Orange via DroneKit
try:
    gps = CubeOrangeGPS(port='/dev/ttyACM0', baud=115200)
    print("? GPS: Cube Orange connected")
except Exception as e:
    print(f"? GPS: Failed to connect - {e}")
    gps = None

# ============================================================
# AI MODEL LOADING
# ============================================================
print("?? Loading AI models...")
try:
    fire_model = YOLO(FIRE_MODEL, task='detect')
    human_model = YOLO(HUMAN_MODEL, task='detect')
    object_model = YOLO(OBJECT_MODEL, task='detect')
    print("? AI models loaded")
except Exception as e:
    print(f"? Model loading failed: {e}")
    exit(1)

# ============================================================
# CSV INITIALIZATION
# ============================================================
os.makedirs(EVIDENCE_DIR, exist_ok=True)
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'timestamp', 'latitude', 'longitude', 'altitude', 'pm25', 
            'gas_resistance', 'temperature', 'fire_confidence', 
            'fire_source', 'severity', 'gps_satellites', 'gps_fix_type', 'evidence_url'
        ])

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def read_pms7003():
    """Read PM2.5 from PMS7003 sensor"""
    if not pms_sensor:
        return 0
    try:
        pms_sensor.flushInput()
        data = pms_sensor.read(32)
        if len(data) == 32 and data[0] == 0x42 and data[1] == 0x4d:
            pm25 = (data[12] << 8) | data[13]
            return pm25
    except:
        pass
    return 0

def read_bme688():
    """Read temperature and gas resistance from BME688"""
    if not bme:
        return 25.0, 100000
    try:
        if bme.get_sensor_data():
            return bme.data.temperature, bme.data.gas_resistance
    except:
        pass
    return 25.0, 100000

def get_gps():
    """Get GPS coordinates from Cube Orange"""
    if gps and gps.connected and gps.has_fix():
        coords = gps.get_coordinates()
        return coords['lat'], coords['lon'], coords['alt']
    return 0.0, 0.0, 0.0

def detect_fire_or_smoke(fire_conf, pm25, temp, gas_res, baseline_temp=BASELINE_TEMPERATURE):
    """
    Determine if it's active fire or smoke based on sensor fusion
    
    Returns: 'ACTIVE_FIRE', 'HEAVY_SMOKE', or 'SMOKE_ONLY'
    """
    temp_rise = temp - baseline_temp
    
    # Active Fire Detection Criteria
    if fire_conf > 0.6 and temp_rise > 5.0 and gas_res < 80000:
        return "ACTIVE_FIRE"
    elif fire_conf > 0.5 and temp_rise > 3.0:
        return "ACTIVE_FIRE"
    # Smoke without visible flames
    elif fire_conf > 0.3 and pm25 > 50 and temp_rise < 3.0:
        return "SMOKE_ONLY"
    # Heavy smoke (might have fire nearby)
    elif pm25 > 100 and gas_res < 50000:
        return "HEAVY_SMOKE"
    else:
        return "SMOKE_ONLY"

def classify_fire_source(pm25, gas_res, temp, human_detected, fire_type):
    """
    Classify fire/smoke source based on sensor patterns using BME688 + PMS7003
    
    BME688 Gas Resistance Patterns:
    - Very Low (< 20,000 O): Electrical/Plastic/Chemical fire (toxic gases)
    - Low (20,000 - 80,000 O): Active combustion with smoke
    - Medium (80,000 - 150,000 O): Wood/Biomass burning
    - High (> 150,000 O): Clean air or cooking smoke
    
    PMS7003 PM2.5 Patterns:
    - Low (< 35 µg/m³): Normal air quality
    - Medium (35-100 µg/m³): Smoke present
    - High (100-250 µg/m³): Heavy smoke
    - Very High (> 250 µg/m³): Dense smoke/industrial
    """
    
    # Electrical/Plastic Fire (most dangerous - toxic gases)
    if gas_res < 20000 and pm25 > 50:
        if fire_type == "ACTIVE_FIRE":
            return "Electrical/Plastic Fire (TOXIC)"
        else:
            return "Electrical/Plastic Smoke (TOXIC)"
    
    # Chemical/Industrial Fire
    elif gas_res < 30000 and pm25 > 150:
        if fire_type == "ACTIVE_FIRE":
            return "Chemical/Industrial Fire"
        else:
            return "Industrial Smoke"
    
    # Active Wood/Biomass Fire
    elif pm25 > 100 and gas_res >= 80000 and gas_res < 200000 and temp > 28:
        if fire_type == "ACTIVE_FIRE":
            return "Wood/Biomass Fire"
        else:
            return "Biomass Smoke"
    
    # Vehicle/Tire Fire (rubber burning)
    elif gas_res < 40000 and pm25 > 80 and pm25 < 200:
        if fire_type == "ACTIVE_FIRE":
            return "Vehicle/Rubber Fire"
        else:
            return "Rubber Smoke"
    
    # Trash/Waste Fire
    elif pm25 > 120 and gas_res < 100000 and temp > 27:
        if fire_type == "ACTIVE_FIRE":
            return "Trash/Waste Fire"
        else:
            return "Waste Burning Smoke"
    
    # Human-caused fire (cooking, campfire, arson)
    elif human_detected and pm25 > 50:
        if fire_type == "ACTIVE_FIRE":
            if pm25 < 100 and gas_res > 100000:
                return "Cooking Fire"
            else:
                return "Human Activity Fire"
        else:
            return "Human-caused Smoke"
    
    # Grass/Agricultural Fire
    elif pm25 > 80 and pm25 < 150 and gas_res > 100000:
        if fire_type == "ACTIVE_FIRE":
            return "Grass/Agricultural Fire"
        else:
            return "Agricultural Smoke"
    
    # Light smoke (possible early stage fire)
    elif pm25 > 35 and pm25 < 80:
        if fire_type == "ACTIVE_FIRE":
            return "Small Fire (Early Stage)"
        else:
            return "Light Smoke Source"
    
    # Heavy smoke with low visibility
    elif pm25 > 250:
        return "Dense Smoke (Fire Nearby)"
    
    # Default classification
    else:
        if fire_type == "ACTIVE_FIRE":
            return "Unknown Fire Source"
        else:
            return "Unknown Smoke Source"

def get_severity(fire_conf, pm25, gas_res, fire_type):
    """Calculate severity level based on fire type and sensor data"""
    
    # CRITICAL: Toxic fires or very high danger
    if gas_res < 20000 or pm25 > 250:
        return "CRITICAL"
    
    # CRITICAL: Active fire with high confidence and dangerous levels
    if fire_type == "ACTIVE_FIRE" and fire_conf > 0.75 and pm25 > 150:
        return "CRITICAL"
    
    # HIGH: Active fire with elevated readings
    if fire_type == "ACTIVE_FIRE" and fire_conf > 0.6 and pm25 > 100:
        return "HIGH"
    
    # HIGH: Heavy smoke that could indicate nearby fire
    if fire_type == "HEAVY_SMOKE" and pm25 > 150:
        return "HIGH"
    
    # MEDIUM: Moderate fire or significant smoke
    if fire_type == "ACTIVE_FIRE" and fire_conf > 0.4:
        return "MEDIUM"
    
    # MEDIUM: Significant smoke levels
    if pm25 > 100:
        return "MEDIUM"
    
    # LOW: Light smoke or small fire
    return "LOW"

from botocore.config import Config

def upload_to_aws(frame, detection_data):
    """
    Upload incident to DynamoDB and evidence to S3.
    Designed for UAV flight: skips quickly if offline to prevent script freezing.
    """
    try:
        # 1. Define timeout configuration (Fast fail if no network)
        fast_config = Config(
            connect_timeout=1, 
            read_timeout=1, 
            retries={'max_attempts': 0}
        )
        
        # Re-initialize clients with fast timeout (or use global ones)
        s3_fast = boto3.client('s3', region_name='ap-south-1', config=fast_config)
        db_fast = boto3.resource('dynamodb', region_name='ap-south-1', config=fast_config)
        table_fast = db_fast.Table('GaganNetraIncidents')

        incident_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # 2. Prepare Evidence Image filename
        # Note: The physical file is already saved in log_burn_event() 
        # but we need the filename for S3
        evidence_filename = f"evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        s3_key = f"incidents/{evidence_filename}"
        
        # Encode frame to memory buffer for upload
        _, buffer = cv2.imencode('.jpg', frame)
        img_bytes = buffer.tobytes()
        
        # 3. Upload to S3
        s3_fast.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=img_bytes,
            ACL='public-read',
            ContentType='image/jpeg'
        )
        
        evidence_url = f"https://{S3_BUCKET}.s3.ap-south-1.amazonaws.com/{s3_key}"
        
        # 4. Upload to DynamoDB
        item = {
            'incident_id': incident_id,
            'timestamp': timestamp,
            'latitude': str(detection_data.get('latitude', 0.0)),
            'longitude': str(detection_data.get('longitude', 0.0)),
            'altitude': str(detection_data.get('altitude', 0.0)),
            'pm25': int(detection_data['pm25']),
            'gas_resistance': int(detection_data['gas_resistance']),
            'temperature': Decimal(str(round(detection_data['temperature'], 2))),
            'fire_confidence': Decimal(str(round(detection_data['fire_confidence'], 3))),
            'fire_source': detection_data['fire_source'],
            'severity': detection_data['severity'],
            'gps_satellites': int(detection_data.get('gps_satellites', 0)),
            'gps_fix_type': int(detection_data.get('gps_fix_type', 0)),
            'evidence_url': evidence_url,
            'status': 'NEW',
            'device_id': 'GAGAN_NETRA_01'
        }
        
        table_fast.put_item(Item=item)
        print(f"?? AWS: Sync Successful ({incident_id[:8]})")
        return True
        
    except Exception:
        # This block catches connection timeouts and No-Network errors
        # It allows the Jetson to keep flying and detecting without lag
        print("?? AWS: Offline Mode (Skipping cloud upload, saving locally only)")
        return False
        
def log_burn_event(frame, fire_conf, pm25, gas_res, temp, human_detected):
    """Log fire/smoke detection event to CSV and AWS with unified naming schema"""
    timestamp_obj = datetime.now()
    timestamp_str = timestamp_obj.strftime("%Y-%m-%d %H:%M:%S")
    lat, lon, alt = get_gps()
    
    # 1. Get GPS status
    gps_sats = 0
    gps_fix = 0
    if gps and gps.connected:
        coords = gps.get_coordinates()
        gps_sats = coords.get('satellites', 0)
        gps_fix = coords.get('fix_type', 0)
    
    # 2. Save Image Locally for CSV Reference
    img_name = f"evid_{timestamp_obj.strftime('%Y%m%d_%H%M%S')}.jpg"
    local_img_path = os.path.join(EVIDENCE_DIR, img_name)
    cv2.imwrite(local_img_path, frame)
    
    # 3. Logic for Classification and Severity
    fire_type = detect_fire_or_smoke(fire_conf, pm25, temp, gas_res)
    fire_source_val = classify_fire_source(pm25, gas_res, temp, human_detected, fire_type)
    severity = get_severity(fire_conf, pm25, gas_res, fire_type)
    full_source_desc = f"{fire_type}: {fire_source_val}"
    
    # 4. LOG TO CSV (Sync with your Dashboard)
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp_str, lat, lon, alt, pm25, gas_res, temp, 
            fire_conf, full_source_desc, severity, gps_sats, gps_fix, local_img_path
        ])
    
    # 5. UPLOAD TO AWS (Sync with Cloud)
    upload_to_aws(frame, {
        'latitude': lat,
        'longitude': lon,
        'altitude': alt,
        'pm25': pm25,
        'gas_resistance': gas_res,
        'temperature': temp,
        'fire_confidence': fire_conf,
        'fire_source': full_source_desc,
        'severity': severity,
        'gps_satellites': gps_sats,
        'gps_fix_type': gps_fix
    })
    
    print(f"?? Event Logged: {full_source_desc} | Severity: {severity}")
    
    gps_status = f"GPS Fix:{gps_fix} Sats:{gps_sats}" if gps and gps.connected else "GPS:N/A"
    print(f"?? {fire_type} | {severity} | PM2.5:{pm25} | GasRes:{gas_res} | Temp:{temp:.1f}°C")
    print(f"   Location: ({lat:.7f}, {lon:.7f}, {alt:.1f}m) | {gps_status}")
    print(f"   Classification: {fire_source}")

# ============================================================
# VIDEO CAPTURE
# ============================================================
print(f"?? Opening {VIDEO_DEVICE} (attempt 1)...")
cap = cv2.VideoCapture(VIDEO_DEVICE, cv2.CAP_V4L2)

if not cap.isOpened():
    print(f"?? Opening {VIDEO_DEVICE} (attempt 2)...")
    time.sleep(3)
    cap = cv2.VideoCapture(VIDEO_DEVICE)

if not cap.isOpened():
    print(f"?? Opening {VIDEO_DEVICE} (attempt 3)...")
    time.sleep(3)
    cap = cv2.VideoCapture(VIDEO_DEVICE)

if not cap.isOpened():
    print("? No camera!")
    exit(1)

# Set buffer size to minimize latency
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
print("? Camera ready\\\\\\\\n")

if RECORD_VIDEO and cap.isOpened():
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = os.path.join(VIDEO_SAVE_PATH, f"flight_{timestamp}.avi")
    
    # Get camera resolution
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = 5.0  # Common for Jetson; adjust if the video plays too fast/slow..
    
    video_writer = cv2.VideoWriter(video_filename, fourcc, fps, (width, height))
    print(f"[*] Recording initialized: {video_filename}")
# ============================================================
# MAIN DETECTION LOOP
# ============================================================
last_log_time = 0
frame_count = 0

print("?? Starting intelligent detection...")
print("-" * 60)

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("?? Frame read failed")
            time.sleep(0.1)
            continue
        
        frame_count += 1
        
        # Read sensors
        pm25 = read_pms7003()
        temp, gas_res = read_bme688()
        
        # Run AI detection
        fire_results = fire_model(frame, conf=FIRE_CONFIDENCE_THRESHOLD, verbose=False)
        human_results = human_model(frame, conf=0.5, verbose=False)
        try:
            object_results = object_model(frame, conf=0.5, verbose=False)
        except Exception as e:
            print(f"? Object detection failed: {e}")
            object_results = []

        # Check for fire detection
        fire_detected = False
        max_fire_conf = 0.0
        
        for result in fire_results:
            if result.boxes:
                for box in result.boxes:
                    conf = float(box.conf[0])
                    if conf > max_fire_conf:
                        max_fire_conf = conf
                    if conf > 0.5:
                        fire_detected = True
        
        # Check for human detection
        human_detected = len(human_results[0].boxes) > 0 if human_results else False
        
        # Check for object detection
        object_detected = len(object_results[0].boxes) > 0 if object_results else False
        
        # Create annotated frame for display
        annotated_frame = frame.copy()
        
        # Draw fire detections (red boxes)
        for result in fire_results:
            if result.boxes:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    cv2.putText(annotated_frame, f"FIRE {conf:.2f}", (x1, y1-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Draw human detections (green boxes)
        for result in human_results:
            if result.boxes:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                    cv2.putText(annotated_frame, "HUMAN", (x1, y1-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Draw object detections (blue boxes)
        for result in object_results:
            if result.boxes:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 0), 3)
                    cv2.putText(annotated_frame, "OBJECT", (x1, y1-10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        
        # Add sensor data overlay (top of screen) - UPDATE THIS SECTION
        gps_text = ""
        if gps and gps.connected:
            coords = gps.get_coordinates()
            if gps.has_fix():
                gps_text = f" | GPS: {coords['lat']:.5f},{coords['lon']:.5f} {coords['alt']:.0f}m"
            else:
                gps_text = f" | GPS: Searching ({coords['satellites']} sats)"
        
        overlay_text = f"PM2.5: {pm25} | Temp: {temp:.1f}C | Gas: {gas_res:.0f}{gps_text}"
        cv2.rectangle(annotated_frame, (0, 0), (1200, 50), (0, 0, 0), -1)
        cv2.putText(annotated_frame, overlay_text, (10, 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add alert if fire detected
        if fire_detected and pm25 > FIRE_PM25_THRESHOLD:
            # Quick classification for display
            fire_type = detect_fire_or_smoke(max_fire_conf, pm25, temp, gas_res)
            severity = get_severity(max_fire_conf, pm25, gas_res, fire_type)
            alert_text = f"ALERT: {severity} {fire_type} DETECTED!"
            cv2.rectangle(annotated_frame, (0, 60), (900, 120), (0, 0, 255), -1)
            cv2.putText(annotated_frame, alert_text, (10, 100),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
        
        # Display frame (only if not in headless mode)
        if not HEADLESS_MODE:
            cv2.imshow('GAGAN NETRA - Live Detection Feed', annotated_frame)
            
            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\\\\\\\\n?? User requested exit...")
                break
        else:
            time.sleep(0.033)  # ~30 FPS
        
        # Log event if fire detected and PM2.5 elevated
        current_time = time.time()
        if fire_detected and pm25 > FIRE_PM25_THRESHOLD:
            if current_time - last_log_time > COOLDOWN:
                log_burn_event(frame, max_fire_conf, pm25, gas_res, temp, human_detected)
                last_log_time = current_time
        
        # Display stats every 30 frames
        if frame_count % 30 == 0:
            print(f"Frame:{frame_count} | PM2.5:{pm25} | Temp:{temp:.1f}°C | Gas:{gas_res:.0f}")
            
        if RECORD_VIDEO and 'video_writer' in locals():
            video_writer.write(annotated_frame)
        
        time.sleep(0.033)  # ~30 FPS

except KeyboardInterrupt:
    print("\\\\\\\\n\\\\\\\\n??  Shutting down...")

finally:
    cap.release()
    if RECORD_VIDEO and 'video_writer' in locals():
        video_writer.release()
        print(f"[*] Video file saved: {video_filename}")
    cv2.destroyAllWindows()
    if pms_sensor:
        pms_sensor.close()
    if gps:  # NEW
        gps.close()
    print("? Cleanup complete")

