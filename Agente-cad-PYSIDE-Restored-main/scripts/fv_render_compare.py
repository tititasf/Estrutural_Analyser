# -*- coding: utf-8 -*-
"""
fv_render_compare.py — Renderiza recorte N2 e N4 gerado lado a lado para comparação visual.
Uso: python scripts/fv_render_compare.py <elem_id>
     python scripts/fv_render_compare.py --all
"""
import sys, io, json, re, argparse, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

PROJ = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main")
RECORTES_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- FV - R00_motor")
OUTPUT_DIR = Path("D:/Agente-cad-PYSIDE/sandbox_fv_arete")

sys.path.insert(0, str(PROJ / "scripts"))


def find_recorte(elem_id):
    """Find the motor recorte DXF for a given element ID."""
    pattern = f"FV_{elem_id}_motor_*.dxf"
    matches = list(RECORTES_DIR.glob(pattern))
    return matches[0] if matches else None


def render_dxf_to_png(dxf_path, png_path, title="", zoom_bbox=None):
    """Render a DXF to PNG using ezdxf + matplotlib."""
    import ezdxf
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    
    fig, ax = plt.subplots(1, 1, figsize=(16, 8), facecolor='#0a0a14')
    ax.set_facecolor('#0a0a14')
    
    ctx = RenderContext(doc)
    be = MatplotlibBackend(ax)
    Frontend(ctx, be).draw_layout(msp, finalize=True)
    
    if zoom_bbox:
        ax.set_xlim(zoom_bbox[0], zoom_bbox[1])
        ax.set_ylim(zoom_bbox[2], zoom_bbox[3])
    
    ax.set_aspect('equal', adjustable='box')
    ax.set_title(title, color='white', fontsize=11, pad=6)
    
    plt.tight_layout()
    plt.savefig(str(png_path), dpi=150, bbox_inches='tight', facecolor='#0a0a14')
    plt.close()


def get_elem_bbox(dxf_path, elem_id):
    """Get bounding box of the target element's polys in the recorte."""
    import ezdxf
    from motor_reverso_fv import _poly_bboxes, _nomenclatura_labels, _base_code, _elem_codes, _row_polys_for_label
    
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    
    polys = _poly_bboxes(msp)
    if not polys:
        return None
    
    target = _base_code(elem_id).upper()
    noms = _nomenclatura_labels(msp)
    own = [n for n in noms if target in _elem_codes(n[0])]
    
    if not own:
        # Fallback: use all polys
        x_min = min(p[0] for p in polys)
        x_max = max(p[1] for p in polys)
        y_min = min(p[2] for p in polys)
        y_max = max(p[3] for p in polys)
    else:
        # Get polys attributed to this element
        from motor_reverso_fv import Y_TOL_ROW
        own_rows = sorted(set((round(y, 1), round(x, 1)) for (_, x, y) in own),
                          key=lambda xy: -xy[0])
        all_polys = []
        for (nom_y, nom_x) in own_rows:
            fp = _row_polys_for_label(polys, nom_x, nom_y, noms, target)
            if fp:
                all_polys.extend(fp)
        
        if not all_polys:
            x_min = min(p[0] for p in polys)
            x_max = max(p[1] for p in polys)
            y_min = min(p[2] for p in polys)
            y_max = max(p[3] for p in polys)
        else:
            x_min = min(p[0] for p in all_polys)
            x_max = max(p[1] for p in all_polys)
            y_min = min(p[2] for p in all_polys)
            y_max = max(p[3] for p in all_polys)
    
    # Add margin
    margin_x = max(50, (x_max - x_min) * 0.15)
    margin_y = max(30, (y_max - y_min) * 0.8)
    
    return (x_min - margin_x, x_max + margin_x, y_min - margin_y, y_max + margin_y)


