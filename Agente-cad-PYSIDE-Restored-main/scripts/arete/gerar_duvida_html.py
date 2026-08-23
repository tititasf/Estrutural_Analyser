#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera a ficha HTML de uma dúvida de interpretação, para decisão do dono.

Padrão nascido do caso ``V313 × P29`` (2026-08-20), que o dono aprovou: a
dúvida só é decidível olhando o desenho, então a ficha entrega **o recorte
real do DXF** com os elementos em disputa destacados, as leituras possíveis
lado a lado e o que muda em cada uma.

Regras que a ficha respeita:

- SVG com pan/zoom por **viewBox** (padrão FV V302); nunca ``transform:scale``;
- geometria vem do DXF, não de bitmap nem de reconstrução;
- uma pergunta por ficha, respondível em uma frase.

Uso::

    from scripts.arete.gerar_duvida_html import Duvida, Destaque, gerar

    gerar(Duvida(
        titulo="V313 chega em P29?",
        pergunta="A viga V313 chega no pilar P29, mesmo com V306 no meio?",
        dxf=Path(...), janela=(1930, 1975, 2240, 2200),
        destaques=[Destaque("P29 — pilar 24/66", 2038, 1963, 2062, 2029, "#b91c1c")],
        leituras=[...], saida=Path(...),
    ))
