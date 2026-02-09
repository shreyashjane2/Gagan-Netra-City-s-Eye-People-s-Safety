#!/usr/bin/env python3
"""
gps_reader.py - GPS reader for GAGAN NETRA using DroneKit
"""

import logging
from dronekit import connect
import threading
import time

# Suppress DroneKit MAVLink errors
logging.getLogger('dronekit.mavlink').setLevel(logging.CRITICAL)
logging.getLogger('autopilot').setLevel(logging.WARNING)

class CubeOrangeGPS:
    def __init__(self, port='/dev/ttyACM0', baud=115200):
        self.vehicle = None
        self.connected = False
        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.altitude_relative = 0.0
        self.satellites = 0
        self.fix_type = 0
        self.heading = 0
        self.ground_speed = 0.0
        
        try:
            print(f"[GPS] Connecting to {port}...")
            self.vehicle = connect(port, baud=baud, wait_ready=False, timeout=15)
            self.connected = True
            print(f"[GPS] ? Connected - Firmware: {self.vehicle.version}")
            
            # Start background update thread
            self.running = True
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()
            
        except Exception as e:
            print(f"[GPS] ? Connection failed: {e}")
            self.connected = False
    
    def _update_loop(self):
        """Background thread to update GPS data"""
        while self.running and self.connected:
            try:
                if self.vehicle:
                    loc = self.vehicle.location.global_frame
                    loc_rel = self.vehicle.location.global_relative_frame
                    gps = self.vehicle.gps_0
                    
                    self.latitude = loc.lat if loc.lat else 0.0
                    self.longitude = loc.lon if loc.lon else 0.0
                    self.altitude = loc.alt if loc.alt else 0.0
                    self.altitude_relative = loc_rel.alt if loc_rel.alt else 0.0
                    self.satellites = gps.satellites_visible
                    self.fix_type = gps.fix_type
                    self.heading = self.vehicle.heading if self.vehicle.heading else 0
                    self.ground_speed = self.vehicle.groundspeed if self.vehicle.groundspeed else 0.0
                    
                time.sleep(0.5)  # Update 2x per second
                
            except Exception as e:
                print(f"[GPS] Update error: {e}")
                time.sleep(1)
    
    def get_coordinates(self):
        """Get current GPS coordinates and status"""
        return {
            'lat': self.latitude,
            'lon': self.longitude,
            'alt': self.altitude,
            'alt_relative': self.altitude_relative,
            'satellites': self.satellites,
            'fix_type': self.fix_type,
            'heading': self.heading,
            'speed': self.ground_speed
        }
    
    def has_fix(self):
        """Check if GPS has a valid fix"""
        return self.fix_type >= 2  # 2=2D, 3=3D
    
    def get_location_string(self):
        """Get formatted location string"""
        if self.has_fix():
            return f"{self.latitude:.7f}, {self.longitude:.7f}"
        else:
            return "No GPS Fix"
    
    def close(self):
        """Close connection"""
        self.running = False
        if self.vehicle:
            self.vehicle.close()
        print("[GPS] Connection closed")
