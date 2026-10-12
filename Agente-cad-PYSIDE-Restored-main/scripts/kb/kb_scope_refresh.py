"""Serialized, canonical work-KB rebuild, called after scoped source publication."""
import argparse
import fcntl
import json
import sys
import traceback
from pathlib import Path
from dotenv import load_dotenv

app=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(app/'scripts/kb'))
import kb_build
from kb_comum import sha256,texto_para_vetor

def run():
    p=argparse.ArgumentParser();p.add_argument('--obra-id',required=True);p.add_argument('--obra-dir',type=Path,required=True)
    args=p.parse_args();root=args.obra_dir.resolve();status=root/'knowledge/index_status.json'
    load_dotenv('/etc/cad-analyzer-knowledge.env',override=False)
    if not kb_build.RE_OBRA.fullmatch(args.obra_id): raise ValueError('invalid work ID')
    with (root/'knowledge/index.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            chunks=kb_build.chunks_obra(args.obra_id,root/'knowledge/sources')
            db=app/'KB-GLOBAL/obras'/f'{args.obra_id}.sqlite'
            kb_build.gravar(db,chunks,'nim','obra:'+args.obra_id,{'obra_id':args.obra_id,'sources':str(root/'knowledge/sources')})
            state={'status':'ready','obra_id':args.obra_id,'chunks':len(chunks),'db':str(db)}
        except Exception as exc:
            state={'status':'failed','obra_id':args.obra_id,'error':type(exc).__name__}
            traceback.print_exc()
        tmp=status.with_suffix('.tmp');tmp.write_text(json.dumps(state));tmp.replace(status)
        print(json.dumps(state),flush=True)

if __name__=='__main__':run()
