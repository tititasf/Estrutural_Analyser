from copy import deepcopy

from portal.app.preprocessamento.sa_levels import merge_sa_levels


def ring(x, y=0):
    return [[x,y],[x+20,y],[x+20,y+60],[x,y+60],[x,y]]


def item(identity, points, handle):
    return dict(item_id=identity, display_name="P77", item_class="pillar",
                geometry={"type":"Polygon", "coordinates":[points]},
                source_entity_handles=[handle], segments=[], levels=[
                    dict(item_id=identity, fact_id=identity+":"+field, field=field,
                         value=None, status="unknown", evidence_ids=[])
                    for field in ("base", "top")])


def fixture():
    true = ring(0)
    outside = ring(100)
    tower = dict(reference=dict(base=100., top=103., unit="m", datum_id="datum"),
                 items=[item("outside", outside, "region-handle"), item("true", true, "pillar-handle")])
    context = dict(evidence_id="current-cad-source", marks=[],
                   state=dict(pilares=[dict(name="P77", points=true, classification="INDETERMINADO")],
                              slabs=[], segmentos={}), tables={})
    return tower, context


def test_pillar_owner_is_its_contour_not_input_order_or_equal_name():
    tower, context = fixture()
    original = deepcopy(tower)
    for order in (tower["items"], list(reversed(tower["items"]))):
        tower["items"] = order
        result = merge_sa_levels(tower, context)
        by_id = {i["item_id"]:i for i in result["items"]}
        assert by_id["true"]["levels"][0]["value"] == 100.
        assert by_id["true"]["levels"][0]["method"] == "scoped_floor_convention"
        assert all(f["status"] == "unknown" for f in by_id["outside"]["levels"])
        assert by_id["outside"]["canonical_owner_item_id"] == "true"
    assert original["items"][0]["levels"][0]["status"] == "unknown"


def test_foreign_region_requires_same_contour_and_original_handle():
    tower, context = fixture()
    context["state"]["slabs"] = [dict(name="L88", nivel=None, points=ring(400),
        slab_steps=[dict(uid="source-step", points=ring(100), evidence_handles=["region-handle"])])]
    result = merge_sa_levels(tower, context)
    foreign = next(i for i in result["items"] if i["item_id"] == "outside")
    assert all(f["status"] == "not_applicable" for f in foreign["levels"])
    assert all(f["status"] == "unknown" for f in foreign["pre_sa_levels"])
    assert foreign["identity_role_proof"][0] == dict(role="slab_region", owner="L88",
                                                   source_entity_handles=["region-handle"])
    context["state"]["slabs"][0]["slab_steps"][0]["evidence_handles"] = ["another-handle"]
    result = merge_sa_levels(tower, context)
    foreign = next(i for i in result["items"] if i["item_id"] == "outside")
    assert all(f["status"] == "unknown" for f in foreign["levels"])


def test_identical_true_pillar_has_priority_over_foreign_role():
    tower, context = fixture()
    context["state"]["slabs"] = [dict(name="L88", nivel=None, points=ring(400),
        slab_steps=[dict(uid="source-step", points=ring(0), evidence_handles=["pillar-handle"])])]
    result = merge_sa_levels(tower, context)
    own = next(i for i in result["items"] if i["item_id"] == "true")
    assert "identity_role_proof" not in own
    assert own["levels"][0]["value"] == 100.


def test_dimensioned_section_role_never_transfers_levels_and_requires_source_proof():
    tower, context = fixture()
    record = dict(status="proved", consumer_authorized="source_role_only",
                  level_transfer_authorized=False, dimension_evidence_handles=["dimension"],
                  source_entity_handles=["region-handle"], original_points=ring(100))
    context["dimensioned_section_profiles"] = dict(records=[record])
    out = merge_sa_levels(tower, context)
    foreign = next(i for i in out["items"] if i["item_id"] == "outside")
    assert all(f["status"] == "not_applicable" and f["value"] is None for f in foreign["levels"])
    assert foreign["identity_role_proof"][0]["role"] == "slab_section_glyph"
    for field, value in [("source_entity_handles", ["other"]),
                         ("dimension_evidence_handles", []),
                         ("level_transfer_authorized", True),
                         ("original_points", ring(120))]:
        saved = record[field]
        record[field] = value
        out = merge_sa_levels(tower, context)
        foreign = next(i for i in out["items"] if i["item_id"] == "outside")
        assert all(f["status"] == "unknown" for f in foreign["levels"])
        record[field] = saved


