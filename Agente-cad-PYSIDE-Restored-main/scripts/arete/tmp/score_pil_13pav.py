# -*- coding: utf-8 -*-
"""
score_pil_13pav.py — Similarity score N4 vs N2 para todos os 35 PIL do 13° PAV.

Métrica estrutural:
  - H lines: conta comprimento total de H lines com largura ≈ fw_ab ou fw_cd (±4cm),
    após deduplicar por posição y (±1cm) — exclui duplicatas de anotação STOG.
  - V lines: comprimento total de V lines dentro da face (≥3cm), sem deduplicar
    (STOG desenha múltiplos segmentos, N4 continua — mesmo comprimento total).
  - sim = min(n4_len, n2_len) / max(n4_len, n2_len) para H e V separados.
  - score = 0.5 * simH + 0.5 * simV

Uso: python scripts/arete/tmp/score_pil_13pav.py
"""
import re
import sys
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent
ARETE = REPO / 'scripts' / 'arete'
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(ARETE))

import ezdxf
from motor_reverso_pil import extrair_ficha_pilar
from ficha_adapter import materializar_item, rodar_gerador, get_output_dxf_path

RECORTES_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- PL - R00")
N4_OUT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n4")
PAV = "13_PAV"
TOL_FW = 4.0   # tolerância fw (cm) para filtro de H estruturais
TOL_Y  = 1.0   # tolerância y (cm) para deduplicar H no mesmo y


def latest_dxf(item: str, folder: Path) -> Path | None:
    sel = sorted(folder.glob(f"PIL_{item}_sel_*.dxf"),
                 key=lambda p: int(re.search(r'(\d+)\.dxf$', p.name).group(1)))
    if sel:
        return sel[-1]
    cands = sorted(folder.glob(f"PIL_{item}_motor_*.dxf"),
                   key=lambda p: int(re.search(r'(\d+)\.dxf$', p.name).group(1)))
    return cands[-1] if cands else None


def gerar_n4(item: str, recorte_path: Path) -> Path | None:
    ficha = extrair_ficha_pilar(str(recorte_path), item)
    row = {'classe': 'PIL', 'elemento_id': item, 'pavimento': PAV,
           'campos_json': ficha, 'recorte_path': str(recorte_path)}
    obra_dir, _ = materializar_item(row)
    ok, log = rodar_gerador(obra_dir, 'PIL', item)
    if not ok:
        return None
    dxf_path = get_output_dxf_path(obra_dir, 'PIL', item)
    if dxf_path.exists():
        dest = N4_OUT / f"PL_preview_{item}.dxf"
        shutil.copy2(str(dxf_path), str(dest))
        return dest
    return None


def get_face_bounds(dxf_path: Path, prefer_abcd: bool = True) -> dict[str, dict]:
    """Extrai limites x de cada face (A–H) a partir de labels TEXT.
    Quando há labels duplicadas (N4 tem elevação x<0 e plant view x>0),
    mantém o x de menor valor (elevação) para cada face."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    label_xs: dict[str, float] = {}
    label_ys: list[float] = []
    for e in msp:
        if e.dxftype() != 'TEXT':
            continue
        m = re.match(r'^[A-Z]\d+\.([A-H])$', e.dxf.text.strip())
        if m:
            face = m.group(1)
            x = e.dxf.insert.x
            if face not in label_xs or x < label_xs[face]:
                label_xs[face] = x
            label_ys.append(e.dxf.insert.y)
    if not label_xs:
        return {}
    y_base = min(label_ys) - 20.0
    faces_sorted = sorted(label_xs.items(), key=lambda kv: kv[1])
    result: dict[str, dict] = {}
    for i, (face, xf) in enumerate(faces_sorted):
        x_prev = faces_sorted[i-1][1] if i > 0 else xf - 600.0
        x_next = faces_sorted[i+1][1] if i+1 < len(faces_sorted) else xf + 600.0
        xml = (x_prev + xf) / 2
        xmr = (xf + x_next) / 2
        result[face] = {'xml': xml, 'xmr': xmr, 'y_base': y_base}
    return result


def extract_lines(dxf_path: Path, bounds: dict[str, dict]) -> dict[str, dict]:
    """Extrai H lines e V lines por face. H deduplica por y (±TOL_Y)."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    result: dict[str, dict] = {f: {'H': [], 'V': []} for f in bounds}

    for e in msp:
        if e.dxftype() != 'LINE':
            continue
        layer = e.dxf.layer.upper()
        if 'PAIN' not in layer:
            continue
        x0, y0_ = e.dxf.start.x, e.dxf.start.y
        x1, y1_ = e.dxf.end.x, e.dxf.end.y
        xc = (x0 + x1) / 2
        is_h = abs(y0_ - y1_) < 0.5
        is_v = abs(x0 - x1) < 0.5
        for face, bd in bounds.items():
            if not (bd['xml'] <= xc <= bd['xmr']):
                continue
            if is_h:
                w = abs(x0 - x1)
                y_pos = round((y0_ + y1_) / 2, 1)
                result[face]['H'].append({'y': y_pos, 'w': w,
                                          'x0': min(x0, x1), 'x1': max(x0, x1)})
            elif is_v:
                h = abs(y0_ - y1_)
                if h >= 3.0:
                    result[face]['V'].append({'h': h})
    return result


