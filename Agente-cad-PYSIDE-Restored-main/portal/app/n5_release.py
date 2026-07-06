"""Liberacao self-service do N5 (DP-13/R9): assemble_n5 real + registro auditavel.

Gating (HANDOFF §1.2 / DP-13): so libera se a validacao do usuario (etapa 5) para a
classe estiver registrada. O rotulo certificado/beta e' um SNAPSHOT congelado no
momento da liberacao (repository.registrar_n5_release) — auditar depois "o que ele
sabia quando liberou" independe do estado atual da curadoria.

Este modulo NAO decide certificacao: le de certification.classificar_certificacao
(que le STATUS.md read-only). O portal so exibe.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from ..db import repository as repo
from . import certification, pipeline_runner
from .config import Settings

log = logging.getLogger("portal.n5_release")


def _hash_dxf(path: str | Path) -> Optional[str]:
    p = Path(path)
    if not p.exists():
        return None
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def liberar_n5(
    conn,
    settings: Settings,
    *,
    obra: dict,
    classe: str,
    pavimento: str,
    membro_id: str,
    job_id: Optional[str] = None,
    engine_version: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Monta o N5 da classe+pav e registra a liberacao com snapshot de certificacao.

    Retorna dict com o rotulo, o release_id e o path do DXF. Levanta ValueError se a
    classe for invalida (repository ja valida contra PL/LV/FV/LJ).
    """
    resultado = pipeline_runner.executar_n5(
        settings, obra, classe=classe, pavimento=pavimento, dry_run=dry_run
    )
    dxf_path = resultado.artefatos.get("n5_dxf") if not dry_run else None
    dxf_hash = _hash_dxf(dxf_path) if dxf_path else None

    # rotulo SNAPSHOT (R9) — lido da fonte do dono no momento exato da liberacao.
    status_cert = certification.classificar_certificacao(settings.status_md_path, classe)

    release_id = repo.registrar_n5_release(
        conn, obra_id=obra["id"], classe=classe, liberado_por=membro_id,
        status_certificacao=status_cert, pavimento=pavimento or "GERAL",
        engine_version=engine_version, job_id=job_id,
        dxf_path=dxf_path, dxf_hash=dxf_hash,
    )
    log.info("N5 liberado: obra=%s classe=%s status=%s por=%s",
             obra.get("nome"), classe, status_cert, membro_id)
    return {
        "release_id": release_id,
        "classe": classe,
        "pavimento": pavimento or "GERAL",
        "status_certificacao": status_cert,
        "dxf_path": dxf_path,
        "dxf_hash": dxf_hash,
        "ok": resultado.ok,
        "dry_run": dry_run,
    }
