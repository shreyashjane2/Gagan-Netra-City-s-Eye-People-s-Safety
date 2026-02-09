import streamlit as st
import boto3
from datetime import datetime
import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import requests

# ============================================================
# CONFIGURATION & UNICODE SYMBOLS
# ============================================================
U_DRONE    = "\U0001F681" # Helicopter/Drone
U_FIRE     = "\U0001F525"
U_WARN     = "\U000026A0"
U_CRITICAL = "\U0001F534" 
U_HIGH     = "\U0001F34A" 
U_MED      = "\U0001F7E1" 
U_LOW      = "\U0001F7E2" 
U_CAMERA   = "\U0001F4F7"
U_MAP      = "\U0001F4CD"
U_INFO     = "\U0001F4CB"
U_TEMP     = "\U0001F321"
U_CLOSE    = "\U0000274C"
U_PREV     = "\U00002B05"
U_NEXT     = "\U000027A1"
U_CHART    = "\U0001F4C8"

# Auto-refresh every 5 seconds
st_autorefresh(interval=5000, key="datarefresh")

# AWS Configuration
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
table = dynamodb.Table('GaganNetraIncidents')

st.set_page_config(page_title=f"GAGAN NETRA {U_DRONE}", layout="wide")

# ============================================================
# BACKGROUND THEME (DARK EMERGENCY GRADIENT)
# ============================================================
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        background-attachment: fixed;
    }
    /* Subtle fire glow overlay */
    .stApp::before {
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background-image: 
            radial-gradient(circle at 20% 80%, rgba(255, 94, 77, 0.08) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(220, 20, 60, 0.05) 0%, transparent 50%);
        pointer-events: none;
        z-index: 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATA FETCHING & TREND CALCULATION
# ============================================================
# C-DAC Pune Fallback Coordinates
DEFAULT_LAT = 18.53516
DEFAULT_LON = 73.81134

@st.cache_data(ttl=5)
def fetch_incidents():
    try:
        response = table.scan()
        items = response.get('Items', [])
        if items:
            df = pd.DataFrame(items)
            
            # Convert to numeric, errors='coerce' turns non-numbers into NaN
            df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce').fillna(0)
            df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce').fillna(0)

            # Replace (0,0) or NaN with C-DAC Pune coordinates
            mask = (df['latitude'] == 0) | (df['longitude'] == 0)
            df.loc[mask, 'latitude'] = DEFAULT_LAT
            df.loc[mask, 'longitude'] = DEFAULT_LON

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df.sort_values('timestamp', ascending=False)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

df = fetch_incidents()

def get_image_bytes(url):
    try:
        response = requests.get(url)
        return response.content
    except Exception as e:
        return None

# ============================================================
# HEADER & TREND METRICS
# ============================================================
st.title(f"{U_DRONE} GAGAN NETRA - Aerial Fire Intelligence")
st.markdown("**Live incident monitoring from UAV-based fire detection system**")
st.markdown("---")

if df.empty:
    st.warning(f"{U_WARN} System active. Waiting for UAV data...")
    st.stop()

# Calculate Trends for Metrics
latest_pm = df['pm25'].iloc[0]
prev_pm = df['pm25'].iloc[1] if len(df) > 1 else latest_pm
pm_delta = latest_pm - prev_pm

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Incidents", len(df))
with col2:
    critical_count = len(df[df['severity'] == 'CRITICAL'])
    st.metric("Critical Alerts", critical_count)
# 1. Calculate Averages
current_avg_pm = df['pm25'].mean()

# 2. Calculate previous average (excluding the latest record) for the trend arrow
if len(df) > 1:
    prev_avg_pm = df['pm25'].iloc[1:].mean()
    avg_delta = current_avg_pm - prev_avg_pm
else:
    avg_delta = 0

with col3:
    # This now shows the Average PM2.5 with a trend arrow
    st.metric(
        label="Average PM2.5", 
        value=f"{current_avg_pm:.1f} \u00B5g/m\u00B3", 
        delta=f"{avg_delta:.1f}", 
        delta_color="inverse"
    )

with col4:
    # Metric for the last detection time
    st.metric("Last Detection", df['timestamp'].iloc[0].strftime("%H:%M:%S"))

st.markdown("---")

# ============================================================
# RECENT INCIDENTS TABLE (Original Location)
# ============================================================
st.subheader(f"{U_FIRE} Recent Incidents")

if 'page' not in st.session_state: st.session_state.page = 0
if 'selected_img' not in st.session_state: st.session_state.selected_img = None

items_per_page = 10
start_idx = st.session_state.page * items_per_page
page_df = df.iloc[start_idx : start_idx + items_per_page].copy()

# Table Headers
h_cols = st.columns([0.5, 2, 1, 1, 1, 1, 2, 0.8])
headers = ["#", "Timestamp", "Severity", "Conf.", "PM2.5", "Temp", "Fire Source", "Evidence"]
for col, text in zip(h_cols, headers):
    col.markdown(f"**{text}**")

st.markdown("---")

# Render Table Rows
for i, (idx, row) in enumerate(page_df.iterrows(), start=start_idx + 1):
    r_cols = st.columns([0.5, 2, 1, 1, 1, 1, 2, 0.8])
    r_cols[0].write(i)
    r_cols[1].write(row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'))
    
    sev = row['severity']
    icon = U_CRITICAL if sev == 'CRITICAL' else U_HIGH if sev == 'HIGH' else U_MED if sev == 'MEDIUM' else U_LOW
    r_cols[2].write(f"{icon} {sev}")
    
    r_cols[3].write(f"{float(row['fire_confidence']):.2f}")
    r_cols[4].write(f"{row['pm25']}")
    r_cols[5].write(f"{float(row['temperature']):.1f}\u00B0C")
    r_cols[6].write(row['fire_source'])
    
    if r_cols[7].button(f"{U_CAMERA}", key=f"btn_{idx}"):
        st.session_state.selected_img = row['evidence_url']
        st.rerun()
    st.markdown('<hr style="margin: 2px 0; border: 0.5px solid rgba(255,255,255,0.1);">', unsafe_allow_html=True)

# ============================================================
# EVIDENCE VIEWER (Updated Header: Timestamp/Event Name)
# ============================================================
if st.session_state.selected_img:
    st.markdown("---")
    sel = df[df['evidence_url'] == st.session_state.selected_img].iloc[0]
    
    v1, v2 = st.columns([5, 1])
    # Replaced Case ID with Fire Source + Timestamp
    v1.subheader(f"{U_INFO} Event: {sel['fire_source']} ({sel['timestamp'].strftime('%H:%M:%S')})")
    if v2.button(f"{U_CLOSE} Close"):
        st.session_state.selected_img = None
        st.rerun()
        
    c_info, c_img = st.columns([1, 1.2])
    with c_info:
        st.markdown(f"### {U_INFO} Analysis Details")
    
        # Check fallback for the selected row
        is_sel_fallback = (float(sel['latitude']) == DEFAULT_LAT) and (float(sel['longitude']) == DEFAULT_LON)
    
        # 1. Primary Classification
        st.info(f"**Classification:** {sel['fire_source']}")
    
        # 2. Environmental Metrics
        st.markdown("#### \U0001F321 Environment") # Thermometer icon
        col_env1, col_env2 = st.columns(2)
        col_env1.write(f"**Temp:** {sel['temperature']}\u00B0C")
        col_env1.write(f"**PM2.5:** {sel['pm25']} \u00B5g/m\u00B3")
        col_env2.write(f"**Gas Res:** {sel['gas_resistance']} \u03A9")
        col_env2.write(f"**Confidence:** {float(sel['fire_confidence']):.1%}")

        # 3. UAV Flight Telemetry
        st.markdown("#### \U0001F681 UAV Telemetry") # Drone icon
        col_tel1, col_tel2 = st.columns(2)
        col_tel1.write(f"**Altitude:** {sel.get('altitude', 'N/A')} m")
        col_tel1.write(f"**Satellites:** {sel.get('gps_satellites', 'N/A')}")
        col_tel2.write(f"**Fix Type:** {sel.get('gps_fix_type', 'N/A')}")
        col_tel2.write(f"**Device ID:** `{sel.get('device_id', 'Unknown')}`")

        # 4. Location Details
        st.markdown("#### \U0001F4CD Location")
        if is_sel_fallback:
            st.warning(f"{U_WARN} GPS Lost: Using C-DAC Pune coordinates")
    
        st.write(f"**Coordinates:** `{sel['latitude']}, {sel['longitude']}`")
    
        g_url = f"https://www.google.com/maps/search/?api=1&query={sel['latitude']},{sel['longitude']}"
        st.markdown(f"[**{U_MAP} Open in Google Maps**]({g_url})")
    with c_img:
        # 1. Display the Image
        st.image(sel['evidence_url'], caption=f"UAV Snapshot: {sel['fire_source']}", use_container_width=True)
        
        # 2. Prepare Download Logic
        img_bytes = get_image_bytes(sel['evidence_url'])
        
        if img_bytes:
            # Create a filename based on timestamp
            timestamp_str = sel['timestamp'].strftime('%Y%m%d_%H%M%S')
            file_name = f"GaganNetra_{timestamp_str}.jpg"
            
            st.download_button(
                label=f"\U0001F4E5 Download Evidence Image",
                data=img_bytes,
                file_name=file_name,
                mime="image/jpeg",
                use_container_width=True
            )
        else:
            st.error("Could not prepare image for download.")

# Pagination Controls
st.markdown("---")
p1, p2, p3 = st.columns([1, 2, 1])
if p1.button(f"{U_PREV} Previous", disabled=st.session_state.page == 0):
    st.session_state.page -= 1
    st.rerun()
p2.markdown(f"<center>Page {st.session_state.page + 1}</center>", unsafe_allow_html=True)
if p3.button(f"Next {U_NEXT}", disabled=len(df) <= (start_idx + items_per_page)):
    st.session_state.page += 1
    st.rerun()

# ============================================================
# ANALYTICS & MAP (Bottom Section)
# ============================================================
st.markdown("---")
st.subheader(f"{U_MAP} Hotspots")

# Global Map
st.map(df[['latitude', 'longitude']])

st.markdown("---")

# PM2.5 Trend Graph (Full Width)
st.subheader(f"{U_CHART} PM2.5 Intensity Over Time")
# Ensure data is sorted by time for a proper line flow
df_trend = df.sort_values('timestamp')
fig_line = px.line(df_trend, x='timestamp', y='pm25', 
                   labels={'pm25': 'PM2.5 Level', 'timestamp': 'Time'},
                   markers=True)
fig_line.update_traces(line_color='#ff4b4b', line_width=3)
fig_line.update_layout(hovermode="x unified")
st.plotly_chart(fig_line, use_container_width=True)

col_a, col_b = st.columns(2)

with col_a:
    # Event Type Bar Chart
    event_counts = df['fire_source'].value_counts().reset_index()
    event_counts.columns = ['Event Type', 'Count']
    fig_bar = px.bar(event_counts, x='Event Type', y='Count', 
                     title="Incident Frequency by Type",
                     color='Count', color_continuous_scale='Reds')
    st.plotly_chart(fig_bar, use_container_width=True)

with col_b:
    # Severity Distribution
    fig_pie = px.pie(df, names='severity', title="Severity Breakdown",
                     color='severity', color_discrete_map={
                         'CRITICAL': '#ef553b', 'HIGH': '#ffa15a', 'MEDIUM': '#fecb52', 'LOW': '#636efa'
                     })
    st.plotly_chart(fig_pie, use_container_width=True)

st.caption(f"{U_DRONE} GAGAN NETRA Cloud Dashboard \u00A9 2026")