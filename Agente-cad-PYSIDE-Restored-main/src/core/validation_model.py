"""Modelo de validação de campo/item [2026-07-13] — 3 origens de campo
(`humano_app`, `humano_portal`, `qa_agente`) que EMPILHAM (um campo pode ter
as 3 ao mesmo tempo), e 4 selos de item (verde/rosa/azul/laranja,
independentes — um item pode ter os 4 ao mesmo tempo).

Fonte única da verdade da lógica de cálculo — reusada por:
- `src/ui/widgets/detail_card.py` (grava `humano_app`, validação no app
  desktop, campo a campo)
- `main.py` (lê pra renderizar os selos na árvore lateral do SA)
- `scripts/arete/qa_evidence_auditor.py` (grava `qa_agente`, único capaz de
  escrever direto no dado hoje, restrito à classe LAJ)
- Sync Portal → desktop (grava `humano_portal`, Fase 2 do masterplan)

Ver `docs/CONVENCAO-SELOS-VALIDACAO.md` pra convenção completa (cores,
pesos, exemplos).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

ORIGEM_HUMANO_APP = "humano_app"
ORIGEM_HUMANO_PORTAL = "humano_portal"
ORIGEM_QA_AGENTE = "qa_agente"

ORIGENS_VALIDAS = (ORIGEM_HUMANO_APP, ORIGEM_HUMANO_PORTAL, ORIGEM_QA_AGENTE)


def migrar_validated_fields_legado(valor_antigo) -> dict:
    """Aceita o formato antigo (`list[str]` de field_ids) ou o novo
    (`dict[field_id, list[{origem, quando}]]`) e sempre devolve o novo
    formato. Dado legado (lista simples) é tratado como validado por
    `humano_app`, sem timestamp — é a única origem que dominava de fato
    até 2026-07-13 (LAJ com `apply` do agente QA é indistinguível
    retroativamente do dado já gravado, assumido `humano_app` por ser o
    caso majoritário — decisão documentada, não um bug)."""
    if valor_antigo is None:
        return {}
    if isinstance(valor_antigo, dict):
        return valor_antigo
    if isinstance(valor_antigo, (list, set, tuple)):
        return {
            str(field_id): [{"origem": ORIGEM_HUMANO_APP, "quando": None}]
            for field_id in valor_antigo
        }
    return {}


def adicionar_validacao_campo(validated_fields, field_id: str, origem: str) -> dict:
    """Registra 1 validação de `field_id` pela `origem` informada —
    idempotente por (field_id, origem): não duplica a MESMA origem 2x,
    mas acumula origens diferentes no mesmo campo (até as 3)."""
    if origem not in ORIGENS_VALIDAS:
        raise ValueError(f"origem inválida: {origem!r} (esperado um de {ORIGENS_VALIDAS})")
    dados = migrar_validated_fields_legado(validated_fields)
    entradas = dados.setdefault(str(field_id), [])
    if not any(e.get("origem") == origem for e in entradas):
        entradas.append({"origem": origem, "quando": datetime.now(timezone.utc).isoformat()})
    return dados


def remover_validacao_campo(validated_fields, field_id: str, origem: Optional[str] = None) -> dict:
    """Remove a validação de `field_id` — se `origem` for informada,
    remove só aquela origem (o campo pode continuar validado por outra);
    senão remove todas as origens desse campo."""
    dados = migrar_validated_fields_legado(validated_fields)
    field_id = str(field_id)
    if field_id not in dados:
        return dados
    if origem is None:
        dados.pop(field_id, None)
    else:
        dados[field_id] = [e for e in dados[field_id] if e.get("origem") != origem]
        if not dados[field_id]:
            dados.pop(field_id, None)
    return dados


def origens_do_campo(validated_fields, field_id: str) -> set[str]:
    """Quais origens já validaram esse campo (0 a 3)."""
    dados = migrar_validated_fields_legado(validated_fields)
    entradas = dados.get(str(field_id), [])
    return {e.get("origem") for e in entradas if e.get("origem")}


def campo_esta_validado(validated_fields, field_id: str) -> bool:
    """Qualquer origem conta como "validado" — pra lógica que só precisa
    saber presença (ex.: contar campos pendentes), não a origem específica."""
    return bool(origens_do_campo(validated_fields, field_id))


def calcular_selos_item(validated_fields, na_fields, campos_obrigatorios) -> dict:
    """Calcula os 3 selos de item que dependem de cobertura campo-a-campo
    (azul/rosa/laranja — o selo verde é independente, calculado por fora
    já que não depende de campo nenhum). Um item pode ter os 3 ao mesmo
    tempo (mais o verde = 4 no total).

    - **azul**: todo campo obrigatório tem origem `humano_app` OU está em
      `na_fields` (N/A conta como resolvido — mesma regra que já existia
      pro antigo `is_fully_validated`).
    - **rosa**: todo campo obrigatório tem origem `humano_portal` OU está
      em `na_fields`.
    - **laranja**: todo campo obrigatório tem origem `qa_agente` OU está
      em `na_fields` — isolado, igual azul/rosa, sem mistura com outras
      origens (correção do dono: "laranja seja só qa agente mesmo, pra
      ficar isolado").

    Lista vazia de `campos_obrigatorios` nunca gera selo (sem campo, não
    há o que "completar")."""
    dados = migrar_validated_fields_legado(validated_fields)
    na = set(na_fields or [])
    obrigatorios = set(campos_obrigatorios or [])

    def _cobertura(origens_aceitas: set[str]) -> bool:
        if not obrigatorios:
            return False
        for field_id in obrigatorios:
            if field_id in na:
                continue
            if not (origens_do_campo(dados, field_id) & origens_aceitas):
                return False
        return True

    return {
        "azul": _cobertura({ORIGEM_HUMANO_APP}),
        "rosa": _cobertura({ORIGEM_HUMANO_PORTAL}),
        "laranja": _cobertura({ORIGEM_QA_AGENTE}),
    }
