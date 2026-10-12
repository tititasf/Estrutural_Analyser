"""Register the approved NOVA/LV presentation profile in the portal.

The profile keeps the generator's dynamic geometry intact.  It records the
owner-approved design, enables the panel hatch that the design uses, and keeps
the two approved reference DXFs available in both independent LV profiles.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


# It must work both as ``python -m scripts.arete...`` and as the direct
# one-off administrative command used on the VPS.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


NOTES = """DESIGN APROVADO — Modo Nova / Laterais de viga

Escopo: AB e Visão Corte de Laterais Para e Laterais Passa, nas montagens
Gradeadas e Sarrafeadas. As duas montagens são sempre geradas e preservadas
separadamente; a escolha do painel seleciona a saída, sem apagar a outra.

Referências aprovadas: “Exemplo Laterais de viga Gradeadas NOVA.dxf” e
“Exemplo Laterais de viga Sarrafeadas NOVA.dxf”. A especificação canônica é
docs/PADRAO-NOVA-LATERAIS-APROVADO.md.

Regras de apresentação: hachuras reais de painéis, lajes e vazios; cotas e
patinhas preservadas; AB em escala 1× e Visão Corte em 2× no N5;
cores/layers/estilos preservados pelo motor. Gradeadas usam travessa 2,2 no
topo e meios pontaletes 3,5; sarrafeadas usam sarrafos 7 e não possuem
parafusos. Geometria, vãos, aberturas e continuidade são calculados
exclusivamente do contrato SA local.
"""


def active_jobs(db_path: Path) -> list[tuple[str, str]]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT id, status FROM portal_jobs WHERE status IN ('na_fila', 'executando')"
        ).fetchall()


def register(db_path: Path, actor: str, *, dry_run: bool = False) -> dict:
    """Apply the profile atomically through the public configuration service."""
    busy = active_jobs(db_path)
    if busy:
        raise RuntimeError(f'Existem jobs ativos; configuração não alterada: {busy}')

    from scripts import drawing_mode_config as profiles
    from portal.app import drawing_frame

    store = profiles.read_store()
    before_revision = store['revision']
    changed_profiles = []
    for cls in ('LV_PARA', 'LV_PASSA'):
        value = profiles.effective('NOVA', cls)
        changed = (
            value['layout']['DRAW_HATCHES_PAINEL'] is not True
            or value['layout']['DRAW_HATCHES_LAJE'] is not True
            or value['human_notes'] != NOTES
        )
        value['layout']['DRAW_HATCHES_LAJE'] = True
        value['layout']['DRAW_HATCHES_PAINEL'] = True
        value['human_notes'] = NOTES
        if changed:
            changed_profiles.append(cls)
            if not dry_run:
                profiles.save('NOVA', cls, value, store['revision'], actor)
                store = profiles.read_store()

    copied = []
    source_items = drawing_frame.examples('NOVA', 'LV_PARA')
    target_items = drawing_frame.examples('NOVA', 'LV_PASSA')
    hashes = {item['sha256'] for item in target_items}
    source_root = drawing_frame.directory('NOVA', 'LV_PARA', 'drawing_examples')
    for item in source_items:
        if item['sha256'] in hashes:
            continue
        copied.append(item['filename'])
        if not dry_run:
            drawing_frame.add_example(
                'NOVA', 'LV_PASSA', item['filename'],
                (source_root / f"{item['id']}.dxf").read_bytes(),
            )
            hashes.add(item['sha256'])

    result = {
        'before_revision': before_revision,
        'revision': profiles.read_store()['revision'] if not dry_run else before_revision,
        'changed_profiles': changed_profiles,
        'copied_to_lv_passa': copied,
        'examples_lv_para': drawing_frame.examples('NOVA', 'LV_PARA'),
        'examples_lv_passa': drawing_frame.examples('NOVA', 'LV_PASSA'),
        'dry_run': dry_run,
    }
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--portal-db', default='portal_data.db', type=Path)
    parser.add_argument('--actor', default='Codex: design NOVA LV aprovado')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    print(json.dumps(register(args.portal_db.resolve(), args.actor, dry_run=args.dry_run), ensure_ascii=False))
