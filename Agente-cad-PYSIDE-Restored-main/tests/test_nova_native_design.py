import json
import math
import sys
from pathlib import Path
import ezdxf
from ezdxf import bbox
from src.core.n5_pillar_frames import flatten_editable
from src.core.pillar_nova_design import apply_zone


def test_flatten_preserves_nested_geometry_layer_and_individual_lines():
    d=ezdxf.new();d.layers.new('red',dxfattribs={'color':1})
    b=d.blocks.new('part');b.add_lwpolyline([(0,0),(10,0),(10,5)],dxfattribs={'layer':'0','color':0})
    wrapper=d.blocks.new('sheet');wrapper.add_blockref('part',(20,30),dxfattribs={'layer':'0','color':0})
    d.modelspace().add_blockref('sheet',(100,200),dxfattribs={'layer':'red','color':3})
    before=bbox.extents(d.modelspace());flatten_editable(d);after=bbox.extents(d.modelspace())
    assert before.extmin.isclose(after.extmin) and before.extmax.isclose(after.extmax)
    assert [e.dxftype() for e in d.modelspace()]==['LINE','LINE']
    assert all(e.dxf.layer=='red' and e.dxf.color==3 for e in d.modelspace())
    assert not d.audit().errors


def test_special_cima_bolt_heads_point_back_to_the_rod_for_each_axis():
    """The normal-based rule covers rotations/mirrors used by L, T, and U."""
    from src.core.pillar_nova_special import bolt_head_angles

    for nx, ny in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        end1_angle, end0_angle = bolt_head_angles((nx, ny))
        end1_direction = (math.cos(end1_angle), math.sin(end1_angle))
        end0_direction = (math.cos(end0_angle), math.sin(end0_angle))

        # end1 is outside along the normal and end0 outside against it: each
        # asymmetric tip must face the shared shaft, not the free exterior.
        assert math.isclose(end1_direction[0] * nx + end1_direction[1] * ny, -1.0, abs_tol=1e-9)
        assert math.isclose(end0_direction[0] * nx + end0_direction[1] * ny, 1.0, abs_tol=1e-9)


def test_actual_zone_hook_and_ini_isolation():
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
    from scripts.gerar_pl_dxf_stog import setup_doc,generate_pilar_zone
    p=json.loads((root/'scripts/arete/relatorios/20261003_nova_portal_n5/production_n3/para/P28.json').read_text())
    d=setup_doc();generate_pilar_zone(d.modelspace(),p,'cima',visual_mode='NOVA')
    assert d._nova_design_revision=='approved_dynamic_v1'
    assert len([e for e in d.modelspace() if e.dxf.layer=='Madeira_textura'])>0
    assert len([e for e in d.modelspace() if e.dxf.layer=='Parafuso_detalhe'])>0
    old=setup_doc();generate_pilar_zone(old.modelspace(),p,'cima',visual_mode='INI')
    assert not hasattr(old,'_nova_design_revision')


def test_grade_omits_redundant_heights_preserves_recess_and_total():
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
    from scripts.gerar_pl_dxf_stog import setup_doc,generate_pilar_zone
    p=json.loads((root/'scripts/arete/relatorios/20261003_nova_portal_n5/production_n3/para/P28.json').read_text())
    d=setup_doc();generate_pilar_zone(d.modelspace(),p,'grades',visual_mode='NOVA')
    vertical=[e for e in d.modelspace().query('DIMENSION') if abs(e.dxf.defpoint2.x-e.dxf.defpoint3.x)<.001]
    assert sum(abs(e.get_measurement()-303.8)<.01 for e in vertical)==1
    assert sum(abs(e.get_measurement()-244.8)<.01 for e in vertical)==4
    for e in vertical:
        if abs(e.get_measurement()-244.8)<.01:assert e.dxf.defpoint.x<e.dxf.defpoint2.x
