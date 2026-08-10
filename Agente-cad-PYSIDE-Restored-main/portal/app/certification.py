"""Rotulo de certificacao por classe (certificado/beta) — R9 / DP-13.

O portal NAO decide certificacao; so LE o estado atual do funil do dono e exibe.
Fonte read-only: docs/STATUS.md (gerado por scripts/arete/gerar_status.py a partir
de relatorios Arete + GOLDEN + triagem + DB). Em conflito, STATUS.md vence (e' o dado).

[ASSUMPTION] STATUS.md nao imprime a palavra 'certificado'/'beta' literalmente; ele
publica, por classe+pav, a coluna "Arete %" e um "Alerta" ("FAIL aberto"). Regra
derivada, documentada e conservadora (nunca superestima certificacao):
    Arete% == 100.0 e sem "FAIL aberto"  ->  'certificado'
    qualquer outro caso                  ->  'beta'
Se STATUS.md nao existir ou a classe nao aparecer, retorna 'beta' (fail-safe: o
usuario ve o rotulo mais cauteloso, nunca 'certificado' por engano). Um mapa
PORTAL_CERT_OVERRIDE (env, "PL:certificado,FV:beta") permite o dono forcar o rotulo
sem esperar nova geracao do STATUS. Se um dia o STATUS passar a emitir o selo real,
trocar apenas o parser aqui — o resto do portal so consome classificar_certificacao().

Mapeamento de nomes de classe: a UI/assemble_n5 usa PL/LV/FV/LJ; o STATUS usa
PIL/LV/FV/LAJ. _norm_classe unifica para o vocabulario de assemble_n5.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

StatusCert = Literal["certificado", "beta"]

# STATUS (Arete) -> vocabulario de assemble_n5 (repository.CLASSES_N5)
_ALIAS = {
    "PIL": "PL",
    "PL": "PL",
    "LV": "LV",
    "FV": "FV",
    "LAJ": "LJ",
    "LJ": "LJ",
}

# Tabela "Ultima rodada Arete por classe" do STATUS.md.
#
# [2026-07-30] Passou a ser lida por NOME DE CABECALHO, nao por posicao. O parser
# anterior contava colunas fixas e quebrava a cada coluna nova no gerador — foi o que
# aconteceu quando "Regressao" entrou entre "Golden selado" e "Alerta". Por nome, o
# gerador pode adicionar/reordenar colunas sem derrubar o rotulo de certificacao (que
# gateia a liberacao do N5). Colunas desconhecidas sao ignoradas; ausentes viram None.
_CELULA_ARETE = re.compile(r"([\d.]+)\s*%")


def _linhas_tabela(texto: str) -> list[dict[str, str]]:
    """Extrai as linhas da tabela como dicts {cabecalho: celula}.

    Aceita qualquer conjunto de colunas desde que existam 'Classe' e 'Arete'.
    Suporta o layout legado (sem 'Regressao') e o atual, sem ramificar.
    """
    cabecalho: list[str] | None = None
    linhas: list[dict[str, str]] = []
    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha.startswith("|"):
            cabecalho = None  # tabela terminou; a proxima recomeca o cabecalho
            continue
        celulas = [c.strip() for c in linha.strip("|").split("|")]
        if cabecalho is None:
            baixo = [c.lower() for c in celulas]
            if any(c.startswith("classe") for c in baixo) and any("arete" in c for c in baixo):
                cabecalho = baixo
            continue
        if all(set(c) <= set("-: ") for c in celulas):
            continue  # separador |---|---|
        linhas.append(dict(zip(cabecalho, celulas)))
    return linhas


def _coluna(linha: dict[str, str], *nomes: str) -> str | None:
    """Primeira coluna cujo cabecalho comeca por um dos nomes dados."""
    for nome in nomes:
        for chave, valor in linha.items():
            if chave.startswith(nome):
                return valor
    return None


def _norm_classe(classe: str) -> str | None:
    return _ALIAS.get((classe or "").strip().upper())


def _parse_overrides() -> dict[str, StatusCert]:
    """PORTAL_CERT_OVERRIDE="PL:certificado,FV:beta" -> {'PL':'certificado',...}."""
    raw = os.environ.get("PORTAL_CERT_OVERRIDE", "").strip()
    out: dict[str, StatusCert] = {}
    if not raw:
        return out
    for par in raw.split(","):
        if ":" not in par:
            continue
        cls, val = par.split(":", 1)
        cls = _norm_classe(cls)
        val = val.strip().lower()
        if cls and val in ("certificado", "beta"):
            out[cls] = val  # type: ignore[assignment]
    return out


def carregar_mapa_certificacao(status_md_path: str | Path) -> dict[str, StatusCert]:
    """Le STATUS.md (read-only) e devolve {classe_norm: 'certificado'|'beta'}.

    Uma classe e' 'certificado' apenas se TODAS as suas linhas (pavimentos) estao a
    100% sem FAIL aberto. Basta um pavimento em beta para a classe inteira ser beta —
    regra conservadora (nunca liberar rotulo forte com um pav em treino).
    """
    mapa: dict[str, StatusCert] = {}
    path = Path(status_md_path)
    if not path.exists():
        return _parse_overrides()  # sem fonte -> so overrides; resto vira beta no getter

    try:
        texto = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _parse_overrides()

    for linha in _linhas_tabela(texto):
        classe = _norm_classe(_coluna(linha, "classe") or "")
        if classe is None:
            continue
        bruto_arete = _coluna(linha, "arete") or ""
        casado = _CELULA_ARETE.search(bruto_arete)
        try:
            arete = float(casado.group(1)) if casado else 0.0
        except ValueError:
            arete = 0.0
        tem_fail = "fail" in (_coluna(linha, "alerta") or "").lower()
        # Regressao (item selado que reprovou) rebaixa para beta. Na pratica e'
        # redundante — regressao e' subconjunto dos FAILs, logo arete < 100 — mas
        # mantem o rotulo correto se o gerador mudar. Conservador por desenho.
        # Ausente (layout legado) nao rebaixa: so um numero > 0 rebaixa.
        bruto_regressao = (_coluna(linha, "regress") or "").strip()
        tem_regressao = bruto_regressao.isdigit() and int(bruto_regressao) > 0
        cert = "certificado" if (arete >= 100.0 and not tem_fail and not tem_regressao) else "beta"
        # rebaixa a classe inteira se qualquer pav for beta
        if mapa.get(classe) == "beta" or cert == "beta":
            mapa[classe] = "beta"
        else:
            mapa[classe] = "certificado"

    mapa.update(_parse_overrides())  # override do dono tem a ultima palavra
    return mapa


def classificar_certificacao(status_md_path: str | Path, classe: str) -> StatusCert:
    """Rotulo de UMA classe. Fail-safe: desconhecida/ausente -> 'beta' (cauteloso, R9)."""
    norm = _norm_classe(classe)
    if norm is None:
        return "beta"
    mapa = carregar_mapa_certificacao(status_md_path)
    return mapa.get(norm, "beta")
