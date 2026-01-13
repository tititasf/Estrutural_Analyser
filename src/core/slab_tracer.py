from shapely.geometry import Point, LineString, Polygon, MultiLineString
from shapely.ops import polygonize, unary_union
from typing import List, Tuple, Optional, Dict
import math

class SlabTracer:
    """
    Algoritmo 'Boundary Tracer' para Lajes.
    Usa 'Path Finding' (Polygonize) para encontrar polígonos fechados formados por vigas/paredes.
    """
    def __init__(self, spatial_index):
        self.spatial_index = spatial_index
        self.global_boundary = None
        
    def _init_global_boundary(self):
        """
        Calcula o 'Envelope' global do desenho para validar o que é 'Exterior'.
        Prioridade: 
        1. Layers explicitos ('MARCO', 'CONTORNO', 'LIMITE').
        2. Se não achar, Convex Hull de toda a estrutura (Vigas/Paredes).
        """
        marco_geoms = []
        structure_geoms = []
        
        # Iterar todos os itens do indice
        # O spatial_index expõe 'items' (Dict[int, Any])
        all_items = list(self.spatial_index.items.values()) if hasattr(self.spatial_index, 'items') else []
        
        invalid_layers = ['COTA', 'DIM', 'TEXT', 'EIXO', 'HATCH', 'MP_', 'OBS', 'TITULO']
        
        for item in all_items:
            geom = None
            layer = ""
            
            if isinstance(item, dict):
                layer = item.get('layer', '').upper()
                if 'points' in item: geom = LineString(item['points'])
                elif 'start' in item: geom = LineString([item['start'], item['end']])
            elif isinstance(item, list) and len(item) > 1:
                geom = LineString(item) # Tupla antiga/lista
                
            if not geom: continue
            
            # Checar se é Marco
            if any(k in layer for k in ['MARCO', 'CONTORNO', 'LIMITE', 'FRAME']):
                marco_geoms.append(geom)
            
            # Checar se é Estrutura (para fallback)
            is_invalid = any(k in layer for k in invalid_layers)
            if not is_invalid:
                structure_geoms.append(geom)
                
        if marco_geoms:
            # Temos um Marco explicito!
            print(f"[INFO] Detectado Marco Global com {len(marco_geoms)} segmentos.")
            try:
                self.global_boundary = unary_union(marco_geoms)
            except:
                self.global_boundary = unary_union(marco_geoms).convex_hull
        elif structure_geoms:
            # Fallback: Convex Hull de tudo
            print(f"[INFO] Marco não detectado. Usando Convex Hull da estrutura ({len(structure_geoms)} segmentos).")
            try:
                # Unary union de muitas linhas pode ser lento. 
                # Otimizacao: Convex Hull dos PONTOS extremidades?
                # Sim, extrair todos os pontos e fazer convex hull é muito mais rapido.
                all_points = []
                for g in structure_geoms:
                    all_points.extend(g.coords)
                
                if all_points:
                    from shapely.geometry import MultiPoint
                    self.global_boundary = MultiPoint(all_points).convex_hull
            except Exception as e:
                print(f"[ERROR] Falha ao calcular Convex Hull: {e}")
                self.global_boundary = None
        
        if self.global_boundary:
             # Otimização: Converter para apenas Exterior Ring se for Poligono (ignorar buracos internos do Hull)
             if isinstance(self.global_boundary, Polygon):
                 self.global_boundary = self.global_boundary.exterior
             elif isinstance(self.global_boundary, MultiLineString):
                 self.global_boundary = self.global_boundary

    def trace_boundary(self, start_point: Tuple[float, float], search_radius: float = 1000.0, valid_layers: List[str] = None) -> Optional[Polygon]:
        """
        Encontra o polígono fechado que contém o start_point.
        valid_layers: Lista de layers permitidos/preferenciais.
        """
        # 1. Coletar linhas candidatas no raio ao redor do ponto
        cx, cy = start_point
        bounds = (cx - search_radius, cy - search_radius, cx + search_radius, cy + search_radius)
        
        candidates = self.spatial_index.query_bbox(bounds)
        lines = []
        
        for item in candidates:
            # Item: geometria original ou dict que a envelopa?
            # O SpatialIndex guarda o objeto original passado no insert.
            # No DXFLoader modificado, lines/polylines são dicts com 'layer'.
            
            geom = None
            layer = None
            
            if isinstance(item, dict):
                # Se for dict vindo do DXFLoader novo
                layer = item.get('layer')
                if 'points' in item: # Polyline
                    pts = item['points']
                    if len(pts) > 1: geom = LineString(pts)
                elif 'start' in item: # Line
                    geom = LineString([item['start'], item['end']])
            
            # Retrocompatibilidade com tupla crua (caso algo mais insira assim)
            elif isinstance(item, tuple) and len(item) == 2: 
                geom = LineString(item)
            elif isinstance(item, list) and len(item) > 1:
                geom = LineString(item)
                
            if geom:
                # Filtragem por Layer (Inteligência)
                if valid_layers:
                    # Se tiver filtro e a linha tiver layer, testamos.
                    # Se linha não tiver layer (tupla antiga), aceitamos ou rejeitamos? Aceitamos por segurança.
                    # Mas se tiver layer e não estiver na lista, rejeita.
                    if layer and layer not in valid_layers:
                        continue
                
                lines.append(geom)
        
        if not lines:
            return None

        # 2. Polygonize
        # Pode ser pesado se muitas linhas. Unary_union ajuda a limpar?
        # Polygonize requer linhas que se tocam perfeitamente ou cruzam.
        # DXF real pode ter gaps. (MVP: Assumir conexões decentes ou tolerância zero).
        
        try:
            # TENTATIVA 1: Noding Rápido (assumindo conexões decentes)
            # unary_union corrige interseções não-nodadas (linhas cruzando sem vertice comum)
            # É fundamental para DXF onde desenhista pode ter passado linha direto.
            noded_lines = unary_union(lines) 
            
            # polygonize retorna gerador de poligonos
            polygons = list(polygonize(noded_lines))
            
            target_pt = Point(cx, cy)
            
            # Encontrar qual polígono contém o ponto
            # Otimização: Ordenar por área (preferir menor polígono fechado que contém o ponto - "sala")
            # Mas polygonize geralmente retorna poligonos atômicos (faces).
            for poly in polygons:
                if poly.contains(target_pt):
                    return poly
            
            # Se não achou com noding simples, pode ser que o ponto esteja EXATAMENTE na borda?
            # Ou que linhas tenham gap micrométrico.
            
            # TENTATIVA 2: Snap / Buffer (Lento, usar só se falhar 1)
            # Buffer pequeno pode fechar gaps
            # Mas cuidado para não fechar passagens reais.
            # Implementação futura se necessário.
            
        except Exception as e:
            # Falha na geometria
            print(f"[DEBUG] Trace Error: {e}")
            return None
                    
        except Exception as e:
            # Falha na geometria
            return None
            
        return None


    def detect_extensions(self, main_poly: Polygon, search_radius: float = 50.0) -> List[Dict]:
        """
        Detecta e GERA 'acréscimos' (strips de 10 unidades) em bordas externas.
        Estratégia: Generative Edge Extrusion (V4).
        1. Para cada aresta da laje:
        2. Testar se aponta para o 'vazio' (Ray Cast).
        3. Se for vazio, extrudar aresta em 10 unidades e criar polígono.
        """
        if not main_poly or not self.spatial_index:
            return []

        generated_extensions = []
        
        # Iterar arestas
        coords = list(main_poly.exterior.coords)
        if len(coords) < 2: return []
        
        # Limiar de bloqueio (se bater em algo a menso de X, é interno)
        # Se bater em algo longe (> 5m), consideramos 'vazio' suficiente para borda?
        # User disse "se não cruzar nada". Aumentando para 10m para evitar internos.
        BLOCK_DIST_THRESHOLD = 1000.0 # 10 metros
        EXTENSION_WIDTH = 10.0
        
        for i in range(len(coords)-1):
            p1 = coords[i]
            p2 = coords[i+1]
            edge = LineString([p1, p2])
            
            if edge.length < 5.0: continue # Ignorar arestas muito curtas
            
            # Calcular Normal Outwards
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = (dx*dx + dy*dy)**0.5
            if length == 0: continue
            
            nx, ny = -dy/length, dx/length
            
            # Verificar se normal aponta pra fora
            mid = edge.interpolate(0.5, normalized=True)
            check_pt = (mid.x + nx*0.1, mid.y + ny*0.1)
            if main_poly.contains(Point(check_pt)):
                nx, ny = -nx, -ny # Inverter
            
            # Classificar Lado
            angle_deg = math.degrees(math.atan2(ny, nx)) % 360
            if 45 <= angle_deg < 135: side = "Norte"
            elif 135 <= angle_deg < 225: side = "Oeste"
            elif 225 <= angle_deg < 315: side = "Sul"
            else: side = "Leste"
            
            # Ray Cast (Fan Scan: -10, 0, +10)
            angles = [0, -10, 10]
            is_blocked = False
            
            shortest_hit = float('inf')
            
            print(f"[DEBUG] Edge {side} (L={length:.1f}): Checking emptiness...")
            
            for ang in angles:
                rad = math.radians(ang)
                rnx = nx * math.cos(rad) - ny * math.sin(rad)
                rny = nx * math.sin(rad) + ny * math.cos(rad)
                
                ray_len = 5000.0 # 50m
                r_start = (mid.x + rnx*1.0, mid.y + rny*1.0) # Start 1cm away
                r_end = (r_start[0] + rnx*ray_len, r_start[1] + rny*ray_len)
                ray_geom = LineString([r_start, r_end])
                
                hits = self.spatial_index.query_bbox(ray_geom.bounds)
                
                ray_blocked_locally = False
                for h in hits:
                    h_geom = None
                    # Simplificado: só geometria serve
                    if isinstance(h, dict):
                        if 'points' in h: h_geom = LineString(h['points'])
                        elif 'start' in h: h_geom = LineString([h['start'], h['end']])
                    elif isinstance(h, list) and len(h) > 1: h_geom = LineString(h)
                    
                    if not h_geom: continue
                    if not ray_geom.intersects(h_geom): continue
                    
                    # Distancia do hit
                    dist = Point(r_start).distance(h_geom)
                    if dist < BLOCK_DIST_THRESHOLD:
                        ray_blocked_locally = True
                        shortest_hit = min(shortest_hit, dist)
                        # print(f"[DEBUG]   Blocked by obstacle at {dist:.1f}")
                        break
                
                if ray_blocked_locally:
                    is_blocked = True
                    break # Se um raio bloqueou, a aresta é interna? 
                          # Ou se TODOS bloquearem? 
                          # Se tiver parede colada, é interno. Um raio basta pra detectar parede.
            
            if is_blocked:
                print(f"[DEBUG]   Edge BLOCKED (Obstacle at {shortest_hit:.1f}). Internal.")
                continue
            
            # Se chegou aqui, é EXTERNA (Vazio). Gerar Extensão.
            print(f"[DEBUG]   Edge FREE. Generating Extension width={EXTENSION_WIDTH}")
            
            # Criar geometria do acréscimo (Retângulo projetado)
            # p1 -> p2 -> p2_out -> p1_out -> p1
            p1_out = (p1[0] + nx*EXTENSION_WIDTH, p1[1] + ny*EXTENSION_WIDTH)
            p2_out = (p2[0] + nx*EXTENSION_WIDTH, p2[1] + ny*EXTENSION_WIDTH)
            
            ext_poly = Polygon([p1, p2, p2_out, p1_out, p1])
            
            generated_extensions.append({
                'type': 'poly',
                'points': list(ext_poly.exterior.coords),
                'role': 'Acrescimo_borda',
                'width_est': EXTENSION_WIDTH,
                'side': side
            })
            
        return generated_extensions


    def detect_slabs_from_texts(self, texts: List[Dict], search_radius: float = 2000.0, valid_layers: List[str] = None) -> List[Dict]:
        """
        Varre textos buscando padrões de laje (Lx, Laje X) e tenta traçar limites.
        """
        slabs = []
        import re
        # Padrão: Começa com L seguido de numero, ou LAJE...
        # Ex: "L1", "L-2", "LAJE 03"
        slab_pattern = re.compile(r'^(L|LAJE)\s*[-_]?\s*\d+[a-zA-Z]*$', re.IGNORECASE)
        
        # DEBUG
        sample_texts = [t.get('text') for t in texts[:5]]
        print(f"[DEBUG] SlabTracer checking {len(texts)} texts. Patterns found?")
        
        for t in texts:
            txt = t.get('text', '').strip()
            if slab_pattern.match(txt):
                pos = t.get('pos')
                if not pos: continue
                
                # Tentar traçar contorno
                poly = self.trace_boundary(pos, search_radius, valid_layers=valid_layers)
                
                found_poly = bool(poly)
                points = []
                area = 0.0
                
                extensions = []
                
                if poly:
                    points = list(poly.exterior.coords)
                    area = poly.area
                    
                    # --- NOVA INTELIGÊNCIA: Detectar Acréscimos ---
                    try:
                        extensions = self.detect_extensions(poly)
                    except Exception as e:
                        print(f"Erro detectando extensões Laje {txt}: {e}")
                    # -----------------------------------------------
                    
                else:
                    # Fallback: Quadrado de 50x50 em volta do texto
                    cx, cy = pos
                    points = [
                        (cx-25, cy-25), (cx+25, cy-25),
                        (cx+25, cy+25), (cx-25, cy+25),
                        (cx-25, cy-25)
                    ]
                
                slabs.append({
                    'id': f"temp_{len(slabs)}", # Temp ID
                    'name': txt.upper(), # L1
                    'pos': pos,
                    'points': points,
                    'area': area,
                    'neighbors': [],
                    'is_detected': found_poly,
                    'is_validated': False, # Novo slab vindo do trace
                    'type': 'Laje',
                    'extensions': extensions # Passar adiante
                })
        
        return slabs

