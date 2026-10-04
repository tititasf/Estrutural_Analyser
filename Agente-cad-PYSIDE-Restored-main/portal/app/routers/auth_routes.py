"""Rotas de autenticacao: POST /login, POST /logout, GET /me (HANDOFF §1.1/§4)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from ...db import repository as repo
from .. import auth
from ..dbdep import get_db_conn

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    login: str
    senha: str
    manter_conectado: bool = False


class MembroOut(BaseModel):
    login: str
    nome: str
    papel: str


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response,
          conn: sqlite3.Connection = Depends(get_db_conn)):
    settings = request.app.state.settings
    membro = auth.autenticar(conn, body.login, body.senha)
    if membro is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="login ou senha invalidos"
        )
    cookie = auth.emitir_cookie(
        settings, membro["login"], persistente=body.manter_conectado,
    )
    cookie_args = dict(
        key=settings.session_cookie_name,
        value=cookie,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    if body.manter_conectado:
        # Dez anos funciona como "ate Sair" nos navegadores sem introduzir
        # estado de sessao novo no banco congelado do portal.
        cookie_args["max_age"] = 10 * 365 * 24 * 3600
    response.set_cookie(**cookie_args)
    return {"ok": True, "membro": {
        "login": membro["login"], "nome": membro["nome"], "papel": membro["papel"],
    }, "trocar_senha": int(membro.get("trocar_senha") or 0) == 1}


@router.post("/logout")
def logout(request: Request, response: Response):
    settings = request.app.state.settings
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}


SENHA_MIN = 6


class TrocarSenhaIn(BaseModel):
    senha_atual: str = ""
    nova_senha: str
    confirmacao: str


@router.post("/trocar-senha")
def trocar_senha(body: TrocarSenhaIn, membro: dict = Depends(auth.exige_login),
                 conn: sqlite3.Connection = Depends(get_db_conn)):
    """Troca a senha do próprio membro. Regra única: 6 caracteres ou mais.

    No primeiro acesso (trocar_senha=1) o membro acabou de entrar com a senha
    padrão, então a atual não é pedida; na troca voluntária ela é conferida.
    """
    obrigatoria = int(membro.get("trocar_senha") or 0) == 1
    if not obrigatoria and not auth.verificar_senha(body.senha_atual, membro["senha_hash"]):
        raise HTTPException(status_code=400, detail="A senha atual não confere.")
    if len(body.nova_senha) < SENHA_MIN:
        raise HTTPException(status_code=400, detail=f"A nova senha precisa ter {SENHA_MIN} caracteres ou mais.")
    if body.nova_senha != body.confirmacao:
        raise HTTPException(status_code=400, detail="A confirmação não é igual à nova senha.")
    if auth.verificar_senha(body.nova_senha, membro["senha_hash"]):
        raise HTTPException(status_code=400, detail="A nova senha precisa ser diferente da atual.")
    repo.atualizar_senha_membro(conn, membro["id"], auth.hash_senha(body.nova_senha))
    return {"ok": True}


@router.get("/me", response_model=MembroOut)
def me(membro: dict = Depends(auth.exige_login)):
    return MembroOut(login=membro["login"], nome=membro["nome"], papel=membro["papel"])
