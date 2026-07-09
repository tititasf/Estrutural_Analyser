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

[RESOLVIDO 2026-07-06] O residual acima ("obra nova acha os recortes so' pelo
path dinamico?") foi testado de verdade ponta a ponta (triagem->recortes->sa
reais numa obra do portal, nao de treino): o SA falhava com
`LookupError: Pavimento SA nao encontrado` porque a obra nunca tinha 1 registro
em `projects` (project_data.vision) — so' existia pra obras abertas no app
desktop ou importadas via `scripts/import_obras_to_db.py`. Corrigido com
`_garantir_project_registrado()` (auto-registra via `DatabaseManager.
create_project()`, API oficial, decisao explicita do dono). Rodando de novo
com o fix: SA completou de verdade, gerando fichas HTML reais (46 pilares,
vigas V1..V317 etc) em `<obra_dir>/<pavimento>_<run_id>/` — NAO em
"Fase-6_Execucao_CAD" (esse path fixo nunca existia de verdade; corrigido em
`encontrar_dir_fichas()` abaixo, usado por paginas_routes.py/fichas_routes.py).
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


def encontrar_dir_fichas(obra_dir: Path) -> Optional[Path]:
    """Acha o diretorio de fichas HTML mais recente gerado pelo SA real.

    [2026-07-06] achado rodando o SA de verdade pela 1a vez contra uma obra
    nova do portal: o motor grava em `<obra_dir>/<pavimento>_<run_id>/`
    (timestamp por rodada, ex.: "13_PAV_20260706_181817", identificavel pelo
    `arete_manifest.json` dentro) — NUNCA em "Fase-6_Execucao_CAD" (esse path
    fixo era suposicao, nenhuma obra do portal tinha chegado ate' aqui pra
    revelar isso antes). Runs mais recentes ordenam por ultimo (timestamp no
    nome ordena lexicograficamente); usado por paginas_routes.py e
    fichas_routes.py (viewer).
    """
    if not obra_dir.exists():
        return None
    candidatos = sorted(
        (d for d in obra_dir.iterdir() if d.is_dir() and (d / "arete_manifest.json").is_file()),
        key=lambda d: d.name,
    )
    return candidatos[-1] if candidatos else None


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


def _garantir_project_registrado(settings: Settings, obra: dict, pavimento: str) -> None:
    """Garante 1 registro em `projects` (project_data.vision) pra obra+pavimento
    ANTES do SA — sem isso, `resolve_sa_project_from_db` (chamado dentro do
    headless) levanta `LookupError: Pavimento SA nao encontrado`, porque a
    unica forma de existir essa linha ate' hoje era abrir o DXF no app desktop
    ou rodar `scripts/import_obras_to_db.py` manualmente. Achado real rodando
    o fluxo inteiro (triagem->recortes->sa) contra uma obra nova do portal.

    [2026-07-06] Decisao explicita do dono: o portal PODE escrever aqui via
    `DatabaseManager.create_project()` — API OFICIAL, a mesma que o app desktop
    usa (main.py) e o script `import_obras_to_db.py` ja' usa em lote. Nao
    inventa schema nem contorna nada; so' evita o passo manual.

    Escopo: so' obras 'rapidas' (arquivo_nome preenchido, 1 arquivo = 1
    pavimento) — sem isso nao ha' UM dxf inequivoco pra registrar. Obra-
    container (multi-documento) fica de fora por ora (SA por documento e'
    trabalho futuro, nao pedido ainda).
    """
    from src.core.database import DatabaseManager
    from src.core.sa_project_source import select_sa_project

    arquivo_nome = obra.get("arquivo_nome")
    if not arquivo_nome:
        return  # obra-container: sem 1 dxf inequivoco, nao inventa qual usar

    obra_dir = _obra_dir(settings, obra)
    work_name = str(obra_dir)
    database = DatabaseManager(db_path=str(settings.sa_db_path))

    try:
        select_sa_project(database.get_projects(), obra=work_name, pavimento=pavimento)
        return  # ja' registrado (rodou antes, ou foi aberto no app desktop) — nada a fazer
    except LookupError:
        pass

    dxf_path = obra_dir / "entrada" / Path(arquivo_nome).with_suffix(".dxf").name
    if not dxf_path.is_file():
        return  # sem DXF convertido ainda (triagem nao rodou) — deixa o erro normal acontecer

    database.create_project(
        name=pavimento, dxf_path=str(dxf_path),
        work_name=work_name, pavement_name=pavimento,
    )


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


