"""Acionamento do pipeline: subprocess do headless + import do assemble_n5 (HANDOFF §1.2).

O portal NUNCA importa PySide6 nem o motor SA. As etapas 2-4 rodam por SUBPROCESS do
CLI existente `scripts.arete.headless_sa_analise` (Qt offscreen isolado num processo
filho — se estourar RAM/travar, nao derruba o web server). A etapa 6 (N5) importa
`src.core.n5_assembler.assemble_n5` diretamente (leve, so ezdxf).

`dry_run=True` (default nos testes) NAO dispara subprocess — retorna o comando que
seria executado. O codigo de producao chama de verdade (dry_run=False).

[FIX 2026-07-06] Achado auditando antes do dono testar: "triagem" e "recortes"
disparavam o MESMO comando `headless_sa_analise.py --wait` — nao eram passos
distintos de verdade (rodava o pipeline inteiro 3x). Corrigido usando o que
REALMENTE existe no repo para cada etapa (pesquisa confirmou via leitura de
codigo, nao suposicao):
  - TRIAGEM = conversao de entrada (DWG->DXF via `converter_dwg_dxf_accore.py`,
    reusa accoreconsole ja instalado — ODA File Converter e' WS-C, ainda nao
    fechado) + validacao de sanidade ezdxf (R6). Bate com a definicao literal
    do HANDOFF-ARCHITECT-PORTAL.md §1.2 ("Conversao de entrada + validacao de
    sanidade ezdxf"), que e' diferente do conceito de "triagem manual" do app
    PySide6 (aquele e' outra coisa, feito no diagnostic_hub.py com mouse).
  - RECORTES = `src.core.recorte_motor.RecorteMotor` (motor real, ja usado em
    producao por `scripts/engrev_laj_recorte_loop.py`, sem depender de UI).
  - SA completo continua sendo o unico que roda `headless_sa_analise.py`.

Residual NAO resolvido aqui (fora do escopo seguro pra eu mexer sozinho): o
motor `headless_sa_analise.py`/`ficha_adapter.get_recorte_path` tem um
fallback hardcoded pra `Obra_TREINO_1` (`scripts/arete/arete_config.py::
RECORTES_ROOT`) — nao confirmei se ele acha os recortes de uma obra NOVA
(fora do treino) so' pelo path dinamico. Isso e' terreno do motor Arete em si
(outra sessao esta ativa nele agora — main.py/beam_tracer.py mudando ao vivo),
nao do portal. So' um teste real com obra nova revela se funciona ponta a
ponta; documentado, nao escondido.
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


_EXT_DWG = ".dwg"
_CLASSES_RECORTE = ("PIL", "LV", "FV", "LAJ")


def _arquivo_entrada(obra_dir: Path, obra: dict) -> Optional[Path]:
    """Localiza o arquivo original da obra dentro de obra_dir/entrada/ (poller)."""
    nome = obra.get("arquivo_nome")
    if nome:
        candidato = obra_dir / "entrada" / nome
        if candidato.exists():
            return candidato
    pasta = obra_dir / "entrada"
    if pasta.exists():
        achados = sorted(pasta.glob("*.dwg")) + sorted(pasta.glob("*.dxf"))
        if achados:
            return achados[0]
    return None


def executar_triagem(
    settings: Settings, obra: dict, *, dry_run: bool = True, log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Etapa 2: conversao de entrada (DWG->DXF se preciso) + sanidade ezdxf (R6).

    NAO roda o pipeline pesado (isso e' etapa 4/SA). So' garante que existe um DXF
    valido e legivel pro resto do fluxo — leve e rapido, como o HANDOFF descreve.
    """
    obra_dir = _obra_dir(settings, obra)
    entrada = _arquivo_entrada(obra_dir, obra)
    comando_desc = ["triagem(conversao+sanidade)", str(obra_dir)]
    if dry_run:
        return ResultadoEtapa(etapa="triagem", ok=True, dry_run=True, comando=comando_desc)

    if entrada is None:
        msg = f"nenhum arquivo .dwg/.dxf encontrado em {obra_dir / 'entrada'}"
        return ResultadoEtapa(etapa="triagem", ok=False, comando=comando_desc, log_tail=msg)

    dxf_path = entrada
    saida_log: list[str] = []

    if entrada.suffix.lower() == _EXT_DWG:
        dxf_path = entrada.with_suffix(".dxf")
        try:
            from scripts.converter_dwg_dxf_accore import convert_dwg_to_dxf  # type: ignore
        except ImportError as exc:
            return ResultadoEtapa(
                etapa="triagem", ok=False, comando=comando_desc,
                log_tail=f"conversor DWG->DXF (accoreconsole) indisponivel: {exc}",
            )
        saida_log.append(f"convertendo {entrada.name} -> {dxf_path.name} via accoreconsole")
        try:
            ok = convert_dwg_to_dxf(entrada, dxf_path)
        except Exception as exc:  # noqa: BLE001 - accoreconsole pode falhar de varias formas
            return ResultadoEtapa(etapa="triagem", ok=False, comando=comando_desc,
                                  log_tail=f"conversao DWG->DXF falhou: {exc}")
        if not ok:
            return ResultadoEtapa(etapa="triagem", ok=False, comando=comando_desc,
                                  log_tail="\n".join(saida_log + ["conversao retornou falha"]))

    # Sanidade ezdxf (R6): garante que o DXF (convertido ou ja original) e' legivel
    # e nao e' conteudo malicioso/corrompido — nunca executa o arquivo, so' parseia.
    try:
        import ezdxf

        doc = ezdxf.readfile(str(dxf_path))
        n_entidades = len(doc.modelspace())
        saida_log.append(f"sanidade ezdxf OK: {dxf_path.name} ({n_entidades} entidades)")
    except Exception as exc:  # noqa: BLE001 - ezdxf levanta varios tipos de erro de parse
        return ResultadoEtapa(etapa="triagem", ok=False, comando=comando_desc,
                              log_tail="\n".join(saida_log + [f"sanidade ezdxf falhou: {exc}"]))

    texto = "\n".join(saida_log)
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(texto, encoding="utf-8", errors="replace")
        except OSError:
            pass

    return ResultadoEtapa(
        etapa="triagem", ok=True, comando=comando_desc, returncode=0,
        log_tail=_tail(texto), artefatos={"dxf_entrada": str(dxf_path)},
    )


