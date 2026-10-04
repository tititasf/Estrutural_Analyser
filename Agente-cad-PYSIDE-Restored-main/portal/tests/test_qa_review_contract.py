import copy
import pytest


def test_posterior_cannot_silently_reverse_prior_findings():
    source = {'checks':[{'id':'tags_lideres','status':'fail'}, {'id':'niveis','status':'uncertain'}]}
    post = {'checks':[{'id':'tags_lideres','status':'pass'}, {'id':'niveis','status':'uncertain'}]}
    assert len(q.transition_errors(source, post)) == 1
    post['finding_resolutions'] = [dict(criterion_id='tags_lideres',source_status='fail',
        disposition='retracted', reason='Marca anterior contradiz a regra de contato.',
        rule_refs=['manual#contato'], evidence=[dict(source='reference.svg',location='contato B',finding='viga no canto BC')])]
    assert not q.transition_errors(source, post)
    post['finding_resolutions'][0]['evidence'][0]['source'] = 'fields.json'
    assert q.transition_errors(source, post)
from portal.app import qa_review_contract as q

def test_cited_svg_requires_its_own_round_read_receipt():
    review = {'execution_audit': {'reads': [
        {'path': 'round/current/fields.json'},
        {'path': 'round/current/reference.png'},
        {'path': 'round/other/source.svg'}]}, 'checks': [
        {'evidence': [{'source': 'reference.png'}, {'source': 'source.svg'}]}]}
    assert len(q.cited_read_errors(review)) == 1
    review['execution_audit']['reads'].append({'path': 'round\\current\\source.svg'})
    assert not q.cited_read_errors(review)
    review['unit_reviews'] = [{'checks': {'dimensoes': {
        'evidence': [{'source': 'reference.svg'}]}}}]
    assert q.cited_read_errors(review)[0].startswith('reference.svg:')


def payload(classe='PIL'):
    return {'assessment':'pass','action':'manter','confidence_basis':'cotas independentes',
            'checks':[{'id':i,'status':'pass','expected':'regra','actual':'cota',
                       'rule_refs':['manual#seção'],
                       'evidence':[{'source':'source.png','location':'face A','finding':'cota 19'}]}
                      for i in q.CRITERIA[classe]]}


@pytest.mark.parametrize('classe', list(q.CRITERIA))
def test_pass_cannot_hide_nested_source_level_unit_error(classe):
    fields = {'sa_snapshot': {'collections': {'items': [
        {'uid': 'one', 'nested': {'nivel': '852.19cm'}, 'height': '55cm'}]}}}
    review = payload(classe)
    review['unit_reviews'] = [{'unit_path': '/collections/items/0', 'checks': {
        c['id']: {'status': 'pass', 'observation': 'original unidade one',
                  'evidence': c['evidence']} for c in review['checks']}}]
    with pytest.raises(ValueError, match='campos da versão julgada'):
        q.validate(review, classe, fields)
    fields['sa_snapshot']['collections']['items'][0]['nested']['nivel'] = '852.19 m'
    assert q.validate(review, classe, fields)['pass'] == 8


@pytest.mark.parametrize('classe',list(q.CRITERIA))
def test_unit_ledger_rejects_omissions_and_hidden_uncertainty(classe):
    fields = {'sa_snapshot': {'collections': {'items': [{'uid':'one'}, {'uid':'two'}]}}}
    p = payload(classe)
    with pytest.raises(ValueError,match='ledger'): q.validate(p,classe,fields)
    p['unit_reviews'] = [{'unit_path':f'/collections/items/{n}', 'checks':{
        c['id']: {'status':c['status'], 'observation':'measured independently',
                  'evidence':[dict(e, location=f'unidade {n} original') for e in c['evidence']]} for c in p['checks']}}
        for n in range(2)]
    assert q.validate(p,classe,fields)['pass']==8
    assert p['unit_coverage']['units']==2
    assert not p['unit_coverage']['measured_accuracy']
    incomplete=copy.deepcopy(p); incomplete['unit_reviews'].pop()
    with pytest.raises(ValueError,match='incompleto'): q.validate(incomplete,classe,fields)
    criterion=q.CRITERIA[classe][0]
    p['unit_reviews'][1]['checks'][criterion]['status']='uncertain'
    with pytest.raises(ValueError,match='esconde'): q.validate(p,classe,fields)
    p['checks'][0]['status']='uncertain';p.update(assessment='inconclusive',action='revisar_humano')
    assert q.validate(p,classe,fields)['uncertain']==1


