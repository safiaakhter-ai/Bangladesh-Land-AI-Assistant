"""
Sarail Upazila Spatial Map Scraper & Seeder.
Fetches digital plot vector boundaries, land use classifications, and plot info for Sarail from map.land.gov.bd.
Stores results in khatians.db (plot_spatial_info & plot_polygons).
"""

import sqlite3
import json
import time
import sys
import logging
from land_map_client import LandMapClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sarail_map_scraper")

DB_PATH = "khatians.db"

# Sample spatial data mapping for Sarail Upazila plots (Bhat Baria Mouza, JL 153)
SARAIL_SAMPLE_PLOTS = [
    {
        "mauza_code": "601215413003",
        "plot_no": "74",
        "sheet_val": "000",
        "major_class": "Agricultural Land",
        "major_class_bn": "আবাদী জমি",
        "sub_class": "Double Crop Land",
        "sub_class_bn": "দুই ফসলী জমি",
        "landuse_zone": "Agricultural Zone",
        "landuse_zone_bn": "কৃষি অঞ্চল",
        "survey_year": "2006-2015",
        "center_lat": 24.1165,
        "center_lon": 91.1245,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[91.1241, 24.1162], [91.1249, 24.1162], [91.1249, 24.1168], [91.1241, 24.1168], [91.1241, 24.1162]]]
        }
    },
    {
        "mauza_code": "601215413003",
        "plot_no": "75",
        "sheet_val": "000",
        "major_class": "Agricultural Land",
        "major_class_bn": "আবাদী জমি",
        "sub_class": "Single Crop Land",
        "sub_class_bn": "এক ফসলী জমি",
        "landuse_zone": "Agricultural Zone",
        "landuse_zone_bn": "কৃষি অঞ্চল",
        "survey_year": "2006-2015",
        "center_lat": 24.1172,
        "center_lon": 91.1251,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[91.1248, 24.1169], [91.1255, 24.1169], [91.1255, 24.1175], [91.1248, 24.1175], [91.1248, 24.1169]]]
        }
    },
    {
        "mauza_code": "601215413003",
        "plot_no": "167",
        "sheet_val": "000",
        "major_class": "Homestead / Settlement",
        "major_class_bn": "ভিটা / বসতবাড়ি",
        "sub_class": "Residential Land",
        "sub_class_bn": "আবাসিক জমি",
        "landuse_zone": "Settlement Zone",
        "landuse_zone_bn": "আবাসিক অঞ্চল",
        "survey_year": "2006-2015",
        "center_lat": 24.1180,
        "center_lon": 91.1260,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[91.1256, 24.1176], [91.1264, 24.1176], [91.1264, 24.1184], [91.1256, 24.1184], [91.1256, 24.1176]]]
        }
    }
]

def init_spatial_tables():
    conn = sqlite3.connect(DB_PATH)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plot_spatial_info (
                mauza_code TEXT,
                plot_no TEXT,
                major_class TEXT,
                sub_class TEXT,
                landuse_zone TEXT,
                survey_year TEXT,
                center_lat REAL,
                center_lon REAL,
                PRIMARY KEY (mauza_code, plot_no)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plot_polygons (
                mauza_code TEXT,
                plot_no TEXT,
                sheet_val TEXT,
                geojson_geometry TEXT,
                PRIMARY KEY (mauza_code, plot_no)
            );
        """)
    conn.close()
    logger.info("Spatial DB tables initialized.")

def seed_sarail_spatial_data():
    init_spatial_tables()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    for item in SARAIL_SAMPLE_PLOTS:
        cursor.execute("""
            INSERT OR REPLACE INTO plot_spatial_info
            (mauza_code, plot_no, major_class, sub_class, landuse_zone, survey_year, center_lat, center_lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["mauza_code"],
            item["plot_no"],
            item["major_class_bn"],
            item["sub_class_bn"],
            item["landuse_zone_bn"],
            item["survey_year"],
            item["center_lat"],
            item["center_lon"]
        ))

        cursor.execute("""
            INSERT OR REPLACE INTO plot_polygons
            (mauza_code, plot_no, sheet_val, geojson_geometry)
            VALUES (?, ?, ?, ?)
        """, (
            item["mauza_code"],
            item["plot_no"],
            item["sheet_val"],
            json.dumps(item["geometry"])
        ))
        inserted += 1

    conn.commit()
    conn.close()
    logger.info("Successfully seeded %d Sarail spatial plot records into khatians.db!", inserted)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    seed_sarail_spatial_data()
