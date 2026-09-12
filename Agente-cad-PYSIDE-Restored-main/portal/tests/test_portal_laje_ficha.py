from __future__ import annotations

import json
from pathlib import Path

from portal.app import laje_ficha, laje_operations


def _state(tmp_path: Path) -> dict:
    state = {
        "slabs": [
            {"name": "L301", "nivel": "852.12", "height": "12", "points": [[0, 0], [200, 0], [200, 100], [0, 100]]},
            {"name": "L302", "nivel": "850", "height": "10", "points": [[0, 0], [100, 0], [100, 100]]},
        ],
        "cortes": [{"own_laje": "L301", "neigh_laje": "L302"}],
    }
    (tmp_path / "estado_13_PAV.json").write_text(json.dumps(state), encoding="utf-8")
    contract = tmp_path / "Fase-6_Execucao_CAD" / "production_sa" / "13_PAV" / "run1" / "n3" / "contracts_lj"
    contract.mkdir(parents=True)
    (contract.parent.parent / "production_manifest.json").write_text("{}", encoding="utf-8")
    (contract / "L301.json").write_text(json.dumps({
        "comprimento": 200, "largura": 100, "modo_selecionado": 1,
        "linhas_verticais": [{"value": 120, "is_union": False}],
        "linhas_horizontais": [{"value": 80, "is_union": True}],
    }), encoding="utf-8")
    return state


def test_ficha_laje_expoe_camadas_campos_e_n3(tmp_path: Path):
    state = _state(tmp_path)
    result = laje_ficha.montar_ficha_laje(tmp_path, "13_PAV", "L301", state)
    assert result["schema"] == "cad.portal.laje_ficha/v1"
    assert list(result["layers"]) == ["sa", "c1", "c2", "c3", "n3"]
    assert result["item"]["nivel"] == "852.12"
    assert result["n3"]["linhas_verticais"][0]["value"] == 120
    assert result["item"]["next"] == "L302"


def test_edicoes_criam_backup_e_override_consumivel(tmp_path: Path):
    _state(tmp_path)
    fields = laje_operations.update_fields(tmp_path, "13_PAV", "L301", {
        "name": "L301A", "nivel": "853.5", "height": "15",
    })
    assert Path(fields["backup"]).is_file()
    state = json.loads((tmp_path / "estado_13_PAV.json").read_text(encoding="utf-8"))
    assert state["slabs"][0]["name"] == "L301A"
    assert state["cortes"][0]["own_laje"] == "L301A"
    laje_operations.update_n3(tmp_path, "13_PAV", "L301A", {
        "linhas_verticais": [{"value": 99, "is_union": True}],
        "linhas_horizontais": [],
    })
    override = laje_operations.load_override(tmp_path, "13_PAV", "L301A")
    assert override["n3"]["linhas_verticais"] == [{"value": 99.0, "is_union": True}]


def test_frontend_laje_esta_integrado_no_template():
    root = Path(__file__).resolve().parents[2]
    js = (root / "portal" / "app" / "static" / "laje_ficha.js").read_text(encoding="utf-8")
    template = (root / "portal" / "app" / "templates" / "obra_detalhe.html").read_text(encoding="utf-8")
    assert "window.LajeFicha" in js
    assert "Opiniões humanas por camada" in js
    assert "Solicitar regeneração N3" in js
    assert "regenerar-n3/status" in js
    assert "Regeneração N3 em andamento" in js
    assert "data-lj-regen-monitor" in js
    assert "LajeFicha.mount" in template
    assert "/static/laje_ficha.js" in template
