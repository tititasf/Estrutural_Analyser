import re

from scripts.arete.pil_l3_qa_microcycle import (
    _central_crossing_beam,
    _allowed_role_coexistence,
    _normalize_beam_dimensions,
    _rendered_pillar_bbox,
    _special_arrival_tip,
    _nearest_beam_contour_center,
    _special_connector_crossings,
    _special_pass_tip,
    _requested_corners,
    _special_l_segments,
    apply_explicit_missing_requests,
    apply_special_l_attention,
    enrich_special_l_faces,
    overlay_special_l_faces,
    validate_tables,
)
from scripts.arete.pil_agentic_highlight_draw import _segments_cross
from scripts.arete.pil_cruzamento_classes import comparar


def _row(name, corner, role):
    return {
        "familia": "viga", "nome": name, "dim": "19/55", "nivel": "852.19cm",
        "canto": corner, "papel": role, "raw": "", "dist_esq": "—", "dist_dir": "—",
    }


def _tables():
    return {
        "faces": {
            face: {"lajes": [], "passa": [], "chega": [], "interior": []}
            for face in "ABCD"
        },
        "orientation": "vertical",
    }


def test_attention_parser_ignores_portuguese_words_that_look_like_corners():
    note = (
        "falta viga chegas ac e bc corretamente e viga interior cc e "
        "viga passa ca, cb, de resto esta ok"
    )
    assert _requested_corners(note, "chega") == ["AC", "BC"]
    assert _requested_corners(note, "passa") == ["CA", "CB"]
    assert _requested_corners(note, "interior") == ["CC"]


def test_explicit_reciprocity_uses_same_beam_for_ac_bc_ca_cb():
    tables = _tables()
    tables["faces"]["C"]["passa"] = [_row("V302", "CB", "passa")]
    tables["faces"]["C"]["interior"] = [_row("V330", "CC", "interior")]
    beams = [{"name": "V302", "dim": "19/55"}, {"name": "V330", "dim": "19/55"}]
    note = "falta viga chegas ac e bc e viga interior cc e viga passa ca, cb"
    apply_explicit_missing_requests(tables, beams, note, "852.19cm")
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["A"]["chega"]} == {("V302", "AC")}
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["B"]["chega"]} == {("V302", "BC")}
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["C"]["passa"]} == {
        ("V302", "CA"), ("V302", "CB")
    }
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["C"]["interior"]} == {("V330", "CC")}


def test_explicit_role_correction_prefers_same_corner_over_unrelated_same_role():
    tables = _tables()
    tables["faces"]["A"]["passa"] = [_row("V330", "AD", "passa")]
    tables["faces"]["A"]["chega"] = [_row("V301", "AC", "chega")]
    beams = [{"name": "V301", "dim": "19/120"}, {"name": "V330", "dim": "19/120"}]
    apply_explicit_missing_requests(tables, beams, "falta viga passa AC", "852.19cm")
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["A"]["passa"]} == {
        ("V330", "AD"), ("V301", "AC")
    }
    assert tables["faces"]["A"]["chega"] == []


def test_explicit_addition_preserves_role_named_after_sem_remover_despite_typos():
    tables = _tables()
    tables["faces"]["A"]["passa"] = [
        _row("V330", "AD", "passa"), _row("V301", "AC", "passa")
    ]
    beams = [{"name": "V301", "dim": "19/120"}, {"name": "V330", "dim": "19/120"}]
    note = (
        "ainda nao adicionou a viga chaega AC sem remvover a viga passa ac "
        "e todas demais coisas, mantendo integridade do resto"
    )
    apply_explicit_missing_requests(tables, beams, note, "852.19cm")
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["A"]["passa"]} == {
        ("V330", "AD"), ("V301", "AC")
    }
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["A"]["chega"]} == {
        ("V301", "AC")
    }
    allowed = _allowed_role_coexistence(tables, note)
    assert allowed == {("A", "V301", "AC")}
    assert validate_tables(tables, allowed) == []


def test_same_beam_uses_canonical_dimension_on_every_face():
    tables = _tables()
    tables["faces"]["C"]["passa"] = [
        _row("V329", "CA", "passa"), _row("V329", "CB", "passa")
    ]
    tables["faces"]["C"]["passa"][0]["dim"] = "19/60"
    tables["faces"]["C"]["passa"][1]["dim"] = "19/55"
    changed = _normalize_beam_dimensions(tables, [{"name": "V329", "dim": "19/60"}])
    assert {row["dim"] for row in tables["faces"]["C"]["passa"]} == {"19/60"}
    assert changed == ["C.passa V329: 19/55→19/60"]


def test_cross_class_comparison_counts_special_faces_e_and_f():
    tables = _tables()
    tables["faces"]["E"] = {"passa": [], "chega": [_row("V327", "ED", "chega")], "interior": []}
    tables["faces"]["F"] = {"passa": [_row("V305", "FD", "passa")], "chega": [], "interior": []}
    cross = {
        "toca": [{"viga": "V327", "papel": "contorno encosta no pilar (gap 0)"}],
        "passa": [{"viga": "V305"}],
    }
    assert comparar(cross, tables) == []


