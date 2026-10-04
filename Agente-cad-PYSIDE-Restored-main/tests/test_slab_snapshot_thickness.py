from src.core.preficha_segments import slab_height_cm, _slab_info


def test_canonical_thickness_survives_export_without_legacy_height():
    slab={'name':'L301','fields':{'laje_dim':'h=12','laje_nivel':'852.12'}}
    assert slab_height_cm(slab)=='12'
    assert _slab_info(slab)['height']=='12'


def test_decimal_thickness_and_legacy_records():
    assert slab_height_cm({'fields':{'laje_dim':'h=12,5'}})=='12.5'
    assert slab_height_cm({'height':'10'})=='10'
    assert slab_height_cm({'fields':{'laje_h':'11'}})=='11'
    assert slab_height_cm({})==''
