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
import subprocess
import tempfile
from pathlib import Path

# QT_QPA_PLATFORM=offscreen ANTES de qualquer import Qt
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT   = _SCRIPT_DIR.parent.parent
sys.path.insert(0, str(_REPO_ROOT))


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
        self.pavimento_pillar_report: dict = {}
        self.pavimento_nivel_report: dict = {}
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
) -> dict:
    """
    Executa pipeline SA completo e gera HTMLs.
    Retorna dict com resumo (n_pilares, n_slabs, n_beams, html_dir).
    """
    from src.core.dxf_loader  import DXFLoader
    from src.core.slab_tracer import SlabTracer
    from src.core.beam_tracer import BeamTracer

    runner = HeadlessRunner()

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
        texts, valid_layers=None, search_radius=200.0, teacher_dims=None,
    )
    runner.slabs_found.sort(key=_nat_key)
    print(f'[SA] Lajes detectadas: {len(runner.slabs_found)}', flush=True)

    # 5. Processar cada laje (preench links laje_pilares_apoio, laje_dim, etc.)
    print('[SA] Processando lajes...', flush=True)
    for i, s in enumerate(runner.slabs_found):
        s['id']         = f'headless_l_{i+1}'
        s['id_item']    = f'{i+1:02}'
        s['project_id'] = 'headless_01'
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
        b['project_id'] = 'headless_01'
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

    # 10. Criar PreValidationDialog headless (sem show/exec)
    print('[SA] Criando PreValidationDialog headless...', flush=True)

    _dados_root      = str(_REPO_ROOT / 'DADOS-OBRAS')
    _convention_file = (
        os.path.join(_dados_root, obra, 'convencao_pilares.json') if obra else None
    )
    _db_path = 'D:/Agente-cad-PYSIDE/project_data.vision'

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


