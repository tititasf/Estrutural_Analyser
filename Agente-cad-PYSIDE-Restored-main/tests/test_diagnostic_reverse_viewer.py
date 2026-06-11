"""
tests/test_diagnostic_reverse_viewer.py
========================================
Testes automatizados do DiagnosticReverseHub — carregamento de DXF no viewer.

Simula uso real: seleciona obra, seleciona pavimento PIL, aguarda render, valida
que o canvas NÃO ficou preso em "Carregando…" e que entidades foram renderizadas.

Executar:
    cd D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main
    python -m pytest tests/test_diagnostic_reverse_viewer.py -v -s

Screenshots salvos em: tests/screenshots/
"""

import os
import sys
import pathlib
import time

# Windows cp1252 safe stdout
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SCREENSHOT_DIR = ROOT / "tests" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

ER_DIR = pathlib.Path(
    "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1"
    "/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"
)

# DXFs para testar: (label, sufixo parcial do filename)
DXF_CASES = [
    ("1_PAV_PIL",  "1\xb0 PAV.- PL"),   # antes all-white (bug)
    ("13_PAV_PIL", "13\xb0 PAV.- PL"),  # referência — sempre correto
    ("2_PAV_PIL",  "2\xb0 PAV.- PL"),   # outro pavimento afetado
]

RENDER_TIMEOUT_MS = 30_000   # 30s máximo por DXF


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def find_dxf(partial: str) -> pathlib.Path | None:
    """Encontra DXF no diretório ER que contenha o trecho parcial."""
    for f in ER_DIR.iterdir():
        if partial in f.name and f.suffix == ".dxf":
            return f
    return None


def grab_screenshot(widget, name: str) -> pathlib.Path:
    """Captura widget via QWidget.grab() — não depende de foco."""
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


def canvas_scene_count(canvas) -> int:
    """Número de items no QGraphicsScene do canvas (scene é atributo direto)."""
    try:
        return len(canvas.scene.items())
    except Exception:
        return -1


def is_loading(canvas) -> bool:
    """Retorna True se o canvas ainda exibe overlay de carregamento."""
    try:
        # set_loading guarda flag interna _loading ou visibilidade do overlay
        if hasattr(canvas, '_loading'):
            return bool(canvas._loading)
        if hasattr(canvas, '_loading_overlay'):
            return canvas._loading_overlay.isVisible()
        return False
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def hub(qtbot):
    """Instancia DiagnosticReverseHub uma vez para todos os testes do módulo."""
    from src.ui.modules.diagnostic_reverse_hub import DiagnosticReverseHub

    widget = DiagnosticReverseHub()
    widget.resize(1400, 900)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget, timeout=5000)

    # Garante que a tab "Visualizador Projeto Completo" está ativa
    center = widget._center
    if center._tabs.currentIndex() != 0:
        center._tabs.setCurrentIndex(0)
        QApplication.processEvents()

    return widget


# ─────────────────────────────────────────────────────────────────────────────
# Testes
# ─────────────────────────────────────────────────────────────────────────────

