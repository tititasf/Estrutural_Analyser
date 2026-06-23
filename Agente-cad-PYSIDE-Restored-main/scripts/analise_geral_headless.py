"""
Análise Geral Headless — equivalente a process_pillars_action sem GUI/PySide6.

Fluxo:
  1. Lê DXF path do projeto no DB
  2. Carrega DXF via DXFLoader
  3. Constrói SpatialIndex
  4. Roda BeamTracer.detect_beams()
  5. Para cada beam FV extrai dados com fixes:
       - panels_n1 = len(merged_bottom_lengths)  [spans entre pilares, não links brutos]
       - comprimento  = sum(merged_bottom_lengths)
       - dim/h        = texto de dimensão MAIS PRÓXIMO do label (h = min do par)
  6. UPSERT em beam_elements (project_data.vision)
  7. Render headless do pavimento (limpo + vínculos) p/ inspeção visual
  8. Roda fv_loop_runner.run() para comparação automática

Uso:
    python -X utf8 scripts/analise_geral_headless.py --obra Obra_TREINO_1 --pav 13
    python -X utf8 scripts/analise_geral_headless.py --obra Obra_TREINO_1 --pav 13 --debug-beam V302
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")


# ── helpers ───────────────────────────────────────────────────────────────────

DIM_RE = re.compile(r"\(?\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*\)?")


def _parse_dim_pair(dim_text: str | None) -> tuple[float, float] | None:
    if not dim_text:
        return None
    m = DIM_RE.search(str(dim_text))
    if not m:
        return None
    first = float(m.group(1).replace(",", "."))
    second = float(m.group(2).replace(",", "."))
    return min(first, second), max(first, second)


def _parse_dim_text(texts: list, beam_pos: tuple | None = None) -> str | None:
    """Retorna o texto de dimensão mais próximo do beam (ou o primeiro válido).
    beam_pos: (x, y) da posição do label do beam no DXF.
    """
    candidates = []
    for t in texts:
        txt = t.get("text", "").strip()
        if _parse_dim_pair(txt):
            if beam_pos and "pos" in t:
                p = t["pos"]
                dist = math.sqrt((p[0] - beam_pos[0]) ** 2 + (p[1] - beam_pos[1]) ** 2)
                candidates.append((dist, txt))
            else:
                return txt
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    return None


def _parse_h(dim_text: str | None) -> float | None:
    """Extrai espessura h da viga a partir de texto tipo '19/55' ou '120/19'.
    Para FV (fundo de viga), h é sempre a dimensão MENOR (espessura da seção).
    Ex: '19/55' → min(19,55)=19  |  '120/19' → min(120,19)=19  |  '24/66' → min(24,66)=24
    """
    pair = _parse_dim_pair(dim_text)
    return pair[0] if pair else None


def _axis_point(coord_value: float, beam_pos: tuple, is_horizontal: bool) -> tuple[float, float]:
    return (coord_value, beam_pos[1]) if is_horizontal else (beam_pos[0], coord_value)


def _dist_point_to_axis_span(pos: tuple, coord: tuple, beam_pos: tuple, is_horizontal: bool) -> float:
    if is_horizontal:
        along = min(max(pos[0], coord[0]), coord[1])
        return math.hypot(pos[0] - along, pos[1] - beam_pos[1])
    along = min(max(pos[1], coord[0]), coord[1])
    return math.hypot(pos[0] - beam_pos[0], pos[1] - along)


def _query_texts(spatial_index, bbox: tuple) -> list[dict]:
    if not spatial_index:
        return []
    return [c for c in spatial_index.query_bbox(bbox) if isinstance(c, dict) and c.get("text")]


def _find_segment_dim(seg: dict, beam_pos: tuple, is_horizontal: bool, spatial_index) -> dict | None:
    coord = seg.get("coord")
    if not coord or not beam_pos:
        return None
    pad_axis = 120.0
    pad_trans = 260.0
    if is_horizontal:
        bbox = (coord[0] - pad_axis, beam_pos[1] - pad_trans, coord[1] + pad_axis, beam_pos[1] + pad_trans)
    else:
        bbox = (beam_pos[0] - pad_trans, coord[0] - pad_axis, beam_pos[0] + pad_trans, coord[1] + pad_axis)
    candidates = []
    for t in _query_texts(spatial_index, bbox):
        pair = _parse_dim_pair(t.get("text", ""))
        if not pair or not t.get("pos"):
            continue
        score = _dist_point_to_axis_span(t["pos"], coord, beam_pos, is_horizontal)
        candidates.append((score, t, pair))
    if not candidates:
        return None
    score, text_link, pair = min(candidates, key=lambda x: x[0])
    if score > pad_trans * 1.5:
        return None
    link = dict(text_link)
    link["type"] = link.get("type") or "text"
    link["role"] = "Dimensao fundo de viga"
    return {"text": link.get("text", ""), "link": link, "width": pair[0], "height": pair[1], "score": score}


def _choose_segment_dim(seg_dim: dict | None, dim_text: str | None, h_n1: float | None, seg_len: float | None) -> dict:
    """Prefere a dimensao vinculada ao segmento e usa a global apenas como fallback."""
    global_pair = _parse_dim_pair(dim_text)
    if not seg_dim:
        if not global_pair:
            return {"text": dim_text or "", "width": h_n1 or 0, "height": 0, "link": None}
        return {
            "text": dim_text or "",
            "width": global_pair[0],
            "height": global_pair[1],
            "link": None,
        }

    local_width = float(seg_dim.get("width") or 0)
    local_score = float(seg_dim.get("score") or 9999)
    global_width = float((global_pair or (h_n1 or 0, 0))[0] or 0)
    return {
        "text": seg_dim.get("text") or dim_text or "",
        "width": local_width or global_width,
        "height": float(seg_dim.get("height") or (global_pair[1] if global_pair else 0) or 0),
        "link": seg_dim.get("link"),
        "score": local_score,
        "source": "segment",
    }


def _is_support_label(text: str, current_beam: str = "") -> bool:
    txt = str(text or "").strip().upper()
    if not txt or _parse_dim_pair(txt):
        return False
    if current_beam and txt == current_beam.upper():
        return False
    return bool(re.match(r"^(?:P|V|VF|VP|CONT)[A-Z0-9_.-]*\d[A-Z0-9_.-]*$", txt))


def _find_support_text(endpoint: tuple, spatial_index, current_beam: str = "") -> dict | None:
    if not endpoint or not spatial_index:
        return None
    radius = 320.0
    bbox = (endpoint[0] - radius, endpoint[1] - radius, endpoint[0] + radius, endpoint[1] + radius)
    candidates = []
    for t in _query_texts(spatial_index, bbox):
        if not _is_support_label(t.get("text", ""), current_beam):
            continue
        pos = t.get("pos")
        if not pos:
            continue
        dist = math.hypot(pos[0] - endpoint[0], pos[1] - endpoint[1])
        candidates.append((dist, t))
    if not candidates:
        return None
    _, link = min(candidates, key=lambda x: x[0])
    out = dict(link)
    out["type"] = out.get("type") or "text"
    out["role"] = "Apoio fundo de viga"
    return out


def _seg_length_2pts(p1, p2) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def get_project(obra_name: str, pav_filter: str | None, db_path: Path):
    """Retorna (project_id, dxf_path) do projeto."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if pav_filter:
            row = conn.execute(
                "SELECT id, dxf_path FROM projects WHERE work_name=? AND pavement_name LIKE ?",
                [obra_name, f"%{pav_filter}%"],
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, dxf_path FROM projects WHERE work_name=? LIMIT 1",
                [obra_name],
            ).fetchone()
        if not row:
            return None, None
        return row["id"], row["dxf_path"]
    finally:
        conn.close()


