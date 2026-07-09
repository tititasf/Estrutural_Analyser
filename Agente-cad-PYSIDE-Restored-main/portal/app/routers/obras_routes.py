"""Rotas de obras: GET /obras, GET /obras/{id} (HANDOFF §1.1/§1.2 etapa 1)."""

from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import access, auth, certification, classificador, drive_poller
from ..dbdep import get_db_conn
from ...db import repository as repo

log = logging.getLogger("portal.obras_routes")

router = APIRouter(prefix="/obras", tags=["obras"])

_EXTENSOES_VALIDAS = (".dwg", ".dxf")  # modo rápido (legado): a obra INTEIRA é 1 DXF/DWG, PDF não serve pra isso
_EXTENSOES_VALIDAS_DOCUMENTOS = (".dwg", ".dxf", ".pdf")  # obra-como-container: PDF é material de referência válido


class CriarObraIn(BaseModel):
    nome: str
    descricao: Optional[str] = None


class ClassificarDocumentoIn(BaseModel):
    classe_confirmada: Optional[str] = None
    pavimento_confirmado: Optional[str] = None
    tipo_documento_confirmado: Optional[str] = None


class MoverDocumentoIn(BaseModel):
    """[2026-07-07] Drag-and-drop na Triagem — mover um doc pra um grupo
    Pavimento+Tipo, ou de volta pra "Indeterminado" (pavimento=None limpa de
    verdade, ver repo.mover_documento_para_indeterminado)."""
    pavimento: Optional[str] = None
    tipo_documento: Optional[str] = None


class AtualizarCabecalhoObraIn(BaseModel):
    """[2026-07-07] Cabeçalho de referência do processamento — quem pediu,
    prazo, critérios do cliente. Todos opcionais: só atualiza o que vier
    preenchido (repo.atualizar_cabecalho_obra usa COALESCE)."""
    nome: Optional[str] = None
    cliente: Optional[str] = None
    data_solicitacao: Optional[str] = None
    data_entrega: Optional[str] = None
    criterios_cliente: Optional[str] = None
    observacoes: Optional[str] = None


class RenomearDocumentoIn(BaseModel):
    nome_exibicao: str