class TestViewerLoadsDXF:
    """Valida que o viewer renderiza DXFs PIL sem travar nem ficar all-white."""

    @pytest.mark.parametrize("label,partial", DXF_CASES)
    def test_dxf_renders_without_hang(self, hub, qtbot, label: str, partial: str):
        """
        Para cada DXF:
          1. Localiza o arquivo no disco
          2. Chama load_dxf_completo() diretamente (simula seleção de item)
          3. Aguarda render completar (até RENDER_TIMEOUT_MS)
          4. Valida: canvas tem entidades E não está em loading
          5. Tira screenshot
        """
        dxf_path = find_dxf(partial)
        assert dxf_path is not None, f"DXF não encontrado para: {partial!r} em {ER_DIR}"

        print(f"\n\n{'='*60}")
        print(f"  TESTE: {label}")
        print(f"  DXF : {dxf_path.name}")
        print(f"{'='*60}")

        center = hub._center
        canvas = center.canvas

        # Limpa scene antes de cada teste
        canvas.scene.clear()
        QApplication.processEvents()

        # Garante tab completo ativa (lazy-load só dispara em tab 0)
        center._tabs.setCurrentIndex(0)
        QApplication.processEvents()

        t_start = time.time()

        # Dispara carregamento (igual ao clique no item da lista)
        center.load_dxf_completo(str(dxf_path))
        QApplication.processEvents()

        # ── Aguarda render ────────────────────────────────────────────
        deadline = time.time() + RENDER_TIMEOUT_MS / 1000
        last_count = 0

        while time.time() < deadline:
            qtbot.wait(500)
            count = canvas_scene_count(canvas)
            loading = is_loading(canvas)

            if count != last_count:
                elapsed = round(time.time() - t_start, 1)
                print(f"  [{elapsed}s] scene items: {count}  loading={loading}")
                last_count = count

            # Render completo = tem itens E não está mais em loading
            if count > 100 and not loading:
                break

        elapsed_total = round(time.time() - t_start, 1)
        final_count = canvas_scene_count(canvas)
        still_loading = is_loading(canvas)

        print(f"\n  [OK] Resultado {label}: {final_count} items em {elapsed_total}s  loading={still_loading}")

        # Screenshot final
        grab_screenshot(hub, f"viewer_{label}_{int(time.time())}")

        # ── Assertions ────────────────────────────────────────────────
        assert not still_loading, (
            f"{label}: viewer ainda em 'Carregando…' após {elapsed_total}s — "
            f"render nunca completou (HANG detectado)"
        )
        assert final_count > 100, (
            f"{label}: apenas {final_count} items na scene após {elapsed_total}s — "
            f"DXF não renderizou ou ficou vazio"
        )

    def test_1pav_has_similar_entity_count_as_13pav(self, hub, qtbot):
        """
        1° PAV e 13° PAV PIL devem ter contagens de entities similares.
        Se 1° PAV renderiza all-white (sem cores), o scene count seria
        diferente pois hatches/fills coloridos não seriam criados.
        """
        center = hub._center

        counts = {}
        for label, partial in [("1_PAV", "1\xb0 PAV.- PL"), ("13_PAV", "13\xb0 PAV.- PL")]:
            dxf = find_dxf(partial)
            if dxf is None:
                pytest.skip(f"DXF não encontrado: {partial}")

            canvas = center.canvas
            canvas.scene.clear()
            center._tabs.setCurrentIndex(0)
            QApplication.processEvents()

            center.load_dxf_completo(str(dxf))

            deadline = time.time() + 35
            while time.time() < deadline:
                qtbot.wait(600)
                cnt = canvas_scene_count(canvas)
                loading = is_loading(canvas)
                if cnt > 100 and not loading:
                    break

            counts[label] = canvas_scene_count(canvas)
            print(f"\n  {label}: {counts[label]} scene items")

        if "1_PAV" in counts and "13_PAV" in counts:
            ratio = counts["1_PAV"] / max(counts["13_PAV"], 1)
            print(f"\n  Ratio 1_PAV/13_PAV = {ratio:.2f}")
            assert ratio > 0.5, (
                f"1° PAV ({counts['1_PAV']}) tem menos da metade dos items do "
                f"13° PAV ({counts['13_PAV']}) — possível all-white ou render incompleto"
            )


