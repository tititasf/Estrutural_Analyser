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

def _parse_dim_text(texts: list, beam_pos: tuple | None = None) -> str | None:
    """Retorna o texto de dimensão mais próximo do beam (ou o primeiro válido).
    beam_pos: (x, y) da posição do label do beam no DXF.
    """
    candidates = []
    for t in texts:
        txt = t.get("text", "").strip()
        if re.search(r"\d+[/xX]\d+", txt):
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
    if not dim_text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)", dim_text)
    if not m:
        return None
    first = float(m.group(1).replace(",", "."))
    second = float(m.group(2).replace(",", "."))
    return min(first, second)


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

def process_beam_fv(b: dict) -> dict:
    """
    Extrai dados FV de um beam do BeamTracer.

    Fixes aplicados:
    - dim_text: usa texto de dimensão MAIS PRÓXIMO da posição do beam label
      (evita capturar centenas de textos do DXF inteiro via region growing)
    - panels_n1: len(merged_bottom_lengths) — painéis separados por pilares
      (merged_bottom_lengths são os spans entre pilares, já corretamente calculados
      em _find_beam_geometry. Cada entry = 1 painel. Mais preciso que contagem bruta.)
    - comprimento: sum(merged_bottom_lengths) — soma dos spans reais
    - fallback: se merged_bottom_lengths vazio → len(seg_bottom) e soma raw
    """
    geo = b.get("geometry", {})
    classified = geo.get("classified", {})
    dim_texts = geo.get("dimension_texts", [])
    beam_pos = b.get("pos")

    merged_groups = classified.get("merged_bottom_groups", [])
    merged_lengths = classified.get("merged_bottom_lengths", [])
    seg_bottom_raw = classified.get("seg_bottom", [])

    # panels + comprimento via merged_lengths (mais preciso)
    if merged_lengths:
        panels_n1 = len(merged_lengths)
        comprimento = sum(merged_lengths)
        # segmentos_fundo: 1 por span detectado
        segmentos_fundo = [
            {
                "seg_index": i + 1,
                "length": merged_lengths[i],
                "logical": True,
            }
            for i in range(len(merged_lengths))
        ]
    elif merged_groups:
        panels_n1 = len(merged_groups)
        comprimento = sum(
            _seg_length_2pts(g[0][0], g[0][1]) for g in merged_groups if g and len(g[0]) >= 2
        )
        segmentos_fundo = [
            {"seg_index": i + 1, "geometry": grp[0] if grp else [], "logical": True}
            for i, grp in enumerate(merged_groups)
        ]
    else:
        # fallback: segmentos brutos
        panels_n1 = len(seg_bottom_raw)
        comprimento = sum(
            _seg_length_2pts(s[0], s[-1]) for s in seg_bottom_raw if len(s) >= 2
        )
        segmentos_fundo = [
            {"seg_index": i + 1, "geometry": s, "logical": False}
            for i, s in enumerate(seg_bottom_raw)
        ]

    # dim: texto mais próximo da posição real do beam
    dim_text = _parse_dim_text(dim_texts, beam_pos=beam_pos)
    h_n1 = _parse_h(dim_text)

    return {
        "viga_nome": b.get("name", "?"),
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
    beams_found = beam_tracer.detect_beams(texts, all_lines_and_polys)
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
            if re.match(r"^[LlFf]\.", name):
                continue

            fv = process_beam_fv(b)

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

    # 6. fv_loop_runner comparação
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
