# -*- coding: utf-8 -*-
"""
test_visual_n2_n4.py — Validacao visual N2 vs N4 ABCD PIL (3 camadas)

Camada 1 — geometrica  : pytest puro, sem Qt, sem render
Camada 2 — ezdxf render: renderiza DXF -> PNG via ezdxf drawing addon, salva comparacao
Camada 3 — Qt offscreen: instancia DXFVectorView real com QT_QPA_PLATFORM=offscreen,
            carrega DXF, captura widget.grab(), salva PNG, computa pixel-diff

Uso:
    pytest scripts/arete/test_visual_n2_n4.py -v
    # Outputs em scripts/arete/visual_output/
"""
import os
# DEVE ser antes de qualquer import Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import json
import sqlite3
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import numpy as np

# ── paths ──────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent.parent          # repo root
SCRIPTS  = Path(__file__).parent.parent
ARETE    = Path(__file__).parent

sys.path.insert(0, str(ARETE))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "src"))

from arete_config import DB_PATH, DADOS_OBRAS, PAV_13

OBRA     = "Obra_TREINO_1"
OBRA_DIR = DADOS_OBRAS / OBRA
GERADOR  = SCRIPTS / "gerar_pl_dxf_stog.py"
OUT_DIR  = ARETE / "visual_output"
OUT_DIR.mkdir(exist_ok=True)

TOL_CM        = 2.0
WIDGET_W, WIDGET_H = 480, 700   # tamanho do widget para render Qt
TEST_ITEMS    = ["P1", "P11"]


# ══════════════════════════════════════════════════════════════════════════
# Helpers compartilhados
# ══════════════════════════════════════════════════════════════════════════

def _db_recorte(item_id: str, pav: str = PAV_13) -> Path | None:
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()
    # Deriva pav da ficha mais recente se nao informado
    if not pav:
        cur.execute("SELECT pavimento FROM reverse_eng_fichas "
                    "WHERE obra_name=? AND classe='PIL' AND elemento_id=? ORDER BY id DESC LIMIT 1",
                    (OBRA, item_id))
        row = cur.fetchone(); pav = row[0] if row else None
    cur.execute("SELECT recorte_path FROM reverse_eng_fichas "
                "WHERE obra_name=? AND classe='PIL' AND elemento_id=? AND pavimento=? "
                "ORDER BY id DESC LIMIT 1", (OBRA, item_id, pav or ""))
    row = cur.fetchone(); conn.close()
    if row and row[0]:
        p = Path(row[0]); return p if p.exists() else None
    return None


def _db_ficha(item_id: str) -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()
    cur.execute("SELECT campos_json FROM reverse_eng_fichas "
                "WHERE obra_name=? AND classe='PIL' AND elemento_id=? ORDER BY id DESC LIMIT 1",
                (OBRA, item_id))
    row = cur.fetchone(); conn.close()
    return json.loads(row[0]) if row and row[0] else {}


def _generate_n4(item_id: str, zone: str = "abcd") -> Path | None:
    """Gera DXF N4 via gerar_pl_dxf_stog.py com ficha N2 + pd_pavimento_cm."""
    campos = {k: v for k, v in _db_ficha(item_id).items() if not k.startswith("_")}
    if not campos.get("pd_pavimento_cm"):
        pj = OBRA_DIR / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item_id}.json"
        if pj.exists():
            v = json.loads(pj.read_text("utf-8")).get("pd_pavimento_cm")
            if v: campos["pd_pavimento_cm"] = float(v)

    tmp = Path(tempfile.gettempdir()) / f"vis_n4_PIL_{item_id}"
    if tmp.exists(): shutil.rmtree(tmp)
    jdir = tmp / "Fase-4_Sincronizacao" / "JSON_Pilares"; jdir.mkdir(parents=True)
    (tmp / "Fase-6_Execucao_CAD").mkdir(parents=True)
    (jdir / f"{item_id}.json").write_text(
        json.dumps(campos, indent=2, ensure_ascii=False), encoding="utf-8")

    subprocess.run(
        [sys.executable, str(GERADOR), "--obra", str(tmp), "--item", item_id, "--zone", zone],
        capture_output=True, timeout=30)
    out = tmp / "Fase-6_Execucao_CAD" / f"PL_{zone.upper()}_preview_{item_id}.dxf"
    return out if out.exists() else None


