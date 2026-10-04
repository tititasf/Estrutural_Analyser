from copy import deepcopy
import json

import httpx
import pytest

from portal.app import corte_references as cr, ficha_reader as fr


def segment(name="V2", classe="fundo", offset=0, label="7"):
    points = [[offset, 0], [offset + 100, 0], [offset + 100, 20], [offset, 20]]
    if classe != "fundo":
        points = [[offset, 0], [offset + 100, 0]]
    return {"uid": f"{classe}|{name}|{label}", "beam_name": name,
            "segment_label": label, "points": points, "width": "20/55"}


def state():
    return {"slabs": [], "cortes": [{"uid": "cut", "beam_name": "V1",
            "pts": [[40, -5], [60, -5], [60, 25], [40, 25]]}],
            "segmentos": {"fundo": [segment()],
                          "lateral_a_para": [segment(classe="lateral_a_para")]}}


def associate(e):
    return cr.associar_referencias(e["cortes"][0], cr.preparar_segmentos(e))


def test_nome_errado_nao_filtra_referencias_nem_sobrescreve_sa():
    e = state()
    original = deepcopy(e)
    item = fr.listar_itens_n1(e, "cortes")[0]
    refs = item["referencias_corte"]
    assert refs["nome_sugerido"] == "V2"
    assert refs["status"] == "divergente"
    assert item["beam_name"] == item["titulo"] == item["campos"]["Viga"] == "V2"
    assert item["beam_name_original"] == item["campos"]["Nome anterior · diagnóstico"] == "V1"
    assert refs["segmentos"]["fundo"][0]["item_id"] == "fundo|V2|7"
    assert set(item["campos_links"]) <= set(item["campos_somente_leitura"])
    assert "Viga" in item["campos_somente_leitura"]
    assert e == original


def test_mais_variantes_para_passa_nao_desempatam_nomes_concorrentes():
    e = state()
    e["segmentos"]["fundo"].append(segment("V3", label="2"))
    for classe in ("lateral_a_passa", "lateral_b_para", "lateral_b_passa"):
        e["segmentos"][classe] = [segment(classe=classe)]
    refs = associate(e)
    assert refs["status"] == "ambigua"
    assert refs["nome_sugerido"] is None
    assert refs["candidatos"] == ["V2", "V3"]
    item = fr.listar_itens_n1(e, "cortes")[0]
    assert item["titulo"] == item["campos"]["Viga"] == "Pendente"
    assert item["beam_name_original"] == "V1"


def test_apenas_fundo_ou_lateral_e_referencia_parcial():
    for only in ("fundo", "lateral_a_para"):
        e = state()
        e["segmentos"] = {only: e["segmentos"][only]}
        refs = associate(e)
        assert refs["status"] == "parcial"
        assert refs["nome_sugerido"] is None
        assert refs["segmentos"][only]


def test_sem_geometria_local_nao_escolhe_viga_mais_proxima():
    e = state()
    e["segmentos"] = {"fundo": [segment(offset=1000)],
                      "lateral_a_para": [segment(classe="lateral_a_para", offset=1000)]}
    assert associate(e)["status"] == "sem_referencia"
    assert associate(e)["nome_sugerido"] is None


def test_fundo_proximo_sem_contato_nao_cria_associacao():
    e = state()
    e["cortes"][0]["pts"] = [[40, 25], [60, 25], [60, 30], [40, 30]]
    e["segmentos"]["lateral_a_para"][0]["points"] = [[0, 20], [100, 20]]
    refs = associate(e)
    assert refs["status"] == "parcial"
    assert refs["segmentos"]["fundo"][0]["distancia_cm"] == 5


@pytest.mark.parametrize("points", [[], [[0, 0]], [[0, float('nan')], [1, 1], [2, 2]], [[0, 0], [1, 1], [2, 2]]])
def test_geometria_invalida_fica_pendente(points):
    e = state()
    e["cortes"][0]["pts"] = points
    refs = associate(e)
    assert refs["nome_sugerido"] is None
    assert refs["status"] == "sem_referencia"


def test_referencias_mantem_a_b_para_passa_e_todos_os_segmentos():
    e = state()
    e["cortes"][0]["beam_name"] = "V2"
    for classe in cr.CLASSES:
        e["segmentos"][classe] = [segment(classe=classe, label="7"), segment(classe=classe, label="8")]
    refs = associate(e)
    assert refs["status"] == "concordante"
    for classe in cr.CLASSES:
        assert [r["segment_label"] for r in refs["segmentos"][classe]] == ["7", "8"]


@pytest.mark.asyncio
async def test_http_ficha_expoe_campos_referencias_e_links_sem_mudar_estado(settings, tmp_path):
    from portal.app import auth
    from portal.app.main import create_app
    from portal.db import connection, repository as repo

    obra_dir = tmp_path / "ObraRefs"
    obra_dir.mkdir()
    source = obra_dir / "estado_13_PAV.json"
    source.write_text(json.dumps(state()), encoding="utf-8")
    original = source.read_bytes()
    conn = connection.init_db(settings.db_path)
    member = repo.criar_membro(conn, login="refs", nome="Refs", senha_hash=auth.hash_senha("teste123"), drive_folder_id="refs")
    obra = repo.criar_obra(conn, membro_id=member, nome="ObraRefs", pasta_drive_id="refs",
                          arquivo_hash="refs", estado="pronta", local_path=str(obra_dir))
    conn.close()
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/login", json={"login": "refs", "senha": "teste123"})
            response = await client.get(f"/obras/{obra}/n1/cortes/cut?pavimento=13_PAV")
            assert response.status_code == 200
            body = response.json()
            assert body["campos"]["Viga"] == body["titulo"] == "V2"
            assert body["campos"]["Nome anterior · diagnóstico"] == "V1"
            assert body["referencias_corte"]["nome_sugerido"] == "V2"
            label = cr.CLASSES["fundo"]
            assert label in body["campos_somente_leitura"]
            assert body["campos_links"][label][0]["item_id"] == "fundo|V2|7"
            listing = await client.get(f"/obras/{obra}/n1/cortes?pavimento=13_PAV")
            assert listing.status_code == 200
            assert listing.json()["itens"][0]["titulo"] == "V2"
            assert listing.json()["itens"][0]["beam_name"] == "V2"
    assert source.read_bytes() == original
