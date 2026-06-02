"""
export.py
---------
Saves district flood results to CSV.
"""

import os

import pandas as pd

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_csv(df: pd.DataFrame, out_path: str = "outputs/flood_results.csv"):
    csv_df = df[["district", "flood_pct"]].copy()
    csv_df = csv_df.sort_values("flood_pct", ascending=False).reset_index(drop=True)
    csv_df.to_csv(out_path, index=False)
    print(f"✅ CSV saved → {out_path}")
    print(csv_df.head(10).to_string(index=False))
