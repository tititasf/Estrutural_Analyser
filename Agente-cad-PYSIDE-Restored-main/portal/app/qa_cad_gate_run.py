"""Gate CAD automático pós-SA: mede cada item do pavimento no DXF original.

Roda logo depois que o SA publica o estado N1 (``pipeline_runner``) e grava um
sidecar por pavimento em ``.portal_overrides/qa_cad_gate/<pav>.json``.  Só
avisa: não altera o estado do SA nem bloqueia o job.  A ficha do item lê o
sidecar e marca "desatualizado" quando o item mudou depois da medição.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from . import ficha_reader, item_geometry, qa_cad_gate as gate, qa_interpretation as interp

log = logging.getLogger(__name__)

# seção do SA -> (classe do gate, coleção SA, campo do nome do item)
SECOES = {
    'pilares': ('PIL', 'pilares', 'name'),
    'lajes': ('LAJ', 'lajes', 'name'),
    'fundos_viga': ('FV', 'fundo', 'beam_name'),
    # LV: um item por viga e comportamento ("V301|para"), faces A e B juntas.
    'laterais_viga': ('LV', 'lateral_a_para', 'beam_name'),
}
# classe da ficha no portal -> classe do gate
CLASSE_PORTAL = {'pilares': 'PIL', 'pilares_especiais': 'PIL', 'lajes': 'LAJ', 'fundo': 'FV',
                 **{f'lateral_{lado}_{beh}': 'LV' for lado in 'ab' for beh in ('para', 'passa')}}
LV_COLECOES = [f'lateral_{lado}_{beh}' for beh in ('para', 'passa') for lado in 'ab']


def _snapshot(state, classe, name):
    if classe == 'LV':
        beam, behavior = name.split('|')
        return interp.snapshot(state, 'LV', beam, behavior)
    return interp.snapshot(state, classe, name)


def sidecar_path(obra_dir, pav):
    return Path(obra_dir) / '.portal_overrides' / 'qa_cad_gate' / f'{pav}.json'


def _read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    os.replace(tmp, path)


def resumo(report):
    """Status do item: confere / diverge / incerto / indisponivel, com as mensagens."""
    if not report:
        return None
    if report.get('error'):
        return dict(status='indisponivel', divergencias=[], incertos=['CAD original: ' + report['error']],
                    medidos=0)
    div, inc, medidos = [], [], 0
    for c in report.get('contacts', []):
        where = f"face {c['face']} {c['beam']}" if 'face' in c else f"{c.get('item')} {c.get('aspect')}"
        if c.get('status') == 'measured':
            medidos += 1
            div += [f'{where}: {m}' for m in (c.get('errors') or {}).values()]
        elif c.get('blocks_promotion', True):
            inc.append(f"{where}: {c.get('reason') or 'sem medição'}")
    status = 'diverge' if div else 'incerto' if inc else 'confere'
    return dict(status=status, divergencias=div, incertos=inc, medidos=medidos)


def run_pavimento(obra_dir, pav, secao=None, item_names=None):
    """Mede os itens do pavimento (ou só a seção/itens do microciclo) e grava o sidecar."""
    obra_dir = Path(obra_dir)
    started = time.perf_counter()
    state = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    source = ficha_reader._fonte_estrutural_producao(obra_dir, pav)
    if not state:
        return None
    path = sidecar_path(obra_dir, pav)
    data = _read(path) if (secao or item_names) else {}
    data.update(schema='cad.qa_gate_pavimento/v1', pavimento=pav,
                source=str(source) if source else None,
                source_sha256=gate._sha256(source) if source else None)
    classes = data.setdefault('classes', {})
    slabs = None
    for sec, (classe, colecao, nome) in SECOES.items():
        if secao and secao != sec:
            continue
        if classe == 'LV':
            pares = {(str(r.get(nome)), col.split('_')[2]) for col in LV_COLECOES
                     for r in item_geometry.collection(state, col) or [] if r.get(nome)}
            names = sorted(f'{b}|{beh}' for b, beh in pares if not item_names or b in item_names)
        else:
            rows = item_geometry.collection(state, colecao) or []
            names = sorted({str(r.get(nome)) for r in rows if r.get(nome)})
            if item_names:
                names = [n for n in names if n in item_names]
        bucket = classes.setdefault(classe, {})
        if not (secao or item_names):
            bucket.clear()
        t0 = time.perf_counter()
        for name in names:
            try:
                snap = _snapshot(state, classe, name)
                if not source:
                    report = dict(error='DXF original indisponível', contacts=[])
                elif classe == 'PIL':
                    report = gate.measure(source, snap)
                elif classe == 'LAJ':
                    report = gate.measure_slabs(source, snap)
                else:
                    if slabs is None:
                        slabs = [row for item in ficha_reader.listar_itens_n1(state, 'lajes')
                                 for row in interp.snapshot(state, 'LAJ', item['item_id'])['collections']['lajes']]
                    report = (gate.measure_lateral_beams if classe == 'LV' else gate.measure_beams)(
                        source, snap, slabs, pav)
                bucket[name] = dict(resumo(report), snapshot_sha256=interp.fingerprint(snap),
                                    medido_em=time.strftime('%Y-%m-%dT%H:%M:%S'))
            except Exception as exc:  # um item ruim não derruba os outros
                log.exception('gate CAD falhou em %s/%s/%s', pav, classe, name)
                bucket[name] = dict(status='indisponivel', divergencias=[], incertos=[f'falha do gate: {exc}'],
                                    medidos=0, medido_em=time.strftime('%Y-%m-%dT%H:%M:%S'))
        data.setdefault('tempos_s', {})[classe] = round(time.perf_counter() - t0, 1)
    data['gerado_em'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    data['duracao_s'] = round(time.perf_counter() - started, 1)
    _write(path, data)
    return path


def best_effort(obra_dir, pav, secao=None, item_names=None):
    if secao and secao not in SECOES:
        return None
    try:
        return run_pavimento(obra_dir, pav, secao=secao, item_names=item_names)
    except Exception:
        log.exception('gate CAD pós-SA falhou em %s', pav)
        return None


def item_name(classe_portal, item_id, beam_name=None):
    if classe_portal == 'fundo':
        return beam_name or item_id
    if CLASSE_PORTAL.get(classe_portal) == 'LV':
        return f"{beam_name or item_id}|{classe_portal.split('_')[2]}"
    return item_id.removesuffix('_Para').removesuffix('_Passa')


def classe_status(obra_dir, pav, classe_portal):
    """{nome do item: status} da classe, para os selos da lista (uma leitura só)."""
    classe = CLASSE_PORTAL.get(classe_portal)
    if not classe:
        return {}
    bucket = (_read(sidecar_path(obra_dir, pav)).get('classes') or {}).get(classe, {})
    return {name: entry.get('status') for name, entry in bucket.items()}


def item_status(obra_dir, pav, classe_portal, item_id, state=None, beam_name=None):
    """Resultado do gate para a ficha do item, ou None se não houver medição."""
    classe = CLASSE_PORTAL.get(classe_portal)
    if not classe:
        return None
    name = item_name(classe_portal, item_id, beam_name)
    classes = _read(sidecar_path(obra_dir, pav)).get('classes') or {}
    entry = classes.get(classe, {}).get(name)
    # Visão Corte (D-92) da viga ou da laje, numa caixa própria da mesma ficha.
    vc = classes.get('VC', {}).get(name.split('|')[0]) if classe in ('FV', 'LV', 'LAJ') else None
    if not entry:
        return dict(status=None, visao_corte=vc) if vc else None
    entry = dict(entry)
    if vc:
        entry['visao_corte'] = vc
    if state is not None and entry.get('snapshot_sha256'):
        try:
            entry['desatualizado'] = interp.fingerprint(_snapshot(state, classe, name)) != entry['snapshot_sha256']
        except Exception:
            entry['desatualizado'] = True
    return entry
