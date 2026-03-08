"""
Schema e validação das fichas de pilares para o pipeline CAD-ANALYZER.

Fase 3 → Fase 4 → Robô (PilarAnalyzer)
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


# --------------------------------------------------------------------------
# Ficha Fase 3 — saída da interpretação semântica do DXF
# --------------------------------------------------------------------------

@dataclass
class FichaFase3Pilar:
    """Ficha preenchida pela interpretação semântica (Fase 3)."""
    # Identificação
    id: str                         # ex: "P1", "P17"
    numero: str                     # número sequencial no pavimento
    pavimento: str                  # ex: "TERREO", "1_PAVIMENTO"
    pavimento_numero: int           # índice do pavimento (0=terreo, 1=1pav...)
    obra: str                       # nome da obra

    # Seção transversal (cm)
    comprimento: float              # lado maior da seção
    largura: float                  # lado menor da seção

    # Altura e nivelamento
    altura_cm: float                # altura total do pilar (cm)
    nivel_saida_m: float            # nível do piso inferior (m)
    nivel_chegada_m: float          # nível do teto/saída (m)
    pavimento_anterior: str = ""    # nome do pavimento abaixo

    # Armadura longitudinal — parafusos (barras verticais) por trecho
    # par_1_2 = quantidade de barras no trecho piso1→piso2, etc.
    par_1_2: str = "0"
    par_2_3: str = "0"
    par_3_4: str = "0"
    par_4_5: str = "0"
    par_5_6: str = "0"
    par_6_7: str = "0"
    par_7_8: str = "0"
    par_8_9: str = "0"

    # Armadura transversal — grades (estribos)
    grade_1: str = ""               # diâmetro da barra (mm)
    distancia_1: str = ""           # espaçamento entre grades (cm)
    grade_2: str = ""
    distancia_2: str = ""
    grade_3: str = ""

    # Pilar especial (L, T, U, etc.)
    pilar_especial: bool = False
    tipo_pilar_especial: str = "L"

    # Metadados de confiança (uso interno — não vai para o robô)
    confidence: float = 0.0
    revisado_por_humano: bool = False

    def to_dict(self):
        return asdict(self)

    def validar(self) -> list[str]:
        """Retorna lista de erros de validação. Vazio = válido."""
        erros = []
        if not self.id:
            erros.append("id vazio")
        if self.comprimento <= 0:
            erros.append(f"comprimento inválido: {self.comprimento}")
        if self.largura <= 0:
            erros.append(f"largura inválida: {self.largura}")
        if self.altura_cm <= 0:
            erros.append(f"altura inválida: {self.altura_cm}")
        if self.comprimento < self.largura:
            erros.append(
                f"comprimento ({self.comprimento}) < largura ({self.largura}) — "
                "convenção: comprimento é o lado maior"
            )
        return erros

    def precisa_revisao(self) -> bool:
        """True se confidence baixa ou campos críticos ausentes."""
        if self.revisado_por_humano:
            return False
        if self.confidence < 0.80:
            return True
        erros = self.validar()
        return len(erros) > 0


# --------------------------------------------------------------------------
# Ficha Fase 4 — formato nativo do robô PilarAnalyzer
# --------------------------------------------------------------------------

def ficha_fase3_to_robo_dict(ficha: FichaFase3Pilar) -> dict:
    """
    Converte FichaFase3Pilar para o formato esperado pelo robô
    (estrutura interna de obras_salvas.json / pilares_salvos.json).

    O robô usa a chave composta: f"{numero}_{pavimento}" como ID externo.
    """
    dados = {
        "numero": str(ficha.numero),
        "nome": ficha.id,
        "obra": ficha.obra,
        "comprimento": str(ficha.comprimento),
        "largura": str(ficha.largura),
        "pavimento": ficha.pavimento,
        "pavimento_numero": str(ficha.pavimento_numero),
        "pavimento_anterior": ficha.pavimento_anterior,
        "nivel_saida": str(ficha.nivel_saida_m),
        "nivel_chegada": str(ficha.nivel_chegada_m),
        "nivel_diferencial": "",
        "altura": str(ficha.altura_cm),
        "parafusos": {
            "par_1_2": ficha.par_1_2,
            "par_2_3": ficha.par_2_3,
            "par_3_4": ficha.par_3_4,
            "par_4_5": ficha.par_4_5,
            "par_5_6": ficha.par_5_6,
            "par_6_7": ficha.par_6_7,
            "par_7_8": ficha.par_7_8,
            "par_8_9": ficha.par_8_9,
        },
        "grades": {
            "grade_1": ficha.grade_1,
            "distancia_1": ficha.distancia_1,
            "grade_2": ficha.grade_2,
            "distancia_2": ficha.distancia_2,
            "grade_3": ficha.grade_3,
        },
        "pilar_especial": {
            "ativar_pilar_especial": ficha.pilar_especial,
            "tipo_pilar_especial": ficha.tipo_pilar_especial,
            "modo_calculo": "NOVA",
            "comprimentos": {"comp_1": "", "comp_2": "", "comp_3": ""},
            "larguras": {"larg_1": "", "larg_2": "", "larg_3": ""},
            "distancia": "",
            "grades": {},
            "detalhes_grades_especiais": {},
            "altura_detalhes_especiais": {},
        },
    }
    return {"dados": dados}


def fichas_to_obras_salvas(
    fichas: list[FichaFase3Pilar],
    nome_obra: str,
) -> dict:
    """
    Converte lista de fichas para o formato completo de obras_salvas.json.

    Estrutura: { nome_obra: { pavimento: { numero: { dados: {...} } } } }
    """
    obras: dict = {nome_obra: {}}
    for ficha in fichas:
        pav = ficha.pavimento
        if pav not in obras[nome_obra]:
            obras[nome_obra][pav] = {}
        obras[nome_obra][pav][str(ficha.numero)] = ficha_fase3_to_robo_dict(ficha)
    return obras


def fichas_to_pilares_salvos(fichas: list[FichaFase3Pilar]) -> dict:
    """
    Converte lista de fichas para o formato de pilares_salvos.json
    (arquivo com todos os pilares do pavimento atual carregado).

    Estrutura: { "numero_pavimento_pavnome": { "dados": {...} } }
    """
    resultado: dict = {}
    for ficha in fichas:
        chave = f"{ficha.numero}_{ficha.pavimento}"
        resultado[chave] = ficha_fase3_to_robo_dict(ficha)
    return resultado


# --------------------------------------------------------------------------
# Utilitários de persistência
# --------------------------------------------------------------------------

def salvar_fichas_json(fichas: list[FichaFase3Pilar], caminho: str) -> None:
    """Salva lista de fichas fase3 em JSON (para revisão/treinamento)."""
    dados = [f.to_dict() for f in fichas]
    with open(caminho, "w", encoding="utf-8") as fp:
        json.dump(dados, fp, ensure_ascii=False, indent=2)


def carregar_fichas_json(caminho: str) -> list[FichaFase3Pilar]:
    """Carrega fichas fase3 de JSON."""
    with open(caminho, "r", encoding="utf-8") as fp:
        dados = json.load(fp)
    fichas = []
    for d in dados:
        # Remove chaves extras que não fazem parte do dataclass
        d.pop("revisado_por_humano", None)
        fichas.append(FichaFase3Pilar(**d))
    return fichas
