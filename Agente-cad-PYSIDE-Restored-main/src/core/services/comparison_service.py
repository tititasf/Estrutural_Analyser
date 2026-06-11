"""
src/core/services/comparison_service.py — CAD-10.4
Compara campos Fase-4 (interpretado) vs DB (atual) vs Ground Truth (Fase-3).

Uso:
    svc = ComparisonService(item_data, obra_path)
    rows = svc.build_rows()   # lista de CompRow
    svc.accept_field(field_id, db, project_id)
    svc.save_correction(field_id, new_value, db, project_id)
"""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from src.core.field_mapping import (
    map_pilar, map_viga_lateral, map_viga_fundo, map_laje,
    map_detail_to_fase4,
)

log = logging.getLogger(__name__)

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")


class FieldStatus(str, Enum):
    IGUAL      = "IGUAL"       # GT == F4 == DB  (ou GT ausente e F4 == DB)
    DIFERENTE  = "DIFERENTE"   # F4 != DB, ambos não-vazios
    AUSENTE_GT = "AUSENTE_GT"  # Ground Truth não tem este campo
    AUSENTE_F4 = "AUSENTE_F4"  # Fase-4 não tem este campo
    CONFLITO   = "CONFLITO"    # campo validado manualmente com valor != F4


@dataclass
class CompRow:
    field_id:  str
    label:     str
    gt_value:  Any = None
    f4_value:  Any = None
    db_value:  Any = None
    status:    FieldStatus = FieldStatus.AUSENTE_F4
    validated: bool = False    # campo está em validated_fields


def _fmt(v: Any) -> str:
    if v is None or v == '' or v == 0.0 or v == 0:
        return ''
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)


