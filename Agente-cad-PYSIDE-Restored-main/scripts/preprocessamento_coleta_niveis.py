"""Canonical N1 collection for pre-SA levels; no production publication."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    ap = argparse.ArgumentParser()
    for key in ('dxf', 'obra', 'pav', 'out'):
        ap.add_argument('--'+key, required=True)
    ap.add_argument('--reference', required=True)
    ap.add_argument('--convention', default='{}')
    args = ap.parse_args()
    os.environ['CAD_SA_DISABLE_FAST_CACHE'] = '1'
    os.environ['CAD_MOTOR_HEADLESS'] = '1'
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from scripts.arete.headless_sa_analise import _run_legacy_analysis
    from src.core.preficha_segments import collect_preficha_segments, serializable_segment
    result = _run_legacy_analysis(args.dxf, args.obra, args.pav, build_html=False,
                                  project_id='pre-sa-level-collection', db_path=str(Path(args.out).with_suffix('.sqlite3')),
                                  context_level_reference=json.loads(args.reference),
                                  context_convention=json.loads(args.convention))
    runner = result['runner']
    slabs = runner.slabs_found
    beams = runner.beams_found
    segments = collect_preficha_segments(beams, slabs, runner.pavimento_pillar_report,
                                         runner.pavimento_nivel_report)
    payload = {'context_calls': getattr(runner, '_sa_context_calls', []),
        'level_report': runner.pavimento_nivel_report,
        'consumer_calls': getattr(runner, '_sa_level_consumer_calls', []),
        'state': {'pavimento': args.pav, 'db_path': str(Path(args.out).with_suffix('.sqlite3')),
        'pilares': list(runner.pavimento_pillar_report.values()),
        'slabs': [{'name': s['name'], 'nivel': (s.get('fields') or {}).get('laje_nivel'),
                   'points': s.get('points'), 'fields': s.get('fields'),
                   'links': s.get('links') or {},
                   'level_inference': s.get('level_inference'),
                   'slab_steps': s.get('slab_steps') or [],
                   'level_links': (s.get('links') or {}).get('laje_nivel'),
                   'cut_links': (s.get('links') or {}).get('laje_visao_corte')}
                  for s in slabs],
        'segmentos': {k:[serializable_segment(s) for s in v] for k,v in segments.items()}},
        'tables': {'slabs': [{'name':s['name'], 'extra_data_json':json.dumps({
            'level_inference':s.get('level_inference')})} for s in slabs],
                   'beams': [{'name':b['name'], 'data_json':json.dumps(b)} for b in beams]}}
    from portal.app.structural_cut_overlay import collect_sections
    # The headless runner exposes records in memory; it need not persist a
    # beams table in its temporary SQLite. Scope section assembly to this pass.
    section_state = dict(payload['state'])
    section_state.pop('db_path', None)
    section_state['_section_beam_records'] = {str(b['id']): b for b in beams if b.get('id')}
    payload['beam_sections'] = collect_sections(Path(args.obra), args.pav, section_state)
    # The temporary SQLite belongs only to this subprocess. Its data is now
    # represented in the frozen inventory, never published as a dangling path.
    payload['state'].pop('db_path', None)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
