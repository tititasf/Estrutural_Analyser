"""Register the owner's approved NOVA design, scoped to LV drawing (not SA facts)."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


def register(db, specification, approved_by, integration_status=None):
    db = Path(db).resolve()
    if not db.is_file():
        raise ValueError('Banco existente obrigatório; não criar banco vazio')
    repo = Path(__file__).resolve().parents[2]
    # Desktop keeps the canonical DB above the checkout. On the VPS the
    # canonical DB lives in the checkout itself; reject only the stale copy.
    if db == repo/'project_data.vision' and (repo.parent/'project_data.vision').is_file():
        raise ValueError('A cópia do banco na raiz do repo é stale; use o banco do workspace')
    if not approved_by.strip():
        raise ValueError('Aprovador humano obrigatório')
    text = Path(specification).read_text(encoding='utf8')
    source_hash = sha256(text.encode()).hexdigest()
    sections = [(section.split('\n',1)[0], section.split('\n',1)[1].strip())
                for section in text.split('\n## ')[1:]]
    now = datetime.now(timezone.utc).isoformat()
    context = 'human_design_t1:NOVA:LV:20261005'
    inserted = 0
    updated = 0
    with sqlite3.connect(db) as con:
        existing = {field: json.loads(raw) for field, raw in con.execute(
            'SELECT field_id, regra_semantica FROM semantic_rag_kb WHERE obra_contexto=?', (context,))}
        for title, body in sections:
            field = 'design.lv.nova.'+sha256(title.encode()).hexdigest()[:12]
            previous = existing.get(field, {})
            if previous.get('source_hash') == source_hash:
                continue
            rule = dict(kind='human_approved_drawing_design', tier='T1', mode='NOVA',
                classes=['LV_PARA','LV_PASSA'], title=title, rule=body,
                source='docs/PADRAO-NOVA-LATERAIS-APROVADO.md', source_hash=source_hash,
                approved_by=previous.get('approved_by', approved_by), approved_at=previous.get('approved_at', now),
                approval='Laterais de viga nova totalmente aprovado; registra todos conhecimentos e regras aprendidas.',
                authority='Consultative drawing convention; never supplies missing SA dimensions.',
                integration_status=integration_status or previous.get('integration_status',
                    'Local validation; VPS generation not yet verified'))
            if previous:
                rule['updated_at'] = now
                con.execute('UPDATE semantic_rag_kb SET regra_semantica=? '
                            'WHERE obra_contexto=? AND field_id=?',
                            (json.dumps(rule, ensure_ascii=False), context, field))
                updated += 1
                continue
            con.execute('INSERT INTO semantic_rag_kb '
                '(classe,regra_semantica,obra_contexto,confianca,tier,field_id,familia) VALUES (?,?,?,?,?,?,?)',
                ('LV',json.dumps(rule,ensure_ascii=False),context,1.,'T1',field,'drawing_design'))
            inserted += 1
    return dict(inserted=inserted, updated=updated, already_registered=not (inserted or updated), source_hash=source_hash)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True,type=Path)
    parser.add_argument('--specification',default='docs/PADRAO-NOVA-LATERAIS-APROVADO.md',type=Path)
    parser.add_argument('--approved-by',required=True)
    parser.add_argument('--integration-status')
    args=parser.parse_args()
    print(json.dumps(register(args.db,args.specification,args.approved_by,args.integration_status)))