def cluster_by_y(h_lines: list[dict], tol: float = TOL_Y) -> list[list[dict]]:
    """Agrupa H lines por posição y (±tol). Retorna lista de clusters."""
    if not h_lines:
        return []
    sorted_h = sorted(h_lines, key=lambda l: l['y'])
    clusters: list[list[dict]] = []
    for line in sorted_h:
        if clusters and abs(line['y'] - clusters[-1][0]['y']) <= tol:
            clusters[-1].append(line)
        else:
            clusters.append([line])
    return clusters


def structural_H_len(h_lines: list[dict], fw_ab: float, fw_cd: float,
                     tol: float = TOL_FW, y_tol: float = TOL_Y) -> float:
    """Comprimento total de H estruturais: por cluster-y, conta 1 H se ALGUMA
    linha no cluster match fw_ab ou fw_cd. Evita sobreduplicas e falsos positivos
    por annotations de largura coincidente."""
    clusters = cluster_by_y(h_lines, y_tol)
    total = 0.0
    for cl in clusters:
        # best matching width (preferência ao fw mais próximo)
        best_w = None
        best_dist = float('inf')
        for line in cl:
            for fw in (fw_ab, fw_cd):
                d = abs(line['w'] - fw)
                if d <= tol and d < best_dist:
                    best_dist = d
                    best_w = line['w']
        if best_w is not None:
            total += best_w
    return total


def score_face(n2_face: dict, n4_face: dict,
               fw_ab: float, fw_cd: float, face: str) -> dict:
    """Calcula sim para uma face. Retorna simH, simV, score."""
    n2_H_len = structural_H_len(n2_face['H'], fw_ab, fw_cd)
    n4_H_len = structural_H_len(n4_face['H'], fw_ab, fw_cd)

    simH = (min(n2_H_len, n4_H_len) / max(n2_H_len, n4_H_len)
            if max(n2_H_len, n4_H_len) > 0 else 1.0)

    # V: comprimento total (sem dedup — segmentos múltiplos STOG)
    n2_V_len = sum(l['h'] for l in n2_face['V'])
    n4_V_len = sum(l['h'] for l in n4_face['V'])

    simV = (min(n2_V_len, n4_V_len) / max(n2_V_len, n4_V_len)
            if max(n2_V_len, n4_V_len) > 0 else 1.0)

    score = 0.5 * simH + 0.5 * simV
    return {
        'simH': simH, 'simV': simV, 'score': score,
        'n2Hlen': round(n2_H_len, 1), 'n4Hlen': round(n4_H_len, 1),
        'n2Vlen': round(n2_V_len, 1), 'n4Vlen': round(n4_V_len, 1),
    }


