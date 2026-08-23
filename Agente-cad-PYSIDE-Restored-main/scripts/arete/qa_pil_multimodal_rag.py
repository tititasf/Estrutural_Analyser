#!/usr/bin/env python3
"""Materializa um pacote RAG multimodal PIL sem promover memória ativa.

O HTML é contexto de navegação, o SVG é evidência visual e o sidecar JSON é
evidência semântica. A decisão humana escolhe a camada. Quando o sidecar não
pertence à camada aprovada (por exemplo, SA aprovado usando L1 como
substituto), o canal visual pode ser T1, mas o canal semântico permanece T0.
Nenhuma execução deste utilitário escreve no banco ou no índice vetorial.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "arete.pil_multimodal_rag_candidates/v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_ok(artifact: dict[str, Any] | None) -> bool:
    if not artifact or not artifact.get("path") or not artifact.get("sha256"):
        return False
    path = Path(artifact["path"])
    return path.is_file() and _sha256(path) == artifact["sha256"]


def _semantic_text(item: str, semantic: dict[str, Any]) -> str:
    parts = [
        f"Pilar {item}",
        f"orientacao={semantic.get('orientation') or 'desconhecida'}",
        f"geometria={semantic.get('geometry_type') or 'nao_tipificada'}",
        "faces=" + ",".join(semantic.get("face_ids") or []),
    ]
    for face, bucket in sorted((semantic.get("faces") or {}).items()):
        for role in ("lajes", "passa", "chega", "interior"):
            rows = bucket.get(role) or []
            for row in rows:
                parts.append(
                    f"face {face} {role}: {row.get('nome')} canto={row.get('canto')} "
                    f"dim={row.get('dim') or '?'} nivel={row.get('nivel_cm') or '?'}"
                )
    return " | ".join(parts)


def build_pack(corpus: dict[str, Any], corpus_path: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    counts = {"semantic_t1_candidate": 0, "visual_t1_candidate": 0, "t0": 0, "tx": 0}

    for source in corpus.get("items") or []:
        artifacts = source.get("artifacts") or {}
        artifact_status = {kind: _artifact_ok(value) for kind, value in artifacts.items()}
        visual_tier = "T1_CANDIDATE" if artifact_status.get("svg") and artifact_status.get("html") else "T0"
        semantic_exact = (
            source.get("semantic_source_kind") == "layer_sidecar"
            and artifact_status.get("tables")
        )
        semantic_tier = "T1_CANDIDATE" if semantic_exact else "T0"
        counts["visual_t1_candidate"] += visual_tier == "T1_CANDIDATE"
        counts["semantic_t1_candidate"] += semantic_tier == "T1_CANDIDATE"
        counts["t0"] += semantic_tier == "T0"
        records.append({
            "record_id": f"pil-{source['item']}-{source['approved_layer']}",
            "item": source["item"],
            "approved_layer": source["approved_layer"],
            "human_verdicts": source.get("human_verdicts") or {},
            "channels": {
                "visual": {"tier": visual_tier, "svg": artifacts.get("svg"), "html": artifacts.get("html")},
                "semantic": {
                    "tier": semantic_tier,
                    "source_kind": source.get("semantic_source_kind"),
                    "tables": artifacts.get("tables"),
                    "payload": source.get("semantic") or {},
                },
            },
            "artifact_integrity": artifact_status,
            "retrieval_text": _semantic_text(source["item"], source.get("semantic") or {}),
            "authority": "candidate_only; human promotion required; local CAD evidence outranks retrieval",
        })

    for source in corpus.get("pending_items") or []:
        counts["t0"] += 1
        records.append({
            "record_id": f"pil-{source['item']}-{source.get('current_layer')}-pending",
            "item": source["item"],
            "status": "T0_PENDING",
            "human_verdicts": source.get("human_verdicts") or {},
            "artifacts": source.get("artifacts") or {},
            "authority": "negative_or_pending_context_only; forbidden_as_confirmatory_retrieval",
        })

    for source in corpus.get("negative_examples") or []:
        counts["tx"] += 1
        records.append({
            "record_id": f"pil-{source['item']}-{source['layer']}-negative",
            "item": source["item"],
            "layer": source["layer"],
            "status": "TX_NEGATIVE",
            "artifacts": source.get("artifacts") or {},
            "authority": "negative_example_only; excluded_from_positive_retrieval",
        })

    return {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_corpus": str(corpus_path.resolve()),
        "source_corpus_sha256": _sha256(corpus_path),
        "promotion_state": "NOT_PROMOTED",
        "counts": counts,
        "records": records,
    }


def write_pack(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=False)
    manifest = {key: value for key, value in payload.items() if key != "records"}
    manifest["record_count"] = len(payload["records"])
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    with (out_dir / "records.jsonl").open("w", encoding="utf-8") as stream:
        for record in payload["records"]:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    (out_dir / "README.md").write_text(
        "# PIL multimodal RAG candidate pack\n\n"
        "Este pacote não foi promovido. SVG/HTML são evidência visual; JSON é "
        "evidência semântica. T0/TX nunca confirmam um resultado. T1_CANDIDATE "
        "ainda exige aprovação humana antes de entrar no RAG consultável.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    payload = build_pack(corpus, args.corpus)
    write_pack(payload, args.out_dir)
    print(json.dumps({"out_dir": str(args.out_dir), **payload["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
