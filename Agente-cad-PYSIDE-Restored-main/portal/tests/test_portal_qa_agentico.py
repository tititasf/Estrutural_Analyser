from __future__ import annotations

import json
import re
import stat
from pathlib import Path

from portal.app import jobs as jobs_mod
from portal.app import qa_jobs
from portal.db import repository as repo
from scripts.arete.qa_cli_fallback import ProviderConfig, TechnicalFailure


class _Provider:
    def __init__(self, name: str, outcome):
        self.config = ProviderConfig(name, f"{name}-model", "high", name, 1)
        self.outcome = outcome
        self.calls: list[str] = []

    def invoke(self, prompt: str, cwd: Path):
        self.calls.append(prompt)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        item = "P9" if "Item: P9." in prompt else "P10"
        payload = {
            "item": item,
            "layer": "L1",
            "verdict": self.outcome,
            "confidence_percent": 91,
            "note": f"evidencia {item}",
            "suggestion": {
                "action": "manter" if self.outcome == "validou" else "corrigir",
                "target_layer": "L1",
                "summary": f"sugestao {item}",
                "proposed": [] if self.outcome == "validou" else [{"role": "face_A_chega"}],
            },
        }
        return json.dumps(payload), self.config.model


class _FVProvider:
    def __init__(self):
        self.config = ProviderConfig("codex", "codex-model", "high", "codex", 1)

    def invoke(self, prompt: str, cwd: Path):
        assert "revisor agentico de FV/SA-N1" in prompt
        return json.dumps({
            "item": "V301", "layer": "L1", "verdict": "invalidou",
            "confidence_percent": 87.5, "note": "segmentação precisa ajuste",
            "suggestion": {"action": "corrigir", "target_layer": "L1",
                           "summary": "separar trecho", "proposed": [
                               {"label": "P1", "points": [[0, 0], [20, 0], [20, 10], [0, 10]]}
                           ]},
        }), self.config.model


class _FVProviderDinamico(_FVProvider):
    def invoke(self, prompt: str, cwd: Path):
        item = re.search(r"Item: ((?:V|VF)\w+)\.", prompt).group(1)
        return json.dumps({
            "item": item, "layer": "L1", "verdict": "validou",
            "confidence_percent": 90, "note": "geometria coerente",
            "suggestion": {"action": "manter", "target_layer": "L1",
                           "summary": "manter", "proposed": []},
        }), self.config.model


def _rodada(conn, tmp_path: Path):
    membro_id = repo.criar_membro(
        conn, login="ana", nome="Ana", senha_hash="h", drive_folder_id="f"
    )
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra_TREINO_1", pasta_drive_id="p"
    )
    round_id, job_id = repo.enfileirar_qa_round(
        conn,
        obra_id=obra_id,
        membro_id=membro_id,
        classe="PIL",
        pavimento="13_PAV",
        layer="L1",
        items=["P9", "P10"],
    )
    pack = (
        tmp_path
        / "scripts"
        / "arete"
        / "html_fichas"
        / "Obra_TREINO_1"
        / "13_PAV_pilares_abcd"
        / "pilares"
    )
    pack.mkdir(parents=True)
    for item in ("P9", "P10"):
        (pack / f"{item}.html").write_text("<html>ficha</html>", encoding="utf-8")
        png = pack / "screenshots_qa" / f"{item}.png"
        png.parent.mkdir(exist_ok=True)
        png.write_bytes(b"fake-png")
    return round_id, job_id


def test_meta_do_job_sobrevive_a_restart(conn, tmp_path):
    round_id, job_id = _rodada(conn, tmp_path)
    app_state = type("State", (), {"job_meta": {}, "db": conn})()
    assert jobs_mod._metadados_job(app_state, job_id) == {
        "etapa": "qa_agentico",
        "round_id": round_id,
    }


