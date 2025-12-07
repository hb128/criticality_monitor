#!/usr/bin/env python3
"""
Position history processor for tracking data.
Groups positions by device ID, deduplicates by timestamp, 
converts lat/lon from E7 format, and supports database storage.
"""

import json
import argparse
import sqlite3
import pandas as pd
import glob

def parse_position_files(input_pattern: str, db_path: str):
    """Save position data from JSON files (single file or wildcard pattern) into a sql database"""
    file_paths = glob.glob(input_pattern)        
    if not file_paths:
        raise FileNotFoundError(f"No JSON files found matching: {input_pattern}")
    print(f"Found {len(file_paths)} files: {input_pattern}")

    # Initialize database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            device_id TEXT,
            timestamp INTEGER,
            lat REAL,
            lon REAL,
            PRIMARY KEY (device_id, timestamp)
        )
    ''')

    all_positions = []
    for file_path in sorted(file_paths):
        with open(file_path, 'r') as f:
            data = json.load(f)
            for device_id, pos in data['locations'].items():
                all_positions.append((
                    device_id,
                    pos['timestamp'],
                    pos['latitude'] / 1e7,
                    pos['longitude'] / 1e7
                ))
    # Pandas bulk insert - PRIMARY KEY auto-deduplicates
    chunk_size = 100
    for i in range(0, len(all_positions), chunk_size):
        chunk = all_positions[i:i + chunk_size]
        cursor.executemany('''
            INSERT OR IGNORE INTO positions 
            (device_id, timestamp, lat, lon) 
            VALUES (?, ?, ?, ?)
        ''', chunk)
        print(f"  Inserted chunk {i//chunk_size + 1}: {len(chunk)} rows")
    conn.commit()
    conn.close()

    # Count final result
    final_count = pd.read_sql_query("SELECT COUNT(*) as count FROM positions", sqlite3.connect(db_path))['count'][0]
    print(f"{len(all_positions):,} raw → {final_count:,} unique (SQLite deduplicated)")

def main():
    parser = argparse.ArgumentParser(description='Convert position history JSON files to database')
    parser.add_argument('input_files', help='JSON files with locations')    
    parser.add_argument('output_database', help='SQLITE database')
    args = parser.parse_args()
    
    parse_position_files(args.input_files,args.output_database)

if __name__ == "__main__":
    main()
