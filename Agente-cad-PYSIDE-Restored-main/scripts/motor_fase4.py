"""
motor_fase4.py — Fase 4 Sincronizacao Headless
================================================
Transforma fichas simplificadas (Fase 3) para formato completo dos robos (Fase 4)
SEM PySide6, SEM UI, SEM interacao humana.

Equivalente headless dos botoes de sincronizacao do main.py:
  - sync_pillars_to_robo_pilares_action()
  - sync_beams_to_laterais_action()
  - sync_slabs_to_robo_laje_action()

Uso:
  python scripts/motor_fase4.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
  python scripts/motor_fase4.py --obra DADOS-OBRAS/Obra_TREINO_21  # processa todos pav

Input:  Fase-3_Interpretacao_Extracao/{Pilares,Vigas,Lajes}/*.json
Output: Fase-4_Sincronizacao/{pilares_salvos.json, JSON_Pilares/, vigas_salvas.json, ...}
"""

import os
import sys
import json
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

import io as _io
# Fix stdout encoding only when running as script (not when imported by pytest)
if __name__ == "__main__" and hasattr(sys.stdout, 'buffer'):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("motor_fase4")


# ==============================================================================
# MODELOS STANDALONE (sem dependencia de PySide6 ou robots)
# Replicam PilarModel/Laje/VigaState com campos minimos para Fase 4
# ==============================================================================

class PilarFase4:
    """
    Modelo de Pilar para Fase 4 — campos minimos que os robos esperam.
    Replica logica de PilarModel + PilarService.distribute_face_heights()
    sem dependencia de PySide6.
    """
    def __init__(self, numero: str, nome: str, comprimento: float, largura: float,
                 altura: float, pavimento: str, nivel_chegada: float = 0.0,
                 nivel_saida: float = 0.0, modo_distribuicao: str = "NOVA"):
        self.numero = numero
        self.nome = nome
        self.comprimento = comprimento  # maior dimensao (h da ficha Fase3)
        self.largura = largura          # menor dimensao (b da ficha Fase3)
        self.altura = altura
        self.pavimento = pavimento
        self.nivel_chegada = nivel_chegada
        self.nivel_saida = nivel_saida
        self.modo_distribuicao = modo_distribuicao

        # Distribuir alturas nas faces (h1-h5) — logica de PilarService
        self._distribute_face_heights(altura)
        self.grade_1 = 0.0
        self.grade_2 = 0.0
        self.grade_3 = 0.0
        self.distancia_1 = 0.0
        self.distancia_2 = 0.0

        # Parafusos (inicializar em 0)
        for i in range(1, 9):
            setattr(self, f"par_{i}_{i+1 if i < 8 else 9}", 0.0)

    def _distribute_face_heights(self, h_val: float):
        """
        Distribui a altura total nas hachuras h1-h5 (Regra Legada):
        h1 = 2.0 (se h > 2)
        h2 = h_resto (limitado a 244 por faixa)
        h3, h4, h5 = faixas restantes.

        Aplica APENAS nas faces primárias A-D.
        Faces E-H ficam com zeros — Fase-3 não contém informação sobre
        faces secundárias (pilares especiais L/T/U). O extrator de DXF
        deve preencher E-H quando identificar geometria especial.
        """
        h_rest = h_val
        h1 = 2.0 if h_rest > 2.0 else h_rest
        h_rest -= h1
        h2 = min(h_rest, 244.0)
        h_rest -= h2
        h3 = min(h_rest, 244.0)
        h_rest -= h3
        h4 = min(h_rest, 244.0)
        h_rest -= h4
        h5 = max(0.0, h_rest)

        for face in ['A', 'B', 'C', 'D']:
            setattr(self, f"h1_{face}", round(h1, 1))
            setattr(self, f"h2_{face}", round(h2, 1))
            setattr(self, f"h3_{face}", round(h3, 1))
            setattr(self, f"h4_{face}", round(h4, 1))
            setattr(self, f"h5_{face}", round(h5, 1))
            setattr(self, f"larg1_{face}", 0.0)
            setattr(self, f"larg2_{face}", 0.0)
            setattr(self, f"larg3_{face}", 0.0)
            setattr(self, f"laje_{face}", 0.0)
            setattr(self, f"posicao_laje_{face}", 0.0)

        # Faces secundárias E-H: zeros (pilar retangular padrão)
        for face in ['E', 'F', 'G', 'H']:
            for campo in ['h1', 'h2', 'h3', 'h4', 'h5',
                          'larg1', 'larg2', 'larg3', 'laje', 'posicao_laje']:
                setattr(self, f"{campo}_{face}", 0.0)

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        return d


@dataclass
class PanelData:
    """6 paineis de uma viga (slot fixo)."""
    width: float = 0.0
    height1: float = 0.0
    height2: float = 0.0
    grade_h1: str = "0"
    grade_h2: str = "0"

    def to_dict(self):
        return {
            "width": self.width, "height1": self.height1,
            "height2": self.height2, "grade_h1": self.grade_h1,
            "grade_h2": self.grade_h2
        }


@dataclass
class HoleData:
    """4 furos de uma viga."""
    active: bool = False
    width: float = 0.0
    height: float = 0.0
    position: float = 0.0

    def to_dict(self):
        return {"active": self.active, "width": self.width,
                "height": self.height, "position": self.position}


@dataclass
class PillarEdge:
    active: bool = False
    width: float = 0.0
    length: float = 0.0

    def to_dict(self):
        return {"active": self.active, "width": self.width, "length": self.length}


class VigaFase4:
    """
    Modelo de Viga para Fase 4 — VigaState com lado A e B.
    Cada viga Fase 3 gera 2 fichas: {nome}_A e {nome}_B.
    """
    def __init__(self, numero: str, nome: str, floor: str, side: str,
                 total_width: float, total_height: float, comprimento: float):
        self.number = numero
        self.name = nome
        self.floor = floor
        self.side = side  # "A" ou "B"
        self.total_width = total_width    # b da ficha Fase3
        self.total_height = str(total_height)  # h da ficha (como string no VigaState)

        # Distribuir comprimento em 6 panels
        self.panels = self._distribute_panels(comprimento, total_height)
        self.holes = [HoleData() for _ in range(4)]
        self.pillar_left = PillarEdge()
        self.pillar_right = PillarEdge()
        self.sarrafo_left_id = 0
        self.sarrafo_right_id = 0

    def _distribute_panels(self, comprimento: float, altura: float) -> List[PanelData]:
        """
        Distribui comprimento em N slots de panels (sem limite fixo).
        FIX LV-B2 2026-06-04: max painel = 244cm se h<122, 122cm se h>=122.
        Chapa NOVA 244x122: com h<122 usa-se 244cm no comprimento; caso contrário 122cm.
        """
        panels = []
        MAX_PANEL_WIDTH = 244.0 if altura < 122.0 else 122.0
        import math
        n_panels = max(1, math.ceil(comprimento / MAX_PANEL_WIDTH))
        restante = comprimento

        for i in range(n_panels):
            if restante <= 0:
                break
            w = min(restante, MAX_PANEL_WIDTH)
            restante -= w
            panels.append(PanelData(
                width=round(w, 1),
                height1=round(altura, 1),
                height2=round(altura, 1),
                # FIX LV-B1 2026-06-04: grade_h = comprimento do painel (SARR_3.5x7)
                grade_h1=str(round(w, 1)),
                grade_h2=str(round(w, 1))
            ))
        return panels

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "name": self.name,
            "floor": self.floor,
            "side": self.side,
            "total_width": self.total_width,
            "total_height": self.total_height,
            "panels": [p.to_dict() for p in self.panels],
            "holes": [h.to_dict() for h in self.holes],
            "pillar_left": self.pillar_left.to_dict(),
            "pillar_right": self.pillar_right.to_dict(),
            "sarrafo_left_id": self.sarrafo_left_id,
            "sarrafo_right_id": self.sarrafo_right_id
        }


