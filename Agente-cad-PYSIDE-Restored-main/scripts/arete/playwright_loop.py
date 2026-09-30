#!/usr/bin/env python
"""
playwright_loop.py — Visualização headless e interpretacao das fichas HTML de pré-análise.

Pipeline de looping:
  1. generate_html_fichas()   -> cria HTMLs (estado JSON -> HTML)
  2. capture_html_pages()     -> Playwright renderiza cada HTML -> PNGs completos
  3. build_loop_report()      -> monta relatório JSON com paths de imagens + metadados
  4. (externo) Claude lê PNGs -> interpreta -> gera feedback -> próxima iteração

Uso stand-alone:
    python playwright_loop.py --obra Obra_TREINO_1 --pav 13_PAV
    python playwright_loop.py --html_dir scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_20260630_120000

Uso como módulo:
    from scripts.arete.playwright_loop import run_loop_cycle
    report = run_loop_cycle(obra='Obra_TREINO_1', pav='13_PAV')
    # report['screenshots'] -> lista de {'slug', 'html', 'png', 'rows'}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Caminhos base ─────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT   = _SCRIPT_DIR.parent.parent
_HTML_BASE   = _SCRIPT_DIR / 'html_fichas'
_LOOPS_DIR   = _SCRIPT_DIR / 'loop_reports'

# Viewport largo para capturar tabelas completas (scroll horizontal desnecessário)
_VIEWPORT_W = 2400
_VIEWPORT_H = 900


# ─────────────────────────────────────────────────────────────────────────────
# Captura Playwright
# ─────────────────────────────────────────────────────────────────────────────

def capture_html_pages(
    html_dir: Path | str,
    out_dir: Path | str | None = None,
    slugs: list[str] | None = None,
) -> list[dict]:
    """
    Abre cada preficha_*.html com Playwright headless e tira screenshot full-page.

    Retorna lista de:
      { slug, html_path, png_path, rows_count, captured_at }
    """
    html_dir = Path(html_dir)
    out_dir  = Path(out_dir) if out_dir else html_dir / 'screenshots'
    out_dir.mkdir(parents=True, exist_ok=True)

    # Candidatos: todos os preficha_*.html ou filtrado por slugs
    htmls = sorted(html_dir.glob('preficha_*.html'))
    if slugs:
        htmls = [h for h in htmls if any(s in h.stem for s in slugs)]

    if not htmls:
        print(f'  [playwright] Nenhum HTML encontrado em {html_dir}')
        return []

    results: list[dict] = []

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': _VIEWPORT_W, 'height': _VIEWPORT_H},
        )
        page = context.new_page()

        for html_path in htmls:
            slug = html_path.stem.replace('preficha_', '')
            png_path = out_dir / f'{slug}.png'
            try:
                page.goto(f'file:///{html_path.as_posix()}', wait_until='networkidle',
                          timeout=15_000)
                page.wait_for_timeout(300)   # aguarda imagens base64 renderizarem

                # Conta linhas de dados visíveis
                rows_count = page.locator('tbody tr').count()

                page.screenshot(path=str(png_path), full_page=True)
                results.append({
                    'slug':         slug,
                    'html_path':    str(html_path),
                    'png_path':     str(png_path),
                    'rows_count':   rows_count,
                    'captured_at':  datetime.now().isoformat(timespec='seconds'),
                })
                print(f'  [playwright] {slug:<30} {rows_count:3d} linhas -> {png_path.name}')
            except Exception as exc:
                print(f'  [playwright] ERRO {slug}: {exc}')

        context.close()
        browser.close()

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Captura de páginas granulares por item (pilares/fundos_viga/lajes)
# ─────────────────────────────────────────────────────────────────────────────
#
# As fichas granulares (uma página HTML por pilar/segmento/laje, com sidebar +
# navegação, geradas por _write_pilar_pages / preficha_fundo_html.py /
# preficha_laje_html.py) empilham 4+ cards de evidência (N1/N2/N3/N4) e
# facilmente passam de 2500-3000px de altura total. Isso expõe um bug real do
# Chromium headless: conteúdo fora do viewport ORIGINAL (o viewport usado no
# primeiro layout/paint) às vezes não é rasterizado, mesmo que:
#   - a imagem já esteja com `naturalWidth/naturalHeight` carregados no DOM
#     (`page.wait_for_function` em "img.complete" não detecta o problema);
#   - `locator.screenshot()` retorne um PNG do tamanho certo — mas com
#     blocos pretos/vazios nas seções que estavam abaixo da dobra;
#   - `page.screenshot(full_page=True)` (mecanismo nativo do Playwright para
#     página inteira) TAMBÉM pode retornar áreas não pintadas nesse cenário
#     de layout (cards com `width:100%!important` empilhados em coluna única).
#
# Fix verificado: redimensionar o viewport para a altura total do documento
# (`document.documentElement.scrollHeight`) ANTES de tirar o screenshot do
# elemento, forçando o Chromium a pintar tudo dentro do viewport "visível".
# Depois disso `locator.screenshot()` funciona normalmente, sem crop manual.
#
# Sintoma característico de quem cair nessa armadilha: screenshots com o
# tamanho certo, mas 100% pretos ou com o topo ok e o resto cortado — e ao
# reabrir a mesma página no navegador normal (não headless) tudo aparece
# certo. Se isso acontecer, é quase certo que é esse bug, não um problema
# nos dados/HTML.


def capture_granular_item_pages(
    section_dir: Path | str,
    out_dir: Path | str | None = None,
    selector: str = '.evidence-grid',
    exclude_names: tuple[str, ...] = ('index.html',),
    exclude_prefixes: tuple[str, ...] = ('interpretacao_',),
    viewport_width: int = 1000,
    recursive: bool = True,
) -> list[dict]:
    """
    Captura screenshots de páginas granulares por item (uma página HTML por
    pilar/segmento/laje), aplicando o fix de paint-culling acima.

    Usar para: scripts/arete/html_fichas/{obra}/{pav}/pilares/**/*.html,
    .../fundos_viga/*.html, .../lajes/*.html — qualquer diretório com páginas
    HTML individuais que tenham a seção `.evidence-grid` (N1/N2/N3/N4).

    Para os relatórios tabulares antigos (preficha_*.html, uma tabela larga
    e não muito alta), prefira `capture_html_pages()` — não sofre desse bug
    e já usa full_page=True com sucesso.

    Retorna lista de { slug, html_path, png_path, captured_at }.
    """
    section_dir = Path(section_dir)
    out_dir = Path(out_dir) if out_dir else section_dir / 'screenshots_qa'
    out_dir.mkdir(parents=True, exist_ok=True)

    pattern = '**/*.html' if recursive else '*.html'
    htmls = sorted(
        h for h in section_dir.glob(pattern)
        if h.name not in exclude_names
        and not h.name.startswith(exclude_prefixes)
    )
    if not htmls:
        print(f'  [playwright-granular] Nenhum HTML encontrado em {section_dir}')
        return []

    results: list[dict] = []
    wait_js = (
        "Array.from(document.images).every("
        "img => img.complete && img.naturalHeight > 0)"
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': viewport_width, 'height': 800})

        for html_path in htmls:
            slug = html_path.stem
            png_path = out_dir / f'{slug}.png'
            try:
                page.goto(f'file:///{html_path.as_posix()}', timeout=15_000)
                try:
                    page.wait_for_function(wait_js, timeout=15_000)
                except Exception:
                    pass  # segue mesmo se alguma imagem individual não carregar
                page.wait_for_timeout(150)

                # Fix de paint-culling: força o viewport a cobrir a página
                # inteira antes do screenshot do elemento. As páginas
                # granulares usam layout de duas colunas
                # (`.sidebar` + `.main-wrap{overflow:auto;height:100vh}`),
                # então `document.documentElement.scrollHeight` NÃO reflete
                # o conteúdo real — ele é auto-referente ao viewport (body é
                # flex-row com filhos limitados a 100vh, então html/body
                # "scrollHeight" ~= altura do viewport atual, não a altura
                # do conteúdo). É preciso medir o container com scroll
                # interno de verdade (`.main-wrap`).
                height = page.evaluate(
                    "(() => {"
                    "  const w = document.querySelector('.main-wrap');"
                    "  return Math.max("
                    "    w ? w.scrollHeight : 0,"
                    "    document.documentElement.scrollHeight,"
                    "  );"
                    "})()"
                )
                page.set_viewport_size({
                    'width': viewport_width,
                    'height': min(int(height) + 100, 32000),
                })
                page.wait_for_timeout(150)

                target = page.locator(selector) if selector else page
                target.screenshot(path=str(png_path))
                results.append({
                    'slug':        slug,
                    'html_path':   str(html_path),
                    'png_path':    str(png_path),
                    'captured_at': datetime.now().isoformat(timespec='seconds'),
                })
                print(f'  [playwright-granular] {slug:<30} -> {png_path.name}')
            except Exception as exc:
                print(f'  [playwright-granular] ERRO {slug}: {exc}')

        browser.close()

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Captura por linha (per-row screenshot para comparação granular)
# ─────────────────────────────────────────────────────────────────────────────

def capture_rows_per_item(
    html_path: Path | str,
    out_dir: Path | str,
    max_rows: int = 50,
) -> list[dict]:
    """
    Captura screenshot de cada linha da tabela individualmente.
    Útil para análise granular por pilar/viga no loop.

    Retorna lista de { row_index, label, png_path }.
    """
    html_path = Path(html_path)
    out_dir   = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': _VIEWPORT_W, 'height': 200})
        page.goto(f'file:///{html_path.as_posix()}', wait_until='networkidle', timeout=15_000)
        page.wait_for_timeout(300)

        rows = page.locator('tbody tr')
        total = min(rows.count(), max_rows)

        for i in range(total):
            row = rows.nth(i)
            # Etiqueta = primeira célula (Nome/Viga)
            try:
                label_raw = row.locator('td').first.inner_text().strip()
                label = re.sub(r'[^\w\-]', '_', label_raw)[:40] or f'row{i}'
            except Exception:
                label = f'row{i}'

            png_path = out_dir / f'{i:03d}_{label}.png'
            try:
                row.screenshot(path=str(png_path))
                results.append({'row_index': i, 'label': label_raw, 'png_path': str(png_path)})
            except Exception as exc:
                print(f'  [playwright-row] ERRO linha {i}: {exc}')

        browser.close()

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Relatório de loop
# ─────────────────────────────────────────────────────────────────────────────

def build_loop_report(
    obra: str,
    pav: str,
    html_dir: Path,
    screenshots: list[dict],
    estado_path: Path | None = None,
    iteration: int = 0,
) -> dict:
    """
    Monta o relatório JSON do ciclo de loop.
    Salvo em loop_reports/{obra}/{pav}_{ts}.json
    """
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report = {
        'iteration':     iteration,
        'obra':          obra,
        'pavimento':     pav,
        'html_dir':      str(html_dir),
        'estado_path':   str(estado_path) if estado_path else None,
        'gerado_em':     ts,
        'screenshots':   screenshots,
        'total_items':   sum(s.get('rows_count', 0) for s in screenshots),
        'abas_geradas':  len(screenshots),
    }
    out_dir = _LOOPS_DIR / obra
    out_dir.mkdir(parents=True, exist_ok=True)
    pav_slug = re.sub(r'[^\w\-]', '_', pav)[:60]
    report_path = out_dir / f'{pav_slug}_{ts}.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n-> Loop report: {report_path}')
    return report