def _converter_e_validar_um(entrada: Path) -> tuple[bool, str, Optional[Path]]:
    """Conversao DWG->DXF (se preciso) + sanidade ezdxf de UM arquivo (R6).

    Retorna (ok, log, dxf_path). Extraido de executar_triagem() em 2026-07-06
    pra ser reusado tambem por executar_triagem_documentos() (obra com N docs)
    sem duplicar a logica de conversao/sanidade.
    """
    dxf_path = entrada
    linhas: list[str] = []

    if entrada.suffix.lower() == _EXT_DWG:
        dxf_path = entrada.with_suffix(".dxf")
        try:
            from scripts.converter_dwg_dxf_accore import convert_dwg_to_dxf  # type: ignore
        except ImportError as exc:
            return False, f"conversor DWG->DXF (accoreconsole) indisponivel: {exc}", None
        linhas.append(f"convertendo {entrada.name} -> {dxf_path.name} via accoreconsole")
        try:
            ok = convert_dwg_to_dxf(entrada, dxf_path)
        except Exception as exc:  # noqa: BLE001 - accoreconsole pode falhar de varias formas
            return False, "\n".join(linhas + [f"conversao DWG->DXF falhou: {exc}"]), None
        if not ok:
            return False, "\n".join(linhas + ["conversao retornou falha"]), None

    try:
        import ezdxf

        doc = ezdxf.readfile(str(dxf_path))
        n_entidades = len(doc.modelspace())
        linhas.append(f"sanidade ezdxf OK: {dxf_path.name} ({n_entidades} entidades)")
    except Exception as exc:  # noqa: BLE001 - ezdxf levanta varios tipos de erro de parse
        return False, "\n".join(linhas + [f"sanidade ezdxf falhou: {exc}"]), None

    return True, "\n".join(linhas), dxf_path


