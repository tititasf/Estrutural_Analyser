"""Item QA refaz a revisão quando o SA muda no meio; na 3ª vez vira falha (dono 2026-10-02)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from portal.app import qa_jobs, qa_versions
from portal.db import repository as repo
from scripts.arete.qa_cli_fallback import ItemResult


def _rodada(conn):
    membro = repo.criar_membro(conn, login="ana", nome="Ana", senha_hash="h", drive_folder_id="f")
    obra = repo.criar_obra(conn, membro_id=membro, nome="Obra", pasta_drive_id="p")
    round_id, _ = repo.enfileirar_qa_round(conn, obra_id=obra, membro_id=membro, classe="PIL",
                                           pavimento="13_PAV", layer="L1", items=["P9"])
    return round_id


@pytest.fixture()
def fakes(monkeypatch, settings, tmp_path):
    settings.repo_root = tmp_path
    estado = {"preparos": 0, "versoes_mudam": 0, "persistidos": 0}

    def prepare(settings_, obra, qa_round, item_id):
        estado["preparos"] += 1
        pasta = tmp_path / "scripts/arete/relatorios/qa_portal" / qa_round["id"] / item_id
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "fields.json").write_text("{}", encoding="utf-8")
        return {}, f"<svg v{estado['preparos']}/>", tmp_path

    def source(*args, **kwargs):
        # as primeiras `versoes_mudam` revisões veem o SA trocado ao final
        if estado["preparos"] <= estado["versoes_mudam"]:
            return "<svg outra/>", {}
        return f"<svg v{estado['preparos']}/>", {}

    def run_round(**kwargs):
        item = ItemResult(item="P9", layer="L1", status="completed", provider="fake", model="m",
                          verdict="validou", note="ok", suggestion={"action": "manter"})
        return SimpleNamespace(items=[item])

    monkeypatch.setattr(qa_versions, "prepare", prepare)
    monkeypatch.setattr(qa_versions, "source", source)
    monkeypatch.setattr(qa_versions, "digest", lambda svg: svg)
    monkeypatch.setattr(qa_versions, "interpretation_digest", lambda svg, fields: json.dumps(fields))
    monkeypatch.setattr(qa_versions, "persist",
                        lambda *a, **k: estado.__setitem__("persistidos", estado["persistidos"] + 1))
    monkeypatch.setattr(qa_jobs, "run_round", run_round)
    monkeypatch.setattr(repo, "gravar_resultado_qa_item",
                        lambda conn, rid, result: estado.__setitem__("resultado", result))
    return estado


def _executar(conn, settings, tmp_path):
    rid = _rodada(conn)
    qa_jobs.executar_qa_round(settings=settings, conn=conn, round_id=rid,
                              log_path=tmp_path / "qa.log", providers=[SimpleNamespace(config=None)])
    return rid


def test_sa_muda_uma_vez_refaz_com_versao_nova(conn, settings, tmp_path, fakes):
    fakes["versoes_mudam"] = 1
    _executar(conn, settings, tmp_path)
    assert fakes["preparos"] == 2
    assert fakes["persistidos"] == 1
    assert fakes["resultado"].status == "completed"


def test_sa_muda_tres_vezes_vira_falha_provavel_bug(conn, settings, tmp_path, fakes):
    fakes["versoes_mudam"] = 99
    _executar(conn, settings, tmp_path)
    assert fakes["preparos"] == qa_jobs.MAX_TENTATIVAS_VERSAO == 3
    assert fakes["persistidos"] == 0
    assert fakes["resultado"].status == "failed"
    assert "provável bug" in fakes["resultado"].note
