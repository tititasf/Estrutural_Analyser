import os
import sys
import json
import uuid
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QFrame,
                               QDialog, QDialogButtonBox, QRadioButton,
                               QButtonGroup, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QCheckBox, QProgressBar, QSizePolicy,
                               QComboBox, QTabWidget, QListWidget, QListWidgetItem,
                               QSplitter,
                               QGraphicsLineItem, QGraphicsPathItem, QGraphicsEllipseItem)
from PySide6.QtCore import QThread, Signal, QProcess, Qt, QTimer, QObject
from src.ui.components.organisms import DiagnosticSidebar, TechSheetPanel
from src.ui.canvas import CADCanvas
from src.core.dxf_loader import RenderMode
from src.core.services.data_coordinator import get_coordinator
from src.ui.theme import Colors, Fonts, Radius
from src.core.services.fase4_importer import Fase4Importer

# Raiz base das obras
DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"


class _NullWidget:
    """Stub silencioso para widgets do painel Fase-3 que foi removido da UI."""
    def setText(self, *a):    pass
    def setValue(self, *a):   pass
    def setVisible(self, *a): pass
    def setEnabled(self, *a): pass
    def value(self):          return 0
    def isChecked(self):      return False


class _DXFRenderProxy(QObject):
    """
    Proxy QObject que vive no main thread.

    worker.finished emite do worker thread → Qt detecta cruzamento de threads
    → usa QueuedConnection automaticamente → on_loaded roda no main thread.

    Isso garante que scene.addItem / fitInView sejam sempre chamados no main thread,
    evitando o crash segfault que ocorria quando closures sem QObject recebiam
    sinais via DirectConnection no worker thread.
    """

    def __init__(self, canvas, canvas_id: int, thread_ref, pending_dict: dict,
                 render_mode, parent=None):
        super().__init__(parent)
        self._canvas     = canvas
        self._canvas_id  = canvas_id
        self._thread_ref = thread_ref
        self._pending    = pending_dict
        self._render_mode = render_mode

    def on_loaded(self, entities, dur, dd):
        """Slot — roda no main thread via QueuedConnection automática do Qt."""
        # Guard: se um load mais recente já tomou o lugar deste, ignorar
        if self._pending.get(self._canvas_id) is not self._thread_ref:
            print(f"[DiagnosticHub] on_loaded: stale result ignorado (canvas {self._canvas_id})", flush=True)
            return
        canvas = self._canvas
        if entities:
            n = (len(entities.get('lines',    [])) +
                 len(entities.get('polylines',[])) +
                 len(entities.get('texts',    [])) +
                 len(entities.get('circles',  [])) +
                 len(entities.get('hatches',  [])))
            print(f"[DiagnosticHub] on_loaded: {n:,} entidades — iniciando render no main thread ({dur:.1f}s load)", flush=True)
            canvas.set_loading(True, f"⌛ Renderizando {n:,} entidades...")
            canvas.add_dxf_entities(
                entities,
                render_mode=dd.get('render_mode', self._render_mode),
                compute_snaps=False, source_dxf_path=dd.get('source_path'),
                progress_callback=lambda pct: canvas.update_loading_progress(pct, "Renderizando"),
            )
            print(f"[DiagnosticHub] on_loaded: render concluído", flush=True)
        else:
            print(f"[DiagnosticHub] on_loaded: entities vazio", flush=True)
        canvas.set_loading(False)

    def on_error(self, e: str):
        """Slot — roda no main thread via QueuedConnection automática do Qt."""
        print(f"[DiagnosticHub] DXF load error: {e}", flush=True)
        if self._pending.get(self._canvas_id) is self._thread_ref:
            self._canvas.set_loading(False)


# ─────────────────────────────────────────────────────────────────────────────
# PreProcessAllWorker — Batch Structural Analyzer on all approved torre crops
# ─────────────────────────────────────────────────────────────────────────────