"""
from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

LAYER_COLOR = {
    "3": "#111827", "7": "#b91c1c", "9": "#2563eb",
    "2": "#9ca3af", "4": "#15803d", "6": "#ea580c", "8": "#7c3aed",
}


@dataclass
class Destaque:
    """Região do desenho a realçar, em coordenadas do DXF."""
    rotulo: str
    x0: float
    y0: float
    x1: float
    y1: float
    cor: str
    tracejado: bool = False


@dataclass
class Nota:
    """Texto ancorado numa coordenada do desenho."""
    texto: str
    x: float
    y: float
    cor: str = "#a16207"


@dataclass
class Leitura:
    """Uma das interpretações possíveis, com sua consequência."""
    titulo: str
    resumo: str
    consequencia: str
    cor: str = "#2563eb"


@dataclass
class Duvida:
    titulo: str
    pergunta: str
    dxf: Path
    janela: tuple[float, float, float, float]
    saida: Path
    legenda: str = ""
    destaques: list[Destaque] = field(default_factory=list)
    notas: list[Nota] = field(default_factory=list)
    leituras: list[Leitura] = field(default_factory=list)
    contexto: str = ""


def _svg(duvida: Duvida) -> str:
    import ezdxf

    x0, y0, x1, y1 = duvida.janela
    doc = ezdxf.readfile(str(duvida.dxf))
    linhas: list[str] = []
    textos: list[str] = []

    def traco(a, b, layer: str) -> None:
        if max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1:
            return
        if max(a[1], b[1]) < y0 or min(a[1], b[1]) > y1:
            return
        cor = LAYER_COLOR.get(layer, "#d1d5db")
        largura = 1.8 if layer in ("3", "7") else 0.8
        linhas.append(
            f'<line x1="{a[0]:.2f}" y1="{-a[1]:.2f}" x2="{b[0]:.2f}" '
            f'y2="{-b[1]:.2f}" stroke="{cor}" stroke-width="{largura}"/>'
        )

    for e in doc.modelspace():
        tipo = e.dxftype()
        if tipo == "LINE":
            traco((e.dxf.start[0], e.dxf.start[1]),
                  (e.dxf.end[0], e.dxf.end[1]), e.dxf.layer)
        elif tipo in ("LWPOLYLINE", "POLYLINE"):
            try:
                pontos = [(p[0], p[1]) for p in e.get_points("xy")]
            except Exception:
                continue
            for a, b in zip(pontos, pontos[1:]):
                traco(a, b, e.dxf.layer)
        elif tipo in ("TEXT", "MTEXT"):
            try:
                texto = (e.plain_text() if tipo == "MTEXT" else e.dxf.text).strip()
                p = e.dxf.insert
            except Exception:
                continue
            if texto and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                textos.append(
                    f'<text x="{p[0]:.2f}" y="{-p[1]:.2f}" font-size="9" '
                    f'fill="#15803d">{_html.escape(texto)}</text>'
                )

    realces = [
        f'<rect x="{d.x0:.2f}" y="{-d.y1:.2f}" width="{d.x1 - d.x0:.2f}" '
        f'height="{d.y1 - d.y0:.2f}" fill="{d.cor}" fill-opacity="0.16" '
        f'stroke="{d.cor}" stroke-width="1.4"'
        + (' stroke-dasharray="4 3"' if d.tracejado else "")
        + "/>"
        for d in duvida.destaques
    ]
    notas = [
        f'<text x="{n.x:.2f}" y="{-n.y:.2f}" font-size="9" fill="{n.cor}" '
        f'font-weight="700">{_html.escape(n.texto)}</text>'
        for n in duvida.notas
    ]
    return (
        f'<svg viewBox="{x0} {-y1} {x1 - x0} {y1 - y0}" '
        'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{_html.escape(duvida.titulo)}">'
        + "".join(realces + linhas + textos + notas)
        + "</svg>"
    )


_CSS = """
:root{--bg:#fff;--fg:#111827;--muted:#6b7280;--line:#e5e7eb;--card:#f9fafb;--warn:#a16207}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#0b0f16;--fg:#e5e7eb;--muted:#9ca3af;--line:#1f2937;--card:#111827;--warn:#fbbf24}}
:root[data-theme="dark"]{--bg:#0b0f16;--fg:#e5e7eb;--muted:#9ca3af;--line:#1f2937;
--card:#111827;--warn:#fbbf24}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);margin:0;padding:28px 20px 64px;
font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:19px;margin:34px 0 10px}
.sub{color:var(--muted);margin:0 0 26px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:18px 20px;margin:16px 0}
.q{border-left:5px solid var(--warn)}
.big{font-size:19px;font-weight:600;line-height:1.5}
figure{margin:0}
.viewer{border:1px solid var(--line);border-radius:10px;background:var(--bg);
overflow:hidden;touch-action:none}
.viewer svg{display:block;width:100%;height:auto;max-height:76vh;cursor:grab}
.viewer svg:active{cursor:grabbing}
figcaption{color:var(--muted);font-size:14px;margin-top:8px}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin:12px 0 0;padding:0;
list-style:none;font-size:14px}
.legend li{display:flex;align-items:center;gap:7px}
.sw{width:15px;height:15px;border-radius:4px;flex:none}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.opt{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:var(--card)}
.opt h3{margin:0 0 8px;font-size:17px}
.btn{font:inherit;font-size:14px;padding:6px 12px;border-radius:8px;cursor:pointer;
border:1px solid var(--line);background:var(--bg);color:var(--fg)}
"""

_JS = """
(function(){
  var svg=document.querySelector('#viewer svg'); if(!svg) return;
  var base=svg.getAttribute('viewBox').split(/\\s+/).map(Number);
  var cur=base.slice(), drag=null;
  function apply(){ svg.setAttribute('viewBox',cur.join(' ')); }
  svg.addEventListener('wheel',function(ev){
    ev.preventDefault();
    var r=svg.getBoundingClientRect();
    var mx=cur[0]+(ev.clientX-r.left)/r.width*cur[2];
    var my=cur[1]+(ev.clientY-r.top)/r.height*cur[3];
    var k=ev.deltaY>0?1.12:1/1.12;
    cur[0]=mx-(mx-cur[0])*k; cur[1]=my-(my-cur[1])*k;
    cur[2]*=k; cur[3]*=k; apply();
  },{passive:false});
  svg.addEventListener('pointerdown',function(ev){
    drag={x:ev.clientX,y:ev.clientY,vb:cur.slice()};
    svg.setPointerCapture(ev.pointerId);
  });
  svg.addEventListener('pointermove',function(ev){
    if(!drag) return;
    var r=svg.getBoundingClientRect();
    cur[0]=drag.vb[0]-(ev.clientX-drag.x)/r.width*cur[2];
    cur[1]=drag.vb[1]-(ev.clientY-drag.y)/r.height*cur[3];
    apply();
  });
  svg.addEventListener('pointerup',function(){drag=null;});
  document.getElementById('reset').addEventListener('click',function(){
    cur=base.slice(); apply();
  });
})();
"""


def gerar(duvida: Duvida) -> Path:
    """Escreve a ficha e devolve o caminho."""
    esc = _html.escape
    legenda = "".join(
        f'<li><span class="sw" style="background:{d.cor}"></span>{esc(d.rotulo)}</li>'
        for d in duvida.destaques
    )
    leituras = "".join(
        f'<div class="opt" style="border-left:5px solid {l.cor}">'
        f"<h3>{esc(l.titulo)}</h3><p>{esc(l.resumo)}</p>"
        f"<p><strong>Se for essa:</strong> {esc(l.consequencia)}</p></div>"
        for l in duvida.leituras
    )
    contexto = (
        f'<h2>Contexto</h2><div class="card">{duvida.contexto}</div>'
        if duvida.contexto else ""
    )
    corpo = (
        '<div class="wrap">'
        f"<h1>{esc(duvida.titulo)}</h1>"
        '<p class="sub">Recorte real do DXF. Arraste para mover, role para dar zoom.</p>'
        f'<div class="card q"><p class="big">{esc(duvida.pergunta)}</p></div>'
        "<h2>O que o desenho mostra</h2>"
        f'<figure><div class="viewer" id="viewer">{_svg(duvida)}</div>'
        f'<figcaption>{esc(duvida.legenda)} '
        '<button class="btn" id="reset" type="button">Reenquadrar</button>'
        "</figcaption></figure>"
        f'<ul class="legend">{legenda}</ul>'
        + ("<h2>As leituras possíveis</h2>"
           f'<div class="cols">{leituras}</div>' if leituras else "")
        + contexto
        + '<h2>O que eu preciso</h2><div class="card q">'
        f'<p class="big">{esc(duvida.pergunta)}</p>'
        '<p style="color:var(--muted);margin-bottom:0">Uma frase basta.</p>'
        "</div></div>"
        f"<script>{_JS}</script>"
    )
    pagina = (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(duvida.titulo)}</title><style>{_CSS}</style></head>"
        f"<body>{corpo}</body></html>"
    )
    duvida.saida.parent.mkdir(parents=True, exist_ok=True)
    duvida.saida.write_text(pagina, encoding="utf-8")
    return duvida.saida
