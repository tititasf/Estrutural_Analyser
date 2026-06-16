# -*- coding: utf-8 -*-
"""
test_n2_n4_abcd.py - Validacao N2 vs N4 para zona ABCD de pilares PIL.

Comparacoes:
  1. span total (pd_pavimento_cm): N4 deve bater N2 +-TOL
  2. divisores estruturais N4 devem conter posicoes das cotas-chave do N2
  3. h_low, panel_top_AB, panel_top_C corretos

Uso:
    pytest scripts/arete/test_n2_n4_abcd.py -v
    python scripts/arete/test_n2_n4_abcd.py  # modo stand-alone
"""

import sys
import json
import tempfile
import subprocess
import shutil
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import ezdxf

from arete_config import (
    DB_PATH, DADOS_OBRAS, RECORTES_ROOT,
    PD_PAVIMENTO_CM, PAV_13,
)

# ── Caminhos ──----------------------------------------------------------------
OBRA        = "Obra_TREINO_1"
OBRA_DIR    = DADOS_OBRAS / OBRA
SCRIPTS_DIR = Path(__file__).parent.parent
GERADOR     = SCRIPTS_DIR / "gerar_pl_dxf_stog.py"

TOL_CM = 2.0  # tolerancia em cm

# Valores estruturais esperados calculados a partir de N1/N2 (todos iguais para 13_PAV PIL)
# h1=2, h2=244 -> h_low = 2 + 244/2 = 124
# Face A/B: panel_top = h_low + H_PARAFUSO(73) = 197
# Face C:   panel_mid = h_low + H_PAR_C(97)  = 221
#           panel_top = panel_mid + H_C_EXTRA(41) = 262
# pd = 321
EXPECTED_DIVS = {0.0, 2.0, 124.0, 197.0, 221.0, 262.0, 321.0}

# Cotas chave do N2 (textos numericos presentes nos recortes verificados)
N2_COTAS_KEY = {
    "P1":  {2.0, 124.0, 197.0, 221.0, 321.0},
    "P11": {2.0, 124.0, 221.0, 321.0},  # 197 nao anotado no recorte P11
}

TEST_ITEMS = ["P1", "P11"]


# ── Helpers -------------------------------------------------------------------

def _recorte_n2(item_id: str, pav: str = PAV_13) -> Path | None:
    """Recorte N2 do item, filtrado pelo pavimento (mesmo logic do CE fix)."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        "SELECT recorte_path FROM reverse_eng_fichas "
        "WHERE obra_name=? AND classe='PIL' AND elemento_id=? AND pavimento=? "
        "ORDER BY id DESC LIMIT 1",
        (OBRA, item_id, pav),
    )
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        p = Path(row[0])
        if p.exists():
            return p
    # fallback: glob (pode pegar pavimento errado mas melhor que nada)
    for pattern in [f"*PL*/**/PIL_{item_id}_*dxf", f"**/*PIL_{item_id}_*dxf"]:
        found = sorted(RECORTES_ROOT.glob(pattern))
        if found:
            return found[0]
    return None


def _get_er_ficha(item_id: str) -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        "SELECT campos_json FROM reverse_eng_fichas "
        "WHERE obra_name=? AND classe='PIL' AND elemento_id=? ORDER BY id DESC LIMIT 1",
        (OBRA, item_id),
    )
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row and row[0] else {}


def _generate_n4_abcd(item_id: str) -> Path | None:
    """Gera PL_ABCD_preview_{item_id}.dxf via gerar_pl_dxf_stog.py com ficha N2."""
    er_ficha = _get_er_ficha(item_id)
    campos = {k: v for k, v in er_ficha.items() if not k.startswith("_")}

    # Injetar pd_pavimento_cm do N1 (ausente na ficha N2 do DB)
    if "pd_pavimento_cm" not in campos or not campos["pd_pavimento_cm"]:
        pj_n1 = OBRA_DIR / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item_id}.json"
        if pj_n1.exists():
            pd_val = json.loads(pj_n1.read_text("utf-8")).get("pd_pavimento_cm")
            if pd_val:
                campos["pd_pavimento_cm"] = float(pd_val)

    tmp_dir = Path(tempfile.gettempdir()) / f"test_n4_PIL_{item_id}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    json_subdir = tmp_dir / "Fase-4_Sincronizacao" / "JSON_Pilares"
    json_subdir.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_dir / "Fase-6_Execucao_CAD"
    out_dir.mkdir(parents=True, exist_ok=True)
    (json_subdir / f"{item_id}.json").write_text(
        json.dumps(campos, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    r = subprocess.run(
        [sys.executable, str(GERADOR), "--obra", str(tmp_dir), "--item", item_id, "--zone", "abcd"],
        capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
    )
    out = out_dir / f"PL_ABCD_preview_{item_id}.dxf"
    if not out.exists() and r.returncode != 0:
        print(f"  [gerador stderr] {r.stderr[:500]}")
    return out if out.exists() else None


def _all_ys(dxf_path: Path) -> list[float]:
    """Todos os Y de LINE e LWPOLYLINE em um DXF."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    ys: list[float] = []
    for e in msp:
        if e.dxftype() == "LINE":
            ys += [e.dxf.start.y, e.dxf.end.y]
        elif e.dxftype() == "LWPOLYLINE":
            ys += [p[1] for p in e.get_points()]
    return ys


