#!/usr/bin/env python
"""Reaplica face_beams (passa/para/dim limpa) em pillars.sides_data_json.

Somente o projeto indicado. Preserva lajes (l1/l2) e campos validados.
Não toca LV/FV. Uso:

  py -3.12 scripts/arete/reenrich_pillar_face_beams_db.py \\
    --project-id dd238e47-1dc6-4f63-a760-4e7ce19a7386 \\
    --db D:/Agente-cad-PYSIDE/project_data.vision \\
    --apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.pillar_face_beams import (  # noqa: E402
    clean_beam_section_dim,
    enrich_pillar_report_with_beams,
)


def _load_report(conn: sqlite3.Connection, project_id: str) -> tuple[dict, dict]:
    report: dict = {}
    meta: dict = {}
    for row in conn.execute(
        "SELECT id, name, points_json, sides_data_json, links_json, "
        "validated_fields_json FROM pillars WHERE project_id=?",
        (project_id,),
    ):
        pid, name, pj, sj, lj, vj = row
        sides = json.loads(sj or "{}")
        entry = {
            "name": name,
            "points": json.loads(pj or "[]"),
            "lajes": [],
        }
        for face in "ABCD":
            face_sd = sides.get(face) or {}
            ln = str(face_sd.get("l1_n") or "").strip()
            if ln:
                laje_val = None if "SEM" in ln.upper() else ln
                entry["lajes"].append({"side": face, "laje": laje_val})
        report[name] = entry
        meta[name] = {
            "id": pid,
            "sides": sides,
            "links": json.loads(lj or "{}"),
            "validated": set(json.loads(vj or "[]") or []),
        }
    return report, meta


def _load_beams(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    beams = []
    for name, raw in conn.execute(
        "SELECT name, data_json FROM beams WHERE project_id=?",
        (project_id,),
    ):
        data = json.loads(raw or "{}")
        data["name"] = name
        beams.append(data)
    return beams


def _blocked_field(face: str, field: str, validated: set) -> bool:
    flat = f"p_s{face}_{field}"
    return field in validated or flat in validated


def _apply_face_beams_to_sides(
    sides: dict,
    face_beams: dict,
    validated: set,
) -> dict:
    """Atualiza só slots de viga; preserva l1/l2 e campos validados."""
    out = json.loads(json.dumps(sides or {}))  # deep copy
    for face in "ABCD":
        face_sd = out.setdefault(face, {})
        if not isinstance(face_sd, dict):
            face_sd = {}
            out[face] = face_sd
        fb = face_beams.get(face) or {}

        # limpa passa/ch antigos se não validados
        for key in list(face_sd.keys()):
            if not isinstance(key, str):
                continue
            if key.startswith("v_passa_") or key.startswith("v_ch") or key in (
                "v_esq_n",
                "v_esq_d",
                "v_int_n",
                "v_int_d",
            ):
                if not _blocked_field(face, key, validated):
                    face_sd.pop(key, None)

        for slot, sfx_base in (
            ("passa_esq", "v_passa_esq"),
            ("passa_dir", "v_passa_dir"),
        ):
            payload = fb.get(slot)
            if not isinstance(payload, dict) or not payload.get("name"):
                continue
            kn, kd = f"{sfx_base}_n", f"{sfx_base}_d"
            if not _blocked_field(face, kn, validated):
                face_sd[kn] = str(payload["name"]).strip()
            dim = clean_beam_section_dim(payload.get("dim"))
            if dim and not _blocked_field(face, kd, validated):
                face_sd[kd] = dim

        for i, payload in enumerate(fb.get("para") or [], 1):
            if i > 3 or not isinstance(payload, dict):
                break
            nm = str(payload.get("name") or "").strip()
            if not nm:
                continue
            kn, kd = f"v_ch{i}_n", f"v_ch{i}_d"
            if not _blocked_field(face, kn, validated):
                face_sd[kn] = nm
            dim = clean_beam_section_dim(payload.get("dim"))
            if dim and not _blocked_field(face, kd, validated):
                face_sd[kd] = dim

    return out


def _sync_links_from_sides(
    links: dict,
    sides: dict,
    validated: set,
) -> dict:
    """DetailCard prioriza links > sides_data.

    Remove vínculos de viga desatualizados (passa/ch/esq) não validados e
    recria rótulos simples a partir do sides_data novo, para a UI SA mostrar
    o mesmo que o reenrich gravou.
    """
    out = json.loads(json.dumps(links or {}))
    beam_prefixes = (
        "v_passa_esq_",
        "v_passa_dir_",
        "v_ch1_",
        "v_ch2_",
        "v_ch3_",
        "v_esq_",
        "v_int_",
    )
    # 1) limpa links de viga não validados
    for key in list(out.keys()):
        if not isinstance(key, str) or not key.startswith("p_s"):
            continue
        # p_sA_v_passa_esq_n
        parts = key.split("_", 2)
        if len(parts) < 3:
            continue
        face = parts[1][1:] if parts[1].startswith("s") else ""
        sfx = parts[2]
        if not any(sfx.startswith(p) for p in beam_prefixes):
            continue
        if _blocked_field(face, sfx, validated) or key in validated:
            continue
        out.pop(key, None)

    # 2) recria links texto a partir de sides (só se ainda não validado)
    for face in "ABCD":
        face_sd = sides.get(face) or {}
        if not isinstance(face_sd, dict):
            continue
        for sfx, val in face_sd.items():
            if not isinstance(sfx, str):
                continue
            if not any(sfx.startswith(p) for p in beam_prefixes):
                continue
            text = str(val or "").strip()
            if not text:
                continue
            if _blocked_field(face, sfx, validated):
                continue
            flat = f"p_s{face}_{sfx}"
            out[flat] = {
                "label": [
                    {
                        "text": text,
                        "type": "text",
                        "role": "label",
                        "source": "pillar_face_beams_reenrich",
                    }
                ]
            }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument(
        "--db",
        default=str(ROOT.parent / "project_data.vision"),
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Grava no DB (sem flag = dry-run)",
    )
    args = ap.parse_args()
    db = Path(args.db)
    if not db.is_file():
        print(f"DB não encontrado: {db}", flush=True)
        return 2

    conn = sqlite3.connect(str(db))
    try:
        report, meta = _load_report(conn, args.project_id)
        beams = _load_beams(conn, args.project_id)
        print(
            f"[reenrich] pilares={len(report)} vigas={len(beams)} "
            f"apply={args.apply}",
            flush=True,
        )
        enrich_pillar_report_with_beams(report, beams)

        n_passa = n_para = n_upd = 0
        for name, entry in report.items():
            fb = entry.get("face_beams") or {}
            for face, slots in fb.items():
                for s in ("passa_esq", "passa_dir"):
                    if slots.get(s):
                        n_passa += 1
                n_para += len(slots.get("para") or [])
            m = meta[name]
            new_sides = _apply_face_beams_to_sides(
                m["sides"], fb, m["validated"]
            )
            new_links = _sync_links_from_sides(
                m["links"], new_sides, m["validated"]
            )
            changed = new_sides != m["sides"] or new_links != m["links"]
            if changed:
                n_upd += 1
                if args.apply:
                    conn.execute(
                        "UPDATE pillars SET sides_data_json=?, links_json=? "
                        "WHERE id=?",
                        (
                            json.dumps(new_sides, ensure_ascii=False),
                            json.dumps(new_links, ensure_ascii=False),
                            m["id"],
                        ),
                    )
        if args.apply:
            conn.commit()
            print(
                f"[reenrich] COMMIT sides_data+links em {n_upd} pilares",
                flush=True,
            )
        else:
            print(
                f"[reenrich] DRY-RUN: {n_upd} pilares mudariam "
                f"(passa_slots={n_passa} para_slots={n_para})",
                flush=True,
            )
        print(
            f"[reenrich] totais face_beams: passa={n_passa} para={n_para}",
            flush=True,
        )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
