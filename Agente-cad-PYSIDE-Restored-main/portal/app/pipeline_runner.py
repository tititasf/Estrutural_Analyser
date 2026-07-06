"""Acionamento do pipeline: subprocess do headless + import do assemble_n5 (HANDOFF §1.2).

O portal NUNCA importa PySide6 nem o motor SA. As etapas 2-4 rodam por SUBPROCESS do
CLI existente `scripts.arete.headless_sa_analise` (Qt offscreen isolado num processo
filho — se estourar RAM/travar, nao derruba o web server). A etapa 6 (N5) importa
`src.core.n5_assembler.assemble_n5` diretamente (leve, so ezdxf).

`dry_run=True` (default nos testes) NAO dispara subprocess — retorna o comando que
seria executado. O codigo de producao chama de verdade (dry_run=False).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import Settings

log = logging.getLogger("portal.pipeline_runner")

# Etapas que o portal aciona (HANDOFF §1.2). 'validacao' nao passa por aqui (so DB).
ETAPAS_SUBPROCESS = ("triagem", "recortes", "sa")
ETAPAS_TODAS = ("triagem", "recortes", "sa", "n5")


@dataclass
class ResultadoEtapa:
    etapa: str
    ok: bool
    comando: list[str] = field(default_factory=list)
    returncode: Optional[int] = None
    log_tail: str = ""
    artefatos: dict = field(default_factory=dict)
    dry_run: bool = False


def engine_version(repo_root: Path) -> str:
    """git rev-parse --short HEAD -> 'git-<sha>' (P5 reprodutibilidade). Fail-safe: 'git-unknown'."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return f"git-{out.stdout.strip()}"
    except (OSError, subprocess.SubprocessError):
        pass
    return "git-unknown"


def _obra_dir(settings: Settings, obra: dict) -> Path:
    """Diretorio de trabalho da obra (onde o headless procura --obra).

    Usa local_path se o poller o gravou; senao cai no layout DADOS-OBRAS/<nome>.
    """
    lp = obra.get("local_path")
    if lp:
        return Path(lp)
    return settings.dados_obras_dir / obra.get("nome", "obra")


def montar_comando_headless(
    settings: Settings,
    obra: dict,
    *,
    secao: Optional[list[str]] = None,
    pav: Optional[str] = None,
) -> list[str]:
    """Comando do headless para as etapas de recortes/sa (HANDOFF §1.2).

    Sempre usa --wait (automacao): serializa contra QUALQUER headless da maquina via
    o single_instance lock, inclusive os disparados pela app PySide6 do dono (§3.1).
    """
    obra_dir = _obra_dir(settings, obra)
    cmd = [
        sys.executable, "-m", "scripts.arete.headless_sa_analise",
        "--obra", str(obra_dir),
        "--pav", pav or settings.pav_default,
        "--wait",
    ]
    for s in secao or []:
        cmd += ["--secao", s]
    return cmd


def _tail(texto: str, linhas: int = 40) -> str:
    return "\n".join((texto or "").splitlines()[-linhas:])


def executar_etapa(
    settings: Settings,
    etapa: str,
    obra: dict,
    *,
    secao: Optional[list[str]] = None,
    pav: Optional[str] = None,
    dry_run: bool = True,
    log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Executa uma etapa de pipeline (triagem/recortes/sa) via subprocess.

    N5 NAO passa por aqui — usa executar_n5(). validacao NAO passa por aqui — so DB.
    dry_run=True devolve o comando sem disparar (default seguro para testes).
    """
    if etapa not in ETAPAS_SUBPROCESS:
        raise ValueError(f"etapa {etapa!r} nao e' de subprocess (validas: {ETAPAS_SUBPROCESS})")

    # triagem e recortes usam o mesmo CLI (fases anteriores do pipeline); MVP dispara
    # o headless que ja encadeia as fases. --secao restringe classe quando informado.
    cmd = montar_comando_headless(settings, obra, secao=secao, pav=pav)

    if dry_run:
        return ResultadoEtapa(etapa=etapa, ok=True, comando=cmd, dry_run=True)

    try:
        proc = subprocess.run(
            cmd, cwd=str(settings.repo_root), capture_output=True, text=True,
            timeout=settings.subprocess_timeout_s,
        )
    except subprocess.TimeoutExpired:
        return ResultadoEtapa(etapa=etapa, ok=False, comando=cmd, returncode=None,
                              log_tail="timeout do subprocess")
    except OSError as exc:
        return ResultadoEtapa(etapa=etapa, ok=False, comando=cmd, returncode=None,
                              log_tail=f"erro ao iniciar subprocess: {exc}")

    saida = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(saida, encoding="utf-8", errors="replace")
        except OSError:
            pass

    obra_dir = _obra_dir(settings, obra)
    artefatos = {
        "obra_dir": str(obra_dir),
        "fase6_dir": str(obra_dir / "Fase-6_Execucao_CAD"),
    }
    return ResultadoEtapa(
        etapa=etapa, ok=(proc.returncode == 0), comando=cmd,
        returncode=proc.returncode, log_tail=_tail(saida), artefatos=artefatos,
    )


def executar_n5(
    settings: Settings,
    obra: dict,
    *,
    classe: str,
    pavimento: str = "GERAL",
    dry_run: bool = True,
) -> ResultadoEtapa:
    """Etapa 6: chama assemble_n5 (import direto, leve). Gera 1 DXF por classe+pav.

    dry_run=True nao importa nem escreve — so descreve a chamada.
    """
    obra_dir = _obra_dir(settings, obra)
    if dry_run:
        return ResultadoEtapa(
            etapa="n5", ok=True, dry_run=True,
            comando=["assemble_n5", str(obra_dir), classe, f"pavimento={pavimento}"],
        )
    try:
        from src.core.n5_assembler import assemble_n5  # import tardio: isola ezdxf
    except ImportError as exc:
        return ResultadoEtapa(etapa="n5", ok=False, log_tail=f"import assemble_n5 falhou: {exc}")

    try:
        resultado = assemble_n5(obra_dir, classe, pavimento=pavimento)
    except Exception as exc:  # noqa: BLE001 - erro do assembler vira estado de job 'error'
        return ResultadoEtapa(etapa="n5", ok=False,
                              comando=["assemble_n5", str(obra_dir), classe],
                              log_tail=f"assemble_n5 erro: {exc}")

    dxf_path = str(resultado.output_path)
    artefatos = {
        "n5_dxf": dxf_path,
        "n5_manifest": str(resultado.manifest_path),
        "ok_count": resultado.ok_count,
        "missing_count": resultado.missing_count,
    }
    ok = resultado.ok_count > 0
    return ResultadoEtapa(etapa="n5", ok=ok, comando=["assemble_n5", str(obra_dir), classe],
                          returncode=0 if ok else 1, artefatos=artefatos)
