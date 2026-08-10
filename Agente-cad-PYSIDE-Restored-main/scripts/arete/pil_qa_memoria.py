#!/usr/bin/env python
"""Memória de QA dos pilares — consolida atenções ESTRUTURADAS em:

  1. `qa_memoria/blocklist_vinculos.json`  — vínculos que o humano reprovou
     (`acao=geometria_invalida`). O SA/QA deve consultar antes de religar a
     mesma geometria e tentar a próxima candidata. Pedido humano registrado
     em P12/P13/P14 (2026-08-07).

  2. `qa_memoria/dataset_correcoes.jsonl` — todo apontamento estruturado + a
     assinatura estrutural do item. É o dataset rotulado que calibra as
     checagens do QA e, adiante, alimenta a camada de precedente (§3.4).

**Não grava nada no schema N1** (regra 1 do CLAUDE.md: schema do SA é imutável).
A memória é side-car, versionável, fora do pack — sobrevive a re-export.

Uso:
  py -3.12 scripts/arete/pil_qa_memoria.py build --pack <pack>      # consolida
  py -3.12 scripts/arete/pil_qa_memoria.py show                     # lista blocklist
  py -3.12 scripts/arete/pil_qa_memoria.py check --item P13 --nome V316  # consulta
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM_DIR = Path(__file__).resolve().parent / "qa_memoria"
BLOCKLIST = MEM_DIR / "blocklist_vinculos.json"
DATASET = MEM_DIR / "dataset_correcoes.jsonl"


def _load_blocklist() -> dict:
    if not BLOCKLIST.is_file():
        return {"schema": "pil.blocklist.v1", "updated_at": None, "entries": []}
    try:
        d = json.loads(BLOCKLIST.read_text(encoding="utf-8"))
        d.setdefault("entries", [])
        return d
    except Exception:
        return {"schema": "pil.blocklist.v1", "updated_at": None, "entries": []}


def is_blocked(obra: str, pav: str, item: str, *, nome: str = "", face: str = "", canto: str = "") -> bool:
    """Consulta pública — usar antes de (re)vincular uma geometria."""
    for e in _load_blocklist().get("entries", []):
        if (e.get("obra"), e.get("pav"), e.get("item")) != (obra, pav, item):
            continue
        if nome and e.get("nome") and e["nome"] != nome:
            continue
        if face and e.get("face") and e["face"] != face:
            continue
        if canto and e.get("canto") and e["canto"] != canto:
            continue
        return True
    return False


def structural_signature(pillar: dict, tables: dict) -> str:
    """Assinatura abstrata do item (para agrupar casos equivalentes)."""
    faces = (tables or {}).get("faces") or {}
    parts = []
    for fid in "ABCD":
        fam = []
        for kind in ("lajes", "passa", "chega", "interior"):
            n = len([r for r in (faces.get(fid) or {}).get(kind) or []
                     if (r.get("nome") or "") not in ("", "—", "-", "nenhuma")])
            if n:
                fam.append(f"{kind}:{n}")
        parts.append(f"{fid}[{','.join(fam)}]")
    orient = (tables or {}).get("orientation") or pillar.get("orientation") or "?"
    xs = [p[0] for p in pillar.get("points") or []]
    ys = [p[1] for p in pillar.get("points") or []]
    dims = ""
    if xs and ys:
        dims = f"{round(max(xs)-min(xs))}x{round(max(ys)-min(ys))}"
    return f"{orient}|{dims}|" + " ".join(parts)


def build(pack: Path, obra: str, pav: str) -> dict:
    MEM_DIR.mkdir(parents=True, exist_ok=True)
    bl = _load_blocklist()
    existing = {(e.get("obra"), e.get("pav"), e.get("item"), e.get("face"),
                 e.get("canto"), e.get("nome")) for e in bl["entries"]}

    sigs = {}
    try:
        sys.path.insert(0, str(ROOT))
        from scripts.arete.pil_agentic_highlight_draw import load_project
        from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar
        from src.core.niveis_extractor import get_pavimento_niveis_abs
        dxf, sh, sn, sp, beams, pillars = load_project(
            ROOT.parent / "project_data.vision",
            "dd238e47-1dc6-4f63-a760-4e7ce19a7386", obra, pav)
        niv = get_pavimento_niveis_abs(obra, pav) or {"chegada_abs": 852.19}
        for p in pillars:
            t = build_abcd_tables_from_pillar(
                p, slab_height_map=sh, slab_nivel_map=sn, slab_points_map=sp,
                beams=beams, nivel_viga_default=f"{niv.get('chegada_abs')}cm")
            sigs[p["name"]] = structural_signature(p, t)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] assinatura estrutural indisponível: {exc}")

    rows = []
    n_new_block = 0
    for f in sorted((pack / "pilares").glob("P*.notes.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        item = doc.get("page")
        notes = doc.get("notes") or {}
        raw = next((v for k, v in notes.items() if k.startswith("aten_pil_struct_")), "")
        if not raw:
            continue
        try:
            entries = json.loads(raw)
        except Exception:
            continue
        livre = next((v for k, v in notes.items() if k.startswith("aten_pil_ctx_human_")), "") or ""
        for e in entries:
            if not e.get("acao"):
                continue
            rec = {
                "obra": obra, "pav": pav, "item": item,
                "acao": e.get("acao"), "face": e.get("face", ""), "canto": e.get("canto", ""),
                "papel": e.get("papel", ""), "nome": e.get("nome", ""), "obs": e.get("obs", ""),
                "assinatura": sigs.get(item, ""),
                "contexto_livre": livre.strip()[:400],
                "registrado_em": doc.get("updated_at"),
            }
            rows.append(rec)
            if e.get("acao") == "geometria_invalida":
                key = (obra, pav, item, e.get("face", ""), e.get("canto", ""), e.get("nome", ""))
                if key not in existing:
                    bl["entries"].append({
                        "obra": obra, "pav": pav, "item": item,
                        "face": e.get("face", ""), "canto": e.get("canto", ""),
                        "nome": e.get("nome", ""),
                        "motivo": e.get("obs", "") or "geometria vinculada reprovada pelo humano",
                        "origem": "atencao_estruturada",
                        "criado_em": datetime.now(timezone.utc).isoformat(),
                    })
                    existing.add(key)
                    n_new_block += 1

    bl["updated_at"] = datetime.now(timezone.utc).isoformat()
    BLOCKLIST.write_text(json.dumps(bl, ensure_ascii=False, indent=2), encoding="utf-8")
    with DATASET.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    return {"apontamentos": len(rows), "blocklist_novos": n_new_block,
            "blocklist_total": len(bl["entries"])}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--pack", required=True)
    b.add_argument("--obra", default="Obra_TREINO_1")
    b.add_argument("--pav", default="13_PAV")
    sub.add_parser("show")
    c = sub.add_parser("check")
    c.add_argument("--item", required=True)
    c.add_argument("--nome", default="")
    c.add_argument("--obra", default="Obra_TREINO_1")
    c.add_argument("--pav", default="13_PAV")
    args = ap.parse_args()

    if args.cmd == "build":
        r = build(Path(args.pack), args.obra, args.pav)
        print(f"[OK] apontamentos estruturados: {r['apontamentos']}")
        print(f"[OK] blocklist: +{r['blocklist_novos']} novos (total {r['blocklist_total']})")
        print(f"     {BLOCKLIST}")
        print(f"     {DATASET}")
    elif args.cmd == "show":
        bl = _load_blocklist()
        print(f"blocklist ({len(bl['entries'])} entradas) — {BLOCKLIST}")
        for e in bl["entries"]:
            print(f"  {e['item']:5s} face={e.get('face') or '*':2s} canto={e.get('canto') or '*':3s} "
                  f"nome={e.get('nome') or '*':8s} — {e.get('motivo','')[:70]}")
    else:
        print("BLOQUEADO" if is_blocked(args.obra, args.pav, args.item, nome=args.nome) else "livre")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
