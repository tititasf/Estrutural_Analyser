"""Testes da base de conhecimento (scripts/kb) — sem modelo real: embedder falso."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "kb"))
import kb_build  # noqa: E402
import kb_comum  # noqa: E402
import kb_query  # noqa: E402


def test_fatiar_respeita_titulos_e_limite():
    md = "# Doc\n\n## Seção A\n\n" + ("palavra " * 200) + "\n\n## Seção B\n\ntexto curto de B com mais de quarenta caracteres\n"
    partes = kb_comum.fatiar_markdown(md, max_chars=300)
    assert all(len(t) <= 600 for _, t in partes)
    assert any(s == "Doc > Seção A" for s, _ in partes)
    assert partes[-1][0] == "Doc > Seção B"


def test_fatiar_nao_trata_comentario_de_codigo_como_titulo():
    md = "# Doc\n\n```bash\n# isto é comentário\necho oi\n```\n\ntexto depois do bloco de código aqui\n"
    assert all("comentário" not in s for s, _ in kb_comum.fatiar_markdown(md))


def test_detectar_classes():
    assert kb_comum.detectar_classes("docs/SA-ANALISE/CLASSES/PIL.md", "", "") == ",PIL,"
    assert kb_comum.detectar_classes("x.md", "Laterais de viga", "") == ",LV,"
    assert kb_comum.detectar_classes("x.md", "", "uma laje só") == ""  # 1 menção no texto não basta


def test_vetor_de_linha_de_tabela_sem_cabecalho_nem_barras():
    txt = "| ID | Data | Decisão |\n| D-48 | — | G10: lados A e B decidem Para/Passa |"
    v = kb_comum.texto_para_vetor("Decisões", "LV", txt)
    assert "ID" not in v and "|" not in v
    assert "D-48 ; G10: lados A e B decidem Para/Passa" in v
    assert kb_comum.texto_para_vetor("T", "", "texto sem tabela") == "T\ntexto sem tabela"


def test_linhas_de_tabela_carregam_cabecalho_e_secao():
    md = "## Processo\n\n| ID | Decisão |\n|---|---|\n| D-01 | G2 não sela |\n| D-02 | sem API |\n\ntexto\n"
    linhas = kb_build._linhas_de_tabela(md)
    assert [l[2] for l in linhas] == ["| D-01 | G2 não sela |", "| D-02 | sem API |"]
    assert all(s == "Processo" and c == "| ID | Decisão |" for s, c, _ in linhas)


class _FakeEmb(kb_comum.Embedder):
    nome, dim = "fake", 8

    def codificar(self, textos, consulta=False):
        out = []
        for t in textos:
            v = np.zeros(8, dtype=np.float32)
            for w in t.lower().split():
                v[hash(w) % 8] += 1
            out.append(v / max(np.linalg.norm(v), 1e-9))
        return np.array(out, dtype=np.float32)


@pytest.fixture
def indice(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_build, "criar_embedder", lambda nome: _FakeEmb())
    monkeypatch.setattr(kb_query, "criar_embedder", lambda nome: _FakeEmb())
    kb_query._EMB_CACHE.clear()
    db = tmp_path / "kb.sqlite"
    chunks = [
        kb_build._chunk("global", "decisao", "docs/D.md", "Decisões", "LV", "canonico", "T1", "2026-09-20", 0,
                        "G9: o recuo de 11 é do Para; o Passa não recua"),
        kb_build._chunk("global", "doc", "docs/H.md", "Velho", "LV", "historico", None, "2026-06-01", 0,
                        "recuo de 11 discutido antes da decisão"),
        kb_build._chunk("global", "doc", "docs/L.md", "Laje", "hachura", "ativo", None, "2026-08-01", 0,
                        "hachura de apoio da laje nos apoios"),
    ]
    kb_build.gravar(db, chunks, "fake", "global", {})
    monkeypatch.setattr(kb_query, "GLOBAL_DB", db)
    return db


def test_busca_hibrida_prefere_canonico_e_filtra(indice):
    res = kb_query.buscar("recuo de 11 no Passa", k=3)
    assert res[0]["path"] == "docs/D.md"  # decisão canônica vence o histórico
    assert kb_query.buscar("recuo de 11", k=3, sem_historico=True)[-1]["status"] != "historico"
    assert {r["path"] for r in kb_query.buscar("hachura", k=3, classe="LAJ")} == {"docs/L.md"}


def test_rebuild_reusa_vetores_do_cache(indice, monkeypatch):
    chamadas = []

    class Conta(_FakeEmb):
        def codificar(self, textos, consulta=False):
            chamadas.append(len(textos))
            return super().codificar(textos, consulta)

    monkeypatch.setattr(kb_build, "criar_embedder", lambda nome: Conta())
    import sqlite3
    con = sqlite3.connect(indice)
    rows = con.execute("SELECT id, escopo, tipo, path, titulo, secao, status, tier, classes, data, ordem, texto "
                       "FROM chunks").fetchall()
    con.close()
    cols = ("id", "escopo", "tipo", "path", "titulo", "secao", "status", "tier", "classes", "data", "ordem", "texto")
    kb_build.gravar(indice, [dict(zip(cols, r)) for r in rows], "fake", "global", {})
    assert chamadas == []  # nada mudou → nenhum embedding recalculado
