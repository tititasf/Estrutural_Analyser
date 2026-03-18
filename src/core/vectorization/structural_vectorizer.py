"""
Structural Vectorizer - Modulo 2 do Pipeline de Vetorizacao
============================================================
Transforma RawEntity em FeatureVector numericos normalizados,
prontos para classificacao, indexacao e busca semantica.

EntityTypes detectados:
  PILAR  — elemento vertical de suporte
  VIGA   — elemento horizontal de travamento
  LAJE   — elemento de cobertura/piso
  FORMA  — forma/cimbramento (paineis, sarrafos)
  TEXTO  — anotacao ou dimensao de texto
  OUTRO  — elemento nao classificado

FeatureVector (8 dimensoes):
  [0] aspect_ratio     — width/height da bbox (0=vertical, 1=quadrado, >1=horizontal)
  [1] area_normalized  — area normalizada (0-1) em relacao ao maior elemento
  [2] vertex_count     — numero de vertices
  [3] is_closed        — 1 se polilinha fechada
  [4] layer_hash_norm  — hash normalizado da layer (0-1)
  [5] color_norm       — cor normalizada (0-1)
  [6] text_is_viga     — 1 se texto e nome de viga
  [7] text_is_pilar    — 1 se texto e nome de pilar
"""

import math
import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum

try:
    from rtree import index as rtree_index
    HAS_RTREE = True
except ImportError:
    HAS_RTREE = False

from .dxf_ingestor import RawEntity, TextPatterns

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    PILAR = "Pilar"
    VIGA = "Viga"
    LAJE = "Laje"
    FORMA = "Forma"
    TEXTO = "Texto"
    OUTRO = "Outro"


@dataclass
class FeatureVector:
    """
    Vetor de features numericas normalizadas de uma entidade estrutural.

    As 8 dimensoes permitem classificacao e busca semantica eficiente.
    """
    aspect_ratio: float = 0.0       # width / height (BBox)
    area_normalized: float = 0.0    # area relativa ao maior elemento da obra
    vertex_count: float = 0.0       # num vertices (normalizado por 10)
    is_closed: float = 0.0          # 0 ou 1
    layer_hash_norm: float = 0.0    # hash(layer) / 1000 (0-1)
    color_norm: float = 0.0         # color / 256 (0-1)
    text_is_viga: float = 0.0       # 0 ou 1
    text_is_pilar: float = 0.0      # 0 ou 1

    def to_list(self) -> List[float]:
        return [
            self.aspect_ratio, self.area_normalized, self.vertex_count,
            self.is_closed, self.layer_hash_norm, self.color_norm,
            self.text_is_viga, self.text_is_pilar
        ]

    def to_dna_key(self, precision: int = 4) -> str:
        """Gera chave DNA para lookup em transformation_rules."""
        return ",".join(f"{v:.{precision}f}" for v in self.to_list())


@dataclass
class StructuralEntity:
    """Entidade estrutural vetorizada com tipo classificado."""
    raw: RawEntity
    entity_type: EntityType = EntityType.OUTRO
    confidence: float = 0.0
    features: FeatureVector = field(default_factory=FeatureVector)

    # Campos extraidos do texto (se aplicavel)
    name: str = ""              # ex: "V32b", "P1", "L2A"
    dim_str: str = ""           # ex: "19/53", "(19x229)", "d=12"
    dim_width: Optional[float] = None
    dim_height: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['entity_type'] = self.entity_type.value
        d['features_list'] = self.features.to_list()
        d['dna_key'] = self.features.to_dna_key()
        return d


@dataclass
class VectorConfig:
    """Configuracao do StructuralVectorizer."""
    max_area_reference: float = 100000.0    # area de referencia para normalizacao
    layer_hash_modulus: int = 1000
    confidence_threshold: float = 0.5


