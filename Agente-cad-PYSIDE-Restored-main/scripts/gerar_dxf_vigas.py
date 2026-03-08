#!/usr/bin/env python3
"""
gerar_dxf_vigas.py - Gerador DXF headless para vigas (ezdxf).

Replica o output dos robos Robo_Laterais_de_Vigas + Robo_Fundos_de_Vigas.
Usa os JSONs da Fase 4 (JSON_Vigas_Laterais + JSON_Vigas_Fundo).

Layout por viga (3 vistas verticais empilhadas):
  [Lateral A: paineis horizontais de 120cm × h_viga]
  gap
  [Lateral B: idem]
  gap
  [Fundo C: paineis horizontais de 120cm × b_viga]

Story: CAD-6.6
Usage: python scripts/gerar_dxf_vigas.py --obra PATH
"""
import argparse, json, sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERRO: ezdxf nao instalado. Execute: pip install ezdxf")
    sys.exit(1)


GAP_ENTRE_VISTAS = 40.0   # espaco vertical entre lateral A, B e fundo
COR_PAINEIS = 7
COR_TEXTO   = 2
COR_COTA    = 3


def setup_layers(doc):
    defs = [
        ("Paineis",         COR_PAINEIS),
        ("Texto Secao",     COR_TEXTO),
        ("NOMENCLATURA",    COR_TEXTO),
        ("Cota Secao (2x)", COR_COTA),
    ]
    for name, color in defs:
        if name not in doc.layers:
            doc.layers.new(name).color = color


def panels_from_json(data: dict) -> list:
    """Retorna lista de (width, height) dos paineis nao-zero."""
    result = []
    for p in data.get("panels", []):
        w = float(p.get("width", 0) or 0)
        h = float(p.get("height1", 0) or 0)
        if w > 0 and h > 0:
            result.append((w, h))
    return result


def draw_vista(msp, panels: list, x0: float, y0: float, label: str):
    """
    Desenha uma vista (lateral ou fundo) horizontalmente.

    Cada painel e um retangulo (largura x altura) disposto da esq. para dir.
    Returns: x_max, y_max
    """
    x = x0
    y_max = y0
    for (pw, ph) in panels:
        pts = [(x, y0), (x + pw, y0), (x + pw, y0 + ph), (x, y0 + ph)]
        pline = msp.add_lwpolyline(pts, close=True)
        pline.dxf.layer = "Paineis"
        x += pw
        y_max = max(y_max, y0 + ph)

    x_max = x

    # Label
    if panels:
        cx = (x0 + x_max) / 2.0
        msp.add_mtext(label, dxfattribs={
            "layer": "Texto Secao",
            "insert": (cx, y0 - 15.0, 0),
            "char_height": 8.0,
            "width": x_max - x0 + 20.0,
            "attachment_point": 5,
        })

    return x_max, y_max


