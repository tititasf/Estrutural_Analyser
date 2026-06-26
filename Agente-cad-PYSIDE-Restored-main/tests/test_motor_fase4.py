"""
test_motor_fase4.py — Testes do motor de transformação Fase-3 → Fase-4.

Cobre:
  - Smoke test com obra real (Obra_TREINO_1)
  - Obra sem Fase-3 (diretório inexistente)
  - Fichas com dados inválidos (b=0, h=0, comprimento=0)
  - Fichas com JSON corrompido
  - Verificação de _sa_meta nos JSONs gerados
  - Verificação de completude_pct para obra válida
  - Relatório de completude SA via validar_pipeline_sa.py

Todos unitários/headless (sem UI, sem PySide6).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MOTOR_SCRIPT = SCRIPTS_DIR / "motor_fase4.py"
VALIDAR_SCRIPT = SCRIPTS_DIR / "validar_pipeline_sa.py"
REAL_OBRA = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _run_motor(obra: Path, extra_args: list = None, timeout: int = 60) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-u", str(MOTOR_SCRIPT), "--obra", str(obra)]
    if extra_args:
        cmd += extra_args
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=env)


def _run_validar(obra: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-u", str(VALIDAR_SCRIPT), "--obra", str(obra)]
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=env)


def _make_fase3_minima(tmp_path: Path, com_pilares: bool = True,
                       com_vigas: bool = True, com_lajes: bool = True) -> Path:
    """Cria estrutura mínima de Fase-3 com fichas válidas."""
    obra = tmp_path / "Obra_MOTOR_TEST"
    fase3 = obra / "Fase-3_Interpretacao_Extracao"

    if com_pilares:
        (fase3 / "Pilares").mkdir(parents=True)
        pilares = {
            "P1": {"b": 19.0, "h": 88.0, "confidence": 0.9, "source": "test"},
            "P2": {"b": 19.0, "h": 73.0, "confidence": 0.8, "source": "test"},
        }
        (fase3 / "Pilares" / "pilares_bh.json").write_text(
            json.dumps(pilares), encoding="utf-8")

    if com_vigas:
        (fase3 / "Vigas").mkdir(parents=True)
        vigas = {
            "V101": {"b": 19.0, "h": 120.0, "comprimento": 518.0, "confidence": 0.8, "source": "test"},
        }
        (fase3 / "Vigas" / "vigas.json").write_text(
            json.dumps(vigas), encoding="utf-8")

    if com_lajes:
        (fase3 / "Lajes").mkdir(parents=True)
        lajes = {
            "L101": {
                "comprimento": 300.0, "largura": 200.0,
                "coordenadas": [[0, 0], [300, 0], [300, 200], [0, 0]],
                "area_cm2": 60000.0, "confidence": 0.75, "source": "test",
                "modo_selecionado": 0,
            },
        }
        (fase3 / "Lajes" / "lajes.json").write_text(
            json.dumps(lajes), encoding="utf-8")

    return obra


# ──────────────────────────────────────────────────────────────────────────────
# Testes: obra real
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not REAL_OBRA.exists(), reason="Obra_TREINO_1 não encontrada")
def test_motor_obra_real_exit_zero():
    """motor_fase4 deve processar obra real sem erros."""
    result = _run_motor(REAL_OBRA, timeout=90)
    assert result.returncode == 0, f"motor_fase4 falhou:\n{result.stderr[:300]}"


@pytest.mark.skipif(not REAL_OBRA.exists(), reason="Obra_TREINO_1 não encontrada")
def test_motor_obra_real_gera_jsons():
    """motor_fase4 deve gerar JSONs em todos os 4 diretórios."""
    _run_motor(REAL_OBRA, timeout=90)
    fase4 = REAL_OBRA / "Fase-4_Sincronizacao"
    for subdir in ["JSON_Pilares", "JSON_Vigas_Laterais", "JSON_Vigas_Fundo", "JSON_Lajes"]:
        d = fase4 / subdir
        assert d.exists(), f"{subdir} não criado"
        jsons = list(d.glob("*.json"))
        assert len(jsons) > 0, f"{subdir} vazio"


@pytest.mark.skipif(not REAL_OBRA.exists(), reason="Obra_TREINO_1 não encontrada")
def test_motor_obra_real_sa_meta_presente():
    """Todos os JSONs gerados devem ter _sa_meta."""
    _run_motor(REAL_OBRA, timeout=90)
    fase4 = REAL_OBRA / "Fase-4_Sincronizacao"
    sem_meta = []
    for subdir in ["JSON_Pilares", "JSON_Vigas_Laterais", "JSON_Vigas_Fundo", "JSON_Lajes"]:
        for jf in (fase4 / subdir).glob("*.json"):
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
            if "_sa_meta" not in data:
                sem_meta.append(jf.name)

    assert len(sem_meta) == 0, f"JSONs sem _sa_meta: {sem_meta[:10]}"


@pytest.mark.skipif(not REAL_OBRA.exists(), reason="Obra_TREINO_1 não encontrada")
def test_motor_obra_real_completude_100():
    """_sa_meta.completude_pct deve ser 100% para obra com todos os dados."""
    _run_motor(REAL_OBRA, timeout=90)
    fase4 = REAL_OBRA / "Fase-4_Sincronizacao"
    baixa_completude = []
    for subdir in ["JSON_Pilares", "JSON_Vigas_Laterais", "JSON_Lajes"]:
        for jf in (fase4 / subdir).glob("*.json"):
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("_sa_meta", {})
            pct = meta.get("completude_pct", 0)
            if pct < 100:
                baixa_completude.append((jf.name, pct))

    assert len(baixa_completude) == 0, (
        f"Itens com completude < 100%: {baixa_completude[:5]}"
    )


@pytest.mark.skipif(not REAL_OBRA.exists(), reason="Obra_TREINO_1 não encontrada")
def test_validar_pipeline_sa_pass():
    """validar_pipeline_sa.py deve retornar exit 0 para obra válida."""
    result = _run_validar(REAL_OBRA)
    assert result.returncode == 0, (
        f"validar_pipeline_sa retornou {result.returncode}:\n{result.stdout[:300]}"
    )
    assert "STATUS: OK" in result.stdout, (
        f"Status não OK:\n{result.stdout[:300]}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Testes: obra sem Fase-3
# ──────────────────────────────────────────────────────────────────────────────

def test_motor_sem_fase3_nao_trava(tmp_path):
    """motor_fase4 deve encerrar limpo quando Fase-3 não existe."""
    obra = tmp_path / "Obra_SEM_FASE3"
    obra.mkdir()
    result = _run_motor(obra)
    assert result.returncode == 0, (
        f"motor_fase4 travou sem Fase-3 (rc={result.returncode}):\n{result.stderr[:200]}"
    )


def test_motor_sem_fase3_nao_gera_jsons(tmp_path):
    """Sem Fase-3, não deve criar arquivos JSON em Fase-4."""
    obra = tmp_path / "Obra_SEM_FASE3"
    obra.mkdir()
    _run_motor(obra)
    fase4 = obra / "Fase-4_Sincronizacao"
    if fase4.exists():
        for subdir in ["JSON_Pilares", "JSON_Vigas_Laterais", "JSON_Vigas_Fundo", "JSON_Lajes"]:
            jsons = list((fase4 / subdir).glob("*.json")) if (fase4 / subdir).exists() else []
            assert len(jsons) == 0, f"{subdir} não deveria ter JSONs sem Fase-3"


# ──────────────────────────────────────────────────────────────────────────────
# Testes: dados inválidos
# ──────────────────────────────────────────────────────────────────────────────

def test_motor_pilar_b_zero(tmp_path):
    """Pilar com b=0 e h=0 deve ser pulado sem crash."""
    obra = _make_fase3_minima(tmp_path, com_vigas=False, com_lajes=False)
    # Sobrescrever com pilar inválido
    pilares = {"P1": {"b": 0, "h": 0}}
    (obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares_bh.json").write_text(
        json.dumps(pilares), encoding="utf-8")

    result = _run_motor(obra)
    assert result.returncode == 0, f"Crash com pilar b=0:\n{result.stderr[:200]}"
    # JSON_Pilares deve existir mas estar vazio
    fase4 = obra / "Fase-4_Sincronizacao" / "JSON_Pilares"
    jsons = list(fase4.glob("P*.json")) if fase4.exists() else []
    assert len(jsons) == 0, f"Pilar inválido não deveria gerar JSON: {[j.name for j in jsons]}"


def test_motor_viga_comprimento_zero(tmp_path):
    """Viga com comprimento=0 deve ser pulada sem crash."""
    obra = _make_fase3_minima(tmp_path, com_pilares=False, com_lajes=False)
    vigas = {"V101": {"b": 19.0, "h": 120.0, "comprimento": 0}}
    (obra / "Fase-3_Interpretacao_Extracao" / "Vigas" / "vigas.json").write_text(
        json.dumps(vigas), encoding="utf-8")

    result = _run_motor(obra)
    assert result.returncode == 0, f"Crash com viga comprimento=0:\n{result.stderr[:200]}"


def test_motor_laje_dimensoes_invalidas(tmp_path):
    """Laje com comprimento=0 deve ser pulada sem crash."""
    obra = _make_fase3_minima(tmp_path, com_pilares=False, com_vigas=False)
    lajes = {"L101": {"comprimento": 0, "largura": 0, "area_cm2": 0, "coordenadas": []}}
    (obra / "Fase-3_Interpretacao_Extracao" / "Lajes" / "lajes.json").write_text(
        json.dumps(lajes), encoding="utf-8")

    result = _run_motor(obra)
    assert result.returncode == 0, f"Crash com laje inválida:\n{result.stderr[:200]}"


def test_motor_fichas_json_corrompido(tmp_path):
    """JSON corrompido em Fase-3 não deve causar crash não tratado."""
    obra = tmp_path / "Obra_JSON_CORROMPIDO"
    fase3_pilares = obra / "Fase-3_Interpretacao_Extracao" / "Pilares"
    fase3_pilares.mkdir(parents=True)
    (fase3_pilares / "pilares_bh.json").write_text(
        "{ isto nao e json valido !!!", encoding="utf-8")

    result = _run_motor(obra)
    # Deve sair limpo ou com mensagem de erro, nunca traceback não tratado
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined or result.returncode == 0, (
        f"JSON corrompido causou crash não tratado:\n{result.stderr[:300]}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Testes: fixture mínima válida
# ──────────────────────────────────────────────────────────────────────────────

def test_motor_fixture_minima_gera_sa_meta(tmp_path):
    """Obra com fichas mínimas válidas deve gerar JSONs com _sa_meta."""
    obra = _make_fase3_minima(tmp_path)
    result = _run_motor(obra)
    assert result.returncode == 0, f"motor_fase4 falhou na fixture:\n{result.stderr[:300]}"

    fase4 = obra / "Fase-4_Sincronizacao"
    for subdir, prefix in [("JSON_Pilares", "P"), ("JSON_Vigas_Laterais", "V"),
                            ("JSON_Vigas_Fundo", "V"), ("JSON_Lajes", "L")]:
        jsons = list((fase4 / subdir).glob("*.json"))
        assert len(jsons) > 0, f"{subdir} vazio para fixture mínima"
        for jf in jsons:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
            assert "_sa_meta" in data, f"{jf.name} sem _sa_meta"
            meta = data["_sa_meta"]
            assert "completude_pct" in meta, f"{jf.name}._sa_meta sem completude_pct"
            assert meta["completude_pct"] >= 0, f"completude_pct negativo"


def test_motor_fixture_minima_campos_required(tmp_path):
    """Campos required (comprimento, largura, altura + larg1/parafusos) devem ter valores não-zero."""
    obra = _make_fase3_minima(tmp_path)
    _run_motor(obra)

    # Verificar pilar
    pilar_json = list((obra / "Fase-4_Sincronizacao" / "JSON_Pilares").glob("P*.json"))[0]
    with open(pilar_json, encoding="utf-8") as f:
        pilar = json.load(f)
    assert pilar["comprimento"] > 0, "comprimento do pilar deve ser > 0"
    assert pilar["largura"] > 0, "largura do pilar deve ser > 0"
    assert pilar["altura"] > 0, "altura do pilar deve ser > 0"
    # larg1 computado: faces A/B = comprimento (faces LONGAS), C/D = largura (faces CURTAS)
    # FIX B1 2026-06-04: A e B são faces longas (comprimento), C e D são curtas (largura)
    assert pilar["larg1_A"] == pilar["comprimento"], "larg1_A deve ser igual ao comprimento"
    assert pilar["larg1_B"] == pilar["comprimento"], "larg1_B deve ser igual ao comprimento (face longa)"
    assert pilar["larg1_C"] == pilar["largura"], "larg1_C deve ser igual à largura (face curta)"
    assert pilar["larg1_D"] == pilar["largura"], "larg1_D deve ser igual à largura (face curta)"
    # parafusos computados: par_1_2 deve ser > 0 para pilar com comprimento > 0
    assert pilar["par_1_2"] > 0, "par_1_2 deve ser computado a partir do comprimento"

    # Verificar viga lateral
    lv_json = list((obra / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais").glob("V*.json"))[0]
    with open(lv_json, encoding="utf-8") as f:
        viga = json.load(f)
    assert float(viga["total_width"]) > 0, "total_width da viga deve ser > 0"
    assert float(viga["total_height"]) > 0, "total_height da viga deve ser > 0"

    # Verificar laje
    lj_json = list((obra / "Fase-4_Sincronizacao" / "JSON_Lajes").glob("L*.json"))[0]
    with open(lj_json, encoding="utf-8") as f:
        laje = json.load(f)
    assert laje["comprimento"] > 0, "comprimento da laje deve ser > 0"
    assert laje["largura"] > 0, "largura da laje deve ser > 0"


def test_motor_fixture_minima_na_fields_corretos(tmp_path):
    """na_fields em _sa_meta deve conter campos que não se aplicam ao tipo."""
    obra = _make_fase3_minima(tmp_path)
    _run_motor(obra)

    # Pilar não deve ter panels/holes/coordenadas no _sa_meta.na_fields
    pilar_json = list((obra / "Fase-4_Sincronizacao" / "JSON_Pilares").glob("P*.json"))[0]
    with open(pilar_json, encoding="utf-8") as f:
        pilar = json.load(f)
    na = set(pilar["_sa_meta"]["na_fields"])
    assert "panels" in na, "panels deveria estar em na_fields do pilar"
    assert "holes" in na, "holes deveria estar em na_fields do pilar"
    assert "coordenadas" in na, "coordenadas deveria estar em na_fields do pilar"

    # Laje não deve ter grade_1/grade_2 em na_fields
    lj_json = list((obra / "Fase-4_Sincronizacao" / "JSON_Lajes").glob("L*.json"))[0]
    with open(lj_json, encoding="utf-8") as f:
        laje = json.load(f)
    na_lj = set(laje["_sa_meta"]["na_fields"])
    assert "grade_1" in na_lj, "grade_1 deveria estar em na_fields da laje"
    assert "panels" in na_lj, "panels deveria estar em na_fields da laje"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
