# -*- coding: utf-8 -*-
"""
Fase 3 - Interpretação e Extração - GAP-2

Módulo principal de interpretação semântica que extrai entidades estruturais
(pilares, vigas, lajes) a partir das entidades catalogadas nas Fases 1-2.
"""

import json
import logging
import math
import re
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pipeline.transformation_engine import TransformationEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class FichaFase3Pilar:
    """Ficha de pilar - saída da interpretação semântica."""
    id: str
    numero: str
    pavimento: str
    pavimento_numero: int
    obra: str
    comprimento: float
    largura: float
    altura_cm: float
    nivel_saida_m: float
    nivel_chegada_m: float
    pavimento_anterior: str = ""
    par_1_2: str = "0"
    par_2_3: str = "0"
    par_3_4: str = "0"
    par_4_5: str = "0"
    par_5_6: str = "0"
    par_6_7: str = "0"
    par_7_8: str = "0"
    par_8_9: str = "0"
    grade_1: str = ""
    distancia_1: str = ""
    grade_2: str = ""
    distancia_2: str = ""
    grade_3: str = ""
    pilar_especial: bool = False
    tipo_pilar_especial: str = "L"
    confidence: float = 0.0
    dna_vector: List[float] = field(default_factory=list)
    revisado_por_humano: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def validar(self) -> list:
        erros = []
        if not self.id:
            erros.append("id vazio")
        if self.comprimento <= 0:
            erros.append(f"comprimento inválido: {self.comprimento}")
        if self.largura <= 0:
            erros.append(f"largura inválida: {self.largura}")
        if self.altura_cm <= 0:
            erros.append(f"altura inválida: {self.altura_cm}")
        return erros
    
    def precisa_revisao(self) -> bool:
        if self.revisado_por_humano:
            return False
        if self.confidence < 0.80:
            return True
        return len(self.validar()) > 0


@dataclass
class FichaFase3Viga:
    """Ficha de viga - saída da interpretação semântica."""
    codigo: str
    pavimento: str
    obra_nome: str
    tipo: str
    largura: float
    altura: float
    comprimento: float
    secao_transversal: dict = field(default_factory=dict)
    tramos: List[dict] = field(default_factory=list)
    armadura_positiva: dict = field(default_factory=dict)
    armadura_negativa: dict = field(default_factory=dict)
    estribos: dict = field(default_factory=dict)
    garfos: Optional[dict] = None
    confidence: float = 0.0
    dna_vector: List[float] = field(default_factory=list)
    data_extracao: datetime = field(default_factory=datetime.now)
    revisado: bool = False
    
    def validate(self) -> list:
        erros = []
        if not self.codigo:
            erros.append("código vazio")
        if self.largura < 12:
            erros.append(f"largura inválida: {self.largura}cm")
        if self.altura < 25:
            erros.append(f"altura inválida: {self.altura}cm")
        return erros
    
    def to_dict(self) -> dict:
        d = asdict(self)
        if isinstance(d.get("data_extracao"), datetime):
            d["data_extracao"] = d["data_extracao"].isoformat()
        return d
    
    def precisa_revisao(self) -> bool:
        if self.revisado:
            return False
        if self.confidence < 0.80:
            return True
        return len(self.validate()) > 0


