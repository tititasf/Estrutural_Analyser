#!/usr/bin/env python
"""Aplica a Camada 2 (Ag.L2) a partir do relatório de evidência dura
(``pil_l2_evidence_check.py``): adiciona os cantos faltantes na tabela ABCD,
redesenha ``{P}_qa_L2.svg`` com o MESMO ``render_agentic_svg`` do motor, e
grava o julgamento em ``aten_pil_ctx_agent_l2_*`` / ``..._verdict_l2_*`` via
``POST /api/notes/{P}`` (faz GET + merge antes — o servidor não mescla sozinho).

Não mexe em nenhum campo ``_human`` (validação humana é do humano).

Método completo: docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md §3.1
Caso piloto: P16 — INSIGHTS-QA-L1.md §8

Uso:
  py -3.12 scripts/arete/pil_l2_apply_evidence_fixes.py \\
    --pack scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_..._pilares_abcd \\
    --report scripts/arete/html_fichas/Obra_TREINO_1/13_PAV_..._pilares_abcd/propostas/l2_evidence_report.json \\
    --items P12 P15 P18 P19 P42 P44 P46 P48 P50 P51 \\
    --port 18765
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.pil_agentic_highlight_draw import load_project, render_agentic_svg  # noqa: E402
from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar  # noqa: E402
from src.core.niveis_extractor import get_pavimento_niveis_abs  # noqa: E402
from src.core.pil_qa_notes_chrome import pil_keys  # noqa: E402


def _beam_dim_nivel(face_beams: dict, beam_name: str, fallback_dim: str, fallback_nivel: str) -> tuple[str, str]:
    for fb in (face_beams or {}).values():
        for slot in ("passa_esq", "passa_dir"):
            e = fb.get(slot)
            if e and e.get("name") == beam_name and e.get("dim"):
                return e["dim"], fallback_nivel
        for e in fb.get("para") or []:
            if e.get("name") == beam_name and e.get("dim"):
                return e["dim"], fallback_nivel
        for e in fb.get("interior") or []:
            if e.get("name") == beam_name and e.get("dim"):
                return e["dim"], fallback_nivel
    return fallback_dim, fallback_nivel


def apply_item(
    finding_item: dict,
    *,
    pillar: dict,
    dxf_path: Path,
    slab_h, slab_n, slab_pts, beams,
    nivel_v: str,
    pack: Path,
    obra: str,
    pav: str,
    port: int,
) -> dict:
    name = finding_item["item"]
    findings = finding_item.get("findings") or []
    if not findings:
        return {"item": name, "skipped": "sem achado"}

    tables = build_abcd_tables_from_pillar(
        pillar, slab_height_map=slab_h, slab_nivel_map=slab_n, slab_points_map=slab_pts,
        beams=beams, nivel_viga_default=nivel_v,
    )
    tables2 = copy.deepcopy(tables)
    face_beams_raw = pillar.get("face_beams") or {}

    added = []
    seen = set()
    for f in findings:
        beam_name = f["beam"]
        for corner in f.get("missing_corners") or []:
            face_id = corner[0]  # 1ª letra do canto = a face onde a entrada "passa" mora
            key = (face_id, corner, beam_name)
            if key in seen:
                continue
            seen.add(key)
            fallback_dim = ""
            brow = next((b for b in beams if b.get("name") == beam_name), None)
            if brow:
                fallback_dim = (brow.get("fields") or {}).get("dimensao") or brow.get("dim") or ""
            dim, nivel = _beam_dim_nivel(face_beams_raw, beam_name, fallback_dim, nivel_v)
            row = {
                "familia": "viga", "nome": beam_name, "dim": dim, "nivel": nivel,
                "canto": corner, "papel": "passa", "raw": "", "dist_esq": "—", "dist_dir": "—",
            }
            lst = tables2["faces"][face_id]["passa"]
            lst[:] = [r for r in lst if (r.get("nome") or "") not in ("", "—", "nenhuma")]
            lst.append(row)
            added.append(row)

    if not added:
        return {"item": name, "skipped": "nada novo (já coberto)"}

    pts = pillar.get("points") or []
    svg = render_agentic_svg(dxf_path, pts, tables2, layer="l2")
    prop_dir = pack / "propostas"
    (prop_dir / f"{name}_qa_L2.svg").write_text(svg, encoding="utf-8")

    evidence_lines = []
    for f in findings:
        evidence_lines.append(
            f"- {f['beam']} ({f['field']}): contorno {[round(v, 1) for v in f['contour_bbox']]} "
            f"encosta full-span em {f['full_span_face']} → implica {f['implied_corners']}, "
            f"faltavam {f['missing_corners']}"
        )
    (prop_dir / f"{name}_qa_L2_tables.json").write_text(
        json.dumps({
            "item": name, "faces": tables2["faces"], "orientation": tables2.get("orientation"),
            "added": added,
            "evidence": "\n".join(evidence_lines),
        }, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    base = f"{obra}_{pav}_{name}"
    added_desc = "; ".join(f"{r['canto']} {r['nome']} {r['dim']}" for r in added)
    l2_text = (
        f"[Camada 2 · {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} · "
        "reavaliação cega de L1 — evidência geométrica automática]\n"
        "Método: docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md §3.1 "
        "(scripts/arete/pil_l2_evidence_check.py).\n"
        f"Evidência no DXF (beams.data_json.links.*_area_segs.contour):\n" + "\n".join(evidence_lines) + "\n"
        f"Ação: redesenhei {name}_qa_L2.svg adicionando {added_desc} — espelhando os campos "
        "já existentes no lado oposto do mesmo segmento de viga (mesma lógica do caso P16).\n"
        "Veredito: INVALIDOU o desenho de L1 (idêntico ao SA, sem a correção materializada). "
        "Peço validação humana da Camada 2 (SVG novo); se ok, fix genérico no motor = builder de "
        "face_beams deve tratar as faces simétricas ao redor do pilar de forma consistente."
    )

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/notes/{name}", timeout=10) as resp:
        doc = json.loads(resp.read().decode("utf-8"))
    notes = doc.get("notes") or {}
    notes[f"aten_pil_ctx_agent_l2_{base}"] = l2_text
    notes[f"aten_pil_ctx_agent_verdict_l2_{base}"] = "invalidou"
    payload = json.dumps({"notes": notes}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/notes/{name}", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    return {"item": name, "added": added, "notes_ok": result.get("ok", False)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    ap.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--pack", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--items", nargs="+", required=True)
    ap.add_argument("--port", type=int, default=18765)
    args = ap.parse_args()

    pack = Path(args.pack)
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    report_by_item = {r["item"]: r for r in report}

    dxf_path, slab_h, slab_n, slab_pts, beams, pillars = load_project(
        Path(args.db), args.project_id, args.obra, args.pav
    )
    pillars_by_name = {p["name"]: p for p in pillars}
    niveis = get_pavimento_niveis_abs(args.obra, args.pav) or {"chegada_abs": 852.19}
    nivel_v = f"{niveis.get('chegada_abs')}cm"

    for name in args.items:
        fi = report_by_item.get(name)
        if not fi:
            print(f"{name:5s} [ERR] sem entrada no relatório")
            continue
        pillar = pillars_by_name.get(name)
        if not pillar:
            print(f"{name:5s} [ERR] pilar não encontrado no DB")
            continue
        try:
            r = apply_item(
                fi, pillar=pillar, dxf_path=dxf_path, slab_h=slab_h, slab_n=slab_n,
                slab_pts=slab_pts, beams=beams, nivel_v=nivel_v, pack=pack,
                obra=args.obra, pav=args.pav, port=args.port,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"{name:5s} [ERR] {exc}")
            continue
        if r.get("skipped"):
            print(f"{name:5s} skip: {r['skipped']}")
        else:
            print(f"{name:5s} OK — adicionado {[a['canto'] for a in r['added']]} — notes_ok={r['notes_ok']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
