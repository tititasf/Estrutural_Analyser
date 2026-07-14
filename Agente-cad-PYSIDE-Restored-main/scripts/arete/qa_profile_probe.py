#!/usr/bin/env python3
"""Executa probes N1 declarados nos perfis semânticos de cada classe.

O runner resolve referências cross-classe em duas fases. Primeiro lê apenas os
campos que identificam a entidade relacionada; depois materializa o request
final. Nenhum resultado amplia sua autoridade além dos checks declarados.
"""

from __future__ import annotations

import argparse
import copy
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.arete.qa_content_cache import ContentAddressedCache, content_hash
from scripts.arete.qa_n1_field_probe import (
    DEFAULT_CACHE,
    DEFAULT_DB,
    REQUEST_SCHEMA,
    run_probe,
)


PROFILE_SCHEMA = "arete.qa_class_profile/v1"
RESULT_SCHEMA = "arete.qa_profile_probe_result/v1"
DEFAULT_PROFILES = REPO_ROOT / "squads" / "qa-global-evidencias" / "data" / "class_profiles"
DEFAULT_REPORTS = Path(__file__).resolve().parent / "relatorios" / "qa_profile_probes"


class ProfileProbeError(ValueError):
    pass


class _StrictFormat(dict[str, Any]):
    def __missing__(self, key: str) -> Any:
        raise ProfileProbeError(f"variável obrigatória ausente: {key}")


