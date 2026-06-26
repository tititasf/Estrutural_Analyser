"""
src/core/services/correction_service.py — CAD-10.6
Lógica de realimentação do interpretador: aplica correções nos JSONs Fase-4,
mantém correction_log e calcula métricas.

Primitiva central: apply_correction(json_path, json_key, new_value)
  — usada pelo ComparisonService.save_correction() e pelo CLI apply_correction.py.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.field_mapping import map_detail_to_fase4, map_pilar

log = logging.getLogger(__name__)

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
_F4_SUBDIRS = {
    'pilar': 'JSON_Pilares',
    'viga':  'JSON_Vigas_Laterais',
    'laje':  'JSON_Lajes',
}


# ─── Primitiva atômica ────────────────────────────────────────────────────────

def apply_correction(json_path: Path, json_key: str, new_value: Any,
                     create_backup: bool = True) -> bool:
    """
    Aplica uma correção atômica em um campo de JSON Fase-4.

    Suporta campos aninhados: "panels[0].width"
    Preserva todos os demais campos inalterados (encoding UTF-8, indent=2).

    Returns True se o valor foi alterado, False se já era igual (idempotente).
    """
    if not json_path.exists():
        log.error(f"[Correction] JSON não encontrado: {json_path}")
        return False

    data = json.loads(json_path.read_text(encoding='utf-8-sig'))

    # Verificar idempotência
    current = _get_nested(data, json_key)
    if current is not None:
        try:
            if abs(float(current) - float(new_value)) < 0.001:
                log.info(f"[Correction] SKIP: {json_path.stem}.{json_key} já tem valor {current}")
                return False
        except (TypeError, ValueError):
            if str(current) == str(new_value):
                log.info(f"[Correction] SKIP: {json_path.stem}.{json_key} já tem valor {current}")
                return False

    # Backup com timestamp
    if create_backup:
        ts = int(time.time())
        bak = json_path.with_suffix(f'.json.bak.{ts}')
        if not bak.exists():  # evita backups duplicados
            shutil.copy2(json_path, bak)

    # Aplicar correção
    _set_nested(data, json_key, new_value)

    json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    log.info(f"[Correction] {json_path.stem}.{json_key}: {current!r} → {new_value!r}")
    return True


def _get_nested(data: dict, key: str) -> Any:
    """Lê valor de campo possivelmente aninhado: 'panels[0].width'."""
    m = re.match(r'^(\w+)\[(\d+)\]\.(\w+)$', key)
    if m:
        arr_name, idx, field = m.groups()
        arr = data.get(arr_name, [])
        if int(idx) < len(arr):
            return arr[int(idx)].get(field)
        return None
    return data.get(key)


def _set_nested(data: dict, key: str, value: Any):
    """Grava valor em campo possivelmente aninhado: 'panels[0].width'."""
    m = re.match(r'^(\w+)\[(\d+)\]\.(\w+)$', key)
    if m:
        arr_name, idx, field = m.groups()
        data.setdefault(arr_name, [])
        while len(data[arr_name]) <= int(idx):
            data[arr_name].append({})
        data[arr_name][int(idx)][field] = value
    else:
        data[key] = value


# ─── Log de correções ─────────────────────────────────────────────────────────

def append_correction_log(obra_path: Path, entry: dict):
    """Adiciona entrada ao correction_log.json, evitando duplicatas."""
    log_path = obra_path / "Fase-3_Interpretacao_Extracao" / "correction_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entries: list = []
    if log_path.exists():
        try:
            entries = json.loads(log_path.read_text(encoding='utf-8'))
        except Exception:
            entries = []

    # Idempotência: pular se já existe entrada com mesmos item+field+new_value
    for e in entries:
        if (e.get('item_id')  == entry.get('item_id') and
                e.get('field')    == entry.get('field')   and
                e.get('new_value') == entry.get('new_value')):
            log.info(f"[CorrectionLog] SKIP duplicata: {entry.get('item_id')}.{entry.get('field')}")
            return

    entries.append(entry)
    log_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding='utf-8')


def build_log_entry(item_id: str, item_type: str, json_key: str,
                    detail_field_id: str, old_value: Any, new_value: Any,
                    obra_name: str = '', pavimento: str = '',
                    conf_before: float = 0.75) -> dict:
    return {
        'item_id':          item_id,
        'item_type':        item_type.lower(),
        'field':            json_key,
        'detail_field_id':  detail_field_id,
        'old_value':        old_value,
        'new_value':        new_value,
        'correction_type':  'manual_validation',
        'obra':             obra_name,
        'pavimento':        pavimento,
        'timestamp':        datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
        'confidence_before': conf_before,
        'confidence_after':  1.0,
    }


# ─── Batch apply from log ─────────────────────────────────────────────────────

def apply_from_log(obra_path: str | Path) -> dict:
    """
    Aplica todas as correções do correction_log.json nos JSONs Fase-4.

    Retorna:
        {'applied': N, 'skipped': N, 'errors': [...],
         'by_type': {'pilar': N, 'viga': N, 'laje': N}}
    """
    obra     = Path(obra_path)
    log_path = obra / "Fase-3_Interpretacao_Extracao" / "correction_log.json"

    if not log_path.exists():
        return {'applied': 0, 'skipped': 0, 'errors': [], 'by_type': {}}

    entries = json.loads(log_path.read_text(encoding='utf-8'))
    applied = skipped = 0
    by_type: dict[str, int] = {}
    errors: list[str] = []

    for entry in entries:
        item_id   = entry.get('item_id', '')
        item_type = entry.get('item_type', 'pilar')
        json_key  = entry.get('field', '')
        new_value = entry.get('new_value')

        json_path = _find_json_path(obra, item_id, item_type)
        if not json_path:
            errors.append(f"JSON não encontrado: {item_id} ({item_type})")
            continue

        try:
            changed = apply_correction(json_path, json_key, new_value)
            if changed:
                applied += 1
                t = item_type.lower()
                by_type[t] = by_type.get(t, 0) + 1
            else:
                skipped += 1
        except Exception as e:
            errors.append(f"{item_id}.{json_key}: {e}")

    return {'applied': applied, 'skipped': skipped, 'errors': errors, 'by_type': by_type}


def _find_json_path(obra: Path, item_id: str, item_type: str) -> Path | None:
    """Localiza o JSON Fase-4 de um item."""
    t = item_type.lower()
    fase4 = obra / "Fase-4_Sincronizacao"

    if 'pilar' in t:
        p = fase4 / "JSON_Pilares" / f"{item_id}.json"
        return p if p.exists() else None

    if 'viga' in t:
        for subdir in ("JSON_Vigas_Laterais", "JSON_Vigas_Fundo"):
            for suffix in ('_A', '_B', '_fundo', ''):
                p = fase4 / subdir / f"{item_id}{suffix}.json"
                if p.exists():
                    return p
        return None

    if 'laje' in t:
        p = fase4 / "JSON_Lajes" / f"{item_id}.json"
        return p if p.exists() else None

    return None


# ─── Métricas ─────────────────────────────────────────────────────────────────

def compute_stats(obra_path: str | Path) -> dict:
    """
    Calcula métricas do correction_log.json:
      - total, por tipo, campos mais corrigidos, tendências de delta.
    """
    obra     = Path(obra_path)
    log_path = obra / "Fase-3_Interpretacao_Extracao" / "correction_log.json"

    if not log_path.exists():
        return {'total': 0, 'by_type': {}, 'top_fields': [], 'obra': obra.name}

    entries = json.loads(log_path.read_text(encoding='utf-8'))
    total   = len(entries)
    by_type: dict[str, int] = {}
    field_counts: dict[str, list] = {}

    for e in entries:
        t = e.get('item_type', 'pilar').lower()
        by_type[t] = by_type.get(t, 0) + 1

        field = e.get('field', '?')
        old_v = e.get('old_value')
        new_v = e.get('new_value')

        if field not in field_counts:
            field_counts[field] = []
        try:
            delta = float(new_v) - float(old_v)
            field_counts[field].append(delta)
        except (TypeError, ValueError):
            field_counts[field].append(None)

    # Top 10 campos mais corrigidos
    top_fields = []
    for field, deltas in sorted(field_counts.items(),
                                key=lambda x: len(x[1]), reverse=True)[:10]:
        numeric = [d for d in deltas if d is not None]
        avg_delta = round(sum(numeric) / len(numeric), 2) if numeric else None
        top_fields.append({
            'field':     field,
            'count':     len(deltas),
            'avg_delta': avg_delta,
        })

    # Tendência por tipo: subestima ou sobrestima?
    trends: dict[str, str] = {}
    for t, count in by_type.items():
        pct = round(100 * count / total, 1) if total else 0
        trends[t] = f"{count} ({pct}%)"

    return {
        'obra':       obra.name,
        'total':      total,
        'by_type':    trends,
        'top_fields': top_fields,
    }


# ─── Detect divergences (para hook no DetailCard) ─────────────────────────────

def detect_divergences(item_data: dict, obra_path: str | Path | None,
                       db_values: dict) -> list[dict]:
    """
    Compara valores do DB (editados pelo usuário) com Fase-4.

    Retorna lista de divergências:
      [{'field_id': str, 'json_key': str, 'f4_value': Any, 'db_value': Any}]
    """
    if not obra_path:
        return []

    obra      = Path(obra_path)
    item_type = item_data.get('type', '').lower()
    item_id   = item_data.get('id_item', '')
    json_path = _find_json_path(obra, item_id, item_type)
    if not json_path:
        return []

    try:
        f4_data = json.loads(json_path.read_text(encoding='utf-8-sig'))
    except Exception:
        return []

    divergences = []
    for field_id, db_val in db_values.items():
        if not db_val:
            continue
        inverse = map_detail_to_fase4(field_id, str(db_val))
        if not inverse:
            continue
        json_key, _ = inverse
        f4_val = _get_nested(f4_data, json_key)
        if f4_val is None:
            continue
        try:
            if abs(float(f4_val) - float(db_val)) < 0.05:
                continue
        except (TypeError, ValueError):
            if str(f4_val).strip() == str(db_val).strip():
                continue

        divergences.append({
            'field_id':  field_id,
            'json_key':  json_key,
            'f4_value':  f4_val,
            'db_value':  db_val,
        })

    return divergences
