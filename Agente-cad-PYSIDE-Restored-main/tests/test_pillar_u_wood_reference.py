"""Approved U timber texture retains the baked INSERT orientation."""
import importlib.util
from pathlib import Path
from collections import Counter
import pytest
import ezdxf,io
from ezdxf import bbox
from ezdxf.lldxf.tagwriter import TagCollector
from src.core.pillar_nova_special import Drawing
from src.core.pillar_u_nova_contract import u_nova_payload

U=[(0,0),(220,0),(220,240),(190,240),(190,30),(30,30),(30,240),(0,240)]

def centered(parts):
    bounds=bbox.extents(parts)
    out=[]
    for original in parts:
        e=original.copy();e.translate(-bounds.center.x,-bounds.center.y,0)
        out.append(tuple((t.code,round(t.value,6) if isinstance(t.value,float) else
                         tuple(round(v,6) for v in t.value) if isinstance(t.value,tuple) else t.value)
                         for t in TagCollector.dxftags(e)
                         if t.code not in {5,8,105,330,360,6,62,370,420,430,440} and t.code<1000))
    return Counter(out)

@pytest.mark.parametrize('asset',['PONTALETE','MEIO PONTALETE'])
def test_u_asset_matches_approved_insert_before_scaling(asset):
    root=Path(__file__).resolve().parents[1]
    path=root/'scripts/arete/relatorios/20261002_nova_design/special_cima_contour_preview.py'
    spec=importlib.util.spec_from_file_location('u_approved_wood',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    approved=module.Drawing({'geometry_points':U})
    current=Drawing(u_nova_payload({'geometry_points':U}))
    assert centered(approved.templates[asset])==centered(current.templates[asset])
    assert tuple(bbox.extents(approved.templates[asset]).size)==pytest.approx(tuple(bbox.extents(current.templates[asset]).size))

def test_legacy_payload_keeps_raw_asset_orientation():
    drawing=Drawing({'geometry_points':[(0,0),(100,0),(100,30),(30,30),(30,120),(0,120)]})
    size=bbox.extents(drawing.templates['MEIO PONTALETE']).size
    assert size.y>size.x

def test_full_u_timber_texture_matches_immutable_approved_drawing():
    root=Path(__file__).resolve().parents[1]
    approved=ezdxf.readfile(root/'scripts/arete/relatorios/20261002_nova_design/preview_UT_contour/U_v10/CIMA.dxf')
    current=Drawing(u_nova_payload({'geometry_points':U})).generate()
    stream=io.StringIO();current.write(stream);stream.seek(0);current=ezdxf.read(stream)
    old=[e for e in approved.modelspace() if e.dxf.layer=='Madeira_textura']
    new=[e for e in current.modelspace() if e.dxf.layer=='Madeira_textura']
    assert len(old)==len(new)==336
    assert centered(old)==centered(new)
