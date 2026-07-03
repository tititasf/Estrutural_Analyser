#!/usr/bin/env python
"""Diagnóstico numérico headless entre as laterais de viga (LV) N1 e N2.

Mesmo padrão de `diagnostico_fv_n1_n2.py`/`diagnostico_pil_n1_n2.py`: lê o
estado N1 já exportado pelo `headless_sa_analise.py` (sem depender de UI
aberta), compara contra a ficha N2 (`reverse_eng_fichas`) e grava um
relatório JSON + JSONL versionado por obra/pavimento/run — schema v2 de
`docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` §4.

Comparação é por VIGA, não por lado (ver `docs/ARETE-LOOP-PROCEDIMENTO-
GERAL.md` §5.2 — a ficha N2 de LV é uma por viga, com `panels_A`/`panels_B`
juntos; os DXFs N3/N4 são por lado, mas isso não afeta esta comparação
numérica, só a ficha visual).

## Por que o metodo de comparação aqui é diferente de PIL/FV (leia antes de mexer)

O campo `width` de cada segmento N1 (`self._segment_data`/estado headless)
vem como uma STRING composta tipo `"19/55"` — dois números concatenados,
não um valor único. A ordem NÃO é estável: a maioria das vigas do 13_PAV
mostra `"{b}/{h}"` (largura da seção / altura), mas pelo menos uma
(`V308`, verificado com dado real) mostra `"{h}/{b}"` invertido. Por isso
esta comparação usa **conjunto de números, não posição**: extrai os dois
números de cada string N1 (ignorando qual é largura/qual é altura) e
verifica se cada um aparece (dentro de tolerância) em QUALQUER um dos
campos numéricos candidatos do N2 (`total_width`, `h_section`,
`h_section_all`, mais as alturas de painel `panels_A[*].height1/height2`
e `panels_B[*].height1/height2`). Isso é deliberadamente permissivo — só
sinaliza divergência quando um número do N1 não aparece em NENHUM desses
campos do N2, o que reduz falso-positivo por causa da ambiguidade de ordem.

**Achado não resolvido (verificado com dado real, 03/07/2026):** em 14 das
30 vigas comparáveis do 13_PAV, o número `120` aparece no N1 (altura de
algum segmento) mas não aparece em NENHUM campo numérico da ficha N2
correspondente (nem `h_section`/`h_section_all`, nem alturas de painel).
Esse padrão é sistemático demais para ser coincidência, mas a causa não foi
determinada nesta sessão — pode ser (a) um valor-fallback nominal que o SA
usa quando não consegue ler a altura real do desenho, ou (b) um campo do
N2 que ainda não foi mapeado aqui. Por isso a causa-raiz usada é
`schema_gap` (não `extractor_bug` — não afirma que o motor está errado,
só que a correspondência de campos precisa de investigação humana), com
confiança 0.6 (sinal real, mas não conclusivo). NÃO promova isso para
`extractor_bug`/confiança alta sem investigar `motor_reverso_lv.py` e
confirmar contra pelo menos um recorte N2 lido visualmente.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    natural_key,
    resolve_state_path,
    same_pavimento,
    slug,
)

DEFAULT_DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_STATE_ROOT = SCRIPT_DIR / "html_fichas"
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "relatorios" / "diagnosticos_lv"

_LATERAL_KINDS = (
    "lateral_a_para", "lateral_b_para", "lateral_a_passa", "lateral_b_passa",
)
_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _numbers_from_text(value: Any) -> set[float]:
    numbers: set[float] = set()
    for raw in _NUMBER_RE.findall(str(value or "")):
        try:
            numbers.add(round(float(raw.replace(",", ".")), 1))
        except ValueError:
            continue
    return numbers


def load_n1_beams(state_path: str | Path) -> tuple[dict, dict[str, dict]]:
    path = Path(state_path)
    state = json.loads(path.read_text(encoding="utf-8"))
    segmentos = state.get("segmentos") or {}
    by_beam: dict[str, dict] = {}
    for kind in _LATERAL_KINDS:
        for segment in segmentos.get(kind) or []:
            if not isinstance(segment, dict):
                continue
            name = str(segment.get("beam_name") or "").strip().upper()
            if not name:
                continue
            entry = by_beam.setdefault(name, {
                "declared_numbers": set(),
                "segmentos_por_lado": {"A": 0, "B": 0},
                "kinds_presentes": set(),
            })
            entry["declared_numbers"] |= _numbers_from_text(segment.get("width"))
            side = str(segment.get("side") or "A").upper()
            entry["segmentos_por_lado"][side] = entry["segmentos_por_lado"].get(side, 0) + 1
            entry["kinds_presentes"].add(kind)

    beams: dict[str, dict] = {}
    for name, entry in by_beam.items():
        beams[name] = {
            "declared_numbers": sorted(entry["declared_numbers"]),
            "segmentos_lado_a": entry["segmentos_por_lado"].get("A", 0),
            "segmentos_lado_b": entry["segmentos_por_lado"].get("B", 0),
        }
    return state, beams


def _n2_candidate_numbers(campos: dict) -> set[float]:
    candidates: set[float] = set()
    for key in ("total_width", "h_section", "b_geom"):
        value = as_float(campos.get(key))
        if value is not None:
            candidates.add(round(value, 1))
    for value in campos.get("h_section_all") or []:
        parsed = as_float(value)
        if parsed is not None:
            candidates.add(round(parsed, 1))
    for side_key in ("panels_A", "panels_B"):
        for panel in campos.get(side_key) or []:
            if not isinstance(panel, dict):
                continue
            for height_key in ("height1", "height2"):
                parsed = as_float(panel.get(height_key))
                if parsed:
                    candidates.add(round(parsed, 1))
    return candidates


def load_n2_beams(
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
            "FROM reverse_eng_fichas WHERE obra_name=? AND classe='LV' "
            "ORDER BY id DESC",
            (obra,),
        ).fetchall()
    finally:
        connection.close()

    beams: dict[str, dict] = {}
    for row_id, item, row_pavimento, raw_json, status, confidence in rows:
        name = str(item or "").strip().upper()
        if not name or name in beams or not same_pavimento(str(row_pavimento or ""), pavimento):
            continue
        try:
            campos = json.loads(raw_json or "{}")
        except json.JSONDecodeError:
            continue
        beams[name] = {
            "candidate_numbers": sorted(_n2_candidate_numbers(campos)),
            "ficha_id": row_id,
            "status": status,
            "confianca_origem": as_float(confidence),
        }
    return beams


def diagnose_item(
    name: str,
    n1: dict | None,
    n2: dict | None,
    *,
    obra: str,
    pavimento: str,
    generated_at: str,
) -> dict:
    if n1 is None or n2 is None:
        cause = "schema_gap"
        description = (
            "Item presente apenas no N2; falta representação de lateral no estado N1."
            if n1 is None
            else "Item presente apenas no N1; falta ficha LV correspondente no N2."
        )
        confidence = 0.99
        quality = "INDETERMINADO"
        missing_numbers: list[float] = []
    else:
        n1_numbers = set(n1.get("declared_numbers") or [])
        n2_candidates = set(n2.get("candidate_numbers") or [])
        missing_numbers = sorted(
            number for number in n1_numbers
            if not any(abs(number - candidate) <= 0.5 for candidate in n2_candidates)
        )
        ratio_missing = (
            len(missing_numbers) / len(n1_numbers) if n1_numbers else 0.0
        )
        quality = classify_delta(ratio_missing if n1_numbers else None)
        if not missing_numbers:
            cause = None
            description = "Todas as dimensões declaradas no N1 aparecem em algum campo do N2."
            confidence = 0.85
        else:
            # schema_gap, não extractor_bug — ver docstring do módulo: a
            # correspondência de campos N1<->N2 para altura de segmento LV
            # ainda não foi validada por um humano lendo o recorte real.
            cause = "schema_gap"
            description = (
                f"Dimensão(ões) declarada(s) no N1 ({missing_numbers}) não aparece(m) "
                "em nenhum campo numérico da ficha N2 (total_width/h_section/"
                "h_section_all/panels_A|B.height). Pode ser valor-fallback do SA ou "
                "campo do N2 ainda não mapeado — requer leitura humana do recorte "
                "antes de virar fix de motor."
            )
            confidence = 0.6

    evidence = {
        "classificacao": quality,
        "numeros_ausentes_no_n2": missing_numbers,
        "n1": n1,
        "n2": n2,
    }
    return {
        "data": generated_at,
        "obra": obra,
        "pavimento": pavimento,
        "classe": "LV",
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
    state, n1_beams = load_n1_beams(resolved_state)
    n2_beams = load_n2_beams(db_path, obra, pavimento)
    generated_at = datetime.now(timezone.utc).isoformat()
    items = [
        diagnose_item(
            name,
            n1_beams.get(name),
            n2_beams.get(name),
            obra=obra,
            pavimento=pavimento,
            generated_at=generated_at,
        )
        for name in sorted(set(n1_beams) | set(n2_beams), key=natural_key)
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
            "n1_itens": len(n1_beams),
            "n2_itens": len(n2_beams),
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
    json_path = run_dir / "diagnostico_lv_n1_n2.json"
    jsonl_path = run_dir / "triagem_auto_lv.jsonl"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with jsonl_path.open("w", encoding="utf-8") as file:
        for item in alerts:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")
    return report, json_path, jsonl_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara numericamente laterais de viga N1×N2 sem abrir a UI"
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
