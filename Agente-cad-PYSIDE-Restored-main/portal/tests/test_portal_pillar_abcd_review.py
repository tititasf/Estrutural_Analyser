import json

import pytest

from portal.tests.test_portal_pillar_n3_ficha import _client


@pytest.mark.asyncio
async def test_abcd_review_endpoint_keeps_sa_snapshot_and_updates_view(settings):
    async with _client(settings) as (client, obra_id, obra_dir):
        state_path = obra_dir / "estado_TERREO.json"
        original = json.loads(state_path.read_text(encoding="utf-8"))
        original["pilares"][0]["interpretacao_abcd"] = {"faces": {"A": {
            "passa": [{"nome": "V409", "dim": "19/60", "nivel": "—", "canto": "AC"}],
        }}}
        state_path.write_text(json.dumps(original), encoding="utf-8")
        url = f"/obras/{obra_id}/n1/pilares/P1/abcd-review?pavimento=TERREO"
        response = await client.put(url, json={"edits": [
            {"face": "A", "role": "passa", "index": 0, "field": "dim", "value": "19/55"},
            {"face": "A", "role": "passa", "index": 0, "field": "canto", "value": "ad"},
        ]})
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == 1
        assert json.loads(state_path.read_text(encoding="utf-8")) == original
        assert (obra_dir / ".portal_overrides/pilares_abcd/TERREO/P1.json").is_file()
        detail = await client.get(f"/obras/{obra_id}/n1/pilares/P1?pavimento=TERREO")
        assert detail.status_code == 200, detail.text
        assert detail.json()["interpretacao_abcd"]["faces"]["A"]["passa"][0]["dim"] == "19/55"
        assert detail.json()["interpretacao_abcd"]["faces"]["A"]["passa"][0]["canto"] == "AD"
        assert 'data-field="canto"' in detail.json()["interpretacao_abcd_html"]
        bad = await client.put(url, json={"edits": [
            {"face": "A", "role": "passa", "index": 0, "field": "dim", "value": "<script>"},
        ]})
        assert bad.status_code == 422
