#!/usr/bin/env python
"""Exporta o pack SA usando o mesmo projeto, DXF e motor da interface humana.

O script resolve o registro ``projects`` exibido no Structural Analyzer,
carrega seu ``dxf_path`` e executa o próprio fluxo da Análise Geral em modo
offscreen. O padrão é somente leitura; ``--persist-db`` habilita commit
transacional depois dos quatro diagnósticos.
"""
from __future__ import annotations

import os
import sys
import re
import json
import html
import copy
import types
import argparse
import importlib
import hashlib
import pickle
import subprocess
import tempfile
import time
from pathlib import Path

# Esta CLI nunca pode herdar o backend visível do dashboard. ``setdefault``
# permitia QT_QPA_PLATFORM=windows vindo do processo pai e abria a app.
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
os.environ['MPLBACKEND'] = 'Agg'
os.environ['CAD_MOTOR_HEADLESS'] = '1'

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT   = _SCRIPT_DIR.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# A cache is only a performance artifact.  It must be invalidated by the
# *contents* of the source and of each N1 owner, never only by mtimes (which
# are particularly unreliable when a workspace is restored/copied).
_FAST_CONTEXT_CACHE_SCHEMA = 2
_FAST_CONTEXT_ENGINE_FILES = (
    'main.py',
    'scripts/analise_geral_headless.py',
    'src/core/dxf_loader.py',
    'src/core/spatial_index.py',
    'src/core/slab_tracer.py',
    'src/core/beam_tracer.py',
    'src/core/beam_interpreters/__init__.py',
    'src/core/beam_interpreters/fundo_viga.py',
    'src/core/beam_interpreters/lateral_viga.py',
    'src/core/beam_interpreters/pilar_viga.py',
    # O fast path reaplica este contrato depois de restaurar o snapshot. Logo
    # ele é dono real do resultado LV e precisa participar da assinatura.
    'src/core/lv_generation_contract.py',
    'src/core/fv_generation_contract.py',
    'src/core/pillar_face_beams.py',
)


def _fast_context_cache_path(dxf_path: str) -> Path:
    """Cache N1 content-addressed para o caminho rápido, sem MainWindow.

    O estado em cache foi produzido pelo mesmo ``BeamTracer`` e pelos
    interpretadores canônicos.  A assinatura inclui todos os donos reais de
    FV (inclusive o contrato N3, porque a ficha/preview dependem dele) e o
    conteúdo do DXF.  Assim uma alteração de motor, contrato ou fonte nunca
    reaproveita uma interpretação antiga.
    """
    signature: list[tuple[str, str]] = []
    for relative in _FAST_CONTEXT_ENGINE_FILES:
        path = _REPO_ROOT / relative
        signature.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
    source = Path(dxf_path).resolve()
    payload = repr((
        _FAST_CONTEXT_CACHE_SCHEMA,
        str(source),
        hashlib.sha256(source.read_bytes()).hexdigest(),
        signature,
    )).encode('utf-8')
    digest = hashlib.sha256(payload).hexdigest()
    return _REPO_ROOT / 'scripts' / 'arete' / '.cache' / 'n1_context' / f'{digest}.pkl'


