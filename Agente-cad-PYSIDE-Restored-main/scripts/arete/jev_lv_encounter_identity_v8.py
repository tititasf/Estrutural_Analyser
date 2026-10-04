"""v8 dry-run: LV encounter identity + four-contract provenance. Zero Jev API calls."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.arete.jev_calibration.adapters_lv_v8 import (
    build_identity_request,
    extract_four_contracts,
    match_encounter,
    scan_v8_leakage,
    source_encounter_identity,
)
from scripts.arete.jev_calibration.catalog_v6 import PAVEMENT_SPECS_V6
from scripts.arete.jev_calibration.catalog_v8 import (
    CATALOG_V8_REVISION,
    FACTORY_V8_VERSION,
    MAX_PAIRED_PACKETS,
    V8_AUDIT_SCHEMA,
    V8_STATUS_SCHEMA,
    catalog_v8_hash,
)
from scripts.arete.jev_calibration.hashing import sha256_json
from scripts.arete.jev_calibration.runner import api_payload
from scripts.arete.jev_sa_second_read import MODEL

REPO = Path(__file__).resolve().parents[2]
DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
OUT = REPO / "scripts" / "arete" / "relatorios" / "20260930_jev_lv_encounter_v8"
CATALOG_14 = "f28c3897-c8df-4bb9-a187-cb090f2c7ec7"
CATALOG_13 = "dd238e47-1dc6-4f63-a760-4e7ce19a7386"
LOCAL_14 = "d4f298ab-1658-4e60-898d-ec666d54ba8c"
TARGETS = (
    {"pavimento": "14_PAV", "beam": "V409", "catalog_project_id": CATALOG_14},
    {"pavimento": "14_PAV", "beam": "V420", "catalog_project_id": CATALOG_14},
    {"pavimento": "13_PAV", "beam": "V301", "catalog_project_id": CATALOG_13},
    {"pavimento": "13_PAV", "beam": "V328", "catalog_project_id": CATALOG_13},
)


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _sha_blob(value: Any) -> str | None:
    if value is None:
        return None
    raw = value if isinstance(value, (bytes, bytearray)) else str(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _connect_ro() -> sqlite3.Connection:
    uri = f"file:{DB_PATH.as_posix()}?mode=ro&query_only=1"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    con.execute("BEGIN")
    return con


def _project_row(con: sqlite3.Connection, project_id: str) -> dict[str, Any] | None:
    row = con.execute(
        "SELECT id, name, work_name, pavement_name, dxf_path, web_sa_project_id, updated_at "
        "FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


def _beam_inventory(con: sqlite3.Connection, project_id: str, name: str) -> dict[str, Any]:
    rows = con.execute(
        "SELECT * FROM beams WHERE project_id=? AND name=?", (project_id, name),
    ).fetchall()
    out = {"project_id": project_id, "name": name, "n_rows": len(rows), "rows": []}
    payloads = []
    for row in rows:
        d = dict(row)
        blobs = {}
        scalars = {}
        for key, value in d.items():
            if key in {"data_json", "links_json", "sides_data_json", "validated_link_classes_json",
                       "na_link_classes_json", "validated_fields_json", "issues_json", "na_fields_json",
                       "na_reasons_json"}:
                blobs[key] = {
                    "len": 0 if value is None else len(value),
                    "sha256": _sha_blob(value),
                    "null": value is None,
                }
            elif isinstance(value, str) and len(value) > 200:
                blobs[key] = {"len": len(value), "sha256": _sha_blob(value), "null": False}
            else:
                scalars[key] = value
        data = {}
        links = {}
        if d.get("data_json"):
            try:
                data = json.loads(d["data_json"])
            except json.JSONDecodeError:
                data = {}
        if d.get("links_json"):
            try:
                links = json.loads(d["links_json"])
            except json.JSONDecodeError:
                links = {}
        payload = dict(data)
        if isinstance(data.get("links"), dict):
            payload_links = data["links"]
        else:
            payload["links"] = links
            payload_links = links
        contracts = extract_four_contracts(payload)
        lv_cell_flags = []
        face_curta_seen = 0
        for cell in (contracts.get("contracts") or {}).values():
            for seg in cell.get("segments") or []:
                if seg.get("flags"):
                    lv_cell_flags.extend(seg["flags"])
                if seg.get("face_curta") is not None:
                    face_curta_seen += 1
                if seg.get("support_start") or seg.get("support_end"):
                    lv_cell_flags.append("has_support")
        out["rows"].append({
            "beam_id": d.get("id"),
            "scalars": scalars,
            "blobs": blobs,
            "data_top_keys": sorted(data.keys()) if isinstance(data, dict) else [],
            "has_lv_generation_contracts": isinstance(data.get("lv_generation_contracts"), dict),
            "lv_interpreter_contract_version": data.get("lv_interpreter_contract_version"),
            "lv_cells_version": data.get("lv_cells_version"),
            "lv_is_h": data.get("lv_is_h"),
            "n_data_links": len(payload_links) if isinstance(payload_links, dict) else 0,
            "contracts": {
                "origin": contracts.get("origin"),
                "present_ids": contracts.get("present_ids"),
                "missing_ids": contracts.get("missing_ids"),
                "segment_counts": {
                    cid: len((cell or {}).get("segments") or [])
                    for cid, cell in (contracts.get("contracts") or {}).items()
                },
                "face_curta_flags_on_segments": face_curta_seen,
            },
        })
        payloads.append(payload)
    out["n1_payloads"] = payloads
    return out


def inventory_db() -> dict[str, Any]:
    con = _connect_ro()
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
        beams_cols = [{"name": r[1], "type": r[2]} for r in con.execute("PRAGMA table_info(beams)")]
        catalog14 = _project_row(con, CATALOG_14)
        catalog13 = _project_row(con, CATALOG_13)
        local14 = _project_row(con, LOCAL_14)
        lv_pp_cols = [r[1] for r in con.execute("PRAGMA table_info(lv_para_passa)")]
        lv_pp = [
            dict(r) for r in con.execute(
                "SELECT * FROM lv_para_passa WHERE item_id IN ('V409','V420','V301','V328')"
            )
        ]
        items = {
            "V409_catalog14": _beam_inventory(con, CATALOG_14, "V409"),
            "V420_catalog14": _beam_inventory(con, CATALOG_14, "V420"),
            "V409_local14": _beam_inventory(con, LOCAL_14, "V409"),
            "V420_local14": _beam_inventory(con, LOCAL_14, "V420"),
            "V301_catalog13": _beam_inventory(con, CATALOG_13, "V301"),
            "V328_catalog13": _beam_inventory(con, CATALOG_13, "V328"),
        }
        for rec in items.values():
            rec.pop("n1_payloads", None)
        return {
            "db_path": str(DB_PATH),
            "mode": "ro+query_only",
            "tables_n": len(tables),
            "beams_columns": beams_cols,
            "projects": {
                "catalog_v6_14_PAV": {"id": CATALOG_14, "present": catalog14 is not None, "row": catalog14},
                "catalog_v6_13_PAV": {"id": CATALOG_13, "present": catalog13 is not None, "row": catalog13},
                "local_treino_14": {"id": LOCAL_14, "present": local14 is not None, "row": local14},
            },
            "vps_parity": "unknown_no_remote_read",
            "lv_para_passa": {"columns": lv_pp_cols, "rows": lv_pp},
            "items": items,
        }
    finally:
        con.close()


def _payloads_by_item() -> dict[tuple[str, str], dict[str, Any]]:
    con = _connect_ro()
    try:
        mapping = {}
        for key, pid, name in (
            (("14_PAV", "V409"), LOCAL_14, "V409"),
            (("14_PAV", "V420"), LOCAL_14, "V420"),
            (("13_PAV", "V301"), CATALOG_13, "V301"),
            (("13_PAV", "V328"), CATALOG_13, "V328"),
        ):
            rec = _beam_inventory(con, pid, name)
            payloads = rec.get("n1_payloads") or []
            project = _project_row(con, pid)
            source_path = Path(project["dxf_path"]) if project and project.get("dxf_path") else None
            source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest() if source_path and source_path.is_file() else None
            mapping[key] = {
                "db_project_id": pid,
                "catalog_project_id": CATALOG_14 if key[0] == "14_PAV" else CATALOG_13,
                "identity_join": pid == (CATALOG_14 if key[0] == "14_PAV" else CATALOG_13),
                "n_rows": rec["n_rows"],
                "payload": payloads[0] if len(payloads) == 1 else None,
                "ambiguous_rows": rec["n_rows"] > 1,
                "local_source_dxf_sha256": source_sha,
            }
        return mapping
    finally:
        con.close()


def _load_frozen_encounters(pavimento: str, beams: set[str]) -> dict[str, Any]:
    spec = PAVEMENT_SPECS_V6[pavimento]
    inventory = json.loads(Path(spec["inventory"]).read_text(encoding="utf-8-sig"))
    actual_sha = sha256_json({k: v for k, v in inventory.items() if k != "inventory_sha256"})
    selected = [
        enc for enc in inventory.get("encounters") or []
        if str(enc.get("beam") or "") in beams
    ]
    return {
        "pavimento": pavimento,
        "inventory_sha256": inventory.get("inventory_sha256"),
        "source_dxf_sha256": inventory.get("source_dxf_sha256"),
        "expected_inventory_sha256": spec.get("expected_inventory_sha256"),
        "computed_inventory_sha256": actual_sha,
        "sha_match": actual_sha == inventory.get("inventory_sha256") == spec.get("expected_inventory_sha256"),
        "n_encounters_selected": len(selected),
        "encounters": selected,
        "project_id": spec["project_id"],
        "parity_claimed": False,
    }


def _refusal(status: str, why: str, **extra: Any) -> dict[str, Any]:
    row = {"eligible": False, "status": status, "why": why, "pack_ready": False}
    row.update(extra)
    return row


def audit_comparisons() -> dict[str, Any]:
    db_payloads = _payloads_by_item()
    comparisons = []
    refusals = Counter()
    n_source_encounters = 0
    for spec in TARGETS:
        pav = spec["pavimento"]
        beam = spec["beam"]
        frozen = _load_frozen_encounters(pav, {beam})
        n_source_encounters += len(frozen["encounters"])
        db = db_payloads[(pav, beam)]
        identity_ok = db["identity_join"]
        n1_payload = db["payload"] if identity_ok else None
        n1 = extract_four_contracts(n1_payload)
        integrity_status = None
        if not frozen["sha_match"]:
            integrity_status = "ABSTAIN_INVENTORY_INTEGRITY"
        elif identity_ok and db["local_source_dxf_sha256"] != frozen["source_dxf_sha256"]:
            integrity_status = "ABSTAIN_SOURCE_IDENTITY"
        if integrity_status:
            encounters = frozen["encounters"] or [{}]
            for enc in encounters:
                comparisons.append(_refusal(
                    integrity_status, "source_bytes_or_inventory_not_verified_for_this_baseline",
                    pavimento=pav, beam=beam, encounter_id=enc.get("encounter_id"),
                    local_source_dxf_sha256=db["local_source_dxf_sha256"],
                    frozen_source_dxf_sha256=frozen["source_dxf_sha256"],
                    source_encounter_present=bool(enc),
                ))
                refusals[integrity_status] += 1
            continue
        if not frozen["encounters"]:
            comparisons.append(_refusal(
                "ABSTAIN_SOURCE", "no_frozen_source_encounters",
                pavimento=pav, beam=beam,
                catalog_project_id=spec["catalog_project_id"],
                db_project_id=db["db_project_id"],
                n1_present_ids=n1.get("present_ids") if identity_ok else [],
                n1_missing_ids=n1.get("missing_ids") if identity_ok else list(n1.get("missing_ids") or []),
                identity_join=identity_ok,
            ))
            refusals["ABSTAIN_SOURCE"] += 1
            if not identity_ok:
                continue
        if not identity_ok:
            reason = (
                "catalog_project_id_absent_local_db_is_different_identity"
                if pav == "14_PAV" else "n1_project_identity_mismatch"
            )
            for enc in frozen["encounters"]:
                ident = source_encounter_identity({**enc, "pavimento": pav})
                comparisons.append(_refusal(
                    "ABSTAIN_PROJECT_IDENTITY", reason,
                    pavimento=pav, beam=beam, encounter_id=(ident or {}).get("encounter_id"),
                    catalog_project_id=spec["catalog_project_id"],
                    db_project_id=db["db_project_id"],
                    vps_parity="unknown_no_remote_read",
                ))
                refusals["ABSTAIN_PROJECT_IDENTITY"] += 1
            if not frozen["encounters"]:
                comparisons.append(_refusal(
                    "ABSTAIN_SOURCE", "no_frozen_source_encounters",
                    pavimento=pav, beam=beam,
                ))
                refusals["ABSTAIN_SOURCE"] += 1
            continue
        if db["n_rows"] != 1 or n1_payload is None:
            status = "ABSTAIN_MISSING_N1" if db["n_rows"] == 0 else "ABSTAIN_AMBIGUOUS_N1_ROW"
            for enc in frozen["encounters"]:
                ident = source_encounter_identity({**enc, "pavimento": pav})
                comparisons.append(_refusal(
                    status, "n1_row_count_not_unique" if db["n_rows"] != 1 else "n1_payload_absent",
                    pavimento=pav, beam=beam, encounter_id=(ident or {}).get("encounter_id"),
                    n_rows=db["n_rows"],
                ))
                refusals[status] += 1
            continue
        others = [{**enc, "pavimento": pav} for enc in frozen["encounters"]]
        for enc in frozen["encounters"]:
            source = {**enc, "pavimento": pav}
            match = match_encounter(
                source=source, n1_contracts=n1, other_source_encounters=others,
            )
            row = {
                "pavimento": pav,
                "beam": beam,
                "encounter_id": match.get("encounter_id"),
                "status": match["status"],
                "why": match["why"],
                "pack_ready": bool(match.get("pack_ready")),
                "pack_blockers": match.get("pack_blockers") or [],
                "same_handle_other_encounters": match.get("same_handle_other_encounters") or [],
                "n1_present_ids": n1.get("present_ids"),
                "n1_missing_ids": n1.get("missing_ids"),
                "n1_origin_layer": (match.get("n1_origin") or {}).get("layer"),
                "matched_contract_ids": (match.get("n1_origin") or {}).get("matched_contract_ids") or [],
                "semantic_verdict": match.get("semantic_verdict"),
                "eligible": bool(match.get("pack_ready")),
                "api_called": False,
            }
            if match.get("pack_ready"):
                packed = build_identity_request(
                    match=match, source=source,
                    identity_base={
                        "project_id": spec["catalog_project_id"],
                        "pavimento": pav,
                        "source_dxf_sha256": frozen["source_dxf_sha256"],
                    },
                )
                leaks = scan_v8_leakage(api_payload(packed["v1_request"]))
                row["request_sha256"] = packed["request_sha256"]
                row["payload_sha256"] = packed["payload_sha256"]
                row["n1_in_payload"] = packed["n1_in_payload"]
                row["payload_leaks"] = leaks
                if leaks:
                    row["eligible"] = False
                    row["pack_ready"] = False
                    row["status"] = "ABSTAIN_PAYLOAD_LEAK"
                    refusals["ABSTAIN_PAYLOAD_LEAK"] += 1
                else:
                    row["packed_request"] = packed
            else:
                refusals[match["status"]] += 1
            comparisons.append(row)
    eligible = [c for c in comparisons if c.get("eligible")]
    packed = []
    skipped = []
    for index, row in enumerate(eligible):
        if index >= MAX_PAIRED_PACKETS:
            skipped.append({k: v for k, v in row.items() if k != "packed_request"})
            continue
        packed.append(row)
    return {
        "frozen": {
            pav: {k: v for k, v in _load_frozen_encounters(pav, set()).items() if k != "encounters"}
            for pav in ("13_PAV", "14_PAV")
        },
        "n_comparisons": len(comparisons),
        "n_frozen_source_encounters": n_source_encounters,
        "n_eligible": len(eligible),
        "n_packed_for_paired_trial": len(packed),
        "n_eligible_over_cap": len(skipped),
        "refusal_counts": dict(refusals),
        "comparisons": [
            {k: v for k, v in row.items() if k != "packed_request"} for row in comparisons
        ],
        "packed_for_paired_trial": packed,
        "eligible_over_cap": skipped,
        "api_calls": 0,
    }


def semantica_md() -> str:
    return """# Semântica N1 LV inspecionada (somente leitura) — v8

