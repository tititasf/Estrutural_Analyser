import sys
import os
import time

# Path fix
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.dxf_loader import DXFLoader
from src.core.geometry_engine import GeometryEngine, ShapeType
from src.core.spatial_index import SpatialIndex
from src.core.text_associator import TextAssociator
from src.core.beam_walker import BeamWalker

def run_pipeline(filepath: str):
    start_time = time.time()
    print(f"--- Pipeline Vision-Estrutural: {filepath} ---")
    
    # 1. Carregar DXF
    loader = DXFLoader(filepath)
    if not loader.load():
        print("Falha no carregamento.")
        return
    print(f"DXF Carregado em {time.time() - start_time:.2f}s")
    print(loader.get_stats())

    # 2. Indexação Espacial Total
    print("\n--- Indexando Entidades ---")
    idx_polys = SpatialIndex() # Pilares
    idx_beams = SpatialIndex() # Para BeamWalker conflitos
    
    # Indexar Polilinhas (Pilares Candidatos)
    for poly in loader.entities['polylines']:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        if xs:
            bounds = (min(xs), min(ys), max(xs), max(ys))
            idx_polys.insert(poly, bounds)
            idx_beams.insert(poly, bounds) # Pilares são obstaculos para vigas
            
    # Indexar Linhas (Paredes/Vigas)
    for line_start, line_end in loader.entities['lines']:
        bounds = (
            min(line_start[0], line_end[0]), min(line_start[1], line_end[1]),
            max(line_start[0], line_end[0]), max(line_start[1], line_end[1])
        )
        idx_beams.insert((line_start, line_end), bounds) # Tupla de 2 pts = Linha
        
    print(f"Indexação concluída em {time.time() - start_time:.2f}s total")

    # 3. Processar Pilares e Associar Textos
    print("\n--- Processando Pilares ---")
    texts_data = loader.entities['texts']
    associator = TextAssociator(None, texts_data) # Spatial index opcional no associator por enquanto
    
    pillars_found = []
    
    polylines = loader.entities['polylines']
    for i, poly in enumerate(polylines):
        # Classificar
        shape = GeometryEngine.classify_shape(poly)
        if shape != ShapeType.UNKNOWN:
            # Associar Texto
            # Para usar associator, precisamos converter poly pontos para Shapely Polygon
            # Isso é feito dentro do associator se passarmos objeto shapely, 
            # ou aqui. GeometryEngine já valida polygon.
            from shapely.geometry import Polygon
            try:
                poly_shape = Polygon(poly)
                if not poly_shape.is_valid: poly_shape = poly_shape.buffer(0)
                
                name, score = associator.find_associated_text(poly_shape)
                
                # Mapear Lados
                sides = GeometryEngine.map_sides(shape, 0, poly)
                
                if score > 0.4: # Filtro de confiança
                    pillars_found.append({
                        'id': i,
                        'type': shape.value,
                        'name': name or "Sem Nome",
                        'score': score
                    })
            except Exception as e:
                pass

    print(f"Pilares Identificados: {len(pillars_found)}")
    # Mostrar top 5
    for p in pillars_found[:5]:
        print(f"  Pilar {p['name']} ({p['type']}) - Score: {p['score']:.2f}")

    # 4. Processar Vigas (Exemplo Beam Walker)
    print("\n--- Teste Beam Walker (Heurística) ---")
    walker = BeamWalker(idx_beams)
    
    # Heurística: Encontrar textos que começam com 'V' e tentar achar linhas paralelas próximas
    # Simplificação: Pegar textos 'V...' e buscar linhas longas perto
    beam_count = 0
    for txt in texts_data:
        content = txt['text'].upper().strip()
        if content.startswith('V') and len(content) < 6: # Ex: V1, V20
            # Tentar achar eixo?
            # Por enquanto, apenas validar que o Walker roda se dermos pontos ficticios perto do texto
            # Simulando um eixo horizontal passando pelo texto
            cx, cy = txt['pos']
            start_pt = (cx - 50, cy)
            end_pt = (cx + 50, cy)
            
            result = walker.walk(start_pt, end_pt)
            if result['conflicts_count'] > 0:
                # print(f"  Viga {content}: {result['conflicts_count']} conflitos detectados no eixo estimado.")
                beam_count += 1
                if beam_count > 5: break # Limitar output

    # 5. Processar Lajes (Slab Tracer)
    print("\n--- Teste Slab Tracer ---")
    from src.core.slab_tracer import SlabTracer
    tracer = SlabTracer(idx_beams) # Reusa index de vigas/paredes
    
    slab_count = 0
    for txt in texts_data:
        content = txt['text'].lower().strip()
        # Heurística: começa com 'l' seguido de numero, ou tem 'h='
        if content.startswith('l') and len(content) < 5 and any(c.isdigit() for c in content):
             poly = tracer.trace_boundary(txt['pos'], search_radius=500.0) # Raio grande
             if poly:
                 print(f"  Laje {txt['text']} detectada! Área: {poly.area:.2f}")
                 slab_count += 1
                 if slab_count > 5: break

    print(f"Tempo Total: {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    dxf_path = os.path.join("c:\\Users\\Ryzen\\Desktop\\GITHUB\\Agente-cad-PYSIDE", "ESTRUTURAL.dxf")
    run_pipeline(dxf_path)
