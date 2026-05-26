from dotenv import load_dotenv
load_dotenv()
import os

import requests
from bs4 import BeautifulSoup
import re


URL = os.getenv("Data_URL")

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def clean_num(text):
    if not text:
        return None
    match = re.findall(r"[\d,]+", text)
    return int(match[0].replace(",", "")) if match else None


def get_ffc_data():
    print("📡 Fetching FFC discharge page...")

    res = requests.get(URL, headers=HEADERS, timeout=20)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    rows = soup.find_all("tr")

    data = []
    current_station = None

    for row in rows:
        classes = row.get("class", [])

        # ───────── MAIN DATA ROW ─────────
        if "data-row" in classes:
            cols = row.find_all("td")

            if len(cols) < 2:
                continue

            station_text = cols[0].get_text(" ", strip=True)

            # extract station + river
            match = re.match(r"(.+)\((.+)\)", station_text)
            if match:
                station = match.group(1).strip()
                river = match.group(2).strip()
            else:
                station = station_text
                river = "Unknown"

            # check "Not Received"
            if "Not Received" in row.get_text():
                data.append({
                    "station": station,
                    "river": river,
                    "inflow": None,
                    "outflow": None,
                    "status": "NOT_RECEIVED"
                })
                current_station = None
                continue

            # inflow/outflow parsing
            inflow_text = cols[1].get_text(" ", strip=True)
            outflow_text = cols[2].get_text(" ", strip=True)

            inflow = clean_num(inflow_text)
            outflow = clean_num(outflow_text)

            # status detection
            status = "UNKNOWN"
            text = row.get_text().upper()
            if "NORMAL" in text:
                status = "NORMAL"
            elif "HIGH" in text:
                status = "HIGH"
            elif "EX_HIGH" in text:
                status = "EXTREME"

            current_station = {
                "station": station,
                "river": river,
                "inflow": inflow,
                "outflow": outflow,
                "status": status
            }

            data.append(current_station)

        # ───────── IGNORE cyp-row (metadata only) ─────────
        elif "cyp-row" in classes:
            continue

    return data


def main():
    data = get_ffc_data()

    print("\n🌊 FFC River Discharge Data\n")

    for d in data:
        print(
            f"{d['station']} ({d['river']}) → "
            f"Inflow: {d['inflow']} | Outflow: {d['outflow']} | Status: {d['status']}"
        )

    return data


if __name__ == "__main__":
    main()