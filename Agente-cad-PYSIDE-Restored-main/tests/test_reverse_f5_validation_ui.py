import json

from PySide6.QtCore import Qt

from src.ui.modules.diagnostic_reverse_hub import _CenterPanel


def _load(panel, *, status, rag_indexed=0):
    panel.load_ficha_granular(
        json.dumps({"comprimento": 100, "largura": 20}),
        classe="PIL",
        confianca=0.9,
        elemento_id="P1",
        context={
            "ficha_id": 1,
            "obra_name": "Obra_X",
            "pavimento": "1_PAV",
            "classe": "PIL",
            "elemento_id": "P1",
            "recorte_path": "P1.dxf",
            "status": status,
            "rag_indexed": rag_indexed,
        },
    )


def test_f5_ui_distinguishes_quarantine_validated_and_revoked(qtbot):
    panel = _CenterPanel()
    qtbot.addWidget(panel)

    _load(panel, status="draft")
    assert "T0" in panel._ficha_status.text()
    assert panel._btn_validate_ficha.isEnabled()
    assert not panel._btn_revoke_ficha.isEnabled()

    _load(panel, status="aprovado", rag_indexed=1)
    assert "T1" in panel._ficha_status.text()
    assert "indexado" in panel._ficha_status.text()
    assert panel._btn_validate_ficha.isEnabled()
    assert panel._btn_revoke_ficha.isEnabled()

    _load(panel, status="revoked")
    assert "TX" in panel._ficha_status.text()
    assert panel._btn_validate_ficha.isEnabled()
    assert not panel._btn_revoke_ficha.isEnabled()


def test_f5_buttons_emit_only_explicit_validation_intent(qtbot):
    panel = _CenterPanel()
    qtbot.addWidget(panel)
    _load(panel, status="draft")

    with qtbot.waitSignal(panel.ficha_validation_requested) as signal:
        qtbot.mouseClick(panel._btn_validate_ficha, Qt.LeftButton)
    assert signal.args == [True]

    _load(panel, status="aprovado", rag_indexed=1)
    with qtbot.waitSignal(panel.ficha_validation_requested) as signal:
        qtbot.mouseClick(panel._btn_revoke_ficha, Qt.LeftButton)
    assert signal.args == [False]
