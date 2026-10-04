"""Adapter integration without starting Qt or a drawing subprocess."""
import ast
import json
import sys
from pathlib import Path

from src.core.fv_generation_contract import build_fv_generation_contract


def test_n3_uses_manual_sidecar_and_floor_metadata_not_pid_filename(tmp_path):
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root/'scripts/arete/headless_sa_analise.py').read_text(encoding='utf-8-sig'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == '_generate_fv_n3_nova_previews')
    ns = {'Path': Path, 'json': json, 'sys': sys, '_REPO_ROOT': root,
          '_run_n3_subprocess_tasks': lambda tasks, **kwargs: ([], [])}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<adapter>', 'exec'), ns)
    obra = tmp_path/'obra'
    sidecar = obra/'.portal_overrides/geometry/13_PAV.json'
    sidecar.parent.mkdir(parents=True)
    points = [[0,22.3],[21.1,0],[255.7,0],[248.2,19],[29.3,19],[13.8,35.4],[0,22.3]]
    sidecar.write_text(json.dumps({'edits': {'fundo': {'test-uid': {
        'points': points, 'length': 234.627, 'width': 20.518}}}}))
    state_path = tmp_path/'html_fichas/estado_13_PAV_item_V987_pid123.json'
    state_path.parent.mkdir()
    state = {'pavimento': '13_PAV', 'segmentos': {'fundo': [{
        'uid':'test-uid', 'beam_name':'V987', 'segment_label':'1',
        'points': [[0,0],[192,0],[192,178],[0,178]], 'length':192, 'width':178}]}}
    state_path.write_text(json.dumps(state))
    original = state_path.read_bytes()
    output = tmp_path/'n3/dxf'
    ns['_generate_fv_n3_nova_previews'](obra, [{'viga_nome':'V987',
        'segmentos_fundo':[{'length':192, 'dim_width':178}]}], output, state_path=state_path)
    actual = json.loads((output.parent/'contracts/V987_fundo.json').read_text())
    expected = build_fv_generation_contract('V987', {'segmentos_fundo': [{
        'length':234.627,'dim_width':20.518,'geometry':points}]})
    assert actual['segments_rich'][0]['panels'] == expected['segments_rich'][0]['panels']
    assert state_path.read_bytes() == original