def test_shared_context_needs_distinct_original_local_proof():
    p=payload('FV')
    shared={'source':'reference.svg','location':'paredes gerais da viga','finding':'largura 19 cm'}
    p['unit_reviews']=[{'unit_path':f'/collections/fundo/{n}','checks':{
        'apoios_limites':{'status':'pass','observation':f'S{n+1}', 'evidence':[shared]}}}
        for n in range(2)]
    assert len(q._local_proof_errors(p))==2
    for n, unit in enumerate(p['unit_reviews']):
        unit['checks']['apoios_limites']['evidence'].append({
            'source':'reference.svg','location':f'entidade original {n}',
            'finding':f'aresta terminal {n} comprovada'})
    assert not q._local_proof_errors(p)
    # Regional level proof and routing context may legitimately be shared.
    for unit in p['unit_reviews']:
        unit['checks']={'niveis':{'status':'pass','evidence':[shared]}}
    assert not q._local_proof_errors(p)


def test_unit_ledger_rejects_self_proof_and_unknown_status():
    p=payload();fields={'sa_snapshot':{'collections':{'pilares':[{}]}}}
    p['unit_reviews']=[{'unit_path':'/collections/pilares/0','checks':{
        c['id']:{'status':'pass','observation':'value','evidence':copy.deepcopy(c['evidence'])}
        for c in p['checks']}}]
    p['unit_reviews'][0]['checks']['niveis']['evidence']=[{
        'source':'fields.json','location':'level','finding':'852.19'}]
    with pytest.raises(ValueError,match='independente'):q.validate(p,'PIL',fields)
    p['checks'][0]['status']='invented'
    with pytest.raises(ValueError,match='inválido'):q.validate(p,'PIL')


def test_equal_lv_indices_do_not_establish_same_physical_interval():
    proof={'source':'reference.png','location':'cota x=120 a 220','finding':'100 cm'}
    def unit(collection, index):
        return {'unit_path':f'/collections/{collection}/{index}','checks':{
            'dimensoes':{'status':'pass','observation':'100 cm', 'evidence':[proof]}}}
    p={'unit_reviews':[unit('lateral_a_para',0),unit('lateral_b_para',0)]}
    assert len(q._local_proof_errors(p))==2
    # The same original dimension can support both sides only with a distinct
    # observation locating the actual interval on each side, not index matching.
    b=p['unit_reviews'][1]['checks']['dimensoes']
    b['evidence']=[dict(proof, location='Face B: cota x=120 a 220')]
    assert not q._local_proof_errors(p)
    b['evidence']=[proof]
    p['unit_reviews'].append(unit('lateral_a_para',1))
    assert len(q._local_proof_errors(p))==3


def test_provider_cannot_supply_measured_unit_metrics():
    p=payload();p['unit_coverage']={'units':100,'measured_accuracy':True}
    q.validate(p,'PIL')
    assert 'unit_coverage' not in p


@pytest.mark.parametrize('other',[
    '/collections/lateral_b_para/1',
    '/collections/lateral_b_passa/0',
    '/collections/lateral_a_passa/0',
    '/collections/lateral_arbitrary/0',
])
def test_shared_lv_dimension_cannot_cross_segment_or_behavior(other):
    proof={'source':'reference.png','location':'cota x=120 a 220','finding':'100 cm'}
    p={'unit_reviews':[{'unit_path':path,'checks':{
        'dimensoes':{'status':'pass','evidence':[proof]}}}
        for path in ('/collections/lateral_a_para/0',other)]}
    assert len(q._local_proof_errors(p)) == 2


def test_read_gate_reports_all_missing_files_for_one_bounded_repair(tmp_path):
    folder=tmp_path/'evidence';folder.mkdir()
    for name in ('source.png','reference.png','fields.json','rules.json'):
        (folder/name).write_bytes(b'fixture')
    with pytest.raises(ValueError) as error:
        q.validate_read_receipts({'origin':'antigravity_stream','reads':[]},folder,tmp_path,'FV')
    assert all(name in str(error.value) for name in ('source.png','reference.png','fields.json','rules.json'))


def test_compact_proof_catalog_preserves_unit_gates():
    p=payload();fields={'sa_snapshot':{'collections':{'pilares':[{}]}}}
    p['evidence_catalog']={'E1':{'source':'reference.png','location':'P1 norte','finding':'cota original 19'}}
    p['unit_reviews']=[{'unit_path':'/collections/pilares/0','checks':{
        c['id']:{'status':'pass','observation':'P1: medida original 19','evidence_refs':['E1']}
        for c in p['checks']}}]
    assert q.validate(p,'PIL',fields)['pass']==8
    assert p['unit_reviews'][0]['checks']['dimensoes']['evidence']==[p['evidence_catalog']['E1']]
    bad=copy.deepcopy(p);bad['unit_reviews'][0]['checks']['niveis']['evidence_refs']=['missing']
    with pytest.raises(ValueError,match='referência ausente'):q.validate(bad,'PIL',fields)
    bad=copy.deepcopy(p);bad['evidence_catalog']['E1']['source']='fields.json'
    for detail in bad['unit_reviews'][0]['checks'].values():detail.pop('evidence')
    with pytest.raises(ValueError,match='independente'):q.validate(bad,'PIL',fields)


