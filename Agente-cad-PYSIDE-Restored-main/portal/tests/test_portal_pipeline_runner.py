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

import json
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


def test_recortes_multi_doc_roda_torre_crop_pra_cada_bruto(settings, tmp_path):
    """[2026-07-07] Obra com N documentos (entrada/ tem N arquivos) — torre_crop
    tem que rodar UMA VEZ POR BRUTO, não só pro primeiro. Achado com o dono:
    a aba Recortes tinha que virar "1 pasta por documento"."""
    obra_dir, obra = _obra_com_entrada(tmp_path, "doc_a.dxf")
    _dxf_valido(obra_dir / "entrada" / "doc_b.dxf")
    r = pipeline_runner.executar_recortes(settings, obra, dry_run=False)
    assert r.ok, r.log_tail
    assert r.artefatos["brutos_processados"] == 2
    assert "doc_a" in r.log_tail
    assert "doc_b" in r.log_tail


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


# --------------------------------------------------------------------------- #
# P4 — microciclo secao+item com --persist-db
# --------------------------------------------------------------------------- #

def test_microciclo_item_monta_comando_com_secao_item_persist(settings, tmp_path):
    _, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    r = pipeline_runner.executar_microciclo_item(
        settings, obra, secao="pilares", item="P900", pav="13_PAV", dry_run=True,
    )
    assert r.ok and r.dry_run
    assert r.etapa == "sa_item"
    cmd = r.comando
    assert "headless_sa_analise" in " ".join(cmd)
    assert "--secao" in cmd and "pilares" in cmd
    assert "--item" in cmd and "P900" in cmd
    assert "--wait" in cmd
    assert "--persist-db" in cmd


def test_montar_comando_secao_sem_item_nao_tem_persist(settings, tmp_path):
    """Script recusa --persist-db com --secao sem --item — não montar lixo."""
    _, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    cmd = pipeline_runner.montar_comando_headless(
        settings, obra, secao=["lajes"], pav="13_PAV",
    )
    assert "--secao" in cmd and "lajes" in cmd
    assert "--item" not in cmd
    assert "--persist-db" not in cmd


def test_montar_comando_completo_sem_secao_tem_persist(settings, tmp_path):
    _, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    cmd = pipeline_runner.montar_comando_headless(settings, obra, pav="13_PAV")
    assert "--secao" not in cmd
    assert "--persist-db" in cmd


def test_microciclo_exige_secao_e_item(settings, tmp_path):
    _, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    with pytest.raises(ValueError):
        pipeline_runner.executar_microciclo_item(
            settings, obra, secao="", item="P1", dry_run=True,
        )
    with pytest.raises(ValueError):
        pipeline_runner.executar_microciclo_item(
            settings, obra, secao="pilares", item="  ", dry_run=True,
        )


# --------------------------------------------------------------------------- #
# executar_triagem_documentos — obra-como-container (2026-07-06): triagem em
# LOTE de N documentos de uma mesma obra, cada um com seu proprio veredito.
# --------------------------------------------------------------------------- #

def test_triagem_documentos_lote_com_dxfs_validos_passa_todos(settings, tmp_path):
    obra_dir = tmp_path / "obra_lote"
    _dxf_valido(obra_dir / "entrada" / "a.dxf")
    _dxf_valido(obra_dir / "entrada" / "b.dxf")
    obra = {"nome": "obra_lote", "local_path": str(obra_dir)}
    documentos = [
        {"id": "doc-a", "arquivo_nome": "a.dxf"},
        {"id": "doc-b", "arquivo_nome": "b.dxf"},
    ]
    r = pipeline_runner.executar_triagem_documentos(settings, obra, documentos, dry_run=False)
    assert r.ok, r.log_tail
    resultados = r.artefatos["documentos"]
    assert len(resultados) == 2
    assert all(item["ok"] for item in resultados)
    assert {item["doc_id"] for item in resultados} == {"doc-a", "doc-b"}


def test_triagem_documentos_lote_com_pdf_pula_conversao_sanidade(settings, tmp_path):
    """[2026-07-07] PDF é material de referência (tipo_documento='PDF') — não
    tenta converter/validar como DXF (ezdxf não abre PDF), só marca ok direto."""
    obra_dir = tmp_path / "obra_com_pdf"
    _dxf_valido(obra_dir / "entrada" / "a.dxf")
    (obra_dir / "entrada" / "memorial.pdf").write_bytes(b"%PDF-1.4 conteudo fake")
    obra = {"nome": "obra_com_pdf", "local_path": str(obra_dir)}
    documentos = [
        {"id": "doc-dxf", "arquivo_nome": "a.dxf"},
        {"id": "doc-pdf", "arquivo_nome": "memorial.pdf"},
    ]
    r = pipeline_runner.executar_triagem_documentos(settings, obra, documentos, dry_run=False)
    assert r.ok, r.log_tail
    resultados = {item["doc_id"]: item for item in r.artefatos["documentos"]}
    assert resultados["doc-dxf"]["ok"] is True
    assert resultados["doc-pdf"]["ok"] is True
    assert resultados["doc-pdf"]["dxf_path"] is None
    assert "PDF" in r.log_tail


