import os
from pathlib import Path
from unittest.mock import patch
import ezdxf
import matplotlib
matplotlib.use("Agg")
import pytest
from src.core.cad_render_cache import prepared_cad_canvas, close_cached_canvas, render_worker_limit


def drawing(path, end=10):
    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (end, end))
    doc.saveas(path)


def test_reuse_removes_view_artists_and_invalidates_revision(tmp_path):
    path = tmp_path / "drawing.dxf"
    drawing(path)
    try:
        with prepared_cad_canvas(path, 900, 640, 140) as (fig, ax):
            first = fig
            children = len(ax.get_children())
            ax.text(10, 10, "only this view")
        with prepared_cad_canvas(path, 900, 640, 140) as (fig, ax):
            assert fig is first
            assert len(ax.get_children()) == children
        with pytest.raises(RuntimeError):
            with prepared_cad_canvas(path, 900, 640, 140) as (_, ax):
                ax.text(1, 1, "failed view")
                raise RuntimeError("save failure")
        with prepared_cad_canvas(path, 900, 640, 140) as (_, ax):
            assert len(ax.get_children()) == children
        drawing(path, 200)
        with prepared_cad_canvas(path, 900, 640, 140) as (fig, _):
            assert fig is not first
            changed = fig
        with prepared_cad_canvas(path, 1000, 640, 140) as (fig, _):
            assert fig is not changed
    finally:
        close_cached_canvas()


def test_worker_limit_respects_cpu_memory_and_items():
    with patch("src.core.cad_render_cache.os.sched_getaffinity", return_value={0, 1, 2, 3}, create=True), patch("src.core.cad_render_cache.Path.read_text", return_value="MemAvailable: 1048576 kB"):
        assert render_worker_limit(20, 40) == 1
    with patch("src.core.cad_render_cache.os.sched_getaffinity", return_value={0, 1, 2, 3}, create=True), patch("src.core.cad_render_cache.Path.read_text", return_value="MemAvailable: 8388608 kB"):
        assert render_worker_limit(20, 40) == 4
        assert render_worker_limit(3, 2) == 2


def test_view_camera_does_not_resize_next_cached_figure(tmp_path):
    path = tmp_path / 'drawing.dxf'
    drawing(path)
    try:
        with prepared_cad_canvas(path,900,640,140) as (fig,ax):
            original = tuple(fig.get_size_inches())
            original_position = ax.get_position().bounds
            fig.set_size_inches(900/140,640/140,forward=True)
            ax.set_position([0,0,1,1])
        with prepared_cad_canvas(path,900,640,140) as (fig,ax):
            assert tuple(fig.get_size_inches()) == original
            assert ax.get_position().bounds == original_position
    finally:
        close_cached_canvas()


def test_svg_parity_across_different_viewports(tmp_path):
    import re
    import xml.etree.ElementTree as ET
    from scripts.arete.export_pilares_abcd_fichas import _render_n1_svg
    import src.core.cad_render_cache as cache_module
    original_canvas = cache_module.prepared_cad_canvas
    def fresh_canvas(*args, **kwargs):
        return original_canvas(*args, **kwargs, reuse=False)
    def normalized(svg):
        node = ET.fromstring(svg)
        for parent in node.iter():
            for child in list(parent):
                if child.tag.rsplit("}", 1)[-1] == "metadata":
                    parent.remove(child)
        ids = {n.attrib["id"]: "id"+str(i) for i, n in enumerate(node.iter()) if "id" in n.attrib}
        for n in node.iter():
            for k,v in list(n.attrib.items()):
                if k == "id": n.attrib[k]=ids[v]
                else:
                    v=re.sub(r"url\(#([^)]*)\)",lambda m:"url(#"+ids.get(m[1],m[1])+")",v)
                    if v.startswith("#") and v[1:] in ids:v="#"+ids[v[1:]]
                    n.attrib[k]=v
        return ET.canonicalize(ET.tostring(node,encoding="unicode"))
    path=tmp_path/"scene.dxf"
    doc=ezdxf.new()
    doc.modelspace().add_line((-200,-300),(400,500))
    doc.modelspace().add_circle((25,25),10)
    doc.modelspace().add_text("CAD annotation",dxfattribs={"height":5,"insert":(15,15)})
    doc.saveas(path)
    try:
        cases = [(pts, view) for pts in [[[0,0],[10,0],[10,20],[0,20]],[[200,100],[230,100],[230,105],[200,105]]] for view in ["near","far"]]
        cached = [normalized(_render_n1_svg(path,pts,context_view=view)) for pts,view in cases]
        with patch("src.core.cad_render_cache.prepared_cad_canvas", fresh_canvas):
            fresh = [normalized(_render_n1_svg(path,pts,context_view=view)) for pts,view in cases]
        assert cached == fresh
    finally:
        close_cached_canvas()


def test_tagged_and_plain_views_share_bounded_backgrounds_without_contamination(tmp_path):
    import re
    from scripts.arete.export_pilares_abcd_fichas import _render_n1_svg
    from scripts.arete.pil_agentic_highlight_draw import render_agentic_svg
    import src.core.cad_render_cache as cache_module
    original_canvas = cache_module.prepared_cad_canvas
    def fresh_canvas(*args, **kwargs):
        return original_canvas(*args, **kwargs, reuse=False)
    path = tmp_path/'tagged.dxf'
    doc = ezdxf.new()
    doc.modelspace().add_line((-500, -400), (600, 800))
    doc.modelspace().add_text('Context', dxfattribs={'insert': (15, 20), 'height': 6})
    doc.saveas(path)
    points = [[[0,0],[30,0],[30,50],[0,50]], [[100,100],[110,100],[110,170],[100,170]]]
    def render_all():
        result = []
        for pts in points + points:
            for svg in (_render_n1_svg(path,pts,context_view='near'),
                        _render_n1_svg(path,pts,context_view='far'),
                        render_agentic_svg(path,pts,{})):
                result.append(re.sub(r'<dc:date>.*?</dc:date>', '', svg))
        return result
    try:
        with matplotlib.rc_context({'svg.hashsalt': 'parity'}):
            with patch('ezdxf.readfile', wraps=ezdxf.readfile) as reader:
                cached = render_all()
                assert reader.call_count == 2
                assert len(cache_module._canvases) == 2
            with patch('src.core.cad_render_cache.prepared_cad_canvas', fresh_canvas):
                fresh = render_all()
        assert cached == fresh
    finally:
        close_cached_canvas()