def _restore_fast_context_cache(runner: 'HeadlessRunner', path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open('rb') as stream:
            state = pickle.load(stream)
        if state.get('schema') != _FAST_CONTEXT_CACHE_SCHEMA:
            return False
        for name in (
            'dxf_data', 'slabs_found', 'beams_found',
            'pavimento_pillar_report', 'pavimento_nivel_report',
            'slab_learning_config',
        ):
            setattr(runner, name, state[name])
        runner._analysis_texts = list(runner.dxf_data.get('texts', []))
        _bind_mainwindow_methods(runner)
        return True
    except Exception as exc:
        print(f'[SA] Cache N1 ignorado: {exc}', flush=True)
        return False


def _store_fast_context_cache(runner: 'HeadlessRunner', path: Path) -> None:
    state = {
        'schema': _FAST_CONTEXT_CACHE_SCHEMA,
        'dxf_data': runner.dxf_data,
        'slabs_found': runner.slabs_found,
        'beams_found': runner.beams_found,
        'pavimento_pillar_report': runner.pavimento_pillar_report,
        'pavimento_nivel_report': runner.pavimento_nivel_report,
        'slab_learning_config': runner.slab_learning_config,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    # Classes distintas podem materializar o mesmo snapshot N1 em paralelo.
    # O destino é determinístico, mas o arquivo de trabalho não pode ser:
    # dois ``.tmp`` iguais corromperiam a publicação atômica.
    temporary = path.with_suffix(f'.{os.getpid()}.tmp')
    with temporary.open('wb') as stream:
        pickle.dump(state, stream, protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(path)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_beam_name(name: str) -> str:
    """F.V305.C-1 -> FV-V305.C | L.V305.A-1 -> LV-V305.A"""
    if not name or name.startswith('FV-') or name.startswith('LV-'):
        return name
    m = re.match(r'^F\.(.+?)\.C(?:-\d+)?$', name)
    if m: return f'FV-{m.group(1)}.C'
    m = re.match(r'^F\.(.+?)(?:-\d+)?$', name)
    if m: return f'FV-{m.group(1)}.C'
    m = re.match(r'^L\.(.+?)\.([AB])(?:-\d+)?$', name)
    if m: return f'LV-{m.group(1)}.{m.group(2)}'
    m = re.match(r'^L\.(.+?)(?:-\d+)?$', name)
    if m: return f'LV-{m.group(1)}'
    return name


def _parse_item_names(raw_values: list[str] | None) -> set[str] | None:
    if not raw_values:
        return None
    names: set[str] = set()
    for raw in raw_values:
        for piece in raw.split(','):
            piece = piece.strip().upper()
            if piece:
                names.add(piece)
    return names or None


def _item_name(item: dict) -> str:
    return str(
        item.get('name')
        or item.get('laje_name')
        or item.get('beam_name')
        or item.get('key')
        or ''
    ).strip().upper()


def _matches_item_name(name: str, wanted: set[str]) -> bool:
    name = str(name or '').strip().upper()
    return (
        name in wanted
        or (name.startswith(('FV-', 'LV-')) and name[3:] in wanted)
    )


def _filter_named(items: list[dict], wanted: set[str]) -> list[dict]:
    return [item for item in items if _matches_item_name(_item_name(item), wanted)]


def _filter_pillar_report(report: dict, wanted: set[str]) -> dict:
    return {
        key: value for key, value in (report or {}).items()
        if _matches_item_name(str(key).upper(), wanted)
        or _matches_item_name(_item_name(value), wanted)
    }


def _apply_item_filter_to_window(window, sections: set[str], wanted: set[str]) -> None:
    if 'pilares' in sections:
        window.pillars_found = _filter_named(list(getattr(window, 'pillars_found', []) or []), wanted)
        window.pavimento_pillar_report = _filter_pillar_report(
            getattr(window, 'pavimento_pillar_report', {}) or {},
            wanted,
        )
        nivel = copy.deepcopy(getattr(window, 'pavimento_nivel_report', {}) or {})
        if isinstance(nivel.get('pilares'), dict):
            nivel['pilares'] = _filter_pillar_report(nivel['pilares'], wanted)
        window.pavimento_nivel_report = nivel
    if 'lajes' in sections:
        window.slabs_found = _filter_named(list(getattr(window, 'slabs_found', []) or []), wanted)
    if {'fundos_viga', 'laterais_viga'} & sections:
        window.beams_found = _filter_named(list(getattr(window, 'beams_found', []) or []), wanted)


def _partial_collections_for_sections(
    collections: dict[str, list[dict]],
    sections: set[str],
    wanted: set[str],
    *,
    beam_dependencies: set[str] | None = None,
) -> dict[str, list[dict]]:
    """Coleção mínima do microciclo, incluindo fatos de viga que ele corrigiu.

    PIL não deve regravar todas as vigas da planta. Porém, se a própria rodada
    corrigiu uma viga por sua ficha FV canônica, o commit parcial precisa levar
    essa dependência explícita; caso contrário o HTML vê o fato novo e o DB
    conserva o legado.
    """
    requested_beams = set(wanted) if {'fundos_viga', 'laterais_viga'} & sections else set()
    requested_beams.update(str(name).upper() for name in (beam_dependencies or set()))
    return {
        'pillars': (
            _filter_named(collections.get('pillars', []), wanted)
            if 'pilares' in sections else []
        ),
        'slabs': (
            _filter_named(collections.get('slabs', []), wanted)
            if 'lajes' in sections else []
        ),
        'beams': (
            _filter_named(collections.get('beams', []), requested_beams)
            if requested_beams else []
        ),
    }


def _log_selected_pillar_topology(pillars: list[dict], wanted: set[str] | None) -> None:
    if not wanted:
        return
    for pillar in pillars:
        if _item_name(pillar) not in wanted:
            continue
        facts = {
            key: value for key, value in pillar.items()
            if re.fullmatch(r'p_s[ABCD]_v_(?:passa_(?:esq|dir)|ch\d)_[nd]', key)
        }
        geometry_links = sum(
            1 for key, payload in (pillar.get('links') or {}).items()
            if key in facts and isinstance(payload, dict) and payload.get('geometry')
        )
        print(
            f'[SA-HUMAN] Topologia {_item_name(pillar)}: '
            f'{json.dumps(facts, ensure_ascii=False, sort_keys=True)}; '
            f'links_geometricos={geometry_links}',
            flush=True,
        )


def _beam_semantic_facts(beam: dict) -> tuple:
    """Assinatura dos fatos canônicos que justificam persistir uma dependência.

    Metadados de proveniência não contam como mudança semântica. Isso impede que
    um microciclo PIL regrave todas as vigas apenas porque o reconciliador marcou
    a fonte canônica em memória.
    """
    fields = beam.get('fields') or {}
    fundo_dims = tuple(sorted(
        (str(key), str(value))
        for key, value in fields.items()
        if re.fullmatch(r'viga_fundo_seg_\d+_dim', str(key))
    ))
    return (
        str(beam.get('dim') or ''),
        str(fields.get('dimensao') or ''),
        str(fields.get('altura_h1') or ''),
        bool(beam.get('fv_is_h', beam.get('is_h', True))),
        fundo_dims,
    )


def _changed_canonical_beam_names(
    old_beams: list[dict], new_beams: list[dict], candidates: set[str],
) -> set[str]:
    """Limita dependências às vigas cujo conteúdo canônico realmente mudou."""
    old_by_name = {_item_name(beam): beam for beam in old_beams or []}
    new_by_name = {_item_name(beam): beam for beam in new_beams or []}
    changed: set[str] = set()
    for name in {str(value).upper() for value in candidates or set()}:
        fresh = new_by_name.get(name)
        previous = old_by_name.get(name)
        if fresh is None:
            continue
        if previous is None or _beam_semantic_facts(previous) != _beam_semantic_facts(fresh):
            changed.add(name)
    return changed


def _fresh_laj_geometry_for_readonly_preview(
    merged_slabs: list[dict], fresh_slabs: list[dict],
) -> int:
    """Expose the newly traced LAJ geometry in a read-only verification pack.

    The regular merge deliberately returns an entirely human-sealed item as-is.
    That is correct for persistence, but made a read-only N1/N2 diagnostic render
    an old ``points_json`` instead of the contour just produced from the DXF.
    Keep all human validation metadata and non-geometric decisions intact while
    replacing only the derived N1 geometry used by the verification artifact.
    Nothing in this helper is persisted.
    """
    fresh_by_name = {
        _item_name(item): item for item in fresh_slabs or []
        if _item_name(item)
    }
    refreshed = 0
    for slab in merged_slabs or []:
        fresh = fresh_by_name.get(_item_name(slab))
        if not isinstance(fresh, dict) or not fresh.get("points"):
            continue
        slab["points"] = copy.deepcopy(fresh["points"])
        for key in ("area", "area_val", "bbox", "pos", "method", "trace_diagnostics"):
            if key in fresh:
                slab[key] = copy.deepcopy(fresh[key])
        links = slab.setdefault("links", {})
        fresh_outline = (fresh.get("links") or {}).get("laje_outline_segs")
        if isinstance(fresh_outline, dict):
            links["laje_outline_segs"] = copy.deepcopy(fresh_outline)
        slab["n1_geometry_preview_source"] = "fresh_dxf_readonly"
        refreshed += 1
    return refreshed


def _beam_topology_coverage(beam: dict) -> tuple[int, float]:
    """Retorna (segmentos, cobertura axial) para detectar regressão parcial.

    Usa uma única autoridade geométrica por vez. Contorno FV, espelho
    ``seg_bottom`` e laterais LV são representações do mesmo vão; somá-las
    triplicava artificialmente a cobertura e recusava uma reconstrução mais
    completa como regressão. A prioridade conserva a fonte física mais forte e
    usa as laterais apenas quando as duas topologias de fundo estão ausentes.
    """
    links = beam.get('links') or {}
    spans: set[tuple[str, float, float]] = set()

    def _add_slots(slots: object) -> None:
        if not isinstance(slots, dict):
            return
        for values in slots.values():
            for link in values or []:
                points = link.get('points') if isinstance(link, dict) else None
                if not points or len(points) < 2:
                    continue
                xs = [float(point[0]) for point in points]
                ys = [float(point[1]) for point in points]
                dx, dy = max(xs) - min(xs), max(ys) - min(ys)
                axis = 'x' if dx >= dy else 'y'
                lo, hi = (min(xs), max(xs)) if axis == 'x' else (min(ys), max(ys))
                spans.add((axis, round(lo, 3), round(hi, 3)))

    # 1. Contornos físicos FV por segmento.
    for source_key, slots in links.items():
        if re.fullmatch(r'viga_fundo_seg_\d+_area_segs', str(source_key)):
            _add_slots(slots)

    # 2. Espelho canônico de fundo, se não houver contornos por segmento.
    if not spans:
        for link in ((links.get('viga_segs') or {}).get('seg_bottom') or []):
            points = link.get('points') if isinstance(link, dict) else None
            if not points or len(points) < 2:
                continue
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
            dx, dy = max(xs) - min(xs), max(ys) - min(ys)
            axis = 'x' if dx >= dy else 'y'
            lo, hi = (min(xs), max(xs)) if axis == 'x' else (min(ys), max(ys))
            spans.add((axis, round(lo, 3), round(hi, 3)))

    # 3. Laterais LV somente como último fallback topológico.
    if not spans:
        for source_key, slots in links.items():
            if re.fullmatch(
                r'viga_[ab]_seg_\d+_(?:comprimento_total|comp_total_passa)',
                str(source_key),
            ):
                _add_slots(slots)

    return len(spans), round(sum(max(0.0, hi - lo) for _, lo, hi in spans), 3)


def _non_regressive_beam_dependencies(
    old_beams: list[dict], new_beams: list[dict], candidates: set[str],
) -> tuple[set[str], dict[str, dict[str, tuple[int, float]]]]:
    """Recusa dependência cujo candidato perdeu segmentos ou cobertura axial."""
    old_by_name = {_item_name(beam): beam for beam in old_beams or []}
    new_by_name = {_item_name(beam): beam for beam in new_beams or []}
    accepted: set[str] = set()
    rejected: dict[str, dict[str, tuple[int, float]]] = {}
    for name in {str(value).upper() for value in candidates or set()}:
        fresh = new_by_name.get(name)
        if fresh is None:
            continue
        previous = old_by_name.get(name)
        old_coverage = _beam_topology_coverage(previous or {})
        new_coverage = _beam_topology_coverage(fresh)
        loses_segments = old_coverage[0] > new_coverage[0]
        loses_span = old_coverage[1] > new_coverage[1] + 0.5
        if previous is not None and (loses_segments or loses_span):
            rejected[name] = {'old': old_coverage, 'new': new_coverage}
        else:
            accepted.add(name)
    return accepted, rejected


def _attach_pl_n3_variants_to_pillars(
    pillars: list[dict], variant_cache: dict | None,
) -> int:
    """Anexa ao snapshot PIL os dois artefatos N3 já materializados.

    O desktop/HTML materializa PARA e PASSA a partir do mesmo N1, mas o
    ``--persist-db`` precisa gravar esses payloads explícitos no SA também.
    Guardamos contrato, payload que alimentou o DXF e caminhos publicados;
    isto evita que o banco apresente N1 novo junto de uma variante N3 antiga.
    """
    if not isinstance(variant_cache, dict):
        return 0
    by_name: dict[str, dict[str, dict]] = {}
    for raw_key, variant in variant_cache.items():
        if not isinstance(raw_key, tuple) or len(raw_key) != 2:
            continue
        name, mode = str(raw_key[0]).upper(), str(raw_key[1]).lower()
        if mode not in {'para', 'passa'} or not isinstance(variant, dict):
            continue
        contract = variant.get('contract') or {}
        payload = variant.get('payload') or {}
        if not isinstance(contract, dict) or not isinstance(payload, dict):
            continue
        by_name.setdefault(name, {})[mode] = {
            'schema': str(contract.get('schema') or 'pil.n3_mode_contract.v2'),
            'modo_semantico': str(contract.get('modo_semantico') or mode).upper(),
            'contract': copy.deepcopy(contract),
            'payload': copy.deepcopy(payload),
            'artifacts': copy.deepcopy(variant.get('paths') or {}),
        }

    attached = 0
    for pillar in pillars or []:
        name = _item_name(pillar)
        modes = by_name.get(name)
        if not modes:
            continue
        # Só a dupla completa é um estado consumível pelo CE/SA.
        if not {'para', 'passa'}.issubset(modes):
            continue
        pillar['pl_n3_variants'] = modes
        pillar['pl_n3_variants_schema'] = 'pil.n3_variants/v1'
        attached += 1
    return attached


def _attach_lv_generation_contracts(
    beams: list[dict], pillars: list[dict], floor: str
) -> int:
    """Anexa ao snapshot SA os quatro contratos N3 derivados do proprio N1."""
    from src.core.lv_generation_contract import build_lv_generation_contracts

    pillar_bboxes = {}
    for pillar in pillars or []:
        points = pillar.get('points') or []
        try:
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
        except (TypeError, ValueError, IndexError):
            continue
        if xs and ys:
            pillar_bboxes[str(pillar.get('name') or pillar.get('id') or '')] = (
                min(xs), min(ys), max(xs), max(ys)
            )

    attached = 0
    for beam in beams or []:
        name = str(beam.get('name') or '').strip().upper()
        if not re.fullmatch(r'V\d+[A-Z]?', name):
            continue
        contracts = build_lv_generation_contracts(
            beam, beam_name=name, floor=floor,
            pillar_bboxes=pillar_bboxes,
        )
        if not any(
            contracts[behavior][side].get('panels')
            for behavior in ('Para', 'Passa') for side in ('A', 'B')
        ):
            continue
        beam['lv_generation_contracts'] = contracts
        beam['lv_generation_contract_version'] = 'lv_generation_contract/v1'
        fields = beam.setdefault('fields', {})
        fields['lv_n3_para_panels_A'] = [
            panel['width'] for panel in contracts['Para']['A']['panels']
        ]
        fields['lv_n3_para_panels_B'] = [
            panel['width'] for panel in contracts['Para']['B']['panels']
        ]
        fields['lv_n3_passa_panels_A'] = [
            panel['width'] for panel in contracts['Passa']['A']['panels']
        ]
        fields['lv_n3_passa_panels_B'] = [
            panel['width'] for panel in contracts['Passa']['B']['panels']
        ]
        fields['lv_n3_passa_total_A'] = contracts['Passa']['A']['total_length']
        fields['lv_n3_passa_total_B'] = contracts['Passa']['B']['total_length']
        attached += 1
    return attached


def _nat_key(x: dict):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r'(\d+)', x.get('name', ''))]


def _fix_nulo_sides(pillar_report: dict, slabs: list, max_dist: float = 300.0) -> int:
    """
    Fallback pos-processamento em dois passes:
    1. Corrige entradas existentes com side='NULO' usando posicao relativa centro-a-centro.
    2. Para pilares com 0 lajes, adiciona entradas para as lajes mais proximas (por bbox).

    Retorna o numero total de entradas criadas/corrigidas.
    """
    import math

    slab_info: list[tuple] = []  # (name, cx, cy, sx0, sy0, sx1, sy1)
    for s in slabs:
        pts = s.get('points') or []
        if len(pts) >= 3:
            try:
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                sx0, sy0, sx1, sy1 = min(xs), min(ys), max(xs), max(ys)
                slab_info.append((s.get('name', ''), (sx0+sx1)/2, (sy0+sy1)/2, sx0, sy0, sx1, sy1))
            except Exception:
                pass

    def _derive_side(pcx, pcy, scx, scy, horizontal):
        dx, dy = scx - pcx, scy - pcy
        if horizontal:
            if abs(dy) >= abs(dx):
                return 'B' if dy > 0 else 'A'
            return 'D' if dx > 0 else 'C'
        else:
            if abs(dx) >= abs(dy):
                return 'B' if dx > 0 else 'A'
            return 'C' if dy > 0 else 'D'

    fixed = 0
    for _nm, entry in pillar_report.items():
        pts = entry.get('points') or []
        if not pts:
            continue
        try:
            pxs = [float(p[0]) for p in pts]
            pys = [float(p[1]) for p in pts]
        except Exception:
            continue
        px0, px1 = min(pxs), max(pxs)
        py0, py1 = min(pys), max(pys)
        pcx, pcy = (px0 + px1) / 2, (py0 + py1) / 2
        horizontal = (px1 - px0) >= (py1 - py0)

        # Passe 1: corrige NULO nas entradas existentes
        for le in entry.get('lajes', []):
            if le.get('side') not in (None, 'NULO', ''):
                continue
            # Encontra bbox da laje pelo nome
            sn = le.get('laje', '')
            match = next((info for info in slab_info if info[0] == sn), None)
            if not match:
                continue
            _scx, _scy, sx0, sy0, sx1, sy1 = match[1], match[2], match[3], match[4], match[5], match[6]
            side = _derive_side(pcx, pcy, _scx, _scy, horizontal)
            # Para C/D, exigir sobreposicao no eixo perpendicular a projecao.
            # Lajes que toquem apenas o canto do pilar (sem sobreposicao real em X/Y)
            # sao deixadas com side='NULO' para _get_side_cell tratar geometricamente.
            if side in ('C', 'D'):
                if horizontal:
                    if sy1 < py0 or sy0 > py1:
                        continue  # laje fora do alcance Y da face curta
                else:
                    if sx1 < px0 or sx0 > px1:
                        continue  # laje fora do alcance X da face curta
            le['side'] = side
            le['side_source'] = 'relative_position_fallback'
            fixed += 1

        # Passe 2: para pilares sem laje nenhuma, adiciona as mais proximas
        if entry.get('lajes'):
            continue
        # Encontra lajes dentro de max_dist por centro-a-centro
        candidates = []
        for sn, scx, scy, sx0, sy0, sx1, sy1 in slab_info:
            # Distancia do centro do pilar para bbox da laje
            cx_clamp = max(sx0, min(sx1, pcx))
            cy_clamp = max(sy0, min(sy1, pcy))
            dist = math.hypot(pcx - cx_clamp, pcy - cy_clamp)
            if dist <= max_dist:
                candidates.append((dist, sn, scx, scy))
        if not candidates:
            continue
        candidates.sort()
        seen_sides: set = set()
        for dist, sn, scx, scy, sx0, sy0, sx1, sy1 in [
            (d, s, x, y, i[3], i[4], i[5], i[6])
            for d, s, x, y in candidates
            for i in slab_info
            if i[0] == s
        ][:4]:
            side = _derive_side(pcx, pcy, scx, scy, horizontal)
            # Para lados C/D (face curta), exigir sobreposicao de bbox no eixo
            # perpendicular a projecao. Uma laje que nao sobrepoe o pilar em X
            # (para VERTICAL) ou em Y (para HORIZONTAL) esta num quadrante errado.
            if side in ('C', 'D'):
                # Exige sobreposicao real no eixo perpendicular a projecao.
                # Uma laje que inicia APOS a borda do pilar (gap > 0) esta no canto
                # de outro lado (A/B), nao na face C/D.
                if horizontal:
                    # HORIZONTAL: C/D = faces W/E; projecao em X → checar sobreposicao em Y
                    if sy1 < py0 or sy0 > py1:
                        continue  # laje fora do alcance Y da face curta
                else:
                    # VERTICAL: C/D = faces N/S; projecao em Y → checar sobreposicao em X
                    if sx1 < px0 or sx0 > px1:
                        continue  # laje fora do alcance X da face curta
            if side in seen_sides:
                continue  # um lado ja tem laje
            seen_sides.add(side)
            entry.setdefault('lajes', []).append({
                'laje': sn,
                'side': side,
                'face': 'AUTO',
                'source': 'proximity_fallback',
                'side_source': 'relative_position_fallback',
                'dist': round(dist, 1),
            })
            fixed += 1
    return fixed


# ─────────────────────────────────────────────────────────────────────────────
# HeadlessRunner — receptor dos metodos de MainWindow via types.MethodType
# ─────────────────────────────────────────────────────────────────────────────

class HeadlessRunner:
    """
    Objeto fake que recebe os metodos de analise do MainWindow via binding.
    Tem apenas os atributos de estado necessarios; sem UI.
    """

    def __init__(self):
        from src.core.spatial_index import SpatialIndex
        self.spatial_index = SpatialIndex()
        self.dxf_data: dict = {}
        self.slabs_found: list = []
        self.beams_found: list = []
        self.pillars_found: list = []
        self.pavimento_pillar_report: dict = {}
        self.pavimento_nivel_report: dict = {}
        self.pavimento_preprocess: dict = {}
        self.slab_learning_config: dict = {}
        self._analysis_texts: list | None = None
        self.current_project_id: str = 'headless_01'

    # Stubs de UI exigidos por alguns metodos
    def log(self, msg: str, *a, **kw):
        print(f'[SA] {msg}', flush=True)

    def show_progress(self, *a, **kw): pass
    def update_progress(self, *a, **kw): pass
    def hide_progress(self): pass
    def _dump_slab_diagnostics(self): pass
    def close(self): pass

    def get_pillar_report(self) -> dict:
        return self.pavimento_pillar_report

    def get_nivel_report(self) -> dict:
        return self.pavimento_nivel_report

    def is_pillar_nasce(self, pillar_name: str) -> bool:
        entry = self.pavimento_pillar_report.get(
            str(pillar_name or '').strip().upper()
        )
        return bool(entry and entry.get('ignore_in_beams'))

    def _apply_preficha_rejections(self, report: dict) -> None:
        pass  # sem DB history em modo headless


def _bind_mainwindow_methods(runner: HeadlessRunner) -> None:
    """
    Importa MainWindow (sem instanciar, sem UI) e faz bind de TODOS os metodos
    de analise (nomes com _) para o runner via types.MethodType.
    Metodos estaticos sao vinculados sem self.
    """
    # Importar main.py — apenas define classes/funcoes; nao executa main()
    import main as _main_mod
    MW = _main_mod.MainWindow

    # Percorre o __dict__ da classe para distinguir staticmethod de instance method
    bound = 0
    skipped = 0
    for name, raw in MW.__dict__.items():
        if not name.startswith('_') or name.startswith('__'):
            continue
        if isinstance(raw, staticmethod):
            # Nao passa self
            setattr(runner, name, raw.__func__)
            bound += 1
        elif isinstance(raw, (classmethod,)):
            pass  # classmethod nao e necessario
        elif callable(raw) and isinstance(raw, types.FunctionType):
            setattr(runner, name, types.MethodType(raw, runner))
            bound += 1
        else:
            skipped += 1

    print(f'[SA] Metodos bindados: {bound} ({skipped} ignorados)', flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────────────────────────────────────

def _run_legacy_analysis(
    dxf_path: str,
    obra: str,
    pavimento: str,
    *,
    project_id: str = 'headless_01',
    build_html: bool = True,
    db_path: str = 'D:/Agente-cad-PYSIDE/project_data.vision',
) -> dict:
    """
    Executa pipeline SA completo e gera HTMLs.
    Retorna dict com resumo (n_pilares, n_slabs, n_beams, html_dir).
    """
    from src.core.dxf_loader  import DXFLoader
    from src.core.slab_tracer import SlabTracer
    from src.core.beam_tracer import BeamTracer

    runner = HeadlessRunner()
    runner.current_project_id = project_id
    runner.pavimento_preprocess = {
        'obra': obra,
        'pavimento': pavimento,
        'convention': {},
        'term_type_map': {},
    }
    # A cache guarda somente o contexto N1 canônico (DXF → PIL/LAJ/BeamTracer),
    # não o HTML.  Portanto um microciclo FV que vai materializar fichas também
    # pode reutilizá-la: a UI continua recebendo exatamente o mesmo snapshot,
    # sem instanciar MainWindow nem pular o interpretador FV.
    cache_path = _fast_context_cache_path(dxf_path)
    if cache_path and _restore_fast_context_cache(runner, cache_path):
        print(f'[SA] Cache N1 contextual: HIT {cache_path.name[:12]}', flush=True)
        return {
            'runner': runner,
            'texts': list(runner.dxf_data.get('texts', [])),
            'n_pilares': len(runner.pavimento_pillar_report),
            'n_slabs': len(runner.slabs_found),
            'n_beams': len(runner.beams_found),
            'cache_hit': True,
        }

    # 1. Carregar DXF
    print(f'[SA] Carregando DXF: {dxf_path}', flush=True)
    runner.dxf_data = DXFLoader.load_dxf(dxf_path)
    if not runner.dxf_data:
        raise RuntimeError(f'DXFLoader retornou None para: {dxf_path}')

    texts    = runner.dxf_data.get('texts', [])
    lines    = runner.dxf_data.get('lines', [])
    polylines = runner.dxf_data.get('polylines', [])
    print(f'[SA] DXF: {len(lines)} linhas, {len(polylines)} polilinhas, {len(texts)} textos',
          flush=True)

    # Snapshot para _collect_plan_pillar_names (protecao de corrida de dados)
    runner._analysis_texts = list(texts)

    # 2. Indexacao espacial
    print('[SA] Indexando geometria...', flush=True)
    si = runner.spatial_index
    for poly in polylines:
        pts = poly.get('points') or []
        if pts:
            bounds = (min(p[0] for p in pts), min(p[1] for p in pts),
                      max(p[0] for p in pts), max(p[1] for p in pts))
            si.insert(poly, bounds)
    for line in lines:
        s, e = line['start'], line['end']
        bounds = (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1]))
        si.insert(line, bounds)
    for txt in texts:
        p = txt['pos']
        bounds = (p[0]-5, p[1]-5, p[0]+5, p[1]+5)
        si.insert(txt, bounds)

    # 3. Bind metodos do MainWindow
    print('[SA] Bindando metodos de analise do MainWindow...', flush=True)
    _bind_mainwindow_methods(runner)

    # 4. Detectar lajes
    print('[SA] Detectando lajes...', flush=True)
    slab_tracer = SlabTracer(si)
    runner.slabs_found = slab_tracer.detect_slabs_from_texts(
        texts, valid_layers=None, search_radius=2000.0, teacher_dims=None,
    )
    runner.slabs_found.sort(key=_nat_key)
    print(f'[SA] Lajes detectadas: {len(runner.slabs_found)}', flush=True)

    # 5. Processar cada laje (preench links laje_pilares_apoio, laje_dim, etc.)
    print('[SA] Processando lajes...', flush=True)
    for i, s in enumerate(runner.slabs_found):
        s['id']         = f'headless_l_{i+1}'
        s['id_item']    = f'{i+1:02}'
        s['project_id'] = project_id
        s['type']       = 'Laje'
        s['laje_name']  = s['name']
        runner._process_slab_intelligent(s)

    # 6. Inferir niveis de laje e montar relatorio de pilares
    print('[SA] Montando relatorio de pilares...', flush=True)
    runner._infer_slab_levels_from_context(runner.slabs_found)
    runner.pavimento_pillar_report = runner._build_complete_pillar_report(runner.slabs_found)
    runner._apply_preficha_rejections(runner.pavimento_pillar_report)
    n_pil = len(runner.pavimento_pillar_report)
    print(f'[SA] Pilares: {n_pil}', flush=True)

    # 7. Relatorio de niveis
    runner.pavimento_nivel_report = runner._build_nivel_report(
        runner.slabs_found, runner.pavimento_pillar_report
    )

    # 8. Detectar vigas
    print('[SA] Detectando vigas...', flush=True)
    beam_tracer = BeamTracer(si)

    all_geo: list = []
    for l in lines + polylines:
        if 'points' in l:
            all_geo.append(l)
        elif 'start' in l:
            all_geo.append({'points': [l['start'], l['end']]})

    visual_obstacles: list = []
    for p_name, p_data in runner.pavimento_pillar_report.items():
        if p_data.get('classification') == 'NASCE' or p_data.get('is_invalid'):
            continue
        bbox = p_data.get('bbox')
        if bbox:
            visual_obstacles.append({'type': 'PILAR_SOLIDO', 'bbox': bbox})
    for s_item in runner.slabs_found:
        for link in (s_item.get('links', {})
                       .get('laje_visao_corte', {})
                       .get('cut_view_geom', [])):
            pts = link.get('points', [])
            if pts:
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                visual_obstacles.append({'type': 'VISAO_CORTE',
                                         'bbox': (min(xs), min(ys), max(xs), max(ys))})

    runner.beams_found = beam_tracer.detect_beams(
        texts,
        all_geo,
        visual_obstacles=visual_obstacles,
    )

    # Normalizar nomes
    for b in runner.beams_found:
        b['name'] = _normalize_beam_name(b['name'])
    runner.beams_found.sort(key=_nat_key)

    # Processar vigas
    for i, b in enumerate(runner.beams_found):
        b['id']         = f'headless_b_{i+1}'
        b['id_item']    = f'{i+1:02}'
        b['id_num']     = i + 1
        b['project_id'] = project_id
        try:
            runner._process_beam_intelligent(b)
            # Mesmo contrato da GUI: FV precisa ser uma área fechada. O
            # reparador preserva contornos válidos/validados e corrige apenas
            # candidatos automáticos degenerados antes dos diagnósticos.
            from src.core.beam_interpreters import FundoVigaInterpreter
            FundoVigaInterpreter.repair_area_links(
                b, context_beams=runner.beams_found
            )
        except Exception as exc:
            print(f'[WARN] _process_beam_intelligent falhou para {b.get("name")}: {exc}',
                  flush=True)

    from src.core.beam_interpreters import FundoVigaInterpreter
    for b in runner.beams_found:
        FundoVigaInterpreter.repair_area_links(
            b, context_beams=runner.beams_found
        )

    # FV fecha as fichas depois dos campos textuais/LV. Reconciliar agora
    # garante que PIL e o DB consumam B/H e eixo da geometria real da viga.
    from src.core.pillar_face_beams import reconcile_beam_fundo_facts
    n_fundo_facts = reconcile_beam_fundo_facts(runner.beams_found)
    if n_fundo_facts:
        print(f'[SA] Fatos FV canônicos reaplicados: {n_fundo_facts} viga(s)', flush=True)

    print(f'[SA] Vigas: {len(runner.beams_found)}', flush=True)

    # 9. Enriquecer pilares com dados de vigas (laje vs viga por face)
    runner._enrich_pillar_report_with_beams(
        runner.pavimento_pillar_report, runner.beams_found
    )

    # 9b. Fallback de sides para entradas com side='NULO' (geometria region-growing
    #     nao alinha precisamente com arestas do pilar; usa posicao relativa de centros)
    n_fixed = _fix_nulo_sides(runner.pavimento_pillar_report, runner.slabs_found)
    if n_fixed:
        print(f'[SA] Sides corrigidos por fallback de posicao relativa: {n_fixed}', flush=True)

    if cache_path:
        _store_fast_context_cache(runner, cache_path)
        print(f'[SA] Cache N1 contextual: STORED {cache_path.name[:12]}', flush=True)

    if not build_html:
        return {
            'runner': runner,
            'texts': texts,
            'n_pilares': n_pil,
            'n_slabs': len(runner.slabs_found),
            'n_beams': len(runner.beams_found),
            'cache_hit': False,
        }

    # 10. Criar PreValidationDialog headless (sem show/exec)
    print('[SA] Criando PreValidationDialog headless...', flush=True)

    _dados_root      = str(_REPO_ROOT / 'DADOS-OBRAS')
    _convention_file = (
        os.path.join(_dados_root, obra, 'convencao_pilares.json') if obra else None
    )
    _db_path = db_path

    beam_texts = [
        {
            'text': text.get('text', ''),
            'pos': list(text.get('pos') or [0, 0]),
            'layer': text.get('layer', ''),
        }
        for text in texts
    ]

    from src.ui.widgets.pre_validation_dialog import PreValidationDialog
    dlg = PreValidationDialog(
        pillar_report=runner.pavimento_pillar_report,
        nivel_report=runner.pavimento_nivel_report,
        slabs=runner.slabs_found,
        convention={},
        obra=obra,
        pavimento=pavimento,
        beam_texts=beam_texts,
        canvas=None,
        convention_file=_convention_file,
        db_path=_db_path,
        dxf_data=runner.dxf_data,
        beams=runner.beams_found,
        parent=None,
    )

    # 11. Salvar estado JSON + gerar HTMLs (auto-path sem QFileDialog)
    print('[SA] Salvando estado JSON...', flush=True)
    dlg._save_analysis_state()

    print('[SA] Gerando HTMLs...', flush=True)
    html_dir = dlg._export_html_snapshot()

    print(f'[SA] Concluido! HTMLs em: {html_dir}', flush=True)
    return {
        'obra':       obra,
        'pavimento':  pavimento,
        'n_pilares':  n_pil,
        'n_slabs':    len(runner.slabs_found),
        'n_beams':    len(runner.beams_found),
        'html_dir':   str(html_dir) if html_dir else '',
    }


