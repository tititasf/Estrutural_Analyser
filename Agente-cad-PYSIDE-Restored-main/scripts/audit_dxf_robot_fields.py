#!/usr/bin/env python3
"""
audit_dxf_robot_fields.py — Auditoria completa dos DXFs STOG vs. campos dos robôs.

Inspeciona PL, LV, FV, LJ DXFs e produz:
  - DXF_ROBOT_FIELDMAP.json: campo_robo → layer → entity_type → status
  - DXF_AUDIT_REPORT.md: relatório humano-legível

Story: CAD-6.1
Usage: python scripts/audit_dxf_robot_fields.py --obra PATH
"""
import argparse, json, sys, math
from pathlib import Path
from collections import defaultdict

try:
    import ezdxf
except ImportError:
    print("ERROR: pip install ezdxf")
    sys.exit(1)


# ==============================================================================
# DXF INSPECTION
# ==============================================================================

def dist2d(p1, p2):
    return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)


def inspect_dxf(dxf_path: Path) -> dict:
    """
    Inspeciona um DXF e retorna:
    - layers: {name: {count, entity_types: {type: count}}}
    - sample_texts: {layer: [texto, ...]} — até 5 amostras
    - sample_dims: {layer: [valor, ...]} — até 5 valores de DIMENSION
    - lwpolylines: {layer: [{n_vertices, is_closed, bbox_area}]}
    - total_entities: int
    """
    result = {
        "file": dxf_path.name,
        "total_entities": 0,
        "layers": defaultdict(lambda: {"count": 0, "entity_types": defaultdict(int)}),
        "sample_texts": defaultdict(list),
        "sample_dims": defaultdict(list),
        "lwpolylines": defaultdict(list),
        "lines": defaultdict(int),
    }

    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        result["error"] = str(e)
        return result

    msp = doc.modelspace()

    for e in msp:
        etype = e.dxftype()
        try:
            layer = e.dxf.layer
        except Exception:
            layer = "0"

        result["total_entities"] += 1
        result["layers"][layer]["count"] += 1
        result["layers"][layer]["entity_types"][etype] += 1

        # Coletar textos
        if etype in ("TEXT", "MTEXT") and len(result["sample_texts"][layer]) < 10:
            try:
                txt = e.plain_text().strip() if etype == "MTEXT" else e.dxf.text.strip()
                if txt:
                    result["sample_texts"][layer].append(txt[:80])
            except Exception:
                pass

        # Coletar valores de DIMENSION
        if etype == "DIMENSION" and len(result["sample_dims"][layer]) < 10:
            try:
                val = e.dxf.actual_measurement
                pos = (e.dxf.defpoint.x, e.dxf.defpoint.y)
                result["sample_dims"][layer].append({"val": round(val, 2), "pos": [round(pos[0], 0), round(pos[1], 0)]})
            except Exception:
                pass

        # Analisar LWPOLYLINE
        if etype == "LWPOLYLINE":
            try:
                pts = list(e.get_points())
                n = len(pts)
                closed = e.closed
                if n >= 3:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    # Área pelo método shoelace
                    area = 0.0
                    for i in range(n):
                        j = (i + 1) % n
                        area += xs[i] * ys[j]
                        area -= xs[j] * ys[i]
                    area = abs(area) / 2.0
                    result["lwpolylines"][layer].append({
                        "n_vertices": n,
                        "is_closed": bool(closed),
                        "bbox_area": round(area, 1),
                        "bbox_x": [round(min(xs), 1), round(max(xs), 1)],
                        "bbox_y": [round(min(ys), 1), round(max(ys), 1)],
                        "insert": [round(xs[0], 1), round(ys[0], 1)]
                    })
            except Exception:
                pass

        # Contar LINE
        if etype == "LINE":
            result["lines"][layer] += 1

    # Converter defaultdicts para dicts normais
    result["layers"] = {k: {"count": v["count"], "entity_types": dict(v["entity_types"])}
                        for k, v in result["layers"].items()}
    result["sample_texts"] = dict(result["sample_texts"])
    result["sample_dims"] = dict(result["sample_dims"])
    result["lwpolylines"] = {k: v for k, v in result["lwpolylines"].items() if v}
    result["lines"] = dict(result["lines"])

    return result


# ==============================================================================
# FIND DXF FILES
# ==============================================================================

