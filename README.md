🚁 GAGAN NETRA - Aerial Fire Intelligence System
UAV-Based Real-Time Fire Detection & Monitoring Platform

Python NVIDIA Jetson DroneKit AWS

📋 Overview
GAGAN NETRA is an advanced aerial fire detection system that combines UAV technology, AI-powered computer vision, and environmental sensors to provide real-time fire monitoring and incident analysis. The system integrates GoPro camera feeds with GPS telemetry and air quality sensors to detect, classify, and report fire incidents with precise geolocation data.

Key Features
🔥 Real-time Fire Detection - AI-powered fire classification with confidence scoring
📍 GPS Integration - Precise geolocation using Cube Orange autopilot with DroneKit
🌡️ Environmental Monitoring - BME680 sensor for temperature, humidity, PM2.5, and gas detection
📹 GoPro Integration - Low-latency video streaming via USB networking
☁️ Cloud Sync - Automatic incident upload to AWS DynamoDB with S3 evidence storage
📊 Live Dashboard - Streamlit-based real-time monitoring interface
🚀 Automated Launch - One-command system initialization with health checks
🏗️ System Architecture
┌─────────────────────────────────────────────────────────────┐
│                     GAGAN NETRA SYSTEM                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   GoPro      │───▶│   FFmpeg     │───▶│  v4l2loop    │  │
│  │  Camera      │    │   Streamer   │    │  /dev/video42│  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                                        │           │
│         │                                        ▼           │
│  ┌──────────────┐                     ┌──────────────────┐  │
│  │ Cube Orange  │────────────────────▶│  Fire Detection  │  │
│  │ GPS (MAVLink)│                     │   AI Engine      │  │
│  └──────────────┘                     └──────────────────┘  │
│         │                                        │           │
│         │                                        ▼           │
│  ┌──────────────┐                     ┌──────────────────┐  │
│  │   BME680     │────────────────────▶│   AWS DynamoDB   │  │
│  │   Sensor     │                     │   + S3 Storage   │  │
│  └──────────────┘                     └──────────────────┘  │
│                                               │              │
│                                               ▼              │
│                                    ┌──────────────────────┐ │
│                                    │ Streamlit Dashboard  │ │
│                                    │   (Port 8501)        │ │
│                                    └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
🛠️ Hardware Requirements
Compute Platform
NVIDIA Jetson Nano/Xavier NX/Orin - AI processing unit
16GB+ SD Card - System storage
5V 4A Power Supply - Stable power delivery
Sensors & Peripherals
Cube Orange Autopilot - GPS/MAVLink telemetry (via USB ACM)
GoPro Hero 9+ - Video capture (USB-C networking mode)
BME680 Sensor - Environmental monitoring (I2C)
Optional: Display for live preview (HDMI)
Network Configuration
USB Network Interface - GoPro → Jetson (172.28.180.x subnet)
WiFi/Ethernet - Cloud connectivity for AWS sync
📦 Software Dependencies
Core Libraries
# Computer Vision
opencv-python==4.8.1

# DroneKit GPS
dronekit==2.9.2
pymavlink==2.4.37

# AWS Integration
boto3==1.34.45
botocore==1.34.45

# Environmental Sensors
bme680==1.1.1
smbus2==0.4.3

# Dashboard
streamlit==1.31.0
streamlit-autorefresh==1.0.1
plotly==5.18.0
pandas==2.0.3

# Video Processing
ffmpeg-python==0.2.0
🚀 Installation
1. Clone Repository
git clone https://github.com/yourusername/gagan-netra.git
cd gagan-netra
2. Install System Dependencies
# Update system
sudo apt update && sudo apt upgrade -y

# Install FFmpeg and v4l2loopback
sudo apt install -y ffmpeg v4l2loopback-dkms

# Install Python development tools
sudo apt install -y python3-pip python3-dev
3. Install Python Packages
pip3 install -r requirements.txt
4. Configure AWS Credentials
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: ap-south-1
# Default output format: json
5. Setup v4l2loopback
sudo modprobe v4l2loopback exclusive_caps=1 card_label="GoPro42" video_nr=42
6. Configure Auto-start (Optional)
# Add to /etc/rc.local or create systemd service
sudo nano /etc/systemd/system/gagan-netra.service
🎯 Usage
Quick Start
cd ~/gagan_netra
chmod +x launch_gagan_netra.sh
./launch_gagan_netra.sh
The launch script will:

✅ Clean up previous processes
✅ Configure v4l2loopback virtual camera
✅ Detect USB network interface
✅ Test GoPro connectivity
✅ Start FFmpeg video stream
✅ Initialize GPS reader
✅ Launch fire detection system
✅ Start Streamlit dashboard (if internet available)
Access Dashboard
# Local access
http://localhost:8501