class LajeFase4:
    """
    Modelo de Laje para Fase 4.
    Calcula linhas_verticais (244cm steps) e linhas_horizontais (122cm steps).
    FIX LJ-B1 2026-06-04: substituído STEP=100 por algoritmo NOVA correto.
    """
    def __init__(self, numero: int, nome: str, comprimento: float, largura: float,
                 pavimento: str, coordenadas: List[List[float]], area_cm2: float = 0.0,
                 modo_selecionado: int = 0):
        self.numero = numero
        self.nome = nome
        self.comprimento = comprimento
        self.largura = largura
        self.pavimento = pavimento
        self.coordenadas = coordenadas  # [[x,y], ...]
        self.area_cm2 = area_cm2 if area_cm2 > 0 else comprimento * largura
        self.modo_selecionado = modo_selecionado
        self.linhas_verticais = self._calc_linhas_verticais(comprimento)
        self.linhas_horizontais = self._calc_linhas_horizontais(largura)
        self.obstaculos = []
        self.unioes_nos_bordes = False
        self.observacoes = ""
        # CAD-7.2: pontaletes calculados (preenchidos por extrair_meioPont_pl se disponível)
        self.pontaletes: dict = {}

    def _calc_linhas_verticais(self, comprimento: float) -> List[dict]:
        """
        Calcula cortes na direção do comprimento (maior dimensão, painéis de 244cm).
        FIX LJ-B1 2026-06-04: usa 244cm como passo (chapa NOVA 244x122).
        is_union = True quando o segmento resultante <= 30cm (emenda, não secciona).
        """
        linhas = []
        pos = 0.0
        MAX_PAINEL = 244.0
        UNION_THRESHOLD = 30.0
        prev = 0.0

        while pos < comprimento:
            pos = min(pos + MAX_PAINEL, comprimento)
            segmento = pos - prev
            linhas.append({
                "value": round(pos, 1),
                "is_union": segmento <= UNION_THRESHOLD
            })
            prev = pos
            if pos >= comprimento:
                break

        return linhas

    def _calc_linhas_horizontais(self, largura: float) -> List[dict]:
        """
        Calcula cortes na direção da largura (menor dimensão, painéis de 122cm).
        FIX LJ-B1 2026-06-04: adicionado (antes sempre retornava []).
        is_union = True quando o segmento resultante <= 30cm.
        """
        linhas = []
        pos = 0.0
        MAX_PAINEL = 122.0
        UNION_THRESHOLD = 30.0
        prev = 0.0

        while pos < largura:
            pos = min(pos + MAX_PAINEL, largura)
            segmento = pos - prev
            linhas.append({
                "value": round(pos, 1),
                "is_union": segmento <= UNION_THRESHOLD
            })
            prev = pos
            if pos >= largura:
                break

        return linhas

    def to_dict(self) -> dict:
        return {
            "numero": self.numero,
            "nome": self.nome,
            "comprimento": self.comprimento,
            "largura": self.largura,
            "pavimento": self.pavimento,
            "coordenadas": self.coordenadas,
            "area_cm2": self.area_cm2,
            "linhas_verticais": self.linhas_verticais,
            "linhas_horizontais": self.linhas_horizontais,
            "obstaculos": self.obstaculos,
            "modo_selecionado": self.modo_selecionado,
            "unioes_nos_bordes": self.unioes_nos_bordes,
            "observacoes": self.observacoes,
            "pontaletes": self.pontaletes,
        }


# ==============================================================================
# SA META — RASTREAMENTO DE COMPLETUDE
# ==============================================================================

from datetime import datetime as _dt

# Campos que NÃO se aplicam por tipo (nunca pertencem ao item, não são defaults)
_NA_FIELDS = {
    "PL": {"panels", "total_width", "pillar_left", "pillar_right", "holes",
           "coordenadas", "linhas_verticais", "linhas_horizontais", "obstaculos",
           "reaproveitamento_dados", "side"},
    "LV": {"numero", "comprimento", "largura", "altura", "grade_1", "grade_2",
           "coordenadas", "linhas_verticais", "linhas_horizontais", "obstaculos",
           "reaproveitamento_dados"},
    "FV": {"numero", "nome", "comprimento", "largura", "altura", "pavimento",
           "grade_1", "grade_2", "coordenadas", "linhas_verticais",
           "linhas_horizontais", "obstaculos", "reaproveitamento_dados"},
    "LJ": {"grade_1", "grade_2", "panels", "total_width", "pillar_left",
           "pillar_right", "holes", "h1_A", "h2_A", "h3_A", "side"},
}

# Campos required que DEVEM ter valor não-zero para esse tipo
_REQUIRED_NONZERO = {
    "PL": {"comprimento", "largura", "altura", "larg1_A", "larg1_B", "par_1_2"},
    "LV": {"total_width", "total_height"},
    "FV": {"total_width", "total_height"},
    "LJ": {"comprimento", "largura", "area_cm2"},
}


import math as _math


def _fix_laje_coordenadas(coords: list, comprimento: float, largura: float) -> list:
    """Corrige bug de fechamento de polígono em lajes.

    O extrator `extrair_poligono_lajes.py` fecha a LWPOLYLINE com `pts.append(pts[0])`.
    Quando a polyline tem apenas 3 vértices únicos, o resultado é:
        [[0,0], [C,0], [C,L], [0,0]]   ← falta [0,L]
    Este fix detecta o padrão e insere o canto ausente.
    """
    if len(coords) != 4:
        return coords  # polígono com mais vértices — não mexer
    first, *middle, last = coords
    # Condição do bug: último ponto == primeiro ponto (fechamento) E
    # o penúltimo ponto não tem o canto [~0, ~largura] esperado
    tol = max(1.0, largura * 0.05)
    last_is_close = (abs(last[0] - first[0]) < tol and abs(last[1] - first[1]) < tol)
    if not last_is_close:
        return coords  # não é padrão de fechamento — não mexer
    # Verifica se o canto [0, largura] está presente
    has_topleft = any(abs(p[0]) < tol and abs(p[1] - largura) < tol for p in middle)
    if has_topleft:
        return coords  # correto, nada a fazer
    # Insere [0, largura] antes do ponto de fechamento
    fixed = list(coords[:-1]) + [[0.0, round(largura, 1)], coords[-1]]
    return fixed


