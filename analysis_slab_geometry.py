import sqlite3
import json
import math

def dist_sq(p1, p2):
    return (p1[0]-p2[0])**2 + (p1[1]-p2[1])**2

def point_to_segment_dist(p, s_start, s_end):
    # Projeção de p no segmento s_start-s_end
    lx, ly = s_end[0]-s_start[0], s_end[1]-s_start[1]
    l2 = lx*lx + ly*ly
    if l2 == 0: return dist_sq(p, s_start)**0.5
    
    t = ((p[0]-s_start[0])*lx + (p[1]-s_start[1])*ly) / l2
    t = max(0, min(1, t))
    proj = [s_start[0] + t*lx, s_start[1] + t*ly]
    return dist_sq(p, proj)**0.5

def analyze_geometry():
    db_path = "project_data.vision"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM projects WHERE name LIKE '%P-1%' OR pavement_name LIKE '%P-1%'")
    rows = cursor.fetchall()
    if not rows:
        print("Project P-1 not found")
        return
    
    pids = [r[0] for r in rows]
    query = f"SELECT name, links_json FROM slabs WHERE project_id IN ({','.join(['?']*len(pids))}) AND is_validated=1"
    cursor.execute(query, pids)
    
    slabs = cursor.fetchall()
    print(f"Analyzing {len(slabs)} validated slabs...\n")
    
    for s_name, links_json in slabs:
        links = json.loads(links_json) if links_json else {}
        outlines = links.get('laje_outline_segs', {})
        contour = outlines.get('contour', [])
        acrescimo = outlines.get('acrescimo_borda', [])
        
        if not contour or not acrescimo:
            continue
            
        print(f"--- Slab {s_name} ---")
        
        # Extract Points
        # Assuming single poly list for simplicity of analysis, usually item 0
        c_pts = contour[0].get('points', [])
        a_pts = acrescimo[0].get('points', [])
        
        if len(c_pts) < 2 or len(a_pts) < 2: continue
        
        # Analyze Acrescimo Segments vs Contour Segments
        # For each point in Acrescimo, find distance to closest Contour segment
        
        dists = []
        for p in a_pts:
            min_d = float('inf')
            for i in range(len(c_pts)):
                p1 = c_pts[i]
                p2 = c_pts[(i+1)%len(c_pts)]
                d = point_to_segment_dist(p, p1, p2)
                if d < min_d: min_d = d
            dists.append(min_d)
            
        if not dists: continue
        
        avg_dist = sum(dists)/len(dists)
        min_dist_found = min(dists)
        max_dist_found = max(dists)
        
        print(f"  Distances Acrescimo->Contour: Min={min_dist_found:.2f}, Max={max_dist_found:.2f}, Avg={avg_dist:.2f}")
        
        # Check alignment (Parallelism) logic would be here
        # Specifically checking the "5cm" rule
        # If segment is parallel, distance is constant ~10.
        # If diagonal, distance varies? Or is it a diagonal constant offset?
        
        # Let's verify coordinates directly for a few points
        print(f"  Sample Contour: {c_pts[:2]}...")
        print(f"  Sample Acrescimo: {a_pts[:2]}...")

    conn.close()

if __name__ == "__main__":
    analyze_geometry()
