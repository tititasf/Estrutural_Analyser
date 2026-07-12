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
from publisher.publish import gerar_code, publicar, revogar  # noqa: E402


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
        "publish_batch",
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

    assert resumo["itens_publicados"] == 3  # P1, P2, L101
    assert resumo["itens_preservados"] == 0

    rows = conn.execute(
        "SELECT item_id, tipo_elemento, code FROM public_codes WHERE kind='item' ORDER BY item_id"
    ).fetchall()
    assert [r["item_id"] for r in rows] == ["L101", "P1", "P2"]
    tipos = {r["item_id"]: r["tipo_elemento"] for r in rows}
    assert tipos["P1"] == "pilar"
    assert tipos["P2"] == "pilar"
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
    assert resumo2["itens_preservados"] == 3
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
        "SELECT code FROM public_codes WHERE obra_id='obra-item-revoke' AND item_id='P1'"
    ).fetchone()
    afetadas = revogar(code=row["code"], conn=conn)
    assert afetadas == 1

    p1 = conn.execute("SELECT revoked FROM public_codes WHERE code=?", (row["code"],)).fetchone()
    assert p1["revoked"] == 1
    p2 = conn.execute(
        "SELECT revoked FROM public_codes WHERE obra_id='obra-item-revoke' AND item_id='P2'"
    ).fetchone()
    assert p2["revoked"] == 0


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
        assert row[0] == 5  # 1 obra + 1 pavimento + 3 itens
    finally:
        ro_conn.close()
