
import sys
import os

# Adjust path to find modules
sys.path.append(os.path.join(os.getcwd(), 'src'))

from shapely.geometry import Polygon, LineString, Point
from core.slab_tracer import SlabTracer
from core.spatial_index import SpatialIndex

def verify_extensions():
    print("🧪 Starting Generative Extension Verification...")
    
    # 1. Setup Mock Spatial Index
    idx = SpatialIndex()
    tracer = SlabTracer(idx)
    
    # 2. Define Main Slab (100x100)
    # 0,0 -> 100,0 -> 100,100 -> 0,100
    main_poly = Polygon([(0,0), (100,0), (100,100), (0,100), (0,0)])
    
    # We DO NOT insert extension geometry anymore. We check if it is GENERATED.
    # But we need to insert the Main Slab geometry into the index so rays don't hit "phantom" self?
    # Actually, detect_extensions Ray Cast starts 1cm OUTSIDE.
    # To test "blocking", we insert obstacles. To test "success", we leave it empty.
    
    # Insert Main Slab lines (walls/beams) as obstacles for inward rays (though we cast outward)
    # Just to be realistic, assume there are walls on the perimeter.
    main_lines = [
        LineString([(0,0), (100,0)]),
        LineString([(100,0), (100,100)]),
        LineString([(100,100), (0,100)]),
        LineString([(0,100), (0,0)])
    ]
    for l in main_lines:
        idx.insert({'points': list(l.coords), 'layer': 'EST_VIGA'}, l.bounds)

    
    # 4. Run Detection on Main Poly
    # Expectation: All 4 sides open -> 4 extensions generated?
    # Or just specific sides? The loop runs for ALL edges.
    # If the index is empty outside, it should generate 4 extensions.
    
    print("🕵️  Detecting extensions (Scenario: Isolated Slab)...")
    extensions = tracer.detect_extensions(main_poly)
    
    if len(extensions) == 4:
         print(f"✅ Correctly generated 4 extensions for isolated slab.")
    else:
         print(f"❌ Unexpected count: {len(extensions)} (Expected 4).")
         for e in extensions: print(f"  - {e['side']} Area={Polygon(e['points']).area}")

    if extensions:
        ext = extensions[0]
        # Check Width
        if 9.9 <= ext['width_est'] <= 10.1:
            print("✅ Width is strictly 10.0 (Generative).")
        else:
            print(f"❌ Width {ext['width_est']} != 10.0")

    
    print("\n--- Test Case 2: Blocked by Neighbor (Internal Edge) ---")
    # Add a neighbor slab explicitly blocking the Right Edge (x=100)
    # Neighbor: 100,0 -> 200,0 ...
    neighbor_wall = LineString([(105, 0), (105, 100)]) # 5cm away. Should BLOCK.
    idx.insert({'points': list(neighbor_wall.coords), 'layer': 'EST_VIGA'}, neighbor_wall.bounds)
    
    print("🕵️  Detecting extensions (Scenario: Right Edge Blocked)...")
    extensions_blocked = tracer.detect_extensions(main_poly)
    
    # Expect: 3 extensions (Top, Bottom, Left). Right is blocked.
    # Right edge is (100,0)->(100,100). Normal (1,0). Ray hits (105,y). Dist 5. Blocked < 200.
    
    right_exts = [e for e in extensions_blocked if e['side'] == 'Leste'] # Leste = Right?
    # Normal (1,0) -> atan2(0,1) = 0. 
    # Logic: 225-315(Sul), 45-135(Norte), 135-225(Oeste). Else Leste.
    # So 0 is Leste. Correct.
    
    if len(right_exts) == 0:
        print("✅ Right edge correctly BLOCKED by neighbor.")
    else:
        print(f"❌ FAILED: Right edge generated extension despite obstacle! {right_exts}")
        
    print(f"   Total extensions: {len(extensions_blocked)} (Expected 3)")


    print("\n--- Test Case 3: Partial Obstacle (Column) ---")
    # If there is a small column, does it block the whole edge?
    # The Ray Cast logic uses 3 rays (-10, 0, 10).
    # If ANY ray hits, what happens? 
    # Current Code: "If is_blocked: continue". 
    # is_blocked becomes True if ANY ray hits geometry < Threshold.
    # So a single column blocks the whole edge. 
    # This might be too strict? But consistent with "Void" check.
    
    # Let's test bottom edge (y=0). (0,0)->(100,0). Normal (0,-1) -> Sul (270).
    # Obstacle at y=-10, x=50. (Small column).
    column = Polygon([(45,-10), (55,-10), (55,-20), (45,-20)])
    idx.insert({'points': list(column.exterior.coords), 'layer': 'PILAR'}, column.bounds)
    
    print("🕵️  Detecting extensions (Scenario: Bottom Edge w/ Column)...")
    exts_col = tracer.detect_extensions(main_poly)
    
    # Check "Sul"
    sul_exts = [e for e in exts_col if e['side'] == 'Sul']
    
    if len(sul_exts) == 0:
        print("ℹ️  Bottom edge blocked by column (Strict Check).")
    else:
        print("ℹ️  Bottom edge NOT blocked by column (Rays passed around?).")
        # Ray angles: 0 (straight), -10, +10.
        # Midpoint x=50. Straight ray hits column. Blocked.
        # So expected is Blocked.

if __name__ == "__main__":
    verify_extensions()
