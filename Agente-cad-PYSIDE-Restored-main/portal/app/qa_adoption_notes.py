"""Apontamento automático da adoção humana de camada QA (dono, 2026-10-03).

Quando um humano valida L1/L2/L3, o SA efetivo anterior e a camada adotada
viram um apontamento comparativo na lista de apontamentos, para depois
corrigir no motor SA o que o agente descobriu.

Consistência arquivo × SQLite (sem transação comum):
1. ``freeze`` grava o pacote imutável do evento ANTES do manifesto;
2. o evento entra no manifesto com ``apontamento: pendente`` (mesma escrita
   atômica da adoção);
3. ``publish_pending`` cria a sessão com ``origem_evento = event_id`` (UNIQUE)
   e só então marca ``criado``. Falha deixa pendente; a próxima chamada
   reprocessa sem duplicar.
"""
from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

log = logging.getLogger(__name__)

REVIEW_KEYS = ('round_id', 'source_version', 'source_sha256', 'verdict', 'note', 'assessment',
               'confidence_percent', 'confidence_basis', 'checks', 'unit_reviews', 'unit_coverage',
               'coverage', 'field_corrections', 'limitations', 'provider', 'model', 'post_review',
               'candidate_sha256', 'base_snapshot_sha256', 'promotion_blockers')
URL_CLASS = {'PIL': 'pilares', 'LAJ': 'lajes', 'FV': 'fundo'}
LEVEL_KEYS = {'nivel', 'nivel_str', 'level', 'level_str', 'nivel_chegada', 'nivel_saida',
              'slab_level', 'beam_level', 'topo', 'nivel_topo'}
MAX_DIFF_LINES = 60


def folder(obra_dir, pavimento, event_id):
    for value in (pavimento, event_id):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', value) or value in {'.', '..'}:
            raise ValueError('identidade de adoção inválida')
    return Path(obra_dir) / '.portal_overrides' / 'qa_adoptions' / pavimento / event_id


def freeze(obra_dir, pavimento, event, *, previous, candidate, record, previous_svg):
    """Congela antes/depois do evento; nada aqui depende de URLs que mudam."""
    from .qa_jobs import _atomic_write_text
    target = folder(obra_dir, pavimento, event['id'])
    review = {k: record.get(k) for k in REVIEW_KEYS}
    files = {'sa_anterior.json': json.dumps(previous, ensure_ascii=False, indent=2),
             'camada.json': json.dumps(candidate, ensure_ascii=False, indent=2),
             'revisao.json': json.dumps(review, ensure_ascii=False, indent=2, default=str)}
    if record.get('svg'):
        files['camada.svg'] = record['svg']
    if previous_svg:
        files['sa_anterior.svg'] = previous_svg
    for name, text in files.items():
        _atomic_write_text(target / name, text)


# ---------------------------------------------------------------- formatação
def _number(value, key=''):
    """Nível absoluto: 2 casas; demais medidas: até 1 casa, sem ',0'."""
    if isinstance(value, bool):
        return str(value)
    number = value
    if isinstance(value, str):
        try:
            number = float(value.strip().replace(',', '.'))
        except ValueError:
            return value
    if not isinstance(number, (int, float)) or not math.isfinite(number):
        return str(value)
    if key.lower() in LEVEL_KEYS:
        return f'{number:.2f}'.replace('.', ',')
    text = f'{round(number, 1):.1f}'.rstrip('0').rstrip('.')
    return '0' if text in {'-0', ''} else text.replace('.', ',')


def _show(value, key=''):
    if value is None:
        return '—'
    if isinstance(value, (int, float, str)) and not isinstance(value, bool):
        return _number(value, key)
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 120 else text[:117] + '…'


def _is_geometry(value):
    return (isinstance(value, list) and value and
            all(isinstance(p, (list, tuple)) and all(isinstance(c, (int, float)) for c in p) for p in value))


