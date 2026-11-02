import sqlite3
import json
import os

db_path = 'dlrms_records.db'
json_path = 'sample_records.json'

if not os.path.exists(json_path):
    print(f"Error: {json_path} not found.")
    exit(1)

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Ensure tables are initialized
# (Re-run table creation SQL from dlrms_scraper.py if not exists)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS survey_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mauza TEXT,
        sheet_number TEXT,
        dag_number TEXT,
        area REAL,
        owner_name TEXT,
        record_content TEXT,
        url TEXT UNIQUE,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS namjari_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mauza TEXT,
        khatian_number TEXT,
        dag_number TEXT,
        mutation_date TEXT,
        from_name TEXT,
        to_name TEXT,
        record_content TEXT,
        url TEXT UNIQUE,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS mouza_maps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        district TEXT,
        upazila TEXT,
        mauza TEXT,
        map_url TEXT,
        map_data TEXT,
        map_image_path TEXT,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Load sample data
with open(json_path, 'r', encoding='utf-8') as f:
    sample_records = json.load(f)

for record in sample_records:
    survey_type = record.get('survey_type')
    if survey_type in ['CS', 'RS', 'BS']:
        # Insert into survey_records
        cursor.execute('''
            INSERT OR IGNORE INTO survey_records 
            (mauza, sheet_number, dag_number, area, owner_name, record_content, url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.get('mauza'),
            record.get('sheet_number'),
            record.get('dag_number'),
            record.get('area_decimals'),
            record.get('owner_name'),
            record.get('record_content'),
            f"https://dlrms.land.gov.bd/survey/{record.get('sheet_number')}/{record.get('dag_number')}"
        ))
    elif survey_type == 'Namjari':
        # Insert into namjari_records
        cursor.execute('''
            INSERT OR IGNORE INTO namjari_records 
            (mauza, khatian_number, dag_number, mutation_date, from_name, to_name, record_content, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.get('mauza'),
            record.get('khatian_number'),
            record.get('dag_number'),
            record.get('mutation_date'),
            record.get('from_name'),
            record.get('to_name'),
            record.get('record_content'),
            f"https://dlrms.land.gov.bd/namjari/{record.get('khatian_number')}/{record.get('dag_number')}"
        ))

# Add a mock mouza map record
cursor.execute('''
    INSERT OR IGNORE INTO mouza_maps 
    (district, upazila, mauza, map_data)
    VALUES (?, ?, ?, ?)
''', (
    'Dhaka',
    'Gulshan',
    'Bhatara',
    json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[90.4244, 23.7936], [90.4300, 23.7936], [90.4300, 23.7980], [90.4244, 23.7980], [90.4244, 23.7936]]]
                },
                "properties": {
                    "mauza": "Bhatara",
                    "jl_no": "202"
                }
            }
        ]
    })
))

conn.commit()
conn.close()
print("Successfully populated SQLite database with sample records!")
