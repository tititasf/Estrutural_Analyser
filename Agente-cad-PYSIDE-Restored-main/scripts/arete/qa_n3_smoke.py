#!/usr/bin/env python3
"""Smoke semântico N3 por classe, variante, contrato e DXF.

Confirma apenas identidade, presença de texto e camadas estruturais declaradas no
perfil. Não interpreta geometria, não escreve DB e não substitui veredito visual.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.arete.qa_artifact_parity import SPEC_SCHEMA, run_parity
from scripts.arete.qa_content_cache import ContentAddressedCache
from scripts.arete.qa_profile_probe import DEFAULT_PROFILES, load_profile


DEFAULT_REPORTS = Path(__file__).resolve().parent / "relatorios" / "qa_n3_smoke"
DEFAULT_CACHE = Path(__file__).resolve().parent / ".cache" / "qa_fastpaths"


def _labeled_path(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("use ROTULO=caminho")
    label, path_raw = raw.split("=", 1)
    path = Path(path_raw).expanduser().resolve()
    if not label.strip() or not path.is_file():
        raise argparse.ArgumentTypeError(f"rótulo vazio ou arquivo ausente: {raw}")
    return label.strip(), path


def build_smoke_spec(
    *, profile: dict[str, Any], item: str,
    contracts: dict[str, Path], dxfs: dict[str, Path],
    payloads: dict[str, Path] | None = None,
) -> dict[str, Any]:
    n3 = profile.get("n3") or {}
    identity_path = str(n3.get("identity_path") or "")
    layers = [str(value) for value in n3.get("expected_layers") or []]
    if not identity_path or not layers:
        raise ValueError(f"perfil {profile.get('class')} sem identity_path/expected_layers N3")
    labels = set(contracts) | set(dxfs)
    if not labels or set(contracts) != set(dxfs):
        raise ValueError("contratos e DXFs devem possuir exatamente os mesmos rótulos")
    allowed_variants = {str(value) for value in n3.get("variants") or []}
    aliases = {str(key): str(value) for key, value in (n3.get("variant_aliases") or {}).items()}
    unknown_variants = sorted(
        label for label in labels
        if label not in allowed_variants and aliases.get(label) not in allowed_variants
    )
    if unknown_variants:
        raise ValueError(
            f"variantes fora do perfil {profile.get('class')}: {', '.join(unknown_variants)}"
        )
    payloads = payloads or {}
    unknown_payloads = set(payloads) - labels
    if unknown_payloads:
        raise ValueError(f"payload sem variante: {sorted(unknown_payloads)}")

    spec: dict[str, Any] = {
        "schema": SPEC_SCHEMA,
        "question": (
            f"Smoke N3 {profile['class']}:{item}: identidade do contrato chega ao DXF "
            "e as camadas mínimas existem?"
        ),
        "variants": {}, "fields": [], "checks": [],
    }
    for label in sorted(labels):
        variant = {"contract": str(contracts[label]), "dxf": str(dxfs[label])}
        if label in payloads:
            variant["payload"] = str(payloads[label])
        spec["variants"][label] = variant
        prefix = label.lower().replace("-", "_")
        identity_id = f"{prefix}.contract.identity"
        text_id = f"{prefix}.dxf.text"
        count_id = f"{prefix}.dxf.text_count"
        spec["fields"].extend([
            {"id": identity_id, "variant": label, "source": "contract", "path": identity_path, "transform": "entity"},
            {"id": text_id, "variant": label, "source": "dxf_text_blob", "path": "", "transform": "text"},
            {"id": count_id, "variant": label, "source": "dxf_entity_count", "path": "TEXT", "transform": "number"},
        ])
        spec["checks"].extend([
            {"id": f"{prefix}.contract_item", "op": "same_entity", "left": identity_id, "value": item},
            {"id": f"{prefix}.identity_in_dxf", "op": "contains", "left": text_id, "right": identity_id},
            {"id": f"{prefix}.has_text", "op": "not_equal", "left": count_id, "value": 0},
        ])
        for index, layer in enumerate(layers, start=1):
            layer_id = f"{prefix}.dxf.layer_{index}"
            spec["fields"].append({
                "id": layer_id, "variant": label, "source": "dxf_layer_count",
                "path": layer, "transform": "number",
            })
            spec["checks"].append({
                "id": f"{prefix}.has_layer_{index}", "op": "not_equal",
                "left": layer_id, "value": 0,
                "reason": f"camada mínima {layer!r} presente no DXF",
            })
    return spec


def run_n3_smoke(
    *, profile: dict[str, Any], item: str,
    contracts: dict[str, Path], dxfs: dict[str, Path],
    payloads: dict[str, Path] | None = None,
    cache: ContentAddressedCache | None = None,
) -> dict[str, Any]:
    spec = build_smoke_spec(
        profile=profile, item=item, contracts=contracts, dxfs=dxfs, payloads=payloads,
    )
    result = run_parity(spec, base_dir=REPO_ROOT, cache=cache)
    result["profile"] = {
        "class": profile["class"], "version": profile.get("version"),
        "motor": (profile.get("n3") or {}).get("motor"),
        "authority": "n3_structural_smoke_only; visual and semantic geometry remain separate",
        "variant_resolution": {
            label: ((profile.get("n3") or {}).get("variant_aliases") or {}).get(label, label)
            for label in sorted(contracts)
        },
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida smoke estrutural N3 sem headless e sem DB.")
    parser.add_argument("--classe", required=True, choices=("PIL", "LAJ", "FV", "LV"))
    parser.add_argument("--item", required=True)
    parser.add_argument("--contract", action="append", required=True, type=_labeled_path)
    parser.add_argument("--dxf", action="append", required=True, type=_labeled_path)
    parser.add_argument("--payload", action="append", default=[], type=_labeled_path)
    parser.add_argument("--profiles-root", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    profile = load_profile(args.classe, args.profiles_root)
    result = run_n3_smoke(
        profile=profile, item=args.item,
        contracts=dict(args.contract), dxfs=dict(args.dxf), payloads=dict(args.payload),
        cache=ContentAddressedCache(args.cache_dir, enabled=not args.no_cache),
    )
    output = (args.out or DEFAULT_REPORTS / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{args.classe}_{args.item}.json").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"overall": result["overall"], "out": str(output)}, ensure_ascii=False))
    return 0 if result["overall"] == "PASS" else 1 if result["overall"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
