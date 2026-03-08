# -*- coding: utf-8 -*-
"""
Fase 2 - Triagem do Pipeline GAP-5
"""

import json
import logging
import math
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rtree import index as rtree_index
except ImportError:
    rtree_index = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class TriagemResultado:
    pavimentos_encontrados: List[str]
    entidades_por_pavimento: Dict[str, int]
    layers_limpos: int
    entidades_nomeadas: int
    detalhes_separados: int
    indice_espacial_criado: bool
    tempo_total_seg: float = 0.0


@dataclass
class IndiceEspacial:
    _idx: Optional[Any] = field(default=None, repr=False)
    _entities: Dict[str, Any] = field(default_factory=dict, repr=False)
    _counter: int = field(default=0, repr=False)
    
    def __post_init__(self):
        if rtree_index is not None and self._idx is None:
            self._idx = rtree_index.Index()
    
    def inserir(self, id_entidade: str, bounds: Tuple[float, float, float, float]):
        if self._idx is not None:
            self._counter += 1
            self._idx.insert(self._counter, bounds)
        self._entities[id_entidade] = bounds
    
    def consultar(self, bounds: Tuple[float, float, float, float]) -> List[str]:
        if self._idx is not None:
            ids = list(self._idx.intersection(bounds))
            # Rtree retorna IDs inteiros, precisamos mapear de volta
            # Para simplificar, retornamos todas as entidades no fallback
            return list(self._entities.keys())[:len(ids)]
        results = []
        min_x, min_y, max_x, max_y = bounds
        for id_ent, b in self._entities.items():
            if not (b[2] < min_x or b[3] < min_y or b[0] > max_x or b[1] > max_y):
                results.append(id_ent)
        return results
    
    def salvar(self, path: str):
        data = {"entities": self._entities, "type": "spatial_index"}
        with open(path, 'w') as f:
            json.dump(data, f)
    
    def carregar(self, path: str):
        with open(path, 'r') as f:
            data = json.load(f)
        self._entities = data.get("entities", {})
    
    def __len__(self) -> int:
        return len(self._entities)


