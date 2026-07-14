# -*- coding: utf-8 -*-
"""Probe mínimo: reproduz enrich_pillar_report_with_beams no P35 com dados reais.

Somente leitura do DB real; nenhuma escrita. Evidência para o run
20260713_193413_c8b7fbb0 (PIL/P35/N1 — chegadas ausentes).
"""
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from src.core.pillar_face_beams import (  # noqa: E402
    beam_bbox_from_entity,
    beam_axis_is_horizontal,
    beam_section_dim,
    enrich_pillar_report_with_beams,
    reconcile_beam_fundo_facts,
)

DB = 'D:/Agente-cad-PYSIDE/project_data.vision'
PROJECT = 'dd238e47-1dc6-4f63-a760-4e7ce19a7386'

con = sqlite3.connect(DB)
cur = con.cursor()

cur.execute(
    "SELECT points_json FROM pillars WHERE name='P35' AND project_id=?",
    (PROJECT,),
)
points = json.loads(cur.fetchone()[0])

cur.execute(
    "SELECT name, data_json, links_json FROM beams WHERE project_id=?",
    (PROJECT,),
)
beams = []
for name, data_json, links_json in cur.fetchall():
    beam = json.loads(data_json) if data_json else {}
    beam['name'] = beam.get('name') or name
    if links_json:
        try:
            links = json.loads(links_json)
            if isinstance(links, dict):
                merged = dict(beam.get('links') or {})
                for key, value in links.items():
                    merged.setdefault(key, value)
                beam['links'] = merged
        except (TypeError, ValueError):
            pass
    beams.append(beam)

print(f'beams carregadas: {len(beams)}')
for beam in beams:
    if beam.get('name') in ('V305', 'V308', 'V327', 'V328'):
        bbox = beam_bbox_from_entity(beam)
        is_h = beam_axis_is_horizontal(beam, fallback_bbox=bbox)
        print(
            beam['name'], 'dim=', beam_section_dim(beam),
            'bbox=', [round(v, 1) for v in bbox] if bbox else None,
            'is_h=', is_h,
        )

report = {'P35': {'name': 'P35', 'points': points, 'lajes': []}}
reconcile_beam_fundo_facts(beams)
enrich_pillar_report_with_beams(report, beams)

entry = report['P35']
print('\n--- output_slots nivel pilar ---')
for key, value in entry.items():
    if key in ('points', 'lajes', 'face_beams'):
        continue
    print(key, '=', json.dumps(value, ensure_ascii=False, default=str)[:200])

print('\n--- face_beams ---')
for fid, data in (entry.get('face_beams') or {}).items():
    slim = {
        'passa_esq': (data.get('passa_esq') or {}).get('name'),
        'passa_dir': (data.get('passa_dir') or {}).get('name'),
        'passa_esq_behavior': (data.get('passa_esq') or {}).get('behavior'),
        'passa_dir_behavior': (data.get('passa_dir') or {}).get('behavior'),
        'para': [p.get('name') for p in (data.get('para') or [])],
    }
    print(fid, json.dumps(slim, ensure_ascii=False))