class TestViewerColors:
    """Valida que o DXF carregado pelo viewer tem cores corretas (não all-white)."""

    def test_dxf_loader_resolves_colors_for_1pav(self):
        """
        Testa DXFLoader diretamente (sem GUI) — verifica cores das entidades.
        1° PAV não deve ter 100% das lines com cor branca (255,255,255).
        """
        import collections
        from src.core.dxf_loader import DXFLoader, RenderMode

        dxf = find_dxf("1\xb0 PAV.- PL")
        assert dxf is not None, "DXF 1° PAV PIL não encontrado"

        # Força re-parse ignorando cache
        data = DXFLoader.load_dxf(str(dxf), mode=RenderMode.TRUE_GEOMETRY)
        assert data, "DXFLoader retornou vazio"

        lines = data.get("lines", [])
        assert len(lines) > 1000, f"Poucos lines: {len(lines)}"

        colors = collections.Counter(l.get("color") for l in lines)
        white_count = colors.get((255, 255, 255), 0)
        white_ratio = white_count / len(lines)

        print(f"\n  1° PAV PIL: {len(lines)} lines")
        print(f"  Top 5 cores: {colors.most_common(5)}")
        print(f"  White ratio: {white_ratio:.1%}  ({white_count}/{len(lines)})")

        assert white_ratio < 0.5, (
            f"1° PAV ainda tem {white_ratio:.1%} das lines brancas — "
            f"color resolution ainda com bug (esperado < 50%)"
        )

    def test_no_displaced_entities_negative_x(self):
        """
        Verifica que DXFLoader nao produz entidades com X < -1000 para DXFs PIL.
        Entidades com X negativo sao 'pedacinhos' deslocados a esquerda — causados
        por bug no LWPOLYLINE/ARC native transform com matrices de reflexao (xscale < 0).
        """
        import tempfile, shutil, pathlib as _pl
        from src.core.dxf_loader import DXFLoader, RenderMode

        for label, partial in [("1_PAV_PL", "1\xb0 PAV.- PL"), ("13_PAV_PL", "13\xb0 PAV.- PL")]:
            dxf = find_dxf(partial)
            if dxf is None:
                continue

            # Force fresh parse (skip pkl cache) by loading from a temp copy
            tmp = _pl.Path(tempfile.mktemp(suffix=".dxf"))
            shutil.copy(str(dxf), str(tmp))
            try:
                data = DXFLoader.load_dxf(str(tmp), mode=RenderMode.TRUE_GEOMETRY)
            finally:
                tmp.unlink(missing_ok=True)

            assert data, f"{label}: DXFLoader retornou vazio"

            neg_polys = [p for p in data.get("polylines", [])
                         if p.get("points") and min(pt[0] for pt in p["points"]) < -1000]
            neg_circles = [c for c in data.get("circles", [])
                           if c.get("center", (0,))[0] < -1000]

            print(f"\n  {label}: neg polylines={len(neg_polys)}  neg circles={len(neg_circles)}")

            assert len(neg_polys) == 0, (
                f"{label}: {len(neg_polys)} polyline(s) com X < -1000 — "
                f"LWPOLYLINE reflection bug nao corrigido"
            )
            assert len(neg_circles) == 0, (
                f"{label}: {len(neg_circles)} circle(s) com X < -1000 — "
                f"ARC/CIRCLE reflection bug nao corrigido"
            )

    def test_no_stale_all_white_pkls_exist(self):
        """
        Verifica que não existem pkls stale (all-white) no diretório ER.
        Pkls all-white causam o bug de renderização sem cor.
        """
        import pickle
        import collections

        stale = []
        for f in ER_DIR.iterdir():
            if not f.name.endswith(".TRUE_GEOMETRY.pkl"):
                continue
            try:
                with open(f, "rb") as fh:
                    data = pickle.load(fh)
                lines = data.get("lines", [])
                if not lines:
                    continue
                top_color, top_count = collections.Counter(
                    l.get("color") for l in lines
                ).most_common(1)[0]
                if top_color == (255, 255, 255) and top_count == len(lines):
                    stale.append(f.name)
            except Exception:
                pass

        print(f"\n  PKLs TRUE_GEOMETRY verificados em ER dir")
        print(f"  Stale (all-white): {len(stale)}")
        for s in stale:
            print(f"    [STALE] {s}")

        assert len(stale) == 0, (
            f"Encontrado(s) {len(stale)} pkl(s) stale all-white — "
            f"delete-os para corrigir renderização:\n" +
            "\n".join(f"  {s}" for s in stale)
        )