def executar_triagem(
    settings: Settings, obra: dict, *, dry_run: bool = True, log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Etapa 2 (LEGADO — obra de arquivo único, sem portal_documentos).

    [2026-07-06] Mantida so' para obras criadas ANTES da migration 002
    (modelo "1 obra = 1 arquivo"). Obras novas (POST /obras/criar) usam
    executar_triagem_documentos() — a obra vira container de N documentos.
    """
    obra_dir = _obra_dir(settings, obra)
    entrada = _arquivo_entrada(obra_dir, obra)
    comando_desc = ["triagem(conversao+sanidade)", str(obra_dir)]
    if dry_run:
        return ResultadoEtapa(etapa="triagem", ok=True, dry_run=True, comando=comando_desc)

    if entrada is None:
        msg = f"nenhum arquivo .dwg/.dxf encontrado em {obra_dir / 'entrada'}"
        return ResultadoEtapa(etapa="triagem", ok=False, comando=comando_desc, log_tail=msg)

    ok, texto, dxf_path = _converter_e_validar_um(entrada)
    if not ok:
        return ResultadoEtapa(etapa="triagem", ok=False, comando=comando_desc, log_tail=texto)

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


def executar_triagem_documentos(
    settings: Settings,
    obra: dict,
    documentos: list[dict],
    *,
    dry_run: bool = True,
    log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Etapa 2 (NOVO MODELO — obra container, 2026-07-06): triagem de N documentos.

    Roda conversao+sanidade (mesmo `_converter_e_validar_um`) para CADA documento
    pendente da obra — um falhar nao impede os outros de rodarem (R6: quarentena
    por item, nao pela obra inteira). O chamador (jobs.py) aplica o resultado por
    documento via repository.atualizar_classificacao_documento (esta funcao so'
    devolve os resultados, nao escreve no DB — pipeline_runner nao conhece o repo).
    """
    obra_dir = _obra_dir(settings, obra)
    comando_desc = ["triagem_documentos", str(obra_dir), f"n_docs={len(documentos)}"]
    if dry_run:
        return ResultadoEtapa(etapa="triagem", ok=True, dry_run=True, comando=comando_desc)

    resultados: list[dict] = []
    linhas_log: list[str] = []
    for doc in documentos:
        entrada = obra_dir / "entrada" / doc["arquivo_nome"]
        if not entrada.exists():
            resultados.append({"doc_id": doc["id"], "ok": False,
                              "erro_msg": f"arquivo nao encontrado em disco: {entrada}"})
            linhas_log.append(f"{doc['arquivo_nome']}: ARQUIVO AUSENTE")
            continue
        # [2026-07-07] PDF (material de referência, tipo_documento="PDF") não
        # entra no pipeline DXF — conversão/sanidade ezdxf não se aplica (não
        # é DWG/DXF). Marca ok direto, sem tentar converter/validar.
        if entrada.suffix.lower() == ".pdf":
            resultados.append({"doc_id": doc["id"], "ok": True, "dxf_path": None, "erro_msg": None})
            linhas_log.append(f"{doc['arquivo_nome']}: PDF (referência, sem conversão/sanidade)")
            continue
        ok, texto_doc, dxf_path = _converter_e_validar_um(entrada)
        linhas_log.append(f"--- {doc['arquivo_nome']} ---\n{texto_doc}")
        resultados.append({
            "doc_id": doc["id"], "ok": ok,
            "dxf_path": str(dxf_path) if dxf_path else None,
            "erro_msg": None if ok else texto_doc[:300],
        })

    texto_completo = "\n".join(linhas_log)
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(texto_completo, encoding="utf-8", errors="replace")
        except OSError:
            pass

    # sucesso "geral" = pelo menos 1 documento processou — falhas individuais
    # viram status='erro' NAQUELE documento (quarentena por item, R6), nao
    # derrubam a obra inteira; se documentos estava vazio, nao ha' nada a fazer.
    ok_geral = any(r["ok"] for r in resultados) if resultados else True
    return ResultadoEtapa(
        etapa="triagem", ok=ok_geral, comando=comando_desc,
        log_tail=_tail(texto_completo), artefatos={"documentos": resultados},
    )


def listar_dwgs_com_status(settings: Settings, obra: dict, documentos: list[dict]) -> list[dict]:
    """[2026-07-08, a pedido do dono] Lista só os documentos .dwg da obra, cada
    um com `tem_dxf` (bool) — checado em DISCO, mesma convenção de sempre
    (`<obra_dir>/entrada/<stem>.dxf`, ver `_entrada_dxf` em recortes_routes.py),
    não em campo de banco (não existe um; a conversão é 100% arquivo-a-arquivo)."""
    obra_dir = _obra_dir(settings, obra)
    entrada_dir = obra_dir / "entrada"
    saida = []
    for doc in documentos:
        if not doc["arquivo_nome"].lower().endswith(_EXT_DWG):
            continue
        dxf_path = entrada_dir / Path(doc["arquivo_nome"]).with_suffix(".dxf").name
        saida.append({
            "doc_id": doc["id"], "arquivo_nome": doc["arquivo_nome"],
            "nome_exibicao": doc.get("nome_exibicao"), "tem_dxf": dxf_path.is_file(),
        })
    return saida


def executar_conversao_dwg(
    settings: Settings,
    obra: dict,
    documentos: list[dict],
    *,
    dry_run: bool = True,
    log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Conversão avulsa DWG->DXF (a pedido do dono, 2026-07-08): converte de uma
    vez só todo DWG da obra que ainda não tem DXF equivalente em disco — reusa
    o MESMO conversor real da ingestão/triagem (`_converter_e_validar_um`, que
    por sua vez chama `scripts.converter_dwg_dxf_accore.convert_dwg_to_dxf`),
    só que disparável isoladamente, sem rodar classificação/sanidade completa
    de novo nos que já converteram. Sequencial (accoreconsole não paraleliza —
    mesma trava de máquina inteira que triagem/recortes já usam, ver jobs.py).
    """
    obra_dir = _obra_dir(settings, obra)
    entrada_dir = obra_dir / "entrada"
    pendentes = [d for d in documentos if d["arquivo_nome"].lower().endswith(_EXT_DWG)
                 and not (entrada_dir / Path(d["arquivo_nome"]).with_suffix(".dxf").name).is_file()]
    comando_desc = ["conversao_dwg_dxf", str(obra_dir), f"n_pendentes={len(pendentes)}"]
    if dry_run:
        return ResultadoEtapa(etapa="converter_dwg", ok=True, dry_run=True, comando=comando_desc)

    resultados: list[dict] = []
    linhas_log: list[str] = []
    for doc in pendentes:
        entrada = entrada_dir / doc["arquivo_nome"]
        if not entrada.exists():
            resultados.append({"doc_id": doc["id"], "ok": False, "erro_msg": "arquivo dwg nao encontrado em disco"})
            linhas_log.append(f"{doc['arquivo_nome']}: ARQUIVO AUSENTE")
            continue
        ok, texto_doc, _dxf_path = _converter_e_validar_um(entrada)
        linhas_log.append(f"--- {doc['arquivo_nome']} ---\n{texto_doc}")
        resultados.append({"doc_id": doc["id"], "ok": ok, "erro_msg": None if ok else texto_doc[:300]})

    texto_completo = "\n".join(linhas_log) if linhas_log else "nenhum DWG pendente de conversao"
    if log_path is not None:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            Path(log_path).write_text(texto_completo, encoding="utf-8", errors="replace")
        except OSError:
            pass

    ok_geral = all(r["ok"] for r in resultados) if resultados else True
    return ResultadoEtapa(
        etapa="converter_dwg", ok=ok_geral, comando=comando_desc,
        log_tail=_tail(texto_completo), artefatos={"documentos": resultados},
    )


def executar_recortes(
    settings: Settings, obra: dict, *, dry_run: bool = True, log_path: Optional[Path] = None,
) -> ResultadoEtapa:
    """Etapa 3: 2 motores reais, propositos DIFERENTES (achado ao vivo com o
    dono 2026-07-07 — a aba Recortes do portal mostrava so' o motor errado):

    1. `RecorteMotor` (src/core/recorte_motor.py) — recorte POR ELEMENTO
       estrutural (1 arquivo por pilar/viga/laje), classes PIL/LV/FV/LAJ.
       Usado pelo pipeline de engenharia reversa (scripts/engrev_laj_recorte_loop.py)
       pra treinar o SA — NAO e' pensado pra revisao humana (uma obra de 13
       pavimentos gera 31 arquivos so' de laje).
    2. `scripts/obra_crop_engine` (torre_crop.py) — recorte da OBRA INTEIRA
       em torre(s) limpa(s) + detalhes/convencoes unificados (DBSCAN por
       densidade). Esse e' o que a aba Recortes do portal REALMENTE precisa
       mostrar pro usuario revisar (poucos itens, cada um a planta inteira).

    Ambos rodam (nenhum efeito colateral entre eles — dirs de saida
    diferentes); a UI so' le' o (2).
    """
    obra_dir = _obra_dir(settings, obra)
    output_dir = obra_dir / "Fase-2_Triagem" / "recortes_reversos"
    comando_desc = ["RecorteMotor.run+obra_crop_engine", str(obra_dir), "classes=" + ",".join(_CLASSES_RECORTE)]
    if dry_run:
        return ResultadoEtapa(etapa="recortes", ok=True, dry_run=True, comando=comando_desc)

    entrada = _arquivo_entrada(obra_dir, obra)
    dxf_path = entrada.with_suffix(".dxf") if entrada and entrada.suffix.lower() == _EXT_DWG else entrada
    if dxf_path is None or not dxf_path.exists():
        msg = f"nenhum DXF encontrado em {obra_dir / 'entrada'} — rode a triagem primeiro"
        return ResultadoEtapa(etapa="recortes", ok=False, comando=comando_desc, log_tail=msg)

    linhas_log: list[str] = []
    total_elementos = 0

    try:
        from src.core.recorte_motor import RecorteMotor
        for classe in _CLASSES_RECORTE:
            try:
                motor = RecorteMotor(str(dxf_path), er_type=classe)
                resultados = motor.run(output_dir, overwrite=True)
            except Exception as exc:  # noqa: BLE001 - motor pode nao achar frame p/ essa classe
                linhas_log.append(f"{classe}: erro ({exc})")
                continue
            linhas_log.append(f"{classe}: {len(resultados)} elemento(s)")
            total_elementos += len(resultados)
    except ImportError as exc:
        linhas_log.append(f"RecorteMotor indisponivel: {exc}")

    from . import recortes_reader, torre_crop
    # [2026-07-07] roda torre_crop pra TODOS os brutos da obra (obra com N
    # documentos = N brutos em entrada/), não só o 1o — achado com o dono:
    # obra completa (multi-doc) precisa de 1 pasta de recortes por documento
    # na aba Recortes, cada um com sua(s) torre(s)+detalhes.
    brutos = recortes_reader.listar_brutos_recorte(obra_dir)
    if not brutos:
        brutos = [{"bruto_id": dxf_path.stem, "nome": dxf_path.name}]
    torres_geradas = 0
    for bruto in brutos:
        bruto_path = (obra_dir / "entrada" / bruto["nome"])
        if not bruto_path.is_file():
            linhas_log.append(f"torre_crop [{bruto['bruto_id']}]: arquivo não encontrado")
            continue
        crop_result = torre_crop.gerar_recortes_bruto(obra_dir, bruto_path, bruto["bruto_id"], force=True)
        if crop_result.get("error"):
            linhas_log.append(f"torre_crop [{bruto['bruto_id']}]: {crop_result['error']}")
        else:
            n_torres = len(crop_result.get("torres") or [])
            tem_detalhes = crop_result.get("detalhes") is not None
            torres_geradas += n_torres
            linhas_log.append(
                f"torre_crop [{bruto['bruto_id']}]: {n_torres} torre(s), detalhes={'sim' if tem_detalhes else 'nao'}"
            )

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
        artefatos={"recortes_dir": str(output_dir), "total_elementos": total_elementos,
                   "brutos_processados": len(brutos), "torres_geradas": torres_geradas},
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
    pav_efetivo = pav or settings.pav_default
    if pav_efetivo == "Indeterminado":
        msg = "Documento sem pavimento (Docs Gerais). Análise estrutural SA ignorada."
        if log_path:
            try:
                Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                Path(log_path).write_text(msg, encoding="utf-8")
            except OSError:
                pass
        return ResultadoEtapa(etapa=etapa, ok=True, comando=[], dry_run=dry_run, log_tail=msg)

    if not obra.get("arquivo_nome"):
        msg = "Obra-container (multi-documento). Análise SA por documento é trabalho futuro. Etapa ignorada."
        if log_path:
            try:
                Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                Path(log_path).write_text(msg, encoding="utf-8")
            except OSError:
                pass
        return ResultadoEtapa(etapa=etapa, ok=True, comando=[], dry_run=dry_run, log_tail=msg)

    cmd = montar_comando_headless(settings, obra, secao=secao, pav=pav_efetivo)

    if dry_run:
        return ResultadoEtapa(etapa=etapa, ok=True, comando=cmd, dry_run=True)

    _garantir_project_registrado(settings, obra, pav or settings.pav_default)

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
