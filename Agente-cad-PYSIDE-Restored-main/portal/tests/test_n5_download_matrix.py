from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from portal.app.n5_result_inventory import download_availability
from portal.tests.test_n5_result_inventory import publish


def render(releases):
    env = Environment(loader=FileSystemLoader(Path(__file__).parents[1] / 'app/templates'),
                      autoescape=select_autoescape())
    return env.get_template('n5_download_matrix.html').render(
        obra={'id': 'obra'}, pavimento='13', n5_por_pav_classe_modo={'13': releases})


def test_parent_template_compiles_without_n5_viewer():
    directory = Path(__file__).parents[1] / 'app/templates'
    env = Environment(loader=FileSystemLoader(directory))
    env.get_template('obra_detalhe.html')
    source = (directory / 'obra_detalhe.html').read_text(encoding='utf-8')
    assert 'data-n5-svg-src=' not in source
    assert "include 'n5_lv_variants.html'" not in source


def test_matrix_only_links_existing_variants_of_selected_release(tmp_path):
    lv = publish(tmp_path, 'LV_INI_PARA_gradeadas', classe='LV', pavimento='13',
                 obra='Obra', visual_mode='INI', lateral_behavior='PARA',
                 lateral_assembly='gradeadas', ok_count=2, missing_count=0)
    publish(tmp_path, 'LV_INI_PASSA_sarrafeadas', classe='LV', pavimento='13',
            obra='Obra', visual_mode='INI', lateral_behavior='PASSA',
            lateral_assembly='sarrafeadas', ok_count=2, missing_count=0)
    lv.update(download_availability(lv))
    html = render({'LV': {'INI': lv}})
    assert html.count('>Baixar DXF</a>') == 2
    assert 'lateral_behavior=PASSA&amp;lateral_assembly=sarrafeadas' in html
    assert 'lateral_behavior=PARA&amp;lateral_assembly=sarrafeadas' not in html
    assert 'data-n5-svg-src' not in html
    assert html.count('data-n5-download-row=') == 9


def test_garfos_false_is_not_unknown_and_unknown_has_single_download(tmp_path):
    fv = publish(tmp_path, 'FV', classe='FV', pavimento='13', visual_mode='INI',
                 possui_garfos=False)
    fv.update(download_availability(fv))
    html = render({'FV': {'INI': fv}})
    assert fv['fundos_garfos'] == 'nao'
    assert html.count('>Baixar DXF</a>') == 1
    assert 'Garfos não informados' not in html
    Path(fv['dxf_path']).with_suffix('.json').write_text('{}')
    fv.update(download_availability(fv))
    html = render({'FV': {'INI': fv}})
    assert html.count('>Baixar DXF</a>') == 1
    assert 'Garfos não informados' in html


def test_deleted_dxf_and_missing_pillar_group_have_no_download(tmp_path):
    pl = publish(tmp_path, 'PL', classe='PL', pavimento='13', visual_mode='INI')
    pl.update(download_availability(pl), pillar_groups_available=['PARA'])
    html = render({'PL': {'INI': pl}})
    assert html.count('>Baixar DXF</a>') == 1
    assert 'pillar_group=PARA' in html
    assert 'pillar_group=PASSA' not in html
    Path(pl['dxf_path']).unlink()
    pl.update(download_availability(pl))
    assert '>Baixar DXF</a>' not in render({'PL': {'INI': pl}})


def test_zip_requires_all_four_classes_in_same_mode(tmp_path):
    releases = {}
    for classe in ('PL', 'LV', 'FV', 'LJ'):
        release = publish(tmp_path, classe, classe=classe, pavimento='13', visual_mode='INI')
        release.update(download_availability(release))
        releases[classe] = {'INI': release}
    assert render(releases).count('>Baixar ZIP</a>') == 1
    releases['LJ'] = {'NOVA': releases['LJ']['INI']}
    assert '>Baixar ZIP</a>' not in render(releases)