Fonte: `src/core/beam_interpreters/lateral_viga_cells.py`,
`src/core/lv_beam_scene.py`, `src/core/lv_generation_contract.py`.
Nenhum desses arquivos foi alterado.

## Quatro contratos, não uma parede

LV é a matriz lado A/B × comportamento PARA/PASSA. Cada célula tem segmentos,
ajustes e prova próprios (`LV.md`; `lateral_viga_cells.py` linhas 9–30 e
445–450 `segment_all_cells`). PARA num extremo e PASSA no outro são encontros
distintos.

Publicação N1 (`lateral_viga_cells.py` 480–555): cada segmento vira
`viga_{a|b}_seg_{N}_{comprimento_total|comp_total_passa}` com `contract_id`
`LV_{side}_{PARA|PASSA}`, `source_slot`, pontos da face e `lv_cell`
(`support_start` / `support_end`, aberturas, flags). Congelar A_PARA não
congela B_PARA/A_PASSA/B_PASSA (457–477).

O contrato de geração (`lv_generation_contract.py` 14–17 e 138–168) relê esses
links: sufixo `comprimento_total` → Para; `comp_total_passa` → Passa. Cada
ficha isolada traz `structural_segments`, `endpoint_events`, `endpoint_labels`
e `contract_id` (249–283). `links.apoios` descreve o fundo e não prova contato
da face lateral (52–54).

