"""Diagnóstico SOMENTE LEITURA sobre snapshots reais; nunca persiste resultado."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, '/opt/cad-analyzer')
section_spec = importlib.util.spec_from_file_location('src.core.beam_section_texts', '/tmp/cad_beam_section_texts_20261001.py')
section = importlib.util.module_from_spec(section_spec)
section_spec.loader.exec_module(section)
sys.modules['src.core.beam_section_texts'] = section
spec = importlib.util.spec_from_file_location('manual_semantics', '/tmp/cad_manual_semantics_20261001.py')
semantic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(semantic)
from portal.app.ficha_reader import _fonte_estrutural_producao

directory = Path('/opt/cad-analyzer/DADOS-OBRAS/Obra_TREINO_1')
for pav in ('13_PAV', '14_PAV'):
    state = json.loads((directory / f'estado_{pav}.json').read_text())
    source = _fonte_estrutural_producao(directory, pav)
    start = perf_counter()
    texts = semantic.source_texts(source)
    cold = (perf_counter()-start)*1000
    start = perf_counter()
    semantic.source_texts(source)
    warm = (perf_counter()-start)*1000
    times, errors, resolved = [], [], 0
    for classe, rows in (state.get('segmentos') or {}).items():
        if classe != 'fundo' and not classe.startswith('lateral_'):
            continue
        for row in rows:
            # Laterais existentes são linhas de 2 pontos; o novo editor envia
            # contornos fechados. Não inventar um retângulo para medir o legado.
            if len(row.get('points') or []) < 3:
                continue
            original = copy.deepcopy(row)
            start = perf_counter()
            try:
                patch, proof = semantic.recognize(row, classe, state, texts)
                times.append((perf_counter()-start)*1000)
                resolved += int(patch.get('beam_height') is not None)
                assert row == original, 'input mutated'
                assert 'points' not in patch, 'geometry rewritten'
            except Exception as exc:
                errors.append({'classe': classe, 'item': row.get('uid'), 'error': str(exc)})
    print(json.dumps({'pav': pav, 'source_available': bool(source), 'text_count': len(texts),
                      'cold_dxf_ms': round(cold, 2), 'cached_dxf_ms': round(warm, 2),
                      'segments': len(times), 'section_resolved': resolved,
                      'mean_ms': round(sum(times)/max(1,len(times)),2),
                      'max_ms': round(max(times, default=0),2), 'error_count': len(errors), 'errors': errors[:2],
                      'input_geometry_preserved': not errors}, ensure_ascii=False))
    beams = semantic.canonical_beams(Path('/opt/cad-analyzer/project_data.vision'), directory, pav)
    context = semantic.pillar_source(source)
    for classe, rows in [('pilares', state.get('pilares') or []), ('lajes', state.get('slabs') or [])]:
        errors, elapsed = [], []
        for row in rows:
            if len(row.get('points') or []) < 3:
                continue
            start = perf_counter()
            try:
                original = copy.deepcopy(row)
                patch, proof = semantic.recognize(row, classe, state, texts, beams, context)
                assert row == original and 'points' not in patch
                elapsed.append((perf_counter()-start)*1000)
            except Exception as exc:
                errors.append(str(exc))
        print(json.dumps({'pav': pav, 'classe': classe, 'items': len(elapsed), 'beams_available': beams is not None,
                          'mean_ms': round(sum(elapsed)/max(1,len(elapsed)),2),
                          'max_ms': round(max(elapsed,default=0),2), 'errors': errors[:3], 'error_count': len(errors)}))
