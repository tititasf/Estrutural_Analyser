from portal.app import pipeline_runner


def test_sa_button_does_not_generate_n3_and_n3_button_keeps_drawing(settings, tmp_path):
    obra = {'nome': 'Teste', 'local_path': str(tmp_path / 'Teste')}
    sa = pipeline_runner.executar_etapa(settings, 'sa', obra, pav='13_PAV', dry_run=True)
    n3 = pipeline_runner.executar_etapa(settings, 'n3', obra, pav='13_PAV', dry_run=True, visual_mode='INI')
    assert '--sa-only' in sa.comando
    assert '--persist-db' in sa.comando
    assert '--sa-only' not in n3.comando
    assert n3.comando[n3.comando.index('--visual-mode') + 1] == 'INI'
    assert n3.etapa == 'n3'
