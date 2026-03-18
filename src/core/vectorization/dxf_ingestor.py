"""
DXF Ingestor - Modulo 1 do Pipeline de Vetorizacao
====================================================
Responsavel por ingerir conteudo bruto de uma obra:
  - DXF estruturais (ezdxf) com deteccao automatica de familia TQS vs BIM
  - PDFs (documentos, atas, detalhes)
  - Imagens JPG/JPEG (detalhes estruturais, fotos de pavimentos)

Saida: Lista de RawEntity normalizadas prontas para vetorizacao.

Familias DXF detectadas:
  - FAMILY_TQS: layers numericos (0,1,2...), SOLID ao inves de HATCH, sem DIMENSION
  - FAMILY_BIM: layers descritivos (F-VIGAS-NOME, S-COLS...), DIMENSION, HATCH, blocks

Padroes universais encontrados nos estruturais:
  - V{N} ou V{N}({L}x{A}) para vigas
  - P{N} para pilares
  - h={valor} para alturas de laje
  - 19cm largura padrao de viga
  - {largura}/{altura} ou {largura}x{altura} para dimensoes de secao
"""

import os
import re
import json
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum

try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False

logger = logging.getLogger(__name__)


class DXFFamily(str, Enum):
    """Familia do arquivo DXF detectada automaticamente."""
    TQS = "FAMILY_TQS"      # Layers numericos, SOLID, sem DIMENSION
    BIM = "FAMILY_BIM"      # Layers descritivos, HATCH, DIMENSION, blocks
    UNKNOWN = "UNKNOWN"


class FileType(str, Enum):
    DXF = "dxf"
    PDF = "pdf"
    IMAGE = "image"
    UNKNOWN = "unknown"


class SourceClass(str, Enum):
    """Classificacao da fonte de origem da entidade."""
    STRUCTURAL_DXF = "structural_dxf"
    DETAIL_IMAGE = "detail_image"
    DOCUMENT_PDF = "document_pdf"
    UNKNOWN = "unknown"


@dataclass
class RawEntity:
    """Entidade estrutural bruta extraida do DXF, antes de vetorizacao."""
    entity_id: str                      # Hash unico da entidade
    source_file: str                    # Path do arquivo de origem
    source_class: str = SourceClass.STRUCTURAL_DXF
    family: str = DXFFamily.UNKNOWN

    # Tipo inferido (pilar/viga/laje/texto/desconhecido)
    entity_type_hint: str = "unknown"

    # Geometria bruta
    layer: str = ""
    dxf_type: str = ""                  # LINE, LWPOLYLINE, TEXT, MTEXT, HATCH, SOLID, etc.
    vertices: List[List[float]] = field(default_factory=list)   # [[x,y], ...]
    text_content: str = ""
    color: int = 0
    linetype: str = ""

    # Bounding box
    bbox_xmin: float = 0.0
    bbox_xmax: float = 0.0
    bbox_ymin: float = 0.0
    bbox_ymax: float = 0.0

    # Metadados de contexto
    pavimento: str = ""
    obra_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def bbox_width(self) -> float:
        return abs(self.bbox_xmax - self.bbox_xmin)

    @property
    def bbox_height(self) -> float:
        return abs(self.bbox_ymax - self.bbox_ymin)

    @property
    def bbox_area(self) -> float:
        return self.bbox_width * self.bbox_height


@dataclass
class IngestedFile:
    """Resultado da ingestao de um arquivo completo."""
    path: str
    file_type: str
    family: str = DXFFamily.UNKNOWN
    entities: List[RawEntity] = field(default_factory=list)
    error: Optional[str] = None
    entity_count: int = 0
    text_count: int = 0
    polyline_count: int = 0

    def is_ok(self) -> bool:
        return self.error is None


@dataclass
class IngestorConfig:
    """Configuracao do DXFIngestor."""
    skip_layers: List[str] = field(default_factory=lambda: [
        "CELL_BORDER", "LABEL_ID", "CARIMBO", "FOLHA MB",
        "Folhas", "Romaneio", "fundo"
    ])
    max_text_length: int = 500
    include_hatches: bool = False
    include_dimensions: bool = False
    min_entity_size: float = 1.0        # ignorar entidades menores que 1 unidade