def _build_fast_pre_validation_dialog(
    runner: HeadlessRunner,
    *,
    obra: str,
    pavimento: str,
    db_path: str,
):
    """Constroi a mesma ficha humana sem depender da arvore completa da UI."""
    from src.ui.widgets.pre_validation_dialog import PreValidationDialog

    convention_file = (
        _REPO_ROOT.parent / 'DADOS-OBRAS' / obra / 'convencao_pilares.json'
    )
    beam_texts = [
        {
            'text': text.get('text', ''),
            'pos': list(text.get('pos') or [0, 0]),
            'layer': text.get('layer', ''),
        }
        for text in (runner.dxf_data or {}).get('texts', [])
    ]
    return PreValidationDialog(
        pillar_report=runner.pavimento_pillar_report,
        nivel_report=runner.pavimento_nivel_report,
        slabs=runner.slabs_found,
        convention={},
        obra=obra,
        pavimento=pavimento,
        beam_texts=beam_texts,
        canvas=None,
        convention_file=(
            str(convention_file) if convention_file.is_file() else None
        ),
        db_path=db_path,
        dxf_data=runner.dxf_data,
        beams=runner.beams_found,
        parent=None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

_DB_DEFAULT = 'D:/Agente-cad-PYSIDE/project_data.vision'

# Nome da pasta de seção (dentro do html_dir exportado) -> módulo do
# diagnóstico headless correspondente. FV foi o primeiro a rodar aqui
# (_run_fv_diagnostic_postprocess); os demais seguem o mesmo contrato
# run_diagnostic(*, obra, pavimento, state_path, db_path) -> (report, json_path, jsonl_path)
# (ver docstrings de cada diagnostico_*_n1_n2.py).
_SECTION_DIAGNOSTIC_MODULES: dict[str, str] = {
    'pilares': 'scripts.arete.diagnostico_pil_n1_n2',
    'lajes': 'scripts.arete.diagnostico_laj_n1_n2',
    'fundos_viga': 'scripts.arete.diagnostico_fv_n1_n2',
    'laterais_viga': 'scripts.arete.diagnostico_lv_n1_n2',
}
_SECTION_LABELS: dict[str, str] = {
    'pilares': 'PIL',
    'lajes': 'LAJ',
    'fundos_viga': 'FV',
    'laterais_viga': 'LV',
}

_CLASS_HEADLESS_LOCKS: dict[str, str] = {
    'pilares': 'headless_sa_pil',
    'lajes': 'headless_sa_laj',
    'fundos_viga': 'headless_sa_fv',
    'laterais_viga': 'headless_sa_lv',
}
_GLOBAL_HEADLESS_LOCK = 'headless_sa_global'


def _headless_lock_plan(
    sections: set[str] | None,
    item_names: set[str] | None,
    persist_db: bool,
) -> tuple[list[str], str]:
    """Seleciona a menor trava que preserva isolamento e memória.

    Uma consulta realmente granular (uma classe, item explícito e read-only)
    só monopoliza sua classe. Rodadas completas/multiclasse ou com escrita no
    DB tomam a trava global e todas as classes, em ordem fixa.
    """
    if sections is not None and len(sections) == 1 and item_names and not persist_db:
        section = next(iter(sections))
        return [_CLASS_HEADLESS_LOCKS[section]], f'classe:{_SECTION_LABELS[section]}'
    return ([_GLOBAL_HEADLESS_LOCK, *_CLASS_HEADLESS_LOCKS.values()], 'global')


def _release_headless_locks(handles: list) -> None:
    """Libera um plano de locks na ordem inversa; seguro para ``atexit``."""
    try:
        from scripts.arete.single_instance import release_lock
    except ImportError:
        from single_instance import release_lock
    for handle in reversed(handles):
        release_lock(handle)


def _filter_diagnostic_files(
    report: dict,
    json_path: Path,
    jsonl_path: Path,
    item_names: set[str] | None,
) -> dict:
    if not item_names:
        return report
    items = [
        item for item in report.get('itens', [])
        if _matches_item_name(str(item.get('item') or ''), item_names)
    ]
    report = copy.deepcopy(report)
    report['itens'] = items
    alerts = [item for item in items if item.get('causa_raiz')]
    resumo = dict(report.get('resumo') or {})
    resumo['itens'] = len(items)
    resumo['alertas'] = len(alerts)
    for key in ('n1_itens', 'n2_itens'):
        if key in resumo:
            resumo[key] = len(items)
    counts: dict[str, int] = {}
    for item in items:
        cls = str((item.get('evidencia') or {}).get('classificacao') or '')
        if cls:
            counts[cls] = counts.get(cls, 0) + 1
    if 'classificacoes' in resumo:
        resumo['classificacoes'] = dict(sorted(counts.items()))
    report['resumo'] = resumo
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    jsonl_path.write_text(
        ''.join(json.dumps(item, ensure_ascii=False) + '\n' for item in alerts),
        encoding='utf-8',
    )
    return report


def _run_diagnostic_postprocess(
    module_name: str,
    *,
    label: str,
    obra: str,
    pavimento: str,
    state_path: str,
    db_path: str,
    item_names: set[str] | None = None,
) -> dict:
    """Executa o gate numérico de uma classe sem bloquear a revisão humana em caso de falha."""
    try:
        module = importlib.import_module(module_name)
        report, json_path, jsonl_path = module.run_diagnostic(
            obra=obra,
            pavimento=pavimento,
            state_path=state_path,
            db_path=db_path,
        )
        report = _filter_diagnostic_files(
            report,
            Path(json_path),
            Path(jsonl_path),
            item_names,
        )
        print(
            f'[SA-HUMAN] Diagnóstico {label}: {report["resumo"]["alertas"]} alerta(s)',
            flush=True,
        )
        return {
            'status': 'ok',
            'run_id': report.get('run_id'),
            'json_path': str(json_path),
            'jsonl_path': str(jsonl_path),
            'resumo': report['resumo'],
        }
    except Exception as exc:
        print(f'[SA-HUMAN] AVISO diagnóstico {label} não gerado: {exc}', flush=True)
        return {'status': 'erro', 'erro': str(exc)}


def _run_fv_diagnostic_postprocess(
    *,
    obra: str,
    pavimento: str,
    state_path: str,
    db_path: str,
) -> dict:
    """Executa o gate numérico FV sem bloquear a revisão humana em caso de falha.

    Mantida como wrapper fino de `_run_diagnostic_postprocess` (mesma
    assinatura/retorno de antes) porque `tests/test_headless_fv_diagnostic_integration.py`
    monkeypatcha `diagnostico_fv_n1_n2.run_diagnostic` e depende deste nome.
    """
    return _run_diagnostic_postprocess(
        'scripts.arete.diagnostico_fv_n1_n2',
        label='FV',
        obra=obra,
        pavimento=pavimento,
        state_path=state_path,
        db_path=db_path,
    )


def _run_section_diagnostics(
    *,
    html_dir: str | Path,
    obra: str,
    pavimento: str,
    state_path: str,
    db_path: str,
    item_names: set[str] | None = None,
) -> dict[str, dict]:
    """Roda o diagnóstico de cada classe cuja pasta de seção existe no run.

    Tolerante a falha por classe (mesmo padrão de `_run_fv_diagnostic_postprocess`):
    uma seção que falhar não impede as demais nem a geração das fichas.
    """
    run_dir = Path(html_dir)
    diagnostics: dict[str, dict] = {}
    for section, module_name in _SECTION_DIAGNOSTIC_MODULES.items():
        if not (run_dir / section).is_dir():
            continue
        diagnostics[section] = _run_diagnostic_postprocess(
            module_name,
            label=_SECTION_LABELS[section],
            obra=obra,
            pavimento=pavimento,
            state_path=state_path,
            db_path=db_path,
            item_names=item_names,
        )
    return diagnostics


_ARETE_DIAG_START = '<!-- ARETE_FV_DIAGNOSTIC_START -->'
_ARETE_DIAG_END = '<!-- ARETE_FV_DIAGNOSTIC_END -->'


def _inject_arete_block(path: Path, block: str) -> None:
    document = path.read_text(encoding='utf-8')
    document = re.sub(
        re.escape(_ARETE_DIAG_START) + r'.*?' + re.escape(_ARETE_DIAG_END),
        '',
        document,
        flags=re.DOTALL,
    )
    wrapped = f'{_ARETE_DIAG_START}{block}{_ARETE_DIAG_END}'
    document = document.replace('</body>', f'{wrapped}</body>', 1)
    path.write_text(document, encoding='utf-8')


def _publish_arete_manifest(
    *,
    html_dir: str | Path,
    obra: str,
    pavimento: str,
    diagnostics: dict[str, dict],
) -> Path:
    """Publica o manifesto Arete e injeta o bloco de diagnóstico nas fichas.

    `diagnostics` é `{section: diagnostic}` — `section` é o nome da pasta
    dentro de `html_dir` (`fundos_viga`, `lajes`, `pilares`, `laterais_viga`);
    cada `diagnostic` tem o mesmo formato retornado por
    `_run_diagnostic_postprocess`. Generalização de uma versão anterior que
    só existia para FV (agora `_SECTION_DIAGNOSTIC_MODULES` define quais
    classes participam).
    """
    run_dir = Path(html_dir).resolve()

    def relative(target: Path | None, start: Path) -> str | None:
        return Path(os.path.relpath(target, start)).as_posix() if target else None

    def json_path_of(diagnostic: dict) -> Path | None:
        return Path(diagnostic['json_path']).resolve() if diagnostic.get('json_path') else None

    manifest_diagnostics: dict[str, dict] = {}
    run_id = None
    for section, diagnostic in diagnostics.items():
        json_path = json_path_of(diagnostic)
        jsonl_path = Path(diagnostic['jsonl_path']).resolve() if diagnostic.get('jsonl_path') else None
        manifest_diagnostics[section] = {
            **diagnostic,
            'json_relative': relative(json_path, run_dir),
            'jsonl_relative': relative(jsonl_path, run_dir),
        }
        run_id = run_id or diagnostic.get('run_id')

    manifest = {
        'schema_version': 2,
        'obra': obra,
        'pavimento': pavimento,
        'run_id': run_id,
        'html_dir': str(run_dir),
        'diagnosticos': manifest_diagnostics,
    }
    manifest_path = run_dir / 'arete_manifest.json'
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    root_index = run_dir / 'index.html'
    if root_index.is_file():
        links = []
        for section, diagnostic in diagnostics.items():
            link = relative(json_path_of(diagnostic), root_index.parent)
            if link:
                label = _SECTION_LABELS.get(section, section.upper())
                links.append(f'<a href="{html.escape(link)}">diagnóstico {label} JSON</a>')
        diagnostic_links = (' · ' + ' · '.join(links)) if links else ''
        _inject_arete_block(
            root_index,
            '<div style="margin:12px;padding:10px;border:1px solid #335;'
            'background:#151922;color:#aaa">'
            '<b style="color:#7eb8f7">Arete desta execução</b> · '
            '<a href="arete_manifest.json">manifesto</a>'
            f'{diagnostic_links}</div>',
        )

    for section, diagnostic in diagnostics.items():
        json_path = json_path_of(diagnostic)
        report = {}
        if json_path and json_path.is_file():
            report = json.loads(json_path.read_text(encoding='utf-8'))
        label = _SECTION_LABELS.get(section, section.upper())

        section_dir = run_dir / section
        section_index = section_dir / 'index.html'
        if section_index.is_file():
            link = relative(json_path, section_index.parent)
            alerts = (diagnostic.get('resumo') or {}).get('alertas', 0)
            _inject_arete_block(
                section_index,
                '<div style="margin:12px 0;padding:10px;border:1px solid #554400;'
                'background:#211d08;color:#f0b840">'
                f'<b>Diagnóstico automático {label}:</b> {alerts} alerta(s) · '
                f'<a href="{html.escape(link or "../arete_manifest.json")}">abrir relatório</a>'
                '<div style="font-size:10px;color:#998b55">Hipótese numérica; '
                'não substitui a revisão humana.</div></div>',
            )

        items = {
            str(item.get('item') or '').upper(): item
            for item in report.get('itens', [])
            if isinstance(item, dict)
        }
        if not items or not section_dir.is_dir():
            continue
        # rglob (não glob) porque pilares/ e laterais_viga/ guardam as fichas
        # por item em subpastas (ex.: pilares/INDETERMINADO/P12.html,
        # laterais_viga/a_passa/V301_1.html), diferente de fundos_viga/ e
        # lajes/ que são planas.
        for page in section_dir.rglob('*.html'):
            if page.name == 'index.html' or page.name.startswith('interpretacao_'):
                continue
            item = items.get(page.stem.upper())
            if not item:
                continue
            evidence = item.get('evidencia') or {}
            quality = str(evidence.get('classificacao') or 'INDETERMINADO')
            cause = str(item.get('causa_raiz') or 'sem alerta numérico')
            description = str(item.get('causa_descricao') or '')
            deltas = evidence.get('deltas') or {}
            delta_values = [value for value in deltas.values() if isinstance(value, (int, float))]
            max_delta = max(delta_values) if delta_values else None
            delta_text = f'{max_delta:.2%}' if max_delta is not None else 'indisponível'
            link = relative(json_path, page.parent)
            color = '#e17055' if item.get('causa_raiz') else '#4fc3a1'
            _inject_arete_block(
                page,
                '<details class="arete-auto-diagnostic" style="margin:16px 0;'
                'padding:10px;border:1px solid #554400;background:#171407">'
                f'<summary style="cursor:pointer;color:{color};font-weight:bold">'
                f'Diagnóstico automático N1×N2 — {html.escape(quality)}</summary>'
                '<p style="color:#998b55;font-size:10px">Hipótese numérica automática; '
                'a marcação humana permanece soberana.</p>'
                f'<p><b>Causa:</b> {html.escape(cause)}<br>'
                f'<b>Delta máximo:</b> {html.escape(delta_text)}<br>'
                f'{html.escape(description)}</p>'
                f'<a href="{html.escape(link or "../arete_manifest.json")}">'
                'Abrir evidência oficial JSON</a></details>',
            )
    return manifest_path


def _generate_fv_n3_nova_previews(
    obra_dir: Path,
    fv_results: list[dict],
    output_dir: Path,
) -> tuple[list[str], list[str]]:
    """Gera N3 NOVA com o resultado do fluxo humano, em diretórios isolados."""
    from src.core.fv_generation_contract import build_fv_generation_contract

    script = _REPO_ROOT / 'scripts' / 'gerar_fv_dxf_stog.py'
    output_dir.mkdir(parents=True, exist_ok=True)
    input_dir = output_dir.parent / 'contracts'
    input_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []
    failed: list[str] = []
    contracts: dict[str, dict] = {}
    for fv_data in fv_results:
        if not isinstance(fv_data, dict):
            continue
        raw_name = str(fv_data.get('viga_nome') or '')
        contract = build_fv_generation_contract(raw_name, fv_data)
        beam_name = str(contract.get('name') or '')
        if beam_name and contract.get('segments_rich'):
            contracts[beam_name] = contract

    for beam_name, contract in contracts.items():
        contract_path = input_dir / f'{beam_name}_fundo.json'
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        command = [
            sys.executable,
            str(script),
            '--obra', str(obra_dir),
            '--item', beam_name,
            '--visual-mode', 'NOVA',
            '--output-dir', str(output_dir),
            '--input-dir', str(input_dir),
        ]
        try:
            result = subprocess.run(
                command,
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                # O destino já é temporário e isolado. Remover a trava aqui evita
                # que guarded_saveas desvie o candidato para outro diretório.
                env={
                    key: value for key, value in os.environ.items()
                    if key != 'CAD_MOTOR_HEADLESS'
                },
            )
        except subprocess.TimeoutExpired:
            failed.append(beam_name)
            print(
                f'[SA-HUMAN] N3 NOVA timeout (120s) para {beam_name}',
                flush=True,
            )
            continue
        expected = output_dir / f'FV_preview_{beam_name}.dxf'
        if result.returncode == 0 and expected.is_file():
            generated.append(beam_name)
        else:
            failed.append(beam_name)
            detail = (result.stderr or result.stdout or '').strip()[-300:]
            print(
                f'[SA-HUMAN] N3 NOVA ausente para {beam_name}: {detail}',
                flush=True,
            )
    return generated, failed


def _filter_fv_results_for_items(
    fv_results: list[dict], item_names: set[str] | None,
) -> list[dict]:
    """Mantém no N3 FV somente os itens explicitamente pedidos pelo microciclo.

    A interpretação N1 continua completa e contextual; este filtro existe apenas
    na fronteira de materialização N3 para não gerar previews de vigas que não
    pertencem ao lote visual atual.
    """
    if not item_names:
        return list(fv_results or [])
    filtered: list[dict] = []
    for result in fv_results or []:
        if not isinstance(result, dict):
            continue
        raw_name = str(result.get('viga_nome') or result.get('name') or '')
        # O resultado N1 usa V309.C, mas a CLI humana trabalha com V309.
        # Extrair a identidade estrutural é preferível a depender do sufixo de
        # vista e preserva VF202/V309A sem hardcode de obra.
        identity = re.search(r'V[F]?\d+[A-Z]?', raw_name.upper())
        if _matches_item_name(raw_name, item_names) or (
            identity is not None and identity.group(0) in item_names
        ):
            filtered.append(result)
    return filtered


def _generate_pl_n3_nova_previews(
    obra: str,
    window,
) -> tuple[list[str], list[str]]:
    """Gera N3 de pilares: **sempre PARA e PASSA** (listas separadas).

    Espelha o desktop/CE: não há escolha manual no N3. Publica em
    ``DADOS-OBRAS/<obra>/Fase-6_Execucao_CAD/n3_variants/{para|passa}/``
    via ``PreValidationDialog.materialize_pl_n3_variants`` (mesmo contrato
    SA + ``generate_pilar_zone`` + ``apply_visual_mode``).

    Returns:
        (generated, failed) labels ``P1_para``, ``P1_passa``, …
    """
    try:
        dialog = window._build_pre_validation_dialog()
    except Exception as exc:
        print(f'[SA-HUMAN] N3 PL dialog falhou: {exc}', flush=True)
        return [], ['dialog-error']
    if dialog is None:
        return [], ['dialog-ausente']
    try:
        generated, failed = dialog.materialize_pl_n3_variants()
    except Exception as exc:
        print(f'[SA-HUMAN] N3 PL materialize falhou: {exc}', flush=True)
        return [], [f'materialize-error:{exc}']
    return list(generated or []), list(failed or [])


def _generate_lv_n3_nova_previews(
    obra_dir: Path,
    beams: list[dict],
    output_dir: Path,
) -> tuple[list[str], list[str]]:
    """Gera N3 isolado das laterais de viga (LV): 2 comportamentos
    (Para/Passa) x 3 vistas (Visão de Corte/Lateral A/Lateral B) por viga.

    Usa os 4 contratos que o próprio SA já calculou e anexou em
    `beam['lv_generation_contracts']` (`_attach_lv_generation_contracts`,
    que por sua vez chama `build_lv_generation_contracts` — mesma fonte que
    alimenta os campos `lv_n3_*_panels_*` do snapshot). Não toca
    Fase-4/Fase-6 reais da obra: grava os JSON de entrada (`V{n}_A.json`/
    `V{n}_B.json`, schema que `gerar_lv_dxf_stog.py` já sabe ler) e os DXF
    de saída no mesmo diretório temporário isolado usado pelo FV.
    """
    script = _REPO_ROOT / 'scripts' / 'gerar_lv_dxf_stog.py'
    output_dir.mkdir(parents=True, exist_ok=True)
    input_root = output_dir.parent / 'contracts_lv'
    generated: list[str] = []
    failed: list[str] = []

    for beam in beams or []:
        contracts = beam.get('lv_generation_contracts')
        if not isinstance(contracts, dict):
            continue
        beam_name = str(beam.get('name') or '').strip().upper()
        if not beam_name:
            continue
        for behavior in ('Para', 'Passa'):
            sides = contracts.get(behavior) or {}
            if not any((sides.get(side) or {}).get('panels') for side in ('A', 'B')):
                continue
            behavior_input_dir = input_root / f'LV-{behavior.upper()}'
            behavior_input_dir.mkdir(parents=True, exist_ok=True)
            for side in ('A', 'B'):
                contract = sides.get(side) or {}
                contract_path = behavior_input_dir / f'{beam_name}_{side}.json'
                contract_path.write_text(
                    json.dumps(contract, ensure_ascii=False, indent=2),
                    encoding='utf-8',
                )
            for view in ('CORTE', 'A', 'B'):
                view_suffix = 'CORTE' if view == 'CORTE' else f'VIEW_{view}'
                label = f'{beam_name}_{behavior}_{view_suffix}'
                command = [
                    sys.executable,
                    str(script),
                    '--obra', str(obra_dir),
                    '--item', beam_name,
                    '--behavior', behavior,
                    '--view', view,
                    '--visual-mode', 'NOVA',
                    '--output-dir', str(output_dir),
                    '--input-dir', str(behavior_input_dir),
                ]
                try:
                    result = subprocess.run(
                        command,
                        cwd=str(_REPO_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=90,
                        # Destino já isolado/temporário — remover a trava evita
                        # que guarded_saveas desvie o candidato pra outro lugar
                        # (mesmo motivo do FV, ver _generate_fv_n3_nova_previews).
                        env={
                            key: value for key, value in os.environ.items()
                            if key != 'CAD_MOTOR_HEADLESS'
                        },
                    )
                except subprocess.TimeoutExpired:
                    failed.append(label)
                    print(
                        f'[SA-HUMAN] N3 LV timeout (90s) para {label}',
                        flush=True,
                    )
                    continue
                expected = output_dir / f'LV_preview_{beam_name}_{behavior}_{view_suffix}.dxf'
                if result.returncode == 0 and expected.is_file():
                    generated.append(label)
                else:
                    failed.append(label)
                    detail = (result.stderr or result.stdout or '').strip()[-300:]
                    print(
                        f'[SA-HUMAN] N3 LV ausente para {label}: {detail}',
                        flush=True,
                    )
    return generated, failed


def _generate_lj_n3_nova_previews(
    obra_dir: Path,
    window,
    output_dir: Path,
) -> tuple[list[str], list[str]]:
    """Gera N3 isolado das lajes (LJ) — reaproveita a MESMA materialização
    que o desktop já faz com sucesso em modo não-read-only
    (`MainWindow._materialize_slabs_for_n1_n3_and_robo`: `slab_to_n1_robot_
    ficha` + `_merge_lj_n3_teacher`, sem gabarito N2/N4), só que gravando em
    diretório temporário isolado em vez de Fase-4/Fase-6 reais da obra — o
    headless roda com `_sa_read_only_run=True`, que pula essa materialização
    de propósito (grava na obra real), por isso LJ nunca tinha N3 aqui.
    """
    script = _REPO_ROOT / 'scripts' / 'gerar_lj_dxf_stog.py'
    output_dir.mkdir(parents=True, exist_ok=True)
    json_dir = output_dir.parent / 'contracts_lj'
    json_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []
    failed: list[str] = []

    for slab in getattr(window, 'slabs_found', []) or []:
        nome = str(slab.get('name') or '').strip().upper()
        if not nome:
            continue
        try:
            ficha = window._slab_to_n1_robot_ficha(slab)
            n3_ficha = window._merge_lj_n3_teacher(ficha, {})
            (json_dir / f'{ficha.get("nome") or nome}.json').write_text(
                json.dumps(n3_ficha, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
        except Exception as exc:
            failed.append(nome)
            print(
                f'[SA-HUMAN] N3 LJ contrato falhou para {nome}: {exc}',
                flush=True,
            )
            continue

        command = [
            sys.executable,
            str(script),
            '--obra', str(obra_dir),
            '--item', nome,
            '--mode', 'planta',
            '--json-dir', str(json_dir),
            '--out-dir', str(output_dir),
        ]
        try:
            result = subprocess.run(
                command,
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=90,
                env={
                    key: value for key, value in os.environ.items()
                    if key != 'CAD_MOTOR_HEADLESS'
                },
            )
        except subprocess.TimeoutExpired:
            failed.append(nome)
            print(f'[SA-HUMAN] N3 LJ timeout (90s) para {nome}', flush=True)
            continue
        expected = output_dir / f'LJ_preview_{nome}.dxf'
        if result.returncode == 0 and expected.is_file():
            generated.append(nome)
        else:
            failed.append(nome)
            detail = (result.stderr or result.stdout or '').strip()[-300:]
            print(
                f'[SA-HUMAN] N3 LJ ausente para {nome}: {detail}',
                flush=True,
            )
    return generated, failed


def run_analysis(
    obra: str,
    pavimento: str,
    *,
    project_id: str | None = None,
    db_path: str = _DB_DEFAULT,
    run_diagnostics: bool = True,
    sections: set[str] | None = None,
    persist_db: bool = False,
    item_names: set[str] | None = None,
) -> dict:
    """Executa a Análise Geral real do SA e exporta um pack imutável.

    `sections`: repassado a `PreValidationDialog._export_html_snapshot`.
    `None` (default) gera todas as classes, como antes. Um subconjunto de
    `{'pilares', 'lajes', 'fundos_viga'}` gera só essas (ver `--secao`).
    """
    started_at = time.perf_counter()
    stage_started_at = started_at

    def report_stage(label: str) -> None:
        """Registra o custo das etapas sem alterar o contrato do headless."""
        nonlocal stage_started_at
        now = time.perf_counter()
        print(
            f'[SA-HUMAN][PERF] {label}: {now - stage_started_at:.2f}s '
            f'(acumulado {now - started_at:.2f}s)',
            flush=True,
        )
        stage_started_at = now

    from src.core.sa_project_source import resolve_sa_project_from_db

    project = resolve_sa_project_from_db(
        db_path=db_path,
        obra=obra,
        pavimento=pavimento,
        project_id=project_id,
    )
    source_path = project['dxf_path']
    project_id = str(project['id'])
    project_name = str(
        project.get('pavement_name') or project.get('name') or pavimento
    )
    # O `project_id` é a fonte de verdade da obra selecionada. Normalizar o
    # pavimento resolvido evita que o default legado de CLI (13_PAV) vaze para
    # diagnósticos, manifestos e artefatos de um projeto diferente.
    from src.core.ficha_utils import canonical_pavimento
    pavimento = canonical_pavimento(project_name)
    # O N1 continua contextual, mas todo o trabalho derivado de classe
    # (contratos, exportação, diagnósticos e N3) respeita ``--secao``.
    active_sections = _n3_sections_for_run(sections)
    print(f'[SA-HUMAN] project_id: {project_id}', flush=True)
    print(f'[SA-HUMAN] projects.dxf_path: {source_path}', flush=True)

    # Deve existir antes do MainWindow: alguns robôs inicializam durante o
    # construtor. Qualquer escrita incidental será desviada para candidato.
    fast_pillar_path = bool(sections == {'pilares'} and item_names)
    os.environ['CAD_MOTOR_HEADLESS'] = '1'
    if fast_pillar_path:
        print(
            '[SA-HUMAN] Fast path N1 PIL: motores canonicos sem MainWindow',
            flush=True,
        )
        fast_result = _run_legacy_analysis(
            source_path,
            obra,
            pavimento,
            project_id=project_id,
            build_html=False,
            db_path=db_path,
        )
        window = fast_result['runner']
        from src.core.database import DatabaseManager
        db = DatabaseManager(db_path)
        old_snapshot = {
            'pillars': db.load_pillars(project_id),
            'slabs': db.load_slabs(project_id),
            'beams': db.load_beams(project_id),
        }
        fresh_snapshot = {
            'pillars': copy.deepcopy(old_snapshot['pillars']),
            'slabs': copy.deepcopy(window.slabs_found),
            'beams': copy.deepcopy(window.beams_found),
        }
        window.pillars_found = copy.deepcopy(old_snapshot['pillars'])
        window.slabs_found = copy.deepcopy(old_snapshot['slabs'])
        window.beams_found = copy.deepcopy(old_snapshot['beams'])
        window.active_project_id = project_id
        window.current_project_name = project_name
        window._analysis_in_progress = False
        window.load_project_action = lambda: None

        def _activate_fast_snapshot(*_args, **_kwargs):
            window.pillars_found = fresh_snapshot['pillars']
            window.slabs_found = fresh_snapshot['slabs']
            window.beams_found = fresh_snapshot['beams']

        window.process_pillars_action = _activate_fast_snapshot
        window._build_pre_validation_dialog = lambda: _build_fast_pre_validation_dialog(
            window,
            obra=obra,
            pavimento=pavimento,
            db_path=db_path,
        )
        report_stage('analise N1 contextual incremental')
    else:
        from main import MainWindow
        window = MainWindow()
        window._sa_read_only_run = True
        window.current_project_id = project_id
        window.active_project_id = project_id
        window.current_project_name = project_name
    try:
        window.load_project_action()
        if not window.dxf_data:
            raise RuntimeError(
                f'SA humano não carregou projects.dxf_path: {source_path}'
            )
        old_snapshot = {
            'pillars': copy.deepcopy(getattr(window, 'pillars_found', []) or []),
            'slabs': copy.deepcopy(getattr(window, 'slabs_found', []) or []),
            'beams': copy.deepcopy(getattr(window, 'beams_found', []) or []),
        }

        # É o mesmo método ligado ao botão "Iniciar Análise Geral".
        # O modal não é aberto; decisões humanas persistidas já foram
        # carregadas pelo projeto e permanecem protegidas na memória.
        window.process_pillars_action(skip_pre_validation=True)
        report_stage('analise N1 contextual completa')
        if getattr(window, '_analysis_in_progress', False):
            raise RuntimeError('Análise Geral humana não foi finalizada')

        # O mesmo merge alimenta os HTMLs/gates e, quando autorizado, o DB.
        # Assim não existe diferença entre o que foi inspecionado e o commit.
        from src.core.sa_db_persistence import fv_area_errors, merge_analysis_snapshot
        fresh_slabs = list(getattr(window, 'slabs_found', []) or [])
        merged, merge_stats = merge_analysis_snapshot(
            old_pillars=old_snapshot['pillars'],
            old_slabs=old_snapshot['slabs'],
            old_beams=old_snapshot['beams'],
            new_pillars=list(getattr(window, 'pillars_found', []) or []),
            new_slabs=fresh_slabs,
            new_beams=list(getattr(window, 'beams_found', []) or []),
            project_id=project_id,
        )
        window.pillars_found = merged['pillars']
        window.slabs_found = merged['slabs']
        window.beams_found = merged['beams']
        # Um artefato headless read-only é evidência do motor que acabou de
        # executar.  Não pode renderizar o contorno antigo de um item azul por
        # causa da proteção de persistência humana do merge.  O commit continua
        # usando o merge normal; esta sobreposição nunca alcança o banco.
        if not persist_db and 'lajes' in active_sections:
            fresh_preview_count = _fresh_laj_geometry_for_readonly_preview(
                window.slabs_found, fresh_slabs,
            )
            if fresh_preview_count:
                print(
                    '[SA-HUMAN] LAJ preview read-only: '
                    f'{fresh_preview_count} contorno(s) N1 recém-traçado(s) do DXF.',
                    flush=True,
                )
        # O merge preserva memoria humana, mas pode reintroduzir slots PIL
        # automaticos de uma rodada antiga. Reaplicar a topologia depois do
        # merge mantem DB, ficha N1 e contratos N3 na mesma autoridade. Em
        # microciclo, somente o item solicitado e' materializado.
        from src.core.pillar_face_beams import materialize_face_beams_in_pillars
        face_beams_materialized = materialize_face_beams_in_pillars(
            merged['pillars'],
            getattr(window, 'pavimento_pillar_report', {}) or {},
            item_names=item_names,
        )
        if face_beams_materialized:
            print(
                '[SA-HUMAN] Slots topologicos PIL reaplicados pos-merge: '
                f'{face_beams_materialized} pilar(es)',
                flush=True,
            )
        # O merge preserva memória humana, mas pode repor inferências antigas.
        # Reexecuta o saneamento derivável na coleção efetivamente persistida:
        # apoio automático precisa tocar a fronteira e ter face/lado; nível de
        # vizinho só vem de fonte semanticamente válida. Não altera vínculos
        # humanos e não depende de item/pavimento/obra.
        window._infer_slab_levels_from_context(window.slabs_found)
        # O merge também pode restaurar contornos automáticos antigos de quatro
        # vértices. Normalize-os somente depois da proteção granular, para o
        # objeto efetivamente diagnosticado/persistido obedecer ao contrato.
        from src.core.beam_interpreters import FundoVigaInterpreter
        for beam in window.beams_found:
            FundoVigaInterpreter.repair_area_links(
                beam, context_beams=window.beams_found
            )

        # A ficha FV fica completa só depois do merge e do reparador. Releia
        # aqui a seção/eixo canônicos antes da exportação e do commit: PIL não
        # pode consumir uma cota textual espacial de outra entidade.
        from src.core.pillar_face_beams import reconcile_beam_fundo_facts
        n_fundo_facts = reconcile_beam_fundo_facts(window.beams_found)
        reconciled_beam_names = {
            _item_name(beam)
            for beam in window.beams_found
            if isinstance(beam, dict)
            and beam.get('_section_dimension_source') == 'fundo_ficha_geometrica'
        }
        if n_fundo_facts:
            print(
                '[SA-HUMAN] Fatos FV canonicos reaplicados: '
                f'{n_fundo_facts} viga(s)',
                flush=True,
            )
        # O relatório de faces foi calculado antes do merge. Atualizá-lo com
        # as vigas reconciliadas mantém ficheiro HTML, N3 e DB sob a mesma
        # evidência; a segunda materialização preserva campos humanos.
        window._enrich_pillar_report_with_beams(
            getattr(window, 'pavimento_pillar_report', {}) or {},
            window.beams_found,
        )
        face_beams_materialized = materialize_face_beams_in_pillars(
            window.pillars_found,
            getattr(window, 'pavimento_pillar_report', {}) or {},
            item_names=item_names,
        )
        if face_beams_materialized:
            print(
                '[SA-HUMAN] Slots topologicos PIL reaplicados pos-FV: '
                f'{face_beams_materialized} pilar(es)',
                flush=True,
            )
        _log_selected_pillar_topology(window.pillars_found, item_names)
        report_stage('merge granular e saneamento N1')
        if 'laterais_viga' in active_sections:
            lv_contracts_attached = _attach_lv_generation_contracts(
                window.beams_found, window.pillars_found, pavimento
            )
            print(
                f'[SA-HUMAN] Contratos N3 LV anexados ao snapshot: '
                f'{lv_contracts_attached}',
                flush=True,
            )
        # Um microciclo de LAJ/PIL não pode ser recusado por um fundo de viga
        # fora do escopo. Quando FV for solicitado, o gate continua idêntico
        # e incide sobre a coleção efetivamente processada.
        invalid_fv_areas = (
            fv_area_errors(window.beams_found)
            if 'fundos_viga' in active_sections
            else []
        )
        if invalid_fv_areas:
            raise RuntimeError(
                'Gate FV recusou contorno sem área fechada: '
                + '; '.join(invalid_fv_areas[:10])
            )
        partial_collections = None
        if item_names:
            # Consumido pelo writer LV para que o microciclo nao reintroduza
            # todos os itens N2 classificados Para/Passa na pasta filtrada.
            # A janela normal nao possui este atributo e mantem a uniao total.
            window._headless_item_names = set(item_names)
            changed_beam_names = _changed_canonical_beam_names(
                old_snapshot['beams'], merged['beams'], reconciled_beam_names,
            )
            safe_beam_names, rejected_beam_dependencies = (
                _non_regressive_beam_dependencies(
                    old_snapshot['beams'], merged['beams'], changed_beam_names,
                )
            )
            if rejected_beam_dependencies:
                print(
                    '[SA-HUMAN] Dependencias de viga recusadas por regressao '
                    f'de topologia: {rejected_beam_dependencies}',
                    flush=True,
                )
            partial_collections = _partial_collections_for_sections(
                merged,
                active_sections,
                item_names,
                beam_dependencies=safe_beam_names,
            )
            _apply_item_filter_to_window(window, active_sections, item_names)
            print(
                '[SA-HUMAN] Filtro de itens: '
                f'{", ".join(sorted(item_names))} em {", ".join(sorted(active_sections))}',
                flush=True,
            )
        print(
            '[SA-HUMAN] Merge granular pronto: '
            f"{len(window.pillars_found)} PIL, "
            f"{len(window.slabs_found)} LAJ, "
            f"{len(window.beams_found)} vigas.",
            flush=True,
        )

        html_dir = None
        dialog = None
        diagnostics = {}
        try:
            dialog = window._build_pre_validation_dialog()
            if dialog:
                if item_names:
                    dialog._headless_item_names = set(item_names)
                if sections is not None and len(sections) == 1:
                    # Estado e pack próprios: classes concorrentes não
                    # sobrescrevem os artefatos umas das outras.
                    dialog._headless_run_scope = next(iter(sections))
                html_dir = dialog._export_html_snapshot(sections=sections)
                # `_export_html_snapshot` salva em `run_dir` local e retorna o Path
                print(f'[SA-HUMAN] Pack exportado: {html_dir}', flush=True)
                report_stage('exportacao inicial de fichas')

                # A exportação PIL já materializou PARA+PASSA no cache do
                # diálogo. Se este run for persistido, anexa o mesmo artefato
                # ao snapshot ANTES do commit — DB e HTML/DXF permanecem na
                # mesma versão sem recalcular por outro caminho.
                if persist_db and 'pilares' in active_sections:
                    collections_for_n3 = partial_collections or merged
                    pl_persisted = _attach_pl_n3_variants_to_pillars(
                        collections_for_n3.get('pillars', []),
                        getattr(dialog, '_pl_n3_cache', None),
                    )
                    print(
                        '[SA-HUMAN] Variantes N3 PL anexadas ao snapshot DB: '
                        f'{pl_persisted}',
                        flush=True,
                    )

                diagnostics = (
                    _run_section_diagnostics(
                        html_dir=html_dir,
                        obra=obra,
                        pavimento=pavimento,
                        state_path=dialog._analysis_state_path(),
                        db_path=db_path,
                        item_names=item_names,
                    )
                    if run_diagnostics
                    else {}
                )
                report_stage('diagnosticos canonicos')
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ERROR] Exception during HTML/diagnostics generation: {e}", flush=True)

        # Persistência NÃO depende de N3 preview: o commit usa collections
        # em memória + diagnósticos do pack. N3 LV/FV/LJ pode travar em COM
        # (subprocess timeout falha em filhos AutoCAD) e bloqueava o DB.
        # Ordem: gate+commit primeiro; N3 é best-effort depois.
        persistence = {'status': 'READ_ONLY'}
        if persist_db:
            required_sections = set(_SECTION_DIAGNOSTIC_MODULES)
            if item_names and sections is not None:
                required_sections = set(sections)
            missing = required_sections - set(diagnostics)
            errors = {
                section: diagnostic.get('erro', 'erro desconhecido')
                for section, diagnostic in diagnostics.items()
                if diagnostic.get('status') != 'ok'
            }
            if missing or errors or not html_dir or not Path(html_dir).is_dir():
                raise RuntimeError(
                    'Persistência recusada pelo gate: '
                    f'seções ausentes={sorted(missing)}, erros={errors}, '
                    f'html_dir={html_dir!s}'
                )
            run_id = next(
                (
                    str(diagnostic.get('run_id'))
                    for diagnostic in diagnostics.values()
                    if diagnostic.get('run_id')
                ),
                Path(html_dir).name.rsplit('_', 1)[-1],
            )
            from src.core.sa_db_persistence import persist_analysis_snapshot
            collections_to_persist = partial_collections or merged
            # O dialogo HTML pode reconstruir os vinculos granulares. Reanexa
            # no objeto exato que sera serializado para preservar o contrato N3
            # correspondente aos campos N1 diagnosticados.
            if 'laterais_viga' in active_sections:
                persisted_lv_contracts = _attach_lv_generation_contracts(
                    collections_to_persist.get('beams', []),
                    merged.get('pillars', []),
                    pavimento,
                )
                print(
                    '[SA-HUMAN] Contratos N3 LV reanexados pre-commit: '
                    f'{persisted_lv_contracts}',
                    flush=True,
                )
            persistence = persist_analysis_snapshot(
                db_path=db_path,
                project_id=project_id,
                collections=collections_to_persist,
                run_id=f'sa-{project_id}-{run_id}',
                html_dir=str(html_dir),
                source_dxf=source_path,
                merge_stats=merge_stats,
                delete_missing=not item_names,
            )
            print(
                '[SA-HUMAN] DB COMMIT transacional: '
                f"{persistence['before']} -> {persistence['after']}",
                flush=True,
            )
            report_stage('persistencia transacional')

        # O N3 consome a coleção da janela, que também pode ter sido
        # reconstruída pelo diálogo. Reanexar é idempotente e evita preview
        # vazio por contrato descartado depois da exportação HTML.
        if 'laterais_viga' in active_sections:
            _attach_lv_generation_contracts(
                list(getattr(window, 'beams_found', []) or []),
                merged.get('pillars', []),
                pavimento,
            )

        # N3 best-effort: prévias isoladas + re-export do pack. Falha/timeout
        # NÃO reverte o commit acima nem aborta a rodada. ``--item`` filtra
        # somente após a análise contextual completa; por isso a seção ativa
        # também deve limitar estes subprocessos caros.
        active_n3_sections = active_sections
        manifest_path = ''
        try:
            obra_dir = _REPO_ROOT.parent / 'DADOS-OBRAS' / obra
            fv_results = _filter_fv_results_for_items(
                list(getattr(window, '_last_fv_results', []) or []),
                item_names if 'fundos_viga' in active_n3_sections else None,
            )
            n3_tmp_root = _REPO_ROOT / 'scripts' / 'arete' / 'tmp'
            n3_tmp_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix='sa_n3_nova_', dir=str(n3_tmp_root)
            ) as n3_temp:
                if 'fundos_viga' in active_n3_sections:
                    try:
                        generated, failed = _generate_fv_n3_nova_previews(
                            obra_dir, fv_results, Path(n3_temp) / 'dxf'
                        )
                        print(
                            f'[SA-HUMAN] N3 NOVA isolado: {len(generated)} gerado(s), '
                            f'{len(failed)} ausente(s)',
                            flush=True,
                        )
                    except Exception as exc:
                        print(f'[SA-HUMAN] N3 NOVA bloco falhou: {exc}', flush=True)
                if 'laterais_viga' in active_n3_sections:
                    try:
                        lv_generated, lv_failed = _generate_lv_n3_nova_previews(
                            obra_dir, window.beams_found, Path(n3_temp) / 'dxf'
                        )
                        print(
                            f'[SA-HUMAN] N3 LV isolado: {len(lv_generated)} gerado(s), '
                            f'{len(lv_failed)} ausente(s)',
                            flush=True,
                        )
                    except Exception as exc:
                        print(f'[SA-HUMAN] N3 LV bloco falhou: {exc}', flush=True)
                if 'lajes' in active_n3_sections:
                    try:
                        lj_generated, lj_failed = _generate_lj_n3_nova_previews(
                            obra_dir, window, Path(n3_temp) / 'dxf'
                        )
                        print(
                            f'[SA-HUMAN] N3 LJ isolado: {len(lj_generated)} gerado(s), '
                            f'{len(lj_failed)} ausente(s)',
                            flush=True,
                        )
                    except Exception as exc:
                        print(f'[SA-HUMAN] N3 LJ bloco falhou: {exc}', flush=True)
                # PL N3: sempre as duas listas (PARA + PASSA), igual desktop/CE.
                # Reaproveita o diálogo da primeira exportação: ela já criou
                # variantes PL e preencheu seu cache antes de escrever HTML.
                if 'pilares' in active_n3_sections and dialog is None:
                    dialog = window._build_pre_validation_dialog()
                    if dialog is not None and item_names:
                        dialog._headless_item_names = set(item_names)
                pl_generated, pl_failed = [], ['dialog-ausente']
                if 'pilares' in active_n3_sections and dialog is not None:
                    try:
                        pl_stats = getattr(dialog, '_last_pl_n3_materialize', {}) or {}
                        pl_generated = list(pl_stats.get('generated') or [])
                        pl_failed = list(pl_stats.get('failed') or [])
                        if not pl_generated and not pl_failed:
                            pl_generated, pl_failed = dialog.materialize_pl_n3_variants()
                    except Exception as exc:
                        pl_failed = [f'materialize-error:{exc}']
                        print(
                            f'[SA-HUMAN] N3 PL materialize falhou: {exc}',
                            flush=True,
                        )
                if 'pilares' in active_n3_sections:
                    print(
                        f'[SA-HUMAN] N3 PL PARA+PASSA: {len(pl_generated)} gerado(s), '
                        f'{len(pl_failed)} ausente(s)',
                        flush=True,
                    )
                needs_secondary_reexport = bool(
                    active_n3_sections & {'fundos_viga', 'laterais_viga', 'lajes'}
                )
                if dialog is None and needs_secondary_reexport:
                    dialog = window._build_pre_validation_dialog()
                if dialog is not None and needs_secondary_reexport:
                    dialog._n3_preview_dir = str(Path(n3_temp) / 'dxf')
                    dialog._n3_contract_dir = str(Path(n3_temp) / 'contracts')
                    html_dir = dialog._export_html_snapshot(sections=sections)
                    print(f'[SA-HUMAN] Pack reexportado c/ N3: {html_dir}', flush=True)
                report_stage('previews N3 e reexportacao')
        except Exception as exc:
            print(f'[SA-HUMAN] AVISO bloco N3 best-effort: {exc}', flush=True)

        try:
            if html_dir:
                manifest_path = _publish_arete_manifest(
                    html_dir=html_dir,
                    obra=obra,
                    pavimento=pavimento,
                    diagnostics=diagnostics,
                )
                print(f'[SA-HUMAN] Manifesto Arete: {manifest_path}', flush=True)
                report_stage('manifesto Arete')
        except Exception as exc:
            manifest_path = ''
            print(f'[SA-HUMAN] AVISO manifesto Arete não gerado: {exc}', flush=True)

        print(
            f'[SA-HUMAN][PERF] total da rodada: {time.perf_counter() - started_at:.2f}s',
            flush=True,
        )
        return {
            'obra': obra,
            'pavimento': project_name,
            'project_id': project_id,
            'dxf_path': source_path,
            'n_pilares': len(window.pillars_found),
            'n_slabs': len(window.slabs_found),
            'n_beams': len(window.beams_found),
            'html_dir': str(html_dir) if html_dir else '',
            'diagnostics': diagnostics,
            'fv_diagnostic': diagnostics.get('fundos_viga', {'status': 'ignorado'}),
            'arete_manifest': str(manifest_path),
            'merge_stats': merge_stats,
            'persistence': persistence,
        }
    finally:
        window.close()


_VALID_SECTIONS = {'pilares', 'lajes', 'fundos_viga', 'laterais_viga'}


def _n3_sections_for_run(sections: set[str] | None) -> set[str]:
    """Resolve as classes que podem executar o pós-processamento N3.

    Sem ``--secao`` preserva o comportamento histórico (todas as classes).
    Com a flag, N3 deve obedecer exatamente ao recorte solicitado: analisar
    contexto completo continua necessário, mas gerar previews das outras
    classes é trabalho caro e sem produto para a rodada filtrada.
    """
    return set(sections) if sections else set(_VALID_SECTIONS)


def _parse_sections(raw_values: list[str] | None) -> set[str] | None:
    """`--secao lajes --secao pilares` ou `--secao lajes,pilares` -> {'lajes','pilares'}.

    Sem a flag (`raw_values` vazio/None) -> None (gera tudo, como hoje).
    """
    if not raw_values:
        return None
    result: set[str] = set()
    for raw in raw_values:
        for piece in raw.split(','):
            piece = piece.strip()
            if not piece:
                continue
            if piece not in _VALID_SECTIONS:
                raise ValueError(
                    f"--secao inválido: '{piece}' (válidos: {sorted(_VALID_SECTIONS)})"
                )
            result.add(piece)
    return result or None


def main() -> None:
    ap = argparse.ArgumentParser(
        description='Exporta HTMLs pelo mesmo fluxo humano do Structural Analyzer'
    )
    ap.add_argument('--obra',  default='Obra_TREINO_1')
    ap.add_argument('--pav',   default='13_PAV')
    ap.add_argument(
        '--project-id', default=None,
        help='ID exato selecionado no SA; sem ele, usa o primeiro projeto do combo',
    )
    ap.add_argument('--db', default=_DB_DEFAULT)
    ap.add_argument(
        '--secao', action='append', default=None,
        help=(
            'Gerar só esta(s) classe(s) — repetível ou separado por vírgula '
            f'(valores: {", ".join(sorted(_VALID_SECTIONS))}). '
            'Sem a flag = todas as classes (comportamento padrão, inalterado).'
        ),
    )
    ap.add_argument(
        '--skip-diagnostico-fv', action='store_true',
        help=(
            'Gera os HTMLs sem executar os diagnósticos numéricos N1×N2 '
            '(FV, LAJ, PIL, LV — nome do flag preservado por compatibilidade)'
        ),
    )
    ap.add_argument(
        '--item', action='append', default=None, nargs='+',
        help=(
            'Filtrar a rodada para um ou mais itens da(s) --secao informada(s). '
            'Aceita repeticao e virgula: --secao lajes --item L318 L319.'
        ),
    )
    ap.add_argument('--open',  action='store_true',
                    help='Abrir HTML no navegador apos gerar')
    ap.add_argument(
        '--persist-db', action='store_true',
        help=(
            'Após análise completa + diagnósticos OK, atualizar PIL/LAJ/FV/LV '
            'no DB em uma única transação, preservando validações granulares.'
        ),
    )
    ap.add_argument('--wait', action='store_true',
                    help='Se outro headless estiver rodando, aguardar a vez '
                         '(poll 10s, timeout 30min) em vez de abortar — '
                         'recomendado para agentes/automacao')
    args = ap.parse_args()
    try:
        sections = _parse_sections(args.secao)
    except ValueError as exc:
        ap.error(str(exc))
    if False:
        ap.error('--persist-db exige execução completa, sem --secao')
    flat_items = [piece for group in (args.item or []) for piece in group]
    item_names = _parse_item_names(flat_items)
    if item_names and sections is None:
        ap.error('--item exige --secao para evitar ambiguidade entre classes')
    if args.persist_db and sections is not None and not item_names:
        ap.error('--persist-db exige execucao completa, sem --secao')
    if args.persist_db and args.skip_diagnostico_fv:
        ap.error('--persist-db exige os quatro diagnósticos; remova --skip-diagnostico-fv')

    # Microciclos read-only de classes distintas têm filas isoladas. Rodadas
    # perigosas reservam global + todas as classes antes de inicializar o Qt.
    try:
        from scripts.arete.single_instance import acquire_lock, wait_for_lock, refresh_lock
    except ImportError:
        from single_instance import acquire_lock, wait_for_lock, refresh_lock
    _lock_names, _lock_scope = _headless_lock_plan(sections, item_names, args.persist_db)
    # A sonda ``headless_sa`` foi criada antes das filas por classe. Só uma
    # rodada global continua aguardando-a: num microciclo read-only de uma
    # classe, consultá-la antes de ``headless_sa_fv/laj/...`` recriava a fila
    # global e anulava exatamente a isolação pretendida.
    acquire = wait_for_lock if args.wait else acquire_lock
    if not _lock_scope.startswith('classe:'):
        _legacy_probe, _holder = acquire('headless_sa')
        if _legacy_probe is None:
            print('[SA] ABORTADO: fila legada headless_sa ainda ocupada.', flush=True)
            if _holder:
                print(f'[SA] Instância ativa: {_holder}', flush=True)
            print('[SA] Rode novamente com --wait. NÃO finalize o processo detentor.', flush=True)
            sys.exit(2)
        _release_headless_locks([_legacy_probe])
    _instance_locks = []
    _holder = None
    _blocked_lock = None
    for _lock_name in _lock_names:
        _lock, _holder = acquire(_lock_name)
        if _lock is None:
            _blocked_lock = _lock_name
            break
        _instance_locks.append(_lock)
    if _blocked_lock is not None:
        _release_headless_locks(_instance_locks)
        print(
            f'[SA] ABORTADO: fila ocupada ({_blocked_lock}; escopo {_lock_scope}).',
            flush=True,
        )
        if _holder:
            print(f'[SA] Instância ativa: {_holder}', flush=True)
        print('[SA] Rode novamente com --wait. NÃO finalize o processo detentor.', flush=True)
        sys.exit(2)

    # QApplication obrigatório para PreValidationDialog, estritamente offscreen.
    # Se a plataforma não for a esperada, falhamos antes de qualquer janela.
    import atexit
    import threading
    print(
        f'[SA] Locks adquiridos: {", ".join(_lock_names)} (escopo {_lock_scope}).',
        flush=True,
    )
    atexit.register(_release_headless_locks, _instance_locks)
    _lock_heartbeat_stop = threading.Event()

    def _heartbeat_lock() -> None:
        while not _lock_heartbeat_stop.wait(15.0):
            for _lock in _instance_locks:
                refresh_lock(_lock, event='running')

    threading.Thread(
        target=_heartbeat_lock,
        name='headless-sa-lock-heartbeat',
        daemon=True,
    ).start()
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(['headless_sa_analise'])
    platform = QGuiApplication.platformName().lower()
    if platform != 'offscreen':
        raise RuntimeError(
            f'Backend Qt inesperado para headless: {platform!r} (esperado: offscreen)'
        )
    app.setQuitOnLastWindowClosed(False)
    for _lock in _instance_locks:
        refresh_lock(_lock, event='qt_offscreen_ready')

    result = run_analysis(
        obra=args.obra,
        pavimento=args.pav,
        project_id=args.project_id,
        db_path=args.db,
        run_diagnostics=not args.skip_diagnostico_fv,
        sections=sections,
        persist_db=args.persist_db,
        item_names=item_names,
    )
    for _lock in _instance_locks:
        refresh_lock(_lock, event='analysis_complete')

    print('\n' + '=' * 60, flush=True)
    print(f'RESUMO: {result["obra"]} / {result["pavimento"]}', flush=True)
    print(f'  Pilares : {result["n_pilares"]}', flush=True)
    print(f'  Lajes   : {result["n_slabs"]}', flush=True)
    print(f'  Vigas   : {result["n_beams"]}', flush=True)
    print(f'  HTMLs   : {result["html_dir"]}', flush=True)
    diagnostics = result['diagnostics']
    if not diagnostics:
        print('  Diagnósticos: ignorados (--skip-diagnostico-fv)', flush=True)
    for section, diag in diagnostics.items():
        label = _SECTION_LABELS.get(section, section.upper())
        print(f'  Diag. {label}: {diag["status"]}', flush=True)
        if diag.get('json_path'):
            print(f'    JSON : {diag["json_path"]}', flush=True)
            print(f'    JSONL: {diag["jsonl_path"]}', flush=True)
        elif diag.get('erro'):
            print(f'    aviso: {diag["erro"]}', flush=True)
    print(f'  Manifest: {result["arete_manifest"]}', flush=True)
    print(f'  Fonte   : {result["dxf_path"]}', flush=True)
    persistence = result.get('persistence') or {}
    print(f'  DB      : {persistence.get("status", "READ_ONLY")}', flush=True)
    if persistence.get('status') == 'COMMITTED':
        print(f'    Antes : {persistence["before"]}', flush=True)
        print(f'    Depois: {persistence["after"]}', flush=True)
    print('=' * 60, flush=True)

    if args.open and result['html_dir']:
        import glob as _glob
        htmls = sorted(_glob.glob(os.path.join(result['html_dir'], 'preficha_*.html')))
        if htmls:
            import subprocess
            print(f'[SA] Abrindo {os.path.basename(htmls[0])} no navegador...', flush=True)
            os.startfile(htmls[0])

    _lock_heartbeat_stop.set()
    _release_headless_locks(_instance_locks)
    _instance_locks.clear()
    print(f'[SA] Locks liberados: {", ".join(_lock_names)}.', flush=True)


if __name__ == '__main__':
    main()
