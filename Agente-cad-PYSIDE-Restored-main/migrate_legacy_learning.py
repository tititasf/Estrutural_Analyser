"""
Migration script: Extrai eventos de validacao humana dos DBs SQLite existentes
e converte para FeedbackEntry no novo formato JSON do SlabLearningStore.

DBs source:
1. engrev_laj_n1_interpretacao_learning.vision (13 human_validated events)
2. engrev_laj_recorte_learning.vision (27 human_approved events)
3. Robo_Lajes/learning_map.db (16 dimension_examples)

Target: projects_repo/<uuid>/learning/slab_learning.json (novo formato)

Uso:
    python migrate_legacy_learning.py --project-uuid <uuid> [--base-dir .]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


DB1_PATH = "D:/Agente-cad-PYSIDE/engrev_laj_n1_interpretacao_learning.vision"
DB2_PATH = "D:/Agente-cad-PYSIDE/engrev_laj_recorte_learning.vision"
DB3_PATH = "_ROBOS_ABAS/Robo_Lajes/laje_src/learning_map.db"


def migrate_db1_n1_interpretation(project_uuid: str, base_dir: str) -> list:
    """Extrai human_laje_outline_validated do DB1 (interpretacao N1)."""
    if not os.path.exists(DB1_PATH):
        print(f"[MIGRATE] DB1 nao encontrado: {DB1_PATH}")
        return []

    db = sqlite3.connect(DB1_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    entries = []

    # Eventos human_laje_outline_validated
    cur.execute("""
        SELECT e.created_at, e.obra_name, e.pavimento, e.classe, e.elemento_id,
               e.event_type, e.analysis_mode, e.operator, e.payload_json,
               f.area_cm2, f.vertex_count, f.confidence_before, f.confidence_after,
               f.candidate_line_count, f.accepted_line_count, f.rejected_line_count
        FROM engrev_laj_n1_interpretacao_events e
        LEFT JOIN engrev_laj_n1_interpretacao_features f ON f.event_id = e.id
        WHERE e.event_type = 'human_laje_outline_validated'
    """)

    for row in cur.fetchall():
        # payload_json pode ter dados do outline
        payload = {}
        if row["payload_json"]:
            try:
                payload = json.loads(row["payload_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        entry = {
            "class_type": "slab",
            "element_id": row["elemento_id"] or "unknown",
            "field_name": "outline_validation",
            "predicted_value": "motor_outline",
            "actual_value": "human_validated",
            "was_correct": True,
            "confidence_at_prediction": row["confidence_before"] or 0.0,
            "context_signature": {
                "source": "db1_n1_interpretation",
                "area_cm2": row["area_cm2"],
                "vertex_count": row["vertex_count"],
                "accepted_lines": row["accepted_line_count"],
                "rejected_lines": row["rejected_line_count"],
            },
            "timestamp": row["created_at"] or datetime.now().isoformat(),
            "pavimento": row["pavimento"] or "",
            "project_uuid": project_uuid,
        }
        entries.append(entry)

    db.close()
    print(f"[MIGRATE] DB1: {len(entries)} eventos human_laje_outline_validated extraidos")
    return entries


def migrate_db2_recorte(project_uuid: str, base_dir: str) -> list:
    """Extrai human_approved do DB2 (recorte de lajes)."""
    if not os.path.exists(DB2_PATH):
        print(f"[MIGRATE] DB2 nao encontrado: {DB2_PATH}")
        return []

    db = sqlite3.connect(DB2_PATH)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    entries = []

    cur.execute("""
        SELECT e.created_at, e.obra_name, e.pavimento, e.classe, e.elemento_id,
               e.event_type, e.source_recorte_path, e.approved_recorte_path,
               e.operator, e.notes,
               f.bbox_motor_json, f.bbox_aprovado_json,
               f.delta_left, f.delta_right, f.delta_bottom, f.delta_top,
               f.entity_count_motor, f.entity_count_aprovado,
               f.own_label_count, f.neighbor_label_count,
               f.dimension_text_count, f.panel_line_count,
               f.contour_closure_score, f.neighbor_capture_score,
               f.confidence_before, f.confidence_after
        FROM engrev_laj_recorte_learning_events e
        LEFT JOIN engrev_laj_recorte_learning_features f ON f.event_id = e.id
        WHERE e.event_type = 'human_approved'
    """)

    for row in cur.fetchall():
        # Determinar was_correct: se deltas sao proximos de zero, motor acertou
        deltas = [row["delta_left"] or 0, row["delta_right"] or 0,
                  row["delta_bottom"] or 0, row["delta_top"] or 0]
        max_delta = max(abs(d) for d in deltas) if deltas else 0
        was_correct = max_delta < 5.0  # tolerancia de 5cm

        entry = {
            "class_type": "slab",
            "element_id": row["elemento_id"] or "unknown",
            "field_name": "recorte_validation",
            "predicted_value": {
                "bbox_motor": row["bbox_motor_json"],
                "source_path": row["source_recorte_path"],
            },
            "actual_value": {
                "bbox_aprovado": row["bbox_aprovado_json"],
                "approved_path": row["approved_recorte_path"],
            },
            "was_correct": was_correct,
            "confidence_at_prediction": row["confidence_before"] or 0.0,
            "context_signature": {
                "source": "db2_recorte",
                "delta_left": row["delta_left"],
                "delta_right": row["delta_right"],
                "delta_bottom": row["delta_bottom"],
                "delta_top": row["delta_top"],
                "entity_count_motor": row["entity_count_motor"],
                "entity_count_aprovado": row["entity_count_aprovado"],
                "contour_closure_score": row["contour_closure_score"],
                "neighbor_capture_score": row["neighbor_capture_score"],
            },
            "timestamp": row["created_at"] or datetime.now().isoformat(),
            "pavimento": row["pavimento"] or "",
            "project_uuid": project_uuid,
        }
        entries.append(entry)

    db.close()
    print(f"[MIGRATE] DB2: {len(entries)} eventos human_approved extraidos")
    return entries


def migrate_db3_learning_map(project_uuid: str, base_dir: str) -> list:
    """Extrai dimension_examples do DB3 (Robo_Lajes/learning_map.db)."""
    db3_full = os.path.join(base_dir, DB3_PATH)
    if not os.path.exists(db3_full):
        print(f"[MIGRATE] DB3 nao encontrado: {db3_full}")
        return []

    db = sqlite3.connect(db3_full)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    entries = []

    cur.execute("""
        SELECT id, mode, features_json, action_keep, offset_x, offset_y,
               feedback_type, source, created_at
        FROM dimension_examples
    """)

    for row in cur.fetchall():
        features = []
        if row["features_json"]:
            try:
                features = json.loads(row["features_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        entry = {
            "class_type": "slab",
            "element_id": f"dim_example_{row['id']}",
            "field_name": "dimension_detection",
            "predicted_value": {
                "mode": row["mode"],
                "features": features,
            },
            "actual_value": {
                "action_keep": row["action_keep"],
                "offset_x": row["offset_x"],
                "offset_y": row["offset_y"],
            },
            "was_correct": row["feedback_type"] == "positive",
            "confidence_at_prediction": 0.5,  # nao tinha confidence registrado
            "context_signature": {
                "source": "db3_learning_map",
                "mode": row["mode"],
                "features_count": len(features),
                "source_type": row["source"],
            },
            "timestamp": row["created_at"] or datetime.now().isoformat(),
            "pavimento": "",
            "project_uuid": project_uuid,
        }
        entries.append(entry)

    db.close()
    print(f"[MIGRATE] DB3: {len(entries)} dimension_examples extraidos")
    return entries


def write_migrated_entries(entries: list, project_uuid: str, base_dir: str) -> str:
    """Escreve entries migradas no formato JSON do SlabLearningStore."""
    target_dir = os.path.join(base_dir, "projects_repo", project_uuid, "learning")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, "slab_learning.json")

    # Se ja existe, fazer merge
    existing = {"feedback_entries": [], "learned_parameters": []}
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    # Adicionar apenas entries novas (idempotente por element_id+field+timestamp)
    existing_keys = {
        f"{e.get('element_id')}|{e.get('field_name')}|{e.get('timestamp')}"
        for e in existing.get("feedback_entries", [])
    }

    added = 0
    for entry in entries:
        key = f"{entry['element_id']}|{entry['field_name']}|{entry['timestamp']}"
        if key not in existing_keys:
            existing.setdefault("feedback_entries", []).append(entry)
            existing_keys.add(key)
            added += 1

    # Atomic write
    tmp_path = target_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, target_path)

    print(f"[MIGRATE] Escrito: {target_path}")
    print(f"[MIGRATE] {added} novas entries adicionadas ({len(entries) - added} duplicadas ignoradas)")
    print(f"[MIGRATE] Total no arquivo: {len(existing.get('feedback_entries', []))} entries")

    return target_path


def main():
    parser = argparse.ArgumentParser(description="Migrar learning legacy para SlabLearningStore")
    parser.add_argument("--project-uuid", required=True, help="UUID do projeto destino")
    parser.add_argument("--base-dir", default=".", help="Diretorio base do projeto")
    args = parser.parse_args()

    print("=" * 60)
    print("MIGRATION: Legacy Learning -> SlabLearningStore")
    print("=" * 60)

    all_entries = []

    # DB1: N1 Interpretation (13 human_validated)
    all_entries.extend(migrate_db1_n1_interpretation(args.project_uuid, args.base_dir))

    # DB2: Recorte (27 human_approved)
    all_entries.extend(migrate_db2_recorte(args.project_uuid, args.base_dir))

    # DB3: Learning Map (16 dimension_examples)
    all_entries.extend(migrate_db3_learning_map(args.project_uuid, args.base_dir))

    print(f"\n[TOTAL] {len(all_entries)} entries coletadas de 3 DBs")

    # Escrever no formato novo
    target = write_migrated_entries(all_entries, args.project_uuid, args.base_dir)

    print(f"\n[DONE] Migration completa. Arquivo: {target}")
    print("\n[NOTA] Os DBs SQLite originais NAO foram modificados.")
    print("[NOTA] Execute 'python -m py_compile src/core/learning/slab_learning_store.py'")
    print("       apos criar o SlabLearningStore para validar integracao.")


if __name__ == "__main__":
    main()
