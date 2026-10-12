import json

from portal.app.n5_result_inventory import result_inventory


def publish(tmp_path, name, **fields):
    path = tmp_path / (name + '.dxf')
    path.write_text('DXF')
    path.with_suffix('.json').write_text(json.dumps(fields))
    return {'dxf_path': str(path), 'classe': fields['classe'], 'pavimento': fields['pavimento']}


def test_inventory_includes_four_lv_files_not_four_database_rows(tmp_path):
    rows = []
    for behavior in ('PARA', 'PASSA'):
        for assembly in ('gradeadas', 'sarrafeadas'):
            rows.append(publish(tmp_path, f'N5_LV_NOVA_{behavior}_{assembly}',
                                classe='LV', pavimento='13', obra='Obra', visual_mode='NOVA',
                                lateral_behavior=behavior, lateral_assembly=assembly,
                                ok_count=2, missing_count=0))
    results = result_inventory([rows[0], rows[0]])['13']['LV']
    assert len(results) == 4
    assert 'Laterais · PASSA · SARRAFEADAS · NOVA' in results
    (tmp_path / 'N5_LV_NOVA_PASSA_gradeadas.dxf').unlink()
    assert len(result_inventory([rows[0]])['13']['LV']) == 3
    broken = tmp_path / 'N5_LV_NOVA_PASSA_sarrafeadas.json'
    data = json.loads(broken.read_text())
    data['pavimento'] = 'OTHER'
    broken.write_text(json.dumps(data))
    assert len(result_inventory([rows[0]])['13']['LV']) == 2


def test_modes_and_garfos_are_historical_and_deduplicated(tmp_path):
    fv = publish(tmp_path, 'FV', classe='FV', pavimento='13', visual_mode='MOLDE_1',
                 vigas_config={'fundos_vigas_possui_garfos': 'nao'})
    pl = publish(tmp_path, 'PL', classe='PL', pavimento='13', visual_mode='MOLDE_2')
    assert result_inventory([fv, fv, pl]) == {'13': {
        'FV': ['Fundos · sem garfos · Formascia'], 'PL': ['Pilares · Molde 2']}}
    (tmp_path / 'FV.json').write_text('{invalid')
    assert 'FV' not in result_inventory([fv, pl])['13']


def test_partial_lateral_variant_is_downloadable_and_labeled_by_its_own_receipt(tmp_path):
    rows=[]
    for behavior in ('PARA','PASSA'):
        for assembly in ('gradeadas','sarrafeadas'):
            partial=behavior=='PASSA' and assembly=='sarrafeadas'
            rows.append(publish(tmp_path,f'N5_LV_NOVA_{behavior}_{assembly}',
                classe='LV',pavimento='13',obra='Obra',visual_mode='NOVA',
                lateral_behavior=behavior,lateral_assembly=assembly,
                ok_count=1,missing_count=int(partial),partial=partial))
    labels=result_inventory([rows[0]])['13']['LV']
    assert len(labels)==4
    assert 'Laterais · PASSA · SARRAFEADAS · NOVA · parcial · itens pendentes' in labels
    assert 'Laterais · PARA · GRADEADAS · NOVA' in labels