def _all_ys(dxf_path: Path) -> list[float]:
    import ezdxf
    doc = ezdxf.readfile(str(dxf_path))
    ys  = []
    for e in doc.modelspace():
        if e.dxftype() == "LINE":
            ys += [e.dxf.start.y, e.dxf.end.y]
        elif e.dxftype() == "LWPOLYLINE":
            ys += [p[1] for p in e.get_points()]
    return ys


def _h_divs_rel(dxf_path: Path) -> set[float]:
    import ezdxf
    doc = ezdxf.readfile(str(dxf_path))
    all_ys, h_ys = [], []
    for e in doc.modelspace():
        if e.dxftype() == "LINE":
            all_ys += [e.dxf.start.y, e.dxf.end.y]
            if abs(e.dxf.start.y - e.dxf.end.y) < 0.5:
                h_ys.append(e.dxf.start.y)
        elif e.dxftype() == "LWPOLYLINE":
            pts = list(e.get_points()); all_ys += [p[1] for p in pts]
            if len(pts) == 2 and abs(pts[0][1]-pts[1][1]) < 0.5:
                h_ys.append(pts[0][1])
    y0 = min(all_ys) if all_ys else 0
    return {round(y - y0, 1) for y in h_ys}


# ══════════════════════════════════════════════════════════════════════════
# CAMADA 1 — Geometrica (sem Qt, sem render)
# ══════════════════════════════════════════════════════════════════════════

EXPECTED_DIVS = {0.0, 2.0, 124.0, 197.0, 221.0, 262.0, 321.0}

class TestGeometrica:
    """Verifica que o N4 gerado tem a geometria correta sem precisar de Qt."""

    @pytest.mark.parametrize("item_id", TEST_ITEMS)
    def test_n4_gera(self, item_id):
        n4 = _generate_n4(item_id)
        assert n4 and n4.stat().st_size > 0, f"{item_id}: N4 nao gerado"

    @pytest.mark.parametrize("item_id", TEST_ITEMS)
    def test_n4_span_321(self, item_id):
        n4 = _generate_n4(item_id); assert n4
        ys = _all_ys(n4)
        span = round(max(ys) - min(ys), 1)
        assert abs(span - 321.0) <= TOL_CM, f"{item_id}: span N4={span} != 321"

    @pytest.mark.parametrize("item_id", TEST_ITEMS)
    def test_n4_divisores(self, item_id):
        n4 = _generate_n4(item_id); assert n4
        divs = _h_divs_rel(n4)
        miss = [d for d in sorted(EXPECTED_DIVS)
                if not any(abs(div-d) <= TOL_CM for div in divs)]
        assert not miss, f"{item_id}: divisores ausentes {miss}. Encontrados: {sorted(divs)}"

    @pytest.mark.parametrize("item_id", TEST_ITEMS)
    def test_n2_recorte_pav_correto(self, item_id):
        p = _db_recorte(item_id)
        assert p, f"{item_id}: recorte N2 13_PAV nao encontrado"
        assert "13" in p.parent.name, (
            f"{item_id}: recorte N2 nao e do 13 PAV: {p.parent.name}")

    @pytest.mark.parametrize("item_id", TEST_ITEMS)
    def test_n2_tem_cota_321(self, item_id):
        import ezdxf
        p = _db_recorte(item_id); assert p
        doc = ezdxf.readfile(str(p))
        nums = set()
        for e in doc.modelspace():
            if e.dxftype() in ("TEXT","MTEXT"):
                t = (e.dxf.text if e.dxftype()=="TEXT" else e.text).strip()
                try: nums.add(round(float(t.replace(",",".")),1))
                except: pass
        assert 321.0 in nums, f"{item_id}: cota 321 ausente no N2 (13_PAV). Textos: {sorted(nums)}"


# ══════════════════════════════════════════════════════════════════════════
# CAMADA 2 — ezdxf render (PNG sem Qt)
# ══════════════════════════════════════════════════════════════════════════

