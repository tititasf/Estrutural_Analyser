# -*- coding: utf-8 -*-
"""Viewer unico de depuracao das laterais: SA x N3 x N4, por viga e segmento.

Um so' HTML, com tres niveis de aba:

    VIGA  ->  SEGMENTO  ->  {SA | N3 | N4}

A ficha (os numeros) aparece logo ABAIXO do desenho e troca junto com a aba,
para que o dono case segmento a segmento sem abrir tres paginas.

As tres camadas, e de onde cada uma vem:

    SA   o recorte do DXF ESTRUTURAL em volta do segmento, que e' o que o
         interpretador leu. E' a unica das tres que nao e' desenho de forma.
    N3   `LV_preview_{viga}_{Para|Passa}_VIEW_{A|B}.dxf`, gerado do N1 pelo
         mesmo caminho do headless (`_generate_lv_n3_nova_previews`).
    N4   `LV_preview_{viga}_VIEW_{A|B}.dxf` da rodada aprovada pelo dono —
         a REFERENCIA.

Uso:
    python scripts/arete/build_lv_debug_viewer.py \
        --n3 <dir com os DXF N3> --n4 <dir com os DXF N4> --out <arquivo.html>
"""
from __future__ import annotations

import argparse
import base64
import html as _html
import io
import json
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402
import ezdxf                              # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext          # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend     # noqa: E402

