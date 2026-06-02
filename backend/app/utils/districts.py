"""
districts.py
------------
Loops over each district in the GeoJSON (or shapefile),
clips the flood mask, and calculates flood inundation %.
Supports: .json, .geojson, .shp
"""

import ee
import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

from .ndwi import get_flood_mask

SCALE = 100
MAX_PIXELS = 1e10


def shapely_to_ee(geom):
    return ee.Geometry(mapping(geom))


def flood_percent_for_district(district_geom: ee.Geometry, flood_mask: ee.Image) -> float:
    try:
        stats = flood_mask.reduceRegion(
            reducer=ee.Reducer.sum().combine(reducer2=ee.Reducer.count(), sharedInputs=True),
            geometry=district_geom,
            scale=SCALE,
            maxPixels=MAX_PIXELS,
        )

        flood_pixels = stats.get("new_flood_sum")
        total_pixels = stats.get("new_flood_count")
        f_val = flood_pixels.getInfo() if flood_pixels is not None else 0
        t_val = total_pixels.getInfo() if total_pixels is not None else 0
        f_val = float(f_val) if f_val is not None else 0.0
        t_val = float(t_val) if t_val is not None else 0.0

        if f_val > 0:
            print(f"    📈 Found {f_val} flood pixels out of {t_val}")

        pct = (f_val / t_val) * 100 if t_val > 0 else 0.0
        return round(pct, 4)
    except Exception as e:
        print(f"    ⚠ Error computing pct: {e}")
        return 0.0


def detect_name_column(gdf: gpd.GeoDataFrame) -> str:
    candidates = [
        "districts",
        "DISTRICTS",
        "district",
        "DISTRICT",
        "NAME_2",
        "name_2",
        "NAME",
        "name",
        "ADM2_EN",
        "adm2_en",
        "DIST_NAME",
        "dist_name",
        "District_N",
    ]
    for col in candidates:
        if col in gdf.columns:
            print(f"  ✅ Using column '{col}' for district names")
            return col

    for col in gdf.columns:
        if col != "geometry" and gdf[col].dtype == object:
            print(f"  ⚠ Guessing column '{col}' for district names")
            return col

    return None


PRIORITY_DISTRICTS = [
    "Swat",
    "Shangla",
    "Kanju",
    "Mingora",
    "Kalam",
    "Behrain",
    "Charsadda",
    "Nowshera",
    "Peshawar",
    "Dera Ismail Khan",
    "Rajanpur",
    "Dera Ghazi Khan",
    "Muzaffargarh",
    "Layyah",
    "Sukkur",
    "Larkana",
    "Shikarpur",
    "Jacobabad",
    "Kashmore",
    "Jafferabad",
    "Naseerabad",
]


def compute_district_flood(file_path: str) -> pd.DataFrame:
    print(f"📂 Loading file: {file_path}")
    gdf = gpd.read_file(file_path)
    print(f"   Total districts in file: {len(gdf)}")

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    name_col = detect_name_column(gdf)

    if name_col:
        mask = gdf[name_col].apply(lambda x: any(p.lower() in str(x).lower() for p in PRIORITY_DISTRICTS))
        gdf = gdf[mask].copy()
        print(f"🎯 Filtered to {len(gdf)} priority districts.")

    pakistan_bbox = ee.Geometry.BBox(60.0, 23.0, 77.5, 37.5)
    flood_mask, _, _ = get_flood_mask(pakistan_bbox)

    records = []
    total = len(gdf)

    for i, row in gdf.iterrows():
        name = row[name_col] if name_col else str(i)
        print(f"[{i + 1}/{total}] Processing: {name}")

        try:
            ee_geom = shapely_to_ee(row.geometry)
            pct = flood_percent_for_district(ee_geom, flood_mask)
            print(f"  → flood: {pct:.4f}%")
        except Exception as e:
            print(f"  ⚠ Skipped {name}: {e}")
            pct = None

        records.append({"district": name, "flood_pct": pct, "geometry": row.geometry})

    return pd.DataFrame(records)