def compare_one(elem_id):
    """Generate N4 and compare with N2 recorte for one element."""
    print(f"\n{'='*60}")
    print(f"  Comparando {elem_id}")
    print(f"{'='*60}")
    
    # Find recorte
    rec = find_recorte(elem_id)
    if not rec:
        print(f"  SKIP — recorte não encontrado para {elem_id}")
        return None
    
    # Load ficha
    ficha_path = OUTPUT_DIR / f"{elem_id}_ficha_n2.json"
    if not ficha_path.exists():
        print(f"  SKIP — ficha não encontrada: {ficha_path}")
        return None
    
    with open(ficha_path, 'r', encoding='utf-8') as f:
        ficha = json.load(f)
    
    # Generate N4
    n4_path = OUTPUT_DIR / f"N4_{elem_id}.dxf"
    try:
        import ezdxf
        from gerar_fv_dxf_stog import setup_doc, draw_viga
        
        doc = setup_doc()
        msp = doc.modelspace()
        
        panels = ficha.get('panels', [])
        b_fv = ficha.get('total_width', 19.0)
        holes = ficha.get('holes', [])
        
        draw_viga(msp, 0, 0, panels, b_fv, elem_id,
                  holes=holes)
        
        doc.saveas(str(n4_path))
        print(f"  N4 gerado: {n4_path}")
    except Exception as ex:
        print(f"  ERRO gerando N4: {ex}")
        traceback.print_exc()
        return None
    
    # Get element bbox in recorte
    bbox = get_elem_bbox(str(rec), elem_id)
    
    # Render recorte N2
    n2_png = OUTPUT_DIR / f"N2_{elem_id}.png"
    try:
        render_dxf_to_png(str(rec), str(n2_png), 
                         title=f"N2 RECORTE — {elem_id}", 
                         zoom_bbox=bbox)
        print(f"  N2 PNG: {n2_png}")
    except Exception as ex:
        print(f"  ERRO renderizando N2: {ex}")
    
    # Render N4 (no zoom needed — it starts at origin)
    n4_png = OUTPUT_DIR / f"N4_{elem_id}.png"
    try:
        # Get N4 bbox
        doc2 = ezdxf.readfile(str(n4_path))
        msp2 = doc2.modelspace()
        from motor_reverso_fv import _poly_bboxes
        n4_polys = _poly_bboxes(msp2)
        if n4_polys:
            x_min = min(p[0] for p in n4_polys)
            x_max = max(p[1] for p in n4_polys)
            y_min = min(p[2] for p in n4_polys)
            y_max = max(p[3] for p in n4_polys)
            margin_x = max(50, (x_max - x_min) * 0.15)
            margin_y = max(30, (y_max - y_min) * 0.8)
            n4_bbox = (x_min - margin_x, x_max + margin_x, y_min - margin_y, y_max + margin_y)
        else:
            n4_bbox = None
        
        render_dxf_to_png(str(n4_path), str(n4_png),
                         title=f"N4 GERADO — {elem_id}",
                         zoom_bbox=n4_bbox)
        print(f"  N4 PNG: {n4_png.name}")
    except Exception as ex:
        print(f"  ERRO renderizando N4: {ex}")
    
    # Semantic comparison: extract N4 ficha via motor reverso
    try:
        from motor_reverso_fv import extrair_ficha_fundo_viga
        n4_ficha = extrair_ficha_fundo_viga(str(n4_path), elem_id)
        
        # Compare key fields
        n2_panels = [p['width'] for p in ficha.get('panels', [])]
        n4_panels = [p['width'] for p in n4_ficha.get('panels', [])]
        
        n2_b = ficha.get('total_width', 0)
        n4_b = n4_ficha.get('total_width', 0)
        
        n2_comp = sum(n2_panels)
        n4_comp = sum(n4_panels)
        
        n2_holes = sum(1 for h in ficha.get('holes', []) if h.get('active'))
        n4_holes = sum(1 for h in n4_ficha.get('holes', []) if h.get('active'))
        
        b_match = abs(n2_b - n4_b) < 0.5
        comp_match = abs(n2_comp - n4_comp) < 1.0
        panels_match = len(n2_panels) == len(n4_panels) and all(
            abs(a - b) < 1.0 for a, b in zip(n2_panels, n4_panels)
        )
        holes_match = n2_holes == n4_holes
        
        overall = b_match and comp_match and panels_match and holes_match
        
        print(f"\n  COMPARAÇÃO SEMÂNTICA:")
        print(f"    b_fv:    N2={n2_b} N4={n4_b} {'✅' if b_match else '❌'}")
        print(f"    comp:    N2={n2_comp} N4={n4_comp} {'✅' if comp_match else '❌'}")
        print(f"    panels:  N2={n2_panels}")
        print(f"             N4={n4_panels} {'✅' if panels_match else '❌'}")
        print(f"    holes:   N2={n2_holes} N4={n4_holes} {'✅' if holes_match else '❌'}")
        print(f"    OVERALL: {'✅ PASS' if overall else '❌ FAIL'}")
        
        return {
            'elem_id': elem_id,
            'b_match': b_match,
            'comp_match': comp_match,
            'panels_match': panels_match,
            'holes_match': holes_match,
            'overall': overall,
            'n2_panels': n2_panels,
            'n4_panels': n4_panels,
        }
    except Exception as ex:
        print(f"  ERRO na comparação: {ex}")
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('elem', nargs='?', default=None)
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()
    
    if args.all:
        # Get all elements from extraction summary
        summary_path = OUTPUT_DIR / "extraction_summary.json"
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        
        results = []
        for item in summary:
            if item.get('status') != 'OK':
                continue
            r = compare_one(item['elem_id'])
            if r:
                results.append(r)
        
        # Print summary
        print(f"\n\n{'='*80}")
        print(f"  RESUMO COMPARAÇÃO — {len(results)} elementos")
        print(f"{'='*80}")
        print(f"{'Elem':<10} {'b':>4} {'comp':>5} {'panels':>7} {'holes':>6} {'overall':>8}")
        print(f"{'-'*10} {'-'*4} {'-'*5} {'-'*7} {'-'*6} {'-'*8}")
        
        pass_count = 0
        for r in results:
            status = '✅' if r['overall'] else '❌'
            if r['overall']:
                pass_count += 1
            print(f"{r['elem_id']:<10} {'✅' if r['b_match'] else '❌':>4} {'✅' if r['comp_match'] else '❌':>5} {'✅' if r['panels_match'] else '❌':>7} {'✅' if r['holes_match'] else '❌':>6} {status:>8}")
        
        print(f"\n  {pass_count}/{len(results)} PASS")
    elif args.elem:
        compare_one(args.elem)
    else:
        print("Uso: python fv_render_compare.py <elem_id>  ou  --all")


if __name__ == '__main__':
    main()
