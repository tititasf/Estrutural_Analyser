#!/usr/bin/env python
"""Diagnóstico numérico headless entre as lajes N1 e N2.

Substitui a versão legada presa à UI (`main.py::_debug_works_pavements_documents`,
~L14060-14204): aquela dependia de `self.slabs_found` (só existe com a app
aberta), comparava contra `projects_repo/{project_id}/laje_data/obras.json`
(cache paralelo/legado) e escrevia sempre no mesmo arquivo fixo
`debug_slab_pav13.json` (sobrescrevendo a cada rodada — não versiona por
obra/pavimento/run).

Esta versão segue o mesmo padrão headless/CLI de `diagnostico_pil_n1_n2.py`/
`diagnostico_fv_n1_n2.py`/`diagnostico_lv_n1_n2.py`:
- lê a geometria N1 do estado exportado por `headless_sa_analise.py`
  (`estado_*.json`, chave `slabs[].points` — precisou ser adicionada ao
  snapshot em `pre_validation_dialog.py::_export_html_snapshot`, antes só
  exportava name/nivel/height sem geometria);
- lê o gabarito N2 direto de `reverse_eng_fichas` (classe='LAJ'), não do
  cache `projects_repo/.../obras.json`;
- usa `diagnostico_common.footprint_delta` (extraída de
  `diagnostico_pil_n1_n2.py` — mesma fórmula de "melhor orientação" que já
  validou o bug do L318 nesta mesma classe, ver
  `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` §7).

## Sobre a distinção `n1_overlap_viga` vs `n1_overlap_laje` (NÃO resolvida aqui)

O ciclo de 02/07 (ver §7 do procedimento) mostrou que "laje invadindo viga
vizinha" e "laje invadindo outra laje" produzem o MESMO sintoma numérico
(dimensão de bbox errada) por causas gemetricamente diferentes. Este
diagnóstico NÃO tenta distinguir as duas — ele só aponta *que* a dimensão
diverge (`extractor_bug` genérico), com confiança mais baixa que PIL/FV
(0.7 em vez de 0.85/0.95) justamente por essa ambiguidade conhecida.
Diferenciar as causas exige olhar o desenho (vínculos de viga adjacente),
não só o número — use a leitura visual/SVG da ficha granular
(`lajes/{nome}.html`) para refinar a causa antes de virar fix de motor,
igual ao protocolo de `2A.3` do procedimento geral.

## Nota de nomenclatura (auditoria 03/07/2026): `laj` aqui, `lj` no checkbox

Este módulo usa `laj` (arquivo, pasta de saída, `causa`/`classe` no JSON) porque
é o valor exato de `reverse_eng_fichas.classe`. Já o checkbox de erro da ficha
granular (`preficha_laje_html.py::_error_marker_block`) usa `lj`, mesmo código
de `_find_beam_dxf("LJ", ...)`/arquivos `LJ_preview_*.dxf`. São duas convenções
pré-existentes e independentes — ver nota completa na docstring de
`_error_marker_block`. Não renomear nenhuma das duas: cada uma tem dado real
em produção (fichas no DB / marcações humanas em localStorage) que dependem
do nome atual.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = SCRIPT_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.arete.diagnostico_common import (  # noqa: E402
    as_float,
    classify_delta,
    footprint_delta,
    natural_key,
    resolve_state_path,
    same_pavimento,
    slug,
)

DEFAULT_DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_STATE_ROOT = SCRIPT_DIR / "html_fichas"
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "relatorios" / "diagnosticos_laj"


def _bbox_dims(points: list | None) -> tuple[float, float] | tuple[None, None]:
    clean: list[tuple[float, float]] = []
    for point in points or []:
        try:
            clean.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    if not clean:
        return None, None
    xs = [point[0] for point in clean]
    ys = [point[1] for point in clean]
    return max(xs) - min(xs), max(ys) - min(ys)


def load_n1_slabs(state_path: str | Path) -> tuple[dict, dict[str, dict]]:
    path = Path(state_path)
    state = json.loads(path.read_text(encoding="utf-8"))
    slabs: dict[str, dict] = {}
    for item in state.get("slabs") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().upper()
        if not name:
            continue
        width, height = _bbox_dims(item.get("points"))
        slabs[name] = {
            "largura_bbox": width,
            "comprimento_bbox": height,
            "nivel": item.get("nivel"),
            "vertices": len(item.get("points") or []),
        }
    return state, slabs


def load_n2_slabs(
    db_path: str | Path,
    obra: str,
    pavimento: str,
) -> dict[str, dict]:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"DB N2 não encontrado: {path}")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT id, elemento_id, pavimento, campos_json, status, confianca "
            "FROM reverse_eng_fichas WHERE obra_name=? AND classe='LAJ' "
            "ORDER BY id DESC",
            (obra,),
        ).fetchall()
    finally:
        connection.close()

    slabs: dict[str, dict] = {}
    for row_id, item, row_pavimento, raw_json, status, confidence in rows:
        name = str(item or "").strip().upper()
        if not name or name in slabs or not same_pavimento(str(row_pavimento or ""), pavimento):
            continue
        try:
            campos = json.loads(raw_json or "{}")
        except json.JSONDecodeError:
            continue
        slabs[name] = {
            "comprimento": as_float(campos.get("comprimento")),
            "largura": as_float(campos.get("largura")),
            "area_cm2": as_float(campos.get("area_cm2")),
            "ficha_id": row_id,
            "status": status,
            "confianca_origem": as_float(confidence),
        }
    return slabs


def diagnose_item(
    name: str,
    n1: dict | None,
    n2: dict | None,
    *,
    obra: str,
    pavimento: str,
    generated_at: str,
) -> dict:
    dim_delta = footprint_delta(
        (n1 or {}).get("largura_bbox"),
        (n1 or {}).get("comprimento_bbox"),
        (n2 or {}).get("comprimento"),
        (n2 or {}).get("largura"),
    )
    quality = classify_delta(dim_delta)

    if n1 is None or n2 is None:
        cause = "schema_gap"
        description = (
            "Item presente apenas no N2; falta representação de laje no estado N1."
            if n1 is None
            else "Item presente apenas no N1; falta ficha LAJ correspondente no N2."
        )
        confidence = 0.99
    elif quality in {"REGULAR", "RUIM"}:
        # Confiança mais baixa que PIL/FV (0.85/0.95) de propósito: o mesmo
        # sintoma numérico pode ser "laje sobre viga" ou "laje sobre laje
        # vizinha" (ver docstring do módulo) — não afirma qual é sem leitura
        # visual da ficha granular.
        cause = "extractor_bug"
        description = (
            "Dimensões da laje (bbox) divergem entre a interpretação N1 e a "
            "ficha N2. Causa ainda não diferenciada entre overlap com viga "
            "vizinha e overlap com laje vizinha — ler a ficha granular "
            "(lajes/{nome}.html) antes de decidir o fix."
        )
        confidence = 0.7 if quality == "RUIM" else 0.6
    else:
        cause = None
        description = "Sem divergência numérica relevante entre N1 e N2."
        confidence = 0.98 if quality == "EXCELENTE" else 0.90

    evidence = {
        "classificacao": quality,
        "dim_delta": dim_delta,
        "n1": n1,
        "n2": n2,
    }
    return {
        "data": generated_at,
        "obra": obra,
        "pavimento": pavimento,
        "classe": "LAJ",
        "item": name,
        "marcado_por": "auto",
        "nota_original": None,
        "causa_raiz": cause,
        "causa_descricao": description,
        "confianca": confidence,
        "evidencia": evidence,
        "campos_afetados": ["N1", "N2"],
        "concordancia": "pendente",
        "status": "aberto" if cause else "nao_reproduzido",
        "fix_aplicado": None,
        "verificado_em": None,
    }


def _run_id(state: dict) -> str:
    raw = str(state.get("gerado_em") or "")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        parsed = datetime.now()
    return parsed.strftime("%Y%m%d_%H%M%S")


def run_diagnostic(
    *,
    obra: str,
    pavimento: str,
    state_path: str | Path | None = None,
    state_root: str | Path = DEFAULT_STATE_ROOT,
    db_path: str | Path = DEFAULT_DB,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[dict, Path, Path]:
    resolved_state = resolve_state_path(obra, pavimento, state_path, state_root)
    state, n1_slabs = load_n1_slabs(resolved_state)
    n2_slabs = load_n2_slabs(db_path, obra, pavimento)
    generated_at = datetime.now(timezone.utc).isoformat()
    items = [
        diagnose_item(
            name,
            n1_slabs.get(name),
            n2_slabs.get(name),
            obra=obra,
            pavimento=pavimento,
            generated_at=generated_at,
        )
        for name in sorted(set(n1_slabs) | set(n2_slabs), key=natural_key)
    ]
    quality_counts = Counter(item["evidencia"]["classificacao"] for item in items)
    alerts = [item for item in items if item["causa_raiz"]]
    state_hash = hashlib.sha256(resolved_state.read_bytes()).hexdigest()
    report = {
        "schema_version": 2,
        "gerado_em": generated_at,
        "obra": obra,
        "pavimento": pavimento,
        "run_id": _run_id(state),
        "fontes": {
            "n1_estado": str(resolved_state),
            "n1_estado_sha256": state_hash,
            "n2_db": str(Path(db_path).resolve()),
        },
        "resumo": {
            "itens": len(items),
            "n1_itens": len(n1_slabs),
            "n2_itens": len(n2_slabs),
            "alertas": len(alerts),
            "classificacoes": dict(sorted(quality_counts.items())),
        },
        "itens": items,
    }

    run_dir = (
        Path(output_root)
        / slug(obra)
        / slug(pavimento)
        / report["run_id"]
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "diagnostico_laj_n1_n2.json"
    jsonl_path = run_dir / "triagem_auto_laj.jsonl"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with jsonl_path.open("w", encoding="utf-8") as file:
        for item in alerts:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")
    return report, json_path, jsonl_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara numericamente lajes N1×N2 sem abrir a UI"
    )
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav", default="13_PAV")
    parser.add_argument("--estado", default=None)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    report, json_path, jsonl_path = run_diagnostic(
        obra=args.obra,
        pavimento=args.pav,
        state_path=args.estado,
        db_path=args.db,
        output_root=args.output_root,
    )
    print(json.dumps(report["resumo"], ensure_ascii=False, indent=2))
    print(f"JSON:  {json_path}")
    print(f"JSONL: {jsonl_path}")
    sample = next((item for item in report["itens"] if item["causa_raiz"]), None)
    if sample:
        print("Amostra (alerta):")
        print(json.dumps(sample, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
