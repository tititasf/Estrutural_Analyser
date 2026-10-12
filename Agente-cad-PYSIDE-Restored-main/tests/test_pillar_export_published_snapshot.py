import json
import pytest
from scripts.arete.export_pilares_abcd_fichas import _published_pillars


def test_readonly_sa_replaces_stale_db_geometry_without_losing_circle(tmp_path):
    stale = [dict(name='P5', points=[[0, 0], [71, 0], [71, 15], [0, 15]], type='legacy')]
    points = [[0, 0], [19, 0], [19, 170], [0, 170]]
    rows = [dict(name='P5', points=points, orientation='Vertical', lajes=[]),
            dict(name='P21', points=[[0, 1], [1, 0], [0, -1]],
                 circular_geometry=dict(diameter=60))]
    snapshot = tmp_path / 'state.json'
    snapshot.write_text(json.dumps(dict(pilares=rows)))
    result = _published_pillars(stale, snapshot)
    assert result[0]['points'] == points and result[0]['orientation'] == 'Vertical'
    assert result[0]['type'] == 'legacy' and result[1]['circular_geometry']['diameter'] == 60
    assert stale[0]['points'] != points


def test_invalid_snapshot_cannot_silently_export_stale_db_contours(tmp_path):
    snapshot = tmp_path / 'state.json'
    for rows in ([], [dict(name='P1', points=[])],
                 [dict(name='P1', points=[[0, 0]] * 3)] * 2):
        snapshot.write_text(json.dumps(dict(pilares=rows)))
        with pytest.raises(ValueError):
            _published_pillars([], snapshot)
