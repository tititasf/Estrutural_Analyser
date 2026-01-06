import sys
import os

# Adicionar raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.dxf_loader import DXFLoader
from src.core.geometry_engine import GeometryEngine, ShapeType

def validate_dxf(filepath: str):
    print(f"--- Iniciando Validação: {filepath} ---")
    
    loader = DXFLoader(filepath)
    if not loader.load():
        print("Erro: Falha ao carregar DXF")
        return

    print("DXF Carregado.")
    print(loader.get_stats())
    
    polylines = loader.entities['polylines']
    print(f"\nAnalisando {len(polylines)} polilinhas...")
    
    counts = {t.value: 0 for t in ShapeType}
    samples = {t.value: [] for t in ShapeType}

    for i, poly in enumerate(polylines):
        shape_type = GeometryEngine.classify_shape(poly)
        counts[shape_type.value] += 1
        
        # Guardar amostras para inspeção detalhada
        if len(samples[shape_type.value]) < 3:
            sides = GeometryEngine.map_sides(shape_type, 0, poly)
            samples[shape_type.value].append({
                'id': i,
                'sides': sides,
                'first_pt': poly[0]
            })

    print("\n--- Resultado da Classificação ---")
    for type_name, count in counts.items():
        print(f"{type_name}: {count}")
        if count > 0:
            print(f"  Amostras: {samples[type_name]}")

if __name__ == "__main__":
    dxf_path = os.path.join("c:\\Users\\Ryzen\\Desktop\\GITHUB\\Agente-cad-PYSIDE", "ESTRUTURAL.dxf")
    validate_dxf(dxf_path)