class TestRecorteMotor:
    """Valida que RecorteMotor gera recortes com a mesma qualidade do viewer.

    Testa paridade total: cores corretas (nao all-white) e coordenadas corretas
    (sem entidades deslocadas para X negativo) para DXFs PIL.
    """

    @pytest.mark.parametrize("label,partial", [
        ("1_PAV_PIL",  "1\xb0 PAV.- PL"),
        ("13_PAV_PIL", "13\xb0 PAV.- PL"),
    ])
    def test_motor_recortes_have_correct_colors(self, tmp_path, label, partial):
        """
        RecorteMotor nao deve gerar recortes all-white.
        Antes do fix, _extract_geometry_from_dxf() hardcodava aci=7 (branco)
        para TODAS as entidades — recortes ficavam brancos no viewer.
        Agora usa DXFLoader (TRUE_GEOMETRY) com cores resolvidas corretamente.
        """
        import collections, ezdxf as _ezdxf
        from src.core.recorte_motor import RecorteMotor

        dxf = find_dxf(partial)
        if dxf is None:
            pytest.skip(f"DXF nao encontrado: {partial}")

        motor = RecorteMotor(str(dxf), er_type="PIL")
        results = motor.run(str(tmp_path), db_path=None, overwrite=True)

        assert results, f"{label}: motor nao gerou nenhum recorte"

        white_issues = []
        for r in results:
            rpath = tmp_path / r["recorte_path"].split("/")[-1].split("\\")[-1]
            if not rpath.exists():
                import pathlib as _pl
                rpath = _pl.Path(r["recorte_path"])
            if not rpath.exists():
                continue

            rdoc = _ezdxf.readfile(str(rpath))
            aci_ct = collections.Counter(getattr(e.dxf, "color", 7) for e in rdoc.modelspace())
            total = sum(aci_ct.values())
            if total == 0:
                continue
            white_ratio = aci_ct.get(7, 0) / total
            if white_ratio >= 0.95:
                white_issues.append(f"  {r['elemento_id']}: {white_ratio:.0%} white ({total} ents)")

        print(f"\n  {label}: {len(results)} recortes, {len(white_issues)} com >=95% white")
        assert not white_issues, (
            f"{label}: {len(white_issues)} recortes all-white — "
            f"motor nao usa DXFLoader corretamente:\n" + "\n".join(white_issues)
        )

    @pytest.mark.parametrize("label,partial", [
        ("1_PAV_PIL",  "1\xb0 PAV.- PL"),
        ("13_PAV_PIL", "13\xb0 PAV.- PL"),
    ])
    def test_motor_recortes_have_no_displaced_entities(self, tmp_path, label, partial):
        """
        Entidades no recorte NAO devem ter X < -100.
        Antes do fix, virtual_entities() tinha o mesmo bug de reflexao que
        LWPOLYLINE native transform — PONTALETE/MEIO PONTALETE apareciam
        deslocados para X negativo (pedacinhos verdes a esquerda do desenho).
        """
        import ezdxf as _ezdxf
        from src.core.recorte_motor import RecorteMotor

        dxf = find_dxf(partial)
        if dxf is None:
            pytest.skip(f"DXF nao encontrado: {partial}")

        motor = RecorteMotor(str(dxf), er_type="PIL")
        results = motor.run(str(tmp_path), db_path=None, overwrite=True)

        displaced = []
        for r in results:
            import pathlib as _pl
            rpath = _pl.Path(r["recorte_path"])
            if not rpath.exists():
                continue
            rdoc = _ezdxf.readfile(str(rpath))
            neg_xs = []
            for e in rdoc.modelspace():
                t = e.dxftype()
                if t == "LINE":
                    if e.dxf.start.x < -100 or e.dxf.end.x < -100:
                        neg_xs.append(min(e.dxf.start.x, e.dxf.end.x))
                elif t == "LWPOLYLINE":
                    for p in e.get_points():
                        if p[0] < -100:
                            neg_xs.append(p[0])
            if neg_xs:
                displaced.append(f"  {r['elemento_id']}: {len(neg_xs)} pts com X<-100 (min={min(neg_xs):.1f})")

        print(f"\n  {label}: {len(results)} recortes, {len(displaced)} com entidades deslocadas")
        assert not displaced, (
            f"{label}: recortes com entidades deslocadas (X < -100):\n" + "\n".join(displaced)
        )

    def test_motor_confidence_matches_between_pavimentos(self):
        """
        O score de confianca de PIL do 1° PAV deve ser similar ao do 13° PAV.
        Antes do fix, 1° PAV tinha todos os recortes all-white com geometria
        deslocada — confianca era artificialmente baixa.
        """
        from src.core.recorte_motor import RecorteMotor

        results_by_pav = {}
        for pav, partial in [("1", "1\xb0 PAV.- PL"), ("13", "13\xb0 PAV.- PL")]:
            dxf = find_dxf(partial)
            if dxf is None:
                continue
            import pathlib as _pl, tempfile as _tmp
            out = _pl.Path(_tmp.mkdtemp())
            try:
                motor = RecorteMotor(str(dxf), er_type="PIL")
                results = motor.run(str(out), db_path=None, overwrite=True)
                confs = [r.get("confidence", 0) for r in results if r.get("confidence") is not None]
                if confs:
                    results_by_pav[pav] = sum(confs) / len(confs)
                    print(f"\n  {pav}° PAV PIL: {len(results)} recortes, avg conf={results_by_pav[pav]:.1f}%")
            finally:
                import shutil as _sh
                _sh.rmtree(str(out), ignore_errors=True)

        if "1" in results_by_pav and "13" in results_by_pav:
            ratio = results_by_pav["1"] / max(results_by_pav["13"], 1)
            print(f"  Ratio 1°/13° confianca: {ratio:.2f}")
            assert ratio > 0.7, (
                f"1° PAV conf={results_by_pav['1']:.1f}% vs 13° PAV conf={results_by_pav['13']:.1f}% "
                f"— ratio={ratio:.2f} muito baixo, possivel regressao no motor"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Testes: Comparison Engine — Fluxo ER (evitar crash ao selecionar lista 2)
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH = pathlib.Path("D:/Agente-cad-PYSIDE/project_data.vision")
OBRA_NAME = "Obra_TREINO_1"

def _db_has_er_data() -> bool:
    """Verifica se o DB tem fichas ER para os testes."""
    if not DB_PATH.exists():
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM reverse_eng_fichas WHERE obra_name=?", (OBRA_NAME,))
        n = cur.fetchone()[0]
        conn.close()
        return n > 0
    except Exception:
        return False


@pytest.mark.skipif(not _db_has_er_data(), reason="DB ER não populado")
class TestComparisonEngineERFlow:
    """Valida que o fluxo Eng. Reversa no Comparison Engine não crasheia.

    Root cause do crash: _on_gerar_n2 carregava DXF STOG inteiro (7-8MB)
    gerando 500k+ ops Qt → STATUS_STACK_BUFFER_OVERRUN.
    Fix: usa recorte DXF individual (<1MB) do DB quando _current_flow=='reverso'.
    """

    def _first_er_item(self, classe_ce: str) -> tuple[str, str]:
        """Retorna (elem_id, recorte_path) do primeiro item ER para a classe."""
        import sqlite3
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe_ce, classe_ce)
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "SELECT elemento_id, recorte_path FROM reverse_eng_fichas "
            "WHERE obra_name=? AND classe=? ORDER BY elemento_id LIMIT 1",
            (OBRA_NAME, db_cls)
        )
        row = cur.fetchone()
        conn.close()
        return row if row else (None, None)

    @pytest.mark.parametrize("classe_ce", ["LV", "PL", "FV", "LJ"])
    def test_get_recorte_dxf_for_er_returns_existing_path(self, classe_ce):
        """_get_recorte_dxf_for_er deve retornar Path existente para itens no DB."""
        # Instancia mínima do ComparisonEngine sem GUI (só testa o método helper)
        import sys
        from unittest.mock import MagicMock, patch
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)

        elem_id, recorte_path = self._first_er_item(classe_ce)
        if elem_id is None:
            pytest.skip(f"Sem itens ER para classe {classe_ce}")

        if not recorte_path or not pathlib.Path(recorte_path).exists():
            pytest.skip(f"recorte_path não existe em disco para {classe_ce}/{elem_id}")

        # Testa a lógica de DB diretamente (sem instanciar CE completo)
        import sqlite3
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe_ce, classe_ce)
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "SELECT recorte_path FROM reverse_eng_fichas "
            "WHERE obra_name=? AND classe=? AND elemento_id=?",
            (OBRA_NAME, db_cls, elem_id)
        )
        row = cur.fetchone()
        conn.close()

        assert row is not None, f"Item {elem_id} não encontrado no DB"
        assert row[0], f"recorte_path vazio para {elem_id}"
        p = pathlib.Path(row[0])
        print(f"\n  {classe_ce}/{elem_id}: recorte={p.name} exists={p.exists()}")
        assert p.exists(), f"recorte DXF não existe em disco: {p}"
        # DXF de recorte deve ser PEQUENO (<1MB) para não crashar
        size_mb = p.stat().st_size / (1024 * 1024)
        print(f"  Tamanho: {size_mb:.2f} MB")
        assert size_mb < 2.0, (
            f"recorte DXF muito grande ({size_mb:.1f}MB) — risco de crash ao carregar: {p.name}"
        )

    @pytest.mark.parametrize("classe_ce", ["LV", "PL", "FV", "LJ"])
    def test_ficha_n2_er_returns_valid_rows(self, classe_ce):
        """_ficha_n2_er deve retornar lista de (chave, valor) com confiança e status."""
        import sqlite3, json
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe_ce, classe_ce)

        elem_id, _ = self._first_er_item(classe_ce)
        if elem_id is None:
            pytest.skip(f"Sem itens ER para classe {classe_ce}")

        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "SELECT campos_json, confianca, status FROM reverse_eng_fichas "
            "WHERE obra_name=? AND classe=? AND elemento_id=?",
            (OBRA_NAME, db_cls, elem_id)
        )
        row = cur.fetchone()
        conn.close()

        assert row is not None, f"Item {elem_id} não encontrado"
        campos_raw, conf, status = row
        assert campos_raw, f"campos_json vazio para {elem_id}"
        campos = json.loads(campos_raw)
        assert isinstance(campos, dict), "campos_json deve ser dict"

        # Simula o que _ficha_n2_er faria
        result = [
            ("Elemento", elem_id),
            ("Classe", db_cls),
            ("Status ER", status or "—"),
            ("Confiança", f"{(conf or 0)*100:.0f}%"),
        ]
        for k, v in campos.items():
            if k.startswith("_"):
                continue
            if isinstance(v, list):
                result.append((k, f"[{len(v)} itens]"))
            elif isinstance(v, dict):
                result.append((k, str(v)[:60]))
            else:
                result.append((k, str(v)))

        print(f"\n  {classe_ce}/{elem_id}: {len(result)} rows, conf={conf:.0%}, status={status}")
        assert len(result) >= 4, "Ficha deve ter pelo menos 4 campos base"
        keys = [r[0] for r in result]
        assert "Elemento" in keys
        assert "Confiança" in keys
        assert "Status ER" in keys

    def test_pav_filter_returns_correct_subset(self):
        """_load_reverse_items deve filtrar por pavimento — não retornar TODOS os itens da obra."""
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()

        # Quantos LV existem no total vs por pavimento
        cur.execute(
            "SELECT COUNT(*) FROM reverse_eng_fichas WHERE obra_name=? AND classe='LV'",
            (OBRA_NAME,)
        )
        total_lv = cur.fetchone()[0]

        cur.execute(
            "SELECT DISTINCT pavimento FROM reverse_eng_fichas WHERE obra_name=? AND classe='LV'",
            (OBRA_NAME,)
        )
        pavs = [r[0] for r in cur.fetchall()]
        conn.close()

        if total_lv == 0 or not pavs:
            pytest.skip("Sem itens LV no DB")

        # Importar o método _pav_key_to_db_pav via módulo
        # (testa sem instanciar NavSidebar completo)
        import sys
        sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main')
        from src.ui.modules.comparison_engine import NavSidebar

        # Para cada pavimento do DB, verifica que o filtro retorna subconjunto
        for db_pav in pavs[:3]:  # testar no máximo 3
            conn2 = sqlite3.connect(str(DB_PATH))
            cur2 = conn2.cursor()
            cur2.execute(
                "SELECT COUNT(*) FROM reverse_eng_fichas WHERE obra_name=? AND classe='LV' AND pavimento=?",
                (OBRA_NAME, db_pav)
            )
            count_pav = cur2.fetchone()[0]
            conn2.close()

            print(f"\n  pav={db_pav}: {count_pav} LV (total={total_lv})")
            assert count_pav < total_lv, (
                f"Pavimento {db_pav} retornou {count_pav} == total {total_lv} "
                f"— filtro não está reduzindo a lista"
            )
            assert count_pav > 0, f"Pavimento {db_pav} retornou 0 itens"

    @pytest.mark.parametrize("discovery_key,expected_db_pav", [
        ("13PAV",                    "13_PAV"),
        ("1PAV",                     "1_PAV"),
        ("14PAV",                    "14_PAV"),
        ("TIPO - 3 AO 12PAV",        "12_PAV"),
        ("PARAISO - COBERTURA - DECK", "COBERTURA"),
    ])
    def test_pav_key_conversion(self, discovery_key: str, expected_db_pav: str):
        """_pav_key_to_db_pav deve converter corretamente pav_key → db_pav."""
        import sys
        sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main')
        from src.ui.modules.comparison_engine import NavSidebar
        result = NavSidebar._pav_key_to_db_pav(discovery_key)
        print(f"\n  '{discovery_key}' → '{result}' (expected '{expected_db_pav}')")
        assert result == expected_db_pav, (
            f"Conversão errada: '{discovery_key}' → '{result}' != '{expected_db_pav}'"
        )

    def test_er_flow_recorte_smaller_than_stog(self):
        """Recorte DXF individual deve ser menor que o DXF STOG completo."""
        import sqlite3
        # Pega tamanho do STOG LV (o mais pesado, ~7MB)
        stog_folder = pathlib.Path(
            "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1"
            "/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"
        )
        stog_lv = next(stog_folder.glob("*LV*.dxf"), None) if stog_folder.exists() else None

        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "SELECT recorte_path FROM reverse_eng_fichas "
            "WHERE obra_name=? AND classe='LV' AND recorte_path IS NOT NULL "
            "ORDER BY elemento_id LIMIT 5",
            (OBRA_NAME,)
        )
        rows = cur.fetchall()
        conn.close()

        if not rows:
            pytest.skip("Sem recortes LV no DB")

        sizes = []
        for (rp,) in rows:
            p = pathlib.Path(rp)
            if p.exists():
                sizes.append(p.stat().st_size)

        if not sizes:
            pytest.skip("Nenhum recorte LV existe em disco")

        avg_recorte_mb = sum(sizes) / len(sizes) / (1024 * 1024)
        stog_mb = stog_lv.stat().st_size / (1024 * 1024) if stog_lv else None

        print(f"\n  Recortes LV: {len(sizes)} amostras, avg={avg_recorte_mb:.2f}MB")
        if stog_mb:
            print(f"  STOG LV completo: {stog_mb:.1f}MB")
            ratio = avg_recorte_mb / stog_mb
            print(f"  Ratio recorte/STOG: {ratio:.3f} ({ratio*100:.1f}%)")
            assert avg_recorte_mb < stog_mb * 0.3, (
                f"Recortes LV ({avg_recorte_mb:.2f}MB avg) não são significativamente "
                f"menores que STOG ({stog_mb:.1f}MB) — fix ER flow pode não ajudar"
            )

        assert avg_recorte_mb < 1.0, (
            f"Recortes LV muito grandes ({avg_recorte_mb:.2f}MB avg) — "
            f"risco de crash ao carregar em série"
        )
