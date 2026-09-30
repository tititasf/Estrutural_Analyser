"""Correções humanas SA, separadas do snapshot de interpretação original."""
from __future__ import annotations
import json
import math
import os
import tempfile
from pathlib import Path

CLASSIFICATIONS = ("SEGUE", "MORRE", "NASCE", "INDETERMINADO", "CONTINUA", "PASSA")
ORIENTATIONS = ("RETANGULAR VERTICAL", "RETANGULAR HORIZONTAL", "QUADRADO", "ESPECIAL")
FIELDS = {"classificacao", "orientacao", "nivel_chegada", "nivel_saida", "pe_direito"}

def eligible(pillar):
    return str(pillar.get("classification") or "").strip().upper() != "NASCE"

def review_path(obra_dir, pavimento, item):
    for value in (pavimento, item):
        if not value or Path(value).name != value or any(c in value for c in '/\\:') or value in ('.', '..'):
            raise ValueError("Identidade inválida")
    return Path(obra_dir) / "sa_reviews" / pavimento / (item + ".json")

def load(obra_dir, pavimento, item):
    path = review_path(obra_dir, pavimento, item)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("fields", {})

def validate(fields):
    if not fields or set(fields) - FIELDS:
        raise ValueError("Campos SA inválidos")
    out = {}
    for key, value in fields.items():
        if key in ("classificacao", "orientacao"):
            value = str(value).strip().upper()
            choices = CLASSIFICATIONS if key == "classificacao" else ORIENTATIONS
            if value not in choices:
                raise ValueError("Convenção ou orientação inválida")
        else:
            if isinstance(value, bool):
                raise ValueError("Número inválido")
            try:
                value = float(str(value).replace(',', '.'))
            except (ValueError, TypeError):
                raise ValueError("Número inválido") from None
            if not math.isfinite(value) or (key == "pe_direito" and value <= 0):
                raise ValueError("Número inválido")
        out[key] = value
    return out

def save(obra_dir, pavimento, item, fields):
    fields = validate(fields)
    path = review_path(obra_dir, pavimento, item)
    merged = {**load(obra_dir, pavimento, item), **fields}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump({"fields": merged}, handle, ensure_ascii=False, indent=2)
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return merged

def apply(pillar, fields):
    if "classificacao" in fields:
        pillar["classification"] = fields["classificacao"]
        pillar["ignore_in_beams"] = fields["classificacao"] == "NASCE"
        pillar["physical_type"] = "visual_only" if fields["classificacao"] == "NASCE" else "solid"
    if "orientacao" in fields:
        pillar["orientation"] = fields["orientacao"]
    return pillar

def apply_state(state, obra_dir, pavimento):
    for pillar in state.get('pilares', []):
        item = str(pillar.get('name') or pillar.get('key') or '')
        if item:
            apply(pillar, load(obra_dir, pavimento, item))
    return state

def apply_report(report, obra_dir, pavimento):
    for key, pillar in report.items():
        apply(pillar, load(obra_dir, pavimento, str(pillar.get('name') or key)))


def apply_robot(payload, fields):
    if 'pe_direito' in fields:
        payload['altura'] = payload['pd_pavimento_cm'] = fields['pe_direito']
    for key in ('nivel_chegada', 'nivel_saida'):
        if key in fields:
            payload[key + '_abs'] = fields[key]
    return payload


def resolve_obra(obra):
    path = Path(str(obra))
    if path.is_absolute():
        return path
    repo = Path(__file__).resolve().parents[2]
    configured = os.environ.get('CAD_DADOS_OBRAS_ROOT', '').strip()
    roots = ([Path(configured)] if configured else []) + [repo.parent / 'DADOS-OBRAS', repo / 'DADOS-OBRAS']
    return next((root / path for root in roots if (root / path).is_dir()), roots[0] / path)
