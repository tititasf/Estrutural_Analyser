import json
import sqlite3

import ezdxf
import pytest

from portal.app.preprocessamento import service
from portal.app.preprocessamento.crosscheck import check_facts
from portal.app.preprocessamento.freshness import changed_sources, stale_modules
from portal.app.preprocessamento.runner import RunnerError


def prepare(root, towers=2):
    folder = root / "Fase-2_Triagem/recortes/A"
    folder.mkdir(parents=True)
    names = [f"torre_{i+1}" for i in range(towers)] + ["convencao_pilares", "detalhes"]
    for name in names:
        doc = ezdxf.new("R2010")
        m = doc.modelspace()
        if name.startswith("torre"):
            m.add_text("P1", dxfattribs={"insert": (10, 10)})
            m.add_lwpolyline([(0, 0), (20, 0), (20, 40), (0, 40)], close=True)
            m.add_text("L1", dxfattribs={"insert": (100, 100)})
        elif name == "convencao_pilares":
            m.add_text("CONVENCAO PILARES", dxfattribs={"insert": (0, 100)})
            m.add_text("MORRE", dxfattribs={"insert": (0, 0)})
        doc.saveas(folder / f"{name}.dxf")
    (folder / "validado.json").write_text(json.dumps(dict.fromkeys(names, True)))
    return [{"bruto_id": "A", "item_id": n} for n in names]


def run(root, declarations, **kw):
    return service.run_floor(obra_dir=root, obra_id="obra-1", pavimento="14_PAV",
                             declarations=declarations, **kw)


