"""Reconcilia dimensoes canonicas N2 PIL a partir das faces medidas no recorte.

Uso: python -B scripts/arete/reconciliar_dimensoes_pil_n2.py --pav 13_PAV --apply
Sem --apply apenas audita. A promocao so e permitida quando A/B e C/D sao
medidas completas e concordantes; nao ha excecao por identificador de pilar.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from motor_reverso_pil import (  # noqa: E402
    DIMENSAO_FACE_TOLERANCIA_CM, extrair_ficha_pilar,
)

DB_PATH = ROOT.parent / 'project_data.vision'


def _faces_nomeadas_no_recorte(recorte_path: str) -> set[str]:
    """Lê a topologia declarada pelo próprio DXF, sem inferir por item."""
    import ezdxf
    doc = ezdxf.readfile(recorte_path)
    faces = set()
    for ent in doc.modelspace():
        if ent.dxftype() != 'TEXT':
            continue
        match = re.match(r'^[A-Z]\d+\.([A-H])$', ent.dxf.text.strip().upper())
        if match:
            faces.add(match.group(1))
    return faces


def resolver_retangular(ficha: dict, recorte_path: str) -> tuple[dict | None, dict]:
    """Devolve dimensoes comprovadas por A/B e C/D ou uma justificativa."""
    validation = (ficha.get('_er_meta') or {}).get('dxf_validation') or {}
    comp_faces = validation.get('comprimento_geom_faces') or {}
    larg_faces = validation.get('largura_geom_faces') or {}
    faces_medidas = set(comp_faces) | set(larg_faces)
    faces_topologia = _faces_nomeadas_no_recorte(recorte_path)
    audit = {
        'schema': 'pil.n2.dimension-resolution/v1',
        'source': 'recorte_dxf_faces',
        'tolerance_cm': DIMENSAO_FACE_TOLERANCIA_CM,
        'applied': False,
    }
    if faces_topologia != {'A', 'B', 'C', 'D'} or faces_medidas != {'A', 'B', 'C', 'D'}:
        audit.update({'topology': 'nao_confirmada',
                      'reason': 'topologia_nao_retangular_ou_medicao_incompleta',
                      'faces_topologia': sorted(faces_topologia),
                      'faces_medidas': sorted(faces_medidas)})
        return None, audit
    comp_ok = abs(comp_faces['A'] - comp_faces['B']) <= DIMENSAO_FACE_TOLERANCIA_CM
    larg_ok = abs(larg_faces['C'] - larg_faces['D']) <= DIMENSAO_FACE_TOLERANCIA_CM
    audit.update({'topology': 'retangular_abcd',
                  'faces': {'A_B': comp_faces, 'C_D': larg_faces},
                  'agreement': {'A_B': comp_ok, 'C_D': larg_ok}})
    if not (comp_ok and larg_ok):
        audit['reason'] = 'faces_opostas_divergentes'
        return None, audit
    resolved = {
        'comprimento': round((comp_faces['A'] + comp_faces['B']) / 2, 1),
        'largura': round((larg_faces['C'] + larg_faces['D']) / 2, 1),
    }
    audit.update({'applied': True, 'resolved': resolved})
    return resolved, audit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pav', default='13_PAV')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, obra_name, elemento_id, campos_json, recorte_path
        FROM reverse_eng_fichas
        WHERE classe='PIL' AND pavimento=? ORDER BY elemento_id
    """, (args.pav,)).fetchall()
    report = []
    changed = 0
    for row in rows:
        existing = json.loads(row['campos_json'])
        fresh = extrair_ficha_pilar(row['recorte_path'], row['elemento_id'], row['obra_name'])
        resolved, audit = resolver_retangular(fresh, row['recorte_path'])
        before = {k: existing.get(k) for k in ('comprimento', 'largura')}
        entry = {'elemento_id': row['elemento_id'], 'before': before, 'resolution': audit}
        if resolved:
            entry['after'] = resolved
            if before != resolved:
                merged = dict(existing)
                merged.update(resolved)
                meta = dict(merged.get('_er_meta') or {})
                meta['dimension_resolution'] = {**audit, 'before': before}
                meta['dxf_validation'] = (fresh.get('_er_meta') or {}).get('dxf_validation', {})
                meta['dxf_path'] = row['recorte_path']
                merged['_er_meta'] = meta
                if args.apply:
                    conn.execute('UPDATE reverse_eng_fichas SET campos_json=? WHERE id=?',
                                 (json.dumps(merged, ensure_ascii=False), row['id']))
                changed += 1
        report.append(entry)
    if args.apply:
        conn.commit()
    conn.close()
    out_dir = ROOT / 'scripts' / 'arete' / 'relatorios' / (
        'reconciliacao_pil_dimensoes_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {'pavimento': args.pav, 'apply': args.apply, 'total': len(rows),
               'alterados': changed, 'itens': report}
    (out_dir / 'RELATORIO.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (out_dir / 'RELATORIO.md').write_text(
        f'# Reconciliação N2 PIL\n\nPavimento: `{args.pav}`  \nItens: {len(rows)}  \nAlterados: {changed}  \nModo aplicado: {args.apply}\n', encoding='utf-8')
    print(json.dumps({'report_dir': str(out_dir), 'total': len(rows), 'changed': changed,
                      'apply': args.apply}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
