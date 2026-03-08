#!/usr/bin/env python3
"""
gerar_dxf_pilares.py - Gerador DXF headless para pilares (ezdxf).

Replica o output do Robo_Pilares para cada pilar do 12 PAV.
Usa dados das Fases 3 e 4:
  - B/H real: Fase-3/Pilares/pilares_bh.json
  - Distribuicao de paineis (h1..h5): Fase-4/JSON_Pilares/P{n}.json

Layout gerado por pilar (4 faces horizontais):
  [Face A] gap [Face B] gap [Face C] gap [Face D]
  Cada face = retangulos empilhados (h1, h2, h3...) na layer Paineis

Story: CAD-6.5
Usage: python scripts/gerar_dxf_pilares.py --obra PATH [--pav "12 PAV"]
"""
import argparse, json, sys
from pathlib import Path

try:
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
except ImportError:
    print("ERRO: ezdxf nao instalado. Execute: pip install ezdxf")
    sys.exit(1)


# Constantes de layout (unidades: cm)
GAP_ENTRE_FACES = 30.0       # espaco entre faces na horizontal
GAP_ENTRE_PILARES = 80.0     # espaco entre pilares diferentes
ALTURA_DEFAULT = 280.0       # pe direito padrao
B_DEFAULT = 30.0             # comprimento default (cm) se nao extraido
H_DEFAULT = 30.0             # largura default (cm)

# Cores por layer (ACI - AutoCAD Color Index)
COR_PAINEIS   = 7    # branco/preto
COR_COTA      = 3    # verde
COR_TEXTO     = 2    # amarelo
COR_NOMENCL   = 1    # vermelho


def setup_layers(doc):
    """Cria as layers necessarias no documento DXF."""
    layers = doc.layers
    defs = [
        ("Paineis",          COR_PAINEIS),
        ("Cota Secao (2x)",  COR_COTA),
        ("Texto Secao",      COR_TEXTO),
        ("NOMENCLATURA",     COR_NOMENCL),
        ("COTA",             COR_COTA),
    ]
    for name, color in defs:
        if name not in layers:
            layer = layers.new(name)
            layer.color = color


def h_values(data: dict, face: str) -> list:
    """Retorna lista de alturas de paineis para a face (sem zeros no final)."""
    vals = []
    for i in range(1, 6):
        v = float(data.get(f"h{i}_{face}", 0.0) or 0.0)
        vals.append(v)
    # Remove zeros no final
    while vals and vals[-1] == 0.0:
        vals.pop()
    return vals if vals else [ALTURA_DEFAULT]


def draw_face(msp, pid: str, face: str, x0: float, y0: float,
              face_width: float, heights: list):
    """
    Desenha uma face do pilar como paineis empilhados.

    Args:
        msp: modelspace
        pid: ID do pilar (ex: "P1")
        face: letra da face (A/B/C/D)
        x0, y0: canto inferior esquerdo
        face_width: largura do painel (cm)
        heights: lista de alturas [h1, h2, h3, ...]
    """
    y = y0
    for i, h in enumerate(heights):
        if h <= 0:
            continue
        # Painel retangular (LWPOLYLINE fechado)
        pts = [
            (x0, y),
            (x0 + face_width, y),
            (x0 + face_width, y + h),
            (x0, y + h),
        ]
        pline = msp.add_lwpolyline(pts, close=True)
        pline.dxf.layer = "Paineis"
        y += h

    # Label da face
    cx = x0 + face_width / 2.0
    cy = y0 - 15.0  # abaixo do painel
    label = f"{pid}.{face}"
    msp.add_mtext(label, dxfattribs={
        "layer": "Texto Secao",
        "insert": (cx, cy, 0),
        "char_height": 10.0,
        "width": face_width + 20.0,
        "attachment_point": 5,  # MIDDLE_CENTER
    })


def draw_bh_dimension(msp, x0: float, y_top: float,
                      b_val: float, h_val: float, x_extent: float):
    """Adiciona dimensao B x H na layer Cota Secao (2x)."""
    # Texto simples com B x H (substitui DIMENSION real por clareza)
    label = f"B={b_val:.0f}cm  H={h_val:.0f}cm"
    msp.add_mtext(label, dxfattribs={
        "layer": "Cota Secao (2x)",
        "insert": (x0, y_top + 25.0, 0),
        "char_height": 8.0,
        "width": x_extent + 20.0,
        "attachment_point": 5,
    })


def draw_nomenclature(msp, x0: float, y_top: float, pid: str, pav: str):
    """Adiciona header NOMENCLATURA acima do pilar."""
    txt = f"{pav} - {pid}"
    msp.add_mtext(txt, dxfattribs={
        "layer": "NOMENCLATURA",
        "insert": (x0, y_top + 50.0, 0),
        "char_height": 10.0,
        "width": 300.0,
        "attachment_point": 5,
    })


