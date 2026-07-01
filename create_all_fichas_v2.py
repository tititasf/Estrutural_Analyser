#!/usr/bin/env python3
"""
create_all_fichas_v2.py
Gera fichas HTML individuais para LV, FV, Lajes, Cortes e Pilares
a partir do estado_13_PAV.json. Estrutura granular de pastas por seção.
"""

import json
import os
from pathlib import Path
from html import escape

ESTADO_JSON = Path('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/estado_13_PAV.json')
OUTPUT_DIR  = Path('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_20260630_203509')

# ─── CSS compartilhado ─────────────────────────────────────────────────────────
SHARED_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body.layout-body { display: flex; height: 100vh; overflow: hidden; background: #111; color: #ccc; font-family: 'Segoe UI', sans-serif; font-size: 11px; line-height: 1.5; }
body.page-body-only { background: #111; color: #ccc; font-family: 'Segoe UI', sans-serif; font-size: 11px; line-height: 1.5; }
.sidebar { width: 185px; min-width: 140px; overflow-y: auto; background: #0d0d0d; border-right: 1px solid #222; flex-shrink: 0; height: 100vh; }
.sidebar-head { padding: 8px 10px 6px; background: #0a0a0a; border-bottom: 1px solid #222; }
.sidebar-head h3 { color: #4fc3a1; font-size: 10px; margin: 0 0 4px; letter-spacing: 0.04em; text-transform: uppercase; }
.sidebar-head a { color: #4a7aaa; font-size: 9px; text-decoration: none; display: block; margin-top: 3px; }
.sidebar-head a:hover { color: #7eb8f7; }
.sidebar-head .back-link { color: #555; font-size: 9px; text-decoration: none; display: block; margin-bottom: 4px; }
.sidebar-head .back-link:hover { color: #aaa; }
.sidebar-list { list-style: none; padding: 4px 0; margin: 0; }
.sidebar-list li a { display: block; padding: 3px 10px; color: #666; text-decoration: none; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sidebar-list li.active a { color: #f0b840; background: #1a1600; font-weight: bold; }
.sidebar-list li a:hover { background: #181818; color: #bbb; }
.sidebar-grp { font-size: 8px; color: #3a3a3a; padding: 8px 8px 2px; text-transform: uppercase; letter-spacing: 1px; border-top: 1px solid #1a1a1a; margin-top: 4px; }
.main { flex: 1; overflow-y: auto; height: 100vh; }
.nav-bar { display: flex; align-items: center; gap: 10px; padding: 5px 14px; background: #0d0d0d; border-bottom: 1px solid #1e1e1e; position: sticky; top: 0; z-index: 5; }
.nav-a { color: #7eb8f7; text-decoration: none; font-size: 10px; padding: 2px 9px; border: 1px solid #2a3a5a; border-radius: 3px; white-space: nowrap; }
.nav-a:hover { background: #1a2030; }
.nav-a.disabled { color: #333; border-color: #222; pointer-events: none; }
.nav-pos { color: #555; font-size: 10px; flex: 1; text-align: center; }
.page-body { padding: 14px 20px; max-width: 960px; }
.page-full { max-width: 960px; margin: 0 auto; padding: 24px 20px; }
h1 { color: #4fc3a1; font-size: 16px; margin-bottom: 12px; border-bottom: 2px solid #222; padding-bottom: 7px; }
h2 { color: #7eb8f7; font-size: 12px; margin: 18px 0 7px; border-left: 3px solid #7eb8f7; padding-left: 7px; }
h3 { color: #f0b840; font-size: 11px; margin: 12px 0 5px; }
.sec { border: 1px solid #1e1e1e; border-radius: 4px; margin: 10px 0; overflow: hidden; }
.sec-title { background: #181818; color: #666; font-size: 9px; padding: 4px 10px; font-weight: bold; letter-spacing: 0.08em; text-transform: uppercase; }
.sec-body { padding: 8px 12px; }
.kv { display: flex; align-items: baseline; gap: 8px; padding: 4px 0; border-bottom: 1px solid #171717; }
.kv:last-child { border-bottom: none; }
.kv-key { color: #555; font-size: 10px; min-width: 130px; flex-shrink: 0; }
.kv-val { color: #bbb; font-size: 11px; white-space: pre-wrap; }
.kv-val.accent  { color: #4fc3a1; font-weight: bold; }
.kv-val.accent2 { color: #7eb8f7; font-weight: bold; }
.kv-val.warn    { color: #f0b840; }
.kv-val.muted   { color: #3a3a3a; font-style: italic; }
.tag { display: inline-block; padding: 1px 7px; border-radius: 3px; font-size: 10px; font-weight: bold; margin-right: 3px; }
.tag-A    { background: #102010; color: #4fc3a1; border: 1px solid #1e3a1e; }
.tag-B    { background: #101228; color: #7eb8f7; border: 1px solid #1e2448; }
.tag-C    { background: #281028; color: #c47ef7; border: 1px solid #3a1e3a; }
.tag-D    { background: #281a08; color: #f0b840; border: 1px solid #3a2a08; }
.tag-Para   { background: #0e1a28; color: #7eb8f7; }
.tag-Passa  { background: #1e0e28; color: #c47ef7; }
.tag-Fundo  { background: #1a0e1e; color: #e090f0; }
.tag-valid  { background: #081808; color: #4fc3a1; }
.tag-warn   { background: #1e1400; color: #f0b840; }
.tag-inv    { background: #281008; color: #e06040; }
.stat-ok    { color: #4fc3a1; }
.stat-warn  { color: #f0b840; }
.link-guide { display: inline-block; margin: 8px 0 4px; color: #4a7aaa; text-decoration: none; font-size: 10px; border: 1px solid #2a3a5a; border-radius: 3px; padding: 3px 9px; }
.link-guide:hover { background: #1a2030; color: #7eb8f7; }
.info-box { background: #131313; border: 1px solid #1e1e1e; border-radius: 4px; padding: 8px 12px; color: #777; font-size: 10px; margin: 8px 0; line-height: 1.6; }
.info-box b { color: #9ab8c8; }
table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 10px; }
th { background: #161616; color: #4fc3a1; padding: 5px 8px; text-align: left; border-bottom: 1px solid #2a2a2a; font-size: 9px; letter-spacing: 0.05em; text-transform: uppercase; white-space: nowrap; }
td { padding: 4px 8px; border-bottom: 1px solid #1a1a1a; color: #aaa; vertical-align: top; }
tr:hover td { background: #141414; }
td a { color: #4a7aaa; text-decoration: none; font-size: 10px; }
td a:hover { color: #7eb8f7; }
.intro { background: #141414; border: 1px solid #1e1e1e; border-radius: 5px; padding: 10px 14px; margin-bottom: 16px; color: #888; font-size: 11px; line-height: 1.7; }
.intro b { color: #4fc3a1; }
a.back { color: #555; text-decoration: none; font-size: 10px; display: inline-block; margin-bottom: 14px; }
a.back:hover { color: #aaa; }
code { background: #1a1a1a; color: #e08060; padding: 1px 4px; border-radius: 2px; font-size: 10px; font-family: monospace; }
.badge { display: inline-flex; align-items: center; gap: 6px; background: #181818; border: 1px solid #2a2a2a; border-radius: 4px; padding: 5px 10px; font-size: 11px; }
.badge .lbl { color: #555; font-size: 9px; text-transform: uppercase; letter-spacing: 0.06em; }
.badge .val { color: #bbb; font-weight: bold; }
"""

# ─── helpers ───────────────────────────────────────────────────────────────────

def e(s):
    return escape(str(s) if s is not None else '')

def tag(label, css_class=None):
    cls = css_class or f'tag-{label}'
    return f'<span class="tag {e(cls)}">{e(label)}</span>'

def kv(key, val, cls=''):
    cls_attr = f' {cls}' if cls else ''
    val_str = val if val not in (None, '', '—') else '<span class="muted">—</span>'
    return f'<div class="kv"><span class="kv-key">{e(key)}</span><span class="kv-val{cls_attr}">{val_str}</span></div>'

def kv_raw(key, val_html):
    return f'<div class="kv"><span class="kv-key">{e(key)}</span><span class="kv-val">{val_html}</span></div>'

def page_head(title, extra_css=''):
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>{e(title)}</title>
<style>{SHARED_CSS}{extra_css}</style>
</head>
"""

def _fmt_cm(val, decimals=1):
    """Converte valor para string cm, aceita '19/55', 19.0, None, etc."""
    if val in (None, '', '—'):
        return '—'
    try:
        return f'{float(val):.{decimals}f} cm'
    except (ValueError, TypeError):
        return str(val)

def sidebar_html(items, active_idx, head_title, guide_rel, back_rel='../../index.html'):
    """items: list of (slug, label, rel_href)"""
    items_html = ''
    for i, (slug, label, href) in enumerate(items):
        active = ' class="active"' if i == active_idx else ''
        items_html += f'<li{active}><a href="{e(href)}" title="{e(label)}">{e(label)}</a></li>\n'
    return f"""<nav class="sidebar">
  <div class="sidebar-head">
    <a class="back-link" href="{e(back_rel)}">← Voltar ao índice</a>
    <h3>{e(head_title)}</h3>
    <a href="{e(guide_rel)}">📖 Guia de Interpretação</a>
  </div>
  <ul class="sidebar-list">
{items_html}  </ul>
</nav>"""

def navbar_html(prev_href, next_href, pos_str):
    prev = f'<a class="nav-a" href="{e(prev_href)}">&#8592; anterior</a>' if prev_href else '<span class="nav-a disabled">&#8592;</span>'
    nxt  = f'<a class="nav-a" href="{e(next_href)}">próximo &#8594;</a>' if next_href else '<span class="nav-a disabled">&#8594;</span>'
    return f'<div class="nav-bar">{prev}<span class="nav-pos">{e(pos_str)}</span>{nxt}</div>'

# ─── LV Individual Ficha ───────────────────────────────────────────────────────

def gen_lv_ficha(seg, idx, all_segs, kind, subfolder, title, guide_rel):
    slug = f'{seg["beam_name"]}_{seg["segment_label"]}'
    prev_href = f'{all_segs[idx-1]["_slug"]}.html' if idx > 0 else None
    next_href = f'{all_segs[idx+1]["_slug"]}.html' if idx < len(all_segs)-1 else None
    pos = f'{idx+1} / {len(all_segs)} — {seg["beam_name"]} · seg.{seg["segment_label"]}'

    sidebar_items = [(s['_slug'], f'{s["beam_name"]}·{s["segment_label"]}', f'{s["_slug"]}.html') for s in all_segs]
    sb = sidebar_html(sidebar_items, idx, title, guide_rel, back_rel='../../index.html')
    nb = navbar_html(prev_href, next_href, pos)

    side  = e(seg.get('side') or '—')
    beh   = e(seg.get('behavior') or '—')
    length = seg.get('length')
    width  = seg.get('width')
    status = seg.get('status') or 'valid'
    atencao = seg.get('atencao') or ''

    length_str = _fmt_cm(length)
    width_str  = _fmt_cm(width)

    side_tag  = f'<span class="tag tag-{side}">{side}</span>'  if side != '—' else '—'
    beh_tag   = f'<span class="tag tag-{beh}">{beh}</span>'   if beh  != '—' else '—'
    stat_cls  = 'stat-ok' if status == 'valid' else 'stat-warn'

    interp_text = {
        'Para':  'Segmento no <b>extremo</b> da viga — encosta em pilar ou parede. Apenas um lado tem espaço para laje.',
        'Passa': 'Segmento <b>interior</b> da viga — a viga continua dos dois lados. Laje pode existir de ambos os lados.',
        'Fundo': 'Face <b>inferior (sofito)</b> da viga. Verificar laje do pavimento inferior alinhada ao fundo.',
    }.get(seg.get('behavior',''), '')

    interp_side_text = {
        'A': 'Lado <b>A = esquerdo</b> olhando de C em direção a D.',
        'B': 'Lado <b>B = direito</b> olhando de C em direção a D.',
    }.get(seg.get('side',''), '')

    aten_block = ''
    if atencao:
        aten_block = f'<div class="sec"><div class="sec-title">Atenção</div><div class="sec-body"><p class="stat-warn">{e(atencao)}</p></div></div>'

    html = page_head(f'LV — {seg["beam_name"]} · {seg["segment_label"]} — {side}-{beh}')
    html += f'<body class="layout-body">\n<div style="display:flex;height:100vh;overflow:hidden;">\n{sb}\n<div class="main">\n{nb}\n<div class="page-body">'
    html += f'<h1>{e(seg["beam_name"])} · seg.{e(seg["segment_label"])} &nbsp;{side_tag} {beh_tag}</h1>'
    html += f'<div class="sec"><div class="sec-title">Dados do Segmento</div><div class="sec-body">'
    html += kv('Viga', seg['beam_name'], 'accent')
    html += kv('Segmento', seg['segment_label'])
    html += kv_raw('Lado', side_tag)
    html += kv_raw('Comportamento', beh_tag)
    html += kv('Comprimento', length_str)
    html += kv('Largura', width_str)
    html += kv_raw('Status', f'<span class="{stat_cls}">{e(status)}</span>')
    html += '</div></div>'
    html += f'<div class="sec"><div class="sec-title">Interpretação</div><div class="sec-body">'
    html += f'<div class="info-box"><b>Comportamento:</b> {interp_text}<br><b>Lateral:</b> {interp_side_text}</div>'
    html += f'<a class="link-guide" href="{e(guide_rel)}">📖 Guia Laterais A/B e Para/Passa</a>'
    html += '</div></div>'
    if aten_block:
        html += aten_block
    html += '</div></div></div>\n</body></html>'
    return slug, html

# ─── FV Individual Ficha ───────────────────────────────────────────────────────

def gen_fv_ficha(seg, idx, all_segs, guide_rel):
    slug = f'{seg["beam_name"]}_{seg["segment_label"]}'
    prev_href = f'{all_segs[idx-1]["_slug"]}.html' if idx > 0 else None
    next_href = f'{all_segs[idx+1]["_slug"]}.html' if idx < len(all_segs)-1 else None
    pos = f'{idx+1} / {len(all_segs)} — FV {seg["beam_name"]} · {seg["segment_label"]}'

    sidebar_items = [(s['_slug'], f'{s["beam_name"]}·{s["segment_label"]}', f'{s["_slug"]}.html') for s in all_segs]
    sb = sidebar_html(sidebar_items, idx, 'Fundos de Viga', guide_rel, back_rel='../index.html')
    nb = navbar_html(prev_href, next_href, pos)

    length = seg.get('length')
    width  = seg.get('width')
    status = seg.get('status') or 'valid'
    atencao = seg.get('atencao') or ''
    length_str = _fmt_cm(length)
    width_str  = _fmt_cm(width)
    stat_cls = 'stat-ok' if status == 'valid' else 'stat-warn'

    aten_block = ''
    if atencao:
        aten_block = f'<div class="sec"><div class="sec-title">Atenção</div><div class="sec-body"><p class="stat-warn">{e(atencao)}</p></div></div>'

    html = page_head(f'FV — {seg["beam_name"]} · {seg["segment_label"]}')
    html += f'<body class="layout-body">\n<div style="display:flex;height:100vh;overflow:hidden;">\n{sb}\n<div class="main">\n{nb}\n<div class="page-body">'
    html += f'<h1>FV — {e(seg["beam_name"])} · seg.{e(seg["segment_label"])} &nbsp;<span class="tag tag-Fundo">Fundo</span></h1>'
    html += f'<div class="sec"><div class="sec-title">Dados do Fundo de Viga</div><div class="sec-body">'
    html += kv('Viga', seg['beam_name'], 'accent')
    html += kv('Segmento', seg['segment_label'])
    html += kv('Comprimento', length_str)
    html += kv('Largura', width_str)
    html += kv_raw('Status', f'<span class="{stat_cls}">{e(status)}</span>')
    html += '</div></div>'
    html += f'<div class="sec"><div class="sec-title">Interpretação</div><div class="sec-body">'
    html += '<div class="info-box"><b>Fundo de Viga (FV):</b> Face inferior (sofito) da viga. Verificar se há laje do pavimento inferior alinhada ao nível do fundo. Se o fundo estiver exposto (borda livre), o campo <code>laje_name</code> fica nulo.</div>'
    html += f'<a class="link-guide" href="{e(guide_rel)}">📖 Guia de Fundos de Viga</a>'
    html += '</div></div>'
    if aten_block:
        html += aten_block
    html += '</div></div></div>\n</body></html>'
    return slug, html

# ─── Lajes Ficha ───────────────────────────────────────────────────────────────

def gen_laje_ficha(slab, idx, all_slabs, guide_rel):
    slug = slab['name']
    prev_href = f'{all_slabs[idx-1]["name"]}.html' if idx > 0 else None
    next_href = f'{all_slabs[idx+1]["name"]}.html' if idx < len(all_slabs)-1 else None
    pos = f'{idx+1} / {len(all_slabs)} — {slab["name"]}'

    sidebar_items = [(s['name'], s['name'], f'{s["name"]}.html') for s in all_slabs]
    sb = sidebar_html(sidebar_items, idx, 'Lajes', guide_rel, back_rel='../index.html')
    nb = navbar_html(prev_href, next_href, pos)

    nivel  = slab.get('nivel')  or ''
    height = slab.get('height') or ''
    nivel_str  = _fmt_cm(nivel, 2)
    height_str = _fmt_cm(height, 0)

    html = page_head(f'Laje — {slab["name"]}')
    html += f'<body class="layout-body">\n<div style="display:flex;height:100vh;overflow:hidden;">\n{sb}\n<div class="main">\n{nb}\n<div class="page-body">'
    html += f'<h1>Laje {e(slab["name"])}</h1>'
    html += f'<div class="sec"><div class="sec-title">Dados da Laje</div><div class="sec-body">'
    html += kv('Nome', slab['name'], 'accent')
    html += kv('Nível topo', nivel_str)
    html += kv('Espessura', height_str)
    html += '</div></div>'
    html += f'<div class="sec"><div class="sec-title">Interpretação</div><div class="sec-body">'
    html += '<div class="info-box"><b>Laje:</b> Placa horizontal de concreto delimitada por vigas ou bordas livres. O campo <code>nivel</code> indica a cota superior (topo). Lajes do mesmo vão têm o mesmo nome — vigas que cruzam o pilar separam os vãos.</div>'
    html += f'<a class="link-guide" href="{e(guide_rel)}">📖 Guia de Lajes</a>'
    html += '</div></div>'
    html += '</div></div></div>\n</body></html>'
    return slug, html

# ─── Cortes Ficha ──────────────────────────────────────────────────────────────

def gen_corte_ficha(corte, idx, all_cortes, guide_rel):
    uid  = corte.get('uid', '')
    beam = corte.get('beam_name', '?')
    slug = f'{beam}_{uid[-6:] if len(uid) > 6 else uid}'.replace(' ', '_')
    prev_href = f'{all_cortes[idx-1]["_slug"]}.html' if idx > 0 else None
    next_href = f'{all_cortes[idx+1]["_slug"]}.html' if idx < len(all_cortes)-1 else None
    pos = f'{idx+1} / {len(all_cortes)} — {beam}'

    sidebar_items = [(c['_slug'], c.get('beam_name','?'), f'{c["_slug"]}.html') for c in all_cortes]
    sb = sidebar_html(sidebar_items, idx, 'Visão de Cortes', guide_rel, back_rel='../index.html')
    nb = navbar_html(prev_href, next_href, pos)

    conf    = corte.get('conf_pct', 0)
    own_l   = corte.get('own_laje', '—') or '—'
    neigh_l = corte.get('neigh_laje', '—') or '—'
    beam_h  = corte.get('beam_h', '—')
    status  = corte.get('status', '—')
    atencao = corte.get('atencao', '') or ''
    beam_h_str = _fmt_cm(beam_h)
    conf_cls = 'stat-ok' if int(conf) >= 70 else 'stat-warn'

    aten_block = ''
    if atencao:
        aten_block = f'<div class="sec"><div class="sec-title">Atenção</div><div class="sec-body"><p class="stat-warn">{e(atencao)}</p></div></div>'

    html = page_head(f'Corte — {beam}')
    html += f'<body class="layout-body">\n<div style="display:flex;height:100vh;overflow:hidden;">\n{sb}\n<div class="main">\n{nb}\n<div class="page-body">'
    html += f'<h1>Visão de Corte — {e(beam)}</h1>'
    html += f'<div class="sec"><div class="sec-title">Dados do Corte</div><div class="sec-body">'
    html += kv('Viga', beam, 'accent')
    html += kv('Confiança', f'{conf}%', 'accent2' if int(conf) >= 70 else 'warn')
    html += kv('Laje própria (own_laje)', own_l)
    html += kv('Laje vizinha (neigh_laje)', neigh_l)
    html += kv('Altura da viga', beam_h_str)
    html += kv('Status', status)
    html += '</div></div>'
    html += f'<div class="sec"><div class="sec-title">Interpretação</div><div class="sec-body">'
    html += '<div class="info-box"><b>Visão de Corte (VC):</b> Corte transversal detectado na lateral de uma viga. A <code>own_laje</code> é a laje do próprio vão da viga; <code>neigh_laje</code> é a laje do vão vizinho. A <code>confiança</code> indica a certeza da detecção automática.</div>'
    html += f'<a class="link-guide" href="{e(guide_rel)}">📖 Guia de Visão de Cortes</a>'
    html += '</div></div>'
    if aten_block:
        html += aten_block
    html += '</div></div></div>\n</body></html>'
    return slug, html

# ─── Index HTML ────────────────────────────────────────────────────────────────

def gen_index_html(title, subtitle, rows_html, guide_href, count, back_href='../index.html'):
    return f"""{page_head(title)}
<body class="page-body-only">
<div class="page-full">
  <a class="back" href="{e(back_href)}">&#8592; Índice geral</a>
  <h1>{e(title)}</h1>
  <div class="intro">
    <b>{e(subtitle)}</b> &nbsp;·&nbsp; {count} itens
    &nbsp;&nbsp;
    <a class="link-guide" href="{e(guide_href)}">📖 Guia de Interpretação</a>
  </div>
  {rows_html}
</div>
</body></html>"""

# ─── Section: LV ──────────────────────────────────────────────────────────────

def build_lv_section(estado):
    segs_map = {
        'lateral_a_para':  ('a_para',  'Lateral A-Para',  'LV-A-Para'),
        'lateral_b_para':  ('b_para',  'Lateral B-Para',  'LV-B-Para'),
        'lateral_a_passa': ('a_passa', 'Lateral A-Passa', 'LV-A-Passa'),
        'lateral_b_passa': ('b_passa', 'Lateral B-Passa', 'LV-B-Passa'),
    }
    base = OUTPUT_DIR / 'laterais_viga'
    guide_rel_from_sub = '../interpretacao_laterais.html'
    guide_rel_from_index = 'interpretacao_laterais.html'
    created = 0

    for kind, (subfolder, title, short) in segs_map.items():
        seg_data = estado['segmentos'].get(kind, [])
        folder = base / subfolder
        folder.mkdir(parents=True, exist_ok=True)
        # Assign slugs
        for s in seg_data:
            s['_slug'] = f'{s["beam_name"]}_{s["segment_label"]}'
        # Generate fichas
        for idx, seg in enumerate(seg_data):
            slug, html = gen_lv_ficha(seg, idx, seg_data, kind, subfolder, title, guide_rel_from_sub)
            (folder / f'{slug}.html').write_text(html, encoding='utf-8')
            created += 1
        # Generate index for this subfolder
        rows = '<table><tr><th>#</th><th>Viga</th><th>Seg.</th><th>Comprimento</th><th>Status</th><th>Link</th></tr>'
        for i, s in enumerate(seg_data):
            length = s.get('length')
            length_str = _fmt_cm(length)
            status = s.get('status') or 'valid'
            rows += f'<tr><td>{i+1}</td><td>{e(s["beam_name"])}</td><td>{e(s["segment_label"])}</td><td>{e(length_str)}</td><td>{e(status)}</td><td><a href="{e(s["_slug"])}.html">→</a></td></tr>'
        rows += '</table>'
        idx_html = gen_index_html(title, short, rows, '../interpretacao_laterais.html', len(seg_data), back_href='../../index.html')
        (folder / 'index.html').write_text(idx_html, encoding='utf-8')
        print(f'[LV] {subfolder}: {len(seg_data)} fichas')

    # Top-level laterais_viga/index.html
    lv_index = f"""{page_head("Laterais de Viga — Índice")}
<body class="page-body-only"><div class="page-full">
  <a class="back" href="../index.html">&#8592; Índice geral</a>
  <h1>Laterais de Viga (LV)</h1>
  <div class="intro">Quatro abas: A-Para, B-Para, A-Passa, B-Passa. &nbsp;<a class="link-guide" href="{guide_rel_from_index}">📖 Guia de Interpretação</a></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0;">
"""
    for kind, (subfolder, title, short) in segs_map.items():
        seg_data = estado['segmentos'].get(kind, [])
        lv_index += f'<div class="sec"><div class="sec-title">{e(title)}</div><div class="sec-body"><div class="kv"><span class="kv-key">Segmentos</span><span class="kv-val accent">{len(seg_data)}</span></div><a class="link-guide" href="{e(subfolder)}/index.html">Abrir →</a></div></div>'
    lv_index += '</div></div></body></html>'
    (base / 'index.html').write_text(lv_index, encoding='utf-8')
    return created

# ─── Section: FV ──────────────────────────────────────────────────────────────

def build_fv_section(estado):
    seg_data = estado['segmentos'].get('fundo', [])
    base = OUTPUT_DIR / 'fundos_viga'
    base.mkdir(parents=True, exist_ok=True)
    guide_rel = 'interpretacao_fundos.html'

    for s in seg_data:
        s['_slug'] = f'{s["beam_name"]}_{s["segment_label"]}'

    for idx, seg in enumerate(seg_data):
        slug, html = gen_fv_ficha(seg, idx, seg_data, guide_rel)
        (base / f'{slug}.html').write_text(html, encoding='utf-8')

    rows = '<table><tr><th>#</th><th>Viga</th><th>Seg.</th><th>Comprimento</th><th>Largura</th><th>Status</th><th>Link</th></tr>'
    for i, s in enumerate(seg_data):
        length = s.get('length')
        width  = s.get('width')
        length_str = _fmt_cm(length)
        width_str  = _fmt_cm(width)
        status = s.get('status') or 'valid'
        rows += f'<tr><td>{i+1}</td><td>{e(s["beam_name"])}</td><td>{e(s["segment_label"])}</td><td>{e(length_str)}</td><td>{e(width_str)}</td><td>{e(status)}</td><td><a href="{e(s["_slug"])}.html">→</a></td></tr>'
    rows += '</table>'

    idx_html = gen_index_html('Fundos de Viga', 'FV — sofito das vigas', rows, guide_rel, len(seg_data))
    (base / 'index.html').write_text(idx_html, encoding='utf-8')
    print(f'[FV] fundos_viga: {len(seg_data)} fichas')
    return len(seg_data)

# ─── Section: Lajes ───────────────────────────────────────────────────────────

def build_lajes_section(estado):
    slabs = estado['slabs']
    base = OUTPUT_DIR / 'lajes'
    base.mkdir(parents=True, exist_ok=True)
    guide_rel = 'interpretacao_lajes.html'

    slabs_sorted = sorted(slabs, key=lambda s: s['name'])

    for idx, slab in enumerate(slabs_sorted):
        slug, html = gen_laje_ficha(slab, idx, slabs_sorted, guide_rel)
        (base / f'{slug}.html').write_text(html, encoding='utf-8')

    rows = '<table><tr><th>#</th><th>Laje</th><th>Nível topo</th><th>Espessura</th><th>Link</th></tr>'
    for i, s in enumerate(slabs_sorted):
        nivel  = s.get('nivel') or ''
        height = s.get('height') or ''
        nivel_str  = _fmt_cm(nivel, 2)
        height_str = _fmt_cm(height, 0)
        rows += f'<tr><td>{i+1}</td><td>{e(s["name"])}</td><td>{e(nivel_str)}</td><td>{e(height_str)}</td><td><a href="{e(s["name"])}.html">→</a></td></tr>'
    rows += '</table>'

    idx_html = gen_index_html('Lajes', 'LAJ — placas horizontais de concreto', rows, guide_rel, len(slabs_sorted))
    (base / 'index.html').write_text(idx_html, encoding='utf-8')
    print(f'[LAJ] lajes: {len(slabs_sorted)} fichas')
    return len(slabs_sorted)

# ─── Section: Visão de Cortes ─────────────────────────────────────────────────

def build_cortes_section(estado):
    cortes = estado['cortes']
    base = OUTPUT_DIR / 'visao_cortes'
    base.mkdir(parents=True, exist_ok=True)
    guide_rel = 'interpretacao_cortes.html'

    for c in cortes:
        uid  = c.get('uid', '')
        beam = c.get('beam_name', '?')
        c['_slug'] = f'{beam}_{uid[-6:] if len(uid) > 6 else uid}'.replace(' ', '_')

    for idx, corte in enumerate(cortes):
        slug, html = gen_corte_ficha(corte, idx, cortes, guide_rel)
        (base / f'{slug}.html').write_text(html, encoding='utf-8')

    rows = '<table><tr><th>#</th><th>Viga</th><th>Confiança</th><th>Laje própria</th><th>Laje vizinha</th><th>Altura</th><th>Status</th><th>Link</th></tr>'
    for i, c in enumerate(cortes):
        conf    = c.get('conf_pct', 0)
        own_l   = c.get('own_laje', '—') or '—'
        neigh_l = c.get('neigh_laje', '—') or '—'
        beam_h  = c.get('beam_h', '—')
        status  = c.get('status', '—')
        beam_h_str = _fmt_cm(beam_h)
        rows += f'<tr><td>{i+1}</td><td>{e(c.get("beam_name","?"))}</td><td>{conf}%</td><td>{e(own_l)}</td><td>{e(neigh_l)}</td><td>{e(beam_h_str)}</td><td>{e(status)}</td><td><a href="{e(c["_slug"])}.html">→</a></td></tr>'
    rows += '</table>'

    idx_html = gen_index_html('Visão de Cortes', 'VC — cortes transversais nas vigas', rows, guide_rel, len(cortes))
    (base / 'index.html').write_text(idx_html, encoding='utf-8')
    print(f'[VC] visao_cortes: {len(cortes)} fichas')
    return len(cortes)

# ─── Main index.html ──────────────────────────────────────────────────────────

def build_main_index(estado):
    obra = estado.get('obra', 'Obra_TREINO_1')
    pav  = estado.get('pavimento', '13_PAV')
    n_pil = len(estado.get('pilares', []))
    n_slab = len(estado.get('slabs', []))
    n_cortes = len(estado.get('cortes', []))
    segs = estado.get('segmentos', {})
    n_ap = len(segs.get('lateral_a_para', []))
    n_bp = len(segs.get('lateral_b_para', []))
    n_aP = len(segs.get('lateral_a_passa', []))
    n_bP = len(segs.get('lateral_b_passa', []))
    n_fv = len(segs.get('fundo', []))

    sections = [
        ('pilares',         '🏛 Pilares',                  f'{n_pil} fichas',   'pilares/index.html'),
        ('pilares_esp',     '🏛 Pilares Especiais',         '2 fichas',          'pilares_especiais/index.html'),
        ('lajes',           '▬ Lajes',                     f'{n_slab} fichas',  'lajes/index.html'),
        ('visao_cortes',    '✂ Visão de Cortes',            f'{n_cortes} fichas','visao_cortes/index.html'),
        ('fundos_viga',     '⬇ Fundos de Viga',            f'{n_fv} fichas',    'fundos_viga/index.html'),
        ('lv_a_para',       '← Laterais A-Para',            f'{n_ap} segs.',     'laterais_viga/a_para/index.html'),
        ('lv_b_para',       '→ Laterais B-Para',            f'{n_bp} segs.',     'laterais_viga/b_para/index.html'),
        ('lv_a_passa',      '↔ Laterais A-Passa',           f'{n_aP} segs.',     'laterais_viga/a_passa/index.html'),
        ('lv_b_passa',      '↔ Laterais B-Passa',           f'{n_bP} segs.',     'laterais_viga/b_passa/index.html'),
        ('convencao_niveis','📐 Convenção de Níveis',        '—',                 'convencao_niveis/interpretacao_niveis.html'),
    ]

    guides = [
        ('pilares/interpretacao_abcd.html',          '📖 Guia ABCD Pilares'),
        ('pilares_especiais/interpretacao_especiais.html', '📖 Guia Pilares Especiais'),
        ('lajes/interpretacao_lajes.html',           '📖 Guia Lajes'),
        ('visao_cortes/interpretacao_cortes.html',   '📖 Guia Visão de Cortes'),
        ('fundos_viga/interpretacao_fundos.html',    '📖 Guia Fundos de Viga'),
        ('laterais_viga/interpretacao_laterais.html','📖 Guia Laterais LV'),
        ('convencao_niveis/interpretacao_niveis.html','📖 Guia Convenção de Níveis'),
    ]

    cards = ''
    for _, label, count, href in sections:
        cards += f'<div class="sec"><div class="sec-title">{e(label)}</div><div class="sec-body"><div class="kv"><span class="kv-key">Itens</span><span class="kv-val accent">{e(count)}</span></div><a class="link-guide" href="{e(href)}">Abrir →</a></div></div>'

    guides_html = '<ul style="list-style:none;padding:0;margin:10px 0;">'
    for href, label in guides:
        guides_html += f'<li style="margin:4px 0;"><a href="{e(href)}" style="color:#4a7aaa;text-decoration:none;font-size:11px;">{e(label)}</a></li>'
    guides_html += '</ul>'

    html = page_head(f'{obra} — {pav} — Índice Geral')
    html += f"""<body class="page-body-only"><div class="page-full">
  <h1>{e(obra)} &mdash; {e(pav)} &mdash; Fichas HTML</h1>
  <div class="intro">
    Fichas geradas automaticamente pelo SA Headless. Use a navegação abaixo para explorar pilares, lajes, vigas e segmentos.
    <br><b>Guias de interpretação</b> explicam as convenções ABCD, Para/Passa, Fundos, Cortes e Níveis.
  </div>
  <h2>Seções de Dados</h2>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0;">
  {cards}
  </div>
  <h2>Guias de Interpretação</h2>
  {guides_html}
</div></body></html>"""

    (OUTPUT_DIR / 'index.html').write_text(html, encoding='utf-8')
    print('[IDX] index.html gerado')

# ─── Run ──────────────────────────────────────────────────────────────────────

def main():
    print(f'Carregando {ESTADO_JSON}...', flush=True)
    with open(ESTADO_JSON) as f:
        estado = json.load(f)

    total = 0
    total += build_lv_section(estado)
    total += build_fv_section(estado)
    total += build_lajes_section(estado)
    total += build_cortes_section(estado)
    build_main_index(estado)

    print(f'\n✓ Concluído. Total de fichas geradas: {total}')
    print(f'  Output: {OUTPUT_DIR}')

if __name__ == '__main__':
    main()
