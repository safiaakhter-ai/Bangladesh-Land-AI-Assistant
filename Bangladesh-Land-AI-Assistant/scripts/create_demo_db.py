"""Create a synthetic, clearly labeled demonstration database.

This is NOT a government record feed. Never use this data for title, ownership,
fee, legal or registration decisions. Generated only on an explicit command.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEMO_ROWS = [
    (1, "BS", "1", "নমুনা মৌজা", "ডেমো উপজেলা", "ডেমো জেলা", "কাল্পনিক ব্যক্তি এক", "101", "0.25 একর"),
    (2, "RS", "2", "নমুনা মৌজা", "ডেমো উপজেলা", "ডেমো জেলা", "কাল্পনিক ব্যক্তি দুই", "102", "0.50 একর"),
    (3, "CS", "3", "প্রশিক্ষণ মৌজা", "ডেমো উপজেলা", "ডেমো জেলা", "কাল্পনিক ব্যক্তি তিন", "103", "0.10 একর"),
    (4, "BS", "4", "প্রশিক্ষণ মৌজা", "ডেমো উপজেলা", "ডেমো জেলা", "কাল্পনিক ব্যক্তি চার", "104", "0.30 একর"),
]


def create_demo_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing database: {path}")
    try:
        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE khatian_index (
                    khatian_id INTEGER PRIMARY KEY,
                    jl_number_id INTEGER,
                    survey_name TEXT,
                    khatian_no TEXT,
                    fetched_detail INTEGER DEFAULT 1
                );
                CREATE TABLE khatian_details (
                    khatian_id INTEGER PRIMARY KEY,
                    jl_number_id INTEGER,
                    survey_name TEXT,
                    detail_json TEXT NOT NULL
                );
                CREATE TABLE plot_spatial_info (
                    mauza_code TEXT, plot_no TEXT, major_class TEXT,
                    sub_class TEXT, landuse_zone TEXT,
                    center_lat REAL, center_lon REAL
                );
                CREATE TABLE plot_polygons (
                    mauza_code TEXT, plot_no TEXT, geojson_geometry TEXT
                );
            """)
            for row_id, survey, number, mouza, upazila, district, owner, dag, area in DEMO_ROWS:
                details = {
                    "ID": row_id,
                    "KHATIAN_NO": number,
                    "SURVEY_NAME": survey,
                    "MOUZA_NAME": mouza,
                    "UPAZILA_NAME": upazila,
                    "DISTRICT_NAME": district,
                    "OWNERS": owner,
                    "DAGS": dag,
                    "TOTAL_LAND": area,
                    "DATA_SOURCE": "DEMO: synthetic educational record, not a government record",
                    "COMMENTS": "DEMO ONLY: Fictional details for UI testing. Not a real land record."
                }
                db.execute("INSERT INTO khatian_index VALUES (?,?,?,?,1)", (row_id, 1, survey, number))
                db.execute("INSERT INTO khatian_details VALUES (?,?,?,?)", (row_id, 1, survey, json.dumps(details, ensure_ascii=False)))
            db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "khatians.db")
    args = parser.parse_args()
    create_demo_db(args.output.resolve())
    print(f"Created four synthetic sample records at {args.output}. NOT REAL LAND RECORDS.")