def diff(before, after, path=''):
    """Lista folhas alteradas; geometria resumida por quantidade de pontos."""
    if _is_geometry(before) or _is_geometry(after):
        if before != after:
            n0 = len(before) if isinstance(before, list) else 0
            n1 = len(after) if isinstance(after, list) else 0
            return [(path, f'geometria {n0} pts', f'geometria {n1} pts (coordenadas alteradas)')]
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for key in list(before) + [k for k in after if k not in before]:
            child = path + '/' + str(key)
            if key not in after:
                out.append((child, _show(before[key], str(key)), '(removido)'))
            elif key not in before:
                out.append((child, '(ausente)', _show(after[key], str(key))))
            else:
                out += diff(before[key], after[key], child)
        return out
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        out = []
        for index, (b, a) in enumerate(zip(before, after)):
            out += diff(b, a, path + '/' + str(index))
        return out
    if before != after:
        key = path.rsplit('/', 1)[-1]
        return [(path, _show(before, key), _show(after, key))]
    return []


def _counts(checks):
    tally = Counter(str((c or {}).get('status') or '?').lower() for c in checks or [] if isinstance(c, dict))
    return f"{tally.get('pass', 0)} PASS / {tally.get('fail', 0)} FAIL / {sum(v for k, v in tally.items() if k not in {'pass', 'fail'})} incertos"


def _read(target, name):
    path = target / name
    return path.read_text(encoding='utf-8') if path.is_file() else None


def page_url(base_url, obra_id, pavimento, classe, item, behavior, layer):
    url_class = URL_CLASS.get(classe) or f'laterais_{behavior}'
    from urllib.parse import urlencode
    query = urlencode({'pavimento': pavimento, 'classe': url_class, 'item': item, 'subvista': layer})
    return base_url.rstrip('/') + f'/obras/{obra_id}?{query}'


def comparison_png(previous_svg, layer_svg, layer):
    """PNG lado a lado dos SVGs congelados (sem PIL: um SVG composto → cairosvg)."""
    from . import qa_versions
    panels = [(t, s) for t, s in (('SA anterior', previous_svg), (f'{layer} adotada', layer_svg)) if s]
    if not panels:
        return None
    ns = 'http://www.w3.org/2000/svg'
    width, height, label = 900, 900, 50
    outer = ET.Element(f'{{{ns}}}svg', {'width': str(width * len(panels)), 'height': str(height + label),
                                         'viewBox': f'0 0 {width * len(panels)} {height + label}'})
    ET.SubElement(outer, f'{{{ns}}}rect', {'width': '100%', 'height': '100%', 'fill': '#ffffff'})
    for index, (title, svg) in enumerate(panels):
        inner = ET.fromstring(qa_versions.safe_svg(svg))
        inner.set('x', str(index * width)); inner.set('y', str(label))
        inner.set('width', str(width)); inner.set('height', str(height))
        inner.set('preserveAspectRatio', 'xMidYMid meet')
        outer.append(inner)
        text = ET.SubElement(outer, f'{{{ns}}}text', {'x': str(index * width + 16), 'y': '34',
                             'font-size': '26', 'font-family': 'sans-serif', 'fill': '#111111'})
        text.text = title
    import cairosvg
    return cairosvg.svg2png(bytestring=ET.tostring(outer, encoding='unicode').encode('utf-8'))


# ---------------------------------------------------------------- conteúdo
def _member_label(conn, member_id):
    row = conn.execute('SELECT login,nome FROM portal_membros WHERE id=?', (member_id,)).fetchone()
    return (row['nome'] or row['login']) if row else str(member_id)


def _identity(event):
    classe, behavior, item = event['key'].split('/', 2)
    return classe, behavior, item


