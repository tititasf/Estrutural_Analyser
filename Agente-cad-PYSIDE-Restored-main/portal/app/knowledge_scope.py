"""Scoped knowledge sources. CAD snapshots are evidence, never global rules."""
from __future__ import annotations
import hashlib
import json
import logging
import re
import subprocess
import sys
import sqlite3
import uuid
from pathlib import Path

log = logging.getLogger(__name__)
_SAFE = re.compile(r'^[A-Za-z0-9_.-]+$')

def safe(value):
    value = str(value)
    if not _SAFE.fullmatch(value) or '..' in value:
        raise ValueError('invalid knowledge scope')
    return value

def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(value, encoding='utf-8')
    temporary.replace(path)

def _evidence_text(value):
    if isinstance(value, dict):
        return {k: _evidence_text(v) for k,v in value.items()
                if k not in {'svg', 'html', 'png', 'image_base64', 'preview_svg'}}
    if isinstance(value,list): return [_evidence_text(v) for v in value]
    return value

def _search_projection(value):
    """Index semantic fields; complete geometry remains in the JSON evidence."""
    if isinstance(value, dict):
        return {k: _search_projection(v) for k,v in value.items()
                if k not in {'points', 'vertices', 'polygon', 'polygons', 'pts',
                             'geometry', 'contour', 'contours', 'triangles',
                             'svg', 'html', 'png', 'image_base64', 'preview_svg'}}
    if isinstance(value, list): return [_search_projection(v) for v in value]
    return value

