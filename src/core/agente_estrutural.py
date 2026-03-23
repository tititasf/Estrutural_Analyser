# -*- coding: utf-8 -*-
"""
agente_estrutural.py - Pipeline Principal do CAD-ANALYZER
==========================================================

Agente estrutural completo que orquestra a extracaoo de entidades DXF,
construcao de grafo espacial, interpretacao semantica, validacao cruzada,
gravacao em banco de dados SQLite (project_data.vision) e checkpoint
opcional via Claude CLI.

Familias DXF suportadas:
  - TQS:      Layers numericos predominantes, SOLID, sem DIMENSION
  - METHODUS:  Prefixo 'MTH-' em layers
  - EBERICK:   Prefixo 'TX*' em layers
  - BIM:       Layers descritivos (CONCRETO, Paineis, etc.)

Pipeline:
  ExtratorDXF -> GrafoEstrutural -> InterpretadorEstrutural
  -> RelatorioValidacao -> GravadorDB [-> ClaudeCheckpoint]

Uso CLI:
  python agente_estrutural.py {obra} {pavimento}
  python agente_estrutural.py {obra}
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── RAG Validation (graceful degradation se módulos ausentes) ────────────────
try:
    _SCRIPTS = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts')
    if _SCRIPTS not in sys.path:
        sys.path.insert(0, os.path.abspath(_SCRIPTS))
    from rag_plausibility import PlausibilityChecker as _PlausibilityChecker
    from rag_validator    import StructuralValidator  as _StructuralValidator
    _rag_plaus     = _PlausibilityChecker()
    _rag_validator = _StructuralValidator()
    _RAG_OK        = True
except Exception as _rag_err:
    _RAG_OK = False
    logging.getLogger(__name__).debug(f"RAG modules not available: {_rag_err}")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Regex patterns for structural element names
# Sprint-B: expandir variacoes P-1, P1.1, PC1, P.1 (pilar_name 32.8% -> >60%)
RE_PILAR = re.compile(
    r'^(PC?\.?-?\d+([A-Z]|\.\d+|-\d+)?|P-\d+[A-Z]?)$',
    re.IGNORECASE,
)
RE_VIGA = re.compile(
    r'^(V|BA|VB|VT|VC)\.?-?\d+([A-Z]|\.\d+|/\d+)?$',
    re.IGNORECASE,
)
RE_LAJE_H = re.compile(r'h\s*[=:]\s*([\d,.]+)', re.IGNORECASE)
# Sprint-B: dim aceita espacos, separadores x/X/*/x e multilinha (viga_dim 46.4% -> >70%)
RE_DIM = re.compile(
    r'(\d{1,3})\s*[xX*\/]\s*(\d{1,3})',
)
RE_DIM_BH = re.compile(
    r'b\s*=\s*(\d{1,3}).*?h\s*=\s*(\d{1,3})',
    re.IGNORECASE | re.DOTALL,
)

# Search radii (DXF units, typically mm)
PILAR_SEARCH_RADIUS = 800.0
VIGA_SEARCH_RADIUS = 1200.0
LAJE_SEARCH_RADIUS = 1500.0
DIM_SEARCH_RADIUS = 600.0
CLUSTER_RADIUS = 500.0

# Side angle boundaries (degrees)
SIDE_BOUNDARIES = {
    'A': (45, 135),    # top
    'B': (-45, 45),    # right
    'C': (-135, -45),  # bottom
    'D': (135, 225),   # left (or equivalently 135..-135 wrapping)
}


# ---------------------------------------------------------------------------
# 1. Dataclasses de Entidade
# ---------------------------------------------------------------------------

@dataclass
class Entidade:
    """Entidade base DXF com posicao e metadados."""
    id: str = ""
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    layer: str = ""
    family: str = ""
    text: str = ""

    @property
    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class PilarDXF:
    """Pilar extraido do DXF."""
    id: str = ""
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    dim_str: str = ""
    dim_l: float = 0.0
    dim_a: float = 0.0
    geometry: Optional[List[Tuple[float, float]]] = None
    layer: str = ""
    family: str = ""

    @property
    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class VigaDXF:
    """Viga extraida do DXF."""
    id: str = ""
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    dim_str: str = ""
    dim_l: float = 0.0
    dim_a: float = 0.0
    geometry_lines: Optional[List[Any]] = None
    layer: str = ""
    family: str = ""

    @property
    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class LajeDXF:
    """Laje extraida do DXF."""
    id: str = ""
    name: str = ""
    x: float = 0.0
    y: float = 0.0
    contour_pts: Optional[List[Tuple[float, float]]] = None
    h_val: float = 0.0
    layer: str = ""
    family: str = ""

    @property
    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class DimText:
    """Texto de dimensao extraido do DXF."""
    x: float = 0.0
    y: float = 0.0
    text: str = ""
    valor: float = 0.0
    is_dim: bool = False

    @property
    def pos(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class ResultadoProcessamento:
    """Resultado agregado do processamento de um pavimento."""
    obra: str = ""
    pavimento: str = ""
    pilares: List[Any] = field(default_factory=list)
    vigas: List[Any] = field(default_factory=list)
    lajes: List[Any] = field(default_factory=list)
    sides_preenchidos: int = 0
    sides_total: int = 0
    fields_preenchidos: int = 0
    fields_total: int = 0
    problemas: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)

    @property
    def pct_fields(self) -> float:
        """Percentual de campos de vigas preenchidos."""
        if self.fields_total == 0:
            return 0.0
        return round(100.0 * self.fields_preenchidos / self.fields_total, 1)

    @property
    def pct_sides(self) -> float:
        """Percentual de lados de pilares preenchidos."""
        if self.sides_total == 0:
            return 0.0
        return round(100.0 * self.sides_preenchidos / self.sides_total, 1)

    def relatorio(self) -> str:
        """Retorna string formatada com relatorio completo."""
        sep = "=" * 60
        lines = [
            sep,
            f"RELATORIO - {self.obra} {self.pavimento}",
            sep,
            f"Entidades: {len(self.pilares)} pilares, "
            f"{len(self.vigas)} vigas, {len(self.lajes)} lajes",
            f"Pilar sides: {self.pct_sides}% "
            f"({self.sides_preenchidos}/{self.sides_total})",
            f"Viga fields: {self.pct_fields}% "
            f"({self.fields_preenchidos}/{self.fields_total})",
        ]

        if self.problemas:
            lines.append(f"PROBLEMAS ({len(self.problemas)} total):")
            for p in self.problemas:
                lines.append(f"  - {p}")

        if self.insights:
            lines.append(f"INSIGHTS ({len(self.insights)} total):")
            for i in self.insights:
                lines.append(f"  + {i}")

        lines.append(sep)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. ExtratorDXF
# ---------------------------------------------------------------------------

class ExtratorDXF:
    """
    Extrai entidades estruturais do DXF usando ezdxf.

    Suporta familias: TQS, METHODUS (MTH-), EBERICK (TX*), BIM.
    Retorna tupla com pilares, vigas, lajes, dims, laje_dims, polylines, lines.
    """

    def __init__(self, dxf_path: str) -> None:
        try:
            import ezdxf
        except ImportError:
            raise ImportError(
                "ezdxf nao instalado. Instale com: pip install ezdxf"
            )

        self.dxf_path = dxf_path
        self.doc = ezdxf.readfile(dxf_path)
        self.msp = self.doc.modelspace()
        self.family = self._detect_family()
        logger.info(f"DXF carregado: {dxf_path} (familia: {self.family})")

    def _detect_family(self) -> str:
        """
        Detecta familia DXF analisando os nomes de layers.

        Returns:
            'TQS', 'METHODUS', 'EBERICK', ou 'BIM'.
        """
        layers = [layer.dxf.name for layer in self.doc.layers]
        layer_names_upper = [l.upper() for l in layers]

        # Check for METHODUS (MTH- prefix)
        mth_count = sum(1 for l in layer_names_upper if l.startswith('MTH-'))
        if mth_count > 0:
            return 'METHODUS'

        # Check for EBERICK (TX* prefix)
        tx_count = sum(1 for l in layer_names_upper if l.startswith('TX'))
        if tx_count > len(layers) * 0.15:
            return 'EBERICK'

        # Check for TQS (predominantly numeric layers)
        numeric_count = sum(
            1 for l in layers if re.match(r'^\d+$', l)
        )
        if numeric_count > len(layers) * 0.3:
            return 'TQS'

        # Check for BIM (descriptive layers)
        bim_keywords = [
            'CONCRETO', 'PAINEI', 'BEAM', 'COLUMN', 'SLAB',
            'PILAR', 'VIGA', 'LAJE', 'F-', 'S-'
        ]
        bim_count = sum(
            1 for l in layer_names_upper
            if any(kw in l for kw in bim_keywords)
        )
        if bim_count > 0:
            return 'BIM'

        return 'TQS'  # fallback

    def extrair(self) -> Tuple[
        List[Dict], List[Dict], List[Dict], List[DimText],
        List[DimText], List[Dict], List[Dict]
    ]:
        """
        Extrai todas as entidades relevantes do DXF.

        Returns:
            Tupla com:
              - pilares_txt: textos que casam com padroes de pilar
              - vigas_txt: textos que casam com padroes de viga
              - lajes_txt: textos que casam com padroes de laje/espessura
              - dims: textos de dimensoes (NNxNN)
              - laje_dims: textos com h= ou espessura de laje
              - polylines: LWPOLYLINE extraidas com pontos e fechamento
              - lines: LINE extraidas com start/end
        """
        pilares_txt: List[Dict] = []
        vigas_txt: List[Dict] = []
        lajes_txt: List[Dict] = []
        dims: List[DimText] = []
        laje_dims: List[DimText] = []
        polylines: List[Dict] = []
        lines: List[Dict] = []

        for entity in self.msp:
            etype = entity.dxftype()
            layer = getattr(entity.dxf, 'layer', '0')

            # --- TEXT / MTEXT ---
            if etype in ('TEXT', 'MTEXT'):
                if etype == 'TEXT':
                    text = getattr(entity.dxf, 'text', '').strip()
                    ip = getattr(entity.dxf, 'insert', None)
                else:
                    # Sprint-B fix: plain_mtext() nao existe em todas versoes ezdxf
                    text = ''
                    for method_name in ('plain_text', 'plain_mtext'):
                        try:
                            fn = getattr(entity, method_name, None)
                            if callable(fn):
                                result = fn()
                                if result:
                                    text = str(result).strip()
                                    break
                        except Exception:
                            pass
                    if not text:
                        try:
                            raw = getattr(entity.dxf, 'text', '') or ''
                            text = re.sub(r'\\[A-Za-z][^;]*;', '', str(raw))
                            text = re.sub(r'\\[\\{}|]', '', text).strip()
                        except Exception:
                            pass
                    ip = getattr(entity.dxf, 'insert', None)

                if not text or not ip:
                    continue

                x, y = float(ip.x), float(ip.y)
                txt_entry = {
                    'text': text,
                    'x': x,
                    'y': y,
                    'pos': (x, y),
                    'layer': layer,
                }

                text_upper = text.upper().strip()

                # Pilar pattern: P.?N[A-Z]?
                if RE_PILAR.match(text_upper):
                    pilares_txt.append(txt_entry)

                # Viga pattern: V|BA|VB|VT|VC + digits
                elif RE_VIGA.match(text_upper):
                    vigas_txt.append(txt_entry)

                # Dimension pattern: NNxNN, NN/NN, b=NN h=NN (Sprint-B: MTEXT multilinha)
                # Testar cada linha do texto (MTEXT pode ter \n)
                text_lines = text.replace('\r', '').split('\n')
                for tline in text_lines:
                    dim_match = RE_DIM.search(tline)
                    if not dim_match:
                        dim_match = RE_DIM_BH.search(text)  # span multiplas linhas
                    if dim_match:
                        val_l = float(dim_match.group(1))
                        val_a = float(dim_match.group(2))
                        dims.append(DimText(
                            x=x, y=y,
                            text=text,
                            valor=val_l,
                            is_dim=True,
                        ))
                        break

                # Laje/espessura: h=N or text starting with L
                h_match = RE_LAJE_H.search(text)
                if h_match:
                    h_val = float(h_match.group(1).replace(',', '.'))
                    laje_dims.append(DimText(
                        x=x, y=y,
                        text=text,
                        valor=h_val,
                        is_dim=False,
                    ))
                    lajes_txt.append(txt_entry)
                elif re.match(r'^L\d+', text_upper):
                    lajes_txt.append(txt_entry)

            # --- LWPOLYLINE ---
            elif etype in ('LWPOLYLINE', 'POLYLINE'):
                try:
                    pts = [(float(p[0]), float(p[1])) for p in entity.get_points('xy')]
                except Exception:
                    continue
                if len(pts) < 2:
                    continue

                is_closed = getattr(entity.dxf, 'flags', 0) & 1 == 1
                if hasattr(entity, 'is_closed'):
                    is_closed = entity.is_closed

                # Sprint-C: extrair bulges para deteccao de pilar cambotado
                bulges = []
                has_arcs = False
                try:
                    if etype == 'LWPOLYLINE':
                        bulges = [
                            float(p[4]) if len(p) > 4 else 0.0
                            for p in entity.get_points('xyzsb')
                        ]
                    elif etype == 'POLYLINE':
                        bulges = [
                            float(getattr(v.dxf, 'bulge', 0.0))
                            for v in entity.vertices
                        ]
                    has_arcs = any(abs(b) > 0.01 for b in bulges)
                    max_bulge = max((abs(b) for b in bulges), default=0.0)
                    arc_segments = sum(1 for b in bulges if abs(b) > 0.01)
                except Exception:
                    bulges = []
                    max_bulge = 0.0
                    arc_segments = 0

                polylines.append({
                    'points': pts,
                    'closed': is_closed,
                    'layer': layer,
                    'bulges': bulges,
                    'has_arcs': has_arcs,
                    'max_bulge': max_bulge if has_arcs else 0.0,
                    'arc_segments': arc_segments,
                })

            # --- LINE ---
            elif etype == 'LINE':
                try:
                    s = entity.dxf.start
                    e = entity.dxf.end
                    lines.append({
                        'start': (float(s.x), float(s.y)),
                        'end': (float(e.x), float(e.y)),
                        'layer': layer,
                    })
                except Exception:
                    continue

        logger.info(
            f"Extracao concluida: {len(pilares_txt)} pilares, "
            f"{len(vigas_txt)} vigas, {len(lajes_txt)} lajes, "
            f"{len(dims)} dims, {len(laje_dims)} laje_dims, "
            f"{len(polylines)} polylines, {len(lines)} lines"
        )

        return pilares_txt, vigas_txt, lajes_txt, dims, laje_dims, polylines, lines

    def _gerar_lajes_sinteticas(
        self,
        laje_dims: List[DimText],
        polylines: List[Dict],
        lines: List[Dict],
    ) -> List[LajeDXF]:
        """
        Agrupa dims de laje em clusters espaciais para gerar lajes sinteticas
        quando nao ha texto explicito de laje (L1, L2...).

        Args:
            laje_dims: Textos com h= detectados.
            polylines: Polilinhas do DXF.
            lines: Linhas do DXF.

        Returns:
            Lista de LajeDXF com name='SYNTHETIC' e id='synth_N'.
        """
        if not laje_dims:
            return []

        # Cluster dims by proximity
        used = set()
        clusters: List[List[DimText]] = []

        for i, d in enumerate(laje_dims):
            if i in used:
                continue
            cluster = [d]
            used.add(i)
            for j, d2 in enumerate(laje_dims):
                if j in used:
                    continue
                dist = math.hypot(d.x - d2.x, d.y - d2.y)
                if dist < CLUSTER_RADIUS:
                    cluster.append(d2)
                    used.add(j)
            clusters.append(cluster)

        sinteticas: List[LajeDXF] = []
        for idx, cluster in enumerate(clusters):
            cx = sum(d.x for d in cluster) / len(cluster)
            cy = sum(d.y for d in cluster) / len(cluster)
            h_val = cluster[0].valor if cluster else 0.0

            sinteticas.append(LajeDXF(
                id=f"synth_{idx}",
                name="SYNTHETIC",
                x=cx,
                y=cy,
                h_val=h_val,
                layer="synthetic",
                family=self.family,
            ))

        logger.info(f"Geradas {len(sinteticas)} lajes sinteticas")
        return sinteticas


# ---------------------------------------------------------------------------
# 3. GrafoEstrutural
# ---------------------------------------------------------------------------

class GrafoEstrutural:
    """
    Grafo de relacoes espaciais entre entidades estruturais.

    Dados os pilares, vigas, lajes extraidos do DXF, monta relacionamentos
    de vizinhanca baseados em distancia euclidiana e direcao angular (A/B/C/D).
    """

    def __init__(self) -> None:
        self.pilares: Dict[str, PilarDXF] = {}
        self.vigas: Dict[str, VigaDXF] = {}
        self.lajes: Dict[str, LajeDXF] = {}

    @staticmethod
    def dist(a: Any, b: Any) -> float:
        """Distancia euclidiana entre duas entidades com .x e .y."""
        return math.hypot(a.x - b.x, a.y - b.y)

    @staticmethod
    def angulo(de: Any, para: Any) -> float:
        """
        Angulo em graus de 'de' para 'para'.
        0 = direita (eixo X positivo), 90 = cima (eixo Y positivo).
        Retorna valor em [-180, 180].
        """
        dx = para.x - de.x
        dy = para.y - de.y
        return math.degrees(math.atan2(dy, dx))

    @staticmethod
    def lado_pilar(angulo_graus: float) -> str:
        """
        Classifica o angulo em lado do pilar.

        A = topo (45 a 135 graus)
        B = direita (-45 a 45 graus)
        C = baixo (-135 a -45 graus)
        D = esquerda (fora dos demais)

        Args:
            angulo_graus: Angulo em graus [-180, 180].

        Returns:
            Lado 'A', 'B', 'C' ou 'D'.
        """
        a = angulo_graus
        if 45 <= a < 135:
            return 'A'
        elif -45 <= a < 45:
            return 'B'
        elif -135 <= a < -45:
            return 'C'
        else:
            return 'D'

    def vizinhos_pilar(
        self, entidade: PilarDXF, raio: float, max_n: int = 4
    ) -> List[Tuple[PilarDXF, float]]:
        """Retorna pilares vizinhos dentro do raio, ordenados por distancia."""
        vizinhos = []
        for pid, p in self.pilares.items():
            if p.id == entidade.id:
                continue
            d = self.dist(entidade, p)
            if d <= raio:
                vizinhos.append((p, d))
        vizinhos.sort(key=lambda x: x[1])
        return vizinhos[:max_n]

    def vizinhos_viga(
        self, entidade: Any, raio: float, max_n: int = 4
    ) -> List[Tuple[VigaDXF, float]]:
        """Retorna vigas vizinhas dentro do raio, ordenadas por distancia."""
        vizinhos = []
        for vid, v in self.vigas.items():
            d = self.dist(entidade, v)
            if d <= raio:
                vizinhos.append((v, d))
        vizinhos.sort(key=lambda x: x[1])
        return vizinhos[:max_n]

    def vizinhos_laje(
        self, entidade: Any, raio: float, max_n: int = 4
    ) -> List[Tuple[LajeDXF, float]]:
        """Retorna lajes vizinhas dentro do raio, ordenadas por distancia."""
        vizinhos = []
        for lid, lj in self.lajes.items():
            d = self.dist(entidade, lj)
            if d <= raio:
                vizinhos.append((lj, d))
        vizinhos.sort(key=lambda x: x[1])
        return vizinhos[:max_n]

    def construir(
        self,
        pilares_txt: List[Dict],
        vigas_txt: List[Dict],
        lajes_txt: List[Dict],
        dims: List[DimText],
        laje_dims: List[DimText],
        polylines: List[Dict],
        lines: List[Dict],
        family: str,
    ) -> None:
        """
        Constroi grafo a partir de entidades extraidas pelo ExtratorDXF.

        Para cada texto de pilar/viga/laje, cria a entidade correspondente,
        associa dimensoes proximas e polilinhas de geometria.

        Args:
            pilares_txt: Textos que casam com padroes de pilar.
            vigas_txt: Textos que casam com padroes de viga.
            lajes_txt: Textos que casam com padroes de laje.
            dims: Textos de dimensao NNxNN.
            laje_dims: Textos com h=N.
            polylines: Polilinhas do DXF.
            lines: Linhas do DXF.
            family: Familia do DXF ('TQS', 'METHODUS', 'EBERICK', 'BIM').
        """
        # --- Build Pilares ---
        for i, pt in enumerate(pilares_txt):
            pid = f"P_{i}_{pt['text']}"
            pilar = PilarDXF(
                id=pid,
                name=pt['text'],
                x=pt['x'],
                y=pt['y'],
                layer=pt.get('layer', ''),
                family=family,
            )

            # Associate dimension
            dim = self._dim_mais_proximo(pilar, dims, DIM_SEARCH_RADIUS)
            if dim:
                pilar.dim_str = dim.text
                parts = re.split(r'[xX*]', dim.text)
                if len(parts) >= 2:
                    try:
                        pilar.dim_l = float(parts[0])
                        pilar.dim_a = float(parts[1])
                    except ValueError:
                        pass

            # Associate geometry (closest closed polyline)
            poly = self._polylines_proximo(pilar, polylines, PILAR_SEARCH_RADIUS)
            if poly and poly.get('closed'):
                pilar.geometry = poly.get('points')

            self.pilares[pid] = pilar

        # --- Build Vigas ---
        for i, vt in enumerate(vigas_txt):
            vid = f"V_{i}_{vt['text']}"
            viga = VigaDXF(
                id=vid,
                name=vt['text'],
                x=vt['x'],
                y=vt['y'],
                layer=vt.get('layer', ''),
                family=family,
            )

            # Associate dimension
            dim = self._dim_mais_proximo(viga, dims, DIM_SEARCH_RADIUS)
            if dim:
                viga.dim_str = dim.text
                parts = re.split(r'[xX*]', dim.text)
                if len(parts) >= 2:
                    try:
                        viga.dim_l = float(parts[0])
                        viga.dim_a = float(parts[1])
                    except ValueError:
                        pass

            # Associate geometry lines (nearby lines and polylines)
            nearby_lines = self._lines_proximo(viga, lines, VIGA_SEARCH_RADIUS)
            nearby_polys = self._polylines_proximo(
                viga, polylines, VIGA_SEARCH_RADIUS, all_matches=True
            )
            viga.geometry_lines = []
            if nearby_lines:
                viga.geometry_lines.extend(nearby_lines)
            if nearby_polys:
                if isinstance(nearby_polys, list):
                    viga.geometry_lines.extend(nearby_polys)
                else:
                    viga.geometry_lines.append(nearby_polys)

            self.vigas[vid] = viga

        # --- Handle METHODUS-specific layers ---
        if family == 'METHODUS':
            self._process_methodus_dims(dims, laje_dims, polylines)

        # --- Viga dimension inheritance ---
        for vid, v in self.vigas.items():
            if not v.dim_str:
                self._herdar_dimensoes(v)

        # --- Build Lajes ---
        for i, lt in enumerate(lajes_txt):
            lid = f"L_{i}_{lt['text']}"

            # Find h= value nearby
            h_val = 0.0
            ld = self._laje_dim_proximo(
                type('Obj', (), {'x': lt['x'], 'y': lt['y']})(),
                laje_dims,
                LAJE_SEARCH_RADIUS,
            )
            if ld:
                h_val = ld.valor

            laje = LajeDXF(
                id=lid,
                name=lt['text'],
                x=lt['x'],
                y=lt['y'],
                h_val=h_val,
                layer=lt.get('layer', ''),
                family=family,
            )

            # Associate contour (closest closed polyline)
            poly = self._polylines_proximo(laje, polylines, LAJE_SEARCH_RADIUS)
            if poly and poly.get('closed'):
                laje.contour_pts = poly.get('points')

            self.lajes[lid] = laje

        logger.info(
            f"Grafo construido: {len(self.pilares)} pilares, "
            f"{len(self.vigas)} vigas, {len(self.lajes)} lajes"
        )

    def _process_methodus_dims(
        self,
        dims: List[DimText],
        laje_dims: List[DimText],
        polylines: List[Dict],
    ) -> None:
        """
        Processa layers especificos do METHODUS para enriquecer
        dimensoes de pilares e vigas.

        Layers relevantes: 'MTH-DIM-PILAR', 'MTH-DIM-VIGA', 'MTH-212'.
        """
        # Filter dims from METHODUS-specific layers
        mth_pilar_dims = [
            d for d in dims
            if hasattr(d, 'layer') and 'MTH-DIM-PILAR' in getattr(d, 'layer', '').upper()
        ]
        mth_viga_dims = [
            d for d in dims
            if hasattr(d, 'layer') and 'MTH-DIM-VIGA' in getattr(d, 'layer', '').upper()
        ]

        # Re-associate METHODUS dims if available
        if mth_pilar_dims:
            for pid, p in self.pilares.items():
                if not p.dim_str:
                    dim = self._dim_mais_proximo(p, mth_pilar_dims, DIM_SEARCH_RADIUS)
                    if dim:
                        p.dim_str = dim.text
        if mth_viga_dims:
            for vid, v in self.vigas.items():
                if not v.dim_str:
                    dim = self._dim_mais_proximo(v, mth_viga_dims, DIM_SEARCH_RADIUS)
                    if dim:
                        v.dim_str = dim.text

    def _herdar_dimensoes(self, v: VigaDXF) -> None:
        """
        Vigas sem dimensao herdam da vizinha mais proxima que tenha dimensao.

        Prioriza vizinhas da mesma familia (mesmo prefixo de nome, ex: 'V').
        """
        if v.dim_str:
            return

        # Extract prefix from viga name (e.g., 'V' from 'V12a')
        prefix_match = re.match(r'^([A-Z]+)', v.name, re.IGNORECASE)
        prefix = prefix_match.group(1).upper() if prefix_match else 'V'

        best_dist = float('inf')
        best_dim = None

        for vid, other in self.vigas.items():
            if not other.dim_str or other.id == v.id:
                continue

            # Prefer same family prefix
            other_prefix_match = re.match(r'^([A-Z]+)', other.name, re.IGNORECASE)
            other_prefix = other_prefix_match.group(1).upper() if other_prefix_match else ''

            d = self.dist(v, other)
            # Weight same-prefix vigas closer
            effective_dist = d if other_prefix == prefix else d * 1.5

            if effective_dist < best_dist:
                best_dist = effective_dist
                best_dim = other.dim_str

        if best_dim and best_dist < VIGA_SEARCH_RADIUS * 2:
            v.dim_str = best_dim
            parts = re.split(r'[xX*]', best_dim)
            if len(parts) >= 2:
                try:
                    v.dim_l = float(parts[0])
                    v.dim_a = float(parts[1])
                except ValueError:
                    pass
            logger.debug(f"Viga {v.name}: herdou dim '{best_dim}' (dist={best_dist:.0f})")

    def _dim_mais_proximo(
        self, entidade: Any, dims: List[DimText], raio: float
    ) -> Optional[DimText]:
        """Encontra o texto de dimensao mais proximo da entidade dentro do raio."""
        best_dist = raio
        best = None
        for d in dims:
            dist = math.hypot(entidade.x - d.x, entidade.y - d.y)
            if dist < best_dist:
                best_dist = dist
                best = d
        return best

    def _laje_dim_proximo(
        self, entidade: Any, laje_dims: List[DimText], raio: float
    ) -> Optional[DimText]:
        """Encontra o texto de laje (h=) mais proximo da entidade dentro do raio."""
        best_dist = raio
        best = None
        for d in laje_dims:
            dist = math.hypot(entidade.x - d.x, entidade.y - d.y)
            if dist < best_dist:
                best_dist = dist
                best = d
        return best

    def _polylines_proximo(
        self,
        entidade: Any,
        polylines: List[Dict],
        raio: float,
        all_matches: bool = False,
    ) -> Any:
        """
        Encontra a polilinha mais proxima da entidade dentro do raio.

        Args:
            entidade: Entidade com .x e .y.
            polylines: Lista de dicts com 'points' e 'closed'.
            raio: Raio de busca.
            all_matches: Se True, retorna lista de todas as polilinhas dentro do raio.

        Returns:
            Dict da polilinha mais proxima, ou lista de dicts se all_matches.
        """
        results = []
        for poly in polylines:
            pts = poly.get('points', [])
            if not pts:
                continue
            # Centroid of polyline
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            dist = math.hypot(entidade.x - cx, entidade.y - cy)
            if dist < raio:
                results.append((poly, dist))

        if not results:
            return [] if all_matches else None

        results.sort(key=lambda x: x[1])

        if all_matches:
            return [r[0] for r in results]
        return results[0][0]

    def _lines_proximo(
        self, entidade: Any, lines: List[Dict], raio: float
    ) -> List[Dict]:
        """Encontra linhas proximas da entidade dentro do raio."""
        results = []
        for line in lines:
            s = line.get('start', (0, 0))
            e = line.get('end', (0, 0))
            mx = (s[0] + e[0]) / 2
            my = (s[1] + e[1]) / 2
            dist = math.hypot(entidade.x - mx, entidade.y - my)
            if dist < raio:
                results.append(line)
        return results


# ---------------------------------------------------------------------------
# 4. InterpretadorEstrutural
# ---------------------------------------------------------------------------

class InterpretadorEstrutural:
    """
    Interpreta semanticamente pilares, vigas e lajes do grafo estrutural.

    Atribui significado aos relacionamentos espaciais (qual viga
    esta em qual lado do pilar, quais sao os apoios de uma viga, etc.).
    """

    def __init__(self, grafo: GrafoEstrutural) -> None:
        self.g = grafo
        self.problemas: List[str] = []
        self.insights: List[str] = []

    def interpretar_pilar(self, pilar: PilarDXF) -> Dict[str, Any]:
        """
        Interpreta um pilar: identifica vigas e lajes em cada lado (A/B/C/D).

        Returns:
            Dict com:
              - sides_data: {A: {segments, label, _l1_n, _l2_n}, B: ..., C: ..., D: ...}
              - links: relacoes com vigas e lajes vizinhas
              - conf_map: mapa de confianca por campo
        """
        sides_data: Dict[str, Dict] = {
            'A': {'segments': [], 'label': '', '_l1_n': '', '_l2_n': ''},
            'B': {'segments': [], 'label': '', '_l1_n': '', '_l2_n': ''},
            'C': {'segments': [], 'label': '', '_l1_n': '', '_l2_n': ''},
            'D': {'segments': [], 'label': '', '_l1_n': '', '_l2_n': ''},
        }
        links: Dict[str, Any] = {}
        conf_map: Dict[str, float] = {}

        # Find neighboring vigas
        vigas_vizinhas = self.g.vizinhos_viga(pilar, PILAR_SEARCH_RADIUS)
        for viga, dist in vigas_vizinhas:
            ang = self.g.angulo(pilar, viga)
            lado = self.g.lado_pilar(ang)
            sides_data[lado]['label'] = viga.name
            sides_data[lado]['segments'].append({
                'name': viga.name,
                'dist': dist,
                'angle': ang,
            })
            links[f'viga_{lado}'] = viga.name
            conf_map[f'viga_{lado}'] = max(0.0, 1.0 - dist / PILAR_SEARCH_RADIUS)

        # Find neighboring lajes
        lajes_vizinhas = self.g.vizinhos_laje(pilar, PILAR_SEARCH_RADIUS)
        for laje, dist in lajes_vizinhas:
            ang = self.g.angulo(pilar, laje)
            lado = self.g.lado_pilar(ang)
            sides_data[lado]['_l1_n'] = laje.name
            links[f'laje_{lado}'] = laje.name
            conf_map[f'laje_{lado}'] = max(0.0, 1.0 - dist / PILAR_SEARCH_RADIUS)

        return {
            'sides_data': sides_data,
            'links': links,
            'conf_map': conf_map,
        }

    def _is_balanco(self, viga_name: str) -> bool:
        """
        Verifica se a viga e um balanco.

        BA* = balanco. VB* tambem pode ser balanco.

        Returns:
            True se nome casa com padrao de balanco.
        """
        return bool(re.match(r'^(BA|VB)\d+', viga_name, re.IGNORECASE))

    def interpretar_viga(self, viga: VigaDXF) -> Dict[str, Any]:
        """
        Interpreta uma viga: identifica apoios, dimensoes e lajes adjacentes.

        Returns:
            Dict com:
              - fields: {numero, dimensao, comprimento_estimado}
              - links: {apoio_ini, apoio_fim, laje_esq, laje_dir}
              - conf_map: mapa de confianca
              - geometry: linhas de geometria
              - pos: posicao (x, y)
              - seg_a, seg_b: segmentos dos lados A e B
        """
        fields: Dict[str, Any] = {
            'numero': viga.name,
            'dimensao': viga.dim_str,
            'comprimento_estimado': 0.0,
        }
        links: Dict[str, str] = {
            'apoio_ini': '',
            'apoio_fim': '',
            'laje_esq': '',
            'laje_dir': '',
        }
        conf_map: Dict[str, float] = {}

        # Find support pillars (closest to the beam endpoints or position)
        pilares_proximos = self.g.vizinhos_pilar(
            type('Obj', (), {'id': viga.id, 'x': viga.x, 'y': viga.y})(),
            VIGA_SEARCH_RADIUS,
            max_n=6,
        )

        if pilares_proximos:
            # Sort by distance, first two are likely supports
            sorted_pilares = sorted(pilares_proximos, key=lambda x: x[1])
            if len(sorted_pilares) >= 1:
                links['apoio_ini'] = sorted_pilares[0][0].name
                conf_map['apoio_ini'] = max(
                    0.0, 1.0 - sorted_pilares[0][1] / VIGA_SEARCH_RADIUS
                )
            if len(sorted_pilares) >= 2:
                links['apoio_fim'] = sorted_pilares[1][0].name
                conf_map['apoio_fim'] = max(
                    0.0, 1.0 - sorted_pilares[1][1] / VIGA_SEARCH_RADIUS
                )

                # Estimate span
                p1 = sorted_pilares[0][0]
                p2 = sorted_pilares[1][0]
                fields['comprimento_estimado'] = round(
                    math.hypot(p1.x - p2.x, p1.y - p2.y), 1
                )

        # Find adjacent slabs (left and right)
        lajes_vizinhas = self.g.vizinhos_laje(viga, LAJE_SEARCH_RADIUS, max_n=4)
        if lajes_vizinhas:
            # Classify slabs based on angle relative to viga
            for laje, dist in lajes_vizinhas:
                ang = self.g.angulo(viga, laje)
                side = self.g.lado_pilar(ang)
                if side in ('A', 'D') and not links['laje_esq']:
                    links['laje_esq'] = laje.name
                    conf_map['laje_esq'] = max(0.0, 1.0 - dist / LAJE_SEARCH_RADIUS)
                elif side in ('B', 'C') and not links['laje_dir']:
                    links['laje_dir'] = laje.name
                    conf_map['laje_dir'] = max(0.0, 1.0 - dist / LAJE_SEARCH_RADIUS)

        # Geometry segments
        seg_a = []
        seg_b = []
        if viga.geometry_lines:
            for gl in viga.geometry_lines:
                if isinstance(gl, dict):
                    s = gl.get('start', gl.get('points', [(0, 0)])[0] if 'points' in gl else (0, 0))
                    if isinstance(s, (list, tuple)) and len(s) >= 2:
                        if s[1] >= viga.y:
                            seg_a.append(gl)
                        else:
                            seg_b.append(gl)

        return {
            'fields': fields,
            'links': links,
            'conf_map': conf_map,
            'geometry': viga.geometry_lines,
            'pos': viga.pos,
            'seg_a': seg_a,
            'seg_b': seg_b,
        }

    def interpretar_laje(self, laje: LajeDXF) -> Dict[str, Any]:
        """
        Interpreta uma laje: identifica vigas e pilares ao redor, contorno e area.

        Returns:
            Dict com:
              - links: {vigas_around, pilares_around}
              - contour: lista de pontos [x, y] ordenados por angulo
              - area: area estimada
              - conf: confianca geral
        """
        links: Dict[str, List[str]] = {
            'vigas_around': [],
            'pilares_around': [],
        }

        # Find neighboring vigas
        vigas_viz = self.g.vizinhos_viga(laje, LAJE_SEARCH_RADIUS, max_n=8)
        for v, d in vigas_viz:
            links['vigas_around'].append(v.name)

        # Find neighboring pilares
        pilares_viz = self.g.vizinhos_pilar(
            type('Obj', (), {'id': laje.id, 'x': laje.x, 'y': laje.y})(),
            LAJE_SEARCH_RADIUS,
            max_n=8,
        )
        for p, d in pilares_viz:
            links['pilares_around'].append(p.name)

        # Contour points sorted by angle from center
        contour: List[List[float]] = []
        if laje.contour_pts:
            center_x = sum(p[0] for p in laje.contour_pts) / len(laje.contour_pts)
            center_y = sum(p[1] for p in laje.contour_pts) / len(laje.contour_pts)
            sorted_pts = sorted(
                laje.contour_pts,
                key=lambda p: math.atan2(p[1] - center_y, p[0] - center_x)
            )
            contour = [[p[0], p[1]] for p in sorted_pts]

        # Estimate area from contour (Shoelace formula)
        area = 0.0
        if contour and len(contour) >= 3:
            n = len(contour)
            for i in range(n):
                j = (i + 1) % n
                area += contour[i][0] * contour[j][1]
                area -= contour[j][0] * contour[i][1]
            area = abs(area) / 2.0

        # Confidence based on data availability
        conf = 0.3
        if laje.h_val > 0:
            conf += 0.3
        if contour:
            conf += 0.2
        if links['vigas_around']:
            conf += 0.2

        return {
            'links': links,
            'contour': contour,
            'area': area,
            'conf': min(conf, 1.0),
        }


# ---------------------------------------------------------------------------
# 5. RelatorioValidacao
# ---------------------------------------------------------------------------

class RelatorioValidacao:
    """
    Valida interpretacoes e gera lista de problemas e insights.

    Verifica consistencia entre pilares, vigas e lajes:
    lados sem viga, vigas sem dimensao, lajes sem contorno, etc.
    """

    def __init__(
        self,
        grafo: GrafoEstrutural,
        interpretacoes: Dict[str, Dict],
    ) -> None:
        self.g = grafo
        self.interp = interpretacoes
        self.problemas: List[str] = []
        self.insights: List[str] = []

    def validar(self) -> None:
        """Executa todas as validacoes: pilares, vigas, lajes, consistencia."""
        self._validar_pilares()
        self._validar_vigas()
        self._validar_lajes()
        self._validar_consistencia()

        logger.info(
            f"Validacao: {len(self.problemas)} problemas, "
            f"{len(self.insights)} insights"
        )

    def _validar_pilares(self) -> None:
        """
        Para cada pilar, verifica lados sem viga e sem laje.

        Gera avisos:
          - "Pilar X: N lados sem viga (isolado?)"
          - "Pilar X: N lados SEM LAJE (borda?)"
        """
        for pid, pilar in self.g.pilares.items():
            interp = self.interp.get(pid, {})
            sides = interp.get('sides_data', {})

            lados_sem_viga = 0
            lados_sem_laje = 0

            for lado, data in sides.items():
                if not data.get('label'):
                    lados_sem_viga += 1
                if not data.get('_l1_n'):
                    lados_sem_laje += 1

            if lados_sem_viga >= 3:
                self.problemas.append(
                    f"Pilar {pilar.name}: {lados_sem_viga} lados sem viga (isolado?)"
                )
            elif lados_sem_viga >= 2:
                self.insights.append(
                    f"Pilar {pilar.name}: {lados_sem_viga} lados sem viga (canto?)"
                )

            if lados_sem_laje >= 3:
                self.problemas.append(
                    f"Pilar {pilar.name}: {lados_sem_laje} lados SEM LAJE (borda?)"
                )

    def _validar_vigas(self) -> None:
        """
        Para cada viga, verifica presenca de dimensao.

        BA* (balanco) sem dimensao e normal.
        Outras vigas sem dimensao geram aviso.
        """
        for vid, viga in self.g.vigas.items():
            interp = self.interp.get(vid, {})
            fields = interp.get('fields', {})
            dimensao = fields.get('dimensao', '')

            if not dimensao:
                if re.match(r'^(BA|VB)\d+', viga.name, re.IGNORECASE):
                    self.insights.append(
                        f"Balanco {viga.name}: sem dimensao "
                        f"(normal, definido em detalhamento)"
                    )
                else:
                    self.problemas.append(
                        f"Viga {viga.name}: sem dimensao, conferir"
                    )

    def _validar_lajes(self) -> None:
        """
        Para cada laje, verifica presenca de espessura e contorno.

        Gera avisos:
          - "Laje X: sem h= (espessura)"
          - "Laje X: sem contorno (normal em TQS)"
        """
        for lid, laje in self.g.lajes.items():
            if laje.h_val <= 0:
                self.problemas.append(
                    f"Laje {laje.name}: sem h= (espessura)"
                )

            if not laje.contour_pts:
                family = laje.family or 'TQS'
                if family == 'TQS':
                    self.insights.append(
                        f"Laje {laje.name}: sem contorno (normal em TQS)"
                    )
                else:
                    self.problemas.append(
                        f"Laje {laje.name}: sem contorno"
                    )

    def _validar_consistencia(self) -> None:
        """
        Verifica se apoios de vigas existem nos pilares conhecidos.

        Gera aviso: "Viga X: apoio 'Y' nao encontrado nos pilares"
        """
        pilar_names = {p.name.upper() for p in self.g.pilares.values()}

        for vid, viga in self.g.vigas.items():
            interp = self.interp.get(vid, {})
            links = interp.get('links', {})

            for key in ('apoio_ini', 'apoio_fim'):
                apoio = links.get(key, '')
                if apoio and apoio.upper() not in pilar_names:
                    self.problemas.append(
                        f"Viga {viga.name}: apoio '{apoio}' nao encontrado nos pilares"
                    )


# ---------------------------------------------------------------------------
# 6. GravadorDB
# ---------------------------------------------------------------------------

class GravadorDB:
    """
    Grava resultados do processamento no SQLite (project_data.vision).

    Tabelas utilizadas: projects, pillars, beams, slabs.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def gravar(
        self,
        obra: str,
        pavimento: str,
        grafo: GrafoEstrutural,
        interpretacoes: Dict[str, Dict],
        dxf_path: str,
    ) -> str:
        """
        Grava todos os dados de um pavimento no banco.

        Args:
            obra: Nome da obra.
            pavimento: Nome do pavimento.
            grafo: Grafo estrutural construido.
            interpretacoes: Dicionario com interpretacoes por entidade.
            dxf_path: Caminho do DXF processado.

        Returns:
            project_id criado ou encontrado.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            pid = self._find_or_create_project(conn, obra, pavimento, dxf_path)
            self._clear(conn, pid)

            # Gravar pilares (sorted by natural key)
            pilares_sorted = sorted(
                grafo.pilares.values(),
                key=lambda p: self._nat_key(p.name),
            )
            for idx, pilar in enumerate(pilares_sorted):
                interp = interpretacoes.get(pilar.id, {})
                self._gravar_pilar(conn, pid, pilar, interp, idx)

            # Gravar vigas
            vigas_sorted = sorted(
                grafo.vigas.values(),
                key=lambda v: self._nat_key(v.name),
            )
            for idx, viga in enumerate(vigas_sorted):
                interp = interpretacoes.get(viga.id, {})
                self._gravar_viga(conn, pid, viga, interp, idx)

            # Gravar lajes
            lajes_sorted = sorted(
                grafo.lajes.values(),
                key=lambda l: self._nat_key(l.name),
            )
            for idx, laje in enumerate(lajes_sorted):
                interp = interpretacoes.get(laje.id, {})
                self._gravar_laje(conn, pid, laje, interp, idx)

            conn.commit()
            logger.info(
                f"Gravado: {obra}/{pavimento} -> project_id={pid} "
                f"({len(pilares_sorted)}P {len(vigas_sorted)}V {len(lajes_sorted)}L)"
            )
            return pid

        except Exception as e:
            conn.rollback()
            logger.error(f"Erro ao gravar: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def _nat_key(text: str) -> List:
        """
        Chave natural para sorting alfanumerico.

        Exemplo: 'P12' -> ['P', 12], 'V1A' -> ['V', 1, 'A']
        """
        parts = re.split(r'(\d+)', text)
        return [int(p) if p.isdigit() else p for p in parts if p]

    def _find_or_create_project(
        self, conn: sqlite3.Connection, obra: str, pav: str, dxf_path: str
    ) -> str:
        """
        Busca projeto existente ou cria novo.

        SELECT id FROM projects WHERE work_name=? AND name=?
        Se encontrado e dxf_path vazio, atualiza.
        Se nao encontrado, INSERT.
        """
        cursor = conn.execute(
            "SELECT id FROM projects WHERE work_name=? AND name=?",
            (obra, pav),
        )
        row = cursor.fetchone()

        if row:
            pid = row[0]
            # Update dxf_path if missing
            conn.execute(
                "UPDATE projects SET dxf_path=? WHERE id=? "
                "AND (dxf_path IS NULL OR dxf_path='')",
                (dxf_path, pid),
            )
            return pid

        # Create new project
        pid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO projects "
            "(id, name, dxf_path, author_name, work_name, pavement_name) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, pav, dxf_path, 'AgenteEstrutural', obra, pav),
        )
        return pid

    def _clear(self, conn: sqlite3.Connection, pid: str) -> None:
        """Limpa dados anteriores do projeto antes de regravar."""
        conn.execute("DELETE FROM pillars WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM beams WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM slabs WHERE project_id=?", (pid,))

    def _gravar_pilar(
        self,
        conn: sqlite3.Connection,
        pid: str,
        pilar: PilarDXF,
        interp: Dict,
        idx: int,
    ) -> None:
        """Grava um pilar no banco."""
        pillar_id = str(uuid.uuid4())
        points_json = json.dumps(pilar.geometry) if pilar.geometry else '[]'
        sides_data_json = json.dumps(interp.get('sides_data', {}))
        links_json = json.dumps(interp.get('links', {}))
        conf_map_json = json.dumps(interp.get('conf_map', {}))

        # Calculate approximate area
        area = 0.0
        if pilar.dim_l > 0 and pilar.dim_a > 0:
            area = pilar.dim_l * pilar.dim_a

        conn.execute(
            "INSERT INTO pillars "
            "(id, project_id, name, type, area, points_json, "
            "sides_data_json, links_json, conf_map_json, is_validated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (
                pillar_id, pid, pilar.name, 'RETANGULAR',
                area, points_json, sides_data_json,
                links_json, conf_map_json,
            ),
        )

    def _gravar_viga(
        self,
        conn: sqlite3.Connection,
        pid: str,
        viga: VigaDXF,
        interp: Dict,
        idx: int,
    ) -> None:
        """Grava uma viga no banco."""
        beam_id = str(uuid.uuid4())
        data = {
            'name': viga.name,
            'pos': viga.pos,
            'dim_str': viga.dim_str,
            'dim_l': viga.dim_l,
            'dim_a': viga.dim_a,
            'fields': interp.get('fields', {}),
            'links': interp.get('links', {}),
            'conf_map': interp.get('conf_map', {}),
        }
        data_json = json.dumps(data)

        sides_data_json = json.dumps({
            'seg_a': interp.get('seg_a', []),
            'seg_b': interp.get('seg_b', []),
        }, default=str)
        links_json = json.dumps(interp.get('links', {}))

        conn.execute(
            "INSERT INTO beams "
            "(id, project_id, name, data_json, "
            "sides_data_json, links_json, is_validated) "
            "VALUES (?, ?, ?, ?, ?, ?, 0)",
            (beam_id, pid, viga.name, data_json, sides_data_json, links_json),
        )

    def _gravar_laje(
        self,
        conn: sqlite3.Connection,
        pid: str,
        laje: LajeDXF,
        interp: Dict,
        idx: int,
    ) -> None:
        """Grava uma laje no banco."""
        slab_id = str(uuid.uuid4())
        contour = interp.get('contour', [])
        points_json = json.dumps(contour)
        area = interp.get('area', 0.0)
        links_json = json.dumps(interp.get('links', {}))

        conn.execute(
            "INSERT INTO slabs "
            "(id, project_id, name, area, points_json, "
            "type, links_json, is_validated) "
            "VALUES (?, ?, ?, ?, ?, 'Laje', ?, 0)",
            (slab_id, pid, laje.name, area, points_json, links_json),
        )


# ---------------------------------------------------------------------------
# 7. ClaudeCheckpoint
# ---------------------------------------------------------------------------

class ClaudeCheckpoint:
    """
    Envia dados de interpretacao ao Claude CLI e recebe correcoes.

    Usa subprocess para chamar o Claude CLI em modo nao-interativo
    (--print) com um prompt compactado contendo os dados relevantes.
    """

    CLAUDE_CMD = 'claude'
    SYSTEM_PROMPT = (
        "Voce e um engenheiro estrutural revisando dados extraidos de DXFs. "
        "Recebera pilares, vigas e lajes com suas interpretacoes e problemas. "
        "Retorne APENAS um JSON com correcoes, no formato: "
        '{"correcoes_vigas": {"NOME_VIGA": {"campo": "valor"}}, '
        '"correcoes_pilares": {"NOME_PILAR": {"lado": {"campo": "valor"}}}}'
    )

    def consultar(
        self,
        obra: str,
        pavimento: str,
        grafo: GrafoEstrutural,
        interpretacoes: Dict[str, Dict],
        problemas: List[str],
        insights: List[str],
    ) -> Dict:
        """
        Executa consulta ao Claude CLI com dados do processamento.

        Args:
            obra: Nome da obra.
            pavimento: Nome do pavimento.
            grafo: Grafo estrutural.
            interpretacoes: Interpretacoes geradas.
            problemas: Lista de problemas detectados.
            insights: Lista de insights.

        Returns:
            Dict com correcoes sugeridas, ou dict vazio se falhar.
        """
        prompt = self._build_prompt(
            obra, pavimento, grafo, interpretacoes, problemas, insights
        )

        try:
            result = subprocess.run(
                [
                    self.CLAUDE_CMD, '--print',
                    '--max-turns', '1',
                    '--system-prompt', self.SYSTEM_PROMPT,
                    '--no-session-persistence',
                ],
                input=prompt,
                env={**os.environ},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                logger.warning(f"Claude CLI retornou code {result.returncode}")
                return {}

            return self._parse_response(result.stdout)

        except FileNotFoundError:
            logger.warning("Claude CLI nao encontrado no PATH")
            return {}
        except subprocess.TimeoutExpired:
            logger.warning("Claude CLI timeout (120s)")
            return {}
        except Exception as e:
            logger.error(f"Erro ao consultar Claude: {e}")
            return {}

    def _build_prompt(
        self,
        obra: str,
        pav: str,
        grafo: GrafoEstrutural,
        interpretacoes: Dict[str, Dict],
        problemas: List[str],
        insights: List[str],
    ) -> str:
        """Monta prompt compacto com dados relevantes para revisao."""
        lines = [
            f"OBRA: {obra} / PAV: {pav}",
            f"PILARES ({len(grafo.pilares)}):",
        ]

        for pid, pilar in list(grafo.pilares.items())[:20]:
            interp = interpretacoes.get(pid, {})
            sides = interp.get('sides_data', {})
            dim = pilar.dim_str or 'SEM_DIM'
            lines.append(f"  {pilar.name} ({dim}): {json.dumps(sides, ensure_ascii=False)}")

        lines.append(f"VIGAS ({len(grafo.vigas)}):")
        for vid, viga in list(grafo.vigas.items())[:30]:
            interp = interpretacoes.get(vid, {})
            fields = interp.get('fields', {})
            links = interp.get('links', {})
            dim = viga.dim_str or 'SEM_DIM'
            lines.append(
                f"  {viga.name} ({dim}): "
                f"apoios=[{links.get('apoio_ini', '?')}, {links.get('apoio_fim', '?')}] "
                f"lajes=[{links.get('laje_esq', '?')}, {links.get('laje_dir', '?')}]"
            )

        lines.append(f"LAJES ({len(grafo.lajes)}):")
        for lid, laje in list(grafo.lajes.items())[:15]:
            interp = interpretacoes.get(lid, {})
            h = laje.h_val
            n_vigas = len(interp.get('links', {}).get('vigas_around', []))
            lines.append(f"  {laje.name} (h={h}): {n_vigas} vigas ao redor")

        if problemas:
            lines.append(f"PROBLEMAS ({len(problemas)}):")
            for p in problemas[:15]:
                lines.append(f"  - {p}")

        return "\n".join(lines)

    def _parse_response(self, raw: str) -> Dict:
        """Extrai JSON da resposta do Claude."""
        # Try to find JSON block in response
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("Nao foi possivel extrair JSON da resposta Claude")
        return {}

    def aplicar_correcoes(
        self,
        interpretacoes: Dict[str, Dict],
        correcoes: Dict,
    ) -> int:
        """
        Aplica correcoes retornadas pelo Claude nas interpretacoes.

        Args:
            interpretacoes: Dict de interpretacoes por entity_id.
            correcoes: Dict com correcoes_vigas e correcoes_pilares.

        Returns:
            Numero de correcoes aplicadas.
        """
        count = 0

        # Apply viga corrections
        corr_vigas = correcoes.get('correcoes_vigas', {})
        for viga_name, campos in corr_vigas.items():
            # Find viga by name
            for vid, interp in interpretacoes.items():
                fields = interp.get('fields', {})
                if fields.get('numero') == viga_name:
                    for campo, valor in campos.items():
                        if campo in fields:
                            fields[campo] = valor
                            count += 1
                        elif campo in interp.get('links', {}):
                            interp['links'][campo] = valor
                            count += 1
                    break

        # Apply pilar corrections
        corr_pilares = correcoes.get('correcoes_pilares', {})
        for pilar_name, lados in corr_pilares.items():
            for pid, interp in interpretacoes.items():
                sides = interp.get('sides_data', {})
                # Match by checking if pilar name appears in the id
                if pilar_name in pid:
                    for lado, data in lados.items():
                        if lado in sides:
                            sides[lado].update(data)
                            count += 1
                    break

        logger.info(f"Claude: {count} correcoes aplicadas")
        return count


# ---------------------------------------------------------------------------
# 8. AgenteEstrutural
# ---------------------------------------------------------------------------

class AgenteEstrutural:
    """
    Agente principal que orquestra todo o pipeline de processamento DXF.

    Pipeline: ExtratorDXF -> GrafoEstrutural -> InterpretadorEstrutural
              -> RelatorioValidacao -> GravadorDB [-> ClaudeCheckpoint]
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        use_claude: bool = False,
    ) -> None:
        """
        Args:
            db_path: Caminho do SQLite. Default: ../../project_data.vision.
            use_claude: Se True, ativa checkpoint via Claude CLI.
        """
        self.db_path = db_path or os.path.join(
            BASE_DIR, '..', '..', 'project_data.vision'
        )
        self.use_claude = use_claude

    def processar(
        self,
        obra: str,
        pavimento: str,
        dxf_path: Optional[str] = None,
    ) -> ResultadoProcessamento:
        """
        Executa pipeline completo para um pavimento.

        Args:
            obra: Nome da obra.
            pavimento: Nome do pavimento.
            dxf_path: Caminho do DXF. Default: DADOS-OBRAS/{obra}/Fase-2_Triagem/
                      Estruturais_Pavimentos_Limpos/{pavimento}.dxf

        Returns:
            ResultadoProcessamento com todas as metricas.
        """
        # Resolve DXF path
        if dxf_path is None:
            dxf_path = os.path.join(
                BASE_DIR, '..', '..', 'DADOS-OBRAS', obra,
                'Fase-2_Triagem', 'Estruturais_Pavimentos_Limpos',
                f'{pavimento}.dxf',
            )

        dxf_path = os.path.abspath(dxf_path)

        if not os.path.exists(dxf_path):
            logger.error(f"DXF nao encontrado: {dxf_path}")
            res = ResultadoProcessamento(obra=obra, pavimento=pavimento)
            res.problemas.append(f"DXF nao encontrado: {dxf_path}")
            return res

        logger.info(f"Processando: {obra}/{pavimento} -> {dxf_path}")

        # --- Phase 1: Extraction ---
        extrator = ExtratorDXF(dxf_path)
        pilares_txt, vigas_txt, lajes_txt, dims, laje_dims, polylines, lines = (
            extrator.extrair()
        )

        # Generate synthetic slabs if no explicit laje texts found
        lajes_sinteticas = []
        if not lajes_txt and laje_dims:
            lajes_sinteticas = extrator._gerar_lajes_sinteticas(
                laje_dims, polylines, lines
            )

        # --- Phase 2: Graph Construction ---
        grafo = GrafoEstrutural()
        grafo.construir(
            pilares_txt, vigas_txt, lajes_txt,
            dims, laje_dims, polylines, lines,
            family=extrator.family,
        )

        # Add synthetic slabs to graph
        for sl in lajes_sinteticas:
            grafo.lajes[sl.id] = sl

        # --- Phase 3: Interpretation ---
        interpretador = InterpretadorEstrutural(grafo)
        interpretacoes: Dict[str, Dict] = {}

        for pid, pilar in grafo.pilares.items():
            interpretacoes[pid] = interpretador.interpretar_pilar(pilar)

        for vid, viga in grafo.vigas.items():
            interpretacoes[vid] = interpretador.interpretar_viga(viga)

        for lid, laje in grafo.lajes.items():
            interpretacoes[lid] = interpretador.interpretar_laje(laje)

        # --- Phase 3.5: RAG Validation ---
        if _RAG_OK:
            _rag_problemas = []
            for pid, pilar in grafo.pilares.items():
                dados_rag = {'b': pilar.dim_l, 'h': pilar.dim_a}
                val = _rag_validator.validate('pilar', pilar.name or pid, dados_rag, obra)
                if val.bloqueado:
                    msg = f"RAG-BLOCK pilar {pilar.name}: " + "; ".join(str(a) for a in val.alertas)
                    _rag_problemas.append(msg)
                    logger.warning(msg)
                plaus = _rag_plaus.check(pilar.name or pid, 'pilar', dados_rag, obra)
                if plaus.acao in ('REVISAR', 'REJEITAR') and not val.bloqueado:
                    interpretacoes[pid]['_rag_nota'] = plaus.nota_rag
                    interpretacoes[pid]['_rag_sim']  = plaus.similarity

            for vid, viga in grafo.vigas.items():
                dados_rag = {'b': viga.dim_l, 'h': viga.dim_a, 'comprimento': viga.dim_str}
                plaus = _rag_plaus.check(viga.name or vid, 'viga', dados_rag, obra)
                if plaus.acao in ('REVISAR', 'REJEITAR'):
                    interpretacoes[vid]['_rag_nota'] = plaus.nota_rag

            for lid, laje in grafo.lajes.items():
                dados_rag = {'h_val': laje.h_val}
                plaus = _rag_plaus.check(laje.name or lid, 'laje', dados_rag, obra)
                if plaus.acao in ('REVISAR', 'REJEITAR'):
                    interpretacoes[lid]['_rag_nota'] = plaus.nota_rag

            if _rag_problemas:
                interpretador.problemas.extend(_rag_problemas)
            logger.debug(f"RAG Phase 3.5 done: {len(grafo.pilares)} pilares, "
                         f"{len(grafo.vigas)} vigas, {len(grafo.lajes)} lajes checked")

        # --- Phase 3.6: Claude Checkpoint (optional) ---
        if self.use_claude:
            checkpoint = ClaudeCheckpoint()
            correcoes = checkpoint.consultar(
                obra, pavimento, grafo, interpretacoes,
                interpretador.problemas, interpretador.insights,
            )
            if correcoes:
                checkpoint.aplicar_correcoes(interpretacoes, correcoes)

        # --- Phase 4: Validation ---
        validacao = RelatorioValidacao(grafo, interpretacoes)
        validacao.validar()

        # --- Phase 5: Database Persistence ---
        try:
            gravador = GravadorDB(self.db_path)
            gravador.gravar(obra, pavimento, grafo, interpretacoes, dxf_path)
        except Exception as e:
            logger.error(f"Erro ao gravar no DB: {e}")
            validacao.problemas.append(f"Erro DB: {e}")

        # --- Build result ---
        resultado = ResultadoProcessamento(
            obra=obra,
            pavimento=pavimento,
            pilares=list(grafo.pilares.values()),
            vigas=list(grafo.vigas.values()),
            lajes=list(grafo.lajes.values()),
            problemas=validacao.problemas,
            insights=validacao.insights,
        )

        # Calculate side fill rate
        total_sides = len(grafo.pilares) * 4
        filled_sides = 0
        for pid, pilar in grafo.pilares.items():
            interp = interpretacoes.get(pid, {})
            sides = interp.get('sides_data', {})
            for lado, data in sides.items():
                if data.get('label') or data.get('_l1_n'):
                    filled_sides += 1

        resultado.sides_total = total_sides
        resultado.sides_preenchidos = filled_sides

        # Calculate viga field fill rate
        total_fields = len(grafo.vigas) * 3  # numero, dimensao, comprimento
        filled_fields = 0
        for vid, viga in grafo.vigas.items():
            interp = interpretacoes.get(vid, {})
            fields = interp.get('fields', {})
            if fields.get('numero'):
                filled_fields += 1
            if fields.get('dimensao'):
                filled_fields += 1
            if fields.get('comprimento_estimado', 0) > 0:
                filled_fields += 1

        resultado.fields_total = total_fields
        resultado.fields_preenchidos = filled_fields

        logger.info(resultado.relatorio())
        return resultado

    def processar_obra_completa(self, obra: str) -> List[ResultadoProcessamento]:
        """
        Processa todos os pavimentos de uma obra.

        Dir: DADOS-OBRAS/{obra}/Fase-2_Triagem/Estruturais_Pavimentos_Limpos/
        """
        dxf_dir = os.path.join(
            BASE_DIR, '..', '..', 'DADOS-OBRAS', obra,
            'Fase-2_Triagem', 'Estruturais_Pavimentos_Limpos',
        )
        dxf_dir = os.path.abspath(dxf_dir)

        if not os.path.isdir(dxf_dir):
            logger.error(f"Diretorio nao encontrado: {dxf_dir}")
            return []

        resultados: List[ResultadoProcessamento] = []

        dxf_files = sorted([
            f for f in os.listdir(dxf_dir)
            if f.lower().endswith('.dxf')
        ])

        logger.info(f"Obra {obra}: {len(dxf_files)} pavimentos encontrados")

        for dxf_file in dxf_files:
            pavimento = os.path.splitext(dxf_file)[0]
            dxf_path = os.path.join(dxf_dir, dxf_file)

            try:
                resultado = self.processar(obra, pavimento, dxf_path=dxf_path)
                resultados.append(resultado)
            except Exception as e:
                logger.error(f"Erro processando {pavimento}: {e}")
                res = ResultadoProcessamento(obra=obra, pavimento=pavimento)
                res.problemas.append(f"Erro fatal: {e}")
                resultados.append(res)

        # Print summary
        total_p = sum(len(r.pilares) for r in resultados)
        total_v = sum(len(r.vigas) for r in resultados)
        total_l = sum(len(r.lajes) for r in resultados)
        total_prob = sum(len(r.problemas) for r in resultados)

        logger.info(
            f"\n{'=' * 60}\n"
            f"RESUMO OBRA: {obra}\n"
            f"Pavimentos: {len(resultados)}\n"
            f"Pilares: {total_p} | Vigas: {total_v} | Lajes: {total_l}\n"
            f"Problemas: {total_prob}\n"
            f"{'=' * 60}"
        )

        return resultados


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main() -> None:
    """
    CLI entry point.

    Uso:
      python agente_estrutural.py {obra} {pavimento}   # Processa um pavimento
      python agente_estrutural.py {obra}                # Processa obra completa

    Opcoes:
      --claude    Ativa checkpoint via Claude CLI
      --db PATH   Caminho do SQLite (default: ../../project_data.vision)
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    # Parse arguments
    args = sys.argv[1:]
    use_claude = '--claude' in args
    args = [a for a in args if not a.startswith('--')]

    db_path = None
    for i, a in enumerate(sys.argv):
        if a == '--db' and i + 1 < len(sys.argv):
            db_path = sys.argv[i + 1]

    if len(args) < 1:
        print("Uso: python agente_estrutural.py {obra} [pavimento]")
        print("     python agente_estrutural.py {obra}  # processa todos")
        print("Opcoes: --claude  --db PATH")
        sys.exit(1)

    obra = args[0]
    agente = AgenteEstrutural(db_path=db_path, use_claude=use_claude)

    if len(args) >= 2:
        pavimento = args[1]
        resultado = agente.processar(obra, pavimento)
        print(resultado.relatorio())
    else:
        resultados = agente.processar_obra_completa(obra)
        for r in resultados:
            print(r.relatorio())
            print()


if __name__ == '__main__':
    main()