def build_promote(conn, obra_dir, pavimento, event):
    classe, behavior, item = _identity(event)
    target = folder(obra_dir, pavimento, event['id'])
    review = json.loads(_read(target, 'revisao.json') or '{}')
    previous = json.loads(_read(target, 'sa_anterior.json') or 'null')
    candidate = json.loads(_read(target, 'camada.json') or 'null')
    previous_svg, layer_svg = _read(target, 'sa_anterior.svg'), _read(target, 'camada.svg')
    layer = event.get('layer') or '?'
    post = review.get('post_review') or {}
    changes = diff(previous, candidate)
    lines = [f"Camada {layer} adotada como SA por {_member_label(conn, event['member_id'])} em {event['at'][:16].replace('T', ' ')} UTC.",
             f"Item: {classe} {item} ({behavior}) — pavimento {pavimento}.",
             f"Rodada {event['round_id']} · agente {review.get('provider') or '?'} / {review.get('model') or '?'}.",
             f"Avaliação da versão anterior: veredito {review.get('verdict') or '?'}; {_counts(review.get('checks'))}.",
             f"Auditoria posterior do candidato: {post.get('assessment') or 'sem auditoria'}; {_counts(post.get('checks'))}.",
             f"Confiança DECLARADA pelo agente (não é acurácia medida): {_show(review.get('confidence_percent'))}%.",
             f"Pendências reconhecidas pelo humano na adoção: {'sim' if event.get('acknowledge_pending') else 'não'}."]
    corrections = review.get('field_corrections') or []
    if corrections:
        lines.append('')
        lines.append(f'Correções propostas pelo agente ({len(corrections)}):')
        for fix in corrections:
            key = str(fix.get('field_path', '')).rsplit('/', 1)[-1]
            proof = '; '.join(str(e.get('finding') if isinstance(e, dict) else e) for e in (fix.get('evidence') or [])[:2])
            lines.append(f"- {fix.get('field_path')}: {_show(fix.get('before'), key)} → {_show(fix.get('after'), key)}"
                         + (f" — {proof}" if proof else ''))
    lines.append('')
    lines.append(f'Diferenças apuradas SA anterior → {layer} adotada ({len(changes)}):')
    for path, before, after in changes[:MAX_DIFF_LINES]:
        lines.append(f'- {path}: {before} → {after}')
    if len(changes) > MAX_DIFF_LINES:
        lines.append(f'- … mais {len(changes) - MAX_DIFF_LINES} diferenças em evidencias.json')
    if review.get('limitations'):
        lines.append('')
        lines.append('Limitações declaradas: ' + '; '.join(str(x) for x in review['limitations'][:6]))
    if not previous_svg:
        lines.append('')
        lines.append('Viewer SA anterior indisponível ou com hash divergente: comparação visual só com a camada.')
    lines.append('')
    lines.append(f"Hashes: candidato {event['candidate_sha256'][:12]}… · base SA {str(review.get('base_snapshot_sha256'))[:12]}… · evento {event['id']}.")
    attachments = [{'nome': f'{classe}-{item}-evidencias.json', 'mime': 'application/json',
                    'blob': json.dumps({'event': event, 'sa_anterior': previous, 'camada_adotada': candidate,
                                        'diferencas': [dict(path=p, antes=b, depois=a) for p, b, a in changes],
                                        'revisao': review}, ensure_ascii=False, indent=2, default=str).encode('utf-8')}]
    if previous_svg:
        attachments.insert(0, {'nome': f'{classe}-{item}-SA-anterior.svg', 'mime': 'image/svg+xml', 'blob': previous_svg.encode('utf-8')})
    if layer_svg:
        attachments.insert(1 if previous_svg else 0, {'nome': f'{classe}-{item}-{layer}-adotada.svg', 'mime': 'image/svg+xml',
                                                      'blob': layer_svg.encode('utf-8')})
    try:
        capture = comparison_png(previous_svg, layer_svg, layer)
    except Exception:  # captura é conveniência; anexos SVG continuam íntegros
        log.exception('falha ao renderizar comparação da adoção %s', event['id'])
        capture = None
    title = f'QA {layer} adotada — {classe} {item}' + (f' {behavior}' if classe == 'LV' else '') + f' ({pavimento})'
    return title, '\n'.join(lines), capture, attachments, layer