@router.get("")
def listar_obras(
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Etapa 1 (Upload): lista as obras do membro (ou de TODOS, se dono — 2026-07-06)."""
    obras = (
        repo.listar_todas_obras(conn)
        if access.eh_dono(membro)
        else repo.listar_obras_por_membro(conn, membro["id"])
    )
    return {
        "membro": membro["login"],
        "papel": membro["papel"],
        "drive": request.app.state.estado_global.get("drive", "ok"),
        "obras": obras,
    }


@router.post("/verificar-drive")
def verificar_drive_agora(
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Dispara 1 varredura do Drive AGORA (2026-07-06) — sem esperar o poller de fundo.

    Membro comum: so' varre a PROPRIA pasta. Dono: varre TODOS (ja' ve' tudo mesmo).
    Cliente novo por chamada (nao reusa app.state.drive_client) — mesma disciplina
    de thread-safety do poller de fundo (fix 2026-07-05, cross-thread sqlite/creds).
    """
    settings = request.app.state.settings
    cliente = drive_poller.montar_drive_client(settings)
    membros_alvo = None if access.eh_dono(membro) else [membro]
    try:
        novas = drive_poller.varrer_uma_vez(conn, cliente, settings, membros=membros_alvo)
    except Exception as exc:  # noqa: BLE001 - mesma degradacao R8 do poller de fundo
        raise HTTPException(status_code=502, detail=f"Drive indisponivel agora: {exc}") from exc
    return {"novas_obras": len(novas), "drive_modo": type(cliente).__name__}


@router.post("/upload")
def upload_obra(
    request: Request,
    arquivo: UploadFile = File(...),
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """[2026-07-06] Upload direto pelo portal — o usuário nunca precisa abrir o Drive.

    O arquivo ainda VAI para o Drive do membro por baixo dos panos (DP-10 continua
    valendo: Drive é a fonte de verdade, o portal só é a porta de entrada) — aqui só
    poupamos o usuário de sair do navegador. Grava em disco por streaming (nunca
    carrega o arquivo inteiro em memória — CAD pode ter centenas de MB) e recusa
    acima de `settings.max_obra_mb` (R6) tao logo o limite estoure, sem terminar
    de receber o resto.

    [FIX 2026-07-06] endpoint definido como SINCRONO de propósito (nao `async def`):
    `Depends(get_db_conn)` e' um generator sincrono, que o FastAPI roda numa thread
    do threadpool — se o corpo da rota fosse `async def`, ele rodaria na thread do
    event loop e usar `conn` ali seria o MESMO bug cross-thread ja' corrigido em
    2026-07-05 (`sqlite3.ProgrammingError`), confirmado reproduzindo de verdade com
    httpx.ASGITransport antes deste fix. Endpoint sincrono = tudo (Depends + corpo)
    na MESMA thread, sem essa classe de bug. `arquivo.file` (o SpooledTemporaryFile
    por baixo do UploadFile) já está totalmente recebido pelo Starlette antes do
    endpoint sincrono rodar — ler dele em chunks aqui e' sincrono e seguro.
    """
    settings = request.app.state.settings
    if not membro.get("drive_folder_id"):
        raise HTTPException(
            status_code=422,
            detail="sua pasta do Drive ainda não foi configurada — peça ao dono para associar.",
        )

    nome = arquivo.filename or "obra"
    ext = Path(nome).suffix.lower()
    if ext not in _EXTENSOES_VALIDAS:
        raise HTTPException(
            status_code=422,
            detail=f"extensão {ext or '(nenhuma)'} não suportada — use .dwg ou .dxf.",
        )

    limite_bytes = settings.max_obra_mb * 1024 * 1024
    tmp_dir = Path(tempfile.mkdtemp(prefix="portal_upload_"))
    tmp_path = tmp_dir / nome
    try:
        tamanho = 0
        with open(tmp_path, "wb") as fh:
            while True:
                pedaco = arquivo.file.read(1024 * 1024)
                if not pedaco:
                    break
                tamanho += len(pedaco)
                if tamanho > limite_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"arquivo maior que o limite de {settings.max_obra_mb}MB.",
                    )
                fh.write(pedaco)

        cliente = drive_poller.montar_drive_client(settings)
        try:
            file_id = cliente.enviar_arquivo(membro["drive_folder_id"], tmp_path, nome)
        except Exception as exc:  # noqa: BLE001 - Drive pode falhar de varias formas (R8)
            raise HTTPException(
                status_code=502, detail=f"falha ao enviar para o Drive: {exc}"
            ) from exc

        # registra a obra JA' (nao espera o poller de fundo) — reusa a mesma
        # variedade/dedup do fluxo normal, so' escopado a este membro.
        try:
            novas = drive_poller.varrer_uma_vez(conn, cliente, settings, membros=[membro])
        except Exception:  # noqa: BLE001 - degradacao R8: upload no Drive ja' funcionou
            novas = []
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return {"file_id": file_id, "novas_obras": len(novas)}


@router.post("/criar")
def criar_obra_endpoint(
    body: CriarObraIn,
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """[2026-07-06] Obra-como-container: 1a etapa do fluxo novo — cria a obra
    EXPLICITAMENTE (nome + descricao), antes de qualquer upload. Documentos
    (varios, de varias classes) entram depois via POST /{id}/documentos; a
    triagem em lote roda depois via POST /{id}/triagem (ja existente).

    Substitui o modelo antigo "1 upload = 1 obra" (POST /upload legado segue
    funcionando para obras ja existentes, mas nao e' mais o caminho recomendado).
    """
    if not membro.get("drive_folder_id"):
        raise HTTPException(
            status_code=422,
            detail="sua pasta do Drive ainda não foi configurada — peça ao dono para associar.",
        )
    nome = body.nome.strip()
    if not nome:
        raise HTTPException(status_code=422, detail="nome da obra não pode ser vazio.")

    settings = request.app.state.settings
    slug = drive_poller._safe_slug(nome)
    cliente = drive_poller.montar_drive_client(settings)
    try:
        pasta_id = cliente.obter_ou_criar_pasta(slug, pasta_pai_id=membro["drive_folder_id"])
    except Exception as exc:  # noqa: BLE001 - Drive pode falhar de varias formas (R8)
        raise HTTPException(status_code=502, detail=f"falha ao criar pasta no Drive: {exc}") from exc

    local_path = settings.dados_obras_dir / membro["login"] / slug
    obra_id = repo.criar_obra(
        conn, membro_id=membro["id"], nome=nome, descricao=body.descricao,
        pasta_drive_id=pasta_id, estado="aguardando_ingestao", local_path=str(local_path),
    )
    return {"obra_id": obra_id, "nome": nome, "descricao": body.descricao, "pasta_drive_id": pasta_id}


@router.post("/{obra_id}/documentos")
def upload_documentos(
    obra_id: str,
    request: Request,
    arquivos: list[UploadFile] = File(...),
    tipo_documento_padrao: Optional[str] = Form(None),
    pavimento_padrao: Optional[str] = Form(None),
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """[2026-07-06] Envia N documentos (de N classes) para uma obra ja criada.

    Cada arquivo vira 1 linha em portal_documentos, classificado imediatamente
    por nome (classificador.classificar_arquivo — so' SUGESTAO, revisavel) e
    enviado ao Drive da obra por baixo dos panos (mesma disciplina do upload
    legado: Drive continua sendo a fonte de verdade). Dedup por hash DENTRO da
    obra: reenviar o mesmo arquivo não duplica.

    [2026-07-07] `tipo_documento_padrao`/`pavimento_padrao` opcionais — quando
    o usuário já sabe que TODO o lote sendo enviado é, por ex., "Detalhe" do
    "13_PAV", evita ter que corrigir cada arquivo um por um depois na tela de
    triagem. Gravado como *_confirmado (mais forte que a sugestão automática
    do classificador, mas o usuário ainda pode corrigir depois).

    Sincrono de proposito — mesmo motivo do fix 2026-07-06 em `upload_obra`
    (Depends(get_db_conn) e' sincrono; `async def` aqui reintroduziria o bug
    cross-thread ja corrigido).
    """
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")

    settings = request.app.state.settings
    limite_bytes = settings.max_obra_mb * 1024 * 1024
    obra_dir = Path(obra["local_path"]) if obra.get("local_path") else settings.dados_obras_dir / obra["nome"]
    entrada_dir = obra_dir / "entrada"
    entrada_dir.mkdir(parents=True, exist_ok=True)

    cliente = drive_poller.montar_drive_client(settings)
    resultados = []
    for arquivo in arquivos:
        nome = arquivo.filename or "documento"
        ext = Path(nome).suffix.lower()
        if ext not in _EXTENSOES_VALIDAS_DOCUMENTOS:
            resultados.append({
                "arquivo_nome": nome, "ok": False,
                "erro": f"extensão {ext or '(nenhuma)'} não suportada — use .dwg, .dxf ou .pdf.",
            })
            continue

        destino = entrada_dir / nome
        try:
            tamanho = 0
            with open(destino, "wb") as fh:
                while True:
                    pedaco = arquivo.file.read(1024 * 1024)
                    if not pedaco:
                        break
                    tamanho += len(pedaco)
                    if tamanho > limite_bytes:
                        raise OSError(f"maior que o limite de {settings.max_obra_mb}MB")
                    fh.write(pedaco)
            arquivo_hash = drive_poller._md5_arquivo(destino)
        except OSError as exc:
            destino.unlink(missing_ok=True)
            resultados.append({"arquivo_nome": nome, "ok": False, "erro": str(exc)})
            continue

        existente = repo.obter_documento_por_hash(conn, obra_id, arquivo_hash)
        if existente is not None:
            destino.unlink(missing_ok=True)
            resultados.append({
                "arquivo_nome": nome, "ok": True, "doc_id": existente["id"], "duplicado": True,
            })
            continue

        file_id = None
        try:
            file_id = cliente.enviar_arquivo(obra["pasta_drive_id"], destino, nome)
        except Exception as exc:  # noqa: BLE001 - degradacao R8: doc fica local mesmo se Drive falhar
            log.warning("falha ao enviar %s ao Drive (obra=%s): %s", nome, obra_id, exc)

        sugestao = classificador.classificar_arquivo(nome)
        doc_id = repo.criar_documento(
            conn, obra_id=obra_id, arquivo_nome=nome, arquivo_drive_id=file_id,
            arquivo_hash=arquivo_hash, local_path=str(destino),
            classe_sugerida=sugestao["classe_sugerida"],
            pavimento_sugerido=sugestao["pavimento_sugerido"],
            tipo_documento_sugerido=sugestao["tipo_documento_sugerido"],
            pavimento_confirmado=pavimento_padrao or None,
            tipo_documento_confirmado=tipo_documento_padrao or None,
            status="pendente",
        )
        resultados.append({"arquivo_nome": nome, "ok": True, "doc_id": doc_id, **sugestao})

    return {"obra_id": obra_id, "documentos": resultados}


@router.post("/{obra_id}/documentos/{doc_id}/classificar")
def classificar_documento_endpoint(
    obra_id: str,
    doc_id: str,
    body: ClassificarDocumentoIn,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """Confirmacao/correcao manual de classe+pavimento na tela de revisao da
    triagem — sobrescreve a sugestao automatica quando ela veio como 'revisar'
    (ou quando o usuario simplesmente discorda dela)."""
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    doc = repo.obter_documento(conn, doc_id)
    if doc is None or doc["obra_id"] != obra_id:
        raise HTTPException(status_code=404, detail="documento nao encontrado nesta obra")
    if not body.classe_confirmada and not body.pavimento_confirmado and not body.tipo_documento_confirmado:
        raise HTTPException(
            status_code=422,
            detail="informe classe_confirmada, pavimento_confirmado e/ou tipo_documento_confirmado.",
        )

    repo.atualizar_classificacao_documento(
        conn, doc_id,
        classe_confirmada=body.classe_confirmada,
        pavimento_confirmado=body.pavimento_confirmado,
        tipo_documento_confirmado=body.tipo_documento_confirmado,
        status="classificado",
    )
    return repo.obter_documento(conn, doc_id)


@router.post("/{obra_id}/documentos/{doc_id}/mover")
def mover_documento_endpoint(
    obra_id: str,
    doc_id: str,
    body: MoverDocumentoIn,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """[2026-07-07] Drag-and-drop na Triagem: move um doc pra um grupo
    Pavimento+Tipo (corrige triagem automática errada), ou de volta pra
    "Indeterminado" quando `pavimento` vem vazio/None — sempre persiste."""
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    doc = repo.obter_documento(conn, doc_id)
    if doc is None or doc["obra_id"] != obra_id:
        raise HTTPException(status_code=404, detail="documento nao encontrado nesta obra")

    if not body.pavimento and not body.tipo_documento:
        repo.mover_documento_para_indeterminado(conn, doc_id)
    else:
        repo.atualizar_classificacao_documento(
            conn, doc_id,
            pavimento_confirmado=body.pavimento,
            tipo_documento_confirmado=body.tipo_documento,
        )
    return repo.obter_documento(conn, doc_id)


@router.get("/{obra_id}/documentos/{doc_id}/arquivo")
def servir_arquivo_documento(
    obra_id: str,
    doc_id: str,
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """[2026-07-08, a pedido do dono] Serve o arquivo bruto do documento —
    usado pelo viewer inline de PDF (Recortes/N1/N3 têm foto renderizada;
    PDF é material de referência, mostra o próprio arquivo direto no navegador)."""
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    doc = repo.obter_documento(conn, doc_id)
    if doc is None or doc["obra_id"] != obra_id:
        raise HTTPException(status_code=404, detail="documento nao encontrado nesta obra")
    settings = request.app.state.settings
    obra_dir = Path(obra["local_path"]) if obra.get("local_path") else settings.dados_obras_dir / obra["nome"]
    caminho = obra_dir / "entrada" / doc["arquivo_nome"]
    if not caminho.is_file():
        raise HTTPException(status_code=404, detail="arquivo nao encontrado em disco")
    media = "application/pdf" if caminho.suffix.lower() == ".pdf" else "application/octet-stream"
    return FileResponse(caminho, filename=doc["arquivo_nome"], media_type=media)


@router.post("/{obra_id}/cabecalho")
def atualizar_cabecalho_obra_endpoint(
    obra_id: str,
    body: AtualizarCabecalhoObraIn,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """[2026-07-07] Edita o cabeçalho de referência (nome, cliente, datas,
    critérios, observações) — tanto pro fluxo completo quanto pro modo rápido,
    pra a obra nunca ficar só com o nome do arquivo bruto como identificação."""
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    nome = body.nome.strip() if body.nome is not None else None
    if nome == "":
        raise HTTPException(status_code=422, detail="nome não pode ficar vazio.")
    repo.atualizar_cabecalho_obra(
        conn, obra_id, nome=nome, cliente=body.cliente,
        data_solicitacao=body.data_solicitacao, data_entrega=body.data_entrega,
        criterios_cliente=body.criterios_cliente, observacoes=body.observacoes,
    )
    return repo.obter_obra(conn, obra_id)


@router.post("/{obra_id}/documentos/{doc_id}/renomear")
def renomear_documento_endpoint(
    obra_id: str,
    doc_id: str,
    body: RenomearDocumentoIn,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    """[2026-07-07] Nome de exibição editável do documento — não mexe no
    arquivo real em disco, só no rótulo mostrado na Triagem."""
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    doc = repo.obter_documento(conn, doc_id)
    if doc is None or doc["obra_id"] != obra_id:
        raise HTTPException(status_code=404, detail="documento nao encontrado nesta obra")
    nome_exibicao = body.nome_exibicao.strip()
    if not nome_exibicao:
        raise HTTPException(status_code=422, detail="nome_exibicao não pode ficar vazio.")
    repo.atualizar_nome_exibicao_documento(conn, doc_id, nome_exibicao)
    return repo.obter_documento(conn, doc_id)


@router.get("/{obra_id}")
def obter_obra(
    obra_id: str,
    request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    settings = request.app.state.settings
    jobs = repo.listar_jobs_por_obra(conn, obra_id)
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    comentarios = repo.listar_comentarios_por_obra(conn, obra_id)
    documentos = repo.listar_documentos_por_obra(conn, obra_id)
    resumo_documentos = repo.contar_documentos_por_status(conn, obra_id)
    # rotulos de certificacao por classe (R9) — exibidos junto da obra
    rotulos = {
        c: certification.classificar_certificacao(settings.status_md_path, c)
        for c in ("PL", "LV", "FV", "LJ")
    }
    return {
        "obra": obra,
        "jobs": jobs,
        "n5_releases": releases,
        "comentarios": comentarios,
        "documentos": documentos,
        "resumo_documentos": resumo_documentos,
        "rotulos_certificacao": rotulos,
    }
