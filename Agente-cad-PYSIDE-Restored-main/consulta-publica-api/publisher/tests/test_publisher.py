"""Testes do Publisher (STORY-01) — AC 1-8.

Roda com pytest a partir da raiz do repo:
    pytest consulta-publica-api/publisher/tests/test_publisher.py -v
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest import mock

import pytest

# `consulta-publica-api` tem hifens, não é um nome de pacote Python válido —
# adicionamos a própria pasta (não a raiz do repo) ao sys.path, e importamos
# `publisher.*` como pacote de topo (nome sem hifen).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from publisher.db import get_connection, assert_no_blacklisted_columns  # noqa: E402
from publisher.publish import (  # noqa: E402
    gerar_code, publicar, publicar_pavimento_minimo, publicar_recorte, revogar,
)


_ESTADO_TERREO = {
    "pilares": [
        {"name": "P1", "points": [[0, 0], [30, 0], [30, 30], [0, 30]], "classification": "OK"},
        {"name": "P2", "points": [[100, 0], [130, 0], [130, 30], [100, 30]], "classification": "OK"},
    ],
    "slabs": [
        {"name": "L101", "nivel": "N1", "height": "12", "points": [[0, 0], [400, 0], [400, 400], [0, 400]]},
    ],
    "cortes": [],
    "segmentos": {"fundo": [], "lateral_a_para": [], "lateral_b_para": [], "lateral_a_passa": [], "lateral_b_passa": []},
}


@pytest.fixture
def obra_dir(tmp_path: Path) -> Path:
    d = tmp_path / "obra_fake"
    d.mkdir()
    (d / "estado_TERREO.json").write_text(json.dumps(_ESTADO_TERREO), encoding="utf-8")
    return d


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "public_consulta_test.db"
    c = get_connection(db_path)
    yield c
    c.close()


def test_schema_no_blacklisted_columns(conn: sqlite3.Connection):
    """AC 2 — nenhuma coluna comercial/pessoal existe em public_codes."""
    assert_no_blacklisted_columns(conn)  # não deve levantar

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(public_codes)")}
    esperado = {
        "code", "kind", "obra_id", "obra_dir", "pavimento", "classe", "item_id",
        "tipo_elemento", "titulo_publico", "obra_rotulo", "revoked", "created_at",
        "publish_batch", "payload_json",
    }
    assert columns == esperado


def test_gerar_code_e_unico_sob_colisao(conn: sqlite3.Connection):
    """AC 1, 7 — retry em colisão simulada de secrets.token_bytes."""
    from publisher.publish import _BASE62_ALPHABET, _CODE_LEN

    colidido = bytes([0] * _CODE_LEN)
    real_token_bytes = __import__("secrets").token_bytes

    call_count = {"n": 0}

    def fake_token_bytes(n):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return colidido
        return real_token_bytes(n)

    # Primeiro insere um código com o token colidido para forçar colisão real.
    code_pre_existente = "".join(_BASE62_ALPHABET[b % 62] for b in colidido)[:_CODE_LEN]
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir) VALUES (?, 'obra', 'x', '/x')",
        (code_pre_existente,),
    )

    with mock.patch("publisher.publish.secrets.token_bytes", side_effect=fake_token_bytes):
        novo_code = gerar_code(conn)

    assert novo_code != code_pre_existente
    assert call_count["n"] >= 2
    assert len(novo_code) == _CODE_LEN


def test_gerar_code_tem_10_caracteres(conn: sqlite3.Connection):
    """Regressão: bug real achado em teste manual — token_bytes(8) hardcoded
    gerava código de 8 chars em vez dos 10 especificados (architecture §3.1)."""
    from publisher.publish import _CODE_LEN

    code = gerar_code(conn)
    assert len(code) == _CODE_LEN == 10


def test_publicar_gera_codigos_unicos_e_mapeia_tipo_elemento(conn, obra_dir):
    """AC 1 — publica pilares e lajes, cada um com code único e tipo_elemento certo."""
    obra = {"id": "obra-123"}
    resumo = publicar(obra, obra_dir, conn=conn)

    assert resumo["itens_publicados"] == 5  # P1 e P2 (Para+Passa), L101
    assert resumo["itens_preservados"] == 0

    rows = conn.execute(
        "SELECT item_id, tipo_elemento, code FROM public_codes WHERE kind='item' ORDER BY item_id"
    ).fetchall()
    assert [r["item_id"] for r in rows] == ["L101", "P1_Para", "P1_Passa", "P2_Para", "P2_Passa"]
    tipos = {r["item_id"]: r["tipo_elemento"] for r in rows}
    assert tipos["P1_Para"] == "pilar"
    assert tipos["P2_Passa"] == "pilar"
    assert tipos["L101"] == "laje"
    codes = [r["code"] for r in rows]
    assert len(codes) == len(set(codes))  # todos únicos


def test_republish_preserva_code_e_revoga_batch_anterior(conn, obra_dir):
    """AC 3 — segunda publicação preserva os codes e revoga o batch antigo."""
    obra = {"id": "obra-123"}
    resumo1 = publicar(obra, obra_dir, conn=conn)
    codes_batch1 = {
        r["item_id"]: r["code"]
        for r in conn.execute("SELECT item_id, code FROM public_codes WHERE kind='item'").fetchall()
    }

    resumo2 = publicar(obra, obra_dir, conn=conn)
    assert resumo2["itens_preservados"] == 5
    assert resumo2["itens_publicados"] == 0
    assert resumo2["publish_batch"] != resumo1["publish_batch"]

    codes_batch2 = {
        r["item_id"]: r["code"]
        for r in conn.execute("SELECT item_id, code FROM public_codes WHERE kind='item'").fetchall()
    }
    assert codes_batch1 == codes_batch2  # mesmos codes preservados

    # Batch anterior deve estar revogado, batch atual não.
    revoked_batch1 = conn.execute(
        "SELECT revoked FROM public_codes WHERE publish_batch = ?", (resumo1["publish_batch"],)
    ).fetchall()
    assert revoked_batch1 == []  # não há mais linhas com o batch antigo (todas migraram pro novo)

    row_atual = conn.execute(
        "SELECT revoked FROM public_codes WHERE publish_batch = ? LIMIT 1", (resumo2["publish_batch"],)
    ).fetchone()
    assert row_atual["revoked"] == 0


def test_obra_rotulo_default_nunca_expoe_nome_cru(conn, obra_dir):
    """AC 5 — sem obra_rotulo explícito, usa default anônimo, nunca o nome real."""
    obra = {"id": "obra-999"}
    publicar(obra, obra_dir, conn=conn)
    row = conn.execute(
        "SELECT obra_rotulo FROM public_codes WHERE obra_id='obra-999' AND kind='obra'"
    ).fetchone()
    assert row["obra_rotulo"].startswith("Obra ·· ")
    assert "Cliente Sigiloso Ltda" not in row["obra_rotulo"]


def test_revogar_obra_inteira(conn, obra_dir):
    """AC 4 — revogar por obra_id marca todos os registros daquela obra."""
    obra = {"id": "obra-revoke"}
    publicar(obra, obra_dir, conn=conn)
    afetadas = revogar(obra_id="obra-revoke", conn=conn)
    assert afetadas >= 5  # 1 obra + 1 pavimento + 3 itens
    restantes = conn.execute(
        "SELECT COUNT(*) c FROM public_codes WHERE obra_id='obra-revoke' AND revoked=0"
    ).fetchone()
    assert restantes["c"] == 0


def test_revogar_item_individual(conn, obra_dir):
    """AC 4 — revogar por code afeta só aquele item."""
    obra = {"id": "obra-item-revoke"}
    publicar(obra, obra_dir, conn=conn)
    row = conn.execute(
        "SELECT code FROM public_codes WHERE obra_id='obra-item-revoke' AND item_id='P1_Para'"
    ).fetchone()
    afetadas = revogar(code=row["code"], conn=conn)
    assert afetadas == 1

    p1 = conn.execute("SELECT revoked FROM public_codes WHERE code=?", (row["code"],)).fetchone()
    assert p1["revoked"] == 1
    p2 = conn.execute(
        "SELECT revoked FROM public_codes WHERE obra_id='obra-item-revoke' AND item_id='P2_Para'"
    ).fetchone()
    assert p2["revoked"] == 0


def test_publicar_pavimento_minimo_sem_estado_sa(conn, tmp_path):
    """[2026-07-13] Mint mínimo (obra+pavimento) tem que funcionar mesmo
    quando `estado_<pav>.json` NÃO existe ainda (Triagem/Recortes, antes do
    SA rodar) — é exatamente o cenário que motivou essa função: pedido do
    dono pra ter o código de pavimento assim que ele valida um recorte."""
    obra_dir = tmp_path / "obra_sem_sa"
    obra_dir.mkdir()  # nenhum estado_*.json aqui de propósito

    resultado = publicar_pavimento_minimo("obra-min-1", obra_dir, "TERREO", conn=conn)
    assert resultado["code_obra"]
    assert resultado["code_pavimento"]

    row_obra = conn.execute(
        "SELECT code FROM public_codes WHERE obra_id='obra-min-1' AND kind='obra'"
    ).fetchone()
    assert row_obra["code"] == resultado["code_obra"]
    row_pav = conn.execute(
        "SELECT code FROM public_codes WHERE obra_id='obra-min-1' AND pavimento='TERREO' AND kind='pavimento'"
    ).fetchone()
    assert row_pav["code"] == resultado["code_pavimento"]


def test_publicar_pavimento_minimo_preserva_code_em_2a_chamada(conn, tmp_path):
    obra_dir = tmp_path / "obra_sem_sa2"
    obra_dir.mkdir()

    r1 = publicar_pavimento_minimo("obra-min-2", obra_dir, "TERREO", conn=conn)
    r2 = publicar_pavimento_minimo("obra-min-2", obra_dir, "TERREO", conn=conn)
    assert r1["code_obra"] == r2["code_obra"]
    assert r1["code_pavimento"] == r2["code_pavimento"]


def test_publicar_recorte_minta_codigo_proprio(conn, tmp_path):
    """[2026-07-13] Cada recorte (Torre 1/Detalhes/etc) ganha seu próprio
    código, distinto do código de pavimento — pedido do dono: "cada um
    tenha seu codigo conforme seja validado"."""
    obra_dir = tmp_path / "obra_recorte"
    obra_dir.mkdir()

    code_recorte = publicar_recorte(
        "obra-rec-1", obra_dir, "TERREO", "torre_1", "bruto-abc", "Torre 1", conn=conn,
    )
    assert code_recorte

    row = conn.execute(
        "SELECT * FROM public_codes WHERE code=?", (code_recorte,)
    ).fetchone()
    assert row["kind"] == "recorte"
    assert row["obra_id"] == "obra-rec-1"
    assert row["pavimento"] == "TERREO"
    assert row["classe"] == "torre_1"
    assert row["item_id"] == "bruto-abc"
    assert row["titulo_publico"] == "Torre 1"

    # obra + pavimento também foram mintados junto (dependência implícita).
    row_pav = conn.execute(
        "SELECT code FROM public_codes WHERE obra_id='obra-rec-1' AND pavimento='TERREO' AND kind='pavimento'"
    ).fetchone()
    assert row_pav is not None
    assert row_pav["code"] != code_recorte