## Eventos que distinguem PARA/PASSA por face, pilar e encontro

Cena (`lv_beam_scene.py`):

- `pillars[A|B]`, `incidents[A|B]`, `end_supports[start|end]` (93–97).
- `_attach_context` (745–793): pilar na faixa da face; `miolo` se o polígono
  cruza os dois lados da parede; `face_lateral_curta` via `_side_face_is_short`.
- Pilar na ponta vai para `end_supports` com `face_curta_por_lado` por face
  (784–791, 883–917). Viga incidente na ponta também vira apoio de extremo
  (825–830). Caso 9: T parte só a face que recebe a viga.

Decisão (`lateral_viga_cells.py` `segment_cell`):

- G6/G9 (14–19, 114–127, 342–351): PARA interrompe na face do pilar (recuo
  11 cm); PASSA engloba o pilar inteiro numa abertura G8.
- G10/D-48 (117–120, 126–127, 142–143): **PARA nunca para nas faces C/D
  (curtas)** — só em A/B/E/F/G/H. A letra é a face por onde a lateral corre.
  Na C/D o pilar é tratado como Passa (`G10_face_curta_CD_sempre_passa`).
- A exceção `miolo` bloqueia atravessamento também na célula Passa
  (121–125); `_wall` recusa `cede_para` e `miolo_por_lado` (137–141).
  G10 isolado não substitui esses atributos do mesmo apoio/encontro.
