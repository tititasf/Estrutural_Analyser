import ezdxf
from typing import List, Dict, Any, Tuple
import logging

class DXFLoader:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.doc = None
        self.msp = None
        self.entities = {
            'polylines': [],
            'lines': [],
            'circles': [],
            'texts': []
        }

    def load(self) -> bool:
        try:
            self.doc = ezdxf.readfile(self.filepath)
            self.msp = self.doc.modelspace()
            self._extract_entities()
            return True
        except Exception as e:
            logging.error(f"Failed to load DXF: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _extract_entities(self):
        # Mapeamento de cor ezdxf -> RGB (simplificado)
        def get_color(entity):
            aci = entity.dxf.color # AutoCAD Color Index
            if aci == 256: # ByLayer
                layer = self.doc.layers.get(entity.dxf.layer)
                aci = layer.dxf.color
            
            # Tabela resumida de cores ACI
            aci_map = {
                1: (255, 0, 0),    # Red
                2: (255, 255, 0),  # Yellow
                3: (0, 255, 0),    # Green
                4: (0, 255, 255),  # Cyan
                5: (0, 0, 255),    # Blue
                6: (255, 0, 255),  # Magenta
                7: (255, 255, 255) # White/Black
            }
            return aci_map.get(aci, (200, 200, 200))

        # Polylines (LWPOLYLINE e POLYLINE)
        for pl in self.msp.query('LWPOLYLINE POLYLINE'):
            try:
                if pl.dxftype() == 'LWPOLYLINE':
                    points = list(pl.get_points(format='xy'))
                else:
                    points = [(v.dxf.location.x, v.dxf.location.y) for v in pl.vertices]
                
                self.entities['polylines'].append({
                    'points': points,
                    'is_closed': pl.is_closed,
                    'layer': pl.dxf.layer,
                    'color': get_color(pl)
                })
            except Exception as e:
                logging.warning(f"Erro ao extrair polilinha: {e}")

        # Lines
        for line in self.msp.query('LINE'):
            s = line.dxf.start
            e = line.dxf.end
            self.entities['lines'].append({
                'start': (s.x, s.y),
                'end': (e.x, e.y),
                'layer': line.dxf.layer,
                'color': get_color(line)
            })

        # Circles e Arcs
        for circle in self.msp.query('CIRCLE'):
            cp = circle.dxf.center
            self.entities['circles'].append({
                'center': (cp.x, cp.y),
                'radius': circle.dxf.radius,
                'layer': circle.dxf.layer,
                'color': get_color(circle)
            })
            
        for arc in self.msp.query('ARC'):
            cp = arc.dxf.center
            self.entities['circles'].append({ # Arcos tratados como círculos simplificados ou podemos adicionar ARC depois
                'center': (cp.x, cp.y),
                'radius': arc.dxf.radius,
                'start_angle': arc.dxf.start_angle,
                'end_angle': arc.dxf.end_angle,
                'layer': arc.dxf.layer,
                'color': get_color(arc)
            })

        # Texts e MTexts
        for text in self.msp.query('TEXT MTEXT'):
            content = text.dxf.text if text.dxftype() == 'TEXT' else text.text
            ins = text.dxf.insert
            self.entities['texts'].append({
                'text': content, 
                'pos': (ins.x, ins.y),
                'layer': text.dxf.layer,
                'color': get_color(text)
            })

    @staticmethod
    def load_dxf(path: str) -> Dict:
        """Helper estático para carregar e retornar entidades direto."""
        loader = DXFLoader(path)
        if loader.load():
            return loader.entities
        return None

    def get_stats(self) -> str:
        return (f"DXF Loaded: {self.filepath}\n"
                f"Polylines: {len(self.entities['polylines'])}\n"
                f"Lines: {len(self.entities['lines'])}\n"
                f"Texts: {len(self.entities['texts'])}")