def test_publicar_recorte_preserva_code_em_revalidacao(conn, tmp_path):
    obra_dir = tmp_path / "obra_recorte2"
    obra_dir.mkdir()

    c1 = publicar_recorte("obra-rec-2", obra_dir, "TERREO", "torre_1", "bruto-x", "Torre 1", conn=conn)
    c2 = publicar_recorte("obra-rec-2", obra_dir, "TERREO", "torre_1", "bruto-x", "Torre 1", conn=conn)
    assert c1 == c2


def test_publicar_recorte_dois_tipos_mesmo_bruto_tem_codes_diferentes(conn, tmp_path):
    obra_dir = tmp_path / "obra_recorte3"
    obra_dir.mkdir()

    c_torre = publicar_recorte("obra-rec-3", obra_dir, "TERREO", "torre_1", "bruto-y", "Torre 1", conn=conn)
    c_detalhes = publicar_recorte(
        "obra-rec-3", obra_dir, "TERREO", "detalhes", "bruto-y", "Detalhes e Convenções Gerais", conn=conn,
    )
    assert c_torre != c_detalhes


def test_db_fecha_sem_lock_pendente(tmp_path, obra_dir):
    """AC 8 — após publicar e fechar, o arquivo abre em mode=ro sem erro."""
    db_path = tmp_path / "public_consulta_ro_test.db"
    conn = get_connection(db_path)
    publicar({"id": "obra-ro"}, obra_dir, conn=conn)
    conn.close()

    ro_uri = f"file:{db_path}?mode=ro"
    ro_conn = sqlite3.connect(ro_uri, uri=True)
    try:
        row = ro_conn.execute(
            "SELECT COUNT(*) c FROM public_codes WHERE obra_id='obra-ro'"
        ).fetchone()
        assert row[0] == 7  # 1 obra + 1 pavimento + 5 itens
    finally:
        ro_conn.close()


