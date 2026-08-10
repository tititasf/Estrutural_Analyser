"""Identidade canônica de obra/pavimento — ponto único de normalização.

Motivação (auditoria 2026-07-30, `docs/MASTERPLAN-CONSOLIDACAO-ENTREGA.md` §2.3):
o mesmo pavimento aparece com grafias diferentes conforme a origem —

    disco : "ALIMONTI - PARAISO - 13° PAV.- FV - R00"
    DB    : "13_PAV"

Cada caminho do sistema improvisava sua própria conversão (ou nenhuma), e o
resultado é a família de bugs "falha de vínculo": o recorte não acha a ficha, o
gate lê zeros e reporta "campo obrigatório ausente" — indistinguível, no
relatório, de erro do motor.

Este módulo NÃO escreve no banco e NÃO decide identidade de obra; ele só
converte texto para a forma canônica. A reconciliação das três chaves de obra
(`project_id`, `obra_id`, `obra_name`) é problema separado — ver
`scripts/arete/qa_identity_integrity.py` para o diagnóstico.
"""

from __future__ import annotations

import re
import unicodedata

# Formas canônicas observadas em reverse_eng_fichas.pavimento (2026-07-30).
COBERTURA = "COBERTURA"
TERREO = "TERREO"
FUNDACAO = "FUNDACAO"
LOCACAO = "LOCACAO"
ATICO = "ATICO"
TIPO = "TIPO"

# Rótulos nomeados já canônicos (portal / prancha). Match EXATO após _limpar.
_PAVIMENTOS_NOMEADOS = {
    "COBERTURA": COBERTURA,
    "TERREO": TERREO,
    "FUNDACAO": FUNDACAO,
    "LOCACAO": LOCACAO,
    "ATICO": ATICO,
    "TIPO": TIPO,
}

# Depois de `_limpar`, tudo que separa o número de "PAV" virou espaço — não há
# mais ordinal, underscore nem mojibake para tratar aqui.
_RE_PAV = re.compile(r"(\d{1,2})\s*(?:PAV|PAVIMENTO)\b")
# "TIPO - 3° AO 12° PAV." — pavimento-tipo que cobre um intervalo.
_RE_INTERVALO = re.compile(r"(\d{1,2})\s*AO?\s*(\d{1,2})\s*(?:PAV|PAVIMENTO)\b")
# "1° SUBSOLO" — e o erro de digitacao "1° SUBOLO", que existe gravado em
# recorte_path da obra S.DIAMOND. Nenhuma obra com subsolo tem ficha ainda, entao
# esta forma canonica e' nova; existe para o item nao morrer como None quando a
# obra entrar. Se o banco vier a gravar outra grafia, ELA vira a canonica aqui.
_RE_SUBSOLO = re.compile(r"(\d{1,2})\s*SUB\s?S?OLO\b")

# Ordinais e o caractere de substituição do mojibake. Tratados ANTES do NFKD
# porque 'º' (U+00BA) decompõe para a LETRA 'o' — vira "13O PAV" e deixa de casar.
_RE_ORDINAL = re.compile("[ºª°�]")


