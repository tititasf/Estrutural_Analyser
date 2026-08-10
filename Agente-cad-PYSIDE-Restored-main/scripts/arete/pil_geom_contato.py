#!/usr/bin/env python
"""Predicado de relação viga↔face do pilar — por ALINHAMENTO, como manda o doc.

Correções de 2026-08-07 (duas, ambas achadas conferindo o P24):

  (1) gap e extensão eram medidos separadamente → uma viga podia reportar
      "100% de contato na face C" e "gap de 80cm da face C" ao mesmo tempo.
      Agora é um predicado só.

  (2) ERRO CONCEITUAL: eu exigia *sobreposição* (toque de polígonos). O doc
      `INTERPRETACAO-PILARES-ABCD.md` é explícito:
        "a classificação é determinada pelo **alinhamento geométrico**,
         não pelo simples toque de polígonos"
      Uma viga N–S colinear com o pilar (mesma faixa de 19cm) tem suas paredes
      COINCIDINDO com as faces A e B — ela **passa** nas duas, mesmo que o
      contorno guardado no DB fique inteiramente ao sul do pilar.
      Caso real: V321 × P24 (o agente lia "sem base"; o correto é passa
      em AC/AD e BC/BD).

Discriminador: **direção de corrida da viga vs direção da face**.
  - mesma direção  + parede colinear + adjacência axial → PASSA (alinhada)
  - direção cruzada + encosta na face + extensão parcial → CHEGA (perpendicular)

Convenção de faces (docs/INTERPRETACAO-PILARES-ABCD.md):
  vertical:   A=oeste(x0) B=leste(x1) C=norte(y1) D=sul(y0)
  horizontal: A=sul(y0)   B=norte(y1) C=oeste(x0) D=leste(x1)
"""
from __future__ import annotations

from dataclasses import dataclass

TOL = 1.5  # cm


@dataclass
class Relacao:
    face: str
    tipo: str           # 'passa' (alinhada) | 'chega' (perpendicular)
    extensao: float     # contato ao longo da face (cm); passa alinhada pode ser 0
    face_len: float
    detalhe: str

    @property
    def fracao(self) -> float:
        return (self.extensao / self.face_len) if self.face_len else 0.0

    def __str__(self) -> str:
        return f"{self.face}: {self.tipo} — {self.detalhe}"


def _face_geom(fid: str, px0, py0, px1, py1, horizontal: bool):
    """(eixo_normal, coord_parede, span_ini, span_fim, direcao_da_face)."""
    if not horizontal:
        t = {"A": ("x", px0, py0, py1, "y"), "B": ("x", px1, py0, py1, "y"),
             "C": ("y", py1, px0, px1, "x"), "D": ("y", py0, px0, px1, "x")}
    else:
        t = {"A": ("y", py0, px0, px1, "x"), "B": ("y", py1, px0, px1, "x"),
             "C": ("x", px0, py0, py1, "y"), "D": ("x", px1, py0, py1, "y")}
    return t[fid]


def _dir_viga(seg: dict) -> str:
    return "x" if (seg["x1"] - seg["x0"]) >= (seg["y1"] - seg["y0"]) else "y"


def relacao(seg: dict, fid: str, px0, py0, px1, py1, *, horizontal: bool) -> Relacao | None:
    """Relação do contorno `seg` com a face `fid`, ou None."""
    axis, wall, s0, s1 = _face_geom(fid, px0, py0, px1, py1, horizontal)[:4]
    face_dir = _face_geom(fid, px0, py0, px1, py1, horizontal)[4]
    face_len = s1 - s0
    vd = _dir_viga(seg)

    if axis == "x":
        w0, w1 = seg["x0"], seg["x1"]          # paredes da viga na normal
        a0, a1 = seg["y0"], seg["y1"]          # extensão ao longo da face
    else:
        w0, w1 = seg["y0"], seg["y1"]
        a0, a1 = seg["x0"], seg["x1"]

    colinear = abs(w0 - wall) <= TOL or abs(w1 - wall) <= TOL
    atravessa = (w0 - TOL) <= wall <= (w1 + TOL)
    adjacente_axial = (a1 >= s0 - TOL) and (a0 <= s1 + TOL)
    ext = max(0.0, min(a1, s1) - max(a0, s0))

    # ── PASSA: viga corre na mesma direção da face e sua parede coincide ──
    if vd == face_dir and colinear and adjacente_axial:
        return Relacao(fid, "passa", ext, face_len,
                       f"parede da viga colinear com a face (alinhamento) · "
                       f"extensão sobreposta {ext:.0f}/{face_len:.0f}cm")

    # ── CHEGA: viga cruza a direção da face e encosta nela ──
    if vd != face_dir and (colinear or atravessa) and ext > TOL:
        return Relacao(fid, "chega", ext, face_len,
                       f"viga perpendicular encosta na face · "
                       f"{ext:.0f}/{face_len:.0f}cm ({100*ext/face_len:.0f}%)")
    return None


