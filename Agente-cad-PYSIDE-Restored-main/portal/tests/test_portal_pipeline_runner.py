"""Testes reais (dry_run=False) de executar_triagem/executar_recortes — 2026-07-06.

Achado antes deste arquivo existir: a suíte inteira só exercitava `dry_run=True`
(que nem chama o código de verdade) para as etapas triagem/recortes — o rewrite que
troca "rodar headless 3x" por "conversão+sanidade" (triagem) e "RecorteMotor real"
(recortes) nunca tinha sido testado com `dry_run=False`. Estes testes rodam o
código real (sem mock do que importa: ezdxf de verdade, RecorteMotor de verdade).

A conversão DWG->DXF via accoreconsole (precisa de AutoCAD instalado, ~10-90s) NÃO é
testada aqui — pesada demais para a suíte rápida; validada manualmente uma vez.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from portal.app import pipeline_runner


def _dxf_valido(path: Path) -> None:
    import ezdxf

    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)


def _obra_com_entrada(tmp_path: Path, nome_arquivo: str = "teste.dxf") -> tuple[Path, dict]:
    obra_dir = tmp_path / "obra_teste"
    entrada = obra_dir / "entrada" / nome_arquivo
    if nome_arquivo.endswith(".dxf"):
        _dxf_valido(entrada)
    else:
        entrada.parent.mkdir(parents=True, exist_ok=True)
        entrada.write_bytes(b"nao e' um dwg de verdade")
    obra = {"nome": "obra_teste", "local_path": str(obra_dir), "arquivo_nome": nome_arquivo}
    return obra_dir, obra


# --------------------------------------------------------------------------- #
# executar_triagem — conversao (se preciso) + sanidade ezdxf real
# --------------------------------------------------------------------------- #

def test_triagem_com_dxf_valido_passa_sanidade(settings, tmp_path):
    _, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    r = pipeline_runner.executar_triagem(settings, obra, dry_run=False)
    assert r.ok, r.log_tail
    assert "dxf_entrada" in r.artefatos
    assert Path(r.artefatos["dxf_entrada"]).exists()


def test_triagem_sem_arquivo_falha_com_mensagem_clara(settings, tmp_path):
    obra_dir = tmp_path / "obra_vazia"
    obra_dir.mkdir(parents=True)
    obra = {"nome": "obra_vazia", "local_path": str(obra_dir), "arquivo_nome": None}
    r = pipeline_runner.executar_triagem(settings, obra, dry_run=False)
    assert not r.ok
    assert "nenhum arquivo" in r.log_tail.lower()


def test_triagem_dxf_corrompido_falha_na_sanidade_r6(settings, tmp_path):
    """R6: arquivo que não é DXF de verdade deve falhar na validação ezdxf, não passar."""
    obra_dir = tmp_path / "obra_corrompida"
    entrada = obra_dir / "entrada" / "teste.dxf"
    entrada.parent.mkdir(parents=True)
    entrada.write_bytes(b"isto nao e um dxf valido, so bytes aleatorios \x00\x01\x02")
    obra = {"nome": "obra_corrompida", "local_path": str(obra_dir), "arquivo_nome": "teste.dxf"}

    r = pipeline_runner.executar_triagem(settings, obra, dry_run=False)
    assert not r.ok
    assert "sanidade" in r.log_tail.lower()


def test_triagem_dry_run_nao_toca_disco(settings, tmp_path):
    obra_dir = tmp_path / "obra_dry"
    obra = {"nome": "obra_dry", "local_path": str(obra_dir)}
    r = pipeline_runner.executar_triagem(settings, obra, dry_run=True)
    assert r.ok and r.dry_run
    assert not obra_dir.exists()  # nada foi criado — dry_run de verdade


# --------------------------------------------------------------------------- #
# executar_recortes — RecorteMotor real (não headless duplicado)
# --------------------------------------------------------------------------- #

def test_recortes_com_dxf_minimo_roda_motor_sem_crashar(settings, tmp_path):
    """DXF mínimo (1 linha) não tem blocos STOG -> 0 elementos, mas o motor RODOU
    de verdade (não é mais o mesmo comando de triagem/sa duplicado)."""
    obra_dir, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    r = pipeline_runner.executar_recortes(settings, obra, dry_run=False)
    assert r.ok, r.log_tail
    assert r.artefatos["total_elementos"] == 0  # DXF mínimo não tem elemento nenhum
    assert (obra_dir / "Fase-2_Triagem" / "recortes_reversos").exists()
    # confirma que passou pelas 4 classes reais (não é um stub)
    for classe in ("PIL", "LV", "FV", "LAJ"):
        assert classe in r.log_tail


def test_recortes_sem_dxf_falha_pedindo_triagem_primeiro(settings, tmp_path):
    obra_dir = tmp_path / "obra_sem_dxf"
    obra_dir.mkdir(parents=True)
    obra = {"nome": "obra_sem_dxf", "local_path": str(obra_dir), "arquivo_nome": None}
    r = pipeline_runner.executar_recortes(settings, obra, dry_run=False)
    assert not r.ok
    assert "triagem" in r.log_tail.lower()


def test_recortes_dry_run_nao_toca_disco(settings, tmp_path):
    obra_dir = tmp_path / "obra_dry2"
    obra = {"nome": "obra_dry2", "local_path": str(obra_dir)}
    r = pipeline_runner.executar_recortes(settings, obra, dry_run=True)
    assert r.ok and r.dry_run
    assert not obra_dir.exists()


# --------------------------------------------------------------------------- #
# executar_etapa — dispatch correto por etapa (não mais o mesmo comando 3x)
# --------------------------------------------------------------------------- #

def test_executar_etapa_dispatch_triagem_recortes_sao_diferentes(settings, tmp_path):
    """Regressão do bug 2026-07-06: triagem e recortes tinham comando IDÊNTICO."""
    _, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    r_triagem = pipeline_runner.executar_etapa(settings, "triagem", obra, dry_run=True)
    r_recortes = pipeline_runner.executar_etapa(settings, "recortes", obra, dry_run=True)
    assert r_triagem.comando != r_recortes.comando


def test_executar_etapa_sa_continua_chamando_headless(settings, tmp_path):
    _, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    r = pipeline_runner.executar_etapa(settings, "sa", obra, dry_run=True)
    assert "headless_sa_analise" in " ".join(r.comando)
