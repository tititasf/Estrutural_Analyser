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
from typing import Any, Optional

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
    """Contrato do poller. Implementacoes: GoogleDriveClient, GoogleDriveOAuthClient,
    FakeDriveClient."""

    @abstractmethod
    def list_new_files(self, pasta_id: str) -> list[DriveFile]:
        """Lista arquivos (nao-lixeira) da pasta. Filtragem de extensao/dedup fica no poller."""

    @abstractmethod
    def download_file(self, file_id: str, dest: Path) -> Path:
        """Baixa o conteudo do arquivo para `dest`. Retorna o path escrito."""

    @abstractmethod
    def enviar_arquivo(self, pasta_id: str, origem_local: Path, nome_remoto: str) -> str:
        """[2026-07-06] Upload direto pelo portal — usuario nunca abre o Drive.

        `origem_local` ja' esta' em disco (o endpoint grava o upload ali por stream,
        nunca carrega o arquivo inteiro em memoria — CAD pode ter centenas de MB).
        Retorna o file_id remoto."""

    @abstractmethod
    def obter_ou_criar_pasta(self, nome: str, pasta_pai_id: Optional[str] = None) -> str:
        """Acha (por nome, sob `pasta_pai_id`) ou cria a pasta. Retorna o id.

        Idempotente: chamar 2x com o mesmo (nome, pai) devolve o MESMO id — nunca
        cria duplicata. `pasta_pai_id=None` procura/cria na raiz do Drive da conta
        (2026-07-06 — criacao dinamica de pasta por membro, ver seed.py)."""


# --------------------------------------------------------------------------- #
# Implementacao real — base comum (monta o `service` googleapiclient)
# --------------------------------------------------------------------------- #

