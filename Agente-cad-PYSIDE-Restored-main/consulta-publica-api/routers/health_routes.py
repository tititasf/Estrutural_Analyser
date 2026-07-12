"""Endpoint de health check (STORY-02, AC 2) — único endpoint desta story;
endpoints de negócio (/resolve, /ficha, /svg, /obra, /paineis-lv) são stories
separadas (03, 05, 06, 07, 12)."""

from __future__ import annotations

from fastapi import APIRouter, Response

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def health(response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ok"}
