#!/usr/bin/env python3
"""
extrair_largura_vigas_fv.py — Extrai largura (B) das vigas do FV DXF.

Descobertas do CAD-6.1 (audit):
  - FV DXF layer "Painéis": DIMENSION(41) — inclui B das vigas (val < 80cm)
  - FV DXF layer "NOMENCLATURA": TEXT "V{n}.C" — labels de ancoragem por viga
  - FV DXF layer "COTA": DIMENSION(5) — valores 64.43, 63.28 = candidatos

Estratégia:
  1. Encontrar posição de cada V{n}.C em "NOMENCLATURA"
  2. Buscar DIMENSION em "Painéis" com val < 80cm mais próximo = B da viga
  3. Fallback: "COTA" DIMENSIONs < 80cm
  4. Fallback: usar vigas_dim.json e estimar B por proporção

Story: CAD-6.2
Usage: python scripts/extrair_largura_vigas_fv.py --obra PATH
"""
import argparse, json, math, re, sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERROR: pip install ezdxf")
    sys.exit(1)


DEFAULT_B = 15.0   # Largura padrão se não encontrar (cm)
B_MIN = 8.0        # Mínimo aceitável (cm) — vigas nunca abaixo disso
B_MAX = 80.0       # Máximo aceitável (cm) — vigas raramente acima disso


def dist2d(p1, p2):
    return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)


def find_fv_dxf(obra_path: Path) -> Path | None:
    """Encontra o FV DXF do 12 PAV."""
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    dxfs = list(fase1.glob("*.dxf")) + list(fase1.glob("*.DXF"))
    # Preferir DXF com "12" e "FV" no nome
    for f in dxfs:
        name_up = f.name.upper()
        if "FV" in name_up and "12" in f.name:
            return f
    # Fallback: qualquer FV
    for f in dxfs:
        if "FV" in f.name.upper():
            return f
    return None


def extract_viga_labels_fv(msp) -> dict:
    """
    Extrai labels V{n}.C do FV DXF.
    Layer "NOMENCLATURA" tem textos como "V19.C", "V22.C".
    Também procura em outras layers.
    Retorna: {vid: (x, y)} — posição do centróide de cada viga no FV
    """
    labels = {}
    # Pattern: V{n}[A-Z]?.C ou V{n}[A-Z]?.c
    pat = re.compile(r'V(\d+[A-Z]?)\.C', re.IGNORECASE)

    for e in msp:
        if e.dxftype() not in ("TEXT", "MTEXT"):
            continue
        try:
            txt = e.plain_text().strip() if e.dxftype() == "MTEXT" else e.dxf.text.strip()
            pos_x = e.dxf.insert.x
            pos_y = e.dxf.insert.y
        except Exception:
            continue

        # Buscar labels V{n}.C (podem ser múltiplos em uma string)
        found = pat.findall(txt)
        for vn in found:
            vid = "V" + vn.upper()
            if vid not in labels:
                labels[vid] = (pos_x, pos_y)

    return labels


def extract_dimensions_from_layer(msp, layer_name: str, val_min: float, val_max: float) -> list:
    """
    Extrai todos os DIMENSION de um layer com valor entre val_min e val_max.
    Retorna: [{val, pos}]
    """
    dims = []
    for e in msp:
        if e.dxftype() != "DIMENSION":
            continue
        try:
            if e.dxf.layer != layer_name:
                continue
            val = e.dxf.actual_measurement
            if val < val_min or val > val_max:
                continue
            pos = (e.dxf.defpoint.x, e.dxf.defpoint.y)
            dims.append({"val": round(val, 2), "pos": pos})
        except Exception:
            continue
    return dims


def find_b_for_viga(viga_pos: tuple, b_dims: list, radius: float = 2000.0) -> dict | None:
    """
    Encontra o DIMENSION de B mais próximo de uma posição de viga.
    """
    best = None
    best_dist = float("inf")

    for dim in b_dims:
        d = dist2d(viga_pos, dim["pos"])
        if d < radius and d < best_dist:
            best_dist = d
            best = {"val": dim["val"], "dist": round(d, 1)}

    return best


