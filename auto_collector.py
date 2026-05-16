import time, requests, pandas as pd
from datetime import datetime
from sqlalchemy import create_engine

TOMTOM_API_KEY = "F02Rqymm7NnxHDKTPHbAtOua1Uj0Y1rF"
DB_URL = "postgresql+psycopg2://postgres:prabhupada@localhost:5432/bangalore_traffic"
engine = create_engine(DB_URL)

JUNCTIONS = [
    (12.9716, 77.5946, "Silk Board"), (12.9352, 77.6245, "Marathahalli"),
    (12.9698, 77.7499, "Whitefield"), (12.9784, 77.6408, "Outer Ring Road KR Puram"),
    (12.9762, 77.6033, "Koramangala"), (12.9719, 77.5937, "HSR Layout"),
    (12.9856, 77.5533, "MG Road"), (13.0358, 77.5970, "Hebbal"),
    (12.9141, 77.6101, "BTM Layout"), (12.9902, 77.7172, "Mahadevapura"),
]

BASE_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

def fetch_traffic():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching traffic...")
    records = []
    for lat, lon, label in JUNCTIONS:
        params = {"key": TOMTOM_API_KEY, "point": f"{lat},{lon}", "unit": "KMPH"}
        try:
            r = requests.get(BASE_URL, params=params, timeout=10)
            r.raise_for_status()
            d = r.json().get("flowSegmentData", {})
            if not d: continue
            records.append({
                "junction_label": label, "latitude": lat, "longitude": lon,
                "fetched_at": datetime.now(), "current_speed": d.get("currentSpeed"),
                "free_flow_speed": d.get("freeFlowSpeed"), "current_travel_time": d.get("currentTravelTime"),
                "free_flow_travel_time": d.get("freeFlowTravelTime"), "confidence": d.get("confidence")
            })
            print(f"  ✅ {label}: {d.get('currentSpeed')} km/h")
        except Exception as e: print(f"  ⚠️  {label}: {e}")
    if records:
        pd.DataFrame(records).to_sql("traffic_speeds", engine, if_exists="append", index=False)
        print(f"✅ {len(records)} records saved.")

if __name__ == "__main__":
    fetch_traffic()
    while True:
        time.sleep(3600)
        fetch_traffic()