- Ponta (`_wall`, 135–165): PASSA engloba o pilar de apoio; PARA só engloba se
  `face_curta_por_lado[side]` é verdadeiro. Contato com pilar **não** implica
  PARA automaticamente.
- G7 (167–190): viga incidente decide por profundidade, nunca por PARA/PASSA.
- `support_start` / `support_end` (316–317, 423–442) nomeiam o evento de
  cada extremo do segmento (pilar, viga, seção, extremidade).

Cena G10 (`lv_beam_scene.py` 680–735 `_side_face_is_short`): aresta paralela
ao eixo, sobre a linha da face, comprimento da menor aresta; só retângulo tem
C/D; L/U/T (E–H) devolve False; quadrado ou sem aresta devolve None.

Contrato Passa (`lv_generation_contract.py` 89–136): recuo de 4 cm no lado
oposto ao volume do pilar que toca o primeiro/último ponto. É ajuste de
Passa, não prova de PARA.

## O que a v8 recusa como veredito

Handle de parede, proximidade de extremo, cobertura do segmento inteiro e
conjunto parede-nível (v6) não identificam encontro. Presença de pilar sem
flag `face_lateral_curta` / `face_curta_por_lado` não autoriza PARA.
Semântica N1 ausente permanece ausente.
"""


def relatorio_md(audit: dict[str, Any], db: dict[str, Any], status: dict[str, Any]) -> str:
    lines = [
        "# Jev conselheiro v8: identidade de encontro e quatro contratos N1",
        "",
        "Dry-run local. Jev não foi chamado. SA, DB, DXF, portal e v1–v7 não foram alterados.",
        "Jev permanece conselheiro; o adaptador não substitui o SA.",
        "",
        f"Catálogo `{CATALOG_V8_REVISION}`; factory `{FACTORY_V8_VERSION}`; "
        f"hash `{catalog_v8_hash()}`.",
        "",
        "## Identidade no SQLite (mode=ro, query_only)",
        "",
        f"DB: `{db['db_path']}`. Paridade VPS: **{db['vps_parity']}**.",
        "",
    ]
    for key, proj in db["projects"].items():
        present = "presente" if proj["present"] else "ausente"
        lines.append(f"- `{key}` `{proj['id']}`: {present}.")
        if proj.get("row"):
            row = proj["row"]
            lines.append(
                f"  work=`{row.get('work_name')}` pav=`{row.get('pavement_name')}` "
                f"updated=`{row.get('updated_at')}`."
            )
    lines += ["", "Itens inventariados (hashes de blobs, sem despejo):", "",
              "| Item | project_id | n | data_json sha256 | contracts | missing |",
              "|---|---|---|---|---|---|"]
    for name, rec in db["items"].items():
        if rec["n_rows"] == 0:
            lines.append(f"| `{name}` | `{rec['project_id']}` | 0 | — | — | — |")
            continue
        row = rec["rows"][0]
        sha = (row.get("blobs") or {}).get("data_json", {}).get("sha256") or "—"
        present = ",".join((row.get("contracts") or {}).get("present_ids") or []) or "—"
        missing = ",".join((row.get("contracts") or {}).get("missing_ids") or []) or "—"
        lines.append(
            f"| `{name}` | `{rec['project_id']}` | {rec['n_rows']} | `{sha[:16]}…` | {present} | {missing} |"
        )
    lines += [
        "",
        "`f28c3897-…` (catálogo v6 14_PAV) não existe neste DB. V409/V420 locais estão em "
        f"`{LOCAL_14}` (identidade diferente; `schemas.RECORDED_LOCAL_14PAV_DIVERGENT`). "
        "Essas linhas **não** entram em comparação N1 com o inventário congelado v3 do "
        "project_id de catálogo.",
        "",
        "`dd238e47-…` (13_PAV) está presente, porém igualdade do project_id "
        "não comprova igualdade da fonte nem proveniência da execução SA.",
        "",
        "`lv_generation_contracts` não é universal: V328 o tem; V301 publica os quatro "
        "contratos só em `links` (`lv_cells_version=guia_lv_cells_v6`). V409 local tem "
        "só `B_PASSA` (3 segmentos); A_PARA/B_PARA/A_PASSA ausentes. V420 local tem os "
        "quatro contratos em links (9 segmentos cada) mas o project_id de catálogo v6 "
        "não está neste DB — a junção com o inventário fonte congelado é recusada.",
        "",
        "`face_curta` / G10: 0 flags nos segmentos persistidos. `_support_view` "
        "(lateral_viga_cells.py 423–442) descarta `face_curta_por_lado`; as aberturas "
        "reescrevem a rule G10 para G8. Inventário fonte v3 também não carrega o flag. "
        "Contato com pilar, sozinho, permanece insuficiente.",
        "",
        "Tabela `lv_para_passa` só tem `tipo=passa` (V301, V328 em 13_PAV) e não "
        "distingue encontro, face nem PARA. Não autoriza veredito.",
        "",
        "## Comparações fonte+N1",
        "",
        f"Registros candidatos: **{audit['n_comparisons']}**, sendo "
        f"**{audit['n_frozen_source_encounters']} encontros fonte** e um registro "
        "de ausência de encontro para V301. Elegíveis para ensaio pareado: "
        f"**{audit['n_eligible']}**. Empacotados (cap {MAX_PAIRED_PACKETS}): "
        f"**{audit['n_packed_for_paired_trial']}**. Chamadas Jev: **{audit['api_calls']}**.",
        "",
        "Recusas:",
        "",
    ]
    for status_name, count in sorted((audit.get("refusal_counts") or {}).items()):
        lines.append(f"- `{status_name}`: {count}")
    lines += [
        "",
        "Por alvo (registros candidatos; o registro V301 representa ausência de encontro):",
        "",
        "| Pav | Item | n | Status |",
        "|---|---|---|---|",
    ]
    grouped = Counter()
    for row in audit.get("comparisons") or []:
        grouped[(row.get("pavimento"), row.get("beam"), row.get("status"))] += 1
    for (pav, beam, st), n in sorted(grouped.items()):
        lines.append(f"| {pav} | `{beam}` | {n} | `{st}` |")
    lines += [
        "",
        f"Pacotes prontos para ensaio pareado: **{audit['n_eligible']}**. Lacunas concretas: "
        "identidade de projeto 14_PAV, equivalência entre fontes locais e snapshots, "
        "eventos de apoio/face/miolo por encontro e proveniência da execução N1. "
        "V301 também não tem encontro fonte no freeze v3. Diferença de hash não prova "
        "mudança geométrica; exige verificação de equivalência, sem reaproveitar o baseline.",
        "",
        "Nenhum dado insuficiente gerou chamada de API. Handle, near, cover e conjunto "
        "de parede não autorizam veredito. Contato com pilar não vira PARA.",
        "",
        "Nenhum G1/G4, pass visual ou melhoria de SA é declarado.",
        "",
        f"API calls new: {status['api_calls_new']}. Execute: {status['execute']}.",
        "",
    ]
    return "\n".join(lines) + "\n"


def run(*, out: Path = OUT) -> dict[str, Any]:
    db = inventory_db()
    audit_body = audit_comparisons()
    audit = {
        "schema": V8_AUDIT_SCHEMA,
        "catalog_revision": CATALOG_V8_REVISION,
        "factory_version": FACTORY_V8_VERSION,
        "catalog_sha256": catalog_v8_hash(),
        "model": MODEL,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dry_run": True,
        "api_calls": 0,
        "n1_mutated": False,
        "db": {k: v for k, v in db.items() if k != "items"} | {
            "items": {
                name: {k: v for k, v in rec.items() if k != "n1_payloads"}
                for name, rec in db["items"].items()
            }
        },
        **audit_body,
    }
    audit["audit_sha256"] = sha256_json({k: v for k, v in audit.items() if k != "audit_sha256"})
    status = {
        "schema": V8_STATUS_SCHEMA,
        "created_at_utc": audit["created_at_utc"],
        "execute": False,
        "api_calls_new": 0,
        "n_comparisons": audit["n_comparisons"],
        "n_frozen_source_encounters": audit["n_frozen_source_encounters"],
        "n_eligible": audit["n_eligible"],
        "n_packed_for_paired_trial": audit["n_packed_for_paired_trial"],
        "refusal_counts": audit["refusal_counts"],
        "benefit_claimed": False,
        "accuracy_claimed": False,
        "parity_claimed": False,
        "n1_changed": False,
        "qa_changed": False,
        "vps_parity": "unknown_no_remote_read",
        "audit_sha256": audit["audit_sha256"],
    }
    _write(out / "audit.json", audit)
    _write(out / "STATUS.json", status)
    _write(out / "SEMANTICA.md", semantica_md())
    _write(out / "RELATORIO.md", relatorio_md(audit, audit["db"], status))
    _write(out / "db_inventory.json", audit["db"])
    return status


def main() -> None:
    status = run()
    print(json.dumps({
        "api_calls_new": status["api_calls_new"],
        "n_comparisons": status["n_comparisons"],
        "n_eligible": status["n_eligible"],
        "n_packed_for_paired_trial": status["n_packed_for_paired_trial"],
        "refusal_counts": status["refusal_counts"],
        "audit_sha256": status["audit_sha256"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