def build_rollback(conn, pavimento, event):
    classe, behavior, item = _identity(event)
    layer = event.get('layer') or '?'
    text = (f"Adoção da camada {layer} (rodada {event['round_id']}) DESFEITA por "
            f"{_member_label(conn, event['member_id'])} em {event['at'][:16].replace('T', ' ')} UTC.\n"
            f"Item: {classe} {item} ({behavior}) — pavimento {pavimento}.\n"
            f"Evento de adoção desfeito: {event.get('promote_event_id') or '?'}. "
            'O apontamento da adoção permanece como histórico.')
    title = f'QA {layer} desfeita — {classe} {item}' + (f' {behavior}' if classe == 'LV' else '') + f' ({pavimento})'
    return title, text, None, [], layer


# ---------------------------------------------------------------- publicação
def _exists(conn, event_id):
    return conn.execute('SELECT 1 FROM portal_apontamento_sessoes WHERE origem_evento=?', (event_id,)).fetchone() is not None


def create(conn, *, obra_id, obra_dir, pavimento, event, base_url):
    """Cria a sessão do evento; repetir é no-op (origem_evento UNIQUE)."""
    from ..db import repository
    if _exists(conn, event['id']):
        return False
    builder = build_promote(conn, obra_dir, pavimento, event) if event['action'] == 'promote' else build_rollback(conn, pavimento, event)
    title, text, capture, attachments, layer = builder
    classe, behavior, item = _identity(event)
    url = page_url(base_url, obra_id, pavimento, classe, item, behavior, layer)
    meta = {'origem': 'qa_adocao', 'acao': event['action'], 'event_id': event['id'], 'round_id': event['round_id'],
            'layer': layer, 'classe': classe, 'item': item, 'behavior': behavior, 'pavimento': pavimento,
            'candidate_sha256': event.get('candidate_sha256')}
    point = dict(texto=text, pagina_url=url, pagina_titulo=title, seletor_elemento=None, elemento_tag=None,
                 elemento_role=None, elemento_texto=None, elemento_json=json.dumps(meta, ensure_ascii=False),
                 clique_x=0.0, clique_y=0.0, pagina_x=0.0, pagina_y=0.0, viewport_largura=0, viewport_altura=0,
                 captura_mime='image/png' if capture else None, captura_blob=capture, anexos=attachments)
    try:
        repository.inserir_sessao_apontamento_ui(conn, obra_id=obra_id, membro_id=event['member_id'], titulo=title,
            paginas=[{'pagina_url': url, 'pagina_titulo': title, 'pontos': [point]}], origem_evento=event['id'])
    except sqlite3.IntegrityError:
        if _exists(conn, event['id']):
            return False  # corrida com outro processo: já criado
        raise
    return True


def _mark(obra_dir, pavimento, event_ids):
    from .qa_interpretation import load_manifest, manifest_lock, manifest_path
    from .qa_jobs import _atomic_write_text
    with manifest_lock(obra_dir, pavimento):
        manifest = load_manifest(obra_dir, pavimento)
        for event in manifest['history']:
            if event.get('id') in event_ids:
                event['apontamento'] = 'criado'
        _atomic_write_text(manifest_path(obra_dir, pavimento), json.dumps(manifest, ensure_ascii=False, indent=2))


def publish_pending(conn, *, obra_id, obra_dir, pavimento, base_url):
    """Reprocessa todos os eventos pendentes do pavimento. Nunca levanta."""
    from .qa_interpretation import load_manifest
    done, failed = [], []
    try:
        pending = [e for e in load_manifest(obra_dir, pavimento)['history'] if e.get('apontamento') == 'pendente']
    except Exception:
        log.exception('manifesto QA ilegível para apontamentos')
        return {'criados': 0, 'pendentes': None}
    for event in pending:
        try:
            create(conn, obra_id=obra_id, obra_dir=obra_dir, pavimento=pavimento, event=event, base_url=base_url)
            done.append(event['id'])
        except Exception:
            log.exception('apontamento da adoção %s ficou pendente', event.get('id'))
            failed.append(event['id'])
    if done:
        try:
            _mark(obra_dir, pavimento, set(done))
        except Exception:  # sessão existe; próxima chamada só remarca (create é no-op)
            log.exception('falha ao marcar apontamentos criados')
    return {'criados': len(done), 'pendentes': len(failed)}
