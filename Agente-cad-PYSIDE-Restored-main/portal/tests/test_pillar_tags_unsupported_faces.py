import json
import math
from pathlib import Path
from portal.app import pipeline_runner


def test_tags_do_not_draw_bbox_faces_for_u_or_circle_or_block_rectangles(settings, tmp_path, monkeypatch):
    settings.repo_root = tmp_path / 'repo'
    script = settings.repo_root / 'scripts/arete/export_pilares_abcd_fichas.py'
    script.parent.mkdir(parents=True)
    script.write_text('# exporter fixture')
    root = tmp_path / 'obra'
    root.mkdir()
    u = [[0,0],[100,0],[100,20],[20,20],[20,180],[100,180],[100,200],[0,200]]
    circle = [[30*math.cos(i*math.pi/16),30*math.sin(i*math.pi/16)] for i in range(32)]
    (root / 'estado_TERREO.json').write_text(json.dumps(dict(pilares=[
        dict(name='P1', points=[[0,0],[19,0],[19,170],[0,170]]),
        dict(name='P12', points=u), dict(name='P21', points=circle)])))
    def render(cmd, **kwargs):
        assert cmd[cmd.index('--item')+1:] == ['P1']
        assert Path(cmd[cmd.index('--snapshot-path')+1]) == root / 'estado_TERREO.json'
        pack = Path(cmd[cmd.index('--output-root')+1]) / 'obra/TERREO_fixture_pilares_abcd'
        (pack / 'propostas').mkdir(parents=True)
        (pack / 'propostas/P1_sa_motor.svg').write_text('<svg/>')
        return pipeline_runner.subprocess.CompletedProcess(cmd,0,'','')
    monkeypatch.setattr(pipeline_runner, 'python_sa_executable', lambda *a:'python')
    monkeypatch.setattr(pipeline_runner.subprocess,'run',render)
    result = pipeline_runner.materializar_n1_tags_pilares(
        settings,dict(nome='obra',local_path=str(root)),project_id='p',pavimento='TERREO')
    assert result['gerados'] == 1 and result['missing'] == []
    assert len(result['item_pending']) == 2
    assert all('faces físicas' in row for row in result['item_pending'])
    assert [row['name'] for row in json.loads((root/'estado_TERREO.json').read_text())['pilares']] == ['P1','P12','P21']
