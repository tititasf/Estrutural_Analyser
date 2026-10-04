"""D-74/D-78: ordem e modo da obra são configuração, não inferência do SA."""
import sqlite3

from services import obra_context
from services.reaproveitamento_service import cadeia, cenarios_da_classe
from services.resolve_service import resolver_code
from publisher import publish


def test_modo_filtra_codigos_diretos_e_misto_reexibe(tmp_path, monkeypatch):
    portal_db = tmp_path / "portal_data.db"
    with sqlite3.connect(portal_db) as c:
        c.execute("CREATE TABLE portal_obras(id TEXT PRIMARY KEY, comportamento TEXT)")
        c.execute("INSERT INTO portal_obras VALUES('o','para')")
    monkeypatch.setattr(obra_context, "PORTAL_DB", portal_db)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE public_codes(code TEXT,kind TEXT,obra_id TEXT,classe TEXT,revoked INTEGER,pavimento TEXT,payload_json TEXT)")
    for code, classe in [("P", "pilares_n3_para"), ("X", "pilares_n3_passa"),
                         ("LP", "lateral_a_para"), ("LX", "lateral_b_passa"),
                         ("F", "fundo"), ("L", "lajes")]:
        conn.execute("INSERT INTO public_codes VALUES(?, 'item','o',?,0,'TERREO',NULL)", (code, classe))
    assert resolver_code(conn, "P") and resolver_code(conn, "LP")
    assert resolver_code(conn, "X") is None and resolver_code(conn, "LX") is None
    assert resolver_code(conn, "F") and resolver_code(conn, "L")
    with sqlite3.connect(portal_db) as c:
        c.execute("UPDATE portal_obras SET comportamento='misto' WHERE id='o'")
    assert resolver_code(conn, "X") and resolver_code(conn, "LX")
    assert cenarios_da_classe("fundo") == cenarios_da_classe("lajes") == ["para", "passa"]


def test_cadeia_usa_cadastro_inclusive_pavimento_sem_itens(tmp_path, monkeypatch):
    portal_db = tmp_path / "portal_data.db"
    with sqlite3.connect(portal_db) as c:
        c.execute("CREATE TABLE portal_obra_pavimentos(obra_id TEXT,pavimento TEXT,ordem INTEGER,repete_de INTEGER,repete_ate INTEGER)")
        c.executemany("INSERT INTO portal_obra_pavimentos VALUES('o',?,?,NULL,NULL)",
                      [("2SS", 0), ("TIPO", 1), ("COBERTURA", 2)])
    monkeypatch.setattr(obra_context, "PORTAL_DB", portal_db)
    conn = sqlite3.connect(":memory:")
    assert cadeia(conn, "o", "COBERTURA") == ["2SS", "TIPO", "COBERTURA"]


def test_publisher_publica_apenas_variante_da_obra(monkeypatch):
    def itens(_estado, classe):
        if classe.startswith("pilares_n3_"):
            suffix = "_Para" if classe.endswith("para") else "_Passa"
            return [{"item_id": "P1" + suffix, "titulo": "P1"}]
        if classe.startswith("lateral_"):
            return [{"item_id": classe + "_S1", "beam_name": "V1", "campos": {"Segmento": "1"}}]
        if classe in {"fundo", "lajes"}:
            return [{"item_id": classe + "1", "titulo": classe}]
        return []
    monkeypatch.setattr(publish.ficha_reader, "listar_itens_n1", itens)
    para = publish._unidades_do_pavimento({}, "para")
    assert any(u["classe"] == "pilares_n3_para" for u in para)
    assert all(not u["classe"].endswith("_passa") for u in para)
    assert {u["classe"] for u in para} >= {"fundo", "lajes"}
    misto = publish._unidades_do_pavimento({}, "misto")
    assert any(u["classe"] == "pilares_n3_passa" for u in misto)
    assert any(u["classe"] == "lateral_a_passa" for u in misto)
