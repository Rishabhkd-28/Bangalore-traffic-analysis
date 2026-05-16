import requests, pandas as pd, numpy as np
from datetime import datetime, timedelta, date
from sqlalchemy import create_engine, text

DB_URL = "postgresql+psycopg2://postgres:prabhupada@localhost:5432/bangalore_traffic"
engine = create_engine(DB_URL)

JUNCTIONS = [
    (12.9716, 77.5946, "Silk Board"), (12.9352, 77.6245, "Marathahalli"),
    (12.9698, 77.7499, "Whitefield"), (12.9784, 77.6408, "Outer Ring Road KR Puram"),
    (12.9762, 77.6033, "Koramangala"), (12.9719, 77.5937, "HSR Layout"),
    (12.9856, 77.5533, "MG Road"), (13.0358, 77.5970, "Hebbal"),
    (12.9141, 77.6101, "BTM Layout"), (12.9902, 77.7172, "Mahadevapura"),
]

HOURLY_CONGESTION = [0.12, 0.10, 0.10, 0.10, 0.12, 0.18, 0.35, 0.65, 0.85, 0.78, 0.55, 0.42, 
                     0.38, 0.35, 0.32, 0.33, 0.45, 0.70, 0.82, 0.75, 0.60, 0.45, 0.30, 0.18]

def backfill_weather():
    print("\n🌦️  PART 1: Backfilling weather data…")
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 12.9716, "longitude": 77.5946,
        "start_date": "2025-01-01", "end_date": str(date.today()),
        "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
        "timezone": "Asia/Kolkata"
    }
    r = requests.get(url, params=params); r.raise_for_status()
    h = r.json().get("hourly", {})
    df = pd.DataFrame({"temperature_c": h.get("temperature_2m"), "precipitation_mm": h.get("precipitation"), 
                       "windspeed_kmh": h.get("windspeed_10m"), "weathercode": h.get("weathercode")})
    df["date"] = pd.to_datetime(h.get("time")).dt.date
    df["hour"] = pd.to_datetime(h.get("time")).dt.hour
    df.to_sql("weather_data", engine, if_exists="replace", index=False)
    print(f"  ✅ {len(df)} weather rows saved.")

def backfill_traffic():
    print("\n🚦 PART 2: Backfilling traffic data…")
    rng = pd.date_range(end=datetime.now(), periods=30*24, freq="h")
    recs = []
    for ts in rng:
        base = HOURLY_CONGESTION[ts.hour]
        for lat, lon, lbl in JUNCTIONS:
            cong = min(0.95, base + np.random.uniform(-0.05, 0.05))
            recs.append({"junction_label": lbl, "latitude": lat, "longitude": lon, "fetched_at": ts,
                         "current_speed": round(30 * (1-cong), 1), "free_flow_speed": 30.0})
    df = pd.DataFrame(recs)
    df.to_sql("traffic_speeds", engine, if_exists="replace", index=False)
    print(f"  ✅ {len(df)} traffic rows saved.")

def rebuild_clean():
    print("\n🧹 PART 3: Rebuilding clean tables…")
    df = pd.read_sql("SELECT * FROM traffic_speeds", engine)
    df["fetched_at"] = pd.to_datetime(df["fetched_at"])
    df["hour"] = df["fetched_at"].dt.hour
    df["is_weekend"] = df["fetched_at"].dt.weekday >= 5
    df["congestion_index"] = (1 - df["current_speed"] / df["free_flow_speed"]).clip(0,1)
    df.to_sql("traffic_speeds_clean", engine, if_exists="replace", index=False)
    
    wdf = pd.read_sql("SELECT * FROM weather_data", engine)
    wdf["date"] = pd.to_datetime(wdf["date"])
    wdf["is_monsoon"] = wdf["date"].dt.month.isin([6,7,8,9])
    wdf.to_sql("weather_clean", engine, if_exists="replace", index=False)
    print("  ✅ Tables rebuilt.")

if __name__ == "__main__":
    backfill_weather(); backfill_traffic(); rebuild_clean()
