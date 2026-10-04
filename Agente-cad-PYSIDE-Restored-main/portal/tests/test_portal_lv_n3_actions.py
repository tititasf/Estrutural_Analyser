from __future__ import annotations

import json
import contextlib
from copy import deepcopy
from pathlib import Path

import ezdxf
import httpx
import pytest

from portal.app import auth
from portal.app.main import create_app
from portal.app import lv_n3_operations, pipeline_runner
from portal.db import connection, repository as repo


def _contracts(obra_dir: Path, *, behavior: str = "para") -> tuple[Path, Path]:
    folder = (obra_dir / "Fase-6_Execucao_CAD" / "production_sa" / "14_PAV" /
              "20260925_010000_1" / "n3" / "contracts_lv" / f"LV-{behavior.upper()}")
    folder.mkdir(parents=True)
    paths = []
    for side in ("A", "B"):
        contract = {
            "number": "410", "name": f"V410_{side}_{behavior.title()}",
            "beam_name": "V410", "floor": "14_PAV", "side": side,
            "behavior": behavior.title(), "contract_id": f"LV_{side}_{behavior.upper()}",
            "total_width": 19, "total_height": 59, "h_section": 55,
            "generation_ready": True, "panels": [
                {"width": 120, "height1": 59, "height2": 59,
                 "grade_h1": 0, "grade_h2": 0, "panel_type": "Sarrafeado",
                 "structural_segment_index": 1},
                {"width": 85, "height1": 59, "height2": 59,
                 "grade_h1": 0, "grade_h2": 0, "panel_type": "Sarrafeado",
                 "structural_segment_index": 2},
            ],
        }
        path = folder / f"V410_{side}.json"
        path.write_text(json.dumps(contract), encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def test_lv_n3_override_preserva_contratos_sa_e_detecta_rodada_nova(tmp_path):
    a_path, b_path = _contracts(tmp_path)
    source_a = a_path.read_bytes()
    source_b = b_path.read_bytes()
    ficha = lv_n3_operations.load_ficha(tmp_path, "14_PAV", "para", "V410")
    draft = deepcopy(ficha)
    draft["sides"]["A"]["panels"][0]["width"] = 125
    draft["sides"]["B"]["total_height"] = 61
    saved = lv_n3_operations.save_ficha(tmp_path, "14_PAV", "para", "V410", draft)
    assert saved["revision"] == 1
    effective = lv_n3_operations.effective_contracts(tmp_path, "14_PAV", "para", "V410")
    assert effective["A"]["panels"][0]["width"] == 125
    assert effective["B"]["total_height"] == 61
    assert (a_path.read_bytes(), b_path.read_bytes()) == (source_a, source_b)
    with pytest.raises(ValueError, match="outra sessão"):
        lv_n3_operations.save_ficha(tmp_path, "14_PAV", "para", "V410", draft)
    with pytest.raises(ValueError, match="painéis"):
        broken = deepcopy(draft)
        broken["sides"]["A"]["panels"].pop()
        lv_n3_operations.save_ficha(tmp_path, "14_PAV", "para", "V410", broken)
    contract = json.loads(a_path.read_text(encoding="utf-8"))
    contract["total_height"] = 60
    a_path.write_text(json.dumps(contract), encoding="utf-8")
    assert lv_n3_operations.load_ficha(tmp_path, "14_PAV", "para", "V410")["stale"]
    with pytest.raises(ValueError, match="contrato SA mudou"):
        lv_n3_operations.effective_contracts(tmp_path, "14_PAV", "para", "V410")


@pytest.mark.parametrize("behavior", ["para", "passa"])
@pytest.mark.parametrize("view,suffix", [
    ("corte", "CORTE"),
    ("paineis-a", "VIEW_A"),
    ("paineis-b", "VIEW_B"),
])
def test_regeneracao_lv_n3_usa_override_e_publica_somente_vista(
    settings, tmp_path, view, suffix, behavior,
):
    obra_dir = tmp_path / "obra_lv"
    source_a, source_b = _contracts(obra_dir, behavior=behavior)
    original = (source_a.read_bytes(), source_b.read_bytes())
    ficha = lv_n3_operations.load_ficha(obra_dir, "14_PAV", behavior, "V410")
    ficha["sides"]["A"]["panels"][0]["width"] = 125
    lv_n3_operations.save_ficha(obra_dir, "14_PAV", behavior, "V410", ficha)
    result = pipeline_runner.regenerar_n3_lv_vista_item(
        settings, {"nome": "obra_lv", "local_path": str(obra_dir)},
        beam="V410", pav="14_PAV", behavior=behavior, view=view,
    )
    assert result.ok, result.log_tail
    target = obra_dir / "Fase-6_Execucao_CAD" / "n3_modes" / "NOVA" / "lv" / behavior / f"LV_preview_V410_{behavior.title()}_{suffix}.dxf"
    assert target.is_file()
    assert len(ezdxf.readfile(target).modelspace()) > 0
    assert (source_a.read_bytes(), source_b.read_bytes()) == original
    assert len(list(target.parent.glob("*.dxf"))) == 1


@contextlib.asynccontextmanager
async def _client(settings):
    conn = connection.init_db(settings.db_path)
    member = repo.criar_membro(
        conn, login="lv-owner", nome="LV Owner",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-lv",
    )
    obra_dir = settings.dados_obras_dir / "ObraLVWeb"
    obra_dir.mkdir(parents=True)
    _contracts(obra_dir)
    (obra_dir / "estado_14_PAV.json").write_text(json.dumps({
        "pilares": [], "slabs": [], "cortes": [],
        "segmentos": {
            "lateral_a_para": [{"uid": "v410-a-1", "beam_name": "V410",
                                  "segment_label": "1", "side": "A", "behavior": "Para",
                                  "length": 205, "width": "19/59", "level": 855.25}],
            "lateral_b_para": [{"uid": "v410-b-1", "beam_name": "V410",
                                  "segment_label": "1", "side": "B", "behavior": "Para",
                                  "length": 205, "width": "19/59", "level": 855.25}],
        },
    }), encoding="utf-8")
    obra_id = repo.criar_obra(
        conn, membro_id=member, nome="ObraLVWeb", pasta_drive_id="folder-lv",
        arquivo_hash="lv-web", estado="pronta", local_path=str(obra_dir),
    )
    conn.close()
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/login", json={"login": "lv-owner", "senha": "segredo123"})
            yield client, obra_id, obra_dir


@pytest.mark.asyncio
async def test_ficha_lv_salva_n3_e_enfileira_vista_isolada(settings, monkeypatch):
    captured = {}

    def enqueue(_conn, **kwargs):
        captured.update(kwargs)
        return "job-v410", True

    monkeypatch.setattr(repo, "enfileirar_job_unico_por_meta", enqueue)
    async with _client(settings) as (client, obra_id, obra_dir):
        base = f"/obras/{obra_id}/lv/para/V410"
        response = await client.get(base + "?pavimento=14_PAV&include_svgs=false")
        assert response.status_code == 200
        ficha = response.json()["n3_ficha"]
        ficha["sides"]["A"]["panels"][0]["width"] = 126
        saved = await client.put(base + "/n3-ficha?pavimento=14_PAV", json=ficha)
        assert saved.status_code == 200, saved.text
        assert saved.json()["ficha"]["sides"]["A"]["panels"][0]["width"] == 126
        queued = await client.post(
            base + "/regenerar-n3/paineis-a?pavimento=14_PAV",
            json={"visual_mode": "NOVA"},
        )
        assert queued.status_code == 200, queued.text
        assert captured["meta"]["requested_view"] == "paineis-a"
        assert captured["meta"]["behavior"] == "para"
        assert captured["chaves"] == (
            "etapa", "secao", "item", "pav", "behavior", "requested_view",
        )
        assert (await client.post(base + "/regenerar-n3/invalida?pavimento=14_PAV")).status_code == 422
