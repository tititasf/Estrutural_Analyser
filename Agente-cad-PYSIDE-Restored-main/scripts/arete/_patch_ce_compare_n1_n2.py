"""Patch Comparar N1 (contexto + destaque real) e Comparar N2 (resolve recorte)."""
from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "ui" / "modules" / "comparison_engine.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"BLOCK NOT FOUND: {label}\n---\n{old[:200]}")
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"BLOCK NOT UNIQUE ({n}): {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = SRC.read_text(encoding="utf-8")

    # 1) Highlight points for PL (and keep LJ/FV)
    text = replace_once(
        text,
        '''    def _get_n1_highlight_points(self, item_id: str, classe: str) -> list:
        """Geometria exata a destacar no N1 — polígono único para LJ,
        um polígono por segmento de fundo para FV. Vazio para as demais
        classes (usam bbox aproximado via _get_n1_bbox_for)."""
        classe_up = str(classe or "").upper()
        if classe_up == "LJ":
            return self._get_lj_n1_points(item_id)
        if classe_up == "FV":
            return self._get_fv_n1_segments(item_id)
        return []
''',
        '''    def _get_n1_highlight_points(self, item_id: str, classe: str) -> list:
        """Geometria exata a destacar no N1.

        - LJ: contorno da laje
        - FV: um polígono por segmento de fundo
        - PL: polígono do pilar (points do SA/DB)
        - demais: vazio (fallback bbox via _get_n1_bbox_for)
        """
        classe_up = str(classe or "").upper()
        if classe_up == "LJ":
            return self._get_lj_n1_points(item_id)
        if classe_up == "FV":
            return self._get_fv_n1_segments(item_id)
        if classe_up == "PL":
            return self._get_pl_n1_points(item_id)
        return []

    def _get_pl_n1_points(self, item_id: str) -> list:
        """Polígono do pilar no estrutural (coords reais da planta)."""
        base = _pil_strip_pp(item_id)
        # 1) Cache em memória (scan / pilares_fase3 com geometry)
        for key in (base, item_id, str(base).upper(), str(base).lower()):
            pd = (getattr(self, "_pilares_fase3", {}) or {}).get(key)
            if isinstance(pd, dict):
                pts = pd.get("points") or pd.get("poly") or []
                if len(pts) >= 3:
                    return list(pts)
        # 2) DB SA — pillars.points_json
        try:
            import sqlite3 as _sq
            conn = _sq.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            conn.row_factory = _sq.Row
            cur = conn.cursor()
            obra = str(getattr(self, "_current_obra", "") or "")
            pav = str(getattr(self, "_current_pav", "") or "")
            row = None
            if obra:
                # prioriza projeto da obra/pav atual
                rows = cur.execute(
                    """
                    SELECT p.points_json, pr.name AS proj, pr.pavement_name
                    FROM pillars p
                    JOIN projects pr ON pr.id = p.project_id
                    WHERE p.name = ?
                      AND (pr.work_name = ? OR pr.name LIKE ?)
                    ORDER BY p.id DESC
                    LIMIT 20
                    """,
                    (base, obra, f"%{obra}%"),
                ).fetchall()
                for r in rows:
                    proj = f"{r['proj'] or ''} {r['pavement_name'] or ''}".upper()
                    if pav and (
                        pav.upper() in proj
                        or "13P" in proj
                        or "13_PAV" in proj
                        or "13" in pav.upper() and "13" in proj
                    ):
                        row = r
                        break
                if row is None and rows:
                    row = rows[0]
            if row is None:
                row = cur.execute(
                    "SELECT points_json FROM pillars WHERE name=? "
                    "ORDER BY id DESC LIMIT 1",
                    (base,),
                ).fetchone()
            conn.close()
            if row and row["points_json"]:
                import json as _json
                pts = _json.loads(row["points_json"] or "[]")
                if isinstance(pts, list) and len(pts) >= 3:
                    return pts
        except Exception as exc:
            _ce_log(f"_get_pl_n1_points error: {exc}")
        return []
''',
        "highlight points PL",
    )

    # 2) Better PL bbox: geometry-based with generous pad for context
    text = replace_once(
        text,
        '''    def _get_n1_bbox_for(self, item_id: str, classe: str = "", R: int = 134):
        """Retorna bbox do item no DXF estrutural usando labels escaneados.
        R=134 (era 267/2) e pad=34 (era 67/2) → zoom 6x mais perto que original.
        Normaliza sufixos de face: V301_A/V301_fundo → V301."""
        import re as _re
        if str(classe).upper() == "LJ":
            lj_bbox = self._points_bbox(self._get_lj_n1_points(item_id), pad=20.0)
            if lj_bbox:
                return lj_bbox
        label_id = _re.sub(r'[_.]([A-Da-d]|fundo)$', '', item_id, flags=_re.I)
        if str(classe).upper() == "PL":
            label_id = _pil_strip_pp(label_id)
        fv_bbox = self._get_n1_fv_bbox_from_db(label_id) if str(classe).upper() == "FV" else None
        if fv_bbox:
            return fv_bbox
        pos = self._est_labels.get(label_id) or self._est_labels.get(item_id)
        if not pos:
            return None
        cx, cy = pos
        xs = [ex for (_, ex, ey, _) in self._est_ents_raw
              if abs(ex - cx) < R and abs(ey - cy) < R]
        ys = [ey for (_, ex, ey, _) in self._est_ents_raw
              if abs(ex - cx) < R and abs(ey - cy) < R]
        if not xs:
            return (cx - R, cy - R, cx + R, cy + R)
        pad = 34
        return (min(xs)-pad, min(ys)-pad, max(xs)+pad, max(ys)+pad)
''',
        '''    def _get_n1_bbox_for(self, item_id: str, classe: str = "", R: int = 134):
        """Retorna bbox do item no DXF estrutural.

        PL usa a geometria real do pilar (points SA) com pad generoso de contexto.
        LJ/FV usam geometria própria. Demais classes: labels escaneados (R=134).
        """
        import re as _re
        classe_up = str(classe).upper()
        if classe_up == "LJ":
            lj_bbox = self._points_bbox(self._get_lj_n1_points(item_id), pad=20.0)
            if lj_bbox:
                return lj_bbox
        if classe_up == "PL":
            pl_pts = self._get_pl_n1_points(item_id)
            # pad ~6x a maior dimensão do pilar (mín. 180 cm) → contexto real de vizinhos
            if pl_pts:
                try:
                    xs = [float(p[0]) for p in pl_pts]
                    ys = [float(p[1]) for p in pl_pts]
                    bw = max(xs) - min(xs)
                    bh = max(ys) - min(ys)
                    pad = max(180.0, max(bw, bh) * 6.0)
                    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
                except Exception:
                    pass
            # fallback: label com R ampliado
            label_id = _pil_strip_pp(item_id)
            pos = self._est_labels.get(label_id) or self._est_labels.get(item_id)
            if pos:
                cx, cy = pos
                R_pl = max(int(R), 400)
                return (cx - R_pl, cy - R_pl, cx + R_pl, cy + R_pl)
        label_id = _re.sub(r'[_.]([A-Da-d]|fundo)$', '', item_id, flags=_re.I)
        if classe_up == "PL":
            label_id = _pil_strip_pp(label_id)
        fv_bbox = self._get_n1_fv_bbox_from_db(label_id) if classe_up == "FV" else None
        if fv_bbox:
            return fv_bbox
        pos = self._est_labels.get(label_id) or self._est_labels.get(item_id)
        if not pos:
            return None
        cx, cy = pos
        xs = [ex for (_, ex, ey, _) in self._est_ents_raw
              if abs(ex - cx) < R and abs(ey - cy) < R]
        ys = [ey for (_, ex, ey, _) in self._est_ents_raw
              if abs(ex - cx) < R and abs(ey - cy) < R]
        if not xs:
            return (cx - R, cy - R, cx + R, cy + R)
        pad = 34
        return (min(xs)-pad, min(ys)-pad, max(xs)+pad, max(ys)+pad)
''',
        "get_n1_bbox_for PL context",
    )

    # 3) Comparar N1: full structural + polygon highlight + focus context
    text = replace_once(
        text,
        '''    def _refresh_n3_compare_if_active(self, classe: str | None = None, item_id: str | None = None) -> bool:
        """Atualiza o viewer comparativo N1 aberto acima do N3 para o item atual."""
        btn = getattr(self, "_btn_comparar_n1", None)
        if not btn or not btn.isChecked():
            return True
        n1_path = self.tri_level._columns[0]._last_loaded_dxf or ""
        if not n1_path or not Path(n1_path).exists():
            return False
        classe = classe or getattr(self.nav_sidebar, "_selected_classe", "")
        item_id = item_id or getattr(self.nav_sidebar, "_selected_item", "")
        bbox = self.tri_level._get_n1_bbox_for(item_id, classe) if item_id else None
        points = (
            self.tri_level._get_n1_highlight_points(item_id, classe)
            if classe in ("LJ", "FV") and item_id else None
        )
        self.tri_level._columns[2].show_n2_above(
            n1_path,
            title=f"DXF N1 - {item_id}" if item_id else "DXF N1",
            bbox=bbox,
            highlight_points=points,
            cull_to_bbox=(classe not in ("LJ", "FV")),
        )
        if classe in ("LJ", "FV") and bbox:
            compare_view = getattr(
                self.tri_level._columns[2], "_n2_above_view", None
            )
            if compare_view and hasattr(compare_view, "focus_on_bbox"):
                compare_view.focus_on_bbox(bbox, context_factor=2.2)
        return True
''',
        '''    def _refresh_n3_compare_if_active(self, classe: str | None = None, item_id: str | None = None) -> bool:
        """Atualiza o viewer comparativo N1 aberto acima do N3 para o item atual.

        PL/LJ/FV: carrega o estrutural completo (sem cull agressivo), destaca a
        geometria real do item e faz zoom com contexto generoso ao redor.
        """
        btn = getattr(self, "_btn_comparar_n1", None)
        if not btn or not btn.isChecked():
            return True
        n1_path = self.tri_level._columns[0]._last_loaded_dxf or ""
        if not n1_path or not Path(n1_path).exists():
            return False
        classe = classe or getattr(self.nav_sidebar, "_selected_classe", "")
        item_id = item_id or getattr(self.nav_sidebar, "_selected_item", "")
        classe_up = str(classe or "").upper()
        bbox = self.tri_level._get_n1_bbox_for(item_id, classe) if item_id else None
        points = (
            self.tri_level._get_n1_highlight_points(item_id, classe)
            if item_id and classe_up in ("LJ", "FV", "PL")
            else None
        )
        # Nunca culpar o mapa para PL/LJ/FV: o usuário precisa do contexto real.
        # O zoom usa focus_on_bbox com context_factor.
        keep_full_map = classe_up in ("LJ", "FV", "PL")
        self.tri_level._columns[2].show_n2_above(
            n1_path,
            title=f"DXF N1 - {item_id}" if item_id else "DXF N1",
            bbox=bbox if not keep_full_map else None,
            highlight_points=points,
            cull_to_bbox=not keep_full_map,
        )
        compare_view = getattr(
            self.tri_level._columns[2], "_n2_above_view", None
        )
        if compare_view is not None:
            # Destaque: polígono real; se não houver points, bbox justo do item
            # (não o bbox expandido de contexto).
            if points:
                compare_view.set_highlight_geometry(points)
            elif bbox and not keep_full_map:
                compare_view.set_highlight_bbox(bbox)
            elif classe_up == "PL" and item_id:
                # Bbox justo só do pilar para o retângulo vermelho, se points falhar
                tight = self.tri_level._points_bbox(
                    self.tri_level._get_pl_n1_points(item_id), pad=4.0
                )
                if tight:
                    compare_view.set_highlight_bbox(tight)
            if bbox and hasattr(compare_view, "focus_on_bbox"):
                # PL: mais contexto (vizinhança de vigas/lajes); LJ/FV: 2.2
                factor = 1.35 if classe_up == "PL" else 2.2
                # Para PL o bbox já inclui pad de contexto (~6x); factor extra leve.
                compare_view.focus_on_bbox(bbox, context_factor=factor)
        _ce_log(
            f"Comparar N1 ok classe={classe} item={item_id} "
            f"points={len(points or [])} bbox={bbox} full_map={keep_full_map}"
        )
        return True
''',
        "refresh n3 compare n1",
    )

    # 4) Comparar N2: resolve recorte even on estrutural flow
    text = replace_once(
        text,
        '''    def _on_comparar_n2_toggled(self, checked: bool):
        """Toggle: mostra/esconde DXF N2 (recorte) acima do viewer N4."""
        col = self.tri_level._columns[3]
        if checked:
            recorte = getattr(self.nav_sidebar, '_selected_recorte_path', "") or ""
            if not recorte or not self._refresh_n4_compare_if_active(recorte, cull_to_bbox=True):
                self.nav_sidebar.set_status("Sem recorte N2 para este item", Colors.TEXT_DIM)
                self._btn_comparar_n2.setChecked(False)
            return
            recorte = getattr(self.nav_sidebar, '_selected_recorte_path', "") or ""
            if recorte and Path(recorte).exists():
                col.show_n2_above(recorte)
            else:
                self.nav_sidebar.set_status("Sem recorte N2 para este item", Colors.TEXT_DIM)
                self._btn_comparar_n2.setChecked(False)
        else:
            col.hide_n2_above()
''',
        '''    def _on_comparar_n2_toggled(self, checked: bool):
        """Toggle: mostra/esconde DXF N2 (recorte) acima do viewer N4."""
        col = self.tri_level._columns[3]
        if checked:
            recorte = self._resolve_n2_recorte_path()
            if not recorte:
                self.nav_sidebar.set_status(
                    "Sem recorte N2 para este item — rode Motor Reverso / selecione na lista Eng.Rev.",
                    Colors.TEXT_DIM,
                )
                self._btn_comparar_n2.setChecked(False)
                _ce_log("Comparar N2: recorte não resolvido")
                return
            if not self._refresh_n4_compare_if_active(
                recorte, cull_to_bbox=False
            ):
                self.nav_sidebar.set_status("Sem recorte N2 para este item", Colors.TEXT_DIM)
                self._btn_comparar_n2.setChecked(False)
                return
            _ce_log(f"Comparar N2 OK path={recorte}")
        else:
            col.hide_n2_above()

    def _resolve_n2_recorte_path(self) -> str:
        """Resolve o DXF de recorte N2 para o item atual (estrutural ou reverso).

        Ordem:
        1. path da lista Eng.Rev. (UserRole+1)
        2. último DXF carregado na coluna N2
        3. lookup DB/disco via _get_recorte_dxf_for_er (base id sem _Para/_Passa)
        """
        recorte = getattr(self.nav_sidebar, "_selected_recorte_path", "") or ""
        if recorte and Path(recorte).exists():
            return str(recorte)
        col_n2 = self.tri_level._columns[1]._last_loaded_dxf or ""
        if col_n2 and Path(col_n2).exists():
            # Só aceita se parecer recorte (não o STOG completo do pav)
            name = Path(col_n2).name.upper()
            if "PIL_" in name or "LV_" in name or "FV_" in name or "LAJ_" in name or "_SEL_" in name or "_MOTOR_" in name:
                return str(col_n2)
        classe = getattr(self.nav_sidebar, "_selected_classe", "") or ""
        item_id = getattr(self.nav_sidebar, "_selected_item", "") or ""
        if not classe or not item_id:
            return ""
        obra = (
            self.fase8_panel.cmb_obra.currentData()
            or self.fase8_panel.cmb_obra.currentText()
        )
        pav = getattr(self.fase8_panel, "current_pav_key", "") or ""
        base_id = item_id
        if str(classe).upper() == "PL":
            base_id = _pil_strip_pp(item_id)
        elif str(classe).upper() == "LV":
            base_id = _lv_elem_id(item_id)
        try:
            found = self._get_recorte_dxf_for_er(
                str(obra), str(classe).upper(), str(base_id), pav=str(pav)
            )
            if found and Path(found).exists():
                return str(found)
        except Exception as exc:
            _ce_log(f"_resolve_n2_recorte_path error: {exc}")
        return ""
''',
        "comparar n2 resolve",
    )

    # 5) refresh n4 compare uses resolved path + no cull for full recorte
    text = replace_once(
        text,
        '''    def _refresh_n4_compare_if_active(self, n2_path=None, classe: str | None = None,
                                      item_id: str | None = None, bbox=None,
                                      cull_to_bbox: bool = True) -> bool:
        """Atualiza o viewer comparativo N2 aberto acima do N4 para o item atual."""
        btn = getattr(self, "_btn_comparar_n2", None)
        if not btn or not btn.isChecked():
            return True
        path = n2_path or getattr(self.nav_sidebar, '_selected_recorte_path', "") or ""
        if not path:
            path = self.tri_level._columns[1]._last_loaded_dxf or ""
        if not path or not Path(str(path)).exists():
            return False
        classe = classe or getattr(self.nav_sidebar, "_selected_classe", "")
        item_id = item_id or getattr(self.nav_sidebar, "_selected_item", "")
        if bbox is None and item_id:
            bbox = self.tri_level._get_n2_bbox_for(item_id, classe)
        highlight_points = (
            self.tri_level._get_lj_content_points_for(item_id)
            if classe == "LJ" and item_id else None
        )
        self.tri_level._columns[3].show_n2_above(
            path,
            title=f"DXF N2 - {item_id}" if item_id else "DXF N2",
            bbox=bbox,
            highlight_points=highlight_points,
            cull_to_bbox=cull_to_bbox,
        )
        return True
''',
        '''    def _refresh_n4_compare_if_active(self, n2_path=None, classe: str | None = None,
                                      item_id: str | None = None, bbox=None,
                                      cull_to_bbox: bool = False) -> bool:
        """Atualiza o viewer comparativo N2 aberto acima do N4 para o item atual.

        Recorte N2 já é local — default sem cull (mostra o recorte inteiro).
        """
        btn = getattr(self, "_btn_comparar_n2", None)
        if not btn or not btn.isChecked():
            return True
        path = n2_path or ""
        if not path:
            path = self._resolve_n2_recorte_path()
        if not path or not Path(str(path)).exists():
            _ce_log(f"Comparar N2 path ausente: {path!r}")
            return False
        classe = classe or getattr(self.nav_sidebar, "_selected_classe", "")
        item_id = item_id or getattr(self.nav_sidebar, "_selected_item", "")
        if bbox is None and item_id and cull_to_bbox:
            bbox = self.tri_level._get_n2_bbox_for(item_id, classe)
        highlight_points = (
            self.tri_level._get_lj_content_points_for(item_id)
            if str(classe).upper() == "LJ" and item_id else None
        )
        self.tri_level._columns[3].show_n2_above(
            path,
            title=f"DXF N2 - {item_id}" if item_id else "DXF N2",
            bbox=bbox if cull_to_bbox else None,
            highlight_points=highlight_points,
            cull_to_bbox=cull_to_bbox,
        )
        return True
''',
        "refresh n4 compare",
    )

    # 6) strip PL Para/Passa em todos os lookups ER
    replacements = [
        (
            '''        # LV: IDs virtuais "V301_A_Para" → elem_id no DB é "V301"
        if classe == "LV":
            item_id = _lv_elem_id(item_id)
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)
''',
            '''        # LV: IDs virtuais "V301_A_Para" → elem_id no DB é "V301"
        # PL: IDs virtuais "P1_Para"/"P1_Passa" → "P1"
        if classe == "LV":
            item_id = _lv_elem_id(item_id)
        elif classe == "PL":
            item_id = _pil_strip_pp(item_id)
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)
''',
        ),
        (
            '''        # LV: IDs virtuais "V301_A_Para" → elem_id no DB/motor é "V301"
        if classe == "LV":
            item_id = _lv_elem_id(item_id)
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)
''',
            '''        # LV: IDs virtuais "V301_A_Para" → elem_id no DB/motor é "V301"
        # PL: IDs virtuais "P1_Para"/"P1_Passa" → "P1"
        if classe == "LV":
            item_id = _lv_elem_id(item_id)
        elif classe == "PL":
            item_id = _pil_strip_pp(item_id)
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)
''',
        ),
    ]
    count = 0
    for old, new in replacements:
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            count += n
    if count == 0:
        raise SystemExit("BLOCK NOT FOUND: strip PL variants")
    print(f"strip PL applied in {count} sites")

    tmp = SRC.with_suffix(".py._cmp_patch")
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.replace(SRC)
        print("PATCHED", SRC)
    except Exception as exc:
        import shutil
        print("replace failed", exc)
        shutil.copy2(tmp, SRC)
        print("COPIED", SRC)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
    print("size", SRC.stat().st_size)


if __name__ == "__main__":
    main()
