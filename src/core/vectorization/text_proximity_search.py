"""
TextProximitySearch -- Busca nomes de elementos por proximidade textual no DXF.

Resolve o problema de Laje_name (6.9% accuracy via ML) usando busca direta:
1. Expande bbox do elemento em raio_expandido
2. Busca MTEXT/TEXT na area expandida
3. Filtra por regex especifico por tipo (L\\d+, P\\d+, V\\d+)
4. Retorna top-3 candidatos por distancia ao centroide
5. Se unico candidato com conf >= 0.8 -> auto-assign
6. Se multiplos -> lista para revisao humana
"""

import math
import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CandidatoNome:
    """Candidato de nome encontrado por proximidade textual."""
    nome: str
    distancia: float
    confianca: float
    fonte: str          # 'regex_laje', 'regex_pilar', 'regex_viga', 'texto_proximo'
    texto_original: str


# Regex por tipo de elemento estrutural
REGEX_MAP = {
    'laje':  re.compile(r'L\d+[A-Za-z]?|LAJ-\d+|LAJE[-_\s]*\d+', re.IGNORECASE),
    'pilar': re.compile(r'P\d+[A-Za-z]?', re.IGNORECASE),
    'viga':  re.compile(r'V\d+[A-Za-z]?', re.IGNORECASE),
}


class TextProximitySearch:
    """
    Busca nomes de elementos estruturais por proximidade textual no DXF.

    Estrategia:
        Para cada elemento (laje, pilar, viga), expande a bbox em raio_padrao,
        busca textos DXF na area expandida, filtra por regex do tipo esperado,
        e retorna candidatos ordenados por confianca (distancia ao centroide normalizada).

    Uso:
        search = TextProximitySearch(raio_padrao=500.0)
        candidatos = search.buscar_candidatos(entity, textos_dxf, 'laje')
        nome = search.selecionar_nome(candidatos, auto_threshold=0.8)
    """

    def __init__(self, raio_padrao: float = 500.0):
        self.raio_padrao = raio_padrao

    def buscar_candidatos(
        self,
        entity: Dict,
        textos_dxf: List[Dict],
        entity_type: str,
    ) -> List[CandidatoNome]:
        """
        Busca candidatos de nome para uma entidade por proximidade textual.

        Args:
            entity: Dict com bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax (ou x, y para textos).
            textos_dxf: Lista de dicts com {x, y, text_content, layer}.
            entity_type: 'laje', 'pilar' ou 'viga'.

        Returns:
            Lista de CandidatoNome ordenados por confianca (desc), max 3.
        """
        # Centroide da entidade
        cx = (entity.get('bbox_xmin', 0) + entity.get('bbox_xmax', 0)) / 2.0
        cy = (entity.get('bbox_ymin', 0) + entity.get('bbox_ymax', 0)) / 2.0

        # Bbox expandida
        xmin_exp = entity.get('bbox_xmin', cx) - self.raio_padrao
        xmax_exp = entity.get('bbox_xmax', cx) + self.raio_padrao
        ymin_exp = entity.get('bbox_ymin', cy) - self.raio_padrao
        ymax_exp = entity.get('bbox_ymax', cy) + self.raio_padrao

        # Regex para o tipo
        pattern = REGEX_MAP.get(entity_type)
        if pattern is None:
            logger.warning(f"Tipo desconhecido para busca por proximidade: {entity_type}")
            return []

        candidatos: List[CandidatoNome] = []

        for texto in textos_dxf:
            tx = float(texto.get('x', 0))
            ty = float(texto.get('y', 0))
            content = str(texto.get('text_content', '')).strip()

            if not content:
                continue

            # Verificar se texto esta dentro da area expandida
            if not (xmin_exp <= tx <= xmax_exp and ymin_exp <= ty <= ymax_exp):
                continue

            # Aplicar regex
            match = pattern.search(content)
            if not match:
                continue

            nome_encontrado = match.group(0).upper()

            # Distancia euclidiana do texto ao centroide
            dist = math.sqrt((tx - cx) ** 2 + (ty - cy) ** 2)

            # Confianca inversamente proporcional a distancia
            # dist=0 -> conf=1.0; dist=raio -> conf=0.5; dist>raio -> <0.5
            if self.raio_padrao > 0:
                conf = max(0.1, 1.0 - (dist / (2.0 * self.raio_padrao)))
            else:
                conf = 1.0

            fonte = f"regex_{entity_type}"

            candidatos.append(CandidatoNome(
                nome=nome_encontrado,
                distancia=round(dist, 2),
                confianca=round(conf, 4),
                fonte=fonte,
                texto_original=content,
            ))

        # Deduplica: se mesmo nome aparece mais de uma vez, manter o mais proximo
        seen: Dict[str, CandidatoNome] = {}
        for c in candidatos:
            if c.nome not in seen or c.distancia < seen[c.nome].distancia:
                seen[c.nome] = c
        candidatos = list(seen.values())

        # Ordenar por confianca (desc) e retornar top 3
        candidatos.sort(key=lambda c: c.confianca, reverse=True)
        return candidatos[:3]

    def selecionar_nome(
        self,
        candidatos: List[CandidatoNome],
        auto_threshold: float = 0.8,
    ) -> Optional[str]:
        """
        Seleciona o nome automaticamente se possivel.

        Args:
            candidatos: Lista de CandidatoNome.
            auto_threshold: Confianca minima para auto-selecao.

        Returns:
            Nome selecionado (str) ou None se precisar revisao humana.
        """
        if not candidatos:
            return None

        # Se unico candidato com confianca >= threshold -> auto-assign
        if len(candidatos) == 1 and candidatos[0].confianca >= auto_threshold:
            return candidatos[0].nome

        # Se melhor candidato tem confianca >> segundo, tambem auto-assign
        if len(candidatos) >= 2:
            best = candidatos[0]
            second = candidatos[1]
            if best.confianca >= auto_threshold and (best.confianca - second.confianca) >= 0.2:
                return best.nome

        # Multiplos candidatos ou confianca baixa -> revisao humana
        return None

    def processar_pavimento(
        self,
        entities: List[Dict],
        textos: List[Dict],
    ) -> Dict[str, str]:
        """
        Processa todos os elementos de um pavimento.

        Para cada entidade, busca candidatos de nome e tenta auto-selecionar.

        Args:
            entities: Lista de dicts com entity_id, entity_type ('laje','pilar','viga'),
                      bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax.
            textos: Lista de dicts com x, y, text_content, layer.

        Returns:
            Dict entity_id -> nome_selecionado (apenas para auto-selecionados).
        """
        resultado: Dict[str, str] = {}

        for entity in entities:
            eid = entity.get('entity_id', entity.get('id', ''))
            etype = str(entity.get('entity_type', '')).lower()

            # Normalizar tipo: "Pilar" -> "pilar", "Viga" -> "viga", etc.
            if etype not in REGEX_MAP:
                continue

            candidatos = self.buscar_candidatos(entity, textos, etype)
            nome = self.selecionar_nome(candidatos)

            if nome:
                resultado[eid] = nome
                logger.debug(
                    f"Auto-assigned {etype} {eid} -> {nome} "
                    f"(conf={candidatos[0].confianca:.2f})"
                )
            elif candidatos:
                logger.debug(
                    f"Revisao necessaria para {etype} {eid}: "
                    f"{[c.nome for c in candidatos]}"
                )

        logger.info(
            f"Pavimento processado: {len(resultado)}/{len(entities)} "
            f"elementos auto-nomeados"
        )
        return resultado