def test_worker_persiste_multi_item_fallback_modelo_e_sugestao(
    conn, settings, tmp_path, db_path, monkeypatch
):
    round_id, _ = _rodada(conn, tmp_path)
    settings.repo_root = tmp_path
    claude = _Provider("claude", TechnicalFailure("authentication", "login"))
    codex = _Provider("codex", "invalidou")
    antigravity = _Provider("antigravity", "validou")

    status = qa_jobs.executar_qa_round(
        settings=settings,
        conn=conn,
        round_id=round_id,
        log_path=tmp_path / "qa.json",
        providers=[claude, codex, antigravity],
    )

    assert status == "completed"
    detail = repo.detalhe_qa_round(conn, round_id)
    assert [item["item_id"] for item in detail["items"]] == ["P9", "P10"]
    assert all(item["provider"] == "codex" for item in detail["items"])
    assert all(item["model"] == "codex-model" for item in detail["items"])
    assert all(item["verdict"] == "invalidou" for item in detail["items"])
    assert all(item["suggestion"]["action"] == "corrigir" for item in detail["items"])
    assert all(item["prompt_sha256"] and item["prompt_text"] for item in detail["items"])
    assert all(item["decision_authority"] == "PENDENTE" for item in detail["items"])
    assert all(item["training_eligible"] is False for item in detail["items"])
    assert all(len(item["evidence"]) == 2 for item in detail["items"])
    assert all(
        {entry["authority"] for entry in item["evidence"]}
        == {"presentation", "visual_evidence"}
        for item in detail["items"]
    )
    assert all(
        [attempt["provider"] for attempt in item["attempts"]] == ["claude", "codex"]
        for item in detail["items"]
    )
    assert len(claude.calls) == len(codex.calls) == 2
    assert antigravity.calls == []
    assert all(item["attempts"][1]["raw_response_sha256"] for item in detail["items"])
    assert all(item["attempts"][1]["raw_response_text"] for item in detail["items"])
    assert (tmp_path / "qa.json").is_file()
    events = (tmp_path / "qa.events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(events) == 2
    event = json.loads(events[0])
    assert event["schema"] == "cad.qa_training_candidate/v1"
    assert event["curation"] == {
        "authority": "PENDENTE",
        "requires_human_approval": True,
        "tier_candidate": "T3",
        "training_eligible": False,
    }

    from scripts.arete import qa_export_training

    promoted_out = tmp_path / "promoted.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_export_training.py", "--db", str(db_path), "--out", str(promoted_out)],
    )
    assert qa_export_training.main() == 0
    assert promoted_out.read_text(encoding="utf-8") == ""

    candidates_out = tmp_path / "candidates.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        [
            "qa_export_training.py", "--db", str(db_path), "--out",
            str(candidates_out), "--include-candidates",
        ],
    )
    assert qa_export_training.main() == 0
    assert len(candidates_out.read_text(encoding="utf-8").splitlines()) == 2


def test_worker_fv_materializa_camada_e_persiste_confianca(conn, settings, tmp_path):
    membro_id = repo.criar_membro(conn, login="bia", nome="Bia", senha_hash="h", drive_folder_id="f2")
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra_FV", pasta_drive_id="p2")
    round_id, _ = repo.enfileirar_qa_round(
        conn, obra_id=obra_id, membro_id=membro_id, classe="FV",
        pavimento="13_PAV", layer="L1", items=["V301"],
    )
    pack = tmp_path / "scripts" / "arete" / "html_fichas" / "Obra_FV" / "13_PAV_x_fundos_viga_hifi"
    folder = pack / "fundos_viga"
    (folder / "screenshots_qa").mkdir(parents=True)
    (folder / "screenshots_qa" / "V301.png").write_bytes(b"png")
    (folder / "V301.html").write_text(
        '<div class="fv-layer-sa"><svg viewBox="0 0 100 50"><path d="M0 0H100"/></svg></div>',
        encoding="utf-8",
    )
    settings.repo_root = tmp_path

    status = qa_jobs.executar_qa_round(
        settings=settings, conn=conn, round_id=round_id,
        log_path=tmp_path / "fv-qa.json", providers=[_FVProvider()],
    )

    assert status == "completed"
    proposal = folder / "propostas" / "V301_qa_proposta_c1.svg"
    assert proposal.is_file()
    assert 'id="qa-proposta"' in proposal.read_text(encoding="utf-8")
    summary = repo.listar_qa_resumos(conn, obra_id, "13_PAV", "FV")
    assert summary["V301"]["L1"]["verdict"] == "invalidou"
    assert summary["V301"]["L1"]["confidence_percent"] == 87.5


