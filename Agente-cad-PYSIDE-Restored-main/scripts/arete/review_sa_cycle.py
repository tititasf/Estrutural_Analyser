"""Review exact corrections in a saved development cycle; no SA or rendering."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.arete.sa_development_review import _json, review_saved_cycle, file_sha256
from scripts.arete.dev_sa_cycle import write

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('report','source','baseline-state','current-state','receipt','out'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--reviewer',action='append',required=True)
    parser.add_argument('--evidence',action='append',default=[],metavar='ID=PATH')
    args=parser.parse_args(); registry={}
    for value in args.evidence:
        identity,separator,path=value.partition('=')
        if not separator or not identity or not path or identity in registry:
            parser.error('--evidence requires unique nonempty ID=PATH')
        registry[identity]=Path(path).resolve()
    target=Path(args.out).resolve()
    if target.exists(): parser.error('Use a new output file; preserve original reports')
    result=review_saved_cycle(_json(args.report),_json(args.receipt),
        source_path=args.source,baseline_state_path=args.baseline_state,
        current_state_path=args.current_state,evidence_paths=registry,
        accepted_reviewers=set(args.reviewer))
    result['raw_report_sha256']=file_sha256(args.report)
    write(target,result)
    print('Reviewed artifact:',target,'pending:',result['assessment']['pending_count'])
    return 0 if result['assessment']['ready_for_publication'] else 3

if __name__=='__main__': sys.exit(main())