class _GoogleDriveServiceMixin:
    """Metodos de list/download comuns as duas variantes de credencial real.

    A diferenca entre `GoogleDriveClient` (service account) e
    `GoogleDriveOAuthClient` (OAuth de usuario) esta so em COMO `self._service`
    e' construido (`_build_service`); a chamada de API e' identica.
    """

    _service: Any

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

    def enviar_arquivo(
        self, pasta_id: str, origem_local: Path, nome_remoto: str
    ) -> str:  # pragma: no cover - I/O externo
        from googleapiclient.http import MediaFileUpload  # type: ignore

        media = MediaFileUpload(str(origem_local), resumable=True)
        corpo = {"name": nome_remoto, "parents": [pasta_id]}
        criado = self._service.files().create(body=corpo, media_body=media, fields="id").execute()
        return criado["id"]

    def obter_ou_criar_pasta(
        self, nome: str, pasta_pai_id: Optional[str] = None
    ) -> str:  # pragma: no cover - I/O externo
        """Busca por nome+pai (idempotente); cria só se não achar.

        [2026-07-06] Base da criação dinâmica de pasta por membro (§ seed.py):
        1 pasta-mãe "Portal-Obras" na raiz do Drive do dono + 1 subpasta por
        membro. `nome` nunca é interpolado cru na query — aspas simples são
        escapadas (Drive API usa sintaxe de query própria, não SQL, mas o
        mesmo cuidado de escaping se aplica).
        """
        pai = pasta_pai_id or "root"
        nome_escapado = nome.replace("'", "\\'")
        q = (
            f"name = '{nome_escapado}' and '{pai}' in parents and "
            "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        resp = self._service.files().list(q=q, fields="files(id,name)").execute()
        achadas = resp.get("files", [])
        if achadas:
            return achadas[0]["id"]

        corpo = {
            "name": nome,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [pai],
        }
        criada = self._service.files().create(body=corpo, fields="id").execute()
        return criada["id"]


class GoogleDriveClient(_GoogleDriveServiceMixin, DriveClient):
    """Cliente real via service account (drive.readonly) — caminho alternativo futuro.

    Para plugar: aponte Settings.drive_sa_json para o JSON da service account e
    compartilhe cada pasta pessoal do Drive com o e-mail dela como leitor
    (HANDOFF §2.1). NAO e' o caminho usado hoje — ver GoogleDriveOAuthClient e a
    decisao do dono em montar_drive_client().
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


class GoogleDriveOAuthClient(_GoogleDriveServiceMixin, DriveClient):
    """Cliente real via credencial OAuth de USUARIO (nao service account).

    [FIX 2026-07-06] O repo so tinha credencial OAuth (a mesma que o DVC usa pro
    remote 'gdrive' — client_id/client_secret proprios + refresh_token ja
    autorizado, escopo 'drive'+'drive.appdata'). Decisao do dono: reusar essa
    credencial em vez de criar service account nova (mais rapido). Diferenca de
    modelo: aqui o portal enxerga o Drive COMO o dono (nao ha "compartilhar
    pasta com robo") — os `drive_folder_id` de cada membro devem ser subpastas
    dentro do proprio Drive do dono (ex.: uma pasta-mae "Portal-Obras" com uma
    subpasta por membro), nao pastas pessoais de terceiros.

    Formato esperado do JSON (`Settings.drive_oauth_json`) — minimo necessario
    para reconstruir `google.oauth2.credentials.Credentials`:
        {"client_id": "...", "client_secret": "...", "refresh_token": "...",
         "token_uri": "https://oauth2.googleapis.com/token",
         "scopes": ["https://www.googleapis.com/auth/drive"]}
    O refresh e' automatico (google-auth troca o refresh_token por access_token
    novo a cada chamada quando o cache expira) — nunca commitar este arquivo
    (portal/.gitignore ja cobre `portal/.secrets/`).
    """

    def __init__(self, oauth_json_path: Path):
        self._oauth_json_path = Path(oauth_json_path)
        if not self._oauth_json_path.exists():
            raise FileNotFoundError(
                f"credencial OAuth do Drive nao encontrada: {self._oauth_json_path}. "
                "Copie os campos client_id/client_secret/refresh_token/token_uri/"
                "scopes para esse arquivo (ex.: a partir da credencial do DVC), ou "
                "use FakeDriveClient em dev."
            )
        try:
            from google.oauth2.credentials import Credentials  # type: ignore
            from googleapiclient.discovery import build  # type: ignore
        except ImportError as exc:  # pragma: no cover - depende de lib externa
            raise NotImplementedError(
                "google-api-python-client/google-auth nao instalados. "
                "Instale-os para usar o Drive real, ou use FakeDriveClient em dev."
            ) from exc

        import json

        dados = json.loads(self._oauth_json_path.read_text(encoding="utf-8"))
        campos_obrigatorios = ("client_id", "client_secret", "refresh_token", "token_uri")
        faltando = [c for c in campos_obrigatorios if not dados.get(c)]
        if faltando:
            raise ValueError(
                f"credencial OAuth incompleta em {self._oauth_json_path}: "
                f"faltam os campos {faltando}."
            )
        creds = Credentials(
            token=dados.get("access_token"),
            refresh_token=dados["refresh_token"],
            token_uri=dados["token_uri"],
            client_id=dados["client_id"],
            client_secret=dados["client_secret"],
            scopes=dados.get("scopes") or ["https://www.googleapis.com/auth/drive"],
        )
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)


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

    def obter_ou_criar_pasta(self, nome: str, pasta_pai_id: Optional[str] = None) -> str:
        """Paridade com o real: `pasta_id` aqui e' so' o path relativo a `raiz`."""
        base = self._pasta(pasta_pai_id) if pasta_pai_id else self.raiz
        alvo = base / nome
        alvo.mkdir(parents=True, exist_ok=True)
        return str(alvo.relative_to(self.raiz)).replace("\\", "/")

    def enviar_arquivo(self, pasta_id: str, origem_local: Path, nome_remoto: str) -> str:
        pasta = self._pasta(pasta_id)
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / nome_remoto
        shutil.copyfile(origem_local, destino)
        return str(destino.relative_to(self.raiz)).replace("\\", "/")


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
    """Escolhe a implementacao: OAuth > service account > FakeDriveClient.

    [FIX 2026-07-06] OAuth (drive_oauth_json) e' o caminho preferido — e' a
    credencial que o dono ja tem (reusada do DVC). Service account
    (drive_sa_json) fica como alternativa futura, se um dia for criada.
    Reason do fallback: o portal sobe em dev/CI sem nenhuma credencial de
    Drive; nesse caso o poller opera sobre uma pasta local
    (settings.dados_obras_dir / '_drive_fake'), sem quebrar.
    """
    if settings.drive_oauth_json.exists():
        try:
            return GoogleDriveOAuthClient(settings.drive_oauth_json)
        except (NotImplementedError, FileNotFoundError, ValueError) as exc:
            log.warning("Drive OAuth indisponivel (%s) — tentando service account", exc)
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
                # [FIX] achado comparando com o histórico recuperado: uma
                # tentativa (incompleta) de implementar "modo rápido vira
                # Pavimento único" tinha reescrito isto pra criar a obra SEM
                # arquivo_nome + 1 portal_documentos, mas movia o arquivo pra
                # <obra>/docs/<doc_id>/ em vez de <obra>/entrada/ (a
                # convenção real usada por TODO o resto do pipeline —
                # _entrada_dxf/_arquivo_entrada só acham o DXF em entrada/).
                # Isso quebrava recortes/SA de verdade pra obras vindas do
                # Drive, além de quebrar 4 testes que validam este contrato.
                # Revertido pro modelo legado estável (1 obra = 1 arquivo,
                # arquivo_nome setado); "Pavimento único" fica pendente,
                # implementado depois com cuidado.
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
