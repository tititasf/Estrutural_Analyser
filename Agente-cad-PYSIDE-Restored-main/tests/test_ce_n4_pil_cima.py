"""
tests/test_ce_n4_pil_cima.py
=============================
Valida via o widget real do Comparison Engine (LevelColumn.switch_to_pil_zones +
DXFVectorView) que o N4 (zona CIMA) do pilar P1 — Obra_TREINO_1 / 13_PAV — exibe
as cotas corrigidas pelo fix "primordial" (concreto interno=66, externo/grade_1=88)
após a regeneração de scripts/gerar_pl_dxf_stog.py.

Usa o widget real LevelColumn (o mesmo do painel N4 da CE) carregando os DXFs de
produção em DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/PL_{ZONE}_preview_P1.dxf,
sem disparar a navegação obra/pav completa da CE (que dispara análise pesada do N1
em background e não é necessária para este teste).

Executar:
    cd D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main
    python -m pytest tests/test_ce_n4_pil_cima.py -v -s

Screenshot salvo em: tests/screenshots/
"""

import sys
import json
import pathlib

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pytest
from PySide6.QtWidgets import QApplication

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SCREENSHOT_DIR = ROOT / "tests" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

OBRA_DIR = pathlib.Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
N4_DIR   = OBRA_DIR / "Fase-6_Execucao_CAD"
FASE4_P1 = OBRA_DIR / "Fase-4_Sincronizacao" / "JSON_Pilares" / "P1.json"


def grab_screenshot(widget, name: str) -> pathlib.Path:
    out = SCREENSHOT_DIR / f"{name}.png"
    try:
        QApplication.processEvents()
        pixmap = widget.grab()
        pixmap.save(str(out), "PNG")
        size_kb = out.stat().st_size // 1024 if out.exists() else 0
        print(f"\n  [SHOT] {out.name}  ({size_kb} KB)")
    except Exception as exc:
        print(f"\n  [WARN] screenshot falhou ({name}): {exc}")
    return out


@pytest.fixture
def n4_col(qtbot):
    from src.ui.modules.comparison_engine import LevelColumn

    col = LevelColumn(
        "N4", "N4 — Robô (ER)", "#2d1a47", "#a855f7",
        "DXF gerado pelo robô a partir da ficha N2", mode='dxf',
    )
    col.resize(1700, 700)
    qtbot.addWidget(col)
    col.show()
    qtbot.waitExposed(col, timeout=5000)
    QApplication.processEvents()
    return col


def test_n4_pil_cima_p1_dims(n4_col, qtbot):
    zone_paths = {
        zone: N4_DIR / f"PL_{zone}_preview_P1.dxf"
        for zone in ("ABCD", "CIMA", "GRADES")
    }
    for zone, p in zone_paths.items():
        assert p.exists(), f"DXF da zona {zone} não encontrado: {p}"

    pj = json.loads(FASE4_P1.read_text(encoding="utf-8"))

    try:
        from src.core.services.dxf_generator import PIL_ZONE_FIELDS
    except Exception:
        PIL_ZONE_FIELDS = {
            'ABCD':   ['nome', 'comprimento', 'largura', 'altura', 'pd_pavimento_cm'],
            'CIMA':   ['nome', 'comprimento', 'largura', 'grade_1'],
            'GRADES': ['nome', 'comprimento', 'largura', 'altura', 'grade_1', 'grade_2'],
        }
    zone_fichas = {zone: pj for zone in PIL_ZONE_FIELDS}

    # ── Carrega os 3 painéis CIMA|ABCD|GRADES no widget real da CE ──────
    n4_col.switch_to_pil_zones(zone_paths, pj, zone_fichas)

    # Aguarda o load assíncrono (DXFLoadWorker) de cada DXFVectorView
    for zone, view in n4_col._zone_views.items():
        qtbot.waitSignal(view.ready, timeout=30000, raising=False)
    for _ in range(20):
        qtbot.wait(200)
        QApplication.processEvents()

    grab_screenshot(n4_col, "ce_n4_pil_p1_3panel")

    # ── Zoom no painel CIMA isolado, para inspeção visual das cotas ─────
    cima_view = n4_col._zone_views['CIMA']
    cima_view.resize(900, 700)
    cima_view._fit()
    cima_view.update()
    QApplication.processEvents()
    qtbot.wait(200)
    grab_screenshot(cima_view, "ce_n4_pil_p1_cima_zoom")

    # ── Valida ficha da zona CIMA (concreto interno=66 / externo grade_1=88) ──
    cima_tbl = n4_col._zone_tables['CIMA']
    valores = {}
    for r in range(cima_tbl.rowCount()):
        campo = cima_tbl.item(r, 0).text()
        valor = cima_tbl.item(r, 1).text()
        valores[campo] = valor
    print(f"\n  [FICHA CIMA] {valores}")

    assert valores.get('comprimento') == '66.0', valores
    assert valores.get('grade_1') == '88.0', valores
