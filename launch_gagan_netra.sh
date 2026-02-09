#!/bin/bash
echo "=========================================="
echo "GAGAN NETRA - Complete System Launch"
echo "=========================================="

# Clean up existing processes
echo "[*] Cleaning up..."
pkill -f gopro_feed
pkill -f ffmpeg
pkill -f "python3.*main.py"
pkill -f streamlit
sleep 2

# Reload v4l2loopback with correct settings
echo "[*] Setting up v4l2loopback..."
sudo modprobe -r v4l2loopback 2>/dev/null
sudo modprobe v4l2loopback exclusive_caps=1 card_label="GoPro42" video_nr=42
sleep 1

# Auto-detect Jetson's IP on USB interface
echo "[*] Detecting USB network configuration..."
USB_IFACE=$(ip link show | grep -E "usb[0-9].*state UP" | grep -oP "usb\\d+" | head -1)

if [ -z "$USB_IFACE" ]; then
    echo "[!] No active USB network interface found"
    echo "[!] Available interfaces:"
    ip link show | grep usb
    exit 1
fi

echo "[+] Using USB interface: $USB_IFACE"

# FIXED IP DETECTION
JETSON_IP=$(ip -4 addr show dev $USB_IFACE 2>/dev/null | grep -oP 'inet\s+\K[\d.]+' | head -1)

if [ -z "$JETSON_IP" ]; then
    echo "[!] No IP assigned to $USB_IFACE"
    echo "    Assign manually: sudo ip addr add 172.28.180.1/24 dev $USB_IFACE"
    exit 1
fi


# Test GoPro connection
echo "[*] Testing GoPro connection..."
if ! ping -c 2 -W 2 172.28.180.51 > /dev/null 2>&1; then
    echo "[!] GoPro not responding at 172.28.180.51"
    echo "[!] Make sure GoPro is powered ON and connected via USB"
    exit 1
fi

echo "[+] GoPro connected"

# Start GoPro webcam mode via API
echo "[*] Enabling GoPro webcam mode..."
if curl --max-time 5 -s "http://172.28.180.51/gopro/webcam/start" > /dev/null 2>&1; then
    echo "[+] GoPro webcam mode enabled"
else
    echo "[!] Warning: Could not enable webcam mode (may already be active)"
fi
sleep 3

# Optimized for Low Latency (Zero Buffer)
ffmpeg -hide_banner -loglevel error \
    -fflags nobuffer -flags low_delay \
    -i "udp://${JETSON_IP}:8554?overrun_nonfatal=1&fifo_size=50000000" \
    -pix_fmt yuyv422 -f v4l2 /dev/video42 \
    -preset ultrafast -tune zerolatency \
    > /dev/null 2>&1 &

FFMPEG_PID=$!

echo "[*] Waiting 15 seconds for stable stream..."
sleep 15

# Verify FFmpeg is running
if pgrep -f "ffmpeg.*${JETSON_IP}:8554" > /dev/null; then
    echo "[+] Stream active!"
else
    echo "[!] FFmpeg failed - manual test works, continuing anyway..."
fi

echo "[+] Stream active"

# Create logs directory
mkdir -p ~/gagan_netra/logs
USER_SITE=$(python3 -m site --user-site)

# Start detection system with display access
echo "[*] Starting fire detection system..."
xhost +local:root > /dev/null
cd ~/gagan_netra
sudo -E env "PATH=$PATH" "PYTHONPATH=$PYTHONPATH:$USER_SITE" DISPLAY=:0 python3 main.py > logs/main.log 2>&1 &
MAIN_PID=$!

# Wait for detection to initialize
sleep 5

# Start Streamlit dashboard
# --- MODIFIED DASHBOARD SECTION ---
#echo "[*] Checking network for Dashboard..."
# Try to ping a reliable host (e.g., 8.8.8.8) with a 2-second timeout
#if ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; then
#    echo "[+] Internet detected. Starting real-time dashboard..."
#    python3 -m streamlit run realtime_dashboard.py \
#        --server.port 8501 \
#        --server.address 0.0.0.0 \
#        --logger.level error > logs/dashboard.log 2>&1 &
#    DASHBOARD_PID=$!
#    DASHBOARD_ENABLED=true
#else
#    echo "[!] No internet detected. Dashboard skipped to prevent system hang."
#    echo "[!] AI Detection will still run in offline mode."
#   DASHBOARD_ENABLED=false
#fi
echo "[INFO] Dashboard skipped. AI is running in the background."
echo ""
echo "Press Ctrl+C to stop all systems"
echo "=========================================="
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "[*] Shutting down GAGAN NETRA..."
    
    echo "    Stopping detection system..."
    sudo kill $MAIN_PID 2>/dev/null
    
    # Only try to kill dashboard if it was enabled
    if [ "$DASHBOARD_ENABLED" = true ]; then
        echo "    Stopping dashboard..."
        kill $DASHBOARD_PID 2>/dev/null
    fi
    
    pkill -f "python3.*main.py"
    pkill -f streamlit
    
    echo "    Stopping FFmpeg stream..."
    kill $FFMPEG_PID 2>/dev/null
    pkill -f ffmpeg
    
    echo "    Stopping GoPro webcam..."
    curl --max-time 3 -s "http://172.28.180.51/gopro/webcam/start" > /dev/null 2>&1
    
    echo "[+] All systems stopped"
    exit 0
}

# Trap Ctrl+C
trap cleanup INT TERM

# Keep script running
echo "[*] System running. Press Ctrl+C to stop."
tail -f /dev/null
    
    # Check detection system
    if ! ps -p $MAIN_PID > /dev/null; then
        echo "[!] Detection system crashed! Restarting..."
        sudo python3 main.py > logs/main.log 2>&1 &
        MAIN_PID=$!
        echo "[+] Detection system restarted (PID: $MAIN_PID)"
    fi
    
    # Check dashboard
    if ! ps -p $DASHBOARD_PID > /dev/null; then
        echo "[!] Dashboard crashed! Restarting..."
        streamlit run realtime_dashboard.py --server.port 8501 --server.address 0.0.0.0 > logs/dashboard.log 2>&1 &
        DASHBOARD_PID=$!
        echo "[+] Dashboard restarted (PID: $DASHBOARD_PID)"
    fi
    
    sleep 10
done