def _h_lines_relative(dxf_path: Path) -> set[float]:
    """Linhas horizontais do N4 como distancias relativas ao y_bot."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    all_ys: list[float] = []
    h_ys: list[float] = []
    for e in msp:
        if e.dxftype() == "LINE":
            all_ys += [e.dxf.start.y, e.dxf.end.y]
            if abs(e.dxf.start.y - e.dxf.end.y) < 0.5:
                h_ys.append(e.dxf.start.y)
        elif e.dxftype() == "LWPOLYLINE":
            pts = list(e.get_points())
            all_ys += [p[1] for p in pts]
            if len(pts) == 2 and abs(pts[0][1] - pts[1][1]) < 0.5:
                h_ys.append(pts[0][1])
    if not all_ys:
        return set()
    y_bot = min(all_ys)
    return {round(y - y_bot, 1) for y in h_ys}


def _dim_measurements_from_defpoints(dxf_path: Path) -> set[float]:
    """Extrai medidas das DIMENSION entities via defpoints (independe de actual_measurement)."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    vals: set[float] = set()
    for e in msp:
        if e.dxftype() != "DIMENSION":
            continue
        try:
            # Dimensao linear vertical: mede |p1.y - p2.y|
            # Defpoints em DXF: defpoint=base, defpoint2=p1, defpoint3=p2 (ou dfp4/5)
            p1y = None
            p2y = None
            if hasattr(e.dxf, 'defpoint2') and hasattr(e.dxf, 'defpoint3'):
                p1y = e.dxf.defpoint2.y
                p2y = e.dxf.defpoint3.y
            elif hasattr(e.dxf, 'defpoint') and hasattr(e.dxf, 'defpoint2'):
                p1y = e.dxf.defpoint.y
                p2y = e.dxf.defpoint2.y
            if p1y is not None and p2y is not None:
                dist = round(abs(p1y - p2y), 1)
                if dist > 0.1:
                    vals.add(dist)
        except Exception:
            pass
    return vals