def test_escrita_atomica_substitui_proposta_somente_leitura(tmp_path):
    proposal = tmp_path / "propostas" / "V310_qa_proposta_c1.svg"
    proposal.parent.mkdir()
    proposal.write_text("antigo", encoding="utf-8")
    proposal.chmod(stat.S_IREAD)

    qa_jobs._atomic_write_text(proposal, "novo")

    assert proposal.read_text(encoding="utf-8") == "novo"
    assert proposal.stat().st_mode & stat.S_IWRITE


def test_worker_fv_isola_falha_de_um_item_e_continua(
    conn, settings, tmp_path, monkeypatch
):
    membro_id = repo.criar_membro(conn, login="caio", nome="Caio", senha_hash="h", drive_folder_id="f3")
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra_FV_2", pasta_drive_id="p3")
    round_id, _ = repo.enfileirar_qa_round(
        conn, obra_id=obra_id, membro_id=membro_id, classe="FV",
        pavimento="13_PAV", layer="L1", items=["V301", "V302"],
    )
    pack = tmp_path / "scripts" / "arete" / "html_fichas" / "Obra_FV_2" / "13_PAV_fundos_viga_hifi"
    folder = pack / "fundos_viga"
    (folder / "screenshots_qa").mkdir(parents=True)
    for item in ("V301", "V302"):
        (folder / "screenshots_qa" / f"{item}.png").write_bytes(b"png")
        (folder / f"{item}.html").write_text(
            '<div class="fv-layer-sa"><svg viewBox="0 0 10 10"></svg></div>', encoding="utf-8"
        )
    settings.repo_root = tmp_path
    original = qa_jobs._materializar_camada_fv

    def materializar(pack_path, item, layer, result):
        if item == "V301":
            raise PermissionError("proposta protegida")
        return original(pack_path, item, layer, result)

    monkeypatch.setattr(qa_jobs, "_materializar_camada_fv", materializar)
    status = qa_jobs.executar_qa_round(
        settings=settings, conn=conn, round_id=round_id,
        log_path=tmp_path / "fv-qa-isolado.json", providers=[_FVProviderDinamico()],
    )

    assert status == "partial_failed"
    items = {item["item_id"]: item for item in repo.listar_qa_items(conn, round_id)}
    assert items["V301"]["status"] == "failed"
    assert items["V302"]["status"] == "completed"


def test_retomada_processa_somente_itens_queued(conn, settings, tmp_path):
    round_id, _ = _rodada(conn, tmp_path)
    settings.repo_root = tmp_path
    first = _Provider("codex", "validou")
    assert qa_jobs.executar_qa_round(
        settings=settings, conn=conn, round_id=round_id,
        log_path=tmp_path / "qa-resume.json", providers=[first],
    ) == "completed"
    conn.execute("UPDATE portal_qa_items SET status='queued' WHERE round_id=? AND item_id='P10'", (round_id,))
    conn.commit()
    resumed = _Provider("codex", "validou")

    assert qa_jobs.executar_qa_round(
        settings=settings, conn=conn, round_id=round_id,
        log_path=tmp_path / "qa-resume-2.json", providers=[resumed],
    ) == "completed"
    assert len(resumed.calls) == 1
    assert "Item: P10." in resumed.calls[0]