def test_triagem_documentos_lote_misto_reporta_cada_um_por_si(settings, tmp_path):
    """1 arquivo valido + 1 corrompido + 1 ausente no mesmo lote — cada doc tem
    seu proprio veredito (ok=True/False), o lote como um todo continua (nao para
    tudo por causa de 1 documento ruim)."""
    obra_dir = tmp_path / "obra_lote_misto"
    _dxf_valido(obra_dir / "entrada" / "bom.dxf")
    (obra_dir / "entrada").mkdir(parents=True, exist_ok=True)
    (obra_dir / "entrada" / "corrompido.dxf").write_bytes(b"nao e dxf \x00\x01")
    obra = {"nome": "obra_lote_misto", "local_path": str(obra_dir)}
    documentos = [
        {"id": "doc-bom", "arquivo_nome": "bom.dxf"},
        {"id": "doc-corrompido", "arquivo_nome": "corrompido.dxf"},
        {"id": "doc-ausente", "arquivo_nome": "nao_existe.dxf"},
    ]
    r = pipeline_runner.executar_triagem_documentos(settings, obra, documentos, dry_run=False)
    assert r.ok  # ao menos 1 doc passou -> lote "ok" no nivel de job
    por_id = {item["doc_id"]: item for item in r.artefatos["documentos"]}
    assert por_id["doc-bom"]["ok"] is True
    assert por_id["doc-corrompido"]["ok"] is False
    assert "sanidade" in por_id["doc-corrompido"]["erro_msg"].lower()
    assert por_id["doc-ausente"]["ok"] is False
    assert "nao encontrado" in por_id["doc-ausente"]["erro_msg"].lower()


def test_triagem_documentos_lista_vazia_e_ok_sem_fazer_nada(settings, tmp_path):
    obra_dir = tmp_path / "obra_sem_docs"
    obra = {"nome": "obra_sem_docs", "local_path": str(obra_dir)}
    r = pipeline_runner.executar_triagem_documentos(settings, obra, [], dry_run=False)
    assert r.ok
    assert r.artefatos["documentos"] == []


def test_triagem_documentos_dry_run_nao_toca_disco(settings, tmp_path):
    obra_dir = tmp_path / "obra_lote_dry"
    obra = {"nome": "obra_lote_dry", "local_path": str(obra_dir)}
    documentos = [{"id": "doc-x", "arquivo_nome": "x.dxf"}]
    r = pipeline_runner.executar_triagem_documentos(settings, obra, documentos, dry_run=True)
    assert r.ok and r.dry_run
    assert not obra_dir.exists()


# --------------------------------------------------------------------------- #
# _garantir_project_registrado — auto-registro em project_data.vision (2026-07-06)
# Achado real rodando o fluxo inteiro contra uma obra nova: `resolve_sa_project_
# from_db` levantava LookupError porque a obra nunca tinha sido registrada em
# `projects` (isso so' acontecia abrindo o DXF no app desktop). `settings.sa_db_path`
# aqui SEMPRE aponta pra tmp (conftest.py) — nunca toca o project_data.vision real.
# --------------------------------------------------------------------------- #

def test_garantir_project_registra_quando_nao_existe(settings, tmp_path):
    from src.core.database import DatabaseManager
    from src.core.sa_project_source import select_sa_project

    obra_dir, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    # simula o dxf ja' convertido pela triagem (mesmo nome, .dxf)
    pipeline_runner._garantir_project_registrado(settings, obra, "13_PAV")

    database = DatabaseManager(db_path=str(settings.sa_db_path))
    projetos = database.get_projects()
    achado = select_sa_project(projetos, obra=str(obra_dir), pavimento="13_PAV")
    assert achado["work_name"] == str(obra_dir)
    assert Path(achado["dxf_path"]).exists()


def test_garantir_project_e_idempotente_nao_duplica(settings, tmp_path):
    from src.core.database import DatabaseManager

    obra_dir, obra = _obra_com_entrada(tmp_path, "teste.dxf")
    pipeline_runner._garantir_project_registrado(settings, obra, "13_PAV")
    pipeline_runner._garantir_project_registrado(settings, obra, "13_PAV")  # de novo

    database = DatabaseManager(db_path=str(settings.sa_db_path))
    projetos = [p for p in database.get_projects() if p.get("work_name") == str(obra_dir)]
    assert len(projetos) == 1  # nao duplicou so' porque chamou 2x