def _calcular_parafusos(comprimento: float) -> list:
    """
    Calcula distribuição dos parafusos baseado no comprimento do pilar.
    Algoritmo extraído de funcoes_auxiliares_5.GradeParafusosMixin.calcular_parafusos.
    Retorna lista de 8 floats (par_1_2..par_8_9).
    """
    if not comprimento or comprimento <= 0:
        return [0.0] * 8
    comp_aj = comprimento + 24  # +24cm para folga dos parafusos
    quantidade = int(_math.ceil(comp_aj / 72))
    if quantidade == 0:
        return [0.0] * 8
    if quantidade == 2:
        valor = round(comp_aj / 2, 1)
        parafusos = [valor, valor]
    else:
        valor_base = int(_math.floor(comp_aj / quantidade))
        resto = int(round(comp_aj - (valor_base * quantidade)))
        parafusos = [float(valor_base)] * quantidade
        left, right = 0, quantidade - 1
        for i in range(resto):
            if i % 2 == 0:
                parafusos[left] += 1
                left += 1
            else:
                parafusos[right] += 1
                right -= 1
    # Preencher até 8 posições (par_1_2..par_8_9)
    while len(parafusos) < 8:
        parafusos.append(0.0)
    return parafusos[:8]


# ==============================================================================
# B2 — DETECÇÃO DE LAJE NO PILAR (georef por centróide)
# ==============================================================================