def test_lote_isolado_duas_torres_indices_e_niveis_desconhecidos(tmp_path):
    declarations = prepare(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    progress = []
    result = run(tmp_path, declarations, progress=progress.append, known_floors=["15_PAV"])
    assert result["coverage"] == {"total": 2, "processed": 2, "failed": 0}
    assert result["details"]["status"] == "not_supported"
    assert progress[-1]["completed"] == progress[-1]["total"] == 2
    packages = [service.read_tower(tmp_path, result, s) for s in result["towers"]]
    assert packages[0]["pillars"]["items"][0]["item_id"] != packages[1]["pillars"]["items"][0]["item_id"]
    assert all(f["value"] is None for p in packages for f in p["levels"])
    assert all(p.read_bytes() == content for p, content in before.items())
    assert service.read_floor(tmp_path, "14_PAV") == result
    with service.index_connection(tmp_path) as conn:
        work = json.loads(conn.execute("SELECT payload FROM work_revisions").fetchone()[0])
    assert work["floors"]["15_PAV"] == {"status": "pending"}


def test_convencao_unica_em_outro_bruto_serve_duas_torres_sem_misturar_identidades(tmp_path):
    prepare(tmp_path)
    recortes = tmp_path / "Fase-2_Triagem/recortes"
    for bruto, filename in (("B", "torre_2.dxf"), ("C", "convencao_pilares.dxf")):
        folder = recortes / bruto
        folder.mkdir()
        (recortes / "A" / filename).rename(folder / filename)
        (folder / "validado.json").write_text(json.dumps({filename.removesuffix('.dxf'): True}))
    (recortes / "A/validado.json").write_text(json.dumps({"torre_1": True, "detalhes": True}))
    declarations = [
        {"bruto_id": "A", "item_id": "torre_1"},
        {"bruto_id": "A", "item_id": "detalhes"},
        {"bruto_id": "B", "item_id": "torre_2"},
        {"bruto_id": "C", "item_id": "convencao_pilares"},
    ]
    floor = run(tmp_path, declarations)
    packages = [service.read_tower(tmp_path, floor, source_id) for source_id in floor["towers"]]
    assert floor["coverage"] == {"total": 2, "processed": 2, "failed": 0}
    assert len({p["scope"]["recorte_id"] for p in packages}) == 2
    assert all(len(p["pillar_conventions"]) == 1 for p in packages)
    assert all(p["pillars"]["convention_source_ids"] ==
               p["convention_bindings"]["pillar_convention"]["selected_source_ids"]
               for p in packages)
    assert all("convencao_pilares_ausente" not in p["pillars"].get("warnings", [])
               for p in packages)
    assert all(p["convention_bindings"]["pillar_convention"]["scope"] == "floor_unique"
               for p in packages)
    assert {tuple(p["pillar_conventions"]) for p in packages} == {
        tuple(p["pillar_conventions"]) for p in packages[:1]
    }
    assert all(len(p["sources"]) == 2 for p in packages)


def test_multiplas_convencoes_externas_nao_sao_escolhidas_por_ordem(tmp_path):
    prepare(tmp_path, towers=1)
    recortes = tmp_path / "Fase-2_Triagem/recortes"
    legend = recortes / "A/convencao_pilares.dxf"
    for bruto in ("B", "C"):
        folder = recortes / bruto
        folder.mkdir()
        (folder / "convencao_pilares.dxf").write_bytes(legend.read_bytes())
        (folder / "validado.json").write_text('{"convencao_pilares":true}')
    legend.unlink()
    (recortes / "A/validado.json").write_text('{"torre_1":true,"detalhes":true}')
    floor = run(tmp_path, [
        {"bruto_id": "A", "item_id": "torre_1"},
        {"bruto_id": "B", "item_id": "convencao_pilares"},
        {"bruto_id": "C", "item_id": "convencao_pilares"},
    ])
    package = service.read_tower(tmp_path, floor, next(iter(floor["towers"])))
    assert package["pillar_conventions"] == {}
    assert package["convention_bindings"]["pillar_convention"]["status"] == "ambiguous"
    assert len(package["convention_bindings"]["pillar_convention"]["candidate_source_ids"]) == 2
    assert any(c["kind"] == "ambiguous_convention_binding" for c in package["conflicts"])


def test_falha_uma_torre_preserva_outra(tmp_path, monkeypatch):
    declarations = prepare(tmp_path)
    original = service.build_inventory_result
    def fail(**kwargs):
        if any(s["item_id"] == "torre_2" for s in kwargs["declarations"]):
            raise RuntimeError("DXF inválido")
        return original(**kwargs)
    monkeypatch.setattr(service, "build_inventory_result", fail)
    result = run(tmp_path, declarations)
    assert result["coverage"] == {"total": 2, "processed": 1, "failed": 1}
    assert result["status"] == "partial"


def test_revalidacao_no_commit_e_historico_imutavel(tmp_path, monkeypatch):
    declarations = prepare(tmp_path)
    first = run(tmp_path, declarations)
    original = service._write_atomic
    def race(path, payload):
        original(path, payload)
        if path.name == "floor.json":
            (tmp_path / "Fase-2_Triagem/recortes/A/validado.json").write_text('{}')
    monkeypatch.setattr(service, "_write_atomic", race)
    with pytest.raises(RunnerError, match="commit"):
        run(tmp_path, declarations)
    assert service.read_floor(tmp_path, "14_PAV") == first
    assert changed_sources(tmp_path, first["sources"])


def test_invalida_so_consumidores_e_detecta_ciclo():
    assert stale_modules({"pillars": ["tower", "legend"], "cuts": ["tower"]}, ["details"]) == []
    assert stale_modules({"pillars": ["tower", "legend"], "cuts": ["tower"]}, ["legend"]) == ["pillars"]
    facts = [{"fact_id": "a", "item_id": "P1", "field": "top", "value": 0,
              "unit": "m", "datum_id": "d", "derived_from": ["b"]},
             {"fact_id": "b", "item_id": "P1", "field": "top", "value": 0,
              "unit": "cm", "datum_id": "other", "derived_from": ["a"]}]
    assert {c["kind"] for c in check_facts(facts)} == {"evidence_cycle", "divergent_values_or_reference"}


def test_cancelamento_em_checkpoint_nao_promove_pavimento(tmp_path):
    declarations = prepare(tmp_path, towers=1)
    def cancel(progress):
        if progress['stage'] == 'before_publish':
            raise InterruptedError('cancelado')
    with pytest.raises(InterruptedError):
        run(tmp_path, declarations, progress=cancel)
    assert service.read_floor(tmp_path, '14_PAV') is None


def test_bruto_de_niveis_sem_recorte_e_versionado(tmp_path):
    declarations = prepare(tmp_path, towers=1)
    raw = tmp_path / "entrada/A.dxf"
    raw.parent.mkdir()
    doc = ezdxf.new("R2010")
    doc.modelspace().add_text("NIVEIS EM METROS", dxfattribs={"insert": (0, 150)})
    for value, x, y in (("13 PAV.", 0, 120), ("852.19", 100, 120),
                        ("14 PAV.", 0, 100), ("855.25", 100, 100)):
        doc.modelspace().add_text(value, dxfattribs={"insert": (x, y)})
    doc.saveas(raw)
    floor = run(tmp_path, declarations)
    package = service.read_tower(tmp_path, floor, next(iter(floor["towers"])))
    assert package["level_inventory"]["reference"]["status"] == "direct_local_reference"
    assert package["level_inventory"]["reference"]["height"] == 3.06
    assert any(source["kind"] == "raw_level_reference" for source in package["sources"])
    raw.write_bytes(raw.read_bytes() + b"\n999\n")
    assert changed_sources(tmp_path, floor["sources"])


def test_recorte_de_niveis_nao_aprovado_nao_bloqueia_lote(tmp_path):
    declarations = prepare(tmp_path, towers=1)
    folder = tmp_path / "Fase-2_Triagem/recortes/A"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_text("NIVEIS EM METROS")
    doc.saveas(folder / "convencao_niveis.dxf")
    (folder / "validado.json").write_text(json.dumps({
        "torre_1": True, "convencao_pilares": True,
        "detalhes": True, "convencao_niveis": False,
    }))
    floor = run(tmp_path, [*declarations, {"bruto_id": "A", "item_id": "convencao_niveis"}])
    assert floor["coverage"]["processed"] == 1
    assert not changed_sources(tmp_path, floor["sources"])