def gerar_dxf_pilar(pid: str, json4: dict, bh: dict,
                    output_path: Path, pav: str) -> dict:
    """
    Gera DXF para um pilar.

    Returns dict com: pid, b, h, n_paineis, path
    """
    # B/H: usa pilares_bh.json se disponivel, senao default
    b = float(bh.get("b", B_DEFAULT))
    h = float(bh.get("h", H_DEFAULT))
    if b <= 0: b = B_DEFAULT
    if h <= 0: h = H_DEFAULT

    # Dimensoes das faces:
    # A e C = dimensao maior (h do pilar = profundidade)
    # B e D = dimensao menor (b do pilar = espessura)
    face_dims = {
        "A": max(b, h),
        "B": min(b, h),
        "C": max(b, h),
        "D": min(b, h),
    }

    doc = ezdxf.new(dxfversion="R2018")
    setup_layers(doc)
    msp = doc.modelspace()

    x_cursor = 0.0
    y_base = 0.0
    n_total_panels = 0

    for face in ["A", "B", "C", "D"]:
        fw = face_dims[face]
        heights = h_values(json4, face)
        n_total_panels += len([hi for hi in heights if hi > 0])
        draw_face(msp, pid, face, x_cursor, y_base, fw, heights)
        x_cursor += fw + GAP_ENTRE_FACES

    total_width = x_cursor - GAP_ENTRE_FACES
    total_height = sum(h_values(json4, "A"))  # height from face A

    draw_bh_dimension(msp, 0.0, total_height, b, h, total_width)
    draw_nomenclature(msp, 0.0, total_height, pid, pav)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output_path))

    return {
        "pid": pid,
        "b": b,
        "h": h,
        "n_paineis": n_total_panels,
        "total_height": total_height,
        "path": str(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Gerar DXF headless para pilares (CAD-6.5)")
    parser.add_argument("--obra", required=True, help="Path da obra")
    parser.add_argument("--pav", default="12 PAV", help="Pavimento (default: 12 PAV)")
    args = parser.parse_args()

    obra = Path(args.obra)
    fase3 = obra / "Fase-3_Interpretacao_Extracao"
    fase4 = obra / "Fase-4_Sincronizacao"
    fase5 = obra / "Fase-5_Geracao_Scripts" / "DXF_Pilares"
    fase5.mkdir(parents=True, exist_ok=True)

    # Carrega B/H extraidos
    bh_path = fase3 / "Pilares" / "pilares_bh.json"
    if bh_path.exists():
        bh_all = json.loads(bh_path.read_text(encoding="utf-8"))
        print(f"  pilares_bh.json: {len(bh_all)} pilares")
    else:
        bh_all = {}
        print("  AVISO: pilares_bh.json nao encontrado, usando defaults B=30 H=30")

    # Lista todos os JSON_Pilares
    json4_dir = fase4 / "JSON_Pilares"
    if not json4_dir.exists():
        print(f"ERRO: {json4_dir} nao existe. Execute motor_fase4.py primeiro.")
        sys.exit(1)

    pilar_jsons = sorted(json4_dir.glob("P*.json"))
    if not pilar_jsons:
        print(f"ERRO: Nenhum P*.json em {json4_dir}")
        sys.exit(1)

    print(f"\n=== GERANDO DXF PILARES ({len(pilar_jsons)} pilares) ===")
    resultados = []
    erros = []

    for jpath in pilar_jsons:
        pid = jpath.stem  # ex: P1
        try:
            json4 = json.loads(jpath.read_text(encoding="utf-8"))
            bh = bh_all.get(pid, {})
            out = fase5 / f"{pid}.dxf"
            res = gerar_dxf_pilar(pid, json4, bh, out, args.pav)
            resultados.append(res)
            conf = "BH-extraido" if bh else "BH-default"
            print(f"  {pid}: b={res['b']:.0f} h={res['h']:.0f} "
                  f"paineis={res['n_paineis']} alt={res['total_height']:.0f}cm [{conf}]")
        except Exception as e:
            erros.append((pid, str(e)))
            print(f"  ERRO {pid}: {e}")

    print(f"\n=== RESULTADO: {len(resultados)} DXFs gerados | {len(erros)} erros ===")
    if erros:
        for pid, msg in erros:
            print(f"  ERRO {pid}: {msg}")

    # Salva relatorio
    rel_path = fase5 / "_relatorio.json"
    rel = {
        "_meta": {
            "total": len(resultados),
            "erros": len(erros),
            "pavimento": args.pav,
            "output_dir": str(fase5),
        },
        "pilares": {r["pid"]: r for r in resultados},
    }
    rel_path.write_text(json.dumps(rel, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Relatorio: {rel_path}")
    print(f"  DXFs em: {fase5}")
    print(f"\n  Proximo: python scripts/comparar_dxf_pilares.py --obra {args.obra}")


if __name__ == "__main__":
    main()
