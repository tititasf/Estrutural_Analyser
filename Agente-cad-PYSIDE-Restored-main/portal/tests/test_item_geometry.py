import copy
import json

import httpx
import pytest

from portal.app import auth, ficha_reader, item_geometry
from portal.app.main import create_app
from portal.db import connection, repository as repo


def snapshot():
    polygon = [[0, 0], [20, 0], [20, 60], [0, 60], [0, 0]]
    return {"pilares": [{"name": "P1", "shape_type": "Retangular", "points": polygon}],
            "slabs": [{"name": "L1", "points": polygon}],
            "segmentos": {"fundo": [
                {"uid": "f1", "beam_name": "V1", "segment_label": "1", "points": polygon},
                {"uid": "f2", "beam_name": "V1", "segment_label": "2", "points": polygon}],
                "lateral_a_para": [{"uid": "a1", "beam_name": "V1", "points": polygon}],
                "lateral_b_para": [{"uid": "b1", "beam_name": "V1", "points": polygon}],
                "lateral_a_passa": [{"uid": "ap1", "beam_name": "V1", "points": polygon}]}}


def test_manual_geometry_and_deletions_survive_republication(tmp_path):
    original = snapshot()
    state_file = tmp_path / "estado_13_PAV.json"
    state_file.write_text(json.dumps(original))
    geometry = [[100, 100], [130, 100], [130, 180], [100, 180]]
    result = item_geometry.mutate(tmp_path, "13_PAV", "pilares", "P1", points=geometry)
    assert result["affected"] == [{"classe": "pilares", "item_id": "P1"}]
    before = state_file.read_bytes()
    with pytest.raises(ValueError):
        item_geometry.mutate(tmp_path, "13_PAV", "pilares", "P1", points=[[0,0],[10,10],[0,10],[10,0]])
    assert state_file.read_bytes() == before
    item_geometry.mutate(tmp_path, "13_PAV", "fundo", "f1", delete=True)
    item_geometry.mutate(tmp_path, "13_PAV", "lateral_a_para", "V1", delete=True, whole_beam=True)
    # A future SA publication can overwrite its derived snapshot. Human decisions persist.
    state_file.write_text(json.dumps(original))
    state = ficha_reader.ler_estado_pavimento(tmp_path, "13_PAV")
    assert state["pilares"][0]["points"][:4] == geometry
    assert [r["uid"] for r in state["segmentos"]["fundo"]] == ["f2"]
    assert state["segmentos"]["fundo"][0]["segment_label"] == "2"
    assert not state["segmentos"]["lateral_a_para"]
    assert not state["segmentos"]["lateral_b_para"]
    assert state["segmentos"]["lateral_a_passa"]
    item_geometry.mutate(tmp_path, "13_PAV", "fundo", "f2", delete=True)
    assert not ficha_reader.ler_estado_pavimento(tmp_path, "13_PAV")["segmentos"]["fundo"]


@pytest.mark.asyncio
async def test_geometry_routes_share_listing_and_scope(settings, tmp_path, monkeypatch):
    directory = tmp_path / "obra"
    directory.mkdir()
    (directory / "estado_13_PAV.json").write_text(json.dumps(snapshot()))
    conn = connection.init_db(settings.db_path)
    member = repo.criar_membro(conn, login="editor", nome="Editor", senha_hash=auth.hash_senha("test123"), drive_folder_id="a")
    obra = repo.criar_obra(conn, membro_id=member, nome="Obra", pasta_drive_id="o", arquivo_hash="x", estado="pronta", local_path=str(directory))
    conn.close()
    app = create_app(settings)
    jobs = []
    def enqueue(request, conn, obra, meta):
        jobs.append(meta)
        return "job-test"
    monkeypatch.setattr("portal.app.routers.jobs_routes._enfileirar", enqueue)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            base = f"/obras/{obra}/itens"
            assert (await client.delete(base + "/pilares/P1?pavimento=13_PAV")).status_code == 401
            await client.post("/login", json={"login":"editor", "senha":"test123"})
            response = await client.put(base + "/pilares/P1/geometria?pavimento=13_PAV", json={"points":[[1,1],[31,1],[31,81],[1,81]]})
            assert response.status_code == 200, response.text
            listing = await client.get(f"/obras/{obra}/n1/pilares?pavimento=13_PAV")
            assert listing.json()["itens"][0]["item_id"] == "P1"
            assert ficha_reader.ler_estado_pavimento(directory, "13_PAV")["pilares"][0]["points"][0] == [1,1]
            assert (await client.delete(base + "/pilares/P1?pavimento=99_PAV")).status_code == 404
            result = await client.post(base + "/pilares/P1/interpretar-sa?pavimento=13_PAV")
            assert result.status_code == 200, result.text
            assert jobs == [{"etapa":"sa_item", "secao":"pilares", "item":"P1", "pav":"13_PAV", "classe_ui":"pilares"}]
            assert (await client.delete(base + "/lateral_a_para/V1?pavimento=13_PAV&inteiro=true")).status_code == 200
            assert (await client.get(f"/obras/{obra}/n1/lateral_b_para?pavimento=13_PAV")).json()["itens"] == []
