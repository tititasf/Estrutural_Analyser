"""Testes do qa_session_index (D0/D1 do MASTERPLAN-MINIRAG-QA-N1).

Cobrem os guardrails de contrato: anti-leakage de fontes N2, independência de
layer, staleness falha-fechado e fidelidade da projeção B2. Usam fixtures
isoladas — nunca o DB real.
"""

import inspect
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import qa_session_index  # noqa: E402
from qa_session_index import (  # noqa: E402
    SessionIndex, _check_dxf_path_allowed, build_index,
)


@pytest.fixture()
def fixture_db(tmp_path):
    db = tmp_path / "fixture.vision"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, work_name TEXT);
        CREATE TABLE slabs (
            id INTEGER PRIMARY KEY, project_id TEXT, name TEXT, area REAL,
            points_json TEXT, type TEXT, links_json TEXT,
            validated_fields_json TEXT, issues_json TEXT, is_validated INTEGER,
            id_item INTEGER, validated_link_classes_json TEXT,
            na_fields_json TEXT, na_link_classes_json TEXT, na_reasons_json TEXT,
            pkl_path TEXT, extra_data_json TEXT
        );
        CREATE TABLE pillars (
            id INTEGER PRIMARY KEY, project_id TEXT, name TEXT, type TEXT,
            area REAL, points_json TEXT, sides_data_json TEXT, links_json TEXT,
            conf_map_json TEXT, validated_fields_json TEXT, issues_json TEXT,
            is_validated INTEGER, id_item INTEGER,
            validated_link_classes_json TEXT, na_fields_json TEXT,
            na_link_classes_json TEXT, na_reasons_json TEXT, pkl_path TEXT,
            extra_data_json TEXT
        );
        CREATE TABLE beams (
            id INTEGER PRIMARY KEY, project_id TEXT, name TEXT, data_json TEXT,
            is_validated INTEGER, id_item INTEGER, sides_data_json TEXT,
            links_json TEXT, validated_fields_json TEXT, issues_json TEXT,
            validated_link_classes_json TEXT, na_fields_json TEXT,
            na_link_classes_json TEXT, na_reasons_json TEXT, pkl_path TEXT,
            seg_a_laje_inf TEXT, seg_b_laje_inf TEXT, laje_inf_enriched_at TEXT,
            laje_inf_algorithm_version TEXT
        );
        """
    )
    con.execute("INSERT INTO projects VALUES ('proj-1','13_TEST','Obra_TEST')")
    links_l1 = {
        "laje_pilares_apoio": {"pillar_geom": [{"ficha": {"pillar_name": "P1"}}]},
        "laje_nivel": {"label": [{"source_slab": "L2", "text": "852.19"}]},
    }
    con.execute(
        "INSERT INTO slabs (id, project_id, name, id_item, is_validated, "
        "points_json, links_json) VALUES (1,'proj-1','L1',1,1,?,?)",
        (json.dumps([[0, 0], [10, 0], [10, 10], [0, 10]]), json.dumps(links_l1)),
    )
    con.execute(
        "INSERT INTO slabs (id, project_id, name, id_item, is_validated, "
        "points_json, links_json) VALUES (2,'proj-1','L2',2,1,'[]','{}')")
    con.execute(
        "INSERT INTO pillars (id, project_id, name, id_item, is_validated, "
        "links_json) VALUES (1,'proj-1','P1',1,1,'{}')")
    con.commit()
    con.close()
    return db


@pytest.fixture()
def fixture_db_b1(fixture_db):
    """Estende fixture_db com semantic_rag_kb + human_event_logs para D2."""
    con = sqlite3.connect(fixture_db)
    con.executescript(
        """
        CREATE TABLE semantic_rag_kb (
            id INTEGER PRIMARY KEY, classe TEXT, regra_semantica TEXT,
            obra_contexto TEXT, confianca REAL, created_at TEXT, tier TEXT,
            field_id TEXT, familia TEXT, pavimento TEXT
        );
        CREATE TABLE human_event_logs (
            log_id TEXT PRIMARY KEY, timestamp TEXT, obra_id TEXT,
            classe TEXT, item_id TEXT, campos_alterados TEXT,
            event_kind TEXT, status TEXT, tier TEXT, user_reason TEXT,
            approved_by TEXT, approved_at TEXT
        );
        """
    )
    con.execute(
        "INSERT INTO semantic_rag_kb (id, classe, regra_semantica, "
        "obra_contexto, confianca, created_at, tier) VALUES "
        "(1,'LAJ',?,'Obra_A','1.0','2026-01-01','T1')",
        (json.dumps({"text": "Nivel inferido nunca confirma campo sozinho"}),),
    )
    con.execute(
        "INSERT INTO semantic_rag_kb (id, classe, regra_semantica, "
        "obra_contexto, confianca, created_at, tier) VALUES "
        "(2,'LAJ',?,'Obra_B','1.0','2026-01-02',NULL)",
        (json.dumps({"text": "Vizinhanca ortogonal exige distancia minima"}),),
    )
    con.execute(
        "INSERT INTO semantic_rag_kb (id, classe, regra_semantica, "
        "obra_contexto, confianca, created_at, tier) VALUES "
        "(3,'PIL',?,'Obra_A','1.0','2026-01-03','T2')",
        (json.dumps({"text": "Face C/D invertida em pilar retangular"}),),
    )
    con.execute(
        "INSERT INTO human_event_logs (log_id, timestamp, obra_id, classe, "
        "item_id, campos_alterados, event_kind, status, tier, user_reason) "
        "VALUES (1,'2026-01-04','Obra_A','LAJ','L1','[\"laje_nivel\"]','edit',"
        "'APPROVED','T1','nivel corrigido apos revisao humana')")
    con.execute(
        "INSERT INTO human_event_logs (log_id, timestamp, obra_id, classe, "
        "item_id, campos_alterados, event_kind, status, tier, user_reason) "
        "VALUES ('2','2026-01-05','Obra_B','LAJ','L9','[\"note\"]','edit',"
        "'CAPTURED',NULL,NULL)")
    con.execute(
        "INSERT INTO human_event_logs (log_id, timestamp, obra_id, classe, "
        "item_id, campos_alterados, event_kind, status, tier, user_reason, "
        "approved_by, approved_at) VALUES "
        "('qa-rag-approval-qa-rag-deadbeef1234','2026-01-06','Obra_A','LAJ',"
        "'MULTI','[\"laje_nivel\"]','approval','APPROVED','T1',"
        "'Aprovacao humana do pacote QA ground truth','dono',"
        "'2026-01-06T00:00:00+00:00')")
    con.commit()
    con.close()
    return fixture_db


@pytest.fixture()
def fixture_dxf(tmp_path):
    import ezdxf
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "qualquer_layer"})
    msp.add_text("L1", dxfattribs={"insert": (5, 12), "layer": "outra"})
    msp.add_text("h=12", dxfattribs={"insert": (5, 8)})
    path = tmp_path / "pav_teste.dxf"
    doc.saveas(path)
    return path


def _build(tmp_path, fixture_db, fixture_dxf=None):
    out = tmp_path / "index"
    return out, build_index("proj-1", out, db_path=fixture_db,
                            pav_dxf=fixture_dxf)


# ── Anti-leakage: fontes N2/engenharia reversa recusadas ────────────────

@pytest.mark.parametrize("bad", [
    "D:/x/Fase-2_Triagem/recortes_reversos/a.dxf",
    "D:/x/RECORTES/a.dxf",
    "D:/x/reverse_eng/a.dxf",
    "D:/x/Fase-1/a.TRUE_GEOMETRY.pkl",
    "D:/x/Fase-1/a.dwg",
])
def test_anti_leakage_recusa_fontes_proibidas(bad):
    with pytest.raises(ValueError):
        _check_dxf_path_allowed(Path(bad))


def test_build_recusa_dxf_de_fase2(tmp_path, fixture_db, fixture_dxf):
    fase2 = tmp_path / "Fase-2_Triagem"
    fase2.mkdir()
    bad = fase2 / "recorte.dxf"
    bad.write_bytes(fixture_dxf.read_bytes())
    with pytest.raises(ValueError, match="anti-leakage"):
        build_index("proj-1", tmp_path / "idx", db_path=fixture_db, pav_dxf=bad)


# ── Independência de layer: layer nunca é filtro, só metadado ───────────

def test_api_b3_nao_expoe_filtro_de_layer():
    for method in (SessionIndex.b3_entities_near, SessionIndex.b3_texts_in_bbox,
                   SessionIndex.b3_entities_of_type):
        params = inspect.signature(method).parameters
        assert "layer" not in params, f"{method.__name__} não pode filtrar por layer"


def test_b3_layer_aparece_apenas_como_metadado(tmp_path, fixture_db, fixture_dxf):
    out, _ = _build(tmp_path, fixture_db, fixture_dxf)
    idx = SessionIndex(out)
    near = idx.b3_entities_near(5, 12, 5, types=["TEXT"])
    idx.close()
    assert near and near[0]["text_content"] == "L1"
    assert "layer_meta" in near[0]


# ── Staleness: qualquer mudança de fonte falha fechado ──────────────────

def test_stale_snapshot_n1_recusa_query(tmp_path, fixture_db):
    out, _ = _build(tmp_path, fixture_db)
    con = sqlite3.connect(fixture_db)
    con.execute("UPDATE slabs SET area=99.9 WHERE name='L1'")
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="STALE"):
        SessionIndex(out)


def test_stale_dxf_recusa_query(tmp_path, fixture_db, fixture_dxf):
    out, _ = _build(tmp_path, fixture_db, fixture_dxf)
    fixture_dxf.write_bytes(fixture_dxf.read_bytes() + b"\n")
    with pytest.raises(RuntimeError, match="STALE"):
        SessionIndex(out)


def test_fresh_apos_rebuild(tmp_path, fixture_db):
    out, _ = _build(tmp_path, fixture_db)
    con = sqlite3.connect(fixture_db)
    con.execute("UPDATE slabs SET area=99.9 WHERE name='L1'")
    con.commit()
    con.close()
    build_index("proj-1", out, db_path=fixture_db)
    idx = SessionIndex(out)
    assert idx.b2_item("L1")
    idx.close()


# ── B2: projeção fiel + grafo declarado ─────────────────────────────────

def test_b2_projecao_fiel_ao_db(tmp_path, fixture_db):
    out, _ = _build(tmp_path, fixture_db)
    idx = SessionIndex(out)
    items = idx.b2_item("L1")
    idx.close()
    assert len(items) == 1
    payload = items[0]["payload"]
    con = sqlite3.connect(fixture_db)
    con.row_factory = sqlite3.Row
    src = dict(con.execute("SELECT * FROM slabs WHERE name='L1'").fetchone())
    con.close()
    for col in ("name", "id_item", "is_validated", "points_json", "links_json"):
        assert payload[col] == src[col], f"divergência em {col}"


def test_b2_grafo_deriva_apenas_dos_links(tmp_path, fixture_db):
    out, manifest = _build(tmp_path, fixture_db)
    idx = SessionIndex(out)
    nb = idx.b2_neighbors("L1")
    idx.close()
    destinos = {e["dst"] for e in nb["outgoing"]}
    assert destinos == {"P1", "L2"}
    assert manifest["b2_edges"] == 2


# ── Citação: toda consulta registrada com hash do manifest ──────────────

def test_toda_consulta_logada_com_hash(tmp_path, fixture_db, fixture_dxf):
    out, manifest = _build(tmp_path, fixture_db, fixture_dxf)
    idx = SessionIndex(out)
    idx.b2_item("L1")
    idx.b2_neighbors("L1")
    idx.b3_entities_near(5, 12, 5)
    idx.close()
    log = out / "session_index_consultas.jsonl"
    entries = [json.loads(line) for line in
               log.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 3
    for entry in entries:
        assert entry["manifest_sha256"] == manifest["manifest_sha256"]
        assert entry["n1_fingerprint"] == manifest["n1_fingerprint_sha256"]


# ── D2: B1 (semântica) — fallback, same-origin, partição, staleness ─────

def test_b1_fallback_quando_embedder_indisponivel(tmp_path, fixture_db_b1, monkeypatch):
    def _boom():
        raise RuntimeError("modelo indisponível (offline)")
    monkeypatch.setattr(qa_session_index, "_local_embedder", _boom)
    out = tmp_path / "index"
    manifest = build_index("proj-1", out, db_path=fixture_db_b1)
    assert manifest["b1"]["enabled"] is True
    assert manifest["b1"]["degraded"] is True
    assert manifest["b1"]["entries"] == 5  # 3 semantic_rag_kb + 2 human_event_logs (log '2' sem motivo/aprovação, excluído)

    idx = SessionIndex(out)
    result = idx.b1_query("qualquer coisa", classe="LAJ")
    idx.close()
    assert result
    assert all(r["retrieval_method"] == "exact_partition_only" for r in result)


def test_b1_same_origin_flag(tmp_path, fixture_db_b1):
    out = tmp_path / "index"
    build_index("proj-1", out, db_path=fixture_db_b1)
    idx = SessionIndex(out)
    same = idx.b1_query(classe="LAJ", obra="Obra_A")
    idx.close()
    by_obra = {r["obra"]: r["same_origin"] for r in same}
    assert by_obra["Obra_A"] is True
    assert by_obra["Obra_B"] is False


def test_b1_partition_filtra_classe_antes_de_ranquear(tmp_path, fixture_db_b1):
    out = tmp_path / "index"
    build_index("proj-1", out, db_path=fixture_db_b1)
    idx = SessionIndex(out)
    result = idx.b1_query("face invertida", classe="PIL")
    idx.close()
    assert result and all(r["classe"] == "PIL" for r in result)


def test_b1_filtra_por_tier(tmp_path, fixture_db_b1):
    out = tmp_path / "index"
    build_index("proj-1", out, db_path=fixture_db_b1)
    idx = SessionIndex(out)
    result = idx.b1_query(classe="LAJ", tier=["T1"])
    idx.close()
    assert result and all(r["tier"] == "T1" for r in result)


def test_b1_consulta_semantica_recupera_vocabulario_diferente(tmp_path, fixture_db_b1):
    out = tmp_path / "index"
    manifest = build_index("proj-1", out, db_path=fixture_db_b1)
    assert manifest["b1"]["degraded"] is False, "modelo local deveria estar disponível/cacheado"
    idx = SessionIndex(out)
    result = idx.b1_query("laje muito perto uma da outra, distancia curta",
                          classe="LAJ", top_k=1)
    idx.close()
    assert result[0]["retrieval_method"] == "semantic_within_partition"
    assert "vizinhanca" in result[0]["text"].lower()


def test_b1_toda_consulta_logada(tmp_path, fixture_db_b1):
    out = tmp_path / "index"
    build_index("proj-1", out, db_path=fixture_db_b1)
    idx = SessionIndex(out)
    idx.b1_query(classe="LAJ")
    idx.close()
    log = out / "session_index_consultas.jsonl"
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    b1_entries = [e for e in entries if e["kind"] == "b1"]
    assert len(b1_entries) == 1
    assert b1_entries[0]["query"]["method"] in (
        "exact_partition_only", "semantic_within_partition")


def test_b1_stale_quando_nova_regra_e_gravada(tmp_path, fixture_db_b1):
    out = tmp_path / "index"
    build_index("proj-1", out, db_path=fixture_db_b1)
    con = sqlite3.connect(fixture_db_b1)
    con.execute(
        "INSERT INTO semantic_rag_kb (id, classe, regra_semantica, "
        "obra_contexto, created_at) VALUES (4,'LAJ',?,'Obra_A','2026-01-06')",
        (json.dumps({"text": "regra nova adicionada depois do build"}),))
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="STALE"):
        SessionIndex(out)


def test_b1_ausente_no_fixture_sem_b1_nao_quebra(tmp_path, fixture_db):
    """fixture_db (sem semantic_rag_kb/human_event_logs) não deve falhar o build."""
    out = tmp_path / "index"
    manifest = build_index("proj-1", out, db_path=fixture_db)
    assert manifest["b1"]["entries"] == 0
    idx = SessionIndex(out)
    assert idx.b1_query(classe="LAJ") == []
    idx.close()


# ── Fix de qualidade pós-MR-1: candidate_id navegável ────────────────────

def test_b1_aprovacao_humana_traz_candidate_id_navegavel(tmp_path, fixture_db_b1):
    """MR-1 (2026-07-19) achou o resumo de aprovação em lote fino demais
    ("aprovado, sem detalhe"). Corrigido: extrai candidate_id do log_id
    (padrão "qa-rag-approval-<candidate_id>") e inclui approved_by/approved_at,
    virando um ponteiro buscável em vez de só afirmar que "existe" aprovação.
    """
    out = tmp_path / "index"
    build_index("proj-1", out, db_path=fixture_db_b1)
    idx = SessionIndex(out)
    result = idx.b1_query(classe="LAJ", item="MULTI")
    idx.close()
    assert result
    entry = next(r for r in result if r["source_table"] == "human_event_logs"
                 and r["item"] == "MULTI")
    assert "candidate_id=qa-rag-deadbeef1234" in entry["text"]
    assert "aprovado por dono" in entry["text"]
    assert "2026-01-06T00:00:00+00:00" in entry["text"]


def test_b1_aprovacao_sem_padrao_de_log_id_nao_quebra():
    from qa_session_index import _b1_row_text_human_event_logs
    text = _b1_row_text_human_event_logs({
        "classe": "LAJ", "item_id": "L1", "log_id": "42",
        "status": "APPROVED", "approved_by": "dono",
        "approved_at": "2026-01-01", "user_reason": None,
        "campos_alterados": None,
    })
    assert "candidate_id=" not in text
    assert "aprovado por dono" in text
