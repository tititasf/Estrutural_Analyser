
import sqlite3
import json
import os

DB_PATH = "project_data.vision"

def analyze_layers():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if we have 'slabs' and if they have points_json with layer info
    # Actually, spatial index is in memory usually, but raw data is in 'projects' or separate tables.
    # Where does the DXF data live? 'dxf_loader' loads from file. 
    # 'main.py' loads DXF and feeds spatial_index.
    # The database might store 'slabs' but maybe not raw lines/layers unless we saved them.
    # checking 'beams' or 'pillars' might give clues, but raw drawing layers might only be in the DXF file.
    
    # Wait, 'slabs' table has 'points_json'.
    print("Checking 'slabs' table...")
    try:
        cursor.execute("SELECT points_json FROM slabs LIMIT 5")
        rows = cursor.fetchall()
        for i, row in enumerate(rows):
            print(f"Slab {i}: {row[0][:100]}...")
    except Exception as e:
        print(f"Error reading slabs: {e}")

    # Look for any table that might store raw entities or layer names.
    # If not, I rely on the file 'main.py' logic.
    
    print("\nSince I cannot access the live RAM spatial_index, and raw DXF entities might not be in DB:")
    print("I will assume typical layer names and make the Ray Caster configurable.")
    
    conn.close()

if __name__ == "__main__":
    analyze_layers()