class StructuralVectorizer:
    """
    Vetoriza RawEntity em StructuralEntity com FeatureVector normalizados.

    Uso:
        vectorizer = StructuralVectorizer()
        entities = vectorizer.vetorizar(raw_entities)
        for e in entities:
            print(e.entity_type, e.features.to_dna_key())
    """

    def __init__(self, config: Optional[VectorConfig] = None):
        self.config = config or VectorConfig()

    def vetorizar(self, raw_entities: List[RawEntity]) -> List[StructuralEntity]:
        """
        Vetoriza uma lista de RawEntity.

        Primeiro calcula o max_area para normalizacao global,
        depois processa cada entidade.
        """
        # Calcular area maxima para normalizacao
        areas = [r.bbox_area for r in raw_entities if r.bbox_area > 0]
        max_area = max(areas) if areas else self.config.max_area_reference

        result = []
        for raw in raw_entities:
            entity = self._vectorize_one(raw, max_area)
            result.append(entity)

        logger.info(f"Vectorized {len(result)} entities")
        return result

    def _vectorize_one(self, raw: RawEntity, max_area: float) -> StructuralEntity:
        """Vetoriza uma unica RawEntity."""
        features = self._compute_features(raw, max_area)
        entity_type, confidence = self._classify(raw, features)

        entity = StructuralEntity(
            raw=raw,
            entity_type=entity_type,
            confidence=confidence,
            features=features,
        )

        # Extrair name/dim do texto
        if raw.text_content:
            entity.name, entity.dim_str, entity.dim_width, entity.dim_height = (
                self._extract_text_fields(raw.text_content)
            )

        return entity

    def _compute_features(self, raw: RawEntity, max_area: float) -> FeatureVector:
        """Computa o FeatureVector de 8 dimensoes."""
        w = raw.bbox_width
        h = raw.bbox_height

        # Aspect ratio: w/h, com protecao contra divisao por zero
        if h > 0:
            aspect = min(w / h, 10.0)   # cap em 10 para evitar outliers
        elif w > 0:
            aspect = 10.0
        else:
            aspect = 1.0

        # Area normalizada
        area_norm = min(raw.bbox_area / max(max_area, 1.0), 1.0)

        # Vertices
        n_verts = min(len(raw.vertices) / 10.0, 1.0)  # normalizado por 10

        # Is closed (polyline fechada = primeiro == ultimo ponto)
        is_closed = 0.0
        if len(raw.vertices) >= 3:
            if (abs(raw.vertices[0][0] - raw.vertices[-1][0]) < 1e-3 and
                    abs(raw.vertices[0][1] - raw.vertices[-1][1]) < 1e-3):
                is_closed = 1.0

        # Layer hash
        layer_hash = abs(hash(raw.layer)) % self.config.layer_hash_modulus
        layer_hash_norm = layer_hash / self.config.layer_hash_modulus

        # Color
        color_norm = min(raw.color / 256.0, 1.0)

        # Text flags
        text = raw.text_content
        text_is_viga = 1.0 if (text and TextPatterns.VIGA.match(text.strip())) else 0.0
        text_is_pilar = 1.0 if (text and TextPatterns.PILAR.match(text.strip())) else 0.0

        return FeatureVector(
            aspect_ratio=round(aspect, 4),
            area_normalized=round(area_norm, 4),
            vertex_count=round(n_verts, 4),
            is_closed=is_closed,
            layer_hash_norm=round(layer_hash_norm, 4),
            color_norm=round(color_norm, 4),
            text_is_viga=text_is_viga,
            text_is_pilar=text_is_pilar,
        )

    def _classify(self, raw: RawEntity, features: FeatureVector):
        """Classifica a entidade usando hint do ingestor + features."""
        hint = raw.entity_type_hint

        # Usar hint do ingestor como ponto de partida
        type_map = {
            "pilar": (EntityType.PILAR, 0.7),
            "viga": (EntityType.VIGA, 0.7),
            "laje": (EntityType.LAJE, 0.7),
            "forma": (EntityType.FORMA, 0.6),
            "texto": (EntityType.TEXTO, 0.5),
            "dimensao": (EntityType.TEXTO, 0.5),
            "elemento": (EntityType.OUTRO, 0.3),
        }

        entity_type, confidence = type_map.get(hint, (EntityType.OUTRO, 0.2))

        # Refinar com features
        if features.text_is_viga == 1.0:
            entity_type, confidence = EntityType.VIGA, 0.9
        elif features.text_is_pilar == 1.0:
            entity_type, confidence = EntityType.PILAR, 0.9

        return entity_type, confidence

    def _extract_text_fields(self, text: str):
        """Extrai name, dim_str, dim_width, dim_height de um texto."""
        text = text.strip()
        name = ""
        dim_str = ""
        dim_w = None
        dim_h = None

        # Nome (primeira palavra tipo V32b, P1, L2)
        tokens = text.split()
        if tokens:
            name = tokens[0]

        # Dimensao no formato 19/53 ou 19x53
        m = TextPatterns.VIGA_DIM.search(text)
        if m:
            dim_str = m.group(0)
            try:
                dim_w = float(m.group(1))
                dim_h = float(m.group(2))
            except ValueError:
                pass

        # Dimensao tipo d=12
        m2 = TextPatterns.LAJE_DIM.search(text)
        if m2 and not dim_str:
            dim_str = m2.group(0)
            try:
                dim_h = float(m2.group(1))
            except ValueError:
                pass

        return name, dim_str, dim_w, dim_h


def vetorizar_entidades(
    raw_entities: List[RawEntity],
    config: Optional[VectorConfig] = None,
) -> List[StructuralEntity]:
    """
    Funcao de conveniencia para vetorizacao direta.

    Args:
        raw_entities: Lista de RawEntity do DXFIngestor
        config: Configuracao opcional

    Returns:
        Lista de StructuralEntity vetorizadas e classificadas
    """
    vectorizer = StructuralVectorizer(config)
    return vectorizer.vetorizar(raw_entities)
