"""Gate CAD automático pós-SA: mede cada item do pavimento no DXF original.

Roda logo depois que o SA publica o estado N1 (``pipeline_runner``) e grava um
sidecar por pavimento em ``.portal_overrides/qa_cad_gate/<pav>.json``.
``measure_state`` oferece a mesma medição sem publicar ou escrever arquivos. Só
avisa: não altera o estado do SA nem bloqueia o job.  A ficha do item lê o
sidecar e marca "desatualizado" quando o item mudou depois da medição.
"""
from __future__ import annotations

import json
import logging
import os
import time
from copy import deepcopy
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
    div, inc, avisos, medidos = [], [], [], 0
    for c in report.get('contacts', []):
        where = f"face {c['face']} {c['beam']}" if 'face' in c else f"{c.get('item')} {c.get('aspect')}"
        if c.get('status') == 'measured':
            medidos += 1
            div += [f'{where}: {m}' for m in (c.get('errors') or {}).values()]
        elif c.get('blocks_promotion', True):
            inc.append(f"{where}: {c.get('reason') or 'sem medição'}")
        else:
            avisos.append(f"{where}: {c.get('reason') or 'sem medição'}")
    # Optional aspects may remain uncertain after a real measurement, but an
    # empty report (or only optional uncertainties) is never proof of agreement.
    if medidos == 0:
        inc.extend(avisos)
        if not inc:
            inc.append('nenhum aspecto medido no CAD original')
    status = 'diverge' if div else 'incerto' if inc else 'confere'
    return dict(status=status, divergencias=div, incertos=inc, medidos=medidos)


def measure_state(source, state, pav, secao=None, item_names=None, obra_dir=None):
    """Measure an in-memory SA state without loading or writing published data.

    Return the canonical sidecar report (including per-class timings). Source
    DXF access is read-only. A filtered measurement includes only requested
    items; merging it into a published sidecar belongs to ``run_pavimento``.
    """
    if not state:
        return None
    started = time.perf_counter()
    # collection/snapshot helpers may fill absent keys with setdefault.
    # Keep this API observational even for incomplete caller-owned states.
    state = deepcopy(state)
    # Published states pass through ficha_reader, which reconstructs regional
    # thickness contours. Raw SA snapshots omit this derived geometry. Use the
    # same adapter here so development and published QA measure the same CAD.
    # Explicit steps (including a reviewed empty list) remain authoritative.
    region_error = None
    missing_steps = [row for row in state.get('slabs', []) if 'slab_steps' not in row]
    if source and missing_steps and secao != 'pilares':
        try:
            from src.core.slab_steps import enrich_state
            enrich_state({'slabs': missing_steps}, source)
        except Exception as exc:
            log.exception('gate CAD: reconstrução das regiões falhou em %s', pav)
            region_error = f'regiões de laje indisponíveis: {exc}'
    data = dict(schema='cad.qa_gate_pavimento/v1', pavimento=pav,
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
        t0 = time.perf_counter()
        for name in names:
            try:
                snap = _snapshot(state, classe, name)
                if not source:
                    report = dict(error='DXF original indisponível', contacts=[])
                elif region_error and classe != 'PIL':
                    report = dict(error=region_error, contacts=[])
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
    if obra_dir is not None and secao in VC_SECOES:
        _measure_cortes(data, obra_dir, pav, source, state, slabs, region_error, item_names)
    data['gerado_em'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    data['duracao_s'] = round(time.perf_counter() - started, 1)
    return data


# Visão Corte (D-92): cortes originais e interpretados de cada viga e degraus de
# laje.  Depende das lajes e dos fundos, então roda com qualquer uma dessas seções.
VC_SECOES = {None, 'lajes', 'fundos_viga', 'laterais_viga'}


def _measure_cortes(data, obra_dir, pav, source, state, slabs, region_error, item_names):
    from . import qa_cad_gate_cortes as cortes
    bucket = data['classes'].setdefault('VC', {})
    t0 = time.perf_counter()
    now = time.strftime('%Y-%m-%dT%H:%M:%S')
    try:
        if not source or region_error:
            raise RuntimeError(region_error or 'DXF original indisponível')
        if slabs is None:
            slabs = [row for item in ficha_reader.listar_itens_n1(state, 'lajes')
                     for row in interp.snapshot(state, 'LAJ', item['item_id'])['collections']['lajes']]
        reports = cortes.measure_obra(obra_dir, pav, source, state, slabs, item_names=item_names)
        for name, report in sorted(reports.items()):
            bucket[name] = dict(resumo(report), snapshot_sha256=cortes.inputs_fingerprint(report), medido_em=now)
    except Exception as exc:
        log.exception('gate CAD Visão Corte falhou em %s', pav)
        data['classes']['VC'] = {'*': dict(status='indisponivel', divergencias=[], medidos=0,
                                           incertos=[f'falha do gate Visão Corte: {exc}'], medido_em=now)}
    data.setdefault('tempos_s', {})['VC'] = round(time.perf_counter() - t0, 1)


def run_pavimento(obra_dir, pav, secao=None, item_names=None):
    """Measure the published state and atomically save its QA sidecar."""
    obra_dir = Path(obra_dir)
    started = time.perf_counter()
    state = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    source = ficha_reader._fonte_estrutural_producao(obra_dir, pav)
    measured = measure_state(source, state, pav, secao=secao, item_names=item_names, obra_dir=obra_dir)
    if measured is None:
        return None
    path = sidecar_path(obra_dir, pav)
    if secao or item_names:
        data = _read(path)
        classes = data.setdefault('classes', {})
        for classe, bucket in measured['classes'].items():
            classes.setdefault(classe, {}).update(bucket)
        if 'tempos_s' in measured:
            data.setdefault('tempos_s', {}).update(measured['tempos_s'])
        data.update({key: value for key, value in measured.items()
                     if key not in {'classes', 'tempos_s'}})
    else:
        data = measured
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
