"""Padrão único de UI/UX pra QComboBox de obras (Masterplan OBRAS DRIVE).

Usado por TODO combobox de obra da app (Diagnostic Hub, Structural Analyzer,
Comparison Engine, Diagnostic Reverse Hub) — garante que os 4 fiquem
visualmente idênticos: obras locais primeiro (ícone de pasta), depois
cabeçalho "☁ OBRAS DRIVE" + sub-cabeçalho por membro (ambos não-clicáveis),
com as obras do portal agrupadas por dono (ícone de rede).

Busca as obras do portal DIRETO via `DriveClient.listar_obras()` — aparecem
mesmo que nunca tenham sido abertas em Gerenciar Projetos antes. O TEXTO de
cada obra real nunca é decorado (só os cabeçalhos), e o `itemData`
(Qt.UserRole) de cada item espelha o mesmo texto — funciona tanto com
chamadores que leem `currentText()`/`currentTextChanged` (Diagnostic Hub,
Structural Analyzer) quanto com os que preferem `currentData()`/`itemData(i)`
(Comparison Engine, Diagnostic Reverse Hub).
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QStyle, QWidget


def popular_combo_obras_com_drive(combo: QComboBox, widget: QWidget, obras_locais: list) -> dict:
    """Popula `combo` com `obras_locais` (lista de nomes, já resolvida pelo
    chamador — cada módulo tem sua própria fonte local) + as obras do portal,
    agrupadas por membro. Preserva a seleção atual se ainda existir.

    Retorna `{obra_local_nome: obra_portal_dict}` — só das obras Drive. O
    chamador usa esse mapa no handler de seleção pra saber se a obra
    escolhida ainda não foi espelhada (`obra_e_drive` == False) e, se for o
    caso, chamar `espelhar_obra_completa_drive` antes de prosseguir.
    """
    obras_locais = list(obras_locais)  # cópia — nunca muta a lista do chamador
    mapa_portal: dict = {}
    grupos_drive: dict = {}
    try:
        from src.core.drive_client import obter_cliente_padrao
        from src.core.drive_mirror import sanitizar_nome_obra

        for o in obter_cliente_padrao().listar_obras():
            nome_local = f"[DRIVE] {sanitizar_nome_obra(o['nome'])}"
            mapa_portal[nome_local] = o
            membro = o.get("membro_nome") or o.get("membro_login") or "—"
            grupos_drive.setdefault(membro, []).append(nome_local)
            if nome_local in obras_locais:
                obras_locais.remove(nome_local)
    except Exception:
        pass
    obras_locais.sort()

    combo.blockSignals(True)
    current = combo.currentText()
    combo.clear()
    combo.addItem("— Selecione uma obra —")

    icon_local = widget.style().standardIcon(QStyle.SP_DirIcon)
    icon_drive = widget.style().standardIcon(QStyle.SP_DriveNetIcon)
    model = combo.model()

    for o in obras_locais:
        combo.addItem(icon_local, o)
        combo.setItemData(combo.count() - 1, o)  # espelha em Qt.UserRole — compat com
        # chamadores que leem `currentData()`/`itemData(i)` em vez de `currentText()`

    if grupos_drive:
        combo.insertSeparator(combo.count())
        combo.addItem("☁ OBRAS DRIVE")
        model.item(combo.count() - 1).setEnabled(False)
        for membro in sorted(grupos_drive.keys()):
            combo.addItem(f"— {membro} —")
            model.item(combo.count() - 1).setEnabled(False)
            for nome_local in sorted(grupos_drive[membro]):
                combo.addItem(icon_drive, nome_local)
                combo.setItemData(combo.count() - 1, nome_local)

    idx = combo.findText(current)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    combo.blockSignals(False)
    return mapa_portal


def espelhar_se_necessario(db, obra_nome: str, mapa_portal: dict) -> None:
    """Chame no handler de seleção do combo: se `obra_nome` for uma obra do
    portal (está em `mapa_portal`), (re)espelha na hora — idempotente,
    sempre pega o estado mais recente do portal. No-op pra obra local."""
    portal_obra = mapa_portal.get(obra_nome)
    if not portal_obra:
        return
    try:
        from src.core.drive_client import obter_cliente_padrao
        from src.core.drive_mirror import espelhar_obra_completa_drive

        espelhar_obra_completa_drive(db, obter_cliente_padrao(), portal_obra)
    except Exception as e:
        print(f"[DriveObrasCombo] Falha ao espelhar obra Drive '{obra_nome}': {e}", flush=True)