def _pip_motor(px: float, py: float, pts: list) -> bool:
    """Ray casting: retorna True se (px,py) está dentro do polígono pts=[[x,y],...]."""
    n = len(pts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = pts[i][0], pts[i][1]
        xj, yj = pts[j][0], pts[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _load_lajes_abs(fase3_path: Path) -> dict:
    """
    Carrega coordenadas absolutas das lajes de lajes_poligono.json.
    Retorna {lid: {'coords_abs': [[x,y]...], 'comprimento': float, 'largura': float}}
    Retorna {} se arquivo não existe ou sem coordenadas absolutas.
    """
    poly_file = fase3_path / "Lajes" / "lajes_poligono.json"
    if not poly_file.exists():
        return {}
    try:
        data = json.loads(poly_file.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}

    result = {}
    for lid, entry in data.items():
        if lid.startswith("_"):
            continue
        coords_abs = entry.get("coordenadas_absolutas")
        if not coords_abs or len(coords_abs) < 3:
            continue
        result[lid] = {
            "coords_abs": coords_abs,
            "comprimento": float(entry.get("comprimento") or 0),
            "largura": float(entry.get("largura") or 0),
        }
    return result


def _detectar_lajes_pilar(cx: float, cy: float, lajes_abs: dict) -> list:
    """
    Retorna lista de laje IDs cujo polígono absoluto contém o ponto (cx, cy).
    Usa ray casting. Resultado pode ser [] se pilar não está em nenhuma laje.
    """
    intersectadas = []
    for lid, info in lajes_abs.items():
        if _pip_motor(cx, cy, info["coords_abs"]):
            intersectadas.append(lid)
    return intersectadas


def _aplicar_laje_pilar(pilar: "PilarFase4", lajes_detectadas: list,
                        espessura_default: float = 10.0) -> None:
    """
    FIX B2 (parcial) — Aplica laje_X e posicao_laje_X nas faces A-D do pilar.

    Limitações conhecidas:
    - Espessura da laje usa valor padrão 10cm (dados não disponíveis em Fase-3).
    - posicao_laje_X = 1 (primeira chapa, conservativo — requer alturas relativas).
    - Não distingue qual face é a "laje face" (requer geometria da orientação do pilar).
    - Aplica nas 4 faces A-D quando pelo menos 1 laje intersecta o pilar.

    Para implementação completa: requere (1) orientação do pilar no DXF,
    (2) espessura real da laje, (3) nível relativo pilar vs. laje.
    """
    if not lajes_detectadas:
        return
    for face in ["A", "B", "C", "D"]:
        setattr(pilar, f"laje_{face}", espessura_default)
        setattr(pilar, f"posicao_laje_{face}", 1.0)


# ==============================================================================
# LV-B3 — DETECÇÃO DE PILAR NOS EXTREMOS DA VIGA
# ==============================================================================

def _load_pilar_centroids(fase3_path: Path) -> list:
    """
    Carrega centróides de pilares de pilares_bh.json.
    Retorna lista de {'pid', 'cx', 'cy', 'b', 'h'}.
    Prioriza cx_geo/cy_geo (Sprint 2 — geometria LWPOLYLINE) se disponível.
    """
    bh_file = fase3_path / "Pilares" / "pilares_bh.json"
    if not bh_file.exists():
        return []
    try:
        data = json.loads(bh_file.read_text(encoding="utf-8-sig"))
    except Exception:
        return []

    pilares = []
    for pid, info in data.items():
        if pid.startswith("_"):
            continue
        # Preferir geometria precisa (Sprint 2), fallback para centróide de label
        cx = info.get('cx_geo') or info.get('cx')
        cy = info.get('cy_geo') or info.get('cy')
        if cx is None or cy is None:
            continue
        pilares.append({
            'pid': pid,
            'cx': float(cx), 'cy': float(cy),
            'b': float(info.get('b') or 0),
            'h': float(info.get('h') or 0),
        })
    return pilares


def _detectar_pillar_edges(vx: float, vy: float, comprimento: float,
                           pilares: list, tolerancia: float = 60.0
                           ) -> tuple:
    """
    LV-B3: Detecta pilares nos extremos (left/right) da viga.

    Estratégia: a viga pode ser horizontal ou vertical. Para cada orientação
    possível, calcula os dois extremos (vx ± C/2, vy) ou (vx, vy ± C/2) e
    verifica qual pilar está mais próximo de cada extremo dentro da tolerância.

    vx, vy      = centróide do label da viga (posição aproximada no plano)
    comprimento = comprimento total da viga (cm)
    pilares     = lista de {'pid', 'cx', 'cy', 'b', 'h'}
    tolerancia  = distância máxima extremo→pilar para considerar match (cm)

    Retorna (left_edge, right_edge) onde cada é dict ou None.
    dict: {'pid', 'width', 'length'} — width = dist viga_start→pilar_wall, length = esp pilar
    """
    if not pilares or comprimento <= 0:
        return None, None

    half = comprimento / 2.0
    # Candidatos: extremos em 4 direções (±X e ±Y)
    endpoints = [
        ('H-', (vx - half, vy), (vx + half, vy)),   # horizontal: left=vx-C/2, right=vx+C/2
        ('V-', (vx, vy - half), (vx, vy + half)),    # vertical:   left=vy-C/2, right=vy+C/2
    ]

    best_config = None
    best_total_dist = float('inf')

    for orient, ep_left, ep_right in endpoints:
        # Para cada extremo, encontrar pilar mais próximo
        def nearest(ep):
            best, d = None, float('inf')
            for p in pilares:
                dist = _math.sqrt((p['cx'] - ep[0])**2 + (p['cy'] - ep[1])**2)
                if dist < d:
                    best, d = p, dist
            return best, d

        pl, dl = nearest(ep_left)
        pr, dr = nearest(ep_right)

        if dl > tolerancia and dr > tolerancia:
            continue

        total = (dl if dl <= tolerancia else tolerancia * 2) + \
                (dr if dr <= tolerancia else tolerancia * 2)
        if total < best_total_dist:
            best_total_dist = total
            best_config = (pl if dl <= tolerancia else None,
                           dl,
                           pr if dr <= tolerancia else None,
                           dr)

    if best_config is None:
        return None, None

    pl_match, dl, pr_match, dr = best_config

    def make_edge(p, dist):
        if p is None:
            return None
        pilar_dim = max(float(p['b'] or 0), float(p['h'] or 0))
        # width = distância do extremo da viga até a parede do pilar (±pilar_dim/2)
        width = max(0.0, round(dist - pilar_dim / 2, 1))
        return PillarEdge(active=True, width=width, length=round(pilar_dim, 1))

    return make_edge(pl_match, dl), make_edge(pr_match, dr)


def _build_sa_meta(tipo: str, data: dict, fields_extraidos: list) -> dict:
    """
    Constrói bloco _sa_meta para um item exportado pelo SA.

    campos_extraidos  — campos que o SA efetivamente extraiu (não são defaults)
    campos_defaulted  — required fields presentes mas com valor default/zero
    na_fields         — campos que não se aplicam a este tipo de item
    completude_pct    — % dos required_nonzero fields com valor válido
    """
    na = _NA_FIELDS.get(tipo, set())
    required_nz = _REQUIRED_NONZERO.get(tipo, set())

    # Campos com valor não-zero/não-vazio no dict final
    ok_fields = {k for k, v in data.items()
                 if not k.startswith("_") and v not in (0, 0.0, "", None, [], {})}

    campos_defaulted = sorted(
        (required_nz - set(fields_extraidos)) - na
    )
    completude = round(
        len(ok_fields.intersection(required_nz)) /
        max(len(required_nz), 1) * 100, 1
    )

    return {
        "_sa_meta": {
            "tipo": tipo,
            "analisado_em": _dt.now().strftime("%Y-%m-%d %H:%M"),
            "campos_extraidos": sorted(fields_extraidos),
            "campos_defaulted": campos_defaulted,
            "na_fields": sorted(na),
            "completude_pct": completude,
        }
    }


# ==============================================================================
# ENGINE DE TRANSFORMACAO
# ==============================================================================

class MotorFase4:
    """
    Engine headless de sincronizacao Fase 3 -> Fase 4.
    Replica logica dos botoes sync do main.py sem PySide6.
    """

    def __init__(self, obra_path: str, pavimento: Optional[str] = None,
                 nivel_chegada: float = 0.0, nivel_saida: float = 280.0):
        self.obra_path = Path(obra_path)
        self.pavimento = pavimento
        self.nivel_chegada = nivel_chegada
        self.nivel_saida = nivel_saida
        self.altura_padrao = abs(nivel_saida - nivel_chegada) or 280.0

        # Detectar nome da obra
        self.obra_nome = self.obra_path.name

        # Paths de input (Fase 3)
        self.fase3_path = self.obra_path / "Fase-3_Interpretacao_Extracao"

        # Paths de output (Fase 4)
        self.fase4_path = self.obra_path / "Fase-4_Sincronizacao"
        self.fase4_path.mkdir(parents=True, exist_ok=True)

        (self.fase4_path / "JSON_Pilares").mkdir(exist_ok=True)
        (self.fase4_path / "JSON_Vigas_Laterais").mkdir(exist_ok=True)
        (self.fase4_path / "JSON_Vigas_Fundo").mkdir(exist_ok=True)
        (self.fase4_path / "JSON_Lajes").mkdir(exist_ok=True)

        self.stats = {"pilares": 0, "vigas": 0, "lajes": 0, "errors": 0}

    # --------------------------------------------------------------------------
    # PILARES
    # --------------------------------------------------------------------------

    def process_pilares(self) -> Dict[str, Any]:
        """Ler fichas Fase3, transformar, salvar Fase4."""
        fichas = self._load_fase3_fichas("Pilares", "pilares.json")
        if not fichas:
            log.warning("Sem fichas de pilares para processar.")
            return {}

        # B2: Carregar coordenadas absolutas de lajes para detecção de interseção
        lajes_abs = _load_lajes_abs(self.fase3_path)
        if lajes_abs:
            log.info(f"[B2] {len(lajes_abs)} lajes com coordenadas absolutas carregadas")
        else:
            log.warning("[B2] lajes_poligono.json não encontrado — laje_X ficará 0")

        # Carregar assembly data (CAD-7.1) — grade_1, grade_2 por pilar
        assembly_path = self.fase3_path / "Pilares" / "pilares_assembly.json"
        assembly_data: Dict[str, Any] = {}
        if assembly_path.exists():
            with open(assembly_path, encoding="utf-8") as f:
                assembly_data = json.load(f)
            log.info(f"Assembly data carregado: {len(assembly_data)} pilares ({assembly_path.name})")
        else:
            log.warning(f"pilares_assembly.json nao encontrado — grades ficarao zeradas")

        pilares_salvos = {}
        pav = self.pavimento or "Pavimento"

        # Pre-calcular mediana de B para usar como fallback quando b=None
        _bs_validos = [float(v.get("b")) for v in fichas.values()
                       if not str(v).startswith("_") and isinstance(v, dict)
                       and v.get("b") is not None and float(v.get("b") or 0) > 0]
        _b_fallback = (sorted(_bs_validos)[len(_bs_validos) // 2]
                       if _bs_validos else 20.0)

        for nome, dados in fichas.items():
            if nome.startswith("_"):
                continue  # Pular _meta
            try:
                b_raw = dados.get("b")
                h_raw = dados.get("h")
                b = float(b_raw or 0)
                h = float(h_raw or 0)
                altura = float(dados.get("altura") or self.altura_padrao)

                # Fallback quando b=None mas h valido: usar mediana dos outros pilares
                if b <= 0 and h > 0:
                    b = _b_fallback
                    log.warning(f"Pilar {nome}: b=None, usando fallback b={b}cm (mediana)")

                if b <= 0 or h <= 0:
                    log.warning(f"Pilar {nome}: dimensoes invalidas (b={b}, h={h}). Pular.")
                    continue

                # b=largura (menor), h=comprimento (maior) — convencao do PilarModel
                comprimento = max(b, h)
                largura = min(b, h)

                # Extrair numero
                nums = re.findall(r"\d+", nome)
                numero = nums[0] if nums else "0"

                pilar = PilarFase4(
                    numero=numero,
                    nome=nome,
                    comprimento=comprimento,
                    largura=largura,
                    altura=altura,
                    pavimento=pav,
                    nivel_chegada=self.nivel_chegada,
                    nivel_saida=self.nivel_saida or altura,
                    modo_distribuicao="NOVA"
                )

                # Enriquecer com assembly data (CAD-7.1)
                asm = assembly_data.get(nome, {})
                if asm:
                    g1 = asm.get("grade_1")
                    g2 = asm.get("grade_2")
                    pilar.grade_1 = float(g1) if g1 is not None else 0.0
                    pilar.grade_2 = float(g2) if g2 is not None else 0.0
                    pilar.distancia_1 = 14.0  # default STOG (nao extraivel do DXF PL)

                # Calcular larg1 por face (A/B=comprimento, C/D=largura, E-H=0)
                # FIX B1 2026-06-04: A e B são faces LONGAS (comprimento), C e D são CURTAS (largura)
                face_larg1_map = {
                    "A": comprimento, "B": comprimento,
                    "C": largura,     "D": largura,
                }
                for face in ["A", "B", "C", "D", "E", "F", "G", "H"]:
                    setattr(pilar, f"larg1_{face}", face_larg1_map.get(face, 0.0))

                # Calcular parafusos (algoritmo deterministico a partir do comprimento)
                pars = _calcular_parafusos(comprimento)
                par_keys = ["par_1_2", "par_2_3", "par_3_4", "par_4_5",
                            "par_5_6", "par_6_7", "par_7_8", "par_8_9"]
                for key, val in zip(par_keys, pars):
                    setattr(pilar, key, val)

                # FIX B2 (parcial) 2026-06-04 — Detectar laje intersectando o pilar
                # Requer cx/cy do pilar (de engenharia_reversa_dxf.py) + lajes_poligono.json
                _lajes_detectadas = []
                cx = dados.get("cx")
                cy = dados.get("cy")
                if cx is not None and cy is not None and lajes_abs:
                    _lajes_detectadas = _detectar_lajes_pilar(float(cx), float(cy), lajes_abs)
                    if _lajes_detectadas:
                        _aplicar_laje_pilar(pilar, _lajes_detectadas)
                        log.info(f"  [B2] Pilar {nome}: lajes detectadas={_lajes_detectadas} "
                                 f"-> laje_X=10cm(default), posicao_laje_X=1(default)")

                pilar_dict = pilar.to_dict()

                # Rastrear quais campos foram efetivamente extraídos (não defaults)
                _extraidos = ["numero", "nome", "comprimento", "largura", "altura", "pavimento",
                              "nivel_chegada", "nivel_saida", "modo_distribuicao",
                              # campos computados deterministicamente
                              "larg1_A", "larg1_B", "larg1_C", "larg1_D",
                              "par_1_2", "par_2_3", "par_3_4", "par_4_5",
                              "par_5_6", "par_6_7"]
                if _lajes_detectadas:
                    _extraidos.extend(["laje_A", "laje_B", "laje_C", "laje_D",
                                       "posicao_laje_A", "posicao_laje_B",
                                       "posicao_laje_C", "posicao_laje_D"])
                if asm:
                    if asm.get("grade_1") is not None:
                        _extraidos.append("grade_1")
                    if asm.get("grade_2") is not None:
                        _extraidos.append("grade_2")
                    _extraidos.append("distancia_1")  # fixo STOG

                pilar_dict.update(_build_sa_meta("PL", pilar_dict, _extraidos))
                pilares_salvos[nome] = pilar_dict

                # Salvar JSON individual
                out_path = self.fase4_path / "JSON_Pilares" / f"{nome}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(pilar_dict, f, ensure_ascii=False, indent=2)

                self.stats["pilares"] += 1
                g1_str = f" grade_1={pilar.grade_1:.0f}" if pilar.grade_1 else ""
                log.info(f"  ✅ Pilar {nome}: {comprimento}x{largura}cm, h={altura}cm{g1_str}")

            except Exception as e:
                log.error(f"  ❌ Pilar {nome}: {e}")
                self.stats["errors"] += 1

        # Salvar pilares_salvos.json (formato simplificado para compatibilidade)
        salvos_path = self.fase4_path / "pilares_salvos.json"
        simplified = {k: {"b": v.get("largura", 0), "h": v.get("comprimento", 0),
                          "altura": v.get("altura", 0)}
                      for k, v in pilares_salvos.items()}
        with open(salvos_path, "w", encoding="utf-8") as f:
            json.dump(simplified, f, ensure_ascii=False, indent=2)

        log.info(f"Pilares: {self.stats['pilares']} processados -> {salvos_path}")
        return pilares_salvos

    # --------------------------------------------------------------------------
    # VIGAS
    # --------------------------------------------------------------------------

    def _project_id_for_beam_elements(self) -> Optional[str]:
        """Resolve o projeto atual no SQLite para ler beam_elements do SA."""
        import sqlite3
        db_path = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        if not db_path.exists():
            return None
        pav = self.pavimento or ""
        pav_digits = "".join(re.findall(r"\d+", str(pav)))
        try:
            conn = sqlite3.connect(str(db_path))
            if pav_digits:
                row = conn.execute(
                    "SELECT id FROM projects WHERE work_name=? AND pavement_name LIKE ? "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (self.obra_nome, f"%{pav_digits}%"),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id FROM projects WHERE work_name=? "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (self.obra_nome,),
                ).fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as exc:
            log.warning(f"[FV-SA] Falha resolvendo projeto beam_elements: {exc}")
            return None

    @staticmethod
    def _seg_len_from_geometry(seg: dict) -> float:
        pts = seg.get("geometry") or []
        if not isinstance(pts, list) or len(pts) < 2:
            return 0.0
        total = 0.0
        for a, b in zip(pts, pts[1:]):
            try:
                dx = float(b[0]) - float(a[0])
                dy = float(b[1]) - float(a[1])
                total += (dx * dx + dy * dy) ** 0.5
            except Exception:
                pass
        return total

    @staticmethod
    def _parse_dim_pair(dim_text: Any) -> Tuple[float, float]:
        m = re.search(r"\(?\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*\)?", str(dim_text or ""))
        if not m:
            return 0.0, 0.0
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", "."))
        return min(a, b), max(a, b)

    def _write_fv_json_from_beam_elements(self, vigas_salvos: Dict[str, Any]) -> int:
        """Sincroniza JSON_Vigas_Fundo a partir da ficha FV persistida pelo SA."""
        import sqlite3
        project_id = self._project_id_for_beam_elements()
        if not project_id:
            return 0
        db_path = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT viga_nome, n_segmentos, campos_json FROM beam_elements "
                "WHERE project_id=? AND classe='FV' "
                "AND (campos_json LIKE '%n_paineis_logicos%' OR campos_json LIKE '%dim_text%') "
                "ORDER BY viga_nome",
                (project_id,),
            ).fetchall()
            conn.close()
        except Exception as exc:
            log.warning(f"[FV-SA] Falha lendo beam_elements: {exc}")
            return 0

        count = 0
        pav = self.pavimento or "Pavimento"
        for row in rows:
            nome = str(row["viga_nome"] or "").strip()
            m_name = re.search(r"(V\d+[A-Z]?)", nome.upper())
            if not m_name:
                continue
            vname = m_name.group(1)
            try:
                data = json.loads(row["campos_json"] or "{}")
            except Exception:
                data = {}
            segs = [s for s in (data.get("segmentos_fundo") or []) if isinstance(s, dict)]
            if not segs:
                continue

            from src.core.fv_generation_contract import build_fv_generation_contract

            out = build_fv_generation_contract(vname, data, floor=pav)
            panels = out["segments_rich"]
            if not panels:
                continue
            out.update(_build_sa_meta(
                "FV", out,
                ["number", "name", "floor", "total_width", "total_height", "panels",
                 "segments_rich", "apoio_inicial", "apoio_final"],
            ))
            out_path = self.fase4_path / "JSON_Vigas_Fundo" / f"{vname}_fundo.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            vigas_salvos.setdefault(vname, {})
            vigas_salvos[vname].update({
                "b": out["total_width"],
                "h": float(out["total_height"] or 0),
                "comprimento": sum(float(p.get("total_width", 0) or 0) for p in panels),
            })
            count += 1

        if count:
            log.info(f"[FV-SA] JSON_Vigas_Fundo sincronizado de beam_elements: {count} fichas")
        return count

    def process_vigas(self) -> Dict[str, Any]:
        """Cada viga Fase3 gera 2 fichas: lado A e lado B."""
        fichas = self._load_fase3_fichas("Vigas", "vigas.json")
        if not fichas:
            log.warning("Sem fichas de vigas para processar.")
            return {}

        # LV-B3: Enriquecer fichas com cx/cy de vigas_dim.json (gerado por extrair_vigas_lv.py)
        _vigas_dim_path = self.fase3_path / "Vigas" / "vigas_dim.json"
        if _vigas_dim_path.exists():
            try:
                with open(_vigas_dim_path, "r", encoding="utf-8") as _f:
                    _vigas_dim = json.load(_f)
                _enrich_count = 0
                for _vid, _vdim in _vigas_dim.items():
                    if _vid in fichas:
                        _cx = _vdim.get("cx")
                        _cy = _vdim.get("cy")
                        if _cx is not None and _cy is not None:
                            fichas[_vid]["cx"] = _cx
                            fichas[_vid]["cy"] = _cy
                            _enrich_count += 1
                log.info(f"[LV-B3] cx/cy enriquecidos de vigas_dim.json: {_enrich_count}/{len(fichas)} vigas")
            except Exception as _e:
                log.warning(f"[LV-B3] Falha ao enriquecer cx/cy de vigas_dim.json: {_e}")

        # LV-B3: Carregar centróides de pilares para detecção de pillar_left/right
        _pilares_geo = _load_pilar_centroids(self.fase3_path)
        if _pilares_geo:
            log.info(f"[LV-B3] {len(_pilares_geo)} pilares com centróide para detecção")
        else:
            log.warning("[LV-B3] Sem centróides de pilar — pillar_left/right ficará inactive")

        vigas_salvos = {}
        pav = self.pavimento or "Pavimento"

        for nome, dados in fichas.items():
            if nome.startswith("_"):
                continue
            try:
                b = float(dados.get("b") or 0)
                h = float(dados.get("h") or 0)
                comprimento = float(dados.get("comprimento") or 0)

                if b <= 0 or comprimento <= 0:
                    log.warning(f"Viga {nome}: dimensoes invalidas. Pular.")
                    continue

                nums = re.findall(r"\d+", nome)
                numero = nums[0] if nums else "0"

                # Gerar lado A e lado B
                for side in ["A", "B"]:
                    nome_side = f"{nome}_{side}"
                    viga = VigaFase4(
                        numero=numero,
                        nome=nome_side,
                        floor=pav,
                        side=side,
                        total_width=b,
                        total_height=h,
                        comprimento=comprimento
                    )
                    # FIX LV-B3 2026-06-04: detecção de pilar nos extremos da viga
                    vx = dados.get("cx")
                    vy = dados.get("cy")
                    if vx is not None and vy is not None and _pilares_geo and comprimento > 0:
                        pl_edge, pr_edge = _detectar_pillar_edges(
                            float(vx), float(vy), comprimento, _pilares_geo)
                        if pl_edge:
                            viga.pillar_left = pl_edge
                        if pr_edge:
                            viga.pillar_right = pr_edge
                        if pl_edge or pr_edge:
                            log.info(f"  [LV-B3] {nome_side}: "
                                     f"left={'✓' if pl_edge else '–'} "
                                     f"right={'✓' if pr_edge else '–'}")
                    # TODO LV-B4: holes inactive — requer CONCRETO layer no DXF STOG

                    viga_dict = viga.to_dict()
                    _extraidos_lv = ["number", "name", "floor", "side",
                                     "total_width", "total_height", "panels"]
                    if viga.pillar_left.active:
                        _extraidos_lv.append("pillar_left")
                    if viga.pillar_right.active:
                        _extraidos_lv.append("pillar_right")
                    viga_dict.update(_build_sa_meta("LV", viga_dict, _extraidos_lv))
                    vigas_salvos[nome_side] = viga_dict

                    # Salvar JSON individual em JSON_Vigas_Laterais
                    out_path = self.fase4_path / "JSON_Vigas_Laterais" / f"{nome_side}.json"
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(viga_dict, f, ensure_ascii=False, indent=2)

                # Salvar fundo (simplificado - mesmo que lado A mas em JSON_Vigas_Fundo)
                fundo_dict = vigas_salvos[f"{nome}_A"].copy()
                # FV: sobrescreve _sa_meta com tipo correto
                _extraidos_fv = ["number", "name", "floor", "total_width", "total_height", "panels"]
                fundo_dict.update(_build_sa_meta("FV", fundo_dict, _extraidos_fv))
                fundo_path = self.fase4_path / "JSON_Vigas_Fundo" / f"{nome}_fundo.json"
                with open(fundo_path, "w", encoding="utf-8") as f:
                    json.dump(fundo_dict, f, ensure_ascii=False, indent=2)

                self.stats["vigas"] += 1
                log.info(f"  ✅ Viga {nome}: b={b}cm, h={h}cm, L={comprimento}cm -> A+B")

            except Exception as e:
                log.error(f"  ❌ Viga {nome}: {e}")
                self.stats["errors"] += 1

        # FV: quando a Analise Geral ja populou beam_elements, a ficha de fundo
        # do Robo/N3 deve vir dessa fonte N1, nao do clone simplificado da lateral.
        self._write_fv_json_from_beam_elements(vigas_salvos)

        # Salvar vigas_salvas.json
        salvos_path = self.fase4_path / "vigas_salvas.json"
        simplified = {}
        for nome_orig, dados in fichas.items():
            if not nome_orig.startswith("_"):
                simplified[nome_orig] = {
                    "b": dados.get("b", 0), "h": dados.get("h", 0),
                    "comprimento": dados.get("comprimento", 0)
                }
        with open(salvos_path, "w", encoding="utf-8") as f:
            json.dump(simplified, f, ensure_ascii=False, indent=2)

        log.info(f"Vigas: {self.stats['vigas']} processadas -> {salvos_path}")
        return vigas_salvos

    # --------------------------------------------------------------------------
    # LAJES
    # --------------------------------------------------------------------------

    def process_lajes(self) -> Dict[str, Any]:
        """Transformar fichas de laje para formato Laje dataclass."""
        fichas = self._load_fase3_fichas("Lajes", "lajes.json")
        if not fichas:
            log.warning("Sem fichas de lajes para processar.")
            return {}

        lajes_salvos = {}
        pav = self.pavimento or "Pavimento"

        # CAD-7.2: Carregar dados de pontaletes se disponível
        _pont_data: dict = {}
        _pont_file = self.fase3_path / "Lajes" / "lajes_meioPont.json"
        if _pont_file.exists():
            try:
                _pont_data = json.loads(_pont_file.read_text(encoding='utf-8-sig'))
                log.info(f"[CAD-7.2] Pontaletes carregados: {len(_pont_data)} lajes")
            except Exception as _e:
                log.warning(f"[CAD-7.2] Erro lendo lajes_meioPont.json: {_e}")

        for nome, dados in fichas.items():
            if nome.startswith("_"):
                continue
            try:
                comprimento = float(dados.get("comprimento") or 0)
                largura = float(dados.get("largura") or 0)
                area_cm2 = float(dados.get("area_cm2") or (comprimento * largura))
                coordenadas = dados.get("coordenadas", [])

                if comprimento <= 0 or largura <= 0:
                    log.warning(f"Laje {nome}: dimensoes invalidas. Pular.")
                    continue

                # Gerar coordenadas padrao se nao existirem
                if not coordenadas:
                    coordenadas = [
                        [0.0, 0.0], [comprimento, 0.0],
                        [comprimento, largura], [0.0, largura], [0.0, 0.0]
                    ]
                else:
                    # Fix: bug de fechamento — extrator produz 4 pts com último=[0,0]
                    # quando LWPOLYLINE tinha apenas 3 vértices únicos.
                    # Padrão bug: [[0,0],[C,0],[C,L],[0,0]] → falta [0,L]
                    coordenadas = _fix_laje_coordenadas(coordenadas, comprimento, largura)

                nums = re.findall(r"\d+", nome)
                numero = int(nums[0]) if nums else 0

                laje = LajeFase4(
                    numero=numero,
                    nome=nome,
                    comprimento=comprimento,
                    largura=largura,
                    pavimento=pav,
                    coordenadas=coordenadas,
                    area_cm2=area_cm2,
                    modo_selecionado=dados.get("modo_selecionado", 0)
                )
                # CAD-7.2: injetar dados de pontalete
                if nome in _pont_data:
                    laje.pontaletes = _pont_data[nome]

                laje_dict = laje.to_dict()
                _extraidos_lj = ["numero", "nome", "comprimento", "largura",
                                  "pavimento", "area_cm2", "linhas_verticais"]
                if coordenadas:
                    _extraidos_lj.append("coordenadas")
                if dados.get("modo_selecionado"):
                    _extraidos_lj.append("modo_selecionado")
                laje_dict.update(_build_sa_meta("LJ", laje_dict, _extraidos_lj))
                lajes_salvos[nome] = laje_dict

                # Salvar JSON individual
                out_path = self.fase4_path / "JSON_Lajes" / f"{nome}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(laje_dict, f, ensure_ascii=False, indent=2)

                self.stats["lajes"] += 1
                log.info(f"  ✅ Laje {nome}: {comprimento}x{largura}cm, {len(laje.linhas_verticais)} cortes")

            except Exception as e:
                log.error(f"  ❌ Laje {nome}: {e}")
                self.stats["errors"] += 1

        # Salvar lajes_salvas.json
        salvos_path = self.fase4_path / "lajes_salvas.json"
        simplified = {}
        for nome_orig, dados in fichas.items():
            if not nome_orig.startswith("_"):
                simplified[nome_orig] = {
                    "comprimento": dados.get("comprimento", 0),
                    "largura": dados.get("largura", 0),
                    "area_cm2": dados.get("area_cm2", 0)
                }
        with open(salvos_path, "w", encoding="utf-8") as f:
            json.dump(simplified, f, ensure_ascii=False, indent=2)

        log.info(f"Lajes: {self.stats['lajes']} processadas -> {salvos_path}")
        return lajes_salvos

    # --------------------------------------------------------------------------
    # OBRAS_SALVAS — formato Robo_Pilares (CAD-7.3)
    # --------------------------------------------------------------------------

    def _gerar_obras_salvas(self):
        """Gera obras_salvas.json e pavimentos_lista.json no formato do PilarAnalyzer.exe."""
        json_dir = self.fase4_path / "JSON_Pilares"
        pilar_files = sorted(json_dir.glob("P*.json"),
                             key=lambda p: int(p.stem[1:]) if p.stem[1:].isdigit() else 999)
        if not pilar_files:
            log.warning("_gerar_obras_salvas: sem JSON_Pilares, ignorando")
            return

        pav = self.pavimento or "12 PAV"
        obra_nome = self.obra_nome

        obras: Dict[str, Any] = {obra_nome: {pav: {}}}
        FACES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

        def empty_aberturas():
            ab = {}
            for side in ("esquerda", "direita"):
                ab[side] = {str(i): {"distancia": "", "largura": "",
                                     "profundidade": "", "posicao": "", "tipo": ""}
                            for i in range(1, 3)}
            return ab

        for pf in pilar_files:
            with open(pf, encoding="utf-8") as f:
                pj = json.load(f)

            numero = str(pj.get("numero", pf.stem[1:]))
            comprimento = pj.get("comprimento", 0.0)
            largura = pj.get("largura", 0.0)
            altura = pj.get("altura", 280.0)
            g1 = pj.get("grade_1", 0.0)
            g2 = pj.get("grade_2", 0.0)
            d1 = pj.get("distancia_1", 14.0)

            # Paineis por face (h1..h5, larg1..3)
            paineis = {}
            for face in FACES:
                larg1 = pj.get(f"larg1_{face}", 0.0)
                paineis[face] = {
                    "laje": "",
                    "posicao_laje": "5",
                    "larg1": str(int(larg1)) if larg1 else "244",
                    "larg2": "0", "larg3": "0",
                    "h1": str(int(pj.get(f"h1_{face}", 0))),
                    "h2": str(int(pj.get(f"h2_{face}", 0))),
                    "h3": str(int(pj.get(f"h3_{face}", 0))),
                    "h4": str(int(pj.get(f"h4_{face}", 0))),
                    "h5": str(int(pj.get(f"h5_{face}", 0))),
                    "aberturas": empty_aberturas()
                }

            dados = {
                "numero": numero,
                "nome": pj.get("nome", f"P{numero}"),
                "obra": obra_nome,
                "comprimento": str(int(comprimento)),
                "largura": str(int(largura)),
                "pavimento": pav,
                "pavimento_numero": "1",
                "pavimento_anterior": pav,
                "nivel_saida": str(self.nivel_saida),
                "nivel_chegada": str(self.nivel_chegada),
                "nivel_diferencial": "",
                "altura": str(int(altura)),
                "parafusos": {f"par_{i}_{i+1 if i<8 else 9}": "0" for i in range(1, 9)},
                "grades": {
                    "grade_1": str(int(g1)) if g1 else "0",
                    "distancia_1": str(int(d1)) if d1 else "14",
                    "grade_2": str(int(g2)) if g2 else "",
                    "distancia_2": "",
                    "grade_3": ""
                },
                "pilar_especial": False,
                "detalhes_grades": {}, "altura_detalhes_grades": "",
                "grades_grupo2": {}, "detalhes_grades_grupo2": {},
                "altura_detalhes_grades_b": "", "ruler_grupo1": {},
                "paineis": paineis,
                "modo_calculo": "automatico",
                "tipo_distribuicao_largura": "padrao",
                "checkbox_descontar_laje": False,
                "checkbox_descontar_aberturas": False,
                "hachura_paineis": False,
                "m2_total": 0.0
            }
            obras[obra_nome][pav][numero] = {
                "dados": dados,
                "item_id": f"{numero}_{pav}",
                "locks": {}
            }

        out_path = self.fase4_path / "obras_salvas.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(obras, f, ensure_ascii=False, indent=2)

        # pavimentos_lista.json
        pav_lista = {obra_nome: {"pavimentos": [pav], "pavimentos_data": {
            pav: {"nome": pav, "numero": "1",
                  "nivel_chegada": str(self.nivel_chegada),
                  "nivel_saida": str(self.nivel_saida)}}}}
        pav_path = self.fase4_path / "pavimentos_lista.json"
        with open(pav_path, "w", encoding="utf-8") as f:
            json.dump(pav_lista, f, ensure_ascii=False, indent=2)

        log.info(f"obras_salvas.json: {len(pilar_files)} pilares → {out_path}")

    # --------------------------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------------------------

    def _load_fase3_fichas(self, tipo: str, filename: str) -> Dict[str, Any]:
        """Carregar fichas da Fase 3. Tenta paths alternatives."""
        # Nome canônico gerado pelos scripts de extração
        canonical = {
            "Pilares": "pilares_bh.json",
            "Vigas": "vigas_dim.json",
            "Lajes": "lajes_data.json",
        }
        extra = canonical.get(tipo)
        candidates = []
        # Para Pilares: pilares_bh.json tem dados corretos por pavimento; pilares.json acumula stale
        # Para Vigas/Lajes: o arquivo primário (vigas.json, lajes.json) é o integrado correto
        if tipo == "Pilares" and extra and extra != filename:
            candidates.append(self.fase3_path / tipo / extra)
        candidates.append(self.fase3_path / tipo / filename)
        if tipo != "Pilares" and extra and extra != filename:
            candidates.append(self.fase3_path / tipo / extra)
        candidates += [
            self.fase3_path / f"Dados_Interpretacao_{tipo}" / filename,
            self.fase3_path / filename.replace(".json", f"_{tipo.lower()}.json"),
        ]
        for path in candidates:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    log.info(f"Carregado: {path} ({len(data)} itens)")
                    return data
                except json.JSONDecodeError as e:
                    log.error(f"JSON corrompido em {path}: {e} — pulando")
                    continue
        log.warning(f"Fichas de {tipo} nao encontradas em {self.fase3_path}")
        return {}

    def _relatorio_completude(self):
        """Lê todos os JSONs de Fase-4 e reporta completude SA por tipo."""
        totals = {"PL": [], "LV": [], "FV": [], "LJ": []}
        dirs = {
            "PL": self.fase4_path / "JSON_Pilares",
            "LV": self.fase4_path / "JSON_Vigas_Laterais",
            "FV": self.fase4_path / "JSON_Vigas_Fundo",
            "LJ": self.fase4_path / "JSON_Lajes",
        }
        for tipo, d in dirs.items():
            for jf in d.glob("*.json"):
                try:
                    with open(jf, encoding="utf-8") as f:
                        data = json.load(f)
                    meta = data.get("_sa_meta")
                    if meta:
                        totals[tipo].append(meta.get("completude_pct", 0))
                except Exception:
                    pass

        log.info("=== RELATÓRIO DE COMPLETUDE SA ===")
        for tipo, scores in totals.items():
            if scores:
                avg = round(sum(scores) / len(scores), 1)
                low = [s for s in scores if s < 80]
                log.info(f"  {tipo}: {len(scores)} itens | média={avg}% | abaixo_80%={len(low)}")
            else:
                log.info(f"  {tipo}: 0 itens")
        log.info("==================================")

    def run(self):
        """Executar pipeline completo."""
        log.info(f"=== motor_fase4.py | Obra: {self.obra_nome} | Pav: {self.pavimento or 'Todos'} ===")

        self.process_pilares()
        self.process_vigas()
        self.process_lajes()

        # Gerar obras_salvas.json no formato do robô (CAD-7.3)
        self._gerar_obras_salvas()

        log.info(f"=== RESULTADO: {self.stats['pilares']} pilares, {self.stats['vigas']} vigas, {self.stats['lajes']} lajes | {self.stats['errors']} erros ===")
        self._relatorio_completude()

        # Salvar relatorio
        relatorio = {
            "obra": self.obra_nome,
            "pavimento": self.pavimento,
            "stats": self.stats,
            "output_path": str(self.fase4_path)
        }
        relatorio_path = self.fase4_path / "motor_fase4_relatorio.json"
        with open(relatorio_path, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2)

        return self.stats


# ==============================================================================
# CLI
# ==============================================================================

def _load_discovery(obra_path: Path) -> dict:
    """
    Carrega dxf_discovery.json do diretório pai de obra_path (DADOS-OBRAS).
    Retorna dict {pav: {PL: path, LV: path, ...}} para a obra, ou {} se não encontrado.
    """
    discovery_file = obra_path.parent / "dxf_discovery.json"
    if not discovery_file.exists():
        # Fallback: buscar dentro da obra
        discovery_file = obra_path / "dxf_discovery.json"
    if not discovery_file.exists():
        log.warning(f"dxf_discovery.json nao encontrado em {obra_path.parent}")
        return {}
    try:
        data = json.loads(discovery_file.read_text(encoding="utf-8-sig"))
        obra_nome = obra_path.name
        obra_data = data.get(obra_nome, {})
        if not obra_data:
            log.warning(f"Obra '{obra_nome}' nao encontrada em dxf_discovery.json")
        return obra_data
    except Exception as e:
        log.error(f"Erro lendo dxf_discovery.json: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(description="motor_fase4 — Fase 4 Sincronizacao Headless")
    parser.add_argument("--obra", required=True, help="Path da obra (ex: DADOS-OBRAS/Obra_TREINO_21)")
    parser.add_argument("--pavimento", default=None, help="Nome do pavimento (ex: '12 PAV'). Se omitido: processa todos.")
    parser.add_argument("--all-pavimentos", action="store_true",
                        help="Processa TODOS os pavimentos via dxf_discovery.json")
    parser.add_argument("--nivel-chegada", type=float, default=0.0, help="Nivel de chegada em cm (default: 0)")
    parser.add_argument("--nivel-saida", type=float, default=280.0, help="Nivel de saida em cm (default: 280)")

    args = parser.parse_args()

    # AC-1: --all-pavimentos lê discovery e itera por pavimento
    if args.all_pavimentos:
        obra_path = Path(args.obra)
        discovery = _load_discovery(obra_path)

        if not discovery:
            log.error("Nenhum pavimento encontrado em dxf_discovery.json")
            sys.exit(1)

        total_pavs = len(discovery)
        processados = 0
        falhas = 0

        log.info(f"=== --all-pavimentos | Obra: {obra_path.name} | {total_pavs} pavimentos ===")

        for pav_nome, dxfs in discovery.items():
            has_pl = dxfs.get("PL") and Path(str(dxfs["PL"])).exists()

            # AC-3: skip se sem DXF PL válido
            if not has_pl:
                log.warning(f"[SKIP] {pav_nome}: DXF PL ausente ou não encontrado")
                falhas += 1
                continue

            log.info(f"--- Processando: {pav_nome} ---")
            try:
                motor = MotorFase4(
                    obra_path=str(obra_path),
                    pavimento=pav_nome,
                    nivel_chegada=args.nivel_chegada,
                    nivel_saida=args.nivel_saida
                )
                stats = motor.run()
                processados += 1
                log.info(f"  OK: {pav_nome} — {stats['pilares']}P {stats['vigas']}V {stats['lajes']}L {stats['errors']}err")
            except Exception as e:
                log.error(f"  FALHOU: {pav_nome} — {e}")
                falhas += 1

        # AC-5: relatório final
        log.info(f"=== RESULTADO MULTI-PAV: {processados}/{total_pavs} processados, {falhas} falhas ===")
        sys.exit(1 if processados == 0 else 0)

    else:
        # AC-4: compatibilidade retroativa — modo single pavimento
        motor = MotorFase4(
            obra_path=args.obra,
            pavimento=args.pavimento,
            nivel_chegada=args.nivel_chegada,
            nivel_saida=args.nivel_saida
        )
        stats = motor.run()
        sys.exit(1 if stats["errors"] > 0 and stats["pilares"] + stats["vigas"] + stats["lajes"] == 0 else 0)


if __name__ == "__main__":
    main()
