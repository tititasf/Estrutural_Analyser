import re
from typing import List, Dict, Tuple

def fix_beam_tracer(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    start_idx = content.find("    def detect_beams(self")
    end_idx = content.find("    def _group_bottom_lengths(")

    if start_idx == -1 or end_idx == -1:
        print("Could not find bounds.")
        return

    new_methods = """    def detect_beams(self, texts: List[Dict], all_lines: List[Dict]) -> List[Dict]:
        beam_labels = []
        for t in texts:
            content = t['text'].strip()
            if (content.startswith('V') or content.startswith('v') or content.upper().startswith('CONT') or content.startswith('VF')) and any(c.isdigit() for c in content):
                beam_labels.append(t)
                
        final_beams = []
        grouped_by_base = {}
        
        for b_text in beam_labels:
            content = b_text['text'].strip()
            pos = b_text['pos']
            
            clean_name = content
            m = re.match(r'^(V|VF|CONT)(\\d+)[A-Z]?$', content)
            if m:
                base_name = f"{m.group(1)}{m.group(2)}"
            else:
                base_name = clean_name

            geometry = self._find_beam_geometry(pos, all_lines, beam_labels)
            
            if base_name not in grouped_by_base:
                grouped_by_base[base_name] = []
            grouped_by_base[base_name].append({
                'name': content,
                'type': 'Viga',
                'pos': pos,
                'geometry': geometry,
                'neighbors': []
            })
            
        for base_name, beam_list in grouped_by_base.items():
            if len(beam_list) == 1:
                b = beam_list[0]
                b['name'] = base_name
                b['parent_name'] = base_name
                final_beams.append(b)
                continue
                
            master_beam = {
                'name': base_name,
                'parent_name': base_name,
                'type': 'Viga',
                'pos': beam_list[0]['pos'], 
                'geometry': {
                    'lines': [], 'texts': [], 'dimension_texts': [],
                    'classified': {'seg_side_a': [], 'seg_side_b': [], 'seg_bottom': [], 'merged_bottom_lengths': []}
                },
                'neighbors': []
            }
            
            seen_centers = set()
            for b in beam_list:
                geo = b['geometry']
                if not geo: continue
                master_beam['geometry']['lines'].extend(geo.get('lines', []))
                master_beam['geometry']['texts'].extend(geo.get('texts', []))
                master_beam['geometry']['dimension_texts'].extend(geo.get('dimension_texts', []))
                
                classi = geo.get('classified', {})
                master_beam['geometry']['classified']['seg_side_a'].extend(classi.get('seg_side_a', []))
                master_beam['geometry']['classified']['seg_side_b'].extend(classi.get('seg_side_b', []))
                
                for seg in classi.get('seg_bottom', []):
                    cx = round(sum(p[0] for p in seg) / len(seg), 1)
                    cy = round(sum(p[1] for p in seg) / len(seg), 1)
                    if (cx, cy) not in seen_centers:
                        seen_centers.add((cx, cy))
                        master_beam['geometry']['classified']['seg_bottom'].append(seg)
                        
            master_beam['geometry']['classified']['merged_bottom_lengths'] = self._group_bottom_lengths(master_beam['geometry']['classified']['seg_bottom'])
            final_beams.append(master_beam)
            
        return final_beams

    def _find_beam_geometry(self, pos: Tuple[float, float], all_lines: List[Dict], beam_labels: List[Dict] = None) -> Dict:
        def _grow(is_h):
            contain_long = 4000
            contain_trans = 80
            if is_h:
                cbox = (pos[0]-contain_long, pos[1]-contain_trans, pos[0]+contain_long, pos[1]+contain_trans)
            else:
                cbox = (pos[0]-contain_trans, pos[1]-contain_long, pos[0]+contain_trans, pos[1]+contain_long)
                
            def _in_box(pts):
                for p in pts:
                    if cbox[0] <= p[0] <= cbox[2] and cbox[1] <= p[1] <= cbox[3]:
                        return True
                return False

            def _owns(pts):
                if not beam_labels: return True
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                my_dist = abs(cx - pos[0]) if is_h else abs(cy - pos[1])
                
                for other in beam_labels:
                    op = other['pos']
                    if abs(op[0] - pos[0]) < 5 and abs(op[1] - pos[1]) < 5:
                        continue
                    if is_h and abs(op[1] - pos[1]) < 40:
                        if abs(cx - op[0]) < my_dist: return False
                    elif not is_h and abs(op[0] - pos[0]) < 40:
                        if abs(cy - op[1]) < my_dist: return False
                return True

            sementes = []
            seed_cands = self.spatial_index.query_bbox((pos[0]-60, pos[1]-60, pos[0]+60, pos[1]+60))
            for cand in seed_cands:
                if isinstance(cand, dict) and 'points' in cand and _in_box(cand['points']):
                    sementes.append(cand)
                    
            visited = set()
            q = []
            res_lines = []
            
            for s in sementes:
                if id(s) not in visited:
                    visited.add(id(s))
                    q.append(s)
                    res_lines.append(s['points'])
                    
            while q and len(res_lines) < 1000:
                curr = q.pop(0)
                for pt in curr['points']:
                    if not (cbox[0] <= pt[0] <= cbox[2] and cbox[1] <= pt[1] <= cbox[3]):
                        continue
                    vizinhos = self.spatial_index.query_bbox((pt[0]-30, pt[1]-30, pt[0]+30, pt[1]+30))
                    for cand in vizinhos:
                        if isinstance(cand, dict) and 'points' in cand:
                            if id(cand) not in visited and _in_box(cand['points']) and _owns(cand['points']):
                                visited.add(id(cand))
                                q.append(cand)
                                res_lines.append(cand['points'])
                                
            if not res_lines: return 0, []
            all_x = [p[0] for l in res_lines for p in l]
            all_y = [p[1] for l in res_lines for p in l]
            return (max(all_x)-min(all_x)) if is_h else (max(all_y)-min(all_y)), res_lines

        len_h, lines_h = _grow(True)
        len_v, lines_v = _grow(False)
        is_horiz = len_h >= len_v
        
        raw_lines = lines_h if is_horiz else lines_v
        
        beam_geometry = {
            'lines': raw_lines,
            'texts': [],
            'dimension_texts': [],
            'classified': {'seg_side_a': [], 'seg_side_b': [], 'seg_bottom': []}
        }
        
        if not raw_lines: return beam_geometry
            
        all_x = [p[0] for l in raw_lines for p in l]
        all_y = [p[1] for l in raw_lines for p in l]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        search_box = (min_x-50, min_y-50, max_x+50, max_y+50)
        cands = self.spatial_index.query_bbox(search_box)
        for c in cands:
            if isinstance(c, dict):
                if 'text' in c:
                    if re.match(r'^\\d+([.,]\\d+)?$', c['text'].strip()):
                        beam_geometry['dimension_texts'].append(c)
                    else:
                        beam_geometry['texts'].append(c)
                        
        beam_geometry['classified'] = self._classify_lines(pos, raw_lines, label_pos=pos)
        beam_geometry['classified']['merged_bottom_lengths'] = self._group_bottom_lengths(beam_geometry['classified']['seg_bottom'])
        return beam_geometry

"""
    new_content = content[:start_idx] + new_methods + content[end_idx:]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Done fixing tracer.")

fix_beam_tracer(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\src\core\beam_tracer.py")
