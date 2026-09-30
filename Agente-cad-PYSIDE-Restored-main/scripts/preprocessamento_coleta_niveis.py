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
                                  context_level_reference=json.loads(args.reference))
    runner = result['runner']
    slabs = runner.slabs_found
    beams = runner.beams_found
    segments = collect_preficha_segments(beams, slabs, runner.pavimento_pillar_report,
                                         runner.pavimento_nivel_report)
    payload = {'level_report': runner.pavimento_nivel_report,
        'consumer_calls': getattr(runner, '_sa_level_consumer_calls', []),
        'state': {'pavimento': args.pav, 'pilares': list(runner.pavimento_pillar_report.values()),
        'slabs': [{'name': s['name'], 'nivel': (s.get('fields') or {}).get('laje_nivel'),
                   'points': s.get('points')} for s in slabs],
        'segmentos': {k:[serializable_segment(s) for s in v] for k,v in segments.items()}},
        'tables': {'slabs': [{'name':s['name'], 'extra_data_json':json.dumps({
            'level_inference':s.get('level_inference')})} for s in slabs],
                   'beams': [{'name':b['name'], 'data_json':json.dumps(b)} for b in beams]}}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
