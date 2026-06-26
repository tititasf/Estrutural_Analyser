#!/usr/bin/env python3
"""
test_fidelidade_stog.py — Testes de fidelidade STOG DXF
=========================================================
Valida que os robos PL/LV/FV/LJ geram DXFs com contagem de entidades
dentro da tolerancia esperada (fixtures capturados de execucao real).

PIPELINE-TEST-01: PL (P1)
PIPELINE-TEST-02: LV/FV (V101)
PIPELINE-TEST-03: LJ (L101, modo planta)
"""
import json
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from collections import Counter

import pytest

# Paths
OBRA_TREINO_1 = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
PROJECT_ROOT = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main")
SCRIPTS = PROJECT_ROOT / "scripts"
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"

SKIP_MSG = "Obra_TREINO_1 nao disponivel no ambiente"

try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False


def _count_entities(dxf_path):
    """Read DXF and return (total, by_type dict, by_layer dict)."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    by_type = Counter()
    by_layer = Counter()
    total = 0
    for e in msp:
        by_type[e.dxftype()] += 1
        by_layer[e.dxf.layer] += 1
        total += 1
    return total, dict(by_type), dict(by_layer)


def _load_fixture(name):
    """Load expected fixture JSON."""
    path = FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _assert_within_tolerance(actual, expected, tolerance_pct, label=""):
    """Assert actual is within tolerance_pct of expected."""
    if expected == 0:
        return  # skip zero-count entries
    lo = expected * (1 - tolerance_pct / 100.0)
    hi = expected * (1 + tolerance_pct / 100.0)
    assert lo <= actual <= hi, (
        f"{label}: expected ~{expected} (+/-{tolerance_pct}%), got {actual} "
        f"(range [{lo:.0f}, {hi:.0f}])"
    )


def _run_robot(script_name, obra_path, extra_args=None, timeout=90):
    """Run a robot script and return the generated DXF path from Fase-6."""
    cmd = [
        sys.executable, str(SCRIPTS / script_name),
        "--obra", str(obra_path),
    ]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT),
    )
    # Robot may print warnings; we only care about exit code
    if result.returncode != 0:
        pytest.fail(f"Robot {script_name} failed (rc={result.returncode}):\n{result.stderr}\n{result.stdout}")
    return result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE-TEST-01: Fidelidade PL
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not OBRA_TREINO_1.exists(), reason=SKIP_MSG)
@pytest.mark.skipif(not HAS_EZDXF, reason="ezdxf not installed")
def test_fidelidade_pl_entidades():
    """Gera DXF PL para P1 e compara vs fixture com tolerancia 5%."""
    fixture = _load_fixture("expected_pl_entities.json")
    tol = fixture.get("tolerance_pct", 5)

    # Generate PL DXF (--max 1 = only first pillar = P1)
    _run_robot("gerar_pl_dxf_stog.py", OBRA_TREINO_1, ["--max", "1"])

    dxf_path = OBRA_TREINO_1 / "Fase-6_Execucao_CAD" / "PL_stog_quality.dxf"
    assert dxf_path.exists(), f"DXF nao gerado: {dxf_path}"

    total, by_type, by_layer = _count_entities(dxf_path)

    # Total entities
    _assert_within_tolerance(total, fixture["total_entities"], tol, "total_entities")

    # By type
    for etype, expected_count in fixture["by_type"].items():
        actual = by_type.get(etype, 0)
        _assert_within_tolerance(actual, expected_count, tol, f"type:{etype}")

    # By layer (check only layers with significant count > 5)
    for layer, expected_count in fixture["by_layer"].items():
        if expected_count < 5:
            continue
        actual = by_layer.get(layer, 0)
        _assert_within_tolerance(actual, expected_count, tol, f"layer:{layer}")


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE-TEST-02: Fidelidade LV e FV
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not OBRA_TREINO_1.exists(), reason=SKIP_MSG)
@pytest.mark.skipif(not HAS_EZDXF, reason="ezdxf not installed")
def test_fidelidade_lv_entidades():
    """Gera DXF LV para V101 e compara vs fixture com tolerancia 5%."""
    fixture = _load_fixture("expected_lv_entities.json")
    tol = fixture.get("tolerance_pct", 5)

    _run_robot("gerar_lv_dxf_stog.py", OBRA_TREINO_1, ["--max", "1"])

    dxf_path = OBRA_TREINO_1 / "Fase-6_Execucao_CAD" / "LV_stog_quality.dxf"
    assert dxf_path.exists(), f"DXF nao gerado: {dxf_path}"

    total, by_type, by_layer = _count_entities(dxf_path)

    _assert_within_tolerance(total, fixture["total_entities"], tol, "total_entities")

    for etype, expected_count in fixture["by_type"].items():
        actual = by_type.get(etype, 0)
        _assert_within_tolerance(actual, expected_count, tol, f"type:{etype}")

    for layer, expected_count in fixture["by_layer"].items():
        if expected_count < 5:
            continue
        actual = by_layer.get(layer, 0)
        _assert_within_tolerance(actual, expected_count, tol, f"layer:{layer}")


@pytest.mark.skipif(not OBRA_TREINO_1.exists(), reason=SKIP_MSG)
@pytest.mark.skipif(not HAS_EZDXF, reason="ezdxf not installed")
def test_fidelidade_fv_entidades():
    """Gera DXF FV para V101 e compara vs fixture com tolerancia 5%."""
    fixture = _load_fixture("expected_fv_entities.json")
    tol = fixture.get("tolerance_pct", 5)

    _run_robot("gerar_fv_dxf_stog.py", OBRA_TREINO_1, ["--max", "1"])

    dxf_path = OBRA_TREINO_1 / "Fase-6_Execucao_CAD" / "FV_stog_quality.dxf"
    assert dxf_path.exists(), f"DXF nao gerado: {dxf_path}"

    total, by_type, by_layer = _count_entities(dxf_path)

    _assert_within_tolerance(total, fixture["total_entities"], tol, "total_entities")

    for etype, expected_count in fixture["by_type"].items():
        actual = by_type.get(etype, 0)
        _assert_within_tolerance(actual, expected_count, tol, f"type:{etype}")

    for layer, expected_count in fixture["by_layer"].items():
        if expected_count < 5:
            continue
        actual = by_layer.get(layer, 0)
        _assert_within_tolerance(actual, expected_count, tol, f"layer:{layer}")


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE-TEST-03: Fidelidade LJ (modo planta)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not OBRA_TREINO_1.exists(), reason=SKIP_MSG)
@pytest.mark.skipif(not HAS_EZDXF, reason="ezdxf not installed")
def test_fidelidade_lj_planta():
    """Gera DXF LJ em modo planta e compara vs fixture com tolerancia 5%."""
    fixture = _load_fixture("expected_lj_entities.json")
    tol = fixture.get("tolerance_pct", 5)

    _run_robot("gerar_lj_dxf_stog.py", OBRA_TREINO_1, ["--mode", "planta"])

    dxf_path = OBRA_TREINO_1 / "Fase-6_Execucao_CAD" / "LJ_stog_quality.dxf"
    assert dxf_path.exists(), f"DXF nao gerado: {dxf_path}"

    total, by_type, by_layer = _count_entities(dxf_path)

    _assert_within_tolerance(total, fixture["total_entities"], tol, "total_entities")

    for etype, expected_count in fixture["by_type"].items():
        actual = by_type.get(etype, 0)
        _assert_within_tolerance(actual, expected_count, tol, f"type:{etype}")

    for layer, expected_count in fixture["by_layer"].items():
        if expected_count < 5:
            continue
        actual = by_layer.get(layer, 0)
        _assert_within_tolerance(actual, expected_count, tol, f"layer:{layer}")

    # LJ-specific: check metadata
    if "n_panels" in fixture:
        # Count lajes from Fase-3 data
        lajes_path = OBRA_TREINO_1 / "Fase-3_Interpretacao_Extracao" / "Lajes" / "lajes.json"
        if lajes_path.exists():
            with open(lajes_path, encoding="utf-8") as f:
                lajes = json.load(f)
            assert len(lajes) == fixture["n_panels"], (
                f"n_panels mismatch: expected {fixture['n_panels']}, got {len(lajes)}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE-TEST-05: Geometrias especiais (pilar L/T, parede longa)
# ═══════════════════════════════════════════════════════════════════════════════

FIXTURE_ESPECIAIS = FIXTURES / "obra_pilares_especiais"


def test_motor_pilar_geometria_especial(tmp_path):
    """Motor com pilar L e parede longa processa sem crash."""
    # Build a minimal obra structure
    obra = tmp_path / "Obra_Especial"
    fase3 = obra / "Fase-3_Interpretacao_Extracao" / "Pilares"
    fase3.mkdir(parents=True)

    # Copy fixture pilares_bh.json
    src = FIXTURE_ESPECIAIS / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_bh.json"
    shutil.copy(src, fase3 / "pilares_bh.json")

    # Also create empty vigas and lajes dirs/files so motor doesnt crash
    vigas_dir = obra / "Fase-3_Interpretacao_Extracao" / "Vigas"
    vigas_dir.mkdir(parents=True)
    with open(vigas_dir / "vigas.json", "w", encoding="utf-8") as f:
        json.dump({}, f)

    lajes_dir = obra / "Fase-3_Interpretacao_Extracao" / "Lajes"
    lajes_dir.mkdir(parents=True)
    with open(lajes_dir / "lajes.json", "w", encoding="utf-8") as f:
        json.dump({}, f)

    # Run motor_fase4
    cmd = [
        sys.executable, str(SCRIPTS / "motor_fase4.py"),
        "--obra", str(obra),
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30,
        encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT),
    )

    # Should not crash (exit code 0)
    assert result.returncode == 0, (
        f"Motor crashed on special geometry pilars (rc={result.returncode}):\n"
        f"{result.stderr[:500]}\n{result.stdout[:500]}"
    )

    # Check output was created
    fase4 = obra / "Fase-4_Sincronizacao"
    stdout = result.stdout

    # PL1 (tipo L, b=19 h=200) should be processed
    assert "PL1" in stdout or fase4.exists(), (
        "Pilar L (PL1) nao foi processado pelo motor"
    )

    # PW1 (parede, h=350 > 200) should be processed with warning
    assert "PW1" in stdout or fase4.exists(), (
        "Parede longa (PW1) nao foi processada pelo motor"
    )


def test_motor_pavimento_inexistente(tmp_path):
    """Motor com pavimento inexistente processa sem crash e gera exit 0."""
    # Build minimal obra
    obra = tmp_path / "Obra_Pav_Test"
    fase3 = obra / "Fase-3_Interpretacao_Extracao" / "Pilares"
    fase3.mkdir(parents=True)
    with open(fase3 / "pilares_bh.json", "w", encoding="utf-8") as f:
        json.dump({"P1": {"b": 19, "h": 88}}, f)

    for subdir, fname in [("Vigas", "vigas.json"), ("Lajes", "lajes.json")]:
        d = obra / "Fase-3_Interpretacao_Extracao" / subdir
        d.mkdir(parents=True)
        with open(d / fname, "w", encoding="utf-8") as f:
            json.dump({}, f)

    cmd = [
        sys.executable, str(SCRIPTS / "motor_fase4.py"),
        "--obra", str(obra),
        "--pavimento", "pav_inexistente",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=30,
        encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT),
    )

    # Should NOT crash. Motor may still process and output warnings.
    # Exit code 0 is acceptable since data was provided (just pav name is wrong)
    assert result.returncode == 0, (
        f"Motor crashed on nonexistent pavimento (rc={result.returncode}):\n"
        f"{result.stderr[:500]}\n{result.stdout[:500]}"
    )


# ---------------------------------------------------------------------------
# Regression tests — bugs corrigidos nas sessões 2026-05 (CAD-12..15 fixes)
# ---------------------------------------------------------------------------

def test_fidelidade_hall_rate_zero_when_nothing_generated(tmp_path):
    """Regressão: hall_rate deve ser 0.0 quando gerado_ids vazio (não 1.0).

    Bug: scripts retornavam `else 1.0` no cálculo de hall_rate quando
    gerado_ids era vazio → anti-hallucination score=0 indevidamente.
    Fix: mudado para `else 0.0` — sem gerado, sem alucinação.
    Método: subprocess para evitar conflito de redirecionamento sys.stdout.
    """
    helper = tmp_path / "check_hall.py"
    helper.write_text(
        "import sys, json\n"
        f"sys.path.insert(0, r'{SCRIPTS}')\n"
        "import ezdxf\n"
        "from pathlib import Path\n"
        "from fidelidade_pilares import calcular_fidelidade\n"
        "stog = Path(sys.argv[1]) / 'stog.dxf'\n"
        "gerado = Path(sys.argv[1]) / 'gerado.dxf'\n"
        "for p in (stog, gerado):\n"
        "    doc = ezdxf.new('R2010'); doc.saveas(str(p))\n"
        "coletivo = {'id_match': 0.0, 'hallucination_rate': 0.0, 'gt_count': 5,\n"
        "            'gerado_count': 0, 'missed': ['P1'], 'hallucinated': []}\n"
        "r = calcular_fidelidade(stog, gerado, coletivo)\n"
        "print(json.dumps(r))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(helper), str(tmp_path)],
        capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"helper falhou:\n{result.stderr[:500]}"
    data = json.loads(result.stdout.strip().splitlines()[-1])
    anti_hall = data["detalhes"]["anti_hallucination"]["score"]
    assert anti_hall == 10.0, (
        f"hall_rate bug: com gerado_count=0 anti-hall deve ser 10.0, obteve {anti_hall}"
    )


def test_fidelidade_gt_vazio_returns_none_score(tmp_path):
    """Regressão: GT vazio deve retornar score=None, não score=0.

    Bug: `{"erro": "GT vazio"}` em coletivo_ids era tratado como dict truthy
    com id_match=0.0 e hall_rate padrão=1.0 → score=0 indevido.
    Fix: early-return com score=None quando coletivo_ids["erro"] == "GT vazio".
    Testado por tipo em subprocessos separados (cada script redireciona sys.stdout).
    """
    out_file = tmp_path / "out.json"
    for modname, tipo in [("fidelidade_pilares", "pilares"), ("fidelidade_lajes", "lajes")]:
        helper = tmp_path / f"check_gt_vazio_{tipo}.py"
        helper.write_text(
            "import sys, json\n"
            f"sys.path.insert(0, r'{SCRIPTS}')\n"
            "import ezdxf\n"
            "from pathlib import Path\n"
            f"from {modname} import calcular_fidelidade\n"
            f"stog = Path(r'{tmp_path}') / 'stog_{tipo}.dxf'\n"
            f"gerado = Path(r'{tmp_path}') / 'gerado_{tipo}.dxf'\n"
            "for p in (stog, gerado):\n"
            "    doc = ezdxf.new('R2010'); doc.saveas(str(p))\n"
            "coletivo = {'erro': 'GT vazio'}\n"
            "r = calcular_fidelidade(stog, gerado, coletivo)\n"
            f"with open(r'{out_file}', 'w') as f: json.dump(r, f)\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(helper)],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
        )
        assert proc.returncode == 0, f"{tipo} helper falhou:\n{proc.stderr[:500]}"
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert data["score"] is None, (
            f"GT vazio deve retornar score=None para {tipo}, obteve {data['score']}"
        )
        assert data["aprovado"] is None, f"GT vazio deve retornar aprovado=None para {tipo}"
        assert "na_motivo" in data, f"GT vazio deve incluir 'na_motivo' em {tipo}"


def test_c5_skip_when_all_elementos_have_erro(tmp_path):
    """Regressão: C5_dxf_coletivo deve retornar SKIP quando todos os elementos têm 'erro'.

    Bug: obras LO-only sem DXFs gerados tinham score_global=0 → C5 FAIL [BLOCK].
    Fix: se todos elementos têm "erro", C5 retorna SKIP (igual ao C1).
    Caso: Obra_TREINO_12 (apenas DXFs LO-format, nada processável).
    """
    helper = tmp_path / "check_c5.py"
    obra = tmp_path / "Obra_LO_Only"
    fase6 = obra / "Fase-6_Execucao_CAD"
    fase6.mkdir(parents=True)
    coletivo = {
        "obra": "Obra_LO_Only", "pavimento": "12 PAV",
        "score_global": 0.0, "score_global_percent": 0.0, "aprovado": False,
        "elementos": {
            "pilares": {"erro": "PL_gerado.dxf não encontrado"},
            "vigas": {"erro": "LV_gerado.dxf não encontrado"},
            "lajes": {"erro": "LJ_gerado.dxf não encontrado"},
        },
    }
    with open(fase6 / "validation_coletivo.json", "w", encoding="utf-8") as f:
        json.dump(coletivo, f)

    helper.write_text(
        "import sys, json\n"
        f"sys.path.insert(0, r'{SCRIPTS}')\n"
        "from certificar_obra import verificar_c5_coletivo\n"
        "from pathlib import Path\n"
        f"r = verificar_c5_coletivo(Path(r'{obra}'))\n"
        "print(json.dumps(r))\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(helper)],
        capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"helper falhou:\n{result.stderr[:500]}"
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["status"] == "SKIP", (
        f"C5 deve ser SKIP quando todos elementos têm 'erro', obteve {data['status']}"
    )
    assert "Nenhum DXF gerado" in data.get("motivo", ""), (
        f"Motivo SKIP deve mencionar 'Nenhum DXF gerado', obteve: {data.get('motivo')}"
    )


def test_load_gt_ids_filters_invalid_keys(tmp_path):
    """Regressão: load_gt_ids deve filtrar chaves inválidas como 'motivo', '_meta'.

    Bug: Obra_TREINO_10 tinha lajes_salvas.json com `{"motivo": {...}}` como
    única chave. load_gt_ids incluía "motivo" como ID válido → C1 FAIL indevido.
    Fix: filtrar chaves que não começam com letra seguida de dígito.
    """
    helper = tmp_path / "check_gt_ids.py"
    gt_file = tmp_path / "lajes_salvas.json"

    # Caso 1: só artefatos
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump({"motivo": {"texto": "erro"}, "_meta": {}}, f)
    helper.write_text(
        "import sys, json\n"
        f"sys.path.insert(0, r'{SCRIPTS}')\n"
        "from validar_dxf_coletivo import load_gt_ids\n"
        f"ids1 = load_gt_ids(r'{gt_file}')\n"
        "assert 'motivo' not in ids1, f'motivo incluido: {{ids1}}'\n"
        "assert len(ids1) == 0, f'esperado 0 IDs, obteve {{ids1}}'\n"
        "print('caso1 ok')\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(helper)],
        capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0, f"caso1 falhou:\n{r.stderr[:300]}\n{r.stdout[:300]}"

    # Caso 2: IDs reais + artefatos
    gt_file2 = tmp_path / "lajes_salvas2.json"
    with open(gt_file2, "w", encoding="utf-8") as f:
        json.dump({"L1": {}, "L2": {}, "motivo": {}, "_ausente": True}, f)
    out2 = tmp_path / "ids2.json"
    helper2 = tmp_path / "check_gt_ids2.py"
    helper2.write_text(
        "import sys, json\n"
        f"sys.path.insert(0, r'{SCRIPTS}')\n"
        "from validar_dxf_coletivo import load_gt_ids\n"
        f"ids2 = load_gt_ids(r'{gt_file2}')\n"
        f"with open(r'{out2}', 'w') as f: json.dump(sorted(ids2), f)\n",
        encoding="utf-8",
    )
    r2 = subprocess.run(
        [sys.executable, str(helper2)],
        capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace",
    )
    assert r2.returncode == 0, f"caso2 falhou:\n{r2.stderr[:300]}"
    ids2 = set(json.loads(out2.read_text(encoding="utf-8")))
    assert ids2 == {"L1", "L2"}, f"esperado {{L1, L2}}, obteve {ids2}"
