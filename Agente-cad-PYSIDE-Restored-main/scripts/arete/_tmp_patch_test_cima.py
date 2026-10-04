from pathlib import Path

p = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\tests\test_pl_cima_especial.py")
t = p.read_text(encoding="utf-8")
old = '''def test_cota_book_slides_text_off_crossing_line_and_other_text():
    from pl_cima_especial import CotaBook

    book = CotaBook()
    book.add_line((20.0, -20.0), (20.0, 40.0))
    x, y = book.place((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), 0.0, 50.0, 0.0, "153 PAINEL", 5.0, 0.0)
    assert x > 24.0
    x2, _y2 = book.place((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), 0.0, 50.0, 0.0, "70(GRADE)", 5.0, 0.0)
    assert abs(x2 - x) > 6.0
'''
new = '''def test_cota_totals_stay_centered_on_the_dim_line():
    from pl_cima_especial import CotaBook

    book = CotaBook()
    x, y = book.place((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), 0.0, 240.0, 0.0, "240 PAINEL", 5.0, 0.0)
    assert x == pytest.approx(120.0, abs=0.2)
    xg, _yg = book.place((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), 0.0, 120.0, 28.0, "120(GRADE)", 5.0, 0.0)
    assert xg == pytest.approx(60.0, abs=0.2)


def test_cima_l_draws_bolts_and_six_abcd_faces():
    from gerar_pl_dxf_stog import generate_pilar_zone, setup_doc
    from src.core.cima_l_contract import n3_faces_l

    faces = n3_faces_l({"subtipo_pil": "L", "geometry_points": P26_POINTS})
    assert [f["id"] for f in faces] == list("ABCDEF")
    assert faces[0]["panel"] == pytest.approx(240.0)
    assert faces[4]["panel"] == pytest.approx(176.0)

    payload = {
        "nome": "P26",
        "comprimento": 50.0,
        "largura": 19.0,
        "subtipo_pil": "L",
        "geometry_points": P26_POINTS,
        "grade_1": 240.0,
        "altura": 321.0,
    }
    doc = setup_doc()
    generate_pilar_zone(doc.modelspace(), payload, "cima", visual_mode="NOVA")
    layers = {e.dxf.layer for e in doc.modelspace()}
    assert "Hachura" in layers
    texts = [
        e.dxf.text for e in doc.modelspace()
        if e.dxftype() == "TEXT" and "PARAFUSO" in (e.dxf.text or "").upper()
    ]
    assert texts

    doc_abcd = setup_doc()
    generate_pilar_zone(doc_abcd.modelspace(), payload, "abcd", visual_mode="NOVA")
    labels = {
        (e.dxf.text or "").strip()
        for e in doc_abcd.modelspace()
        if e.dxftype() == "TEXT"
    }
    for fid in "ABCDEF":
        assert fid in labels

    doc_gr = setup_doc()
    generate_pilar_zone(doc_gr.modelspace(), payload, "grades", visual_mode="NOVA")
    names = " ".join(
        e.dxf.text or "" for e in doc_gr.modelspace() if e.dxftype() == "TEXT"
    )
    for fid in "ABCDEF":
        assert f"P26.{fid}" in names or fid in names
'''
if old not in t:
    if "test_cota_totals_stay_centered" in t:
        print("already patched")
    else:
        t = t + "\n\n" + new
        tmp = p.with_suffix(".py.tmpwrite")
        tmp.write_text(t, encoding="utf-8")
        tmp.replace(p)
        print("appended")
else:
    t = t.replace(old, new, 1)
    tmp = p.with_suffix(".py.tmpwrite")
    tmp.write_text(t, encoding="utf-8")
    tmp.replace(p)
    print("replaced")
