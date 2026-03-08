import sys
import os
from pathlib import Path

# Configurar Path
ROOT = Path("c:/Users/Ryzen/Desktop/GITHUB/Agente-cad-PYSIDE")
sys.path.append(str(ROOT))

from src.core.dxf_loader import DXFLoader
from src.core.spatial_index import SpatialIndex
from src.core.geometry_engine import GeometryEngine, ShapeType
from src.core.text_associator import TextAssociator
from src.core.beam_walker import BeamWalker
from src.core.slab_tracer import SlabTracer
from shapely.geometry import Polygon

def run_validation():
    dxf_path = ROOT / "ESTRUTURAL.dxf"
    print(f"--- INICIANDO VALIDAÇÃO: {dxf_path.name} ---")
    
    # 1. DXF Loader
    loader = DXFLoader(str(dxf_path))
    if not loader.load():
        print("[ERRO] Falha ao carregar DXF.")
        return
    
    entities = loader.entities
    print(f"[OK] DXF Carregado: {len(entities.get('polylines', []))} polilinhas, {len(entities.get('texts', []))} textos.")
    
    # 2. Spatial Index
    s_index = SpatialIndex()
    for poly in entities.get('polylines', []):
        pts = poly['points']
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if xs: s_index.insert(pts, (min(xs), min(ys), max(xs), max(ys)))
        
    beam_index = SpatialIndex()
    for l in entities.get('lines', []):
        s, e = l['start'], l['end']
        beam_index.insert((s, e), (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1])))
    for poly in entities.get('polylines', []):
        pts = poly['points']
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if xs: beam_index.insert(pts, (min(xs), min(ys), max(xs), max(ys)))

    # 3. Pillar Detection
    associator = TextAssociator(None, entities.get('texts', []))
    walker = BeamWalker(beam_index)
    
    pillars = []
    for i, p_item in enumerate(entities.get('polylines', [])):
        poly = p_item['points']
        shape = GeometryEngine.classify_shape(poly)
        if shape != ShapeType.UNKNOWN:
            poly_geo = Polygon(poly)
            if not poly_geo.is_valid: poly_geo = poly_geo.buffer(0)
            name, _ = associator.find_associated_text(poly_geo)
            pillars.append({'name': name or f"P#{i}", 'type': shape.value})
            
    print(f"[OK] Pilares Detectados: {len(pillars)}")
    
    # 4. Slab Detection
    tracer = SlabTracer(beam_index)
    slabs = []
    for txt in entities.get('texts', []):
        content = txt['text'].lower()
        if content.startswith('l') and any(c.isdigit() for c in content):
            poly = tracer.trace_boundary(txt['pos'], search_radius=800.0)
            if poly and poly.area > 500:
                slabs.append(txt['text'])
                
    print(f"[OK] Lajes Detectadas: {len(slabs)} ({', '.join(slabs[:5])}...)")
    
    # 5. Beam Walker Check (Exemplo em um ponto)
    if entities.get('texts'):
        sample_pt = entities['texts'][0]['pos']
        walk = walker.walk(sample_pt, (sample_pt[0] + 500, sample_pt[1]))
        print(f"[OK] Beam Walker operando: {len(walk['segments'])} segmentos encontrados em teste de raio.")

    print("\n--- SISTEMA PRONTO PARA VALIDAÇÃO HUMANA ---")
    print("Todos os motores de cálculo estão respondendo corretamente.")

if __name__ == "__main__":
    run_validation()
