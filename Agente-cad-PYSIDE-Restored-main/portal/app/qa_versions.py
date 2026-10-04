"""Revisões de versões reais: evidência atual, opinião e proposta contextual.

Artefatos são derivados; nenhum resultado altera o SA ou os DXFs originais.
"""
from __future__ import annotations

import hashlib
import copy
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from . import ficha_reader, qa_human_notes

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
PREVIOUS = {'L1': 'sa', 'L2': 'c1', 'L3': 'c2'}


def interpretation_digest(svg, fields):
    """Identifica desenho e interpretação; mudanças só nos campos também contam."""
    clean = copy.deepcopy(fields)
    if isinstance(clean, dict):
        clean.pop('_qa_reference_svg', None)
        clean.pop('original_cad_measurements', None)
    payload = {'svg': digest(svg), 'fields': clean}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                   allow_nan=False).encode()).hexdigest()


def directory(obra_dir, pavimento, classe, item, behavior='para'):
    for value in (pavimento, classe, item, behavior):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', value) or value in {'.', '..'}:
            raise ValueError('identidade QA inválida')
    return Path(obra_dir) / '.portal_overrides' / 'qa_versions' / pavimento / classe / behavior / item


def digest(svg):
    # Matplotlib emits fresh clip IDs and metadata dates on every render.
    # Compare the drawing, not these serialization-only changes.
    # Preserve the historical hash format; HTML href normalization is display-only.
    root = ET.fromstring(safe_svg(svg, normalize_href=False))
    for parent in root.iter():
        for child in list(parent):
            if child.tag.rsplit('}', 1)[-1] == 'metadata':
                parent.remove(child)
    ids = {node.get('id'): f'qa-ref-{index}' for index, node in enumerate(root.iter()) if node.get('id')}
    for node in root.iter():
        for key, value in list(node.attrib.items()):
            if key == 'id':
                node.set(key, ids[value])
            else:
                value = re.sub(r'url\(#([^)]*)\)', lambda m: 'url(#'+ids.get(m[1], m[1])+')', value)
                if key.rsplit('}', 1)[-1] == 'href' and value.startswith('#'):
                    value = '#' + ids.get(value[1:], value[1:])
                node.set(key, value)
    canonical = ET.canonicalize(ET.tostring(root, encoding='unicode'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def candidate_level_unit_errors(candidate):
    """Reject explicit centimetre suffixes on absolute levels, without converting data.

    Heights and local distances remain in cm. Numeric levels and unspecified
    placeholders do not gain a unit or a correctness verdict from this gate.
    """
    keys = {'nivel', 'nivel_str', 'level', 'level_str', 'nivel_chegada',
            'nivel_saida', 'slab_level', 'beam_level'}
    errors = []

    def visit(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                location = path + '/' + str(key).replace('~', '~0').replace('/', '~1')
                if (key in keys and isinstance(child, str) and
                        re.search(r'[-+]?\d+(?:[.,]\d+)?\s*cm\b', child, re.I)):
                    errors.append(location + ': nível absoluto rotulado em cm; conferir datum e fonte, corrigir explicitamente em m antes de aprovar')
                visit(child, location)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + '/' + str(index))

    if isinstance(candidate, dict):
        visit(candidate.get('collections', {}), '/collections')
    return errors


def candidate_integrity_errors(candidate, svg):
    if not candidate:
        return []
    errors = candidate_level_unit_errors(candidate)
    if candidate.get('classe') != 'PIL':
        return errors
    from .qa_interpretation import fingerprint
    from src.core.pillar_abcd_tables import validate_face_slab_beam_invariant
    root = ET.fromstring(safe_svg(svg)) if svg else None
    if (root is None or root.get('data-qa-pil-render') != 'snapshot-abcd-v1' or
            root.get('data-qa-interpretation-sha256') != fingerprint(candidate)):
        errors.append('viewer PIL não comprova reconstrução da interpretação candidata exata; solicite nova revisão')
    for row in candidate.get('collections', {}).get('pilares', []):
        tables = row.get('interpretacao_abcd')
        if tables:
            errors.extend('ABCD: '+v['detail'] for v in validate_face_slab_beam_invariant(tables))
    return errors


def read(obra_dir, pavimento, classe, item, behavior='para'):
    folder = directory(obra_dir, pavimento, classe, item, behavior)
    result = {}
    for layer in ('L1', 'L2', 'L3'):
        path = folder / (layer + '.json')
        if path.is_file():
            record = json.loads(path.read_text(encoding='utf-8'))
            svg_path = folder / (record['round_id'] + '.svg')
            record['svg'] = svg_path.read_text(encoding='utf-8') if record.get('viewer_generated') and svg_path.is_file() else None
            # Uma aprovação histórica pode preceder o gate atual de unidades.
            # Bloquear adoção sem reescrever a rodada ou o veredito do agente.
            from .qa_review_contract import _level_unit_errors, _local_proof_errors, transition_errors, cited_read_errors
            unit_errors = _level_unit_errors(record.get('post_review') or {}) + _local_proof_errors(record.get('post_review') or {})
            unit_errors += transition_errors(record, record.get('post_review') or {})
            unit_errors += cited_read_errors(record) + cited_read_errors(record.get('post_review') or {})
            unit_errors += candidate_integrity_errors(record.get('candidate_interpretation'), record.get('svg'))
            from . import qa_cad_gate
            unit_errors += qa_cad_gate.errors(qa_cad_gate.for_snapshot(obra_dir, pavimento, record.get('candidate_interpretation')))
            if unit_errors:
                record['promotion_ready'] = False
                record['promotion_blockers'] = list(record.get('promotion_blockers') or []) + unit_errors
            result[layer] = record
    for layer, previous in (('L2', 'L1'), ('L3', 'L2')):
        record = result.get(layer)
        prior = result.get(previous) or {}
        if record and (not prior.get('svg') or prior.get('stale') or record.get('source_sha256') != digest(prior['svg'])):
            record['stale'] = True
            record['svg'] = None
        if record and prior.get('svg') and prior.get('candidate_interpretation'):
            fields = {'sa_snapshot':prior['candidate_interpretation'], 'base_sa_snapshot':prior['base_sa_snapshot']}
            if record.get('source_interpretation_sha256') != interpretation_digest(prior['svg'],fields):
                record['stale'] = True
                record['svg'] = None
    return result


def _lateral_label(group, points, side, full_label, frame_width):
    """Compact segment identity; fit its own span without changing CAD points."""
    identity = re.search(r'\bSEG\s*(\d+)\b', str(full_label), re.I)
    caption = side + identity[1] if identity else side + ' ' + str(full_label)
    left, right = min(x for x,y in points), max(x for x,y in points)
    size = min(frame_width / 80, (right-left) * .75 / (.65*len(caption)))
    if size <= 0 or not math.isfinite(size):
        raise ValueError('largura de etiqueta lateral inválida')
    label = ET.SubElement(group, '{'+NS+'}text', {
        'x':str((left+right)/2), 'y':str(min(y for x,y in points)-2),
        'fill':'#ffffff', 'font-size':str(size), 'text-anchor':'middle',
        'font-family':'sans-serif', 'font-weight':'bold',
        'stroke':'#000000', 'stroke-width':str(size*.08), 'paint-order':'stroke',
        'data-qa-lateral-label':'compact-v1'})
    label.text = caption
    ET.SubElement(label, '{'+NS+'}title').text = side + ' ' + str(full_label)
    return label


def current_sa(obra_dir, pavimento, classe, item, behavior='para', *, obra_id='', html_root=None):
    state = ficha_reader.ler_estado_pavimento(obra_dir, pavimento)
    if not state:
        raise LookupError('estado SA não encontrado')
    from . import qa_interpretation
    sa_snapshot = qa_interpretation.snapshot(state, classe, item, behavior)
    adopted = qa_interpretation.effective_entry(obra_dir, pavimento, classe, item, behavior, state)
    if adopted:
        record_path = directory(obra_dir, pavimento, classe, item, behavior) / (adopted['round_id']+'.svg')
        record = json.loads(record_path.with_suffix('.json').read_text(encoding='utf-8'))
        svg = record_path.read_text(encoding='utf-8')
        if adopted['candidate_sha256'] != qa_interpretation.fingerprint({'interpretation':sa_snapshot,'svg':digest(svg)}):
            raise ValueError('artefato do SA adotado diverge da versão validada')
        return svg, {'sa_snapshot': sa_snapshot, 'base_sa_snapshot': sa_snapshot}
    if classe == 'FV':
        from .fv_ficha import montar_ficha_fv
        data = montar_ficha_fv(obra_dir, pavimento, item, state, html_fichas_root=html_root)
        svg = data['context']['layers']['sa'].get('svg')
        fields = data['segments']
    elif classe == 'LV':
        from .lv_ficha import resolver_camada_lv, montar_ficha_lv, _stack_cut_svgs
        data = montar_ficha_lv(obra_dir, pavimento, item, behavior, state, include_svgs=False)
        photos = []
        for side in ('A', 'B'):
            card = resolver_camada_lv(obra_dir, pavimento, item, behavior, state, 'sa',
                    obra_id=obra_id, side=side, segment_index=0)
            drawing = card.get('svg')
            if card.get('mode') == 'torre_context':
                from .lv_ficha import _torre_context_itens
                from . import dxf_preview
                structural_class = 'lateral_' + side.lower() + '_' + behavior
                source_info, _, _ = _torre_context_itens(obra_dir, pavimento, state, structural_class)
                raw = dxf_preview.renderizar_dxf_completo_cacheado(Path(source_info['path']), obra_dir / '.previews')
                node = ET.fromstring(raw.decode() if isinstance(raw, bytes) else raw)
                own = [float(v) for v in node.get('viewBox').split()]
                sx, sy = own[2]/card['frame_px'][0], own[3]/card['frame_px'][1]
                box = card['viewbox']
                node.set('viewBox', f'{own[0]+box[0]*sx} {own[1]+box[1]*sy} {box[2]*sx} {box[3]*sy}')
                group = ET.SubElement(node, '{'+NS+'}g', {'id':'qa-lateral-'+side})
                for highlight in card['highlights']:
                    pts = [[own[0]+x*sx, own[1]+y*sy] for x,y in highlight['points']]
                    ET.SubElement(group, '{'+NS+'}polygon', {'points':' '.join(f'{x},{y}' for x,y in pts),
                        'fill':'#ff69b4','fill-opacity':'0.15','stroke':'#ff69b4','stroke-width':'0.5'})
                    _lateral_label(group, pts, side, highlight['label'], box[2]*sx)
                drawing = ET.tostring(node, encoding='unicode')
            photos.append(drawing)
        if not all(photos):
            raise ValueError('contexto estrutural A/B indisponível para revisar lateral')
        svg = _stack_cut_svgs(photos)
        fields = {side: data['sides'][side]['segments'] for side in ('A', 'B')}
    else:
        structural_class = {'PIL': 'pilares', 'LAJ': 'lajes'}[classe]
        row = ficha_reader.obter_item_n1(state, structural_class, item)
        if row is None:
            raise LookupError('item não encontrado no SA atual')
        fields = {key: row.get(key) for key in ('campos', 'points', 'interpretacao_abcd')}
        if classe == 'LAJ':
            from .laje_ficha import resolver_camada_laje
            svg = resolver_camada_laje(obra_dir, pavimento, item, state, 'sa').get('svg')
        else:
            from . import pillar_level_view, pillar_abcd_review
            from .routers.n1_routes import _resumo_pilar_n1
            summary = _resumo_pilar_n1(state, obra_dir, item, pavimento) or {}
            tables = pillar_level_view.enrich_pillar_abcd_levels(
                row.get('interpretacao_abcd') or {}, state, summary.get('nivel_chegada'),
                pillar_level_view.load_preprocess_slab_levels(obra_dir, pavimento),
                pillar_name=item, beam_dim_texts=pillar_level_view.load_beam_dimension_texts(state))
            fields['interpretacao_abcd_portal'] = pillar_abcd_review.apply_review(tables, obra_dir, pavimento, item)
            fields['resumo_pilar'] = summary
            photos = ficha_reader.resolver_fotos_portal(obra_dir, pavimento, structural_class, row)
            views = ficha_reader.resolver_visualizacoes_n1_pilar(obra_dir, pavimento, structural_class, row,
                         foto_n1_fallback=photos.get('n1'), html_fichas_root=html_root)
            svg = views.get('com_tag') or views.get('proximo')
            fields['_qa_reference_svg'] = views.get('proximo')
            from .item_geometry import load
            if item in load(obra_dir, pavimento).get('edits', {}).get('pilares', {}):
                svg = ficha_reader._svg_sa_laje_contextual(obra_dir, pavimento, row, classe=structural_class)
    if not svg or '<svg' not in svg:
        raise ValueError('viewer SA contextual indisponível')
    if not isinstance(fields, dict):
        fields = {'segments': fields}
    fields['sa_snapshot'] = sa_snapshot
    fields['base_sa_snapshot'] = sa_snapshot
    return svg, fields


def availability(obra_dir, pavimento, classe, item, behavior='para'):
    records = read(obra_dir, pavimento, classe, item, behavior)
    layers = {}
    for layer, record in records.items():
        # HTML does not resolve arbitrary XML prefixes (e.g. ns4:href).
        # Normalize only the displayed copy; persisted hashes/history stay exact.
        if record.get('svg'):
            record['svg'] = safe_svg(record['svg'])
        key = layer.lower().replace('l', 'c')
        layers[key] = {'available': bool(record.get('svg')), 'svg': record.get('svg'), 'lazy': False}
    return records, layers


def source(obra_dir, pavimento, classe, item, layer, behavior='para', **kwargs):
    if layer == 'L1':
        return current_sa(obra_dir, pavimento, classe, item, behavior, **kwargs)
    previous = {'L2': 'L1', 'L3': 'L2'}[layer]
    records = read(obra_dir, pavimento, classe, item, behavior)
    prior = records.get(previous) or {}
    if not prior.get('svg'):
        raise ValueError(f'{layer} exige viewer populado da {previous}')
    first = records.get('L1') or {}
    if first:
        current, current_fields = current_sa(obra_dir, pavimento, classe, item, behavior, **kwargs)
        if first.get('source_sha256') != digest(current):
            raise ValueError('SA alterado desde a Camada 1; solicite novamente L1')
        if first.get('source_interpretation_sha256') and first['source_interpretation_sha256'] != interpretation_digest(current, current_fields):
            raise ValueError('campos SA alterados desde a Camada 1; solicite novamente L1')
    if 'interpretation' in prior:
        if prior.get('candidate_interpretation'):
            return prior['svg'], {'sa_snapshot': copy.deepcopy(prior['candidate_interpretation']),
                'base_sa_snapshot': copy.deepcopy(prior['base_sa_snapshot'])}
        return prior['svg'], {
            'source_interpretation': copy.deepcopy(prior['interpretation']),
            'geometry_proposals': copy.deepcopy(prior.get('proposed') or []),
            'geometry_coordinate_space': 'svg_viewBox',
            'pending_field_corrections': copy.deepcopy(prior.get('field_corrections') or []),
            'field_corrections_applied': False,
        }
    return prior['svg'], prior.get('proposed') or []


def safe_svg(svg, *, normalize_href=True):
    root = ET.fromstring(svg)
    # HTML readers lowercase SVG attributes; XML renderers require canonical case.
    for node in root.iter():
        for low, proper in (('viewbox', 'viewBox'), ('preserveaspectratio', 'preserveAspectRatio')):
            if low in node.attrib:
                node.set(proper, node.attrib.pop(low))
    for parent in root.iter():
        for node in list(parent):
            if node.tag.rsplit('}', 1)[-1] in {'script', 'foreignObject', 'image'}:
                parent.remove(node)
        for key, value in list(parent.attrib.items()):
            if key.lower().startswith('on'):
                del parent.attrib[key]
            elif key.rsplit('}', 1)[-1] == 'href' and not value.startswith('#'):
                del parent.attrib[key]
            elif 'url(' in value and 'url(#' not in value:
                del parent.attrib[key]
            elif normalize_href and key.rsplit('}', 1)[-1] == 'href' and key != 'href':
                # SVG2 href works in XML renderers and inline HTML, unlike nsN:href.
                parent.set('href', value)
                del parent.attrib[key]
    # A use without href can recurse into its own document in CairoSVG.
    for parent in root.iter():
        for node in list(parent):
            if node.tag.rsplit('}', 1)[-1] == 'use' and not any(k.rsplit('}', 1)[-1] == 'href' for k in node.attrib):
                parent.remove(node)
    root.attrib.pop('style', None)  # Browser sizing must not override image dimensions.
    return ET.tostring(root, encoding='unicode')


def render_png(svg_path, png_path):
    import subprocess
    import sys
    subprocess.run([sys.executable, '-m', 'cairosvg', str(svg_path), '-o', str(png_path),
                    '--output-width', '1800', '--output-height', '1800'],
                   check=True, timeout=60, capture_output=True)


def prepare(settings, obra, round_row, item):
    import cairosvg
    obra_dir = Path(obra.get('local_path') or settings.dados_obras_dir / obra['nome'])
    behavior = round_row.get('behavior', 'para')
    svg, fields = source(obra_dir, round_row['pavimento'], round_row['classe'], item,
                         round_row['layer'], behavior, obra_id=obra['id'],
                         html_root=settings.repo_root / 'scripts/arete/html_fichas' / obra['nome'])
    folder = settings.repo_root / 'scripts/arete/relatorios/qa_portal' / round_row['id'] / item
    folder.mkdir(parents=True, exist_ok=True)
    reference = fields.pop('_qa_reference_svg', None) if isinstance(fields, dict) else None
    if not reference and isinstance(fields,dict) and fields.get('sa_snapshot'):
        from . import qa_interpretation
        state = ficha_reader.ler_estado_pavimento(obra_dir,round_row['pavimento'])
        reference = qa_interpretation.render(obra_dir,round_row['pavimento'],fields['sa_snapshot'],state,
                                             round_row['layer'],reference=True)
    if reference:
        (folder / 'reference.svg').write_text(safe_svg(reference), encoding='utf-8')
        render_png(folder / 'reference.svg', folder / 'reference.png')
    from . import qa_cad_gate
    if isinstance(fields, dict) and fields.get('sa_snapshot', {}).get('classe') in ('PIL', 'LAJ'):
        fields['original_cad_measurements'] = qa_cad_gate.for_snapshot(obra_dir, round_row['pavimento'], fields['sa_snapshot'])
    (folder / 'source.svg').write_text(safe_svg(svg), encoding='utf-8')
    (folder / 'fields.json').write_text(json.dumps(fields, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
    render_png(folder / 'source.svg', folder / 'source.png')
    notes = qa_human_notes.load(obra_dir, round_row['pavimento'], round_row['classe'], item, behavior)
    from . import qa_review_contract
    documents = qa_review_contract.knowledge(settings.repo_root, round_row['classe'], folder)
    context = '\n'.join('- ' + str(path.relative_to(settings.repo_root)) for path in
                         (folder / 'source.svg', folder / 'source.png', folder / 'fields.json',
                          folder / 'knowledge.json', folder / 'rules.json'))
    context += '\n' + documents
    if reference:
        context += '\nREFERÊNCIA N1 SEM TAGS SA GERADAS:\n- ' + str((folder / 'reference.png').relative_to(settings.repo_root))
        context += '\n- ' + str((folder / 'reference.svg').relative_to(settings.repo_root))
    context += qa_review_contract.evidence_audit(settings, obra, round_row, item, folder)
    context += qa_review_contract.instructions(round_row['classe'], PREVIOUS[round_row['layer']])
    if round_row['classe'] == 'PIL' and fields.get('sa_snapshot'):
        from src.core.pillar_abcd_tables import validate_face_slab_beam_invariant
        tables = fields['sa_snapshot']['collections']['pilares'][0].get('interpretacao_abcd')
        if tables:
            context += '\nCONTRADIÇÕES ABCD A CONFERIR NO CAD E NO MANUAL (não são correção automática): '+json.dumps(
                validate_face_slab_beam_invariant(tables),ensure_ascii=False)
        context += '\nMedições independentes em fields.json.original_cad_measurements: pares de paredes + rótulo de seção no DXF original, com handles e hash. Confira os handles no original e as imagens. Divergência obriga fail de dimensoes/distancias_cantos, nunca pass por alegação de engrossamento sem parede. Corrija todas as referências da viga e as distâncias em interpretacao_abcd. Ausência/ambiguidade exige uncertain; não invente medidas. Este gate não certifica altura/cota/semântica pela largura isolada.'
        context += '\nO candidato PIL desenha exatamente interpretacao_abcd do snapshot. Se mudar papel, canto, dimensão ou nível de uma ligação, corrija também essa tabela nas collections; um patch em nivel_str sozinho não muda seus vínculos. Não aprove BB/BD por concordância com JSON: confira a regra de chega/laje no manual vigente e o contato CAD.'
    if round_row['classe'] == 'LAJ' and fields.get('original_cad_measurements'):
        context += '\nMedições independentes em fields.json.original_cad_measurements: rótulo, h= e cota escritos DENTRO do contorno de cada laje/degrau no DXF original (E1), com handles e hash. Divergência medida obriga fail do critério (identidade_contorno, dimensoes_espessura, niveis). Status uncertain = nada escrito ou valores ambíguos: aí niveis só pode passar com outra prova independente citada (corte/delta E3, validação humana E8); vizinhas com mesmo nível (E4) nunca bastam sozinhas. Não invente cotas.'
    context += '\nNOTAS HUMANAS POR VERSÃO: ' + json.dumps(notes, ensure_ascii=False)
    return context, svg, obra_dir


def validate_result(result):
    if result.status != 'completed':
        return
    suggestion = result.suggestion or {}
    checks = suggestion.get('checks')
    if not isinstance(checks, list) or not checks or any(
        not isinstance(check, dict) or not check.get('criterion') or not check.get('observation')
        or check.get('status') not in {'pass', 'fail', 'uncertain'} for check in checks):
        raise ValueError('revisão sem critérios e observações verificáveis')
    if result.verdict == 'validou' and (suggestion.get('action') != 'manter' or suggestion.get('proposed')):
        raise ValueError('aprovação deve manter a versão sem gerar geometria')
    if result.verdict == 'validou' and any(c['status'] != 'pass' for c in checks):
        raise ValueError('aprovação contradiz critérios falhos ou incertos')
    if result.verdict == 'invalidou' and suggestion.get('action') not in {'corrigir', 'revisar_humano'}:
        raise ValueError('reprovação sem encaminhamento válido')


def corrected_svg(svg, proposed):
    root = ET.fromstring(safe_svg(svg))
    view = [float(v) for v in re.split(r'[ ,]+', root.get('viewBox', '').strip())]
    if len(view) != 4 or not all(math.isfinite(v) for v in view) or view[2] <= 0 or view[3] <= 0:
        raise ValueError('viewBox ausente na evidência')
    if not isinstance(proposed, list) or not proposed:
        raise ValueError('correção sem contornos')
    # Base original é preservada. A correção é identificada por cor e título próprios.
    for node in list(root):
        if node.get('id') == 'qa-correction':
            root.remove(node)
    group = ET.SubElement(root, '{'+NS+'}g', {'id': 'qa-correction'})
    ET.SubElement(group, '{'+NS+'}title').text = 'Proposta de correção agêntica; referência anterior preservada'
    for row in proposed:
        points = row.get('points') if isinstance(row, dict) else None
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError('contorno corrigido precisa de três vértices')
        if any(not isinstance(p, list) or len(p) != 2 or any(isinstance(n, bool) or
               not isinstance(n, (int, float)) or not math.isfinite(n) for n in p) for p in points):
            raise ValueError('coordenadas inválidas')
        area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points, points[1:]+points[:1]))) / 2
        if area <= 1e-6:
            raise ValueError('contorno degenerado')
        from shapely.geometry import Polygon
        from shapely.validation import explain_validity
        contour = Polygon(points)
        if not contour.is_valid:
            raise ValueError('contorno topologicamente inválido: ' + explain_validity(contour))
        if any(not (view[0] <= x <= view[0]+view[2] and view[1] <= y <= view[1]+view[3]) for x,y in points):
            raise ValueError('contorno fora do viewBox da evidência')
        polygon = ET.SubElement(group, '{'+NS+'}polygon', {'points':' '.join(f'{x},{y}' for x,y in points),
            'fill':'#00e5ff', 'fill-opacity':'.18', 'stroke':'#00e5ff', 'stroke-width':'2',
            'vector-effect':'non-scaling-stroke', 'data-prop-label':str(row.get('label') or '')})
        ET.SubElement(polygon, '{'+NS+'}title').text = str(row.get('note') or row.get('role') or '')
    return ET.tostring(root, encoding='unicode')


def persist(obra_dir, round_row, result, svg, fields=None):
    from .qa_jobs import _atomic_write_text
    validate_result(result)
    if result.status != 'completed':
        return
    suggestion = result.suggestion or {}
    generate = result.verdict == 'invalidou' and suggestion.get('action') == 'corrigir'
    package = suggestion.pop('_candidate_package', None)
    output = package['svg'] if package else (corrected_svg(svg, suggestion.get('proposed')) if generate else None)
    folder = directory(obra_dir, round_row['pavimento'], round_row['classe'], result.item,
                       round_row.get('behavior', 'para'))
    record = {'round_id':round_row['id'], 'source_version':PREVIOUS[round_row['layer']],
              'source_sha256':digest(svg), 'verdict':result.verdict, 'note':result.note,
              'confidence_percent':suggestion.get('confidence_percent'), 'checks':suggestion.get('checks'),
              'proposed':suggestion.get('proposed'), 'provider':result.provider, 'model':result.model,
              'viewer_generated':generate,
              'assessment':suggestion.get('assessment'),
              'coverage':suggestion.get('coverage'),
              'unit_reviews':suggestion.get('unit_reviews'),
              'unit_coverage':suggestion.get('unit_coverage'),
              'confidence_basis':suggestion.get('confidence_basis'),
              'field_corrections':suggestion.get('field_corrections', []),
              'execution_audit':suggestion.get('execution_audit'),
              'limitations':suggestion.get('limitations', [])}
    if fields is not None:
        snapshot = copy.deepcopy(fields)
        if isinstance(snapshot, dict):
            snapshot.pop('_qa_reference_svg', None)
        record.update({'snapshot_schema': 1, 'interpretation': snapshot,
                       'source_interpretation_sha256': interpretation_digest(svg, fields),
                       'authority': 'agentic', 'human_validated': False,
                       'corrections_applied': False,
                       'promotion_ready': False,
                       'promotion_blockers': ['interpretação corrigida e adaptador SA ainda não materializados']})
    if package:
        from .qa_interpretation import fingerprint
        post_review = suggestion.get('post_review')
        ready = bool(post_review and post_review.get('status') == 'completed' and
                     post_review.get('execution_audit') and suggestion.get('execution_audit'))
        from .qa_review_contract import transition_errors
        blockers = transition_errors(suggestion, post_review or {}) + candidate_integrity_errors(package['interpretation'], output)
        from . import qa_cad_gate
        blockers += qa_cad_gate.errors(package.get('original_cad_measurements'))
        ready = ready and not blockers
        record.update(candidate_interpretation=package['interpretation'],
            base_sa_snapshot=fields['base_sa_snapshot'], base_snapshot_sha256=fingerprint(fields['base_sa_snapshot']),
            candidate_sha256=fingerprint({'interpretation':package['interpretation'],'svg':digest(output)}),
            corrections_applied=True, viewer_generated=True, post_review=post_review,
            promotion_ready=ready, promotion_blockers=blockers if blockers else ([] if ready else ['exige auditorias concluídas com comprovantes reais de leitura das evidências']))
    if output:
        _atomic_write_text(folder / (round_row['id'] + '.svg'), output)
    text = json.dumps(record, ensure_ascii=False, indent=2)
    _atomic_write_text(folder / (round_row['id'] + '.json'), text)
    _atomic_write_text(folder / (round_row['layer'] + '.json'), text)


def materialize_candidate(settings, obra, round_row, result, fields, obra_dir):
    """Reconstrói e entrega evidência nova à auditoria posterior; nenhuma adoção."""
    from . import qa_interpretation, qa_review_contract
    suggestion = result.suggestion or {}
    original = fields.get('sa_snapshot') if isinstance(fields, dict) else None
    if not original:
        return None  # histórico v3 não tem autoridade de promoção
    candidate = qa_interpretation.compile_candidate(original, suggestion)
    state = ficha_reader.ler_estado_pavimento(obra_dir, round_row['pavimento'])
    state = qa_interpretation.replace_item(state, candidate)
    svg = qa_interpretation.render(obra_dir, round_row['pavimento'], candidate, state, round_row['layer'])
    folder = settings.repo_root / 'scripts/arete/relatorios/qa_portal' / round_row['id'] / result.item / 'candidate'
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'source.svg').write_text(safe_svg(svg), encoding='utf-8')
    render_png(folder/'source.svg', folder/'source.png')
    from . import qa_cad_gate
    original_cad = qa_cad_gate.for_snapshot(obra_dir, round_row['pavimento'], candidate)
    candidate_fields = {'sa_snapshot':candidate}
    if original_cad is not None:
        candidate_fields['original_cad_measurements'] = original_cad
    (folder/'fields.json').write_text(json.dumps(candidate_fields,ensure_ascii=False,indent=2),encoding='utf-8')
    reference = qa_interpretation.render(obra_dir, round_row['pavimento'], candidate, state, round_row['layer'], reference=True)
    (folder/'reference.svg').write_text(safe_svg(reference),encoding='utf-8')
    render_png(folder/'reference.svg',folder/'reference.png')
    context = '\n'.join('- '+str(p.relative_to(settings.repo_root)) for p in
                        (folder/'source.svg',folder/'source.png',folder/'fields.json',folder/'reference.svg',folder/'reference.png'))
    context += '\n'+qa_review_contract.knowledge(settings.repo_root,round_row['classe'],folder)
    context += '\nDocumentos auditáveis: '+str((folder/'knowledge.json').relative_to(settings.repo_root))+'; '+str((folder/'rules.json').relative_to(settings.repo_root))
    context += '\nNotas humanas salvas: '+json.dumps(qa_human_notes.load(obra_dir,round_row['pavimento'],round_row['classe'],result.item,round_row.get('behavior','para')),ensure_ascii=False)
    context += qa_review_contract.evidence_audit(settings,obra,round_row,result.item,folder)
    context += qa_review_contract.instructions(round_row['classe'],'candidato reconstruído')
    context += '\nAUDITORIA POSTERIOR: julgue este candidato, sem nova correção nesta execução. Use action=manter quando todos os critérios passarem; caso contrário action=revisar_humano. Confira também os efeitos das mudanças: '+json.dumps(suggestion.get('field_corrections') or [],ensure_ascii=False)
    context += '\nACHADOS ANTERIORES: '+json.dumps(suggestion.get('checks') or [],ensure_ascii=False)
    context += '\nACHADOS ANTERIORES POR UNIDADE: '+json.dumps([
        {'criterion_id':str(unit.get('unit_path'))+'/'+key, 'source_status':detail.get('status'),
         'observation':detail.get('observation')}
        for unit in suggestion.get('unit_reviews') or [] if isinstance(unit,dict)
        for key,detail in (unit.get('checks') or {}).items() if isinstance(detail,dict)
        and detail.get('status') in {'fail','uncertain'}],ensure_ascii=False)
    context += '\nPara cada critério antes fail/uncertain e agora pass, envie suggestion.finding_resolutions com criterion_id, source_status, disposition (corrected|resolved_uncertainty|retracted), reason, evidence (reference.png/reference.svg com location e finding) e rule_refs. Explique o que mudou ou por que o achado anterior estava errado. Uma mudança de confiança não resolve um achado. Confronte marcas ABCD com a regra chega/laje e reporte contradições da própria ficha.'
    context += '\nPara achados por unidade, criterion_id é unit_path + / + nome do critério, como listado acima. A resolução do check geral não substitui a resolução de cada unidade.'
    context += '\nGATES DETERMINÍSTICOS DO CANDIDATO: '+json.dumps(candidate_integrity_errors(candidate, svg),ensure_ascii=False)
    return_source = {'checks':suggestion.get('checks') or [], 'unit_reviews':suggestion.get('unit_reviews') or []}
    context += '\nGATE DE PAREDES E RÓTULOS DXF ORIGINAIS: '+json.dumps(original_cad,ensure_ascii=False)
    return {'svg':svg,'interpretation':candidate,'context':context,'folder':folder,'source_review':return_source,
            'original_cad_measurements':original_cad}
