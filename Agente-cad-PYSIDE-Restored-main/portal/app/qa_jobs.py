"""Execucao persistente de uma rodada QA multi-item no worker serial do portal."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from scripts.arete.qa_cli_fallback import ProviderInvoker, default_providers, run_round

from ..db import repository as repo


DOCS_QA_PIL = (
    "CLAUDE.md",
    "docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md",
    "docs/PROCEDIMENTO-QA-PIL-N1-CONTEXTUAL.md",
    "docs/INTERPRETACAO-PILARES-ABCD.md",
    "docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md",
)


def _append_event(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


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
    if qa_round["classe"] != "PIL":
        raise ValueError("primeiro E2E QA suporta PIL; outras classes falham fechado")

    repo.iniciar_qa_round(conn, round_id)
    pack = localizar_pack_pil(settings.repo_root, obra["nome"], qa_round["pavimento"])
    provider_list = list(providers or default_providers(settings.subprocess_timeout_s))
    persisted = []
    events_path = log_path.with_suffix(".events.jsonl")
    for item_row in repo.listar_qa_items(conn, round_id):
        item_id = item_row["item_id"]
        result = run_round(
            round_id=round_id,
            items=[item_id],
            layer=qa_round["layer"],
            cwd=settings.repo_root,
            context_for_item=lambda item, p=pack: contexto_item_pil(
                settings.repo_root, p, item, qa_round["layer"]
            ),
            providers=provider_list,
        ).items[0]
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
        persisted.append(result)

    completed = sum(item.status == "completed" for item in persisted)
    if completed == len(persisted):
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