class TextPatterns:
    """Padroes regex para classificacao de texto estrutural."""

    # Vigas: V32b, V1A, V-2, V32(19/53), V1(19x53)
    VIGA = re.compile(r'^V\d+[a-zA-Z]?\b', re.IGNORECASE)
    VIGA_DIM = re.compile(r'(\d+)[/x](\d+)', re.IGNORECASE)  # 19/53 ou 19x53

    # Pilares: P1, P32A, P-1
    PILAR = re.compile(r'^P\d+[a-zA-Z]?\b', re.IGNORECASE)
    PILAR_DIM = re.compile(r'\((\d+)[xX](\d+)\)', re.IGNORECASE)  # (19x229)

    # Lajes: L1, L2A, LAJ-1
    LAJE = re.compile(r'^L[Aa]?[Jj]?[E-]?\d+[a-zA-Z]?\b', re.IGNORECASE)
    LAJE_NIVEL = re.compile(r'h\s*=\s*([\d,\.]+)', re.IGNORECASE)  # h=15, h=12
    LAJE_DIM = re.compile(r'd\s*=\s*(\d+)', re.IGNORECASE)         # d=12, d=15

    # Dimensoes genericas
    DIMENSION = re.compile(r'(\d+(?:[,\.]\d+)?)\s*[xX/]\s*(\d+(?:[,\.]\d+)?)')


class FamilyDetector:
    """Detecta a familia do DXF (TQS vs BIM) com base nas caracteristicas do arquivo."""

    TQS_LAYER_PATTERN = re.compile(r'^\d+$')            # layers puramente numericos
    BIM_LAYER_PATTERNS = [
        re.compile(r'^[A-Z]-', re.IGNORECASE),           # F-VIGAS, S-COLS
        re.compile(r'^(VIGA|PILAR|LAJE|BEAM|COLUMN|SLAB)', re.IGNORECASE),
    ]

    @classmethod
    def detect(cls, doc) -> DXFFamily:
        """Detecta familia a partir de um documento ezdxf carregado."""
        if not HAS_EZDXF or doc is None:
            return DXFFamily.UNKNOWN

        layers = [layer.dxf.name for layer in doc.layers]
        numeric_layers = sum(1 for l in layers if cls.TQS_LAYER_PATTERN.match(l))
        bim_layers = sum(1 for l in layers
                         for pat in cls.BIM_LAYER_PATTERNS if pat.match(l))

        msp = doc.modelspace()
        has_hatch = any(e.dxftype() == 'HATCH' for e in msp if True)
        has_dimension = any(e.dxftype() == 'DIMENSION' for e in msp if True)

        # Heuristica TQS: mais layers numericos, SOLID, sem HATCH/DIMENSION
        if numeric_layers > len(layers) * 0.3 and not has_hatch:
            return DXFFamily.TQS
        # Heuristica BIM: layers descritivos, HATCH, DIMENSION
        if bim_layers > 0 or (has_hatch and has_dimension):
            return DXFFamily.BIM

        return DXFFamily.UNKNOWN


