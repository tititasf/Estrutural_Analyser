#!/usr/bin/env python3
"""
create_all_fichas_v3.py
Fichas HTML enriquecidas com dados de três fontes:
  N1  = Fase-4 JSONs (schema real do robô STOG)
  N2  = DB reverse_eng_fichas (motor reverso — extraído do DXF humano)
  SA  = estado_13_PAV.json (Structural Analyzer — segmentos, comportamento)
"""

import json, sqlite3, os
from pathlib import Path
from html import escape

ESTADO_JSON = Path('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/estado_13_PAV.json')
OUTPUT_DIR  = Path('D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_20260630_203509')
DB_PATH     = Path('D:/Agente-cad-PYSIDE/project_data.vision')
FASE4_BASE  = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-4_Sincronizacao')

OBRA = 'Obra_TREINO_1'
PAV  = '13_PAV'

# ─── CSS ─────────────────────────────────────────────────────────────────────
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body.L { display: flex; height: 100vh; overflow: hidden; background: #111; color: #ccc; font-family: 'Segoe UI', sans-serif; font-size: 11px; line-height: 1.5; }
body.P { background: #111; color: #ccc; font-family: 'Segoe UI', sans-serif; font-size: 11px; line-height: 1.5; }
.sidebar { width: 190px; min-width: 140px; overflow-y: auto; background: #0d0d0d; border-right: 1px solid #1e1e1e; flex-shrink: 0; height: 100vh; }
.sb-head { padding: 8px 10px 6px; background: #0a0a0a; border-bottom: 1px solid #1e1e1e; }
.sb-head h3 { color: #4fc3a1; font-size: 9px; margin: 0 0 3px; letter-spacing: 0.05em; text-transform: uppercase; }
.sb-head a { color: #3a6a9a; font-size: 9px; text-decoration: none; display: block; margin-top: 2px; }
.sb-head a:hover { color: #7eb8f7; }
.sb-back { color: #444; font-size: 9px; text-decoration: none; display: block; margin-bottom: 3px; }
.sb-back:hover { color: #999; }
.sb-list { list-style: none; padding: 3px 0; margin: 0; }
.sb-list li a { display: block; padding: 3px 10px; color: #555; text-decoration: none; font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sb-list li.act a { color: #f0b840; background: #161200; font-weight: bold; }
.sb-list li a:hover { background: #161616; color: #aaa; }
.main { flex: 1; overflow-y: auto; height: 100vh; }
.nav { display: flex; align-items: center; gap: 10px; padding: 4px 14px; background: #0d0d0d; border-bottom: 1px solid #181818; position: sticky; top: 0; z-index: 5; }
.nav-a { color: #4a7aaa; text-decoration: none; font-size: 10px; padding: 2px 9px; border: 1px solid #1e2e4a; border-radius: 3px; white-space: nowrap; }
.nav-a:hover { background: #121a28; }
.nav-a.off { color: #2a2a2a; border-color: #1a1a1a; pointer-events: none; }
.nav-pos { color: #444; font-size: 10px; flex: 1; text-align: center; }
.body { padding: 14px 20px 24px; max-width: 980px; }
.pg { max-width: 980px; margin: 0 auto; padding: 22px 20px 28px; }
h1 { color: #4fc3a1; font-size: 16px; margin-bottom: 14px; padding-bottom: 7px; border-bottom: 1px solid #1e1e1e; }
h2 { color: #7eb8f7; font-size: 12px; margin: 18px 0 7px; border-left: 3px solid #2a4a7a; padding-left: 7px; }
h3 { color: #aaa; font-size: 10px; margin: 10px 0 4px; letter-spacing: 0.06em; text-transform: uppercase; }
.sec { border: 1px solid #1a1a1a; border-radius: 4px; margin: 10px 0; overflow: hidden; }
.sec-t { background: #151515; color: #555; font-size: 9px; padding: 4px 10px; letter-spacing: 0.08em; text-transform: uppercase; display: flex; align-items: center; gap: 8px; }
.sec-t .badge-src { display: inline-block; padding: 1px 5px; border-radius: 2px; font-size: 8px; font-weight: bold; margin-left: 4px; }
.src-n1 { background: #0e1a10; color: #4fc3a1; }
.src-n2 { background: #0e1028; color: #7eb8f7; }
.src-sa { background: #281a08; color: #f0b840; }
.sec-b { padding: 8px 12px; }
.kv { display: flex; align-items: baseline; gap: 8px; padding: 3px 0; border-bottom: 1px solid #141414; }
.kv:last-child { border-bottom: none; }
.k { color: #4a4a4a; font-size: 10px; min-width: 150px; flex-shrink: 0; }
.v { color: #bbb; font-size: 11px; white-space: pre-wrap; }
.v.hi { color: #4fc3a1; font-weight: bold; }
.v.hi2 { color: #7eb8f7; font-weight: bold; }
.v.warn { color: #f0b840; }
.v.lo { color: #333; font-style: italic; }
.v.ok { color: #4fc3a1; }
.v.bad { color: #e06040; }
.tag { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; margin: 0 2px; }
.t-A { background: #0e180e; color: #4fc3a1; border: 1px solid #1a2e1a; }
.t-B { background: #0e1020; color: #7eb8f7; border: 1px solid #1a1a38; }
.t-Para { background: #0a1424; color: #5a9adf; }
.t-Passa { background: #1a0a24; color: #a06adf; }
.t-Fundo { background: #180a20; color: #d080e0; }
.t-sarr { background: #0a1808; color: #4aaa4a; }
.t-grad { background: #180808; color: #e04040; }
.t-mist { background: #181008; color: #d08030; }
.t-inv { background: #100818; color: #9050c0; }
.conf-high { color: #4fc3a1; }
.conf-mid  { color: #f0b840; }
.conf-low  { color: #e06040; }
tbl { width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 10px; }
th { background: #141414; color: #4fc3a1; padding: 4px 8px; text-align: left; border-bottom: 1px solid #222; font-size: 9px; letter-spacing: 0.05em; text-transform: uppercase; white-space: nowrap; }
td { padding: 3px 8px; border-bottom: 1px solid #131313; color: #999; vertical-align: top; }
tr:hover td { background: #131313; }
a.g { color: #3a6a9a; text-decoration: none; font-size: 10px; border: 1px solid #1e2e4a; border-radius: 3px; padding: 3px 9px; display: inline-block; margin: 8px 0; }
a.g:hover { background: #121a28; color: #7eb8f7; }
a.bk { color: #444; text-decoration: none; font-size: 10px; display: inline-block; margin-bottom: 14px; }
a.bk:hover { color: #aaa; }
.info { background: #111; border: 1px solid #1a1a1a; border-radius: 4px; padding: 8px 12px; color: #666; font-size: 10px; margin: 8px 0; line-height: 1.7; }
.info b { color: #8ab8c8; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
.intro { background: #111; border: 1px solid #1a1a1a; border-radius: 5px; padding: 10px 14px; margin-bottom: 16px; color: #777; font-size: 11px; line-height: 1.7; }
.intro b { color: #4fc3a1; }
table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 10px; }
code { background: #181818; color: #d07050; padding: 1px 4px; border-radius: 2px; font-size: 10px; font-family: 'Courier New', monospace; }
"""

# ─── helpers ─────────────────────────────────────────────────────────────────
e  = lambda s: escape(str(s) if s is not None else '')
fv = lambda v, d=1: (f'{float(v):.{d}f}' if v not in (None,'','—') and str(v).replace('.','').replace('-','').isdigit() else (str(v) if v not in (None,'','—') else '—'))
def fmt_cm(v, d=1):
    if v in (None, '', '—'): return '—'
    try:    return f'{float(v):.{d}f} cm'
    except: return str(v)

def head(title):
    return f'<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="UTF-8">\n<title>{e(title)}</title>\n<style>{CSS}</style>\n</head>\n'

def kv(key, val, cls=''):
    c = f' class="v {cls}"' if cls else ' class="v"'
    if val in (None, '', '—'): val_html = '<span class="v lo">—</span>'
    else: val_html = f'<span{c}>{e(str(val))}</span>'
    return f'<div class="kv"><span class="k">{e(key)}</span>{val_html}</div>'

def kv_raw(key, html_val):
    return f'<div class="kv"><span class="k">{e(key)}</span><span class="v">{html_val}</span></div>'

def conf_badge(c):
    if c is None: return '<span class="v lo">—</span>'
    try:
        f = float(c)
        cls = 'conf-high' if f >= 0.85 else ('conf-mid' if f >= 0.70 else 'conf-low')
        return f'<span class="{cls}">{f:.2f}</span>'
    except: return f'<span class="v">{e(c)}</span>'

def tipo_viga_tag(tv):
    if not tv: return '—'
    m = {'sarrafeada':'t-sarr', 'gradeada':'t-grad', 'mista':'t-mist', 'invertida':'t-inv'}
    for k, cls in m.items():
        if k in tv: return f'<span class="tag {cls}">{e(tv)}</span>'
    return f'<span class="tag">{e(tv)}</span>'

def panel_table(panels, label='Painéis'):
    if not panels: return ''
    rows = ''
    for i, p in enumerate(panels):
        w   = fmt_cm(p.get('largura_cm') or p.get('width'))
        h1  = fmt_cm(p.get('height1'))
        h2  = fmt_cm(p.get('height2'))
        gh1 = fmt_cm(p.get('grade_h1') or p.get('grade_h1'))
        ls  = fmt_cm(p.get('laje_sup_local') or p.get('slab_top'))
        li  = fmt_cm(p.get('laje_inf_local') or p.get('slab_bottom'))
        pt  = e(p.get('panel_type') or '—')
        rows += f'<tr><td>{i+1}</td><td>{w}</td><td>{h1}</td><td>{h2}</td><td>{gh1}</td><td>{ls}</td><td>{li}</td><td>{pt}</td></tr>'
    return (f'<h3>{e(label)}</h3>'
            f'<table><tr><th>#</th><th>Largura</th><th>H1</th><th>H2</th>'
            f'<th>Grade H1</th><th>Laje sup.</th><th>Laje inf.</th><th>Tipo</th></tr>'
            f'{rows}</table>')

def sidebar(items, active_idx, title, guide_rel, back='../../index.html'):
    li = ''
    for i, (_, lbl, href) in enumerate(items):
        a = ' class="act"' if i == active_idx else ''
        li += f'<li{a}><a href="{e(href)}" title="{e(lbl)}">{e(lbl)}</a></li>\n'
    return (f'<nav class="sidebar"><div class="sb-head">'
            f'<a class="sb-back" href="{e(back)}">← índice geral</a>'
            f'<h3>{e(title)}</h3>'
            f'<a href="{e(guide_rel)}">📖 Guia</a>'
            f'</div><ul class="sb-list">{li}</ul></nav>')

def navbar(prev, nxt, pos):
    p = f'<a class="nav-a" href="{e(prev)}">&#8592; ant.</a>' if prev else '<span class="nav-a off">&#8592;</span>'
    n = f'<a class="nav-a" href="{e(nxt)}">próx. &#8594;</a>'  if nxt  else '<span class="nav-a off">&#8594;</span>'
    return f'<div class="nav">{p}<span class="nav-pos">{e(pos)}</span>{n}</div>'

def sec(title, body_html, src_tag=''):
    badge = f'<span class="badge-src {src_tag}">{src_tag.upper().replace("SRC-","")}</span>' if src_tag else ''
    return (f'<div class="sec"><div class="sec-t">{e(title)}{badge}</div>'
            f'<div class="sec-b">{body_html}</div></div>')

def index_table_wrap(rows_html, headers):
    ths = ''.join(f'<th>{e(h)}</th>' for h in headers)
    return f'<table><tr>{ths}</tr>{rows_html}</table>'

# ─── data loading ─────────────────────────────────────────────────────────────

def load_estado():
    with open(ESTADO_JSON, encoding='utf-8') as f:
        return json.load(f)

def load_n2_fichas(classe):
    """Returns dict: elemento_id -> campos_json + confianca."""
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute(
        "SELECT elemento_id, campos_json, confianca FROM reverse_eng_fichas "
        "WHERE obra_name=? AND pavimento=? AND classe=?",
        (OBRA, PAV, classe)
    )
    result = {}
    for elem_id, cj_raw, conf in cur.fetchall():
        try:
            cj = json.loads(cj_raw) if cj_raw else {}
        except Exception:
            cj = {}
        cj['_confianca'] = conf
        result[elem_id] = cj
    db.close()
    return result

def load_fase4_lv():
    folder = FASE4_BASE / 'JSON_Vigas_Laterais'
    d = {}
    if folder.exists():
        for p in folder.glob('*.json'):
            try:
                with open(p, encoding='utf-8') as f:
                    obj = json.load(f)
                name = obj.get('name', p.stem)
                d[name] = obj
            except Exception:
                pass
    return d

def load_fase4_fv():
    folder = FASE4_BASE / 'JSON_Vigas_Fundo'
    d = {}
    if folder.exists():
        for p in folder.glob('*.json'):
            try:
                with open(p, encoding='utf-8') as f:
                    obj = json.load(f)
                name = obj.get('name', p.stem.replace('_fundo',''))
                d[name] = obj
            except Exception:
                pass
    return d

def load_fase4_laj():
    folder = FASE4_BASE / 'JSON_Lajes'
    d = {}
    if folder.exists():
        for p in folder.glob('*.json'):
            try:
                with open(p, encoding='utf-8') as f:
                    obj = json.load(f)
                nome = obj.get('nome', p.stem)
                d[nome] = obj
            except Exception:
                pass
    return d

# ─── LV section ─────────────────────────────────────────────────────────────

def gen_lv_ficha(seg, idx, all_segs, kind, title, guide_rel,
                 n2_fichas, fase4_lv):
    slug = f'{seg["beam_name"]}_{seg["segment_label"]}'
    prev = f'{all_segs[idx-1]["_slug"]}.html' if idx > 0 else None
    nxt  = f'{all_segs[idx+1]["_slug"]}.html' if idx < len(all_segs)-1 else None
    pos  = f'{idx+1} / {len(all_segs)} — {seg["beam_name"]} · seg.{seg["segment_label"]}'

    sb_items = [(s['_slug'], f'{s["beam_name"]}·{s["segment_label"]}', f'{s["_slug"]}.html') for s in all_segs]
    sb = sidebar(sb_items, idx, title, guide_rel, back='../../index.html')
    nb = navbar(prev, nxt, pos)

    # Data sources
    sa  = seg
    beam = seg['beam_name']
    side = seg.get('side', 'A')
    beh  = seg.get('behavior', '')
    seg_i = max(0, int(seg.get('segment_label', 1)) - 1)

    # N2: match by beam_name (DB stores V13, not V13_A)
    n2 = n2_fichas.get(beam, {})

    # N1: Fase-4 has V13_A or V13_B
    f4_key = f'{beam}_{side}'
    n1 = fase4_lv.get(f4_key, {})

    h_side     = n2.get(f'h_{side}')
    laje_sup   = n2.get(f'laje_sup_{side}')
    laje_inf   = n2.get(f'laje_inf_{side}')
    b_geom     = n2.get('b_geom') or n2.get('total_width') or n1.get('total_width')
    tipo_viga  = n2.get('tipo_viga', '')
    continuation = n2.get('continuation', '') or ''
    text_left  = n2.get('text_left', '') or ''
    text_right = n2.get('text_right', '') or ''
    pl = n2.get('pillar_left', {}) or {}
    pr = n2.get('pillar_right', {}) or {}

    panels_side = n2.get(f'panels_{side}', [])
    seg_panel = panels_side[seg_i] if seg_i < len(panels_side) else {}

    sect_views = n2.get('section_views', [])
    n1_panels  = n1.get('panels', [])

    side_tag = f'<span class="tag t-{side}">{side}</span>'
    beh_tag  = f'<span class="tag t-{beh}">{beh}</span>' if beh else ''
    conf_h   = conf_badge(n2.get('_confianca'))

    # SA section
    sa_body = (
        kv('Viga (beam_name)', beam, 'hi')
        + kv('Segmento (label)', seg.get('segment_label'))
        + kv_raw('Lado (side)', side_tag)
        + kv_raw('Comportamento', beh_tag)
        + kv('Comprimento do segmento', fmt_cm(seg.get('length')))
        + kv('Status', seg.get('status') or 'valid')
        + (kv('Atenção', seg.get('atencao')) if seg.get('atencao') else '')
    )

    # N2 section — beam-level
    n2_body = (
        conf_badge_kv('Confiança N2', n2.get('_confianca'))
        + kv_raw('Tipo de viga', tipo_viga_tag(tipo_viga))
        + kv(f'Altura lateral face {side} (h_{side})', fmt_cm(h_side))
        + kv('Largura da seção (b_geom)', fmt_cm(b_geom))
        + kv(f'Laje superior face {side}', fmt_cm(laje_sup))
        + kv(f'Laje inferior face {side}', fmt_cm(laje_inf))
        + kv('Laje superior face oposta', fmt_cm(n2.get(f'laje_sup_{"B" if side=="A" else "A"}')))
        + kv('Laje inferior face oposta', fmt_cm(n2.get(f'laje_inf_{"B" if side=="A" else "A"}')))
        + kv('Referência esquerda (pilar)', text_left or ('P' if pl.get('active') else '—'))
        + kv('Referência direita (pilar)', text_right or ('P' if pr.get('active') else '—'))
        + kv('Continuação', continuation or '—')
        + kv('Seções transversais (views)', str(len(sect_views)) if sect_views else '0')
    )

    # N2 — panel específico deste segmento
    panel_body = ''
    if seg_panel:
        panel_body = (
            kv('Largura do painel', fmt_cm(seg_panel.get('largura_cm') or seg_panel.get('width')))
            + kv('Altura principal (H1)', fmt_cm(seg_panel.get('height1')))
            + kv('Altura secundária (H2)', fmt_cm(seg_panel.get('height2')))
            + kv('Grade H1', fmt_cm(seg_panel.get('grade_h1')))
            + kv('Grade H2', fmt_cm(seg_panel.get('grade_h2')))
            + kv('Laje superior local', fmt_cm(seg_panel.get('laje_sup_local') or seg_panel.get('slab_top')))
            + kv('Laje inferior local', fmt_cm(seg_panel.get('laje_inf_local') or seg_panel.get('slab_bottom')))
            + kv('Laje central embutida', fmt_cm(seg_panel.get('laje_central_alt') or seg_panel.get('slab_center')))
            + kv('Tipo de painel', seg_panel.get('panel_type') or '—')
            + kv('Reaproveitamento', 'Sim' if seg_panel.get('reuse') else 'Não')
            + kv('Posição (is_first/is_last)', f'{"primeiro " if seg_panel.get("is_first") else ""}{"último" if seg_panel.get("is_last") else ""}')
        )

    # N1 Fase-4
    n1_body = (
        kv('Arquivo N1 (Fase-4)', f4_key)
        + kv('Largura da seção N1 (total_width)', fmt_cm(n1.get('total_width')))
        + kv('Altura lateral N1 (total_height)', fmt_cm(n1.get('total_height')))
        + kv('Floor', n1.get('floor') or '—')
        + kv('Nº de painéis N1', str(len(n1_panels)) if n1_panels else '—')
    )

    # All panels N2 table
    all_panels_html = panel_table(panels_side, f'Todos os painéis — face {side}')
    if not all_panels_html and n1_panels:
        all_panels_html = panel_table(n1_panels, 'Painéis N1 (Fase-4)')

    # Interpretation box
    interp = {
        'Para':  f'Segmento no <b>extremo</b> da viga — encosta em pilar/parede. Face {side} = {"esquerda" if side=="A" else "direita"} olhando C→D.',
        'Passa': f'Segmento <b>interior</b> da viga — continua nos dois lados. Face {side} = {"esquerda" if side=="A" else "direita"} olhando C→D.',
    }.get(beh, '')

    html = head(f'LV — {beam} · {seg["segment_label"]} — {side}-{beh}')
    html += f'<body class="L"><div style="display:flex;height:100vh;overflow:hidden;">{sb}\n<div class="main">{nb}\n<div class="body">'
    html += f'<h1>{e(beam)} · seg.{e(seg["segment_label"])} &nbsp; {side_tag} {beh_tag}</h1>'
    if interp:
        html += f'<div class="info"><b>Interpretação:</b> {interp}</div>'
    html += sec('SA — Structural Analyzer', sa_body, 'src-sa')
    html += sec('N2 — Ficha Motor Reverso (viga completa)', n2_body, 'src-n2')
    if panel_body:
        html += sec(f'N2 — Painel #{seg_i+1} (este segmento)', panel_body, 'src-n2')
    if all_panels_html:
        html += sec(f'N2 — Tabela de painéis face {side}', all_panels_html, 'src-n2')
    html += sec('N1 — Fase-4 JSON', n1_body, 'src-n1')
    html += f'<a class="g" href="{e(guide_rel)}">📖 Guia de Laterais A/B e Para/Passa</a>'
    html += '</div></div></div>\n</body></html>'
    return slug, html

def conf_badge_kv(key, c):
    return kv_raw(key, conf_badge(c))

def build_lv_section(estado, n2_lv, fase4_lv):
    specs = {
        'lateral_a_para':  ('a_para',  'LV — Lateral A-Para',  '../interpretacao_laterais.html'),
        'lateral_b_para':  ('b_para',  'LV — Lateral B-Para',  '../interpretacao_laterais.html'),
        'lateral_a_passa': ('a_passa', 'LV — Lateral A-Passa', '../interpretacao_laterais.html'),
        'lateral_b_passa': ('b_passa', 'LV — Lateral B-Passa', '../interpretacao_laterais.html'),
    }
    base = OUTPUT_DIR / 'laterais_viga'
    created = 0
    for kind, (subfolder, title, guide_rel) in specs.items():
        seg_data = estado['segmentos'].get(kind, [])
        folder = base / subfolder
        folder.mkdir(parents=True, exist_ok=True)
        for s in seg_data:
            s['_slug'] = f'{s["beam_name"]}_{s["segment_label"]}'
        for idx, seg in enumerate(seg_data):
            slug, html = gen_lv_ficha(seg, idx, seg_data, kind, title, guide_rel, n2_lv, fase4_lv)
            (folder / f'{slug}.html').write_text(html, encoding='utf-8')
            created += 1
        # index for this subfolder
        rows = ''
        for i, s in enumerate(seg_data):
            n2 = n2_lv.get(s['beam_name'], {})
            tv = n2.get('tipo_viga', '—') or '—'
            ls = fmt_cm(n2.get(f'laje_sup_{s.get("side","A")}'))
            li = fmt_cm(n2.get(f'laje_inf_{s.get("side","A")}'))
            c  = n2.get('_confianca')
            cstr = f'{float(c):.2f}' if c is not None else '—'
            rows += (f'<tr><td>{i+1}</td><td>{e(s["beam_name"])}</td>'
                     f'<td>{e(s["segment_label"])}</td>'
                     f'<td>{e(fmt_cm(s.get("length")))}</td>'
                     f'<td>{e(tv)}</td><td>{e(ls)}</td><td>{e(li)}</td>'
                     f'<td>{cstr}</td>'
                     f'<td><a href="{e(s["_slug"])}.html">→</a></td></tr>')
        idx_html = _page_index(title, ['#','Viga','Seg.','Comprimento','Tipo','Laje sup.','Laje inf.','Conf.','Link'],
                               rows, guide_rel, len(seg_data))
        (folder / 'index.html').write_text(idx_html, encoding='utf-8')
        print(f'[LV] {subfolder}: {len(seg_data)} fichas enriquecidas')
    return created

# ─── FV section ─────────────────────────────────────────────────────────────

def gen_fv_ficha(seg, idx, all_segs, guide_rel, n2_fv, fase4_fv):
    slug = f'{seg["beam_name"]}_{seg["segment_label"]}'
    prev = f'{all_segs[idx-1]["_slug"]}.html' if idx > 0 else None
    nxt  = f'{all_segs[idx+1]["_slug"]}.html' if idx < len(all_segs)-1 else None
    pos  = f'{idx+1} / {len(all_segs)} — FV {seg["beam_name"]} · {seg["segment_label"]}'

    sb_items = [(s['_slug'], f'{s["beam_name"]}·{s["segment_label"]}', f'{s["_slug"]}.html') for s in all_segs]
    sb = sidebar(sb_items, idx, 'FV — Fundos de Viga', guide_rel, back='../index.html')
    nb = navbar(prev, nxt, pos)

    beam = seg['beam_name']
    seg_i = max(0, int(seg.get('segment_label', 1)) - 1)
    n2 = n2_fv.get(beam, {})
    n1 = fase4_fv.get(beam, {})

    panels_n2 = n2.get('panels', [])
    seg_panel = panels_n2[seg_i] if seg_i < len(panels_n2) else {}
    holes = [h for h in (n2.get('holes') or []) if h.get('active')]
    segs_rich = n2.get('segments_rich', [])
    seg_rich = segs_rich[seg_i] if seg_i < len(segs_rich) else {}

    # SA section
    sa_body = (
        kv('Viga (beam_name)', beam, 'hi')
        + kv('Segmento (label)', seg.get('segment_label'))
        + kv('Comprimento do segmento', fmt_cm(seg.get('length')))
        + kv('Largura', fmt_cm(seg.get('width')))
        + kv('Status', seg.get('status') or 'valid')
        + (kv('Atenção', seg.get('atencao')) if seg.get('atencao') else '')
    )

    # N2 beam-level
    pl = n2.get('pillar_left', {}) or {}
    pr = n2.get('pillar_right', {}) or {}
    n2_body = (
        conf_badge_kv('Confiança N2', n2.get('_confianca'))
        + kv('Largura da seção (total_width)', fmt_cm(n2.get('total_width') or n1.get('total_width')))
        + kv('Altura total do fundo', fmt_cm(n2.get('total_height') or n1.get('total_height')))
        + kv('Nº de painéis total', str(len(panels_n2)) if panels_n2 else '—')
        + kv('Aberturas activas (holes)', str(len(holes)) if holes else '0')
        + kv('Pilar esquerdo activo', 'Sim' if pl.get('active') else 'Não')
        + kv('Pilar direito activo', 'Sim' if pr.get('active') else 'Não')
        + kv('Rótulo esquerdo', n2.get('label_left') or '—')
        + kv('Rótulo direito', n2.get('label_right') or '—')
        + kv('Nº linhas folha (_n_linhas_folha)', str(n2.get('_n_linhas_folha', '—')))
    )

    # N2 painel específico
    panel_body = ''
    if seg_panel:
        panel_body = (
            kv('Largura do painel', fmt_cm(seg_panel.get('width')))
            + kv('Altura principal (height1)', fmt_cm(seg_panel.get('height1')))
            + kv('Altura secundária (height2)', fmt_cm(seg_panel.get('height2')))
            + kv('Grade H1', fmt_cm(seg_panel.get('grade_h1')))
            + kv('Grade H2', fmt_cm(seg_panel.get('grade_h2')))
        )
    if seg_rich:
        sr_panels = seg_rich.get('panels', [])
        if sr_panels:
            panel_body += f'<h3>Segmento enriquecido ({len(sr_panels)} sub-painéis)</h3>'
            for sp in sr_panels[:3]:
                panel_body += f'<div class="kv"><span class="k">Sub-painel</span><span class="v">w={fmt_cm(sp.get("width"))} h1={fmt_cm(sp.get("height1"))} h2={fmt_cm(sp.get("height2"))}</span></div>'

    # holes table
    holes_body = ''
    if holes:
        holes_body = '<table><tr><th>#</th><th>Largura</th><th>Altura</th><th>Posição</th><th>Texto</th></tr>'
        for i, h in enumerate(holes):
            holes_body += f'<tr><td>{i+1}</td><td>{fmt_cm(h.get("width"))}</td><td>{fmt_cm(h.get("height"))}</td><td>{e(h.get("position","—"))}</td><td>{e(h.get("text",""))}</td></tr>'
        holes_body += '</table>'

    # N1
    n1_body = (
        kv('Arquivo N1 (Fase-4)', f'{beam}_fundo')
        + kv('total_width N1', fmt_cm(n1.get('total_width')))
        + kv('total_height N1', fmt_cm(n1.get('total_height')))
        + kv('Floor N1', n1.get('floor') or '—')
        + kv('Nº painéis N1', str(len(n1.get('panels', []))))
    )

    # All panels table
    all_panels_html = panel_table(panels_n2, 'Tabela completa de painéis')

    html = head(f'FV — {beam} · {seg["segment_label"]}')
    html += f'<body class="L"><div style="display:flex;height:100vh;overflow:hidden;">{sb}\n<div class="main">{nb}\n<div class="body">'
    html += f'<h1>FV — {e(beam)} · seg.{e(seg["segment_label"])} <span class="tag t-Fundo">Fundo</span></h1>'
    html += f'<div class="info"><b>Fundo de Viga (FV):</b> face inferior (sofito) da viga. Verificar laje do pavimento inferior alinhada ao nível do fundo.</div>'
    html += sec('SA — Structural Analyzer', sa_body, 'src-sa')
    html += sec('N2 — Motor Reverso FV (viga completa)', n2_body, 'src-n2')
    if panel_body:
        html += sec(f'N2 — Painel #{seg_i+1} (este segmento)', panel_body, 'src-n2')
    if holes_body:
        html += sec('N2 — Aberturas (holes)', holes_body, 'src-n2')
    if all_panels_html:
        html += sec('N2 — Tabela de painéis (completa)', all_panels_html, 'src-n2')
    html += sec('N1 — Fase-4 JSON', n1_body, 'src-n1')
    html += f'<a class="g" href="{e(guide_rel)}">📖 Guia de Fundos de Viga</a>'
    html += '</div></div></div>\n</body></html>'
    return slug, html

def build_fv_section(estado, n2_fv, fase4_fv):
    seg_data = estado['segmentos'].get('fundo', [])
    base = OUTPUT_DIR / 'fundos_viga'
    base.mkdir(parents=True, exist_ok=True)
    guide_rel = 'interpretacao_fundos.html'
    for s in seg_data:
        s['_slug'] = f'{s["beam_name"]}_{s["segment_label"]}'
    for idx, seg in enumerate(seg_data):
        slug, html = gen_fv_ficha(seg, idx, seg_data, guide_rel, n2_fv, fase4_fv)
        (base / f'{slug}.html').write_text(html, encoding='utf-8')
    # index
    rows = ''
    for i, s in enumerate(seg_data):
        n2 = n2_fv.get(s['beam_name'], {})
        tw = fmt_cm(n2.get('total_width'))
        th = fmt_cm(n2.get('total_height'))
        np_ = str(len(n2.get('panels', []))) if n2 else '—'
        c = n2.get('_confianca'); cstr = f'{float(c):.2f}' if c else '—'
        rows += (f'<tr><td>{i+1}</td><td>{e(s["beam_name"])}</td><td>{e(s["segment_label"])}</td>'
                 f'<td>{e(fmt_cm(s.get("length")))}</td><td>{e(tw)}</td><td>{e(th)}</td>'
                 f'<td>{np_}</td><td>{cstr}</td><td><a href="{e(s["_slug"])}.html">→</a></td></tr>')
    idx_html = _page_index('Fundos de Viga', ['#','Viga','Seg.','Comprimento','Largura seção','Altura fundo','Painéis','Conf.','Link'],
                           rows, guide_rel, len(seg_data))
    (base / 'index.html').write_text(idx_html, encoding='utf-8')
    print(f'[FV] fundos_viga: {len(seg_data)} fichas enriquecidas')
    return len(seg_data)

# ─── LAJ section ─────────────────────────────────────────────────────────────

def gen_laj_ficha(slab_sa, idx, all_slabs, guide_rel, n2_laj, fase4_laj):
    name = slab_sa['name']
    slug = name
    prev = f'{all_slabs[idx-1]["name"]}.html' if idx > 0 else None
    nxt  = f'{all_slabs[idx+1]["name"]}.html' if idx < len(all_slabs)-1 else None
    pos  = f'{idx+1} / {len(all_slabs)} — {name}'

    sb_items = [(s['name'], s['name'], f'{s["name"]}.html') for s in all_slabs]
    sb = sidebar(sb_items, idx, 'Lajes', guide_rel, back='../index.html')
    nb = navbar(prev, nxt, pos)

    # N2 and N1
    n2 = n2_laj.get(name, {})
    n1 = fase4_laj.get(name, {})
    nivel_sa = slab_sa.get('nivel') or ''
    ht_sa    = slab_sa.get('height') or ''

    comp   = n2.get('comprimento') or n1.get('comprimento')
    larg   = n2.get('largura') or n1.get('largura')
    area   = n2.get('area_cm2') or n1.get('area_cm2')
    lv     = n2.get('linhas_verticais', []) or n1.get('linhas_verticais', [])
    lh     = n2.get('linhas_horizontais', []) or n1.get('linhas_horizontais', [])
    obs    = n2.get('obstaculos', []) or n1.get('obstaculos', [])
    modo   = n2.get('modo_selecionado') or n1.get('modo_selecionado')
    unioes = n2.get('unioes_nos_bordes') or n1.get('unioes_nos_bordes')
    obs_txt= n2.get('observacoes') or n1.get('observacoes') or ''
    pont   = n2.get('pontaletes') or n1.get('pontaletes') or {}
    coord  = n2.get('coordenadas') or n1.get('coordenadas') or []

    # SA body
    sa_body = (
        kv('Nome', name, 'hi')
        + kv('Nível topo (SA)', fmt_cm(nivel_sa, 2) if nivel_sa else '—')
        + kv('Espessura (SA)', fmt_cm(ht_sa, 0) if ht_sa else '—')
    )

    # N2 body
    n2_body = (
        conf_badge_kv('Confiança N2', n2.get('_confianca'))
        + kv('Comprimento (X)', fmt_cm(comp))
        + kv('Largura (Y)', fmt_cm(larg))
        + kv('Área total', f'{float(area):.1f} cm²' if area else '—')
        + kv('Nº de pontos do contorno', str(len(coord)) if coord else '—')
        + kv('Linhas verticais de painéis', str(len(lv)) + ('' if not lv else f' — valores: {[round(x["value"],1) for x in lv]}'))
        + kv('Linhas horizontais de painéis', str(len(lh)) + ('' if not lh else f' — valores: {[round(x["value"],1) for x in lh]}'))
        + kv('Obstáculos (pilares/shafts)', str(len(obs)) if obs else '0')
        + kv('Modo de distribuição', str(modo) if modo is not None else '—')
        + kv('Uniões nos bordos', 'Sim' if unioes else 'Não')
        + kv('Observações', obs_txt or '—')
        + kv('Pontaletes', str(pont) if pont else '—')
    )

    # linhas table
    linhas_body = ''
    if lv or lh:
        linhas_body = '<table><tr><th>Tipo</th><th>Posição</th><th>União</th></tr>'
        for x in lv:
            linhas_body += f'<tr><td>Vertical (X)</td><td>{round(float(x["value"]),1)} cm</td><td>{"Sim" if x.get("is_union") else "Não"}</td></tr>'
        for x in lh:
            linhas_body += f'<tr><td>Horizontal (Y)</td><td>{round(float(x["value"]),1)} cm</td><td>{"Sim" if x.get("is_union") else "Não"}</td></tr>'
        linhas_body += '</table>'

    # N1 body
    n1_body = (
        kv('Arquivo N1 (Fase-4)', name)
        + kv('Nome N1', n1.get('nome') or '—')
        + kv('Comprimento N1', fmt_cm(n1.get('comprimento')))
        + kv('Largura N1', fmt_cm(n1.get('largura')))
        + kv('Área N1', f'{float(n1["area_cm2"]):.1f} cm²' if n1.get('area_cm2') else '—')
        + kv('Pavimento N1', n1.get('pavimento') or '—')
    )

    html = head(f'Laje — {name}')
    html += f'<body class="L"><div style="display:flex;height:100vh;overflow:hidden;">{sb}\n<div class="main">{nb}\n<div class="body">'
    html += f'<h1>Laje {e(name)}</h1>'
    html += f'<div class="info"><b>Laje:</b> Placa horizontal de concreto delimitada por vigas. O mesmo vão sempre tem a mesma laje — vigas que cruzam pilares separam os vãos.</div>'
    html += sec('SA — Structural Analyzer', sa_body, 'src-sa')
    html += sec('N2 — Motor Reverso LAJ', n2_body, 'src-n2')
    if linhas_body:
        html += sec('N2 — Linhas de Painéis', linhas_body, 'src-n2')
    html += sec('N1 — Fase-4 JSON', n1_body, 'src-n1')
    html += f'<a class="g" href="{e(guide_rel)}">📖 Guia de Lajes</a>'
    html += '</div></div></div>\n</body></html>'
    return slug, html

def build_laj_section(estado, n2_laj, fase4_laj):
    slabs = sorted(estado['slabs'], key=lambda s: s['name'])
    base = OUTPUT_DIR / 'lajes'
    base.mkdir(parents=True, exist_ok=True)
    guide_rel = 'interpretacao_lajes.html'
    for idx, slab in enumerate(slabs):
        slug, html = gen_laj_ficha(slab, idx, slabs, guide_rel, n2_laj, fase4_laj)
        (base / f'{slug}.html').write_text(html, encoding='utf-8')
    # index
    rows = ''
    for i, s in enumerate(slabs):
        n2 = n2_laj.get(s['name'], {})
        n1 = fase4_laj.get(s['name'], {})
        comp = n2.get('comprimento') or n1.get('comprimento'); cstr = fmt_cm(comp)
        larg = n2.get('largura') or n1.get('largura'); lstr = fmt_cm(larg)
        area = n2.get('area_cm2') or n1.get('area_cm2')
        astr = f'{float(area):.0f} cm²' if area else '—'
        lv_ = n2.get('linhas_verticais', []) or n1.get('linhas_verticais', [])
        lh_ = n2.get('linhas_horizontais', []) or n1.get('linhas_horizontais', [])
        c = n2.get('_confianca'); cfstr = f'{float(c):.2f}' if c else '—'
        rows += (f'<tr><td>{i+1}</td><td>{e(s["name"])}</td><td>{e(cstr)}</td>'
                 f'<td>{e(lstr)}</td><td>{e(astr)}</td>'
                 f'<td>{len(lv_)}/{len(lh_)}</td><td>{cfstr}</td>'
                 f'<td><a href="{e(s["name"])}.html">→</a></td></tr>')
    idx_html = _page_index('Lajes', ['#','Laje','Comp. (X)','Larg. (Y)','Área','Linhas V/H','Conf.','Link'],
                           rows, guide_rel, len(slabs))
    (base / 'index.html').write_text(idx_html, encoding='utf-8')
    print(f'[LAJ] lajes: {len(slabs)} fichas enriquecidas')
    return len(slabs)

# ─── Cortes section ─────────────────────────────────────────────────────────

def gen_corte_ficha(corte, idx, all_cortes, guide_rel, n2_lv):
    uid  = corte.get('uid', '')
    beam = corte.get('beam_name', '?')
    slug = f'{beam}_{uid[-6:] if len(uid) > 6 else uid}'.replace(' ', '_')
    prev = f'{all_cortes[idx-1]["_slug"]}.html' if idx > 0 else None
    nxt  = f'{all_cortes[idx+1]["_slug"]}.html' if idx < len(all_cortes)-1 else None
    pos  = f'{idx+1} / {len(all_cortes)} — {beam}'

    sb_items = [(c['_slug'], c.get('beam_name','?'), f'{c["_slug"]}.html') for c in all_cortes]
    sb = sidebar(sb_items, idx, 'Visão de Cortes', guide_rel, back='../index.html')
    nb = navbar(prev, nxt, pos)

    conf     = corte.get('conf_pct', 0)
    own_l    = corte.get('own_laje', '—') or '—'
    neigh_l  = corte.get('neigh_laje', '—') or '—'
    beam_h   = corte.get('beam_h', '—')
    status   = corte.get('status', '—')
    atencao  = corte.get('atencao', '') or ''
    beam_h_s = fmt_cm(beam_h)
    conf_cls = 'ok' if int(conf) >= 70 else 'warn'

    # N2 LV data for this beam (section_views)
    n2 = n2_lv.get(beam, {})
    sect_views = n2.get('section_views', [])
    tipo_viga  = n2.get('tipo_viga', '')
    h_A = n2.get('h_A'); h_B = n2.get('h_B')
    b_geom = n2.get('b_geom')
    laje_sup_A = n2.get('laje_sup_A'); laje_inf_A = n2.get('laje_inf_A')
    laje_sup_B = n2.get('laje_sup_B'); laje_inf_B = n2.get('laje_inf_B')

    sa_body = (
        kv('Viga', beam, 'hi')
        + kv('Confiança SA (%)', f'{conf}%', conf_cls)
        + kv('Laje própria (own_laje)', own_l)
        + kv('Laje vizinha (neigh_laje)', neigh_l)
        + kv('Altura da viga', beam_h_s)
        + kv('Status', status)
        + (kv('Atenção', atencao) if atencao else '')
    )

    n2_body = ''
    if n2:
        n2_body = (
            conf_badge_kv('Confiança N2', n2.get('_confianca'))
            + kv_raw('Tipo de viga', tipo_viga_tag(tipo_viga))
            + kv('Largura da seção (b_geom)', fmt_cm(b_geom))
            + kv('Altura lateral A (h_A)', fmt_cm(h_A))
            + kv('Altura lateral B (h_B)', fmt_cm(h_B))
            + kv('Laje sup. A', fmt_cm(laje_sup_A))
            + kv('Laje inf. A', fmt_cm(laje_inf_A))
            + kv('Laje sup. B', fmt_cm(laje_sup_B))
            + kv('Laje inf. B', fmt_cm(laje_inf_B))
            + kv('Nº seções transversais', str(len(sect_views)))
        )

    # section_views table
    sv_body = ''
    if sect_views:
        sv_body = '<table><tr><th>#</th><th>Label</th><th>h_A</th><th>h_B</th><th>b</th><th>Laje sup A</th><th>Laje inf A</th><th>Topologia</th></tr>'
        for i, sv in enumerate(sect_views[:6]):
            sv_body += (f'<tr><td>{i+1}</td><td>{e(sv.get("label",""))}</td>'
                        f'<td>{fmt_cm(sv.get("h_A"))}</td><td>{fmt_cm(sv.get("h_B"))}</td>'
                        f'<td>{fmt_cm(sv.get("b"))}</td>'
                        f'<td>{fmt_cm(sv.get("laje_sup_A"))}</td><td>{fmt_cm(sv.get("laje_inf_A"))}</td>'
                        f'<td>{e(sv.get("topology",""))}</td></tr>')
        sv_body += '</table>'

    html = head(f'Corte — {beam}')
    html += f'<body class="L"><div style="display:flex;height:100vh;overflow:hidden;">{sb}\n<div class="main">{nb}\n<div class="body">'
    html += f'<h1>Visão de Corte — {e(beam)}</h1>'
    html += f'<div class="info"><b>Visão de Corte (VC):</b> corte transversal detectado na lateral da viga. <code>own_laje</code> = laje do próprio vão; <code>neigh_laje</code> = laje do vão vizinho.</div>'
    html += sec('SA — Structural Analyzer', sa_body, 'src-sa')
    if n2_body:
        html += sec('N2 — Ficha LV Motor Reverso (dados desta viga)', n2_body, 'src-n2')
    if sv_body:
        html += sec('N2 — Seções Transversais (section_views)', sv_body, 'src-n2')
    html += f'<a class="g" href="{e(guide_rel)}">📖 Guia Visão de Cortes</a>'
    html += '</div></div></div>\n</body></html>'
    return slug, html

def build_cortes_section(estado, n2_lv):
    cortes = estado['cortes']
    base = OUTPUT_DIR / 'visao_cortes'
    base.mkdir(parents=True, exist_ok=True)
    guide_rel = 'interpretacao_cortes.html'
    for c in cortes:
        uid = c.get('uid', ''); beam = c.get('beam_name', '?')
        c['_slug'] = f'{beam}_{uid[-6:] if len(uid) > 6 else uid}'.replace(' ', '_')
    for idx, corte in enumerate(cortes):
        slug, html = gen_corte_ficha(corte, idx, cortes, guide_rel, n2_lv)
        (base / f'{slug}.html').write_text(html, encoding='utf-8')
    rows = ''
    for i, c in enumerate(cortes):
        conf = c.get('conf_pct', 0)
        n2 = n2_lv.get(c.get('beam_name',''), {})
        tv = n2.get('tipo_viga', '—') or '—'
        rows += (f'<tr><td>{i+1}</td><td>{e(c.get("beam_name","?"))}</td>'
                 f'<td>{conf}%</td><td>{e(c.get("own_laje","—"))}</td>'
                 f'<td>{e(c.get("neigh_laje","—"))}</td>'
                 f'<td>{fmt_cm(c.get("beam_h"))}</td><td>{e(tv)}</td>'
                 f'<td>{e(c.get("status","—"))}</td>'
                 f'<td><a href="{e(c["_slug"])}.html">→</a></td></tr>')
    idx_html = _page_index('Visão de Cortes', ['#','Viga','Conf.','Laje própria','Laje vizinha','Altura viga','Tipo viga','Status','Link'],
                           rows, guide_rel, len(cortes))
    (base / 'index.html').write_text(idx_html, encoding='utf-8')
    print(f'[VC] visao_cortes: {len(cortes)} fichas enriquecidas')
    return len(cortes)

# ─── index helpers ───────────────────────────────────────────────────────────

def _page_index(title, headers, rows, guide_href, count, back='../index.html'):
    ths = ''.join(f'<th>{e(h)}</th>' for h in headers)
    html = head(title)
    html += f'<body class="P"><div class="pg">'
    html += f'<a class="bk" href="{e(back)}">← índice geral</a>'
    html += f'<h1>{e(title)}</h1>'
    html += (f'<div class="intro">{count} itens &nbsp;&nbsp;'
             f'<a class="g" href="{e(guide_href)}">📖 Guia de Interpretação</a></div>')
    html += f'<table><tr>{ths}</tr>{rows}</table>'
    html += '</div></body></html>'
    return html

def build_main_index(estado):
    obra = estado.get('obra', OBRA); pav = estado.get('pavimento', PAV)
    n_pil = len(estado.get('pilares', []))
    n_slab = len(estado.get('slabs', []))
    n_cortes = len(estado.get('cortes', []))
    segs = estado.get('segmentos', {})
    n_fv = len(segs.get('fundo', []))
    n_ap = len(segs.get('lateral_a_para', []))
    n_bp = len(segs.get('lateral_b_para', []))
    n_aP = len(segs.get('lateral_a_passa', []))
    n_bP = len(segs.get('lateral_b_passa', []))

    sections = [
        ('🏛 Pilares',           f'{n_pil} fichas',   'pilares/index.html',                              'pilares/interpretacao_abcd.html'),
        ('🏛 Pilares Especiais', '2 fichas',           'pilares_especiais/index.html',                    'pilares_especiais/interpretacao_especiais.html'),
        ('▬ Lajes (LAJ)',        f'{n_slab} fichas',  'lajes/index.html',                                'lajes/interpretacao_lajes.html'),
        ('✂ Visão de Cortes',    f'{n_cortes} fichas','visao_cortes/index.html',                         'visao_cortes/interpretacao_cortes.html'),
        ('⬇ Fundos de Viga(FV)', f'{n_fv} fichas',    'fundos_viga/index.html',                          'fundos_viga/interpretacao_fundos.html'),
        ('← LV A-Para',          f'{n_ap} segs.',     'laterais_viga/a_para/index.html',                 'laterais_viga/interpretacao_laterais.html'),
        ('→ LV B-Para',          f'{n_bp} segs.',     'laterais_viga/b_para/index.html',                 'laterais_viga/interpretacao_laterais.html'),
        ('↔ LV A-Passa',         f'{n_aP} segs.',     'laterais_viga/a_passa/index.html',                'laterais_viga/interpretacao_laterais.html'),
        ('↔ LV B-Passa',         f'{n_bP} segs.',     'laterais_viga/b_passa/index.html',                'laterais_viga/interpretacao_laterais.html'),
        ('📐 Convenção de Níveis','—',                 'convencao_niveis/interpretacao_niveis.html',      'convencao_niveis/interpretacao_niveis.html'),
    ]

    cards = ''
    for label, count, href, guide_href in sections:
        cards += (f'<div class="sec"><div class="sec-t">{e(label)}</div><div class="sec-b">'
                  f'<div class="kv"><span class="k">Itens</span><span class="v hi">{e(count)}</span></div>'
                  f'<a class="g" href="{e(href)}">Abrir fichas →</a>'
                  f'<br><a class="g" href="{e(guide_href)}" style="margin-top:4px">📖 Guia</a>'
                  f'</div></div>')

    html = head(f'{obra} — {pav} — Índice Geral')
    html += f'<body class="P"><div class="pg">'
    html += f'<h1>{e(obra)} &mdash; {e(pav)}</h1>'
    html += (f'<div class="intro">Fichas geradas pelo SA Headless + Motor Reverso. '
             f'<b>Três fontes de dados</b> por ficha: <span class="src-n1 badge-src">N1</span> Fase-4 JSON &nbsp; '
             f'<span class="src-n2 badge-src">N2</span> Motor Reverso (DB) &nbsp; '
             f'<span class="src-sa badge-src">SA</span> Structural Analyzer.</div>')
    html += '<h2>Seções</h2>'
    html += f'<div class="grid3">{cards}</div>'
    html += '</div></body></html>'
    (OUTPUT_DIR / 'index.html').write_text(html, encoding='utf-8')
    print('[IDX] index.html atualizado')

# ─── main ────────────────────────────────────────────────────────────────────

def main():
    print('Carregando dados...', flush=True)
    estado  = load_estado()
    print('  estado OK')
    n2_lv   = load_n2_fichas('LV')
    print(f'  N2 LV: {len(n2_lv)} fichas')
    n2_fv   = load_n2_fichas('FV')
    print(f'  N2 FV: {len(n2_fv)} fichas')
    n2_laj  = load_n2_fichas('LAJ')
    print(f'  N2 LAJ: {len(n2_laj)} fichas')
    fase4_lv  = load_fase4_lv()
    print(f'  Fase4 LV: {len(fase4_lv)} JSONs')
    fase4_fv  = load_fase4_fv()
    print(f'  Fase4 FV: {len(fase4_fv)} JSONs')
    fase4_laj = load_fase4_laj()
    print(f'  Fase4 LAJ: {len(fase4_laj)} JSONs')

    total = 0
    total += build_lv_section(estado, n2_lv, fase4_lv)
    total += build_fv_section(estado, n2_fv, fase4_fv)
    total += build_laj_section(estado, n2_laj, fase4_laj)
    total += build_cortes_section(estado, n2_lv)
    build_main_index(estado)

    print(f'\nConcluido. Total fichas geradas: {total}', flush=True)
    print(f'  Output: {OUTPUT_DIR}', flush=True)

if __name__ == '__main__':
    main()
