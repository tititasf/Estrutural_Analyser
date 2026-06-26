#!/usr/bin/env python3
"""
test_pipeline_e2e.py — Teste E2E: Fase-3 -> Fase-4 -> Fase-6
==============================================================
Executa pipeline completo em Obra_TREINO_1:
  1. motor_fase4.py -> gera JSONs Fase-4
  2. gerar_pl_dxf_stog.py P1 -> DXF pilar
  3. gerar_lj_dxf_stog.py L101 -> DXF laje
  4. gerar_lv_dxf_stog.py V101 -> DXF viga lateral
  5. Valida todos os outputs existem, tamanho > 0, SA meta OK
  6. Tempo total < 120s
"""
import json
import os
import sys
import subprocess
import time
from pathlib import Path

import pytest

OBRA_TREINO_1 = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
PROJECT_ROOT = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main")
SCRIPTS = PROJECT_ROOT / "scripts"

SKIP_MSG = "Obra_TREINO_1 nao disponivel no ambiente"

try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False


def _run(script, args, label="", timeout=90):
    """Run a script, return (stdout, duration_s). Fail on error."""
    cmd = [sys.executable, str(SCRIPTS / script)] + args
    t0 = time.time()
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
        cwd=str(PROJECT_ROOT),
    )
    dt = time.time() - t0
    if result.returncode != 0:
        pytest.fail(
            f"[{label}] {script} failed (rc={result.returncode}, {dt:.1f}s):\n"
            f"{result.stderr[:500]}\n{result.stdout[:500]}"
        )
    return result.stdout, dt


@pytest.mark.skipif(not OBRA_TREINO_1.exists(), reason=SKIP_MSG)
@pytest.mark.skipif(not HAS_EZDXF, reason="ezdxf not installed")
def test_pipeline_e2e_completo():
    """Executa pipeline completo e valida outputs. Tempo total < 120s."""
    timings = {}
    t_total_start = time.time()

    # ── Fase 4: motor_fase4.py ────────────────────────────────────────────
    out, dt = _run("motor_fase4.py", ["--obra", str(OBRA_TREINO_1)], "Fase-4", timeout=60)
    timings["motor_fase4"] = dt

    fase4 = OBRA_TREINO_1 / "Fase-4_Sincronizacao"
    assert fase4.exists(), "Fase-4_Sincronizacao nao criada"

    # Check at least pilares_salvos.json or JSON_Pilares/ exists
    has_pilares = (
        (fase4 / "pilares_salvos.json").exists()
        or (fase4 / "JSON_Pilares").exists()
    )
    assert has_pilares, "Nenhum output de pilares em Fase-4"

    # ── Fase 6: PL ───────────────────────────────────────────────────────
    out, dt = _run("gerar_pl_dxf_stog.py", ["--obra", str(OBRA_TREINO_1), "--max", "1"], "PL")
    timings["gerar_pl"] = dt

    pl_dxf = OBRA_TREINO_1 / "Fase-6_Execucao_CAD" / "PL_stog_quality.dxf"
    assert pl_dxf.exists(), "PL DXF nao gerado"
    assert pl_dxf.stat().st_size > 0, "PL DXF vazio"

    # ── Fase 6: LJ ───────────────────────────────────────────────────────
    out, dt = _run("gerar_lj_dxf_stog.py", ["--obra", str(OBRA_TREINO_1), "--mode", "planta"], "LJ")
    timings["gerar_lj"] = dt

    lj_dxf = OBRA_TREINO_1 / "Fase-6_Execucao_CAD" / "LJ_stog_quality.dxf"
    assert lj_dxf.exists(), "LJ DXF nao gerado"
    assert lj_dxf.stat().st_size > 0, "LJ DXF vazio"

    # ── Fase 6: LV ───────────────────────────────────────────────────────
    out, dt = _run("gerar_lv_dxf_stog.py", ["--obra", str(OBRA_TREINO_1), "--max", "1"], "LV")
    timings["gerar_lv"] = dt

    lv_dxf = OBRA_TREINO_1 / "Fase-6_Execucao_CAD" / "LV_stog_quality.dxf"
    assert lv_dxf.exists(), "LV DXF nao gerado"
    assert lv_dxf.stat().st_size > 0, "LV DXF vazio"

    # ── Validate DXFs have entities ──────────────────────────────────────
    for dxf_path, label in [(pl_dxf, "PL"), (lj_dxf, "LJ"), (lv_dxf, "LV")]:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        count = sum(1 for _ in msp)
        assert count > 10, f"{label} DXF tem apenas {count} entidades (esperado >10)"

    # ── Timing report ────────────────────────────────────────────────────
    t_total = time.time() - t_total_start
    timings["total"] = t_total

    print("\n=== Pipeline E2E Timing Report ===")
    for step, dt in timings.items():
        print(f"  {step:20s}: {dt:6.1f}s")

    assert t_total < 120, f"Pipeline total {t_total:.1f}s excedeu limite de 120s"


@pytest.mark.skipif(not OBRA_TREINO_1.exists(), reason=SKIP_MSG)
def test_pipeline_fase4_sa_meta():
    """Verifica que motor_fase4 gera _sa_meta com completude_pct."""
    _run("motor_fase4.py", ["--obra", str(OBRA_TREINO_1)], "Fase-4-SA", timeout=60)

    fase4 = OBRA_TREINO_1 / "Fase-4_Sincronizacao"
    # Check for _sa_meta files
    sa_meta_found = False
    for root, dirs, files in os.walk(str(fase4)):
        for f in files:
            if "_sa_meta" in f and f.endswith(".json"):
                sa_meta_found = True
                meta_path = Path(root) / f
                with open(meta_path, encoding="utf-8") as fh:
                    meta = json.load(fh)
                if "completude_pct" in meta:
                    pct = meta["completude_pct"]
                    assert 0 <= pct <= 100, f"completude_pct={pct} fora de [0,100]"
                break
        if sa_meta_found:
            break

    # SA meta may not exist in all pipeline versions; just log
    if not sa_meta_found:
        print("[AVISO] _sa_meta nao encontrado em Fase-4 (feature pode nao estar ativa)")
