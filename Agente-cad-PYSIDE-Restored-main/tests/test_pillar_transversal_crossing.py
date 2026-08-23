"""Viga perpendicular que atravessa a face é chegada, não passagem.

O teste de contato por parede só reconhece viga paralela à face. Uma viga
perpendicular que cruza a face não alinha parede nenhuma e, quando também não
cobre o pilar inteiro, ficava fora da tabela (V312 em P42, V316 em P44).
"""
from src.core.pillar_face_beams import apply_transversal_crossing_arrivals


def _corner_side(fid, axis, fixed, r0, r1, bi):
    """Mesma convenção do motor: qual extremo da face a viga cobre mais."""
    if axis == "H":
        mid = (max(r0, bi["x0"]) + min(r1, bi["x1"])) / 2.0
        return "esq" if mid <= (r0 + r1) / 2.0 else "dir"
    mid = (max(r0, bi["y0"]) + min(r1, bi["y1"])) / 2.0
    mid_face = (r0 + r1) / 2.0
    if fid == "A":
        return "esq" if mid >= mid_face else "dir"
    return "esq" if mid <= mid_face else "dir"


def _bucket():
    return {"passa_esq": None, "passa_dir": None, "para": [], "interior": []}


def _beam(name, x0, y0, x1, y1, is_h):
    return {"name": name, "dim": "19/120", "is_h": is_h,
            "runs": [(x0, y0, x1, y1)], "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "evidence_segments": []}


# P42 real: pilar horizontal 50x19; V312 vertical cruza pelo meio.
P42_FACES = {"A": ("H", 2991.0, 1587.9, 1637.9), "B": ("H", 3010.0, 1587.9, 1637.9)}
P42_CORNERS = {"A": ("AC", "AD"), "B": ("BC", "BD")}


def test_cruzamento_no_meio_da_face_vira_chegada_no_canto_proprio():
    faces = {"A": _bucket(), "B": _bucket()}

    added = apply_transversal_crossing_arrivals(
        faces, beam_info=[_beam("V312", 1600.9, 2680.0, 1624.9, 3141.0, False)],
        face_coords=P42_FACES, face_corners=P42_CORNERS,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0,
    )

    assert added == 2
    assert [(r["name"], r["corner"]) for r in faces["A"]["para"]] == [("V312", "AA")]
    assert [(r["name"], r["corner"]) for r in faces["B"]["para"]] == [("V312", "BB")]
    assert faces["A"]["para"][0]["source"] == "transversal_face_crossing"


def test_viga_paralela_a_face_nao_e_cruzamento():
    faces = {"A": _bucket(), "B": _bucket()}

    added = apply_transversal_crossing_arrivals(
        faces, beam_info=[_beam("V301", 1200.0, 2991.0, 2400.0, 3010.0, True)],
        face_coords=P42_FACES, face_corners=P42_CORNERS,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0,
    )

    assert added == 0
    assert faces["A"]["para"] == []


def test_cruzamento_encostado_num_extremo_usa_o_canto_daquele_extremo():
    faces = {"A": _bucket(), "B": _bucket()}

    apply_transversal_crossing_arrivals(
        faces, beam_info=[_beam("V9", 1587.9, 2680.0, 1611.9, 3141.0, False)],
        face_coords=P42_FACES, face_corners=P42_CORNERS,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0,
    )

    assert faces["A"]["para"][0]["corner"] == "AC"


def test_face_vertical_nao_inverte_os_cantos():
    # P29: pilar vertical; face A a oeste, C ao norte e D ao sul. Uma viga
    # horizontal cruzando pela parte de cima chega em AC, nunca em AD.
    faces = {"A": _bucket()}
    coords = {"A": ("V", 2037.9, 1963.0, 2029.0)}
    corners = {"A": ("AC", "AD")}

    apply_transversal_crossing_arrivals(
        faces, beam_info=[_beam("VF202", 1349.3, 2007.8, 3807.4, 2031.8, True)],
        face_coords=coords, face_corners=corners,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0,
    )

    assert faces["A"]["para"][0]["corner"] == "AC"


def test_viga_ja_presente_na_face_nao_duplica():
    faces = {"A": _bucket(), "B": _bucket()}
    faces["A"]["passa_esq"] = {"name": "V312", "dim": "19/120", "corner": "AC"}

    apply_transversal_crossing_arrivals(
        faces, beam_info=[_beam("V312", 1600.9, 2680.0, 1624.9, 3141.0, False)],
        face_coords=P42_FACES, face_corners=P42_CORNERS,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0,
    )

    assert faces["A"]["para"] == []


def test_corredor_mais_grosso_que_a_secao_nao_gera_chegada():
    # VF202 no 13_PAV: seção 19/55, corredor traçado com 76 cm — bbox de uma
    # diagonal, não um trecho físico. Criava contato com pilares distantes.
    faces = {"A": _bucket(), "B": _bucket()}
    # Vertical: a espessura é a extensão em x — 76 cm para uma seção de 19.
    inflado = _beam("VF202", 1600.0, 2950.0, 1676.0, 3026.0, False)
    inflado["dim"] = "19/55"

    added = apply_transversal_crossing_arrivals(
        faces, beam_info=[inflado], face_coords=P42_FACES,
        face_corners=P42_CORNERS, corner_side=_corner_side,
        tol=2.0, min_overlap=1.0,
    )

    assert added == 0


def test_corredor_com_padding_do_tracador_continua_valendo():
    # V312: seção 19, corredor 24 — a folga do traçador não invalida o trecho.
    from src.core.pillar_face_beams import _run_thickness_matches_section

    assert _run_thickness_matches_section(24.0, "19/120") is True
    assert _run_thickness_matches_section(76.0, "19/55") is False
    # Deslocamento de uma largura inteira continua sendo trecho real.
    assert _run_thickness_matches_section(40.0, "14/50") is True
    # Sem seção declarada a checagem não bloqueia.
    assert _run_thickness_matches_section(999.0, "") is True


def test_viga_que_termina_na_face_tambem_chega():
    # V313 em P29: o corredor nasce exatamente no y da face C e segue para
    # fora. Terminar na face é a outra forma de chegar nela.
    faces = {"C": _bucket()}
    coords = {"C": ("H", 2029.0, 2037.9, 2061.9)}
    corners = {"C": ("CA", "CB")}
    pillar = (2037.9, 1963.0, 2061.9, 2029.0)
    viga = _beam("V313", 2040.4, 2029.0, 2059.4, 2421.0, False)

    added = apply_transversal_crossing_arrivals(
        faces, beam_info=[viga], face_coords=coords, face_corners=corners,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0, pillar_bbox=pillar,
    )

    assert added == 1
    assert faces["C"]["para"][0]["corner"] == "CC"


def test_viga_que_termina_pelo_lado_de_dentro_nao_e_chegada():
    # Trecho que morre na face vindo de dentro do pilar é interior, não
    # chegada: aceitar isso inverteria o papel.
    faces = {"C": _bucket()}
    coords = {"C": ("H", 2029.0, 2037.9, 2061.9)}
    corners = {"C": ("CA", "CB")}
    pillar = (2037.9, 1963.0, 2061.9, 2029.0)
    viga = _beam("VX", 2040.4, 1970.0, 2059.4, 2029.0, False)

    added = apply_transversal_crossing_arrivals(
        faces, beam_info=[viga], face_coords=coords, face_corners=corners,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0, pillar_bbox=pillar,
    )

    assert added == 0


def test_sem_bbox_do_pilar_so_o_cruzamento_conta():
    faces = {"C": _bucket()}
    coords = {"C": ("H", 2029.0, 2037.9, 2061.9)}
    corners = {"C": ("CA", "CB")}
    viga = _beam("V313", 2040.4, 2029.0, 2059.4, 2421.0, False)

    added = apply_transversal_crossing_arrivals(
        faces, beam_info=[viga], face_coords=coords, face_corners=corners,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0,
    )

    assert added == 0


def test_viga_ja_vinculada_nas_faces_vizinhas_nao_chega_no_canto():
    # P35/V308: corre paralela a A/B e morre no canto C. Já vinculada nas
    # longas, ali ela é interior — aceitar como chegada reintroduziria um
    # falso positivo que o dono já tinha apontado.
    faces = {"A": _bucket(), "B": _bucket(), "C": _bucket()}
    faces["A"]["passa_esq"] = {"name": "V308", "dim": "19/55", "corner": "AC"}
    coords = {"C": ("V", 100.0, 0.0, 19.0)}
    corners = {"A": ("AC", "AD"), "B": ("BC", "BD"), "C": ("CA", "CB")}
    pillar = (100.0, 0.0, 160.0, 19.0)
    viga = _beam("V308", 0.0, 0.0, 100.0, 19.0, True)

    added = apply_transversal_crossing_arrivals(
        faces, beam_info=[viga], face_coords=coords, face_corners=corners,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0, pillar_bbox=pillar,
    )

    assert added == 0


def test_vao_ocupado_por_viga_fecha_e_a_chegada_vale():
    """R1 do dono: V313 para 38 cm antes de P29, com V306 no meio.

    O vão é continuação da viga — 19 cm de V306 mais a própria seção fecham
    os 38. O corredor de V306 vem **medido**, não do traçado, que para num
    pilar bem antes.
    """
    faces = {"C": _bucket()}
    coords = {"C": ("H", 2029.0, 2037.9, 2061.9)}
    corners = {"C": ("CA", "CB")}
    pillar = (2037.9, 1963.0, 2061.9, 2029.0)
    v313 = _beam("V313", 2040.4, 2067.0, 2059.4, 2423.0, False)
    v306 = _beam("V306", 1349.0, 2048.0, 1603.0, 2067.0, True)
    v306["measured_corridors"] = [(1357.0, 2048.0, 3788.0, 2067.0)]

    added = apply_transversal_crossing_arrivals(
        faces, beam_info=[v313, v306], face_coords=coords, face_corners=corners,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0, pillar_bbox=pillar,
    )

    assert added == 1
    assert faces["C"]["para"][0]["name"] == "V313"
    assert faces["C"]["para"][0]["corner"] == "CC"


def test_vao_vazio_nao_fecha():
    # Sem viga ocupando o vão, os 38 cm não são continuação de nada.
    faces = {"C": _bucket()}
    coords = {"C": ("H", 2029.0, 2037.9, 2061.9)}
    corners = {"C": ("CA", "CB")}
    pillar = (2037.9, 1963.0, 2061.9, 2029.0)
    v313 = _beam("V313", 2040.4, 2067.0, 2059.4, 2423.0, False)

    added = apply_transversal_crossing_arrivals(
        faces, beam_info=[v313], face_coords=coords, face_corners=corners,
        corner_side=_corner_side, tol=2.0, min_overlap=1.0, pillar_bbox=pillar,
    )

    assert added == 0