def find_stog_dxfs(obra_path: Path) -> dict:
    """Encontra DXFs STOG: PL, LV, FV, LJ, EVG."""
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    all_dxfs = list(fase1.glob("*.dxf")) + list(fase1.glob("*.DXF"))

    result = {"PL": [], "LV": [], "FV": [], "LJ": [], "EVG": [], "OTHER": []}
    seen = set()

    for f in all_dxfs:
        if f.name in seen:
            continue
        seen.add(f.name)
        name_up = f.name.upper()
        if "- PL" in name_up or name_up.endswith("PL.DXF"):
            result["PL"].append(f)
        elif "- LV" in name_up or name_up.endswith("LV.DXF"):
            result["LV"].append(f)
        elif "- FV" in name_up or name_up.endswith("FV.DXF"):
            result["FV"].append(f)
        elif "- LJ" in name_up or name_up.endswith("LJ.DXF"):
            result["LJ"].append(f)
        elif "EVG" in name_up:
            result["EVG"].append(f)
        else:
            result["OTHER"].append(f)

    return result


# ==============================================================================
# FIELD MAPPING ANALYSIS
# ==============================================================================

def analyze_fieldmap(inspections: dict) -> dict:
    """
    Analisa as inspeções e produz o mapeamento campo_robô → DXF.
    """
    fieldmap = {}

    # ---------- PILARES ----------
    pl_data = inspections.get("PL")
    if pl_data:
        pl_layers = pl_data.get("layers", {})
        pl_texts = pl_data.get("sample_texts", {})
        pl_dims = pl_data.get("sample_dims", {})
        pl_lwp = pl_data.get("lwpolylines", {})

        fieldmap["pilar.comprimento_largura"] = {
            "source": "PL DXF",
            "layer": "Cota Seção (2x)",
            "entity_type": "DIMENSION",
            "method": "inverse-proximity ao label P{n}.face",
            "status": "EXTRAIDO",
            "samples": pl_dims.get("Cota Seção (2x)", [])[:3]
        }

        fieldmap["pilar.h1_h5_por_face"] = {
            "source": "COMPUTED",
            "formula": "h1=2, h2=244, h3=resta (para altura=280: h3=34)",
            "status": "COMPUTADO",
            "note": "Fórmula legada determinística — não precisa leitura DXF"
        }

        # Painéis
        paineis_layer = None
        for layer_name in pl_layers:
            if "PAINE" in layer_name.upper() or "PANEL" in layer_name.upper():
                paineis_layer = layer_name
                break

        fieldmap["pilar.larg1_3_por_face"] = {
            "source": "PL DXF" if paineis_layer else "DEFAULT",
            "layer": paineis_layer,
            "entity_types_found": pl_layers.get(paineis_layer, {}).get("entity_types", {}) if paineis_layer else {},
            "lwpolylines_found": pl_lwp.get(paineis_layer, [])[:3] if paineis_layer else [],
            "status": "AUDITADO_PRESENTE" if paineis_layer else "AUDITADO_ZERO",
            "note": "Se 0 no motor_fase4.py, o robô calcula automaticamente na UI"
        }

        # Parafusos
        par_layer = None
        for layer_name in pl_layers:
            if "PARAF" in layer_name.upper() or "BOLT" in layer_name.upper():
                par_layer = layer_name
                break

        fieldmap["pilar.par_1_2_a_8_9"] = {
            "source": "PL DXF" if par_layer else "DEFAULT_ZERO",
            "layer": par_layer,
            "entity_types_found": pl_layers.get(par_layer, {}).get("entity_types", {}) if par_layer else {},
            "status": "AUDITADO_PRESENTE" if par_layer else "AUDITADO_ZERO",
            "note": "0 padrão no motor — confirmar se PL DXF tem dados por pilar"
        }

        # Grades
        grade_layer = None
        for layer_name in pl_layers:
            if "GRADE" in layer_name.upper() or "ARMAD" in layer_name.upper():
                grade_layer = layer_name
                break

        fieldmap["pilar.grade_1_3"] = {
            "source": "PL DXF" if grade_layer else "DEFAULT_ZERO",
            "layer": grade_layer,
            "entity_types_found": pl_layers.get(grade_layer, {}).get("entity_types", {}) if grade_layer else {},
            "status": "AUDITADO_PRESENTE" if grade_layer else "AUDITADO_ZERO",
        }

        # Todos os layers PL para referência
        fieldmap["_PL_ALL_LAYERS"] = {
            k: {"count": v["count"], "types": v["entity_types"]}
            for k, v in sorted(pl_layers.items())
        }

    # ---------- VIGAS LATERAIS ----------
    lv_data = inspections.get("LV")
    if lv_data:
        lv_layers = lv_data.get("layers", {})
        lv_dims = lv_data.get("sample_dims", {})
        lv_texts = lv_data.get("sample_texts", {})
        lv_lwp = lv_data.get("lwpolylines", {})

        fieldmap["viga.total_height"] = {
            "source": "LV DXF",
            "layer": "Cota Seção (2x)",
            "entity_type": "DIMENSION",
            "method": "nearest DIMENSION 20-400cm ao label V{n}.face",
            "status": "EXTRAIDO",
            "samples": lv_dims.get("Cota Seção (2x)", [])[:3]
        }

        fieldmap["viga.comprimento"] = {
            "source": "LV DXF",
            "layer": "COTA",
            "entity_type": "DIMENSION",
            "method": "MAX DIMENSION >= 100cm em raio 800 do label V{n}.A",
            "status": "EXTRAIDO",
            "samples": lv_dims.get("COTA", [])[:3]
        }

        # Furos
        furos_layer = None
        for layer_name in lv_layers:
            if "FURO" in layer_name.upper() or "HOLE" in layer_name.upper() or "BOLT" in layer_name.upper():
                furos_layer = layer_name
                break

        fieldmap["viga.holes"] = {
            "source": "LV DXF" if furos_layer else "DEFAULT_ZERO",
            "layer": furos_layer,
            "entity_types_found": lv_layers.get(furos_layer, {}).get("entity_types", {}) if furos_layer else {},
            "status": "AUDITADO_PRESENTE" if furos_layer else "AUDITADO_ZERO",
        }

        fieldmap["_LV_ALL_LAYERS"] = {
            k: {"count": v["count"], "types": v["entity_types"]}
            for k, v in sorted(lv_layers.items())
        }

    # ---------- FUNDO VIGAS — total_width ----------
    fv_data = inspections.get("FV")
    if fv_data:
        fv_layers = fv_data.get("layers", {})
        fv_dims = fv_data.get("sample_dims", {})
        fv_texts = fv_data.get("sample_texts", {})
        fv_lwp = fv_data.get("lwpolylines", {})

        # Procurar layer com dimensões pequenas (B da viga tipicamente 12-40cm)
        dim_layers_small = {}
        for layer_name, dims in fv_dims.items():
            small = [d for d in dims if d["val"] < 60 and d["val"] > 5]
            if small:
                dim_layers_small[layer_name] = small

        fieldmap["viga.total_width_fundo"] = {
            "source": "FV DXF",
            "candidate_layers": dim_layers_small,
            "all_dim_samples": {k: v[:5] for k, v in fv_dims.items()},
            "status": "AUDITADO_PRESENTE" if dim_layers_small else "DESCONHECIDO",
            "note": "total_width = espessura da viga (B cm) — procurar DIMENSION < 60cm por viga"
        }

        fieldmap["_FV_ALL_LAYERS"] = {
            k: {"count": v["count"], "types": v["entity_types"]}
            for k, v in sorted(fv_layers.items())
        }

        # Textos do FV para entender nomenclatura
        fieldmap["_FV_SAMPLE_TEXTS"] = {k: v[:5] for k, v in fv_texts.items()}

    # ---------- LAJES — coordenadas ----------
    lj_data = inspections.get("LJ")
    if lj_data:
        lj_layers = lj_data.get("layers", {})
        lj_lwp = lj_data.get("lwpolylines", {})
        lj_texts = lj_data.get("sample_texts", {})
        lj_dims = lj_data.get("sample_dims", {})

        # Procurar LWPOLYLINE com grande área (contorno da laje)
        large_polys = {}
        for layer_name, polys in lj_lwp.items():
            big = [p for p in polys if p["bbox_area"] > 50000]  # > 500m² em unidades DXF
            if big:
                large_polys[layer_name] = big[:3]

        fieldmap["laje.coordenadas"] = {
            "source": "LJ DXF",
            "candidate_layers_with_large_lwpoly": large_polys,
            "all_lwpoly_layers": {k: v[:3] for k, v in lj_lwp.items()},
            "status": "AUDITADO_PRESENTE" if large_polys else "DESCONHECIDO",
            "note": "coordenadas = LWPOLYLINE fechada com maior área perto do label L{n}"
        }

        fieldmap["laje.comprimento_largura"] = {
            "source": "LJ DXF",
            "layer": "AUX00",
            "entity_type": "MTEXT",
            "method": "parse 'L{n}\\n{dim1}X{dim2}' — dim1 x dim2 em cm",
            "status": "EXTRAIDO",
            "samples": lj_texts.get("AUX00", [])[:5]
        }

        # Linhas para linhas_verticais/horizontais
        line_layers = {k: v for k, v in lj_data.get("lines", {}).items() if v > 5}
        fieldmap["laje.linhas_internas"] = {
            "source": "LJ DXF",
            "line_rich_layers": line_layers,
            "status": "COMPUTADO" if not line_layers else "AUDITADO_PRESENTE",
            "note": "linhas_verticais computadas cada 100cm; horizontais podem estar em LINE entities"
        }

        fieldmap["_LJ_ALL_LAYERS"] = {
            k: {"count": v["count"], "types": v["entity_types"]}
            for k, v in sorted(lj_layers.items())
        }

        fieldmap["_LJ_SAMPLE_TEXTS"] = {k: v[:5] for k, v in lj_texts.items()}

    return fieldmap