def test_garantir_project_obra_container_sem_arquivo_nome_nao_registra(settings, tmp_path):
    """Obra-container (multi-doc, arquivo_nome=None) fica fora de escopo — nao
    inventa qual documento registrar."""
    from src.core.database import DatabaseManager

    obra_dir = tmp_path / "obra_container"
    obra = {"nome": "obra_container", "local_path": str(obra_dir), "arquivo_nome": None}
    pipeline_runner._garantir_project_registrado(settings, obra, "13_PAV")

    database = DatabaseManager(db_path=str(settings.sa_db_path))
    projetos = [p for p in database.get_projects() if p.get("work_name") == str(obra_dir)]
    assert projetos == []


def test_garantir_project_sem_dxf_convertido_ainda_nao_registra(settings, tmp_path):
    """Sem o DXF (triagem ainda nao rodou) nao ha' o que registrar — deixa o
    erro real acontecer no SA em vez de registrar um dxf_path inexistente."""
    from src.core.database import DatabaseManager

    obra_dir = tmp_path / "obra_sem_dxf"
    obra_dir.mkdir(parents=True)
    obra = {"nome": "obra_sem_dxf", "local_path": str(obra_dir), "arquivo_nome": "x.dwg"}
    pipeline_runner._garantir_project_registrado(settings, obra, "13_PAV")

    database = DatabaseManager(db_path=str(settings.sa_db_path))
    projetos = [p for p in database.get_projects() if p.get("work_name") == str(obra_dir)]
    assert projetos == []


# --------------------------------------------------------------------------- #
# encontrar_dir_fichas — achado real rodando o SA de verdade contra uma obra
# nova: as fichas ficam em <obra_dir>/<pavimento>_<run_id>/, NAO em
# "Fase-6_Execucao_CAD" (path fixo que nunca existiu de verdade).
# --------------------------------------------------------------------------- #

def test_encontrar_dir_fichas_pega_a_rodada_mais_recente(tmp_path):
    obra_dir = tmp_path / "obra_com_fichas"
    obra_dir.mkdir()
    antiga = obra_dir / "13_PAV_20260706_100000"
    antiga.mkdir()
    (antiga / "arete_manifest.json").write_text("{}", encoding="utf-8")
    (antiga / "index.html").write_text("<html>antiga</html>", encoding="utf-8")

    recente = obra_dir / "13_PAV_20260706_181817"
    recente.mkdir()
    (recente / "arete_manifest.json").write_text("{}", encoding="utf-8")
    (recente / "index.html").write_text("<html>recente</html>", encoding="utf-8")

    achado = pipeline_runner.encontrar_dir_fichas(obra_dir)
    assert achado == recente


def test_encontrar_dir_fichas_ignora_pastas_sem_manifest(tmp_path):
    """Pasta sem arete_manifest.json nao e' uma rodada real do SA (ex.: 'entrada',
    'Fase-2_Triagem') — nao deve ser confundida com um diretorio de fichas."""
    obra_dir = tmp_path / "obra_mista"
    (obra_dir / "entrada").mkdir(parents=True)
    (obra_dir / "Fase-2_Triagem").mkdir(parents=True)
    assert pipeline_runner.encontrar_dir_fichas(obra_dir) is None


def test_encontrar_dir_fichas_obra_sem_sa_ainda_devolve_none(tmp_path):
    obra_dir = tmp_path / "obra_nova_sem_sa"
    obra_dir.mkdir()
    assert pipeline_runner.encontrar_dir_fichas(obra_dir) is None
    assert pipeline_runner.encontrar_dir_fichas(tmp_path / "nao_existe") is None


def test_triagem_documentos_grava_log_consolidado_quando_log_path_passado(settings, tmp_path):
    obra_dir = tmp_path / "obra_com_log"
    _dxf_valido(obra_dir / "entrada" / "a.dxf")
    obra = {"nome": "obra_com_log", "local_path": str(obra_dir)}
    log_path = tmp_path / "logs" / "job_x.log"
    r = pipeline_runner.executar_triagem_documentos(
        settings, obra, [{"id": "doc-a", "arquivo_nome": "a.dxf"}],
        dry_run=False, log_path=log_path,
    )
    assert r.ok
    assert log_path.exists()
    assert "a.dxf" in log_path.read_text(encoding="utf-8")


