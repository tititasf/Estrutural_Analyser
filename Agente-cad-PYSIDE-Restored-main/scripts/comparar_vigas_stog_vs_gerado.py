#!/usr/bin/env python3
"""
comparar_vigas_stog_vs_gerado.py - Comparacao NAO-CIRCULAR para vigas.

Extrai comprimento e altura_lateral dos DXFs gerados (Fase-5) e compara
com vigas_dim.json (ground truth extraido do DXF STOG LV).

Ground truth = COTA annotations do DXF STOG LV (camadas COTA e Cota Secao 2x).
Gerado       = geometry LWPOLYLINE em DXF_Vigas (total_x_extent, max_h).

Usage: python scripts/comparar_vigas_stog_vs_gerado.py --obra PATH
"""
import argparse, json, sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERRO: ezdxf nao instalado")
    sys.exit(1)


TOL = 0.05   # tolerancia 5%
MIN_CONF = 0.5  # confianca minima do STOG para incluir na comparacao


def extrair_dims_do_dxf_gerado(dxf_path: Path) -> dict:
    """
    Le DXF gerado (Fase-5) e extrai comprimento e altura_lateral
    das LWPOLYLINE na layer 'Paineis'.

    Layout gerado:
      - X-axis: panels lado a lado → total x_extent = comprimento
      - Y-axis: panels empilhados por altura → max h_rect = altura_lateral

    Retorna {'comprimento': float, 'altura': float} ou None.
    """
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception:
        return None

    xs_all = []
    heights = set()
    for e in msp.query('LWPOLYLINE'):
        if 'ain' not in e.dxf.layer:
            continue
        try:
            pts = list(e.get_points())
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if w > 5 and h > 5:
                xs_all.extend(xs)
                heights.add(round(h, 1))
        except Exception:
            continue

    if not xs_all or not heights:
        return None

    comprimento = round(max(xs_all) - min(xs_all), 1)
    altura = float(max(heights))
    return {'comprimento': comprimento, 'altura': altura}


def match(v_gerado, v_stog, tol=TOL) -> bool:
    if v_stog == 0:
        return False
    return abs(v_gerado - v_stog) / v_stog <= tol


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--obra", required=True)
    args = parser.parse_args()

    obra = Path(args.obra)

    stog_path = obra / "Fase-3_Interpretacao_Extracao" / "Vigas" / "vigas_dim.json"
    dxf_dir   = obra / "Fase-5_Geracao_Scripts" / "DXF_Vigas"

    if not stog_path.exists():
        print(f"ERRO: {stog_path} nao encontrado. Execute extrair_vigas_lv.py primeiro.")
        sys.exit(1)

    stog_data = json.loads(stog_path.read_text(encoding='utf-8'))

    # Remove meta-entries
    stog_vigas = {k: v for k, v in stog_data.items()
                  if isinstance(v, dict) and 'comprimento_cm' in v}

    print(f"Ground truth STOG: {len(stog_vigas)} vigas")
    print(f"DXF gerados em: {dxf_dir}")

    resultados = {}
    n_total = 0
    n_match_comp = 0
    n_match_alt = 0
    n_match_both = 0
    n_skip = 0

    print("\n=== COMPARACAO DXF GERADO vs STOG (VIGAS) ===")
    for vid in sorted(stog_vigas, key=lambda v: (len(v), v)):
        stog = stog_vigas[vid]
        conf = stog.get('confidence', 0.5)

        if conf < MIN_CONF:
            print(f"  {vid}: SKIP (conf={conf:.2f} < {MIN_CONF})")
            n_skip += 1
            continue

        comp_stog = stog.get('comprimento_cm')
        alt_stog  = stog.get('altura_lateral_cm')

        if not comp_stog or not alt_stog:
            print(f"  {vid}: SKIP (dados STOG incompletos)")
            n_skip += 1
            continue

        dxf_path = dxf_dir / f"{vid}.dxf"
        if not dxf_path.exists():
            print(f"  {vid}: DXF nao encontrado ({dxf_path.name})")
            continue

        gerado = extrair_dims_do_dxf_gerado(dxf_path)
        if not gerado:
            print(f"  {vid}: DXF invalido (sem LWPOLYLINE Paineis)")
            continue

        comp_gen = gerado['comprimento']
        alt_gen  = gerado['altura']

        ok_comp = match(comp_gen, comp_stog)
        ok_alt  = match(alt_gen, alt_stog)
        ok      = ok_comp and ok_alt

        n_total   += 1
        if ok_comp: n_match_comp += 1
        if ok_alt:  n_match_alt  += 1
        if ok:      n_match_both += 1

        status   = 'PASS' if ok else 'FAIL'
        comp_str = 'ok' if ok_comp else 'FAIL'
        alt_str  = 'ok' if ok_alt  else 'FAIL'
        print(f"  {vid}: [{status}] "
              f"comp: {comp_stog:.0f}vs{comp_gen:.0f}({comp_str}) "
              f"alt: {alt_stog:.0f}vs{alt_gen:.0f}({alt_str}) "
              f"[conf={conf:.2f}]")

        resultados[vid] = {
            'status': status,
            'comp_stog': comp_stog, 'comp_gen': comp_gen, 'ok_comp': ok_comp,
            'alt_stog':  alt_stog,  'alt_gen':  alt_gen,  'ok_alt':  ok_alt,
            'stog_conf': round(conf, 2),
        }

    rate_both = n_match_both / n_total * 100 if n_total else 0
    rate_comp = n_match_comp / n_total * 100 if n_total else 0
    rate_alt  = n_match_alt  / n_total * 100 if n_total else 0

    print(f"\n=== SCORE FINAL ===")
    print(f"  Vigas comparadas: {n_total} | Skipped: {n_skip}")
    print(f"  Comprimento match: {n_match_comp}/{n_total} = {rate_comp:.1f}%")
    print(f"  Altura match:      {n_match_alt}/{n_total} = {rate_alt:.1f}%")
    print(f"  Comp+Alt match:    {n_match_both}/{n_total} = {rate_both:.1f}%  (meta: 75%)")

    if rate_both >= 75:
        print(f"  RESULTADO: PASS (>= 75%)")
    else:
        print(f"  RESULTADO: FAIL (< 75%)")

    relatorio = {
        'score_both':    round(rate_both, 1),
        'score_comp':    round(rate_comp, 1),
        'score_alt':     round(rate_alt, 1),
        'n_total':       n_total,
        'n_skip':        n_skip,
        'min_conf':      MIN_CONF,
        'tolerancia':    TOL,
        'vigas':         resultados,
    }

    out = obra / "Fase-5_Geracao_Scripts" / "_relatorio_stog_vigas_vs_gerado.json"
    out.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n  Salvo: {out}")


if __name__ == "__main__":
    main()
