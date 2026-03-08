#!/usr/bin/env python3
"""
gerar_dxf_lajes.py - Gerador DXF headless para lajes (ezdxf).

Replica o output do Robo_Lajes usando os JSONs da Fase 4 (JSON_Lajes).

Layout por laje (planta baixa / top view):
  - Poligono externo (coordenadas) na layer "Contorno"
  - Paineis divididos pelas linhas_verticais e linhas_horizontais
  - Obstaculos (se houver) como retangulos hachurados

Story: CAD-6.7
Usage: python scripts/gerar_dxf_lajes.py --obra PATH
"""
import argparse, json, sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERRO: ezdxf nao instalado. Execute: pip install ezdxf")
    sys.exit(1)


COR_CONTORNO = 7
COR_PAINEL   = 3
COR_TEXTO    = 2
COR_OBST     = 1


def setup_layers(doc):
    defs = [
        ("Contorno",        COR_CONTORNO),
        ("Paineis",         COR_PAINEL),
        ("Texto Secao",     COR_TEXTO),
        ("NOMENCLATURA",    COR_TEXTO),
        ("Obstaculos",      COR_OBST),
    ]
    for name, color in defs:
        if name not in doc.layers:
            doc.layers.new(name).color = color


def draw_polygon(msp, coords: list, layer: str):
    """Desenha poligono LWPOLYLINE a partir de lista de [x, y]."""
    pts = [(c[0], c[1]) for c in coords]
    pline = msp.add_lwpolyline(pts, close=True)
    pline.dxf.layer = layer


def draw_panels(msp, comp: float, larg: float,
                linhas_v: list, linhas_h: list):
    """
    Desenha paineis da laje como retangulos.

    linhas_v: posicoes x das divisoes verticais (incluindo comp no final)
    linhas_h: posicoes y das divisoes horizontais (incluindo larg no final)
    """
    # Garante que o limite da laje esta incluido
    xs = sorted(set([0.0] + [float(l["value"]) for l in linhas_v]))
    ys = sorted(set([0.0] + [float(l["value"]) for l in linhas_h]))

    if not xs or xs[-1] < comp:
        xs.append(comp)
    if not ys or ys[-1] < larg:
        ys.append(larg)

    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            x0, x1 = xs[i], xs[i + 1]
            y0, y1 = ys[j], ys[j + 1]
            if (x1 - x0) <= 0 or (y1 - y0) <= 0:
                continue
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            pline = msp.add_lwpolyline(pts, close=True)
            pline.dxf.layer = "Paineis"


def gerar_dxf_laje(lid: str, data: dict, output_path: Path, pav: str) -> dict:
    """Gera DXF de uma laje (planta baixa de formas)."""
    doc = ezdxf.new(dxfversion="R2018")
    setup_layers(doc)
    msp = doc.modelspace()

    comp = float(data.get("comprimento", 100.0) or 100.0)
    larg = float(data.get("largura", 100.0) or 100.0)
    coords = data.get("coordenadas", [])
    linhas_v = data.get("linhas_verticais", [])
    linhas_h = data.get("linhas_horizontais", [])
    obstaculos = data.get("obstaculos", [])

    # Contorno externo
    if coords and len(coords) >= 3:
        draw_polygon(msp, coords, "Contorno")
    else:
        # Retangulo padrao se sem coordenadas
        rect = [[0, 0], [comp, 0], [comp, larg], [0, larg], [0, 0]]
        draw_polygon(msp, rect, "Contorno")

    # Paineis internos
    draw_panels(msp, comp, larg, linhas_v, linhas_h)

    # Obstaculos
    for ob in obstaculos:
        if not ob.get("active", False):
            continue
        ox = float(ob.get("x", 0) or 0)
        oy = float(ob.get("y", 0) or 0)
        ow = float(ob.get("width", 0) or 0)
        oh = float(ob.get("height", 0) or 0)
        if ow > 0 and oh > 0:
            pts = [(ox, oy), (ox + ow, oy), (ox + ow, oy + oh), (ox, oy + oh)]
            pline = msp.add_lwpolyline(pts, close=True)
            pline.dxf.layer = "Obstaculos"

    # Label
    cx = comp / 2.0
    cy = larg / 2.0
    msp.add_mtext(lid, dxfattribs={
        "layer": "Texto Secao",
        "insert": (cx, cy, 0),
        "char_height": max(10.0, comp * 0.05),
        "width": comp,
        "attachment_point": 5,
    })

    # Dimensoes
    n_paineis_v = len(linhas_v) + 1 if linhas_v else 1
    n_paineis_h = len(linhas_h) + 1 if linhas_h else 1
    header = f"{pav} - {lid}  {comp:.1f}x{larg:.1f}cm  paineis: {n_paineis_v}x{n_paineis_h}"
    msp.add_mtext(header, dxfattribs={
        "layer": "NOMENCLATURA",
        "insert": (0.0, larg + 30.0, 0),
        "char_height": 10.0,
        "width": comp + 20.0,
        "attachment_point": 5,
    })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output_path))

    return {
        "lid": lid,
        "comprimento": comp,
        "largura": larg,
        "area_cm2": comp * larg,
        "n_paineis_v": n_paineis_v,
        "n_paineis_h": n_paineis_h,
        "n_obstaculos": sum(1 for o in obstaculos if o.get("active", False)),
        "path": str(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Gerar DXF headless para lajes (CAD-6.7)")
    parser.add_argument("--obra", required=True)
    parser.add_argument("--pav", default="12 PAV")
    args = parser.parse_args()

    obra = Path(args.obra)
    lajes_dir = obra / "Fase-4_Sincronizacao" / "JSON_Lajes"
    out_dir   = obra / "Fase-5_Geracao_Scripts" / "DXF_Lajes"
    out_dir.mkdir(parents=True, exist_ok=True)

    laje_jsons = sorted(lajes_dir.glob("L*.json"),
                        key=lambda p: (len(p.stem), p.stem))
    if not laje_jsons:
        print(f"ERRO: Nenhum L*.json em {lajes_dir}")
        sys.exit(1)

    print(f"\n=== GERANDO DXF LAJES ({len(laje_jsons)} lajes) ===")
    resultados = []
    erros = []

    for jpath in laje_jsons:
        lid = jpath.stem
        try:
            data = json.loads(jpath.read_text(encoding="utf-8"))
            out = out_dir / f"{lid}.dxf"
            res = gerar_dxf_laje(lid, data, out, args.pav)
            resultados.append(res)
            print(f"  {lid}: {res['comprimento']:.1f}x{res['largura']:.1f}cm "
                  f"paineis={res['n_paineis_v']}x{res['n_paineis_h']} "
                  f"area={res['area_cm2']:.0f}cm2")
        except Exception as e:
            erros.append((lid, str(e)))
            print(f"  ERRO {lid}: {e}")

    print(f"\n=== RESULTADO: {len(resultados)} DXFs gerados | {len(erros)} erros ===")
    if erros:
        for lid, msg in erros:
            print(f"  ERRO {lid}: {msg}")

    rel_path = out_dir / "_relatorio.json"
    rel = {
        "_meta": {
            "total": len(resultados),
            "erros": len(erros),
            "pavimento": args.pav,
            "output_dir": str(out_dir),
        },
        "lajes": {r["lid"]: r for r in resultados},
    }
    rel_path.write_text(json.dumps(rel, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Relatorio: {rel_path}")
    print(f"  DXFs em: {out_dir}")
    print(f"\n  Proximo: python scripts/comparar_dxf.py --obra {args.obra}")


if __name__ == "__main__":
    main()