def test_special_l_segment_mapping_has_six_physical_faces_for_both_mirrors():
    p26 = [[3936, 2242], [4101, 2242], [4101, 2261], [3955, 2261], [3955, 2460], [3936, 2460], [3936, 2242]]
    p27 = [[4552, 2242], [4552, 2460], [4533, 2460], [4533, 2261], [4387, 2261], [4387, 2242], [4552, 2242]]
    for points in (p26, p27):
        faces = _special_l_segments(points)
        assert set(faces) == set("ABCDEF")
        assert faces["A"]["vertical"] and faces["B"]["vertical"]
        assert not faces["E"]["vertical"] and not faces["F"]["vertical"]
        assert faces["C"]["length"] == 19
        assert faces["D"]["length"] == 19


def test_special_arrival_point_is_centered_in_incoming_beam_width():
    points = [[3936, 2242], [4101, 2242], [4101, 2261], [3955, 2261],
              [3955, 2460], [3936, 2460], [3936, 2242]]
    segments = _special_l_segments(points)
    horizontal = {
        "name": "V304", "is_h": True,
        "points": [[3807, 2429], [4601, 2429], [4601, 2453], [3807, 2453]],
    }
    vertical = {
        "name": "V323", "is_h": False,
        "points": [[3909, 1963], [3934, 1963], [3934, 2242], [3909, 2242]],
    }
    assert _special_arrival_tip(segments["A"], "AC", segments, horizontal) == (3936.0, 2441.0)
    assert _special_arrival_tip(segments["E"], "EA", segments, vertical) == (3921.5, 2242.0)


def test_special_arrival_uses_effective_segment_center_for_a_and_b():
    contours = [
        {"x0": 3807.3825, "x1": 3936.3825, "y0": 2422.038, "y1": 2441.038},
        {"x0": 4552.3825, "x1": 4601.3825, "y0": 2422.038, "y1": 2441.038},
    ]
    expected_y = 2431.538
    assert _nearest_beam_contour_center(
        contours, (4533.3825, 2441.038), horizontal=True
    ) == (4533.3825, expected_y)
    assert _nearest_beam_contour_center(
        contours, (4552.3825, 2441.038), horizontal=True
    ) == (4552.3825, expected_y)


def test_special_pass_point_is_exactly_on_shared_corner():
    points = [[3936, 2242], [4101, 2242], [4101, 2261], [3955, 2261],
              [3955, 2460], [3936, 2460], [3936, 2242]]
    segments = _special_l_segments(points)
    assert _special_pass_tip("CA", segments) == (3936.0, 2460.0)
    assert _special_pass_tip("CB", segments) == (3955.0, 2460.0)
    assert _special_pass_tip("ED", segments) == (4101.0, 2242.0)
    assert _special_pass_tip("FD", segments) == (4101.0, 2261.0)


def test_central_crossing_beam_prefers_perpendicular_geometry_at_pillar_center():
    pillar = {
        "orientation": "horizontal",
        "points": [[0, 0], [50, 0], [50, 19], [0, 19], [0, 0]],
    }
    axial = {
        "name": "V301",
        "is_h": True,
        "points": [[-100, 0], [100, 0], [100, 19], [-100, 19], [-100, 0]],
    }
    crossing = {
        "name": "V312",
        "is_h": False,
        "points": [[20, -100], [30, -100], [30, 100], [20, 100], [20, -100]],
    }
    assert _central_crossing_beam([axial, crossing], pillar)["name"] == "V312"


def test_special_l_materializes_six_faces_and_full_ef_tag_semantics():
    points = [[3936, 2242], [4101, 2242], [4101, 2261], [3955, 2261],
              [3955, 2460], [3936, 2460], [3936, 2242]]
    tables = _tables()
    special = {
        "format": "Em L",
        "sides": {
            "E": {"l1_n": "L325", "v_passa_esq_n": "V305", "v_passa_dir_n": "V305"},
            "F": {"l1_n": "L325", "v_passa_esq_n": "V305", "v_passa_dir_n": "V305"},
        },
    }
    actions = enrich_special_l_faces(
        tables, special, {"L325": "12"}, {"L325": "859.12"},
        points=points, beams=[{"name": "V305", "dim": "19/55"}],
        nivel_viga="852.19cm",
    )
    assert tables["geometry_type"] == "L_special_6_faces"
    assert tables["face_ids"] == list("ABCDEF")
    assert set(tables["face_geometry"]) == set("ABCDEF")
    assert {row["canto"] for row in tables["faces"]["E"]["passa"]} == {"EA", "ED"}
    assert {row["canto"] for row in tables["faces"]["F"]["passa"]} == {"FB", "FD"}
    assert {row["dim"] for row in tables["faces"]["E"]["passa"]} == {"19/55"}
    assert any("A–F" in action for action in actions)

    rendered = overlay_special_l_faces('<svg viewBox="0 0 351 360"></svg>', points, tables)
    assert rendered.count('data-special-face=') == 6
    assert "E.V.passa EA" in rendered
    assert "F.V.passa FB" in rendered
    assert "MOTOR A–F ATIVO" in rendered
    assert 'marker-end="url(#pil-special-arrow-E)"' in rendered
    assert 'stroke="none"' in rendered
    assert 'r="0.8"' in rendered
    assert 'font-size="0.682' in rendered
    connector_values = re.findall(
        r'<line x1="([\d.-]+)" y1="([\d.-]+)" x2="([\d.-]+)" y2="([\d.-]+)" '
        r'stroke="#[0-9a-f]+" stroke-width="0\.32" marker-end=',
        rendered,
    )
    connectors = [
        ((float(x1), float(y1)), (float(x2), float(y2)))
        for x1, y1, x2, y2 in connector_values
    ]
    assert all(
        not _segments_cross(*connectors[i], *connectors[j])
        for i in range(len(connectors)) for j in range(i + 1, len(connectors))
    )
    assert _special_connector_crossings(rendered) == []


