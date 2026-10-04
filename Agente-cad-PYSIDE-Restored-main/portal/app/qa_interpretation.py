"""Snapshots SA completos e adoção humana derivada, sem reescrever fontes."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import uuid
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import item_geometry


def classes(classe, behavior='para'):
    if classe == 'LV' and behavior in {'para', 'passa'}:
        return [f'lateral_a_{behavior}', f'lateral_b_{behavior}']
    try:
        return [{'PIL': 'pilares', 'LAJ': 'lajes', 'FV': 'fundo'}[classe]]
    except KeyError as exc:
        raise ValueError('classe/comportamento SA inválido') from exc


def snapshot(state, classe, item, behavior='para'):
    groups = {}
    for structural_class in classes(classe, behavior):
        groups[structural_class] = [copy.deepcopy(row) for row in item_geometry.collection(state, structural_class)
            if str(row.get('name') if classe in {'PIL', 'LAJ'} else row.get('beam_name')) == item]
    if not any(groups.values()):
        raise LookupError('item ausente no snapshot SA')
    return {'schema': 'cad.qa_interpretation/v1', 'classe': classe, 'item': item,
            'behavior': behavior, 'coordinate_space': 'cad_world_cm', 'collections': groups}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def replace_item(state, value):
    result = copy.deepcopy(state)
    for key, candidates in value['collections'].items():
        rows = item_geometry.collection(result, key)
        rows[:] = [row for row in rows if str(row.get('name') if value['classe'] in {'PIL', 'LAJ'}
                    else row.get('beam_name')) != value['item']]
        rows.extend(copy.deepcopy(candidates))
    return result


def validate(value, original):
    from shapely.geometry import Polygon, LineString
    if not isinstance(value, dict) or any(value.get(key) != original.get(key) for key in
            ('schema', 'classe', 'item', 'behavior', 'coordinate_space')):
        raise ValueError('candidato altera identidade ou espaço de coordenadas SA')
    groups = value.get('collections')
    if not isinstance(groups, dict) or set(groups) != set(original['collections']):
        raise ValueError('candidato incompleto: todas as coleções do item são obrigatórias')
    fingerprint(value)  # rejeita NaN/infinito em qualquer campo
    identities = set()
    for key, rows in groups.items():
        if not isinstance(rows, list):
            raise ValueError('coleção SA deve ser uma lista')
        if value['classe'] in {'PIL', 'LAJ'} and len(rows) != 1:
            raise ValueError('candidato deve conter exatamente um pilar/laje')
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('registro SA inválido')
            identity = item_geometry.identity(row, key)
            owner = row.get('name') if value['classe'] in {'PIL', 'LAJ'} else row.get('beam_name')
            if not identity or str(owner) != value['item'] or (key, identity) in identities:
                raise ValueError('identidade SA duplicada, vazia ou pertencente a outro item')
            identities.add((key, identity))
            if value['classe'] == 'LV' and isinstance(row.get('lv_cell'), dict):
                previous = next((r for r in original['collections'][key]
                                 if item_geometry.identity(r, key) == identity), {})
                cell_level = row['lv_cell'].get('level')
                old_cell_level = (previous.get('lv_cell') or {}).get('level')
                changed_level = row.get('level') != previous.get('level') or cell_level != old_cell_level
                def normalized_level(level):
                    text = str(level).strip().replace(',', '.')
                    try:
                        return float(text)
                    except (ValueError, TypeError):
                        return text
                if changed_level and row.get('level') not in (None, '') and cell_level not in (None, '') and normalized_level(row['level']) != normalized_level(cell_level):
                    raise ValueError('correção LV deixa level e lv_cell.level contraditórios; corrija todas as ocorrências comprovadas')
            if value['classe'] == 'LV' and (str(row.get('side', '')).upper() != key.split('_')[1].upper()
                    or str(row.get('behavior', '')).lower() != value['behavior']):
                raise ValueError('lado/comportamento do segmento não corresponde à coleção')
            points = row.get('points')
            if not isinstance(points, list) or len(points) < (2 if value['classe']=='LV' else 3) or any(
                    not isinstance(p, (list, tuple)) or len(p) != 2 or any(
                    isinstance(n, bool) or not isinstance(n, (float, int)) or not math.isfinite(n)
                    for n in p) for p in points):
                raise ValueError('geometria SA inválida: vértices CAD finitos obrigatórios')
            if value['classe']=='LV' and len(points)==2:
                geometry = LineString(points)
                if not geometry.is_valid or geometry.length <= 1e-6:
                    raise ValueError('linha lateral degenerada')
            else:
                polygon = Polygon(points)
                if not polygon.is_valid or polygon.area <= 1e-6:
                    raise ValueError('geometria SA cruzada ou degenerada')
            if value['classe'] in {'FV', 'LV'}:
                label = str(row.get('segment_label', ''))
                if not re.fullmatch(r'[1-9][0-9]{0,3}', label):
                    raise ValueError('segmento precisa de índice positivo')
                label_key = (key, 'segment:' + label)
                if label_key in identities:
                    raise ValueError('índice de segmento duplicado')
                identities.add(label_key)
    if not identities:
        raise ValueError('interpretação completa não pode excluir o item inteiro')
    return copy.deepcopy(value)


def compile_candidate(original, suggestion):
    """Resposta completa ou patches JSON Pointer, sempre sobre cópia do SA."""
    complete = suggestion.get('candidate_interpretation')
    if complete is not None:
        if suggestion.get('field_corrections'):
            raise ValueError('escolha snapshot completo OU patches; não envie ambos')
        if not suggestion.get('candidate_evidence') or not suggestion.get('candidate_rule_refs'):
            raise ValueError('interpretação completa exige suggestion.candidate_evidence e suggestion.candidate_rule_refs não vazios; ou use apenas patches com candidate_interpretation=null')
        if fingerprint(complete) == fingerprint(original):
            raise ValueError('candidato não altera a interpretação SA')
        return validate(complete, original)
    candidate = copy.deepcopy(original)
    corrections = suggestion.get('field_corrections') or []
    if not corrections:
        raise ValueError('correção sem interpretação completa ou patches SA')
    paths = set()
    for correction in corrections:
        path = correction.get('field_path', '')
        if not isinstance(path, str) or not path.startswith('/collections/') or any(
                path == previous or path.startswith(previous+'/') or previous.startswith(path+'/') for previous in paths):
            raise ValueError('field_path deve ser JSON Pointer único relativo ao snapshot, começando /collections/; remova o prefixo /sa_snapshot (exemplo: /collections/lajes/0/height)')
        paths.add(path)
        if not correction.get('evidence') or not correction.get('rule_refs'):
            raise ValueError('correção de campo sem evidência/regra')
        parts = [p.replace('~1', '/').replace('~0', '~') for p in path[1:].split('/')]
        def index(part):
            if not re.fullmatch(r'0|[1-9][0-9]*', part):
                raise ValueError('índice de lista JSON Pointer inválido')
            return int(part)
        target = candidate
        try:
            for part in parts[:-1]:
                target = target[index(part)] if isinstance(target, list) else target[part]
            key = index(parts[-1]) if isinstance(target, list) else parts[-1]
            before = target[key] if isinstance(target, list) else target.get(key)
            if 'before' not in correction or before != correction['before'] or 'after' not in correction:
                raise ValueError('valor before não corresponde ao snapshot SA')
            target[key] = copy.deepcopy(correction['after'])
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError('caminho de correção SA inexistente') from exc
    return validate(candidate, original)


def render(obra_dir, pavimento, candidate, state, layer, *, reference=False):
    """Render novo do CAD original + interpretação candidata; não usa HTML antigo."""
    import xml.etree.ElementTree as ET
    from . import ficha_reader, dxf_preview
    from .qa_versions import safe_svg, NS
    source = ficha_reader._fonte_estrutural_producao(Path(obra_dir), pavimento)
    if not source:
        raise ValueError('DXF estrutural original indisponível para reconstruir viewer')
    rows = [row for group in candidate['collections'].values() for row in group]
    points = [p for row in rows for p in row['points']]
    source_bbox = dxf_preview.obter_bbox_dxf(source)
    if not source_bbox or any(not (source_bbox[0]-1e-6 <= p[0] <= source_bbox[2]+1e-6 and
                source_bbox[1]-1e-6 <= p[1] <= source_bbox[3]+1e-6) for p in points):
        raise ValueError('geometria candidata fora dos limites do CAD original ou CAD sem limites')
    if candidate['classe'] == 'PIL' and not reference:
        from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar
        from scripts.arete.pil_agentic_highlight_draw import render_agentic_svg
        row = rows[0]
        slabs = state.get('slabs') or []
        tables = copy.deepcopy(row.get('interpretacao_abcd')) or build_abcd_tables_from_pillar(row,
            slab_height_map={s['name']: s.get('height') for s in slabs if s.get('name')},
            slab_nivel_map={s['name']: s.get('nivel') for s in slabs if s.get('name')},
            slab_points_map={s['name']: s.get('points') for s in slabs if s.get('name')},
            beams=state.get('beams') or [], nivel_viga_default='')
        if not isinstance(tables, dict) or not isinstance(tables.get('faces'), dict):
            raise ValueError('interpretação ABCD candidata inválida')
        root = ET.fromstring(safe_svg(render_agentic_svg(source, row['points'], tables, layer=layer.lower())))
        root.set('data-qa-pil-render', 'snapshot-abcd-v1')
        root.set('data-qa-interpretation-sha256', fingerprint(candidate))
        return ET.tostring(root, encoding='unicode')
    bbox = (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points))
    rendered = dxf_preview.renderizar_dxf_svg_com_transform_cacheado(source,
        Path(obra_dir) / '.previews' / 'qa_interpretation',
        bbox=ficha_reader._recorte_contextual_laje(bbox, source_bbox), margem_pct=0,
        largura_px=1400, altura_px=900)
    root = ET.fromstring(safe_svg(rendered.svg.decode()))
    if reference:
        return ET.tostring(root, encoding='unicode')
    vx, vy, vw, vh = map(float, root.get('viewBox').split())
    x0, y0, x1, y1 = rendered.bbox_dxf
    def transform(p):
        return vx + (p[0]-x0)/(x1-x0)*vw, vy + (y1-p[1])/(y1-y0)*vh
    group = ET.SubElement(root, '{'+NS+'}g', {'id': 'qa-interpretation'})
    legend = []
    for row in rows:
        converted = [transform(p) for p in row['points']]
        ET.SubElement(group, '{'+NS+'}'+('polyline' if len(converted)==2 else 'polygon'), {'points': ' '.join(f'{x},{y}' for x,y in converted),
            'fill': 'none' if len(converted)==2 else '#00e5ff', 'fill-opacity': '.15', 'stroke': '#00e5ff', 'stroke-width': '1.5',
            'vector-effect': 'non-scaling-stroke', 'data-sa-id': item_geometry.identity(row,
                'lajes' if candidate['classe']=='LAJ' else 'fundo')})
        content = [candidate['item']]
        if row.get('segment_label'):
            content.append(str(row.get('side') or '')+' S'+str(row['segment_label']))
        for key in ('height', 'nivel', 'length', 'width', 'beam_height', 'level', 'section_dim'):
            if row.get(key) is not None and row.get(key) != '':
                content.append(key+'='+str(row[key]))
        legend.append(' · '.join(content))
        compact = (str(row.get('side') or '')+' S'+str(row['segment_label'])) if row.get('segment_label') else candidate['item']
        label = ET.SubElement(group, '{'+NS+'}text', {
            'x': str(sum(x for x,y in converted)/len(converted)),
            'y': str(sum(y for x,y in converted)/len(converted)), 'fill': 'white',
            'stroke': '#07131f', 'stroke-width': '.6', 'paint-order': 'stroke',
            'font-size': str(vw/180), 'text-anchor': 'middle',
            'style': 'fill:#ffffff;stroke:#07131f;font-family:Arial,sans-serif'})
        label.text = compact
    # Campos fora do CAD: um quadro separado evita que dezenas de tags ocultem
    # cotas, apoios e paredes que o auditor precisa conferir no desenho original.
    font = vw/120
    line_height = font*1.8
    band_height = line_height*(len(legend)+2)
    root.set('viewBox', f'{vx} {vy} {vw} {vh+band_height}')
    height_match = re.fullmatch(r'([0-9.]+)([a-z%]*)', root.get('height', '900'))
    if height_match and height_match[2] != '%':
        root.set('height', str(float(height_match[1])*(vh+band_height)/vh)+height_match[2])
    ET.SubElement(group, '{'+NS+'}rect', {'x':str(vx), 'y':str(vy+vh),
        'width':str(vw), 'height':str(band_height),
        'style':'fill:#07131f;stroke:none'})
    for index, content in enumerate([candidate['item']+' · interpretação '+layer+' · dimensões em cm; níveis em m']+legend):
        node = ET.SubElement(group, '{'+NS+'}text', {'x':str(vx+font),
            'y':str(vy+vh+line_height*(index+1)), 'font-size':str(font),
            'style':'fill:#ffffff;stroke:none;font-family:Arial,sans-serif'})
        node.text = content
    return ET.tostring(root, encoding='unicode')


def manifest_path(obra_dir, pavimento):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', pavimento) or pavimento in {'.', '..'}:
        raise ValueError('pavimento inválido')
    return Path(obra_dir) / '.portal_overrides' / 'qa_effective' / (pavimento+'.json')


def load_manifest(obra_dir, pavimento):
    path = manifest_path(obra_dir, pavimento)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'items':{}, 'history':[]}


@contextmanager
def manifest_lock(obra_dir, pavimento):
    """Serializa adoções entre processos; o kernel libera o lock em caso de crash."""
    path = manifest_path(obra_dir,pavimento).with_suffix('.lock')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as handle:
        if path.stat().st_size == 0:
            handle.write(b'0'); handle.flush()
        deadline = time.monotonic()+10
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ValueError('outra validação humana está em andamento; tente novamente')
                time.sleep(.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def key(classe, item, behavior='para'):
    return classe+'/'+behavior+'/'+item


def apply_effective(state, obra_dir, pavimento):
    """A fonte original e as alterações manuais mais novas nunca são sobrescritas."""
    manifest = load_manifest(obra_dir, pavimento)
    applied = {}
    for identity, entry in manifest['items'].items():
        try:
            base = snapshot(state, entry['classe'], entry['item'], entry['behavior'])
            if fingerprint(base) != entry['base_snapshot_sha256']:
                continue
            candidate = validate(entry['interpretation'], base)
            state = replace_item(state, candidate)
            applied[identity] = {'round_id':entry['round_id'], 'layer':entry['layer']}
        except LookupError:
            continue
    state['_qa_effective'] = applied
    return state


def effective_entry(obra_dir, pavimento, classe, item, behavior, state):
    identity = key(classe, item, behavior)
    marker = (state.get('_qa_effective') or {}).get(identity)
    entry = load_manifest(obra_dir, pavimento)['items'].get(identity)
    return entry if entry and marker and marker['round_id']==entry['round_id'] else None


def effective_svg(obra_dir, pavimento, classe, item, state, behavior='para', *, side=None):
    """Somente o artefato exato validado pelo humano ganha autoridade SA."""
    from . import qa_versions
    entry = effective_entry(obra_dir, pavimento, classe, item, behavior, state)
    if not entry:
        return None
    path = qa_versions.directory(obra_dir, pavimento, classe, item, behavior) / (entry['round_id']+'.svg')
    if not path.is_file():
        raise ValueError('viewer SA validado indisponível')
    svg = qa_versions.safe_svg(path.read_text(encoding='utf-8'))
    if fingerprint({'interpretation':entry['interpretation'], 'svg':qa_versions.digest(svg)}) != entry['candidate_sha256']:
        raise ValueError('viewer SA validado alterado')
    return svg


def promote(obra_dir, pavimento, classe, item, behavior, layer, round_id, token,
            member_id, *, acknowledge_pending=False, previous_svg=None):
    from . import ficha_reader, qa_adoption_notes, qa_versions
    from .fv_operations import _MUTATION_LOCK
    from .qa_jobs import _atomic_write_text
    with _MUTATION_LOCK, manifest_lock(obra_dir,pavimento):
        records = qa_versions.read(obra_dir, pavimento, classe, item, behavior)
        record = records.get(layer)
        if not record or record['round_id'] != round_id or record.get('stale'):
            raise ValueError('camada mudou ou está expirada; reabra antes de validar')
        if not record.get('promotion_ready') or token != record.get('candidate_sha256'):
            raise ValueError('candidato incompleto ou hash de validação divergente')
        if (record.get('post_review') or {}).get('assessment') != 'pass' and not acknowledge_pending:
            raise ValueError('revisão possui pendências; reconhecimento humano explícito obrigatório')
        state = ficha_reader.ler_estado_pavimento(obra_dir, pavimento)
        current = snapshot(state, classe, item, behavior)
        if fingerprint(current) != record.get('base_snapshot_sha256'):
            raise ValueError('SA mudou desde a revisão; solicite uma nova camada')
        candidate = validate(record['candidate_interpretation'], current)
        if fingerprint({'interpretation':candidate, 'svg':qa_versions.digest(record['svg'])}) != token:
            raise ValueError('conteúdo da camada alterado após publicação')
        manifest = load_manifest(obra_dir, pavimento)
        identity = key(classe, item, behavior)
        prior = manifest['items'].get(identity)
        # Hash da base sem adoção: futuras alterações manuais desativam a adoção antiga.
        unadopted = ficha_reader.ler_estado_pavimento(obra_dir, pavimento, apply_qa=False)
        event = {'id':str(uuid.uuid4()), 'action':'promote', 'member_id':member_id,
                 'at':datetime.now(timezone.utc).isoformat(), 'key':identity, 'previous':copy.deepcopy(prior),
                 'round_id':round_id, 'candidate_sha256':token, 'acknowledge_pending':acknowledge_pending,
                 'layer':layer, 'apontamento':'pendente'}
        # Antes/depois congelados antes do manifesto: o apontamento nunca perde a origem.
        qa_adoption_notes.freeze(obra_dir, pavimento, event, previous=current, candidate=candidate,
                                 record=record, previous_svg=previous_svg)
        manifest['items'][identity] = {'classe':classe, 'item':item, 'behavior':behavior,
            'layer':layer, 'round_id':round_id, 'member_id':member_id, 'at':event['at'],
            'candidate_sha256':token, 'interpretation':candidate,
            'base_snapshot_sha256':fingerprint(snapshot(unadopted, classe, item, behavior))}
        manifest['history'].append(event)
        _atomic_write_text(manifest_path(obra_dir,pavimento), json.dumps(manifest,ensure_ascii=False,indent=2))
        return {'effective':manifest['items'][identity], 'event_id':event['id']}


def rollback(obra_dir, pavimento, classe, item, behavior, expected_round_id, member_id):
    from .fv_operations import _MUTATION_LOCK
    from .qa_jobs import _atomic_write_text
    with _MUTATION_LOCK, manifest_lock(obra_dir,pavimento):
        manifest = load_manifest(obra_dir,pavimento)
        identity = key(classe,item,behavior)
        current = manifest['items'].get(identity)
        if not current or current['round_id'] != expected_round_id:
            raise ValueError('SA vigente mudou; reabra antes de desfazer')
        event = next((e for e in reversed(manifest['history']) if e['key']==identity and
                     e['action']=='promote' and e['round_id']==expected_round_id), None)
        if not event:
            raise ValueError('histórico de promoção indisponível')
        previous = event['previous']
        if previous:
            manifest['items'][identity] = copy.deepcopy(previous)
        else:
            manifest['items'].pop(identity)
        manifest['history'].append({'id':str(uuid.uuid4()), 'action':'rollback', 'key':identity,
            'round_id':expected_round_id, 'member_id':member_id, 'at':datetime.now(timezone.utc).isoformat(),
            'layer':event.get('layer'), 'promote_event_id':event['id'], 'apontamento':'pendente'})
        _atomic_write_text(manifest_path(obra_dir,pavimento),json.dumps(manifest,ensure_ascii=False,indent=2))
        return {'effective':previous}
