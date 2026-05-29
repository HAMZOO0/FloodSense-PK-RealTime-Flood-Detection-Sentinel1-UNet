import requests
import re
import json
from dotenv import load_dotenv

load_dotenv()

URL = "https://ffd.pmd.gov.pk/river-state"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def clean_num(text):
    if not text:
        return 0
    match = re.findall(r"[\d,]+", text)
    return int(match[0].replace(",", "")) if match else 0

def get_ffc_data():
    """
    Scrapes official FFD live data by parsing embedded JavaScript station objects.
    Provides discharge, status, trends, and timestamps.
    """
    print(f"[FFD] Fetching high-fidelity data from {URL}...", flush=True)
    
    try:
        res = requests.get(URL, headers=HEADERS, timeout=30)
        res.raise_for_status()
        html = res.text
    except Exception as e:
        print(f"❌ FFD Fetch Error: {e}")
        return []

    # Extract all station blocks: var s = { ... };
    pattern = r'var s = \{(.*?)\};'
    matches = re.findall(pattern, html, re.DOTALL)

    data = []
    for m in matches:
        def field(key):
            # Handles both "key": and key: (unquoted keys in JS objects)
            r = re.search(rf'["\']?{key}["\']?:\s*["\']([^"\']*)["\']', m)
            return r.group(1) if r else None

        name      = field("name")
        status    = field("status")
        river     = field("area_name")
        recorded  = field("recording_time")

        # Parse gauges array for Inflow/Outflow and Trends
        # Format: {type:"OUTFLOW",discharge:"43,700",trend:"Falling"}
        gauges_raw = re.findall(
            r'\{["\']?type["\']?:\s*["\']([^"\']*)["\']\s*,\s*["\']?discharge["\']?:\s*["\']([^"\']*)["\']\s*,\s*["\']?trend["\']?:\s*["\']([^"\']*)["\']',
            m
        )
        
        inflow = 0
        outflow = 0
        inflow_trend = "Steady"
        outflow_trend = "Steady"

        for g_type, g_disc, g_trend in gauges_raw:
            val = clean_num(g_disc)
            if g_type.upper() == "INFLOW":
                inflow = val
                inflow_trend = g_trend
            elif g_type.upper() == "OUTFLOW":
                outflow = val
                outflow_trend = g_trend

        # Normalize status to match dashboard expectations
        std_status = "UNKNOWN"
        if status:
            s_up = status.upper()
            if "NORMAL" in s_up: std_status = "NORMAL"
            elif "HIGH" in s_up: std_status = "HIGH"
            elif "EXTREME" in s_up or "EX" in s_up: std_status = "EXTREME"

        data.append({
            "station": name,
            "river": river,
            "inflow": inflow,
            "outflow": outflow,
            "status": std_status,
            "inflow_trend": inflow_trend,
            "outflow_trend": outflow_trend,
            "recorded": recorded
        })

    return data

def main():
    data = get_ffc_data()
    print(f"\n🌊 FFD High-Fidelity River Data ({len(data)} stations)\n")
    for d in data:
        print(
            f"{d['station']} ({d['river']}) → "
            f"Inflow: {d['inflow']} ({d['inflow_trend']}) | "
            f"Outflow: {d['outflow']} ({d['outflow_trend']}) | "
            f"Status: {d['status']}"
        )
    return data

if __name__ == "__main__":
    main()