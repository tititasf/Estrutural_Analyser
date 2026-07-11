"""Patch one-shot: CE PIL N3 load + restore_single_view + logging + n3_ok variants."""
from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "ui" / "modules" / "comparison_engine.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"BLOCK NOT FOUND: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"BLOCK NOT UNIQUE ({text.count(old)}): {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    original = text

    text = replace_once(
        text,
        """    def restore_single_view(self):
        \"\"\"Restore N4 column to single-viewer layout (called on item/classe change).\"\"\"
        if not getattr(self, '_pil_mode', False):
            return
        self._pil_splitter.setVisible(False)
        self._splitter_vf.setVisible(True)
        self._pil_mode = False
""",
        """    def restore_single_view(self):
        \"\"\"Restore column to single-viewer layout (called on item/classe change).

        Remove o splitter multi-zona do layout em vez de só ocultá-lo — senão
        cada seleção PL acumula splitters e o painel N3 fica em branco.
        \"\"\"
        if not getattr(self, '_pil_mode', False):
            return
        pil_sp = getattr(self, '_pil_splitter', None)
        if pil_sp is not None:
            try:
                self.layout().removeWidget(pil_sp)
            except Exception:
                pass
            pil_sp.setParent(None)
            pil_sp.deleteLater()
            self._pil_splitter = None
        self._zone_views = {}
        self._zone_tables = {}
        self._splitter_vf.setVisible(True)
        self._pil_mode = False
""",
        "restore_single_view",
    )

    text = replace_once(
        text,
        """        if not getattr(self, '_pil_mode', False):
            self._splitter_vf.setVisible(False)

            splitter = QSplitter(Qt.Horizontal)
            self._zone_views: dict = {}
            self._zone_tables: dict = {}

            for zone in active_zones:
                panel = QWidget()
                pv = QVBoxLayout(panel)
                pv.setContentsMargins(2, 2, 2, 2)
                pv.setSpacing(2)

                zone_hdr = QLabel(zone)
                zone_hdr.setAlignment(Qt.AlignCenter)
                zone_hdr.setFixedHeight(20)
                zone_hdr.setStyleSheet(
                    f"color: {accent}; font-weight: bold; font-size: 11px; "
                    f"background: {Colors.BG_DEEP}; border-radius: 3px;"
                )
                pv.addWidget(zone_hdr)

                view = DXFVectorView(bg=Colors.BG_DEEP)
                view.setMinimumHeight(135)  # 180px * 0.75
                pv.addWidget(view, self.SINGLE_VIEWER_STRETCH[0])

                tbl = QTableWidget(0, 2)
                tbl.setHorizontalHeaderLabels(["Campo", "Valor"])
                tbl.horizontalHeader().setSectionResizeMode(
                    0, QHeaderView.ResizeToContents)
                tbl.horizontalHeader().setSectionResizeMode(
                    1, QHeaderView.Stretch)
                tbl.verticalHeader().setVisible(False)
                tbl.setEditTriggers(QTableWidget.NoEditTriggers)
                tbl.setMinimumHeight(90)
                tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                tbl.setStyleSheet(self.ficha_table.styleSheet())
                pv.addWidget(tbl, self.SINGLE_VIEWER_STRETCH[1])

                self._zone_views[zone] = view
                self._zone_tables[zone] = tbl
                splitter.addWidget(panel)

            # Inserir splitter PIL após o header (index 1)
            lay.insertWidget(1, splitter)
            self._pil_splitter = splitter
            self._pil_mode = True

        # Load DXFs into viewers
        from pathlib import Path as _Path
        for zone, view in self._zone_views.items():
            p = zone_paths.get(zone)
            if p and _Path(p).exists():
                view.load_dxf(str(p), None)
            else:
                view.clear_image(f"Sem ficha {zone}")

        self._update_pil_zone_fichas(er_ficha, zone_fichas)
""",
        """        if getattr(self, '_pil_mode', False) and getattr(self, '_pil_splitter', None) is not None:
            # Já em multi-zona: reutiliza viewers (evita acumular splitters).
            self._splitter_vf.setVisible(False)
            self._pil_splitter.setVisible(True)
        else:
            # Garante limpeza se um splitter residual ficou órfão.
            if getattr(self, '_pil_splitter', None) is not None:
                try:
                    lay.removeWidget(self._pil_splitter)
                except Exception:
                    pass
                try:
                    self._pil_splitter.setParent(None)
                    self._pil_splitter.deleteLater()
                except Exception:
                    pass
                self._pil_splitter = None

            self._splitter_vf.setVisible(False)

            splitter = QSplitter(Qt.Horizontal)
            self._zone_views: dict = {}
            self._zone_tables: dict = {}

            for zone in active_zones:
                panel = QWidget()
                pv = QVBoxLayout(panel)
                pv.setContentsMargins(2, 2, 2, 2)
                pv.setSpacing(2)

                zone_hdr = QLabel(zone)
                zone_hdr.setAlignment(Qt.AlignCenter)
                zone_hdr.setFixedHeight(20)
                zone_hdr.setStyleSheet(
                    f"color: {accent}; font-weight: bold; font-size: 11px; "
                    f"background: {Colors.BG_DEEP}; border-radius: 3px;"
                )
                pv.addWidget(zone_hdr)

                view = DXFVectorView(bg=Colors.BG_DEEP)
                view.setMinimumHeight(135)  # 180px * 0.75
                pv.addWidget(view, self.SINGLE_VIEWER_STRETCH[0])

                tbl = QTableWidget(0, 2)
                tbl.setHorizontalHeaderLabels(["Campo", "Valor"])
                tbl.horizontalHeader().setSectionResizeMode(
                    0, QHeaderView.ResizeToContents)
                tbl.horizontalHeader().setSectionResizeMode(
                    1, QHeaderView.Stretch)
                tbl.verticalHeader().setVisible(False)
                tbl.setEditTriggers(QTableWidget.NoEditTriggers)
                tbl.setMinimumHeight(90)
                tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                tbl.setStyleSheet(self.ficha_table.styleSheet())
                pv.addWidget(tbl, self.SINGLE_VIEWER_STRETCH[1])

                self._zone_views[zone] = view
                self._zone_tables[zone] = tbl
                splitter.addWidget(panel)

            # Inserir splitter PIL após o header (index 1)
            lay.insertWidget(1, splitter)
            self._pil_splitter = splitter
            self._pil_mode = True

        # Load DXFs into viewers
        from pathlib import Path as _Path
        for zone, view in list((self._zone_views or {}).items()):
            p = zone_paths.get(zone)
            if p and _Path(p).exists():
                try:
                    view.load_dxf(str(p), None)
                except Exception as exc:
                    view.clear_image(f"Erro {zone}: {exc}")
            else:
                view.clear_image(f"Sem ficha {zone}")

        self._update_pil_zone_fichas(er_ficha or {}, zone_fichas)
""",
        "switch_to_pil_zones body",
    )

    text = replace_once(
        text,
        """            elif cls == "PL":
                # Cada pilar PIL gera DUAS instâncias: Para (Vigas Param) e Passa (Vigas Passam)
                for pp in ("para", "passa"):
                    virt_id = f"{iid}_{pp.capitalize()}"
                    label = "Param" if pp == "para" else "Passam"
                    display_text = f"{iid}-Vigas {label}"
                    rows[virt_id] = {
                        "id": virt_id,
                        "text": display_text,
                        "source": "estrutural",
                        "recorte_path": "",
                        "ok": n3_ok,
                        "base_stem": str(iid),
                    }
""",
        """            elif cls == "PL":
                # Cada pilar PIL gera DUAS instâncias: Para (Vigas Param) e Passa (Vigas Passam)
                for pp in ("para", "passa"):
                    virt_id = f"{iid}_{pp.capitalize()}"
                    label = "Param" if pp == "para" else "Passam"
                    display_text = f"{iid}-Vigas {label}"
                    # Verde só se o contrato derivado existir (não o N3 canônico).
                    var_root = prev_dir / "n3_variants" / pp
                    mode_ok = (
                        (var_root / f"PL_ABCD_preview_{iid}.dxf").exists()
                        and (var_root / f"PL_GRADES_preview_{iid}.dxf").exists()
                        and (var_root / f"{iid}.json").exists()
                    )
                    rows[virt_id] = {
                        "id": virt_id,
                        "text": display_text,
                        "source": "estrutural",
                        "recorte_path": "",
                        "ok": mode_ok,
                        "base_stem": str(iid),
                    }
""",
        "PL virtual items n3_ok",
    )

    text = replace_once(
        text,
        """            pil_mode = _pil_pp_from_id(item_id) if classe == "PL" else ""
            if pil_mode:
                zones, mode_payload = self.tri_level._find_n3_pil_mode_zones(
                    obra_dir, item_id,
                )
                if not zones:
                    col.pipeline.set_step(1, 'error', 'Contrato SA PARA/PASSA ausente')
                    col.pipeline.set_step(2, 'error', 'Rode análise SA para publicar')
                    self.nav_sidebar.set_status(
                        f"❌ N3 PIL {pil_mode.upper()} ausente — {item_id}",
                        Colors.ACCENT_DANGER,
                    )
                    self.nav_sidebar._enable_item_btns()
                    return
                # Não há fallback para o N3 canônico aqui: o item virtual deve
                # provar que está exibindo a variante escolhida, não uma cópia.
                col.pipeline.set_step(1, 'ok', f'Contrato SA {pil_mode.upper()}')
                col.pipeline.set_step(2, 'running', 'Carregando zonas...')
                col.switch_to_pil_zones(zones, mode_payload)
                self._configure_level_attention("N3", classe, item_id)
                col.pipeline.set_step(2, 'ok', f'N3 {pil_mode.upper()}')
                self.nav_sidebar.set_status(
                    f"✅ N3 PIL {pil_mode.upper()} — {item_id}",
                    Colors.ACCENT_SUCCESS,
                )
                self._refresh_n3_compare_n4_if_active(classe, item_id)
                self.nav_sidebar._enable_item_btns()
                return
""",
        """            pil_mode = _pil_pp_from_id(item_id) if classe == "PL" else ""
            if pil_mode:
                _ce_log(f"N3 PIL mode={pil_mode} item={item_id} obra_dir={obra_dir}")
                zones, mode_payload = self.tri_level._find_n3_pil_mode_zones(
                    obra_dir, item_id,
                )
                _ce_log(
                    f"N3 PIL zones={list(zones)} payload_keys={len(mode_payload or {})} "
                    f"variant={(mode_payload or {}).get('_sa_mode_variant')}"
                )
                if not zones:
                    col.pipeline.set_step(1, 'error', 'Contrato SA PARA/PASSA ausente')
                    col.pipeline.set_step(2, 'error', 'Rode análise SA para publicar')
                    self.nav_sidebar.set_status(
                        f"❌ N3 PIL {pil_mode.upper()} ausente — {item_id}",
                        Colors.ACCENT_DANGER,
                    )
                    self.nav_sidebar._enable_item_btns()
                    return
                # Não há fallback para o N3 canônico aqui: o item virtual deve
                # provar que está exibindo a variante escolhida, não uma cópia.
                col.pipeline.set_step(1, 'ok', f'Contrato SA {pil_mode.upper()}')
                col.pipeline.set_step(2, 'running', 'Carregando zonas...')
                # Ficha principal + mini-fichas por zona (contrato derivado).
                try:
                    col.set_ficha(self.tri_level._ficha_n3_for(classe, item_id))
                except Exception as exc:
                    _ce_log(f"N3 PIL set_ficha error: {exc}")
                try:
                    col.switch_to_pil_zones(zones, mode_payload or {})
                except Exception as exc:
                    _ce_log(f"N3 PIL switch_to_pil_zones error: {exc}")
                    col.pipeline.set_step(2, 'error', f'UI zonas: {exc}')
                    self.nav_sidebar.set_status(
                        f"❌ N3 PIL UI — {item_id}: {exc}",
                        Colors.ACCENT_DANGER,
                    )
                    self.nav_sidebar._enable_item_btns()
                    return
                self._configure_level_attention("N3", classe, item_id)
                col.pipeline.set_step(2, 'ok', f'N3 {pil_mode.upper()}')
                self.nav_sidebar.set_status(
                    f"✅ N3 PIL {pil_mode.upper()} — {item_id}",
                    Colors.ACCENT_SUCCESS,
                )
                _ce_log(f"N3 PIL OK {item_id} mode={pil_mode}")
                self._refresh_n3_compare_n4_if_active(classe, item_id)
                self.nav_sidebar._enable_item_btns()
                return
""",
        "on_gerar_n3 pil_mode",
    )

    # Enrich N1 PL ficha with face fields + contract summary
    text = replace_once(
        text,
        """        elif classe == 'PL':
            base_item_id = _pil_strip_pp(item_id)
            pd_ = self._pilares_fase3.get(base_item_id, {})
            pa  = self._pilares_assembly.get(base_item_id, {})
            pos = self._est_labels.get(base_item_id)
            rows += [
                ("==", "DIMENSIONAMENTO"),
                ("b (cm)", _fmt(pd_.get("b"))),
                ("h (cm)", _fmt(pd_.get("h"))),
                ("Altura (cm)", _fmt(pd_.get("altura"))),
                ("Nível saída", _fmt(pd_.get("nivel_saida"))),
                ("Nível chegada", _fmt(pd_.get("nivel_chegada"))),
                ("==", "DADOS GERAIS - PILAR"),
                ("grade_1", _fmt(pa.get("grade_1"))),
                ("grade_2", _fmt(pa.get("grade_2"))),
                ("distancia_1", _fmt(pa.get("distancia_1"))),
                ("Pos. estrutural (x,y)", f"({pos[0]:.0f}, {pos[1]:.0f})" if pos else "—"),
                ("Confidence", _pct(pd_.get("confidence"))),
                ("Source", _fmt(pd_.get("source"))),
            ]
""",
        """        elif classe == 'PL':
            base_item_id = _pil_strip_pp(item_id)
            pd_ = self._pilares_fase3.get(base_item_id, {})
            pa  = self._pilares_assembly.get(base_item_id, {})
            pos = self._est_labels.get(base_item_id)
            rows += [
                ("==", "DIMENSIONAMENTO"),
                ("b (cm)", _fmt(pd_.get("b"))),
                ("h (cm)", _fmt(pd_.get("h"))),
                ("Altura (cm)", _fmt(pd_.get("altura"))),
                ("Nível saída", _fmt(pd_.get("nivel_saida"))),
                ("Nível chegada", _fmt(pd_.get("nivel_chegada"))),
                ("==", "DADOS GERAIS - PILAR"),
                ("grade_1", _fmt(pa.get("grade_1"))),
                ("grade_2", _fmt(pa.get("grade_2"))),
                ("distancia_1", _fmt(pa.get("distancia_1"))),
                ("Pos. estrutural (x,y)", f"({pos[0]:.0f}, {pos[1]:.0f})" if pos else "—"),
                ("Confidence", _pct(pd_.get("confidence"))),
                ("Source", _fmt(pd_.get("source"))),
            ]
            # Campos de face (SA) + resumo do contrato N3 derivado, se existir.
            try:
                sa_faces = self._pl_sa_face_summary(base_item_id)
            except Exception:
                sa_faces = []
            if sa_faces:
                rows.append(("==", "FACES SA (laje / viga)"))
                rows.extend(sa_faces)
            mode = _pil_pp_from_id(item_id)
            if mode and self._current_obra:
                try:
                    crows = self._pl_n3_contract_summary(base_item_id, mode)
                    if crows:
                        rows.append(("==", f"CONTRATO N3 {mode.upper()} (derivado SA)"))
                        rows.extend(crows)
                except Exception:
                    pass
""",
        "ficha_n1 PL faces",
    )

    if text == original:
        raise SystemExit("No changes applied")

    # Inject helper methods near _ficha_n3_for if missing
    if "def _pl_sa_face_summary" not in text:
        anchor = "    def _ficha_n3(self, vn: str) -> list:\n"
        helpers = '''    def _pl_sa_face_summary(self, base_item_id: str) -> list:
        """Lê faces do pilar no DB (extra_data / sides) para a ficha N1."""
        rows: list = []
        try:
            import sqlite3
            conn = sqlite3.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT p.extra_data_json, p.sides_data_json, pr.name AS proj
                FROM pillars p
                JOIN projects pr ON pr.id = p.project_id
                WHERE p.name = ?
                ORDER BY p.id DESC
                LIMIT 8
                """,
                (base_item_id,),
            )
            candidates = cur.fetchall()
            conn.close()
        except Exception:
            return rows
        pick = None
        for row in candidates:
            proj = str(row["proj"] or "")
            if "13P" in proj.upper() or "13_PAV" in proj.upper() or "13" in proj:
                pick = row
                break
        if pick is None and candidates:
            pick = candidates[0]
        if not pick:
            return rows
        try:
            extra = json.loads(pick["extra_data_json"] or "{}")
        except Exception:
            extra = {}
        try:
            sides = json.loads(pick["sides_data_json"] or "{}")
        except Exception:
            sides = {}
        for fid in ("A", "B", "C", "D"):
            l1 = extra.get(f"p_s{fid}_l1_n") or (sides.get(fid) or {}).get("l1_n") or "—"
            l1h = extra.get(f"p_s{fid}_l1_h") or (sides.get(fid) or {}).get("l1_h") or "—"
            vn = (
                extra.get(f"p_s{fid}_v_int_n")
                or (sides.get(fid) or {}).get("v_int_n")
                or extra.get(f"p_s{fid}_v_esq_n")
                or (sides.get(fid) or {}).get("v_esq_n")
                or "—"
            )
            vd = (
                extra.get(f"p_s{fid}_v_int_d")
                or (sides.get(fid) or {}).get("v_int_d")
                or extra.get(f"p_s{fid}_v_esq_d")
                or (sides.get(fid) or {}).get("v_esq_d")
                or "—"
            )
            rows.append((f"Face {fid} laje", f"{l1} / H={l1h}"))
            rows.append((f"Face {fid} viga", f"{vn} / dim={vd}"))
        return rows

    def _pl_n3_contract_summary(self, base_item_id: str, mode: str) -> list:
        """Resumo do contrato N3 PARA/PASSA publicado em n3_variants."""
        rows: list = []
        if not self._current_obra or mode not in ("para", "passa"):
            return rows
        path = (
            DADOS_OBRAS_ROOT / self._current_obra / "Fase-6_Execucao_CAD"
            / "n3_variants" / mode / f"{base_item_id}.json"
        )
        if not path.exists():
            rows.append(("Contrato", f"ausente: {path.name}"))
            return rows
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            rows.append(("Contrato", f"erro leitura: {exc}"))
            return rows
        contract = data.get("_sa_mode_contract") or {}
        rows.append(("modo", str(contract.get("modo_semantico") or mode).upper()))
        rows.append(("schema", str(contract.get("schema") or "—")))
        for fid, face in (contract.get("faces") or {}).items():
            topo = (face or {}).get("vazio_topo") or {}
            stops = (face or {}).get("aberturas_vigas_que_param") or []
            arrs = (face or {}).get("aberturas_vigas_que_chegam") or []
            act_s = [o for o in stops if o.get("estado") == "ativa"]
            act_a = [o for o in arrs if o.get("estado") == "ativa"]
            neu = [o for o in arrs if o.get("estado") == "neutralizada"]
            bits = [f"topo={topo.get('valor_cm')}({topo.get('fonte')})"]
            for o in act_s:
                bits.append(f"PARA {o.get('slot')}:{o.get('nome')}")
            for o in act_a:
                bits.append(f"CHEGA {o.get('slot')}:{o.get('nome')}")
            for o in neu:
                bits.append(f"NEUT {o.get('slot')}:{o.get('nome')}")
            rows.append((f"Face {fid}", "; ".join(bits)))
        return rows

'''
        if anchor not in text:
            raise SystemExit("anchor for helpers not found")
        text = text.replace(anchor, helpers + anchor, 1)

    tmp = SRC.with_suffix(".py._patch_tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.replace(SRC)
        print("PATCHED", SRC)
    except Exception as exc:
        import shutil
        print("replace failed:", exc, "— trying copy2")
        shutil.copy2(tmp, SRC)
        print("COPIED", SRC)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
    print("done, bytes", SRC.stat().st_size)


if __name__ == "__main__":
    main()