def _render(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format_map(_StrictFormat(context))
    if isinstance(value, list):
        return [_render(entry, context) for entry in value]
    if isinstance(value, dict):
        return {key: _render(entry, context) for key, entry in value.items()}
    return copy.deepcopy(value)


def load_profile(classe: str, root: Path = DEFAULT_PROFILES) -> dict[str, Any]:
    path = root / f"{classe.lower()}.json"
    if not path.is_file():
        raise ProfileProbeError(f"perfil inexistente: {path}")
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ProfileProbeError(f"schema de perfil inválido: {path}")
    if str(profile.get("class") or "").upper() != classe.upper():
        raise ProfileProbeError(f"classe do perfil diverge: {path}")
    return profile


def list_profiles(root: Path = DEFAULT_PROFILES) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        rows.append({
            "class": profile.get("class"),
            "version": profile.get("version"),
            "probes": sorted((profile.get("n1") or {}).get("probes", {})),
            "path": str(path.resolve()),
        })
    return rows


def run_profile_probe(
    con: sqlite3.Connection,
    profile: dict[str, Any],
    *,
    probe_id: str,
    item: str,
    variables: dict[str, Any] | None = None,
    project_id: str | None = None,
    obra: str | None = None,
    pav: str | None = None,
    cache: ContentAddressedCache | None = None,
) -> dict[str, Any]:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ProfileProbeError(f"schema esperado: {PROFILE_SCHEMA}")
    probe = ((profile.get("n1") or {}).get("probes") or {}).get(probe_id)
    if not isinstance(probe, dict):
        raise ProfileProbeError(f"probe desconhecido: {profile.get('class')}:{probe_id}")
    context = {"item": item, **(variables or {})}
    rendered = _render(probe, context)
    fields = copy.deepcopy(rendered.get("fields") or [])
    checks = copy.deepcopy(rendered.get("checks") or [])
    if not fields or not checks:
        raise ProfileProbeError("probe exige fields e checks")

    dynamic = [field for field in fields if field.get("item_from")]
    direct = [field for field in fields if not field.get("item_from")]
    resolved: dict[str, Any] = {}
    preflight: dict[str, Any] | None = None
    if dynamic:
        references = sorted({str(field["item_from"]) for field in dynamic})
        direct_ids = {str(field.get("id")) for field in direct}
        unknown = [reference for reference in references if reference not in direct_ids]
        if unknown:
            raise ProfileProbeError(f"item_from sem campo direto: {unknown}")
        pre_request = {
            "schema": REQUEST_SCHEMA,
            "project_id": project_id,
            "obra": obra,
            "pav": pav,
            "question": f"Resolver entidades relacionadas para {probe_id}",
            "fields": direct,
            "checks": [
                {"id": f"resolve:{reference}", "op": "present", "left": reference}
                for reference in references
            ],
        }
        preflight = run_probe(
            con, pre_request, project_id=project_id, obra=obra, pav=pav, cache=cache,
        )
        pre_values = {row["id"]: row.get("value") for row in preflight.get("fields", [])}
        missing = [reference for reference in references if pre_values.get(reference) in (None, "", [], {})]
        if missing:
            return {
                "schema": RESULT_SCHEMA,
                "overall": "PENDENTE",
                "scope_authority": "field_checks_only; unresolved cross-class reference",
                "profile": {"class": profile["class"], "version": profile.get("version"), "probe": probe_id},
                "reason": f"referência cross-classe ausente: {', '.join(missing)}",
                "preflight": preflight,
            }
        for field in dynamic:
            reference = str(field.pop("item_from"))
            field["item"] = str(pre_values[reference])
            resolved[field["id"]] = {"item_from": reference, "item": field["item"]}

    final_request = {
        "schema": REQUEST_SCHEMA,
        "project_id": project_id,
        "obra": obra,
        "pav": pav,
        "question": str(rendered.get("question") or probe_id),
        "fields": [{key: value for key, value in field.items() if key != "item_from"} for field in fields],
        "checks": checks,
    }
    try:
        result = run_probe(
            con, final_request, project_id=project_id, obra=obra, pav=pav, cache=cache,
        )
    except ValueError as exc:
        # Uma referência resolvida no payload pode não ter sido materializada
        # na tabela cross-classe deste projeto. Isso é falta de evidência,
        # nunca autorização para inventar o vínculo nem erro fatal do ciclo.
        if not dynamic or "item ausente:" not in str(exc):
            raise
        return {
            "schema": RESULT_SCHEMA,
            "overall": "PENDENTE",
            "scope_authority": "field_checks_only; unresolved cross-class materialization",
            "reason": f"referência cross-classe não materializada: {exc}",
            "profile": {
                "class": profile["class"],
                "version": profile.get("version"),
                "probe": probe_id,
                "item": item,
                "resolved_cross_class": resolved,
            },
            "preflight": preflight,
        }
    result["profile"] = {
        "schema": PROFILE_SCHEMA,
        "class": profile["class"],
        "version": profile.get("version"),
        "probe": probe_id,
        "item": item,
        "variables": variables or {},
        "resolved_cross_class": resolved,
        "authority": profile.get("authority"),
        "manual_guides": profile.get("manual_guides", []),
    }
    if preflight is not None:
        result["profile"]["preflight_snapshots"] = preflight.get("snapshots", {})
    return result


def _parse_vars(rows: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        if "=" not in row:
            raise ProfileProbeError(f"--var exige CHAVE=VALOR: {row}")
        key, value = row.split("=", 1)
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Executa prova N1 específica usando perfil semântico da classe.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--profiles-root", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--classe", choices=("PIL", "LAJ", "FV", "LV"))
    parser.add_argument("--probe")
    parser.add_argument("--item")
    parser.add_argument("--var", action="append", default=[])
    parser.add_argument("--project-id")
    parser.add_argument(
        "--use-profile-sample", action="store_true",
        help="Usa explicitamente o project_id de exemplo do perfil; nunca é implícito.",
    )
    parser.add_argument("--obra")
    parser.add_argument("--pav")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.list:
        print(json.dumps(list_profiles(args.profiles_root), ensure_ascii=False, indent=2))
        return 0
    if not args.classe or not args.probe or not args.item:
        parser.error("--classe, --probe e --item são obrigatórios sem --list")
    profile = load_profile(args.classe, args.profiles_root)
    if args.use_profile_sample and (args.project_id or args.obra or args.pav):
        parser.error("--use-profile-sample não pode ser combinado com outro escopo")
    scope_project = (
        str((profile.get("sample") or {}).get("project_id") or "")
        if args.use_profile_sample else args.project_id
    )
    if not scope_project and not (args.obra and args.pav):
        parser.error("informe --project-id, --obra+--pav ou --use-profile-sample")
    with sqlite3.connect(args.db) as con:
        result = run_profile_probe(
            con, profile, probe_id=args.probe, item=args.item,
            variables=_parse_vars(args.var), project_id=scope_project,
            obra=args.obra, pav=args.pav,
            cache=ContentAddressedCache(args.cache_dir, enabled=not args.no_cache),
        )
    output = args.out or DEFAULT_REPORTS / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{args.classe}_{args.item}_{content_hash(args.probe)[:8]}.json"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"overall": result["overall"], "out": str(output)}, ensure_ascii=False))
    return 0 if result["overall"] == "PASS" else 1 if result["overall"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