def _eq(a: Any, b: Any) -> bool:
    """Compara com tolerância para floats."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) < 0.05
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def _empty(v: Any) -> bool:
    return v is None or v == '' or v == [] or v == {} or v == 0.0 or v == 0


# ─── Labels legíveis por field_id ─────────────────────────────────────────────

_FIELD_LABELS: dict[str, str] = {
    'dim':          'Dimensão (CxL)',
    'altura':       'Altura',
    'grade_1':      'Grade 1',
    'grade_2':      'Grade 2',
    'par_1_2':      'Par 1-2',
    'par_2_3':      'Par 2-3',
    'par_3_4':      'Par 3-4',
    'par_4_5':      'Par 4-5',
    'par_5_6':      'Par 5-6',
    'par_6_7':      'Par 6-7',
    'par_7_8':      'Par 7-8',
    'par_8_9':      'Par 8-9',
    'distancia_1':  'Distância 1',
    'distancia_2':  'Distância 2',
    'pavimento':    'Pavimento',
}

def _label(field_id: str) -> str:
    if field_id in _FIELD_LABELS:
        return _FIELD_LABELS[field_id]
    # p_s{face}_c_h1 → Face A - Chapa H1  /  p_s{face}_l1_h → Face A - Laje H
    if field_id.startswith('p_s') and '_' in field_id[3:]:
        rest = field_id[3:]  # 'A_c_h1' or 'A_l1_h'
        parts = rest.split('_', 1)
        face = parts[0]      # 'A'
        key  = parts[1] if len(parts) > 1 else ''
        # Make key human-readable
        key_label = key.upper().replace('C_H', 'Chapa H').replace('C_LARG', 'Chapa Larg').replace('L1_H', 'Laje H').replace('L1_P', 'Laje Pos')
        return f"Face {face} - {key_label}"
    # viga_a_seg_1_h1
    if field_id.startswith('viga_'):
        return field_id.replace('_', ' ').title()
    return field_id.replace('_', ' ').title()


# ─── Loaders GT ──────────────────────────────────────────────────────────────

def _load_gt_pilar(obra: Path, item_id: str) -> dict:
    gt_path = obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_ground_truth.json"
    if not gt_path.exists():
        return {}
    try:
        all_gt = json.loads(gt_path.read_text(encoding='utf-8', errors='replace'))
        return all_gt.get(item_id, {})
    except Exception:
        return {}


def _load_gt_viga(obra: Path, item_id: str) -> dict:
    gt_path = obra / "Fase-3_Interpretacao_Extracao" / "Vigas" / "vigas_ground_truth.json"
    if not gt_path.exists():
        return {}
    try:
        all_gt = json.loads(gt_path.read_text(encoding='utf-8', errors='replace'))
        return all_gt.get(item_id, {})
    except Exception:
        return {}


def _load_gt_laje(obra: Path, item_id: str) -> dict:
    gt_path = obra / "Fase-3_Interpretacao_Extracao" / "Lajes" / "lajes_ground_truth.json"
    if not gt_path.exists():
        return {}
    try:
        all_gt = json.loads(gt_path.read_text(encoding='utf-8', errors='replace'))
        return all_gt.get(item_id, {})
    except Exception:
        return {}


# ─── Service ─────────────────────────────────────────────────────────────────

class ComparisonService:
    """
    Carrega GT + Fase-4 para um item do DB e compara campo a campo.
    Imutável por construção — accept/save_correction criam side effects externos.
    """

    def __init__(self, item_data: dict, obra_path: str | Path | None):
        self.item_data  = item_data
        self.obra       = Path(obra_path) if obra_path else None
        self.item_id    = item_data.get('id_item') or item_data.get('name', '')
        self.item_type  = item_data.get('type', '').lower()
        self.validated  = set(item_data.get('validated_fields', []))

        self._gt_raw:  dict = {}
        self._f4_raw:  dict | None = None   # None = arquivo não existe
        self._f4_map:  dict = {}            # resultado de map_*
        self._f4_path: Path | None = None

        self._load_sources()

    # ── Carregamento ─────────────────────────────────────────────────────────

    def _load_sources(self):
        if not self.obra or not self.item_id:
            return

        if 'pilar' in self.item_type:
            self._gt_raw = _load_gt_pilar(self.obra, self.item_id)
            f4p = self.obra / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{self.item_id}.json"
            if f4p.exists():
                self._f4_path = f4p
                self._f4_raw  = json.loads(f4p.read_text(encoding='utf-8-sig'))
                self._f4_map  = map_pilar(self._f4_raw)

        elif 'viga' in self.item_type:
            base_id = self.item_id.rsplit('_', 1)[0] if '_' in self.item_id else self.item_id
            self._gt_raw = _load_gt_viga(self.obra, base_id)
            for side in ('A', 'B', 'fundo'):
                f4p = self.obra / "Fase-4_Sincronizacao" / (
                    "JSON_Vigas_Laterais" if side != 'fundo' else "JSON_Vigas_Fundo"
                ) / f"{base_id}_{side}.json"
                if not f4p.exists():
                    f4p = self.obra / "Fase-4_Sincronizacao" / (
                        "JSON_Vigas_Laterais" if side != 'fundo' else "JSON_Vigas_Fundo"
                    ) / f"{self.item_id}_{side}.json"
                if f4p.exists():
                    self._f4_path = f4p
                    self._f4_raw  = json.loads(f4p.read_text(encoding='utf-8-sig'))
                    self._f4_map  = (map_viga_lateral(self._f4_raw, side)
                                     if side != 'fundo' else map_viga_fundo(self._f4_raw))
                    break

        elif 'laje' in self.item_type:
            self._gt_raw = _load_gt_laje(self.obra, self.item_id)
            f4p = self.obra / "Fase-4_Sincronizacao" / "JSON_Lajes" / f"{self.item_id}.json"
            if f4p.exists():
                self._f4_path = f4p
                self._f4_raw  = json.loads(f4p.read_text(encoding='utf-8-sig'))
                self._f4_map  = map_laje(self._f4_raw)

    # ── Build rows ────────────────────────────────────────────────────────────

    def build_rows(self) -> list[CompRow]:
        """Gera lista de CompRow para exibição na tabela."""
        if self._f4_raw is None and not self._gt_raw:
            return []

        rows: list[CompRow] = []
        seen: set[str] = set()

        f4_flat   = self._f4_map.get('flat',   {}) if self._f4_map else {}
        f4_sd     = self._f4_map.get('sides_data', {}) if self._f4_map else {}
        f4_links  = self._f4_map.get('links',  {}) if self._f4_map else {}

        # ── flat fields ──────────────────────────────────────────────────
        for fid, f4_val in f4_flat.items():
            if fid in seen:
                continue
            seen.add(fid)
            db_val = self._db_value(fid)
            gt_val = self._gt_value_for(fid)
            rows.append(self._make_row(fid, f4_val, db_val, gt_val))

        # ── sides_data → field IDs p_s{face}_{key} ────────────────────────
        for face, keys in f4_sd.items():
            for key, f4_val in keys.items():
                fid = f'p_s{face}_{key}'
                if fid in seen:
                    continue
                seen.add(fid)
                db_val = self._db_value_sides(face, key)
                rows.append(self._make_row(fid, f4_val, db_val, None))

        # ── links fields ──────────────────────────────────────────────────
        for fid, slots in f4_links.items():
            if fid in seen:
                continue
            seen.add(fid)
            db_val = self._db_value(fid)
            # Extrair texto do link para exibição
            f4_val = self._extract_link_text(slots)
            rows.append(self._make_row(fid, f4_val, db_val, None))

        # ── GT-only fields (campos no GT mas não em F4) ───────────────────
        for k, v in self._gt_raw.items():
            # Mapear chaves GT simples (b, h, altura) para field_ids comuns
            fid = {'b': 'dim', 'h': 'dim', 'altura': 'altura'}.get(k, k)
            if fid not in seen and not _empty(v):
                seen.add(fid)
                rows.append(CompRow(
                    field_id=fid,
                    label=_label(fid),
                    gt_value=v,
                    f4_value=None,
                    db_value=self._db_value(fid),
                    status=FieldStatus.AUSENTE_F4,
                    validated=fid in self.validated,
                ))

        return rows

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_row(self, fid: str, f4_val: Any, db_val: Any, gt_val: Any) -> CompRow:
        validated = fid in self.validated
        status: FieldStatus

        if _empty(f4_val):
            status = FieldStatus.AUSENTE_F4
        elif validated and not _eq(f4_val, db_val):
            status = FieldStatus.CONFLITO
        elif _empty(db_val):
            status = FieldStatus.DIFERENTE  # F4 tem valor, DB está vazio
        elif _eq(f4_val, db_val):
            status = FieldStatus.IGUAL
        else:
            status = FieldStatus.DIFERENTE

        return CompRow(
            field_id=fid,
            label=_label(fid),
            gt_value=gt_val,
            f4_value=f4_val,
            db_value=db_val,
            status=status,
            validated=validated,
        )

    def _db_value(self, fid: str) -> Any:
        # Tenta links primeiro, depois campos diretos
        links = self.item_data.get('links', {})
        if fid in links:
            return self._extract_link_text(links[fid])
        return self.item_data.get(fid)

    def _db_value_sides(self, face: str, key: str) -> Any:
        sd = self.item_data.get('sides_data', {})
        if isinstance(sd, dict):
            return sd.get(face, {}).get(key)
        return None

    def _gt_value_for(self, fid: str) -> Any:
        if not self._gt_raw:
            return None
        # Mapeamento direto
        direct_map = {
            'dim':   lambda: f"{self._gt_raw.get('b','?')}x{self._gt_raw.get('h','?')}",
            'altura': lambda: self._gt_raw.get('altura'),
        }
        fn = direct_map.get(fid)
        if fn:
            try:
                return fn()
            except Exception:
                return None
        return self._gt_raw.get(fid)

    @staticmethod
    def _extract_link_text(slots: Any) -> str:
        """Extrai texto legível de um dict de links."""
        if not slots or not isinstance(slots, dict):
            return ''
        texts = []
        for slot_data in slots.values():
            if isinstance(slot_data, list):
                for item in slot_data:
                    if isinstance(item, dict) and 'text' in item:
                        texts.append(item['text'])
        return ', '.join(texts) if texts else str(slots)[:40]

    # ── Score ──────────────────────────────────────────────────────────────

    def score(self) -> dict:
        """Retorna {'completude_pct', 'match_pct', 'total', 'f4_filled', 'matched'}."""
        rows = self.build_rows()
        total   = len(rows)
        f4_fill = sum(1 for r in rows if not _empty(r.f4_value))
        matched = sum(1 for r in rows if r.status == FieldStatus.IGUAL)
        return {
            'total':          total,
            'f4_filled':      f4_fill,
            'matched':        matched,
            'completude_pct': round(100 * f4_fill / total, 1) if total else 0,
            'match_pct':      round(100 * matched / f4_fill, 1) if f4_fill else 0,
        }

    # ── Actions ───────────────────────────────────────────────────────────────

    def accept_field(self, fid: str, db, project_id: str) -> bool:
        """Aplica valor Fase-4 no item_data + persiste no DB. Não adiciona a validated_fields."""
        if self._f4_map is None:
            return False

        f4_flat = self._f4_map.get('flat', {})
        f4_sd   = self._f4_map.get('sides_data', {})

        # Atualizar item_data em memória
        if fid in f4_flat:
            self.item_data[fid] = f4_flat[fid]
        elif fid.startswith('p_s'):
            # p_sA_h1 → fid[3:] = 'A_h1' → face='A', key='h1'
            rest  = fid[3:]          # 'A_h1'
            parts = rest.split('_', 1)
            face  = parts[0]         # 'A'
            key   = parts[1] if len(parts) > 1 else ''  # 'h1'
            sd = self.item_data.setdefault('sides_data', {})
            sd.setdefault(face, {})[key] = f4_sd.get(face, {}).get(key)
        else:
            return False

        # Persistir no DB
        try:
            t = self.item_type
            if 'pilar' in t:
                db.save_pillar(self.item_data, project_id)
            elif 'viga' in t:
                db.save_beam(self.item_data, project_id)
            elif 'laje' in t:
                db.save_slab(self.item_data, project_id)
            return True
        except Exception as e:
            log.error(f"[ComparisonService] accept_field {fid}: {e}")
            return False

    def accept_all_non_conflict(self, db, project_id: str) -> tuple[int, int]:
        """Aceita todos os campos sem CONFLITO. Retorna (aceitos, conflitos_preservados)."""
        rows = self.build_rows()
        accepted = 0
        preserved = 0
        for row in rows:
            if row.status == FieldStatus.CONFLITO:
                preserved += 1
            elif row.status in (FieldStatus.DIFERENTE,) and not _empty(row.f4_value):
                if self.accept_field(row.field_id, db, project_id):
                    accepted += 1
        return accepted, preserved

    def save_correction(self, fid: str, new_value: Any, db, project_id: str) -> bool:
        """
        Grava correção manual de volta ao JSON Fase-4.
        1. Faz backup do JSON original (*.json.bak)
        2. Atualiza a chave correspondente no JSON
        3. Grava entrada em correction_log.json
        """
        if not self._f4_path or not self._f4_path.exists():
            log.warning("[ComparisonService] save_correction: sem Fase-4 JSON para corrigir")
            return False

        # Mapeamento inverso field_id → json_key_fase4
        inverse = map_detail_to_fase4(fid, str(new_value))
        if not inverse:
            log.warning(f"[ComparisonService] Sem mapeamento inverso para {fid}")
            return False

        json_key, converted_val = inverse
        old_value = self._f4_raw.get(json_key) if self._f4_raw else None

        # Backup
        bak_path = self._f4_path.with_suffix('.json.bak')
        if not bak_path.exists():
            shutil.copy2(self._f4_path, bak_path)

        # Atualizar JSON
        data = dict(self._f4_raw or {})
        data[json_key] = converted_val
        self._f4_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        self._f4_raw = data

        # Correction log
        log_path = (self.obra / "Fase-3_Interpretacao_Extracao" / "correction_log.json"
                    if self.obra else None)
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            entries: list = []
            if log_path.exists():
                try:
                    entries = json.loads(log_path.read_text(encoding='utf-8'))
                except Exception:
                    entries = []
            entries.append({
                'item':       self.item_id,
                'field':      json_key,
                'old_value':  old_value,
                'new_value':  converted_val,
                'source':     'manual_correction',
                'timestamp':  datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
                'user':       'operator',
            })
            log_path.write_text(
                json.dumps(entries, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )

        # Atualizar DB também (item_data já foi alterado pelo accept_field se chamado antes)
        self.item_data[fid] = new_value
        try:
            t = self.item_type
            if 'pilar' in t:
                db.save_pillar(self.item_data, project_id)
            elif 'viga' in t:
                db.save_beam(self.item_data, project_id)
            elif 'laje' in t:
                db.save_slab(self.item_data, project_id)
        except Exception as e:
            log.error(f"[ComparisonService] save_correction DB update: {e}")

        log.info(f"[ComparisonService] Correção salva: {self.item_id}.{json_key} "
                 f"{old_value!r} → {converted_val!r}")
        return True

    # ── Estado ────────────────────────────────────────────────────────────────

    @property
    def has_fase4(self) -> bool:
        return self._f4_raw is not None

    @property
    def has_obra(self) -> bool:
        return self.obra is not None
