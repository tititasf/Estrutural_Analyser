"""
src/core/services/fase4_importer.py — CAD-10.2
Importa JSONs ricos da Fase-4 para o DB, complementando dados do Ground Truth.

Uso:
    from src.core.services.fase4_importer import Fase4Importer
    imp = Fase4Importer(db)
    result = imp.import_obra(obra_path, pavimento, project_id)
    # result: {'pilares': N, 'vigas': M, 'lajes': K, 'conflitos': C, 'erros': [...]}
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.core.field_mapping import (
    map_pilar, map_viga_lateral, map_viga_fundo, map_laje,
    CONF_FASE4, CONF_VALIDATED,
)

log = logging.getLogger(__name__)


# ─── Merge helpers ────────────────────────────────────────────────────────────

def _is_validated(field_id: str, validated_fields: list) -> bool:
    return field_id in validated_fields


def _merge_flat(existing: dict, new_flat: dict, validated_fields: list) -> tuple[dict, list]:
    """
    Aplica new_flat sobre existing, respeitando validated_fields.
    Retorna (merged_dict, lista de field_ids em conflito).
    """
    merged = dict(existing)
    conflicts: list[str] = []
    for fid, new_val in new_flat.items():
        if _is_validated(fid, validated_fields):
            old_val = existing.get(fid)
            if old_val is not None and str(old_val) != str(new_val):
                conflicts.append(fid)
            # mantém valor validado
        else:
            merged[fid] = new_val
    return merged, conflicts


def _merge_sides_data(existing_sd: dict, new_sd: dict, validated_fields: list) -> dict:
    """
    Merge sides_data: existing_sd[face][key] preservado se p_s{face}_{key} validado.
    """
    merged = {face: dict(keys) for face, keys in existing_sd.items()}
    for face, keys in new_sd.items():
        if face not in merged:
            merged[face] = {}
        for key, val in keys.items():
            field_id = f'p_s{face}_{key}'
            if not _is_validated(field_id, validated_fields):
                merged[face][key] = val
    return merged


def _merge_links(existing_links: dict, new_links: dict, validated_fields: list) -> dict:
    merged = dict(existing_links)
    for fid, slots in new_links.items():
        if not _is_validated(fid, validated_fields):
            merged[fid] = slots
    return merged


def _merge_conf(existing_conf: dict, new_meta: dict) -> dict:
    merged = dict(existing_conf)
    for fid, conf in new_meta.items():
        existing = merged.get(fid, 0.0)
        # Manual validated = 1.0 → nunca diminui
        if existing < CONF_VALIDATED:
            merged[fid] = max(existing, conf)
    return merged


# ─── Importer principal ──────────────────────────────────────────────────────

class Fase4Importer:
    """Importa Fase-4 JSONs para o DB preservando dados validados manualmente."""

    def __init__(self, db):
        self.db = db

    # ── Pilar ──────────────────────────────────────────────────────────────

    def _import_pilar(self, pilar_json: dict, project_id: str) -> tuple[bool, list]:
        """Importa 1 pilar. Retorna (ok, conflicts)."""
        nome = pilar_json.get('nome') or pilar_json.get('name', '')
        if not nome:
            return False, []

        mapping = map_pilar(pilar_json)

        # Buscar existente no DB
        existing = self._get_existing_pillar(nome, project_id)
        validated = existing.get('validated_fields', []) if existing else []

        # Merge
        flat, conflicts = _merge_flat(existing or {}, mapping['flat'], validated)
        sides = _merge_sides_data(
            existing.get('sides_data', {}) if existing else {},
            mapping['sides_data'], validated
        )
        conf_map = _merge_conf(
            existing.get('confidence_map', {}) if existing else {},
            mapping['meta']
        )

        pillar = {
            'id':       f"{project_id}_pil_{nome}",
            'id_item':  nome,
            'name':     nome,
            'type':     'Pilar',
            'area_val': float(
                _safe_float(pilar_json.get('comprimento', 0)) *
                _safe_float(pilar_json.get('largura', 0))
            ),
            'points':   existing.get('points', [[0.0, 0.0]]) if existing else [[0.0, 0.0]],
            'sides_data':              sides,
            'links':                   existing.get('links', {}) if existing else {},
            'confidence_map':          conf_map,
            'validated_fields':        validated,
            'validated_link_classes':  existing.get('validated_link_classes', {}) if existing else {},
            'na_fields':               existing.get('na_fields', []) if existing else [],
            'na_link_classes':         existing.get('na_link_classes', {}) if existing else {},
            'na_reasons':              existing.get('na_reasons', {}) if existing else {},
            'issues':                  existing.get('issues', []) if existing else [],
            'is_validated':            existing.get('is_validated', False) if existing else False,
            'pkl_path':                None,
        }

        # Adicionar flat fields no sides_data raiz para _get_initial_value acesso direto
        for key, val in flat.items():
            if key not in ('name', 'id_item', 'type', 'area_val', 'points', 'sides_data',
                           'links', 'confidence_map', 'validated_fields', 'issues'):
                pillar[key] = val

        try:
            self.db.save_pillar(pillar, project_id)
            return True, conflicts
        except Exception as e:
            log.error(f"Erro ao salvar pilar {nome}: {e}")
            return False, []

    def _get_existing_pillar(self, nome: str, project_id: str) -> dict | None:
        try:
            pillars = self.db.load_pillars(project_id)
            return next((p for p in pillars if p.get('id_item') == nome), None)
        except Exception:
            return None

    # ── Viga ──────────────────────────────────────────────────────────────

    def _import_viga(self, viga_json: dict, viga_id: str, project_id: str,
                     side: str = 'A') -> tuple[bool, list]:
        """Importa 1 face de viga. Retorna (ok, conflicts)."""
        mapping = map_viga_lateral(viga_json, side) if side.lower() != 'fundo' else map_viga_fundo(viga_json)

        existing = self._get_existing_beam(viga_id, project_id)
        validated = existing.get('validated_fields', []) if existing else []

        flat, conflicts = _merge_flat(existing or {}, mapping['flat'], validated)
        conf_map = _merge_conf(
            existing.get('confidence_map', {}) if existing else {},
            mapping['meta']
        )

        beam = {
            'id':                     f"{project_id}_beam_{viga_id}",
            'id_item':                viga_id,
            'name':                   viga_json.get('name', viga_id),
            'type':                   'Viga',
            'links':                  _merge_links(
                                          existing.get('links', {}) if existing else {},
                                          mapping['links'], validated),
            'confidence_map':         conf_map,
            'validated_fields':       validated,
            'validated_link_classes': existing.get('validated_link_classes', {}) if existing else {},
            'na_fields':              existing.get('na_fields', []) if existing else [],
            'na_link_classes':        existing.get('na_link_classes', {}) if existing else {},
            'na_reasons':             existing.get('na_reasons', {}) if existing else {},
            'issues':                 existing.get('issues', []) if existing else [],
            'is_validated':           existing.get('is_validated', False) if existing else False,
            'pkl_path':               None,
        }
        # Flat fields → direto no beam (data_json inclui tudo)
        for k, v in flat.items():
            if k not in beam:
                beam[k] = v

        try:
            self.db.save_beam(beam, project_id)
            return True, conflicts
        except Exception as e:
            log.error(f"Erro ao salvar viga {viga_id}: {e}")
            return False, []

    def _get_existing_beam(self, viga_id: str, project_id: str) -> dict | None:
        try:
            beams = self.db.load_beams(project_id)
            return next((b for b in beams if b.get('id_item') == viga_id), None)
        except Exception:
            return None

    # ── Laje ──────────────────────────────────────────────────────────────

    def _import_laje(self, laje_json: dict, project_id: str) -> tuple[bool, list]:
        """Importa 1 laje. Retorna (ok, conflicts)."""
        nome = laje_json.get('nome', '')
        if not nome:
            return False, []

        mapping = map_laje(laje_json)
        existing = self._get_existing_slab(nome, project_id)
        validated = existing.get('validated_fields', []) if existing else []

        flat, conflicts = _merge_flat(existing or {}, mapping['flat'], validated)
        links = _merge_links(
            existing.get('links', {}) if existing else {},
            mapping['links'], validated
        )

        slab = {
            'id':                     f"{project_id}_slab_{nome}",
            'id_item':                nome,
            'name':                   nome,
            'type':                   'Laje',
            'area':                   flat.get('area', 0.0),
            'points':                 flat.get('points', [[0.0, 0.0]]),
            'links':                  links,
            'validated_fields':       validated,
            'validated_link_classes': existing.get('validated_link_classes', {}) if existing else {},
            'na_fields':              existing.get('na_fields', []) if existing else [],
            'na_link_classes':        existing.get('na_link_classes', {}) if existing else {},
            'na_reasons':             existing.get('na_reasons', {}) if existing else {},
            'issues':                 existing.get('issues', []) if existing else [],
            'is_validated':           existing.get('is_validated', False) if existing else False,
            'pkl_path':               None,
        }
        # Flat fields
        for k, v in flat.items():
            if k not in slab:
                slab[k] = v

        try:
            self.db.save_slab(slab, project_id)
            return True, conflicts
        except Exception as e:
            log.error(f"Erro ao salvar laje {nome}: {e}")
            return False, []

    def _get_existing_slab(self, nome: str, project_id: str) -> dict | None:
        try:
            slabs = self.db.load_slabs(project_id)
            return next((s for s in slabs if s.get('id_item') == nome), None)
        except Exception:
            return None

    # ── Entrada principal ─────────────────────────────────────────────────

    def import_obra(self, obra_path: str | Path, pavimento: str,
                    project_id: str) -> dict:
        """
        Importa todos os JSONs Fase-4 de uma obra/pavimento para o DB.

        Retorna:
            {'pilares': N, 'vigas': M, 'lajes': K,
             'conflitos': C, 'erros': [...], 'tempo_ms': T}
        """
        import time
        t0 = time.time()

        obra = Path(obra_path)
        fase4 = obra / 'Fase-4_Sincronizacao'
        if not fase4.exists():
            return {'pilares': 0, 'vigas': 0, 'lajes': 0,
                    'conflitos': 0, 'erros': [f'Fase-4 não encontrada: {fase4}']}

        n_pil = n_vig = n_laj = 0
        all_conflicts: list[str] = []
        erros: list[str] = []

        # ── Pilares ──────────────────────────────────────────────────
        for f in sorted((fase4 / 'JSON_Pilares').glob('*.json')):
            try:
                data = json.loads(f.read_text(encoding='utf-8-sig'))
                ok, conflicts = self._import_pilar(data, project_id)
                if ok:
                    n_pil += 1
                    all_conflicts.extend(conflicts)
                else:
                    erros.append(f'Pilar {f.stem}: falhou')
            except Exception as e:
                erros.append(f'Pilar {f.stem}: {e}')

        # ── Vigas Laterais ───────────────────────────────────────────
        for f in sorted((fase4 / 'JSON_Vigas_Laterais').glob('*.json')):
            try:
                data = json.loads(f.read_text(encoding='utf-8-sig'))
                # ID: V101_A → base="V101", side="A"
                stem = f.stem  # ex: V101_A
                parts = stem.rsplit('_', 1)
                viga_id = parts[0] if len(parts) == 2 else stem
                side    = parts[1] if len(parts) == 2 else 'A'
                ok, conflicts = self._import_viga(data, viga_id, project_id, side)
                if ok:
                    n_vig += 1
                    all_conflicts.extend(conflicts)
                else:
                    erros.append(f'Viga {stem}: falhou')
            except Exception as e:
                erros.append(f'Viga {f.stem}: {e}')

        # ── Vigas Fundo ──────────────────────────────────────────────
        for f in sorted((fase4 / 'JSON_Vigas_Fundo').glob('*.json')):
            try:
                data = json.loads(f.read_text(encoding='utf-8-sig'))
                # ID: V101_fundo → base="V101"
                viga_id = f.stem.replace('_fundo', '')
                ok, conflicts = self._import_viga(data, f'{viga_id}_fundo', project_id, 'fundo')
                if ok:
                    n_vig += 1
                    all_conflicts.extend(conflicts)
                else:
                    erros.append(f'Viga fundo {f.stem}: falhou')
            except Exception as e:
                erros.append(f'Viga fundo {f.stem}: {e}')

        # ── Lajes ────────────────────────────────────────────────────
        for f in sorted((fase4 / 'JSON_Lajes').glob('*.json')):
            try:
                data = json.loads(f.read_text(encoding='utf-8-sig'))
                ok, conflicts = self._import_laje(data, project_id)
                if ok:
                    n_laj += 1
                    all_conflicts.extend(conflicts)
                else:
                    erros.append(f'Laje {f.stem}: falhou')
            except Exception as e:
                erros.append(f'Laje {f.stem}: {e}')

        elapsed_ms = int((time.time() - t0) * 1000)
        result = {
            'pilares':  n_pil,
            'vigas':    n_vig,
            'lajes':    n_laj,
            'conflitos': len(set(all_conflicts)),
            'erros':    erros,
            'tempo_ms': elapsed_ms,
        }
        log.info(
            f"[Fase4Importer] {obra.name}: "
            f"{n_pil} pilares, {n_vig} vigas, {n_laj} lajes, "
            f"{len(set(all_conflicts))} conflitos, {elapsed_ms}ms"
        )
        return result


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default
