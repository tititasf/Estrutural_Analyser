"""Rotas de obras: GET /obras, GET /obras/{id} (HANDOFF §1.1/§1.2 etapa 1)."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from .. import access, auth, certification, drive_poller
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(prefix="/obras", tags=["obras"])

_EXTENSOES_VALIDAS = (".dwg", ".dxf")


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
        "rotulos_certificacao": rotulos,
    }
