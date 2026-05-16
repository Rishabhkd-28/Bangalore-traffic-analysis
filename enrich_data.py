import os
import zipfile
import random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://postgres:prabhupada@localhost:5432/bangalore_traffic")

engine = create_engine(DB_URL)

def enrich_bmtc_stops():
    print("\n🚌 PART 1: Loading BMTC stops from GTFS zip…")
    zip_path = "bmtc_gtfs.zip"
    stops_df = None
    if os.path.exists(zip_path):
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                names = z.namelist()
                stop_file = next((n for n in names if n.endswith("stops.txt")), None)
                if stop_file:
                    with z.open(stop_file) as f:
                        stops_df = pd.read_csv(f)
                    print(f"  Loaded {len(stops_df)} stops from zip/{stop_file}")
        except Exception as e:
            print(f"  ⚠️  Could not read zip: {e}")

    if stops_df is None or len(stops_df) < 20:
        print("  Zip has <20 stops — using comprehensive Bangalore BMTC stop list…")
        stops_df = build_realistic_bmtc_stops()

    col_map = {}
    for c in stops_df.columns:
        lc = c.lower()
        if "lat" in lc:   col_map[c] = "latitude"
        elif "lon" in lc: col_map[c] = "longitude"
        elif "name" in lc:col_map[c] = "stop_name"
        elif "id" in lc:  col_map[c] = "stop_id"
    stops_df = stops_df.rename(columns=col_map)
    stops_df = stops_df[["stop_id", "stop_name", "latitude", "longitude"]].copy()
    stops_df["latitude"]  = pd.to_numeric(stops_df["latitude"],  errors="coerce")
    stops_df["longitude"] = pd.to_numeric(stops_df["longitude"], errors="coerce")
    stops_df.dropna(inplace=True)
    bbox = dict(lat_min=12.834, lat_max=13.141, lon_min=77.460, lon_max=77.800)
    stops_df = stops_df[
        stops_df["latitude"].between(bbox["lat_min"], bbox["lat_max"]) &
        stops_df["longitude"].between(bbox["lon_min"], bbox["lon_max"])
    ]
    stops_df["stop_name"] = stops_df["stop_name"].str.strip().str.title()
    stops_df.drop_duplicates(subset="stop_id", inplace=True)
    stops_df.reset_index(drop=True, inplace=True)
    stops_df.to_sql("bmtc_stops",       engine, if_exists="replace", index=False)
    stops_df.to_sql("bmtc_stops_clean", engine, if_exists="replace", index=False)
    print(f"  ✅ bmtc_stops_clean: {len(stops_df)} stops saved.")
    return stops_df

def build_realistic_bmtc_stops():
    corridors = [
        ("Outer Ring Road",                  12.9100, 77.5900, 12.9900, 77.7000, 40),
        ("Whitefield Road",                  12.9700, 77.6800, 12.9700, 77.7800, 25),
        ("Sarjapur Road",                    12.8600, 77.6700, 12.9400, 77.6800, 20),
        ("Bannerghatta Road",                12.8700, 77.5800, 12.9700, 77.5900, 25),
        ("Hosur Road",                       12.8300, 77.6600, 12.9500, 77.6600, 20),
        ("Old Madras Road",                  12.9800, 77.6300, 13.0000, 77.7000, 18),
        ("Tumkur Road",                      13.0000, 77.5000, 13.1000, 77.5200, 18),
        ("Bellary Road",                     13.0000, 77.5800, 13.1000, 77.6000, 18),
        ("Mysore Road",                      12.9500, 77.4700, 12.9600, 77.5700, 20),
        ("Electronics City Phase 1",         12.8200, 77.6600, 12.8600, 77.6700, 15),
    ]
    rows = []
    stop_id = 2000
    rng = np.random.default_rng(seed=99)
    for (prefix, lat_s, lon_s, lat_e, lon_e, n) in corridors:
        lats = np.linspace(lat_s, lat_e, n) + rng.uniform(-0.001, 0.001, n)
        lons = np.linspace(lon_s, lon_e, n) + rng.uniform(-0.001, 0.001, n)
        for i, (la, lo) in enumerate(zip(lats, lons)):
            rows.append({
                "stop_id":   stop_id,
                "stop_name": f"{prefix} Stop {i+1}",
                "latitude":  round(float(la), 6),
                "longitude": round(float(lo), 6),
            })
            stop_id += 1
    return pd.DataFrame(rows)