def _sem_acento(texto: str) -> str:
    """Remove acentos preservando o resto. 'TÉRREO' -> 'TERREO'."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _limpar(texto: str) -> str:
    """Reduz qualquer grafia a MAIÚSCULAS, dígitos e espaço simples.

    Faz o separador entre número e "PAV" ser sempre espaço, seja ele ordinal
    ('13° PAV'), underscore da forma canônica ('13_PAV'), mojibake ('13� PAV')
    ou nada ('13PAV'). Sem isto a própria forma canônica não passava pelo
    normalizador — '_' é caractere de palavra e quebrava o casamento.
    """
    sem_ordinal = _RE_ORDINAL.sub(" ", str(texto))
    ascii_maiusculo = _sem_acento(sem_ordinal).upper()
    apenas_alfanum = re.sub(r"[^0-9A-Z]+", " ", ascii_maiusculo)
    return re.sub(r"\s+", " ", apenas_alfanum).strip()


def normalizar_pavimento(texto: str | None) -> str | None:
    """Converte qualquer grafia de pavimento para a forma canônica do banco.

    Devolve ``None`` quando não reconhece — nunca chuta. Chutar aqui produz
    vínculo silenciosamente errado, que é pior do que não vincular.

    >>> normalizar_pavimento("ALIMONTI - PARAISO - 13° PAV.- FV - R00")
    '13_PAV'
    >>> normalizar_pavimento("ALIMONTI - PARAISO - TÉRREO - PL - R00")
    'TERREO'
    >>> normalizar_pavimento("13_PAV")
    '13_PAV'
    >>> normalizar_pavimento("planta sem pavimento") is None
    True
    """
    if not texto:
        return None
    limpo = _limpar(texto)

    # COBERTURA vem com sufixos ("COBERTURA - DECK", "COBERTURA E DECK").
    if "COBERTURA" in limpo:
        return COBERTURA
    if "TERREO" in limpo:
        return TERREO

    subsolo = _RE_SUBSOLO.search(limpo)
    if subsolo:
        return f"{int(subsolo.group(1))}_SUBSOLO"

    # Intervalo ANTES do caso simples: "3 AO 12 PAV" tem de virar 12_PAV, não
    # 3_PAV. O banco registra o pavimento-tipo pelo topo do intervalo (existe
    # 12_PAV; não existem 3_PAV..11_PAV).
    intervalo = _RE_INTERVALO.search(limpo)
    if intervalo:
        return f"{int(intervalo.group(2))}_PAV"

    simples = _RE_PAV.search(limpo)
    if simples:
        return f"{int(simples.group(1))}_PAV"

    # Rótulos canônicos do portal / código de prancha (pavimento_de_codigo_prancha
    # devolve FUNDACAO, LOCACAO, ATICO, TIPO). Sem isto, o viewer fazia
    # `normalizar_pavimento("FUNDACAO") is None` e respondia 409 mesmo com
    # torre limpa no disco (achado F12 2026-07-31).
    # Só match EXATO no texto limpo — "TIPO - 3 AO 12 PAV" já caiu no intervalo
    # acima e vira 12_PAV; não deve virar TIPO.
    if limpo in _PAVIMENTOS_NOMEADOS:
        return _PAVIMENTOS_NOMEADOS[limpo]
    return None


# ── Códigos de prancha ───────────────────────────────────────────────────────
# Nome de arquivo de projeto usa sigla, não prosa:
#   TMC-EST-PE-6000-13P-R03   -> 13_PAV
#   TMC-EST-EX-3000-1PV-R00   -> 1_PAV
#   TMC-EST-PE-8000-COB-R03   -> COBERTURA
#   TMC-EST-EX-2000-TER-R01   -> TERREO
# Vocabulário separado de `normalizar_pavimento` de propósito: aquele está
# validado contra os 806 recortes reais e não deve mudar de comportamento por
# causa disto. Aqui a entrada é nome de arquivo, não caminho de recorte.
_RE_CODIGO_PAV = re.compile(r"\b(\d{1,2})PV?\b")
_CODIGOS_NOMEADOS = {
    "COB": COBERTURA,
    "TER": TERREO,
    "TERREO": TERREO,
    "SUB": "1_SUBSOLO",
    "FUN": "FUNDACAO",
    "LOC": "LOCACAO",
    "ATC": "ATICO",
    "TIP": "TIPO",
}


def pavimento_de_codigo_prancha(nome: str | None) -> str | None:
    """Pavimento a partir do CÓDIGO no nome do arquivo de prancha.

    Devolve ``None`` quando não reconhece — mesma regra de sempre: mostrar o
    pavimento errado é pior do que não mostrar nenhum.

    >>> pavimento_de_codigo_prancha("TMC-EST-PE-6000-13P-R03")
    '13_PAV'
    >>> pavimento_de_codigo_prancha("TMC-EST-PE-8000-COB-R03_R2018_ASCII_ODA")
    'COBERTURA'
    >>> pavimento_de_codigo_prancha("TMC-EST-EX-0000-LOC-R03")
    'LOCACAO'
    """
    if not nome:
        return None
    limpo = _limpar(nome)
    # A prosa vence quando existe ("13 PAV" num nome de arquivo é inequívoco).
    direto = normalizar_pavimento(nome)
    if direto:
        return direto
    codigo = _RE_CODIGO_PAV.search(limpo)
    if codigo:
        return f"{int(codigo.group(1))}_PAV"
    for token in limpo.split():
        if token in _CODIGOS_NOMEADOS:
            return _CODIGOS_NOMEADOS[token]
    return None


def mesmo_pavimento(a: str | None, b: str | None) -> bool:
    """Compara pavimentos de origens diferentes pela forma canônica.

    Só é verdade quando ambos são reconhecidos: dois ``None`` não são "iguais",
    são "desconhecidos" — tratá-los como iguais casaria qualquer coisa com
    qualquer coisa.
    """
    na, nb = normalizar_pavimento(a), normalizar_pavimento(b)
    return na is not None and na == nb


def pavimento_de_caminho(caminho: str | None) -> str | None:
    """Pavimento a partir de um caminho de arquivo, olhando pasta a pasta.

    Prefere o segmento mais específico: percorre da folha para a raiz e devolve
    o primeiro reconhecido, porque a pasta do recorte é mais confiável do que a
    raiz da obra (que pode conter o nome de outro pavimento por acaso).
    """
    if not caminho:
        return None
    partes = [p for p in str(caminho).replace("\\", "/").split("/") if p]
    for parte in reversed(partes):
        achado = normalizar_pavimento(parte)
        if achado:
            return achado
    return None
