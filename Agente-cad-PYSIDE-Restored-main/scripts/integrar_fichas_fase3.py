#!/usr/bin/env python3
"""
integrar_fichas_fase3.py - Integra todas as fontes Fase 3 em vigas.json e lajes.json completos.

Fontes para vigas:
  - vigas_dim.json: comprimento + altura_lateral (h)
  - vigas_largura.json: largura_cm (b)

Fontes para lajes:
  - lajes_poligono.json: coordenadas + comprimento + largura

Story: CAD-6.4
Usage: python scripts/integrar_fichas_fase3.py --obra PATH
"""
import argparse, json, sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Integrar fichas Fase 3 completas')
    parser.add_argument('--obra', required=True)
    args = parser.parse_args()

    obra = Path(args.obra)
    fase3 = obra / "Fase-3_Interpretacao_Extracao"

    # ── VIGAS ──────────────────────────────────────────────────────────────────
    print("=== VIGAS ===")
    vigas_dim_path   = fase3 / "Vigas" / "vigas_dim.json"
    vigas_larg_path  = fase3 / "Vigas" / "vigas_largura.json"
    vigas_out_path   = fase3 / "Vigas" / "vigas.json"

    if not vigas_dim_path.exists():
        print(f"  ERRO: vigas_dim.json nao encontrado em {vigas_dim_path}")
        sys.exit(1)
    if not vigas_larg_path.exists():
        print(f"  ERRO: vigas_largura.json nao encontrado em {vigas_larg_path}")
        sys.exit(1)

    vigas_dim  = json.loads(vigas_dim_path.read_text(encoding='utf-8'))
    vigas_larg = json.loads(vigas_larg_path.read_text(encoding='utf-8'))

    vigas_merged = {}
    for vid, dim_data in vigas_dim.items():
        if vid.startswith("_"):
            continue
        larg_data = vigas_larg.get(vid, {})

        h = float(dim_data.get("altura_lateral_cm", 0))   # Altura lateral = h da viga
        b = float(larg_data.get("largura_cm", 15.0))      # Largura = b (espessura)
        comprimento = float(dim_data.get("comprimento_cm", 0))

        if h <= 0:
            print(f"  AVISO: Viga {vid}: altura_lateral=0, usando h=40")
            h = 40.0
        if comprimento <= 0:
            print(f"  AVISO: Viga {vid}: comprimento=0, pulando")
            continue

        vigas_merged[vid] = {
            "b": b,
            "h": h,
            "comprimento": comprimento,
            "confidence": round(
                (dim_data.get("confidence", 0.7) + larg_data.get("confidence", 0.5)) / 2, 3
            ),
            "source": f"vigas_dim+{larg_data.get('source', 'default')}",
            "sides": dim_data.get("sides", ["A", "B"])
        }

    vigas_merged["_meta"] = {
        "total": len(vigas_merged) - 1,  # -1 for _meta
        "pavimento": "12 PAV",
        "integrado_em": "2026-03-08",
        "fontes": ["vigas_dim.json", "vigas_largura.json"]
    }

    with open(vigas_out_path, "w", encoding="utf-8") as f:
        json.dump(vigas_merged, f, indent=2, ensure_ascii=False)

    total_v = len([k for k in vigas_merged if not k.startswith("_")])
    print(f"  vigas.json atualizado: {total_v} vigas")
    for vid, v in sorted([(k,v) for k,v in vigas_merged.items() if not k.startswith("_")],
                          key=lambda x: (len(x[0]), x[0])):
        print(f"    {vid}: b={v['b']}cm h={v['h']}cm L={v['comprimento']}cm")

    # ── LAJES ──────────────────────────────────────────────────────────────────
    print("\n=== LAJES ===")
    lajes_poly_path = fase3 / "Lajes" / "lajes_poligono.json"
    lajes_out_path  = fase3 / "Lajes" / "lajes.json"

    if not lajes_poly_path.exists():
        print(f"  ERRO: lajes_poligono.json nao encontrado. Execute CAD-6.3 primeiro.")
        sys.exit(1)

    lajes_poly = json.loads(lajes_poly_path.read_text(encoding='utf-8'))

    lajes_merged = {}
    for lid, poly_data in lajes_poly.items():
        if lid.startswith("_"):
            continue
        comp = poly_data.get("comprimento", 0) or 0
        larg = poly_data.get("largura", 0) or 0
        coords = poly_data.get("coordenadas", []) or []

        if comp <= 0 or larg <= 0:
            print(f"  AVISO: Laje {lid}: dimensoes invalidas, usando 100x100")
            comp, larg = 100.0, 100.0

        if not coords:
            coords = [[0.0,0.0],[comp,0.0],[comp,larg],[0.0,larg],[0.0,0.0]]

        lajes_merged[lid] = {
            "comprimento": comp,
            "largura": larg,
            "coordenadas": coords,
            "area_cm2": round(comp * larg, 1),
            "confidence": poly_data.get("confidence", 0.4),
            "source": poly_data.get("source", "unknown"),
            "modo_selecionado": 0
        }

    lajes_merged["_meta"] = {
        "total": len(lajes_merged) - 1,
        "pavimento": "12 PAV",
        "integrado_em": "2026-03-08",
        "fontes": ["lajes_poligono.json"]
    }

    with open(lajes_out_path, "w", encoding="utf-8") as f:
        json.dump(lajes_merged, f, indent=2, ensure_ascii=False)

    total_l = len([k for k in lajes_merged if not k.startswith("_")])
    print(f"  lajes.json atualizado: {total_l} lajes")
    for lid, v in sorted([(k,v) for k,v in lajes_merged.items() if not k.startswith("_")],
                          key=lambda x: (len(x[0]), x[0])):
        src = v.get("source","?")[:20]
        print(f"    {lid}: {v['comprimento']}x{v['largura']}cm area={v['area_cm2']:.0f} [{src}]")

    print(f"\n=== INTEGRACAO COMPLETA: {total_v} vigas + {total_l} lajes ===")
    print(f"  Proximos passos: python scripts/motor_fase4.py --obra {args.obra}")


if __name__ == "__main__":
    main()
