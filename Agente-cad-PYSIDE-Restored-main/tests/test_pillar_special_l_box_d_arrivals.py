from src.core.pillar_special_faces import (
    enrich_special_pillar_tables, physical_face_contact, special_l_face_segments,
)

# P27 do 13_PAV: L com braço horizontal para oeste; tampa curta D em x=4387,4.
P27 = [[4552.4, 2242.0], [4552.4, 2460.0], [4533.4, 2460.0], [4533.4, 2261.0],
       [4387.4, 2261.0], [4387.4, 2242.0], [4552.4, 2242.0]]


def _row(nome, canto, esq, dir_):
    return {'familia': 'viga', 'nome': nome, 'dim': '14/50', 'nivel': '—', 'canto': canto,
            'papel': 'chega', 'raw': '', 'dist_esq': esq, 'dist_dir': dir_}


def _tables():
    faces = {f: {'lajes': [], 'passa': [], 'chega': [], 'interior': []} for f in 'ABCD'}
    # Tabela da caixa envolvente: D = face sul inteira.
    faces['D']['chega'] = [_row('V327', 'DA', '151cm', '0cm'), _row('V328', 'DB', '0cm', '146cm')]
    return {'faces': faces}


def test_box_d_arrivals_with_impossible_corner_move_to_e():
    tables = enrich_special_pillar_tables(_tables(), {'points': P27}, beams=[], slab_points_map={})
    assert tables['faces']['D']['chega'] == []
    moved = {r['nome']: r['canto'] for r in tables['faces']['E']['chega']}
    assert set(moved) == {'V327', 'V328'}
    assert all(c[0] == 'E' and c[1] in tables['face_neighbors']['E'] for c in moved.values())
    segments = special_l_face_segments(P27)
    for fid in 'ABCDEF':
        for kind in ('passa', 'chega'):
            for row in tables['faces'][fid].get(kind) or []:
                physical_face_contact(segments, fid, kind, row)


def test_valid_d_corner_stays_on_d():
    tables = _tables()
    neighbors_d = enrich_special_pillar_tables(_tables(), {'points': P27}, beams=[], slab_points_map={})['face_neighbors']['D']
    tables['faces']['D']['chega'] = [_row('V999', 'D' + neighbors_d[0], '0cm', '5cm')]
    tables = enrich_special_pillar_tables(tables, {'points': P27}, beams=[], slab_points_map={})
    assert [r['nome'] for r in tables['faces']['D']['chega']] == ['V999']