# ---------------------------------------------------------------------------
# [2026-09-28] LV = 1 código por viga por listagem; pilar = 2 códigos.
# ---------------------------------------------------------------------------

def _seg(uid, viga, label, side, behavior):
    return {"uid": uid, "beam_name": viga, "segment_label": label, "side": side,
            "behavior": behavior, "length": 100, "points": [[0, 0], [100, 0]]}


@pytest.fixture
def obra_lv(tmp_path: Path) -> Path:
    estado = json.loads(json.dumps(_ESTADO_TERREO))
    estado["segmentos"]["lateral_a_para"] = [
        _seg("ap|V301|2", "V301", "2", "A", "Para"), _seg("ap|V301|1", "V301", "1", "A", "Para"),
        _seg("ap|V302|1", "V302", "1", "A", "Para"),
    ]
    estado["segmentos"]["lateral_b_para"] = [_seg("bp|V301|1", "V301", "1", "B", "Para")]
    estado["segmentos"]["lateral_a_passa"] = [_seg("aq|V301|1", "V301", "1", "A", "Passa")]
    d = tmp_path / "obra_lv"
    d.mkdir()
    (d / "estado_TERREO.json").write_text(json.dumps(estado), encoding="utf-8")
    return d


def _itens(conn, tipo):
    return [dict(r) for r in conn.execute(
        "SELECT code, classe, item_id, titulo_publico, payload_json FROM public_codes"
        " WHERE kind='item' AND revoked=0 AND tipo_elemento=? ORDER BY titulo_publico, payload_json",
        (tipo,))]