class DXFIngestor:
    """
    Ingesta arquivos DXF estruturais em RawEntity normalizadas.

    Uso:
        config = IngestorConfig()
        ingestor = DXFIngestor(config)
        result = ingestor.ingerir(Path('pavimento.dxf'), obra_id='obra123', pavimento='P-1')
        for entity in result.entities:
            print(entity.entity_type_hint, entity.text_content)
    """

    def __init__(self, config: Optional[IngestorConfig] = None):
        self.config = config or IngestorConfig()

    def ingerir(
        self,
        dxf_path: Path,
        obra_id: str = "",
        pavimento: str = "",
    ) -> IngestedFile:
        """Ingesta um arquivo DXF e retorna IngestedFile com lista de RawEntity."""
        result = IngestedFile(path=str(dxf_path), file_type=FileType.DXF)

        if not HAS_EZDXF:
            result.error = "ezdxf not installed"
            return result

        if not dxf_path.exists():
            result.error = f"File not found: {dxf_path}"
            return result

        try:
            doc = ezdxf.readfile(str(dxf_path))
            msp = doc.modelspace()
            family = FamilyDetector.detect(doc)
            result.family = family
        except Exception as e:
            result.error = str(e)
            logger.error(f"Error reading {dxf_path}: {e}")
            return result

        entities = []
        for ent in msp:
            try:
                raw = self._process_entity(ent, dxf_path, family, obra_id, pavimento)
                if raw is not None:
                    entities.append(raw)
            except Exception as e:
                logger.debug(f"Skip entity {ent.dxftype()}: {e}")

        result.entities = entities
        result.entity_count = len(entities)
        result.text_count = sum(1 for e in entities if e.dxf_type in ('TEXT', 'MTEXT'))
        result.polyline_count = sum(1 for e in entities if e.dxf_type in ('LWPOLYLINE', 'POLYLINE'))

        logger.info(f"Ingested {dxf_path.name}: {result.entity_count} entities "
                    f"({result.text_count} texts, {result.polyline_count} polys) family={family.value}")
        return result

    def _process_entity(
        self, ent, dxf_path: Path, family: DXFFamily,
        obra_id: str, pavimento: str
    ) -> Optional[RawEntity]:
        """Processa uma entidade DXF individual."""
        layer = getattr(ent.dxf, 'layer', '0')
        dxf_type = ent.dxftype()

        # Skip blacklisted layers
        if layer in self.config.skip_layers:
            return None

        # Generate stable entity ID
        raw_id = f"{dxf_path.stem}:{layer}:{dxf_type}:{ent.dxf.handle}"
        entity_id = hashlib.md5(raw_id.encode()).hexdigest()[:16]

        raw = RawEntity(
            entity_id=entity_id,
            source_file=str(dxf_path),
            family=family.value,
            layer=layer,
            dxf_type=dxf_type,
            color=getattr(ent.dxf, 'color', 0),
            obra_id=obra_id,
            pavimento=pavimento,
        )

        if dxf_type in ('TEXT', 'MTEXT'):
            text = (getattr(ent.dxf, 'text', '') or
                    getattr(ent, 'plain_mtext', lambda: '')() or '')
            text = text.strip()[:self.config.max_text_length]
            if not text:
                return None
            raw.text_content = text
            raw.entity_type_hint = self._classify_text(text)
            # BBox from insert point
            ip = getattr(ent.dxf, 'insert', None)
            if ip:
                raw.bbox_xmin = raw.bbox_xmax = float(ip.x)
                raw.bbox_ymin = raw.bbox_ymax = float(ip.y)

        elif dxf_type in ('LWPOLYLINE', 'POLYLINE'):
            try:
                pts = [(p[0], p[1]) for p in ent.get_points('xy')]
            except Exception:
                pts = []
            if not pts:
                return None
            raw.vertices = [[float(x), float(y)] for x, y in pts]
            raw.bbox_xmin = min(p[0] for p in pts)
            raw.bbox_xmax = max(p[0] for p in pts)
            raw.bbox_ymin = min(p[1] for p in pts)
            raw.bbox_ymax = max(p[1] for p in pts)
            if raw.bbox_area < self.config.min_entity_size:
                return None
            raw.entity_type_hint = self._classify_poly_by_layer(layer)

        elif dxf_type == 'LINE':
            try:
                s, e2 = ent.dxf.start, ent.dxf.end
                raw.vertices = [[float(s.x), float(s.y)], [float(e2.x), float(e2.y)]]
                raw.bbox_xmin = min(s.x, e2.x)
                raw.bbox_xmax = max(s.x, e2.x)
                raw.bbox_ymin = min(s.y, e2.y)
                raw.bbox_ymax = max(s.y, e2.y)
            except Exception:
                return None
            raw.entity_type_hint = self._classify_poly_by_layer(layer)

        elif dxf_type == 'HATCH' and self.config.include_hatches:
            raw.entity_type_hint = "hachura"
        else:
            return None

        return raw

    def _classify_text(self, text: str) -> str:
        """Classifica texto como pilar/viga/laje/dimensao/outro."""
        t = text.strip()
        if TextPatterns.VIGA.match(t):
            return "viga"
        if TextPatterns.PILAR.match(t):
            return "pilar"
        if TextPatterns.LAJE.match(t) or TextPatterns.LAJE_NIVEL.search(t):
            return "laje"
        if TextPatterns.DIMENSION.search(t):
            return "dimensao"
        return "texto"

    def _classify_poly_by_layer(self, layer: str) -> str:
        """Inferencia de tipo pela layer."""
        l = layer.lower()
        if any(k in l for k in ('viga', 'beam', 'vg')):
            return "viga"
        if any(k in l for k in ('pilar', 'col', 'pl')):
            return "pilar"
        if any(k in l for k in ('laje', 'slab', 'lj', 'sco')):
            return "laje"
        if any(k in l for k in ('painel', 'madeira', 'sarr')):
            return "forma"
        return "elemento"


def ingerir_obra(
    obra_path: Path,
    obra_id: str = "",
    config: Optional[IngestorConfig] = None,
) -> List[IngestedFile]:
    """
    Ingesta todos os DXFs de uma obra (recursivo).

    Args:
        obra_path: Diretorio da obra
        obra_id: ID da obra para rastreabilidade
        config: Configuracao opcional

    Returns:
        Lista de IngestedFile, um por arquivo DXF encontrado
    """
    ingestor = DXFIngestor(config)
    results = []

    dxf_files = sorted(obra_path.rglob("*.dxf"))
    logger.info(f"Found {len(dxf_files)} DXF files in {obra_path}")

    for dxf_file in dxf_files:
        # Inferir pavimento do nome do arquivo/diretorio
        pavimento = dxf_file.stem
        result = ingestor.ingerir(dxf_file, obra_id=obra_id, pavimento=pavimento)
        results.append(result)

    return results


def ingerir_dxf_unico(
    dxf_path: Path,
    obra_id: str = "",
    pavimento: str = "",
    config: Optional[IngestorConfig] = None,
) -> IngestedFile:
    """Ingesta um unico arquivo DXF."""
    ingestor = DXFIngestor(config)
    return ingestor.ingerir(dxf_path, obra_id=obra_id, pavimento=pavimento)
