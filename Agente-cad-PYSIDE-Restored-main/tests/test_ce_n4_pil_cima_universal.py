"""
tests/test_ce_n4_pil_cima_universal.py
========================================
Checagem de generalização do "motor universal" da zona CIMA
(scripts/gerar_pl_dxf_stog.py::draw_cima) para itens com perfis variados
de comprimento/grade_1 — não só P1.

Casos escolhidos (Fase-4_Sincronizacao/JSON_Pilares):
  P1  comp=66  grade_1=88   (grade_1 == comp+22 — caso "feliz")
  P3  comp=60  grade_1=88   (grade_1 != comp+22, tem grade_1_div_a/b)
  P9  comp=104 grade_1=82   (grade_1 < comp — confirma que CIMA não depende de grade_1)
  P15 comp=45  grade_1=122  (pilar quadrado 45x45)

A fix "primordial" usa hc=comp/2 e chapa_full_w=comp+22 (constantes SCR fixas),
independentes de grade_1 — este teste renderiza o DXF real de cada item no
widget LevelColumn (CE) e confere que a cota central = comprimento (comp).

Executar:
    python -m pytest tests/test_ce_n4_pil_cima_universal.py -v -s
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

OBRA_DIR  = pathlib.Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
N4_DIR    = OBRA_DIR / "Fase-6_Execucao_CAD"
JSON_DIR  = OBRA_DIR / "Fase-4_Sincronizacao" / "JSON_Pilares"


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
def cima_view(qtbot):
    from src.ui.modules.comparison_engine import DXFVectorView
    from src.ui.theme import Colors

    view = DXFVectorView(bg=Colors.BG_DEEP)
    view.resize(900, 700)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view, timeout=5000)
    QApplication.processEvents()
    return view


@pytest.mark.parametrize("item_id", ["P1", "P3", "P9", "P15"])
def test_cima_universal(cima_view, qtbot, item_id):
    dxf_path = N4_DIR / f"PL_CIMA_preview_{item_id}.dxf"
    assert dxf_path.exists(), f"DXF não encontrado: {dxf_path}"

    pj = json.loads((JSON_DIR / f"{item_id}.json").read_text(encoding="utf-8"))
    comp = pj.get("comprimento")
    grade_1 = pj.get("grade_1")
    print(f"\n  [{item_id}] comp={comp} grade_1={grade_1}")

    cima_view.load_dxf(str(dxf_path), None)
    qtbot.waitSignal(cima_view.ready, timeout=30000, raising=False)
    for _ in range(15):
        qtbot.wait(200)
        QApplication.processEvents()

    cima_view._fit()
    cima_view.update()
    QApplication.processEvents()

    grab_screenshot(cima_view, f"ce_n4_cima_universal_{item_id}")

    # cota central deve exibir o valor de `comprimento` (concreto interno)
    import ezdxf
    doc = ezdxf.readfile(str(dxf_path))
    dim_texts = []
    for e in doc.modelspace().query("DIMENSION"):
        try:
            txt = e.dxf.text
        except Exception:
            txt = ""
        m = e.get_measurement()
        dim_texts.append((txt, m))
    print(f"  [DIMS] {dim_texts}")

    # draw_cima desenha tudo escalado ×2 em torno de (ox,oy) — a cota central
    # do concreto (sem texto override, '<>') deve medir comprimento*2
    measured = [round(m) for (_t, m) in dim_texts]
    assert round(comp * 2) in measured, (comp, dim_texts)
