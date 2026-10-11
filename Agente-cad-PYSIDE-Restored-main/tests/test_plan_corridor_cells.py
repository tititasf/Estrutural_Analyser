from src.core.plan_corridor_cells import corridor_cell_pieces, is_corridor_cell, plan_segments


def _rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


# Encontro V302×V316 do 13_PAV: paredes do V302 em y=2661/2680 param nas
# bordas do miolo; paredes do V316 em x=2477.4/2496.4 seguem para cima.
FLANGE = _rect(2461.9, 2661, 2511.9, 2680)
WEB = _rect(2477.4, 2661, 2496.4, 2759)
DXF = {'lines': [
    {'start': (2000, 2661), 'end': (2461.9, 2661)}, {'start': (2511.9, 2661), 'end': (3000, 2661)},
    {'start': (2000, 2680), 'end': (2461.9, 2680)}, {'start': (2511.9, 2680), 'end': (3000, 2680)},
    {'start': (2477.4, 2680), 'end': (2477.4, 2900)}, {'start': (2496.4, 2680), 'end': (2496.4, 2900)},
], 'polylines': [{'points': FLANGE}, {'points': WEB}]}


def test_beam_junction_pieces_are_corridor_cells():
    assert corridor_cell_pieces([FLANGE, WEB], plan_segments(DXF)) == [True, True]


def test_cut_symbol_drawn_over_slab_is_not_a_corridor_cell():
    # T solto sobre a laje: nenhuma linha continua seus lados.
    flange, web = _rect(2203.8, 2671, 2258.8, 2685), _rect(2226, 2641, 2236, 2671)
    segs = plan_segments({'lines': DXF['lines'], 'polylines': [{'points': flange}, {'points': web}]})
    assert not is_corridor_cell(flange, segs)
    assert not is_corridor_cell(web, segs)


def test_one_continued_wall_is_not_enough():
    piece = _rect(0, 0, 50, 19)
    segs = plan_segments({'lines': [{'start': (-100, 0), 'end': (0, 0)}], 'polylines': [{'points': piece}]})
    assert not is_corridor_cell(piece, segs)