def score_item(item: str, n2_path: Path, n4_path: Path) -> dict | None:
    ficha = extrair_ficha_pilar(str(n2_path), item)
    comp = float(ficha.get('comprimento_geom') or ficha.get('comprimento', 60))
    larg = float(ficha.get('largura', 24))
    fw_ab = round(comp + 22, 1)
    # fw_cd: usa larg_c_geom medido do N2 (fw real da face C sem +22)
    # fallback: min(larg,19) — convenção histórica SCR para larg>=19
    _larg_c_raw = ficha.get('larg_c_geom') or (min(larg, 19) if larg >= 19 else larg)
    fw_cd = round(float(_larg_c_raw), 1)

    n2_bounds = get_face_bounds(n2_path)
    n4_bounds = get_face_bounds(n4_path)

    if not n2_bounds or not n4_bounds:
        return None

    n2_lines = extract_lines(n2_path, n2_bounds)
    n4_lines = extract_lines(n4_path, n4_bounds)

    scores = {}
    face_scores = []
    for face in ('A', 'B', 'C', 'D'):
        if face not in n2_bounds or face not in n4_bounds:
            continue
        fs = score_face(n2_lines.get(face, {'H': [], 'V': []}),
                        n4_lines.get(face, {'H': [], 'V': []}),
                        fw_ab, fw_cd, face)
        scores[face] = fs
        face_scores.append(fs['score'])

    overall = sum(face_scores) / len(face_scores) if face_scores else 0.0
    return {'overall': overall, 'faces': scores,
            'fw_ab': fw_ab, 'fw_cd': fw_cd}


def main():
    N4_OUT.mkdir(parents=True, exist_ok=True)

    # Descobrir todos os itens
    all_dxfs = sorted(RECORTES_DIR.glob("PIL_P*_*.dxf"))
    items_seen = set()
    items = []
    for p in all_dxfs:
        m = re.match(r'PIL_(P\d+)_', p.name)
        if m and m.group(1) not in items_seen:
            items_seen.add(m.group(1))
            items.append(m.group(1))
    items.sort(key=lambda x: int(x[1:]))

    print(f"Itens encontrados ({len(items)}): {items}")
    print()

    results = []
    for item in items:
        n2_path = latest_dxf(item, RECORTES_DIR)
        if n2_path is None:
            print(f"  {item}: sem recorte N2 — SKIP")
            continue

        n4_path = N4_OUT / f"PL_preview_{item}.dxf"
        if not n4_path.exists():
            print(f"  {item}: regenerando N4...", end=' ', flush=True)
            n4_path = gerar_n4(item, n2_path)
            if n4_path is None:
                print("FALHOU")
                results.append((item, None, None))
                continue
            print("OK")

        sc = score_item(item, n2_path, n4_path)
        if sc is None:
            results.append((item, None, "sem bounds"))
        else:
            results.append((item, sc, None))

    # Relatório
    print()
    print(f"{'PIL':<6} {'Score%':>7} {'simH_A':>7} {'simV_A':>7} {'simH_B':>7} {'simV_B':>7}  fw_ab  fw_cd  STATUS")
    print("-" * 90)
    ok_count = 0
    fail_items = []
    for item, sc, err in results:
        if sc is None:
            print(f"{item:<6} {'ERR':>7}  {err or ''}")
            fail_items.append(item)
            continue
        pct = round(sc['overall'] * 100, 1)
        fa = sc['faces'].get('A', {})
        fb = sc['faces'].get('B', {})
        simHA = round(fa.get('simH', 0) * 100, 1)
        simVA = round(fa.get('simV', 0) * 100, 1)
        simHB = round(fb.get('simH', 0) * 100, 1)
        simVB = round(fb.get('simV', 0) * 100, 1)
        status = "OK" if pct >= 80 else "FAIL"
        if pct >= 80:
            ok_count += 1
        else:
            fail_items.append(item)
        print(f"{item:<6} {pct:>7.1f}% {simHA:>7.1f}% {simVA:>7.1f}% {simHB:>7.1f}% {simVB:>7.1f}%"
              f"  {sc['fw_ab']:>5.0f}  {sc['fw_cd']:>5.0f}  {status}")

    total = len([r for r in results if r[1] is not None])
    media = sum(r[1]['overall'] * 100 for r in results if r[1]) / total if total else 0
    print(f"\nRESULTADO: {ok_count}/{total} >=80% | MEDIA={media:.1f}%")
    if fail_items:
        print(f"FAIL: {fail_items}")


if __name__ == '__main__':
    main()
