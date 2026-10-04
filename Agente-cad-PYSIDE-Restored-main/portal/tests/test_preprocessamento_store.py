from __future__ import annotations

import json

import pytest

from portal.app.preprocessamento.contracts import ContextEnvelope, ContextFact, ScopeIdentity
from portal.app.preprocessamento.store import PreprocessStore, StoreError
from portal.db import repository as repo


def _envelope(obra_id: str, run_id: str = "run-1") -> ContextEnvelope:
    return ContextEnvelope(
        run_id=run_id,
        scope=ScopeIdentity(obra_id, "14_PAV", "pre-src-v1:torre-1", "a" * 64),
        status="complete",
        created_at="2026-09-22T12:00:00Z",
        items=(ContextFact("P1:classe", "P1", "classe", "NASCE"),),
    )


def _store(conn, settings):
    membro = repo.criar_membro(conn, login="pre", nome="Pre", senha_hash="h", drive_folder_id="f")
    obra_id = repo.criar_obra(conn, membro_id=membro, nome="Obra", pasta_drive_id="p")
    obra_dir = settings.dados_obras_dir / "Obra"
    obra_dir.mkdir(parents=True)
    return PreprocessStore(obra_dir=obra_dir, conn=conn), obra_id


def test_publicacao_atomica_indexa_e_valida_payload(conn, settings):
    store, obra_id = _store(conn, settings)
    package = store.publish(
        _envelope(obra_id),
        payloads={"torres/torre-1/pilares.json": {"items": ["P1"]}},
        engine_version="pre-v1",
    )

    loaded = store.read("run-1")
    assert loaded.envelope.scope.obra_id == obra_id
    assert loaded.manifest_hash == package.manifest_hash
    assert json.loads((package.directory / "torres/torre-1/pilares.json").read_text())["items"] == ["P1"]


def test_falha_antes_do_rename_nao_substitui_pacote_bom(conn, settings, monkeypatch):
    store, obra_id = _store(conn, settings)
    good = store.publish(_envelope(obra_id, "good"))
    original = store._write_file
    calls = {"count": 0}

    def fail_second(path, content):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("queda simulada")
        return original(path, content)

    monkeypatch.setattr(store, "_write_file", fail_second)
    with pytest.raises(OSError, match="queda simulada"):
        store.publish(_envelope(obra_id, "broken"), payloads={"dados.json": {"x": 1}})

    assert store.read("good").manifest_hash == good.manifest_hash
    assert not (store.root / "14_PAV" / "broken").exists()


def test_falha_apos_rename_e_recuperavel(conn, settings, monkeypatch):
    store, obra_id = _store(conn, settings)

    def fail_index(*args, **kwargs):
        raise RuntimeError("db indisponível")

    monkeypatch.setattr(store, "_index", fail_index)
    with pytest.raises(RuntimeError, match="db indisponível"):
        store.publish(_envelope(obra_id, "orphan"))

    assert (store.root / "14_PAV" / "orphan" / "manifest.json").is_file()
    monkeypatch.undo()
    assert store.recover_unindexed() == 1
    assert store.read("orphan").envelope.run_id == "orphan"


def test_payload_corrompido_falha_fechado(conn, settings):
    store, obra_id = _store(conn, settings)
    package = store.publish(_envelope(obra_id), payloads={"dados.json": {"x": 1}})
    (package.directory / "dados.json").write_text('{"x":2}', encoding="utf-8")

    with pytest.raises(StoreError, match="corrompido"):
        store.read("run-1")


def test_indice_nao_pode_ler_outro_run_da_mesma_obra(conn, settings):
    store, obra_id = _store(conn, settings)
    store.publish(_envelope(obra_id, "run-1"))
    other = store.publish(_envelope(obra_id, "run-2"))
    with conn:
        conn.execute(
            "UPDATE portal_preprocess_runs SET manifest_relative_path=? WHERE run_id=?",
            (other.manifest_path.relative_to(store.obra_dir).as_posix(), "run-1"),
        )
    with pytest.raises(StoreError, match="divergem"):
        store.read("run-1")


@pytest.mark.parametrize("path", ["../fora.json", "/absoluto.json", "manifest.json"])
def test_payload_path_inseguro_e_rejeitado(conn, settings, path):
    store, obra_id = _store(conn, settings)
    with pytest.raises(StoreError, match="path|reservado"):
        store.publish(_envelope(obra_id), payloads={path: {}})
