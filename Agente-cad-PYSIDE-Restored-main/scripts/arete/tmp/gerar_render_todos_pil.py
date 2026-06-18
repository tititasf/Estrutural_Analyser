# -*- coding: utf-8 -*-
"""
gerar_render_todos_pil.py
Gera N4 para P30/P31 (PIL fichas não estão no DB) e renderiza comparação
N4 vs N2 para todos os 7 itens de abertura (P11, P17, P28, P29, P30, P31, P32).
"""
import re
import sys
import shutil
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
ARETE = Path(__file__).parent.parent  # scripts/arete/
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(ARETE))

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

from motor_reverso_pil import extrair_ficha_pilar
from ficha_adapter import materializar_item, rodar_gerador, get_output_dxf_path

RECORTES_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- PL - R00")
N4_OUT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n4")
ITEMS = ['P11', 'P17', 'P28', 'P29', 'P30', 'P31', 'P32']
PAV   = "13_PAV"


def latest_dxf(item: str, folder: Path) -> Path | None:
    sel_cands = sorted(folder.glob(f"PIL_{item}_sel_*.dxf"),
                       key=lambda p: int(re.search(r'(\d+)\.dxf$', p.name).group(1)))
    if sel_cands:
        return sel_cands[-1]
    cands = sorted(folder.glob(f"PIL_{item}_motor_*.dxf"),
                   key=lambda p: int(re.search(r'(\d+)\.dxf$', p.name).group(1)))
    return cands[-1] if cands else None


def gerar_n4_pil(item: str, recorte_path: Path) -> Path | None:
    print(f"  Extraindo ficha {item} ...")
    ficha = extrair_ficha_pilar(str(recorte_path), item)
    row = {
        'classe': 'PIL', 'elemento_id': item,
        'pavimento': PAV, 'campos_json': ficha,
        'recorte_path': str(recorte_path),
    }
    obra_dir, _ = materializar_item(row)
    print(f"  Rodando gerador {item} ...")
    ok, log = rodar_gerador(obra_dir, 'PIL', item)
    if not ok:
        print(f"  [FAIL] {item}: {log[-400:]}")
        return None
    dxf_path = get_output_dxf_path(obra_dir, 'PIL', item)
    if dxf_path.exists():
        dest = N4_OUT / f"PL_preview_{item}.dxf"
        shutil.copy2(str(dxf_path), str(dest))
        print(f"  [OK] {dest}")
        return dest
    print(f"  [FAIL] DXF não gerado: {dxf_path}")
    return None


def get_pain_lines(dxf_path: Path) -> list[tuple]:
    """Extrai linhas da layer Painéis. Retorna lista de (x0,y0,x1,y1)."""
    doc = ezdxf.readfile(str(dxf_path))
    lines = []
    for e in doc.modelspace():
        if e.dxftype() != 'LINE':
            continue
        if 'PAIN' not in e.dxf.layer.upper() and 'PAIN' not in e.dxf.layer:
            continue
        lines.append((
            e.dxf.start.x, e.dxf.start.y,
            e.dxf.end.x,   e.dxf.end.y,
        ))
    return lines


