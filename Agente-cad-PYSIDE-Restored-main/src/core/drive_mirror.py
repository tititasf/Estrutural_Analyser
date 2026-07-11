"""Cria o "espelho local" de 1 item de obra Drive (Masterplan OBRAS DRIVE, Fase 1).

Função pura (sem Qt, sem rede) — recebe os dados já buscados do portal (via
`DriveClient`) e grava só o necessário em `project_data.vision` pra que o
Diagnostic Hub existente (`diagnostic_hub.py`) enxergue esse item exatamente
como enxergaria um bruto/recorte local de verdade: 1 linha em `works`, 1 linha
em `obra_triagem` (o bruto) e 1 linha em `obra_recortes` (o item de recorte),
mais o mapeamento em `drive_obras` que o download sob demanda usa depois.

Nunca baixa o .dxf em si — só cria os registros. O arquivo físico só é
buscado quando `diagnostic_hub.py` efetivamente tenta abrir aquele path
(ver `_garantir_drive_download` em `diagnostic_hub.py`).

Validação (recorte, SA, N1+N3): SÓ PULL (portal → app). A app nunca escreve
de volta no portal — decisão do dono (2026-07-10) pra evitar que um
clique/teste local na app sobrescreva validação real da equipe feita na web.
Os botões de validar na app (Diagnostic Hub, Structural Analyzer,
Comparison Engine) são flags LOCAIS — servem de lembrete pro dono, não
sincronizam pra fora.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from src.core.database import DatabaseManager

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")


def sanitizar_nome_obra(nome: str) -> str:
    """Mesma regra de sanitização de `ProjectStorageManager._sanitize_name`."""
    nome = nome.replace(" ", "_").replace("/", "_").replace(".", "")
    return re.sub(r"[^\w\-]", "", nome)


def _recorte_type_e_index(item_id: str) -> tuple[str, int]:
    """`torre_1` -> ("torre", 0), `torre_2` -> ("torre", 1); demais item_id viram
    seu próprio recorte_type com index 0 (`detalhes`, `convencao_pilares`, etc)."""
    m = re.match(r"^torre_(\d+)$", item_id)
    if m:
        return "torre", int(m.group(1)) - 1
    return item_id, 0


def criar_espelho_local_drive(
    db: DatabaseManager,
    obra_portal: dict,
    bruto_portal: dict,
    item_portal: dict,
    dados_obras_root: Optional[Path] = None,
) -> tuple[str, Path]:
    """Garante o espelho local de 1 item de recorte de uma obra Drive.

    Args:
        db: DatabaseManager já aberto (mesma project_data.vision do Hub).
        obra_portal: dict do portal com pelo menos {"id", "nome"}.
        bruto_portal: dict do portal com pelo menos {"bruto_id", "nome"} —
            `nome` é o file_name original do bruto (ex: "13PAV.dxf").
        item_portal: dict do portal com pelo menos {"item_id"} (ex: "torre_1").

    Returns:
        (obra_local_nome, item_local_path) — `obra_local_nome` é o valor a
        passar pro Hub (`request_open_bruto.emit(obra_local_nome, ...)`);
        `item_local_path` é o path local esperado do .dxf do item (pode não
        existir em disco ainda — só é baixado sob demanda).
    """
    root = dados_obras_root or DADOS_OBRAS_ROOT
    obra_nome_portal = obra_portal["nome"]
    obra_local_nome = f"[DRIVE] {sanitizar_nome_obra(obra_nome_portal)}"

    bruto_id = bruto_portal["bruto_id"]
    bruto_file_name = bruto_portal.get("nome") or f"{bruto_id}.dxf"
    item_id = item_portal["item_id"]

    obra_dir = root / obra_local_nome
    recortes_dir = obra_dir / "Fase-2_Triagem" / "recortes" / bruto_id
    bruto_local_path = obra_dir / "entrada" / bruto_file_name
    item_local_path = recortes_dir / f"{item_id}.dxf"

    conn = db._get_conn()
    try:
        # obra_recortes não é criada por DatabaseManager (é criada sob demanda por
        # scripts/obra_crop_engine.py) — garante que existe antes de gravar nela.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS obra_recortes (
                id                TEXT PRIMARY KEY,
                obra_name         TEXT NOT NULL,
                pavimento_name    TEXT NOT NULL,
                dxf_bruto_path    TEXT NOT NULL,
                recorte_type      TEXT NOT NULL,
                recorte_index     INTEGER DEFAULT 0,
                output_path       TEXT,
                bbox_auto         TEXT,
                bbox_approved     TEXT,
                entity_count      INTEGER DEFAULT 0,
                score             REAL DEFAULT 0.0,
                status            TEXT DEFAULT 'auto',
                n_torres          INTEGER DEFAULT 1,
                created_at        TEXT,
                approved_at       TEXT,
                UNIQUE(obra_name, pavimento_name, recorte_type, recorte_index)
            )
            """
        )

        conn.execute("INSERT OR IGNORE INTO works (name) VALUES (?)", (obra_local_nome,))

        conn.execute(
            """
            INSERT OR IGNORE INTO obra_triagem
                (id, obra_name, file_path, file_name, file_ext, suggested_category,
                 suggested_order, confidence, status, classifier, notes, created_at)
            VALUES (?, ?, ?, ?, '.dxf', 'Bruto', 0, 1.0, 'approved', 'drive-mirror', ?, CURRENT_TIMESTAMP)
            """,
            (
                f"drive:{bruto_id}",
                obra_local_nome,
                str(bruto_local_path),
                bruto_file_name,
                f"pav={bruto_portal.get('pavimento') or 'Indeterminado'}",
            ),
        )

        # Status real vindo do portal (não mais hardcoded 'approved' pra
        # tudo) — respeita o `validado` que a Triagem web já expõe por item.
        # No re-espelhamento (ON CONFLICT): NUNCA rebaixa um status já
        # 'approved' localmente (protege validação feita no app OU já
        # puxada do portal antes) — só adota o status novo do portal se o
        # local ainda não estava aprovado. Harmoniza com a regra do dono:
        # nenhum lado sobrescreve validação já feita no outro.
        recorte_type, recorte_index = _recorte_type_e_index(item_id)
        status_portal = "approved" if item_portal.get("validado") else "auto"
        conn.execute(
            """
            INSERT INTO obra_recortes
                (id, obra_name, pavimento_name, dxf_bruto_path, recorte_type, recorte_index,
                 output_path, status, n_torres, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(obra_name, pavimento_name, recorte_type, recorte_index) DO UPDATE SET
                output_path=excluded.output_path,
                dxf_bruto_path=excluded.dxf_bruto_path,
                status=CASE WHEN obra_recortes.status='approved' THEN obra_recortes.status ELSE excluded.status END
            """,
            (
                f"drive:{bruto_id}:{item_id}",
                obra_local_nome,
                bruto_portal.get("pavimento") or "Indeterminado",
                str(bruto_local_path),
                recorte_type,
                recorte_index,
                str(item_local_path),
                status_portal,
                _now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    db.registrar_drive_item(
        obra_nome=obra_local_nome,
        bruto_id=bruto_id,
        item_id=item_id,
        portal_obra_id=obra_portal["id"],
        portal_bruto_id=bruto_id,
        portal_item_id=item_id,
    )

    return obra_local_nome, item_local_path


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat()


def puxar_validacoes_n1n3(db: DatabaseManager, obra_nome: str) -> None:
    """Puxa o estado de validação N1+N3 do portal pra TODAS as classes já
    tocadas e faz merge protetivo local (nunca rebaixa n1_ok/n3_ok já True).
    Chamado junto de `espelhar_obra_completa_drive`. No-op pra obra local."""
    portal_obra_id = db.obter_portal_obra_id(obra_nome) if obra_nome else None
    if not portal_obra_id:
        return
    try:
        from src.core.drive_client import obter_cliente_padrao

        validacoes = obter_cliente_padrao().listar_validacoes_classe(portal_obra_id)
    except Exception:
        return
    for classe, v in validacoes.items():
        db.set_validacao_n1n3(obra_nome, classe, bool(v.get("n1_ok")), bool(v.get("n3_ok")))


def _garantir_projeto_pavimento_drive(
    db: DatabaseManager, obra_local_nome: str, obra_portal: dict, bruto_portal: dict,
    validado_sa_portal: bool = False,
    dados_obras_root: Optional[Path] = None,
) -> None:
    """Cria/atualiza (idempotente) a linha em `projects` (1 por pavimento)
    que o Structural Analyzer usa pra listar/abrir pavimentos — `dxf_path`
    aponta pro mesmo `torre_1.dxf` que o Diagnostic Hub usa (mesmo
    motor/dado dos dois lados, igual já vale pra obra local). Não baixa
    nada — só metadado.

    `validado_sa_portal`: estado de validação "item completo" do SA vindo do
    portal (Fase 2). Merge protetivo: NUNCA rebaixa `validado_sa` já 1
    localmente (validação feita no app ou puxada antes) — só adota True se
    ainda não estava validado localmente."""
    root = dados_obras_root or DADOS_OBRAS_ROOT
    bruto_id = bruto_portal["bruto_id"]
    pavimento = bruto_portal.get("pavimento") or "Indeterminado"
    torre1_path = root / obra_local_nome / "Fase-2_Triagem" / "recortes" / bruto_id / "torre_1.dxf"

    conn = db._get_conn()
    try:
        # Detecta (só referência, NUNCA funde) o project que o pipeline SA do
        # PORTAL já registrou pra esse MESMO pavimento real — chave exata:
        # work_name = `obra['local_path']` (o path que `_garantir_project_
        # registrado`, do lado portal, usa) + mesmo pavement_name. Ids/
        # work_name continuam 100% isolados; isso só guarda a referência pra
        # a UI poder mostrar "SA já rodou na web: X pilares/vigas/lajes".
        web_sa_project_id = None
        local_path_portal = obra_portal.get("local_path")
        if local_path_portal:
            row_web = conn.execute(
                "SELECT id FROM projects WHERE work_name = ? AND pavement_name = ? AND id NOT LIKE 'drive:%'",
                (local_path_portal, pavimento)
            ).fetchone()
            if row_web:
                web_sa_project_id = row_web[0]

        conn.execute(
            """
            INSERT INTO projects
                (id, name, dxf_path, work_name, pavement_name, author_name, sync_status,
                 validado_sa, validado_sa_em, web_sa_project_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'drive-mirror', 'pending', ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                dxf_path=excluded.dxf_path,
                validado_sa=CASE WHEN projects.validado_sa=1 THEN 1 ELSE excluded.validado_sa END,
                validado_sa_em=CASE WHEN projects.validado_sa=1 THEN projects.validado_sa_em ELSE excluded.validado_sa_em END,
                web_sa_project_id=excluded.web_sa_project_id
            """,
            (
                f"drive:{bruto_id}", pavimento, str(torre1_path), obra_local_nome, pavimento,
                1 if validado_sa_portal else 0,
                _now_iso() if validado_sa_portal else None,
                web_sa_project_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


# Nomes de pasta canônicos — DEVEM bater com `ProjectManager._FASE1_FOLDER_MAP`
# (project_manager.py). Duplicado aqui (não importado de lá) porque
# drive_mirror.py é núcleo/sem-Qt e não deve depender de um widget de UI.
_FASE1_FOLDER_POR_CATEGORIA = {
    "bruto": ("Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF", "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)"),
    "detalhe": ("Detalhes_Estruturais_DWG_PDF_DXF_MD", "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)"),
    "referencia": ("Documentos_e_Atas_de_Reunioes_PDF_MD", "Documentos e Atas de Reunioes(.PDF/.MD)"),
}


def _categoria_documento(arquivo_nome: str, tipo_documento: Optional[str]) -> tuple[str, str]:
    """Mapeia (extensão + `tipo_documento` do portal: 'Bruto'/'Detalhe') pro
    par (nome_pasta, categoria_canonica) da Fase-1_Ingestao local. Heurística
    pragmática — o portal só distingue Bruto/Detalhe, não os 4 buckets
    completos da app desktop; "Projetos Finalizados" fica sem equivalente."""
    ext = Path(arquivo_nome).suffix.lower()
    eh_detalhe = (tipo_documento or "").strip().lower() == "detalhe"
    if ext in (".dwg", ".dxf"):
        return _FASE1_FOLDER_POR_CATEGORIA["detalhe" if eh_detalhe else "bruto"]
    if ext == ".pdf" and eh_detalhe:
        return _FASE1_FOLDER_POR_CATEGORIA["detalhe"]
    return _FASE1_FOLDER_POR_CATEGORIA["referencia"]


def _garantir_documento_drive(
    db: DatabaseManager, obra_local_nome: str, obra_portal: dict, doc_portal: dict,
    project_id: Optional[str], dados_obras_root: Optional[Path] = None,
) -> None:
    """Cria (idempotente) a linha em `project_documents` (aba "1. Ingestão")
    pra 1 documento bruto/PDF/etc do portal — só metadado, nunca baixa. Se
    `project_id` for None (documento sem pavimento identificável), só registra
    o mapeamento de download — não aparece na aba Ingestão ainda."""
    root = dados_obras_root or DADOS_OBRAS_ROOT
    arquivo_nome = doc_portal.get("arquivo_nome") or "arquivo_sem_nome"
    folder, categoria = _categoria_documento(arquivo_nome, doc_portal.get("tipo_documento_confirmado") or doc_portal.get("tipo_documento_sugerido"))
    arquivo_local = root / obra_local_nome / "Fase-1_Ingestao" / folder / arquivo_nome

    if project_id:
        conn = db._get_conn()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO project_documents
                    (id, project_id, name, file_path, extension, phase, category, sync_status, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, 'pending', CURRENT_TIMESTAMP)
                """,
                (f"drive:{doc_portal['id']}", project_id, arquivo_nome, str(arquivo_local),
                 Path(arquivo_nome).suffix.lower(), categoria),
            )
            conn.commit()
        finally:
            conn.close()

    db.registrar_drive_documento(
        obra_nome=obra_local_nome,
        arquivo_local=str(arquivo_local),
        portal_obra_id=obra_portal["id"],
        portal_doc_id=doc_portal["id"],
    )


def _preferir_bruto_por_pavimento(brutos: list[dict]) -> list[dict]:
    """O portal às vezes lista 2+ 'brutos' pro MESMO pavimento (variantes
    .dwg/.dxf/ODA do mesmo arquivo fonte) — sem isso, cada pavimento viraria
    2 pavimentos/projetos duplicados na app. Mantém só 1 por pavimento,
    preferindo o que tem sufixo ODA (convenção já estabelecida: o crop engine
    só roda no .dxf convertido, não no .dwg cru — só esse tem recorte real)."""
    por_pav: dict[str, dict] = {}
    for b in brutos:
        pav = b.get("pavimento") or f"__sem_pavimento__{b['bruto_id']}"
        atual = por_pav.get(pav)
        if atual is None or ("ODA" in b["bruto_id"].upper() and "ODA" not in atual["bruto_id"].upper()):
            por_pav[pav] = b
    return list(por_pav.values())


def espelhar_obra_completa_drive(db: DatabaseManager, drive_client, obra_portal: dict) -> str:
    """Espelha TODOS os brutos/itens/documentos/pavimentos de 1 obra do portal
    de uma vez (chamado ao selecionar a obra na sidebar de Gerenciar
    Projetos) — só metadados (título/referência/nome), NENHUM .dxf/.dwg/.pdf
    é baixado aqui. Cobre os 3 lugares que a app usa pra ver uma obra:
    Triagem+Recortes (Diagnostic Hub), Ingestão (`project_documents`) e
    pavimentos (`projects`, usado pelo Structural Analyzer) — todos com
    download real sob demanda só quando o item específico é aberto.

    Retorna o `obra_local_nome` (mesmo pra todos os itens dessa obra), pronto
    pra usar como `work_name`/`obra_name` no resto da app — a partir daqui a
    obra Drive se comporta como uma obra local qualquer.
    """
    obra_local_nome = f"[DRIVE] {sanitizar_nome_obra(obra_portal['nome'])}"

    # O portal às vezes lista 2+ "brutos" pro MESMO arquivo fonte (ex: o .dwg
    # original E o .dxf convertido por ODA) — só o convertido tem recorte de
    # verdade (crop engine não roda em .dwg cru), então brutos sem nenhum
    # item de recorte são pulados aqui (evita pavimento/projeto duplicado).
    brutos_com_itens = []
    for bruto in drive_client.listar_brutos(obra_portal["id"]):
        itens = drive_client.listar_itens(obra_portal["id"], bruto["bruto_id"])
        if itens:
            brutos_com_itens.append((bruto, itens))
    brutos_dedup = _preferir_bruto_por_pavimento([b for b, _ in brutos_com_itens])
    itens_por_bruto_id = {b["bruto_id"]: itens for b, itens in brutos_com_itens}

    try:
        validacoes_sa = drive_client.listar_validacoes_sa(obra_portal["id"])
    except Exception:
        validacoes_sa = {}

    pavimento_para_project_id: dict[str, str] = {}
    nome_bruto_para_path_entrada: dict[str, Path] = {}
    for bruto in brutos_dedup:
        _garantir_projeto_pavimento_drive(
            db, obra_local_nome, obra_portal, bruto,
            validado_sa_portal=bool(validacoes_sa.get(bruto["bruto_id"])),
        )
        pavimento = bruto.get("pavimento") or "Indeterminado"
        pavimento_para_project_id[pavimento] = f"drive:{bruto['bruto_id']}"
        bruto_file_name = bruto.get("nome") or f"{bruto['bruto_id']}.dxf"
        nome_bruto_para_path_entrada[bruto_file_name] = DADOS_OBRAS_ROOT / obra_local_nome / "entrada" / bruto_file_name

        for item in itens_por_bruto_id[bruto["bruto_id"]]:
            criar_espelho_local_drive(db, obra_portal, bruto, item)

    try:
        documentos = drive_client.obter_obra(obra_portal["id"]).get("documentos", [])
    except Exception:
        documentos = []
    for doc in documentos:
        pavimento_doc = doc.get("pavimento_confirmado") or doc.get("pavimento_sugerido") or None
        project_id = pavimento_para_project_id.get(pavimento_doc) if pavimento_doc else None
        _garantir_documento_drive(db, obra_local_nome, obra_portal, doc, project_id)

        # Documento é o MESMO arquivo físico que um bruto de Triagem (path
        # `entrada/<nome>`, convenção usada por `obra_triagem`/Diagnostic Hub)?
        # Registra o mapeamento TAMBÉM por esse path — sem isso, abrir o
        # bruto cru na aba BRUTO do Hub nunca encontra o download certo,
        # porque aquele path é diferente do path de Fase-1_Ingestao usado
        # acima em `_garantir_documento_drive`.
        path_entrada = nome_bruto_para_path_entrada.get(doc.get("arquivo_nome"))
        if path_entrada:
            db.registrar_drive_documento(
                obra_nome=obra_local_nome,
                arquivo_local=str(path_entrada),
                portal_obra_id=obra_portal["id"],
                portal_doc_id=doc["id"],
            )

    puxar_validacoes_n1n3(db, obra_local_nome)

    return obra_local_nome
