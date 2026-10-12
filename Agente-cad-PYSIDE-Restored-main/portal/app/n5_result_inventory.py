"""Inventário de desenhos publicados, independente da aprovação ou modo aberto."""
import json
from pathlib import Path

from fastapi import HTTPException

from .n5_lateral_variants import lateral_variant_path

MODE_LABELS = {"INI": "iNI", "NOVA": "NOVA", "MOLDE_1": "Formascia",
               "MOLDE_2": "Molde 2", "MOLDE_3": "Molde 3"}
CLASS_LABELS = {"PL": "Pilares", "LV": "Laterais", "FV": "Fundos", "LJ": "Lajes"}


def download_availability(release):
    """Disponibilidade do arquivo que o endpoint resolve, sem misturar releases antigos."""
    path = Path(release.get("dxf_path") or "")
    result = {"download_available": path.is_file(), "lateral_variants_available": [],
              "fundos_garfos": "", "partial": False, "item_pending": []}
    if result['download_available']:
        try:
            manifest = json.loads(path.with_suffix('.json').read_text(encoding='utf8'))
            result['partial'] = bool(manifest.get('partial'))
            result['item_pending'] = [item for item in manifest.get('items', []) if item.get('status') != 'ok']
        except (OSError, ValueError, AttributeError):
            pass
    classe = str(release.get("classe") or "").upper()
    if classe == "LV" and result["download_available"]:
        for behavior in ("PARA", "PASSA"):
            for assembly in ("gradeadas", "sarrafeadas"):
                try:
                    lateral_variant_path(path, classe, behavior, assembly)
                except HTTPException:
                    continue
                result["lateral_variants_available"].append(f"{behavior}:{assembly}")
    if classe == "FV" and result["download_available"]:
        try:
            manifest = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            config = manifest.get("vigas_config") or {}
            value = manifest.get("possui_garfos", config.get("fundos_vigas_possui_garfos"))
            if value is True or value == "sim":
                result["fundos_garfos"] = "sim"
            elif value is False or value == "nao":
                result["fundos_garfos"] = "nao"
        except (OSError, ValueError, AttributeError):
            pass
    return result


def result_inventory(releases):
    inventory = {}
    seen = set()
    for release in releases:
        path = Path(release.get("dxf_path") or "")
        if not path.is_file():
            continue
        try:
            manifest = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(manifest, dict):
            continue
        classe = str(release.get("classe") or "").upper()
        pav = str(release.get("pavimento") or "GERAL")
        mode = str(manifest.get("visual_mode") or "NOVA").upper()
        if classe not in CLASS_LABELS or mode not in MODE_LABELS:
            continue
        variants = [(manifest.get("lateral_behavior"), manifest.get("lateral_assembly"))]
        if classe == "LV" and mode in ("NOVA","MOLDE_1","INI"):
            variants = []
            for behavior in ("PARA", "PASSA"):
                for assembly in ("gradeadas", "sarrafeadas"):
                    try:
                        lateral_variant_path(path, classe, behavior, assembly)
                    except HTTPException:
                        continue
                    variants.append((behavior, assembly))
        for behavior, assembly in variants:
            parts = [CLASS_LABELS[classe]]
            if classe == "LV":
                if behavior in {"PARA", "PASSA"}:
                    parts.append(behavior)
                if assembly in {"gradeadas", "sarrafeadas"}:
                    parts.append(assembly.upper())
            if classe == "FV":
                config = manifest.get("vigas_config") or {}
                garfos = manifest.get("possui_garfos", config.get("fundos_vigas_possui_garfos"))
                if garfos in (True, "sim"):
                    parts.append("com garfos")
                elif garfos in (False, "nao"):
                    parts.append("sem garfos")
            parts.append(MODE_LABELS[mode])
            variant_manifest = manifest
            if classe == 'LV':
                try:
                    variant_path = lateral_variant_path(path, classe, behavior, assembly)
                    variant_manifest = json.loads(variant_path.with_suffix('.json').read_text(encoding='utf8'))
                except (HTTPException, OSError, ValueError):
                    continue
            if variant_manifest.get('partial'):
                parts.append('parcial · itens pendentes')
            label = " · ".join(parts)
            key = (pav, classe, label)
            if key in seen:
                continue
            seen.add(key)
            inventory.setdefault(pav, {}).setdefault(classe, []).append(label)
    return inventory
