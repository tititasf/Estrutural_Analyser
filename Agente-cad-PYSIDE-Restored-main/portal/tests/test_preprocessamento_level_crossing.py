import ezdxf

from portal.app.preprocessamento.adapters.level_crossing import survey_levels


def _dxf(path, texts):
    doc = ezdxf.new("R2010")
    for value, pos in texts:
        doc.modelspace().add_text(value, dxfattribs={"insert": pos})
    doc.saveas(path)


def test_cruzamento_lista_lajes_sem_recorte_aprovado(tmp_path):
    tower = tmp_path / "torre.dxf"
    raw = tmp_path / "bruto.dxf"
    _dxf(tower, [("L1", (0, 0)), ("L2", (200, 0)),
                 ("852.12", (20, 0)), ("852.19", (220, 0))])
    _dxf(raw, [("MEDIDAS EM CENTIMETROS - NIVEIS EM METROS", (0, 150)),
               ("12 PAV.", (0, 120)), ("848.98", (100, 120)),
               ("13 PAV.", (0, 100)), ("852.19", (100, 100))])
    labels = [
        {"item_id": "s:L1", "item_class": "slab", "display_name": "L1", "label_position": [0, 0]},
        {"item_id": "s:L2", "item_class": "slab", "display_name": "L2", "label_position": [200, 0]},
    ]
    source = {"source_id": "raw:1", "relative_path": "bruto.dxf"}
    facts, inventory = survey_levels(tower, source_id="tower:1", floor="13_PAV",
                                     pillars=[], labels=labels, raw_reference=source, obra_dir=tmp_path)
    assert inventory["reference"]["status"] == "direct_local_reference"
    assert inventory["reference"]["height"] == 3.21
    assert inventory["coverage"]["slab_levels_observed"] == 2
    assert [(f["item_id"], f["value"], f["unit"]) for f in facts] == [
        ("s:L1", 852.12, "m"), ("s:L2", 852.19, "m")]


def test_sem_referencia_nao_promove_valor_para_campo(tmp_path):
    tower = tmp_path / "torre.dxf"
    _dxf(tower, [("L1", (0, 0)), ("L2", (200, 0)),
                 ("852.12", (20, 0)), ("852.19", (220, 0))])
    labels = [
        {"item_id": "s:L1", "item_class": "slab", "display_name": "L1", "label_position": [0, 0]},
        {"item_id": "s:L2", "item_class": "slab", "display_name": "L2", "label_position": [200, 0]},
    ]
    facts, inventory = survey_levels(tower, source_id="tower:1", floor="13_PAV",
                                     pillars=[], labels=labels)
    assert all(f["status"] == "raw_unreferenced" and f["value"] is None for f in facts)
    assert inventory["reference"]["status"] == "missing"


def test_marcas_divergentes_no_mesmo_item_permanecem_conflito(tmp_path):
    tower = tmp_path / "torre.dxf"
    raw = tmp_path / "bruto.dxf"
    _dxf(tower, [("L1", (0, 0)), ("L2", (200, 0)),
                 ("852.12", (20, 0)), ("852.19", (25, 0))])
    _dxf(raw, [("NIVEIS EM METROS", (0, 150)), ("12 PAV.", (0, 120)),
               ("848.98", (100, 120)), ("13 PAV.", (0, 100)), ("852.19", (100, 100))])
    labels = [
        {"item_id": "s:L1", "item_class": "slab", "display_name": "L1", "label_position": [0, 0]},
        {"item_id": "s:L2", "item_class": "slab", "display_name": "L2", "label_position": [200, 0]},
    ]
    facts, _ = survey_levels(tower, source_id="tower:1", floor="13_PAV", pillars=[], labels=labels,
                             raw_reference={"source_id": "raw:1", "relative_path": "bruto.dxf"},
                             obra_dir=tmp_path)
    assert facts[0]["status"] == "conflict" and facts[0]["value"] is None


def test_cota_zero_e_negativa_com_tabela_de_alturas_concorrente(tmp_path):
    tower = tmp_path / "torre.dxf"
    raw = tmp_path / "bruto.dxf"
    _dxf(tower, [("L1", (0, 0)), ("L2", (200, 0)),
                 ("-3.00", (20, 0)), ("0.00", (220, 0))])
    _dxf(raw, [("NIVEIS EM METROS", (0, 150)),
               ("12 PAV.", (0, 120)), ("-3.00", (100, 120)),
               ("12 PAV.", (800, 120)), ("3.00", (900, 120)),
               ("13 PAV.", (0, 100)), ("0.00", (100, 100)),
               ("13 PAV.", (800, 100)), ("6.00", (900, 100))])
    labels = [
        {"item_id": "s:L1", "item_class": "slab", "display_name": "L1", "label_position": [0, 0]},
        {"item_id": "s:L2", "item_class": "slab", "display_name": "L2", "label_position": [200, 0]},
    ]
    facts, inventory = survey_levels(tower, source_id="tower:1", floor="13_PAV",
                                     pillars=[], labels=labels,
                                     raw_reference={"source_id": "raw:1", "relative_path": "bruto.dxf"},
                                     obra_dir=tmp_path)
    assert inventory["reference"]["status"] == "direct_local_reference"
    assert inventory["reference"]["base"] == -3.0
    assert inventory["reference"]["top"] == 0.0
    assert [fact["value"] for fact in facts] == [-3.0, 0.0]
