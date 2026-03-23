#!/usr/bin/env python3
"""
gerar_pavimento_pilares_formato_real.py
Gera DXF de pilares em grid, no mesmo formato do combined_v*.dxf (robot output).

Fontes:
  - JSON_Pilares/*.json  (Fase-4_Sincronizacao)  → dimensoes e alturas de paineis
  - gerar_dxf_pilares.py (Restored) como referencia de layers e geometria

Layout:
  COLS colunas de células CELL_W x CELL_H (em mm, ×10 a partir dos cm do JSON)
  Dentro de cada célula: 4 faces (A/B/C/D) como LWPOLYLINEs empilhados

Layers (identicos ao robot):
  Paineis        — paineis de forma (branco/preto, ACI 7)
  Cota Secao (2x)— cotas B×H (verde, ACI 3)
  Texto Secao    — textos de face (amarelo, ACI 2)
  NOMENCLATURA   — header pilar (vermelho, ACI 1)
  COTA           — cotas gerais (verde, ACI 3)
  LABEL_ID       — etiqueta de célula (ciano, ACI 3)
  CELL_BORDER    — borda da célula (cinza, ACI 8)

Uso:
  python scripts/gerar_pavimento_pilares_formato_real.py
  python scripts/gerar_pavimento_pilares_formato_real.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1
  python scripts/gerar_pavimento_pilares_formato_real.py --cols 5 --out meu_dxf.dxf
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERRO: ezdxf nao instalado. Execute: pip install ezdxf")
    sys.exit(1)

# ---------------------------------------------------------------------------
# CONSTANTES DE LAYOUT (em mm — correspondentes aos cm do JSON × 10)
# ---------------------------------------------------------------------------
GAP_ENTRE_FACES   = 300.0   # 30 cm → 300 mm
MARGIN            = 300.0   # margem interna da célula
LABEL_RESERVED    = 250.0   # espaço reservado para label no topo
CELL_W            = 3800.0  # largura da célula (mm)
CELL_H            = 4200.0  # altura da célula (mm) — 280 cm × 10 = 2800 + margens
COLS_DEFAULT      = 5       # colunas por linha

# Cores ACI
COR_PAINEIS  = 7    # branco/preto
COR_COTA     = 3    # verde
COR_TEXTO    = 2    # amarelo
COR_NOMENCL  = 1    # vermelho
COR_LABEL    = 3    # ciano
COR_BORDER   = 8    # cinza


# ---------------------------------------------------------------------------
# LAYERS
# ---------------------------------------------------------------------------
LAYER_DEFS = [
    ("Paineis",          COR_PAINEIS),
    ("Cota Secao (2x)",  COR_COTA),
    ("Texto Secao",      COR_TEXTO),
    ("NOMENCLATURA",     COR_NOMENCL),
    ("COTA",             COR_COTA),
    ("LABEL_ID",         COR_LABEL),
    ("CELL_BORDER",      COR_BORDER),
]


def setup_layers(doc):
    for name, color in LAYER_DEFS:
        if name not in doc.layers:
            lyr = doc.layers.new(name)
            lyr.color = color


# ---------------------------------------------------------------------------
# HELPERS DE DADOS JSON
# ---------------------------------------------------------------------------
def h_values(data: dict, face: str) -> list:
    """Retorna lista de alturas de paineis para a face (mm), sem zeros finais."""
    vals = []
    for i in range(1, 6):
        v = float(data.get(f"h{i}_{face}", 0.0) or 0.0)
        vals.append(v * 10.0)   # cm → mm
    while vals and vals[-1] == 0.0:
        vals.pop()
    # Fallback: altura padrao se tudo zero
    if not vals:
        altura = float(data.get("altura", 280.0) or 280.0) * 10.0
        vals = [altura]
    return vals


def face_width_mm(data: dict, face: str) -> float:
    """Largura da face em mm (cm → mm × 10).
    A/C = dimensao maior, B/D = dimensao menor."""
    b = float(data.get("comprimento", data.get("largura_b", 30.0)) or 30.0)
    h = float(data.get("largura",     data.get("largura_h", 30.0)) or 30.0)
    if b <= 0: b = 30.0
    if h <= 0: h = 30.0
    dim_maior = max(b, h) * 10.0
    dim_menor = min(b, h) * 10.0
    return dim_maior if face in ("A", "C") else dim_menor


# ---------------------------------------------------------------------------
# DESENHO DE UM PILAR (dentro de um offset de célula)
# ---------------------------------------------------------------------------
def draw_pilar(msp, pid: str, data: dict, cell_ox: float, cell_oy: float, pav: str):
    """
    Desenha o pilar com 4 faces (A/B/C/D) como LWPOLYLINE empilhados.
    cell_ox, cell_oy = canto inferior esquerdo da célula.
    Conteúdo posicionado com MARGIN interno.
    """
    content_x0 = cell_ox + MARGIN
    content_y0 = cell_oy + MARGIN

    # --- Calcula posições X de cada face ---
    face_widths = {f: face_width_mm(data, f) for f in ("A", "B", "C", "D")}
    total_draw_width = sum(face_widths.values()) + GAP_ENTRE_FACES * 3

    # Centralizar horizontalmente na célula
    available_w = CELL_W - 2 * MARGIN
    x_start = content_x0 + max(0.0, (available_w - total_draw_width) / 2.0)

    x_cursor = x_start
    face_x0 = {}
    for face in ("A", "B", "C", "D"):
        face_x0[face] = x_cursor
        x_cursor += face_widths[face] + GAP_ENTRE_FACES

    # --- Desenha cada face ---
    max_h_total = 0.0
    for face in ("A", "B", "C", "D"):
        fw   = face_widths[face]
        hvals = h_values(data, face)
        fx0  = face_x0[face]
        fy   = content_y0

        for h in hvals:
            if h <= 0:
                continue
            # Painel como LWPOLYLINE fechado
            pts = [
                (fx0,      fy),
                (fx0 + fw, fy),
                (fx0 + fw, fy + h),
                (fx0,      fy + h),
            ]
            pl = msp.add_lwpolyline(pts, close=True)
            pl.dxf.layer = "Paineis"
            fy += h

        h_total = sum(h for h in hvals if h > 0)
        max_h_total = max(max_h_total, h_total)

        # Label da face (abaixo do painel, relativo ao topo do desenho para não ultrapassar célula)
        label_y = content_y0 - 120.0
        cx = fx0 + fw / 2.0
        # Linha vertical de legenda
        msp.add_line(
            (cx, content_y0 - 20),
            (cx, content_y0 - 80),
            dxfattribs={"layer": "COTA"},
        )
        t = msp.add_text(
            f"{pid}.{face}",
            dxfattribs={
                "insert": (cx, content_y0 - 100.0),
                "height": 50.0,
                "layer": "Texto Secao",
            },
        )

    # --- Cota B×H (ASCII only para compatibilidade DXF) ---
    b_val = float(data.get("comprimento", 30.0) or 30.0)
    h_val = float(data.get("largura",     30.0) or 30.0)
    cota_y = content_y0 + max_h_total + 100.0
    cota_label = f"B={b_val:.0f}cm  H={h_val:.0f}cm  alt={max_h_total/10:.0f}cm"
    msp.add_text(
        cota_label,
        dxfattribs={
            "insert": (x_start, cota_y),
            "height": 55.0,
            "layer": "Cota Secao (2x)",
        },
    )

    # --- NOMENCLATURA (ASCII only) ---
    pav_ascii = pav.encode("ascii", "replace").decode("ascii")
    nome_y = cota_y + 150.0
    msp.add_text(
        f"{pav_ascii} - {pid}",
        dxfattribs={
            "insert": (x_start, nome_y),
            "height": 70.0,
            "layer": "NOMENCLATURA",
        },
    )


# ---------------------------------------------------------------------------
# GRID PRINCIPAL
# ---------------------------------------------------------------------------
def build_combined_pilares(json_dir: Path, out_path: Path, obra_name: str,
                            pav: str, cols: int):
    pilar_files = sorted(json_dir.glob("P*.json"),
                         key=lambda p: int("".join(filter(str.isdigit, p.stem)) or "0"))
    if not pilar_files:
        print(f"ERRO: Nenhum P*.json em {json_dir}")
        sys.exit(1)

    print(f"  {len(pilar_files)} pilares encontrados")

    doc = ezdxf.new("R2018")
    setup_layers(doc)
    msp = doc.modelspace()

    row, col = 0, 0
    for jpath in pilar_files:
        pid  = jpath.stem
        data = json.loads(jpath.read_text(encoding="utf-8"))

        cell_ox = col * CELL_W
        cell_oy = -(row + 1) * CELL_H   # negativo para crescer para baixo como combined_v*.dxf

        # Borda da célula
        bx0, bx1 = cell_ox, cell_ox + CELL_W
        by0, by1 = cell_oy, cell_oy + CELL_H
        msp.add_lwpolyline(
            [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)],
            close=True,
            dxfattribs={"layer": "CELL_BORDER"},
        )

        # Label no topo da célula (mesma posição que combined_v*.dxf)
        label = f"{obra_name} | {pid}"
        msp.add_text(
            label,
            dxfattribs={
                "insert": (cell_ox + MARGIN, cell_oy + CELL_H - 180.0),
                "height": 90.0,
                "layer": "LABEL_ID",
            },
        )

        # Desenha o pilar
        try:
            draw_pilar(msp, pid, data, cell_ox, cell_oy, pav)
            print(f"  {pid}: b={data.get('comprimento',30):.0f}cm "
                  f"h={data.get('largura',30):.0f}cm "
                  f"alt={data.get('altura',280):.0f}cm  -> celula [{col},{row}]")
        except Exception as e:
            print(f"  ERRO {pid}: {e}")

        col += 1
        if col >= cols:
            col = 0
            row += 1

    total_rows = row + (1 if col > 0 else 0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_path))

    print(f"\n  Salvo: {out_path}")
    print(f"  Grid: {len(pilar_files)} pilares — {cols} cols × {total_rows} linhas")
    print(f"  Extents: {cols * CELL_W / 1000:.1f}m × {total_rows * CELL_H / 1000:.1f}m")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Gera DXF de pilares no formato robot (combined_v*.dxf)"
    )
    parser.add_argument(
        "--obra",
        default="D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1",
        help="Path da obra (default: Obra_TREINO_1)",
    )
    parser.add_argument(
        "--pav",
        default="TÉRREO",
        help="Nome do pavimento (default: TÉRREO)",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=COLS_DEFAULT,
        help=f"Colunas por linha (default: {COLS_DEFAULT})",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Caminho de saída do DXF",
    )
    args = parser.parse_args()

    obra_path  = Path(args.obra)
    obra_name  = obra_path.name
    json_dir   = obra_path / "Fase-4_Sincronizacao" / "JSON_Pilares"

    if not json_dir.exists():
        print(f"ERRO: {json_dir} nao existe")
        sys.exit(1)

    out_path = (
        Path(args.out)
        if args.out
        else obra_path / "Fase-5_Geracao_Scripts" / "DXF_Pilares" / f"combined_pilares_{obra_name}.dxf"
    )

    print(f"\n=== GERAR DXF PILARES — formato robot ===")
    print(f"  Obra  : {obra_name}")
    print(f"  JSON  : {json_dir}")
    print(f"  Output: {out_path}")
    print(f"  Grid  : {args.cols} cols, CELL={CELL_W:.0f}×{CELL_H:.0f}mm\n")

    build_combined_pilares(json_dir, out_path, obra_name, args.pav, args.cols)


if __name__ == "__main__":
    main()
