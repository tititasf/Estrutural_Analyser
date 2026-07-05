from types import SimpleNamespace

import src.ui.modules.comparison_engine as comparison_engine
from src.ui.modules.comparison_engine import (
    ComparisonEngineModule,
    _resolve_open_dxf_paths,
)


def test_n2_abre_o_recorte_selecionado(tmp_path):
    recorte = tmp_path / "PIL_P5_motor.dxf"
    recorte.write_text("n2", encoding="utf-8")

    paths = _resolve_open_dxf_paths(
        1, tmp_path, "PL", "P5", selected_recorte_path=str(recorte)
    )

    assert paths == [recorte]


def test_pil_n4_abre_combinado_com_as_tres_zonas(tmp_path):
    n4_dir = tmp_path / "Fase-6_Execucao_CAD" / "n4"
    n4_dir.mkdir(parents=True)
    combined = n4_dir / "PL_preview_P5.dxf"
    combined.write_text("CIMA ABCD GRADES", encoding="utf-8")

    paths = _resolve_open_dxf_paths(3, tmp_path, "PL", "P5")

    assert paths == [combined]


def test_pil_n4_usa_splits_sem_cair_em_n3(tmp_path):
    n4_dir = tmp_path / "Fase-6_Execucao_CAD" / "n4"
    n4_dir.mkdir(parents=True)
    expected = []
    for zone in ("CIMA", "ABCD", "GRADES"):
        path = n4_dir / f"PL_{zone}_preview_P5.dxf"
        path.write_text(zone, encoding="utf-8")
        expected.append(path)
    n3 = tmp_path / "Fase-6_Execucao_CAD" / "PL_CIMA_preview_P5.dxf"
    n3.parent.mkdir(parents=True, exist_ok=True)
    n3.write_text("N3", encoding="utf-8")

    paths = _resolve_open_dxf_paths(3, tmp_path, "PL", "P5", str(n3))

    assert paths == expected


def test_pil_para_passa_salva_uma_vez_e_sincroniza_n2_n4(monkeypatch):
    saved = []
    monkeypatch.setattr(
        comparison_engine,
        "save_para_passa",
        lambda *args: saved.append(args),
    )

    class Button:
        def __init__(self):
            self.checked = None

        def setChecked(self, checked):
            self.checked = checked

    def column():
        return SimpleNamespace(
            _para_passa_row=SimpleNamespace(isVisible=lambda: True),
            _para_btn=Button(),
            _passa_btn=Button(),
            _attention_loading=False,
        )

    columns = [column() for _ in range(4)]
    statuses = []
    fake = SimpleNamespace(
        fase8_panel=SimpleNamespace(
            cmb_obra=SimpleNamespace(
                currentData=lambda: "Obra_TREINO_1",
                currentText=lambda: "",
            ),
            current_pav_key="13_PAV",
        ),
        tri_level=SimpleNamespace(_columns=columns),
        nav_sidebar=SimpleNamespace(
            set_status=lambda *args: statuses.append(args),
            refresh_tree=lambda: None,
        ),
    )

    ComparisonEngineModule._save_pil_para_passa_and_sync(fake, "P5", "passa")

    assert saved == [("Obra_TREINO_1", "13_PAV", "PIL", "P5", "passa")]
    for index in (1, 3):
        assert columns[index]._para_btn.checked is False
        assert columns[index]._passa_btn.checked is True
        assert columns[index]._attention_loading is False
    assert "Vigas Passam" in statuses[0][0]
