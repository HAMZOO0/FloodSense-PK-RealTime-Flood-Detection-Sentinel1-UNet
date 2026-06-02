import re

import requests
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
    print(f"[FFD] Fetching high-fidelity data from {URL}...", flush=True)

    try:
        res = requests.get(URL, headers=HEADERS, timeout=30)
        res.raise_for_status()
        html = res.text
    except Exception as e:
        print(f"❌ FFD Fetch Error: {e}")
        return []

    pattern = r"var\s+s\s*=\s*\{(.*?)\};"
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

    data = []
    for m in matches:
        def field(key):
            patterns = [
                rf'["\']?{key}["\']?\s*:\s*["\']([^"\']*)["\']',
                rf'["\']?{key}["\']?\s*:\s*([^,\n\}}\s]*)',
            ]
            for p in patterns:
                r = re.search(p, m)
                if r and r.group(1):
                    return r.group(1).strip()
            return None

        name = field("name") or "Unknown Station"
        status = field("status") or "NORMAL"
        river = field("area_name") or "Unknown River"
        recorded = field("recording_time") or "N/A"

        gauge_objects = re.findall(r"\{([^{}]+)\}", m)

        inflow = 0
        outflow = 0
        inflow_trend = "Steady"
        outflow_trend = "Steady"

        for obj_str in gauge_objects:
            def obj_field(key):
                pat = rf'["\']?{key}["\']?\s*:\s*["\']([^"\']*)["\']'
                res = re.search(pat, obj_str)
                return res.group(1) if res else None

            g_type = obj_field("type")
            g_disc = obj_field("discharge")
            g_trend = obj_field("trend")

            if not g_type:
                continue

            val = clean_num(g_disc)
            if g_type.upper() == "INFLOW":
                inflow = val
                inflow_trend = g_trend or "Steady"
            elif g_type.upper() == "OUTFLOW":
                outflow = val
                outflow_trend = g_trend or "Steady"

        std_status = "UNKNOWN"
        if status:
            s_up = status.upper()
            if "NORMAL" in s_up:
                std_status = "NORMAL"
            elif "HIGH" in s_up:
                std_status = "HIGH"
            elif "EXTREME" in s_up or "EX" in s_up:
                std_status = "EXTREME"

        data.append(
            {
                "station": name,
                "river": river,
                "inflow": inflow,
                "outflow": outflow,
                "status": std_status,
                "inflow_trend": inflow_trend,
                "outflow_trend": outflow_trend,
                "recorded": recorded,
            }
        )

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
