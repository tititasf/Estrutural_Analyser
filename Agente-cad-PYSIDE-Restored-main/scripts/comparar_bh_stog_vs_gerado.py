#!/usr/bin/env python3
"""
comparar_bh_stog_vs_gerado.py - Comparacao NAO-CIRCULAR.

Extrai B/H dos DXFs gerados (Fase-5) e compara com pilares_bh_stog.json (ground truth).
Ground truth = geometria extraida diretamente do DXF STOG original.

Usage: python scripts/comparar_bh_stog_vs_gerado.py --obra PATH
"""
import argparse, json, sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERRO: ezdxf nao instalado")
    sys.exit(1)


TOL = 0.05   # tolerancia 5%
MIN_CONF = 0.4  # confianca minima do STOG para incluir na comparacao


def extrair_bh_do_dxf_gerado(dxf_path: Path) -> dict:
    """
    Le DXF gerado (Fase-5) e extrai B/H das LWPOLYLINE na layer 'Paineis'.
    Retorna {'b': float, 'h': float, 'n_panels': int} ou None.
    """
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception as e:
        return None

    # No DXF gerado: eixo X = dimensao do pilar (B ou H), eixo Y = altura dos paineis
    # Por isso usa w_rect (x-extent) e nao h_rect (y-extent)
    widths = []
    for e in msp.query('LWPOLYLINE'):
        if 'ain' not in e.dxf.layer:
            continue
        try:
            pts = list(e.get_points())
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            w = max(xs) - min(xs)   # dimensao do pilar (B ou H)
            h = max(ys) - min(ys)   # altura do painel (h1, h2, h3...)
            if w > 5 and h > 3:
                widths.append(round(w, 1))
        except Exception:
            continue

    if not widths:
        return None

    unique_w = sorted(set(widths), reverse=True)
    if len(unique_w) >= 2:
        H = float(unique_w[0])   # maior largura = H (face larga)
        B = float(unique_w[1])   # menor largura = B (face estreita)
    else:
        H = float(unique_w[0])
        B = float(unique_w[0])

    return {'b': B, 'h': H, 'n_panels': len(widths), 'unique_w': unique_w[:4]}


def match(v_gerado, v_stog, tol=TOL) -> bool:
    if v_stog == 0:
        return False
    return abs(v_gerado - v_stog) / v_stog <= tol


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--obra", required=True)
    args = parser.parse_args()

    obra = Path(args.obra)

    stog_path = obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_bh_stog.json"
    dxf_dir   = obra / "Fase-5_Geracao_Scripts" / "DXF_Pilares"

    if not stog_path.exists():
        print(f"ERRO: {stog_path} nao encontrado. Execute extrair_secoes_stog_pl.py primeiro.")
        sys.exit(1)

    stog_data = json.loads(stog_path.read_text(encoding='utf-8'))
    stog_data.pop('_meta', None)

    print(f"Ground truth STOG: {len(stog_data)} pilares")
    print(f"DXF gerados em: {dxf_dir}")

    resultados = {}
    n_total = 0
    n_match_b = 0
    n_match_h = 0
    n_match_bh = 0
    n_skip = 0

    print("\n=== COMPARACAO DXF GERADO vs STOG ===")
    for pid in sorted(stog_data, key=lambda p: (len(p), p)):
        stog = stog_data[pid]
        conf = stog.get('confidence', 0.5)

        if conf < MIN_CONF:
            print(f"  {pid}: SKIP (conf={conf:.2f} < {MIN_CONF})")
            n_skip += 1
            continue

        dxf_path = dxf_dir / f"{pid}.dxf"
        if not dxf_path.exists():
            print(f"  {pid}: DXF nao encontrado ({dxf_path.name})")
            continue

        gerado = extrair_bh_do_dxf_gerado(dxf_path)
        if not gerado:
            print(f"  {pid}: DXF invalido (sem LWPOLYLINE)")
            continue

        B_stog = stog['b']
        H_stog = stog['h']
        B_gen  = gerado['b']
        H_gen  = gerado['h']

        ok_b = match(B_gen, B_stog)
        ok_h = match(H_gen, H_stog)
        ok   = ok_b and ok_h

        n_total  += 1
        if ok_b: n_match_b += 1
        if ok_h: n_match_h += 1
        if ok:   n_match_bh += 1

        status = 'PASS' if ok else 'FAIL'
        b_ok = 'ok' if ok_b else 'FAIL'
        h_ok = 'ok' if ok_h else 'FAIL'
        print(f"  {pid}: [{status}] "
              f"B: {B_stog:.0f}vs{B_gen:.0f}({b_ok}) "
              f"H: {H_stog:.0f}vs{H_gen:.0f}({h_ok}) "
              f"[stog={stog['source']},conf={conf:.2f}]")

        resultados[pid] = {
            'status': status,
            'B_stog': B_stog, 'B_gen': B_gen, 'ok_b': ok_b,
            'H_stog': H_stog, 'H_gen': H_gen, 'ok_h': ok_h,
            'stog_source': stog['source'],
            'stog_conf': round(conf, 2),
        }

    rate_bh = n_match_bh / n_total * 100 if n_total else 0
    rate_b  = n_match_b  / n_total * 100 if n_total else 0
    rate_h  = n_match_h  / n_total * 100 if n_total else 0

    print(f"\n=== SCORE FINAL ===")
    print(f"  Pilares comparados: {n_total} | Skipped: {n_skip}")
    print(f"  B match: {n_match_b}/{n_total} = {rate_b:.1f}%")
    print(f"  H match: {n_match_h}/{n_total} = {rate_h:.1f}%")
    print(f"  B+H match: {n_match_bh}/{n_total} = {rate_bh:.1f}%  (meta: 75%)")

    if rate_bh >= 75:
        print(f"  RESULTADO: PASS (>= 75%)")
    else:
        print(f"  RESULTADO: FAIL (< 75%)")

    relatorio = {
        'score_bh': round(rate_bh, 1),
        'score_b':  round(rate_b, 1),
        'score_h':  round(rate_h, 1),
        'n_total':  n_total,
        'n_skip':   n_skip,
        'min_conf': MIN_CONF,
        'tolerancia': TOL,
        'pilares': resultados,
    }

    out = obra / "Fase-5_Geracao_Scripts" / "_relatorio_stog_vs_gerado.json"
    out.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n  Salvo: {out}")

    if rate_bh < 75:
        print("\n  PROXIMO: Atualizar pilares_bh.json com dados STOG e regenerar DXFs")
        print(f"  python scripts/atualizar_bh_com_stog.py --obra {args.obra}")
    else:
        print("\n  Pipeline validado! DXFs gerados batem com geometria STOG.")


if __name__ == "__main__":
    main()
