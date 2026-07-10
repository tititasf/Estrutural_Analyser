"""Sugestão de classe/pavimento por nome de arquivo (2026-07-06 — triagem em lote).

NUNCA confiada sem revisão humana — masterplan original: "TRIAGEM: humano
confirma/edita classificação dos documentos por pavimento". Este módulo só
PROPÕE (`classe_sugerida`/`pavimento_sugerido`); a confirmação (`*_confirmada`)
é do usuário na tela de triagem, ou promovida automaticamente só quando a
sugestão é INEQUÍVOCA (uma classe clara detectada).

Reaproveita os MESMOS padrões que o motor real já usa, em vez de inventar um
critério novo e divergente:
- Classe: mesma marcação que `src.core.recorte_motor.RecorteMotor._detect_type`
  usa (` PL `, ` LV `, ` FV `, ` LJ `) — aqui estendida para `GF` (5ª classe real
  observada nos arquivos de Obra_TREINO_1, ainda não coberta pelo RecorteMotor)
  e para nunca levantar exceção (motor real prefere falhar; aqui preferimos
  'não identificado' e deixar a triagem/humano decidir).
- Pavimento: mesma função `_floor_key` de `src.core.sa_project_source` (usada
  pelo próprio `select_sa_project` para casar pavimento) — reusar garante que
  a sugestão do portal fala a MESMA língua que o motor vai usar depois.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# classe -> marcadores (maiúsculo, com espaços/hífens ao redor — igual RecorteMotor)
_MARCADORES_CLASSE = {
    "PIL": ("- PL -", " PL "),
    "LV": ("- LV -", " LV "),
    "FV": ("- FV -", " FV "),
    "LAJ": ("- LJ -", " LJ "),
    "GF": ("- GF -", " GF "),
}


def sugerir_classe(nome_arquivo: str) -> Optional[str]:
    """Retorna 'PIL'|'LV'|'FV'|'LAJ'|'GF' ou None (não identificado — nunca lança)."""
    fn = f" {nome_arquivo.upper()} "
    for classe, marcadores in _MARCADORES_CLASSE.items():
        if any(m in fn for m in marcadores):
            return classe
    return None


def sugerir_pavimento(nome_arquivo: str) -> Optional[str]:
    """Best-effort — extrai um rótulo de pavimento legível do nome do arquivo.

    Usa a MESMA normalização de `sa_project_source._floor_key` (numérico N_PAV,
    ou rótulos especiais TERREO/COBERTURA/ATICO/SUBSOLO/GARAGEM/FUNDACAO/TIPO)
    para que a sugestão já fale a língua que o motor vai exigir depois. Casos
    compostos (ex.: "TIPO - 3° AO 12° PAV", "COBERTURA - DECK") não têm um único
    rótulo certo — devolve o melhor palpite; a triagem SEMPRE expõe pra revisão.
    """
    from src.core.sa_project_source import _floor_key  # reuso deliberado, ver docstring

    texto = nome_arquivo.upper()
    # tenta pedaço a pedaço (separado por ' - ' ou '.') pra achar o token de pavimento
    pedacos = re.split(r"\s*-\s*|\.\s*", texto)
    for pedaco in pedacos:
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        # [ACHADO 2026-07-06] arquivos reais usam "13° PAV" (grau + espaço) — o
        # regex de _floor_key exige o dígito colado em "PAV" (só aceita "_"
        # opcional no meio, não espaço nem "°"). Sem normalizar, "13° PAV" cai
        # no fallback TEXT (vira "13PAV" como texto puro, não NUMBER,13) e a
        # sugestão de pavimento nunca aparecia para NENHUM arquivo do padrão
        # real da Obra_TREINO_1 — só pros nomes "TMC-...-13P-..." (sem grau).
        # Acentos ("TÉRREO") também quebram o casamento de "TER" — removidos
        # aqui (só na SUGESTÃO local; _floor_key em si não é alterado).
        sem_acento = unicodedata.normalize("NFKD", pedaco).encode("ascii", "ignore").decode()
        pedaco_normalizado = sem_acento.replace("°", "").replace(" ", "")
        chave = _floor_key(pedaco_normalizado)
        if chave[0] == "NUMBER":
            return f"{chave[1]}_PAV"
        if chave[0] == "SPECIAL":
            return chave[1]
    return None


_MARCADORES_DETALHE = ("DETALHE", "DET ", "-DET", "_DET", "CONVENCAO", "CONVENÇÃO")


def sugerir_tipo_documento(nome_arquivo: str) -> str:
    """Eixo NOVO (2026-07-07), diferente de classe estrutural — 'que TIPO de
    documento é este': Bruto (planta a recortar), Detalhe (desenho de detalhe/
    convenção) ou PDF (material de referência, fora do pipeline DXF).

    Best-effort só como as demais sugestões daqui — nunca força, a triagem
    sempre revisa. Extensão .pdf é sinal forte e inequívoco; para .dwg/.dxf,
    o padrão real (Obra_TREINO_1) é a maioria ser bruto — só vira 'Detalhe'
    se o nome tiver marcador explícito.
    """
    nome_upper = nome_arquivo.upper()
    if nome_upper.endswith(".PDF"):
        return "PDF"
    if any(m in f" {nome_upper} " for m in _MARCADORES_DETALHE):
        return "Detalhe"
    return "Bruto"


def classificar_arquivo(nome_arquivo: str) -> dict:
    """Sugestão completa + veredito de confiança para a triagem em lote.

    'classificado' (auto-aceito): classe E pavimento identificados com clareza.
    'revisar': falta classe OU pavimento — humano decide antes de prosseguir.
    PDF nunca precisa de classe estrutural (não entra no pipeline DXF) — só
    pavimento é relevante pra ele, então não força 'revisar' por falta de classe.
    """
    tipo = sugerir_tipo_documento(nome_arquivo)
    pavimento = sugerir_pavimento(nome_arquivo)
    if tipo == "PDF":
        status = "classificado" if pavimento else "revisar"
        return {
            "classe_sugerida": None, "pavimento_sugerido": pavimento,
            "tipo_documento_sugerido": tipo, "status": status,
        }
    classe = sugerir_classe(nome_arquivo)
    status = "classificado" if (classe and pavimento) else "revisar"
    return {
        "classe_sugerida": classe,
        "pavimento_sugerido": pavimento,
        "tipo_documento_sugerido": tipo,
        "status": status,
    }
