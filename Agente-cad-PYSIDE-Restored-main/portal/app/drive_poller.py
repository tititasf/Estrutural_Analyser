"""Poller do Google Drive (DP-10/DP-11/R8) por injecao de dependencia.

Interface `DriveClient` abstrata + duas implementacoes:
  - GoogleDriveClient: real, google-api-python-client + service account (drive.readonly).
  - FakeDriveClient: le de uma pasta local (dev/teste) — o "Drive" e' um diretorio.

O poller usa a INTERFACE, nunca a implementacao concreta — troca por DI. A logica de
varredura, dedup (file_id+md5) e degradacao (R8) e' identica para as duas.

Dedup (HANDOFF §2.5): chave = arquivo_hash (md5 do conteudo). O indice UNIQUE em
portal_obras.arquivo_hash barra reprocessar o mesmo conteudo; obter_obra_por_hash
evita a excecao antes de inserir. Md5 diferente = nova obra (versao).

Degradacao (R8): qualquer erro de rede/credencial/cota e' logado e reagendado; nunca
sobe ao Uvicorn. O estado 'drive_indisponivel' fica em portal_drive_sync_state.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..db import connection as db_conn
from ..db import repository as repo
from .config import Settings

log = logging.getLogger("portal.drive_poller")

_EXT_VALIDAS = (".dwg", ".dxf")


@dataclass
class DriveFile:
    """Descritor minimo de um arquivo no Drive (ou no fake local)."""

    file_id: str
    name: str
    md5: Optional[str] = None
    modified_time: Optional[str] = None
    size_bytes: Optional[int] = None


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #

class DriveClient(ABC):
    """Contrato do poller. Implementacoes: GoogleDriveClient, FakeDriveClient."""

    @abstractmethod
    def list_new_files(self, pasta_id: str) -> list[DriveFile]:
        """Lista arquivos (nao-lixeira) da pasta. Filtragem de extensao/dedup fica no poller."""

    @abstractmethod
    def download_file(self, file_id: str, dest: Path) -> Path:
        """Baixa o conteudo do arquivo para `dest`. Retorna o path escrito."""


# --------------------------------------------------------------------------- #
# Implementacao real (Google Drive)
# --------------------------------------------------------------------------- #

class GoogleDriveClient(DriveClient):
    """Cliente real via service account (drive.readonly).

    Para plugar as credenciais depois: aponte Settings.drive_sa_json para o JSON da
    service account e compartilhe cada pasta pessoal do Drive com o e-mail dela como
    leitor (HANDOFF §2.1). Sem o JSON, o construtor levanta erro claro — o portal
    escolhe o FakeDriveClient enquanto nao houver credencial (ver montar_drive_client).
    """

    _SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    def __init__(self, sa_json_path: Path):
        self._sa_json_path = Path(sa_json_path)
        if not self._sa_json_path.exists():
            raise FileNotFoundError(
                f"credencial da service account nao encontrada: {self._sa_json_path}. "
                "Coloque o JSON da service account ai (drive.readonly) e compartilhe "
                "as pastas do Drive com o e-mail dela, ou use FakeDriveClient em dev."
            )
        try:
            from google.oauth2 import service_account  # type: ignore
            from googleapiclient.discovery import build  # type: ignore
        except ImportError as exc:  # pragma: no cover - depende de lib externa
            raise NotImplementedError(
                "google-api-python-client/google-auth nao instalados. "
                "Instale-os para usar o Drive real, ou use FakeDriveClient em dev."
            ) from exc
        creds = service_account.Credentials.from_service_account_file(
            str(self._sa_json_path), scopes=self._SCOPES
        )
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_new_files(self, pasta_id: str) -> list[DriveFile]:  # pragma: no cover - I/O externo
        q = f"'{pasta_id}' in parents and trashed=false"
        resp = (
            self._service.files()
            .list(q=q, fields="files(id,name,md5Checksum,modifiedTime,size)")
            .execute()
        )
        out: list[DriveFile] = []
        for f in resp.get("files", []):
            size = f.get("size")
            out.append(
                DriveFile(
                    file_id=f["id"],
                    name=f.get("name", ""),
                    md5=f.get("md5Checksum"),
                    modified_time=f.get("modifiedTime"),
                    size_bytes=int(size) if size is not None else None,
                )
            )
        return out

    def download_file(self, file_id: str, dest: Path) -> Path:  # pragma: no cover - I/O externo
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore

        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = self._service.files().get_media(fileId=file_id)
        with open(dest, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _status, done = downloader.next_chunk()
        return dest


# --------------------------------------------------------------------------- #
# Implementacao fake (pasta local) — dev/teste
# --------------------------------------------------------------------------- #

class FakeDriveClient(DriveClient):
    """Simula o Drive lendo de um diretorio local. `pasta_id` = subpasta em `raiz`.

    file_id = caminho relativo (estavel); md5 = hash do conteudo. Perfeito para os
    testes do poller sem tocar rede nem credencial.
    """

    def __init__(self, raiz: str | Path):
        self.raiz = Path(raiz)

    def _pasta(self, pasta_id: str) -> Path:
        return self.raiz / pasta_id

    def list_new_files(self, pasta_id: str) -> list[DriveFile]:
        pasta = self._pasta(pasta_id)
        if not pasta.exists():
            return []
        out: list[DriveFile] = []
        for p in sorted(pasta.iterdir()):
            if not p.is_file():
                continue
            out.append(
                DriveFile(
                    file_id=str(p.relative_to(self.raiz)).replace("\\", "/"),
                    name=p.name,
                    md5=_md5_arquivo(p),
                    modified_time=None,
                    size_bytes=p.stat().st_size,
                )
            )
        return out

    def download_file(self, file_id: str, dest: Path) -> Path:
        src = self.raiz / file_id
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return dest


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _md5_arquivo(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_slug(nome: str) -> str:
    """Nome de arquivo (sem extensao) -> slug seguro de pasta de obra."""
    base = Path(nome).stem
    slug = "".join(c if (c.isalnum() or c in "-_") else "_" for c in base).strip("_")
    return slug or "obra"


def montar_drive_client(settings: Settings) -> DriveClient:
    """Escolhe a implementacao: real se a credencial existir, senao FakeDriveClient.

    Reason: o portal sobe em dev/CI sem credencial de Drive; nesse caso o poller opera
    sobre uma pasta local (settings.dados_obras_dir / '_drive_fake'), sem quebrar.
    """
    if settings.drive_sa_json.exists():
        try:
            return GoogleDriveClient(settings.drive_sa_json)
        except (NotImplementedError, FileNotFoundError) as exc:
            log.warning("Drive real indisponivel (%s) — caindo para FakeDriveClient", exc)
    fake_raiz = settings.dados_obras_dir / "_drive_fake"
    fake_raiz.mkdir(parents=True, exist_ok=True)
    return FakeDriveClient(fake_raiz)


# --------------------------------------------------------------------------- #
# Uma varredura (sincrona) — testavel isoladamente
# --------------------------------------------------------------------------- #

def varrer_uma_vez(
    conn,
    client: DriveClient,
    settings: Settings,
    *,
    membros: Optional[list[dict]] = None,
) -> list[str]:
    """Varre todas as pastas de membros com drive_folder_id. Retorna ids de obras novas.

    Idempotente (dedup por md5). Degrada por membro (R8): erro em um nao para os outros.
    """
    if membros is None:
        membros = repo.listar_membros(conn, apenas_ativos=True)
    obras_novas: list[str] = []
    limite_bytes = settings.max_obra_mb * 1024 * 1024

    for membro in membros:
        pasta_id = membro.get("drive_folder_id")
        if not pasta_id:
            continue
        try:
            arquivos = client.list_new_files(pasta_id)
        except Exception as exc:  # noqa: BLE001 - degradar sem derrubar (R8)
            log.warning("poller degradado para membro %s: %s", membro.get("login"), exc)
            repo.registrar_sync_state(
                conn, membro_id=membro["id"], pasta_drive_id=pasta_id,
                ultimo_scan_status="drive_indisponivel",
            )
            continue

        ultimo: Optional[DriveFile] = None
        for arq in arquivos:
            ultimo = arq
            if Path(arq.name).suffix.lower() not in _EXT_VALIDAS:
                continue
            if arq.size_bytes is not None and arq.size_bytes > limite_bytes:
                log.warning("arquivo %s excede %d MB — ignorado (R6)", arq.name, settings.max_obra_mb)
                continue
            md5 = arq.md5
            if md5 and repo.obter_obra_por_hash(conn, md5) is not None:
                continue  # ja visto (dedup)

            slug = _safe_slug(arq.name)
            dest = settings.dados_obras_dir / membro["login"] / slug / "entrada" / arq.name
            try:
                client.download_file(arq.file_id, dest)
                if md5 is None:
                    md5 = _md5_arquivo(dest)
                    if repo.obter_obra_por_hash(conn, md5) is not None:
                        continue
                obra_id = repo.criar_obra(
                    conn, membro_id=membro["id"], nome=slug,
                    pasta_drive_id=pasta_id, arquivo_drive_id=arq.file_id,
                    arquivo_nome=arq.name, arquivo_hash=md5,
                    estado="aguardando_ingestao",
                    local_path=str(dest.parent.parent),  # .../<slug>/
                )
                obras_novas.append(obra_id)
                log.info("obra nova detectada: %s (membro=%s)", slug, membro["login"])
            except Exception as exc:  # noqa: BLE001 - falha de download nao para a fila
                log.warning("falha ao baixar %s: %s", arq.name, exc)

        repo.registrar_sync_state(
            conn, membro_id=membro["id"], pasta_drive_id=pasta_id,
            ultimo_arquivo_id=ultimo.file_id if ultimo else None,
            ultimo_arquivo_hash=ultimo.md5 if ultimo else None,
            ultimo_modified_time=ultimo.modified_time if ultimo else None,
            ultimo_scan_status="ok",
        )
    return obras_novas


# --------------------------------------------------------------------------- #
# Loop asyncio (background task no lifespan)
# --------------------------------------------------------------------------- #

def _varrer_ciclo(settings: Settings, client: "DriveClient") -> list[str]:
    """Abre e fecha a PROPRIA conexao dentro da mesma thread do `asyncio.to_thread`.

    [FIX 2026-07-05] a versao anterior recebia `app_state.db` (conexao aberta na
    thread do lifespan) e repassava para dentro de `asyncio.to_thread`, que roda
    em uma thread do executor — mesma classe de bug do `request.app.state.db` nos
    routers (`sqlite3.ProgrammingError` cross-thread, confirmado rodando o
    servidor de verdade). Abrindo a conexao aqui, dentro da funcao que de fato
    roda na thread do executor, o objeto nunca atravessa fronteira de thread.
    """
    conn = db_conn.get_connection(settings.db_path)
    try:
        return varrer_uma_vez(conn, client, settings)
    finally:
        conn.close()


async def poller_loop(app_state) -> None:
    """Task de fundo: varre a cada poll_interval_s, com backoff em falha persistente.

    `app_state` = FastAPI app.state (tem .settings, .drive_client, .estado_global).
    Roda ate cancelamento (shutdown do lifespan).
    """
    settings: Settings = app_state.settings
    intervalo = settings.poll_interval_s
    backoff = intervalo
    while True:
        try:
            novas = await asyncio.to_thread(_varrer_ciclo, settings, app_state.drive_client)
            app_state.estado_global["drive"] = "ok"
            if novas:
                log.info("poller: %d obra(s) nova(s)", len(novas))
            backoff = intervalo  # sucesso reseta o backoff
            await asyncio.sleep(intervalo)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - nunca derruba o Uvicorn (R8)
            app_state.estado_global["drive"] = "degradado"
            log.warning("poller_loop degradado: %s (backoff %ds)", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 1800)  # teto 30min
