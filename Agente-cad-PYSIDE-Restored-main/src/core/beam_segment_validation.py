"""Segmentos de viga (FV/LV) — chaves e checagem de completude.

Compartilhado entre o sync web→app (`main.py::_sincronizar_selo_verde_drive`)
e usado como referência de convenção pela UI (`detail_card.py`, que tem sua
própria versão ligada a widgets — mesma chave `{prefix}_seg_{idx}`, mesma
regra de cascata, mas sem depender de instância de widget aqui).

Masterplan OBRAS DRIVE Fase 14.
"""

from __future__ import annotations

import re


def segment_key(prefix: str, idx: int) -> str:
    return f"{prefix}_seg_{idx}"


def existing_segment_indices(beam: dict, prefix: str) -> set:
    """Índices de segmento presentes neste beam pra este prefixo — varre
    `fields` e as chaves de raiz do dict (convenção `{prefix}_seg_{idx}_...`
    usada em toda a ficha)."""
    pattern = re.compile(rf"^{re.escape(prefix)}_seg_(\d+)_")
    indices: set = set()
    fields = beam.get("fields") if isinstance(beam.get("fields"), dict) else {}
    for key in list(beam.keys()) + list(fields.keys()):
        match = pattern.match(str(key))
        if match:
            indices.add(int(match.group(1)))
    return indices


def segments_for_behavior(beam: dict, prefix: str, behavior: str) -> set:
    """Índices de segmento de `prefix` (viga_a/viga_b) cujo dado presente
    corresponde ao `behavior` pedido ('para'/'passa') — mesma convenção de
    sufixo usada pela ficha (`_comprimento_total` = Para,
    `_comp_total_passa` = Passa)."""
    suffix = "comprimento_total" if behavior.lower() == "para" else "comp_total_passa"
    pattern = re.compile(rf"^{re.escape(prefix)}_seg_(\d+)_{suffix}$")
    indices: set = set()
    fields = beam.get("fields") if isinstance(beam.get("fields"), dict) else {}
    for key in list(beam.keys()) + list(fields.keys()):
        match = pattern.match(str(key))
        if match:
            indices.add(int(match.group(1)))
    return indices


def all_active_segment_keys(beam: dict) -> set:
    """Todas as chaves de segmento ativas neste beam — FV usa só
    `viga_fundo`; LV usa `viga_a`/`viga_b` conforme `beam['type']`."""
    itype = str(beam.get("type") or "").lower()
    keys: set = set()
    if itype in ("viga_fundo", "viga_fundo_c"):
        for idx in existing_segment_indices(beam, "viga_fundo"):
            keys.add(segment_key("viga_fundo", idx))
        return keys
    prefixes = []
    if itype in ("viga_lateral", "viga_lateral_a"):
        prefixes.append("viga_a")
    if itype in ("viga_lateral", "viga_lateral_b"):
        prefixes.append("viga_b")
    for prefix in prefixes:
        for idx in existing_segment_indices(beam, prefix):
            keys.add(segment_key(prefix, idx))
    return keys


def cascade_segments_to_item(beam: dict) -> bool:
    """Se TODOS os segmentos ativos do beam estão com selo (manual ou por
    campo), marca `is_validated=True` (selo verde) — nunca mexe no selo azul
    (`is_fully_validated`), que continua exigindo 100% dos campos do item
    inteiro. Retorna True se mudou algo."""
    active = all_active_segment_keys(beam)
    if not active:
        return False
    segs = beam.get("validated_segments") or {}
    if all(segs.get(k) for k in active) and not beam.get("is_validated"):
        beam["is_validated"] = True
        return True
    return False