def get_face_extents_n4(dxf_path: Path) -> dict[str, tuple]:
    """Retorna bounding box de cada face ABCD no N4 (coordenadas reais do DXF)."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    # Face labels no N4 ficam em x≈-6935 (drawing region, não plant view)
    face_info: dict[str, dict] = {}
    for e in msp:
        if e.dxftype() != 'TEXT':
            continue
        m = re.match(r'^[A-Z]\d+\.([ABCDEFGH])$', e.dxf.text.strip())
        if m and e.dxf.insert.x < -5000:  # elevation region
            face_info[m.group(1)] = {'lx': e.dxf.insert.x, 'ly': e.dxf.insert.y}
    return face_info


def get_n2_face_extents(dxf_path: Path) -> dict[str, dict]:
    """
    Extrai para cada face ABCD do N2: x do label, x das linhas PAIN,
    y_min/y_max das linhas PAIN.
    """
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    face_label_xs: dict[str, float] = {}
    face_label_ys: list[float] = []
    for e in msp:
        if e.dxftype() == 'TEXT':
            m = re.match(r'^[A-Z]\d+\.([ABCDEFGH])$', e.dxf.text.strip())
            if m:
                face_label_xs[m.group(1)] = e.dxf.insert.x
                face_label_ys.append(e.dxf.insert.y)
    if not face_label_xs:
        return {}
    y_face_base = (min(face_label_ys) - 20.0) if face_label_ys else -1e9
    faces_sorted = sorted(face_label_xs.items(), key=lambda kv: kv[1])
    result = {}
    for i, (face, x_face) in enumerate(faces_sorted):
        if face not in ('A', 'B', 'C', 'D'):
            continue
        x_next = faces_sorted[i+1][1] if i+1 < len(faces_sorted) else x_face + 600.0
        x_mid_l = (faces_sorted[i-1][1] + x_face) / 2 if i > 0 else x_face - 600.0
        x_mid_r = (x_face + x_next) / 2
        xs, ys = [], []
        for e in msp:
            if e.dxftype() != 'LINE': continue
            if 'PAIN' not in e.dxf.layer.upper(): continue
            xc = (e.dxf.start.x + e.dxf.end.x) / 2
            if x_mid_l <= xc <= x_mid_r:
                xs.extend([e.dxf.start.x, e.dxf.end.x])
                ys.extend([e.dxf.start.y, e.dxf.end.y])
        if xs:
            result[face] = {
                'x_mid_l': x_mid_l, 'x_mid_r': x_mid_r,
                'xl': min(xs), 'xr': max(xs),
                'yb': min(ys), 'yt': max(ys),
            }
    return result


def render_face_lines(ax, lines: list[tuple], color: str,
                      x_mid_l: float, x_mid_r: float,
                      yb: float, yt: float, lw: float = 1.2):
    """Plota linhas de uma face no eixo, normalizando para 0..1 space."""
    face_lines = [(x0, y0, x1, y1) for (x0, y0, x1, y1) in lines
                  if x_mid_l <= (x0+x1)/2 <= x_mid_r]
    if not face_lines:
        return
    xvals = [v for (x0,y0,x1,y1) in face_lines for v in (x0,x1)]
    xl = min(xvals)
    xr = max(xvals)
    dx = xr - xl if xr != xl else 1
    dy = yt - yb if yt != yb else 1
    for (x0, y0, x1, y1) in face_lines:
        nx0 = (x0 - xl) / dx
        nx1 = (x1 - xl) / dx
        ny0 = (y0 - yb) / dy
        ny1 = (y1 - yb) / dy
        ax.plot([nx0, nx1], [ny0, ny1], color=color, lw=lw)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_aspect('equal')
    ax.axis('off')


def render_item(item: str, n4_path: Path, n2_path: Path, out_path: Path):
    """Renderiza comparação N4 vs N2 para as 4 faces ABCD lado a lado."""
    n4_lines = get_pain_lines(n4_path)
    n2_lines = get_pain_lines(n2_path)
    n2_extents = get_n2_face_extents(n2_path)

    # Para N4, as faces estão normalizadas na drawing region (x negativo)
    # Precisamos descobrir os extents x de cada face no N4
    doc_n4 = ezdxf.readfile(str(n4_path))
    msp_n4 = doc_n4.modelspace()
    face_labels_n4: dict[str, float] = {}
    face_label_ys_n4: list[float] = []
    for e in msp_n4:
        if e.dxftype() == 'TEXT':
            m = re.match(r'^[A-Z]\d+\.([ABCDEFGH])$', e.dxf.text.strip())
            if m:
                # Pega labels na região de elevação (x < 0 geralmente)
                if e.dxf.insert.x < 0:
                    face_labels_n4[m.group(1)] = e.dxf.insert.x
                    face_label_ys_n4.append(e.dxf.insert.y)

    if not face_labels_n4:
        # Tenta sem filtro de x
        for e in msp_n4:
            if e.dxftype() == 'TEXT':
                m = re.match(r'^[A-Z]\d+\.([ABCDEFGH])$', e.dxf.text.strip())
                if m:
                    face_labels_n4[m.group(1)] = e.dxf.insert.x
                    face_label_ys_n4.append(e.dxf.insert.y)

    y_base_n4 = (min(face_label_ys_n4) - 20.0) if face_label_ys_n4 else -1e9
    faces_sorted_n4 = sorted(face_labels_n4.items(), key=lambda kv: kv[1])

    n4_face_extents: dict[str, dict] = {}
    for i, (face, x_face) in enumerate(faces_sorted_n4):
        if face not in ('A','B','C','D'):
            continue
        x_next = faces_sorted_n4[i+1][1] if i+1 < len(faces_sorted_n4) else x_face + 600.0
        x_mid_l = (faces_sorted_n4[i-1][1] + x_face) / 2 if i > 0 else x_face - 600.0
        x_mid_r = (x_face + x_next) / 2
        xs, ys = [], []
        for (x0,y0,x1,y1) in n4_lines:
            xc = (x0+x1)/2
            if x_mid_l <= xc <= x_mid_r:
                xs.extend([x0,x1]); ys.extend([y0,y1])
        if xs:
            n4_face_extents[face] = {
                'x_mid_l': x_mid_l, 'x_mid_r': x_mid_r,
                'xl': min(xs), 'xr': max(xs),
                'yb': min(ys), 'yt': max(ys),
            }

    faces = [f for f in ('A','B','C','D') if f in n4_face_extents or f in n2_extents]
    if not faces:
        print(f"  [WARN] {item}: nenhuma face encontrada para render")
        return

    n_faces = len(faces)
    fig, axes = plt.subplots(2, n_faces, figsize=(n_faces * 2.5, 7))
    if n_faces == 1:
        axes = [[axes[0]], [axes[1]]]

    fig.suptitle(f"{item} — N4 (azul) vs N2 (vermelho)", fontsize=12, y=1.01)

    for col, face in enumerate(faces):
        ax_n4 = axes[0][col]
        ax_n2 = axes[1][col]

        ax_n4.set_title(f"N4 Face {face}", fontsize=8)
        ax_n2.set_title(f"N2 Face {face}", fontsize=8)

        if face in n4_face_extents:
            ext = n4_face_extents[face]
            render_face_lines(ax_n4, n4_lines, '#0044cc',
                              ext['x_mid_l'], ext['x_mid_r'],
                              ext['yb'], ext['yt'])
        else:
            ax_n4.axis('off')
            ax_n4.text(0.5, 0.5, 'sem dados', ha='center', va='center', fontsize=7)

        if face in n2_extents:
            ext2 = n2_extents[face]
            render_face_lines(ax_n2, n2_lines, '#cc0000',
                              ext2['x_mid_l'], ext2['x_mid_r'],
                              ext2['yb'], ext2['yt'])
        else:
            ax_n2.axis('off')
            ax_n2.text(0.5, 0.5, 'sem dados', ha='center', va='center', fontsize=7)

    plt.tight_layout()
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  [RENDER] {out_path.name}")


def main():
    N4_OUT.mkdir(parents=True, exist_ok=True)

    # 1. Gerar N4 para itens faltando
    missing = [i for i in ITEMS if not (N4_OUT / f"PL_preview_{i}.dxf").exists()]
    if missing:
        print(f"\n=== Gerando N4 para: {missing} ===")
        for item in missing:
            rec = latest_dxf(item, RECORTES_DIR)
            if rec is None:
                print(f"  [SKIP] {item}: sem recorte DXF")
                continue
            gerar_n4_pil(item, rec)

    # 2. Renderizar comparação para todos os 7 itens
    print(f"\n=== Renderizando comparações ===")
    for item in ITEMS:
        n4_path = N4_OUT / f"PL_preview_{item}.dxf"
        n2_path = latest_dxf(item, RECORTES_DIR)

        if not n4_path.exists():
            print(f"  [SKIP] {item}: N4 não existe")
            continue
        if n2_path is None:
            print(f"  [SKIP] {item}: N2 não encontrado")
            continue

        out = N4_OUT / f"qc_{item}.png"
        try:
            render_item(item, n4_path, n2_path, out)
        except Exception as exc:
            print(f"  [ERR] {item}: {exc}")
            import traceback
            traceback.print_exc()

    print("\nDone.")


if __name__ == "__main__":
    main()