@dataclass
class FichaFase3Laje:
    """Ficha de laje - saída da interpretação semântica."""
    codigo: str
    pavimento: str
    obra_nome: str
    tipo: str
    dimensoes: dict = field(default_factory=dict)
    espessura: float = 10.0
    outline_segs: List[dict] = field(default_factory=list)
    nivel: float = 0.0
    armadura: dict = field(default_factory=dict)
    confidence: float = 0.0
    dna_vector: List[float] = field(default_factory=list)
    data_extracao: datetime = field(default_factory=datetime.now)
    revisado: bool = False
    
    def validate(self) -> list:
        erros = []
        if not self.codigo:
            erros.append("código vazio")
        if self.tipo not in ["macica", "pre_moldada", "steel_deck"]:
            erros.append(f"tipo inválido '{self.tipo}'")
        if self.espessura < 7:
            erros.append(f"espessura inválida: {self.espessura}cm")
        if not self.outline_segs or len(self.outline_segs) < 3:
            erros.append("outline_segs deve ter pelo menos 3 vértices")
        return erros
    
    def area(self) -> float:
        if not self.outline_segs or len(self.outline_segs) < 3:
            dim = self.dimensoes or {}
            return (dim.get("comprimento", 0) / 100) * (dim.get("largura", 0) / 100)
        n = len(self.outline_segs)
        area_cm2 = 0.0
        for i in range(n):
            j = (i + 1) % n
            area_cm2 += self.outline_segs[i].get("x", 0) * self.outline_segs[j].get("y", 0)
            area_cm2 -= self.outline_segs[j].get("x", 0) * self.outline_segs[i].get("y", 0)
        return abs(area_cm2) / 2 / 10000
    
    def to_dict(self) -> dict:
        d = asdict(self)
        if isinstance(d.get("data_extracao"), datetime):
            d["data_extracao"] = d["data_extracao"].isoformat()
        return d
    
    def precisa_revisao(self) -> bool:
        if self.revisado:
            return False
        if self.confidence < 0.80:
            return True
        return len(self.validate()) > 0


@dataclass
class InterpretacaoResultado:
    """Resultado da interpretação Fase 3."""
    obra_id: str
    pilares: List[FichaFase3Pilar] = field(default_factory=list)
    vigas: List[FichaFase3Viga] = field(default_factory=list)
    lajes: List[FichaFase3Laje] = field(default_factory=list)
    erros: List[str] = field(default_factory=list)
    tempo_total_seg: float = 0.0
    
    @property
    def total_fichas(self) -> int:
        return len(self.pilares) + len(self.vigas) + len(self.lajes)
    
    @property
    def accuracy_media(self) -> float:
        if self.total_fichas == 0:
            return 0.0
        all_conf = [p.confidence for p in self.pilares] + [v.confidence for v in self.vigas] + [l.confidence for l in self.lajes]
        return sum(all_conf) / len(all_conf) if all_conf else 0.0