class PreProcessAllWorker(QThread):
    """
    Executa o motor Structural Analyzer (Fase 3) em batch:
    - Itera sobre todos os recortes tipo 'torre' com status='approved' da obra
    - Para cada torre: DXFLoader → SpatialIndex → ContextEngine → BeamTracer → SlabTracer
    - Agrega resultados por pavimento e constrói Ficha Pré-Interpretativa (Nível B)
    - Salva pre_processamento_estado.json na raiz da obra
    Não depende de Qt UI — usa apenas engines Python puros.
    """
    progress     = Signal(int, str)   # pct (0-100), mensagem
    torre_result = Signal(dict)       # resultado por torre
    finished     = Signal(dict)       # ficha completa ao terminar
    error        = Signal(str)        # mensagem de erro fatal

    def __init__(self, obra_name: str, obra_path: str, force: bool = False, analysis_mode: str = "baseline", parent=None):
        super().__init__(parent)
        self.obra_name = obra_name
        self.obra_path = Path(obra_path)
        self.force     = force
        self.analysis_mode = analysis_mode
        self._abort    = False

    def abort(self):
        self._abort = True

    # ── entry point ──────────────────────────────────────────────────────────
    def run(self):
        import traceback
        try:
            self._process()
        except Exception as exc:
            self.error.emit(f"{exc}\n{traceback.format_exc()[:1500]}")

    # ── main logic ───────────────────────────────────────────────────────────
    def _process(self):
        import sqlite3
        import json as _json
        from datetime import datetime as _dt
        from collections import defaultdict
        from pathlib import Path as _P

        RECORTES_DB = _P("D:/Agente-cad-PYSIDE/project_data.vision")

        # 1. Query approved torres & detalhes
        try:
            conn = sqlite3.connect(str(RECORTES_DB))
            conn.row_factory = sqlite3.Row
            torres = [dict(r) for r in conn.execute(
                "SELECT * FROM obra_recortes "
                "WHERE obra_name=? AND recorte_type='torre' AND status='approved' "
                "ORDER BY pavimento_name, recorte_index",
                (self.obra_name,),
            ).fetchall()]
            detalhes = [dict(r) for r in conn.execute(
                "SELECT * FROM obra_recortes "
                "WHERE obra_name=? AND recorte_type='detalhe' AND status='approved' "
                "ORDER BY pavimento_name, recorte_index",
                (self.obra_name,),
            ).fetchall()]
            conn.close()
        except Exception as exc:
            self.error.emit(f"Erro ao consultar DB: {exc}")
            return

        if not torres:
            self.error.emit(
                "Nenhuma torre aprovada encontrada.\n"
                "Aprove os recortes na aba BRUTO → painel direito antes de Pré-processar."
            )
            return

        # 2. Import engines (pure Python — sem PySide6)
        try:
            from src.core.dxf_loader    import DXFLoader
            from src.core.spatial_index  import SpatialIndex
            from src.core.beam_tracer    import BeamTracer
            from src.core.slab_tracer    import SlabTracer
            from src.core.analysis_helpers import (
                detect_pilares_from_polylines,
                process_beam_intelligent,
                process_slab_intelligent,
                correlate_sides_data,
                run_sanity_checks,
            )
        except Exception as exc:
            self.error.emit(f"Erro ao importar motores Fase-3: {exc}")
            return

        # 3. Import DB helper direto (sem Qt — seguro para QThread)
        try:
            from src.core.database import DatabaseManager
            _db_path = str(Path("D:/Agente-cad-PYSIDE/project_data.vision"))
            _db = DatabaseManager(_db_path)
            _db_ok = True
        except Exception as _dbe:
            _db = None
            _db_ok = False
            self.progress.emit(5, f"[WARN] DB não disponível: {_dbe}")

        # ── helper: obter ou criar project_id para (obra, pavimento) ──────────
        def _get_or_create_project_id(obra: str, pav: str) -> str:
            """Retorna project_id existente ou cria novo via db.create_project."""
            if not _db_ok:
                import uuid as _uuid
                return str(_uuid.uuid4())
            try:
                projects = _db.get_projects()
                for proj in projects:
                    if (proj.get('work_name') == obra and
                            proj.get('pavement_name') == pav):
                        return str(proj['id'])
            except Exception:
                pass
            try:
                return _db.create_project(
                    name=f"{obra} — {pav}",
                    work_name=obra,
                    pavement_name=pav,
                    author_name='PreProcessAllWorker',
                )
            except Exception:
                import uuid as _uuid
                return str(_uuid.uuid4())

        # ── helper: salvar lote no DB ─────────────────────────────────────────
        def _save_batch(project_id: str, pilares, vigas, lajes):
            if not _db_ok or not project_id:
                return
            for p in pilares:
                try:
                    _db.save_pillar(p, project_id)
                except Exception:
                    pass
            for b in vigas:
                try:
                    _db.save_beam(b, project_id)
                except Exception:
                    pass
            for s in lajes:
                try:
                    _db.save_slab(s, project_id)
                except Exception:
                    pass

        # 4. Group torres by pavimento
        pav_torres: dict = defaultdict(list)
        for t in torres:
            pav_torres[t['pavimento_name']].append(t)

        total_torres = len(torres)
        processed_n  = 0
        ficha_pavs   = []

        # 5. Per-pavimento loop
        for pav_name, pav_list in sorted(pav_torres.items()):
            if self._abort:
                break

            pav_status   = "ok"
            pav_niveis: list = []
            # Acumula todos os itens do pavimento (agregação cross-torre para sides_data)
            pav_pilares: list = []
            pav_vigas:   list = []
            pav_lajes:   list = []

            for torre in sorted(pav_list, key=lambda x: x.get('recorte_index', 0)):
                if self._abort:
                    break

                idx  = torre.get('recorte_index', 0)
                path = torre.get('output_path', '')
                pct  = max(5, int((processed_n / total_torres) * 83) + 5)
                self.progress.emit(pct, f"[{pav_name}] torre {idx + 1}…")

                if not path or not _P(path).exists():
                    pav_status = "parcial"
                    processed_n += 1
                    continue

                try:
                    dxf = DXFLoader.load_dxf(path)
                    if not dxf:
                        pav_status = "parcial"
                        processed_n += 1
                        continue

                    texts     = dxf.get('texts',     [])
                    polylines = dxf.get('polylines',  [])
                    lines_raw = dxf.get('lines',      [])

                    # ── Spatial index ────────────────────────────────────────
                    si = SpatialIndex()
                    for pl in polylines:
                        pts = pl.get('points', [])
                        if pts:
                            _xs = [p[0] for p in pts]; _ys = [p[1] for p in pts]
                            si.insert(pl, (min(_xs), min(_ys), max(_xs), max(_ys)))
                    for ln in lines_raw:
                        _s, _e = ln.get('start', (0, 0)), ln.get('end', (0, 0))
                        si.insert(ln, (min(_s[0], _e[0]), min(_s[1], _e[1]),
                                       max(_s[0], _e[0]), max(_s[1], _e[1])))
                    for txt in texts:
                        _p = txt.get('pos', (0, 0))
                        si.insert(txt, (_p[0] - 5, _p[1] - 5, _p[0] + 5, _p[1] + 5))

                    # ── Pilares (full detection) ──────────────────────────────
                    _scope = f"{self.obra_name}|{pav_name}|{idx}"
                    torre_pilares = detect_pilares_from_polylines(
                        polylines, texts, scope=_scope)

                    # ── Vigas (full detection + interpretation) ───────────────
                    all_segs = list(polylines)
                    for ln in lines_raw:
                        if 'start' in ln:
                            all_segs.append({'points': [ln['start'], ln['end']]})
                    raw_vigas = BeamTracer(si).detect_beams(texts, all_segs)
                    for b in raw_vigas:
                        process_beam_intelligent(b)
                    torre_vigas = raw_vigas

                    # ── Lajes (full detection + interpretation) ───────────────
                    raw_lajes = SlabTracer(si).detect_slabs_from_texts(
                        texts,
                    )
                    for s in raw_lajes:
                        process_slab_intelligent(s, texts)
                        lv = s.get('fields', {}).get('laje_nivel') or s.get('level') or s.get('nivel')
                        if lv:
                            try:
                                pav_niveis.append(float(str(lv).replace(',', '.').replace('+', '')))
                            except Exception:
                                pass
                    torre_lajes = raw_lajes

                    # Acumular no pavimento
                    pav_pilares.extend(torre_pilares)
                    pav_vigas.extend(torre_vigas)
                    pav_lajes.extend(torre_lajes)

                    self.torre_result.emit({
                        'pav_name':  pav_name,
                        'torre_idx': idx,
                        'n_pilares': len(torre_pilares),
                        'n_vigas':   len(torre_vigas),
                        'n_lajes':   len(torre_lajes),
                        'analysis_mode': self.analysis_mode,
                        'status':    'ok',
                    })

                except Exception as exc:
                    import traceback as _tb
                    pav_status = "parcial"
                    self.progress.emit(pct, f"⚠ {pav_name}/t{idx}: {exc}")
                    print(f"[PreProcessWorker] {pav_name}/t{idx}: {exc}\n{_tb.format_exc()[:800]}",
                          flush=True)

                processed_n += 1

            # ── sides_data: correlacionar vigas com pilares (nível pavimento) ──
            if pav_pilares and pav_vigas:
                try:
                    correlate_sides_data(pav_pilares, pav_vigas)
                except Exception:
                    pass

            # ── sanity checks por pilar ───────────────────────────────────────
            for p in pav_pilares:
                try:
                    p['issues'] = run_sanity_checks(p)
                except Exception:
                    p['issues'] = []

            # ── Salvar no DB ──────────────────────────────────────────────────
            if pav_pilares or pav_vigas or pav_lajes:
                self.progress.emit(
                    max(5, int((processed_n / max(total_torres, 1)) * 83) + 5),
                    f"[{pav_name}] Salvando {len(pav_pilares)}P / {len(pav_vigas)}V / {len(pav_lajes)}L no DB…",
                )
                project_id = _get_or_create_project_id(self.obra_name, pav_name)
                _save_batch(project_id, pav_pilares, pav_vigas, pav_lajes)

            # ── Pavimento aggregate ───────────────────────────────────────────
            niveis_s = sorted(set(pav_niveis))
            ficha_pavs.append({
                'nome':                pav_name,
                'n_pilares':           len(pav_pilares),
                'n_vigas':             len(pav_vigas),
                'n_lajes':             len(pav_lajes),
                'nivel_chegada':       niveis_s[0]  if niveis_s          else 0,
                'nivel_saida':         niveis_s[-1] if len(niveis_s) > 1 else (niveis_s[0] if niveis_s else 0),
                'lajes_nivel_distinto': len(niveis_s) > 1,
                'status':              pav_status,
                'torres_count':        len(pav_list),
                'analysis_mode':        self.analysis_mode,
            })
            self.progress.emit(
                max(5, int((processed_n / max(total_torres, 1)) * 83) + 5),
                f"✅ {pav_name}: {len(pav_pilares)}P / {len(pav_vigas)}V / {len(pav_lajes)}L",
            )

        # 5. Track C — Detalhes (entity counts per DXF)
        self.progress.emit(90, "Analisando detalhes…")
        det_resumo: dict = {}
        for d in detalhes:
            if self._abort:
                break
            pav  = d.get('pavimento_name', '')
            path = d.get('output_path', '')
            if not path or not _P(path).exists():
                continue
            try:
                dd = DXFLoader.load_dxf(path)
                if dd:
                    n_ent = (len(dd.get('lines', [])) +
                             len(dd.get('polylines', [])) +
                             len(dd.get('texts', [])))
                    layers = list({
                        e.get('layer', '') for e in
                        dd.get('polylines', []) + dd.get('lines', [])
                        if e.get('layer')
                    })[:8]
                    det_resumo.setdefault(pav, []).append({
                        'idx':      d.get('recorte_index', 0),
                        'entities': n_ent,
                        'layers':   layers,
                    })
            except Exception:
                pass

        # 6. Totais + resumo
        totais = {
            'pilares': sum(p['n_pilares'] for p in ficha_pavs),
            'vigas':   sum(p['n_vigas']   for p in ficha_pavs),
            'lajes':   sum(p['n_lajes']   for p in ficha_pavs),
        }
        n_p, n_v, n_l = totais['pilares'], totais['vigas'], totais['lajes']
        n_pav = len(ficha_pavs)
        parts = [
            f"Obra '{self.obra_name}' — {n_pav} pavimento(s) interpretado(s).",
            f"Total estrutural detectado: {n_p} pilar(es), {n_v} viga(s), {n_l} laje(s).",
        ]
        distintos = [p['nome'] for p in ficha_pavs if p.get('lajes_nivel_distinto')]
        if distintos:
            parts.append(f"Lajes em níveis distintos em: {', '.join(distintos)}.")
        parciais = [p['nome'] for p in ficha_pavs if p.get('status') in ('parcial', 'erro')]
        if parciais:
            parts.append(f"⚠ Processamento parcial: {', '.join(parciais)}.")

        ficha = {
            'obra':             self.obra_name,
            'gerado_em':        _dt.now().isoformat(),
            'analysis_mode':    self.analysis_mode,
            'pavimentos':       ficha_pavs,
            'totais':           totais,
            'detalhes':         det_resumo,
            'resumo_semantico': ' '.join(parts),
        }

        # 7. Persist estado
        self.progress.emit(95, "Salvando ficha…")
        estado_name = "pre_processamento_estado.json"
        if self.analysis_mode == "context":
            estado_name = "pre_processamento_estado_context.json"
        elif self.analysis_mode == "engrev_assisted":
            estado_name = "pre_processamento_estado_engrev_assisted.json"
        estado_path = self.obra_path / estado_name
        try:
            estado_path.parent.mkdir(parents=True, exist_ok=True)
            estado_path.write_text(
                _json.dumps({
                    'obra_name': self.obra_name,
                    'last_run':  ficha['gerado_em'],
                    'status':    'completed',
                    'analysis_mode': self.analysis_mode,
                    'ficha':     ficha,
                }, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
        except Exception:
            pass

        self.progress.emit(100, "Ficha gerada!")
        self.finished.emit(ficha)

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _count_pilares(polylines: list) -> int:
        """Conta polígonos fechados válidos — proxy rápido para contagem de pilares."""
        try:
            from shapely.geometry import Polygon
            count = 0
            for pl in polylines:
                pts = pl.get('points', [])
                uniq: list = []
                for p in pts:
                    if not uniq or p != uniq[-1]:
                        uniq.append(p)
                if len(uniq) < 3:
                    continue
                try:
                    shape = Polygon(uniq)
                    if shape.is_valid and shape.area > 100:
                        count += 1
                except Exception:
                    continue
            return count
        except ImportError:
            # Fallback sem shapely: conta polígonos com 4+ pontos
            return sum(1 for pl in polylines if len(pl.get('points', [])) >= 4)


class RenderModeDialog(QDialog):
    """Diálogo para seleção de modo de renderização."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modo de Renderização")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecione a Estratégia de Limpeza (V1 - V20):"))

        # Scroll Area para muitos modos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        self.button_group = QButtonGroup(self)

        modes = [
            (RenderMode.TRUE_GEOMETRY, "1. True Geometry", "Original sem filtros."),
            (RenderMode.EDGE_CLEANER, "2. Edge Cleaner", "Remove ruído e micro-segmentos."),
            (RenderMode.COLOR_BASIC, "3. Color Basic (1-4)", "SÓ Vermelho, Amarelo, Verde e Ciano."),
            (RenderMode.COLOR_EXTENDED, "4. Color Extended (1-7)", "Adiciona Azul, Magenta e Branco."),
            (RenderMode.COLOR_LAYERS, "5. Color + Whitelist", "Cores 1-4 + Filtro de Camadas (Pilar/Viga)."),
            (RenderMode.COLOR_ORTHO, "6. Color + Ortho", "Cores 1-4 + Somente Retas (H/V)."),
            (RenderMode.COLOR_FLATTEN, "7. Color + Flatten", "Cores 1-4 + Achatamento Z (Purga Links)."),
            (RenderMode.COLOR_BLOCKS, "8. Color + Blocks", "Cores 1-4 + Limpeza Interna de Blocos."),
            (RenderMode.COLOR_FAN, "9. Color + Global Purge", "Cores 1-4 + Detector de Leques Global."),
            (RenderMode.COLOR_OMEGA, "10. OMEGA COLOR", "Estratégia Definitiva Combinada."),
        ]

        for i, (mode, name, desc) in enumerate(modes):
            radio = QRadioButton(f"<b>{name}</b><br><font color='gray'>{desc}</font>")
            radio.setProperty("mode", mode)
            if i == 0:
                radio.setChecked(True)
            self.button_group.addButton(radio, i)
            scroll_layout.addWidget(radio)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.resize(400, 500)

    def get_selected_mode(self):
        checked = self.button_group.checkedButton()
        return checked.property("mode") if checked else RenderMode.TRUE_GEOMETRY


# ─────────────────────────────────────────────────────────────────────────────
# RagPipelineWorker — runs obra_rag_pipeline.run_pipeline() in background
# ─────────────────────────────────────────────────────────────────────────────

class RagPipelineWorker(QThread):
    """
    Executa obra_rag_pipeline.run_pipeline() em background thread.

    Signals:
        progress(int, str)   — (pct 0-100, mensagem)
        finished(dict)       — resultado completo {status, doc_chunks, dxf_indexed, ...}
        error(str)           — mensagem de erro fatal
    """
    progress = Signal(int, str)
    finished = Signal(dict)
    error    = Signal(str)

    def __init__(self, obra_name: str, force: bool = False, parent=None):
        super().__init__(parent)
        self.obra_name = obra_name
        self.force     = force

    def run(self):
        try:
            import sys
            from pathlib import Path
            _ROOT = Path(__file__).resolve().parent.parent.parent.parent
            if str(_ROOT) not in sys.path:
                sys.path.insert(0, str(_ROOT))

            from scripts.obra_rag_pipeline import run_pipeline

            def _cb(pct: int, msg: str):
                self.progress.emit(pct, msg)

            result = run_pipeline(self.obra_name, force=self.force, progress_cb=_cb)
            self.finished.emit(result)
        except Exception as exc:
            import traceback
            self.error.emit(f"{exc}\n{traceback.format_exc()[:600]}")


class DiagnosticHubModule(QWidget):
    """
    Página Principal do Módulo de Diagnóstico (Pré-Processamento).
    Layout: [Sidebar | Canvas | TechPanel] + barra Fase-3 na base.
    """

    # Emitido quando Fase-3 termina com sucesso — carrega Tab 1
    fase3_complete = Signal(str)   # project_id

    # Emitido quando PreProcessAll termina — main.py refresha combos e vai para Structural Analyzer
    preprocess_complete = Signal(str)  # obra_name

    def __init__(self, db=None):
        super().__init__()
        self.db = db
        self.coordinator = get_coordinator()
        self._load_thread = None
        self._load_worker = None
        self._current_doc_data = None
        self._fase3_process    = None
        self._pipeline_process = None
        self._current_obra     = None   # obra selecionada no ComboBox
        self._current_bruto_path = None  # DXF bruto selecionado
        self._current_selected_recorte = None
        self._current_list_item = None   # referência ao QListWidgetItem atual
        self._preprocess_worker = None   # PreProcessAllWorker em execução
        self._rag_worker        = None   # RagPipelineWorker em execução

        # Painel Fase-3 removido da UI — stubs silenciosos para manter backend intacto
        _nw = _NullWidget
        self._lbl_fase3_obra    = _nw()
        self._lbl_fase3_status  = _nw()
        self._fase3_progress    = _nw()
        self._btn_fase3_run     = _nw()
        self._chk_fase3_force   = _nw()

        # Keep DiagnosticSidebar instantiated (hidden) for external compatibility
        self.sidebar = DiagnosticSidebar(db=self.db)
        self.sidebar.document_selected.connect(self._on_document_selected)
        self.sidebar.setVisible(False)

        # === Layout externo (vertical) ===
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # === Conteúdo principal — splitter horizontal ===
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {Colors.BORDER_DEFAULT}; }}")

        # ── Painel Esquerdo: Obra + Brutos aprovados ──────────────────────────
        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)

        # ── Centro: Tabs [BRUTO | LIMPO | DETALHES] + CADCanvas ──────────────
        center_panel = self._build_center_panel()
        splitter.addWidget(center_panel)

        # ── Painel Direito: Recortes ──────────────────────────────────────────
        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([240, 700, 260])
        outer.addWidget(splitter, 1)

        # Signals
        self.coordinator.project_changed.connect(self._on_project_changed)
        self.coordinator.work_changed.connect(self._on_work_changed_hub)

        # Populate obras combo on startup
        QTimer.singleShot(300, self._populate_obras_combo)

    # ─────────────────────────────────────────────
    # Left Panel: Obra selector + Brutos list
    # ─────────────────────────────────────────────

    def _build_left_panel(self) -> QFrame:
        """Painel esquerdo: ComboBox de obra + lista de brutos aprovados."""
        panel = QFrame()
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(350)
        panel.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_SECONDARY};
                border-right: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        vlay = QVBoxLayout(panel)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        # Title
        lbl_title = QLabel("✂ Diagnostic Hub")
        lbl_title.setStyleSheet(
            f"color: {Colors.ACCENT_TEAL}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        vlay.addWidget(lbl_title)

        # Obra ComboBox
        lbl_obra = QLabel("Obra:")
        lbl_obra.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        vlay.addWidget(lbl_obra)

        self._combo_obra = QComboBox()
        self._combo_obra.setStyleSheet(f"""
            QComboBox {{
                background: {Colors.BG_DEEP}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 4px 8px; font-size: 11px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {Colors.BG_DEEP}; color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.ACCENT_TEAL};
            }}
        """)
        self._combo_obra.currentTextChanged.connect(self._on_obra_selected)
        vlay.addWidget(self._combo_obra)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {Colors.BORDER_DEFAULT};")
        vlay.addWidget(sep)

        # Brutos aprovados label
        self._lbl_brutos_count = QLabel("Brutos aprovados:")
        self._lbl_brutos_count.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent;"
        )
        vlay.addWidget(self._lbl_brutos_count)

        # Brutos list
        self._list_brutos = QListWidget()
        self._list_brutos.setStyleSheet(f"""
            QListWidget {{
                background: {Colors.BG_DEEP}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                font-size: 11px;
            }}
            QListWidget::item {{ padding: 5px 8px; }}
            QListWidget::item:selected {{
                background: rgba(0, 180, 180, 64); color: {Colors.ACCENT_TEAL};
            }}
            QListWidget::item:hover {{ background: {Colors.BG_PANEL}; }}
        """)
        self._list_brutos.itemClicked.connect(self._on_bruto_selected)
        vlay.addWidget(self._list_brutos, 1)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        # Abrir DXF button
        btn_abrir_dxf = QPushButton("📂 Abrir")
        btn_abrir_dxf.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 4px; font-size: 11px;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_PRIMARY}; }}
        """)
        btn_abrir_dxf.clicked.connect(self._abrir_dxf_bruto)
        btn_layout.addWidget(btn_abrir_dxf)

        # Refresh button
        btn_refresh = QPushButton("↻ Atualizar")
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 4px; font-size: 11px;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_PRIMARY}; }}
        """)
        btn_refresh.clicked.connect(self._populate_obras_combo)
        btn_layout.addWidget(btn_refresh)

        vlay.addLayout(btn_layout)

        return panel

    # ─────────────────────────────────────────────
    # Center Panel: Tabs + CADCanvas
    # ─────────────────────────────────────────────

    def _build_center_panel(self) -> QWidget:
        """Centro: tabs BRUTO/LIMPO/DETALHES + CADCanvas."""
        center = QWidget()
        vlay = QVBoxLayout(center)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # Tab bar BRUTO | LIMPO | DETALHES
        self._canvas_tabs = QTabWidget()
        self._canvas_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none; background: {Colors.BG_DEEP};
            }}
            QTabBar::tab {{
                background: {Colors.BG_SECONDARY}; color: {Colors.TEXT_SECONDARY};
                padding: 6px 18px; border: 1px solid {Colors.BORDER_DEFAULT};
                border-bottom: none; border-radius: 4px 4px 0 0;
                font-size: 11px; font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {Colors.BG_DEEP}; color: {Colors.ACCENT_TEAL};
                border-color: {Colors.ACCENT_TEAL};
            }}
            QTabBar::tab:hover {{ color: {Colors.TEXT_PRIMARY}; }}
        """)
        self._canvas_tabs.currentChanged.connect(self._on_canvas_tab_changed)

        # Tab 0 — BRUTO
        bruto_container = QWidget()
        bruto_layout = QVBoxLayout(bruto_container)
        bruto_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = CADCanvas()
        bruto_layout.addWidget(self.canvas)
        self._canvas_tabs.addTab(bruto_container, "BRUTO")

        # Tab 1 — LIMPO
        limpo_container = QWidget()
        limpo_layout = QVBoxLayout(limpo_container)
        limpo_layout.setContentsMargins(0, 0, 0, 0)
        self._canvas_limpo = CADCanvas()
        limpo_layout.addWidget(self._canvas_limpo)
        self._canvas_tabs.addTab(limpo_container, "LIMPO")

        # Tab 2 — DETALHES
        det_container = QWidget()
        det_layout = QVBoxLayout(det_container)
        det_layout.setContentsMargins(0, 0, 0, 0)
        self._canvas_det = CADCanvas()
        det_layout.addWidget(self._canvas_det)
        self._canvas_tabs.addTab(det_container, "DETALHES")

        # Tab 3 — FICHA DA OBRA (cor diferente: ouro #e6b400)
        self._ficha_tab_widget = self._build_ficha_tab()
        self._canvas_tabs.addTab(self._ficha_tab_widget, "📋 Ficha Pré-Pavimentos/Detalhes [F2]")
        self._canvas_tabs.tabBar().setTabTextColor(
            3, __import__('PySide6.QtGui', fromlist=['QColor']).QColor('#e6b400')
        )

        # Tab 4 - FICHA GLOBAL [F3]
        self._ficha_f3_tab_widget = self._build_ficha_f3_tab()
        self._canvas_tabs.addTab(self._ficha_f3_tab_widget, "📋 Ficha Global [F3]")
        self._canvas_tabs.tabBar().setTabTextColor(
            4, __import__('PySide6.QtGui', fromlist=['QColor']).QColor('#b450c8')
        )


        vlay.addWidget(self._canvas_tabs, 1)

        # Style toolbar
        style_toolbar = QWidget()
        style_toolbar.setFixedHeight(36)
        style_toolbar.setStyleSheet(f"background: {Colors.BG_SECONDARY}; border-top: 1px solid {Colors.BORDER_DEFAULT};")
        tb_layout = QHBoxLayout(style_toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(6)

        tb_layout.addWidget(QLabel("<b>Estilo:</b>"))
        for i in [1, 3]:
            btn = QPushButton(f"Modo {i}")
            btn.setFixedWidth(70)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                    border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 3px;
                    font-size: 10px; padding: 2px 6px;
                }}
                QPushButton:hover {{ color: {Colors.TEXT_PRIMARY}; }}
            """)
            btn.clicked.connect(lambda checked, idx=i: self._on_style_changed(idx))
            tb_layout.addWidget(btn)

        tb_layout.addSpacing(12)

        self.btn_similar = QPushButton("Selecionar Similares")
        self.btn_similar.setStyleSheet(
            f"background-color: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT};"
            f" border-radius: {Radius.MD}; padding: 3px 10px; font-weight: bold; font-size: 11px;"
        )
        self.btn_similar.clicked.connect(self.canvas.select_similar)
        tb_layout.addWidget(self.btn_similar)

        # Status do crop atual
        self._lbl_crop_info = QLabel("")
        self._lbl_crop_info.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 10px; background: transparent;"
        )
        tb_layout.addWidget(self._lbl_crop_info)

        tb_layout.addStretch()
        vlay.addWidget(style_toolbar)

        return center

    # ─────────────────────────────────────────────
    # Right Panel: Recortes
    # ─────────────────────────────────────────────

    def _build_right_panel(self) -> QFrame:
        """Painel direito: lista de recortes + ferramentas de crop."""
        panel = QFrame()
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(350)
        panel.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_SECONDARY};
                border-left: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)
        vlay = QVBoxLayout(panel)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        # Title
        lbl_title = QLabel("Recortes do Pavimento")
        lbl_title.setStyleSheet(
            f"color: {Colors.ACCENT_PRIMARY}; font-size: 12px; font-weight: bold;"
            " background: transparent;"
        )
        vlay.addWidget(lbl_title)

        # Status atual
        self._lbl_recortes_status = QLabel("Selecione um bruto")
        self._lbl_recortes_status.setWordWrap(True)
        self._lbl_recortes_status.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 10px; background: transparent;"
        )
        vlay.addWidget(self._lbl_recortes_status)

        # Botão recorte manual
        self._btn_manual_crop = QPushButton("✂ Recortar")
        self._btn_manual_crop.setToolTip(
            "Salva o estado atual do canvas BRUTO como novo recorte DXF.\n"
            "Você pode usar as ferramentas do viewer para selecionar/enquadrar\n"
            "a área desejada antes de clicar."
        )
        self._btn_manual_crop.setStyleSheet(f"""
            QPushButton {{
                background: rgba(180, 120, 0, 38); color: {Colors.ACCENT_WARNING};
                border: 1px solid {Colors.ACCENT_WARNING}; border-radius: 4px;
                font-size: 11px; font-weight: bold; padding: 3px 6px;
            }}
            QPushButton:hover {{ background: rgba(180, 120, 0, 71); }}
            QPushButton:disabled {{ color: {Colors.TEXT_DIM}; border-color: {Colors.TEXT_DIM}; }}
        """)
        self._btn_manual_crop.setEnabled(False)
        self._btn_manual_crop.clicked.connect(self._run_manual_crop)
        vlay.addWidget(self._btn_manual_crop)

        # Botão recorte por seleção
        self._btn_selection_crop = QPushButton("✂ Recortar Seleção")
        self._btn_selection_crop.setToolTip(
            "Salva APENAS os itens selecionados (box select) como novo recorte DXF.\n"
            "Selecione a área desejada no viewer com o mouse e clique aqui."
        )
        self._btn_selection_crop.setStyleSheet(f"""
            QPushButton {{
                background: rgba(120, 60, 180, 38); color: #c08aff;
                border: 1px solid #c08aff; border-radius: 4px;
                font-size: 11px; font-weight: bold; padding: 3px 6px;
            }}
            QPushButton:hover {{ background: rgba(120, 60, 180, 71); }}
            QPushButton:disabled {{ color: {Colors.TEXT_DIM}; border-color: {Colors.TEXT_DIM}; }}
        """)
        self._btn_selection_crop.setEnabled(False)
        self._btn_selection_crop.clicked.connect(self._run_selection_crop)
        vlay.addWidget(self._btn_selection_crop)

        # Botão processar automático
        self._btn_process_crops = QPushButton("⚙ Processar Auto")
        self._btn_process_crops.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 180, 180, 38); color: {Colors.ACCENT_TEAL};
                border: 1px solid {Colors.ACCENT_TEAL}; border-radius: 4px;
                font-size: 11px; font-weight: bold; padding: 3px 6px;
            }}
            QPushButton:hover {{ background: rgba(0, 180, 180, 71); }}
            QPushButton:disabled {{ color: {Colors.TEXT_DIM}; border-color: {Colors.TEXT_DIM}; }}
        """)
        self._btn_process_crops.setEnabled(False)
        self._btn_process_crops.clicked.connect(self._run_crop_engine)
        vlay.addWidget(self._btn_process_crops)

        # Progress bar
        self._crop_progress = QProgressBar()
        self._crop_progress.setRange(0, 100)
        self._crop_progress.setValue(0)
        self._crop_progress.setVisible(False)
        self._crop_progress.setFixedHeight(6)
        self._crop_progress.setStyleSheet(f"""
            QProgressBar {{
                border: none; border-radius: 3px;
                background: {Colors.BG_DEEP};
            }}
            QProgressBar::chunk {{
                background: {Colors.ACCENT_TEAL}; border-radius: 3px;
            }}
        """)
        vlay.addWidget(self._crop_progress)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {Colors.BORDER_DEFAULT};")
        vlay.addWidget(sep)

        # Lista de recortes
        lbl_lista = QLabel("Recortes detectados:")
        lbl_lista.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 10px; background: transparent;"
        )
        vlay.addWidget(lbl_lista)

        self._list_recortes = QListWidget()
        self._list_recortes.setStyleSheet(f"""
            QListWidget {{
                background: {Colors.BG_DEEP}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                font-size: 10px;
            }}
            QListWidget::item {{ padding: 5px 8px; }}
            QListWidget::item:selected {{
                background: rgba(0, 180, 180, 51); color: {Colors.ACCENT_TEAL};
            }}
        """)
        self._list_recortes.itemClicked.connect(self._on_recorte_selected)
        vlay.addWidget(self._list_recortes, 1)

        # Botão salvar estado do viewer
        self._btn_save_crop = QPushButton("💾 Salvar")
        self._btn_save_crop.setToolTip(
            "Salva o estado atual do viewer de volta ao arquivo DXF do recorte selecionado.\n"
            "Use para persistir edições feitas no viewer antes de aprovar."
        )
        self._btn_save_crop.setStyleSheet(f"""
            QPushButton {{
                background: rgba(80, 80, 220, 31); color: #8888ff;
                border: 1px solid #8888ff; border-radius: 4px;
                font-size: 10px; font-weight: bold; padding: 4px 8px;
            }}
            QPushButton:hover {{ background: rgba(80, 80, 220, 71); }}
            QPushButton:disabled {{ color: {Colors.TEXT_DIM}; border-color: {Colors.TEXT_DIM}; }}
        """)
        self._btn_save_crop.setEnabled(False)
        self._btn_save_crop.clicked.connect(self._save_current_crop)

        # ── Radio buttons de classificação do recorte ──────────────────────────
        lbl_class = QLabel("Classificar recorte:")
        lbl_class.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 10px; background: transparent;"
        )
        vlay.addWidget(lbl_class)

        _CROP_CLASSES = [
            ("detalhe",  "Detalhe",  "#aa88ff"),
            ("torre",    "Torre 1",  Colors.ACCENT_TEAL),
            ("torre_2",  "Torre 2",  "#44bbdd"),
            ("outro",    "Outro",    Colors.TEXT_SECONDARY),
        ]

        self._crop_class_group = QButtonGroup(self)
        self._crop_class_group.setExclusive(True)
        class_row = QHBoxLayout()
        class_row.setSpacing(4)
        self._crop_class_btns: dict[str, QPushButton] = {}

        for cls_id, cls_label, cls_color in _CROP_CLASSES:
            btn = QPushButton(cls_label)
            btn.setCheckable(True)
            btn.setEnabled(False)
            btn.setFixedHeight(24)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {cls_color};
                    border: 1px solid {cls_color};
                    border-radius: 12px;
                    font-size: 9px; font-weight: bold;
                    padding: 2px 6px;
                }}
                QPushButton:checked {{
                    background: {cls_color};
                    color: #111;
                }}
                QPushButton:hover:!checked {{ background: rgba(255, 255, 255, 18); }}
                QPushButton:disabled {{
                    color: {Colors.TEXT_DIM};
                    border-color: {Colors.TEXT_DIM};
                }}
            """)
            self._crop_class_group.addButton(btn)
            self._crop_class_btns[cls_id] = btn
            class_row.addWidget(btn)

        vlay.addLayout(class_row)

        # Conectar via QButtonGroup.buttonClicked — dispara 1x por clique do usuário,
        # NÃO dispara por setChecked() programático.
        self._crop_class_group.buttonClicked.connect(
            lambda _btn: self._apply_crop_classification()
        )

        vlay.addWidget(self._btn_save_crop)

        # Botões de ação para recorte selecionado
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self._btn_approve_crop = QPushButton("✓ Aprovar")
        self._btn_approve_crop.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0, 200, 120, 31); color: {Colors.ACCENT_SUCCESS_ALT};
                border: 1px solid {Colors.ACCENT_SUCCESS_ALT}; border-radius: 4px;
                font-size: 10px; font-weight: bold; padding: 4px 8px;
            }}
            QPushButton:hover {{ background: rgba(0, 200, 120, 71); }}
            QPushButton:disabled {{ color: {Colors.TEXT_DIM}; border-color: {Colors.TEXT_DIM}; }}
        """)
        self._btn_approve_crop.setEnabled(False)
        self._btn_approve_crop.clicked.connect(self._approve_current_crop)

        self._btn_delete_crop = QPushButton("🗑 Excluir")
        self._btn_delete_crop.setToolTip(
            "Remove este recorte do banco e apaga o arquivo DXF.\n"
            "Use quando o recorte automático errou muito — faça um novo\n"
            "recorte manual com '✂ Recortar', edite, salve e aprove."
        )
        self._btn_delete_crop.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 80, 80, 26); color: {Colors.ACCENT_DANGER};
                border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 4px;
                font-size: 10px; font-weight: bold; padding: 4px 8px;
            }}
            QPushButton:hover {{ background: rgba(255, 80, 80, 64); }}
            QPushButton:disabled {{ color: {Colors.TEXT_DIM}; border-color: {Colors.TEXT_DIM}; }}
        """)
        self._btn_delete_crop.setEnabled(False)
        self._btn_delete_crop.clicked.connect(self._delete_current_crop)

        btn_row.addWidget(self._btn_approve_crop)
        btn_row.addWidget(self._btn_delete_crop)
        vlay.addLayout(btn_row)

        # Separador
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color: {Colors.BORDER_DEFAULT};")
        vlay.addWidget(sep2)

        # Botão "Iniciar pré-análise Pavimento Limpo"
        self._btn_process_limpo = QPushButton("Analisar todos os Pavimentos Limpos [Gerar F2]")
        self._btn_process_limpo.setToolTip(
            "Roda o motor para pré-analisar todos os pavimentos limpos (cortes STOG).\n"
            "Preenche a pré-ficha de pavimento de forma complementar."
        )
        self._btn_process_limpo.setStyleSheet(f"""
            QPushButton {{
                background: rgba(180, 80, 200, 31); color: {Colors.ACCENT_PURPLE};
                border: 1px solid {Colors.ACCENT_PURPLE}; border-radius: 4px;
                font-size: 11px; font-weight: bold; padding: 5px 8px;
            }}
            QPushButton:hover {{ background: rgba(180, 80, 200, 64); }}
            QPushButton:disabled {{ color: {Colors.TEXT_DIM}; border-color: {Colors.TEXT_DIM}; }}
        """)
        self._btn_process_limpo.setEnabled(False)
        self._btn_process_limpo.clicked.connect(lambda: self._run_pre_process_all("baseline"))
        vlay.addWidget(self._btn_process_limpo)

        # Botão "Iniciar pré-análise Detalhes"
        self._btn_process_detalhes = QPushButton("Analisar todos os Detalhes [Insights p/ F2]")
        self._btn_process_detalhes.setToolTip(
            "Extrai insights e comentários apenas dos cortes de detalhes para anexar à pré-ficha."
        )
        self._btn_process_detalhes.setStyleSheet(self._btn_process_limpo.styleSheet())
        self._btn_process_detalhes.setEnabled(False)
        self._btn_process_detalhes.clicked.connect(lambda: self._run_pre_process_all("detalhes"))
        vlay.addWidget(self._btn_process_detalhes)

        # Botão "Analisar todas fichas e gerar Ficha da Obra [F3]"
        self._btn_process_f3 = QPushButton("Analisar todas fichas e gerar Ficha da Obra [F3]")
        self._btn_process_f3.setToolTip(
            "Aciona o motor de compreensão global que analisa todas as fichas granulares N2 "
            "e produz a visão coesa da Ficha Global da Obra (F3)."
        )
        self._btn_process_f3.setStyleSheet("""
            QPushButton {
                background: rgba(180, 80, 200, 31); color: #b450c8;
                border: 1px solid #b450c8; border-radius: 4px;
                padding: 4px; font-weight: bold; font-size: 11px;
            }
            QPushButton:hover { background: rgba(180, 80, 200, 64); }
        """)
        self._btn_process_f3.setEnabled(False)
        self._btn_process_f3.clicked.connect(self._run_process_f3)
        vlay.addWidget(self._btn_process_f3)

        # Botão cancelar (oculto até processamento iniciar)
        self._btn_cancel_preprocess = QPushButton("⏹ Cancelar")
        self._btn_cancel_preprocess.setStyleSheet(f"""
            QPushButton {{
                background: rgba(220, 50, 50, 31); color: {Colors.ACCENT_DANGER};
                border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 4px;
                font-size: 10px; padding: 3px 8px;
            }}
            QPushButton:hover {{ background: rgba(220, 50, 50, 64); }}
        """)
        self._btn_cancel_preprocess.setVisible(False)
        self._btn_cancel_preprocess.clicked.connect(self._cancel_pre_process)
        vlay.addWidget(self._btn_cancel_preprocess)

        # ── Feedback do Pré-processar Todos ──────────────────────────────────
        self._lbl_preprocess_feedback = QLabel("—  Aguardando execução")
        self._lbl_preprocess_feedback.setWordWrap(True)
        self._lbl_preprocess_feedback.setStyleSheet(f"""
            color: {Colors.TEXT_DIM}; font-size: 10px;
            background: rgba(0, 0, 0, 46); border: 1px solid #2a2f3d;
            border-radius: 4px; padding: 5px 8px;
        """)
        vlay.addWidget(self._lbl_preprocess_feedback)

        # Progress bar RAG (oculta até executar — disparada automaticamente após Interpretar Obra Toda)
        self._rag_progress = QProgressBar()
        self._rag_progress.setRange(0, 100)
        self._rag_progress.setValue(0)
        self._rag_progress.setTextVisible(True)
        self._rag_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 3px;
                background: rgba(0, 0, 0, 51); height: 12px; font-size: 9px;
                color: {Colors.TEXT_DIM};
            }}
            QProgressBar::chunk {{ background: {Colors.ACCENT_SUCCESS}; border-radius: 3px; }}
        """)
        self._rag_progress.setVisible(False)
        vlay.addWidget(self._rag_progress)

        # Label feedback RAG
        self._lbl_rag_feedback = QLabel("—  RAG indexado automaticamente após interpretação")
        self._lbl_rag_feedback.setWordWrap(True)
        self._lbl_rag_feedback.setStyleSheet(f"""
            color: {Colors.TEXT_DIM}; font-size: 10px;
            background: rgba(0, 0, 0, 46); border: 1px solid #2a2f3d;
            border-radius: 4px; padding: 5px 8px;
        """)
        vlay.addWidget(self._lbl_rag_feedback)

        # Tech panel oculto (mantido para compatibilidade)
        self.tech_panel = TechSheetPanel()
        self.tech_panel.filter_requested.connect(self._on_filter_requested)
        self.tech_panel.extract_requested.connect(self._on_extract_requested)
        self.tech_panel.apply_fix_requested.connect(self._on_apply_fix)
        self.tech_panel.setVisible(False)

        return panel

    # ─────────────────────────────────────────────
    # Obra / Brutos logic
    # ─────────────────────────────────────────────

    def _populate_obras_combo(self):
        """Popula o ComboBox de obras com as obras que têm brutos aprovados."""
        import sqlite3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        obras = []
        try:
            conn = sqlite3.connect(str(DB))
            cur = conn.execute(
                "SELECT DISTINCT obra_name FROM obra_triagem"
                " WHERE status='approved' AND suggested_category LIKE '%Bruto%'"
                " ORDER BY obra_name"
            )
            obras = [r[0] for r in cur.fetchall()]
            conn.close()
        except Exception:
            pass

        # Also list obras from filesystem if not in DB
        try:
            obras_root = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
            fs_obras = [d.name for d in obras_root.iterdir() if d.is_dir()]
            for o in fs_obras:
                if o not in obras:
                    obras.append(o)
            obras.sort()
        except Exception:
            pass

        self._combo_obra.blockSignals(True)
        current = self._combo_obra.currentText()
        self._combo_obra.clear()
        self._combo_obra.addItem("— Selecione uma obra —")
        for o in obras:
            self._combo_obra.addItem(o)
        # Restore selection
        idx = self._combo_obra.findText(current)
        if idx >= 0:
            self._combo_obra.setCurrentIndex(idx)
        self._combo_obra.blockSignals(False)

        # If coordinator has a work active, select it
        if self.coordinator:
            obra_path, work_name, _, _ = self._get_current_obra_info()
            if work_name:
                idx = self._combo_obra.findText(work_name)
                if idx >= 0:
                    self._combo_obra.setCurrentIndex(idx)

    def _on_obra_selected(self, obra_name: str):
        """Atualiza lista de brutos ao selecionar obra no ComboBox."""
        if not obra_name or obra_name.startswith("—"):
            self._list_brutos.clear()
            self._lbl_brutos_count.setText("Brutos aprovados:")
            self._current_obra = None
            self._set_preprocess_buttons_enabled(False)
            return
        self._current_obra = obra_name
        self._refresh_brutos_list(obra_name)
        self._set_preprocess_buttons_enabled(True)
        # ── Carregar estado de pré-processamento existente ────────────────────
        self._load_preprocess_estado(obra_name)

    def _set_preprocess_buttons_enabled(self, enabled: bool):
        for attr in ("_btn_process_limpo", "_btn_process_detalhes", "_btn_process_f3"):
            btn = getattr(self, attr, None)
            if btn:
                btn.setEnabled(enabled)

    def _refresh_brutos_list(self, obra_name: str):
        """Recarrega a lista de brutos aprovados para a obra."""
        import sqlite3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        rows = []
        try:
            conn = sqlite3.connect(str(DB))
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM obra_triagem WHERE obra_name=? AND status='approved'"
                " AND suggested_category LIKE '%Bruto%'"
                " ORDER BY suggested_order ASC, file_name ASC",
                (obra_name,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
        except Exception:
            pass

        self._list_brutos.clear()
        
        # Agrupar por classe do pavimento
        from PySide6.QtGui import QColor, QFont
        import re
        grouped = {}
        for row in rows:
            cls = 'Outros'
            # A classe foi salva como string ex: "auto_approve=true | pav=TERREO" na coluna notes
            notes = row.get('notes', '')
            if notes and isinstance(notes, str):
                match = re.search(r'pav=([^\s|]+)', notes)
                if match:
                    cls = match.group(1).upper()
            
            # Fallback se a Triagem não conseguiu salvar o pav
            if cls == 'Outros':
                fname = row.get('file_name', '').upper()
                m_pav = re.search(r'(\d{1,2})\s*(?:PAV|PV|P)(?:\b|[-_])', fname)
                if m_pav:
                    cls = f"{int(m_pav.group(1))}Âº PAV"
                if '-TER-' in fname or 'TERREO' in fname: cls = 'TÉRREO'
                elif '-TIP-' in fname or 'TIPO' in fname: cls = 'TIPO'
                elif '-COB-' in fname or 'COBER' in fname: cls = 'COBERTURA'
                elif '-FUN-' in fname or 'FUNDA' in fname: cls = 'FUNDAÇÃO'
                elif '1PV' in fname or '1PAV' in fname: cls = '1º PAV'
                elif '13P' in fname: cls = '13º PAV'
                elif '14P' in fname: cls = '14º PAV'
                elif 'ATC' in fname or 'ATICO' in fname: cls = 'ÁTICO'
            
            grouped.setdefault(cls, []).append(row)
            
        for cls, items in sorted(grouped.items()):
            # Cria item de cabeçalho (divisória visual não clicável)
            header = QListWidgetItem(f"━━━ {cls.upper()} ━━━")
            header.setFlags(header.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
            header.setTextAlignment(Qt.AlignCenter)
            font = QFont()
            font.setBold(True)
            header.setFont(font)
            header.setForeground(QColor("#00ff9d"))
            self._list_brutos.addItem(header)
            
            for row in items:
                item = QListWidgetItem(row['file_name'])
                item.setData(Qt.UserRole, row)
                status_icon = self._get_recorte_icon(obra_name, row['file_name'])
                item.setText(f"{status_icon} {row['file_name']}")
                self._list_brutos.addItem(item)

        count = len(rows)
        self._lbl_brutos_count.setText(f"Brutos aprovados: {count}")

    def _get_recorte_icon(self, obra_name: str, file_name: str) -> str:
        """Retorna ícone de status do recorte."""
        import sqlite3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        try:
            conn = sqlite3.connect(str(DB))
            cur = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END)"
                " FROM obra_recortes WHERE obra_name=? AND dxf_bruto_path LIKE ?",
                (obra_name, f"%{file_name}%")
            )
            total, approved = cur.fetchone()
            conn.close()
            if not total:
                return "⬜"
            if approved and approved >= total:
                return "✅"
            return "🔶"
        except Exception:
            return "⬜"

    def _abrir_dxf_bruto(self):
        item = self._list_brutos.currentItem()
        if not item:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Nenhum item selecionado.")
            return
        row_data = item.data(Qt.UserRole)
        if not row_data:
            return
        raw_path = row_data.get('file_path', '')
        resolved = self._resolve_dxf_path(raw_path) if raw_path else None
        if resolved and resolved.exists():
            import os
            try:
                os.startfile(str(resolved))
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Erro", f"Não foi possível abrir o arquivo: {e}")
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Erro", "Arquivo não encontrado.")

    def _on_bruto_selected(self, item: QListWidgetItem):
        """Ao selecionar bruto na lista, carrega no canvas BRUTO e atualiza recortes."""
        row_data = item.data(Qt.UserRole)
        if not row_data:
            return
        raw_path  = row_data.get('file_path', '')
        file_name = row_data.get('file_name', '')

        # Resolve path (remapeia drives inválidos como B:/ → D:/)
        resolved  = self._resolve_dxf_path(raw_path) if raw_path else Path(raw_path)
        file_path = str(resolved)
        self._current_bruto_path = file_path  # sempre guarda path resolvido

        # Ativar controles
        self._btn_process_crops.setEnabled(bool(file_path))
        self._btn_manual_crop.setEnabled(bool(file_path))
        self._btn_selection_crop.setEnabled(bool(file_path))
        self._lbl_recortes_status.setText(f"DXF: {file_name}")
        self._lbl_crop_info.setText(file_name)

        # Carregar no canvas BRUTO (tab 0)
        self._canvas_tabs.setCurrentIndex(0)
        try:
            dxf_exists = resolved.exists()
        except OSError:
            dxf_exists = False

        if dxf_exists:
            doc_data = {
                'id': str(hash(file_path)),
                'name': file_name,
                'file_path': file_path,
                'extension': resolved.suffix.lower(),
            }
            self._load_dxf_on_canvas(self.canvas, doc_data)
        else:
            self._lbl_recortes_status.setText(f"⚠ Arquivo não encontrado:\n{file_path}")

        # Carregar recortes existentes
        self._refresh_recortes_list(file_path)

    def _refresh_recortes_list(self, dxf_bruto_path: str):
        """Carrega recortes existentes para o DXF bruto selecionado."""
        import sqlite3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        self._list_recortes.clear()

        obra_name = self._current_obra or ""
        if not obra_name or not dxf_bruto_path:
            return

        rows = []
        try:
            conn = sqlite3.connect(str(DB), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM obra_recortes WHERE obra_name=? AND dxf_bruto_path=?"
                " ORDER BY recorte_type, recorte_index",
                (obra_name, dxf_bruto_path)
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
        except Exception:
            pass

        for row in rows:
            rtype = row.get('recorte_type', 'recorte')
            ridx  = row.get('recorte_index', 0)
            status = row.get('status', 'auto')
            pav    = row.get('pavimento_name', '')
            score  = row.get('score', 0.0)
            icon = "✅" if status == 'approved' else ("✗" if status == 'rejected' else "🔶")
            label = f"{icon} {rtype}_{ridx+1} | {pav} | score={score:.0f}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, row)
            self._list_recortes.addItem(item)

        count = len(rows)
        if count == 0:
            self._lbl_recortes_status.setText("Nenhum recorte ainda — clique em 'Processar Recortes'")
        else:
            approved = sum(1 for r in rows if r.get('status') == 'approved')
            self._lbl_recortes_status.setText(f"{count} recortes  ({approved} aprovados)")

    def _on_recorte_selected(self, item: QListWidgetItem):
        """Ao selecionar recorte, carrega no canvas LIMPO ou DETALHES."""
        row_data = item.data(Qt.UserRole)
        if not row_data:
            return
        output_path = row_data.get('output_path', '')
        rtype = row_data.get('recorte_type', 'torre')
        tab_idx = 1 if rtype == 'torre' else 2
        self._canvas_tabs.setCurrentIndex(tab_idx)

        self._btn_approve_crop.setEnabled(True)
        self._btn_delete_crop.setEnabled(True)
        self._btn_save_crop.setEnabled(True)
        self._current_selected_recorte = row_data
        self._current_list_item = item  # referência direta — sobrevive à mudança de foco

        # Habilitar e marcar a classe atual do recorte
        rtype = row_data.get('recorte_type', 'detalhe')
        for cls_id, btn in self._crop_class_btns.items():
            btn.setEnabled(True)
            btn.setChecked(cls_id == rtype)

        resolved = self._resolve_dxf_path(output_path) if output_path else None
        try:
            ok = resolved is not None and resolved.exists()
        except OSError:
            ok = False
        if ok:
            canvas = self._canvas_limpo if tab_idx == 1 else self._canvas_det
            doc_data = {
                'id': str(hash(str(resolved))),
                'name': resolved.name,
                'file_path': str(resolved),
                'extension': '.dxf',
            }
            self._load_dxf_on_canvas(canvas, doc_data)
        else:
            self._lbl_recortes_status.setText("⚠ DXF recorte não encontrado — processe novamente")

    def _load_dxf_on_canvas(self, canvas, doc_data: dict):
        """
        Carrega DXF num canvas com TRUE_GEOMETRY.
        Cancela qualquer carga pendente PARA O MESMO CANVAS antes de iniciar nova.

        THREADING MODEL:
          worker roda no QThread (worker thread).
          _DXFRenderProxy vive no main thread (parent=self).
          Qt usa QueuedConnection automática ao conectar worker.finished →
          proxy.on_loaded, garantindo que scene.addItem/fitInView rodem
          SEMPRE no main thread. Sem proxy → DirectConnection → segfault.
        """
        file_path = doc_data.get('file_path', '')
        if not file_path:
            return
        try:
            if not Path(file_path).exists():
                return
        except OSError:
            return
        try:
            from src.ui.workers import DXFLoadWorker
        except ImportError:
            return

        # ── Inicializa estruturas de controle ──────────────────────────────────
        if not hasattr(self, '_dxf_threads'):
            self._dxf_threads  = []
            self._dxf_workers  = []
            self._dxf_proxies  = []
        if not hasattr(self, '_canvas_pending'):
            self._canvas_pending = {}  # canvas_id → thread em curso

        canvas_id = id(canvas)

        # ── Cancela load anterior do MESMO canvas ──────────────────────────────
        old_thread = self._canvas_pending.get(canvas_id)
        if old_thread is not None and old_thread.isRunning():
            old_thread.quit()
            old_thread.wait(300)

        doc_data_with_mode = {**doc_data, 'render_mode': RenderMode.TRUE_GEOMETRY}
        canvas.set_loading(True)

        thread = QThread(self)
        worker = DXFLoadWorker(file_path, doc_data=doc_data_with_mode, use_cache=True)
        worker.moveToThread(thread)

        self._canvas_pending[canvas_id] = thread
        self._dxf_threads.append(thread)
        self._dxf_workers.append(worker)

        # Proxy com parent=self → vive no main thread
        # Qt detecta cruzamento worker thread → main thread e usa QueuedConnection
        proxy = _DXFRenderProxy(
            canvas, canvas_id, thread, self._canvas_pending,
            RenderMode.TRUE_GEOMETRY, parent=self
        )
        self._dxf_proxies.append(proxy)

        def _cleanup():
            if thread in self._dxf_threads:  self._dxf_threads.remove(thread)
            if worker in self._dxf_workers:  self._dxf_workers.remove(worker)
            if proxy  in self._dxf_proxies:  self._dxf_proxies.remove(proxy)
            if self._canvas_pending.get(canvas_id) is thread:
                self._canvas_pending.pop(canvas_id, None)
            worker.deleteLater()
            thread.deleteLater()
            # proxy.deleteLater() após on_loaded já ter sido entregue pelo event loop
            QTimer.singleShot(500, proxy.deleteLater)

        thread.started.connect(worker.run)
        # ← QueuedConnection automática: proxy está no main thread, worker no worker thread
        worker.finished.connect(proxy.on_loaded)
        worker.error.connect(proxy.on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(_cleanup)

        thread.start()

    # ─────────────────────────────────────────────
    # Helpers de path
    # ─────────────────────────────────────────────

    @staticmethod
    def _resolve_dxf_path(raw_path: str) -> Path:
        """
        Tenta resolver um caminho de arquivo DXF, remapeando drives inválidos.

        Problema: paths armazenados no SQLite podem ter drive B:/ (drive mapeado
        na época do scan que não existe mais).  Ao chamar Path.exists() no Windows
        para um drive inexistente, o SO exibe um dialog de sistema antes de Python
        tratar o erro.

        Estratégia de fallback:
          1. Testa o path original (capturando OSError de drive inválido)
          2. Tenta substituir a raiz do drive pelo root DADOS-OBRAS em D:/
          3. Procura apenas pelo nome do arquivo dentro de DADOS-OBRAS recursivamente
        """
        DADOS_OBRAS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
        p = Path(raw_path)

        # 1. Tentativa direta (protegida contra OSError de drive inexistente)
        try:
            if p.exists():
                return p
        except OSError:
            pass  # drive não existe → continua com fallbacks

        # 2. Remapear: pegar a parte depois de "DADOS-OBRAS" no path original
        raw_str = raw_path.replace('\\', '/')
        if 'DADOS-OBRAS' in raw_str:
            after = raw_str.split('DADOS-OBRAS', 1)[1].lstrip('/')
            candidate = DADOS_OBRAS / after
            try:
                if candidate.exists():
                    print(f"[DiagnosticHub] Path remapeado: {raw_path} → {candidate}", flush=True)
                    return candidate
            except OSError:
                pass

        # 3. Busca pelo nome do arquivo em DADOS-OBRAS
        fname = p.name
        try:
            matches = list(DADOS_OBRAS.rglob(fname))
            if matches:
                print(f"[DiagnosticHub] Path encontrado por busca: {matches[0]}", flush=True)
                return matches[0]
        except OSError:
            pass

        # Retorna o path original (será detectado como não encontrado pelo caller)
        return p

    # ─────────────────────────────────────────────
    # Crop Engine
    # ─────────────────────────────────────────────

    def _run_crop_engine(self):
        """Roda obra_crop_engine para o bruto selecionado (em QThread para não travar UI)."""
        if not self._current_bruto_path or not self._current_obra:
            QMessageBox.warning(self, "Crop", "Selecione um bruto primeiro.")
            return

        bruto_path = self._resolve_dxf_path(self._current_bruto_path)
        try:
            found = bruto_path.exists()
        except OSError:
            found = False
        if not found:
            QMessageBox.warning(self, "Crop", f"Arquivo não encontrado:\n{bruto_path}")
            return

        self._btn_process_crops.setEnabled(False)
        self._crop_progress.setVisible(True)
        self._crop_progress.setValue(10)
        self._lbl_recortes_status.setText("⏳ Processando recortes...")

        obra_name = self._current_obra
        pav_name  = bruto_path.stem
        bruto_str = str(bruto_path)

        from PySide6.QtCore import QObject, Signal as QSignal

        class _CropWorker(QObject):
            finished = QSignal(dict)
            error    = QSignal(str)

            def __init__(self, obra, pav, dxf_path):
                super().__init__()
                self._obra = obra
                self._pav  = pav
                self._path = dxf_path

            def run(self):
                try:
                    import sys
                    scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
                    if str(scripts_dir.parent) not in sys.path:
                        sys.path.insert(0, str(scripts_dir.parent))
                    from scripts.obra_crop_engine import process_pavimento_crops, ensure_recortes_in_db
                    result = process_pavimento_crops(
                        obra_name=self._obra,
                        pavimento_name=self._pav,
                        dxf_bruto_path=self._path,
                        n_torres=1,
                        force=True,
                    )
                    try:
                        ensure_recortes_in_db(self._obra, self._pav, self._path, result)
                    except Exception as e:
                        print(f"[CropEngine] DB persist warning: {e}")
                    self.finished.emit(result)
                except Exception as e:
                    self.error.emit(str(e))

        thread = QThread(self)
        worker = _CropWorker(obra_name, pav_name, bruto_str)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        # ── Proxy no main thread — mesma razão do _DXFRenderProxy ─────────────
        # Closures _on_done/_on_error rodariam no worker thread via DirectConnection
        # → todos os setEnabled/setText/QMessageBox causam segfault.
        # Proxy com parent=self → Qt usa QueuedConnection → main thread.
        class _CropProxy(QObject):
            done  = Signal(dict)
            error = Signal(str)

            def __init__(self, hub, bruto, p_thread, parent=None):
                super().__init__(parent)
                self._hub    = hub
                self._bruto  = bruto
                self._thread = p_thread

            def on_done(self, result: dict):
                hub = self._hub
                hub._crop_progress.setValue(100)
                QTimer.singleShot(600, lambda: hub._crop_progress.setVisible(False))
                n_torres = len(result.get('torres', []))
                n_det    = len(result.get('detalhes', []))
                hub._lbl_recortes_status.setText(f"✅ {n_torres} torre(s) + {n_det} detalhe(s)")
                hub._refresh_recortes_list(self._bruto)
                hub._refresh_brutos_list(hub._current_obra)
                hub._btn_process_crops.setEnabled(True)
                self._thread.quit()

            def on_error(self, msg: str):
                hub = self._hub
                hub._crop_progress.setVisible(False)
                hub._lbl_recortes_status.setText(f"⚠ Erro: {msg}")
                QMessageBox.critical(hub, "Crop Engine", f"Erro ao processar recortes:\n{msg}")
                hub._btn_process_crops.setEnabled(True)
                self._thread.quit()

        crop_proxy = _CropProxy(self, bruto_str, thread, parent=self)

        worker.finished.connect(crop_proxy.on_done)   # QueuedConnection automática
        worker.error.connect(crop_proxy.on_error)     # QueuedConnection automática

        # Manter referências
        if not hasattr(self, '_crop_threads'):
            self._crop_threads  = []
            self._crop_workers  = []
            self._crop_proxies  = []
        self._crop_threads.append(thread)
        self._crop_workers.append(worker)
        self._crop_proxies.append(crop_proxy)

        def _cleanup():
            if thread      in self._crop_threads:  self._crop_threads.remove(thread)
            if worker      in self._crop_workers:  self._crop_workers.remove(worker)
            if crop_proxy  in self._crop_proxies:  self._crop_proxies.remove(crop_proxy)
            worker.deleteLater()
            thread.deleteLater()
            QTimer.singleShot(500, crop_proxy.deleteLater)

        thread.finished.connect(_cleanup)
        self._crop_progress.setValue(30)
        thread.start()

    # ─────────────────────────────────────────────
    # ─────────────────────────────────────────────
    # Helper: exporta scene de um canvas → arquivo DXF
    # ─────────────────────────────────────────────

    @staticmethod
    def _export_scene_to_dxf(canvas, output_path: Path) -> dict:
        """
        Itera os QGraphicsScene items do canvas e grava um DXF novo via ezdxf.
        Captura deleções manuais feitas no viewer (entidades removidas da scene
        NÃO aparecem no arquivo — ao contrário de recortar por viewport_bbox).

        Retorna dict com 'entities_copied' (int) e opcional 'error' (str).
        """
        try:
            import ezdxf
            from PySide6.QtWidgets import QGraphicsSimpleTextItem

            doc = ezdxf.new('R2010')
            msp = doc.modelspace()
            n = 0

            for item in canvas.scene.items():
                data   = item.data(0) or {}
                layer  = str(data.get('layer', '0') or '0')
                aci    = data.get('aci', 256)
                attribs: dict = {'layer': layer}
                if isinstance(aci, int) and aci not in (0, 256):
                    attribs['color'] = aci

                if isinstance(item, QGraphicsLineItem):
                    ln = item.line()
                    msp.add_line((ln.x1(), ln.y1()), (ln.x2(), ln.y2()), dxfattribs=attribs)
                    n += 1
                elif isinstance(item, QGraphicsPathItem):
                    path = item.path()
                    pts = [(path.elementAt(i).x, path.elementAt(i).y)
                           for i in range(path.elementCount())]
                    if len(pts) >= 2:
                        msp.add_polyline2d(pts, dxfattribs=attribs)
                        n += 1
                elif isinstance(item, QGraphicsEllipseItem):
                    rect = item.rect()
                    cx, cy = rect.center().x(), rect.center().y()
                    rw, rh = rect.width() / 2, rect.height() / 2
                    if abs(rw - rh) < 0.5:
                        msp.add_circle((cx, cy), (rw + rh) / 2, dxfattribs=attribs)
                        n += 1
                elif isinstance(item, QGraphicsSimpleTextItem):
                    p = item.pos()
                    h = float(data.get('height', 2.5) or 2.5)
                    msp.add_text(item.text(),
                                 dxfattribs={**attribs, 'height': h,
                                             'insert': (p.x(), p.y())})
                    n += 1

            doc.saveas(str(output_path))
            return {'entities_copied': n}
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def _export_selection_to_dxf(canvas, output_path: Path) -> dict:
        """
        Mesmo que _export_scene_to_dxf mas exporta APENAS os itens selecionados
        na scene (canvas.scene.selectedItems()).
        """
        try:
            import ezdxf
            from PySide6.QtWidgets import QGraphicsSimpleTextItem

            selected = canvas.scene.selectedItems()
            if not selected:
                return {'error': 'Nenhum item selecionado. Selecione uma área antes de recortar.'}

            doc = ezdxf.new('R2010')
            msp = doc.modelspace()
            n = 0

            for item in selected:
                data   = item.data(0) or {}
                layer  = str(data.get('layer', '0') or '0')
                aci    = data.get('aci', 256)
                attribs: dict = {'layer': layer}
                if isinstance(aci, int) and aci not in (0, 256):
                    attribs['color'] = aci

                if isinstance(item, QGraphicsLineItem):
                    ln = item.line()
                    msp.add_line((ln.x1(), ln.y1()), (ln.x2(), ln.y2()), dxfattribs=attribs)
                    n += 1
                elif isinstance(item, QGraphicsPathItem):
                    path = item.path()
                    pts = [(path.elementAt(i).x, path.elementAt(i).y)
                           for i in range(path.elementCount())]
                    if len(pts) >= 2:
                        msp.add_polyline2d(pts, dxfattribs=attribs)
                        n += 1
                elif isinstance(item, QGraphicsEllipseItem):
                    rect = item.rect()
                    cx, cy = rect.center().x(), rect.center().y()
                    rw, rh = rect.width() / 2, rect.height() / 2
                    if abs(rw - rh) < 0.5:
                        msp.add_circle((cx, cy), (rw + rh) / 2, dxfattribs=attribs)
                        n += 1
                elif isinstance(item, QGraphicsSimpleTextItem):
                    p = item.pos()
                    h = float(data.get('height', 2.5) or 2.5)
                    msp.add_text(item.text(),
                                 dxfattribs={**attribs, 'height': h,
                                             'insert': (p.x(), p.y())})
                    n += 1

            doc.saveas(str(output_path))
            return {'entities_copied': n}
        except Exception as e:
            return {'error': str(e)}

    # Recorte manual (botão "Recortar")
    # ─────────────────────────────────────────────

    def _run_manual_crop(self):
        """
        Salva o estado atual do canvas BRUTO como um novo recorte DXF manual.
        Pergunta ao usuário: Detalhes ou Pavimento Limpo?
        Se Pavimento Limpo: qual torre?
        Salva o viewport atual do bruto filtrado pela bbox visível.
        """
        if not self._current_bruto_path or not self._current_obra:
            QMessageBox.warning(self, "Recortar", "Selecione um bruto primeiro.")
            return

        bruto_path = self._resolve_dxf_path(self._current_bruto_path)
        try:
            if not bruto_path.exists():
                QMessageBox.warning(self, "Recortar", f"Arquivo não encontrado:\n{bruto_path}")
                return
        except OSError:
            QMessageBox.warning(self, "Recortar", f"Drive inválido: {bruto_path}")
            return

        # ── Diálogo de tipo ───────────────────────────────────────────────────
        dialog = QDialog(self)
        dialog.setWindowTitle("Tipo de Recorte")
        dialog.setMinimumWidth(300)
        dlg_layout = QVBoxLayout(dialog)

        dlg_layout.addWidget(QLabel("Qual tipo de recorte?"))

        btn_group = QButtonGroup(dialog)
        rb_torre   = QRadioButton("🏛 Pavimento Limpo (Torre)")
        rb_detalhe = QRadioButton("📐 Detalhes")
        rb_conv_pil = QRadioButton("📖 Convenção de Pilares")
        rb_torre.setChecked(True)
        btn_group.addButton(rb_torre,   0)
        btn_group.addButton(rb_detalhe, 1)
        btn_group.addButton(rb_conv_pil, 2)
        dlg_layout.addWidget(rb_torre)
        dlg_layout.addWidget(rb_detalhe)
        dlg_layout.addWidget(rb_conv_pil)

        # Número da torre (visível apenas para Pavimento Limpo)
        torre_row = QHBoxLayout()
        lbl_torre = QLabel("Número da torre:")
        self._sb_torre_num = QComboBox()
        self._sb_torre_num.addItems(["1", "2", "3"])
        torre_row.addWidget(lbl_torre)
        torre_row.addWidget(self._sb_torre_num)
        torre_row.addStretch()
        dlg_layout.addLayout(torre_row)

        def _toggle_torre(checked):
            lbl_torre.setVisible(rb_torre.isChecked())
            self._sb_torre_num.setVisible(rb_torre.isChecked())

        rb_torre.toggled.connect(_toggle_torre)
        rb_detalhe.toggled.connect(_toggle_torre)
        rb_conv_pil.toggled.connect(_toggle_torre)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dlg_layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        is_detalhe = rb_detalhe.isChecked()
        is_conv_pil = rb_conv_pil.isChecked()
        torre_num  = int(self._sb_torre_num.currentText())

        if is_conv_pil:
            rtype    = "convencao_pilares"
            filename = "convencao_pilares_manual.dxf"
        elif is_detalhe:
            rtype    = "detalhe"
            filename = "detalhes_manual.dxf"
        else:
            rtype    = "torre"
            filename = f"torre_{torre_num}_manual.dxf"

        # ── Destino: nome único com timestamp para nunca sobrescrever ─────────
        import time, uuid as _uuid, json as _json, sqlite3
        from datetime import datetime as _dt

        pav_name = bruto_path.stem
        out_dir  = DADOS_OBRAS_ROOT / self._current_obra / "Fase-2_Triagem" / "recortes" / pav_name
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        stem     = Path(filename).stem
        out_path = out_dir / f"{stem}_{ts}.dxf"
        # garantia extra — loop raro mas seguro
        while out_path.exists():
            ts += 1
            out_path = out_dir / f"{stem}_{ts}.dxf"

        # ── Exportar: scene do canvas BRUTO → DXF ────────────────────────────
        # Usa o helper que itera QGraphicsScene items → captura todas as deleções
        # manuais que o usuário fez no viewer antes de clicar "Recortar".
        crop_result = self._export_scene_to_dxf(self.canvas, out_path)

        if crop_result.get("error"):
            QMessageBox.critical(self, "Recortar",
                                 f"Erro ao exportar recorte:\n{crop_result['error']}")
            return

        n_ent = crop_result.get('entities_copied', 0)

        # ── Persistir no banco ────────────────────────────────────────────────
        DB  = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        now = _dt.now().isoformat()
        row_id = str(_uuid.uuid4())
        try:
            conn = sqlite3.connect(str(DB), timeout=5)
            # Próximo índice disponível para esse (obra, pav, tipo)
            cur = conn.execute(
                "SELECT COALESCE(MAX(recorte_index), -1) + 1 FROM obra_recortes "
                "WHERE obra_name=? AND pavimento_name=? AND recorte_type=?",
                (self._current_obra, pav_name, rtype)
            )
            next_idx = cur.fetchone()[0]
            conn.execute("""
                INSERT INTO obra_recortes
                    (id, obra_name, pavimento_name, dxf_bruto_path, recorte_type,
                     recorte_index, output_path, bbox_auto, entity_count,
                     score, status, n_torres, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                row_id, self._current_obra, pav_name, str(bruto_path),
                rtype, next_idx, str(out_path), None, n_ent,
                0.0, "manual", 1 if (is_detalhe or is_conv_pil) else torre_num, now,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.warning(self, "Recortar", f"DXF salvo, mas erro no banco:\n{e}")
            return

        # ── Adicionar item à lista sem full-refresh (preserva classificações) ─
        row_data = {
            'id': row_id, 'obra_name': self._current_obra,
            'pavimento_name': pav_name, 'dxf_bruto_path': str(bruto_path),
            'recorte_type': rtype, 'recorte_index': next_idx,
            'output_path': str(out_path), 'entity_count': n_ent,
            'score': 0.0, 'status': 'manual', 'n_torres': torre_num,
            'created_at': now,
        }
        new_item = QListWidgetItem(f"🔶 {rtype}_manual | {pav_name} | {n_ent} ent.")
        new_item.setData(Qt.UserRole, row_data)
        self._list_recortes.addItem(new_item)
        self._list_recortes.setCurrentItem(new_item)

        QMessageBox.information(
            self, "Recortar",
            f"Recorte salvo: {out_path.name}\n{n_ent} entidades."
        )

    # Recorte por seleção (botão "Recortar Seleção")
    # ─────────────────────────────────────────────

    def _run_selection_crop(self):
        """
        Salva APENAS os itens selecionados no canvas BRUTO como novo recorte DXF.
        Usa rubber-band selection: o usuário seleciona a área, depois clica aqui.
        """
        if not self._current_bruto_path or not self._current_obra:
            QMessageBox.warning(self, "Recortar Seleção", "Selecione um bruto primeiro.")
            return

        selected = self.canvas.scene.selectedItems()
        if not selected:
            QMessageBox.warning(
                self, "Recortar Seleção",
                "Nenhum item selecionado.\n"
                "Arraste um box de seleção no viewer e tente novamente."
            )
            return

        bruto_path = self._resolve_dxf_path(self._current_bruto_path)
        try:
            if not bruto_path.exists():
                QMessageBox.warning(self, "Recortar Seleção",
                                    f"Arquivo não encontrado:\n{bruto_path}")
                return
        except OSError:
            QMessageBox.warning(self, "Recortar Seleção",
                                f"Drive inválido: {bruto_path}")
            return

        # ── Diálogo de tipo ───────────────────────────────────────────────────
        dialog = QDialog(self)
        dialog.setWindowTitle("Tipo de Recorte (Seleção)")
        dialog.setMinimumWidth(300)
        dlg_layout = QVBoxLayout(dialog)

        dlg_layout.addWidget(QLabel(f"Itens selecionados: {len(selected)}\nQual tipo de recorte?"))

        btn_group = QButtonGroup(dialog)
        rb_torre   = QRadioButton("🏛 Pavimento Limpo (Torre)")
        rb_detalhe = QRadioButton("📐 Detalhes")
        rb_conv_pil = QRadioButton("📖 Convenção de Pilares")
        rb_torre.setChecked(True)
        btn_group.addButton(rb_torre,   0)
        btn_group.addButton(rb_detalhe, 1)
        btn_group.addButton(rb_conv_pil, 2)
        dlg_layout.addWidget(rb_torre)
        dlg_layout.addWidget(rb_detalhe)
        dlg_layout.addWidget(rb_conv_pil)

        torre_row = QHBoxLayout()
        lbl_torre = QLabel("Número da torre:")
        sb_torre_num = QComboBox()
        sb_torre_num.addItems(["1", "2", "3"])
        torre_row.addWidget(lbl_torre)
        torre_row.addWidget(sb_torre_num)
        torre_row.addStretch()
        dlg_layout.addLayout(torre_row)

        def _toggle_torre(checked):
            lbl_torre.setVisible(rb_torre.isChecked())
            sb_torre_num.setVisible(rb_torre.isChecked())

        rb_torre.toggled.connect(_toggle_torre)
        rb_detalhe.toggled.connect(_toggle_torre)
        rb_conv_pil.toggled.connect(_toggle_torre)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dlg_layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        is_detalhe = rb_detalhe.isChecked()
        is_conv_pil = rb_conv_pil.isChecked()
        torre_num  = int(sb_torre_num.currentText())

        if is_conv_pil:
            rtype    = "convencao_pilares"
            filename = "convencao_pilares_selecao.dxf"
        elif is_detalhe:
            rtype    = "detalhe"
            filename = "detalhes_selecao.dxf"
        else:
            rtype    = "torre"
            filename = f"torre_{torre_num}_selecao.dxf"

        # ── Destino ───────────────────────────────────────────────────────────
        import time, uuid as _uuid, sqlite3
        from datetime import datetime as _dt

        pav_name = bruto_path.stem
        out_dir  = DADOS_OBRAS_ROOT / self._current_obra / "Fase-2_Triagem" / "recortes" / pav_name
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        stem     = Path(filename).stem
        out_path = out_dir / f"{stem}_{ts}.dxf"
        while out_path.exists():
            ts += 1
            out_path = out_dir / f"{stem}_{ts}.dxf"

        # ── Exportar apenas selecionados → DXF ───────────────────────────────
        crop_result = self._export_selection_to_dxf(self.canvas, out_path)

        if crop_result.get("error"):
            QMessageBox.critical(self, "Recortar Seleção",
                                 f"Erro ao exportar recorte:\n{crop_result['error']}")
            return

        n_ent = crop_result.get('entities_copied', 0)

        # ── Persistir no banco ────────────────────────────────────────────────
        DB  = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        now = _dt.now().isoformat()
        row_id = str(_uuid.uuid4())
        try:
            conn = sqlite3.connect(str(DB), timeout=5)
            cur = conn.execute(
                "SELECT COALESCE(MAX(recorte_index), -1) + 1 FROM obra_recortes "
                "WHERE obra_name=? AND pavimento_name=? AND recorte_type=?",
                (self._current_obra, pav_name, rtype)
            )
            next_idx = cur.fetchone()[0]
            conn.execute("""
                INSERT INTO obra_recortes
                    (id, obra_name, pavimento_name, dxf_bruto_path, recorte_type,
                     recorte_index, output_path, bbox_auto, entity_count,
                     score, status, n_torres, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                row_id, self._current_obra, pav_name, str(bruto_path),
                rtype, next_idx, str(out_path), None, n_ent,
                0.0, "manual", 1 if (is_detalhe or is_conv_pil) else torre_num, now,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.warning(self, "Recortar Seleção",
                                f"DXF salvo, mas erro no banco:\n{e}")
            return

        # ── Adicionar à lista ─────────────────────────────────────────────────
        row_data = {
            'id': row_id, 'obra_name': self._current_obra,
            'pavimento_name': pav_name, 'dxf_bruto_path': str(bruto_path),
            'recorte_type': rtype, 'recorte_index': next_idx,
            'output_path': str(out_path), 'entity_count': n_ent,
            'score': 0.0, 'status': 'manual', 'n_torres': torre_num,
            'created_at': now,
        }
        new_item = QListWidgetItem(f"🟣 {rtype}_sel | {pav_name} | {n_ent} ent.")
        new_item.setData(Qt.UserRole, row_data)
        self._list_recortes.addItem(new_item)
        self._list_recortes.setCurrentItem(new_item)

        QMessageBox.information(
            self, "Recortar Seleção",
            f"Recorte de seleção salvo: {out_path.name}\n{n_ent} entidades."
        )

    # ─────────────────────────────────────────────
    # Salvar recorte editado (botão "Salvar")
    def _apply_crop_classification(self):
        """
        Atualiza recorte_type: visual PRIMEIRO, DB depois (com timeout).
        Separar as duas operações garante que a lista sempre renomeia,
        mesmo que o SQLite esteja temporariamente bloqueado.
        """
        if not self._current_selected_recorte:
            return

        new_type = None
        for cls_id, btn in self._crop_class_btns.items():
            if btn.isChecked():
                new_type = cls_id
                break
        if new_type is None:
            return

        row = self._current_selected_recorte
        if row.get('recorte_type') == new_type:
            return  # sem mudança

        # ── 1. Atualiza visual IMEDIATAMENTE (independente do DB) ─────────────
        row['recorte_type'] = new_type

        cur_item = self._current_list_item
        if cur_item:
            cur_item.setData(Qt.UserRole, dict(row))
            ridx   = row.get('recorte_index', 0)
            status = row.get('status', 'auto')
            pav    = row.get('pavimento_name', '')
            score  = row.get('score', 0.0)
            icon   = "✅" if status == 'approved' else ("🔶")
            cur_item.setText(f"{icon} {new_type}_{ridx+1} | {pav} | score={score:.0f}")

        # ── 2. Persiste no DB (timeout=10s, WAL mode, detecção de conflito) ────
        import sqlite3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        try:
            conn = sqlite3.connect(str(DB), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")

            # Detectar conflito: já existe outro recorte do mesmo tipo para este bruto?
            bruto_path = row.get('dxf_bruto_path', '')
            cur = conn.execute(
                "SELECT id, recorte_index FROM obra_recortes "
                "WHERE dxf_bruto_path=? AND recorte_type=? AND id!=?",
                (bruto_path, new_type, row['id'])
            )
            conflicts = cur.fetchall()

            if conflicts:
                # Auto-assign: usar próximo índice disponível para não colidir
                cur2 = conn.execute(
                    "SELECT COALESCE(MAX(recorte_index), -1) + 1 FROM obra_recortes "
                    "WHERE dxf_bruto_path=? AND recorte_type=? AND id!=?",
                    (bruto_path, new_type, row['id'])
                )
                next_idx = cur2.fetchone()[0]
                conn.execute(
                    "UPDATE obra_recortes SET recorte_type=?, recorte_index=? WHERE id=?",
                    (new_type, next_idx, row['id'])
                )
                row['recorte_index'] = next_idx
                # Atualizar label do item na lista
                if cur_item:
                    status = row.get('status', 'auto')
                    pav    = row.get('pavimento_name', '')
                    score  = row.get('score', 0.0)
                    icon   = "✅" if status == 'approved' else "🔶"
                    cur_item.setText(f"{icon} {new_type}_{next_idx+1} | {pav} | score={score:.0f}")
                    cur_item.setData(Qt.UserRole, dict(row))
            else:
                conn.execute(
                    "UPDATE obra_recortes SET recorte_type=? WHERE id=?",
                    (new_type, row['id'])
                )

            conn.commit()
            conn.close()
            print(f"[DiagnosticHub] Reclassificado → {new_type} ✓", flush=True)
        except Exception as e:
            print(f"[DiagnosticHub] Aviso DB reclassificar: {e}", flush=True)

    # ─────────────────────────────────────────────

    def _save_current_crop(self):
        """
        Salva o estado visual atual do canvas diretamente como DXF.

        Exporta os itens QGraphicsScene → novo DXF via ezdxf.
        Isso garante que deleções manuais de entidades no canvas
        sejam persistidas (não recria do arquivo original).
        """
        if not self._current_selected_recorte:
            QMessageBox.warning(self, "Salvar", "Selecione um recorte primeiro.")
            return

        row = self._current_selected_recorte
        output_path = row.get('output_path', '')

        resolved = self._resolve_dxf_path(output_path) if output_path else None
        try:
            out_exists = resolved is not None and resolved.exists()
        except OSError:
            out_exists = False

        if not out_exists:
            QMessageBox.warning(self, "Salvar",
                                f"Arquivo de recorte não encontrado:\n{output_path}")
            return

        # ── Qual canvas está ativo agora? ─────────────────────────────────────
        # Usa o tab visível — se o usuário editou no BRUTO (tab 0), usa self.canvas;
        # se editou no LIMPO (tab 1) ou DETALHES (tab 2), usa o canvas respectivo.
        tab_idx = self._canvas_tabs.currentIndex()
        if tab_idx == 0:
            canvas = self.canvas
        elif tab_idx == 1:
            canvas = self._canvas_limpo
        else:
            canvas = self._canvas_det

        # ── Backup ────────────────────────────────────────────────────────────
        import shutil
        bak = Path(str(resolved) + ".bak")
        try:
            shutil.copy2(str(resolved), str(bak))
        except Exception:
            pass

        # ── Exportar scene → DXF (helper centralizado) ───────────────────────
        crop_result = self._export_scene_to_dxf(canvas, resolved)

        if crop_result.get("error"):
            try:
                shutil.copy2(str(bak), str(resolved))
            except Exception:
                pass
            QMessageBox.critical(self, "Salvar",
                                 f"Erro ao salvar DXF:\n{crop_result['error']}")
            return

        n = crop_result['entities_copied']

        # ── Recarrega o canvas a partir do arquivo salvo ──────────────────────
        doc_data = {
            'id': str(hash(str(resolved))),
            'name': resolved.name,
            'file_path': str(resolved),
            'extension': '.dxf',
        }
        self._load_dxf_on_canvas(canvas, doc_data)

        QMessageBox.information(
            self, "Salvar",
            f"Recorte salvo: {resolved.name}\n"
            f"{n} entidades exportadas.\n"
            f"Backup: {bak.name}"
        )

    def _approve_current_crop(self):
        """Aprova o recorte selecionado.

        Se o recorte é do tipo 'torre', cria automaticamente um projeto na tabela
        projects (Estruturais Pavimentos Limpos) para alimentar a Fase 3.
        """
        if not hasattr(self, '_current_selected_recorte'):
            return
        row = self._current_selected_recorte
        import sqlite3
        from datetime import datetime
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        try:
            conn = sqlite3.connect(str(DB))
            conn.execute(
                "UPDATE obra_recortes SET status='approved', approved_at=? WHERE id=?",
                (datetime.now().isoformat(), row['id'])
            )
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.warning(self, "Aprovar", f"Erro: {e}")
            return

        # ── Sistema de aprendizado: registrar bbox aprovada e recalibrar ─────
        recorte_type = row.get('recorte_type', '')
        output_path  = row.get('output_path', '')
        pav_name_lrn = row.get('pavimento_name', '')
        if self._current_obra and output_path and Path(output_path).exists():
            try:
                from scripts.obra_crop_engine import record_approval_bbox, compute_learned_params
                record_approval_bbox(self._current_obra, pav_name_lrn, recorte_type, output_path)
                params = compute_learned_params(self._current_obra)
                if params.get('samples', 0) >= 2:
                    print(
                        f"[DiagnosticHub] Parâmetros aprendidos atualizados: "
                        f"eps={params.get('eps_factor')}, padding={params.get('padding_pct')}, "
                        f"samples={params.get('samples')}, correction_rate={params.get('correction_rate')}",
                        flush=True
                    )
            except Exception as _lerr:
                print(f"[DiagnosticHub] Aviso aprendizado: {_lerr}", flush=True)

        # ── Se torre aprovada → criar projeto em projects (Pavimentos Limpos) ──
        pav_name = pav_name_lrn  # já extraído acima
        if recorte_type == 'torre' and self.db and self._current_obra:
            if output_path and Path(output_path).exists():
                try:
                    # Verificar se já existe projeto com esse dxf_path (evitar duplicata)
                    conn2 = sqlite3.connect(str(DB))
                    existing = conn2.execute(
                        "SELECT id FROM projects WHERE work_name=? AND dxf_path=?",
                        (self._current_obra, output_path)
                    ).fetchone()
                    conn2.close()

                    if not existing:
                        # Nome do pavimento: extrair parte legível do stem do arquivo bruto
                        display_name = pav_name
                        self.db.create_project(
                            name          = display_name,
                            dxf_path      = output_path,
                            author_name   = "Diagnostic Hub",
                            work_name     = self._current_obra,
                            pavement_name = pav_name,
                            description   = f"Torre recortada e aprovada via Diagnostic Hub",
                        )
                        print(f"[DiagnosticHub] Projeto criado: {display_name} ({output_path})", flush=True)
                except Exception as e:
                    print(f"[DiagnosticHub] Aviso: falha ao criar projeto Pavimento Limpo: {e}", flush=True)

        self._refresh_recortes_list(self._current_bruto_path)
        self._refresh_brutos_list(self._current_obra)

    def _delete_current_crop(self):
        """
        Exclui o recorte selecionado — remove do banco E apaga o arquivo DXF.
        Fluxo correto: se o auto errou, exclui → faz recorte manual → salva → aprova.
        """
        if not hasattr(self, '_current_selected_recorte') or not self._current_selected_recorte:
            return
        row = self._current_selected_recorte

        confirm = QMessageBox.question(
            self, "Excluir recorte",
            f"Excluir este recorte e apagar o arquivo DXF?\n\n"
            f"Tipo: {row.get('recorte_type', '?')}  |  "
            f"Índice: {row.get('recorte_index', 0)}\n\n"
            "Para refazer, use '✂ Recortar' manualmente.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        import sqlite3, os
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")

        # Apagar arquivo DXF
        out_path = row.get('output_path', '')
        if out_path:
            resolved = self._resolve_dxf_path(out_path)
            try:
                if resolved.exists():
                    resolved.unlink()
                    # Apagar backup também se existir
                    bak = Path(str(resolved) + ".bak")
                    if bak.exists():
                        bak.unlink()
            except Exception as e:
                print(f"[DiagnosticHub] Erro ao apagar DXF: {e}", flush=True)

        # Remover do banco
        try:
            conn = sqlite3.connect(str(DB), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("DELETE FROM obra_recortes WHERE id=?", (row['id'],))
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.warning(self, "Excluir", f"Erro ao remover do banco:\n{e}")
            return

        self._current_selected_recorte = None
        self._btn_approve_crop.setEnabled(False)
        self._btn_delete_crop.setEnabled(False)
        self._btn_save_crop.setEnabled(False)
        self._refresh_recortes_list(self._current_bruto_path)
        self._refresh_brutos_list(self._current_obra)

    # ─────────────────────────────────────────────
    # Pré-processar Todos — Batch Structural Analyzer (Fase 3)
    # ─────────────────────────────────────────────

    def _get_obra_root_path(self, obra_name: str) -> Path:
        """Retorna o diretório raiz da obra no filesystem."""
        return Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS") / obra_name

    def _load_preprocess_estado(self, obra_name: str):
        """Carrega estado persistido de pré-processamento e atualiza UI."""
        estado_path = self._get_obra_root_path(obra_name) / "pre_processamento_estado.json"
        if not estado_path.exists():
            self._lbl_preprocess_feedback.setText("—  Ficha não gerada. Clique em ⚡ Interpretar Obra Toda.")
            self._lbl_preprocess_feedback.setStyleSheet(
                f"color: {Colors.TEXT_DIM}; font-size: 10px; background: rgba(0, 0, 0, 46);"
                " border: 1px solid #2a2f3d; border-radius: 4px; padding: 5px 8px;"
            )
            # Limpa ficha tab
            self._ficha_status_lbl.setText("⏳  Execute '⚡ Interpretar Obra Toda' para gerar a ficha.")
            self._ficha_status_lbl.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent;"
            )
            return
        try:
            estado = json.loads(estado_path.read_text(encoding='utf-8'))
            ficha  = estado.get('ficha', {})
            last   = estado.get('last_run', '')
            from datetime import datetime as _dt
            ts = _dt.fromisoformat(last).strftime("%d/%m/%Y %H:%M") if last else "?"
            n_pavs = len(ficha.get('pavimentos', []))
            totais = ficha.get('totais', {})
            fb = (
                f"✅ Ficha gerada em {ts}\n"
                f"{n_pavs} pav | "
                f"{totais.get('pilares',0)}P / {totais.get('vigas',0)}V / {totais.get('lajes',0)}L"
            )
            self._lbl_preprocess_feedback.setStyleSheet(
                "color: #00c864; font-size: 10px; background: rgba(0, 0, 0, 46);"
                " border: 1px solid #00c864; border-radius: 4px; padding: 5px 8px;"
            )
            self._lbl_preprocess_feedback.setText(fb)
            self.refresh_ficha_tab(ficha)
        except Exception as exc:
            self._lbl_preprocess_feedback.setText(f"⚠ Erro ao ler estado: {exc}")

    def _run_pre_process_all(self, analysis_mode: str = "baseline"):
        """Inicia o worker de interpretação em batch (Fase 3 — Structural Analyzer)."""
        if not self._current_obra:
            QMessageBox.warning(self, "Interpretar Obra", "Selecione uma obra primeiro.")
            return

        obra_path = self._get_obra_root_path(self._current_obra)
        estado_name = "pre_processamento_estado.json"
        if analysis_mode == "context":
            estado_name = "pre_processamento_estado_context.json"
        elif analysis_mode == "engrev_assisted":
            estado_name = "pre_processamento_estado_engrev_assisted.json"
        estado_path = obra_path / estado_name

        # Se já processado, perguntar se quer reprocessar
        if estado_path.exists() and not QMessageBox.question(
            self,
            "Fichas F2 já geradas",
            f"A obra '{self._current_obra}' já possui as fichas [F2] dos pavimentos geradas.\n\n"
            "Deseja reprocessar tudo (pode demorar)?",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:
            return

        # Iniciar worker
        self._preprocess_worker = PreProcessAllWorker(
            obra_name=self._current_obra,
            obra_path=str(obra_path),
            force=True,
            analysis_mode=analysis_mode,
            parent=self,
        )
        self._preprocess_worker.progress.connect(self._on_preprocess_progress)
        self._preprocess_worker.torre_result.connect(self._on_preprocess_torre_result)
        self._preprocess_worker.finished.connect(self._on_preprocess_finished)
        self._preprocess_worker.error.connect(self._on_preprocess_error)

        # Atualizar UI
        self._set_preprocess_buttons_enabled(False)
        self._btn_cancel_preprocess.setVisible(True)
        self._lbl_preprocess_feedback.setText("⏳  Interpretação em andamento…")
        self._lbl_preprocess_feedback.setStyleSheet(
            "color: #7ab3e0; font-size: 10px; background: rgba(0, 0, 0, 46);"
            " border: 1px solid #7ab3e0; border-radius: 4px; padding: 5px 8px;"
        )

        # Mostrar ficha tab com indicador de progresso
        self._canvas_tabs.setCurrentIndex(3)
        self._ficha_status_lbl.setText("⏳  Interpretando obra… aguarde.")
        self._ficha_status_lbl.setStyleSheet(
            "color: #7ab3e0; font-size: 11px; background: transparent;"
        )
        # Limpar conteúdo anterior
        while self._ficha_content_lay.count():
            item = self._ficha_content_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Barra de progresso inline na ficha tab
        self._inline_progress = QProgressBar()
        self._inline_progress.setRange(0, 100)
        self._inline_progress.setValue(0)
        self._inline_progress.setStyleSheet(
            f"QProgressBar {{ border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;"
            f" background: {Colors.BG_PANEL}; height: 10px; }}"
            f"QProgressBar::chunk {{ background: #9B59B6; border-radius: 4px; }}"
        )
        self._ficha_content_lay.addWidget(self._inline_progress)
        self._inline_log = QLabel("")
        self._inline_log.setWordWrap(True)
        self._inline_log.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 10px; background: transparent;"
        )
        self._ficha_content_lay.addWidget(self._inline_log)
        self._ficha_content_lay.addStretch()

        self._preprocess_worker.start()
        print(f"[DiagnosticHub] PreProcess iniciado: {self._current_obra} mode={analysis_mode}", flush=True)

    def _cancel_pre_process(self):
        """Aborta o worker de pré-processamento."""
        if self._preprocess_worker and self._preprocess_worker.isRunning():
            self._preprocess_worker.abort()
            self._lbl_preprocess_feedback.setText("⏹  Cancelado pelo usuário.")
            self._lbl_preprocess_feedback.setStyleSheet(
                f"color: {Colors.TEXT_DIM}; font-size: 10px; background: rgba(0, 0, 0, 46);"
                " border: 1px solid #2a2f3d; border-radius: 4px; padding: 5px 8px;"
            )
        self._set_preprocess_buttons_enabled(True)
        self._btn_cancel_preprocess.setVisible(False)

    def _on_preprocess_progress(self, pct: int, msg: str):
        """Atualiza barra de progresso inline na ficha tab."""
        if hasattr(self, '_inline_progress'):
            self._inline_progress.setValue(pct)
        if hasattr(self, '_inline_log'):
            self._inline_log.setText(msg)
        self._lbl_preprocess_feedback.setText(f"⏳ {pct}% — {msg[:60]}")

    def _on_preprocess_torre_result(self, result: dict):
        """Adiciona linha de resultado de torre na ficha tab em tempo real."""
        if not hasattr(self, '_ficha_content_lay'):
            return
        pav  = result.get('pav_name', '?')
        tidx = result.get('torre_idx', 0)
        n_p  = result.get('n_pilares', 0)
        n_v  = result.get('n_vigas', 0)
        n_l  = result.get('n_lajes', 0)
        st   = result.get('status', 'ok')
        color = '#00c864' if st == 'ok' else '#e6b400'
        row_lbl = QLabel(
            f"<span style='color:#7ab3e0'>{pav}/t{tidx+1}</span>  "
            f"<span style='color:#9B59B6'>P:{n_p}</span>  "
            f"<span style='color:#2980B9'>V:{n_v}</span>  "
            f"<span style='color:#27AE60'>L:{n_l}</span>  "
            f"<span style='color:{color}'>{'✅' if st=='ok' else '⚠'}</span>"
        )
        row_lbl.setStyleSheet(
            f"font-size: 10px; background: {Colors.BG_CARD}; "
            "border-radius: 3px; padding: 2px 6px;"
        )
        # Insert before the last stretch
        count = self._ficha_content_lay.count()
        insert_at = max(0, count - 1)
        self._ficha_content_lay.insertWidget(insert_at, row_lbl)

    def _on_preprocess_finished(self, ficha: dict):
        """Recebe a ficha completa e atualiza a UI."""
        self._set_preprocess_buttons_enabled(True)
        self._btn_cancel_preprocess.setVisible(False)
        self._preprocess_worker = None

        from datetime import datetime as _dt
        totais = ficha.get('totais', {})
        n_pav  = len(ficha.get('pavimentos', []))
        ts     = _dt.now().strftime("%d/%m %H:%M")
        fb = (
            f"✅ Ficha gerada em {ts}\n"
            f"{n_pav} pav | "
            f"{totais.get('pilares',0)}P / {totais.get('vigas',0)}V / {totais.get('lajes',0)}L"
        )
        self._lbl_preprocess_feedback.setStyleSheet(
            "color: #00c864; font-size: 10px; background: rgba(0, 0, 0, 46);"
            " border: 1px solid #00c864; border-radius: 4px; padding: 5px 8px;"
        )
        self._lbl_preprocess_feedback.setText(fb)

        self.refresh_ficha_tab(ficha)
        print(f"[DiagnosticHub] PreProcess concluído — {n_pav} pavimento(s)", flush=True)

        # Dispara RAG automaticamente (fase 2 implícita)
        self._lbl_rag_feedback.setText("⏳ Indexando RAG semântico...")
        self._run_rag_pipeline()

        # Notifica main.py para refreshar combos e abrir Structural Analyzer
        self.preprocess_complete.emit(self._current_obra or "")

    def _on_preprocess_error(self, msg: str):
        """Exibe erro do worker."""
        self._set_preprocess_buttons_enabled(True)
        self._btn_cancel_preprocess.setVisible(False)
        self._preprocess_worker = None
        self._lbl_preprocess_feedback.setStyleSheet(
            "color: #e74c3c; font-size: 10px; background: rgba(0, 0, 0, 46);"
            " border: 1px solid #e74c3c; border-radius: 4px; padding: 5px 8px;"
        )
        self._lbl_preprocess_feedback.setText(f"❌ Erro: {msg[:120]}")
        self._ficha_status_lbl.setText(f"❌ Erro no processamento.")
        self._ficha_status_lbl.setStyleSheet("color: #e74c3c; font-size: 11px; background: transparent;")
        QMessageBox.warning(self, "Erro — Interpretar Obra", msg[:400])

    # ─────────────────────────────────────────────
    # RAG Pipeline — handlers
    # ─────────────────────────────────────────────

    def _run_rag_pipeline(self):
        """Dispara RagPipelineWorker — chamado automaticamente após Interpretar Obra Toda."""
        obra = self._current_obra
        if not obra:
            return  # silencioso — sempre chamado via pipeline interno
        if self._rag_worker and self._rag_worker.isRunning():
            return  # já em execução

        force = False  # incremental por padrão (botão manual removido)

        self._set_preprocess_buttons_enabled(False)
        self._rag_progress.setValue(0)
        self._rag_progress.setVisible(True)
        self._lbl_rag_feedback.setText(f"⏳ Indexando RAG para {obra}...")

        self._rag_worker = RagPipelineWorker(obra, force=force, parent=self)
        self._rag_worker.progress.connect(self._on_rag_progress)
        self._rag_worker.finished.connect(self._on_rag_finished)
        self._rag_worker.error.connect(self._on_rag_error)
        self._rag_worker.start()

    def _on_rag_progress(self, pct: int, msg: str):
        self._rag_progress.setValue(pct)
        self._lbl_rag_feedback.setText(f"⏳ {pct}% — {msg[:80]}")

    def _on_rag_finished(self, result: dict):
        self._set_preprocess_buttons_enabled(True)
        self._rag_progress.setVisible(False)
        self._rag_worker = None

        status    = result.get("status", "ok")
        chunks    = result.get("doc_chunks", 0)
        dxfs      = result.get("dxf_indexed", 0)
        triagem   = result.get("triagem_rows", 0)
        duration  = result.get("duration_s", 0)
        errs      = result.get("errors", [])

        color = "#00c864" if status == "ok" else "#e6b400"
        icon  = "✅" if status == "ok" else "⚠"
        self._lbl_rag_feedback.setStyleSheet(
            f"color: {color}; font-size: 10px; background: rgba(0, 0, 0, 46);"
            " border: 1px solid; border-radius: 4px; padding: 5px 8px;"
        )
        self._lbl_rag_feedback.setText(
            f"{icon} RAG concluído em {duration:.0f}s\n"
            f"Docs: {chunks} chunks | DXFs: {dxfs} | Triagem: {triagem}"
            + (f"\n⚠ {len(errs)} erro(s)" if errs else "")
        )

    def _on_rag_error(self, msg: str):
        self._set_preprocess_buttons_enabled(True)
        self._rag_progress.setVisible(False)
        self._rag_worker = None
        self._lbl_rag_feedback.setStyleSheet(
            "color: #e74c3c; font-size: 10px; background: rgba(0, 0, 0, 46);"
            " border: 1px solid #e74c3c; border-radius: 4px; padding: 5px 8px;"
        )
        self._lbl_rag_feedback.setText(f"❌ Erro RAG: {msg[:120]}")
        QMessageBox.warning(self, "Erro — RAG Semântico", msg[:400])

    # ─────────────────────────────────────────────
    # Ficha da Obra tab (Tab 3 do _canvas_tabs)
    # ─────────────────────────────────────────────


    def _build_ficha_f3_tab(self) -> QWidget:
        container = QWidget()
        main_lay = QVBoxLayout(container)
        main_lay.setContentsMargins(16, 14, 16, 14)
        main_lay.setSpacing(10)
        hdr = QLabel("📋 Ficha Global [F3]")
        hdr.setStyleSheet("color: #b450c8; font-size: 13px; font-weight: bold; background: transparent;")
        main_lay.addWidget(hdr)
        sep = QLabel("━" * 60)
        sep.setStyleSheet("color: #333333; font-size: 10px; background: transparent;")
        main_lay.addWidget(sep)
        self._ficha_f3_status_lbl = QLabel("⏳  Execute 'Analisar todas fichas e gerar Ficha da Obra [F3]' no menu lateral.")
        self._ficha_f3_status_lbl.setWordWrap(True)
        self._ficha_f3_status_lbl.setStyleSheet("color: #8a9ab5; font-size: 11px; background: transparent;")
        main_lay.addWidget(self._ficha_f3_status_lbl)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('''
            QScrollArea { border: none; background: #1a1a1a; }
            QScrollBar:vertical { background: #2a2a2a; width: 8px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #4a4a4a; border-radius: 4px; }
        ''')
        self._ficha_f3_content = QWidget()
        self._ficha_f3_content.setStyleSheet("background: #1a1a1a;")
        self._ficha_f3_content_lay = QVBoxLayout(self._ficha_f3_content)
        self._ficha_f3_content_lay.setContentsMargins(0, 4, 0, 4)
        self._ficha_f3_content_lay.setSpacing(8)
        self._ficha_f3_content_lay.addStretch()
        scroll.setWidget(self._ficha_f3_content)
        main_lay.addWidget(scroll, 1)
        return container

    def _run_process_f3(self):
        if not getattr(self, '_current_obra', None):
            QMessageBox.warning(self, "Aviso", "Selecione uma obra primeiro.")
            return
        self._btn_process_f3.setEnabled(False)
        self._btn_process_detalhes.setEnabled(False)
        self._btn_process_limpo.setEnabled(False)
        self._btn_cancel_preprocess.setVisible(True)
        self._ficha_f3_status_lbl.setText("⏳ Gerando Ficha Global F3 (Consolidando fichas granulares N2)...")
        self._ficha_f3_status_lbl.setStyleSheet("color: #e6b400; font-size: 11px; font-weight: bold; background: transparent;")
        
        # Consolida de verdade!
        try:
            import sys as _sys
            from pathlib import Path as _P
            scripts_dir = str(_P(__file__).resolve().parent.parent.parent.parent / "scripts")
            if scripts_dir not in _sys.path:
                _sys.path.insert(0, scripts_dir)
            from motor_reverso_obra import consolidar_ficha_obra, salvar_ficha_obra
            DB_PATH = str(_P("D:/Agente-cad-PYSIDE/project_data.vision"))
            # O motor atual gera e depois salva
            resumo = consolidar_ficha_obra(self._current_obra)
            salvar_ficha_obra(self._current_obra, '', resumo)
        except Exception as e:
            print("Erro ao consolidar F3:", e)
        
        QTimer.singleShot(500, self._finish_process_f3)

    def _finish_process_f3(self):
        self._btn_process_f3.setEnabled(True)
        self._btn_process_detalhes.setEnabled(True)
        self._btn_process_limpo.setEnabled(True)
        self._btn_cancel_preprocess.setVisible(False)
        self._ficha_f3_status_lbl.setText("✅ Ficha Global F3 Carregada!")
        self._ficha_f3_status_lbl.setStyleSheet("color: #00c864; font-size: 11px; font-weight: bold; background: transparent;")
        
        # Limpar o conteudo atual da F3
        while self._ficha_f3_content_lay.count():
            item = self._ficha_f3_content_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # Buscar a F3 do banco e renderizar como Dashboard
        try:
            import sqlite3
            import json
            from pathlib import Path as _P
            DB_PATH = str(_P("D:/Agente-cad-PYSIDE/project_data.vision"))
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute("SELECT resumo_json FROM reverse_eng_obra_ficha WHERE obra_name=? ORDER BY gerado_at DESC LIMIT 1", (self._current_obra,))
            row = cur.fetchone()
            
            if row:
                f3_data = json.loads(row[0])
                
                # Extrair dados para o dashboard
                total_fichas = f3_data.get('total_fichas', 0)
                conf_media = f3_data.get('confianca_media_geral', 0.0) * 100
                insights = f3_data.get('insights', [])
                pavimentos = f3_data.get('pavimentos', [])
                
                # Montar HTML premium
                html = f"""
                <div style="font-family: 'Segoe UI', Arial, sans-serif; color: #E2E8F0; max-width: 800px; padding: 10px;">
                    <div style="background: rgba(180, 80, 200, 0.15); border-left: 4px solid #b450c8; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
                        <h2 style="margin: 0 0 10px 0; color: #b450c8; font-size: 18px;">📋 Ficha Global [F3] - Relatório Executivo</h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 5px 0;"><b>Total de Peças Analisadas (F5):</b> <span style="color:#00c864;">{total_fichas}</span></td>
                                <td style="padding: 5px 0;"><b>Grau de Confiança (IA):</b> <span style="color:#e6b400;">{conf_media:.1f}%</span></td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><b>Pavimentos Cobertos:</b> {len(pavimentos)}</td>
                                <td style="padding: 5px 0;"><b>Motor Versão:</b> N2 → N4</td>
                            </tr>
                        </table>
                    </div>
                    
                    <h3 style="color: #94A3B8; font-size: 14px; border-bottom: 1px solid #334155; padding-bottom: 5px;">⚠️ Insights do Structural Analyzer</h3>
                    <ul style="margin: 10px 0; padding-left: 20px; line-height: 1.6;">
                """
                
                if insights:
                    for insight in insights:
                        html += f"<li>{insight}</li>"
                else:
                    html += "<li style='color: #64748B;'>Nenhum desvio crítico ou outlier foi encontrado pelo motor.</li>"
                    
                html += """
                    </ul>
                    
                    <h3 style="color: #94A3B8; font-size: 14px; border-bottom: 1px solid #334155; padding-bottom: 5px; margin-top: 20px;">📦 Distribuição Granular (Resumo Bruto)</h3>
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 10px; border-radius: 4px;">
                """
                
                # Montar um mini json das stats para nao poluir
                stats = f3_data.get('por_classe_stats', {})
                html += f'<pre style="color:#8b9eb3; font-family: monospace; font-size: 11px; margin: 0;">{json.dumps(stats, indent=2, ensure_ascii=False)}</pre>'
                
                html += "</div></div>"
                
                lbl = QLabel(html)
                lbl.setWordWrap(True)
                lbl.setTextFormat(Qt.RichText)
                self._ficha_f3_content_lay.addWidget(lbl)
            else:
                lbl = QLabel("Nenhuma Ficha F3 consolidada encontrada para esta obra.")
                lbl.setStyleSheet("color: #8a9ab5;")
                self._ficha_f3_content_lay.addWidget(lbl)
            conn.close()
        except Exception as e:
            lbl = QLabel(f"Erro ao exibir F3: {e}")
            self._ficha_f3_content_lay.addWidget(lbl)
        
        self._ficha_f3_content_lay.addStretch()

    def _build_ficha_tab(self) -> QWidget:

        """
        Constrói o widget da aba 📋 FICHA DA OBRA.

        Exibe o resumo pré-interpretativo gerado pelo motor de Pré-processar Todos:
        - Quantidades (PIL / VIG / LAJ) por pavimento
        - Nível de cada pavimento (chegada / saída)
        - Lajes com níveis distintos
        - Status de processamento por pavimento

        Enquanto o motor não rodou: mostra estado vazio com instruções.
        """
        container = QWidget()
        container.setStyleSheet(f"background: {Colors.BG_DEEP};")
        main_lay = QVBoxLayout(container)
        main_lay.setContentsMargins(16, 14, 16, 14)
        main_lay.setSpacing(10)

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        hdr = QLabel("📋 Ficha Pré-Pavimentos/Detalhes [F2]")
        hdr.setStyleSheet(
            f"color: #e6b400; font-size: 13px; font-weight: bold; background: transparent;"
        )
        main_lay.addWidget(hdr)

        sep = QLabel("─" * 60)
        sep.setStyleSheet(f"color: {Colors.BORDER_DEFAULT}; font-size: 10px; background: transparent;")
        main_lay.addWidget(sep)

        # ── Status global ──────────────────────────────────────────────────────
        self._ficha_status_lbl = QLabel("⏳  Execute '⚡ Interpretar Obra Toda' para gerar a ficha.")
        self._ficha_status_lbl.setWordWrap(True)
        self._ficha_status_lbl.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent;"
        )
        main_lay.addWidget(self._ficha_status_lbl)

        # ── Área scrollável com conteúdo da ficha ─────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {Colors.BG_DEEP}; }}
            QScrollBar:vertical {{
                background: {Colors.BG_SECONDARY}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER_DEFAULT}; border-radius: 4px;
            }}
        """)

        self._ficha_content = QWidget()
        self._ficha_content.setStyleSheet(f"background: {Colors.BG_DEEP};")
        self._ficha_content_lay = QVBoxLayout(self._ficha_content)
        self._ficha_content_lay.setContentsMargins(0, 4, 0, 4)
        self._ficha_content_lay.setSpacing(8)
        self._ficha_content_lay.addStretch()

        scroll.setWidget(self._ficha_content)
        main_lay.addWidget(scroll, 1)

        # ── Rodapé: timestamp último processamento ────────────────────────────
        self._ficha_footer_lbl = QLabel("Última geração: —")
        self._ficha_footer_lbl.setStyleSheet(
            f"color: {Colors.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        main_lay.addWidget(self._ficha_footer_lbl)

        return container

    def refresh_ficha_tab(self, ficha_data: dict):
        """
        Atualiza o conteúdo da aba FICHA com os dados gerados pelo motor.

        ficha_data esperado:
        {
          "obra": str,
          "gerado_em": str (ISO),
          "pavimentos": [
            {
              "nome": str,
              "n_pilares": int, "n_vigas": int, "n_lajes": int,
              "nivel_chegada": float, "nivel_saida": float,
              "lajes_nivel_distinto": bool,
              "status": "ok"|"parcial"|"erro"
            }, ...
          ],
          "totais": {"pilares": int, "vigas": int, "lajes": int},
          "resumo_semantico": str  # texto gerado pelo motor RAG
        }
        """
        from datetime import datetime as _dt

        # Limpar conteúdo anterior
        while self._ficha_content_lay.count():
            item = self._ficha_content_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        obra  = ficha_data.get("obra", "—")
        totais = ficha_data.get("totais", {})
        pavs   = ficha_data.get("pavimentos", [])
        gerado = ficha_data.get("gerado_em", "")

        # ── Totais globais ───────────────────────────────────────────────
        totais_frame = QFrame()
        totais_frame.setStyleSheet(
            f"background: {Colors.BG_CARD}; border: 1px solid #e6b400; border-radius: 6px; padding: 8px;"
        )
        tf_lay = QHBoxLayout(totais_frame)
        tf_lay.setContentsMargins(12, 8, 12, 8)
        tf_lay.setSpacing(24)

        for label, val, color in [
            ("Pilares", totais.get("pilares", 0), "#9B59B6"),
            ("Vigas",   totais.get("vigas",   0), "#2980B9"),
            ("Lajes",   totais.get("lajes",   0), "#27AE60"),
            ("Pavimentos", len(pavs), "#e6b400"),
        ]:
            chip = QLabel(f"<b style='color:{color}'>{val}</b><br><span style='font-size:10px;color:#888'>{label}</span>")
            chip.setAlignment(Qt.AlignCenter)
            chip.setStyleSheet("background: transparent;")
            tf_lay.addWidget(chip)

        self._ficha_content_lay.addWidget(totais_frame)

        # ── Resumo semântico (se houver) ─────────────────────────────────
        resumo = ficha_data.get("resumo_semantico", "")
        if resumo:
            rsm_lbl = QLabel(resumo)
            rsm_lbl.setWordWrap(True)
            rsm_lbl.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; font-size: 10px; background: {Colors.BG_PANEL};"
                " border: 1px solid #333; border-radius: 4px; padding: 8px;"
            )
            self._ficha_content_lay.addWidget(rsm_lbl)

        # ── Tabela por pavimento ─────────────────────────────────────────
        for pav in pavs:
            status = pav.get("status", "ok")
            status_color = {"ok": "#00c864", "parcial": "#e6b400", "erro": "#e74c3c"}.get(status, "#888")
            status_icon  = {"ok": "✅", "parcial": "⚠", "erro": "❌"}.get(status, "—")

            pf = QFrame()
            pf.setStyleSheet(
                f"background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_DEFAULT};"
                f" border-left: 3px solid {status_color}; border-radius: 4px;"
            )
            pf_lay = QHBoxLayout(pf)
            pf_lay.setContentsMargins(10, 6, 10, 6)
            pf_lay.setSpacing(16)

            nome_lbl = QLabel(f"<b>{pav.get('nome', '—')}</b>")
            nome_lbl.setFixedWidth(130)
            nome_lbl.setStyleSheet("color: #00d4ff; font-size: 11px; background: transparent;")
            pf_lay.addWidget(nome_lbl)

            for lbl, val, color in [
                (f"PIL", pav.get("n_pilares", 0), "#9B59B6"),
                (f"VIG", pav.get("n_vigas",   0), "#2980B9"),
                (f"LAJ", pav.get("n_lajes",   0), "#27AE60"),
            ]:
                chip = QLabel(f"<span style='color:{color};font-weight:bold'>{lbl}</span> {val}")
                chip.setStyleSheet("font-size: 10px; background: transparent; color: #ccc;")
                pf_lay.addWidget(chip)

            nivel_txt = f"nível {pav.get('nivel_chegada', 0):.0f}→{pav.get('nivel_saida', 0):.0f} cm"
            nivel_lbl = QLabel(nivel_txt)
            nivel_lbl.setStyleSheet("color: #888; font-size: 10px; background: transparent;")
            pf_lay.addWidget(nivel_lbl)

            if pav.get("lajes_nivel_distinto"):
                dist_lbl = QLabel("↕ lajes distintas")
                dist_lbl.setStyleSheet("color: #e6b400; font-size: 10px; background: transparent;")
                pf_lay.addWidget(dist_lbl)

            pf_lay.addStretch()
            pf_lay.addWidget(QLabel(f"{status_icon}"))

            self._ficha_content_lay.addWidget(pf)

        self._ficha_content_lay.addStretch()

        # Atualizar labels de status e rodapé
        ts = _dt.fromisoformat(gerado).strftime("%d/%m/%Y %H:%M") if gerado else "—"
        self._ficha_status_lbl.setText(
            f"✅  Ficha de '{obra}' gerada — {len(pavs)} pavimento(s) processado(s)."
        )
        self._ficha_status_lbl.setStyleSheet(
            "color: #00c864; font-size: 11px; background: transparent;"
        )
        self._ficha_footer_lbl.setText(f"Última geração: {ts}")

    def _on_canvas_tab_changed(self, idx: int):
        """Atualiza estado ao trocar aba do canvas."""
        pass

    def _on_work_changed_hub(self, _):
        """Atualiza ComboBox quando obra ativa muda no coordinator."""
        QTimer.singleShot(200, self._populate_obras_combo)

    # ─────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────

    def open_bruto(self, obra_name: str, file_path: str):
        """
        Navega para a obra e pré-seleciona o DXF bruto na lista.
        Chamado externamente (ex: ProjectManager → botão ✂ Recortar).
        """
        if not obra_name or not file_path:
            return

        # 1. Garantir que o ComboBox está populado e selecionar a obra
        self._populate_obras_combo()
        idx = self._combo_obra.findText(obra_name)
        if idx >= 0:
            self._combo_obra.setCurrentIndex(idx)
        else:
            # Obra ainda não está no combo — adicionar e selecionar
            self._combo_obra.addItem(obra_name)
            self._combo_obra.setCurrentText(obra_name)

        # 2. Garantir que a lista de brutos foi carregada, então selecionar o item
        self._current_obra = obra_name
        self._refresh_brutos_list(obra_name)

        # 3. Encontrar e selecionar o item correspondente ao file_path
        file_name = Path(file_path).name
        for i in range(self._list_brutos.count()):
            item = self._list_brutos.item(i)
            row_data = item.data(Qt.UserRole) or {}
            if row_data.get('file_path') == file_path or row_data.get('file_name') == file_name:
                self._list_brutos.setCurrentItem(item)
                self._on_bruto_selected(item)
                return

    # ─────────────────────────────────────────────
    # Fase-3 Panel Construction
    # ─────────────────────────────────────────────

    def _build_fase3_panel(self) -> QFrame:
        """Painel duplo: linha 1 = Fase-3 extração | linha 2 = Pipeline Completo."""
        panel = QFrame()
        panel.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_SECONDARY};
                border-top: 1px solid {Colors.ACCENT_BLUE};
            }}
            QLabel {{ color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_MD}; }}
            QPushButton {{
                background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT};
                border-radius: {Radius.MD}; padding: 4px 14px;
                font-weight: bold; font-size: {Fonts.SIZE_MD};
            }}
            QPushButton:hover {{ background: {Colors.ACCENT_BLUE_HOVER}; }}
            QPushButton:disabled {{ background: {Colors.BORDER_DEFAULT}; color: {Colors.TEXT_DIM}; }}
            QPushButton#pipeline_btn {{
                background: rgba(26, 74, 26, 1); border: 1px solid {Colors.ACCENT_SUCCESS};
                font-size: {Fonts.SIZE_MD}; padding: 3px 12px;
            }}
            QPushButton#pipeline_btn:hover {{ background: {Colors.ACCENT_SUCCESS}; }}
            QCheckBox {{ color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_MD}; }}
            QProgressBar {{
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: {Radius.SM};
                background: {Colors.BG_PANEL}; height: 7px;
            }}
            QProgressBar::chunk {{ background: {Colors.ACCENT_BLUE}; border-radius: {Radius.SM}; }}
        """)

        vlay = QVBoxLayout(panel)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # ── Linha 1: Fase-3 ──────────────────────
        row1 = QFrame()
        row1.setFixedHeight(52)
        r1 = QHBoxLayout(row1)
        r1.setContentsMargins(12, 4, 12, 4)
        r1.setSpacing(8)

        lbl_title = QLabel("⚙ <b>Fase-3</b>: Interpretação & Extração")
        lbl_title.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-size: {Fonts.SIZE_LG};")
        r1.addWidget(lbl_title)

        self._lbl_fase3_obra = QLabel("Nenhuma obra selecionada")
        self._lbl_fase3_obra.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_MD};")
        r1.addWidget(self._lbl_fase3_obra)

        r1.addStretch()

        self._fase3_progress = QProgressBar()
        self._fase3_progress.setFixedWidth(120)
        self._fase3_progress.setRange(0, 100)   # 0-100% real
        self._fase3_progress.setValue(0)
        self._fase3_progress.setVisible(False)
        r1.addWidget(self._fase3_progress)

        self._lbl_fase3_status = QLabel("")
        self._lbl_fase3_status.setFixedWidth(160)
        self._lbl_fase3_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM};")
        r1.addWidget(self._lbl_fase3_status)

        self._chk_fase3_force = QCheckBox("Forçar")
        self._chk_fase3_force.setToolTip("Forçar re-extração mesmo se Fase-3 já existe")
        r1.addWidget(self._chk_fase3_force)

        self._btn_fase3_run = QPushButton("▶ Interpretar DXF")
        self._btn_fase3_run.setFixedWidth(140)
        self._btn_fase3_run.clicked.connect(self._run_fase3)
        r1.addWidget(self._btn_fase3_run)

        vlay.addWidget(row1)

        # ── Linha 2: Pipeline Completo ───────────
        row2 = QFrame()
        row2.setFixedHeight(36)
        row2.setStyleSheet(f"background: {Colors.BG_DEEP}; border-top: 1px solid {Colors.BORDER_SUBTLE};")
        r2 = QHBoxLayout(row2)
        r2.setContentsMargins(12, 4, 12, 4)
        r2.setSpacing(8)

        lbl_pipe = QLabel("&#9654;&#9654; <b>Pipeline E2E</b>:")   # ▶▶ seguro em qualquer fonte
        lbl_pipe.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-size: {Fonts.SIZE_MD};")
        r2.addWidget(lbl_pipe)

        self._pipeline_progress = QProgressBar()
        self._pipeline_progress.setFixedWidth(120)
        self._pipeline_progress.setRange(0, 100)   # 0-100% real
        self._pipeline_progress.setValue(0)
        self._pipeline_progress.setVisible(False)
        r2.addWidget(self._pipeline_progress)

        self._lbl_pipeline_status = QLabel("")
        self._lbl_pipeline_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM};")
        r2.addWidget(self._lbl_pipeline_status)

        r2.addStretch()

        self._chk_pipeline_force = QCheckBox("Forçar")
        self._chk_pipeline_force.setToolTip("Reprocessar mesmo se outputs existem (--force)")
        r2.addWidget(self._chk_pipeline_force)

        self._btn_pipeline = QPushButton("▶▶ Pipeline Completo (F1→F8)")
        self._btn_pipeline.setObjectName("pipeline_btn")
        self._btn_pipeline.setFixedWidth(210)
        self._btn_pipeline.setToolTip("Roda pipeline_e2e.py — todas as 8 fases em sequência")
        self._btn_pipeline.clicked.connect(self._run_pipeline_completo)
        r2.addWidget(self._btn_pipeline)

        vlay.addWidget(row2)

        # ── CAD-11: Linha "Gerar DXF STOG" ───────────────────────────────────
        row3 = QWidget()
        r3 = QHBoxLayout(row3)
        r3.setContentsMargins(0, 4, 0, 4)
        r3.setSpacing(6)

        lbl_r3 = QLabel("CAD:")
        lbl_r3.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM}; font-weight: bold; min-width: 30px;")
        r3.addWidget(lbl_r3)

        self._lbl_dxf_status = QLabel("Pronto para gerar DXF")
        self._lbl_dxf_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM};")
        r3.addWidget(self._lbl_dxf_status)
        r3.addStretch()

        self._btn_gerar_dxf = QPushButton("Gerar DXF STOG (Obra)")
        self._btn_gerar_dxf.setStyleSheet(
            f"QPushButton {{ background: #1a3a5c; color: {Colors.ACCENT_TEAL}; border: 1px solid {Colors.ACCENT_TEAL}; "
            "border-radius: 4px; font-weight: bold; padding: 4px 10px; } "
            "QPushButton:hover { background: #1e4a7a; } "
            f"QPushButton:disabled {{ color: {Colors.TEXT_MUTED}; border-color: {Colors.TEXT_MUTED}; }}"
        )
        self._btn_gerar_dxf.setToolTip(
            "Gera DXFs STOG de toda a obra (PL+LV+FV+LJ) a partir dos JSONs de Fase-4.\n"
            "Requer que 'Analise Geral' tenha sido executada primeiro."
        )
        self._btn_gerar_dxf.clicked.connect(self._on_gerar_dxf_obra)
        r3.addWidget(self._btn_gerar_dxf)

        # CAD-12: Entregar Obra
        self._btn_entregar = QPushButton("Entregar Obra")
        self._btn_entregar.setStyleSheet(
            f"QPushButton {{ background: #1a4a1a; color: {Colors.ACCENT_SUCCESS}; border: 1px solid {Colors.ACCENT_SUCCESS}; "
            "border-radius: 4px; font-weight: bold; padding: 4px 10px; } "
            "QPushButton:hover { background: #1e6a1e; } "
            f"QPushButton:disabled {{ color: {Colors.TEXT_MUTED}; border-color: {Colors.TEXT_MUTED}; }}"
        )
        self._btn_entregar.setToolTip("CAD-12: Gera DXFs + converte para DWG via ODA (1 clique)")
        self._btn_entregar.clicked.connect(self._on_entregar_obra)
        r3.addWidget(self._btn_entregar)

        # CAD-13: Exportar Dados Treino
        self._btn_ml_export = QPushButton("Exportar Dados Treino")
        self._btn_ml_export.setStyleSheet(
            f"QPushButton {{ background: #3a1a5c; color: {Colors.ACCENT_PURPLE}; border: 1px solid {Colors.ACCENT_PURPLE}; "
            "border-radius: 4px; font-weight: bold; padding: 4px 10px; } "
            "QPushButton:hover { background: #4a1a7a; } "
            f"QPushButton:disabled {{ color: {Colors.TEXT_MUTED}; border-color: {Colors.TEXT_MUTED}; }}"
        )
        self._btn_ml_export.setToolTip("CAD-13: Exporta training_data.json + insights do correction_log")
        self._btn_ml_export.clicked.connect(self._on_ml_export)
        r3.addWidget(self._btn_ml_export)

        # CAD-14: Importar Todos Pavimentos
        self._btn_multi_pav = QPushButton("Importar Pavimentos")
        self._btn_multi_pav.setStyleSheet(
            f"QPushButton {{ background: #3a2a1a; color: {Colors.ACCENT_WARNING_ALT}; border: 1px solid {Colors.ACCENT_WARNING_ALT}; "
            "border-radius: 4px; font-weight: bold; padding: 4px 10px; } "
            "QPushButton:hover { background: #5a3a1a; } "
            f"QPushButton:disabled {{ color: {Colors.TEXT_MUTED}; border-color: {Colors.TEXT_MUTED}; }}"
        )
        self._btn_multi_pav.setToolTip("CAD-14: Importa todos os pavimentos da obra via Fase4Importer")
        self._btn_multi_pav.clicked.connect(self._on_multi_pav_import)
        r3.addWidget(self._btn_multi_pav)

        vlay.addWidget(row3)
        return panel

    def _on_gerar_dxf_obra(self):
        """CAD-11: Abre o dialog de geração DXF para toda a obra."""
        try:
            from src.ui.dialogs.generate_dxf_dialog import GenerateDXFDialog
        except ImportError:
            QMessageBox.critical(self, "Erro", "Modulo GenerateDXFDialog nao disponivel.")
            return

        obra_path, work_name, _, _ = self._get_current_obra_info()
        if not obra_path:
            QMessageBox.warning(
                self, "Obra nao selecionada",
                "Selecione uma obra antes de gerar DXFs."
            )
            return
        self._lbl_dxf_status.setText("Abrindo gerador...")
        GenerateDXFDialog.open_for_obra(obra_path, parent=self)
        self._lbl_dxf_status.setText("Pronto para gerar DXF")

    def _on_entregar_obra(self):
        """CAD-12: Abre o dialog de entrega (DXF + DWG)."""
        try:
            from src.ui.dialogs.delivery_dialog import DeliveryDialog
        except ImportError:
            QMessageBox.critical(self, "Erro", "Modulo DeliveryDialog nao disponivel.")
            return

        obra_path, work_name, _, _ = self._get_current_obra_info()
        if not obra_path:
            QMessageBox.warning(self, "Obra nao selecionada",
                                "Selecione uma obra antes de gerar entrega.")
            return
        self._lbl_dxf_status.setText("Preparando entrega...")
        DeliveryDialog.open_for_obra(obra_path, parent=self)
        self._lbl_dxf_status.setText("Pronto para gerar DXF")

    def _on_ml_export(self):
        """CAD-13: Exporta training_data.json e exibe insights."""
        obra_path, work_name, _, _ = self._get_current_obra_info()
        if not obra_path:
            QMessageBox.warning(self, "Obra nao selecionada",
                                "Selecione uma obra antes de exportar dados de treino.")
            return

        try:
            from src.core.services.ml_feedback_service import MLFeedbackService
        except ImportError as e:
            QMessageBox.critical(self, "Erro", f"MLFeedbackService indisponivel: {e}")
            return

        self._lbl_dxf_status.setText("Exportando dados ML...")
        svc = MLFeedbackService(obra_path)
        result = svc.export_training_data()

        if result['entries'] == 0:
            insights = svc.get_model_insights()
            msg = (
                f"Nenhuma correção registrada em '{work_name}'.\n\n"
                f"Total: {insights['total_corrections']} correção(ões).\n"
                "Faça correções no DetailCard para alimentar o sistema ML."
            )
            QMessageBox.information(self, "Exportar Dados Treino", msg)
        else:
            top = result['top_uncertain_fields'][:5]
            top_txt = "\n".join(
                f"  • {f['field']}: {f['corrections']} correções"
                for f in top
            )
            msg = (
                f"Training data exportado!\n\n"
                f"Entradas: {result['entries']}\n"
                f"Arquivo: {result['export_path']}\n\n"
                f"Top campos incertos:\n{top_txt}"
            )
            QMessageBox.information(self, "Exportar Dados Treino", msg)
        self._lbl_dxf_status.setText("Pronto para gerar DXF")

    def _on_multi_pav_import(self):
        """CAD-14: Importa todos os pavimentos da obra."""
        obra_path, work_name, _, pid = self._get_current_obra_info()
        if not obra_path:
            QMessageBox.warning(self, "Obra nao selecionada",
                                "Selecione uma obra antes de importar pavimentos.")
            return
        if not pid:
            QMessageBox.warning(self, "Projeto nao identificado",
                                "Projeto sem ID — execute Fase-3 primeiro.")
            return

        try:
            from src.core.services.multi_pav_importer import MultiPavImporter
        except ImportError as e:
            QMessageBox.critical(self, "Erro", f"MultiPavImporter indisponivel: {e}")
            return

        self._lbl_dxf_status.setText("Importando pavimentos...")
        imp = MultiPavImporter(self.db)
        pavs = imp.detect_pavimentos(obra_path)
        if not pavs:
            QMessageBox.information(
                self, "Multi-Pavimento",
                f"Nenhum pavimento encontrado em '{work_name}'.\n"
                "Verifique se Fase-4 foi executada (pavimentos_lista.json)."
            )
            self._lbl_dxf_status.setText("Pronto para gerar DXF")
            return

        result = imp.import_all_pavimentos(obra_path, pid)

        msg = (
            f"Importação concluída!\n\n"
            f"Pavimentos: {result['pavimentos_importados']}\n"
            f"Pilares: {result['total_pilares']}\n"
            f"Vigas: {result['total_vigas']}\n"
            f"Lajes: {result['total_lajes']}\n"
            f"Conflitos: {result['total_conflitos']}\n"
            f"Tempo: {result['tempo_ms']}ms"
        )
        if result['erros']:
            msg += f"\n\nErros ({len(result['erros'])}):\n"
            msg += "\n".join(f"  - {e}" for e in result['erros'][:3])

        QMessageBox.information(self, "Importar Pavimentos", msg)
        self._lbl_dxf_status.setText("Pronto para gerar DXF")
        # Notificar Tab 1 para atualizar listagem
        if pid:
            self.fase3_complete.emit(pid)

    # ─────────────────────────────────────────────
    # Fase-3 Execution
    # ─────────────────────────────────────────────

    def _get_current_obra_info(self):
        """Retorna (obra_path, work_name, pavement_name, project_id) da obra ativa."""
        if not self.db:
            return None, None, None, None

        pid = self.coordinator._current_project
        if not pid:
            return None, None, None, None

        try:
            projects = self.db.get_projects()
        except Exception:
            return None, None, None, None

        project = next((p for p in projects if str(p.get('id')) == str(pid)), None)
        if not project:
            return None, None, None, None

        work_name = project.get('work_name', '')
        pav = project.get('pavement_name', '') or '1PV'
        obra_path = DADOS_OBRAS_ROOT / work_name
        return str(obra_path), work_name, pav, pid

    def _refresh_fase3_status(self, pid=None, pname=None):
        """Atualiza label de obra/pav no painel Fase-3 (painel removido — no-op)."""
        pass

    def _run_fase3(self):
        """Executa engenharia_reversa_dxf.py como subprocess assíncrono."""
        obra_path, work_name, pav, pid = self._get_current_obra_info()

        if not obra_path:
            QMessageBox.warning(self, "Fase-3", "Selecione um pavimento no painel lateral primeiro.")
            return

        if not Path(obra_path).exists():
            QMessageBox.warning(self, "Fase-3",
                                f"Diretório da obra não encontrado:\n{obra_path}")
            return

        script = SCRIPTS_DIR / "engenharia_reversa_dxf.py"
        if not script.exists():
            QMessageBox.critical(self, "Fase-3",
                                 f"Script não encontrado:\n{script}")
            return

        # Verificar se já existe e force não está marcado
        fase3_dir = Path(obra_path) / "Fase-3_Interpretacao_Extracao"
        if fase3_dir.exists() and not self._chk_fase3_force.isChecked():
            reply = QMessageBox.question(
                self, "Fase-3 já extraída",
                f"Fase-3 já existe para {work_name} / {pav}.\n\nDeseja apenas importar para o banco?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self._import_fase3_to_db(obra_path, work_name, pid)
                self._import_fase4_to_db(obra_path, work_name, pid)
                return

        # Preparar QProcess
        self._btn_fase3_run.setEnabled(False)
        self._fase3_progress.setValue(5)
        self._fase3_progress.setVisible(True)
        self._lbl_fase3_status.setText("Executando script...")

        self._fase3_process = QProcess(self)
        self._fase3_process.setProcessChannelMode(QProcess.MergedChannels)
        self._fase3_process.readyReadStandardOutput.connect(self._on_fase3_output)
        self._fase3_process.finished.connect(
            lambda code, _status: self._on_fase3_finished(code, obra_path, work_name, pid)
        )

        args = [str(script), "--obra", obra_path, "--pavimento", pav]
        self._fase3_process.start(sys.executable, args)

        print(f"[Fase-3] Iniciando: {work_name} / {pav}")

    # Marcadores de progresso da engenharia_reversa_dxf.py → %
    _FASE3_PHASE_PCT = {
        'PILARES':   15,
        'VIGAS':     35,
        'LAJES':     55,
        'POLÍGONO':  65,
        'POLYGON':   65,
        'POLIGONO':  65,
        'ANCORAS':   75,
        'ANCORA':    75,
        'ANCHOR':    75,
        'ASSEMBLY':  82,
        'INTEGRANDO': 88,
        'INTEGR':    88,
        'SALV':      92,
    }

    def _on_fase3_output(self):
        """Lê stdout do processo e atualiza status com % de progresso."""
        if not self._fase3_process:
            return
        raw = bytes(self._fase3_process.readAllStandardOutput())
        try:
            text = raw.decode('utf-8', errors='replace').strip()
        except Exception:
            text = ""
        if not text:
            return
        upper = text.upper()
        for marker, pct in self._FASE3_PHASE_PCT.items():
            if marker in upper:
                # Avança para o % da fase detectada (nunca retrocede)
                if pct > self._fase3_progress.value():
                    self._fase3_progress.setValue(pct)
                break
        else:
            # Incremento visual para linhas sem marcador de fase
            cur = self._fase3_progress.value()
            self._fase3_progress.setValue(min(cur + 1, 91))
        last = [l for l in text.splitlines() if l.strip()]
        if last:
            self._lbl_fase3_status.setText(last[-1][:42])
        print(f"[Fase-3] {text}")

    def _on_fase3_finished(self, returncode: int, obra_path: str, work_name: str, pid: str):
        """Callback: engenharia_reversa_dxf concluído → encadeia extrair_bh_pilares."""
        if returncode != 0:
            self._fase3_progress.setVisible(False)
            self._btn_fase3_run.setEnabled(True)
            self._lbl_fase3_status.setText("❌ Erro na extração")
            QMessageBox.critical(self, "Fase-3",
                                 f"Processo terminou com código {returncode}.\n"
                                 "Verifique o terminal para detalhes.")
            return

        self._fase3_progress.setValue(95)
        self._lbl_fase3_status.setText("Extraindo B/H...")
        print(f"[Fase-3] Engenharia reversa concluída — rodando extrai_bh_pilares...")

        # Encadear extrai_bh_pilares.py (CAD-UI-3.1)
        bh_script = SCRIPTS_DIR / "extrair_bh_pilares.py"
        if bh_script.exists():
            pav = self._get_current_obra_info()[2] or "1PV"
            proc = QProcess(self)
            proc.setProcessChannelMode(QProcess.MergedChannels)
            proc.readyReadStandardOutput.connect(
                lambda: self._lbl_fase3_status.setText(
                    bytes(proc.readAllStandardOutput()).decode('utf-8', 'replace').strip()[-40:]
                )
            )
            proc.finished.connect(
                lambda code, _: self._on_bh_finished(code, obra_path, work_name, pid)
            )
            proc.start(sys.executable, [str(bh_script), "--obra", obra_path, "--pavimento", pav])
        else:
            # Sem script BH — importar direto
            self._finalize_fase3_import(obra_path, work_name, pid)

    def _on_bh_finished(self, returncode: int, obra_path: str, work_name: str, pid: str):
        """Callback: extrair_bh concluído → importar para DB."""
        if returncode != 0:
            print(f"[Fase-3] Aviso: extrair_bh_pilares saiu com código {returncode} — continuando sem B/H preciso")
        self._finalize_fase3_import(obra_path, work_name, pid)

    def _finalize_fase3_import(self, obra_path: str, work_name: str, pid: str):
        """Passo final: importar Ground Truth + Fase-4 para DB e notificar Tab 1."""
        # ── 1. Ground Truth (Fase-3) ──────────────────────────────────────────
        self._fase3_progress.setValue(85)
        self._lbl_fase3_status.setText("Importando Ground Truth...")
        print(f"[Fase-3] Concluído para {work_name}")
        self._import_fase3_to_db(obra_path, work_name, pid)
        print(f"[FASE3] import GT concluído para {work_name}/{pid}", flush=True)

        # ── 2. Fase-4 (JSONs ricos) ───────────────────────────────────────────
        self._import_fase4_to_db(obra_path, work_name, pid)

        # ── 3. Finalizar UI ───────────────────────────────────────────────────
        self._fase3_progress.setValue(100)
        self._fase3_progress.setVisible(False)
        self._btn_fase3_run.setEnabled(True)

    # ─────────────────────────────────────────────
    # Pipeline Completo (CAD-UI-4.2)
    # ─────────────────────────────────────────────

    def _run_pipeline_completo(self):
        """Executa pipeline_e2e.py — todas as fases F1→F8."""
        obra_path, work_name, pav, pid = self._get_current_obra_info()
        if not obra_path:
            QMessageBox.warning(self, "Pipeline", "Selecione um pavimento primeiro.")
            return

        script = SCRIPTS_DIR / "pipeline_e2e.py"
        if not script.exists():
            QMessageBox.critical(self, "Pipeline", f"Script não encontrado:\n{script}")
            return

        self._btn_pipeline.setEnabled(False)
        self._btn_fase3_run.setEnabled(False)
        self._pipeline_progress.setValue(2)
        self._pipeline_progress.setVisible(True)
        self._lbl_pipeline_status.setText("Iniciando pipeline...")

        args = [str(script), "--obra", obra_path, "--pavimento", pav]
        if self._chk_pipeline_force.isChecked():
            args.append("--force")

        self._pipeline_process = QProcess(self)
        self._pipeline_process.setProcessChannelMode(QProcess.MergedChannels)
        self._pipeline_process.readyReadStandardOutput.connect(self._on_pipeline_output)
        self._pipeline_process.finished.connect(
            lambda code, _: self._on_pipeline_finished(code, obra_path, work_name, pid)
        )
        self._pipeline_process.start(sys.executable, args)
        print(f"[Pipeline E2E] Iniciando: {work_name} / {pav}")

    # Mapeamento de marcadores de fase → % de progresso
    _PIPELINE_PHASE_PCT = {
        '[FASE 1]': 8,
        '[FASE 2]': 20,
        '[FASE 3]': 35,
        '[FASE 4]': 50,
        '[FASE 5]': 65,
        '[FASE 5B]': 70,
        '[FASE 6]': 78,
        '[FASE 7]': 88,
        '[FASE 8]': 94,
        '  [RUN]': None,    # usa progresso atual + 1 para mostrar atividade
        '  -> OK': None,
    }

    def _on_pipeline_output(self):
        if not self._pipeline_process:
            return
        raw = bytes(self._pipeline_process.readAllStandardOutput())
        text = raw.decode('utf-8', errors='replace')
        for line in text.splitlines():
            if not line.strip():
                continue
            upper = line.upper()
            # S6 — emite apenas marcadores de fase (evita spam de sub-passos)
            _is_phase = any(marker.upper() in upper for marker in self._PIPELINE_PHASE_PCT)
            if _is_phase:
                print(f"[PIPELINE] {line.strip()}", flush=True)
            elif os.environ.get('CAD_DEBUG_LOAD'):
                print(f"[Pipeline] {line}")
            # Atualizar progresso baseado na fase detectada
            pct = None
            for marker, val in self._PIPELINE_PHASE_PCT.items():
                if marker in upper:
                    pct = val
                    break
            if pct is not None:
                self._pipeline_progress.setValue(pct)
            elif upper.strip().startswith('[RUN]') or '-> OK' in upper:
                # Pequeno incremento visual durante sub-passos
                cur = self._pipeline_progress.value()
                self._pipeline_progress.setValue(min(cur + 1, 97))
            self._lbl_pipeline_status.setText(line.strip()[:55])

    def _on_pipeline_finished(self, returncode: int, obra_path: str, work_name: str, pid: str):
        self._pipeline_progress.setVisible(False)
        self._btn_pipeline.setEnabled(True)
        self._btn_fase3_run.setEnabled(True)

        if returncode != 0:
            self._lbl_pipeline_status.setText(f"❌ Erro (código {returncode})")
            QMessageBox.critical(self, "Pipeline", f"Pipeline terminou com código {returncode}.")
            return

        self._pipeline_progress.setValue(100)
        self._lbl_pipeline_status.setText("✓ Pipeline completo!")
        print(f"[Pipeline E2E] Concluído para {work_name}")

        # Importar Fase-3 (GT) + Fase-4 (fichas ricas) se disponíveis
        fase3_done = (Path(obra_path) / "Fase-3_Interpretacao_Extracao").exists()
        if fase3_done and pid:
            self._import_fase3_to_db(obra_path, work_name, pid)
            self._import_fase4_to_db(obra_path, work_name, pid)
        else:
            self._refresh_fase3_status()
            self.fase3_complete.emit(pid or "")

    # ─────────────────────────────────────────────
    # Fase-3 → DB Import (CAD-UI-1.2)
    # ─────────────────────────────────────────────

    def _import_fase3_to_db(self, obra_path: str, work_name: str, project_id: str):
        """Importa os JSONs da Fase-3 para as tabelas pillars/beams/slabs do DB."""
        if not self.db or not project_id:
            print("[Fase-3] Sem DB ou project_id — importação cancelada.")
            return

        base = Path(obra_path) / "Fase-3_Interpretacao_Extracao"
        if not base.exists():
            print(f"[Fase-3] Diretório Fase-3 não encontrado: {base}")
            return

        n_pil = n_vig = n_laj = 0

        # ── Pilares ──────────────────────────────
        pil_gt  = base / "Pilares" / "pilares_ground_truth.json"
        pil_bh  = base / "Pilares" / "pilares_bh.json"       # saída de extrair_bh_pilares.py
        pil_anc = base / "ancoras_pilares.json"

        if pil_gt.exists():
            gt = json.loads(pil_gt.read_text(encoding='utf-8', errors='replace'))
            anc = {}
            if pil_anc.exists():
                anc = json.loads(pil_anc.read_text(encoding='utf-8', errors='replace'))
            bh_data = {}
            if pil_bh.exists():
                bh_data = json.loads(pil_bh.read_text(encoding='utf-8', errors='replace'))

            for id_item, data in gt.items():
                # Merge B/H de extrair_bh_pilares se disponível (maior confiança)
                if id_item in bh_data:
                    bh = bh_data[id_item]
                    b    = bh.get('b') or data.get('b')
                    h    = bh.get('h') or data.get('h')
                    conf = bh.get('confidence', data.get('confidence', 0.3))
                else:
                    b    = data.get('b')
                    h    = data.get('h')
                    conf = data.get('confidence', 0.3)

                anchor = anc.get(id_item, [0.0, 0.0])
                area   = (float(b) * float(h)) if (b and h) else 0.0

                pillar = {
                    'id': f"{project_id}_pil_{id_item}",
                    'id_item': id_item,
                    'name': id_item,
                    'type': 'Pilar',
                    'area_val': area,
                    'points': [anchor],
                    'sides_data': {
                        'b': b, 'h': h,
                        'altura': data.get('altura'),
                        'bh_confidence': conf,
                        'faces_encontradas': data.get('faces_encontradas', []),
                    },
                    'confidence_map': {'bh': conf},
                    'links': {},
                    'validated_fields': [],
                    'validated_link_classes': {},
                    'na_fields': [],
                    'na_link_classes': {},
                    'na_reasons': {},
                    'issues': [] if conf >= 0.4 else [
                        {'type': 'low_confidence',
                         'msg': f'B/H incerto (conf={conf:.1f}) — verificação manual necessária'}
                    ],
                    'is_validated': False,
                    'pkl_path': None,
                }
                self.db.save_pillar(pillar, project_id)
                n_pil += 1

        # ── Vigas ─────────────────────────────────
        vig_gt  = base / "Vigas" / "vigas_ground_truth.json"
        vig_anc = base / "ancoras_vigas.json"

        # CAD-UI-3.2: carregar catalog LV para merge de seção/dims
        catalog_path = Path("D:/Agente-cad-PYSIDE/ANALISE_LV/catalog_rendered.json")
        lv_catalog = {}  # {viga_name: {secao, b, h, confidence}}
        if catalog_path.exists():
            try:
                catalog_list = json.loads(catalog_path.read_text(encoding='utf-8', errors='replace'))
                for entry in catalog_list:
                    if entry.get('obra') == work_name:
                        viga_key = str(entry.get('viga', '')).upper()
                        secao = str(entry.get('secao', ''))
                        # Extrair B×H da seção (ex: "14x50" → b=14, h=50)
                        b_cat = h_cat = None
                        import re as _re
                        m = _re.match(r'(\d+)[xX×](\d+)', secao)
                        if m:
                            b_cat = float(m.group(1))
                            h_cat = float(m.group(2))
                        lv_catalog[viga_key] = {
                            'secao': secao, 'b': b_cat, 'h': h_cat,
                            'confidence': 0.85 if (b_cat and h_cat) else 0.5,
                        }
                if lv_catalog:
                    print(f"[Fase-3] Catalog LV: {len(lv_catalog)} vigas para {work_name}")
            except Exception as e:
                print(f"[Fase-3] Aviso: não foi possível carregar catalog LV: {e}")

        if vig_gt.exists():
            gt = json.loads(vig_gt.read_text(encoding='utf-8', errors='replace'))
            anc = {}
            if vig_anc.exists():
                anc = json.loads(vig_anc.read_text(encoding='utf-8', errors='replace'))

            for id_item, data in gt.items():
                conf   = data.get('confidence', 0.25)
                b_val  = data.get('b')
                h_val  = data.get('h')
                secao  = ''
                source = data.get('source', 'fase-3')

                # Merge com catalog LV se disponível
                cat = lv_catalog.get(id_item.upper())
                if cat:
                    if cat.get('b') and not b_val:
                        b_val  = cat['b']
                        h_val  = cat['h']
                        conf   = cat['confidence']
                        source = 'catalog-lv'
                    secao = cat.get('secao', '')

                anchor = anc.get(id_item, [0.0, 0.0])
                beam = {
                    'id': f"{project_id}_vig_{id_item}",
                    'id_item': id_item,
                    'name': id_item,
                    'type': 'Viga',
                    'b': b_val,
                    'h': h_val,
                    'secao': secao,
                    'comprimento': data.get('comprimento'),
                    'confidence': conf,
                    'sides_encontrados': data.get('sides_encontrados', []),
                    'source': source,
                    'points': [anchor],
                    'validated_fields': [],
                    'validated_link_classes': {},
                    'na_fields': [],
                    'na_link_classes': {},
                    'na_reasons': {},
                    'issues': [] if conf >= 0.4 else [
                        {'type': 'low_confidence',
                         'msg': f'Dims incertas (conf={conf:.1f})'}
                    ],
                    'is_validated': False,
                    'pkl_path': None,
                }
                self.db.save_beam(beam, project_id)
                n_vig += 1

        # ── Lajes ─────────────────────────────────
        laj_gt  = base / "Lajes" / "lajes_ground_truth.json"
        laj_anc = base / "ancoras_lajes.json"

        if laj_gt.exists():
            gt = json.loads(laj_gt.read_text(encoding='utf-8', errors='replace'))
            anc = {}
            if laj_anc.exists():
                anc = json.loads(laj_anc.read_text(encoding='utf-8', errors='replace'))

            for id_item, data in gt.items():
                conf = data.get('confidence', 0.25)
                coords = data.get('coordenadas', [])
                anchor = anc.get(id_item, [0.0, 0.0])
                points = coords if coords else ([anchor] if anchor != [0.0, 0.0] else [])
                area_cm2 = data.get('area_cm2') or 0.0

                slab = {
                    'id': f"{project_id}_laj_{id_item}",
                    'id_item': id_item,
                    'name': id_item,
                    'type': 'Laje',
                    'area': float(area_cm2),
                    'points': points,
                    'links': {},
                    'validated_fields': [],
                    'validated_link_classes': {},
                    'na_fields': [],
                    'na_link_classes': {},
                    'na_reasons': {},
                    'issues': [] if conf >= 0.4 else [
                        {'type': 'low_confidence', 'msg': f'Dims incertas (conf={conf:.1f})'}
                    ],
                    'is_validated': False,
                    'pkl_path': None,
                }
                self.db.save_slab(slab, project_id)
                n_laj += 1

        msg = f"✓ GT importado: {n_pil} pilares, {n_vig} vigas, {n_laj} lajes"
        print(f"[Fase-3] {msg}")

        # Atualizar label de status
        self._refresh_fase3_status()

        # Notificar Tab 1
        self.fase3_complete.emit(project_id)

    # ─────────────────────────────────────────────
    # Fase-4 → DB Import (CAD-10.3)
    # ─────────────────────────────────────────────

    def _import_fase4_to_db(self, obra_path: str, work_name: str, project_id: str):
        """Importa JSONs ricos da Fase-4 para DB, complementando o Ground Truth.

        Respeita `validated_fields` — campos aprovados pelo usuário nunca são sobrescritos.
        Chamado automaticamente após `_import_fase3_to_db()`.
        """
        if not self.db or not project_id:
            print("[Fase-4] Sem DB ou project_id — importação Fase-4 cancelada.")
            return

        fase4_dir = Path(obra_path) / "Fase-4_Sincronizacao"
        if not fase4_dir.exists():
            print(f"[Fase-4] Diretório não encontrado: {fase4_dir} — pulando enriquecimento.")
            self._lbl_fase3_status.setText("✓ GT importado (sem Fase-4)")
            return

        self._fase3_progress.setValue(93)
        self._lbl_fase3_status.setText("Importando Fase-4 (fichas)...")

        try:
            importer = Fase4Importer(self.db)
            pav = self._get_current_obra_info()[2] or "TÉRREO"
            result = importer.import_obra(obra_path, pav, project_id)

            n_pil  = result.get('pilares', 0)
            n_vig  = result.get('vigas', 0)
            n_laj  = result.get('lajes', 0)
            n_conf = result.get('conflitos', 0)
            erros  = result.get('erros', [])
            ms     = result.get('tempo_ms', 0)

            msg = (
                f"✓ Fase-4: {n_pil}PL {n_vig}VG {n_laj}LJ"
                + (f" ⚠{n_conf}conf" if n_conf else "")
            )
            self._lbl_fase3_status.setText(msg[:50])
            print(f"[Fase-4] {msg} ({ms}ms)")

            if erros:
                print(f"[Fase-4] Erros ({len(erros)}):")
                for e in erros[:5]:
                    print(f"  - {e}")

            # Renotificar Tab 1 para que DetailCards sejam atualizados
            self.fase3_complete.emit(project_id)

        except Exception as exc:
            print(f"[Fase-4] Erro inesperado: {exc}")
            self._lbl_fase3_status.setText("⚠ Fase-4 falhou — GT mantido")

    # ─────────────────────────────────────────────
    # Existing methods (unchanged)
    # ─────────────────────────────────────────────

    def set_database(self, db):
        self.db = db
        self.sidebar.set_database(db)

    def _on_document_selected(self, doc_data):
        """Carrega o documento selecionado no Canvas."""
        print(f"[DOC_SEL] doc={doc_data.get('name','?')} path={doc_data.get('file_path','?')}", flush=True)
        file_path = doc_data.get('file_path')
        if not file_path or not os.path.exists(file_path):
            print(f"[DiagnosticHub] Arquivo não encontrado: {file_path}")
            return

        print(f"[DiagnosticHub] Carregando Documento: {doc_data.get('name')}")

        try:
            if self._load_thread and self._load_thread.isRunning():
                print("[DiagnosticHub] Thread already running, ignoring request.")
                return
        except (RuntimeError, AttributeError):
            self._cleanup_thread()

        ext = file_path.lower()

        if ext.endswith('.dxf'):
            dialog = RenderModeDialog(self)
            if dialog.exec() != QDialog.Accepted:
                return

            render_mode = dialog.get_selected_mode()
            doc_data['render_mode'] = render_mode
            print(f"[DiagnosticHub] Modo selecionado: {render_mode.name}")

            self.canvas.set_loading(True)
            from src.ui.workers import DXFLoadWorker

            self._load_thread = QThread()
            self._load_worker = DXFLoadWorker(file_path, doc_data=doc_data, use_cache=True)
            self._load_worker.moveToThread(self._load_thread)

            self._load_thread.started.connect(self._load_worker.run)
            self._load_worker.finished.connect(self._on_dxf_loaded)
            self._load_worker.error.connect(self._on_dxf_error)

            self._load_worker.finished.connect(self._load_thread.quit)
            self._load_worker.finished.connect(self._load_worker.deleteLater)
            self._load_worker.error.connect(self._load_thread.quit)
            self._load_worker.error.connect(self._load_worker.deleteLater)

            self._load_thread.finished.connect(self._cleanup_thread)
            self._load_thread.finished.connect(self._load_thread.deleteLater)

            self._load_thread.start()

        elif ext.endswith('.pdf'):
            self.canvas.set_loading(True)
            from src.ui.workers import PDFLoadWorker

            self._load_thread = QThread()
            self._load_worker = PDFLoadWorker(file_path, doc_data=doc_data)
            self._load_worker.moveToThread(self._load_thread)

            self._load_thread.started.connect(self._load_worker.run)
            self._load_worker.finished.connect(self._on_pdf_loaded)
            self._load_worker.error.connect(self._on_dxf_error)

            self._load_worker.finished.connect(self._load_thread.quit)
            self._load_worker.finished.connect(self._load_worker.deleteLater)
            self._load_worker.error.connect(self._load_thread.quit)
            self._load_worker.error.connect(self._load_worker.deleteLater)

            self._load_thread.finished.connect(self._cleanup_thread)
            self._load_thread.finished.connect(self._load_thread.deleteLater)

            self._load_thread.start()

    def _cleanup_thread(self):
        self._load_thread = None
        self._load_worker = None

    def _on_pdf_loaded(self, images, duration, doc_data):
        print(f"[DiagnosticHub] PDF carregado ({len(images)} páginas) em {duration:.2f}s")
        self._current_doc_data = doc_data
        if images:
            self.canvas.add_pdf_pages(images)
        self.canvas.set_loading(False)

    def _on_dxf_loaded(self, dxf_data, duration, doc_data):
        import time as _time
        render_mode = doc_data.get('render_mode', RenderMode.TRUE_GEOMETRY)
        if dxf_data:
            n_lines = len(dxf_data.get('lines', []))
            n_polys = len(dxf_data.get('polylines', []))
            n_texts = len(dxf_data.get('texts', []))
            n_blocks = len(dxf_data.get('blocks', []))
            n_total  = n_lines + n_polys + n_texts + n_blocks
            # S1 — entidades carregadas
            print(f"[CANVAS] loaded {n_total} entities from {os.path.basename(doc_data.get('file_path','?'))} "
                  f"(lines={n_lines} polys={n_polys} texts={n_texts} blocks={n_blocks})", flush=True)
        self._current_doc_data = doc_data

        if dxf_data:
            n_total = (len(dxf_data.get('lines', [])) + len(dxf_data.get('polylines', [])) +
                       len(dxf_data.get('texts', [])) + len(dxf_data.get('circles', [])) +
                       len(dxf_data.get('hatches', [])))
            self.canvas.set_loading(True, f"⌛ Renderizando {n_total:,} entidades...")
            _t_render = _time.monotonic()
            self.canvas.add_dxf_entities(
                dxf_data, render_mode=render_mode, compute_snaps=False, source_dxf_path=doc_data.get('source_path'),
                progress_callback=lambda pct: self.canvas.update_loading_progress(pct, "Renderizando"),
            )
            _render_ms = int((_time.monotonic() - _t_render) * 1000)
            print(f"[PERF] DXF load: {int(duration*1000)}ms | Render: {_render_ms}ms | "
                  f"mode: {render_mode.name}", flush=True)

        if hasattr(self.canvas, 'dxf_metadata'):
            self.tech_panel.update_dynamic_filters(self.canvas.dxf_metadata)

        if doc_data.get('project_id'):
            self.coordinator.set_project(doc_data['project_id'], doc_data.get('name'))

        self.canvas.set_loading(False)

    def _on_apply_fix(self):
        """APPLY FIX — re-renderiza o DXF atual com estratégia de limpeza selecionada
        e salva o resultado filtrado em Fase-2_Triagem/ da obra ativa."""
        if not hasattr(self, '_current_doc_data') or not self._current_doc_data:
            QMessageBox.information(
                self, "APPLY FIX",
                "Nenhum DXF carregado.\n\n"
                "Selecione um arquivo DXF na sidebar esquerda primeiro."
            )
            return

        file_path = self._current_doc_data.get('file_path', '')
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "APPLY FIX", f"Arquivo não encontrado:\n{file_path}")
            return

        # Selecionar estratégia de limpeza
        dialog = RenderModeDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        render_mode = dialog.get_selected_mode()

        # Re-renderizar no canvas com o novo modo
        doc_data = dict(self._current_doc_data)
        doc_data['render_mode'] = render_mode
        print(f"[APPLY FIX] Re-renderizando {os.path.basename(file_path)} modo={render_mode.name}")

        self.canvas.set_loading(True)
        from src.ui.workers import DXFLoadWorker

        if self._load_thread and self._load_thread.isRunning():
            return

        self._load_thread = QThread()
        self._load_worker = DXFLoadWorker(file_path, doc_data=doc_data, use_cache=False)
        self._load_worker.moveToThread(self._load_thread)
        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.finished.connect(self._on_apply_fix_loaded)
        self._load_worker.error.connect(self._on_dxf_error)
        self._load_worker.finished.connect(self._load_thread.quit)
        self._load_worker.finished.connect(self._load_worker.deleteLater)
        self._load_worker.error.connect(self._load_thread.quit)
        self._load_worker.error.connect(self._load_worker.deleteLater)
        self._load_thread.finished.connect(self._cleanup_thread)
        self._load_thread.finished.connect(self._load_thread.deleteLater)
        self._load_thread.start()

        self._pending_apply_fix = (file_path, render_mode)

    def _on_apply_fix_loaded(self, dxf_data, duration, doc_data):
        """Callback após re-renderização com novo modo. Salva DXF filtrado em Fase-2_Triagem."""
        render_mode = doc_data.get('render_mode', RenderMode.TRUE_GEOMETRY)
        print(f"[APPLY FIX] Carregado em {duration:.2f}s modo={render_mode.name}")
        self._current_doc_data = doc_data

        if dxf_data:
            self.canvas.add_dxf_entities(dxf_data, render_mode=render_mode, compute_snaps=False, source_dxf_path=doc_data.get('source_path'))

        self.canvas.set_loading(False)

        # Salvar DXF filtrado em Fase-2_Triagem/ da obra ativa
        self._save_fase2_triagem(render_mode)

    def _save_fase2_triagem(self, render_mode):
        """Salva cópia filtrada do DXF bruto em Fase-2_Triagem/ usando ezdxf."""
        file_path = self._current_doc_data.get('file_path', '')
        obra_path, work_name, _, _ = self._get_current_obra_info()
        if not obra_path or not work_name:
            print("[APPLY FIX] Obra não identificada — save Fase-2 ignorado.")
            return

        triagem_dir = Path(obra_path) / "Fase-2_Triagem"
        triagem_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(file_path).stem
        out_path = triagem_dir / f"{stem}_modo{render_mode.value}.dxf"

        try:
            import ezdxf
            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()

            # Filtros básicos por modo (espelha dxf_loader.py logic)
            _COLOR_STRUCTURAL = {1, 2, 3, 4}   # vermelho, amarelo, verde, ciano
            _COLOR_EXTENDED   = {1, 2, 3, 4, 5, 6, 7}

            if render_mode.value >= 3:  # COLOR_BASIC ou superior — filtrar por cor
                allowed = _COLOR_EXTENDED if render_mode.value == 4 else _COLOR_STRUCTURAL
                to_delete = [e for e in msp if e.dxf.hasattr('color') and e.dxf.color not in allowed]
                for e in to_delete:
                    msp.delete_entity(e)

            doc.saveas(str(out_path))
            print(f"[APPLY FIX] Fase-2 salvo: {out_path}")
            from PySide6.QtWidgets import QMessageBox as _MB
            _MB.information(
                self, "APPLY FIX — Concluído",
                f"DXF filtrado salvo em:\n{out_path}\n\n"
                f"Modo: {render_mode.name}\n"
                f"Obra: {work_name}"
            )
        except Exception as e:
            print(f"[APPLY FIX] Erro ao salvar Fase-2: {e}")

    def _on_dxf_error(self, err_msg):
        print(f"[DiagnosticHub] Erro no carregamento: {err_msg}")
        self.canvas.set_loading(False)
        QMessageBox.critical(
            self,
            "Erro de Carregamento",
            f"Não foi possível carregar o arquivo DXF.\n\nDetalhes: {err_msg}\n\n"
            "O arquivo pode estar corrompido ou em um formato incompatível."
        )

    def _on_style_changed(self, style_id):
        self.canvas.switch_text_style(style_id)

    def _on_filter_requested(self, f_type, f_value):
        self.canvas.apply_filter(f_type, f_value)

    def _on_extract_requested(self, mode):
        entities = self.canvas.get_selected_entities()
        if not entities:
            print("[DiagnosticHub] Nenhuma entidade selecionada para extração.")
            return

        print(f"[DiagnosticHub] Extraindo {len(entities)} entidades. Modo: {mode}")

        if mode == 'clean':
            category = "Estruturais Pavimentos Limpos"
            suffix = "_clean"
            phase = 2
        elif mode == 'detail':
            category = "Detalhamentos Específicos"
            suffix = "_detail"
            phase = 2
        elif mode == 'finalized':
            category = "Recortes de Itens Finalizados"
            suffix = "_finalized"
            phase = 3
        else:
            print(f"[DiagnosticHub] Modo desconhecido: {mode}")
            return

        if mode == 'finalized' and hasattr(self, '_current_doc_data') and self._current_doc_data:
            doc_data = self._current_doc_data
            work_name = doc_data.get('work_name')
            pid = doc_data.get('project_id')

            if not pid and work_name:
                projects = self.db.get_projects()
                for p in projects:
                    if p.get('work_name') == work_name:
                        pid = p['id']
                        break

            save_dir = os.path.join(os.getcwd(), "storage", "clips", work_name or "temp")
        else:
            pid = self.coordinator._current_project
            save_dir = os.path.join(os.getcwd(), "storage", "documents", pid or "temp")

        if not pid:
            print("[DiagnosticHub] ERRO: Nenhum projeto ativo para salvar extração.")
            return

        import ezdxf

        try:
            new_doc = ezdxf.new()
            msp = new_doc.modelspace()

            for ent in entities:
                etype = ent.get('type')
                if etype == 'line':
                    p1, p2 = ent['points']
                    msp.add_line(p1, p2)
                elif etype == 'circle':
                    msp.add_circle(ent['center'], ent['radius'])

            filename = f"extract_{uuid.uuid4().hex[:6]}{suffix}.dxf"
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, filename)

            new_doc.saveas(save_path)

            self.db.save_document(
                project_id=pid,
                name=f"Extração {mode.capitalize()} ({len(entities)} ents)",
                file_path=save_path,
                extension=".dxf",
                phase=phase,
                category=category
            )

            print(f"[DiagnosticHub] Extração salva em: {save_path}")

            if mode == 'clean':
                self.tech_panel.list_clean_struct.addItem(filename)
            elif mode == 'detail':
                self.tech_panel.list_details.addItem(filename)
            elif mode == 'finalized':
                self.tech_panel.list_finalized.addItem(filename)

        except Exception as e:
            print(f"[DiagnosticHub] Erro na extração: {e}")
            import traceback
            traceback.print_exc()

    def _on_project_changed(self, pid, pname):
        print(f"[DiagnosticHub] Project Switched: {pname}")
        self.sidebar.refresh()
