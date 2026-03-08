#!/usr/bin/env python3
"""
extrair_secoes_stog_pl.py - Extrai B/H REAL de cada pilar do DXF STOG PL.

Estrategia correta (baseada em auditoria DXF):
  1. Gordo = LWPOLYLINE 'Paineis' com w>5 e h_rect>3
     - Cada gordo pertence ao pilar cuja label P{n} esta mais proxima
     - h_rect = profundidade da face = dimensao do pilar (H ou B)
     - Se 2+ gordos por pilar com h_rects diferentes: maior=H, menor=B
     - Se 1 gordo + w<=80: B=min(h_rect,w), H=max(h_rect,w) - w e 2a dimensao
     - Se 1 gordo + w>80: busca 'Cota Secao (2x)' DIMENSION perto do gordo
  2. Fallback: pilares sem gordo usam 'Cota Secao (2x)' DIMENSION proximos

Story: CAD-6.8b (validacao real contra STOG)
Usage: python scripts/extrair_secoes_stog_pl.py --obra PATH [--dxf PATH_PL_DXF]
"""
import argparse, json, re, sys
from pathlib import Path
from collections import defaultdict

try:
    import ezdxf
except ImportError:
    print("ERRO: ezdxf nao instalado")
    sys.exit(1)

MAX_GORDO_RADIUS = 700   # max dist gordo->pilar label
DIM_NEAR_GORDO   = 200   # "Cota Secao" dims near gordo
DIM_NEAR_LABEL   = 600   # fallback: dims near pilar label


def extrair_labels(msp) -> dict:
    """Retorna {pid: [{'face','x','y','text'}]}"""
    labels_map = defaultdict(list)
    for e in msp:
        if e.dxftype() not in ('MTEXT', 'TEXT'):
            continue
        try:
            txt = e.plain_text() if hasattr(e, 'plain_text') else e.dxf.text
            txt = txt.strip()
            x, y = e.dxf.insert.x, e.dxf.insert.y
            for part in txt.split('-'):
                m = re.match(r'(P\d+[A-Z]?)\.([A-Z])', part.strip())
                if m:
                    pid, face = m.group(1), m.group(2)
                    labels_map[pid].append({'face': face, 'x': x, 'y': y, 'text': txt})
        except Exception:
            continue
    return dict(labels_map)


def extrair_gordos(msp) -> list:
    """LWPOLYLINE 'Paineis' com w>5 e h_rect>3."""
    result = []
    for e in msp.query('LWPOLYLINE'):
        if 'ain' not in e.dxf.layer:
            continue
        try:
            pts = list(e.get_points())
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if w > 5 and h > 3:
                result.append({
                    'cx': (min(xs)+max(xs))/2,
                    'cy': (min(ys)+max(ys))/2,
                    'w':  round(w, 1),
                    'h':  round(h, 1),
                })
        except Exception:
            continue
    return result


def extrair_dims_cota(msp) -> list:
    """DIMENSION da layer 'Cota Secao (2x)' com val 5-300."""
    result = []
    for e in msp.query('DIMENSION'):
        lay = e.dxf.layer
        if 'Cota' not in lay or 'x' not in lay.lower():
            continue
        try:
            val = abs(e.get_measurement())
            if 5 < val < 300:
                pts = []
                for attr in ['defpoint', 'defpoint2', 'defpoint3']:
                    try:
                        p = getattr(e.dxf, attr)
                        pts.append((p.x, p.y))
                    except Exception:
                        pass
                if pts:
                    cx = sum(x for x, y in pts) / len(pts)
                    cy = sum(y for x, y in pts) / len(pts)
                    result.append({'val': round(val, 1), 'cx': cx, 'cy': cy})
        except Exception:
            continue
    return result


def dist(ax, ay, bx, by):
    return ((ax-bx)**2 + (ay-by)**2)**0.5


def assign_gordos_to_pilares(labels_map: dict, gordos: list) -> dict:
    """
    Atribui cada gordo ao pilar cuja label (qualquer face) esta mais proxima.
    Usa distancia MINIMA a qualquer face-label do pilar.
    Retorna {pid: [gordo_dict, ...]}
    """
    # Lista plana de (pid, x, y) para todos os labels
    all_labels = [
        (pid, l['x'], l['y'])
        for pid, lbs in labels_map.items()
        for l in lbs
    ]

    pid_gordos = defaultdict(list)
    for g in gordos:
        # Distancia minima a qualquer label de cada pilar
        best_d = {}
        for pid, lx, ly in all_labels:
            d = dist(g['cx'], g['cy'], lx, ly)
            if pid not in best_d or d < best_d[pid]:
                best_d[pid] = d

        # Pilar com label mais proximo
        nearest_pid = min(best_d, key=best_d.get)
        d = best_d[nearest_pid]
        if d <= MAX_GORDO_RADIUS:
            pid_gordos[nearest_pid].append({**g, 'dist': round(d, 0)})

    return dict(pid_gordos)


