"""Re-enriquece e regenera todos os n3_variants com o motor NOVA universal.

Uso:
  py -3.12 scripts/arete/regen_n3_variants_nova.py
  py -3.12 scripts/arete/regen_n3_variants_nova.py --item P1 P2 P3
  py -3.12 scripts/arete/regen_n3_variants_nova.py --variant para
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from gerar_pl_dxf_stog import setup_doc, generate_pilar_zone  # noqa: E402
from pl_abcd_visual_nova import enrich_payload_for_abcd_nova  # noqa: E402
from visual_modes import apply_visual_mode, normalize_visual_mode  # noqa: E402


def _sanitize_payload(payload: dict) -> dict:
    """Limpa malha/rebaixo legados antes do enrich."""
    p = dict(payload)
    p.pop("_pl_nova_enriched", None)
    for fid in "ABCDEFGH":
        p.pop(f"paineis_intervals_{fid}", None)
        try:
            r = float(p.get(f"rebaixo_laje_{fid}") or 0.0)
        except (TypeError, ValueError):
            r = 0.0
        if r > 40.0:
            p[f"rebaixo_laje_{fid}"] = 0.0
    p["modo_distribuicao"] = "NOVA"
    return p


def _regen_one(
    json_path: Path,
    *,
    visual: str = "NOVA",
) -> dict:
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    payload = enrich_payload_for_abcd_nova(_sanitize_payload(raw))
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    item = json_path.stem
    var_dir = json_path.parent
    visual = normalize_visual_mode(visual)
    wrote = {}
    for zone in ("abcd", "grades"):
        doc = setup_doc()
        zone_pj = json.loads(json.dumps(payload))
        count = generate_pilar_zone(
            doc.modelspace(), zone_pj, zone, visual_mode=visual
        )
        if count < 0:
            continue
        apply_visual_mode(doc, visual, "PL")
        out = var_dir / f"PL_{zone.upper()}_preview_{item}.dxf"
        doc.saveas(str(out))
        wrote[zone] = count
    return {
        "item": item,
        "variant": var_dir.name,
        "intervals": {f: payload.get(f"paineis_intervals_{f}") for f in "ABCD"},
        "rebaixo": {f: payload.get(f"rebaixo_laje_{f}") for f in "ABCD"},
        "ents": wrote,
        "enriched": bool(payload.get("_pl_nova_enriched")),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Regen n3_variants com motor NOVA")
    ap.add_argument(
        "--obra",
        default=r"D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1",
    )
    ap.add_argument("--item", nargs="*", default=None, help="P1 P2 … default: todos")
    ap.add_argument(
        "--variant",
        choices=["para", "passa", "both"],
        default="both",
    )
    ap.add_argument("--visual-mode", choices=["NOVA", "INI"], default="NOVA")
    args = ap.parse_args()
    obra = Path(args.obra)
    variants = (
        ["para", "passa"] if args.variant == "both" else [args.variant]
    )
    items = {s.upper() for s in (args.item or [])} or None
    for mode in variants:
        root = obra / "Fase-6_Execucao_CAD" / "n3_variants" / mode
        if not root.is_dir():
            print(f"SKIP missing {root}")
            continue
        print(f"=== {mode} ===")
        for jf in sorted(root.glob("P*.json")):
            if items is not None and jf.stem.upper() not in items:
                continue
            try:
                info = _regen_one(jf, visual=args.visual_mode)
                print(
                    info["item"],
                    "iv",
                    info["intervals"],
                    "reb",
                    info["rebaixo"],
                    "ents",
                    info["ents"],
                    "enr",
                    info["enriched"],
                )
            except Exception as exc:
                print(f"FAIL {jf.name}: {exc}")


if __name__ == "__main__":
    main()