def _run_diagnostic_postprocess(
    module_name: str,
    *,
    label: str,
    obra: str,
    pavimento: str,
    state_path: str,
    db_path: str,
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


def run_analysis(
    obra: str,
    pavimento: str,
    *,
    project_id: str | None = None,
    db_path: str = _DB_DEFAULT,
    run_diagnostics: bool = True,
    sections: set[str] | None = None,
    persist_db: bool = False,
) -> dict:
    """Executa a Análise Geral real do SA e exporta um pack imutável.

    `sections`: repassado a `PreValidationDialog._export_html_snapshot`.
    `None` (default) gera todas as classes, como antes. Um subconjunto de
    `{'pilares', 'lajes', 'fundos_viga'}` gera só essas (ver `--secao`).
    """
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
    print(f'[SA-HUMAN] project_id: {project_id}', flush=True)
    print(f'[SA-HUMAN] projects.dxf_path: {source_path}', flush=True)

    # Deve existir antes do MainWindow: alguns robôs inicializam durante o
    # construtor. Qualquer escrita incidental será desviada para candidato.
    os.environ['CAD_MOTOR_HEADLESS'] = '1'
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
        if getattr(window, '_analysis_in_progress', False):
            raise RuntimeError('Análise Geral humana não foi finalizada')

        # O mesmo merge alimenta os HTMLs/gates e, quando autorizado, o DB.
        # Assim não existe diferença entre o que foi inspecionado e o commit.
        from src.core.sa_db_persistence import fv_area_errors, merge_analysis_snapshot
        merged, merge_stats = merge_analysis_snapshot(
            old_pillars=old_snapshot['pillars'],
            old_slabs=old_snapshot['slabs'],
            old_beams=old_snapshot['beams'],
            new_pillars=list(getattr(window, 'pillars_found', []) or []),
            new_slabs=list(getattr(window, 'slabs_found', []) or []),
            new_beams=list(getattr(window, 'beams_found', []) or []),
            project_id=project_id,
        )
        window.pillars_found = merged['pillars']
        window.slabs_found = merged['slabs']
        window.beams_found = merged['beams']
        # O merge pode restaurar contornos automáticos antigos de quatro
        # vértices. Normalize-os somente depois da proteção granular, para o
        # objeto efetivamente diagnosticado/persistido obedecer ao contrato.
        from src.core.beam_interpreters import FundoVigaInterpreter
        for beam in window.beams_found:
            FundoVigaInterpreter.repair_area_links(
                beam, context_beams=window.beams_found
            )
        invalid_fv_areas = fv_area_errors(window.beams_found)
        if invalid_fv_areas:
            raise RuntimeError(
                'Gate FV recusou contorno sem área fechada: '
                + '; '.join(invalid_fv_areas[:10])
            )
        print(
            '[SA-HUMAN] Merge granular pronto: '
            f"{len(window.pillars_found)} PIL, "
            f"{len(window.slabs_found)} LAJ, "
            f"{len(window.beams_found)} vigas.",
            flush=True,
        )

        html_dir = None
        diagnostics = {}
        try:
            dialog = window._build_pre_validation_dialog()
            if dialog:
                html_dir = dialog._export_html_snapshot(sections=sections)
                # `_export_html_snapshot` salva em `run_dir` local e retorna o Path
                print(f'[SA-HUMAN] Pack exportado: {html_dir}', flush=True)

                diagnostics = (
                    _run_section_diagnostics(
                        html_dir=html_dir,
                        obra=obra,
                        pavimento=pavimento,
                        state_path=dialog._analysis_state_path(),
                        db_path=db_path,
                    )
                    if run_diagnostics
                    else {}
                )
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ERROR] Exception during HTML/diagnostics generation: {e}", flush=True)

        obra_dir = _REPO_ROOT.parent / 'DADOS-OBRAS' / obra
        fv_results = list(getattr(window, '_last_fv_results', []) or [])
        n3_tmp_root = _REPO_ROOT / 'scripts' / 'arete' / 'tmp'
        n3_tmp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix='sa_n3_nova_', dir=str(n3_tmp_root)
        ) as n3_temp:
            generated, failed = _generate_fv_n3_nova_previews(
                obra_dir, fv_results, Path(n3_temp) / 'dxf'
            )
            print(
                f'[SA-HUMAN] N3 NOVA isolado: {len(generated)} gerado(s), '
                f'{len(failed)} ausente(s)',
                flush=True,
            )
            dialog = window._build_pre_validation_dialog()
            dialog._n3_preview_dir = str(Path(n3_temp) / 'dxf')
            dialog._n3_contract_dir = str(Path(n3_temp) / 'contracts')
            html_dir = dialog._export_html_snapshot(sections=sections)
            state_path = dialog._analysis_state_path()
        print(f'[SA-HUMAN] Pack exportado: {html_dir}', flush=True)
        diagnostics = (
            _run_section_diagnostics(
                html_dir=html_dir,
                obra=obra,
                pavimento=pavimento,
                state_path=state_path,
                db_path=db_path,
            )
            if run_diagnostics
            else {}
        )
        try:
            manifest_path = _publish_arete_manifest(
                html_dir=html_dir,
                obra=obra,
                pavimento=pavimento,
                diagnostics=diagnostics,
            )
            print(f'[SA-HUMAN] Manifesto Arete: {manifest_path}', flush=True)
        except Exception as exc:
            manifest_path = ''
            print(f'[SA-HUMAN] AVISO manifesto Arete não gerado: {exc}', flush=True)
        persistence = {'status': 'READ_ONLY'}
        if persist_db:
            required_sections = set(_SECTION_DIAGNOSTIC_MODULES)
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
            persistence = persist_analysis_snapshot(
                db_path=db_path,
                project_id=project_id,
                collections=merged,
                run_id=f'sa-{project_id}-{run_id}',
                html_dir=str(html_dir),
                source_dxf=source_path,
                merge_stats=merge_stats,
            )
            print(
                '[SA-HUMAN] DB COMMIT transacional: '
                f"{persistence['before']} -> {persistence['after']}",
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
    if args.persist_db and sections is not None:
        ap.error('--persist-db exige execução completa, sem --secao')
    if args.persist_db and args.skip_diagnostico_fv:
        ap.error('--persist-db exige os quatro diagnósticos; remova --skip-diagnostico-fv')

    # Trava anti-OOM: duas execuções simultâneas do headless (SA+matplotlib)
    # esgotam a RAM da workstation. O lock é liberado pelo SO ao fim do
    # processo (mesmo em crash) — nunca fica órfão; basta aguardar e rerodar.
    try:
        from scripts.arete.single_instance import acquire_lock, wait_for_lock
    except ImportError:
        from single_instance import acquire_lock, wait_for_lock
    if args.wait:
        _instance_lock, _holder = wait_for_lock('headless_sa')
    else:
        _instance_lock, _holder = acquire_lock('headless_sa')
    if _instance_lock is None:
        print('[SA] ABORTADO: já existe uma execução do headless em andamento '
              '(proteção anti-OOM — 1 headless por vez nesta máquina).', flush=True)
        if _holder:
            print(f'[SA] Instância ativa: {_holder}', flush=True)
        print('[SA] O que fazer: rode novamente com --wait para aguardar '
              'automaticamente a vez, ou aguarde a execução atual terminar. '
              'NÃO finalize o processo detentor — ele está trabalhando.', flush=True)
        sys.exit(2)

    # QApplication obrigatorio para PreValidationDialog (mesmo offscreen)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    result = run_analysis(
        obra=args.obra,
        pavimento=args.pav,
        project_id=args.project_id,
        db_path=args.db,
        run_diagnostics=not args.skip_diagnostico_fv,
        sections=sections,
        persist_db=args.persist_db,
    )

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


if __name__ == '__main__':
    main()
