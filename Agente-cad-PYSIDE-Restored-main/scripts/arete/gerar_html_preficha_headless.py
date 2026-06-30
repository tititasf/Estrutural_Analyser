#!/usr/bin/env python
"""
Gerador headless de fichas HTML de pré-análise de pilares/vigas/lajes.

Lê o snapshot de estado salvo automaticamente pelo PreValidationDialog
(scripts/arete/html_fichas/{obra}/estado_{pav}.json) e regenera todos
os HTMLs sem interação humana.

Uso:
    python gerar_html_preficha_headless.py --obra Obra_TREINO_1 --pav 13_PAV
    python gerar_html_preficha_headless.py --estado /path/to/estado_13_PAV.json
    python gerar_html_preficha_headless.py --obra Obra_TREINO_1  # todos os pavimentos

Saída:  scripts/arete/html_fichas/{obra}/{pav}_{ts}/
"""
from __future__ import annotations

import argparse
import base64
import glob
import html as _html
import io
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ── Caminhos base ─────────────────────────────────────────────────────────────
_SCRIPT_DIR    = Path(__file__).resolve().parent
_REPO_ROOT     = _SCRIPT_DIR.parent.parent
_HTML_BASE     = _SCRIPT_DIR / 'html_fichas'
_RELATORIOS    = _SCRIPT_DIR / 'relatorios'
_DADOS_OBRAS   = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
_DB_DEFAULT    = 'D:/Agente-cad-PYSIDE/project_data.vision'

# ── CSS compartilhado ─────────────────────────────────────────────────────────
_CSS = (
    'body{background:#1a1a1a;color:#c8c8c8;font:11px monospace;margin:16px}'
    'h1{color:#7eb8f7;font-size:16px} .meta,.muted{color:#777}'
    'table{border-collapse:collapse;width:100%}'
    'th{position:sticky;top:0;background:#2a2a2a;color:#4fc3a1;padding:6px;white-space:nowrap}'
    'td{padding:5px 7px;border-bottom:1px solid #303030;vertical-align:top;white-space:pre-wrap}'
    '.img-geo{width:240px;height:140px;object-fit:contain;background:#111}'
    '.img-n4{width:440px;height:260px;object-fit:contain;background:#111}'
    '.img-n2{width:440px;height:260px;object-fit:contain;background:#111}'
    'tr:hover td{background:#222}'
    'table.n2{font-size:9px;border-collapse:collapse}'
    'table.n2 td{padding:1px 4px;border:none}'
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers de imagem
# ─────────────────────────────────────────────────────────────────────────────

def _file_b64(path: str | Path) -> str:
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode('ascii')
    except Exception:
        return ''


def _find_n4_png(class_prefix: str, item_name: str) -> str:
    """Render N4 mais recente: relatorios/{ts}/png/{PREFIX}_{item}.png"""
    pattern = str(_RELATORIOS / '*' / 'png' / f'{class_prefix}_{item_name}.png')
    matches = sorted(glob.glob(pattern), reverse=True)
    return _file_b64(matches[0]) if matches else ''


def _find_n2_png(obra: str, subfolder: str, item_name: str) -> str:
    path = _DADOS_OBRAS / obra / 'Fase-6_Execucao_CAD' / subfolder / f'{item_name}_n2.png'
    return _file_b64(path)


def _render_polygon_png(points: list) -> str:
    """Renderiza polígono como PNG base64 via matplotlib (sem display)."""
    if not points or len(points) < 2:
        return ''
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]

        fig, ax = plt.subplots(figsize=(2.4, 1.4))
        fig.patch.set_facecolor('#111111')
        ax.set_facecolor('#1a1a1a')
        ax.plot(xs + [xs[0]], ys + [ys[0]], color='#4fc3a1', linewidth=1.5)
        ax.fill(xs, ys, alpha=0.18, color='#4fc3a1')
        ax.set_aspect('equal')
        ax.axis('off')
        ax.margins(0.12)

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=90, bbox_inches='tight',
                    facecolor='#111111', edgecolor='none')
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''


# ─────────────────────────────────────────────────────────────────────────────
# Ficha N2 do DB
# ─────────────────────────────────────────────────────────────────────────────