def upsert_beam_element_fv(conn: sqlite3.Connection, project_id: str, viga_nome: str,
                            n_segmentos: int, campos: dict):
    """UPSERT cirúrgico em beam_elements para classe FV."""
    el_id = f"BE-FV-{project_id}-{viga_nome}"
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO beam_elements
            (id, project_id, parent_beam_id, viga_nome, classe,
             campos_json, n_segmentos, is_validated, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'FV', ?, ?, 0, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            campos_json  = excluded.campos_json,
            n_segmentos  = excluded.n_segmentos,
            updated_at   = excluded.updated_at
        """,
        (el_id, str(project_id), "", viga_nome,
         json.dumps(campos, ensure_ascii=False),
         n_segmentos, now, now),
    )


# ── motor FV (extração sem GUI) ───────────────────────────────────────────────

def process_beam_fv(b: dict, spatial_index=None, visual_obstacles=None) -> dict:
    """
    Extrai dados FV de um beam do BeamTracer.
    Fixes aplicados:
    - dim_text: usa texto de dimensão MAIS PRÓXIMO da posição do beam label
    - panels_n1: len(merged_bottom_lengths)
    - bridging: obstáculos visuais (Pilares NASCE, Visão Corte) são superados fundindo spans adjacentes
    """
    visual_obstacles = visual_obstacles or []
    geo = b.get("geometry", {})
    classified = geo.get("classified", {})
    beam_pos = b.get("pos")
    dim_texts = []
    if beam_pos and spatial_index:
        cands = spatial_index.query_bbox((beam_pos[0]-300, beam_pos[1]-300, beam_pos[0]+300, beam_pos[1]+300))
        for cand in cands:
            if isinstance(cand, dict) and 'text' in cand:
                dim_texts.append(cand)

    merged_groups = classified.get("merged_bottom_groups", [])
    merged_lengths = classified.get("merged_bottom_lengths", [])
    merged_coords = classified.get("merged_bottom_groups_coords", [])
    seg_bottom_raw = classified.get("seg_bottom", [])

    # BRIDGING LOGIC: se houver coords, podemos fundir gaps que caem dentro de visual_obstacles
    if merged_coords and len(merged_coords) > 1 and visual_obstacles and beam_pos:
        is_h = b.get("is_h", True)
        new_coords = []
        new_lengths = []
        
        cur_min, cur_max = merged_coords[0]
        
        for i in range(1, len(merged_coords)):
            nxt_min, nxt_max = merged_coords[i]
            gap_mid = (cur_max + nxt_min) / 2.0
            
            # Ponto do gap a ser checado contra as bboxes
            gap_pt = (gap_mid, beam_pos[1]) if is_h else (beam_pos[0], gap_mid)
            
            bridged = False
            for obs in visual_obstacles:
                bx1, by1, bx2, by2 = obs['bbox']
                # Expansão leve na bbox para capturar imperfeições
                if bx1 - 10 <= gap_pt[0] <= bx2 + 10 and by1 - 10 <= gap_pt[1] <= by2 + 10:
                    bridged = True
                    break
                    
            if bridged:
                cur_max = max(cur_max, nxt_max)
            else:
                new_coords.append((cur_min, cur_max))
                new_lengths.append(cur_max - cur_min)
                cur_min, cur_max = nxt_min, nxt_max
                
        new_coords.append((cur_min, cur_max))
        new_lengths.append(cur_max - cur_min)
        
        merged_coords = new_coords
        merged_lengths = new_lengths

    is_horizontal = b.get('is_h', True)
    
    if merged_lengths:
        panels_n1 = len(merged_lengths)
        comprimento = sum(merged_lengths)
        segmentos_fundo = [
            {"seg_index": i + 1, "length": merged_lengths[i],
             "coord": merged_coords[i] if i < len(merged_coords) else None,
             "logical": True}
            for i in range(len(merged_lengths))
        ]
    elif merged_groups:
        panels_n1 = len(merged_groups)
        comprimento = sum(_seg_length_2pts(g[0][0], g[0][1]) for g in merged_groups if g and len(g[0]) >= 2)
        segmentos_fundo = []
        for i, grp in enumerate(merged_groups):
            p_min, p_max = None, None
            if grp and len(grp[0]) >= 2:
                if is_horizontal:
                    p_min = min(grp[0][0][0], grp[0][-1][0])
                    p_max = max(grp[0][0][0], grp[0][-1][0])
                else:
                    p_min = min(grp[0][0][1], grp[0][-1][1])
                    p_max = max(grp[0][0][1], grp[0][-1][1])
            segmentos_fundo.append({
                "seg_index": i + 1, 
                "geometry": grp[0] if grp else [], 
                "coord": (p_min, p_max) if p_min is not None else None, 
                "logical": True
            })
    else:
        panels_n1 = len(seg_bottom_raw)
        comprimento = sum(_seg_length_2pts(s[0], s[-1]) for s in seg_bottom_raw if len(s) >= 2)
        segmentos_fundo = []
        for i, s in enumerate(seg_bottom_raw):
            p_min, p_max = None, None
            if len(s) >= 2:
                if is_horizontal:
                    p_min = min(s[0][0], s[-1][0])
                    p_max = max(s[0][0], s[-1][0])
                else:
                    p_min = min(s[0][1], s[-1][1])
                    p_max = max(s[0][1], s[-1][1])
            segmentos_fundo.append({
                "seg_index": i + 1, 
                "geometry": s, 
                "coord": (p_min, p_max) if p_min is not None else None, 
                "logical": False
            })

    # dim: texto mais próximo da posição real do beam
    dim_text = _parse_dim_text(dim_texts, beam_pos=beam_pos)
    h_n1 = _parse_h(dim_text)
    apoio_inicial = ""
    apoio_final = ""
    supports = (b.get("geometry", {}) or {}).get("support_candidates", []) or []
    if supports:
        def _support_key(s):
            pts = s.get("points") or []
            if pts:
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                return cx if is_horizontal else cy
            pos = s.get("pos") or (0, 0)
            return pos[0] if is_horizontal else pos[1]

        def _support_label(s):
            for key in ("name", "text", "label", "id_item", "id"):
                if s.get(key):
                    return str(s.get(key))
            return ""

        ordered = sorted(supports, key=_support_key)
        apoio_inicial = _support_label(ordered[0]) if ordered else ""
        apoio_final = _support_label(ordered[-1]) if len(ordered) > 1 else ""

    for seg in segmentos_fundo:
        seg_len = seg.get("length")
        if seg_len is None and seg.get("coord"):
            try:
                seg_len = abs(float(seg["coord"][1]) - float(seg["coord"][0]))
            except Exception:
                seg_len = 0.0

        seg_dim = _find_segment_dim(seg, beam_pos, is_horizontal, spatial_index) if beam_pos else None
        chosen_dim = _choose_segment_dim(seg_dim, dim_text, h_n1, seg_len)
        seg_dim_text = chosen_dim.get("text") or ""
        seg_width = chosen_dim.get("width") or 0
        seg_height = chosen_dim.get("height") or 0

        start_link = end_link = None
        if seg.get("coord") and beam_pos:
            start_pt = _axis_point(float(seg["coord"][0]), beam_pos, is_horizontal)
            end_pt = _axis_point(float(seg["coord"][1]), beam_pos, is_horizontal)
            start_link = _find_support_text(start_pt, spatial_index, b.get("name", ""))
            end_link = _find_support_text(end_pt, spatial_index, b.get("name", ""))

        seg["dim_text"] = seg_dim_text
        if chosen_dim.get("link"):
            seg["dim_link"] = chosen_dim.get("link")
        seg["dim_width"] = round(float(seg_width or 0), 1)
        seg["dim_height"] = round(float(seg_height or 0), 1)
        if chosen_dim.get("source"):
            seg["dim_source"] = chosen_dim.get("source")
        seg["apoio_inicial"] = (start_link or {}).get("text") or apoio_inicial
        seg["apoio_final"] = (end_link or {}).get("text") or apoio_final
        if start_link:
            seg["apoio_inicial_link"] = start_link
        if end_link:
            seg["apoio_final_link"] = end_link
        seg["ficha"] = {
            "largura_total_fundo": round(float(seg_width or 0), 1),
            "comprimento_total_fundo": round(float(seg_len or 0), 1),
            "altura_total": round(float(seg_height or 0), 1),
            "abertura_especial": "N/A",
            "chanfro_esq_top": "N/A",
            "chanfro_esq_fun": "N/A",
            "chanfro_dir_top": "N/A",
            "chanfro_dir_fun": "N/A",
            "abertura_topo_esq": "N/A",
            "abertura_topo_dir": "N/A",
            "abertura_fundo_esq": "N/A",
            "abertura_fundo_dir": "N/A",
        }

    viga_nome = b.get("name", "?")
    if viga_nome != "?":
        if viga_nome.endswith("-1"):
            viga_nome = viga_nome[:-2] + ".C"
        elif not viga_nome.endswith(".C"):
            viga_nome = viga_nome + ".C"

    return {
        "viga_nome": viga_nome,
        "panels_n1": panels_n1,
        "comprimento_fundo": round(comprimento, 1),
        "dim_text": dim_text,
        "h_n1": h_n1,
        "merged_groups_count": len(merged_groups),
        "merged_lengths_count": len(merged_lengths),
        "seg_bottom_raw_count": len(seg_bottom_raw),
        "segmentos_fundo": segmentos_fundo,
    }


# ── runner principal ──────────────────────────────────────────────────────────

def run(
    obra_name: str,
    pav_filter: str | None = None,
    db_path: Path = DB_PATH,
    debug_beam: str | None = None,
):
    print(f"\n[Análise Geral Headless] obra={obra_name} pav={pav_filter or 'TODOS'}")

    # 1. Projeto
    project_id, dxf_path = get_project(obra_name, pav_filter, db_path)
    if not project_id:
        print("  [ERRO] Projeto não encontrado no DB.")
        return
    if not dxf_path or not Path(dxf_path).exists():
        print(f"  [ERRO] DXF não encontrado: {dxf_path}")
        return
    print(f"  project_id: {project_id}")
    print(f"  dxf_path:   {dxf_path}")

    # 2. DXF
    print("  Carregando DXF...")
    from src.core.dxf_loader import DXFLoader, RenderMode
    dxf_data = DXFLoader.load_dxf(dxf_path, mode=RenderMode.TRUE_GEOMETRY)
    if not dxf_data:
        print("  [ERRO] DXFLoader retornou None.")
        return
    lines = dxf_data.get("lines", [])
    polys = dxf_data.get("polylines", [])
    texts = dxf_data.get("texts", [])
    print(f"  DXF: {len(lines)} linhas, {len(polys)} polys, {len(texts)} textos")

    # 3. SpatialIndex
    print("  Construindo SpatialIndex...")
    from src.core.spatial_index import SpatialIndex
    spatial_index = SpatialIndex()
    for poly in polys:
        pts = poly.get("points", [])
        if pts:
            bounds = (
                min(p[0] for p in pts), min(p[1] for p in pts),
                max(p[0] for p in pts), max(p[1] for p in pts),
            )
            spatial_index.insert(poly, bounds)
    for line in lines:
        s, e = line["start"], line["end"]
        bounds = (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1]))
        spatial_index.insert(line, bounds)
    for txt in texts:
        p = txt["pos"]
        spatial_index.insert(txt, (p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5))
    print(f"  SpatialIndex: {spatial_index.counter} objetos indexados")

    # 4. BeamTracer
    print("  Executando BeamTracer...")
    from src.core.beam_tracer import BeamTracer
    all_lines_and_polys = []
    for l in lines + polys:
        if "points" in l:
            all_lines_and_polys.append(l)
        elif "start" in l:
            all_lines_and_polys.append({"points": [l["start"], l["end"]]})

    beam_tracer = BeamTracer(spatial_index)
    # 4.5 Obter Obstáculos Visuais
    print("  Carregando obstáculos visuais do DB...")
    try:
        from scripts.motor_reverso_fv import _get_visual_obstacles
        visual_obstacles = _get_visual_obstacles(str(project_id))
        print(f"  Obstáculos visuais encontrados: {len(visual_obstacles)}")
    except Exception as e:
        print(f"  [WARN] Falha ao carregar obstáculos visuais: {e}")
        visual_obstacles = []
    beams_found = beam_tracer.detect_beams(texts, all_lines_and_polys, visual_obstacles=visual_obstacles)
    print(f"  Beams detectados: {len(beams_found)}")

    # debug de um beam específico
    if debug_beam:
        for b in beams_found:
            if b.get("name") == debug_beam:
                classified = b.get("geometry", {}).get("classified", {})
                mbg = classified.get("merged_bottom_groups", [])
                mbl = classified.get("merged_bottom_lengths", [])
                sb = classified.get("seg_bottom", [])
                dt = b.get("geometry", {}).get("dimension_texts", [])
                print(f"\n  --- DEBUG {debug_beam} ---")
                print(f"  merged_bottom_groups: {len(mbg)}")
                print(f"  merged_bottom_lengths: {mbl}")
                print(f"  seg_bottom: {len(sb)}")
                print(f"  dimension_texts: {[t.get('text') for t in dt]}")
                for i, g in enumerate(mbg):
                    print(f"    group[{i}]: {len(g)} rects, len={mbl[i] if i<len(mbl) else '?'}")
                break
        else:
            print(f"\n  [WARN] Beam '{debug_beam}' não encontrado na análise.")


    # 5. Processar cada beam FV e salvar no DB
    print("  Salvando resultados em beam_elements...")
    conn = sqlite3.connect(str(db_path))
    try:
        n_saved = 0
        for b in beams_found:
            name = b.get("name", "")
            # Excluir fragmentos L.* e F.*
            if re.match(r"^[LlFf]\.", name) or re.match(r"^[LF]V-", name):
                continue

            fv = process_beam_fv(b, spatial_index, visual_obstacles)

            campos = {
                "viga": name,
                "dim": fv["dim_text"],
                "segmentos_fundo": fv["segmentos_fundo"],
                "n_paineis_logicos": fv["panels_n1"],
                "comprimento_total_fundo": fv["comprimento_fundo"],
                "h_espessura": fv["h_n1"],
                "merged_groups_count": fv["merged_groups_count"],
                "merged_lengths_count": fv["merged_lengths_count"],
                "seg_bottom_raw_count": fv["seg_bottom_raw_count"],
            }

            upsert_beam_element_fv(conn, project_id, name, fv["panels_n1"], campos)
            n_saved += 1

        conn.commit()
        print(f"  Beam elements FV atualizados: {n_saved}")
    finally:
        conn.close()

    # 6. Render headless (limpo + vínculos) para inspeção visual
    try:
        from scripts.fv_render_loop import render_pavimento
        render_dir = ROOT / "sandbox_fv_loop"
        prefix = f"fv_{obra_name}_{pav_filter or 'all'}".replace(" ", "_")
        pngs = render_pavimento(dxf_data, beams_found, render_dir, prefix=prefix)
        if pngs:
            print("\n  [Render visual]")
            print(f"    limpo:    {pngs.get('limpo')}")
            print(f"    vínculos: {pngs.get('vinculos')}  ({pngs.get('beams_desenhados')} vigas)")
    except Exception as e:
        print(f"  [WARN] Render visual falhou: {e}")

    # 7. fv_loop_runner comparação
    print("\n" + "=" * 60)
    print("  Rodando comparação FV (fv_loop_runner)...")
    print("=" * 60)
    import scripts.fv_loop_runner as fvr
    results = fvr.run(obra_name, pav_filter, db_path)
    return results


def main():
    parser = argparse.ArgumentParser(description="Análise Geral Headless — sem GUI")
    parser.add_argument("--obra", required=True, help="Nome da obra")
    parser.add_argument("--pav", default=None, help="Filtro parcial do pavimento (ex: 13)")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--debug-beam", default=None, help="Debug detalhado de um beam específico (ex: V302)")
    args = parser.parse_args()

    run(
        obra_name=args.obra,
        pav_filter=args.pav,
        db_path=Path(args.db),
        debug_beam=args.debug_beam,
    )


if __name__ == "__main__":
    main()