ARETE = Path(__file__).resolve().parent
SCRIPTS = ARETE.parent
REPO = SCRIPTS.parent
for _p in (REPO, SCRIPTS, ARETE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.core.lv_generation_contract import (  # noqa: E402
    build_lv_generation_contracts,
)

DB_PADRAO = 'D:/Agente-cad-PYSIDE/project_data.vision'
PROJETO = 'dd238e47-1dc6-4f63-a760-4e7ce19a7386'
VIGAS = ('V301', 'V302', 'V303', 'V304')
DXF_ESTRUTURAL = (
    'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes/'
    'TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA/torre_1.dxf'
)


# ───────────────────────────── render ─────────────────────────────

_CACHE_DOC: dict = {}


def _doc(caminho: str):
    if caminho not in _CACHE_DOC:
        _CACHE_DOC[caminho] = ezdxf.readfile(caminho)
    return _CACHE_DOC[caminho]


def _svg(caminho: str, janela=None, largura=11.0, altura=4.2) -> str:
    """PNG embutido (data URI) do DXF, opcionalmente recortado na janela.

    PNG, nao SVG, de proposito. O recorte do DXF ESTRUTURAL em volta de um
    segmento mostra uma janela pequena, mas o SVG sai com TODAS as entidades da
    prancha — a primeira versao desta pagina deu 211 MB. Em PNG a mesma pagina
    cabe em poucos MB, e para casar segmento com desenho a resolucao basta.
    """
    try:
        doc = _doc(str(caminho))
    except Exception:
        return ''
    fig = plt.figure(figsize=(largura, altura), dpi=104)
    ax = fig.add_axes([0, 0, 1, 1])
    try:
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(
            doc.modelspace(), finalize=False,
        )
        if janela:
            x0, y0, x1, y1 = janela
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
        else:
            ax.autoscale_view()
        ax.set_axis_off()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', facecolor='#0d0d0d')
        return ('data:image/png;base64,'
                + base64.b64encode(buf.getvalue()).decode('ascii'))
    except Exception:
        return ''
    finally:
        plt.close(fig)


def _svg_tag(svg: str) -> str:
    if not svg:
        return ('<div class="vazio">artefato ausente — '
                'nao ha desenho para esta combinacao</div>')
    return f'<img loading="lazy" src="{svg}" alt="">'


# ───────────────────────────── dados ─────────────────────────────

def _coletar(db: str, n3_dir: Path, n4_dir: Path) -> list[dict]:
    conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    bboxes = {}
    for nome, pts in conn.execute(
            'SELECT name, points_json FROM pillars WHERE project_id=?',
            (PROJETO,)):
        try:
            p = json.loads(pts or '[]')
            xs = [float(q[0]) for q in p]
            ys = [float(q[1]) for q in p]
            if xs:
                bboxes[str(nome)] = (min(xs), min(ys), max(xs), max(ys))
        except Exception:
            continue

    from arete.gerar_lv_n4_fichas import _entry_from_live_recorte

    out = []
    for viga in VIGAS:
        row = conn.execute(
            'SELECT data_json FROM beams WHERE project_id=? AND name=?',
            (PROJETO, viga)).fetchone()
        if not row:
            continue
        beam = json.loads(row[0] or '{}')
        contratos = build_lv_generation_contracts(
            beam, beam_name=viga, floor='13_PAV', pillar_bboxes=bboxes)
        try:
            n4 = _entry_from_live_recorte(viga)
        except Exception:
            n4 = {}
        out.append({
            'viga': viga,
            'rotulo_dim': (beam.get('fields') or {}).get('dimensao'),
            'contratos': contratos,
            'n4': n4,
            'n3_dir': n3_dir,
            'n4_dir': n4_dir,
        })
    return out


def _janela_do_segmento(pontos, folga=90.0):
    if not pontos or len(pontos) < 2:
        return None
    xs = [float(p[0]) for p in pontos]
    ys = [float(p[1]) for p in pontos]
    x0, x1 = min(xs) - folga, max(xs) + folga
    y0, y1 = min(ys) - folga, max(ys) + folga
    if x1 - x0 < 260:
        m = (x0 + x1) / 2
        x0, x1 = m - 130, m + 130
    if y1 - y0 < 130:
        m = (y0 + y1) / 2
        y0, y1 = m - 65, m + 65
    return (x0, y0, x1, y1)


def _tab_ficha(pares: list[tuple[str, object]]) -> str:
    linhas = ''.join(
        f'<tr><th>{_html.escape(str(k))}</th>'
        f'<td>{_html.escape(str(v))}</td></tr>' for k, v in pares)
    return f'<table class="ficha">{linhas}</table>'


# ───────────────────────────── html ─────────────────────────────

CSS = """
*{box-sizing:border-box}
/* `display:flex` em `.barra` vence o `display:none` que o atributo `hidden`
   aplica pelo user-agent — sem este `!important` TODAS as barras de nivel 3
   aparecem de uma vez. */
[hidden]{display:none!important}
body{margin:0;background:#0d0d0d;color:#d8d8d8;
     font:13px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace}
h1{font-size:15px;margin:0;padding:12px 16px;border-bottom:1px solid #262626;
   color:#7fd1b9;letter-spacing:.4px}
.aviso{padding:8px 16px;background:#1a1408;border-bottom:1px solid #3a2d10;
       color:#e0b060;font-size:12px}
.barra{display:flex;flex-wrap:wrap;gap:6px;padding:9px 16px;
       border-bottom:1px solid #262626}
.barra.n2{background:#111}
.barra.n3{background:#141414}
button.aba{background:#1b1b1b;border:1px solid #303030;color:#bbb;
           padding:5px 11px;border-radius:4px;cursor:pointer;font:inherit}
button.aba:hover{background:#242424;color:#eee}
button.aba.on{background:#17392f;border-color:#2f7a63;color:#8fe0c4}
.painel{padding:14px 16px}
.desenho{background:#0d0d0d;border:1px solid #262626;border-radius:6px;
         overflow:auto;margin-bottom:12px}
.desenho img{display:block;max-width:100%;height:auto}
.rot{padding:6px 10px;color:#7fd1b9;font-size:12px}
.arq{color:#5f5f5f;margin-left:8px}
.vazio{padding:38px;text-align:center;color:#8a6b4a}
table.ficha{border-collapse:collapse;width:100%;max-width:760px}
table.ficha th{text-align:left;padding:4px 10px 4px 0;color:#8a8a8a;
               font-weight:400;white-space:nowrap;vertical-align:top;width:220px}
table.ficha td{padding:4px 0;color:#e2e2e2}
table.ficha tr+tr th,table.ficha tr+tr td{border-top:1px solid #1e1e1e}
.legenda{padding:6px 16px 14px;color:#6f6f6f;font-size:11.5px}
"""

JS = """
function mostrar(prefixo){
  document.querySelectorAll('[data-nivel]').forEach(function(el){
    var chave = el.getAttribute('data-chave');
    var on = chave === prefixo || prefixo.indexOf(chave + '|') === 0;
    if(el.tagName === 'BUTTON'){ el.classList.toggle('on', on); }
  });
  document.querySelectorAll('[data-grupo]').forEach(function(el){
    var g = el.getAttribute('data-grupo');
    el.hidden = !(prefixo === g || prefixo.indexOf(g + '|') === 0
                  || g.indexOf(prefixo + '|') === 0);
  });
  document.querySelectorAll('[data-folha]').forEach(function(el){
    el.hidden = el.getAttribute('data-folha') !== prefixo;
  });
  try{ localStorage.setItem('lv_debug_aba', prefixo); }catch(e){}
}
window.addEventListener('DOMContentLoaded', function(){
  var inicial = null;
  try{ inicial = localStorage.getItem('lv_debug_aba'); }catch(e){}
  var primeiro = document.querySelector('[data-folha]');
  if(!inicial || !document.querySelector('[data-folha="'+inicial+'"]')){
    inicial = primeiro ? primeiro.getAttribute('data-folha') : '';
  }
  if(inicial){ mostrar(inicial); }
});
"""


def montar(dados: list[dict], destino: Path) -> Path:
    partes = [
        '<!doctype html><meta charset="utf-8">',
        '<title>LV — depuracao SA x N3 x N4</title>',
        f'<style>{CSS}</style>',
        '<h1>Laterais de viga — depuracao por segmento</h1>',
        '<div class="aviso">O <b>N4</b> e a referencia (aprovado pelo dono). '
        'O <b>N3</b> sai do N1/SA pelo mesmo caminho do headless, nos dois '
        'comportamentos. O quadro <b>SA</b> mostra o recorte do DXF '
        '<b>estrutural</b> que o interpretador leu — nao e desenho de '
        'forma.</div>',
    ]

    partes.append('<div class="barra">')
    for d in dados:
        v = d["viga"]
        partes.append(
            '<button class="aba" data-nivel="1" data-chave="%s" '
            'onclick="mostrar(\'%s\')">%s</button>' % (v, v, v))
    partes.append('</div>')

    CAMADAS = ('SA-Para', 'SA-Passa', 'N3-Para', 'N3-Passa',
               'N3-Corte', 'N4-Corte', 'N4-Segmentos')

    folhas = []
    for d in dados:
        viga, ct = d['viga'], d['contratos']
        n3, n4d = Path(d['n3_dir']), Path(d['n4_dir'])

        # As VISTAS nao mudam por segmento — renderiza uma vez por viga.
        vistas = {}
        grupos = (
            ('N3-Para', [('N3 Para · vista A', n3 / ('LV_preview_%s_Para_VIEW_A.dxf' % viga)),
                         ('N3 Para · vista B', n3 / ('LV_preview_%s_Para_VIEW_B.dxf' % viga))]),
            ('N3-Passa', [('N3 Passa · vista A', n3 / ('LV_preview_%s_Passa_VIEW_A.dxf' % viga)),
                          ('N3 Passa · vista B', n3 / ('LV_preview_%s_Passa_VIEW_B.dxf' % viga))]),
            ('N3-Corte', [('N3 Para · visao de corte', n3 / ('LV_preview_%s_Para_CORTE.dxf' % viga)),
                          ('N3 Passa · visao de corte', n3 / ('LV_preview_%s_Passa_CORTE.dxf' % viga))]),
            ('N4-Corte', [('N4 · visao de corte', n4d / ('LV_preview_%s_CORTE.dxf' % viga))]),
            ('N4-Segmentos', [('N4 · vista A', n4d / ('LV_preview_%s_VIEW_A.dxf' % viga)),
                              ('N4 · vista B', n4d / ('LV_preview_%s_VIEW_B.dxf' % viga))]),
        )
        for rot, cam in grupos:
            blocos = []
            for titulo, caminho in cam:
                alt = 3.0 if 'Corte' in rot else 4.2
                svg = _svg(str(caminho), altura=alt) if caminho.exists() else ''
                blocos.append(
                    '<div class="rot">%s <span class="arq">%s</span></div>'
                    '<div class="desenho">%s</div>'
                    % (_html.escape(titulo), caminho.name, _svg_tag(svg)))
            vistas[rot] = ''.join(blocos)

        segs_por_comp = {c: ct[c]['A']['structural_segments']
                         for c in ('Para', 'Passa')}
        n_seg = max(len(segs_por_comp['Para']), len(segs_por_comp['Passa']))

        partes.append('<div class="barra n2" data-grupo="%s" hidden>' % viga)
        for i in range(1, n_seg + 1):
            ch = '%s|S%d' % (viga, i)
            partes.append(
                '<button class="aba" data-nivel="2" data-chave="%s" '
                'onclick="mostrar(\'%s\')">S%d</button>' % (ch, ch, i))
        partes.append('</div>')

        for i in range(1, n_seg + 1):
            ch = '%s|S%d' % (viga, i)
            partes.append('<div class="barra n3" data-grupo="%s" hidden>' % ch)
            for cam in CAMADAS:
                fo = '%s|%s' % (ch, cam)
                partes.append(
                    '<button class="aba" data-nivel="3" data-chave="%s" '
                    'onclick="mostrar(\'%s\')">%s</button>'
                    % (fo, fo, cam.replace('-', ' · ')))
            partes.append('</div>')

            for comp in ('Para', 'Passa'):
                segs = segs_por_comp[comp]
                c = ct[comp]['A']
                if i <= len(segs):
                    seg = segs[i - 1]
                    pts = seg.get('points') or []
                    svg = _svg(DXF_ESTRUTURAL, _janela_do_segmento(pts))
                    idx = int(seg.get('segment_index') or 0)
                    meus = [p for p in c['panels']
                            if int(p.get('structural_segment_index') or 0) == idx]
                    ficha = _tab_ficha([
                        ('viga · segmento', '%s · S%d de %d' % (viga, i, len(segs))),
                        ('comportamento', comp),
                        ('comprimento estrutural (N1)',
                         '%.1f cm' % float(seg.get('width') or 0)),
                        ('pontos', ' -> '.join(
                            '(%.1f, %.1f)' % (float(q[0]), float(q[1]))
                            for q in pts[:2])),
                        ('paineis que o N3 poe aqui',
                         ', '.join('%.1f' % float(p['width']) for p in meus)
                         or '(nenhum)'),
                        ('source_key', seg.get('source_key')),
                        ('secao (rotulo da viga)', d['rotulo_dim']),
                        ('h_section -> altura da face',
                         '%s -> %s' % (c.get('h_section'), c.get('total_height'))),
                        ('regra de altura', c.get('h_face_rule')),
                        ('total da face (N3)', '%.1f cm' % float(c['total_length'])),
                    ])
                    corpo = ('<div class="desenho">%s</div>%s'
                             '<div class="legenda">Recorte do DXF ESTRUTURAL em '
                             'volta deste segmento — a evidencia que o SA leu no '
                             'comportamento %s.</div>' % (_svg_tag(svg), ficha, comp))
                else:
                    corpo = ('<div class="vazio">o comportamento %s nao tem '
                             'segmento S%d (tem %d)</div>' % (comp, i, len(segs)))
                folhas.append(
                    '<div class="painel" data-folha="%s|SA-%s" hidden>%s</div>'
                    % (ch, comp, corpo))

            for cam in ('N3-Para', 'N3-Passa', 'N3-Corte', 'N4-Corte',
                        'N4-Segmentos'):
                if cam in ('N3-Para', 'N3-Passa'):
                    comp = cam.split('-')[1]
                    c = ct[comp]['A']
                    segs = segs_por_comp[comp]
                    meus = []
                    if i <= len(segs):
                        idx = int(segs[i - 1].get('segment_index') or 0)
                        meus = [p for p in c['panels']
                                if int(p.get('structural_segment_index') or 0) == idx]
                    extra = _tab_ficha([
                        ('comportamento', comp),
                        ('paineis DESTE segmento (S%d)' % i,
                         ', '.join('%.1f' % float(p['width']) for p in meus)
                         or '(nenhum)'),
                        ('altura da face', '%.1f cm' % float(c['total_height'])),
                        ('total da face', '%.1f cm' % float(c['total_length'])),
                        ('segmentos estruturais', c['structural_segment_count']),
                        ('paineis na face', len(c['panels'])),
                        ('generation_ready', c.get('generation_ready')),
                    ])
                    leg = ('Vista inteira do N3. Os paineis listados sao os que '
                           'a conversao atribuiu a ESTE segmento.')
                elif cam == 'N3-Corte':
                    extra = _tab_ficha([
                        ('h_section (Para / Passa)',
                         '%s / %s' % (ct['Para']['A'].get('h_section'),
                                      ct['Passa']['A'].get('h_section'))),
                        ('altura da face (Para / Passa)',
                         '%s / %s' % (ct['Para']['A'].get('total_height'),
                                      ct['Passa']['A'].get('total_height'))),
                        ('regra', ct['Para']['A'].get('h_face_rule')),
                        ('secao medida no N2', d['n4'].get('h_section_all')),
                    ])
                    leg = 'Visao de corte do N3, nos dois comportamentos.'
                else:
                    us_a = [u for u in (d['n4'].get('face_units') or [])
                            if str(u.get('side') or '').upper() == 'A']
                    us_b = [u for u in (d['n4'].get('face_units') or [])
                            if str(u.get('side') or '').upper() == 'B']

                    def _res(us):
                        larg = [round(float(p.get('width', 0) or 0), 1)
                                for u in us for p in (u.get('panels') or [])]
                        alt = sorted({round(float(u.get('h_total') or 0), 1)
                                      for u in us
                                      if float(u.get('h_total') or 0) > 0})
                        return larg, alt

                    la, aa = _res(us_a)
                    lb, ab = _res(us_b)
                    extra = _tab_ficha([
                        ('lado A — desenhos', len(us_a)),
                        ('lado A — rotulos', ', '.join(
                            str(u.get('label') or '(sem)') for u in us_a)),
                        ('lado A — larguras', ', '.join(map(str, la))),
                        ('lado A — total', '%.1f cm' % sum(la)),
                        ('lado A — alturas (corpo+laje)', aa),
                        ('lado B — desenhos', len(us_b)),
                        ('lado B — rotulos', ', '.join(
                            str(u.get('label') or '(sem)') for u in us_b)),
                        ('lado B — larguras', ', '.join(map(str, lb))),
                        ('lado B — total', '%.1f cm' % sum(lb)),
                        ('lado B — alturas (corpo+laje)', ab),
                        ('secao medida no N2', d['n4'].get('h_section_all')),
                    ])
                    leg = ('REFERENCIA. O N4 nao numera segmentos: casar S%d '
                           'com o desenho e o que esta pagina existe para '
                           'fazer.' % i)
                folhas.append(
                    '<div class="painel" data-folha="%s|%s" hidden>%s%s'
                    '<div class="legenda">%s</div></div>'
                    % (ch, cam, vistas[cam], extra, leg))

    partes.extend(folhas)
    partes.append('<script>%s</script>' % JS)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text('\n'.join(partes), encoding='utf-8')
    return destino


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=DB_PADRAO)
    ap.add_argument('--n3', required=True)
    ap.add_argument('--n4', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    dados = _coletar(a.db, Path(a.n3), Path(a.n4))
    destino = montar(dados, Path(a.out))
    print('HTML', destino)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
