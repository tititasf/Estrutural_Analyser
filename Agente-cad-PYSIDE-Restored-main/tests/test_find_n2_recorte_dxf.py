import sqlite3
from pathlib import Path

from src.ui.widgets.pre_validation_dialog import PreValidationDialog


def test_analysis_state_path_is_scoped_for_headless_class():
    dialog = PreValidationDialog.__new__(PreValidationDialog)
    dialog._obra = 'Obra_TREINO_1'
    dialog._pavimento = '13_PAV'
    assert dialog._analysis_state_path().endswith('estado_13_PAV.json')
    dialog._headless_run_scope = 'pilares'
    assert dialog._analysis_state_path().endswith('estado_13_PAV_pilares.json')


def _make_db(tmp_path: Path) -> str:
    db_path = str(tmp_path / "project_data.vision")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE reverse_eng_recortes (
            id INTEGER PRIMARY KEY,
            obra_name TEXT NOT NULL,
            elemento_id TEXT NOT NULL,
            recorte_path TEXT NOT NULL,
            classe TEXT,
            status TEXT DEFAULT 'manual',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    return db_path


def _touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("0\nEOF\n", encoding="ascii")
    return str(path)


def test_prefers_aprovado_over_newer_auto_recorte(tmp_path: Path):
    """Reproduz o bug real: um recorte 'auto_aprovado' mais recente (ou de
    outra pasta com nome que ordena depois em glob) nunca deve vencer o
    recorte 'aprovado' — mesmo que tenha timestamp de criação mais antigo
    no arquivo, o registro no DB é a fonte de verdade."""
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)

    aprovado_path = _touch(tmp_path / "pasta_aprovada" / "LAJ_L301_motor_100.dxf")
    auto_path = _touch(tmp_path / "pasta_auto_motor" / "LAJ_L301_motor_999.dxf")

    conn.execute(
        "INSERT INTO reverse_eng_recortes "
        "(obra_name, elemento_id, classe, status, recorte_path, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Obra_TESTE", "L301", "LAJ", "auto_aprovado", auto_path, "2026-01-02T00:00:00"),
    )
    conn.execute(
        "INSERT INTO reverse_eng_recortes "
        "(obra_name, elemento_id, classe, status, recorte_path, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Obra_TESTE", "L301", "LAJ", "aprovado", aprovado_path, "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    dialog = PreValidationDialog.__new__(PreValidationDialog)
    dialog._obra = "Obra_TESTE"
    dialog._db_path = db_path

    result = dialog._find_n2_recorte_dxf("LAJ", "L301")
    assert result == aprovado_path


def test_falls_back_to_most_recent_when_no_aprovado_exists(tmp_path: Path):
    db_path = _make_db(tmp_path)
    conn = sqlite3.connect(db_path)
    only_path = _touch(tmp_path / "so_motor" / "LAJ_L999_motor_1.dxf")
    conn.execute(
        "INSERT INTO reverse_eng_recortes "
        "(obra_name, elemento_id, classe, status, recorte_path, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Obra_TESTE", "L999", "LAJ", "motor", only_path, "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    dialog = PreValidationDialog.__new__(PreValidationDialog)
    dialog._obra = "Obra_TESTE"
    dialog._db_path = db_path

    assert dialog._find_n2_recorte_dxf("LAJ", "L999") == only_path


def test_returns_empty_when_db_missing_and_no_files_on_disk(tmp_path: Path):
    dialog = PreValidationDialog.__new__(PreValidationDialog)
    dialog._obra = "Obra_Sem_Nada"
    dialog._db_path = str(tmp_path / "nao_existe.vision")

    assert dialog._find_n2_recorte_dxf("LAJ", "L1") == ""
