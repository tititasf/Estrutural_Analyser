"""
Schema e validação das fichas de lajes para o pipeline CAD-ANALYZER.

Fase 3 → Fase 4 → Robô (Robo_Lajes)
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime
import json


@dataclass
class FichaFase3Laje:
    """Ficha preenchida pela interpretação semântica (Fase 3) para LAJES."""
    # Identificação
    codigo: str
    pavimento: str
    obra_nome: str
    
    # Tipo
    tipo: str  # "macica", "pre_moldada", "steel_deck"
    
    # Dimensões
    dimensoes: dict  # {comprimento, largura, espessura}
    espessura: float  # cm
    
    # Geometria
    outline_segs: List[dict]  # [{x, y}, ...] - vértices do contorno
    nivel: float  # cota em metros
    
    # Armadura
    armadura: dict  # {tipo, diametro, espacamento, direcao}
    
    # Metadados
    confidence: float = 0.0
    dna_vector: List[float] = field(default_factory=list)
    data_extracao: datetime = field(default_factory=datetime.now)
    revisado: bool = False
    
    def validate(self) -> List[str]:
        """Retorna lista de erros de validação."""
        erros = []
        if not self.codigo:
            erros.append("código vazio")
        if not self.pavimento:
            erros.append("pavimento vazio")
        if not self.obra_nome:
            erros.append("nome da obra vazio")
        
        tipos_validos = ["macica", "pre_moldada", "steel_deck"]
        if self.tipo not in tipos_validos:
            erros.append(f"tipo inválido '{self.tipo}'. Válidos: {tipos_validos}")
        
        if self.espessura < 7:
            erros.append(f"espessura inválida: {self.espessura}cm (mínimo 7cm para laje maciça)")
        
        if not self.dimensoes:
            erros.append("dimensões não informadas")
        else:
            comp = self.dimensoes.get("comprimento", 0)
            larg = self.dimensoes.get("largura", 0)
            if comp <= 0:
                erros.append(f"comprimento inválido: {comp}")
            if larg <= 0:
                erros.append(f"largura inválida: {larg}")
        
        if not (0.0 <= self.confidence <= 1.0):
            erros.append(f"confidence inválida: {self.confidence}")
        
        if not self.outline_segs:
            erros.append("outline_segs vazio - laje deve ter contorno")
        elif len(self.outline_segs) < 3:
            erros.append("outline_segs deve ter pelo menos 3 vértices")
        
        return erros
    
    def to_dict(self) -> dict:
        """Serializa a ficha para dict."""
        d = asdict(self)
        if isinstance(d.get("data_extracao"), datetime):
            d["data_extracao"] = d["data_extracao"].isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "FichaFase3Laje":
        """Factory method para criar FichaFase3Laje a partir de dict."""
        if "data_extracao" in data and isinstance(data["data_extracao"], str):
            try:
                data["data_extracao"] = datetime.fromisoformat(data["data_extracao"])
            except ValueError:
                data["data_extracao"] = datetime.now()
        campos_validos = {"codigo", "pavimento", "obra_nome", "tipo", "dimensoes", "espessura",
            "outline_segs", "nivel", "armadura", "confidence", "dna_vector", "data_extracao", "revisado"}
        data_filtrada = {k: v for k, v in data.items() if k in campos_validos}
        return cls(**data_filtrada)
    
    def to_json(self, indent: int = 2) -> str:
        """Serializa a ficha para JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    
    def precisa_revisao(self) -> bool:
        """Retorna True se a ficha precisa de revisão humana."""
        if self.revisado:
            return False
        if self.confidence < 0.80:
            return True
        return len(self.validate()) > 0
    
    def area(self) -> float:
        """Calcula área da laje em m² usando fórmula do shoelace."""
        if not self.outline_segs or len(self.outline_segs) < 3:
            dim = self.dimensoes or {}
            comp = dim.get("comprimento", 0) / 100
            larg = dim.get("largura", 0) / 100
            return comp * larg
        
        n = len(self.outline_segs)
        area_cm2 = 0.0
        for i in range(n):
            j = (i + 1) % n
            area_cm2 += self.outline_segs[i].get("x", 0) * self.outline_segs[j].get("y", 0)
            area_cm2 -= self.outline_segs[j].get("x", 0) * self.outline_segs[i].get("y", 0)
        return abs(area_cm2) / 2 / 10000
    
    def volume_concreto(self) -> float:
        """Calcula volume de concreto em m³."""
        return self.area() * (self.espessura / 100)


def ficha_fase3_to_robo_laje_dict(ficha: FichaFase3Laje) -> dict:
    """Converte FichaFase3Laje para formato do robô de lajes."""
    tipo_laje = ficha.tipo
    tipo_robo = {"macica": "MACICA", "pre_moldada": "PRE_MOLDADA", "steel_deck": "STEEL_DECK"}.get(tipo_laje, "MACICA")
    
    armadura = ficha.armadura or {}
    dados = {
        "codigo": ficha.codigo,
        "pavimento": ficha.pavimento,
        "tipo": tipo_robo,
        "dimensoes": ficha.dimensoes,
        "espessura": ficha.espessura,
        "nivel": ficha.nivel,
        "outline": ficha.outline_segs,
        "armadura": {
            "tipo": armadura.get("tipo", "CA-50"),
            "diametro": armadura.get("diametro", 0),
            "espacamento": armadura.get("espacamento", 0),
            "direcao": armadura.get("direcao", "bidirecional"),
        },
    }
    return {"dados": dados}


def fichas_to_lajes_salvas(fichas: List[FichaFase3Laje]) -> dict:
    """Converte lista de fichas para formato lajes_salvas.json."""
    resultado = {}
    for ficha in fichas:
        chave = f"{ficha.codigo}_{ficha.pavimento}"
        resultado[chave] = ficha_fase3_to_robo_laje_dict(ficha)
    return resultado


def fichas_to_lajes_outline(fichas: List[FichaFase3Laje]) -> dict:
    """Converte lista de fichas para formato lajes_outline.json."""
    resultado = {}
    for ficha in fichas:
        chave = f"{ficha.codigo}_{ficha.pavimento}"
        resultado[chave] = {
            "outline": ficha.outline_segs,
            "nivel": ficha.nivel,
            "area_m2": ficha.area(),
        }
    return resultado


def fichas_to_pavimentos_lista(fichas: List[FichaFase3Laje]) -> List[List[str]]:
    """Extrai lista ordenada de pavimentos das fichas."""
    vistos = {}
    ordem = {"TERREO": 0, "P-1": 1, "P-2": 2, "P-3": 3, "P-4": 4}
    for ficha in fichas:
        if ficha.pavimento not in vistos:
            pav_upper = ficha.pavimento.upper().replace("-", "_")
            nivel = ordem.get(pav_upper, len(vistos))
            vistos[ficha.pavimento] = nivel
    return [[nome, str(nivel)] for nome, nivel in sorted(vistos.items(), key=lambda x: x[1])]


def salvar_fichas_json(fichas: List[FichaFase3Laje], caminho: str) -> None:
    """Salva lista de fichas fase3 em JSON."""
    dados = [f.to_dict() for f in fichas]
    with open(caminho, "w", encoding="utf-8") as fp:
        json.dump(dados, fp, ensure_ascii=False, indent=2)


def carregar_fichas_json(caminho: str) -> List[FichaFase3Laje]:
    """Carrega fichas fase3 de JSON."""
    with open(caminho, "r", encoding="utf-8") as fp:
        dados = json.load(fp)
    return [FichaFase3Laje.from_dict(d) for d in dados]
