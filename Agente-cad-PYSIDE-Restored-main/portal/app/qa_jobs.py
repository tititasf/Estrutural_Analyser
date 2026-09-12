"""Execucao persistente de uma rodada QA multi-item no worker serial do portal."""

from __future__ import annotations

import json
import logging
import os
import stat
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup

from scripts.arete.qa_cli_resilient import ProviderInvoker, default_providers, run_round
from src.ui.widgets.fv_qa_proposal_draw import render_qa_proposal_svg

from . import fv_operations
from ..db import repository as repo


log = logging.getLogger("portal.qa_jobs")


DOCS_QA_PIL = (
    "CLAUDE.md",
    "docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md",
    "docs/PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md",
    "docs/INTERPRETACAO-PILARES-ABCD.md",
    "docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md",
)

DOCS_QA_FV = (
    "CLAUDE.md",
    "docs/PROCEDIMENTO-QA-FV-N1-CONTEXTUAL.md",
    "docs/PROVENIENCIA-CAMPOS-FV.md",
    "docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md",
)


def _append_event(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _atomic_write_text(path: Path, content: str) -> None:
    """Substitui artefato protegido sem truncar o inode/hardlink existente."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp_path, 0o664)
        try:
            os.replace(tmp_path, path)
        except PermissionError:
            if os.name != "nt" or not path.exists():
                raise
            path.chmod(path.stat().st_mode | stat.S_IWRITE)
            os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def garantir_png_item_pil(pack: Path, item: str) -> Path:
    """Materializa a evidencia visual canônica do item para as CLIs."""
    png = pack / "pilares" / "screenshots_qa" / f"{item}.png"
    if png.is_file() and png.stat().st_size > 0:
        return png
    from scripts.arete.playwright_loop import capture_granular_item_pages

    capture_granular_item_pages(
        pack / "pilares",
        out_dir=png.parent,
        selector="body",
        include_names=(f"{item}.html",),
    )
    if not png.is_file() or png.stat().st_size == 0:
        raise RuntimeError(f"evidencia PNG nao foi gerada para {item}")
    return png


def localizar_pack_pil(repo_root: Path, obra_nome: str, pavimento: str) -> Path:
    obra_dir = repo_root / "scripts" / "arete" / "html_fichas" / obra_nome
    candidates = [
        path
        for path in obra_dir.glob(f"{pavimento}*_pilares_abcd")
        if path.is_dir() and (path / "pilares").is_dir()
    ]
    if not candidates:
        raise FileNotFoundError(
            f"pack PIL ABCD nao encontrado para {obra_nome}/{pavimento} em {obra_dir}"
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def localizar_pack_fv(repo_root: Path, obra_nome: str, pavimento: str) -> Path:
    obra_dir = repo_root / "scripts" / "arete" / "html_fichas" / obra_nome
    candidates = [
        path for path in obra_dir.glob("*_fundos_viga_hifi*")
        if path.is_dir() and (path / "fundos_viga").is_dir()
    ]
    if not candidates:
        raise FileNotFoundError(
            f"pack FV HI-FI nao encontrado para {obra_nome}/{pavimento} em {obra_dir}"
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _svg_sa_fv(ficha: Path) -> str:
    soup = BeautifulSoup(ficha.read_text(encoding="utf-8", errors="replace"), "html.parser")
    svg = soup.select_one(".fv-layer-sa svg")
    return str(svg) if svg is not None else ""


def garantir_png_item_fv(pack: Path, item: str) -> Path:
    ficha = pack / "fundos_viga" / f"{item}.html"
    png = pack / "fundos_viga" / "screenshots_qa" / f"{item}.png"
    if png.is_file() and png.stat().st_size > 0:
        return png
    svg = _svg_sa_fv(ficha)
    if not svg:
        raise RuntimeError(f"SVG SA contextual ausente para {item}")
    png.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cairosvg

        cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            write_to=str(png),
            output_width=1400,
            output_height=1400,
        )
    except Exception as exc:
        raise RuntimeError(f"evidencia PNG FV nao foi gerada para {item}: {exc}") from exc
    return png


def contexto_item_pil(repo_root: Path, pack: Path, item: str, layer: str) -> str:
    ficha = pack / "pilares" / f"{item}.html"
    if not ficha.is_file():
        raise FileNotFoundError(f"ficha ausente: {ficha}")
    notes = pack / "pilares" / f"{item}.notes.json"
    visual_png = garantir_png_item_pil(pack, item)
    paths = [f"- {path}" for path in DOCS_QA_PIL]
    paths.append(f"- ficha: {ficha.relative_to(repo_root)}")
    paths.append(f"- evidencia visual PNG obrigatoria: {visual_png.relative_to(repo_root)}")
    if notes.is_file():
        paths.append(f"- notas: {notes.relative_to(repo_root)}")
    previous = {"L2": "L1", "L3": "L2"}.get(layer.upper())
    if previous:
        tables = pack / "propostas" / f"{item}_qa_{previous}_tables.json"
        svg = pack / "propostas" / f"{item}_qa_{previous}.svg"
        if tables.is_file():
            paths.append(f"- tabelas base {previous}: {tables.relative_to(repo_root)}")
        if svg.is_file():
            paths.append(f"- desenho base {previous}: {svg.relative_to(repo_root)}")
    return "\n".join(paths) + (
        "\nA ficha e grande: use Grep pelo marcador data-ficha-panel=\"interp\"; "
        "nao leia o HTML inteiro. Abra a evidencia PNG com a ferramenta de imagem; "
        "sem inspeciona-la, use revisar_humano. Para L1, julgue o SA. Para L2/L3, preserve a "
        "camada anterior e nunca reconstrua a partir do SA."
    )


def contexto_item_fv(repo_root: Path, pack: Path, item: str, layer: str, human_context: str = "") -> str:
    ficha = pack / "fundos_viga" / f"{item}.html"
    if not ficha.is_file():
        raise FileNotFoundError(f"ficha FV ausente: {ficha}")
    visual_png = garantir_png_item_fv(pack, item)
    paths = [f"- {path}" for path in DOCS_QA_FV]
    paths.extend((
        f"- ficha: {ficha.relative_to(repo_root)}",
        f"- evidencia visual PNG obrigatoria: {visual_png.relative_to(repo_root)}",
    ))
    previous = {"L2": "c1", "L3": "c2"}.get(layer.upper())
    if previous:
        prior = pack / "fundos_viga" / "propostas" / f"{item}_qa_proposta_{previous}.svg"
        if prior.is_file():
            paths.append(f"- desenho base {previous.upper()}: {prior.relative_to(repo_root)}")
    context = "\n".join(paths) + (
        "\nRevise a ficha de fundo HI-FI e a evidencia PNG. Para L1 julgue o SA; "
        "para L2/L3 julgue exclusivamente a camada anterior quando ela existir. "
        "Uma reprovação automatizada só é válida com suggestion.action=corrigir e proposed "
        "contendo todos os segmentos corrigidos, com polígonos fecháveis de ao menos 3 pontos "
        "no mesmo sistema de coordenadas CAD do SVG. Se não conseguir fornecer essa geometria, "
        "não reprove: a resposta deve falhar para revisão operacional, nunca gerar uma camada vazia."
    )
    if human_context.strip():
        context += "\n\nNOTAS E APONTAMENTOS HUMANOS (considere-os na revisão):\n" + human_context[:24000]
    return context


def _materializar_camada_fv(pack: Path, item: str, layer: str, result) -> None:
    suggestion = result.suggestion or {}
    if result.verdict != "invalidou":
        return
    if suggestion.get("action") != "corrigir":
        raise ValueError("FV reprovado sem acao corrigir")
    proposed = fv_operations.normalize_proposed_segments(suggestion.get("proposed"))
    previous_segments = []
    if layer in {"L2", "L3"}:
        prior = "c1" if layer == "L2" else "c2"
        prior_path = pack / "fundos_viga" / "propostas" / f"{item}_qa_proposta_{prior}.json"
        if prior_path.is_file():
            previous_segments = fv_operations.proposal_segments(prior_path, item)
    output_svg = render_qa_proposal_svg(
        beam=item,
        n1_segments=previous_segments,
        proposed_segments=proposed,
        show_n1_dimmed=bool(previous_segments),
        title=f"{item} · revisão agentica {layer}",
    )
    if not output_svg or "<svg" not in output_svg:
        raise ValueError("renderer FV nao produziu SVG da camada")
    proposals = pack / "fundos_viga" / "propostas"
    suffix = layer.lower().replace("l", "c")
    _atomic_write_text(proposals / f"{item}_qa_proposta_{suffix}.svg", output_svg)
    _atomic_write_text(
        proposals / f"{item}_qa_proposta_{suffix}.json",
        json.dumps({"beam": item, "layer": layer, "verdict": result.verdict,
                    "confidence_percent": suggestion.get("confidence_percent"),
                    "proposed": proposed}, ensure_ascii=False, indent=2),
    )


def executar_qa_round(
    *,
    settings,
    conn,
    round_id: str,
    log_path: Path,
    providers: Iterable[ProviderInvoker] | None = None,
) -> str:
    qa_round = repo.obter_qa_round(conn, round_id)
    if qa_round is None:
        raise KeyError(f"rodada QA inexistente: {round_id}")
    obra = repo.obter_obra(conn, qa_round["obra_id"])
    if obra is None:
        raise KeyError(f"obra da rodada QA inexistente: {qa_round['obra_id']}")
    if qa_round["classe"] not in {"PIL", "FV"}:
        raise ValueError("QA agentico funcional somente para PIL e FV")

    repo.iniciar_qa_round(conn, round_id)
    if qa_round["classe"] == "PIL":
        pack = localizar_pack_pil(settings.repo_root, obra["nome"], qa_round["pavimento"])
        context_for_item = lambda item, p=pack: contexto_item_pil(
            settings.repo_root, p, item, qa_round["layer"]
        )
    else:
        pack = localizar_pack_fv(settings.repo_root, obra["nome"], qa_round["pavimento"])
        obra_dir = Path(obra.get("local_path") or (settings.dados_obras_dir / obra["nome"]))
        def context_for_item(item, p=pack):
            override = fv_operations.load_override(obra_dir, qa_round["pavimento"], item)
            human_context = json.dumps({
                "notas_por_versao": override.get("notes") or {},
                "apontamentos": override.get("annotations") or [],
            }, ensure_ascii=False, indent=2)
            return contexto_item_fv(
                settings.repo_root, p, item, qa_round["layer"], human_context,
            )
    provider_list = list(providers or default_providers(settings.subprocess_timeout_s))
    events_path = log_path.with_suffix(".events.jsonl")

    def controle_operador() -> str | None:
        job = conn.execute(
            "SELECT status, erro_msg FROM portal_jobs WHERE id=?", (qa_round["job_id"],)
        ).fetchone()
        if job is None or job["status"] != "cancelado":
            return None
        if job["erro_msg"] == repo.PAUSA_OPERADOR:
            with conn:
                conn.execute(
                    """UPDATE portal_qa_rounds SET status='queued', finalizado_em=NULL,
                       updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?""",
                    (round_id,),
                )
            return "paused"
        items = repo.listar_qa_items(conn, round_id)
        completed = sum(item["status"] == "completed" for item in items)
        repo.finalizar_qa_round(conn, round_id, "partial_failed" if completed else "failed")
        return "cancelled"
    for item_row in repo.listar_qa_items(conn, round_id):
        if item_row["status"] != "queued":
            continue
        controle = controle_operador()
        if controle:
            return controle
        item_id = item_row["item_id"]
        result = run_round(
            round_id=round_id,
            items=[item_id],
            layer=qa_round["layer"],
            cwd=settings.repo_root,
            context_for_item=context_for_item,
            providers=provider_list,
            qa_class=qa_round["classe"],
        ).items[0]
        if qa_round["classe"] == "FV":
            try:
                _materializar_camada_fv(pack, item_id, qa_round["layer"], result)
            except Exception as exc:  # noqa: BLE001 - isola falha de um artefato
                log.exception("rodada QA %s: materializacao de %s falhou", round_id, item_id)
                repo.gravar_falha_qa_item(conn, round_id, item_id, str(exc)[:1000])
                _append_event(events_path, {
                    "schema": "cad.qa_processing_error/v1",
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "round_id": round_id,
                    "item": item_id,
                    "error": str(exc)[:1000],
                })
                continue
        repo.gravar_resultado_qa_item(conn, round_id, result)
        _append_event(
            events_path,
            {
                "schema": "cad.qa_training_candidate/v1",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "round_id": round_id,
                "obra_id": qa_round["obra_id"],
                "obra": obra["nome"],
                "pavimento": qa_round["pavimento"],
                "classe": qa_round["classe"],
                "layer": qa_round["layer"],
                "result": asdict(result),
                "curation": {
                    "training_eligible": False,
                    "tier_candidate": "T3",
                    "requires_human_approval": True,
                    "authority": "PENDENTE",
                },
            },
        )
    controle = controle_operador()
    if controle:
        return controle
    final_items = repo.listar_qa_items(conn, round_id)
    completed = sum(item["status"] == "completed" for item in final_items)
    if completed == len(final_items):
        status = "completed"
    elif completed:
        status = "partial_failed"
    else:
        status = "failed"
    repo.finalizar_qa_round(conn, round_id, status)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(repo.detalhe_qa_round(conn, round_id), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return status