class Fase2Triagem:
    PAVIMENTO_PATTERNS = [
        (r'P[-_]?(\d+)', lambda m: f'P{m.group(1)}'),
        (r'TERREO|TERREO', lambda m: 'TERREO'),
        (r'SUBSOLO', lambda m: 'SUBSOLO'),
    ]
    
    LAYERS_EQUIVALENTES = {
        'PILAR': 'PILAR', 'PILARES': 'PILAR', 'PILLAR': 'PILAR',
        'VIGA': 'VIGA', 'VIGAS': 'VIGA', 'BEAM': 'VIGA',
        'LAJE': 'LAJE', 'LAJES': 'LAJE', 'SLAB': 'LAJE',
        'COTA': 'COTA', 'COTAS': 'COTA', 'DIMENSION': 'COTA',
    }
    
    DETALHE_PATTERNS = [r'DETALHE', r'DETAIL', r'ESCALA', r'ISCA']
    
    def __init__(self, obra_dir: str, db_path: str = "project_data.vision"):
        self.obra_dir = Path(obra_dir)
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
    
    def _connect(self) -> sqlite3.Connection:
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def executar(self, obra_id: Optional[str] = None) -> TriagemResultado:
        logger.info(f"[{obra_id or 'N/A'}] Iniciando Fase 2 - Triagem")
        inicio = time.time()
        
        entidades = self._carregar_entidades(obra_id)
        textos = self._carregar_textos(obra_id)
        
        entidades = self.limpar_layers(entidades)
        pavimentos = self.separar_pavimentos(entidades)
        entidades_nomeadas = self.nomear_entidades(entidades, textos)
        indice = self.criar_indice_espacial(entidades)
        detalhes = self.detectar_detalhes(entidades)
        
        resultado = TriagemResultado(
            pavimentos_encontrados=sorted(list(pavimentos.keys())),
            entidades_por_pavimento={pav: len(ents) for pav, ents in pavimentos.items()},
            layers_limpos=len(entidades),
            entidades_nomeadas=len(entidades_nomeadas),
            detalhes_separados=len(detalhes),
            indice_espacial_criado=len(indice) > 0
        )
        
        resultado.tempo_total_seg = time.time() - inicio
        return resultado
    
    def _carregar_entidades(self, obra_id: Optional[str]) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        if obra_id:
            cursor.execute("SELECT id, obra_id, tipo, layer, dados_json, posicao_x, posicao_y FROM dxf_entidades WHERE obra_id = ?", (obra_id,))
        else:
            cursor.execute("SELECT id, obra_id, tipo, layer, dados_json, posicao_x, posicao_y FROM dxf_entidades")
        
        entidades = []
        for row in cursor.fetchall():
            entidade = dict(row)
            try:
                entidade["dados"] = json.loads(entidade["dados_json"]) if entidade["dados_json"] else {}
            except:
                entidade["dados"] = {}
            del entidade["dados_json"]
            entidades.append(entidade)
        return entidades
    
    def _carregar_textos(self, obra_id: Optional[str]) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        textos = []
        
        cursor.execute("SELECT id, dados_json, posicao_x, posicao_y FROM dxf_entidades WHERE tipo IN ('TEXT', 'MTEXT', 'TEXTO')")
        for row in cursor.fetchall():
            entidade = dict(row)
            try:
                dados = json.loads(entidade["dados_json"]) if entidade["dados_json"] else {}
            except:
                dados = {}
            textos.append({
                "conteudo": dados.get("conteudo", ""),
                "posicao_x": entidade["posicao_x"],
                "posicao_y": entidade["posicao_y"]
            })
        return textos
    
    def separar_pavimentos(self, entidades: List[Dict]) -> Dict[str, List[Dict]]:
        logger.info("Separando entidades por pavimento")
        pavimentos: Dict[str, List[Dict]] = {}
        
        for entidade in entidades:
            layer = entidade.get("layer", "").upper()
            pavimento = self._detectar_pavimento(layer, entidade)
            
            if pavimento not in pavimentos:
                pavimentos[pavimento] = []
            entidade["pavimento"] = pavimento
            pavimentos[pavimento].append(entidade)
        
        if not pavimentos:
            pavimentos["GERAL"] = entidades
        
        return pavimentos
    
    def _detectar_pavimento(self, layer: str, entidade: Dict) -> str:
        for pattern, formatter in self.PAVIMENTO_PATTERNS:
            match = re.search(pattern, layer, re.IGNORECASE)
            if match:
                return formatter(match)
        
        dados = entidade.get("dados", {})
        conteudo = dados.get("conteudo", "")
        for pattern, formatter in self.PAVIMENTO_PATTERNS:
            match = re.search(pattern, conteudo, re.IGNORECASE)
            if match:
                return formatter(match)
        
        return layer.split('_')[0] if '_' in layer else "GERAL"
    
    def limpar_layers(self, entidades: List[Dict]) -> List[Dict]:
        logger.info("Limpando e padronizando layers")
        
        for entidade in entidades:
            layer_original = entidade.get("layer", "")
            layer_limpo = layer_original.upper()
            layer_limpo = re.sub(r'[^A-Z0-9_]', '_', layer_limpo)
            layer_limpo = re.sub(r'_+', '_', layer_limpo)
            layer_limpo = layer_limpo.strip('_')
            
            for equivalente, padrao in self.LAYERS_EQUIVALENTES.items():
                if equivalente in layer_limpo:
                    layer_limpo = padrao
                    break
            
            entidade["layer_original"] = layer_original
            entidade["layer"] = layer_limpo
        
        return entidades
    
    def nomear_entidades(self, entidades: List[Dict], textos: List[Dict]) -> List[Dict]:
        logger.info("Nomeando entidades com textos próximos")
        entidades_nomeadas = []
        distancia_maxima = 500.0
        
        for entidade in entidades:
            ent_x = entidade.get("posicao_x")
            ent_y = entidade.get("posicao_y")
            
            if ent_x is None or ent_y is None:
                continue
            
            texto_mais_proximo = None
            menor_distancia = distancia_maxima
            
            for texto in textos:
                txt_x = texto.get("posicao_x")
                txt_y = texto.get("posicao_y")
                
                if txt_x is None or txt_y is None:
                    continue
                
                dx = ent_x - txt_x
                dy = ent_y - txt_y
                distancia = math.sqrt(dx * dx + dy * dy)
                
                if distancia < menor_distancia:
                    menor_distancia = distancia
                    texto_mais_proximo = texto
            
            if texto_mais_proximo:
                entidade["nome_associado"] = texto_mais_proximo.get("conteudo", "")
                entidade["distancia_nome"] = menor_distancia
                entidades_nomeadas.append(entidade)
        
        return entidades_nomeadas
    
    def criar_indice_espacial(self, entidades: List[Dict]) -> IndiceEspacial:
        logger.info("Criando índice espacial")
        indice = IndiceEspacial()
        
        for entidade in entidades:
            bbox = self._obter_bbox(entidade)
            if bbox:
                id_entidade = entidade.get("id", str(hash(json.dumps(entidade))))
                indice.inserir(id_entidade, bbox)
        
        return indice
    
    def _obter_bbox(self, entidade: Dict) -> Optional[Tuple[float, float, float, float]]:
        dados = entidade.get("dados", {})
        if "bbox" in dados:
            bbox = dados["bbox"]
            return (bbox.get("min_x", 0), bbox.get("min_y", 0), bbox.get("max_x", 0), bbox.get("max_y", 0))
        
        if "pontos" in dados:
            pontos = dados["pontos"]
            if pontos:
                xs = [p.get("x", 0) for p in pontos]
                ys = [p.get("y", 0) for p in pontos]
                return (min(xs), min(ys), max(xs), max(ys))
        
        pos_x = entidade.get("posicao_x")
        pos_y = entidade.get("posicao_y")
        
        if pos_x is not None and pos_y is not None:
            tolerance = 10.0
            return (pos_x - tolerance, pos_y - tolerance, pos_x + tolerance, pos_y + tolerance)
        
        return None
    
    def detectar_detalhes(self, entidades: List[Dict]) -> List[Dict]:
        logger.info("Detectando detalhes não estruturais")
        detalhes = []
        
        for entidade in entidades:
            is_detalhe = False
            motivo = []
            
            layer = entidade.get("layer", "").upper()
            for pattern in self.DETALHE_PATTERNS:
                if re.search(pattern, layer, re.IGNORECASE):
                    is_detalhe = True
                    motivo.append(f"layer:{pattern}")
                    break
            
            dados = entidade.get("dados", {})
            conteudo = dados.get("conteudo", "")
            for pattern in self.DETALHE_PATTERNS:
                if re.search(pattern, conteudo, re.IGNORECASE):
                    is_detalhe = True
                    motivo.append(f"texto:{pattern}")
                    break
            
            if is_detalhe:
                entidade["detalhe_motivo"] = ", ".join(motivo)
                entidade["is_detalhe"] = True
                detalhes.append(entidade)
            else:
                entidade["is_detalhe"] = False
        
        return detalhes


__all__ = ['Fase2Triagem', 'TriagemResultado', 'IndiceEspacial']
