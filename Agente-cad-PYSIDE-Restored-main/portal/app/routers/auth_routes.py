"""Rotas de autenticacao: POST /login, POST /logout, GET /me (HANDOFF §1.1/§4)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from .. import auth
from ..dbdep import get_db_conn

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    login: str
    senha: str


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
    cookie = auth.emitir_cookie(settings, membro["login"])
    response.set_cookie(
        key=settings.session_cookie_name,
        value=cookie,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_horas * 3600,
    )
    return {"ok": True, "membro": {
        "login": membro["login"], "nome": membro["nome"], "papel": membro["papel"],
    }}


@router.post("/logout")
def logout(request: Request, response: Response):
    settings = request.app.state.settings
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}


@router.get("/me", response_model=MembroOut)
def me(membro: dict = Depends(auth.exige_login)):
    return MembroOut(login=membro["login"], nome=membro["nome"], papel=membro["papel"])