# ==============================================================================
# REPORT GENERATOR
# ==============================================================================

def generate_report(inspections: dict, fieldmap: dict) -> str:
    lines = ["# DXF Audit Report — CAD-ANALYZER", "", f"**Data:** 2026-03-08 | **Story:** CAD-6.1", ""]

    # Sumário por DXF
    lines.append("## 1. Sumário DXF Files\n")
    for dtype in ["PL", "LV", "FV", "LJ", "EVG"]:
        data = inspections.get(dtype)
        if not data:
            lines.append(f"- **{dtype}:** não encontrado\n")
            continue
        total = data.get("total_entities", 0)
        n_layers = len(data.get("layers", {}))
        lines.append(f"- **{dtype}** `{data['file']}`: {total} entidades, {n_layers} layers\n")

    # Layers por DXF
    for dtype in ["PL", "LV", "FV", "LJ"]:
        data = inspections.get(dtype)
        if not data:
            continue
        lines.append(f"\n## 2.{dtype} Layers\n")
        layers = data.get("layers", {})
        # Sort by count desc
        for lname, ldata in sorted(layers.items(), key=lambda x: -x[1]["count"]):
            types_str = ", ".join(f"{t}:{c}" for t, c in ldata["entity_types"].items())
            lines.append(f"- `{lname}` ({ldata['count']} ents): {types_str}")
        lines.append("")

    # Field Mapping
    lines.append("\n## 3. Field Mapping — Campo Robô → DXF\n")
    lines.append("| Campo | Status | Layer | Method |")
    lines.append("|-------|--------|-------|--------|")

    for field, info in fieldmap.items():
        if field.startswith("_"):
            continue
        status = info.get("status", "?")
        layer = info.get("layer", info.get("source", "?"))
        method = info.get("method", info.get("note", info.get("formula", "?"))[:60])
        lines.append(f"| `{field}` | {status} | {layer} | {method} |")

    # Gaps críticos
    lines.append("\n## 4. Gaps Críticos\n")
    for field, info in fieldmap.items():
        if field.startswith("_"):
            continue
        status = info.get("status", "?")
        if status in ("DESCONHECIDO", "AUDITADO_ZERO"):
            lines.append(f"### {field}")
            lines.append(f"- Status: {status}")
            if "note" in info:
                lines.append(f"- Nota: {info['note']}")
            if "candidate_layers" in info:
                lines.append(f"- Candidatos: {list(info['candidate_layers'].keys())}")
            lines.append("")

    # Descobertas LWPOLYLINE (lajes)
    lj = inspections.get("LJ")
    if lj and lj.get("lwpolylines"):
        lines.append("\n## 5. LWPOLYLINE no LJ DXF (candidatos para polígono de laje)\n")
        for layer_name, polys in sorted(lj["lwpolylines"].items()):
            lines.append(f"### Layer: `{layer_name}` ({len(polys)} polígonos)")
            for p in polys[:5]:
                lines.append(f"  - {p['n_vertices']} verts | closed={p['is_closed']} | area={p['bbox_area']:.0f} | bbox_x={p['bbox_x']} bbox_y={p['bbox_y']}")
            lines.append("")

    # DIMENSIONs do FV DXF
    fv = inspections.get("FV")
    if fv and fv.get("sample_dims"):
        lines.append("\n## 6. DIMENSIONs no FV DXF (candidatos para largura_fundo)\n")
        for layer_name, dims in sorted(fv["sample_dims"].items()):
            lines.append(f"### Layer: `{layer_name}`")
            for d in dims[:8]:
                lines.append(f"  - val={d['val']} | pos={d['pos']}")
            lines.append("")

    # Textos FV + LJ
    for dtype, label in [("FV", "Fundo Vigas"), ("LJ", "Lajes")]:
        data = inspections.get(dtype)
        if data and data.get("sample_texts"):
            lines.append(f"\n## 7. Textos {label} ({dtype} DXF)\n")
            for layer_name, texts in sorted(data["sample_texts"].items()):
                if texts:
                    lines.append(f"**Layer `{layer_name}`:** {' | '.join(texts[:5])}")
            lines.append("")

    return "\n".join(lines)


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description='Auditar DXFs STOG e mapear campos dos robôs')
    parser.add_argument('--obra', required=True, help='Path da obra')
    parser.add_argument('--output-dir', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    out_dir = Path(args.output_dir) if args.output_dir else obra_path / "Fase-3_Interpretacao_Extracao" / "Audit_DXF"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Encontrar DXFs
    dxf_map = find_stog_dxfs(obra_path)
    print("\n=== DXFs Encontrados ===")
    for dtype, files in dxf_map.items():
        for f in files:
            print(f"  {dtype}: {f.name}")

    # Inspecionar cada tipo
    inspections = {}
    for dtype in ["PL", "LV", "FV", "LJ", "EVG"]:
        files = dxf_map.get(dtype, [])
        if not files:
            print(f"  [WARN] {dtype} não encontrado")
            continue
        f = files[0]  # usar primeiro arquivo de cada tipo
        print(f"\nInspecionando {dtype}: {f.name} ...", end="", flush=True)
        data = inspect_dxf(f)
        inspections[dtype] = data
        print(f" {data['total_entities']} entidades, {len(data.get('layers',{}))} layers")

    # Salvar inspeção raw
    raw_path = out_dir / "dxf_inspection_raw.json"
    with open(raw_path, "w", encoding="utf-8") as fp:
        json.dump(inspections, fp, indent=2, ensure_ascii=False, default=str)
    print(f"\nInspeção raw salva: {raw_path}")

    # Análise de field mapping
    print("\nAnalisando field mapping...")
    fieldmap = analyze_fieldmap(inspections)

    fieldmap_path = out_dir / "DXF_ROBOT_FIELDMAP.json"
    with open(fieldmap_path, "w", encoding="utf-8") as fp:
        json.dump(fieldmap, fp, indent=2, ensure_ascii=False, default=str)
    print(f"Field map salvo: {fieldmap_path}")

    # Gerar relatório
    report = generate_report(inspections, fieldmap)
    report_path = out_dir / "DXF_AUDIT_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as fp:
        fp.write(report)
    print(f"Relatório salvo: {report_path}")

    # Sumário no console
    print("\n=== RESUMO FIELD MAP ===")
    print(f"{'Campo':<35} {'Status':<20} {'Fonte'}")
    print("-" * 75)
    for field, info in fieldmap.items():
        if field.startswith("_"):
            continue
        status = info.get("status", "?")
        source = info.get("source", "?")
        icon = "✅" if status in ("EXTRAIDO", "COMPUTADO") else ("⚠️" if status == "AUDITADO_PRESENTE" else "❌")
        print(f"{icon} {field:<33} {status:<20} {source}")

    # Destacar gaps
    print("\n=== GAPS CRÍTICOS ===")
    for field, info in fieldmap.items():
        if field.startswith("_"):
            continue
        status = info.get("status", "?")
        if status not in ("EXTRAIDO", "COMPUTADO", "AUDITADO_ZERO"):
            print(f"  ❌ {field}: {status} — {info.get('note', '')}")

    print(f"\n=== OUTPUT ===")
    print(f"  {raw_path}")
    print(f"  {fieldmap_path}")
    print(f"  {report_path}")


if __name__ == "__main__":
    main()