# ─────────────────────────────────────────────────────────────────────────────
# Ciclo completo: gerar HTMLs -> capturar -> relatório
# ─────────────────────────────────────────────────────────────────────────────

def run_loop_cycle(
    obra: str,
    pav: str,
    iteration: int = 0,
    capture_rows: bool = False,
    slugs_filter: list[str] | None = None,
) -> dict:
    """
    Ciclo completo:
      1. Localiza estado JSON mais recente
      2. Gera HTMLs via gerar_html_preficha_headless
      3. Captura screenshots via Playwright
      4. Gera loop_report JSON
      5. Retorna report (paths de PNGs prontos para leitura por visão)

    Args:
        obra:           nome da obra (ex: 'Obra_TREINO_1')
        pav:            pavimento  (ex: '13_PAV')
        iteration:      índice do ciclo (para rastreamento)
        capture_rows:   se True, captura também screenshot por linha
        slugs_filter:   lista de slugs a capturar (None = todos)
    """
    sys.path.insert(0, str(_REPO_ROOT))
    from scripts.arete.gerar_html_preficha_headless import (
        generate_html_fichas, _find_estado,
    )

    # 1. Localiza estado
    estados = _find_estado(obra, pav)
    if not estados:
        raise FileNotFoundError(
            f'Estado não encontrado para {obra}/{pav}. '
            f'Abra o PreValidationDialog e clique "Gerar todos HTMLs" ao menos uma vez.'
        )
    estado_path = estados[0]
    with open(estado_path, encoding='utf-8') as f:
        state = json.load(f)

    # 2. Gera HTMLs
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    pav_slug = re.sub(r'[^\w\-]', '_', pav)[:60]
    html_dir = _HTML_BASE / obra / f'{pav_slug}_{ts}'
    generate_html_fichas(state, html_dir)

    # 3. Captura screenshots full-page
    screenshots = capture_html_pages(html_dir, slugs=slugs_filter)

    # 3b. Captura por linha (opcional)
    if capture_rows and screenshots:
        for s in screenshots:
            rows_dir = Path(s['png_path']).parent / 'rows' / s['slug']
            rows = capture_rows_per_item(s['html_path'], rows_dir)
            s['row_screenshots'] = rows

    # 4. Relatório
    report = build_loop_report(obra, pav, html_dir, screenshots, estado_path, iteration)
    return report


