"""Regenera N3 (ABCD/GRADES) com visual NOVA via o motor geral.

NÃO contém lógica de geometria por item. O padrão correto vive em:
  scripts/pl_abcd_visual_nova.enrich_payload_for_abcd_nova
  scripts/gerar_pl_dxf_stog.generate_pilar_zone (_prepare_pj_for_visual)

Uso:
  py -3.12 scripts/arete/regen_pl_n3_para_visual.py --item P1
  py -3.12 scripts/arete/regen_pl_n3_para_visual.py --item P2 P3
  py -3.12 scripts/arete/regen_pl_n3_para_visual.py --all
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pl_abcd_visual_nova import enrich_payload_for_abcd_nova  # noqa: E402
from gerar_pl_dxf_stog import setup_doc, generate_pilar_zone  # noqa: E402
from visual_modes import apply_visual_mode, normalize_visual_mode  # noqa: E402


def _optional_sa_levels(item: str, db_path: Path | None) -> float | None:
    """Opcional: maior nível de laje no SA. Sem path/DB → None (motor usa contrato)."""
    if db_path is None or not db_path.is_file():
        return None
    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        # project_id não é fixo: pega o mais recente com esse name
        row = conn.execute(
            "SELECT extra_data_json FROM pillars WHERE name=? "
            "ORDER BY rowid DESC LIMIT 1",
            (item,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        extra = json.loads(row[0] or "{}")
        top = None
        for fid in "ABCD":
            v = extra.get(f"p_s{fid}_l1_v")
            if v is None:
                continue
            try:
                lv = float(str(v).replace(",", "."))
            except Exception:
                continue
            top = lv if top is None else max(top, lv)
        return top
    except Exception as exc:
        print("sa levels skip:", exc)
        return None


def _regen_one(
    *,
    item: str,
    var_dir: Path,
    design_dir: Path | None,
    db_path: Path | None,
    visual_mode: str = "NOVA",
) -> None:
    json_path = var_dir / f"{item}.json"
    if not json_path.exists():
        # fallback Fase-4
        alt = var_dir.parents[1] / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item}.json"
        if alt.exists():
            json_path = alt
        else:
            print(f"SKIP missing {item}")
            return
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    sa_top = _optional_sa_levels(item, db_path)
    payload = enrich_payload_for_abcd_nova(payload, pillar_top_level=sa_top)
    # grava ao lado da variante se pasta n3_variants
    out_json = var_dir / f"{item}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        item,
        "intervals",
        {f: payload.get(f"paineis_intervals_{f}") for f in "ABCD"},
        "rebaixo",
        {f: payload.get(f"rebaixo_laje_{f}") for f in "ABCD"},
    )
    visual = normalize_visual_mode(visual_mode)
    for zone in ("abcd", "grades"):
        doc = setup_doc()
        count = generate_pilar_zone(
            doc.modelspace(), payload, zone, visual_mode=visual
        )
        # Perfil final INI (MLINE) ou NOVA (noop) — mesma geometria base.
        # Path canônico sem sufixo: o Comparison Engine carrega exatamente
        # PL_*_preview_{item}.dxf e o seletor INI/NOVA reescreve esse arquivo.
        apply_visual_mode(doc, visual, "PL")
        out = var_dir / f"PL_{zone.upper()}_preview_{item}.dxf"
        doc.saveas(str(out))
        print(f"  wrote {out.name} entities={count} mode={visual}")
        # Cópia opcional de laboratório (Desing-Visual-DXF) com sufixo de modo.
        if design_dir and design_dir.exists() and zone == "abcd":
            suffix = "" if visual == "NOVA" else f"_{visual}"
            dst = design_dir / f"PL_ABCD_preview_{item}_PARA_GERADO{suffix}.dxf"
            shutil.copy2(out, dst)
            print("  copy", dst.name)


def main() -> None:
    ap = argparse.ArgumentParser(description="Regen N3 ABCD NOVA (motor geral)")
    ap.add_argument("--item", nargs="*", default=None, help="Itens (ex. P1 P2). Default: --all se vazio com --all")
    ap.add_argument("--all", action="store_true", help="Todos os P*.json da pasta de variantes")
    ap.add_argument(
        "--obra",
        default=r"D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1",
        help="Pasta da obra (contém Fase-6_Execucao_CAD)",
    )
    ap.add_argument(
        "--db",
        default=r"D:/Agente-cad-PYSIDE/project_data.vision",
        help="SQLite SA opcional para níveis de laje",
    )
    ap.add_argument(
        "--design-dir",
        default=r"D:/Agente-cad-PYSIDE/Desing-Visual-DXF",
        help="Cópia opcional do DXF ABCD gerado",
    )
    ap.add_argument(
        "--visual-mode",
        choices=["NOVA", "INI"],
        default="NOVA",
        help="Perfil visual final (geometria idêntica; INI aplica MLINE)",
    )
    ap.add_argument(
        "--variant",
        choices=["para", "passa", "both"],
        default="para",
        help="Pasta n3_variants (para / passa / both) — mesmas regras de desenho",
    )
    args = ap.parse_args()
    obra = Path(args.obra)
    variants = (
        ["para", "passa"] if args.variant == "both" else [args.variant]
    )
    db_path = Path(args.db) if args.db else None
    design = Path(args.design_dir) if args.design_dir else None

    for variant in variants:
        var_dir = obra / "Fase-6_Execucao_CAD" / "n3_variants" / variant
        if not var_dir.exists():
            if variant == "para":
                var_dir = obra / "Fase-6_Execucao_CAD"
            else:
                print(f"SKIP variant {variant}: missing {var_dir}")
                continue
        var_dir.mkdir(parents=True, exist_ok=True)

        if args.all or not args.item:
            items = sorted({p.stem for p in var_dir.glob("P*.json")})
            if not items:
                f4 = obra / "Fase-4_Sincronizacao" / "JSON_Pilares"
                items = (
                    sorted({p.stem for p in f4.glob("P*.json")})
                    if f4.exists()
                    else []
                )
        else:
            items = list(args.item)
        if not items:
            print(f"SKIP variant {variant}: nenhum item")
            continue
        print(f"=== variant={variant} mode={args.visual_mode} ===")
        for item in items:
            _regen_one(
                item=item,
                var_dir=var_dir,
                design_dir=design if variant == "para" else None,
                db_path=db_path,
                visual_mode=args.visual_mode,
            )


if __name__ == "__main__":
    main()