def _n2_text_nums(dxf_path: Path) -> set[float]:
    """Textos numericos presentes no recorte N2."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    nums: set[float] = set()
    for e in msp:
        if e.dxftype() in ("TEXT", "MTEXT"):
            txt = (e.dxf.text if e.dxftype() == "TEXT" else e.text).strip()
            try:
                nums.add(round(float(txt.replace(",", ".")), 1))
            except (ValueError, TypeError):
                pass
    return nums


def _n2_span_from_texts(text_nums: set[float]) -> float | None:
    """O maior valor numerico no recorte N2 == pd_pavimento_cm (ex: 321.0)."""
    structural = [v for v in text_nums if v > 200]
    return max(structural) if structural else None


# ============================================================================
# PYTEST TESTS
# ============================================================================

import pytest


@pytest.mark.parametrize("item_id", TEST_ITEMS)
def test_n4_abcd_gera(item_id):
    """N4 ABCD DXF e gerado sem erro e nao e vazio."""
    n4_path = _generate_n4_abcd(item_id)
    assert n4_path is not None, f"{item_id}: N4 DXF nao foi gerado"
    assert n4_path.stat().st_size > 0, f"{item_id}: N4 DXF vazio"


@pytest.mark.parametrize("item_id", TEST_ITEMS)
def test_n4_span_correto(item_id):
    """N4 span geometrico == pd_pavimento_cm N1 (321cm para 13_PAV)."""
    n4_path = _generate_n4_abcd(item_id)
    assert n4_path, f"{item_id}: N4 nao gerado"

    ys = _all_ys(n4_path)
    assert ys, f"{item_id}: N4 nao tem geometria"
    span = round(max(ys) - min(ys), 1)

    pj = OBRA_DIR / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item_id}.json"
    pd_esp = float(json.loads(pj.read_text("utf-8")).get("pd_pavimento_cm", 0))

    assert abs(span - pd_esp) <= TOL_CM, (
        f"{item_id}: N4 span={span}cm != pd={pd_esp}cm (diff={abs(span-pd_esp):.1f}cm)"
    )


@pytest.mark.parametrize("item_id", TEST_ITEMS)
def test_n2_tem_cota_pd(item_id):
    """N2 recorte contem texto numerico igual ao pd_pavimento_cm (321)."""
    n2_path = _recorte_n2(item_id)
    assert n2_path, f"{item_id}: recorte N2 nao encontrado"

    nums = _n2_text_nums(n2_path)
    pd_esp = PD_PAVIMENTO_CM.get(PAV_13, 321.0)
    assert pd_esp in nums or any(abs(v - pd_esp) <= TOL_CM for v in nums), (
        f"{item_id}: cota '{pd_esp}' ausente em N2. Textos: {sorted(nums)}"
    )


@pytest.mark.parametrize("item_id", TEST_ITEMS)
def test_n4_divisores_estruturais(item_id):
    """N4 tem linhas horizontais nos divisores estruturais esperados (relativos ao y_bot)."""
    n4_path = _generate_n4_abcd(item_id)
    assert n4_path, f"{item_id}: N4 nao gerado"

    divs = _h_lines_relative(n4_path)
    ausentes = [d for d in sorted(EXPECTED_DIVS)
                if not any(abs(div - d) <= TOL_CM for div in divs)]

    assert not ausentes, (
        f"{item_id}: divisores estruturais ausentes no N4: {ausentes}\n"
        f"  encontrados: {sorted(divs)}\n"
        f"  esperados:   {sorted(EXPECTED_DIVS)}"
    )


@pytest.mark.parametrize("item_id", TEST_ITEMS)
def test_n4_face_c_maior_que_ab(item_id):
    """Face C panel_top (262) > Face A/B panel_top (197) no N4."""
    n4_path = _generate_n4_abcd(item_id)
    assert n4_path, f"{item_id}: N4 nao gerado"

    divs = _h_lines_relative(n4_path)
    has_197 = any(abs(d - 197.0) <= TOL_CM for d in divs)
    has_262 = any(abs(d - 262.0) <= TOL_CM for d in divs)

    assert has_197, f"{item_id}: panel_top A/B (197cm) ausente. divs={sorted(divs)}"
    assert has_262, f"{item_id}: panel_top C (262cm) ausente. divs={sorted(divs)}"


@pytest.mark.parametrize("item_id", TEST_ITEMS)
def test_n4_dim_measurements(item_id):
    """N4 DIMENSION entities medem valores estruturais via defpoints (h_low=124, etc)."""
    n4_path = _generate_n4_abcd(item_id)
    assert n4_path, f"{item_id}: N4 nao gerado"

    vals = _dim_measurements_from_defpoints(n4_path)
    if not vals:
        pytest.skip(f"{item_id}: sem DIMENSION entities legiveis via defpoints")

    # h_low (124) e pd (321) devem estar presentes como medidas
    for expected in [124.0, 321.0]:
        assert any(abs(v - expected) <= TOL_CM for v in vals), (
            f"{item_id}: dim {expected}cm ausente. vals={sorted(vals)}"
        )


@pytest.mark.parametrize("item_id", TEST_ITEMS)
def test_n2_cotas_presentes_em_n4_divs(item_id):
    """Cotas chave do N2 (textos) devem aparecer como divisores geometricos do N4."""
    n2_path = _recorte_n2(item_id)
    if not n2_path:
        pytest.skip(f"{item_id}: recorte N2 nao encontrado")

    n4_path = _generate_n4_abcd(item_id)
    assert n4_path, f"{item_id}: N4 nao gerado"

    n2_nums = _n2_text_nums(n2_path)
    n4_divs = _h_lines_relative(n4_path)
    chaves  = N2_COTAS_KEY[item_id]

    ausentes = []
    for c in sorted(chaves):
        if not any(abs(d - c) <= TOL_CM for d in n4_divs):
            ausentes.append(c)

    assert not ausentes, (
        f"{item_id}: cotas N2 ausentes nos divisores N4: {ausentes}\n"
        f"  N2 textos:  {sorted(n2_nums)}\n"
        f"  N4 divs:    {sorted(n4_divs)}"
    )


# ============================================================================
# MODO STAND-ALONE
# ============================================================================

def _run_all_tests():
    print("=" * 70)
    print("TEST N2 vs N4 ABCD PIL - validacao geometrica")
    print("=" * 70)

    n_pass = n_fail = 0

    for item_id in TEST_ITEMS:
        print(f"\n--- ITEM: {item_id} ---")
        erros: list[str] = []

        # Gerar N4
        print("  [1] Gerando N4 ABCD...", end=" ")
        n4_path = _generate_n4_abcd(item_id)
        if not n4_path:
            print("FALHOU - N4 nao gerado")
            n_fail += 1
            continue
        print(f"OK ({n4_path.stat().st_size // 1024}KB)")

        # Analise N2
        n2_path = _recorte_n2(item_id)
        if n2_path:
            n2_nums = _n2_text_nums(n2_path)
            n2_span = _n2_span_from_texts(n2_nums)
            print(f"  [N2] textos numericos: {sorted(n2_nums)}")
            print(f"  [N2] span estimado:    {n2_span}cm")
        else:
            print("  [N2] recorte NAO encontrado")
            n2_nums = set()
            n2_span = None

        # Analise N4
        ys = _all_ys(n4_path)
        n4_span = round(max(ys) - min(ys), 1) if ys else 0.0
        divs = _h_lines_relative(n4_path)
        dim_vals = _dim_measurements_from_defpoints(n4_path)
        print(f"  [N4] span geometrico:  {n4_span}cm")
        print(f"  [N4] divisores rel:    {sorted(divs)}")
        print(f"  [N4] dim defpoints:    {sorted(dim_vals)[:10]}")

        # Verificacao 1: span N4 == pd_pavimento_cm N1
        pj = OBRA_DIR / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item_id}.json"
        pd_esp = float(json.loads(pj.read_text("utf-8")).get("pd_pavimento_cm", 0))
        if abs(n4_span - pd_esp) > TOL_CM:
            erros.append(f"span N4={n4_span} != pd={pd_esp} (diff={abs(n4_span-pd_esp):.1f}cm)")
        else:
            print(f"  OK span: N4={n4_span}cm == pd={pd_esp}cm")

        # Verificacao 2: divisores estruturais esperados
        ausentes_divs = [d for d in sorted(EXPECTED_DIVS)
                         if not any(abs(div - d) <= TOL_CM for div in divs)]
        if ausentes_divs:
            erros.append(f"divisores ausentes: {ausentes_divs}")
        else:
            print(f"  OK divisores: {sorted(EXPECTED_DIVS)} todos presentes")

        # Verificacao 3: face C > face A/B
        has_197 = any(abs(d - 197.0) <= TOL_CM for d in divs)
        has_262 = any(abs(d - 262.0) <= TOL_CM for d in divs)
        if not has_197:
            erros.append("panel_top A/B (197cm) ausente")
        if not has_262:
            erros.append("panel_top C (262cm) ausente")
        if has_197 and has_262:
            print(f"  OK faces: panel_top_AB=197cm, panel_top_C=262cm")

        # Verificacao 4: cotas N2 presentes em divisores N4
        chaves = N2_COTAS_KEY.get(item_id, set())
        ausentes_n2 = [c for c in sorted(chaves)
                       if not any(abs(d - c) <= TOL_CM for d in divs)]
        if ausentes_n2:
            erros.append(f"cotas N2 ausentes em divs N4: {ausentes_n2}")
        else:
            print(f"  OK cotas N2->N4: {sorted(chaves)} todas nos divisores")

        # Verificacao 5: N2 tem cota 321
        if n2_nums and not any(abs(v - pd_esp) <= TOL_CM for v in n2_nums):
            erros.append(f"cota pd={pd_esp} ausente no N2 recorte")

        if erros:
            print(f"\n  FALHOU ({len(erros)} erros):")
            for e in erros:
                print(f"    - {e}")
            n_fail += 1
        else:
            print(f"\n  PASSOU - N2 bate N4 geometricamente")
            n_pass += 1

    print(f"\n{'='*70}")
    print(f"RESULTADO: {n_pass}/{n_pass+n_fail} PASS | {n_fail} FAIL")
    print(f"{'='*70}")
    return n_fail == 0


if __name__ == "__main__":
    ok = _run_all_tests()
    sys.exit(0 if ok else 1)