def bh_from_gordos(gordos_list: list, dims_cota: list) -> tuple:
    """
    Determina (B, H, fonte, confianca, debug_info) a partir dos gordos do pilar.
    """
    debug = {}
    # Gordos com w <= 80 sao mais confiáveis (w é a segunda dimensão do pilar)
    # Gordos com w > 80 podem ter w = altura de painel aggregada
    gordos_direct = [g for g in gordos_list if g['w'] <= 80]
    gordos_wide   = [g for g in gordos_list if g['w'] > 80]

    # Prefere gordos diretos (w <= 80) se disponivel
    effective = gordos_direct if gordos_direct else gordos_wide
    h_rects = sorted(set(round(g['h'], 1) for g in effective), reverse=True)
    debug['h_rects'] = h_rects
    debug['n_direct'] = len(gordos_direct)
    debug['n_wide'] = len(gordos_wide)

    if len(h_rects) >= 2:
        # 2+ faces distintas — direto
        H = float(h_rects[0])
        B = float(h_rects[1])
        return B, H, 'lwpoly-2faces', 0.92, debug

    if len(h_rects) == 1:
        h_rect = float(h_rects[0])
        g = gordos_list[0]
        w = g['w']
        debug['gordo_w'] = w

        if w <= 80:
            # w e a segunda dimensao do pilar
            H = max(h_rect, w)
            B = min(h_rect, w)
            debug['method'] = 'gordo-w-as-B'
            return B, H, 'lwpoly-w-dim', 0.85, debug

        # w grande (panel height) -> buscar dims perto do gordo por FREQUENCIA
        # "Cota Secao (2x)" significa cada dimensao anotada 2x -> maior freq = dim real
        from collections import Counter
        near_vals = [round(d['val'], 0)
                     for d in dims_cota
                     if dist(d['cx'], d['cy'], g['cx'], g['cy']) < DIM_NEAR_GORDO]
        freq = Counter(near_vals)
        debug['dim_freq'] = dict(sorted(freq.items(), key=lambda x: -x[1])[:6])

        # Filtra: [10..160], exclui gordo_w (ja conhecida = panel height)
        # Usa frequencia: dim real aparece 2x ou mais no "2x"
        cands_freq = {v: c for v, c in freq.items()
                      if 10 <= v <= 160 and abs(v - h_rect) > 2}

        if cands_freq:
            # Dim nao-h_rect mais frequente = outra dimensao do pilar
            other_dim = max(cands_freq, key=lambda v: (cands_freq[v], v))
            B = min(h_rect, float(other_dim))
            H = max(h_rect, float(other_dim))
            debug['other_dim_freq'] = cands_freq[other_dim]
            return B, H, 'lwpoly+dim-freq', 0.83, debug

        # Sem dim confiavel -> usar h_rect como UNICA dimensao (provavel quadrado)
        debug['fallback'] = 'square-assumed'
        return h_rect, h_rect, 'lwpoly-square', 0.60, debug

    return None, None, None, 0.0, debug


def extrair_bh_label_fallback(pid, labels, dims_cota, bh_prev: dict) -> tuple:
    """Fallback: usa pilares_bh.json anterior (inverse-proximity) como estimativa."""
    if pid in bh_prev:
        prev = bh_prev[pid]
        return float(prev['b']), float(prev['h']), 'prev-inverse-prox', float(prev.get('confidence', 0.5)) * 0.8, {}
    return 30.0, 30.0, 'default', 0.25, {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--obra", required=True)
    parser.add_argument("--dxf", help="Path do PL DXF (auto-detectado se omitido)")
    args = parser.parse_args()

    obra = Path(args.obra)

    if args.dxf:
        pl_dxf = Path(args.dxf)
    else:
        ingests = obra / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
        import os
        candidates = [f for f in os.listdir(ingests) if 'PL' in f and f.endswith('.dxf') and '12' in f]
        if not candidates:
            print(f"ERRO: PL DXF nao encontrado em {ingests}")
            sys.exit(1)
        pl_dxf = ingests / candidates[0]

    print(f"Lendo: {pl_dxf.name}")
    doc = ezdxf.readfile(str(pl_dxf))
    msp = doc.modelspace()

    labels_map  = extrair_labels(msp)
    gordos      = extrair_gordos(msp)
    dims_cota   = extrair_dims_cota(msp)

    print(f"Pilares (labels): {len(labels_map)}")
    print(f"Gordos (Paineis h>3): {len(gordos)}")
    print(f"Dims Cota Secao (2x): {len(dims_cota)}")

    pid_gordos = assign_gordos_to_pilares(labels_map, gordos)
    print(f"Pilares com gordo: {len(pid_gordos)}")

    # Carrega pilares_bh.json anterior como fallback
    bh_prev_path = obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_bh.json"
    bh_prev = {}
    if bh_prev_path.exists():
        bh_prev = json.loads(bh_prev_path.read_text(encoding='utf-8'))
        print(f"Fallback: {bh_prev_path.name} ({len(bh_prev)-1} pilares)")

    print("\n=== B/H EXTRAIDOS DO STOG ===")
    resultado = {}
    for pid in sorted(labels_map, key=lambda p: (len(p), p)):
        labels = labels_map[pid]
        gordos_pid = pid_gordos.get(pid, [])

        if gordos_pid:
            B, H, fonte, conf, dbg = bh_from_gordos(gordos_pid, dims_cota)
        else:
            B, H, fonte, conf, dbg = extrair_bh_label_fallback(pid, labels, dims_cota, bh_prev)

        resultado[pid] = {
            "b": B, "h": H, "source": fonte, "confidence": conf,
            "n_gordos": len(gordos_pid),
            "debug": dbg,
        }
        print(f"  {pid}: B={B} H={H} [{fonte}] conf={conf} n_gordos={len(gordos_pid)}")

    resultado["_meta"] = {
        "total": len(resultado) - 1,
        "pavimento": "12 PAV",
        "dxf": pl_dxf.name,
        "algoritmo": "gordo-nearest-label + dim-cota-secao",
    }

    out = obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_bh_stog.json"
    out.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Salvo: {out}")
    print(f"  Proximo: python scripts/comparar_bh_stog_vs_gerado.py --obra {args.obra}")


if __name__ == "__main__":
    main()