def test_lv_um_codigo_por_viga_com_modo_e_segmentos(conn, obra_lv):
    publicar({"id": "obra-lv"}, obra_lv, conn=conn)
    lvs = _itens(conn, "viga_lateral")
    chaves = sorted((r["titulo_publico"], json.loads(r["payload_json"])["modo"]) for r in lvs)
    assert chaves == [("V301", "param"), ("V301", "passa"), ("V302", "param")]

    v301 = next(json.loads(r["payload_json"]) | {"_code": r["code"]} for r in lvs
                if r["titulo_publico"] == "V301" and '"param"' in r["payload_json"])
    segs = v301["segmentos"]
    assert [(s["lado"], s["segmento"]) for s in segs] == [("A", "1"), ("A", "2"), ("B", "1")]
    assert [s["indice"] for s in segs] == [0, 1, 2]
    assert segs[1]["svg"]["n1"] == f"/api/v1/ficha/{v301['_code']}/svg/n1?seg=1"
    ancora = next(r for r in lvs if r["code"] == v301["_code"])
    assert (ancora["classe"], ancora["item_id"]) == ("lateral_a_para", "ap|V301|1")

    # Republicar preserva o código da viga.
    publicar({"id": "obra-lv"}, obra_lv, conn=conn)
    assert {r["code"] for r in _itens(conn, "viga_lateral")} == {r["code"] for r in lvs}


