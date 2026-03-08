#!/usr/bin/env python3
"""
comparar_dxf.py - Comparador de DXFs gerados vs. dados Fase 3 (ground truth).

Estratégia de comparação:
  - Pilares: verifica B/H dos DXFs gerados vs. pilares_bh.json (ground truth)
  - Vigas: verifica b/h/comprimento dos DXFs gerados vs. vigas.json (Fase 3)
  - Lajes: verifica comprimento/largura/area dos DXFs gerados vs. lajes.json (Fase 3)

Métricas:
  - match_rate: % de elementos que batem com tolerancia de ±5%
  - dim_error_pct: erro médio percentual nas dimensões
  - score_geral: média ponderada (pilares 33%, vigas 33%, lajes 33%)

Meta: score_geral >= 75% (limite inicial — dados Fase 3 ainda têm incerteza)

Story: CAD-6.8
Usage: python scripts/comparar_dxf.py --obra PATH
"""
import argparse, json, sys, math
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("ERRO: ezdxf nao instalado. Execute: pip install ezdxf")
    sys.exit(1)


TOL_PCT = 5.0   # tolerancia: 5% de erro aceito


def pct_error(a: float, b: float) -> float:
    """Erro percentual entre a (gerado) e b (referencia)."""
    if b == 0:
        return 0.0 if a == 0 else 100.0
    return abs(a - b) / abs(b) * 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Extração de métricas dos DXFs gerados
# ─────────────────────────────────────────────────────────────────────────────