def test_special_connector_crossing_is_a_machine_readable_visual_gate():
    svg = (
        '<svg><line x1="0" y1="0" x2="10" y2="10" stroke="#ff8a65" '
        'stroke-width="0.32" marker-end="x"/>'
        '<line x1="0" y1="10" x2="10" y2="0" stroke="#80cbc4" '
        'stroke-width="0.32" marker-end="y"/></svg>'
    )
    assert _special_connector_crossings(svg) == [(0, 1)]


def test_special_overlay_uses_rendered_pillar_polygon_as_exact_transform_anchor():
    points = [[3936, 2242], [4101, 2242], [4101, 2261], [3955, 2261],
              [3955, 2460], [3936, 2460], [3936, 2242]]
    tables = _tables()
    tables["geometry_type"] = "L_special_6_faces"
    tables["faces"].update({
        face: {"lajes": [], "passa": [], "chega": [], "interior": []}
        for face in "EF"
    })
    base = (
        '<svg viewBox="0 0 100 100"><path d="M 90 80 L 90 20 L 80 20 '
        'L 80 70 L 10 70 L 10 80 z" '
        'style="fill: #ff1744; opacity: 0.12"/></svg>'
    )
    assert _rendered_pillar_bbox(base) == (10.0, 20.0, 90.0, 80.0)
    rendered = overlay_special_l_faces(base, points, tables)
    assert '<line x1="10.00" y1="80.00" x2="90.00" y2="80.00"' in rendered


def test_special_l_attention_rebuilds_only_declared_faces_from_geometry():
    points = [[3936, 2242], [4101, 2242], [4101, 2261], [3955, 2261],
              [3955, 2460], [3936, 2460], [3936, 2242]]
    tables = _tables()
    enrich_special_l_faces(
        tables,
        {"format": "Em L", "sides": {
            "E": {"l1_n": "L325", "v_passa_esq_n": "V305", "v_passa_dir_n": "V305"},
            "F": {"l1_n": "L325", "v_passa_esq_n": "V305", "v_passa_dir_n": "V305"},
        }},
        {"L325": "12"}, {"L325": "859.12"}, points=points,
        beams=[{"name": "V305", "dim": "19/55", "is_h": True,
                "points": [[4101, 2230], [4387, 2230], [4387, 2254], [4101, 2254]]}],
        nivel_viga="852.19cm",
    )
    tables["faces"]["B"]["chega"] = [_row("V305", "BD", "chega"), _row("V304", "BC", "chega")]
    tables["faces"]["D"]["chega"] = [_row("V323", "DA", "chega")]
    tables["faces"]["A"]["lajes"] = [{"nome": "L325", "canto": "AD"}]
    beams = [
        {"name": "V304", "dim": "19/50", "is_h": True,
         "points": [[3807, 2429], [4601, 2429], [4601, 2453], [3807, 2453]]},
        {"name": "V305", "dim": "19/55", "is_h": True,
         "points": [[4101, 2230], [4387, 2230], [4387, 2254], [4101, 2254]]},
        {"name": "V323", "dim": "19/50", "is_h": False,
         "points": [[3909, 1963], [3934, 1963], [3934, 2242], [3909, 2242]]},
    ]
    note = (
        "para lado A a viga que chega AC; para lado E tem viga que chega EA, "
        "e nao tem laje, e tem viga passa ED. os atuais do E ta confuso e errado. "
        "D e somente viga interior. F nesse caso so viga passa FD, B so viga chega BC"
    )
    apply_special_l_attention(tables, beams, points, note, "852.19cm")
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["B"]["chega"]} == {("V304", "BC")}
    assert [row["nome"] for row in tables["faces"]["A"]["lajes"]] == ["L325"]
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["D"]["interior"]} == {("V305", "DD")}
    assert tables["faces"]["D"]["passa"] == []
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["E"]["chega"]} == {("V323", "EA")}
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["E"]["passa"]} == {("V305", "ED")}
    assert tables["faces"]["E"]["lajes"] == []
    assert {(r["nome"], r["canto"]) for r in tables["faces"]["F"]["passa"]} == {("V305", "FD")}
    assert tables["faces"]["F"]["lajes"] == []