def medir_no_dxf(msp, fid: str, largura: float, px0, py0, px1, py1, *, horizontal: bool,
                 alcance: float = 200.0, tol: float = 2.0):
    """Mede o trecho ocupado na face lendo as LINHAS DO DXF (verdade de terra).

    Motivo (2026-08-08): o contorno guardado em
    ``beams.links.viga_fundo_seg_N_area_segs`` pode NÃO coincidir com o desenho.
    Caso real: V304 × P24 — DXF tem paredes em y=2441 e y=2460 (a viga ocupa
    2441..2460), mas o contorno do DB diz 2422..2441 — deslocado exatamente uma
    largura de viga (19 cm). Ancorar pelo contorno punha o ponto 19 cm fora da
    viga, e o humano via na hora.

    Estratégia: varre as linhas do DXF perpendiculares à face, do lado de fora
    dela, e procura o PAR de paredes separado por ~`largura` (a seção da viga).
    Retorna (ini, fim) em cm a partir do canto inicial da face, ou None.
    """
    axis, wall, s0, s1 = _face_geom(fid, px0, py0, px1, py1, horizontal)[:4]
    fora_maior = wall >= (px1 if axis == "x" else py1) - tol   # face no lado "alto"

    coords: set[float] = set()
    for e in msp:
        t = e.dxftype()
        if t == "LINE":
            pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif t == "LWPOLYLINE":
            try:
                pts = [(p[0], p[1]) for p in e.get_points()]
            except Exception:
                continue
        else:
            continue
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            if axis == "x":
                # face vertical → paredes da viga que chega são horizontais
                if abs(y1 - y2) > 0.5:
                    continue
                lo, hi = min(x1, x2), max(x1, x2)
                dentro = (lo <= wall + alcance and hi >= wall - tol) if fora_maior \
                    else (hi >= wall - alcance and lo <= wall + tol)
                if dentro and (s0 - tol) <= y1 <= (s1 + tol):
                    coords.add(round(y1, 1))
            else:
                if abs(x1 - x2) > 0.5:
                    continue
                lo, hi = min(y1, y2), max(y1, y2)
                dentro = (lo <= wall + alcance and hi >= wall - tol) if fora_maior \
                    else (hi >= wall - alcance and lo <= wall + tol)
                if dentro and (s0 - tol) <= x1 <= (s1 + tol):
                    coords.add(round(x1, 1))

    cs = sorted(coords)
    melhor = None
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            d = cs[j] - cs[i]
            if abs(d - largura) <= tol:
                erro = abs(d - largura)
                if melhor is None or erro < melhor[0]:
                    melhor = (erro, cs[i], cs[j])
    if not melhor:
        return None

    # Origem = canto ESQUERDO da face, a MESMA que `_beam_seg_on_face` usa
    # para desenhar (senão o ponto sai espelhado — bug 2026-08-10):
    #   vertical  : A e D contam do extremo ALTO (py1/px1) → invertem;
    #               B e C contam do extremo baixo.
    #   horizontal: TODAS contam do extremo baixo (px0/py0) → nenhuma inverte.
    # Verificado lendo `_beam_seg_on_face` face a face, não deduzido.
    inverte = (fid in ("A", "D")) and not horizontal
    if inverte:
        return s1 - melhor[2], s1 - melhor[1]
    return melhor[1] - s0, melhor[2] - s0


def contato_medido(seg: dict, fid: str, px0, py0, px1, py1, *, horizontal: bool):
    """Trecho REAL ocupado na face → (ini, fim) em cm a partir do canto s0.

    Usado para posicionar o pontinho da tag no CENTRO da viga que chega
    (padrão PADRAO-TAGS-DESTAQUE-AGENTICO-PIL: chega → centro da viga,
    nunca a esquina do pilar).
    """
    axis, wall, s0, s1 = _face_geom(fid, px0, py0, px1, py1, horizontal)[:4]
    a0, a1 = (seg["y0"], seg["y1"]) if axis == "x" else (seg["x0"], seg["x1"])
    ini, fim = max(a0, s0), min(a1, s1)
    if fim <= ini:
        return None
    return ini - s0, fim - s0
