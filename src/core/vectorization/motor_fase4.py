"""
Motor Fase 4 - Calculation Engine
====================================
Transforma entidades estruturais vetorizadas (pilares, vigas, lajes)
em configuracoes de calculo para os Robos (Bolt, Crane, Slab).

Workflow:
    ObraKnowledge (entities do StructuralVectorizer)
        -> MotorFase4.processar_pavimento(kb, pavimento)
        -> calcular_pilares / calcular_laterais / calcular_fundos / calcular_lajes / calcular_garfos
        -> CalculationResult (pronto para Bolt/Crane/Slab)

Responsabilidades:
- Parsear secoes estruturais (ex: '19/53' -> (19, 53))
- Associar textos proximos a entities (por proximidade espacial)
- Calcular configuracoes de paineis, garfos, lajes
- Propagar secoes cross-pavimento via _global_label_sections
- Fallback: TransformationEngine quando disponivel
"""

import re
import json
import math
import logging
import collections
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Regex para parsear secoes estruturais: '19/53', '19x53', '19X53'
SECAO_REGEX = re.compile(r'(\d+(?:\.\d+)?)\s*[/xX\xd7]\s*(\d+(?:\.\d+)?)', re.IGNORECASE)
LABEL_VIGA_REGEX = re.compile(r'^V\s*(\d+)')
LABEL_PILAR_REGEX = re.compile(r'^P\s*(\d+)')

# Constantes de calculo
MAX_PAINEL_LARGURA = 244.0    # cm — largura maxima de painel de compensado
LAJE_GRID_STEP = 122.0        # cm — passo do grid de pontaletes
PE_DIREITO_DEFAULT = 280.0    # cm — pe direito padrao
LAJE_ESPESSURA_DEFAULT = 12.0 # cm — espessura de laje padrao
ESCALA_UNIDADE = 1.0          # fator de escala DXF -> cm


@dataclass
class CalculationResult:
    """Resultado completo do calculo de um pavimento."""

    pavimento: str
    obra_root: str
    pilares: List[Dict] = field(default_factory=list)
    laterais: List[Dict] = field(default_factory=list)
    fundos: List[Dict] = field(default_factory=list)
    lajes: List[Dict] = field(default_factory=list)
    garfos: List[Dict] = field(default_factory=list)

    @property
    def total_configs(self) -> int:
        return len(self.pilares) + len(self.laterais) + len(self.fundos) + len(self.lajes) + len(self.garfos)

    def resumo(self) -> str:
        return (
            f"[{self.pavimento}] PL={len(self.pilares)} LV={len(self.laterais)} "
            f"FV={len(self.fundos)} LJ={len(self.lajes)} GF={len(self.garfos)} "
            f"TOTAL={self.total_configs}"
        )


