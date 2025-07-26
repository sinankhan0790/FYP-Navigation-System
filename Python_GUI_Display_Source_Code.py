import serial
import threading
import tkinter as tk
from tkinter import ttk
from tkintermapview import TkinterMapView
import csv
import os
import math
from collections import deque

# ====== CONFIGURATION ======
SERIAL_PORT = 'COM4'  # Update this to your actual port
BAUD_RATE = 115200
OUTPUT_CSV = "gps_positions.csv"
MIN_DISTANCE_METERS = 3

# ====== GLOBALS ======
marker = None
path_points = []
total_distance = 0.0
start_lat = None
start_lon = None
gps_history = deque(maxlen=5)

# ====== HELPER FUNCTIONS ======
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def moving_average(new_point):
    gps_history.append(new_point)
    avg_lat = sum(p[0] for p in gps_history) / len(gps_history)
    avg_lon = sum(p[1] for p in gps_history) / len(gps_history)
    return avg_lat, avg_lon

def calculate_heading(lat1, lon1, lat2, lon2):
    d_lon = math.radians(lon2 - lon1)
    y = math.sin(d_lon) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - \
        math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(d_lon)
    heading_rad = math.atan2(y, x)
    heading_deg = (math.degrees(heading_rad) + 360) % 360
    return heading_deg

# ====== GUI SETUP ======
root = tk.Tk()
root.title("GPS Tracking Map")
root.geometry("1100x650")

# Left frame
left_frame = tk.Frame(root)
left_frame.pack(side='left', fill='y', padx=10, pady=10)

lat_label = tk.Label(left_frame, text="X_dis: --")
lon_label = tk.Label(left_frame, text="Y_dis: --")
alt_label = tk.Label(left_frame, text="Z_dis (m): --")
speed_label = tk.Label(left_frame, text="Speed (km/h): --")
heading_label = tk.Label(left_frame, text="Heading: --°")
total_dist_label = tk.Label(left_frame, text="Total Distance (m): 0")
date_label = tk.Label(left_frame, text="Date: --")
time_label = tk.Label(left_frame, text="Time: --")

for widget in [lat_label, lon_label, alt_label, speed_label, heading_label, total_dist_label, date_label, time_label]:
    widget.pack(anchor='w', pady=2)

tk.Label(left_frame, text="Map Type:").pack(anchor='w', pady=(10, 0))
map_type_combo = ttk.Combobox(left_frame, values=["OpenStreetMap", "Google Normal", "Google Satellite"], state="readonly")
map_type_combo.set("OpenStreetMap")
map_type_combo.pack(anchor='w')

# Map frame
map_widget = TkinterMapView(root, width=800, height=650, corner_radius=0)
map_widget.pack(side='right', fill='both', expand=True)

def change_map_type(event):
    selected = map_type_combo.get()
    if selected == "OpenStreetMap":
        map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
    elif selected == "Google Normal":
        map_widget.set_tile_server("https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}")
    elif selected == "Google Satellite":
        map_widget.set_tile_server("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}")

map_type_combo.bind("<<ComboboxSelected>>", change_map_type)

# ====== CSV SETUP ======
if not os.path.exists(OUTPUT_CSV):
    with open(OUTPUT_CSV, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["X_dis", "Y_dis", "Z_dis", "Speed", "Heading", "Date", "Time"])

# ====== SERIAL READER ======
def read_serial():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    buffer = ""
    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if line:
            buffer += line + "\n"
            if "---------------------------" in line:
                parse_data(buffer)
                buffer = ""

def parse_data(data):
    global marker, path_points, total_distance, start_lat, start_lon
    lines = data.split('\n')
    lat = lon = alt = speed = date = time_str = None

    for line in lines:
        if line.startswith("Latitude:"):
            try: lat = float(line.split(":")[1].strip())
            except: lat = None
        elif line.startswith("Longitude:"):
            try: lon = float(line.split(":")[1].strip())
            except: lon = None
        elif line.startswith("Altitude"):
            alt = line.split(":")[1].strip()
        elif line.startswith("Speed"):
            speed = line.split(":")[1].strip()
        elif line.startswith("Date"):
            date = line.split(":")[1].strip()
        elif line.startswith("Time"):
            time_str = line.split(":")[1].strip()

    if lat and lon and lat != 0 and lon != 0:
        smoothed_lat, smoothed_lon = moving_average((lat, lon))

        # Ignore small changes less than 0.0001 degrees
        if path_points:
            last_lat, last_lon = path_points[-1]
            if abs(smoothed_lat - last_lat) < 0.00001 and abs(smoothed_lon - last_lon) < 0.00001:
                return
        elif start_lat is not None:
            if abs(smoothed_lat - start_lat) < 0.00001 and abs(smoothed_lon - start_lon) < 0.00001:
                return

        if start_lat is None:
            start_lat, start_lon = smoothed_lat, smoothed_lon

        map_widget.set_position(smoothed_lat, smoothed_lon)
        map_widget.set_zoom(18)

        if marker is None:
            marker = map_widget.set_marker(smoothed_lat, smoothed_lon, text="Current Location")
        else:
            marker.set_position(smoothed_lat, smoothed_lon)

        if not path_points:
            path_points.append((smoothed_lat, smoothed_lon))
            heading_label.config(text=f"Heading: --°")
        else:
            last_lat, last_lon = path_points[-1]
            distance = haversine(last_lat, last_lon, smoothed_lat, smoothed_lon)

            try:
                current_speed = float(speed)
            except:
                current_speed = 0.0

            if current_speed >= 1.0 or distance >= 1.5:
                if distance >= MIN_DISTANCE_METERS:
                    path_points.append((smoothed_lat, smoothed_lon))
                    total_distance += distance
                    total_dist_label.config(text=f"Total Distance (m): {total_distance:.2f}")
                    map_widget.set_path(path_points)

                heading = calculate_heading(last_lat, last_lon, smoothed_lat, smoothed_lon)
                heading_label.config(text=f"Heading: {heading:.1f}°")

        lat_label.config(text=f"X_dis: {smoothed_lat:.6f}")
        lon_label.config(text=f"Y_dis: {smoothed_lon:.6f}")
        alt_label.config(text=f"Z_dis (m): {alt}")
        speed_label.config(text=f"Speed (km/h): {speed}")
        date_label.config(text=f"Date: {date}")
        time_label.config(text=f"Time: {time_str}")

        with open(OUTPUT_CSV, mode='a', newline='') as file:
            writer = csv.writer(file)
            heading_deg = heading if 'heading' in locals() else "--"
            writer.writerow([smoothed_lat, smoothed_lon, alt, speed, heading_deg, date, time_str])

# ====== START THREAD ======
threading.Thread(target=read_serial, daemon=True).start()

# ====== RUN GUI ======
root.mainloop()
