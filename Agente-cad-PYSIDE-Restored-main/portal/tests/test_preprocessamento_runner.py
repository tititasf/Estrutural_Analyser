from __future__ import annotations

import json
import ezdxf
import pytest

from portal.app.preprocessamento import runner
from portal.app.preprocessamento.runner import RunnerError, run_inventory
from portal.app.preprocessamento.sources import resolve_crop_source


def _prepare(tmp_path):
    crop = tmp_path / "obra" / "Fase-2_Triagem" / "recortes" / "A" / "torre_1.dxf"
    crop.parent.mkdir(parents=True)
    drawing = ezdxf.new("R2010")
    drawing.modelspace().add_text("P1", dxfattribs={"insert": (10, 10)})
    drawing.saveas(crop)
    (crop.parent / "validado.json").write_text('{"torre_1": true}', encoding="utf-8")
    manifest = tmp_path / "input.json"
    manifest.write_text(json.dumps({
        "obra_id": "obra-1",
        "pavimento_id": "14_PAV",
        "obra_dir": str(tmp_path / "obra"),
        "sources": [{"bruto_id": "A", "item_id": "torre_1"}],
    }), encoding="utf-8")
    return manifest, crop


def test_preview_nao_escreve_nada(tmp_path):
    manifest, crop = _prepare(tmp_path)
    before = crop.read_bytes()
    output = tmp_path / "output"

    result = run_inventory(
        input_manifest=manifest, output_dir=output,
        obra_id="obra-1", pavimento_id="14_PAV", preview=True,
    )

    assert result["status"] == "partial"
    assert result["modules"]["sa_consumption"] == "disabled"
    assert not output.exists()
    assert crop.read_bytes() == before


def test_recorte_nao_validado_so_pode_ser_previa(tmp_path):
    manifest, crop = _prepare(tmp_path)
    (crop.parent / "validado.json").write_text('{"torre_1": false}', encoding="utf-8")
    output = tmp_path / "output"
    with pytest.raises(RunnerError, match="pendentes de validação"):
        run_inventory(
            input_manifest=manifest, output_dir=output,
            obra_id="obra-1", pavimento_id="14_PAV",
        )
    assert not output.exists()
    result = run_inventory(
        input_manifest=manifest, output_dir=output,
        obra_id="obra-1", pavimento_id="14_PAV", preview=True,
    )
    assert result["provisional"] is True
    assert len(result["unvalidated_source_ids"]) == 1
    assert not output.exists()


def test_execucao_escreve_somente_output_e_nao_toca_fonte(tmp_path):
    manifest, crop = _prepare(tmp_path)
    before_files = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    output = tmp_path / "output"

    result = run_inventory(
        input_manifest=manifest, output_dir=output,
        obra_id="obra-1", pavimento_id="14_PAV",
    )

    after_files = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert set(after_files) - set(before_files) == {"output/inventory.json"}
    assert crop.read_bytes() == before_files["obra/Fase-2_Triagem/recortes/A/torre_1.dxf"]
    assert result["modules"]["inventory"] == "complete"


def test_selecao_por_id_opaco(tmp_path):
    manifest, _ = _prepare(tmp_path)
    source = resolve_crop_source(
        obra_dir=tmp_path / "obra", obra_id="obra-1", pavimento_id="14_PAV",
        bruto_id="A", item_id="torre_1",
    )
    result = run_inventory(
        input_manifest=manifest, output_dir=tmp_path / "output",
        obra_id="obra-1", pavimento_id="14_PAV",
        selected_source_ids={source.source_id}, preview=True,
    )
    assert [item["source_id"] for item in result["sources"]] == [source.source_id]


def test_runner_processa_convencao_explicita_sem_disparar_sa(tmp_path):
    import ezdxf

    obra_dir = tmp_path / "obra"
    crop = obra_dir / "Fase-2_Triagem" / "recortes" / "A" / "convencao_pilares.dxf"
    crop.parent.mkdir(parents=True)
    document = ezdxf.new("R2010")
    model = document.modelspace()
    model.add_text("CONVENÇÃO DE PILARES", dxfattribs={"insert": (0, 100)})
    model.add_text("TIPO A", dxfattribs={"insert": (0, 0)})
    document.saveas(crop)
    manifest = tmp_path / "input-conv.json"
    manifest.write_text(json.dumps({
        "obra_id": "obra-1", "pavimento_id": "14_PAV", "obra_dir": str(obra_dir),
        "sources": [{"bruto_id": "A", "item_id": "convencao_pilares"}],
    }), encoding="utf-8")

    result = run_inventory(
        input_manifest=manifest, output_dir=tmp_path / "output",
        obra_id="obra-1", pavimento_id="14_PAV", preview=True,
    )

    assert result["modules"]["pillar_convention"] == "complete"
    assert next(iter(result["pillar_conventions"].values()))["signature_index"] == {"EMPTY": ["TIPO A"]}
    assert result["modules"]["sa_consumption"] == "disabled"


def test_runner_inventaria_torre_sem_propagar_convencao_de_outro_bruto(tmp_path):
    manifest, _ = _prepare(tmp_path)
    result = run_inventory(
        input_manifest=manifest, output_dir=tmp_path / "output",
        obra_id="obra-1", pavimento_id="14_PAV", preview=True,
    )
    tower = next(iter(result["pillars"].values()))
    assert tower["convention_source_ids"] == []
    assert tower["warnings"] == ["convencao_pilares_ausente"]
    assert result["modules"]["pillars"] == "partial"


def test_fonte_alterada_durante_leitura_nao_publica_resultado(tmp_path, monkeypatch):
    manifest, crop = _prepare(tmp_path)
    original = runner.inventory_pillars

    def changing_inventory(*args, **kwargs):
        result = original(*args, **kwargs)
        crop.write_bytes(crop.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(runner, "inventory_pillars", changing_inventory)
    output = tmp_path / "output"
    with pytest.raises(RunnerError, match="fonte alterada"):
        run_inventory(
            input_manifest=manifest, output_dir=output,
            obra_id="obra-1", pavimento_id="14_PAV",
        )
    assert not output.exists()
