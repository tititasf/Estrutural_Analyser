"""
Schema e validação das fichas de vigas para o pipeline CAD-ANALYZER.

Fase 3 → Fase 4 → Robô (Robo_Laterais_de_Vigas / Robo_Fundos_de_Vigas)
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime
import json


@dataclass
class FichaFase3Viga:
    """Ficha preenchida pela interpretação semântica (Fase 3) para VIGAS."""
    # Identificação
    codigo: str
    pavimento: str
    obra_nome: str
    
    # Tipo e geometria
    tipo: str
    largura: float
    altura: float
    comprimento: float
    
    # Seção transversal
    secao_transversal: dict
    
    # Tramos (vanos)
    tramos: List[dict]
    
    # Armadura
    armadura_positiva: dict
    armadura_negativa: dict
    
    # Estribos
    estribos: dict
    
    # Garfos (se existir)
    garfos: Optional[dict] = None
    
    # Metadados
    confidence: float = 0.0
    dna_vector: List[float] = field(default_factory=list)
    data_extracao: datetime = field(default_factory=datetime.now)
    revisado: bool = False
    
    def validate(self) -> List[str]:
        """Retorna lista de erros de validação. Lista vazia = válido."""
        erros = []
        if not self.codigo:
            erros.append("código vazio")
        if not self.pavimento:
            erros.append("pavimento vazio")
        if not self.obra_nome:
            erros.append("nome da obra vazio")
        tipos_validos = ["retangular", "L", "T"]
        if self.tipo not in tipos_validos:
            erros.append(f"tipo inválido '{self.tipo}'. Válidos: {tipos_validos}")
        if self.largura < 12:
            erros.append(f"largura inválida: {self.largura}cm (mínimo 12cm)")
        if self.altura < 25:
            erros.append(f"altura inválida: {self.altura}cm (mínimo 25cm)")
        if self.comprimento <= 0:
            erros.append(f"comprimento inválido: {self.comprimento}")
        if not (0.0 <= self.confidence <= 1.0):
            erros.append(f"confidence inválida: {self.confidence}")
        if not self.tramos:
            erros.append("viga deve ter pelo menos 1 tramo")
        return erros
    
    def to_dict(self) -> dict:
        """Serializa a ficha para dict."""
        d = asdict(self)
        if isinstance(d.get("data_extracao"), datetime):
            d["data_extracao"] = d["data_extracao"].isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "FichaFase3Viga":
        """Factory method para criar FichaFase3Viga a partir de dict."""
        if "data_extracao" in data and isinstance(data["data_extracao"], str):
            try:
                data["data_extracao"] = datetime.fromisoformat(data["data_extracao"])
            except ValueError:
                data["data_extracao"] = datetime.now()
        campos_validos = {"codigo", "pavimento", "obra_nome", "tipo", "largura", "altura",
            "comprimento", "secao_transversal", "tramos", "armadura_positiva",
            "armadura_negativa", "estribos", "garfos", "confidence", "dna_vector",
            "data_extracao", "revisado"}
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
    
    def area_secao(self) -> float:
        """Calcula área da seção transversal em cm²."""
        return self.largura * self.altura
    
    def volume_concreto(self) -> float:
        """Calcula volume de concreto em m³."""
        return (self.area_secao() * self.comprimento) / 1_000_000


def ficha_fase3_to_robo_viga_dict(ficha: FichaFase3Viga) -> dict:
    """Converte FichaFase3Viga para formato do robô de vigas."""
    tipo_secao = ficha.tipo
    secao_robo = {"retangular": "RET", "L": "L", "T": "T"}.get(tipo_secao, "RET")
    arm_pos = ficha.armadura_positiva or {}
    arm_neg = ficha.armadura_negativa or {}
    estribos = ficha.estribos or {}
    dados = {
        "codigo": ficha.codigo,
        "pavimento": ficha.pavimento,
        "tipo": secao_robo,
        "dimensoes": {"b": ficha.largura, "h": ficha.altura},
        "comprimento": ficha.comprimento,
        "armadura": {
            "positiva": {"qtd_barras": arm_pos.get("qtd_barras", 0), "diametro": arm_pos.get("diametro", 0)},
            "negativa": {"qtd_barras": arm_neg.get("qtd_barras", 0), "diametro": arm_neg.get("diametro", 0)},
        },
        "estribos": {"diametro": estribos.get("diametro", 0), "espacamento": estribos.get("espacamento", 0)},
        "tramos": ficha.tramos,
        "garfos": ficha.garfos,
        "secao_transversal": ficha.secao_transversal,
    }
    return {"dados": dados}


def fichas_to_vigas_salvas(fichas: List[FichaFase3Viga]) -> dict:
    """Converte lista de fichas para formato vigas_salvas.json."""
    resultado = {}
    for ficha in fichas:
        chave = f"{ficha.codigo}_{ficha.pavimento}"
        resultado[chave] = ficha_fase3_to_robo_viga_dict(ficha)
    return resultado


def fichas_to_tramos_salvos(fichas: List[FichaFase3Viga]) -> dict:
    """Converte lista de fichas para formato tramos_salvos.json."""
    resultado = {}
    for ficha in fichas:
        for i, tramo in enumerate(ficha.tramos, 1):
            chave = f"{ficha.codigo}_{ficha.pavimento}_T{i}"
            resultado[chave] = {
                "comprimento": tramo.get("comprimento", 0),
                "tipo_apoio": tramo.get("tipo_apoio", "fixo"),
                "apoio_inicio": tramo.get("apoio_inicio", "fixo"),
                "apoio_fim": tramo.get("apoio_fim", "fixo"),
            }
    return resultado


def fichas_to_pavimentos_lista(fichas: List[FichaFase3Viga]) -> List[List[str]]:
    """Extrai lista ordenada de pavimentos das fichas."""
    vistos = {}
    ordem = {"TERREO": 0, "P-1": 1, "P-2": 2, "P-3": 3, "P-4": 4}
    for ficha in fichas:
        if ficha.pavimento not in vistos:
            pav_upper = ficha.pavimento.upper().replace("-", "_")
            nivel = ordem.get(pav_upper, len(vistos))
            vistos[ficha.pavimento] = nivel
    return [[nome, str(nivel)] for nome, nivel in sorted(vistos.items(), key=lambda x: x[1])]


def salvar_fichas_json(fichas: List[FichaFase3Viga], caminho: str) -> None:
    """Salva lista de fichas fase3 em JSON."""
    dados = [f.to_dict() for f in fichas]
    with open(caminho, "w", encoding="utf-8") as fp:
        json.dump(dados, fp, ensure_ascii=False, indent=2)


def carregar_fichas_json(caminho: str) -> List[FichaFase3Viga]:
    """Carrega fichas fase3 de JSON."""
    with open(caminho, "r", encoding="utf-8") as fp:
        dados = json.load(fp)
    return [FichaFase3Viga.from_dict(d) for d in dados]
