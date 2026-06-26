# -*- coding: utf-8 -*-
"""
validar_13pav_intervals.py — Extrai paineis_intervals de cada PIL 13_PAV
e mostra tabela item-a-item para inspeção visual.
Uso: python scripts/arete/validar_13pav_intervals.py
"""
import re, sqlite3, sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    sys.exit("ezdxf não instalado")

DB    = Path("D:/Agente-cad-PYSIDE/project_data.vision")
OBRA  = "Obra_TREINO_1"
PAV   = "13_PAV"
H1    = 2.0

def extract_face(dxf_path: Path) -> dict:
    """Extrai paineis_intervals_A e h_par_A do DXF N2."""
    result: dict = {}
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    face_label_xs: dict = {}
    face_label_ys: list = []
    for e in msp:
        if e.dxftype() == 'TEXT':
            m = re.match(r'^[A-Z]\d+\.([ABCDEFGH])$', e.dxf.text.strip())
            if m:
                face_label_xs[m.group(1)] = e.dxf.insert.x
                face_label_ys.append(e.dxf.insert.y)

    y_face_base = (min(face_label_ys) - 20.0) if face_label_ys else -1e9

    if len(face_label_xs) < 2:
        return result  # TIPO/12_PAV sem labels

    faces_sorted = sorted(face_label_xs.items(), key=lambda kv: kv[1])
    for i, (face, x_face) in enumerate(faces_sorted):
        if face != 'A':
            continue
        x_next = (faces_sorted[i + 1][1] if i + 1 < len(faces_sorted) else x_face + 600.0)
        x_mid_left  = ((faces_sorted[i - 1][1] + x_face) / 2 if i > 0 else x_face - 600.0)
        x_mid_right = (x_face + x_next) / 2

        _p_hs = sorted(set(
            round(ep.dxf.start.y, 1)
            for ep in msp
            if ep.dxftype() == 'LINE'
            and 'PAIN' in ep.dxf.layer.upper()
            and abs(ep.dxf.start.y - ep.dxf.end.y) < 0.5
            and x_mid_left <= (ep.dxf.start.x + ep.dxf.end.x) / 2 <= x_mid_right
            and ep.dxf.start.y >= y_face_base
        ))

        if len(_p_hs) >= 2:
            ivs = [round(_p_hs[j + 1] - _p_hs[j], 1) for j in range(len(_p_hs) - 1)]
            # Normalizar h1 se incluído como primeiro interval
            if ivs and abs(ivs[0] - H1) < 0.5:
                ivs = ivs[1:]
            if len(ivs) >= 1:
                result['paineis_intervals_A'] = ivs
                result['n2_raw_lines'] = len(_p_hs)

        # h_par via COTA texts
        cota_vals = []
        for e in msp:
            if e.dxftype() == 'TEXT' and 'COTA' in e.dxf.layer.upper():
                try:
                    v = float(e.dxf.text.strip().replace(',', '.'))
                    if v > 10.0 and x_face <= e.dxf.insert.x <= x_next and e.dxf.insert.y >= y_face_base:
                        cota_vals.append(v)
                except Exception:
                    pass
        if cota_vals and len(sorted(cota_vals)) >= 2:
            result['h_par_cota'] = sorted(cota_vals)[1]

    return result


def n4_line_count(ivs: list) -> int:
    """Linhas horizontais que o gerador N4 vai produzir (face A)."""
    if not ivs:
        return 3  # h1 + y_low + y_mid (padrão)
    # h1 strip + len(ivs) linhas de intervals
    return 1 + len(ivs)


def main():
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT elemento_id FROM reverse_eng_fichas "
        "WHERE obra_name=? AND classe='PIL' AND pavimento=? ORDER BY elemento_id",
        (OBRA, PAV)
    )
    items = [r[0] for r in cur.fetchall()]
    conn.close()

    print(f"{'PIL':<6} {'ivs_A':<50} {'hp_cota':>7}  {'n2raw':>5}  {'n4est':>5}  {'OK':>3}")
    print("-" * 85)

    issues = []
    ok_count = 0
    for item in items:
        conn = sqlite3.connect(str(DB))
        cur = conn.cursor()
        cur.execute(
            "SELECT recorte_path FROM reverse_eng_fichas "
            "WHERE obra_name=? AND classe='PIL' AND elemento_id=? AND pavimento=? "
            "ORDER BY id DESC LIMIT 1",
            (OBRA, item, PAV)
        )
        row = cur.fetchone()
        conn.close()
        if not row or not row[0]:
            print(f"{item:<6} {'<sem recorte>':50}")
            continue
        rp = Path(row[0])
        if not rp.exists():
            print(f"{item:<6} {'<arquivo nao existe>':50}")
            continue

        try:
            data = extract_face(rp)
        except Exception as ex:
            print(f"{item:<6} ERRO: {ex}")
            continue

        ivs = data.get('paineis_intervals_A', [])
        hp_c = data.get('h_par_cota', 0)
        n2raw = data.get('n2_raw_lines', 0)
        n4est = n4_line_count(ivs)

        # Verificação: primeiro intervalo não deve ser <= h1
        flag = ''
        if ivs and ivs[0] <= H1 + 0.5:
            flag = ' *** H1-LEAK'
            issues.append(f"{item}: ivs[0]={ivs[0]}")
        else:
            ok_count += 1

        ivs_str = str(ivs)
        print(f"{item:<6} {ivs_str:<50} {hp_c:>7.0f}  {n2raw:>5}  {n4est:>5}  {flag}")

    print(f"\n{ok_count}/{len(items)} itens OK (sem h1-leak)")
    if issues:
        print(f"\nISSUES:")
        for iss in issues:
            print(f"  {iss}")


if __name__ == '__main__':
    main()
