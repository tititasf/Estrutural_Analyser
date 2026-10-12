from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from portal.app.preprocessamento import preprocess_runner
from portal.app.preprocessamento.runner import RunnerError
from portal.app.preprocessamento.sources import SourceKind, SourceRecord
from portal.app.routers import preprocessamento_routes as routes
from portal.app import jobs
from portal.db import repository as repo


def _source(obra_id: str, validated: bool = True) -> SourceRecord:
    return SourceRecord(
        source_id="pre-src-v1:" + "a" * 64, obra_id=obra_id,
        pavimento_id="14_PAV", bruto_id="A", item_id="torre_1",
        kind=SourceKind.TOWER, revision="b" * 64,
        relative_path="Fase-2_Triagem/recortes/A/torre_1.dxf",
        validated=validated,
    )


def test_job_usa_recortes_validados_e_deduplica(conn, membro_id, settings, monkeypatch):
    settings.preprocess_enabled = True
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Teste", pasta_drive_id="p")
    monkeypatch.setattr(routes, "inventory_floor_sources", lambda **kwargs: (_source(obra_id),))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings, job_meta={})))
    member = {"id": membro_id, "papel": "membro"}
    payload = routes.PreprocessRequest(pavimento="14_PAV")

    first = routes.start_preprocess(obra_id, payload, request, member, conn)
    second = routes.start_preprocess(obra_id, payload, request, member, conn)

    assert first["created"] is True
    assert second["created"] is False
    assert first["job_id"] == second["job_id"]
    assert first["tower_count"] == 1
    assert routes.get_preprocess(obra_id, "14_PAV", request, member, conn)["status"] == "na_fila"
    with pytest.raises(HTTPException) as forbidden:
        routes.get_preprocess(obra_id, "14_PAV", request, {"id": "outro", "papel": "membro"}, conn)
    assert forbidden.value.status_code == 403


def test_job_preserva_revisao_com_validacao_humana_opcional(conn, membro_id, settings, monkeypatch):
    # Owner decision 2026-10-08: preprocessing may precede human review.
    # Source scope/revision remain frozen; enqueueing cannot fabricate approval.
    settings.preprocess_enabled = True
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Teste", pasta_drive_id="p")
    source = _source(obra_id, False)
    monkeypatch.setattr(routes, "inventory_floor_sources", lambda **kwargs: (source,))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings, job_meta={})))
    result = routes.start_preprocess(obra_id, routes.PreprocessRequest(pavimento="14_PAV"), request,
                                    {"id": membro_id, "papel": "membro"}, conn)
    assert result["created"] is True
    assert source.validated is False
    meta = repo.obter_job_meta(conn, result["job_id"])
    assert meta["frozen_sources"] == {source.source_id: source.revision}
    assert meta["sources"] == [{"bruto_id": source.bruto_id, "item_id": source.item_id}]
    assert len(repo.listar_jobs_por_obra(conn, obra_id)) == 1


def test_worker_publica_parcial_somente_quando_revisao_confere(tmp_path):
    from portal.tests.test_preprocessamento_service import prepare
    from portal.app.preprocessamento.runner import resolve_declared_sources
    obra_dir = tmp_path / "obra"
    declarations = prepare(obra_dir)
    sources = resolve_declared_sources(obra_dir=obra_dir, obra_id="obra-1",
                                       pavimento_id="14_PAV", declarations=declarations)
    frozen = {source.source_id: source.revision for source in sources}
    result = preprocess_runner.execute_inventory_job(
        obra_dir=obra_dir, obra_id="obra-1", pavimento="14_PAV", job_id="job-1",
        frozen_sources=frozen, declarations=declarations,
    )
    output = obra_dir / "preprocessamento/v1/14_PAV/runs/job-1/floor.json"
    assert result["status"] == "partial"
    assert result["sa_consumption"] == "scoped_context_available"
    assert result["collected_segments"] == 0
    before = hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(RunnerError, match="alterados"):
        preprocess_runner.execute_inventory_job(
            obra_dir=obra_dir, obra_id="obra-1", pavimento="14_PAV", job_id="job-2",
            frozen_sources={next(iter(frozen)): "c" * 64}, declarations=declarations,
        )
    assert hashlib.sha256(output.read_bytes()).hexdigest() == before
    assert not (obra_dir / "preprocessamento/v1/14_PAV/runs/job-2").exists()
    with pytest.raises(RunnerError, match="inválida"):
        preprocess_runner.execute_inventory_job(
            obra_dir=obra_dir, obra_id="obra-1", pavimento="..", job_id="job-3",
            frozen_sources=frozen, declarations=declarations,
        )


def test_worker_preprocessamento_nao_altera_estado_sa(conn, membro_id, settings, monkeypatch):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Teste", pasta_drive_id="p",
                              estado="aguardando_ingestao")
    meta = {"etapa": "preprocessamento", "pav": "14_PAV", "scope_hash": "h",
            "frozen_sources": {}, "sources": []}
    job_id, _ = repo.enfileirar_job_unico_por_meta(
        conn, obra_id=obra_id, meta=meta, chaves=("etapa", "pav", "scope_hash"))
    monkeypatch.setattr(preprocess_runner, "execute_inventory_job", lambda **kwargs: {
        "status": "partial", "tower_count": 1, "sa_consumption": "disabled"})
    app_state = SimpleNamespace(settings=settings, db=conn, job_meta={job_id: meta})
    job = repo.consumir_job(conn)

    jobs.processar_um_job(app_state, job)

    assert repo.listar_jobs_por_obra(conn, obra_id)[0]["status"] == "concluido"
    assert repo.obter_obra(conn, obra_id)["estado"] == "aguardando_ingestao"
    assert repo.obter_job_meta(conn, job_id)["result"]["sa_consumption"] == "disabled"


def test_preprocess_count_matches_visible_interpreted_inventory(tmp_path, monkeypatch):
    from portal.tests.test_structural_review import entry
    from portal.app import structural_review as review
    inferred = entry()
    original = dict(inferred, kind='identified')
    step = dict(inferred, step_uid='L322-step')
    inventory = dict(entries=[original, inferred], interpreted_slab_sections=[step])
    result = dict(towers={'tower': {'status': 'complete'}}, sources=['tower'],
                  coverage={}, status='complete', run_id='job1', sa_consumption='scoped_context_available')
    monkeypatch.setattr(preprocess_runner, 'run_floor', lambda **kwargs: result)
    monkeypatch.setattr(preprocess_runner, 'read_tower', lambda *args: {'beam_sections': inventory})
    args = dict(obra_dir=tmp_path, obra_id='work', pavimento='13_PAV', job_id='job1',
                frozen_sources={}, declarations=[])
    assert preprocess_runner.execute_inventory_job(**args)['interpreted_cut_count'] == 2
    review.decide(tmp_path, '13_PAV', inventory, review.entry_id(inferred), 'delete', 'human')
    assert preprocess_runner.execute_inventory_job(**args)['interpreted_cut_count'] == 2
    assert review.load(tmp_path, '13_PAV')[review.entry_id(inferred)]['action'] == 'rejected'
    args['pavimento'] = '14_PAV'
    assert preprocess_runner.execute_inventory_job(**args)['interpreted_cut_count'] == 2
