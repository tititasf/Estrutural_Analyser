"""Lossless bounded source fragments, suitable for staged advisory queries."""
import json
import sys
from pathlib import Path
from scripts.arete.jev_calibration.hashing import sha256_json

def encoded(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf8')

def split_record(record,max_bytes=6000):
    # A token budget must additionally be checked by the API tokenizer; bytes
    # are only a conservative transport bound, never reported as real tokens.
    header={k:v for k,v in record.items() if k!='entities'}
    chunks=[];current=[]
    for ent in record['entities']:
        if len(encoded({'event':header,'entities':[ent]}))>max_bytes:
            raise ValueError('Single CAD entity exceeds fragment budget; no truncation permitted')
        if current and len(encoded({'event':header,'entities':[*current,ent]}))>max_bytes:
            chunks.append({'event':header,'entities':current});current=[]
        current.append(ent)
    if current or not chunks:chunks.append({'event':header,'entities':current})
    assert [e for c in chunks for e in c['entities']]==record['entities']
    return chunks

def main():
    folder=Path(sys.argv[1]);data=json.loads((folder/'SOURCE-EVENTS.json').read_text(encoding='utf8'))
    claimed=data.pop('sha256')
    if sha256_json(data)!=claimed:raise ValueError('Source evidence integrity failure')
    dest=folder/'source_fragments';dest.mkdir(exist_ok=False);items=[]
    for i,row in enumerate(data['records'],1):
        chunks=split_record(row)
        for j,chunk in enumerate(chunks,1):
            raw=encoded(chunk);name=f'{i:03d}_{j:03d}.json';(dest/name).write_bytes(raw)
            items.append({'file':name,'encounter_id':row['encounter_id'],'fragment':j,
                'fragment_count':len(chunks),'bytes':len(raw),'sha256':sha256_json(chunk),
                'handles':[e['handle'] for e in chunk['entities']]})
    result={'events':len(data['records']),'fragments':len(items),'max_bytes':max(r['bytes'] for r in items),
        'coverage_verified':True,'source_evidence_sha256':claimed,'api_calls':0,'items':items,
        'note':'Fragments retain every entity. Final semantic decision needs all fragments and validated context.'}
    (folder/'FRAGMENTS.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='items'},indent=2))

if __name__=='__main__':main()
