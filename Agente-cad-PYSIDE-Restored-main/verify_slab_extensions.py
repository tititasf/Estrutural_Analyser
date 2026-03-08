
import sys
import os

# Adjust path to find modules
sys.path.append(os.path.join(os.getcwd(), 'src'))

from shapely.geometry import Polygon, LineString, Point
from core.slab_tracer import SlabTracer
from core.spatial_index import SpatialIndex

def verify_extensions():
    print("🧪 Starting Generative Extension Verification (Continuous Chain Strategy)...")
    
    # 1. Setup Mock Spatial Index
    idx = SpatialIndex()
    tracer = SlabTracer(idx)
    
    # 2. Define Main Slab (100x100)
    # 0,0 -> 100,0 -> 100,100 -> 0,100
    main_poly = Polygon([(0,0), (100,0), (100,100), (0,100), (0,0)])
    
    # Insert Main Slab lines (walls/beams) as obstacles for inward rays
    main_lines = [
        LineString([(0,0), (100,0)]),
        LineString([(100,0), (100,100)]),
        LineString([(100,100), (0,100)]),
        LineString([(0,100), (0,0)])
    ]
    for l in main_lines:
        idx.insert({'points': list(l.coords), 'layer': 'EST_VIGA'}, l.bounds)

    
    # 4. Run Detection on Main Poly (Isolated)
    # Expectation: All 4 sides free -> 1 continuous chain (Ring) -> 1 Composite Polygon
    
    print("🕵️  Detecting extensions (Scenario: Isolated Slab)...")
    extensions = tracer.detect_extensions(main_poly)
    
    print(f"Extensions generated: {len(extensions)}")
    for i, e in enumerate(extensions):
        print(f"  Ext {i}: Type={e.get('type')} Side={e.get('side')} Pts={len(e['points'])}")

    if len(extensions) == 1:
        print("✅ Correctly generated 1 continuous Composite extension (Ring) for isolated slab.")
    else:
         print(f"⚠️ Generated {len(extensions)} separate extensions. Might indicate chain break or island logic mismatch.")


    print(f"\n--- Test Case 2: Blocked by Neighbor (Internal Edge) ---")
    # Add neighbor on the RIGHT (Leste)
    # Slab is 0,0 to 100,100. Right edge is x=100.
    # Neighbor: 105,0 to 205,100 (Gap=5). Block threshold=1000. Should be blocked.
    
    neighbor_poly = Polygon([(105, 0), (205, 0), (205, 100), (105, 100)]) 
    idx.insert({'points': list(neighbor_poly.exterior.coords), 'layer': 'wall'}, neighbor_poly.bounds)
    
    s2 = SlabTracer(idx)
    exts2 = s2.detect_extensions(main_poly)
    
    print(f"Extensions generated: {len(exts2)}")
    for i, e in enumerate(exts2):
        print(f"  Ext {i}: Type={e.get('type')} Side={e.get('side')}")
        
    # Expectation: Right blocked. Top, Left, Bottom Free.
    # Sequence: Top->Right(Blocked)->Bottom->Left
    # Should form ONE chain: Bottom->Left->Top (C-Shape).
    if len(exts2) == 1:
        print("✅ Correctly generated 1 continuous chain (C-Shape).")
    elif len(exts2) == 3:
         print("ℹ️ Generated 3 separate extensions (Chaining failed or separated).")
    else:
         print(f"❌ Unexpected count: {len(exts2)}")


    print(f"\n--- Test Case 3: Partial Obstacle (Column) ---")
    # Coluna perto da borda de baixo (Sul)
    # Sul edge: (100,0) -> (0,0). Mid=(50,0).
    # Coluna em (50, -9). Dist=9. Threshold=1000. Blocked.
    
    idx3 = SpatialIndex() 
    col_poly = Polygon([(45, -10), (55, -10), (55, -8), (45, -8)]) # Center ~ (50, -9)
    idx3.insert({'points': list(col_poly.exterior.coords), 'type': 'pillar'}, col_poly.bounds)
    
    s3 = SlabTracer(idx3)
    exts3 = s3.detect_extensions(main_poly)
    
    # Sul blocked. Right, Top, Left free.
    # Should again be a C-shape chain (Right->Top->Left).
    print(f"Extensions generated: {len(exts3)}")
    if len(exts3) == 1:
        print("✅ Correctly generated 1 continuous chain (C-Shape) avoiding blocked edge.")
    elif len(exts3) == 3:
         print("ℹ️ Generated 3 separate extensions.")
    else:
        print(f"❌ Unexpected count: {len(exts3)}")
        
if __name__ == "__main__":
    verify_extensions()
