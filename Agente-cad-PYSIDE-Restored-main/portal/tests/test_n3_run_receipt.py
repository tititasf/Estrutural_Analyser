import json
import pytest
from portal.app.pipeline_runner import auditar_manifesto_n3_da_rodada


def test_incomplete_current_run_cannot_reuse_previous_success(tmp_path):
    root = tmp_path/'Fase-6_Execucao_CAD/production_sa/P'
    root.mkdir(parents=True)
    base = dict(schema='cad.sa.production/v1', n3=dict(status='requested',
                fv_failed=[], lv_failed=[], lj_failed=[], pl_failed=[]))
    old = root/'old.json'; old.write_text(json.dumps(base))
    current = root/'current.json'
    base['n3']['fv_failed'] = ['V9']
    current.write_text(json.dumps(base))
    marker = '[SA-HUMAN] PRODUCTION_MANIFEST '
    path, errors = auditar_manifesto_n3_da_rodada(marker+str(current), tmp_path)
    assert path == current.resolve() and errors == ['FV/V9']
    with pytest.raises(RuntimeError, match='ausente ou ambiguo'):
        auditar_manifesto_n3_da_rodada('logs sem recibo', tmp_path)
    with pytest.raises(RuntimeError, match='ausente ou ambiguo'):
        auditar_manifesto_n3_da_rodada(marker+str(old)+'\n'+marker+str(current), tmp_path)


def test_receipt_rejects_other_obra_and_missing_class_result(tmp_path):
    marker = '[SA-HUMAN] PRODUCTION_MANIFEST '
    with pytest.raises(RuntimeError, match='fora do diretorio'):
        auditar_manifesto_n3_da_rodada(marker+str(tmp_path/'other.json'), tmp_path)
    path=tmp_path/'Fase-6_Execucao_CAD/production_sa/P/current.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(schema='cad.sa.production/v1',n3=dict(status='requested'))))
    with pytest.raises(RuntimeError,match='sem resultado'):
        auditar_manifesto_n3_da_rodada(marker+str(path),tmp_path)