class MotorFase4:
    """
    Motor de calculo Fase 4 — transforma ObraKnowledge em configs para robos.

    Uso:
        motor = MotorFase4(pe_direito=280.0, laje_espessura=12.0)
        result = motor.processar_pavimento(kb, 'P-1')
        for pilar in result.pilares:
            print(pilar)
    """

    def __init__(
        self,
        pe_direito: float = PE_DIREITO_DEFAULT,
        laje_espessura: float = LAJE_ESPESSURA_DEFAULT,
        escala: float = ESCALA_UNIDADE,
        kb=None,
    ):
        self.pe_direito = pe_direito
        self.laje_espessura = laje_espessura
        self.escala = escala
        self._kb = kb
        self._global_label_sections: Dict[str, Dict] = {}
        self._use_transformation_engine = True
        self._transformation_engine = None

        try:
            from core.robot_integration import RobotIntegration
            self._transformation_engine = RobotIntegration(db_path='project_data.vision')
        except Exception as e:
            logger.warning(f"Could not initialize TransformationEngine in MotorFase4: {e}")

    # ------------------------------------------------------------------
    # Utilitarios geometricos (metodos estaticos / de classe)
    # ------------------------------------------------------------------

    @staticmethod
    def parsear_secao(texto: str) -> Optional[Tuple[float, float]]:
        """
        Parseia texto de secao estrutural.

        Formatos suportados:
            '19/53'  -> (19.0, 53.0)
            '19x53'  -> (19.0, 53.0)
            '25X58'  -> (25.0, 58.0)

        Returns:
            (largura, altura) ou None se nao reconhecido
        """
        m = SECAO_REGEX.search(str(texto))
        if m:
            return float(m.group(1)), float(m.group(2))
        return None

    @staticmethod
    def comprimento_from_bbox(entity: Dict) -> float:
        """
        Calcula comprimento de uma entidade a partir da bbox.

        Para vigas, usa o maior lado da bbox como comprimento.
        """
        x_min = entity.get('bbox_x_min', 0)
        y_min = entity.get('bbox_y_min', 0)
        x_max = entity.get('bbox_x_max', 0)
        y_max = entity.get('bbox_y_max', 0)
        width = abs(x_max - x_min)
        height = abs(y_max - y_min)
        return max(width, height)

    @staticmethod
    def bbox_dimensions(entity: Dict) -> Tuple[float, float]:
        """Retorna (width, height) da bbox."""
        x_min = entity.get('bbox_x_min', 0)
        y_min = entity.get('bbox_y_min', 0)
        x_max = entity.get('bbox_x_max', 0)
        y_max = entity.get('bbox_y_max', 0)
        return abs(x_max - x_min), abs(y_max - y_min)

    @staticmethod
    def bbox_center(entity: Dict) -> Tuple[float, float]:
        """Centro da bbox."""
        x_min = entity.get('bbox_x_min', 0)
        y_min = entity.get('bbox_y_min', 0)
        x_max = entity.get('bbox_x_max', 0)
        y_max = entity.get('bbox_y_max', 0)
        return (x_min + x_max) / 2, (y_min + y_max) / 2

    @staticmethod
    def auto_dividir_paineis(comprimento: float, max_largura: float = MAX_PAINEL_LARGURA) -> List[float]:
        """
        Divide comprimento em paineis <= max_largura.

        Ex: 500cm -> [166.7, 166.7, 166.6] (3 paineis uniformes)

        Returns:
            Lista de larguras de cada painel
        """
        n_paineis = math.ceil(comprimento / max_largura)
        largura_uniforme = round(comprimento / n_paineis, 1)
        return [largura_uniforme] * n_paineis

    # ------------------------------------------------------------------
    # Associacao espacial
    # ------------------------------------------------------------------

    def associar_textos(
        self,
        entities: List[Dict],
        textos: List[Dict],
        raio: float = 200.0,
    ) -> Dict[str, List[Dict]]:
        """
        Associacao espacial: encontra textos proximos a cada entity.

        Usa grid espacial para O(n) ao inves de O(n*m).

        Returns:
            Dict: entity_id -> lista de textos proximos (ordenados por dist)
        """
        cell_size = raio
        grid: Dict[Tuple[int, int], List] = {}

        for txt in textos:
            tx = txt.get('x', 0)
            ty = txt.get('y', 0)
            gx = int(tx / cell_size)
            gy = int(ty / cell_size)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    key = (gx + dx, gy + dy)
                    grid.setdefault(key, []).append(txt)

        resultado: Dict[str, List] = {}
        raio2 = raio * raio

        for ent in entities:
            ent_id = ent.get('id', '')
            cx, cy = self.bbox_center(ent)
            gx = int(cx / cell_size)
            gy = int(cy / cell_size)
            proximos = []
            for candidate in grid.get((gx, gy), []):
                tx = candidate.get('x', 0)
                ty = candidate.get('y', 0)
                dist2 = (tx - cx) ** 2 + (ty - cy) ** 2
                if dist2 <= raio2:
                    proximos.append({**candidate, '_dist': math.sqrt(dist2)})
            proximos.sort(key=lambda t: t['_dist'])
            resultado[ent_id] = proximos

        return resultado

    def _extrair_secao_de_textos(
        self,
        textos_proximos: List[Dict],
    ) -> Optional[Tuple[float, float]]:
        """Tenta extrair secao (largura, altura) dos textos proximos."""
        for txt in textos_proximos:
            content = txt.get('text_content', '')
            secao = self.parsear_secao(content)
            if secao:
                return secao
        return None

    def _extrair_label(
        self,
        entity: Dict,
        textos_proximos: List[Dict],
    ) -> str:
        """Extrai label (V1, P3, etc.) da entity ou dos textos proximos."""
        label = entity.get('label', '').strip()
        if label:
            return label
        for txt in textos_proximos:
            content = txt.get('text_content', '').strip()
            if LABEL_VIGA_REGEX.match(content) or LABEL_PILAR_REGEX.match(content):
                return content
        return ''

    def _comprimento_from_spatial(
        self,
        viga: Dict,
        all_vigas: List[Dict],
    ) -> float:
        """Estimate viga comprimento from spatial relationships (pilar span)."""
        if not hasattr(self, '_spatial_cache'):
            self._load_spatial_cache()

        viga_label = viga.get('label', '')
        pilar_positions = self._spatial_cache.get(viga_label, [])  # type: ignore

        if len(pilar_positions) < 2:
            return self.comprimento_from_bbox(viga)

        max_dist = 0.0
        for i in range(len(pilar_positions)):
            px1, py1 = pilar_positions[i]
            for px2, py2 in pilar_positions[i + 1:]:
                dist = math.sqrt((px2 - px1) ** 2 + (py2 - py1) ** 2)
                if dist > max_dist:
                    max_dist = dist

        return max_dist / self.escala if max_dist > 10 else self.comprimento_from_bbox(viga)

    def _load_spatial_cache(self):
        """Load pilar positions for PILAR_SUPORTA_VIGA from DB."""
        cache: Dict[str, List] = {}
        if not hasattr(self, '_kb') or self._kb is None:
            self._spatial_cache = cache
            return
        try:
            rels = self._kb.buscar_relacionamentos('PILAR_SUPORTA_VIGA')
            pilares = self._kb.buscar_pilares()
            pilar_map = {p.get('label', ''): p for p in pilares}
            for r in rels:
                viga_label = r.get('entity_b_label', '')
                pilar_label = r.get('entity_a_label', '')
                p = pilar_map.get(pilar_label)
                if p:
                    cx = (p.get('bbox_x_min', 0) + p.get('bbox_x_max', 0)) / 2
                    cy = (p.get('bbox_y_min', 0) + p.get('bbox_y_max', 0)) / 2
                    cache.setdefault(viga_label, []).append((cx, cy))
        except Exception:
            pass
        self._spatial_cache = cache

    # ------------------------------------------------------------------
    # Enriquecimento de secoes
    # ------------------------------------------------------------------

    def _enriquecer_secoes(
        self,
        entities: List[Dict],
        textos: List[Dict],
        entity_type: str,
        raio_secao: float = 200.0,
    ) -> List[Dict]:
        """
        Pre-enriquecimento inteligente de secoes estruturais.

        3 passos:
        1. Tenta extrair secao dos textos proximos (SECAO_REGEX)
        2. Propaga secao por label (se V1a em pav1 tem 19/53, propaga para V1a em pav2)
        3. Fallback para global_default do label mais comum

        Returns:
            Entities enriquecidas com section_largura e section_altura
        """
        # Busca textos que contem secoes no pavimento inteiro
        textos_secao = [t for t in textos if SECAO_REGEX.search(str(t.get('text_content', '')))]
        secao_map = self.associar_textos(entities, textos_secao, raio=raio_secao)

        resultado = []
        label_secoes: Dict[str, Tuple[float, float]] = {}

        for ent in entities:
            eid = ent.get('id', '')
            sec_l = ent.get('section_largura')
            sec_a = ent.get('section_altura')
            label = self._extrair_label(ent, secao_map.get(eid, []))

            if not (sec_l and sec_a):
                textos_prox = secao_map.get(eid, [])
                secao = self._extrair_secao_de_textos(textos_prox)
                if secao:
                    sec_l, sec_a = secao

            if sec_l and sec_a and label:
                label_secoes[label.strip().upper()] = (sec_l, sec_a)

            resultado.append({**ent, 'section_largura': sec_l, 'section_altura': sec_a, 'label': label})

        # Cross-pavimento: propaga do _global_label_sections
        global_map = getattr(self, '_global_label_sections', {})
        cross_pav_added = 0
        for ent in resultado:
            if ent.get('section_largura') and ent.get('section_altura'):
                continue
            label = ent.get('label', '').strip().upper()
            if label in global_map:
                glabel_data = global_map[label]
                ent['section_largura'] = glabel_data.get('largura')
                ent['section_altura'] = glabel_data.get('altura')
                cross_pav_added += 1

        if cross_pav_added:
            logger.info(f"  Cross-pav enrichment: +{cross_pav_added} labels from global map ({len(global_map)})")

        # Propaga dentro do pavimento atual
        propagadas = 0
        for ent in resultado:
            if ent.get('section_largura') and ent.get('section_altura'):
                continue
            label = ent.get('label', '').strip().upper()
            if label in label_secoes:
                ent['section_largura'], ent['section_altura'] = label_secoes[label]
                propagadas += 1

        remaining = sum(1 for e in resultado if not (e.get('section_largura') and e.get('section_altura')))
        if propagadas:
            logger.info(f"  Propagadas {propagadas} secoes por label ({remaining} restantes)")

        return resultado

    # ------------------------------------------------------------------
    # Calculo por tipo de elemento
    # ------------------------------------------------------------------

    def calcular_pilares(
        self,
        pilares_db: List[Dict],
        textos_db: List[Dict],
        pe_direito: Optional[float] = None,
    ) -> List[Dict]:
        """
        Calcula PilarConfig a partir de entities do tipo 'pilar'.

        Returns:
            Lista de dicts com configuracao de cada pilar
        """
        pe_direito = pe_direito or self.pe_direito
        textos_map = self.associar_textos(pilares_db, textos_db)
        _count_defaults = 0
        configs = []

        for pilar in pilares_db:
            pid = pilar.get('id', '')
            textos_prox = textos_map.get(pid, [])
            sec_larg, sec_alt = None, None

            secao_texto = self._extrair_secao_de_textos(textos_prox)
            if secao_texto:
                sec_larg, sec_alt = secao_texto
            else:
                sec_larg = pilar.get('section_largura')
                sec_alt = pilar.get('section_altura')

            if not sec_larg:
                sec_larg = 19.0
                _count_defaults += 1
            if not sec_alt:
                sec_alt = 19.0

            label = self._extrair_label(pilar, textos_prox)
            altura_pilar = pe_direito
            alt_abaixo_laje = self.laje_espessura
            alturas_painel = [altura_pilar - alt_abaixo_laje]

            paineis = [{'a': sec_larg, 'b': sec_alt, 'c': sec_larg, 'd': sec_alt}]

            config_dict = {
                'id': pid,
                'label': label,
                'section_largura': sec_larg,
                'section_altura': sec_alt,
                'pe_direito': pe_direito,
                'alturas_painel': alturas_painel,
                'paineis': paineis,
                'bbox_x_min': pilar.get('bbox_x_min', 0),
                'bbox_y_min': pilar.get('bbox_y_min', 0),
                'bbox_x_max': pilar.get('bbox_x_max', 0),
                'bbox_y_max': pilar.get('bbox_y_max', 0),
            }
            configs.append(config_dict)

        if _count_defaults:
            logger.warning(f"  {_count_defaults} pilares sem secao -> default 19")
        logger.info(f"  calcular_pilares: {len(configs)} configs")
        return configs

    def calcular_laterais(
        self,
        vigas_db: List[Dict],
        textos_db: List[Dict],
    ) -> List[Dict]:
        """
        Calcula VigaLateralConfig a partir de entities do tipo 'viga'.

        Returns:
            Lista de dicts com configuracao de face lateral de cada viga
        """
        textos_map = self.associar_textos(vigas_db, textos_db)
        _count_defaults = 0
        configs = []

        for viga in vigas_db:
            vid = viga.get('id', '')
            textos_prox = textos_map.get(vid, [])
            sec_larg, sec_alt = None, None

            secao_texto = self._extrair_secao_de_textos(textos_prox)
            if secao_texto:
                sec_larg, sec_alt = secao_texto
            else:
                sec_larg = viga.get('section_largura')
                sec_alt = viga.get('section_altura')

            if not sec_larg:
                sec_larg = 19.0
                _count_defaults += 1
            if not sec_alt:
                sec_alt = 60.0

            comprimento = self.comprimento_from_bbox(viga) / self.escala
            if comprimento < 50.0:
                comprimento = self._comprimento_from_spatial(viga, vigas_db)

            label = self._extrair_label(viga, textos_prox)
            paineis_larguras = self.auto_dividir_paineis(comprimento)
            n_paineis = len(paineis_larguras)
            alturas1 = [sec_alt] * n_paineis
            alturas2 = [sec_alt] * n_paineis

            config_dict = {
                'id': vid,
                'label': label,
                'section_largura': sec_larg,
                'section_altura': sec_alt,
                'comprimento': comprimento,
                'n_paineis': n_paineis,
                'paineis_larguras': paineis_larguras,
                'alturas_face_a': alturas1,
                'alturas_face_b': alturas2,
                'tipo': 'Sarrafeado',
            }
            configs.append(config_dict)

        if _count_defaults:
            logger.warning(f"  {_count_defaults} vigas sem largura -> default 19")
            logger.warning(f"  {_count_defaults} vigas sem altura -> default 60")
        logger.info(f"  calcular_laterais: {len(configs)} configs")
        return configs

    def calcular_fundos(
        self,
        vigas_db: List[Dict],
        textos_db: List[Dict],
    ) -> List[Dict]:
        """
        Calcula FundoVigaConfig a partir de entities do tipo 'viga'.

        Returns:
            Lista de dicts com configuracao de fundo de cada viga
        """
        textos_map = self.associar_textos(vigas_db, textos_db)
        configs = []

        for viga in vigas_db:
            vid = viga.get('id', '')
            textos_prox = textos_map.get(vid, [])

            secao_texto = self._extrair_secao_de_textos(textos_prox)
            if secao_texto:
                sec_larg, sec_alt = secao_texto
            else:
                sec_larg = viga.get('section_largura') or 19.0
                sec_alt = viga.get('section_altura') or 60.0

            comprimento = self.comprimento_from_bbox(viga) / self.escala
            if comprimento < 50.0:
                comprimento = self._comprimento_from_spatial(viga, vigas_db)

            label = self._extrair_label(viga, textos_prox)
            paineis_larguras = self.auto_dividir_paineis(comprimento)
            paineis_str = [str(round(p, 1)) for p in paineis_larguras]

            config_dict = {
                'id': vid,
                'label': label,
                'nome': label,
                'largura': sec_larg,
                'altura': sec_alt,
                'comprimento': comprimento,
                'paineis': paineis_str,
                'linha1': f"{sec_larg}cm",
                'linha2': f"{comprimento:.0f}cm",
                'linha3': " + ".join(paineis_str),
            }
            configs.append(config_dict)

        logger.info(f"  calcular_fundos: {len(configs)} configs")
        return configs

    def calcular_lajes(
        self,
        lajes_db: List[Dict],
        kb,
        pavimento: str,
        vigas_db: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        Calcula LajeConfig a partir de entities do tipo 'laje'.

        Usa relacionamentos espaciais VIGA_BORDA_LAJE para determinar
        a lista de vigas que delimitam cada laje.

        Returns:
            Lista de dicts com configuracao de escoramento de cada laje
        """
        vigas_db = vigas_db or []
        _count_laje_invalid = 0
        _count_contorno = 0
        _count_spatial_bbox = 0
        configs = []

        viga_bbox_map: Dict[str, Dict] = {}
        for v in vigas_db:
            vlabel = v.get('label', '')
            if vlabel:
                viga_bbox_map[vlabel] = v

        laje_bordering_vigas: Dict[str, List[str]] = {}
        try:
            rels = kb.buscar_relacionamentos('VIGA_BORDA_LAJE')
            for rel in rels:
                laje_label = rel.get('entity_b_label', '')
                viga_label = rel.get('entity_a_label', '')
                laje_bordering_vigas.setdefault(laje_label, []).append(viga_label)
        except Exception as e:
            logger.debug(f"Could not load spatial relationships: {e}")

        for laje in lajes_db:
            lid = laje.get('id', '')
            x_min = laje.get('bbox_x_min', 0)
            y_min = laje.get('bbox_y_min', 0)
            x_max = laje.get('bbox_x_max', 0)
            y_max = laje.get('bbox_y_max', 0)
            width = abs(x_max - x_min) / self.escala
            height = abs(y_max - y_min) / self.escala
            area = width * height

            if area < 1:
                _count_laje_invalid += 1
                continue

            label = laje.get('label', f'L{_count_contorno + 1}')
            if not label or not label.startswith('L'):
                label = f'L{_count_contorno + 1}'
            _count_contorno += 1

            # Outline: tenta json, fallback para bbox
            outline = []
            try:
                points_json = laje.get('points_json')
                if points_json:
                    outline = json.loads(points_json)
            except (json.JSONDecodeError, TypeError):
                pass

            if not outline:
                outline = [
                    [x_min, y_min], [x_max, y_min],
                    [x_max, y_max], [x_min, y_max],
                ]
                _count_spatial_bbox += 1

            # Grid de pontaletes
            n_cols = max(1, round(width / LAJE_GRID_STEP))
            n_rows = max(1, round(height / LAJE_GRID_STEP))
            grid_step_x = width / n_cols
            grid_step_y = height / n_rows

            # Vigas de borda
            bordering = laje_bordering_vigas.get(label, [])

            config_dict = {
                'id': lid,
                'label': label,
                'area': round(area, 2),
                'width': round(width, 1),
                'height': round(height, 1),
                'outline': outline,
                'n_cols': n_cols,
                'n_rows': n_rows,
                'grid_step_x': round(grid_step_x, 1),
                'grid_step_y': round(grid_step_y, 1),
                'espessura': self.laje_espessura,
                'bordering_vigas': bordering,
            }
            configs.append(config_dict)

        logger.info(
            f"  calcular_lajes: {len(configs)} configs "
            f"({_count_spatial_bbox} bbox-fallback, {_count_laje_invalid} invalid)"
        )
        return configs

    def calcular_garfos(
        self,
        vigas_db: List[Dict],
        textos_db: List[Dict],
        pe_direito: Optional[float] = None,
    ) -> List[Dict]:
        """
        Calcula GarfoConfig a partir de entities do tipo 'viga'.

        Calcula posicoes de garfos (forcadores) ao longo do comprimento da viga.

        Returns:
            Lista de dicts com configuracao de garfos de cada viga
        """
        pe_direito = pe_direito or self.pe_direito
        textos_map = self.associar_textos(vigas_db, textos_db)
        configs = []

        for viga in vigas_db:
            vid = viga.get('id', '')
            textos_prox = textos_map.get(vid, [])

            secao_texto = self._extrair_secao_de_textos(textos_prox)
            if secao_texto:
                sec_larg, sec_alt = secao_texto
            else:
                sec_larg = viga.get('section_largura') or 19.0
                sec_alt = viga.get('section_altura') or 60.0

            comprimento = self.comprimento_from_bbox(viga) / self.escala
            if comprimento < 50.0:
                comprimento = self._comprimento_from_spatial(viga, vigas_db)

            label = self._extrair_label(viga, textos_prox)
            secao_str = f"{sec_larg:.0f}/{sec_alt:.0f}"

            config_dict = {
                'id': vid,
                'label': label,
                'section_largura': sec_larg,
                'section_altura': sec_alt,
                'secao': secao_str,
                'comprimento': comprimento,
                'pe_direito': pe_direito,
                'espessura_laje': self.laje_espessura,
                'pavimento': '',
            }
            configs.append(config_dict)

        logger.info(f"  Calculados {len(configs)} garfos")
        return configs

    # ------------------------------------------------------------------
    # Processamento principal
    # ------------------------------------------------------------------

    @staticmethod
    def carregar_pe_direito_pi(
        db_path: str,
        work_name: str,
        pavimento_nome: str = '',
    ) -> Optional[float]:
        """
        Sprint-D: Busca pe_direito real (em cm) da tabela pavimento_pi.

        Args:
            db_path: Caminho para o SQLite (project_data.vision)
            work_name: Nome da obra (work_name no DB)
            pavimento_nome: Nome do pavimento (fuzzy match, opcional)

        Returns:
            Pe direito em cm ou None se nao encontrado.
        """
        try:
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(str(db_path))
            rows = conn.execute(
                """
                SELECT pp.pe_direito FROM pavimento_pi pp
                JOIN projects p ON pp.project_id = p.id
                WHERE p.work_name = ?
                ORDER BY pp.created_at DESC
                """,
                (work_name,),
            ).fetchall()
            conn.close()
            if not rows:
                return None
            # Tentar match por nome do pavimento
            if pavimento_nome:
                pav_upper = pavimento_nome.upper()
                for row in rows:
                    if row[1] and pav_upper in str(row[1]).upper():
                        val = row[0]
                        if val:
                            return float(val) / 10.0  # mm -> cm
            # Fallback: primeiro resultado
            val = rows[0][0]
            if val:
                return float(val) / 10.0  # mm -> cm
        except Exception as ex:
            logger.warning(f"Erro ao buscar pe_direito_pi para {work_name}: {ex}")
        return None

    def processar_pavimento(
        self,
        kb,
        pavimento: str,
        pe_direito: Optional[float] = None,
        db_path: Optional[str] = None,
    ) -> CalculationResult:
        """
        Calculo completo para um pavimento.

        Pode utilizar a flag _use_transformation_engine para
        delegar ao novo TransformationEngine (Fase 4).

        Args:
            kb: ObraKnowledge com entities do pavimento
            pavimento: Nome do pavimento
            pe_direito: Pe direito (opcional -- se None, tenta pi_data ou usa default)
            db_path: Caminho DB para busca de pe_direito_pi (Sprint-D)

        Returns:
            CalculationResult com todas as configs
        """
        # Sprint-D: usar pe_direito real do PI se disponivel
        if pe_direito is None and db_path:
            work_name = getattr(kb, 'obra_root', '') or getattr(kb, 'work_name', '')
            if work_name:
                pd_real = self.carregar_pe_direito_pi(db_path, work_name, pavimento)
                if pd_real:
                    logger.info(
                        f"  [PI] pe_direito_real={pd_real:.1f}cm "
                        f"(override default {self.pe_direito}cm)"
                    )
                    pe_direito = pd_real

        if self._use_transformation_engine and self._transformation_engine:
            return self._process_with_transformation_engine(kb, pavimento, pe_direito)
        return self._processar_pavimento_legacy(kb, pavimento, pe_direito)

    def _process_with_transformation_engine(
        self,
        kb,
        pavimento: str,
        pe_direito: Optional[float] = None,
    ) -> CalculationResult:
        """Processa pavimento usando o novo TransformationEngine baseado em regras."""
        pe_direito = pe_direito or self.pe_direito
        logger.info(f"Processando pavimento '{pavimento}' com TransformationEngine...")

        vigas = kb.buscar_vigas(pavimento) if hasattr(kb, 'buscar_vigas') else []
        pilares = kb.buscar_pilares(pavimento) if hasattr(kb, 'buscar_pilares') else []
        lajes = kb.buscar_lajes(pavimento) if hasattr(kb, 'buscar_lajes') else []

        entities = vigas + pilares + lajes

        results_te = self._transformation_engine.process_pavimento(
            obra=kb.obra_root if hasattr(kb, 'obra_root') else '',
            pavimento=pavimento,
            entities=entities,
        )

        result = CalculationResult(
            pavimento=pavimento,
            obra_root=kb.obra_root if hasattr(kb, 'obra_root') else '',
            pilares=[r for r in results_te.get('pillars', []) if r.get('status') == 'success'],
            laterais=[r for r in results_te.get('beams', []) if r.get('status') == 'success'],
            fundos=[r for r in results_te.get('beams', []) if r.get('status') == 'success'],
            lajes=[r for r in results_te.get('slabs', []) if r.get('status') == 'success'],
            garfos=[r for r in results_te.get('beams', []) if r.get('status') == 'success'],
        )
        logger.info(f"  Resultado (TransformationEngine): {result.resumo()}")
        return result

    def _processar_pavimento_legacy(
        self,
        kb,
        pavimento: str,
        pe_direito: Optional[float] = None,
    ) -> CalculationResult:
        """
        Calculo completo para um pavimento (Motor legacy).

        Args:
            kb: ObraKnowledge
            pavimento: Nome do pavimento
            pe_direito: Pe direito em cm
        """
        pe_direito = pe_direito or self.pe_direito
        logger.info(f"Processando pavimento: {pavimento} (Legacy)")

        vigas = kb.buscar_vigas(pavimento) if hasattr(kb, 'buscar_vigas') else []
        pilares = kb.buscar_pilares(pavimento) if hasattr(kb, 'buscar_pilares') else []
        lajes = kb.buscar_lajes(pavimento) if hasattr(kb, 'buscar_lajes') else []
        textos = kb.buscar_textos(pavimento) if hasattr(kb, 'buscar_textos') else []

        logger.info(
            f"  Entities: {len(vigas)} vigas, {len(pilares)} pilares, "
            f"{len(lajes)} lajes, {len(textos)} textos"
        )

        pilar_secoes: Dict[str, Tuple] = {}
        viga_secoes: Dict[str, Tuple] = {}

        pilares_enriq = self._enriquecer_secoes(pilares, textos, 'pilar')
        vigas_enriq = self._enriquecer_secoes(vigas, textos, 'viga')

        for pilar in pilares_enriq:
            pid = pilar.get('id', '')
            largura = pilar.get('section_largura') or pilar.get('largura')
            if largura:
                pilar_secoes[pid] = (largura, pilar.get('section_altura', largura))

        for viga in vigas_enriq:
            vid = viga.get('id', '')
            largura = viga.get('section_largura') or viga.get('largura')
            if largura:
                viga_secoes[vid] = (largura, viga.get('section_altura', 60.0))

        textos_map_p = self.associar_textos(pilares_enriq, textos, raio=200.0)
        textos_map_v = self.associar_textos(vigas_enriq, textos, raio=200.0)

        result = CalculationResult(
            pavimento=pavimento,
            obra_root=kb.obra_root if hasattr(kb, 'obra_root') else '',
            pilares=self.calcular_pilares(pilares_enriq, textos, pe_direito),
            laterais=self.calcular_laterais(vigas_enriq, textos),
            fundos=self.calcular_fundos(vigas_enriq, textos),
            lajes=self.calcular_lajes(lajes, kb, pavimento, vigas_enriq),
            garfos=self.calcular_garfos(vigas_enriq, textos, pe_direito),
        )
        logger.info(f"  {result.resumo()}")
        return result

    def _build_global_label_sections(self, kb) -> None:
        """Build cross-pavimento label->section map from ALL entities in the obra."""
        global_map: Dict[str, Dict] = {}
        try:
            conn = kb._conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT label, section_largura, section_altura
                FROM structural_entities
                WHERE label IS NOT NULL
                  AND section_largura IS NOT NULL
                  AND section_altura IS NOT NULL
            """)
            for row in cur.fetchall():
                label = row[0].strip().upper() if row[0] else ''
                if label:
                    global_map[label] = {'largura': row[1], 'altura': row[2]}
        except Exception as e:
            logger.warning(f"Could not build global label-section map: {e}")

        self._global_label_sections = global_map
        logger.info(f"Global label-section map: {len(global_map)} labels across all pavimentos")

    def processar_obra(self, kb) -> List[CalculationResult]:
        """
        Processa todos os pavimentos de uma obra.

        Pre-builds a global label->section map for cross-pavimento enrichment.

        Returns:
            Lista de CalculationResult, um por pavimento
        """
        pavimentos = kb.listar_pavimentos() if hasattr(kb, 'listar_pavimentos') else []
        self._build_global_label_sections(kb)

        resultados = []
        for pav in pavimentos:
            nome_pav = pav.get('nome', pav) if isinstance(pav, dict) else pav
            try:
                result = self.processar_pavimento(kb, nome_pav)
                resultados.append(result)
            except Exception as e:
                logger.error(f"Erro processando pavimento {nome_pav}: {e}")

        return resultados