def executar_recortes(
    settings: Settings, obra: dict, *, dry_run: bool = True, log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Etapa 3: segmentacao/crop via RecorteMotor (src/core/recorte_motor.py).

    Motor real (nao GUI) — ja usado em producao por scripts/engrev_laj_recorte_loop.py.
    Roda as 4 classes (PIL/LV/FV/LAJ); classe que nao encontrar elemento so' fica
    com results=[] (nao e' falha — a obra pode nao ter aquela classe).
    """
    obra_dir = _obra_dir(settings, obra)
    output_dir = obra_dir / "Fase-2_Triagem" / "recortes_reversos"
    comando_desc = ["RecorteMotor.run", str(obra_dir), "classes=" + ",".join(_CLASSES_RECORTE)]
    if dry_run:
        return ResultadoEtapa(etapa="recortes", ok=True, dry_run=True, comando=comando_desc)

    entrada = _arquivo_entrada(obra_dir, obra)
    dxf_path = entrada.with_suffix(".dxf") if entrada and entrada.suffix.lower() == _EXT_DWG else entrada
    if dxf_path is None or not dxf_path.exists():
        msg = f"nenhum DXF encontrado em {obra_dir / 'entrada'} — rode a triagem primeiro"
        return ResultadoEtapa(etapa="recortes", ok=False, comando=comando_desc, log_tail=msg)

    try:
        from src.core.recorte_motor import RecorteMotor
    except ImportError as exc:
        return ResultadoEtapa(etapa="recortes", ok=False, comando=comando_desc,
                              log_tail=f"RecorteMotor indisponivel: {exc}")

    total_elementos = 0
    linhas_log: list[str] = []
    for classe in _CLASSES_RECORTE:
        try:
            motor = RecorteMotor(str(dxf_path), er_type=classe)
            resultados = motor.run(output_dir, overwrite=True)
        except Exception as exc:  # noqa: BLE001 - motor pode nao achar frame p/ essa classe
            linhas_log.append(f"{classe}: erro ({exc})")
            continue
        linhas_log.append(f"{classe}: {len(resultados)} elemento(s)")
        total_elementos += len(resultados)

    texto = "\n".join(linhas_log)
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(texto, encoding="utf-8", errors="replace")
        except OSError:
            pass

    return ResultadoEtapa(
        etapa="recortes", ok=True, comando=comando_desc, returncode=0,
        log_tail=_tail(texto),
        artefatos={"recortes_dir": str(output_dir), "total_elementos": total_elementos},
    )


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
    """Executa uma etapa de pipeline (triagem/recortes/sa).

    N5 NAO passa por aqui — usa executar_n5(). validacao NAO passa por aqui — so DB.
    dry_run=True devolve o comando sem disparar (default seguro para testes).

    triagem/recortes NAO chamam mais o headless (achado 2026-07-06 — eram o MESMO
    comando repetido 3x). So' 'sa' de fato dispara o subprocess pesado.
    """
    if etapa not in ETAPAS_SUBPROCESS:
        raise ValueError(f"etapa {etapa!r} nao e' de subprocess (validas: {ETAPAS_SUBPROCESS})")

    if etapa == "triagem":
        return executar_triagem(settings, obra, dry_run=dry_run, log_path=log_path)
    if etapa == "recortes":
        return executar_recortes(settings, obra, dry_run=dry_run, log_path=log_path)

    # etapa == "sa": unico caminho que dispara headless_sa_analise.py de verdade.
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
