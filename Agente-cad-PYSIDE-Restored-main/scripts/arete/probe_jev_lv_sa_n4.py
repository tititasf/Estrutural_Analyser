# -*- coding: utf-8 -*-
"""Primeiro teste Jev (TypeSafe System One) no caminho LV SA x N3 x N4.

O codigo conta. O Jev so julga o que o codigo ja mediu.
Nao grava em producao. Nao imprime chave.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient

ARETE = Path(__file__).resolve().parent
REPO = ARETE.parent.parent
for _p in (REPO, ARETE.parent, ARETE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.core.lv_generation_contract import build_lv_generation_contracts  # noqa: E402
from arete.build_lv_debug_viewer import (  # noqa: E402
    DB_PADRAO, N4_APROVADO, PROJETO, VIGAS, _n4_units,
)

load_dotenv(REPO / '.env')


def _faces() -> list[dict]:
    conn = sqlite3.connect(f'file:{DB_PADRAO}?mode=ro', uri=True)
    bboxes = {}
    for nome, pts in conn.execute(
            'SELECT name, points_json FROM pillars WHERE project_id=?',
            (PROJETO,)):
        try:
            p = json.loads(pts or '[]')
            xs = [float(q[0]) for q in p]
            ys = [float(q[1]) for q in p]
            if xs:
                bboxes[str(nome)] = (min(xs), min(ys), max(xs), max(ys))
        except Exception:
            continue

    out = []
    for viga in VIGAS:
        row = conn.execute(
            'SELECT data_json FROM beams WHERE project_id=? AND name=?',
            (PROJETO, viga)).fetchone()
        if not row:
            continue
        beam = json.loads(row[0] or '{}')
        ct = build_lv_generation_contracts(
            beam, beam_name=viga, floor='13_PAV', pillar_bboxes=bboxes)
        n4_a = N4_APROVADO / ('LV_preview_%s_A.dxf' % viga)
        para = ct.get('Para') or {}
        for lado in ('A', 'B'):
            segs = ((para.get(lado) or {}).get('structural_segments') or [])
            pans = ((para.get(lado) or {}).get('panels') or [])
            n4 = _n4_units(n4_a, lado) if n4_a.exists() else []
            out.append({
                'beam': viga,
                'face': lado,
                'sa_structural_segments': len(segs),
                'n3_panels_on_face': len(pans),
                'n4_face_segments': len(n4),
                'n4_heights_59_or_124': [
                    int(u.get('h_class') or 0) for u in n4
                ],
                'sa_equals_n4': len(segs) == len(n4),
            })
    return out


def _dump(title: str, obj) -> None:
    print('\n===', title, '===')
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    faces = _faces()
    same_all = all(f['sa_equals_n4'] for f in faces)
    print('CODIGO (contagem exata, nao e o Jev)')
    print('SA == N4 em todas as faces?', same_all)
    for f in faces:
        print('  {beam}.{face}  SA={sa_structural_segments}  '
              'N3_paineis={n3_panels_on_face}  N4={n4_face_segments}  '
              'igual={sa_equals_n4}'.format(**f))

    state_simple = {
        'glossary': {
            'SA': 'Structural Analyzer: segmentos estruturais da planta (S1..Sn).',
            'N4': 'DXF de forma gerado do recorte humano aprovado (n4_AN).',
            'face': 'Lado A ou B da viga.',
        },
        'rule': (
            'Two counts are the same only when sa_structural_segments equals '
            'n4_face_segments on that face. Do not average across faces.'
        ),
        'faces': faces,
        'code_already_computed': {
            'all_faces_have_equal_sa_and_n4': same_all,
        },
    }

    q_simple = {
        'same_count_every_face': Noul(
            instructions=(
                'On every object in `faces`, is `sa_structural_segments` '
                'equal to `n4_face_segments`?'
            ),
            criteria=NoulCriteria(
                true='Every listed face has equal SA and N4 counts.',
                false='At least one listed face has different SA and N4 counts.',
            ),
        ),
        'count_relationship': Choice(
            instructions=(
                'Across the faces in `faces`, how do SA structural segment '
                'counts compare to N4 face segment counts?'
            ),
            criteria={
                'equal_everywhere': (
                    'SA count equals N4 count on every face'
                ),
                'sa_always_higher': (
                    'SA count is higher than N4 on every face, never equal'
                ),
                'n4_always_higher': (
                    'N4 count is higher than SA on every face, never equal'
                ),
                'mixed': (
                    'Some faces equal, some SA higher, or some N4 higher'
                ),
            },
        ),
    }

    with TypeSafeClient() as client:
        r1 = client.system_one(state=state_simple, questions=q_simple)
        print('\nJEV chamada 1 — pergunta simples')
        print('model', r1.model)
        print('same_count_every_face noul',
              round(r1.nouls['same_count_every_face'].noul, 4))
        rel = r1.choices['count_relationship']
        print('count_relationship', rel.choice,
              'confidence', round(rel.confidence, 4))
        print('probabilities', {k: round(v, 4)
                                for k, v in rel.probabilities.items()})
        if r1.usage:
            print('tokens in/out', r1.usage.input_tokens, r1.usage.output_tokens)

        state_n3 = {
            'goal': (
                'N3 must draw the same face segments as the approved N4, '
                'using SA interpretation and its fichas. N3 is generated from '
                'N1/SA, not from the human N2 recorte.'
            ),
            'do_not': (
                'Do not rewrite the Structural Analyzer schema. Do not invent '
                'panel widths. Counting is already done in `faces`.'
            ),
            'faces': faces,
            'known_pipeline': {
                'SA_grammar': (
                    'Splits the plant at pillars and section changes (S1..Sn).'
                ),
                'N4_grammar': (
                    'Face occurrences in the form drawing (V301.A, CONT., #n). '
                    'On V301 a 19/55 stretch (height ~59) and a 19/120 stretch '
                    '(height ~124) in the same N4 label are two segments.'
                ),
                'N3_today': (
                    'Uses SA structural_segment_index to place panels on the '
                    'face. One N1 section label (often 19/55) is stamped onto '
                    'every LV segment. Mixed 19/55 vs 19/120 is not implemented.'
                ),
            },
        }
        q_n3 = {
            'n3_can_match_n4_with_current_sa_segments': Noul(
                instructions=(
                    'Given `faces` and `known_pipeline`, can N3 reach the N4 '
                    'segment count on every face if it keeps using SA '
                    'structural segments one-for-one as its segments?'
                ),
                criteria=NoulCriteria(
                    true=(
                        'SA count already equals N4 on every face, so a '
                        'one-for-one copy would match.'
                    ),
                    false=(
                        'SA and N4 counts differ, so copying SA segments '
                        'one-for-one cannot match N4 counts.'
                    ),
                ),
            ),
            'primary_mismatch': Choice(
                instructions=(
                    'What is the main reason N3 segment counts do not match '
                    'approved N4, given `faces` and `known_pipeline`?'
                ),
                criteria={
                    'grammar_sa_vs_n4': {
                        'what': (
                            'SA and N4 count different units: plant stretches '
                            'vs form-face occurrences (and V301 59 vs 124).'
                        ),
                        'not_for': (
                            'A mere render bug, or N3 inventing extra panels '
                            'inside an already-correct segment list.'
                        ),
                    },
                    'n3_panel_split_only': {
                        'what': (
                            'SA and N4 already agree on how many segments; '
                            'N3 only splits panels wrongly inside them.'
                        ),
                        'not_for': 'Faces where SA count != N4 count.',
                    },
                    'missing_n4_source': {
                        'what': (
                            'N4 files in the comparison are the wrong or old '
                            'drawings, so the target count is invalid.'
                        ),
                        'not_for': 'Counts taken from n4_AN as listed in faces.',
                    },
                    'insufficient_evidence': {
                        'what': (
                            'The supplied state is not enough to name a cause.'
                        ),
                        'not_for': 'A cause already described in known_pipeline.',
                    },
                },
            ),
            'next_code_action': Choice(
                instructions=(
                    'What should the CAD-ANALYZER code do next to move N3 '
                    'toward N4, without replacing the N3 generator by Jev?'
                ),
                criteria={
                    'map_sa_spans_onto_n4_units': (
                        'Build an explicit mapping from SA S-tags onto N4 '
                        'face units (including 59/124 splits) and drive N3 '
                        'panel grouping from that mapping.'
                    ),
                    'change_sa_schema': (
                        'Change Structural Analyzer fields so N1 already '
                        'emits N4 face units.'
                    ),
                    'let_jev_draw_n3': (
                        'Ask Jev to generate the N3 DXF or rewrite the '
                        'STOG generator.'
                    ),
                    'stop_and_ask_owner': (
                        'Counts and grammar are too ambiguous; ask the owner '
                        'which unit definition N3 must follow.'
                    ),
                },
            ),
            'how_far_is_n3': Score(
                instructions=(
                    'How far is current N3 from matching approved N4 segment '
                    'counts, using `faces` (compare n3_panels_on_face and '
                    'n4_face_segments, and SA vs N4)?'
                ),
                criteria=[
                    'Already the same count on every face',
                    'Close: a few faces off by a small split, most agree',
                    'Same grammar, but panel grouping is consistently wrong',
                    'Different unit grammar; counts disagree on every face',
                ],
            ),
        }
        r2 = client.system_one(state=state_n3, questions=q_n3)
        print('\nJEV chamada 2 — diagnostico N3')
        print('model', r2.model)
        print('n3_can_match_one_for_one noul',
              round(r2.nouls['n3_can_match_n4_with_current_sa_segments'].noul, 4))
        mm = r2.choices['primary_mismatch']
        print('primary_mismatch', mm.choice, 'confidence', round(mm.confidence, 4))
        print('  probs', {k: round(v, 4) for k, v in mm.probabilities.items()})
        nx = r2.choices['next_code_action']
        print('next_code_action', nx.choice, 'confidence', round(nx.confidence, 4))
        print('  probs', {k: round(v, 4) for k, v in nx.probabilities.items()})
        sc = r2.scores['how_far_is_n3']
        print('how_far_is_n3 score', round(sc.score, 3),
              'confidence', round(sc.confidence, 4))
        print('  legend', sc.legend)
        print('  probs', {k: round(v, 4) for k, v in sc.probabilities.items()})
        if r2.usage:
            print('tokens in/out', r2.usage.input_tokens, r2.usage.output_tokens)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