def test_unmatched_and_ambiguous_pillar_geometries_remain_pending():
    tower, context = fixture()
    tower["items"].append(item("another-true",ring(0),"other-pillar-handle"))
    result=merge_sa_levels(tower,context)
    assert all(f["status"] == "unknown" for i in result["items"] for f in i["levels"])
    assert all(i["canonical_owner_item_id"] is None for i in result["items"])


def test_duplicate_survey_identity_unions_handles_only_for_equal_contours():
    from portal.app.preprocessamento.sa_levels import pillar_survey_geometry
    first = item("id",ring(100),"original-handle")
    duplicate = item("id",list(reversed(ring(100))),"copy-handle")
    result=pillar_survey_geometry([first,duplicate])
    assert result["id"]["source_entity_handles"] == ["copy-handle","original-handle"]
    assert first["source_entity_handles"] == ["original-handle"]
    collision=item("id",ring(120),"unrelated-handle")
    result=pillar_survey_geometry([first,collision,duplicate])
    assert result["id"]["geometry"] is None
    assert result["id"]["source_entity_handles"] == []


def test_role_reconciliation_preserves_history_without_unknown_gate_reintroduction():
    from portal.app.sa_development_gate import assess_cycle
    tower,context=fixture()
    context["state"]["slabs"]=[dict(name="L88",nivel=None,points=ring(400),
        slab_steps=[dict(uid="source-step",points=ring(100),evidence_handles=["region-handle"])])]
    result=merge_sa_levels(tower,context)
    foreign=next(i for i in result["items"] if i["item_id"]=="outside")
    package=dict(level_inventory=dict(items=[foreign]), levels=foreign["levels"],
                 pre_sa_survey_levels=tower["items"][0]["levels"])
    assessment=assess_cycle(package,{})
    assert not any(p["kind"] in {"level_pending","levels_incomplete"} for p in assessment["pending"])
    assert len(foreign["pre_sa_levels"])==2


def test_other_named_canonical_pillar_prevents_foreign_role_exclusion():
    from portal.app.preprocessamento.sa_levels import pillar_ownership
    tower,context=fixture()
    context["state"]["pilares"]=[dict(name="P88",points=ring(100))]
    context["state"]["slabs"]=[dict(name="L88",slab_steps=[
        dict(uid="source-step",points=ring(100),evidence_handles=["region-handle"])])]
    _,roles=pillar_ownership(tower["items"],context)
    assert "outside" not in roles


def test_circular_survey_remains_analytic_without_fabricated_polygon():
    from portal.app.preprocessamento.sa_levels import pillar_ownership, pillar_survey_geometry
    first=item("circle",ring(100),"circle-handle")
    first["geometry"]=dict(type="Circle",center=[100.,0.],radius=10.)
    duplicate=deepcopy(first);duplicate["source_entity_handles"]=["duplicate-circle-handle"]
    surveyed=pillar_survey_geometry([first,duplicate])
    assert surveyed["circle"]["geometry"] == first["geometry"]
    _,context=fixture()
    receivers,roles=pillar_ownership(list(surveyed.values()),context)
    assert receivers == {}
    assert roles == {}


def test_named_cut_role_requires_original_handle_and_exact_contour():
    from portal.app.preprocessamento.sa_levels import pillar_ownership
    tower, context = fixture()
    cut = dict(role='Cut_view_geom_auto', points=ring(100),
               source_entity_handles=['region-handle'], ficha=dict(beam_name='V412'))
    context['state']['slabs'] = [dict(name='L88', links=dict(
        laje_visao_corte=dict(cut_view_geom=[cut])))]
    _, roles = pillar_ownership(tower['items'], context)
    assert roles['outside'] == [dict(role='beam_section', owner='V412',
                                    source_entity_handles=['region-handle'])]
    for update in (dict(source_entity_handles=['other-handle']), dict(points=ring(101)),
                   dict(ficha={}), dict(role='unclassified')):
        original = deepcopy(cut)
        cut.update(update)
        _, roles = pillar_ownership(tower['items'], context)
        assert 'outside' not in roles
        cut.clear(); cut.update(original)


def test_extended_cut_retains_original_contour_proof():
    from portal.app.preprocessamento.sa_levels import pillar_ownership
    tower, context = fixture()
    cut = dict(role='Cut_view_geom_auto', points=ring(101), original_pts=ring(100),
               source_entity_handles=['region-handle'], ficha=dict(beam_name='V412'))
    context['state']['slabs'] = [dict(name='L88', links=dict(
        laje_visao_corte=dict(cut_view_geom=[cut])))]
    _, roles = pillar_ownership(tower['items'], context)
    assert roles['outside'][0]['owner'] == 'V412'
