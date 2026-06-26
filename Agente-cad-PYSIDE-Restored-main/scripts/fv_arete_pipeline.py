# -*- coding: utf-8 -*-
"""
FV ARETE Pipeline — Extrai N2 de cada recorte, gera N4, compara.
Uso: python scripts/fv_arete_pipeline.py
"""
import sys, io, json, re, hashlib, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

# Paths
PROJ = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main")
RECORTES_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- FV - R00_motor")
OUTPUT_DIR = Path("D:/Agente-cad-PYSIDE/sandbox_fv_arete")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJ / "scripts"))

from motor_reverso_fv import extrair_ficha_fundo_viga

def md5_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def extract_elem_id(filename):
    """FV_V305_motor_178... -> V305"""
    m = re.match(r'FV_(V\w+?)_motor_', filename)
    if m:
        return m.group(1)
    m = re.match(r'FV_(VF\w+?)_motor_', filename)
    if m:
        return m.group(1)
    return None

def main():
    recortes = sorted(RECORTES_DIR.glob("FV_*_motor_*.dxf"))
    print(f"Found {len(recortes)} recortes in {RECORTES_DIR.name}")
    
    results = []
    
    for rec in recortes:
        elem_id = extract_elem_id(rec.name)
        if not elem_id:
            print(f"  SKIP {rec.name} — cannot extract elem_id")
            continue
        
        print(f"\n{'='*60}")
        print(f"  {elem_id} — {rec.name}")
        print(f"{'='*60}")
        
        rec_hash = md5_file(rec)
        
        # Step 1: Extract N2 ficha
        try:
            ficha = extrair_ficha_fundo_viga(
                str(rec), elem_id,
                obra_name="Obra_TREINO_1",
                obra_root="D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1"
            )
            
            n_panels = len(ficha.get('panels', []))
            panel_widths = [p['width'] for p in ficha.get('panels', [])]
            total_comp = sum(panel_widths)
            b_fv = ficha.get('total_width', 0)
            n_holes = sum(1 for h in ficha.get('holes', []) if h.get('active'))
            conf = ficha.get('_confianca', ficha.get('_er_meta', {}).get('confianca', 0))
            n_rows = ficha.get('_er_meta', {}).get('n_linhas_folha', 
                         ficha.get('_n_linhas_folha', 1))
            
            print(f"  b_fv={b_fv}cm  comp={total_comp}cm  panels={n_panels}  holes={n_holes}  rows={n_rows}  conf={conf}")
            print(f"  panel_widths={panel_widths}")
            
            # Save ficha
            ficha_path = OUTPUT_DIR / f"{elem_id}_ficha_n2.json"
            with open(ficha_path, 'w', encoding='utf-8') as f:
                json.dump(ficha, f, indent=2, ensure_ascii=False)
            
            results.append({
                'elem_id': elem_id,
                'recorte': rec.name,
                'rec_hash': rec_hash,
                'b_fv': b_fv,
                'comp': total_comp,
                'n_panels': n_panels,
                'panel_widths': panel_widths,
                'n_holes': n_holes,
                'n_rows': n_rows,
                'conf': conf,
                'status': 'OK',
                'error': None,
            })
            
        except Exception as ex:
            print(f"  ERRO extração: {ex}")
            traceback.print_exc()
            results.append({
                'elem_id': elem_id,
                'recorte': rec.name,
                'rec_hash': rec_hash,
                'status': 'ERRO',
                'error': str(ex),
            })
    
    # Summary table
    print(f"\n\n{'='*80}")
    print(f"  RESUMO EXTRAÇÃO — {len(results)} elementos")
    print(f"{'='*80}")
    print(f"{'Elem':<10} {'b_fv':>6} {'comp':>8} {'panels':>7} {'holes':>6} {'rows':>5} {'conf':>5} {'status':<6}")
    print(f"{'-'*10} {'-'*6} {'-'*8} {'-'*7} {'-'*6} {'-'*5} {'-'*5} {'-'*6}")
    
    ok_count = 0
    for r in results:
        if r['status'] == 'OK':
            ok_count += 1
            print(f"{r['elem_id']:<10} {r['b_fv']:>6.1f} {r['comp']:>8.1f} {r['n_panels']:>7} {r['n_holes']:>6} {r['n_rows']:>5} {r['conf']:>5.2f} {'OK':<6}")
        else:
            print(f"{r['elem_id']:<10} {'':>6} {'':>8} {'':>7} {'':>6} {'':>5} {'':>5} {'ERRO':<6}  {r['error']}")
    
    print(f"\n  {ok_count}/{len(results)} extraídos com sucesso")
    
    # Save results
    summary_path = OUTPUT_DIR / "extraction_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Summary saved to {summary_path}")

if __name__ == '__main__':
    main()