def main():
    parser = argparse.ArgumentParser(description='Extrair largura B das vigas do FV DXF')
    parser.add_argument('--obra', required=True)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    fv_path = find_fv_dxf(obra_path)

    if not fv_path:
        print(f"ERRO: FV DXF não encontrado em {obra_path}")
        sys.exit(1)

    print(f"FV DXF: {fv_path.name}")
    doc = ezdxf.readfile(str(fv_path))
    msp = doc.modelspace()

    # 1. Extrair labels V{n}.C
    print("\nExtraindo labels V{n}.C...", end="", flush=True)
    viga_labels = extract_viga_labels_fv(msp)
    print(f" {len(viga_labels)} vigas encontradas: {sorted(viga_labels.keys())}")

    # 2. Extrair DIMENSIONs de "Painéis" com val < 80cm
    print("Extraindo DIMENSIONs de 'Painéis' (B_MIN..B_MAX)...", end="", flush=True)
    paineis_dims = extract_dimensions_from_layer(msp, "Painéis", B_MIN, B_MAX)
    print(f" {len(paineis_dims)} DIMENSIONs — vals: {[d['val'] for d in paineis_dims]}")

    # 3. Extrair DIMENSIONs de "COTA" com val < 80cm
    print("Extraindo DIMENSIONs de 'COTA' (B_MIN..B_MAX)...", end="", flush=True)
    cota_dims = extract_dimensions_from_layer(msp, "COTA", B_MIN, B_MAX)
    print(f" {len(cota_dims)} DIMENSIONs — vals: {[d['val'] for d in cota_dims]}")

    # 4. Extrair DIMENSIONs de "Cota Seção (2x)" se existir
    print("Extraindo DIMENSIONs de 'Cota Seção (2x)'...", end="", flush=True)
    secao_dims = extract_dimensions_from_layer(msp, "Cota Seção (2x)", B_MIN, B_MAX)
    print(f" {len(secao_dims)} DIMENSIONs")

    # 5. Todas as DIMENSIONs pequenas (fallback global)
    all_small_dims = paineis_dims + cota_dims + secao_dims

    # 6. Ler vigas_dim.json para ter lista completa de vigas
    vigas_dim_path = obra_path / "Fase-3_Interpretacao_Extracao" / "Vigas" / "vigas_dim.json"
    all_vids = []
    if vigas_dim_path.exists():
        vigas_dim = json.loads(vigas_dim_path.read_text(encoding='utf-8'))
        all_vids = sorted(vigas_dim.keys(), key=lambda x: (len(x), x))
    else:
        # Usar labels encontrados
        all_vids = sorted(viga_labels.keys(), key=lambda x: (len(x), x))

    # 7. Para cada viga, encontrar B
    result = {}
    for vid in all_vids:
        # Tentar por proximidade ao label V{n}.C
        if vid in viga_labels:
            label_pos = viga_labels[vid]
            found = find_b_for_viga(label_pos, all_small_dims, radius=3000)
            if found:
                confidence = 0.85 if found["dist"] < 500 else 0.70 if found["dist"] < 1500 else 0.50
                result[vid] = {
                    "id": vid,
                    "largura_cm": found["val"],
                    "confidence": confidence,
                    "source": "fv-dxf-proximity",
                    "dist": found["dist"],
                    "label_pos": [round(label_pos[0], 1), round(label_pos[1], 1)]
                }
                continue

        # Fallback: nenhum label V{n}.C encontrado para esta viga
        # Usar valor mais frequente entre os DIMENSIONs pequenos
        if all_small_dims:
            # Usar a mediana dos vals como estimativa
            vals = [d["val"] for d in all_small_dims]
            vals.sort()
            median_b = vals[len(vals)//2]
            result[vid] = {
                "id": vid,
                "largura_cm": median_b,
                "confidence": 0.30,
                "source": "fv-dxf-global-median",
                "note": "Sem label V{n}.C próximo — usando mediana global"
            }
        else:
            result[vid] = {
                "id": vid,
                "largura_cm": DEFAULT_B,
                "confidence": 0.10,
                "source": "default",
                "note": f"Sem dados FV DXF — default {DEFAULT_B}cm"
            }

    # 8. Salvar
    out_path = Path(args.output) if args.output else obra_path / "Fase-3_Interpretacao_Extracao" / "Vigas" / "vigas_largura.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # 9. Relatório
    extraidos = sum(1 for v in result.values() if v["source"] == "fv-dxf-proximity")
    fallback_median = sum(1 for v in result.values() if "median" in v.get("source", ""))
    fallback_default = sum(1 for v in result.values() if v["source"] == "default")

    print(f"\n=== RESULTADO ===")
    print(f"  Vigas com B extraído por proximidade: {extraidos}/{len(result)}")
    print(f"  Fallback mediana global:               {fallback_median}")
    print(f"  Fallback default ({DEFAULT_B}cm):          {fallback_default}")
    print(f"  Output: {out_path}")

    print(f"\n{'Viga':<8} {'B (cm)':<10} {'Conf':<8} {'Fonte'}")
    print("-" * 50)
    for vid, v in sorted(result.items(), key=lambda x: (len(x[0]), x[0])):
        print(f"{vid:<8} {v['largura_cm']:<10} {v['confidence']:<8.2f} {v['source']}")

    # Mostrar DIMENSIONs de B encontrados no FV DXF
    print(f"\n=== DIMENSIONs B em 'Paineis' ({len(paineis_dims)}) ===")
    for d in paineis_dims:
        print(f"  val={d['val']} pos={d['pos']}")

    print(f"\n=== Labels V{{n}}.C encontrados ({len(viga_labels)}) ===")
    for vid, pos in sorted(viga_labels.items(), key=lambda x: (len(x[0]), x[0])):
        print(f"  {vid}: pos=({pos[0]:.0f}, {pos[1]:.0f})")


if __name__ == "__main__":
    main()
