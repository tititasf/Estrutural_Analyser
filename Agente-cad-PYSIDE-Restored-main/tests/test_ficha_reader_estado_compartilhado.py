from pathlib import Path

from portal.app import ficha_reader


def test_lote_le_uma_vez_e_entrega_copias(monkeypatch, tmp_path):
    calls = []

    def fake(obra_dir, pavimento, *, apply_qa=True):
        calls.append((obra_dir, pavimento, apply_qa))
        return {"beams": [{"name": "V1"}]}

    monkeypatch.setattr(ficha_reader, "_ler_estado_pavimento", fake)
    with ficha_reader.estado_compartilhado():
        a = ficha_reader.ler_estado_pavimento(tmp_path, "13_PAV")
        a["beams"].clear()
        b = ficha_reader.ler_estado_pavimento(Path(str(tmp_path)), "13_PAV")
        ficha_reader.ler_estado_pavimento(tmp_path, "13_PAV", apply_qa=False)
    assert b == {"beams": [{"name": "V1"}]}
    assert len(calls) == 2
    ficha_reader.ler_estado_pavimento(tmp_path, "13_PAV")
    assert len(calls) == 3
