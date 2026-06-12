#!/usr/bin/env python3
"""
Extract detailed geometry from STOG DXF file for vigas V4, V5, V6, V7
"""

import ezdxf
from collections import defaultdict
import sys

# DXF file path
DXF_FILE = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_16\Fase-1_Ingestao\Projetos_Finalizados_para_Engenharia_Reversa\NOVA-TRISUL-VALDIR NIEMEYER-1PV-LV-R00_R2018_ASCII_ODA.dxf"

# Known text positions for vigas
KNOWN_POSITIONS = {
    'V4': {'A': 32565, 'B': 32377},
    'V5': {'A': 32814, 'B': 32471},
    'V7': {'A': 32536, 'B': 32302},
}

# Y range for searching
SEARCH_Y_RANGE = 200

def extract_lwpolyline_bounds(entity):
    """Extract min/max X and Y from LWPOLYLINE entity"""
    points = [point[:2] for point in entity.get_points()]
    if not points:
        return None
    
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return {
        'min_x': min(xs),
        'max_x': max(xs),
        'min_y': min(ys),
        'max_y': max(ys),
        'width': max(xs) - min(xs),
        'height': max(ys) - min(ys),
        'points': len(points)
    }

def main():
    print("Loading DXF file...")
    try:
        doc = ezdxf.readfile(DXF_FILE)
    except Exception as e:
        print(f"Error loading DXF: {e}")
        sys.exit(1)
    
    print(f"DXF loaded successfully")
    
    # Get all layers
    all_layers = set(entity.dxf.layer for entity in doc.modelspace())
    print(f"\nTotal layers found: {len(all_layers)}")
    
    # Filter for relevant layers
    paineis_layers = [l for l in all_layers if 'PAINEL' in l.upper()]
    laje_layers = [l for l in all_layers if 'LAJ' in l.upper()]
    madeira_layers = [l for l in all_layers if 'MADEIRA' in l.upper()]
    
    print(f"Painéis layers: {paineis_layers[:5]}..." if len(paineis_layers) > 5 else f"Painéis layers: {paineis_layers}")
    print(f"Laje layers: {laje_layers[:5]}..." if len(laje_layers) > 5 else f"Laje layers: {laje_layers}")
    print(f"Madeira layers: {madeira_layers[:5]}..." if len(madeira_layers) > 5 else f"Madeira layers: {madeira_layers}")
    
    # Search for TEXT entities to find V6 and confirm others
    print("\n--- Searching for TEXT entities (viga labels) ---")
    text_entities = {}
    for entity in doc.modelspace():
        if entity.dxf.entity_type == 'TEXT':
            text = entity.dxf.text
            if any(viga in text for viga in ['V4', 'V5', 'V6', 'V7']):
                y = entity.dxf.insert[1]
                if text not in text_entities:
                    text_entities[text] = []
                text_entities[text].append(y)
    
    # Print found text entities
    for text in sorted(text_entities.keys()):
        positions = text_entities[text]
        print(f"  {text}: Y positions = {positions}")
    
    # Build search positions
    search_positions = dict(KNOWN_POSITIONS)
    
    # Find V6 positions from TEXT
    for text, positions in text_entities.items():
        if 'V6' in text:
            if text == 'V6.A':
                search_positions['V6']['A'] = positions[0] if positions else None
            elif text == 'V6.B':
                search_positions['V6']['B'] = positions[0] if positions else None
    
    if 'V6' not in search_positions:
        search_positions['V6'] = {'A': None, 'B': None}
    
    print(f"\nSearch positions: {search_positions}")
    
    # Extract geometry for each viga
    results = {}
    
    for viga_name in ['V4', 'V5', 'V6', 'V7']:
        print(f"\n--- Extracting geometry for {viga_name} ---")
        results[viga_name] = {
            'positions': search_positions[viga_name],
            'panels': [],
            'laje_heights': [],
            'hatches': []
        }
        
        # For each face (A and B)
        for face, y_pos in search_positions[viga_name].items():
            if y_pos is None:
                print(f"  {viga_name}.{face}: position not found")
                continue
            
            y_min = y_pos - SEARCH_Y_RANGE
            y_max = y_pos + SEARCH_Y_RANGE
            
            print(f"  {viga_name}.{face}: Y={y_pos}, search range [{y_min}, {y_max}]")
            
            # Search for LWPOLYLINE in Painéis layer
            if paineis_layers:
                paineis_found = []
                for layer in paineis_layers:
                    for entity in doc.modelspace().query(f'[layer=="{layer}"]'):
                        if entity.dxf.entity_type == 'LWPOLYLINE':
                            bounds = extract_lwpolyline_bounds(entity)
                            if bounds and y_min <= bounds['min_y'] <= y_max or y_min <= bounds['max_y'] <= y_max:
                                paineis_found.append({
                                    'layer': layer,
                                    'bounds': bounds
                                })
                
                if paineis_found:
                    print(f"    Found {len(paineis_found)} panel entities in Y range")
                    for item in paineis_found:
                        print(f"      Layer: {item['layer']}, Width: {item['bounds']['width']:.2f}, Height: {item['bounds']['height']:.2f}")
                        results[viga_name]['panels'].append(item['bounds']['width'])
            
            # Search for LWPOLYLINE in Laje layers
            if laje_layers:
                laje_found = []
                for layer in laje_layers:
                    for entity in doc.modelspace().query(f'[layer=="{layer}"]'):
                        if entity.dxf.entity_type == 'LWPOLYLINE':
                            bounds = extract_lwpolyline_bounds(entity)
                            if bounds and y_min <= bounds['min_y'] <= y_max or y_min <= bounds['max_y'] <= y_max:
                                laje_found.append({
                                    'layer': layer,
                                    'height': bounds['height']
                                })
                
                if laje_found:
                    print(f"    Found {len(laje_found)} laje entities in Y range")
                    for item in laje_found:
                        print(f"      Layer: {item['layer']}, Height: {item['height']:.2f}")
                        results[viga_name]['laje_heights'].append(item['height'])
        
        # Search for HATCH near viga
        avg_y = sum(y for y in search_positions[viga_name].values() if y is not None) / len([y for y in search_positions[viga_name].values() if y is not None])
        y_min = avg_y - SEARCH_Y_RANGE * 2
        y_max = avg_y + SEARCH_Y_RANGE * 2
        
        hatches_found = []
        for entity in doc.modelspace():
            if entity.dxf.entity_type == 'HATCH':
                # Get hatch bounds
                try:
                    bounds = entity.bounds
                    if bounds and y_min <= bounds[1] <= y_max or y_min <= bounds[3] <= y_max:
                        hatches_found.append({
                            'pattern': entity.dxf.pattern_name,
                            'scale': entity.dxf.pattern_scale
                        })
                except:
                    pass
        
        if hatches_found:
            print(f"  Found {len(hatches_found)} HATCH entities")
            for item in hatches_found:
                print(f"    Pattern: {item['pattern']}, Scale: {item['scale']}")
                results[viga_name]['