# ─────────────────────────────────────────────────────────────────────────────
# Leitura de screenshots para visão do agente
# ─────────────────────────────────────────────────────────────────────────────

def list_latest_screenshots(obra: str, pav: str) -> list[Path]:
    """
    Retorna lista de PNGs da geração mais recente de loop para a obra/pav.
    Pronto para passar ao Read tool (leitura de imagem pelo agente).
    """
    pav_slug = re.sub(r'[^\w\-]', '_', pav)[:60]
    candidates = sorted(
        (_HTML_BASE / obra).glob(f'{pav_slug}_*/screenshots/*.png'),
        reverse=True,
    )
    # Agrupa por geração mais recente (primeiro timestamp)
    if not candidates:
        return []
    latest_dir = candidates[0].parent
    return sorted(latest_dir.glob('*.png'))


def print_vision_summary(report: dict) -> None:
    """Imprime sumário com paths de PNGs para leitura de visão."""
    print('\n' + '=' * 60)
    print(f'LOOP #{report["iteration"]} — {report["obra"]} / {report["pavimento"]}')
    print(f'HTMLs em: {report["html_dir"]}')
    print(f'Screenshots prontos para interpretacao:')
    for s in report['screenshots']:
        print(f'  {s["slug"]:<30} -> {s["png_path"]}')
    print('=' * 60)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description='Loop headless: gera HTMLs + captura screenshots via Playwright'
    )
    ap.add_argument('--obra',      required=False, help='Nome da obra')
    ap.add_argument('--pav',       required=False, help='Pavimento')
    ap.add_argument('--html_dir',  required=False, help='Diretório HTML já gerado (pula geração)')
    ap.add_argument('--iteration', type=int, default=0, help='Índice do ciclo')
    ap.add_argument('--rows',      action='store_true', help='Capturar também por linha')
    ap.add_argument('--slugs',     nargs='*', help='Filtrar slugs (ex: pilares visao_cortes)')
    ap.add_argument(
        '--granular-dir', required=False,
        help=(
            'Diretório de páginas granulares por item (ex: .../lajes, '
            '.../fundos_viga, .../pilares) — usa capture_granular_item_pages '
            'com o fix de paint-culling em vez de capture_html_pages'
        ),
    )
    ap.add_argument(
        '--granular-out', required=False,
        help='Diretório de saída dos PNGs granulares (default: <dir>/screenshots_qa)',
    )
    args = ap.parse_args()

    if args.granular_dir:
        results = capture_granular_item_pages(
            Path(args.granular_dir), out_dir=args.granular_out,
        )
        print_vision_summary({
            'iteration': args.iteration,
            'obra': args.obra or '?',
            'pavimento': args.pav or '?',
            'html_dir': args.granular_dir,
            'screenshots': [
                {'slug': r['slug'], 'png_path': r['png_path']} for r in results
            ],
        })
    elif args.html_dir:
        # Apenas captura screenshots de diretório HTML existente
        html_dir = Path(args.html_dir)
        screenshots = capture_html_pages(html_dir, slugs=args.slugs)
        print_vision_summary({
            'iteration': args.iteration,
            'obra': args.obra or '?',
            'pavimento': args.pav or '?',
            'html_dir': str(html_dir),
            'screenshots': screenshots,
        })
    elif args.obra and args.pav:
        report = run_loop_cycle(
            obra=args.obra,
            pav=args.pav,
            iteration=args.iteration,
            capture_rows=args.rows,
            slugs_filter=args.slugs,
        )
        print_vision_summary(report)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
