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

    def baixar_recorte(self, obra_id: str, bruto_id: str, item_id: str, destino: Path) -> Path:
        """Baixa o .dxf REAL de 1 recorte (torre_1, detalhes, etc) pro `destino`
        informado — nunca a obra inteira. Cria a pasta pai se precisar.
        Idempotente: se `destino` ja existir com o mesmo conteudo, sobrescreve
        (sempre pega a versao mais recente do portal)."""
        self._garantir_login()
        url = f"{self.base_url}/obras/{obra_id}/recortes/brutos/{bruto_id}/{item_id}/arquivo"
        resp = self._sessao.get(url, timeout=self._timeout_s, stream=True)
        if resp.status_code == 401:
            self._autenticado = False
            self._garantir_login()
            resp = self._sessao.get(url, timeout=self._timeout_s, stream=True)
        if not resp.ok:
            raise DriveClienteError(
                f"download do recorte falhou: HTTP {resp.status_code} ({obra_id}/{bruto_id}/{item_id})"
            )
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(destino.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
        tmp.replace(destino)
        return destino
