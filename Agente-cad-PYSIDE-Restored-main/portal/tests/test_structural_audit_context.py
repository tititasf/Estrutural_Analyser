import base64
import hashlib
from io import BytesIO

import ezdxf
from PIL import Image, ImageChops

from portal.app import ficha_reader
from portal.app.structural_audit_context import capture


def test_deleted_highlight_keeps_same_cad_neighborhood(tmp_path, monkeypatch):
    source = tmp_path / 'structural.dxf'
    doc = ezdxf.new()
    cad = doc.modelspace()
    cad.add_lwpolyline([(-150,-100),(200,-100),(200,200),(-150,200)], close=True,
                      dxfattribs={'color':3})
    cad.add_text('P8  LAJE L323', dxfattribs={'insert':(-120,120),'height':15,'color':2})
    doc.saveas(source)
    before_bytes = source.read_bytes()
    monkeypatch.setattr(ficha_reader, '_fonte_estrutural_producao', lambda *a: source)
    monkeypatch.setattr(ficha_reader, 'ler_estado_pavimento', lambda *a: {})
    neighbor = dict(item_id='P8',titulo='P8',points=[[-150,-100],[-120,-100],[-120,-70]],campos={'nivel':852.19})
    monkeypatch.setattr(ficha_reader, 'listar_itens_n1', lambda state, cls: [neighbor] if cls=='pilares' else [])
    selected = dict(points=[[0,0],[19,0],[19,55],[0,55]])
    result=dict(action='delete',affected=[dict(classe='cortes_interpretados',item_id='target')],
                before=[selected],after=[])
    evidence=capture(tmp_path,'13_PAV',result)
    assert evidence['status']=='captured'
    assert evidence['source_sha256']==hashlib.sha256(before_bytes).hexdigest()
    assert source.read_bytes()==before_bytes
    assert evidence['nearby_items']==[dict(classe='pilares',**neighbor)]
    image=Image.open(BytesIO(base64.b64decode(evidence['png_base64'])))
    assert image.size==(evidence['width'],evidence['height'])
    left=image.crop((0,70,1000,920))
    right=image.crop((1000,70,2000,920))
    difference=ImageChops.difference(left,right)
    # Only the deleted contour changes; the CAD drawing and neighbors remain.
    changed=difference.getbbox()
    assert changed is not None
    x0,y0,x1,y1=evidence['bbox_dxf']
    assert changed[2]-changed[0] <= 19/(x1-x0)*1000+5
    assert changed[3]-changed[1] <= 55/(y1-y0)*850+5
    assert len(right.getcolors(maxcolors=1000000))>10
    image.save(tmp_path/'context.png')


def test_unavailable_context_is_explicit(tmp_path,monkeypatch):
    monkeypatch.setattr(ficha_reader,'_fonte_estrutural_producao',lambda *a:None)
    monkeypatch.setattr('portal.app.routers.viewer_routes.encontrar_estrutural_limpo',lambda *a:None)
    result=capture(tmp_path,'13_PAV',dict(before=[],after=[]))
    assert result['status']=='unavailable' and result['reason']