def gerar_dxf_viga(vid: str, data_a: dict, data_b: dict, data_fundo: dict,
                   output_path: Path, pav: str) -> dict:
    """Gera DXF de uma viga com 3 vistas."""
    doc = ezdxf.new(dxfversion="R2018")
    setup_layers(doc)
    msp = doc.modelspace()

    panels_a     = panels_from_json(data_a)
    panels_b     = panels_from_json(data_b)
    panels_fundo = panels_from_json(data_fundo)

    y_cursor = 0.0

    # Vista Lateral A
    if panels_a:
        x_max_a, y_max_a = draw_vista(msp, panels_a, 0.0, y_cursor, f"{vid}_A")
        y_cursor = y_max_a + GAP_ENTRE_VISTAS
    else:
        x_max_a = 0.0

    # Vista Lateral B
    if panels_b:
        x_max_b, y_max_b = draw_vista(msp, panels_b, 0.0, y_cursor, f"{vid}_B")
        y_cursor = y_max_b + GAP_ENTRE_VISTAS
    else:
        x_max_b = 0.0

    # Vista Fundo
    if panels_fundo:
        x_max_c, y_max_c = draw_vista(msp, panels_fundo, 0.0, y_cursor, f"{vid}_Fundo")
        y_cursor = y_max_c + GAP_ENTRE_VISTAS
    else:
        x_max_c = 0.0

    total_width = max(x_max_a, x_max_b, x_max_c)

    # NOMENCLATURA
    b = float(data_a.get("total_width", 0) or 0)
    h = float(data_a.get("total_height", 0) or 0)
    comprimento = sum(pw for pw, ph in panels_a)
    header = f"{pav} - {vid}  b={b:.0f}cm  h={h:.0f}cm  L={comprimento:.0f}cm"
    msp.add_mtext(header, dxfattribs={
        "layer": "NOMENCLATURA",
        "insert": (0.0, y_cursor, 0),
        "char_height": 9.0,
        "width": total_width + 20.0,
        "attachment_point": 5,
    })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output_path))

    return {
        "vid": vid,
        "b": b,
        "h": h,
        "comprimento": comprimento,
        "n_paineis_a": len(panels_a),
        "n_paineis_b": len(panels_b),
        "n_paineis_fundo": len(panels_fundo),
        "path": str(output_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Gerar DXF headless para vigas (CAD-6.6)")
    parser.add_argument("--obra", required=True)
    parser.add_argument("--pav", default="12 PAV")
    args = parser.parse_args()

    obra = Path(args.obra)
    lat_dir  = obra / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais"
    fundo_dir = obra / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo"
    out_dir  = obra / "Fase-5_Geracao_Scripts" / "DXF_Vigas"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Descobre todos os IDs de vigas a partir dos arquivos V{n}_A.json
    vigas_ids = sorted(set(
        p.stem.rsplit("_", 1)[0]
        for p in lat_dir.glob("*_A.json")
    ), key=lambda v: (len(v), v))

    if not vigas_ids:
        print(f"ERRO: Nenhum V*_A.json em {lat_dir}")
        sys.exit(1)

    print(f"\n=== GERANDO DXF VIGAS ({len(vigas_ids)} vigas) ===")
    resultados = []
    erros = []

    for vid in vigas_ids:
        try:
            path_a     = lat_dir / f"{vid}_A.json"
            path_b     = lat_dir / f"{vid}_B.json"
            vid_num    = vid.replace("V", "")
            path_fundo = fundo_dir / f"V{vid_num}_fundo.json"

            data_a     = json.loads(path_a.read_text(encoding="utf-8")) if path_a.exists() else {}
            data_b     = json.loads(path_b.read_text(encoding="utf-8")) if path_b.exists() else {}
            data_fundo = json.loads(path_fundo.read_text(encoding="utf-8")) if path_fundo.exists() else {}

            out = out_dir / f"{vid}.dxf"
            res = gerar_dxf_viga(vid, data_a, data_b, data_fundo, out, args.pav)
            resultados.append(res)
            print(f"  {vid}: b={res['b']:.0f} h={res['h']:.0f} L={res['comprimento']:.0f}cm "
                  f"| paineis A={res['n_paineis_a']} B={res['n_paineis_b']} F={res['n_paineis_fundo']}")
        except Exception as e:
            erros.append((vid, str(e)))
            print(f"  ERRO {vid}: {e}")

    print(f"\n=== RESULTADO: {len(resultados)} DXFs gerados | {len(erros)} erros ===")
    if erros:
        for vid, msg in erros:
            print(f"  ERRO {vid}: {msg}")

    # Salva relatorio
    rel_path = out_dir / "_relatorio.json"
    rel = {
        "_meta": {
            "total": len(resultados),
            "erros": len(erros),
            "pavimento": args.pav,
            "output_dir": str(out_dir),
        },
        "vigas": {r["vid"]: r for r in resultados},
    }
    rel_path.write_text(json.dumps(rel, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Relatorio: {rel_path}")
    print(f"  DXFs em: {out_dir}")
    print(f"\n  Proximo: python scripts/comparar_dxf_vigas.py --obra {args.obra}")


if __name__ == "__main__":
    main()