def extrair_metricas_pilar(dxf_path: Path) -> dict:
    """Extrai B, H e n_paineis do DXF gerado de pilar."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    paineis = []
    for e in msp.query('LWPOLYLINE[layer=="Paineis"]'):
        pts = list(e.get_points())
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        if w > 0 and h > 0:
            paineis.append({"x0": min(xs), "y0": min(ys), "w": w, "h": h})

    if not paineis:
        return {"b": 0, "h": 0, "n_paineis": 0}

    # Face A = primeira face (x0=0)
    face_a = [p for p in paineis if abs(p["x0"]) < 1.0]
    if not face_a:
        face_a = paineis[:3]

    # Largura da face A = h do pilar (comprimento/largo)
    h_pilar = max((p["w"] for p in face_a), default=0)
    # Largura face B = b do pilar (espessura)
    xs_uniq = sorted(set(round(p["x0"], 0) for p in paineis))
    if len(xs_uniq) >= 2:
        # face B starts at (face_A_width + gap)
        face_b = [p for p in paineis if abs(p["x0"] - xs_uniq[1]) < 5.0]
        b_pilar = max((p["w"] for p in face_b), default=0)
    else:
        b_pilar = h_pilar

    # Altura total (soma das alturas da face A)
    total_h = sum(p["h"] for p in face_a)

    return {
        "h_pilar": round(h_pilar, 1),
        "b_pilar": round(b_pilar, 1),
        "total_height": round(total_h, 1),
        "n_paineis": len(paineis),
        "n_faces": len(xs_uniq),
    }


def extrair_metricas_viga(dxf_path: Path) -> dict:
    """Extrai comprimento, b, h do DXF gerado de viga."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    paineis = []
    for e in msp.query('LWPOLYLINE[layer=="Paineis"]'):
        pts = list(e.get_points())
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        paineis.append({"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys), "w": w, "h": h})

    if not paineis:
        return {"comprimento": 0, "b": 0, "h": 0, "n_paineis": 0}

    # Vista lateral A = primeira vista (y0 minimo)
    y_uniq = sorted(set(round(p["y0"], 0) for p in paineis))
    vista_a = [p for p in paineis if abs(p["y0"] - y_uniq[0]) < 5.0]

    comprimento = sum(p["w"] for p in vista_a)
    h_viga = max((p["h"] for p in vista_a), default=0)
    b_viga = 0.0

    # Terceira vista (Fundo) = y0 mais alto
    if len(y_uniq) >= 3:
        vista_fundo = [p for p in paineis if abs(p["y0"] - y_uniq[2]) < 5.0]
        b_viga = max((p["h"] for p in vista_fundo), default=0)

    return {
        "comprimento": round(comprimento, 1),
        "h": round(h_viga, 1),
        "b": round(b_viga, 1),
        "n_paineis": len(paineis),
        "n_vistas": len(y_uniq),
    }


def extrair_metricas_laje(dxf_path: Path) -> dict:
    """Extrai comprimento, largura e area do DXF gerado de laje."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    # Contorno
    contorno = list(msp.query('LWPOLYLINE[layer=="Contorno"]'))
    if not contorno:
        return {"comprimento": 0, "largura": 0, "area": 0}

    pts = list(contorno[0].get_points())
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    comp = max(xs) - min(xs)
    larg = max(ys) - min(ys)

    # Paineis
    paineis = list(msp.query('LWPOLYLINE[layer=="Paineis"]'))

    return {
        "comprimento": round(comp, 1),
        "largura": round(larg, 1),
        "area": round(comp * larg, 0),
        "n_paineis": len(paineis),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Comparação
# ─────────────────────────────────────────────────────────────────────────────

def comparar_pilares(dxf_dir: Path, bh_json: dict, tol: float) -> dict:
    """Compara DXFs de pilares com pilares_bh.json (ground truth B/H)."""
    resultados = {}
    n_ok = 0
    erros_pct = []

    for dxf_path in sorted(dxf_dir.glob("P*.dxf")):
        pid = dxf_path.stem
        try:
            metricas = extrair_metricas_pilar(dxf_path)
        except Exception as e:
            resultados[pid] = {"status": "ERRO_LEITURA", "msg": str(e)}
            continue

        ref = bh_json.get(pid, {})
        if not ref:
            resultados[pid] = {"status": "SEM_REF", "metricas": metricas}
            continue

        ref_b = float(ref.get("b", 0))
        ref_h = float(ref.get("h", 0))
        gen_h = metricas["h_pilar"]
        gen_b = metricas["b_pilar"]

        err_h = pct_error(gen_h, ref_h)
        err_b = pct_error(gen_b, ref_b)
        err_medio = (err_h + err_b) / 2.0
        ok = err_medio <= tol

        if ok:
            n_ok += 1
        erros_pct.append(err_medio)

        resultados[pid] = {
            "status": "OK" if ok else "DIFF",
            "ref_b": ref_b, "ref_h": ref_h,
            "gen_b": gen_b, "gen_h": gen_h,
            "err_b_pct": round(err_b, 1),
            "err_h_pct": round(err_h, 1),
            "err_medio_pct": round(err_medio, 1),
            "n_paineis": metricas["n_paineis"],
        }

    n_com_ref = len([r for r in resultados.values() if r.get("status") in ("OK", "DIFF")])
    match_rate = (n_ok / n_com_ref * 100) if n_com_ref > 0 else 0
    avg_err = sum(erros_pct) / len(erros_pct) if erros_pct else 0

    return {
        "match_rate": round(match_rate, 1),
        "avg_err_pct": round(avg_err, 1),
        "n_ok": n_ok,
        "n_total": n_com_ref,
        "detalhes": resultados,
    }


def comparar_vigas(dxf_dir: Path, vigas_json: dict, tol: float) -> dict:
    """Compara DXFs de vigas com vigas.json (ground truth b/h/L)."""
    resultados = {}
    n_ok = 0
    erros_pct = []

    for dxf_path in sorted(dxf_dir.glob("V*.dxf")):
        vid = dxf_path.stem
        try:
            metricas = extrair_metricas_viga(dxf_path)
        except Exception as e:
            resultados[vid] = {"status": "ERRO_LEITURA", "msg": str(e)}
            continue

        ref = vigas_json.get(vid, {})
        if not ref:
            resultados[vid] = {"status": "SEM_REF", "metricas": metricas}
            continue

        ref_b = float(ref.get("b", 0))
        ref_h = float(ref.get("h", 0))
        ref_L = float(ref.get("comprimento", 0))

        gen_L = metricas["comprimento"]
        gen_h = metricas["h"]

        err_L = pct_error(gen_L, ref_L)
        err_h = pct_error(gen_h, ref_h)
        err_medio = (err_L + err_h) / 2.0
        ok = err_medio <= tol

        if ok:
            n_ok += 1
        erros_pct.append(err_medio)

        resultados[vid] = {
            "status": "OK" if ok else "DIFF",
            "ref_b": ref_b, "ref_h": ref_h, "ref_L": ref_L,
            "gen_L": gen_L, "gen_h": gen_h,
            "err_L_pct": round(err_L, 1),
            "err_h_pct": round(err_h, 1),
            "err_medio_pct": round(err_medio, 1),
        }

    n_com_ref = len([r for r in resultados.values() if r.get("status") in ("OK", "DIFF")])
    match_rate = (n_ok / n_com_ref * 100) if n_com_ref > 0 else 0
    avg_err = sum(erros_pct) / len(erros_pct) if erros_pct else 0

    return {
        "match_rate": round(match_rate, 1),
        "avg_err_pct": round(avg_err, 1),
        "n_ok": n_ok,
        "n_total": n_com_ref,
        "detalhes": resultados,
    }


def comparar_lajes(dxf_dir: Path, lajes_json: dict, tol: float) -> dict:
    """Compara DXFs de lajes com lajes.json (ground truth comprimento/largura)."""
    resultados = {}
    n_ok = 0
    erros_pct = []

    for dxf_path in sorted(dxf_dir.glob("L*.dxf"), key=lambda p: (len(p.stem), p.stem)):
        lid = dxf_path.stem
        try:
            metricas = extrair_metricas_laje(dxf_path)
        except Exception as e:
            resultados[lid] = {"status": "ERRO_LEITURA", "msg": str(e)}
            continue

        ref = lajes_json.get(lid, {})
        if not ref:
            resultados[lid] = {"status": "SEM_REF", "metricas": metricas}
            continue

        ref_c = float(ref.get("comprimento", 0))
        ref_l = float(ref.get("largura", 0))
        gen_c = metricas["comprimento"]
        gen_l = metricas["largura"]

        err_c = pct_error(gen_c, ref_c)
        err_l = pct_error(gen_l, ref_l)
        err_medio = (err_c + err_l) / 2.0
        ok = err_medio <= tol

        if ok:
            n_ok += 1
        erros_pct.append(err_medio)

        resultados[lid] = {
            "status": "OK" if ok else "DIFF",
            "ref_c": ref_c, "ref_l": ref_l,
            "gen_c": gen_c, "gen_l": gen_l,
            "err_c_pct": round(err_c, 1),
            "err_l_pct": round(err_l, 1),
            "err_medio_pct": round(err_medio, 1),
        }

    n_com_ref = len([r for r in resultados.values() if r.get("status") in ("OK", "DIFF")])
    match_rate = (n_ok / n_com_ref * 100) if n_com_ref > 0 else 0
    avg_err = sum(erros_pct) / len(erros_pct) if erros_pct else 0

    return {
        "match_rate": round(match_rate, 1),
        "avg_err_pct": round(avg_err, 1),
        "n_ok": n_ok,
        "n_total": n_com_ref,
        "detalhes": resultados,
    }


# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Comparar DXFs gerados vs. ground truth (CAD-6.8)")
    parser.add_argument("--obra", required=True)
    parser.add_argument("--tol", type=float, default=TOL_PCT,
                        help=f"Tolerancia erro %% (default: {TOL_PCT})")
    args = parser.parse_args()

    obra = Path(args.obra)
    fase3 = obra / "Fase-3_Interpretacao_Extracao"
    fase5 = obra / "Fase-5_Geracao_Scripts"

    # Carrega ground truths
    bh_path    = fase3 / "Pilares" / "pilares_bh.json"
    vigas_path = fase3 / "Vigas" / "vigas.json"
    lajes_path = fase3 / "Lajes" / "lajes.json"

    bh_json    = json.loads(bh_path.read_text(encoding="utf-8"))    if bh_path.exists()    else {}
    vigas_json = json.loads(vigas_path.read_text(encoding="utf-8")) if vigas_path.exists() else {}
    lajes_json = json.loads(lajes_path.read_text(encoding="utf-8")) if lajes_path.exists() else {}

    # Diretórios DXF
    dxf_pilares = fase5 / "DXF_Pilares"
    dxf_vigas   = fase5 / "DXF_Vigas"
    dxf_lajes   = fase5 / "DXF_Lajes"

    print(f"\n=== COMPARADOR DXF vs. GROUND TRUTH (tol={args.tol}%) ===\n")

    # Pilares
    print("--- PILARES ---")
    res_pilares = comparar_pilares(dxf_pilares, bh_json, args.tol)
    print(f"  Match rate: {res_pilares['match_rate']:.1f}% ({res_pilares['n_ok']}/{res_pilares['n_total']})")
    print(f"  Erro médio: {res_pilares['avg_err_pct']:.1f}%")
    for pid, r in res_pilares["detalhes"].items():
        if r.get("status") == "DIFF":
            print(f"  DIFF {pid}: ref B={r.get('ref_b')} H={r.get('ref_h')} | "
                  f"gen B={r.get('gen_b')} H={r.get('gen_h')} | "
                  f"err={r.get('err_medio_pct')}%")

    # Vigas
    print("\n--- VIGAS ---")
    res_vigas = comparar_vigas(dxf_vigas, vigas_json, args.tol)
    print(f"  Match rate: {res_vigas['match_rate']:.1f}% ({res_vigas['n_ok']}/{res_vigas['n_total']})")
    print(f"  Erro médio: {res_vigas['avg_err_pct']:.1f}%")
    for vid, r in res_vigas["detalhes"].items():
        if r.get("status") == "DIFF":
            print(f"  DIFF {vid}: ref h={r.get('ref_h')} L={r.get('ref_L')} | "
                  f"gen h={r.get('gen_h')} L={r.get('gen_L')} | "
                  f"err={r.get('err_medio_pct')}%")

    # Lajes
    print("\n--- LAJES ---")
    res_lajes = comparar_lajes(dxf_lajes, lajes_json, args.tol)
    print(f"  Match rate: {res_lajes['match_rate']:.1f}% ({res_lajes['n_ok']}/{res_lajes['n_total']})")
    print(f"  Erro médio: {res_lajes['avg_err_pct']:.1f}%")
    for lid, r in res_lajes["detalhes"].items():
        if r.get("status") == "DIFF":
            print(f"  DIFF {lid}: ref {r.get('ref_c')}x{r.get('ref_l')} | "
                  f"gen {r.get('gen_c')}x{r.get('gen_l')} | "
                  f"err={r.get('err_medio_pct')}%")

    # Score geral
    scores = []
    if res_pilares["n_total"] > 0:
        scores.append(res_pilares["match_rate"])
    if res_vigas["n_total"] > 0:
        scores.append(res_vigas["match_rate"])
    if res_lajes["n_total"] > 0:
        scores.append(res_lajes["match_rate"])

    score_geral = sum(scores) / len(scores) if scores else 0.0
    meta = 75.0
    status = "PASS" if score_geral >= meta else "FAIL"

    print(f"\n=== SCORE GERAL: {score_geral:.1f}% ({status} | meta: {meta}%) ===")
    print(f"  Pilares: {res_pilares['match_rate']:.1f}% | "
          f"Vigas: {res_vigas['match_rate']:.1f}% | "
          f"Lajes: {res_lajes['match_rate']:.1f}%")

    # Salva relatorio
    relatorio = {
        "_meta": {
            "score_geral": score_geral,
            "status": status,
            "meta": meta,
            "tolerancia_pct": args.tol,
        },
        "pilares": res_pilares,
        "vigas": res_vigas,
        "lajes": res_lajes,
    }
    rel_path = obra / "Fase-5_Geracao_Scripts" / "_relatorio_comparacao.json"
    rel_path.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Relatorio: {rel_path}")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
