from copy import deepcopy
import ezdxf
import pytest
from scripts import drawing_mode_config as config
from scripts.visual_modes import apply_visual_mode


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG', str(tmp_path / 'profiles.json'))


def drawing():
    doc = ezdxf.new('R2018')
    doc.layers.new('Painéis', dxfattribs={'color': 200})
    doc.layers.new('NOMENCLATURA', dxfattribs={'color': 7})
    doc.modelspace().add_line((0, 0), (50, 0), dxfattribs={'layer': 'Painéis'})
    doc.modelspace().add_text('V301', dxfattribs={'layer': 'NOMENCLATURA', 'height': 12})
    return doc


def test_ten_profiles_validate_and_unchanged_save_does_not_transform():
    catalog = config.catalog()
    for mode, classes in catalog['modes'].items():
        for cls, value in classes.items():
            assert config.validate(mode, cls, deepcopy(value)) == {}
    config.save('NOVA', 'FV', catalog['modes']['NOVA']['FV'], 0, 'test')
    doc = drawing()
    apply_visual_mode(doc, 'NOVA', 'FV')
    assert doc.modelspace()[0].dxf.layer == 'Painéis'
    assert doc.modelspace()[1].dxf.height == 12
    assert not doc.modelspace()[0].has_xdata('DRAWING_MODE_CONFIG')


def test_save_changes_actual_dxf_color_name_and_text_height(tmp_path):
    value = config.effective('NOVA', 'FV')
    value['layers']['Painéis'].update(name='PAINEL_PERSONALIZADO', color=1)
    value['appearance']['text_scale'] = 2
    config.save('NOVA', 'FV', value, 0, 'test')
    doc = drawing()
    apply_visual_mode(doc, 'NOVA', 'FV')
    doc.saveas(tmp_path / 'changed.dxf')
    loaded = ezdxf.readfile(tmp_path / 'changed.dxf')
    assert loaded.modelspace()[0].dxf.layer == 'PAINEL_PERSONALIZADO'
    assert loaded.layers.get('PAINEL_PERSONALIZADO').dxf.color == 1
    assert loaded.modelspace()[1].dxf.height == 24
    assert not loaded.audit().errors


def test_lateral_behavior_and_mode_are_independent():
    value = config.effective('NOVA', 'LV_PARA')
    value['components']['textos'] = False
    config.save('NOVA', 'LV_PARA', value, 0, 'test')
    para, passa, ini = drawing(), drawing(), drawing()
    apply_visual_mode(para, 'NOVA', 'LV', 'Para')
    apply_visual_mode(passa, 'NOVA', 'LV', 'Passa')
    apply_visual_mode(ini, 'INI', 'LV', 'Para')
    assert not list(para.modelspace().query('TEXT'))
    assert len(list(passa.modelspace().query('TEXT'))) == 1
    assert len(list(ini.modelspace().query('TEXT'))) == 1


def test_hidden_component_removed_inside_block():
    value = config.effective('NOVA', 'PL')
    value['components']['sarrafos'] = False
    config.save('NOVA', 'PL', value, 0, 'test')
    doc = drawing()
    doc.layers.new('SARRAFO')
    block = doc.blocks.new('GRA-E')
    block.add_line((0, 0), (0, 20), dxfattribs={'layer': 'SARRAFO'})
    doc.modelspace().add_blockref('GRA-E', (0, 0))
    apply_visual_mode(doc, 'NOVA', 'PL')
    assert len(block) == 0


def test_dimension_style_and_pattern_scale_are_rendered():
    value = config.effective('NOVA', 'FV')
    value['appearance'].update(dimension_scale=2, hatch_scale=3, hatch_angle=30)
    config.save('NOVA', 'FV', value, 0, 'test')
    doc = drawing()
    dimension = doc.modelspace().add_linear_dim(base=(0, -20), p1=(0, 0), p2=(50, 0))
    dimension.render()
    hatch = doc.modelspace().add_hatch()
    hatch.set_pattern_fill('ANSI31', scale=2)
    hatch.paths.add_polyline_path([(0, 0), (50, 0), (50, 20), (0, 20)], is_closed=True)
    apply_visual_mode(doc, 'NOVA', 'FV')
    assert dimension.dimension.override().get('dimtxt') == doc.dimstyles.get('Standard').dxf.dimtxt * 2
    assert hatch.dxf.pattern_scale == 6
    assert hatch.dxf.pattern_angle == 30
    assert not doc.audit().errors


def test_stale_revision_and_invalid_values_do_not_overwrite():
    value = config.effective('NOVA', 'FV')
    config.save('NOVA', 'FV', value, 0, 'test')
    with pytest.raises(RuntimeError):
        config.save('NOVA', 'FV', value, 0, 'test')
    value['appearance']['text_scale'] = float('nan')
    with pytest.raises(ValueError):
        config.save('NOVA', 'FV', value, 1, 'test')
    assert config.read_store()['revision'] == 1


def test_line_hatch_and_block_controls_preserve_valid_geometry():
    value = config.effective('NOVA', 'PL')
    value['blocks']['MULDURA'] = False
    value['layer_styles']['Painéis']['linetype'] = 'DASHED'
    value['layer_styles']['Hachura']['hatch_pattern'] = 'ANSI32'
    config.save('NOVA', 'PL', value, 0, 'test')
    doc = drawing()
    doc.blocks.new('MULDURA').add_line((0, 0), (1, 1))
    doc.modelspace().add_blockref('MULDURA', (0, 0))
    doc.layers.new('Hachura')
    hatch = doc.modelspace().add_hatch(dxfattribs={'layer': 'Hachura'})
    hatch.paths.add_polyline_path([(0, 0), (20, 0), (20, 20)], is_closed=True)
    apply_visual_mode(doc, 'NOVA', 'PL')
    assert not list(doc.modelspace().query('INSERT'))
    assert doc.modelspace()[0].dxf.linetype == 'DASHED'
    assert not hatch.dxf.solid_fill and hatch.dxf.pattern_name == 'ANSI32'
    assert not doc.audit().errors


def test_generation_uses_one_snapshot_when_settings_change(monkeypatch):
    from scripts.gerar_pl_dxf_stog import setup_doc
    value = config.effective('NOVA', 'PL')
    value['appearance']['text_scale'] = 2
    config.save('NOVA', 'PL', value, 0, 'first')
    doc = setup_doc()
    @config.configured_function('PL')
    def generate(msp, visual_mode='NOVA'):
        msp.add_text('P1', dxfattribs={'height': 10})
    generate(doc.modelspace())
    value['appearance']['text_scale'] = 3
    config.save('NOVA', 'PL', value, 1, 'second')
    apply_visual_mode(doc, 'NOVA', 'PL')
    assert doc.modelspace()[0].dxf.height == 20
    assert doc.header['$USERI1'] == 1