def _n2_ficha_html(db_path: str, obra: str, classe: str, elemento_id: str) -> str:
    if not db_path or not os.path.isfile(db_path):
        return '<span style="color:#555">sem DB</span>'
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT campos_json FROM reverse_eng_fichas "
            "WHERE classe=? AND elemento_id=? AND obra_name=? "
            "ORDER BY id DESC LIMIT 1",
            (classe, elemento_id, obra),
        ).fetchone()
        conn.close()
        if not row:
            return '<span style="color:#555">—</span>'
        data = json.loads(row[0])
        skip = {'_er_meta', 'modo_distribuicao', 'pavimento', 'numero', 'nome'}
        entries = []
        for k, v in data.items():
            if k in skip:
                continue
            if v in (0, 0.0, '', None) or (isinstance(v, list) and not v):
                continue
            entries.append(
                f'<tr><td style="color:#7eb8f7;white-space:nowrap">'
                f'{_html.escape(str(k))}</td>'
                f'<td>{_html.escape(str(v))}</td></tr>'
            )
        if not entries:
            return '<span style="color:#555">sem dados</span>'
        return f'<table class="n2">{"".join(entries)}</table>'
    except Exception as exc:
        return f'<span style="color:#555">erro: {_html.escape(str(exc))}</span>'


# ─────────────────────────────────────────────────────────────────────────────
# Helpers HTML
# ─────────────────────────────────────────────────────────────────────────────

def _img_cell(b64: str, css_class: str = 'img-n4') -> str:
    if b64:
        return f'<td><img class="{css_class}" src="data:image/png;base64,{b64}"></td>'
    return '<td><span class="muted">—</span></td>'


def _text_cell(val) -> str:
    return f'<td>{_html.escape(str(val) if val is not None else "")}</td>'


def _html_cell(content: str) -> str:
    return f'<td style="max-width:340px;overflow:auto">{content}</td>'


