"""Identidade e criação de item desenhado na web (P3).

Usa uma cópia MÍNIMA do schema real de `reverse_eng_fichas`/`reverse_eng_recortes`
(DDL extraído do project_data.vision em 2026-07-30), não um schema inventado —
é o que garante que `UNIQUE(obra_name, pavimento, classe, elemento_id)` e a
afinidade de tipo de `projeto_id` (declarado INTEGER, recebe TEXT) se comportam
como no banco de produção.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from src.core.item_manual import (
    IdentidadeItem,
    ItemDuplicado,
    STATUS_MANUAL,
    caminho_preview_n3,
    criar_item_manual,
    eh_projeto_web,
    item_ja_existe,
    materializar_preview_n3,
    normalizar_nome_item,
    projeto_id_web,
    sugerir_proximo_nome,
)

_DDL = """
CREATE TABLE reverse_eng_fichas (
    id              INTEGER PRIMARY KEY,
    projeto_id      INTEGER,
    obra_name       TEXT NOT NULL DEFAULT '',
    pavimento       TEXT NOT NULL DEFAULT '',
    classe          TEXT NOT NULL DEFAULT '',
    elemento_id     TEXT NOT NULL DEFAULT '',
    campos_json     TEXT NOT NULL DEFAULT '{}',
    recorte_path    TEXT,
    confianca       REAL DEFAULT 0.0,
    status          TEXT DEFAULT 'draft',
    aprovado_at     DATETIME,
    rag_indexed     INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME,
    UNIQUE(obra_name, pavimento, classe, elemento_id)
);
CREATE TABLE reverse_eng_recortes (
    id            INTEGER PRIMARY KEY,
    ficha_id      INTEGER REFERENCES reverse_eng_fichas(id),
    obra_name     TEXT NOT NULL,
    elemento_id   TEXT NOT NULL,
    recorte_path  TEXT NOT NULL,
    bbox_json     TEXT,
    entity_count  INTEGER,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    projeto_id TEXT, classe TEXT, status TEXT DEFAULT 'manual', confidence REAL DEFAULT NULL
);
"""


@pytest.fixture
def conn():
    con = sqlite3.connect(":memory:")
    con.executescript(_DDL)
    yield con
    con.close()


# ── projeto_id_web / eh_projeto_web ──────────────────────────────────────────

def test_projeto_id_e_deterministico():
    a = projeto_id_web("Obra_TREINO_1", "13_PAV")
    b = projeto_id_web("Obra_TREINO_1", "13_PAV")
    assert a == b == "web:Obra_TREINO_1:13_PAV"


def test_projeto_id_normaliza_o_pavimento():
    """Grafia de disco vira canônica — mesma obra/pavimento sempre bate."""
    a = projeto_id_web("Obra_TREINO_1", "ALIMONTI - PARAISO - 13° PAV.- PL - R00")
    b = projeto_id_web("Obra_TREINO_1", "13_PAV")
    assert a == b


def test_eh_projeto_web():
    assert eh_projeto_web("web:Obra_TREINO_1:13_PAV")
    assert not eh_projeto_web("TREINO_1")
    assert not eh_projeto_web("5924186a-095e-4a93-893e-d310bbc7bbab")
    assert not eh_projeto_web(None)


# ── normalizar_nome_item ─────────────────────────────────────────────────────

@pytest.mark.parametrize("bruto,esperado", [
    ("p12", "P12"), (" P12 ", "P12"), ("p 12", "P12"), ("L301", "L301"),
])
def test_normalizar_nome(bruto, esperado):
    assert normalizar_nome_item(bruto) == esperado


# ── item_ja_existe / criar_item_manual ───────────────────────────────────────

def test_criar_item_grava_ficha_e_recorte_juntos(conn):
    ident = criar_item_manual(
        conn, obra_name="Obra_TREINO_1", pavimento="13_PAV", classe="PIL",
        elemento_id="p99", recorte_path="C:/tmp/PIL_P99_web.dxf",
        bbox=(100.0, 200.0, 150.0, 250.0), entity_count=4,
    )
    assert ident.elemento_id == "P99"  # normalizado
    assert ident.projeto_id == "web:Obra_TREINO_1:13_PAV"

    ficha = conn.execute(
        "SELECT projeto_id, typeof(projeto_id), status, campos_json "
        "FROM reverse_eng_fichas"
    ).fetchone()
    assert ficha == ("web:Obra_TREINO_1:13_PAV", "text", STATUS_MANUAL, "{}")

    recorte = conn.execute(
        "SELECT bbox_json, entity_count, status FROM reverse_eng_recortes"
    ).fetchone()
    assert json.loads(recorte[0]) == {"x0": 100.0, "y0": 200.0, "x1": 150.0, "y1": 250.0}
    assert recorte[1] == 4
    assert recorte[2] == STATUS_MANUAL


def test_ficha_nasce_sem_campos_interpretados(conn):
    """campos_json vazio: inventar campo aqui pareceria interpretação real."""
    criar_item_manual(
        conn, obra_name="O", pavimento="13_PAV", classe="PIL", elemento_id="P1",
        recorte_path="x.dxf", bbox=(0, 0, 1, 1),
    )
    campos = conn.execute("SELECT campos_json FROM reverse_eng_fichas").fetchone()[0]
    assert json.loads(campos) == {}


def test_duplicata_de_ficha_e_recusada_antes_de_gravar(conn):
    criar_item_manual(
        conn, obra_name="O", pavimento="13_PAV", classe="PIL", elemento_id="P1",
        recorte_path="a.dxf", bbox=(0, 0, 1, 1),
    )
    with pytest.raises(ItemDuplicado):
        criar_item_manual(
            conn, obra_name="O", pavimento="13_PAV", classe="PIL", elemento_id="p1",
            recorte_path="b.dxf", bbox=(0, 0, 1, 1),
        )
    # nao deixou o recorte "b.dxf" orfao no meio do caminho
    assert conn.execute("SELECT COUNT(*) FROM reverse_eng_fichas").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM reverse_eng_recortes").fetchone()[0] == 1


def test_duplicata_e_por_obra_pavimento_classe_nao_so_nome(conn):
    """P1 do PIL e P1 da LAJ sao itens diferentes; mesmo pavimento em outra
    obra tambem nao colide."""
    criar_item_manual(conn, obra_name="Obra_A", pavimento="13_PAV", classe="PIL",
                       elemento_id="P1", recorte_path="a.dxf", bbox=(0, 0, 1, 1))
    criar_item_manual(conn, obra_name="Obra_A", pavimento="13_PAV", classe="LAJ",
                       elemento_id="P1", recorte_path="b.dxf", bbox=(0, 0, 1, 1))
    criar_item_manual(conn, obra_name="Obra_B", pavimento="13_PAV", classe="PIL",
                       elemento_id="P1", recorte_path="c.dxf", bbox=(0, 0, 1, 1))
    assert conn.execute("SELECT COUNT(*) FROM reverse_eng_fichas").fetchone()[0] == 3


def test_recorte_orfao_tambem_bloqueia_duplicata(conn):
    """reverse_eng_recortes NAO tem UNIQUE — a checagem é do código.

    Recorte sem ficha (órfão) ainda ocupa o nome: reusá-lo criaria dois
    recortes disputando o mesmo item na hora de montar o N3.
    """
    conn.execute(
        "INSERT INTO reverse_eng_recortes (obra_name, elemento_id, recorte_path, "
        "projeto_id, classe, status) VALUES (?,?,?,?,?,?)",
        ("O", "P1", "orfao.dxf", projeto_id_web("O", "13_PAV"), "PIL", "manual"),
    )
    assert item_ja_existe(
        conn, IdentidadeItem("O", "13_PAV", "PIL", "P1")
    )
    with pytest.raises(ItemDuplicado):
        criar_item_manual(conn, obra_name="O", pavimento="13_PAV", classe="PIL",
                           elemento_id="P1", recorte_path="novo.dxf", bbox=(0, 0, 1, 1))


def test_elemento_id_vazio_e_rejeitado(conn):
    with pytest.raises(ValueError):
        criar_item_manual(conn, obra_name="O", pavimento="13_PAV", classe="PIL",
                           elemento_id="   ", recorte_path="x.dxf", bbox=(0, 0, 1, 1))


# ── sugerir_proximo_nome ─────────────────────────────────────────────────────

def test_sugere_proximo_nome_pelo_maior_numero_ja_usado(conn):
    """P1..P35 e P41..P51: contar daria 46 e colidiria com P46. Tem de olhar o
    maior número, não a quantidade — é exatamente o padrão real do 13_PAV."""
    for n in list(range(1, 36)) + list(range(41, 52)):
        conn.execute(
            "INSERT INTO reverse_eng_fichas (obra_name, pavimento, classe, elemento_id) "
            "VALUES (?,?,?,?)",
            ("O", "13_PAV", "PIL", f"P{n}"),
        )
    assert sugerir_proximo_nome(conn, "O", "13_PAV", "PIL") == "P52"


def test_sugere_p1_quando_nao_ha_nenhum(conn):
    assert sugerir_proximo_nome(conn, "O", "13_PAV", "PIL") == "P1"


def test_sugestao_por_classe_usa_prefixo_certo(conn):
    assert sugerir_proximo_nome(conn, "O", "13_PAV", "LAJ") == "L1"
    assert sugerir_proximo_nome(conn, "O", "13_PAV", "FV") == "VF1"
    assert sugerir_proximo_nome(conn, "O", "13_PAV", "LV") == "V1"


def test_sugestao_nao_mistura_pavimentos(conn):
    conn.execute(
        "INSERT INTO reverse_eng_fichas (obra_name, pavimento, classe, elemento_id) "
        "VALUES ('O','14_PAV','PIL','P99')"
    )
    assert sugerir_proximo_nome(conn, "O", "13_PAV", "PIL") == "P1"


# ── P5 materializar_preview_n3 ───────────────────────────────────────────────

def test_caminho_preview_n3_mapeia_classe_sa_para_prefixo_fase6(tmp_path):
    assert caminho_preview_n3(tmp_path, "PIL", "P12").name == "PL_preview_P12.dxf"
    assert caminho_preview_n3(tmp_path, "LAJ", "L3").name == "LJ_preview_L3.dxf"
    assert caminho_preview_n3(tmp_path, "FV", "V301").name == "FV_preview_V301.dxf"
    assert caminho_preview_n3(tmp_path, "LV", "V10_A").name == "LV_preview_V10_A.dxf"
    assert "Fase-6_Execucao_CAD" in str(caminho_preview_n3(tmp_path, "PIL", "P1"))


def test_materializar_preview_n3_copia_recorte_para_path_canonic(tmp_path):
    src = tmp_path / "recorte.dxf"
    src.write_text("0\nSECTION\n", encoding="utf-8")
    dest = materializar_preview_n3(
        tmp_path / "obra",
        classe="PIL",
        elemento_id="P900",
        recorte_path=src,
    )
    assert dest.is_file()
    assert dest.name == "PL_preview_P900.dxf"
    assert dest.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")
    # original permanece (não move)
    assert src.is_file()


def test_materializar_preview_n3_recorte_ausente_falha(tmp_path):
    with pytest.raises(FileNotFoundError):
        materializar_preview_n3(
            tmp_path, classe="PIL", elemento_id="P1",
            recorte_path=tmp_path / "nao_existe.dxf",
        )