# Network access (replace with your Jetson IP)
http://192.168.1.xxx:8501
Manual Component Testing
Test GPS Connection
python3 gps_reader.py
Test GoPro Stream
# Enable GoPro webcam mode
curl http://172.28.180.51/gopro/webcam/start

# Test FFmpeg stream (replace JETSON_IP)
ffmpeg -i udp://172.28.180.1:8554 -f v4l2 /dev/video42
Test BME680 Sensor
python3 -c "import bme680; sensor = bme680.BME680(); print(sensor.get_sensor_data())"
📊 Data Flow & CSV Logging
CSV Log Structure (gagan_netra_flight_log.csv)
timestamp,fire_source,fire_confidence,temperature,humidity,pm25,gas_resistance,latitude,longitude,altitude,gps_satellites,gps_fix_type,severity,evidence_url,device_id
Severity Classification
CRITICAL - PM2.5 > 150, Confidence > 85%
HIGH - PM2.5 > 100, Confidence > 70%
MEDIUM - PM2.5 > 50, Confidence > 50%
LOW - Below threshold
Fire Source Categories
🏭 Industrial Fire
🌾 Agricultural Burning
🌲 Forest Fire
🔥 Uncontrolled Burn
⚠️ Unknown Source
🔧 Configuration Files
Network Settings
Edit IP addresses in launch_gagan_netra.sh:

# GoPro static IP
GOPRO_IP="172.28.180.51"

# Auto-detected Jetson IP on USB interface
JETSON_IP=$(ip -4 addr show dev usb0 | grep -oP 'inet\s+\K[\d.]+')
GPS Port Configuration
Edit in gps_reader.py:

port = '/dev/ttyACM0'  # Change if using different port
baud = 115200
AWS Configuration
Edit in main.py:

dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
table = dynamodb.Table('GaganNetraIncidents')
s3_bucket = 'gagan-netra-evidence'
🐛 Troubleshooting
GoPro Connection Issues
# Check USB network interface
ip addr show | grep usb

# Manually assign IP if needed
sudo ip addr add 172.28.180.1/24 dev usb0

# Test GoPro ping
ping 172.28.180.51
GPS Not Connecting
# List serial devices
ls -l /dev/ttyACM*
ls -l /dev/ttyUSB*

# Check MAVLink messages
mavproxy.py --master=/dev/ttyACM0 --baudrate=115200
FFmpeg Stream Failure
# Check v4l2loopback
lsmod | grep v4l2loopback

# Verify virtual device
ls -l /dev/video42

# Test direct FFmpeg output
ffmpeg -i udp://172.28.180.1:8554 -f sdl "GoPro Stream"
Dashboard Not Loading
# Check if Streamlit is running
ps aux | grep streamlit

# View dashboard logs
tail -f ~/gagan_netra/logs/dashboard.log

# Manually start dashboard
streamlit run realtime_dashboard.py --server.port 8501
📁 Project Structure
gagan-netra/
│
├── main.py                      # Main detection loop
├── gps_reader.py               # DroneKit GPS interface
├── threaded_camera.py          # Threaded camera handler
├── realtime_dashboard.py       # Streamlit dashboard
├── launch_gagan_netra.sh       # System launcher
│
├── logs/                       # Runtime logs
│   ├── main.log
│   └── dashboard.log
│
├── gagan_netra_flight_log.csv # Local incident log
│
├── requirements.txt            # Python dependencies
├── .gitignore                 # Git exclusions
└── README.md                  # This file
🔐 Security Notes
Never commit AWS credentials - Use IAM roles or environment variables
Sanitize GPS coordinates - Implement geofencing for sensitive areas
Secure network interfaces - Use VPN for remote dashboard access
Encrypt evidence uploads - Enable S3 server-side encryption
🤝 Contributing
Contributions are welcome! Please:

Fork the repository
Create a feature branch (git checkout -b feature/AmazingFeature)
Commit changes (git commit -m 'Add AmazingFeature')
Push to branch (git push origin feature/AmazingFeature)
Open a Pull Request
📝 License
This project is licensed under the MIT License - see the LICENSE file for details.

🙏 Acknowledgments
DroneKit - MAVLink/ArduPilot interface
NVIDIA - Jetson platform support
GoPro - USB networking documentation
AWS - Cloud infrastructure
OpenCV - Computer vision foundation```
## 📧 Contact

**Project Maintainer:** Shreyash Jane  
**Email:** shreyashjane2@gmail.com 
**Project Link:** https://github.com/shreyashjane2/Gagan-Netra-City-s-Eye-People-s-Safety
---

**⚠️ DISCLAIMER:** This system is designed for research and early warning purposes. Always follow local regulations regarding UAV operations and fire reporting procedures.

**🚁 Built with ❤️ for aerial fire intelligence**