class Fase3Interpretacao:
    """Interpretação semântica de entidades estruturais."""
    
    DISTANCIA_MAXIMA_TEXTO = 500.0
    CONFIDENCE_ALTA = 0.8
    CONFIDENCE_MEDIA = 0.6
    CONFIDENCE_BAIXA = 0.4
    
    def __init__(self, db_path: str = "project_data.vision"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.transform_engine: Optional[TransformationEngine] = None
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
        if self.transform_engine:
            self.transform_engine.close()
            self.transform_engine = None
    
    def executar(self, obra_id: str) -> InterpretacaoResultado:
        """Executa interpretação completa da obra."""
        logger.info(f"[{obra_id}] Iniciando Fase 3 - Interpretação")
        resultado = InterpretacaoResultado(obra_id=obra_id)
        
        try:
            obra = self._carregar_obra(obra_id)
            if not obra:
                resultado.erros.append(f"Obra não encontrada: {obra_id}")
                return resultado
            
            entidades = self._carregar_entidades(obra_id)
            if not entidades:
                resultado.erros.append(f"Nenhuma entidade encontrada: {obra_id}")
                return resultado
            
            textos = self._carregar_textos(obra_id)
            pavimentos = self._organizar_pavimentos(entidades)
            
            self.transform_engine = TransformationEngine(self.db_path)
            self.transform_engine.load_rules_from_db()
            
            resultado.pilares = self.interpretar_pilares(entidades, pavimentos, textos, obra.get("nome", obra_id))
            resultado.vigas = self.interpretar_vigas(entidades, pavimentos, textos, obra.get("nome", obra_id))
            resultado.lajes = self.interpretar_lajes(entidades, pavimentos, textos, obra.get("nome", obra_id))
            
            self._aplicar_transformacoes(resultado)
            total_salvas = self.salvar_fichas(resultado, obra_id)
            
            logger.info(f"[{obra_id}] Fase 3: {len(resultado.pilares)} pilares, {len(resultado.vigas)} vigas, {len(resultado.lajes)} lajes")
            logger.info(f"[{obra_id}] Accuracy média: {resultado.accuracy_media:.2%}")
            
        except Exception as e:
            logger.error(f"[{obra_id}] Erro na Fase 3: {e}")
            resultado.erros.append(str(e))
        
        return resultado
    
    def _carregar_obra(self, obra_id: str) -> Optional[dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM obras WHERE id = ?", (obra_id,))
        row = cursor.fetchone()
        return dict(row) if row else {"id": obra_id, "nome": f"Obra_{obra_id[:8]}"}
    
    def _carregar_entidades(self, obra_id: str) -> List[dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, obra_id, tipo, layer, dados_json, posicao_x, posicao_y FROM dxf_entidades WHERE obra_id = ?", (obra_id,))
        
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
    
    def _carregar_textos(self, obra_id: str) -> List[dict]:
        cursor = self.conn.cursor()
        textos = []
        try:
            cursor.execute("SELECT dados_json, posicao_x, posicao_y FROM dxf_entidades WHERE obra_id = ? AND tipo IN ('TEXT', 'MTEXT', 'TEXTO', 'ATTRIB')", (obra_id,))
            for row in cursor.fetchall():
                try:
                    dados = json.loads(row["dados_json"]) if row["dados_json"] else {}
                except:
                    dados = {}
                conteudo = dados.get("conteudo", "") or dados.get("text", "")
                if conteudo:
                    textos.append({"conteudo": conteudo, "posicao_x": row["posicao_x"], "posicao_y": row["posicao_y"]})
        except sqlite3.OperationalError:
            pass
        return textos
    
    def _organizar_pavimentos(self, entidades: List[dict]) -> dict:
        pavimentos = {}
        for ent in entidades:
            pavimento = ent.get("pavimento", "GERAL")
            if pavimento not in pavimentos:
                pavimentos[pavimento] = []
            pavimentos[pavimento].append(ent)
        return pavimentos
    
    def interpretar_pilares(self, entidades: List[dict], pavimentos: dict, textos: List[dict], obra_nome: str) -> List[FichaFase3Pilar]:
        """Interpreta pilares a partir de entidades catalogadas."""
        pilares = []
        entidades_pilar = self._filtrar_entidades_pilar(entidades)
        
        for ent in entidades_pilar:
            try:
                ficha = self._criar_ficha_pilar(ent, textos, pavimentos, obra_nome)
                if ficha:
                    pilares.append(ficha)
            except Exception as e:
                logger.debug(f"Erro ao interpretar pilar: {e}")
        
        return pilares
    
    def _filtrar_entidades_pilar(self, entidades: List[dict]) -> List[dict]:
        pilar_keywords = {"PILAR", "PILLAR", "P", "COL"}
        filtradas = []
        for ent in entidades:
            tipo = ent.get("tipo", "").upper()
            layer = ent.get("layer", "").upper()
            dados = ent.get("dados", {})
            nome_block = dados.get("nome_block", "").upper()
            
            if tipo in ("INSERT", "BLOCK_REFERENCE", "BLOCK"):
                filtradas.append(ent)
            elif any(k in layer for k in pilar_keywords):
                filtradas.append(ent)
            elif any(k in nome_block for k in pilar_keywords):
                filtradas.append(ent)
        return filtradas
    
    def _criar_ficha_pilar(self, entidade: dict, textos: List[dict], pavimentos: dict, obra_nome: str) -> Optional[FichaFase3Pilar]:
        dados = entidade.get("dados", {})
        pavimento = entidade.get("pavimento", "GERAL")
        pavimento_numero = self._extrair_numero_pavimento(pavimento)
        
        dimensoes = self._extrair_dimensoes_pilar(entidade)
        largura = dimensoes.get("largura", 30.0)
        comprimento = dimensoes.get("comprimento", 30.0)
        
        if comprimento < largura:
            comprimento, largura = largura, comprimento
        
        nome = self._extrair_nome_pilar(entidade, textos)
        numero = self._extrair_numero_pilar(nome)
        altura_cm = 300.0
        
        area = largura * comprimento
        perimetro = 2 * (largura + comprimento)
        dna_vector = [largura, comprimento, area, perimetro]
        
        confidence = self.calcular_confidence({"nome": nome, "dimensoes": dimensoes}, entidade)
        
        return FichaFase3Pilar(
            id=nome or f"P{len(pavimentos.get(pavimento, [])) + 1}",
            numero=numero,
            pavimento=pavimento,
            pavimento_numero=pavimento_numero,
            obra=obra_nome,
            comprimento=comprimento,
            largura=largura,
            altura_cm=altura_cm,
            nivel_saida_m=0.0,
            nivel_chegada_m=altura_cm / 100,
            confidence=confidence,
            dna_vector=dna_vector
        )
    
    def _extrair_dimensoes_pilar(self, entidade: dict) -> dict:
        dados = entidade.get("dados", {})
        atributos = dados.get("atributos", {})
        
        if "largura" in atributos and "comprimento" in atributos:
            return {"largura": float(atributos["largura"]), "comprimento": float(atributos["comprimento"])}
        
        nome_block = dados.get("nome_block", "")
        match = self._parse_dimensoes_nome(nome_block)
        if match:
            return match
        
        conteudo = dados.get("conteudo", "")
        match = self._parse_dimensoes_nome(conteudo)
        if match:
            return match
        
        return {"largura": 30.0, "comprimento": 30.0}
    
    def _parse_dimensoes_nome(self, texto: str) -> Optional[dict]:
        patterns = [r"(\d+)[xX/](\d+)", r"(\d+)\.(\d+)"]
        for pattern in patterns:
            match = re.search(pattern, texto)
            if match:
                d1 = float(match.group(1))
                d2 = float(match.group(2))
                if d1 < 10 and d2 < 10:
                    d1 *= 10
                    d2 *= 10
                return {"largura": d1, "comprimento": d2}
        return None
    
    def _extrair_nome_pilar(self, entidade: dict, textos: List[dict]) -> str:
        dados = entidade.get("dados", {})
        nome_block = dados.get("nome_block", "")
        if nome_block:
            match = re.search(r"([A-Z]?\d+)", nome_block, re.IGNORECASE)
            if match:
                return match.group(1)
        
        texto = self._encontrar_texto_proximo(entidade, textos)
        if texto:
            match = re.search(r"([A-Z]?\d+)", texto, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""
    
    def _extrair_numero_pilar(self, nome: str) -> str:
        match = re.search(r"(\d+)", nome)
        return match.group(1) if match else "0"
    
    def interpretar_vigas(self, entidades: List[dict], pavimentos: dict, textos: List[dict], obra_nome: str) -> List[FichaFase3Viga]:
        """Interpreta vigas a partir de entidades catalogadas."""
        vigas = []
        entidades_viga = self._filtrar_entidades_viga(entidades)
        grupos_vigas = self._agrupar_vigas_por_linha(entidades_viga)
        
        for grupo in grupos_vigas:
            try:
                ficha = self._criar_ficha_viga(grupo, textos, pavimentos, obra_nome)
                if ficha:
                    vigas.append(ficha)
            except Exception as e:
                logger.debug(f"Erro ao interpretar viga: {e}")
        
        return vigas
    
    def _filtrar_entidades_viga(self, entidades: List[dict]) -> List[dict]:
        viga_keywords = {"VIGA", "BEAM", "V", "VG"}
        filtradas = []
        for ent in entidades:
            tipo = ent.get("tipo", "").upper()
            layer = ent.get("layer", "").upper()
            if tipo in ("LINE", "POLYLINE", "LWPOLYLINE", "SPLINE"):
                if any(k in layer for k in viga_keywords):
                    filtradas.append(ent)
        return filtradas
    
    def _agrupar_vigas_por_linha(self, entidades: List[dict]) -> List[List[dict]]:
        if not entidades:
            return []
        return [[ent] for ent in entidades]
    
    def _criar_ficha_viga(self, grupo: List[dict], textos: List[dict], pavimentos: dict, obra_nome: str) -> Optional[FichaFase3Viga]:
        if not grupo:
            return None
        
        entidade = grupo[0]
        dados = entidade.get("dados", {})
        pavimento = entidade.get("pavimento", "GERAL")
        dimensoes = self._extrair_dimensoes_viga(entidade)
        codigo = self._extrair_codigo_viga(entidade, textos)
        comprimento = self._calcular_comprimento_viga(grupo)
        
        dna_vector = [dimensoes.get("largura", 20), dimensoes.get("altura", 40), comprimento, len(grupo)]
        confidence = self.calcular_confidence({"codigo": codigo, "dimensoes": dimensoes}, entidade)
        
        return FichaFase3Viga(
            codigo=codigo or f"V{uuid.uuid4().hex[:4].upper()}",
            pavimento=pavimento,
            obra_nome=obra_nome,
            tipo="retangular",
            largura=dimensoes.get("largura", 20.0),
            altura=dimensoes.get("altura", 40.0),
            comprimento=comprimento,
            secao_transversal={"b": dimensoes.get("largura", 20), "h": dimensoes.get("altura", 40)},
            tramos=[{"comprimento": comprimento, "tipo_apoio": "fixo"}],
            armadura_positiva={"qtd_barras": 3, "diametro": 12.5},
            armadura_negativa={"qtd_barras": 2, "diametro": 10.0},
            estribos={"diametro": 5.0, "espacamento": 15.0},
            confidence=confidence,
            dna_vector=dna_vector
        )
    
    def _extrair_dimensoes_viga(self, entidade: dict) -> dict:
        dados = entidade.get("dados", {})
        largura, altura = 20.0, 40.0
        nome = dados.get("nome", "")
        match = re.search(r"(\d+)[xX/](\d+)", nome)
        if match:
            largura = float(match.group(1))
            altura = float(match.group(2))
        return {"largura": largura, "altura": altura}
    
    def _extrair_codigo_viga(self, entidade: dict, textos: List[dict]) -> str:
        dados = entidade.get("dados", {})
        nome = dados.get("nome", "")
        if nome:
            match = re.search(r"([A-Z]?\d+)", nome, re.IGNORECASE)
            if match:
                return match.group(1)
        
        texto = self._encontrar_texto_proximo(entidade, textos)
        if texto:
            match = re.search(r"([A-Z]?\d+)", texto, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""
    
    def _calcular_comprimento_viga(self, grupo: List[dict]) -> float:
        comprimento_total = 0.0
        for ent in grupo:
            dados = ent.get("dados", {})
            if "comprimento" in dados:
                comprimento_total += float(dados["comprimento"])
            elif "pontos" in dados:
                pontos = dados["pontos"]
                if len(pontos) >= 2:
                    p1, p2 = pontos[0], pontos[-1]
                    dx = p2.get("x", 0) - p1.get("x", 0)
                    dy = p2.get("y", 0) - p1.get("y", 0)
                    comprimento_total += math.sqrt(dx*dx + dy*dy)
        return comprimento_total if comprimento_total > 0 else 300.0
    
    def interpretar_lajes(self, entidades: List[dict], pavimentos: dict, textos: List[dict], obra_nome: str) -> List[FichaFase3Laje]:
        """Interpreta lajes a partir de entidades catalogadas."""
        lajes = []
        entidades_laje = self._filtrar_entidades_laje(entidades)
        
        for ent in entidades_laje:
            try:
                ficha = self._criar_ficha_laje(ent, textos, pavimentos, obra_nome)
                if ficha:
                    lajes.append(ficha)
            except Exception as e:
                logger.debug(f"Erro ao interpretar laje: {e}")
        
        return lajes
    
    def _filtrar_entidades_laje(self, entidades: List[dict]) -> List[dict]:
        laje_keywords = {"LAJE", "SLAB", "L", "LJ"}
        filtradas = []
        for ent in entidades:
            tipo = ent.get("tipo", "").upper()
            layer = ent.get("layer", "").upper()
            if tipo in ("HATCH", "REGION"):
                filtradas.append(ent)
            elif tipo in ("POLYLINE", "LWPOLYLINE"):
                if any(k in layer for k in laje_keywords):
                    filtradas.append(ent)
        return filtradas
    
    def _criar_ficha_laje(self, entidade: dict, textos: List[dict], pavimentos: dict, obra_nome: str) -> Optional[FichaFase3Laje]:
        dados = entidade.get("dados", {})
        pavimento = entidade.get("pavimento", "GERAL")
        codigo = self._extrair_codigo_laje(entidade, textos)
        outline = self._extrair_outline_laje(entidade)
        dimensoes = self._calcular_dimensoes_laje(outline)
        espessura = 10.0
        
        area = self._calcular_area_shoelace(outline)
        dna_vector = [dimensoes.get("comprimento", 300), dimensoes.get("largura", 300), area, espessura]
        confidence = self.calcular_confidence({"codigo": codigo, "outline": outline}, entidade)
        
        return FichaFase3Laje(
            codigo=codigo or f"L{uuid.uuid4().hex[:4].upper()}",
            pavimento=pavimento,
            obra_nome=obra_nome,
            tipo="macica",
            dimensoes=dimensoes,
            espessura=espessura,
            outline_segs=outline,
            nivel=0.0,
            armadura={"tipo": "CA-50", "diametro": 10.0, "espacamento": 15.0, "direcao": "bidirecional"},
            confidence=confidence,
            dna_vector=dna_vector
        )
    
    def _extrair_codigo_laje(self, entidade: dict, textos: List[dict]) -> str:
        dados = entidade.get("dados", {})
        nome = dados.get("nome", "")
        if nome:
            match = re.search(r"([A-Z]?\d+)", nome, re.IGNORECASE)
            if match:
                return match.group(1)
        
        texto = self._encontrar_texto_proximo(entidade, textos)
        if texto:
            match = re.search(r"([A-Z]?\d+)", texto, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""
    
    def _extrair_outline_laje(self, entidade: dict) -> List[dict]:
        dados = entidade.get("dados", {})
        if "pontos" in dados:
            return dados["pontos"]
        if "vertices" in dados:
            return dados["vertices"]
        return [{"x": 0, "y": 0}, {"x": 300, "y": 0}, {"x": 300, "y": 300}, {"x": 0, "y": 300}]
    
    def _calcular_dimensoes_laje(self, outline: List[dict]) -> dict:
        if not outline:
            return {"comprimento": 300, "largura": 300}
        xs = [p.get("x", 0) for p in outline]
        ys = [p.get("y", 0) for p in outline]
        return {"comprimento": max(xs) - min(xs), "largura": max(ys) - min(ys)}
    
    def _calcular_area_shoelace(self, outline: List[dict]) -> float:
        if not outline or len(outline) < 3:
            return 0.0
        n = len(outline)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += outline[i].get("x", 0) * outline[j].get("y", 0)
            area -= outline[j].get("x", 0) * outline[i].get("y", 0)
        return abs(area) / 2
    
    def _encontrar_texto_proximo(self, entidade: dict, textos: List[dict]) -> str:
        ent_x, ent_y = entidade.get("posicao_x"), entidade.get("posicao_y")
        if ent_x is None or ent_y is None or not textos:
            return ""
        
        texto_mais_proximo = None
        menor_distancia = self.DISTANCIA_MAXIMA_TEXTO
        
        for texto in textos:
            txt_x, txt_y = texto.get("posicao_x"), texto.get("posicao_y")
            if txt_x is None or txt_y is None:
                continue
            dx = ent_x - txt_x
            dy = ent_y - txt_y
            distancia = math.sqrt(dx*dx + dy*dy)
            if distancia < menor_distancia:
                menor_distancia = distancia
                texto_mais_proximo = texto
        
        return texto_mais_proximo.get("conteudo", "") if texto_mais_proximo else ""
    
    def _extrair_numero_pavimento(self, pavimento: str) -> int:
        pavimento = pavimento.upper()
        if "TERREO" in pavimento:
            return 0
        if "SUBSOLO" in pavimento:
            match = re.search(r"(\d+)", pavimento)
            return -int(match.group(1)) if match else -1
        match = re.search(r"(\d+)", pavimento)
        return int(match.group(1)) if match else 0
    
    def calcular_confidence(self, ficha: dict, entidade: dict) -> float:
        """Calcula confidence score baseado em completude, geometria, textos e consistência."""
        confidence = 0.0
        
        campos_necessarios = ["nome", "codigo", "dimensoes"]
        campos_preenchidos = sum(1 for c in campos_necessarios if ficha.get(c))
        confidence += (campos_preenchidos / len(campos_necessarios)) * 0.4
        
        dados = entidade.get("dados", {})
        if "pontos" in dados or "vertices" in dados:
            confidence += 0.3
        elif "comprimento" in dados:
            confidence += 0.2
        
        if entidade.get("nome_associado") or ficha.get("nome"):
            confidence += 0.2
        
        dimensoes = ficha.get("dimensoes", {})
        if dimensoes:
            larg = dimensoes.get("largura", 0)
            comp = dimensoes.get("comprimento", 0)
            if 10 <= larg <= 100 and 10 <= comp <= 100:
                confidence += 0.1
        
        return min(confidence, 1.0)
    
    def gerar_dna_vector(self, entidade: dict, tipo: str) -> List[float]:
        """Gera DNA vector para entidade."""
        dados = entidade.get("dados", {})
        
        if tipo == "pilar":
            dim = self._extrair_dimensoes_pilar(entidade)
            larg = dim.get("largura", 30)
            alt = dim.get("comprimento", 30)
            return [larg, alt, larg * alt, 2 * (larg + alt)]
        elif tipo == "viga":
            dim = self._extrair_dimensoes_viga(entidade)
            comp = self._calcular_comprimento_viga([entidade])
            return [dim.get("largura", 20), dim.get("altura", 40), comp, 1]
        elif tipo == "laje":
            outline = self._extrair_outline_laje(entidade)
            dim = self._calcular_dimensoes_laje(outline)
            area = self._calcular_area_shoelace(outline)
            return [dim.get("comprimento", 300), dim.get("largura", 300), area, 10]
        return []
    
    def _aplicar_transformacoes(self, resultado: InterpretacaoResultado):
        """Aplica TransformationEngine para melhorar accuracy."""
        if not self.transform_engine:
            return
        
        for pilar in resultado.pilares:
            if pilar.confidence < self.CONFIDENCE_ALTA:
                self._aplicar_regra_pilar(pilar)
        
        for viga in resultado.vigas:
            if viga.confidence < self.CONFIDENCE_ALTA:
                self._aplicar_regra_viga(viga)
        
        for laje in resultado.lajes:
            if laje.confidence < self.CONFIDENCE_ALTA:
                self._aplicar_regra_laje(laje)
    
    def _aplicar_regra_pilar(self, pilar: FichaFase3Pilar):
        if not self.transform_engine:
            return
        predicted = self.transform_engine.apply_rule("Pilar_name", pilar.dna_vector)
        if predicted:
            pilar.id = predicted
            pilar.confidence = min(pilar.confidence + 0.1, 1.0)
    
    def _aplicar_regra_viga(self, viga: FichaFase3Viga):
        if not self.transform_engine:
            return
        predicted = self.transform_engine.apply_rule("Viga_name", viga.dna_vector)
        if predicted:
            viga.codigo = predicted
            viga.confidence = min(viga.confidence + 0.1, 1.0)
    
    def _aplicar_regra_laje(self, laje: FichaFase3Laje):
        if not self.transform_engine:
            return
        predicted = self.transform_engine.apply_rule("Laje_name", laje.dna_vector)
        if predicted:
            laje.codigo = predicted
            laje.confidence = min(laje.confidence + 0.1, 1.0)
    
    def salvar_fichas(self, resultado: InterpretacaoResultado, obra_id: str) -> int:
        """Salva fichas na tabela fase3_fichas do SQLite."""
        cursor = self.conn.cursor()
        total_salvas = 0
        
        try:
            for pilar in resultado.pilares:
                ficha_id = f"{obra_id}_pilar_{pilar.numero}"
                cursor.execute("""
                    INSERT OR REPLACE INTO fase3_fichas (id, obra_id, pavimento, tipo, codigo, dados_json, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ficha_id, obra_id, pilar.pavimento, "pilar", pilar.id, json.dumps(pilar.to_dict()), pilar.confidence))
                total_salvas += 1
            
            for viga in resultado.vigas:
                ficha_id = f"{obra_id}_viga_{viga.codigo}"
                cursor.execute("""
                    INSERT OR REPLACE INTO fase3_fichas (id, obra_id, pavimento, tipo, codigo, dados_json, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ficha_id, obra_id, viga.pavimento, "viga", viga.codigo, json.dumps(viga.to_dict()), viga.confidence))
                total_salvas += 1
            
            for laje in resultado.lajes:
                ficha_id = f"{obra_id}_laje_{laje.codigo}"
                cursor.execute("""
                    INSERT OR REPLACE INTO fase3_fichas (id, obra_id, pavimento, tipo, codigo, dados_json, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ficha_id, obra_id, laje.pavimento, "laje", laje.codigo, json.dumps(laje.to_dict()), laje.confidence))
                total_salvas += 1
            
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Erro ao salvar fichas: {e}")
            raise
        
        return total_salvas


def carregar_fichas_obra(db_path: str, obra_id: str, tipo: Optional[str] = None) -> List[dict]:
    """Carrega fichas de uma obra do SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if tipo:
        cursor.execute("SELECT * FROM fase3_fichas WHERE obra_id = ? AND tipo = ?", (obra_id, tipo))
    else:
        cursor.execute("SELECT * FROM fase3_fichas WHERE obra_id = ?", (obra_id,))
    
    fichas = []
    for row in cursor.fetchall():
        ficha = dict(row)
        try:
            ficha["dados"] = json.loads(ficha["dados_json"]) if ficha["dados_json"] else {}
        except:
            ficha["dados"] = {}
        del ficha["dados_json"]
        fichas.append(ficha)
    
    conn.close()
    return fichas


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fase 3 - Interpretação e Extração")
    parser.add_argument("--obra", type=str, required=True, help="ID ou nome da obra")
    parser.add_argument("--db", type=str, default="project_data.vision", help="Banco de dados")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("=" * 70)
    print("FASE 3 - INTERPRETAÇÃO E EXTRAÇÃO")
    print("=" * 70)
    
    interpretacao = Fase3Interpretacao(args.db)
    try:
        resultado = interpretacao.executar(args.obra)
        print(f"\nResultado:")
        print(f"  Pilares: {len(resultado.pilares)}")
        print(f"  Vigas: {len(resultado.vigas)}")
        print(f"  Lajes: {len(resultado.lajes)}")
        print(f"  Total fichas: {resultado.total_fichas}")
        print(f"  Accuracy média: {resultado.accuracy_media:.2%}")
        
        if resultado.erros:
            print(f"\nErros:")
            for erro in resultado.erros:
                print(f"  - {erro}")
    finally:
        interpretacao.close()
