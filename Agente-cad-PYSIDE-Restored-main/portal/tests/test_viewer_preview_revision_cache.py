from pathlib import Path
import json
import ezdxf
from starlette.requests import Request
from portal.app import dxf_preview as dp


def test_extent_cache_reuses_revision_and_invalidates_changed_dxf(tmp_path, monkeypatch):
    path = tmp_path / 'structural.dxf'
    doc = ezdxf.new(); doc.modelspace().add_line((0, 0), (10, 20)); doc.saveas(path)
    dp._bbox_dxf_revision.cache_clear()
    original = ezdxf.readfile
    reads = []
    def read(p):
        reads.append(p)
        return original(p)
    monkeypatch.setattr(ezdxf, 'readfile', read)
    assert dp.obter_bbox_dxf(path) == (0, 0, 10, 20)
    assert dp.obter_bbox_dxf(path) == (0, 0, 10, 20)
    assert len(reads) == 1
    doc.modelspace().add_line((-25, -5), (30, 45)); doc.saveas(path)
    assert dp.obter_bbox_dxf(path) == (-25, -5, 30, 45)
    assert len(reads) == 2


def test_transform_only_reads_metadata_without_opening_svg(tmp_path, monkeypatch):
    path = tmp_path / 'structural.dxf'; path.write_text('revision')
    bbox = (1., 2., 11., 22.)
    key = dp._hash_cache(path, bbox, .08, (640, 480))
    svg = tmp_path / (key + '.svg'); svg.write_bytes(b'<svg/>')
    (tmp_path / (key + '.transform.json')).write_text(json.dumps({
        'bbox_dxf': bbox, 'largura_px': 640, 'altura_px': 480}))
    original = Path.read_bytes
    def read(p):
        if p == svg:
            raise AssertionError('Metadata endpoint opened the SVG')
        return original(p)
    monkeypatch.setattr(Path, 'read_bytes', read)
    result = dp.renderizar_dxf_svg_com_transform_cacheado(path, tmp_path, bbox=bbox, incluir_svg=False)
    assert result.svg == b''
    assert result.bbox_dxf == bbox
    assert result.px_para_dxf(320, 240) == (6, 12)


def test_tower_response_revalidates_and_never_serves_stale_revision(tmp_path, monkeypatch):
    from portal.app.routers import recortes_routes as routes
    source = tmp_path / 'tower.dxf'; source.write_text('version one')
    monkeypatch.setattr(routes, '_obra_do_membro', lambda *args: {})
    monkeypatch.setattr(routes, '_obra_dir', lambda *args: tmp_path)
    monkeypatch.setattr(routes.torre_crop, 'obter_recorte_bruto', lambda *args: {'path': str(source)})
    rendered=[]
    def render(*args):
        rendered.append(1)
        return b'<svg/>'
    monkeypatch.setattr(dp, 'renderizar_dxf_completo_cacheado', render)
    def request(etag=''):
        return Request({'type':'http', 'headers':[(b'if-none-match',etag.encode())]})
    def call(req):
        return routes.foto_torre_endpoint('obra','raw','torre_1',req,{},None)
    first=call(request()); assert first.status_code==200
    tag=first.headers['etag']
    cached=call(request('W/'+tag)); assert cached.status_code==304
    assert len(rendered)==1
    source.write_text('version two, with geometry change')
    changed=call(request(tag)); assert changed.status_code==200
    assert changed.headers['etag']!=tag
    assert len(rendered)==2
