"""Login por membro + sessao via cookie assinado (HANDOFF §4).

- Senha: hash bcrypt via `bcrypt` direto. Valida contra portal_membros.senha_hash.
- Sessao: cookie assinado com itsdangerous.URLSafeTimedSerializer (HttpOnly,
  SameSite=Lax, Secure quando houver TLS). Payload = {login}. TTL forcado na
  desserializacao (max_age).

[ASSUMPTION] O HANDOFF §4 sugeria uma tabela `sessoes` server-side para revogacao.
O schema real do portal_data.db (migration 001) NAO tem essa tabela e a instrucao
e' USAR a camada de dados existente, nao recria-la. Escolhi a interpretacao mais
simples: sessao STATELESS assinada com TTL — logout apaga o cookie no cliente. Sem
tabela nova, sem violar o schema congelado. Revogacao fina fica como refinamento
pos-P3 (o handoff ja lista "revogacao fina de sessao" como "pode vir depois").

[FIX 2026-07-05] `passlib.context.CryptContext(schemes=["bcrypt"])` foi trocado por
chamada direta ao pacote `bcrypt` — `passlib` 1.7.4 quebra a deteccao de versao do
backend com `bcrypt` >=4.1 (`AttributeError: module 'bcrypt' has no attribute
'__about__'`), o que faz o self-test interno do passlib falhar com
`ValueError: password cannot be longer than 72 bytes` mesmo para senhas curtas.
`bcrypt` puro nao tem esse bug (validado rodando de verdade). `passlib` fica
sem uso neste modulo.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..db import repository as repo
from .config import Settings
from .dbdep import get_db_conn

# salt namespaceado para o cookie de sessao do portal
_SALT = "portal-sessao-v1"


def hash_senha(senha_plana: str) -> str:
    """Gera hash bcrypt (usado pelo seed/admin ao cadastrar membro)."""
    return bcrypt.hashpw(senha_plana.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha_plana.encode("utf-8"), senha_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt=_SALT)


def emitir_cookie(settings: Settings, login: str) -> str:
    """Cria o valor assinado do cookie de sessao para `login`."""
    return _serializer(settings).dumps({"login": login})


def ler_cookie(settings: Settings, valor: str) -> Optional[str]:
    """Valida o cookie; devolve o login ou None (assinatura ruim / expirado)."""
    if not valor:
        return None
    max_age = settings.session_ttl_horas * 3600
    try:
        dados = _serializer(settings).loads(valor, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(dados, dict):
        return None
    login = dados.get("login")
    return login if isinstance(login, str) else None


def autenticar(conn: sqlite3.Connection, login: str, senha: str) -> Optional[dict]:
    """Valida login+senha contra portal_membros. Retorna o membro (dict) ou None.

    Membro inativo (ativo=0) e' recusado como se nao existisse.
    """
    membro = repo.obter_membro_por_login(conn, login)
    if membro is None:
        return None
    if int(membro.get("ativo", 1)) != 1:
        return None
    if not verificar_senha(senha, membro.get("senha_hash", "")):
        return None
    return membro


# --------------------------------------------------------------------------- #
# Dependencia FastAPI: exige_login (§4 middleware)
# --------------------------------------------------------------------------- #

def exige_login(
    request: Request, conn: sqlite3.Connection = Depends(get_db_conn)
) -> dict:
    """Depends(...) que valida o cookie e injeta o membro atual.

    Le settings do app.state e usa uma conexao propria da request (Depends).
    Sem sessao valida -> 401. As rotas /login e estaticos NAO usam esta dependencia.
    """
    settings: Settings = request.app.state.settings
    valor = request.cookies.get(settings.session_cookie_name, "")
    login = ler_cookie(settings, valor)
    if login is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="sessao invalida ou expirada",
        )
    membro = repo.obter_membro_por_login(conn, login)
    if membro is None or int(membro.get("ativo", 1)) != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="membro nao encontrado ou inativo",
        )
    return membro


# alias legivel para anotacoes de rota
MembroAtual = Depends(exige_login)