@pytest.mark.parametrize('classe',list(q.CRITERIA))
def test_class_interpretation_manuals_need_current_cli_read(classe,tmp_path):
    import hashlib
    folder=tmp_path/'evidence';folder.mkdir()
    source=folder/'source.png';source.write_bytes(b'original pixels')
    manuals=[]
    for name in q.INTERPRETATION[classe]:
        path=tmp_path/'docs'/name;path.parent.mkdir(exist_ok=True)
        path.write_text('canonical rule '+name,encoding='utf-8');manuals.append(path)
    def receipt(path):
        return {'path':path.relative_to(tmp_path).as_posix(),
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    audit={'origin':'antigravity_stream','reads':[receipt(source)]}
    with pytest.raises(ValueError) as error:
        q.validate_read_receipts(audit,folder,tmp_path,classe)
    assert all(name in str(error.value) for name in q.INTERPRETATION[classe])
    audit['reads'].extend(receipt(path) for path in manuals)
    assert q.validate_read_receipts(audit,folder,tmp_path,classe) is audit
    manuals[0].write_text('updated canonical rule',encoding='utf-8')
    with pytest.raises(ValueError,match=q.INTERPRETATION[classe][0]):
        q.validate_read_receipts(audit,folder,tmp_path,classe)


def test_repair_diagnostics_identify_all_self_proof_checks():
    p=payload()
    for c in p['checks'][:3]:c['evidence'][0]['source']='fields.json'
    with pytest.raises(ValueError) as error:q.validate(p,'PIL')
    assert all(c['id'] in str(error.value) for c in p['checks'][:3])


@pytest.mark.parametrize('classe',list(q.CRITERIA))
def test_pass_cannot_call_absolute_level_centimeters(classe):
    p=payload(classe)
    check=next(c for c in p['checks'] if 'niveis' in c['id'])
    check['observation']='Nível da laje é 852.12cm (852.12m).'
    with pytest.raises(ValueError,match='níveis absolutos'): q.validate(p,classe)
    check['observation']='Nível da laje é 852.12 m; altura 12 cm.'
    assert q.validate(p,classe)['pass']==8


def test_unit_level_opinion_cannot_hide_wrong_units():
    p=payload()
    p['unit_reviews']=[{'unit_path':'/collections/pilares/0','checks':{
        'niveis':{'status':'pass','observation':'Cota de nível 852,19 cm confirmada',
                  'evidence':[{'source':'reference.png','location':'P1','finding':'cota 852,19'}]}}}]
    with pytest.raises(ValueError,match='níveis absolutos'): q.validate(p,'PIL')


def test_level_proof_can_include_a_legitimate_dimensional_cota():
    p={'unit_reviews':[{'unit_path':'/collections/lateral_a_para/0','checks':{
        'niveis_lajes_aberturas':{'status':'pass','observation':'Nível 852.19 m; altura 13 cm',
            'evidence':[{'finding':'Cota 305.5 cm no vão livre entre apoios'},
                        {'finding':'Cota de nível 852.19 m na região da laje'}]}}}]}
    assert not q._level_unit_errors(p)
    p['unit_reviews'][0]['checks']['niveis_lajes_aberturas']['evidence'][1]['finding']='Cota altimétrica 852.19 cm'
    assert q._level_unit_errors(p)


def test_cli_prompt_complete_correction_contract_is_explicit():
    from scripts.arete.qa_cli_fallback import build_item_prompt
    import json
    prompt=build_item_prompt(item='P1',layer='L1',context=q.instructions('PIL','SA'),qa_class='PIL')
    schema=json.JSONDecoder().raw_decode(prompt.split('Schema esperado:\n',1)[1])[0]
    suggestion=schema['suggestion']
    assert suggestion['candidate_interpretation'] is None
    assert suggestion['candidate_evidence']==suggestion['candidate_rule_refs']==[]
    assert suggestion['proposed']==[]
    assert 'EXATAMENTE UMA' in prompt and 'Não copie o snapshot completo também' in prompt

@pytest.mark.parametrize('classe',list(q.CRITERIA))
def test_required_coverage_and_independent_proof(classe):
    p=payload(classe)
    assert q.validate(p,classe)=={'pass':8,'fail':0,'uncertain':0}
    incomplete=copy.deepcopy(p);incomplete['checks'].pop()
    with pytest.raises(ValueError,match='incompleto'):q.validate(incomplete,classe)
    p['checks'][0]['evidence'][0]['source']='fields.json'
    with pytest.raises(ValueError,match='payload'):q.validate(p,classe)

def test_uncertainty_cannot_be_approval_or_geometry():
    p=payload();p['checks'][0]['status']='uncertain'
    with pytest.raises(ValueError,match='coerente'):q.validate(p,'PIL')
    p.update(assessment='inconclusive',action='revisar_humano')
    assert q.validate(p,'PIL')['uncertain']==1
    p['action']='corrigir'
    with pytest.raises(ValueError,match='sem prova'):q.validate(p,'PIL')

def test_overlay_cannot_prove_attributes_and_auditor_remains_auxiliary():
    p=payload();check=p['checks'][0]
    check['evidence']=[{'source':'source.svg','location':'overlay SA','finding':'tags geradas'}]
    with pytest.raises(ValueError,match='overlay'):q.validate(p,'PIL')
    check['evidence']=[{'source':'evidence_audit.json','location':'reports','finding':'snapshot'}]
    with pytest.raises(ValueError,match='payload'):q.validate(p,'PIL')
    check['status']='uncertain';p.update(assessment='inconclusive',action='revisar_humano')
    assert q.validate(p,'PIL')['uncertain']==1

def test_missing_rag_is_recorded_without_fake_retrieval(tmp_path,monkeypatch):
    monkeypatch.setenv('CAD_QA_KB_DB',str(tmp_path/'absent.sqlite'))
    root=tmp_path/'repo';root.mkdir();folder=root/'evidence';folder.mkdir()
    q.knowledge(root,'FV',folder)
    import json
    result=json.loads((folder/'knowledge.json').read_text())
    assert result['status']=='unavailable' and result['hits']==[]
    assert json.loads((folder/'rules.json').read_text())['missing']


@pytest.mark.parametrize('classe', list(q.CRITERIA))
def test_common_contracts_cannot_be_skipped_or_use_old_read(classe, tmp_path):
    import hashlib
    folder = tmp_path / 'evidence'; folder.mkdir()
    source = folder / 'source.png'; source.write_bytes(b'pixels')
    manuals = []
    for relative in q.COMMON_CONTRACTS:
        path = tmp_path / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('current human adoption and numeric contract', encoding='utf-8')
        manuals.append(path)
    def receipt(path):
        return {'path': path.relative_to(tmp_path).as_posix(),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    audit = {'origin': 'antigravity_stream', 'reads': [receipt(source)]}
    with pytest.raises(ValueError) as error:
        q.validate_read_receipts(audit, folder, tmp_path, classe)
    assert all(relative in str(error.value) for relative in q.COMMON_CONTRACTS)
    audit['reads'].extend(receipt(path) for path in manuals)
    assert q.validate_read_receipts(audit, folder, tmp_path, classe) is audit
    manuals[0].write_text('new owner decision', encoding='utf-8')
    with pytest.raises(ValueError, match='QA-SA-AUTOAJUSTE'):
        q.validate_read_receipts(audit, folder, tmp_path, classe)


@pytest.mark.parametrize('classe', list(q.CRITERIA))
def test_global_numeric_exception_is_explicit_in_effective_prompt(classe):
    prompt = q.instructions(classe, 'SA')
    assert 'níveis absolutos em metros usam exatamente duas casas' in prompt
    assert 'somente validação humana adota o SA' in prompt
    assert all(path in prompt for path in q.COMMON_CONTRACTS)

def test_auditor_resolves_exact_project_without_applying(tmp_path,monkeypatch):
    import json, sqlite3
    from types import SimpleNamespace
    script=tmp_path/'scripts/arete/qa_evidence_auditor.py';script.parent.mkdir(parents=True);script.touch()
    db=tmp_path/'project_data.vision'
    with sqlite3.connect(db) as c:
        c.execute('create table projects(id,work_name,pavement_name)')
        c.execute('insert into projects values(?,?,?)',('project',str(tmp_path/'obra'),'13_PAV'))
    stale=tmp_path/'stale.vision'
    with sqlite3.connect(stale) as c:
        c.execute('create table projects(id,work_name,pavement_name)')
    folder=tmp_path/'reports';folder.mkdir()
    def run(args,**kwargs):
        assert args[args.index('--project-id')+1]=='project'
        assert 'apply' not in args and '--jev-execute' not in args
        out=folder/'evidence_audit';out.mkdir();(out/'manifesto.json').write_text('{}')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(q.subprocess,'run',run)
    q.evidence_audit(SimpleNamespace(repo_root=tmp_path,sa_db_path=stale),{'nome':'obra','local_path':str(tmp_path/'obra')},
                     {'classe':'PIL','pavimento':'13_PAV'},'P1',folder)
    assert json.loads((folder/'evidence_audit.json').read_text())['status']=='reviewed'
    assert json.loads((folder/'evidence_audit.json').read_text())['database']==str(db.resolve())
