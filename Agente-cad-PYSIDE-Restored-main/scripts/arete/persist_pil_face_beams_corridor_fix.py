#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reaplica `face_beams` nos pilares já persistidos, com a recuperação de
corredor calibrada — sem reanalisar o DXF do zero.

Por quê este script existe, e não `headless_sa_analise.py --persist-db`
--------------------------------------------------------------------------
A reanálise completa (`--persist-db` no modo "SA humano") reexecuta o
BeamTracer inteiro a partir do DXF bruto, e isso REGRIDE a seção de algumas
vigas: `canonical_fundo_section_dim` liga o contorno de fundo com evidência
diferente da que já está persistida (medido em 2026-08-23: `VF301` volta a
`19/66`, a seção do pilar, em vez do `14/55` já curado). Os registros já
salvos em `pillars`/`beams` carregam correções de sessões anteriores que uma
nova varredura geométrica não reproduz.

Este script não toca em `beams` nem em geometria: lê os pilares e vigas
EXATAMENTE como estão persistidos, aplica só a recuperação de corredor
(`src.core.beam_corridor_recovery`, a mesma fonte que o comparador de QA
usa) e a mesma `enrich_pillar_report_with_beams` que o app chama — e grava
de volta só o campo `face_beams` de cada pilar, via `DatabaseManager.save_pillar`
(que preserva validação humana automaticamente).

Uso
---
    # Dry-run (padrão): mostra o que mudaria, não escreve nada.
    python scripts/arete/persist_pil_face_beams_corridor_fix.py \\
        --db D:/Agente-cad-PYSIDE/project_data.vision \\
        --obra Obra_TREINO_1 --pav 13_PAV

    # Escreve de verdade.
    python scripts/arete/persist_pil_face_beams_corridor_fix.py \\
        --db D:/Agente-cad-PYSIDE/project_data.vision \\
        --obra Obra_TREINO_1 --pav 13_PAV --write
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))


def _resolve_project(db_path: str, obra: str, pav: str, project_id: str | None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if project_id:
            row = conn.execute(
                "SELECT id, dxf_path FROM projects WHERE id=?", (project_id,),
            ).fetchone()
            if not row:
                raise SystemExit(f"project_id não encontrado: {project_id}")
            return row["id"], row["dxf_path"]

        from src.core.ficha_utils import canonical_pavimento

        candidatos = conn.execute(
            "SELECT id, dxf_path, pavement_name, name FROM projects WHERE work_name=?",
            (obra,),
        ).fetchall()
        for row in candidatos:
            nome = row["pavement_name"] or row["name"] or ""
            if canonical_pavimento(nome) == pav:
                return row["id"], row["dxf_path"]
        raise SystemExit(
            f"Nenhum projeto de {obra!r} resolve para pavimento {pav!r}. "
            f"Candidatos: {[dict(r) for r in candidatos]}"
        )
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--project-id", default=None)
    ap.add_argument(
        "--write", action="store_true",
        help="Sem esta flag, só mostra o que mudaria (dry-run).",
    )
    args = ap.parse_args()

    from src.core.database import DatabaseManager
    from src.core.beam_corridor_recovery import (
        pillar_support_boxes, recover_pillar_beam_corridors,
    )
    from src.core.pillar_face_beams import (
        enrich_pillar_report_with_beams, reconcile_beam_fundo_facts,
    )

    project_id, dxf_path = _resolve_project(args.db, args.obra, args.pav, args.project_id)
    print(f"[persist] project_id={project_id} dxf_path={dxf_path}")

    db = DatabaseManager(args.db)
    pillars = db.load_pillars(project_id)
    beams = db.load_beams(project_id)
    if not pillars:
        raise SystemExit("Nenhum pilar encontrado para este projeto.")
    print(f"[persist] pilares={len(pillars)} vigas={len(beams)}")

    # Snapshot ANTES de mutar, para o relatório de diferença.
    antes = {p["name"]: json.dumps(p.get("face_beams") or {}, sort_keys=True) for p in pillars}

    supports = pillar_support_boxes(pillars)
    repaired, measured = recover_pillar_beam_corridors(dxf_path, beams, supports)
    n_reparadas = sum(1 for v in repaired.values() if v)
    print(f"[persist] corredores reparados: {n_reparadas} viga(s)")
    for beam in beams:
        name = str(beam.get("name") or "")
        if repaired.get(name):
            beam["_recovered_corridor"] = repaired[name]
        if measured.get(name):
            beam["_measured_corridor"] = measured[name]

    reconcile_beam_fundo_facts(beams)

    report = {}
    for pillar in pillars:
        pillar.setdefault(
            "lajes", pillar.get("lajes") or pillar.get("lajes_adjacentes") or [],
        )
        report[pillar["name"]] = pillar
    enrich_pillar_report_with_beams(report, beams)

    mudaram = []
    for p in pillars:
        depois = json.dumps(p.get("face_beams") or {}, sort_keys=True)
        if depois != antes.get(p["name"]):
            mudaram.append(p["name"])
    print(f"[persist] pilares com face_beams alterado: {len(mudaram)} -> {sorted(mudaram)}")

    if not args.write:
        print("[persist] DRY-RUN — nada foi escrito. Rode com --write para gravar.")
        return 0

    for p in pillars:
        db.save_pillar(p, project_id)
    print(f"[persist] Gravados {len(pillars)} pilar(es) em {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
