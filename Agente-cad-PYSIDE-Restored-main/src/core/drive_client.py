"""Cliente HTTP da app desktop pro portal web (Masterplan OBRAS DRIVE, Fase 1).

O portal (`portal/`) roda como servidor FastAPI separado (porto default 21380,
`portal/app/config.py`), com autenticacao por cookie de sessao (login+senha,
igual o navegador). Este cliente reusa `requests.Session()` pra manter o
cookie entre chamadas — login e' feito 1 vez (lazy, na primeira chamada) e
reaproveitado pelo resto da sessao da app.

Escopo desta Fase 1: so' o necessario pra listar obras/documentos/recortes do
portal e baixar sob demanda o .dxf de UM recorte especifico (nunca a obra
inteira) — usado por `diagnostic_hub.py` quando um item de obra Drive ainda
nao existe no espelho local.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# Não depende do CWD do processo (main.py pode ser lançado de qualquer lugar) —
# ancora sempre no .env da raiz do projeto desktop: src/core/ -> src/ -> raiz.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


class DriveClienteError(RuntimeError):
    """Erro de comunicacao com o portal (rede, auth, 404, etc)."""


class DriveClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        login: Optional[str] = None,
        senha: Optional[str] = None,
        timeout_s: float = 30.0,
    ):
        self.base_url = (base_url or os.environ.get("PORTAL_BASE_URL") or "http://127.0.0.1:21380").rstrip("/")
        self._login = login or os.environ.get("PORTAL_LOGIN")
        self._senha = senha or os.environ.get("PORTAL_SENHA")
        self._timeout_s = timeout_s
        self._sessao = requests.Session()
        self._autenticado = False
        self.ultimo_last_modified: Optional[str] = None

    def _garantir_login(self) -> None:
        if self._autenticado:
            return
        if not self._login or not self._senha:
            raise DriveClienteError(
                "Credenciais do portal nao configuradas — defina PORTAL_LOGIN e "
                "PORTAL_SENHA (env) ou passe login/senha ao criar DriveClient."
            )
        resp = self._sessao.post(
            f"{self.base_url}/login",
            json={"login": self._login, "senha": self._senha},
            timeout=self._timeout_s,
        )
        if not resp.ok:
            raise DriveClienteError(f"login no portal falhou: HTTP {resp.status_code}")
        corpo = resp.json()
        if not corpo.get("ok"):
            raise DriveClienteError(f"login no portal recusado: {corpo}")
        self._autenticado = True

    def _get(self, path: str) -> dict:
        self._garantir_login()
        resp = self._sessao.get(f"{self.base_url}{path}", timeout=self._timeout_s)
        if resp.status_code == 401:
            # sessao pode ter expirado (TTL) — tenta logar de novo 1x
            self._autenticado = False
            self._garantir_login()
            resp = self._sessao.get(f"{self.base_url}{path}", timeout=self._timeout_s)
        if not resp.ok:
            raise DriveClienteError(f"GET {path} falhou: HTTP {resp.status_code} — {resp.text[:200]}")
        return resp.json()

    def listar_obras(self) -> list[dict]:
        """Todas as obras visiveis pro membro logado (todas, se papel=dono)."""
        return self._get("/obras").get("obras", [])

    def obter_obra(self, obra_id: str) -> dict:
        """Detalhe completo — inclui `documentos` (Triagem: pavimento/tipo/classe)."""
        return self._get(f"/obras/{obra_id}")

    def listar_brutos(self, obra_id: str) -> list[dict]:
        return self._get(f"/obras/{obra_id}/recortes/brutos").get("brutos", [])

    def listar_itens(self, obra_id: str, bruto_id: str) -> list[dict]:
        return self._get(f"/obras/{obra_id}/recortes/brutos/{bruto_id}/itens").get("itens", [])

    def obter_validacao_sa(self, obra_id: str, bruto_id: str) -> dict:
        """Estado de validação "item completo" do SA pra 1 pavimento (Fase 2)."""
        return self._get(f"/obras/{obra_id}/sa/{bruto_id}")

    def listar_validacoes_sa(self, obra_id: str) -> dict:
        """{bruto_id: validado} de todos os pavimentos já tocados dessa obra."""
        return self._get(f"/obras/{obra_id}/sa").get("validacoes", {})

    def obter_validacao_classe(self, obra_id: str, classe: str) -> dict:
        """Estado de validação N1+N3 (etapa 5) pra 1 classe estrutural
        (PIL/LV/FV/LJ) — Masterplan OBRAS DRIVE Fase 3."""
        return self._get(f"/obras/{obra_id}/validacao/{classe}")

    def listar_itens_n1(self, obra_id: str, classe: str, pavimento: str) -> list[dict]:
        """[{item_id, titulo, validado}] de 1 classe N1 (pilares/lajes/etc)
        num pavimento — usado pra sincronizar o selo verde (validação simples
        do item no N1 da web) no SA da app, sem depender do selo azul local
        (completude de campos), Masterplan OBRAS DRIVE Fase 12."""
        path = f"/obras/{obra_id}/n1/{classe}"
        if pavimento:
            from urllib.parse import quote
            path += f"?pavimento={quote(pavimento)}"
        return self._get(path).get("itens", [])

    def listar_validacoes_classe(self, obra_id: str) -> dict:
        """{classe: {n1_ok, n3_ok, validado}} de todas as classes já tocadas."""
        return self._get(f"/obras/{obra_id}/validacao").get("validacoes", {})

    def listar_n5_releases(self, obra_id: str) -> list:
        """Liberações N5 já feitas no portal (classe/pavimento/status de
        certificação certificado|beta) — SOMENTE LEITURA no lado app: liberar
        N5 é uma ação self-service do portal (monta/audita arquivo no
        servidor), não algo pra empurrar da app."""
        return self._get(f"/obras/{obra_id}").get("n5_releases", [])

    def baixar_recorte(self, obra_id: str, bruto_id: str, item_id: str, destino: Path) -> Path:
        """Baixa o .dxf REAL de 1 recorte (torre_1, detalhes, etc) pro `destino`
        informado — nunca a obra inteira."""
        url = self.url_recorte(obra_id, bruto_id, item_id)
        return self._baixar_arquivo(url, destino, contexto=f"{obra_id}/{bruto_id}/{item_id}")

    def baixar_documento(self, obra_id: str, doc_id: str, destino: Path) -> Path:
        """Baixa o arquivo REAL de 1 documento bruto/PDF/etc (não-recorte) pro
        `destino` informado."""
        url = self.url_documento(obra_id, doc_id)
        return self._baixar_arquivo(url, destino, contexto=f"{obra_id}/documentos/{doc_id}")

    def url_recorte(self, obra_id: str, bruto_id: str, item_id: str) -> str:
        return f"{self.base_url}/obras/{obra_id}/recortes/brutos/{bruto_id}/{item_id}/arquivo"

    def url_documento(self, obra_id: str, doc_id: str) -> str:
        return f"{self.base_url}/obras/{obra_id}/documentos/{doc_id}/arquivo"

    def obter_last_modified(self, url: str) -> Optional[str]:
        """HEAD leve (sem baixar o corpo) só pra comparar versão remota —
        Masterplan OBRAS DRIVE Fase 13 (cache/expiração por versão, nunca por
        tempo). None se o servidor não informar `Last-Modified` (mantém a
        cópia local, não força re-download sem sinal confiável)."""
        try:
            self._garantir_login()
            resp = self._sessao.head(url, timeout=self._timeout_s)
            if resp.status_code == 401:
                self._autenticado = False
                self._garantir_login()
                resp = self._sessao.head(url, timeout=self._timeout_s)
            if not resp.ok:
                return None
            return resp.headers.get("Last-Modified")
        except Exception:
            return None

    def _baixar_arquivo(self, url: str, destino: Path, contexto: str) -> Path:
        """Cria a pasta pai se precisar. Idempotente: se `destino` ja existir,
        sobrescreve (sempre pega a versao mais recente do portal). Guarda o
        `Last-Modified` da resposta em `self.ultimo_last_modified` pro
        chamador persistir como versão conhecida (Fase 13)."""
        self._garantir_login()
        resp = self._sessao.get(url, timeout=self._timeout_s, stream=True)
        if resp.status_code == 401:
            self._autenticado = False
            self._garantir_login()
            resp = self._sessao.get(url, timeout=self._timeout_s, stream=True)
        if not resp.ok:
            raise DriveClienteError(f"download falhou: HTTP {resp.status_code} ({contexto})")
        self.ultimo_last_modified = resp.headers.get("Last-Modified")
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(destino.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
        tmp.replace(destino)
        return destino


_cliente_padrao: Optional["DriveClient"] = None


def obter_cliente_padrao(login: Optional[str] = None, senha: Optional[str] = None) -> "DriveClient":
    """Singleton do processo — todo mundo que fala com o portal (o dialog de
    Obras Drive no Gerenciar Projetos e o download sob demanda no Diagnostic
    Hub) reusa a MESMA sessão/cookie, pra logar só 1x por sessão da app.
    `login`/`senha` só importam na primeira chamada (ou após `resetar_cliente_padrao`)."""
    global _cliente_padrao
    if _cliente_padrao is None:
        _cliente_padrao = DriveClient(login=login, senha=senha)
    return _cliente_padrao


def resetar_cliente_padrao() -> None:
    """Descarta o singleton (ex: usuário trocou de conta/senha errada)."""
    global _cliente_padrao
    _cliente_padrao = None
