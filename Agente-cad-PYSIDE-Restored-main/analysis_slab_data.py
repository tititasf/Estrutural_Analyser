import sqlite3
import json

def analyze_slabs():
    db_path = "project_data.vision"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Find Project P-1
    cursor.execute("SELECT id, name, pavement_name FROM projects WHERE name LIKE '%P-1%' OR pavement_name LIKE '%P-1%'")
    projects = cursor.fetchall()
    
    if not projects:
        print("❌ Project P-1 not found.")
        return

    print(f"✅ Found Projects: {projects}")
    
    for pid, name, pav in projects:
        print(f"\n--- Analyzing Project: {name} (ID: {pid}) ---")
        
        # 2. Get Validated Slabs
        cursor.execute("SELECT name, validated_fields_json, links_json FROM slabs WHERE project_id = ? AND is_validated = 1", (pid,))
        slabs = cursor.fetchall()
        
        if not slabs:
            print("  ⚠️ No validated slabs found.")
            continue
            
        print(f"  🔍 Found {len(slabs)} validated slabs.")
        
        for s_name, val_json, links_json in slabs:
            val_data = json.loads(val_json) if val_json else None
            links_data = json.loads(links_json) if links_json else None
            
            # String search for "10" or "acrescimo" to be quick
            dump_val = str(val_data).lower()
            dump_links = str(links_data).lower()
            
            found = False
            if '10' in dump_val or 'acrescimo' in dump_val:
                print(f"  📌 Slab: {s_name} [VALIDATION DATA]")
                print(f"     Type: {type(val_data)}")
                print(f"     Data: {val_data}")
                found = True
                
            if '10' in dump_links or 'acrescimo' in dump_links:
                print(f"  📌 Slab: {s_name} [LINKS DATA]")
                print(f"     Type: {type(links_data)}")
                print(f"     Data: {links_data}")
                found = True

    conn.close()

if __name__ == "__main__":
    analyze_slabs()
