import json
from pathlib import Path
import pytest
from src.core import pillar_sa_review as r
from portal.app.ficha_reader import ler_estado_pavimento
from src.core.n5_assembler import _state_pillar_ids

def test_classification_reactivates_without_changing_snapshot(tmp_path):
    state = {'pilares': [{'name':'P1','classification':'NASCE'}, {'name':'P2','classification':'SEGUE'}]}
    path = tmp_path / 'estado_13_PAV.json'
    path.write_text(json.dumps(state))
    assert _state_pillar_ids(tmp_path, '13_PAV') == ['P2']
    r.save(tmp_path, '13_PAV', 'P1', {'classificacao':'SEGUE'})
    assert _state_pillar_ids(tmp_path, '13_PAV') == ['P1','P2']
    assert ler_estado_pavimento(tmp_path, '13_PAV')['pilares'][0]['classification'] == 'SEGUE'
    assert json.loads(path.read_text()) == state
    r.save(tmp_path, '13_PAV', 'P2', {'classificacao':'NASCE'})
    assert _state_pillar_ids(tmp_path, '13_PAV') == ['P1']

def test_manual_levels_zero_and_orientation_preserved(tmp_path):
    r.save(tmp_path,'13_PAV','P1',{'orientacao':'RETANGULAR HORIZONTAL','nivel_saida':0,'nivel_chegada':'3,2','pe_direito':320})
    r.save(tmp_path,'13_PAV','P1',{'classificacao':'MORRE'})
    fields=r.load(tmp_path,'13_PAV','P1')
    assert fields['nivel_saida']==0 and fields['nivel_chegada']==3.2
    assert r.apply_robot({},fields)=={'altura':320,'pd_pavimento_cm':320,'nivel_saida_abs':0,'nivel_chegada_abs':3.2}
    p=r.apply({'classification':'NASCE','ignore_in_beams':True},fields)
    assert r.eligible(p) and not p['ignore_in_beams'] and p['orientation']=='RETANGULAR HORIZONTAL'

@pytest.mark.parametrize('fields',[{'pe_direito':0},{'pe_direito':'nan'},{'nivel_saida':float('inf')},{'classificacao':'x'},{'orientacao':'x'},{'extra':3}])
def test_invalid_fields_fail(fields):
    with pytest.raises(ValueError): r.validate(fields)

@pytest.mark.parametrize('item',['../P1','a/b','a\\b','..'])
def test_identity_path_rejected(tmp_path,item):
    with pytest.raises(ValueError): r.save(tmp_path,'13_PAV',item,{'classificacao':'NASCE'})