def enrich_accidents():
    print("\n🚨 PART 2: Generating 250 realistic accident records (2022–2025)…")
    HOTSPOTS = [
        ("Silk Board Junction",       12.9176, 77.6227, 0.15),
        ("Marathahalli Bridge",       12.9571, 77.7006, 0.12),
        ("Hebbal Flyover",            13.0450, 77.5943, 0.10),
        ("Outer Ring Road Bellandur", 12.9373, 77.6746, 0.10),
        ("KR Puram Junction",        13.0035, 77.6945, 0.08),
    ]
    VIOLATIONS = ["Speeding", "Signal Jumping", "Drunk Driving",
                  "Tailgating", "Lane Violation", "Illegal U-Turn",
                  "Phone Usage", "Wrong Side Driving"]
    SEVERITIES = ["Low", "Medium", "High", "Critical"]
    SEV_WEIGHTS = [0.40, 0.35, 0.18, 0.07]
    HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 3, 8, 9, 6, 4, 4, 4, 4, 4, 5, 7, 9, 8, 6, 4, 3, 2, 1]
    rng    = random.Random(42)
    nprng  = np.random.default_rng(42)
    start  = date(2022, 1, 1)
    end    = date(2025, 12, 31)
    days   = (end - start).days
    hotspot_names   = [h[0] for h in HOTSPOTS]
    hotspot_weights = [h[3] for h in HOTSPOTS]
    total_w         = sum(hotspot_weights)
    hotspot_weights = [w / total_w for w in hotspot_weights]
    hotspot_map     = {h[0]: (h[1], h[2]) for h in HOTSPOTS}
    rows = []
    for _ in range(250):
        acc_date = start + timedelta(days=rng.randint(0, days))
        hour     = rng.choices(range(24), weights=HOUR_WEIGHTS)[0]
        minute   = rng.randint(0, 59)
        location = rng.choices(hotspot_names, weights=hotspot_weights)[0]
        base_lat, base_lon = hotspot_map[location]
        lat = round(base_lat + nprng.uniform(-0.002, 0.002), 6)
        lon = round(base_lon + nprng.uniform(-0.002, 0.002), 6)
        severity = rng.choices(SEVERITIES, weights=SEV_WEIGHTS)[0]
        vehicles = rng.randint(1, 5)
        if severity == "Critical":
            fatalities = rng.randint(1, 3); injuries   = rng.randint(1, 4)
        elif severity == "High":
            fatalities = rng.randint(0, 1); injuries   = rng.randint(1, 3)
        elif severity == "Medium":
            fatalities = 0; injuries   = rng.randint(0, 2)
        else:
            fatalities = 0; injuries   = rng.randint(0, 1)
        casualties = fatalities + injuries
        rows.append({
            "date":           str(acc_date),
            "time":           f"{hour:02d}:{minute:02d}:00",
            "location":       location,
            "latitude":       lat,
            "longitude":      lon,
            "severity":       severity,
            "vehicles":       vehicles,
            "casualties":     casualties,
            "violation_type": rng.choice(VIOLATIONS),
            "fatalities":     fatalities,
            "injuries":       injuries,
        })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["hour"]  = df["time"].str[:2].astype(int)
    sev_map = {"Critical": 3, "High": 2, "Medium": 1, "Low": 0}
    df["severity_score"] = df["severity"].map(sev_map).fillna(0).astype(int)
    df.to_sql("accidents",       engine, if_exists="replace", index=False)
    df.to_sql("accidents_clean", engine, if_exists="replace", index=False)
    print(f"  ✅ accidents_clean: {len(df)} rows saved.")

if __name__ == "__main__":
    enrich_bmtc_stops()
    enrich_accidents()