def test_pilar_dois_codigos_com_modo_pilar(conn, obra_dir):
    publicar({"id": "obra-p"}, obra_dir, conn=conn)
    pilares = _itens(conn, "pilar")
    assert sorted((r["titulo_publico"], json.loads(r["payload_json"])["modo_pilar"]) for r in pilares) == [
        ("P1", "param"), ("P1", "passa"), ("P2", "param"), ("P2", "passa")]


def test_codigos_legados_sao_herdados(conn, obra_lv):
    """QR já impresso continua abrindo: pilar antigo vira o `param`, segmento
    1 antigo vira a viga; os demais segmentos antigos ficam revogados."""
    def legado(code, classe, item_id):
        conn.execute(
            "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id,"
            " tipo_elemento, titulo_publico, publish_batch) VALUES (?, 'item', 'obra-lg', ?, 'TERREO', ?, ?, 'x', 'x', 'velho')",
            (code, str(obra_lv), classe, item_id))
    legado("PILARP1AAA", "pilares", "P1")
    legado("SEGV301S01", "lateral_a_para", "ap|V301|1")
    legado("SEGV301S02", "lateral_a_para", "ap|V301|2")
    conn.commit()

    publicar({"id": "obra-lg"}, obra_lv, conn=conn)
    vivo = {r["code"]: dict(r) for r in conn.execute(
        "SELECT code, classe, item_id, payload_json FROM public_codes WHERE revoked=0 AND kind='item'")}
    assert vivo["PILARP1AAA"]["classe"] == "pilares_n3_para"
    assert json.loads(vivo["PILARP1AAA"]["payload_json"]) == {"modo_pilar": "param"}
    assert json.loads(vivo["SEGV301S01"]["payload_json"])["viga"] == "V301"
    assert "SEGV301S02" not in vivo


def test_db_antigo_ganha_coluna_payload_json(tmp_path):
    db_path = tmp_path / "antigo.db"
    velho = sqlite3.connect(db_path)
    velho.execute("CREATE TABLE public_codes (code TEXT PRIMARY KEY, kind TEXT NOT NULL, obra_id TEXT NOT NULL,"
                  " obra_dir TEXT NOT NULL, pavimento TEXT, classe TEXT, item_id TEXT, tipo_elemento TEXT,"
                  " titulo_publico TEXT, obra_rotulo TEXT, revoked INTEGER NOT NULL DEFAULT 0,"
                  " created_at TEXT, publish_batch TEXT)")
    velho.commit()
    velho.close()
    c = get_connection(db_path)
    try:
        assert "payload_json" in {r["name"] for r in c.execute("PRAGMA table_info(public_codes)")}
    finally:
        c.close()


def test_portal_interno_acha_codigo_de_pilar_e_segmento(tmp_path, obra_lv):
    """O portal interno pergunta por (classe, item_id) N1 — pilar cai no
    código `param`, segmento cai no código da viga."""
    from portal.app.public_codes_lookup import buscar_code_item

    db_path = tmp_path / "lookup.db"
    c = get_connection(db_path)
    publicar({"id": "obra-lk"}, obra_lv, conn=c)
    esperado_p1 = c.execute("SELECT code FROM public_codes WHERE item_id='P1_Para'").fetchone()["code"]
    viga = c.execute("SELECT code FROM public_codes WHERE titulo_publico='V301' AND classe='lateral_a_para'").fetchone()["code"]
    c.close()
    assert buscar_code_item(db_path, "obra-lk", "TERREO", "pilares", "P1") == esperado_p1
    assert buscar_code_item(db_path, "obra-lk", "TERREO", "lateral_b_para", "bp|V301|1") == viga
    assert buscar_code_item(db_path, "obra-lk", "TERREO", "lateral_a_para", "ap|V301|2") == viga