def _build_document(title: str, obra: str, pav: str, headers: list[str],
                    th_extra: str, body_rows: list[str]) -> str:
    th_row = ''.join(f'<th>{_html.escape(h)}</th>' for h in headers) + th_extra
    return (
        f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        f'<title>{_html.escape(title)}</title>'
        f'<style>{_CSS}</style></head>'
        f'<body><h1>{_html.escape(title)}</h1>'
        f'<div class="meta">Obra: <b>{_html.escape(obra)}</b> | '
        f'Pavimento: <b>{_html.escape(pav)}</b> | '
        f'Gerado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | '
        f'Registros: {len(body_rows)}</div>'
        f'<table><thead><tr>{th_row}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table></body></html>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Geradores por seção
# ─────────────────────────────────────────────────────────────────────────────

def _pilar_formato(points: list) -> str:
    if not points or len(points) < 3:
        return '?'
    if len(points) == 4:
        return 'Retangular'
    return 'Especial'


def _gen_pilares(state: dict, db_path: str, especiais: bool = False) -> tuple[str, list[str]]:
    obra = state['obra']
    pav  = state['pavimento']
    title = f"Pré-ficha — {'Pilares Especiais' if especiais else 'Pilares'}"
    headers = ['Nome', 'Classif.', 'Formato', 'Nível', 'Lado A', 'Lado B', 'Lado C', 'Lado D', 'Atenção']
    th_extra = '<th>Foto N1</th><th>Foto N4</th><th>Ficha N2</th>'

    rows = []
    for p in state['pilares']:
        fmt = _pilar_formato(p.get('points') or [])
        if especiais != (fmt != 'Retangular'):
            continue
        data_cells = (
            _text_cell(p['name'])
            + _text_cell(p['classification'])
            + _text_cell(fmt)
            + _text_cell(p.get('nivel_str') or '—')
            + _text_cell(p.get('lado_A') or '')
            + _text_cell(p.get('lado_B') or '')
            + _text_cell(p.get('lado_C') or '')
            + _text_cell(p.get('lado_D') or '')
            + _text_cell(p.get('atencao') or '')
        )
        geo  = _render_polygon_png(p.get('points') or [])
        n4   = _find_n4_png('PIL', p['name'])
        n2h  = _n2_ficha_html(db_path, obra, 'PIL', p['name'])
        extra = _img_cell(geo, 'img-geo') + _img_cell(n4) + _html_cell(n2h)
        rows.append(f'<tr>{data_cells}{extra}</tr>')

    return _build_document(title, obra, pav, headers, th_extra, rows), rows


def _gen_cortes(state: dict) -> tuple[str, list[str]]:
    obra = state['obra']
    pav  = state['pavimento']
    title = 'Pré-ficha — Visão de Cortes'
    headers = ['Viga', 'Confiança', 'Laje A', 'Laje B', 'Altura', 'Status']
    th_extra = '<th>Foto</th>'

    rows = []
    for c in state['cortes']:
        data_cells = (
            _text_cell(c.get('beam_name') or '')
            + _text_cell(f"{c.get('conf_pct', 0)}%")
            + _text_cell(c.get('own_laje') or '—')
            + _text_cell(c.get('neigh_laje') or '—')
            + _text_cell(c.get('beam_h') or '—')
            + _text_cell(c.get('status') or '')
        )
        geo = _render_polygon_png(c.get('pts') or [])
        extra = _img_cell(geo, 'img-geo')
        rows.append(f'<tr>{data_cells}{extra}</tr>')

    return _build_document(title, obra, pav, headers, th_extra, rows), rows


_SEG_CLASS = {
    'fundo':           'FV',
    'lateral_a_para':  'LV',
    'lateral_b_para':  'LV',
    'lateral_a_passa': 'LV',
    'lateral_b_passa': 'LV',
}

_SEG_TITLES = {
    'fundo':           'Segmentos Fundos',
    'lateral_a_para':  'Segmentos Lateral A Para',
    'lateral_b_para':  'Segmentos Lateral B Para',
    'lateral_a_passa': 'Segmentos Lateral A Passa',
    'lateral_b_passa': 'Segmentos Lateral B Passa',
}


def _gen_segmento(state: dict, kind: str) -> tuple[str, list[str]]:
    obra = state['obra']
    pav  = state['pavimento']
    cls  = _SEG_CLASS.get(kind, 'LV')
    title = f"Pré-ficha — {_SEG_TITLES.get(kind, kind)}"
    th_extra = '<th>Foto N1</th><th>Foto N4</th><th>Foto N2</th>'

    if kind == 'fundo':
        headers = ['Viga', 'Segmento', 'Comprimento', 'Status', 'Atenção']
    else:
        headers = ['Viga', 'Segmento', 'Lado', 'Comportamento', 'Comprimento', 'Status', 'Atenção']

    rows = []
    for seg in state['segmentos'].get(kind, []):
        beam = seg.get('beam_name') or ''
        if kind == 'fundo':
            data_cells = (
                _text_cell(beam)
                + _text_cell(seg.get('segment_label') or '')
                + _text_cell(f"{seg.get('length', 0):.1f}")
                + _text_cell(seg.get('status') or '')
                + _text_cell(seg.get('atencao') or '')
            )
        else:
            data_cells = (
                _text_cell(beam)
                + _text_cell(seg.get('segment_label') or '')
                + _text_cell(seg.get('side') or '')
                + _text_cell(seg.get('behavior') or '')
                + _text_cell(f"{seg.get('length', 0):.1f}")
                + _text_cell(seg.get('status') or '')
                + _text_cell(seg.get('atencao') or '')
            )
        geo = _render_polygon_png(seg.get('points') or [])
        n4  = _find_n4_png(cls, beam)
        n2  = _find_n2_png(obra, f'comparacao_{cls.lower()}', beam)
        if not n2:
            n2 = _find_n2_png(obra, 'comparacao_lv', beam)
        extra = _img_cell(geo, 'img-geo') + _img_cell(n4) + _img_cell(n2, 'img-n2')
        rows.append(f'<tr>{data_cells}{extra}</tr>')

    return _build_document(title, obra, pav, headers, th_extra, rows), rows


# ─────────────────────────────────────────────────────────────────────────────
# Gerador principal
# ─────────────────────────────────────────────────────────────────────────────

def generate_html_fichas(state: dict, output_dir: str | Path) -> list[dict]:
    """
    Gera todos os HTMLs a partir do state dict e retorna lista de
    {'file': ..., 'title': ..., 'count': ...} para indexação.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = state.get('db_path') or _DB_DEFAULT
    obra    = state['obra']
    pav     = state['pavimento']

    generated: list[dict] = []

    def _save(slug: str, doc: str, rows: list) -> None:
        fpath = output_dir / f'preficha_{slug}.html'
        fpath.write_text(doc, encoding='utf-8')
        generated.append({'file': fpath.name, 'title': f'Pré-ficha — {slug}', 'count': len(rows)})
        print(f'  [{len(rows):3d} itens] {fpath.name}')

    print(f'\nGerando HTMLs: {obra} / {pav}')

    doc, rows = _gen_pilares(state, db_path, especiais=False)
    _save('pilares', doc, rows)
    doc, rows = _gen_pilares(state, db_path, especiais=True)
    _save('pilares_especiais', doc, rows)
    doc, rows = _gen_cortes(state)
    _save('visao_cortes', doc, rows)

    for kind in _SEG_TITLES:
        doc, rows = _gen_segmento(state, kind)
        _save(kind, doc, rows)

    # Índice
    li = ''.join(
        f'<li><a href="{_html.escape(g["file"])}">'
        f'Pré-ficha — {_html.escape(g["file"].replace("preficha_","").replace(".html",""))}'
        f'</a> — {g["count"]} item(s)</li>'
        for g in generated
    )
    index = (
        '<!DOCTYPE html><html lang="pt-BR"><meta charset="UTF-8">'
        f'<body style="background:#1a1a1a;color:#ccc;font:14px sans-serif">'
        f'<h2 style="color:#7eb8f7">Pré-fichas — {_html.escape(obra)} / {_html.escape(pav)}</h2>'
        f'<p style="color:#777">Gerado: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>'
        f'<ul>{li}</ul></body></html>'
    )
    (output_dir / 'index.html').write_text(index, encoding='utf-8')

    print(f'  indice: {output_dir / "index.html"}')
    print(f'{len(generated)} fichas salvas em: {output_dir}\n')
    return generated


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _find_estado(obra: str, pav: str | None) -> list[Path]:
    """Localiza arquivo(s) de estado para a obra/pav."""
    obra_dir = _HTML_BASE / obra
    if not obra_dir.is_dir():
        return []
    if pav:
        import re
        pav_slug = re.sub(r'[^\w\-]', '_', pav)[:60]
        p = obra_dir / f'estado_{pav_slug}.json'
        return [p] if p.is_file() else []
    return sorted(obra_dir.glob('estado_*.json'))


def main() -> None:
    ap = argparse.ArgumentParser(description='Gera fichas HTML de pré-análise headless')
    ap.add_argument('--obra',   help='Nome da obra (ex: Obra_TREINO_1)')
    ap.add_argument('--pav',    help='Pavimento (ex: 13_PAV). Omitir = todos')
    ap.add_argument('--estado', help='Caminho direto ao estado JSON')
    args = ap.parse_args()

    estados: list[Path] = []
    if args.estado:
        estados = [Path(args.estado)]
    elif args.obra:
        estados = _find_estado(args.obra, args.pav)
        if not estados:
            sys.exit(f'Nenhum estado encontrado em {_HTML_BASE / args.obra}. '
                     f'Abra o PreValidationDialog na app e clique "Gerar todos HTMLs" '
                     f'ao menos uma vez para criar o snapshot inicial.')
    else:
        ap.print_help()
        sys.exit(1)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    for estado_path in estados:
        with open(estado_path, encoding='utf-8') as f:
            state = json.load(f)
        obra = state['obra']
        pav  = state['pavimento']
        import re
        pav_slug = re.sub(r'[^\w\-]', '_', pav)[:60]
        out_dir  = _HTML_BASE / obra / f'{pav_slug}_{ts}'
        generate_html_fichas(state, out_dir)


if __name__ == '__main__':
    main()
