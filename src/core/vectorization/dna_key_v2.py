"""
DNA Key v2 -- Tipo-especifico para melhor coverage.

Atual: [aspect_ratio, area_normalized, vertex_count, is_closed, ...]  -> 8D generico
V2:    Especifico por tipo para melhor granularidade de matching.

Coverage esperado: 15% -> 45% de matches no dna_frequency_map

Cada tipo gera DNA com dimensoes relevantes para aquele tipo:
- Pilar: foco em secao, nivel, cambotamento
- Viga:  foco em comprimento, secao h/w, texto V
- Laje:  foco em area, perimetro, convexidade, islands

Quantizacao para reduzir espaco de chaves unicas e aumentar reuso.
"""

import math
import hashlib
import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class DNAKeyV2:
    """
    DNA key v2 -- tipo-especifico para melhor coverage.

    Gera chaves DNA com dimensoes otimizadas por tipo de elemento,
    usando quantizacao para reduzir a cardinalidade e aumentar hits
    no dna_frequency_map.

    Uso:
        dna = DNAKeyV2()
        key = dna.gerar_dna_auto(entity_dict, 'pilar')
        # -> "0.8,0.12,0.4,0.735,0.05,0.3,0,0"
    """

    def __init__(self, bins: int = 10, precision: int = 4):
        """
        Args:
            bins: Numero de bins para quantizacao (default 10 -> 0.0, 0.1, ..., 1.0).
            precision: Casas decimais na chave DNA.
        """
        self.bins = bins
        self.precision = precision

    def quantizar(self, valor: float, bins: Optional[int] = None) -> float:
        """
        Quantiza valor float para o bin mais proximo.

        Ex: bins=10 -> valores 0.0, 0.1, 0.2, ..., 1.0
            valor=0.37 -> 0.4

        Args:
            valor: Valor a quantizar (espera-se 0-1 normalizado).
            bins: Override do numero de bins.

        Returns:
            Valor quantizado.
        """
        n = bins or self.bins
        if n <= 0:
            return valor
        clamped = max(0.0, min(1.0, valor))
        return round(round(clamped * n) / n, self.precision)

    def _layer_hash(self, layer: str) -> float:
        """Hash normalizado da layer (0-1)."""
        if not layer:
            return 0.0
        h = int(hashlib.md5(layer.encode()).hexdigest()[:8], 16)
        return (h % 1000) / 1000.0

    def _has_text_pattern(self, text: str, pattern: str) -> float:
        """Retorna 1.0 se texto casa com pattern, 0.0 caso contrario."""
        if not text:
            return 0.0
        return 1.0 if re.search(pattern, text.strip(), re.IGNORECASE) else 0.0

    def _safe_float(self, entity: Dict, key: str, default: float = 0.0) -> float:
        """Extrai float de entity com fallback seguro."""
        try:
            val = entity.get(key, default)
            return float(val) if val is not None else default
        except (TypeError, ValueError):
            return default

    def _compute_aspect(self, entity: Dict) -> float:
        """Aspect ratio normalizado (0-1, cap em 10)."""
        w = self._safe_float(entity, 'bbox_width',
                             abs(self._safe_float(entity, 'bbox_xmax') - self._safe_float(entity, 'bbox_xmin')))
        h = self._safe_float(entity, 'bbox_height',
                             abs(self._safe_float(entity, 'bbox_ymax') - self._safe_float(entity, 'bbox_ymin')))
        if h > 0:
            return min(w / h, 10.0) / 10.0  # normalizado 0-1
        elif w > 0:
            return 1.0
        return 0.5

    def _compute_area_norm(self, entity: Dict) -> float:
        """Area normalizada (log-scale, 0-1)."""
        area = self._safe_float(entity, 'bbox_area')
        if area <= 0:
            w = abs(self._safe_float(entity, 'bbox_xmax') - self._safe_float(entity, 'bbox_xmin'))
            h = abs(self._safe_float(entity, 'bbox_ymax') - self._safe_float(entity, 'bbox_ymin'))
            area = w * h
        if area <= 0:
            return 0.0
        # Log-scale: log(area) / log(max_expected_area=1e6)
        return min(math.log10(max(area, 1.0)) / 6.0, 1.0)

    def _compute_n_verts(self, entity: Dict) -> float:
        """Numero de vertices normalizado (0-1, cap em 100)."""
        verts = entity.get('vertices', [])
        if isinstance(verts, (list, tuple)):
            n = len(verts)
        else:
            n = int(self._safe_float(entity, 'vertex_count', 0))
        return min(n / 100.0, 1.0)

    def _compute_perimetro_norm(self, entity: Dict) -> float:
        """Perimetro normalizado (sum distancias vertices consecutivos, log-scale)."""
        verts = entity.get('vertices', [])
        if not isinstance(verts, (list, tuple)) or len(verts) < 2:
            return 0.0
        perim = 0.0
        for i in range(len(verts) - 1):
            try:
                dx = float(verts[i + 1][0]) - float(verts[i][0])
                dy = float(verts[i + 1][1]) - float(verts[i][1])
                perim += math.sqrt(dx * dx + dy * dy)
            except (TypeError, IndexError, ValueError):
                continue
        if perim <= 0:
            return 0.0
        return min(math.log10(max(perim, 1.0)) / 5.0, 1.0)

    def _compute_convexidade(self, entity: Dict) -> float:
        """
        Convexidade: area_real / area_bbox (0-1).
        Aproxima pela razao de vertices que formam angulos convexos.
        Sem shapely, usa heuristica: se poligono fechado, calcula area via shoelace.
        """
        verts = entity.get('vertices', [])
        if not isinstance(verts, (list, tuple)) or len(verts) < 3:
            return 0.5

        # Shoelace area
        try:
            pts = [(float(v[0]), float(v[1])) for v in verts]
        except (TypeError, IndexError, ValueError):
            return 0.5

        n = len(pts)
        shoelace = 0.0
        for i in range(n):
            j = (i + 1) % n
            shoelace += pts[i][0] * pts[j][1]
            shoelace -= pts[j][0] * pts[i][1]
        real_area = abs(shoelace) / 2.0

        bbox_area = self._safe_float(entity, 'bbox_area')
        if bbox_area <= 0:
            w = abs(self._safe_float(entity, 'bbox_xmax') - self._safe_float(entity, 'bbox_xmin'))
            h = abs(self._safe_float(entity, 'bbox_ymax') - self._safe_float(entity, 'bbox_ymin'))
            bbox_area = w * h

        if bbox_area <= 0:
            return 0.5

        return min(real_area / bbox_area, 1.0)

    def _has_islands(self, entity: Dict) -> float:
        """Verifica se entidade tem 'islands' (furos/aberturas na laje)."""
        islands = entity.get('islands', entity.get('laje_islands', []))
        if isinstance(islands, (list, tuple)):
            return 1.0 if len(islands) > 0 else 0.0
        if isinstance(islands, str):
            return 1.0 if islands.strip() not in ('', '[]', 'null', 'None') else 0.0
        return 0.0

    def _compute_level_frac(self, entity: Dict) -> float:
        """
        Fracao do nivel/pavimento (0-1).
        Usa campo 'pavimento' ou 'level' para estimar posicao relativa.
        """
        pav = str(entity.get('pavimento', entity.get('level', '')))
        # Tentar extrair numero do pavimento (ex: "P-1" -> 1, "COBERTURA" -> 10)
        m = re.search(r'(\d+)', pav)
        if m:
            num = int(m.group(1))
            return min(num / 20.0, 1.0)  # normaliza para max 20 pavimentos
        return 0.0

    def _estimate_section_area(self, entity: Dict) -> float:
        """Estima area da secao transversal do pilar (normalizada)."""
        # Usar dim_width * dim_height se disponivel
        dw = self._safe_float(entity, 'dim_width', 0)
        dh = self._safe_float(entity, 'dim_height', 0)
        if dw > 0 and dh > 0:
            area = dw * dh
            return min(area / 10000.0, 1.0)  # normaliza para max 100x100cm
        return 0.0

    def _is_cambotado(self, entity: Dict) -> float:
        """Detecta se pilar e cambotado (desalinhado entre pavimentos)."""
        extra = entity.get('extra', {})
        if isinstance(extra, dict):
            return 1.0 if extra.get('cambotado', False) else 0.0
        return 0.0

    def _compute_comprimento_norm(self, entity: Dict) -> float:
        """Comprimento da viga normalizado (max diagonal da bbox, log-scale)."""
        w = abs(self._safe_float(entity, 'bbox_xmax') - self._safe_float(entity, 'bbox_xmin'))
        h = abs(self._safe_float(entity, 'bbox_ymax') - self._safe_float(entity, 'bbox_ymin'))
        comp = math.sqrt(w * w + h * h)
        if comp <= 0:
            return 0.0
        return min(math.log10(max(comp, 1.0)) / 4.0, 1.0)  # max ~10000 unidades

    def _estimate_section_h(self, entity: Dict) -> float:
        """Estima altura da secao da viga (normalizada)."""
        dh = self._safe_float(entity, 'dim_height', 0)
        if dh > 0:
            return min(dh / 100.0, 1.0)  # max 100cm
        return 0.0

    def _estimate_section_w(self, entity: Dict) -> float:
        """Estima largura da secao da viga (normalizada)."""
        dw = self._safe_float(entity, 'dim_width', 0)
        if dw > 0:
            return min(dw / 50.0, 1.0)  # max 50cm (tipico 14-25cm)
        return 0.0

    def _compute_bbox_ratio(self, entity: Dict) -> float:
        """Razao bbox (min_dim / max_dim), mede elongacao."""
        w = abs(self._safe_float(entity, 'bbox_xmax') - self._safe_float(entity, 'bbox_xmin'))
        h = abs(self._safe_float(entity, 'bbox_ymax') - self._safe_float(entity, 'bbox_ymin'))
        if w <= 0 and h <= 0:
            return 0.5
        min_d = min(w, h)
        max_d = max(w, h)
        return min_d / max_d if max_d > 0 else 0.5

    def _fmt(self, val: float) -> str:
        """Formata valor para a chave DNA."""
        return f"{val:.{self.precision}f}"

    # ---- DNA Generators por tipo ----

    def gerar_dna_pilar(self, entity: Dict) -> str:
        """
        DNA para pilar (8D):
        aspect, area_norm, n_verts, layer_hash, secao_area_est, level_frac, is_cambotado, text_P
        """
        values = [
            self.quantizar(self._compute_aspect(entity)),
            self.quantizar(self._compute_area_norm(entity)),
            self.quantizar(self._compute_n_verts(entity)),
            self.quantizar(self._layer_hash(entity.get('layer', ''))),
            self.quantizar(self._estimate_section_area(entity)),
            self.quantizar(self._compute_level_frac(entity)),
            self._is_cambotado(entity),
            self._has_text_pattern(entity.get('text_content', ''), r'^P\d+'),
        ]
        return ",".join(self._fmt(v) for v in values)

    def gerar_dna_viga(self, entity: Dict) -> str:
        """
        DNA para viga (8D):
        aspect, area_norm, n_verts, layer_hash, comprimento_norm, secao_h_est, secao_w_est, text_V
        """
        values = [
            self.quantizar(self._compute_aspect(entity)),
            self.quantizar(self._compute_area_norm(entity)),
            self.quantizar(self._compute_n_verts(entity)),
            self.quantizar(self._layer_hash(entity.get('layer', ''))),
            self.quantizar(self._compute_comprimento_norm(entity)),
            self.quantizar(self._estimate_section_h(entity)),
            self.quantizar(self._estimate_section_w(entity)),
            self._has_text_pattern(entity.get('text_content', ''), r'^V\d+'),
        ]
        return ",".join(self._fmt(v) for v in values)

    def gerar_dna_laje(self, entity: Dict) -> str:
        """
        DNA para laje (8D):
        area_norm, perimetro_norm, n_verts, convexidade, has_islands, aspect, bbox_ratio, level_frac
        """
        values = [
            self.quantizar(self._compute_area_norm(entity)),
            self.quantizar(self._compute_perimetro_norm(entity)),
            self.quantizar(self._compute_n_verts(entity)),
            self.quantizar(self._compute_convexidade(entity)),
            self._has_islands(entity),
            self.quantizar(self._compute_aspect(entity)),
            self.quantizar(self._compute_bbox_ratio(entity)),
            self.quantizar(self._compute_level_frac(entity)),
        ]
        return ",".join(self._fmt(v) for v in values)

    def gerar_dna_auto(self, entity: Dict, entity_type: str) -> str:
        """
        Dispatcher: gera DNA key v2 baseado no tipo da entidade.

        Args:
            entity: Dict com campos de entidade.
            entity_type: 'pilar', 'viga' ou 'laje' (case-insensitive).

        Returns:
            Chave DNA como string de 8 floats separados por virgula.
        """
        t = entity_type.lower().strip()

        if t in ('pilar', 'pillar', 'p'):
            return self.gerar_dna_pilar(entity)
        elif t in ('viga', 'beam', 'v'):
            return self.gerar_dna_viga(entity)
        elif t in ('laje', 'slab', 'l'):
            return self.gerar_dna_laje(entity)
        else:
            # Fallback: DNA generico (v1 style com quantizacao)
            logger.warning(f"Tipo nao mapeado para DNA v2: {entity_type}, usando generico")
            return self._gerar_dna_generico(entity)

    def _gerar_dna_generico(self, entity: Dict) -> str:
        """Fallback DNA generico (similar a v1 mas com quantizacao)."""
        values = [
            self.quantizar(self._compute_aspect(entity)),
            self.quantizar(self._compute_area_norm(entity)),
            self.quantizar(self._compute_n_verts(entity)),
            0.0,  # is_closed placeholder
            self.quantizar(self._layer_hash(entity.get('layer', ''))),
            0.0,  # color placeholder
            0.0,  # flag 1
            0.0,  # flag 2
        ]
        return ",".join(self._fmt(v) for v in values)