def _search_lines(value, prefix=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _search_lines(child, prefix+'.'+key if prefix else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _search_lines(child, prefix+'['+str(index)+']')
    else:
        yield prefix+': '+json.dumps(value,ensure_ascii=False,separators=(',',':'))

def _source(root, obra_id, floor, relative, title, payload, provenance):
    data = {'scope': {'obra_id':obra_id, 'pavimento_id':floor},
            'status':'observed_unreviewed', 'provenance':provenance,
            'data':_evidence_text(payload)}
    target = root/'knowledge'/'sources'/'pavimentos'/safe(floor)/relative
    _write(target.with_suffix('.json'), json.dumps(data,ensure_ascii=False,indent=2))
    search_text = '\n'.join(_search_lines(_search_projection(data)))
    _write(target.with_suffix('.md'), '# '+title+'\n\n'
           'Escopo exclusivo: obra '+obra_id+'; pavimento '+floor+'.\n'
           'Evidência observada; não é aprovação nem regra universal.\n'
           'Evidência completa com geometria: '+target.with_suffix('.json').name+'\n\n'
           + search_text+'\n')

def _archive_removed(directory, current):
    if not directory.is_dir(): return
    knowledge = next(parent for parent in directory.parents if parent.name == 'knowledge')
    history = knowledge/'history'/uuid.uuid4().hex
    for path in directory.rglob('*'):
        if path.is_file() and path.suffix in {'.md','.json'} and path.stem not in current:
            target=history/path.relative_to(directory)
            target.parent.mkdir(parents=True,exist_ok=True)
            path.replace(target)

def _archive_towers(directory, current):
    """Removed/failed towers must not keep stale facts in the searchable sources."""
    if not directory.is_dir(): return
    for child in directory.iterdir():
        if child.is_dir() and child.name not in current:
            _archive_removed(child, set())

def request_index(obra_dir, obra_id):
    root = Path(obra_dir).resolve()
    app = Path(__file__).resolve().parents[2]
    script = app/'scripts/kb/kb_scope_refresh.py'
    if not script.is_file(): raise RuntimeError('canonical scoped index runner unavailable')
    status = root/'knowledge/index_status.json'
    _write(status,json.dumps({'status':'queued','obra_id':safe(obra_id)}))
    output = (root/'knowledge/index.log').open('a')
    try:
        subprocess.Popen([sys.executable,str(script),'--obra-id',safe(obra_id),
                          '--obra-dir',str(root)],stdout=output,stderr=subprocess.STDOUT,
                         start_new_session=True)
    finally: output.close()

def publish_floor(obra_dir, obra_id, result):
    from .preprocessamento.service import read_tower
    root = Path(obra_dir).resolve(); floor=safe(result['pavimento_id']); safe(obra_id)
    if result['obra_id'] != obra_id: raise ValueError('cross-work preprocessing memory')
    _source(root,obra_id,floor,Path('preprocessamento/inventario'),
            'Pré-processamento '+floor, result, {'run_id':result['run_id']})
    current_towers = set()
    for sid, ref in result['towers'].items():
        if ref.get('status') == 'failed': continue
        package = read_tower(root,result,sid)
        if package['scope']['obra_id'] != obra_id: raise ValueError('cross-work tower memory')
        provenance={'run_id':result['run_id'],'recorte_id':sid,
                    'source_revision':package['scope']['source_revision'],
                    'sources':package.get('sources',[]),'package_hash':ref['hash']}
        key=hashlib.sha256(sid.encode()).hexdigest()[:20]
        current_towers.add(key)
        for module in ('pillars','structural_labels','level_inventory','level_conventions','pillar_conventions','cuts','beam_sections','conflicts','auxiliary_evidence','context_qa'):
            _source(root,obra_id,floor,Path('preprocessamento')/key/module,
                    module+' '+floor,package.get(module),provenance)
        auxiliary_keys = set()
        for evidence in package.get('auxiliary_evidence', []):
            eid = hashlib.sha256(evidence['source_id'].encode()).hexdigest()[:20]
            auxiliary_keys.add(eid)
            _source(root,obra_id,floor,Path('preprocessamento')/key/'recortes_auxiliares'/eid,
                    'Recorte auxiliar '+evidence['source_id'],evidence,provenance)
        _archive_removed(root/'knowledge/sources/pavimentos'/floor/'preprocessamento'/key/'recortes_auxiliares',auxiliary_keys)
        current_facts = set()
        for fact in package.get('levels',[]):
            fid=hashlib.sha256(str(fact.get('fact_id',fact)).encode()).hexdigest()[:20]
            current_facts.add(fid)
            _source(root,obra_id,floor,Path('niveis')/key/fid,
                    'Nível '+str(fact.get('display_name') or fact.get('item_id') or fid),fact,provenance)
        _archive_removed(root/'knowledge/sources/pavimentos'/floor/'niveis'/key,current_facts)
    for category in ('preprocessamento','niveis'):
        _archive_towers(root/'knowledge/sources/pavimentos'/floor/category,current_towers)
    publish_sa(root,obra_id,floor,enqueue=False)
    request_index(root,obra_id)

def publish_sa(obra_dir, obra_id, floor, enqueue=True):
    root=Path(obra_dir).resolve(); safe(obra_id); floor=safe(floor)
    state=root/('estado_'+floor+'.json')
    if not state.is_file(): return
    payload=json.loads(state.read_text())
    if payload.get('pavimento') != floor or Path(payload.get('obra','')).resolve()!=root:
        raise ValueError('SA snapshot scope mismatch')
    provenance={'snapshot':str(state.relative_to(root)),
                'snapshot_sha256':hashlib.sha256(state.read_bytes()).hexdigest(),
                'generated_at':payload.get('gerado_em'), 'source':'SA; not independent confirmation'}
    database=Path(payload.get('db_path',''))
    if not database.is_file(): raise ValueError('SA evidence database unavailable')
    with sqlite3.connect('file:'+database.as_posix()+'?mode=ro',uri=True) as conn:
        conn.row_factory=sqlite3.Row
        projects=[dict(row) for row in conn.execute('SELECT * FROM projects WHERE pavement_name=?',(floor,))
                  if Path(row['work_name'] or '').resolve()==root
                  and root in Path(row['dxf_path'] or '').resolve().parents]
        if not projects: raise ValueError('no project bound to work and floor')
        grouped={}
        for category,table in (('pilares','pillars'),('lajes','slabs'),('vigas','beams')):
            grouped[category]=[]
            for project in projects:
                for row in conn.execute('SELECT * FROM '+table+' WHERE project_id=?',(project['id'],)):
                    item=dict(row)
                    for field,value in list(item.items()):
                        if field.endswith('_json') and value:
                            try: item[field]=json.loads(value)
                            except ValueError: pass
                    grouped[category].append(item)
    provenance['projects']=[p['id'] for p in projects]
    for category,items in grouped.items():
        current=set()
        for item in items:
            name=str(item.get('key') or item.get('name') or item.get('nome') or item.get('id') or '')
            key=hashlib.sha256(str(item.get('id') or name).encode()).hexdigest()[:20]
            current.add(key)
            _source(root,obra_id,floor,Path('sa')/category/key,
                    category+' '+name,item,provenance)
        _archive_removed(root/'knowledge/sources/pavimentos'/floor/'sa'/category,current)
    if enqueue: request_index(root,obra_id)

def best_effort_sa(obra, floor):
    if not floor or not obra.get('local_path'): return
    try: publish_sa(obra['local_path'],obra['id'],floor)
    except Exception: log.exception('scoped SA knowledge publication failed')

def graph_nodes(conn):
    nodes=[];edges=[]
    for row in conn.execute('SELECT id,nome,local_path FROM portal_obras ORDER BY nome'):
        oid,name,directory=row; nid='obra:'+oid
        nodes.append({'id':nid,'label':name,'tipo':'obra','status':'ativo','grau':1,
                      'titulo':'Conhecimento exclusivo da obra '+name,'obra_id':oid,
                      'path':'/app/obras/'+oid,'data':''})
        for (floor,) in conn.execute('SELECT pavimento FROM portal_obra_pavimentos WHERE obra_id=? ORDER BY ordem',(oid,)):
            fid=nid+':pavimento:'+floor
            status='sem índice'
            if directory:
                p=Path(directory)/'knowledge/index_status.json'
                if p.is_file():
                    try: status=json.loads(p.read_text()).get('status',status)
                    except (OSError,ValueError): pass
            nodes.append({'id':fid,'label':floor,'tipo':'pavimento','status':'ativo','grau':1,
                          'obra_id':oid,'pavimento_id':floor,
                          'titulo':name+' / '+floor+' · memória: '+status,
                          'path':'/app/obras/'+oid+'?pavimento='+floor})
            edges.append({'s':nid,'t':fid,'tipo':'pertence'})
    return nodes,edges
