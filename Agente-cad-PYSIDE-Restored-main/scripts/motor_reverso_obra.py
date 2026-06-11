# -*- coding: utf-8 -*-
"""
Motor Reverso Obra — Consolida fichas granulares N2 em ficha da obra.

Agrega estatisticas por classe (PIL/LV/FV/LAJ) e detecta padroes
recorrentes entre elementos de uma mesma obra/pavimento.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = "D:/Agente-cad-PYSIDE/project_data.vision"

def consolidar_ficha_obra(obra_name: str, pavimento: str | None = None) -> dict:
    """
    Le todas as fichas aprovadas de reverse_eng_fichas para a obra
    e gera um resumo consolidado para reverse_eng_obra_ficha.

    Args:
        obra_name: nome da obra (ex: "Obra_TREINO_1")
        pavimento: se fornecido, filtra por pavimento especifico

    Returns: dict com resumo da obra
    """
    conn = sqlite3.connect(DB_PATH)

    where_pav = "AND pavimento=?" if pavimento else ""
    params = (obra_name, pavimento) if pavimento else (obra_name,)

    rows = conn.execute(f"""
        SELECT classe, elemento_id, campos_json, confianca, status, pavimento
        FROM reverse_eng_fichas
        WHERE obra_name=? {where_pav}
        AND status IN ('approved', 'draft')
        ORDER BY classe, elemento_id
    """, params).fetchall()

    conn.close()

    por_classe: dict[str, list] = {'PIL': [], 'LV': [], 'FV': [], 'LAJ': []}
    pavimentos_encontrados = set()
    total_confianca = []

    for classe, elem_id, campos_json, conf, status, pav in rows:
        try:
            campos = json.loads(campos_json) if campos_json else {}
        except Exception:
            campos = {}

        cls = classe.upper()
        por_classe.setdefault(cls, []).append({
            'elemento_id': elem_id,
            'campos': campos,
            'confianca': conf or 0,
            'status': status,
            'pavimento': pav,
        })
        pavimentos_encontrados.add(pav)
        if conf:
            total_confianca.append(conf)

    # Estatisticas por classe
    stats = {}
    for cls, items in por_classe.items():
        if not items:
            continue
        confs = [i['confianca'] for i in items if i['confianca']]
        stats[cls] = {
            'total': len(items),
            'confianca_media': round(sum(confs)/len(confs), 3) if confs else 0,
            'aprovados': sum(1 for i in items if i['status'] == 'approved'),
            'elementos': [i['elemento_id'] for i in items],
        }

        # Padroes especificos por classe
        if cls == 'PIL':
            comps = [i['campos'].get('comprimento', 0) for i in items if i['campos'].get('comprimento',0) > 0]
            largs = [i['campos'].get('largura', 0) for i in items if i['campos'].get('largura',0) > 0]
            if comps:
                stats[cls]['comprimento_range'] = [min(comps), max(comps)]
            if largs:
                stats[cls]['largura_range'] = [min(largs), max(largs)]

        elif cls in ('LV', 'FV'):
            heights = [i['campos'].get('total_height', 0) for i in items if i['campos'].get('total_height',0)]
            heights = [float(h) if isinstance(h, str) else h for h in heights]
            if heights:
                stats[cls]['altura_range'] = [min(heights), max(heights)]

        elif cls == 'LAJ':
            areas = [i['campos'].get('area_cm2', 0) for i in items if i['campos'].get('area_cm2',0)]
            if areas:
                stats[cls]['area_range'] = [min(areas), max(areas)]

    resumo = {
        'obra_name': obra_name,
        'pavimentos': sorted(pavimentos_encontrados),
        'pavimento_filtro': pavimento,
        'total_fichas': len(rows),
        'confianca_media_geral': round(sum(total_confianca)/len(total_confianca), 3) if total_confianca else 0,
        'por_classe': stats,
        'gerado_em': datetime.now().isoformat(),
    }

    return resumo


def salvar_ficha_obra(obra_name: str, pavimento: str, resumo: dict) -> bool:
    """Salva ou atualiza reverse_eng_obra_ficha."""
    total_pil = resumo.get('por_classe', {}).get('PIL', {}).get('total', 0)
    total_lv  = resumo.get('por_classe', {}).get('LV',  {}).get('total', 0)
    total_fv  = resumo.get('por_classe', {}).get('FV',  {}).get('total', 0)
    total_laj = resumo.get('por_classe', {}).get('LAJ', {}).get('total', 0)
    conf_media = resumo.get('confianca_media_geral', 0)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO reverse_eng_obra_ficha
                (obra_name, pavimento, total_pil, total_lv, total_fv, total_laj,
                 confianca_media, resumo_json, gerado_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(obra_name, pavimento) DO UPDATE SET
                total_pil=excluded.total_pil, total_lv=excluded.total_lv,
                total_fv=excluded.total_fv, total_laj=excluded.total_laj,
                confianca_media=excluded.confianca_media,
                resumo_json=excluded.resumo_json, gerado_at=excluded.gerado_at
        """, (obra_name, pavimento, total_pil, total_lv, total_fv, total_laj,
              conf_media, json.dumps(resumo, ensure_ascii=False), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as ex:
        print(f"[motor_reverso_obra] erro DB: {ex}")
        return False
