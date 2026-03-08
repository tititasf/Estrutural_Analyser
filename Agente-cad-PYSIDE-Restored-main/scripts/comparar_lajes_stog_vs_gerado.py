#!/usr/bin/env python3
"""
comparar_lajes_stog_vs_gerado.py - Comparacao NAO-CIRCULAR para lajes.

Extrai comprimento e largura dos DXFs gerados (Fase-5) e compara
com lajes.json (ground truth extraido do DXF STOG LJ via AUX00 panels
e COTA dimensions).

Ground truth = lajes.json (derivado de AUX00 MTEXT + COTA dims do STOG LJ DXF).
Gerado       = Contorno LWPOLYLINE nos DXF_Lajes gerados.

Usage: python scripts/comparar_lajes_stog_vs_gerado.py --obra PATH
"""
import argparse, json, sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERRO: ezdxf nao instalado")
    sys.exit(1)


TOL = 0.05    # tolerancia 5%
MIN_CONF = 0.35  # confianca minima (lajes tem conf 0.40-0.55)


def extrair_dims_do_dxf_gerado(dxf_path: Path) -> dict:
    """
    Le DXF gerado (Fase-5) e extrai comprimento e largura
    da LWPOLYLINE na layer 'Contorno'.

    O 'Contorno' e um retangulo exato: w = comprimento, h = largura.

    Retorna {'comprimento': float, 'largura': float} ou None.
    """
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception:
        return None

    for e in msp.query('LWPOLYLINE'):
        if e.dxf.layer != 'Contorno':
            continue
        try:
            pts = list(e.get_points())
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            w = round(max(xs) - min(xs), 1)
            h = round(max(ys) - min(ys), 1)
            if w > 5 and h > 5:
                return {'comprimento': w, 'largura': h}
        except Exception:
            continue

    return None


def match(v_gerado, v_stog, tol=TOL) -> bool:
    if v_stog == 0:
        return False
    return abs(v_gerado - v_stog) / v_stog <= tol


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--obra", required=True)
    args = parser.parse_args()

    obra = Path(args.obra)

    stog_path = obra / "Fase-3_Interpretacao_Extracao" / "Lajes" / "lajes.json"
    dxf_dir   = obra / "Fase-5_Geracao_Scripts" / "DXF_Lajes"

    if not stog_path.exists():
        print(f"ERRO: {stog_path} nao encontrado. Execute extrair_lajes_lj.py primeiro.")
        sys.exit(1)

    stog_data = json.loads(stog_path.read_text(encoding='utf-8'))

    # Remove meta-entries
    stog_lajes = {k: v for k, v in stog_data.items()
                  if isinstance(v, dict) and 'comprimento' in v}

    print(f"Ground truth STOG: {len(stog_lajes)} lajes")
    print(f"DXF gerados em: {dxf_dir}")
    print(f"Tolerancia: {TOL*100:.0f}% | MIN_CONF: {MIN_CONF}")

    resultados = {}
    n_total = 0
    n_match_comp = 0
    n_match_larg = 0
    n_match_both = 0
    n_skip = 0

    print("\n=== COMPARACAO DXF GERADO vs STOG (LAJES) ===")
    for lid in sorted(stog_lajes, key=lambda v: (len(v), v)):
        stog = stog_lajes[lid]
        conf = stog.get('confidence', 0.5)

        if conf < MIN_CONF:
            print(f"  {lid}: SKIP (conf={conf:.2f} < {MIN_CONF})")
            n_skip += 1
            continue

        comp_stog = stog.get('comprimento')
        larg_stog = stog.get('largura')

        if not comp_stog or not larg_stog:
            print(f"  {lid}: SKIP (dados STOG incompletos)")
            n_skip += 1
            continue

        dxf_path = dxf_dir / f"{lid}.dxf"
        if not dxf_path.exists():
            print(f"  {lid}: DXF nao encontrado ({dxf_path.name})")
            continue

        gerado = extrair_dims_do_dxf_gerado(dxf_path)
        if not gerado:
            print(f"  {lid}: DXF invalido (sem Contorno LWPOLYLINE)")
            continue

        comp_gen = gerado['comprimento']
        larg_gen = gerado['largura']

        ok_comp = match(comp_gen, comp_stog)
        ok_larg = match(larg_gen, larg_stog)
        ok      = ok_comp and ok_larg

        n_total   += 1
        if ok_comp: n_match_comp += 1
        if ok_larg: n_match_larg += 1
        if ok:      n_match_both += 1

        status    = 'PASS' if ok else 'FAIL'
        comp_str  = 'ok' if ok_comp else 'FAIL'
        larg_str  = 'ok' if ok_larg  else 'FAIL'
        print(f"  {lid}: [{status}] "
              f"comp: {comp_stog:.1f}vs{comp_gen:.1f}({comp_str}) "
              f"larg: {larg_stog:.1f}vs{larg_gen:.1f}({larg_str}) "
              f"[src={stog.get('source','?')},conf={conf:.2f}]")

        resultados[lid] = {
            'status':    status,
            'comp_stog': comp_stog, 'comp_gen': comp_gen, 'ok_comp': ok_comp,
            'larg_stog': larg_stog, 'larg_gen': larg_gen, 'ok_larg': ok_larg,
            'stog_conf': round(conf, 2),
            'stog_source': stog.get('source', '?'),
        }

    rate_both = n_match_both / n_total * 100 if n_total else 0
    rate_comp = n_match_comp / n_total * 100 if n_total else 0
    rate_larg = n_match_larg / n_total * 100 if n_total else 0

    print(f"\n=== SCORE FINAL ===")
    print(f"  Lajes comparadas: {n_total} | Skipped: {n_skip}")
    print(f"  Comprimento match: {n_match_comp}/{n_total} = {rate_comp:.1f}%")
    print(f"  Largura match:     {n_match_larg}/{n_total} = {rate_larg:.1f}%")
    print(f"  Comp+Larg match:   {n_match_both}/{n_total} = {rate_both:.1f}%  (meta: 75%)")

    if rate_both >= 75:
        print(f"  RESULTADO: PASS (>= 75%)")
    else:
        print(f"  RESULTADO: FAIL (< 75%)")

    relatorio = {
        'score_both':    round(rate_both, 1),
        'score_comp':    round(rate_comp, 1),
        'score_larg':    round(rate_larg, 1),
        'n_total':       n_total,
        'n_skip':        n_skip,
        'min_conf':      MIN_CONF,
        'tolerancia':    TOL,
        'lajes':         resultados,
    }

    out = obra / "Fase-5_Geracao_Scripts" / "_relatorio_stog_lajes_vs_gerado.json"
    out.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n  Salvo: {out}")


if __name__ == "__main__":
    main()