def test_promover_snapshot_sa_publica_estado_canonico_atomico(tmp_path):
    obra_dir = tmp_path / "obra_snapshot"
    obra_dir.mkdir()
    isolated = obra_dir / "estado_TERREO_pilares_pid123.json"
    isolated.write_text(json.dumps({
        "pilares": [{"name": "P1", "points": [[0, 0], [1, 0], [1, 1], [0, 1]]}],
        "slabs": [], "cortes": [], "segmentos": {},
    }), encoding="utf-8")
    promoted = pipeline_runner.promover_snapshot_sa(obra_dir, "TERREO")
    assert promoted == obra_dir / "estado_TERREO.json"
    payload = json.loads(promoted.read_text(encoding="utf-8"))
    assert payload["pilares"][0]["name"] == "P1"
    assert not list(obra_dir.glob(".estado_TERREO.json.*.tmp"))


def test_promover_snapshot_sa_rejeita_payload_sem_pilares(tmp_path):
    obra_dir = tmp_path / "obra_snapshot_invalido"
    obra_dir.mkdir()
    (obra_dir / "estado_TERREO_pid9.json").write_text(
        json.dumps({"slabs": []}), encoding="utf-8",
    )
    assert pipeline_runner.promover_snapshot_sa(obra_dir, "TERREO") is None
    assert not (obra_dir / "estado_TERREO.json").exists()


def _escrever_pacote_n3_minimo(obra_dir: Path, name: str = "P1") -> None:
    root = obra_dir / "Fase-6_Execucao_CAD" / "n3_variants"
    for mode in ("para", "passa"):
        folder = root / mode
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.json").write_text("{}", encoding="utf-8")
        (folder / f"PL_ABCD_preview_{name}.dxf").write_text("DXF", encoding="utf-8")
        (folder / f"PL_GRADES_preview_{name}.dxf").write_text("DXF", encoding="utf-8")


def test_job_sa_publica_n1_materializa_ficha_e_audita_n3(settings, tmp_path, monkeypatch):
    obra_dir = tmp_path / "obra_sa_integrada"
    obra_dir.mkdir()
    obra = {"nome": "obra_sa_integrada", "local_path": str(obra_dir)}
    monkeypatch.setattr(pipeline_runner, "_garantir_project_registrado", lambda *a, **k: None)

    def fake_run(*args, **kwargs):
        (obra_dir / "estado_TERREO_pid777.json").write_text(json.dumps({
            "pilares": [{
                "name": "P1",
                "points": [[0, 0], [40, 0], [40, 20], [0, 20], [0, 0]],
            }],
            "slabs": [], "cortes": [], "segmentos": {},
        }), encoding="utf-8")
        _escrever_pacote_n3_minimo(obra_dir)
        return pipeline_runner.subprocess.CompletedProcess(args[0], 0, "SA ok", "")

    monkeypatch.setattr(pipeline_runner.subprocess, "run", fake_run)
    result = pipeline_runner._rodar_subprocess_sa(
        settings, ["python", "headless"], obra=obra, etapa="sa",
        dry_run=False, log_path=None, pav="TERREO",
    )
    assert result.ok, result.log_tail
    assert (obra_dir / "estado_TERREO.json").is_file()
    assert result.artefatos["pilar_n3_fichas"]["created"] == 1
    assert result.artefatos["pilar_n3"]["variantes_completas"] == 2
    from src.core.pillar_n3_ficha import ficha_path
    assert ficha_path(obra_dir, "TERREO", "P1").is_file()


def test_job_sa_nao_declara_sucesso_com_desenhos_n3_ausentes(settings, tmp_path, monkeypatch):
    obra_dir = tmp_path / "obra_sa_sem_n3"
    obra_dir.mkdir()
    obra = {"nome": "obra_sa_sem_n3", "local_path": str(obra_dir)}
    monkeypatch.setattr(pipeline_runner, "_garantir_project_registrado", lambda *a, **k: None)

    def fake_run(*args, **kwargs):
        (obra_dir / "estado_TERREO_pid778.json").write_text(json.dumps({
            "pilares": [{
                "name": "P1",
                "points": [[0, 0], [40, 0], [40, 20], [0, 20], [0, 0]],
            }],
        }), encoding="utf-8")
        return pipeline_runner.subprocess.CompletedProcess(args[0], 0, "SA parcial", "")

    monkeypatch.setattr(pipeline_runner.subprocess, "run", fake_run)
    result = pipeline_runner._rodar_subprocess_sa(
        settings, ["python", "headless"], obra=obra, etapa="sa",
        dry_run=False, log_path=None, pav="TERREO",
    )
    assert not result.ok
    assert len(result.artefatos["pilar_n3"]["missing"]) == 6
    assert "pacote N3 de pilares incompleto" in result.log_tail
