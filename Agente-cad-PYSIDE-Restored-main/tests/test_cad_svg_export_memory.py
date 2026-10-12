import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from src.core.cad_render_cache import visible_cad_strokes
from scripts.arete.export_pilares_abcd_fichas import _write_spooled_svg, _read_spooled_svg

def test_view_culling_preserves_boundary_pixels_order_and_cache():
    fig,ax=plt.subplots(figsize=(4,4),dpi=100)
    segments=[((-100,0),(100,0)),((0,-100),(0,100)),((1.999,-2),(1.999,2)),((2.01,-2),(2.01,2)),((30,30),(31,31))]
    collection=LineCollection(segments,linewidths=5,color='#ff00ff80')
    ax.add_collection(collection);ax.set_xlim(-2,2);ax.set_ylim(-2,2)
    fig.canvas.draw();before=np.asarray(fig.canvas.buffer_rgba()).copy();original=collection.get_paths()
    with visible_cad_strokes(ax):
        assert len(collection.get_paths())==4
        fig.canvas.draw();after=np.asarray(fig.canvas.buffer_rgba()).copy()
    assert collection.get_paths() is original
    np.testing.assert_array_equal(before,after)
    plt.close(fig)

def test_spooled_svg_roundtrip_does_not_send_svg_in_future(tmp_path):
    source='<svg>'+('á &amp; geometry\n'*100000)+'</svg>'
    receipt=_write_spooled_svg(tmp_path,source)
    assert len(receipt)<300
    assert _read_spooled_svg(receipt)==source
    assert not list(tmp_path.iterdir())

def test_worker_limit_respects_service_budget_without_root_controller(monkeypatch):
    from pathlib import Path
    from src.core.cad_render_cache import render_worker_limit
    gig = 1024**3
    content = {
        '/proc/meminfo': 'MemAvailable: 64000000 kB\n',
        '/proc/self/cgroup': '0::/system.slice/cad-portal.service\n',
        '/sys/fs/cgroup/system.slice/cad-portal.service/memory.max': str(5*gig),
        '/sys/fs/cgroup/system.slice/cad-portal.service/memory.current': str(2*gig),
        '/sys/fs/cgroup/system.slice/memory.max': 'max',
    }
    def read(path, *args, **kwargs):
        key = path.as_posix()
        if key not in content:
            raise FileNotFoundError(str(path))
        return content[key]
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr('os.sched_getaffinity', lambda _: set(range(8)), raising=False)
    assert render_worker_limit(8, 21) == 2

def test_publication_space_guard_preserves_existing_asset(monkeypatch,tmp_path):
    import shutil
    import pytest
    from scripts.arete.export_pilares_abcd_fichas import _write_publication_text
    target=tmp_path/'asset.svg'
    target.write_text('old',encoding='utf-8')
    monkeypatch.setattr(shutil,'disk_usage',lambda _: type('Usage',(),{'free':0})())
    with pytest.raises(RuntimeError,match='Sem espaço'):
        _write_publication_text(target,'new')
    assert target.read_text(encoding='utf-8') == 'old'
    assert len(list(tmp_path.iterdir())) == 1
    monkeypatch.setattr(shutil,'disk_usage',lambda _: type('Usage',(),{'free':1024**3})())
    _write_publication_text(target,'geometria á')
    assert target.read_text(encoding='utf-8') == 'geometria á'
    assert len(list(tmp_path.iterdir())) == 1
