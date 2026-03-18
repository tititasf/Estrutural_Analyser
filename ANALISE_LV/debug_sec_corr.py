import json, sys

with open('D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json', encoding='utf-8') as f:
    params = json.load(f)

target_names = ['V318', 'V542A', 'V205', 'V401', 'V207', 'V5_a', 'V311', 'V530', 'V225']

for vdata in params:
    name = vdata.get('viga', '') or vdata.get('nome', '')
    if not any(t in name for t in target_names):
        continue
    fa = vdata.get('face_a') or {}
    fa_x_min = fa.get('face_x_min', 0)
    fa_x_max = fa.get('face_x_max', 0)
    fa_cx = (fa_x_min + fa_x_max) / 2
    all_concreto = vdata.get('all_concreto_polys') or []
    all_sarr35   = vdata.get('all_sarr35_polys') or []
    all_madeira  = vdata.get('all_madeira_polys') or []
    sec_polys = all_concreto + all_sarr35 + all_madeira

    sec_xs = [v[0] for pp in sec_polys for v in (pp.get('vertices') or []) if len(v) >= 2]

    if sec_xs and fa_x_max > fa_x_min:
        sec_cx_mm = (min(sec_xs) + max(sec_xs)) / 2
        corr_mm = fa_cx - sec_cx_mm
    else:
        sec_cx_mm = None
        corr_mm = 0

    poly_centroids = []
    for pp in sec_polys:
        verts = pp.get('vertices') or []
        xp = [v[0] for v in verts if len(v) >= 2]
        if xp:
            poly_centroids.append(sum(xp) / len(xp))
    sec_cx_mean = sum(poly_centroids) / len(poly_centroids) if poly_centroids else None
    corr_mean = (fa_cx - sec_cx_mean) if sec_cx_mean else 0

    poly_centroids_s = sorted(poly_centroids)
    n = len(poly_centroids_s)
    sec_cx_median = poly_centroids_s[n // 2] if n % 2 == 1 else (poly_centroids_s[n//2-1] + poly_centroids_s[n//2]) / 2 if n > 0 else None
    corr_median = (fa_cx - sec_cx_median) if sec_cx_median is not None else 0

    print(f"\n=== {name} ===")
    print(f"  fa_x=[{fa_x_min:.0f},{fa_x_max:.0f}] fa_cx={fa_cx:.0f}")
    print(f"  n_concreto={len(all_concreto)} n_sarr35={len(all_sarr35)} n_madeira={len(all_madeira)}")
    if sec_xs:
        print(f"  sec_xs_range=[{min(sec_xs):.0f},{max(sec_xs):.0f}]")
    print(f"  corr_minmax={corr_mm:.0f}  corr_mean={corr_mean:.0f}  corr_median={corr_median:.0f}")
    print(f"  poly_cx: {[f'{c:.0f}' for c in poly_centroids_s]}")