def _render_dxf_png(dxf_path: Path, out_png: Path, title: str = "",
                    size_px: tuple[int,int] = (400, 600)) -> Path:
    """Renderiza DXF como PNG via ezdxf drawing + matplotlib (sem Qt)."""
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    fig = plt.figure(figsize=(size_px[0]/100, size_px[1]/100), dpi=100)
    ax  = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#0d0d1a")
    fig.patch.set_facecolor("#0d0d1a")

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True)

    if title:
        ax.set_title(title, color="white", fontsize=9, pad=3)
    ax.set_aspect("equal")
    ax.axis("off")
    plt.savefig(str(out_png), dpi=100, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_png


def _side_by_side_png(left: Path, right: Path, out: Path,
                      label_l: str = "N2", label_r: str = "N4") -> Path:
    """Junta dois PNGs lado a lado com labels e salva comparacao."""
    from PIL import Image, ImageDraw, ImageFont
    img_l = Image.open(left).convert("RGB")
    img_r = Image.open(right).convert("RGB")

    # Normaliza altura
    h = max(img_l.height, img_r.height)
    if img_l.height != h:
        img_l = img_l.resize((img_l.width, h))
    if img_r.height != h:
        img_r = img_r.resize((img_r.width, h))

    gap     = 6
    bar     = 28
    canvas  = Image.new("RGB", (img_l.width + img_r.width + gap, h + bar), (20,20,30))
    canvas.paste(img_l, (0, bar))
    canvas.paste(img_r, (img_l.width + gap, bar))

    draw = ImageDraw.Draw(canvas)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    draw.text((img_l.width//2 - 20, 6), label_l, fill=(100,220,100), font=font)
    draw.text((img_l.width + gap + img_r.width//2 - 20, 6), label_r,
              fill=(168,85,247), font=font)
    canvas.save(str(out))
    return out


def _pixel_diff(png_a: Path, png_b: Path,
                size: tuple[int,int] = (200, 400)) -> dict:
    """Redimensiona ambas as imagens para o mesmo size e computa diff de pixels."""
    from PIL import Image
    a = np.array(Image.open(png_a).convert("RGB").resize(size), dtype=float)
    b = np.array(Image.open(png_b).convert("RGB").resize(size), dtype=float)
    diff = np.abs(a - b)
    return {
        "mean_diff"  : float(diff.mean()),
        "max_diff"   : float(diff.max()),
        "pct_changed": float((diff.mean(axis=2) > 10).mean() * 100),
    }


class TestEzdxfRender:
    """Renderiza N2 e N4 com ezdxf e compara visualmente."""

    @pytest.mark.parametrize("item_id", TEST_ITEMS)
    def test_render_comparacao(self, item_id):
        n2_path = _db_recorte(item_id); assert n2_path, f"{item_id}: sem N2"
        n4_path = _generate_n4(item_id);assert n4_path, f"{item_id}: sem N4"

        png_n2 = OUT_DIR / f"n2_{item_id}.png"
        png_n4 = OUT_DIR / f"n4_{item_id}.png"
        png_cmp= OUT_DIR / f"compare_{item_id}.png"

        _render_dxf_png(n2_path, png_n2, title=f"N2 13_PAV {item_id}")
        _render_dxf_png(n4_path, png_n4, title=f"N4 ABCD {item_id}")
        _side_by_side_png(png_n2, png_n4, png_cmp,
                          label_l=f"N2 {item_id}", label_r=f"N4 {item_id}")

        stats = _pixel_diff(png_n2, png_n4)
        print(f"\n[{item_id}] pixel-diff: mean={stats['mean_diff']:.1f} "
              f"max={stats['max_diff']:.0f} pct_changed={stats['pct_changed']:.1f}%")
        print(f"  -> {png_cmp}")

        # Nao falha por diff (N2 tem anotacoes extras, escala diferente)
        # mas garante que ambos renderizaram (nao sao pretos solidos)
        from PIL import Image
        n4_arr = np.array(Image.open(png_n4).convert("RGB"), dtype=float)
        assert n4_arr.std() > 5.0, f"{item_id}: N4 PNG parece vazio/preto solido"


# ══════════════════════════════════════════════════════════════════════════
# CAMADA 3 — Qt offscreen (DXFVectorView real)
# ══════════════════════════════════════════════════════════════════════════

class TestQtOffscreen:
    """Instancia DXFVectorView com QT_QPA_PLATFORM=offscreen e captura render real."""

    @pytest.fixture(autouse=True)
    def _check_env(self):
        assert os.environ.get("QT_QPA_PLATFORM") == "offscreen", \
            "QT_QPA_PLATFORM nao e 'offscreen' — defina antes de importar Qt"

    def _import_widget(self):
        """Importa DXFVectorView isolando dependencias do CE."""
        import importlib
        # Precisamos do modulo CE sem instanciar a app toda
        if "src.ui.modules.comparison_engine" not in sys.modules:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "comparison_engine",
                ROOT / "src" / "ui" / "modules" / "comparison_engine.py")
            mod = importlib.util.module_from_spec(spec)
            # Pre-popula modulos de Qt para evitar crash na importacao
            spec.loader.exec_module(mod)
            sys.modules["src.ui.modules.comparison_engine"] = mod
        else:
            mod = sys.modules["src.ui.modules.comparison_engine"]
        return mod.DXFVectorView

    @pytest.mark.parametrize("item_id", TEST_ITEMS)
    def test_widget_n4_render(self, item_id, qtbot):
        """Instancia DXFVectorView, carrega N4, captura QPixmap, salva PNG."""
        DXFVectorView = self._import_widget()

        n4_path = _generate_n4(item_id)
        assert n4_path, f"{item_id}: N4 nao gerado"

        view = DXFVectorView(bg="#0d0d1a")
        view.resize(WIDGET_W, WIDGET_H)
        qtbot.addWidget(view)
        view.show()

        with qtbot.waitSignal(view.ready, timeout=15000,
                              raising=True) as blocker:
            view.load_dxf(str(n4_path))

        # Aguarda paint diferido
        qtbot.wait(200)

        # Captura render
        px = view.grab()
        assert not px.isNull(), f"{item_id}: grab() retornou pixmap nulo"

        out_png = OUT_DIR / f"qt_n4_{item_id}.png"
        saved   = px.save(str(out_png))
        assert saved, f"{item_id}: nao salvou PNG"
        print(f"\n[{item_id}] Qt N4 render -> {out_png} ({out_png.stat().st_size//1024}KB)")

        # Verifica que nao e preto solido
        from PIL import Image as _PIL
        arr = np.array(_PIL.open(out_png).convert("RGB"), dtype=float)
        assert arr.std() > 5.0, f"{item_id}: render N4 parece vazio (std={arr.std():.2f})"

    @pytest.mark.parametrize("item_id", TEST_ITEMS)
    def test_widget_n2_render(self, item_id, qtbot):
        """Instancia DXFVectorView, carrega N2 (recorte 13_PAV), captura QPixmap."""
        DXFVectorView = self._import_widget()

        n2_path = _db_recorte(item_id)
        assert n2_path, f"{item_id}: recorte N2 nao encontrado"

        view = DXFVectorView(bg="#0d0d1a")
        view.resize(WIDGET_W, WIDGET_H)
        qtbot.addWidget(view)
        view.show()

        with qtbot.waitSignal(view.ready, timeout=20000, raising=True):
            view.load_dxf(str(n2_path))

        qtbot.wait(200)

        px = view.grab()
        out_png = OUT_DIR / f"qt_n2_{item_id}.png"
        px.save(str(out_png))
        print(f"\n[{item_id}] Qt N2 render -> {out_png} ({out_png.stat().st_size//1024}KB)")

        from PIL import Image as _PIL
        arr = np.array(_PIL.open(out_png).convert("RGB"), dtype=float)
        assert arr.std() > 5.0, f"{item_id}: render N2 parece vazio"

    @pytest.mark.parametrize("item_id", TEST_ITEMS)
    def test_comparacao_qt_side_by_side(self, item_id, qtbot):
        """Gera PNG lado a lado N2 vs N4 usando renders do Qt widget real."""
        DXFVectorView = self._import_widget()

        n2_path = _db_recorte(item_id)
        n4_path = _generate_n4(item_id)
        assert n2_path and n4_path

        pngs = {}
        for label, dxf_path in [("n2", n2_path), ("n4", n4_path)]:
            view = DXFVectorView(bg="#0d0d1a")
            view.resize(WIDGET_W, WIDGET_H)
            qtbot.addWidget(view)
            view.show()
            with qtbot.waitSignal(view.ready, timeout=20000, raising=True):
                view.load_dxf(str(dxf_path))
            qtbot.wait(200)
            out = OUT_DIR / f"qt_{label}_{item_id}_cmp.png"
            view.grab().save(str(out))
            pngs[label] = out

        cmp_out = OUT_DIR / f"qt_compare_{item_id}.png"
        _side_by_side_png(pngs["n2"], pngs["n4"], cmp_out,
                          label_l=f"N2 {item_id} (13_PAV)",
                          label_r=f"N4 {item_id} (robot)")
        stats = _pixel_diff(pngs["n2"], pngs["n4"])
        print(f"\n[{item_id}] Qt pixel-diff: mean={stats['mean_diff']:.1f} "
              f"max={stats['max_diff']:.0f} "
              f"pct_changed={stats['pct_changed']:.1f}%")
        print(f"  -> {cmp_out}")
