                    GAGAN NETRA – Aerial Fire Intelligence System

 ┌──────────────┐
 │   GoPro      │
 │   Camera     │
 └──────┬───────┘
        │  (USB Network / UDP Stream)
        ▼
 ┌──────────────┐
 │    FFmpeg    │
 │   Streamer   │
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │ v4l2loopback │
 │ /dev/video42 │
 └──────┬───────┘
        ▼
 ┌──────────────────────────────┐
 │      Fire Detection AI       │
 │  (OpenCV / Jetson Inference) │
 └──────┬───────────────┬───────┘
        │               │
        │               │
        │               ▼
        │      ┌──────────────────┐
        │      │ AWS Cloud        │
        │      │ DynamoDB + S3    │
        │      └──────┬───────────┘
        │             ▼
        │     ┌──────────────────────┐
        │     │ Streamlit Dashboard  │
        │     │  Real-time Monitor   │
        │     └──────────────────────┘
        │
        │
        │
 ┌──────▼────────┐
 │ Cube Orange   │
 │ GPS (MAVLink) │
 └──────┬────────┘
        │
        ▼
 ┌──────────────┐
 │ Telemetry &  │
 │ Geo-tagging  │
 └──────────────┘

 ┌──────────────┐
 │   BME680     │
 │ Env Sensor   │
 └──────┬───────┘
        ▼
 ┌──────────────────────────────┐
 │ Temp / Humidity / Gas / PM2.5│
 │ Data Fusion with AI Engine   │
 └──────────────────────────────┘


