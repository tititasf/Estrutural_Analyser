#!/usr/bin/env python
"""Diagnóstico numérico headless entre os pilares N1 e N2.

Mesmo padrão de `diagnostico_fv_n1_n2.py` (primeira implementação, classe
FV): lê o estado N1 já exportado pelo `headless_sa_analise.py` (sem depender
de UI aberta), compara contra a ficha N2 (`reverse_eng_fichas`) e grava um
relatório JSON + JSONL versionado por obra/pavimento/run — schema v2 de
`docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md` §4, pronto para entrar no log de
triagem com `marcado_por: "auto"`.

Peculiaridade de PIL (sem equivalente em FV/LAJ): pilares não-retangulares
(`em L`, `em U`, `Circular`, `Especial` — ver `_pilar_formato`) têm bbox que
não corresponde diretamente a `comprimento`/`largura` do N2 (esses campos
descrevem a seção retangular padrão, não a bounding box de uma planta em L).
Por isso o diagnóstico numérico de dimensão só abre alerta para pilares
`Retangular`; os demais são registrados com `causa_raiz: null` e a evidência
de formato, para não gerar falso-positivo por comparação inválida — fica
como TODO explícito (ver `causa_descricao` de cada item não-retangular) para
uma extensão futura por face/parte, não uma omissão silenciosa.
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

# `_pilar_formato` abaixo é uma reimplementação PURA (sem Qt) da função de
# mesmo nome em pre_validation_dialog.py — ver docstring da função — por isso
# este script NÃO precisa de QT_QPA_PLATFORM/offscreen nem de importar
# nenhum módulo PySide6. sys.path só é ajustado para o import absoluto do
# helper compartilhado abaixo.
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
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "relatorios" / "diagnosticos_pil"

_FACE_SLOTS = "ABCDEFGH"


def _pilar_formato(points: list) -> str:
    """Reimplementação mínima de `_pilar_formato`
    (src/ui/widgets/pre_validation_dialog.py) — evita importar o módulo
    inteiro (widgets Qt pesados) só por uma função geométrica pura. Mesma
    lógica: remove vértice de fechamento + colineares, classifica por
    contagem de vértices limpos. Mantida em paridade manual; se a lógica de
    origem mudar, replicar aqui também."""
    if not points:
        return "Especial"
    try:
        clean = list(points)
        if len(clean) > 1:
            if (abs(float(clean[0][0]) - float(clean[-1][0])) < 0.5
                    and abs(float(clean[0][1]) - float(clean[-1][1])) < 0.5):
                clean = clean[:-1]

        changed = True
        while changed and len(clean) > 3:
            changed = False
            new: list = []
            count = len(clean)
            for i in range(count):
                p0 = clean[(i - 1) % count]
                p1 = clean[i]
                p2 = clean[(i + 1) % count]
                vert = (abs(float(p0[0]) - float(p1[0])) < 0.5
                        and abs(float(p1[0]) - float(p2[0])) < 0.5)
                horiz = (abs(float(p0[1]) - float(p1[1])) < 0.5
                         and abs(float(p1[1]) - float(p2[1])) < 0.5)
                if vert or horiz:
                    changed = True
                else:
                    new.append(p1)
            clean = new or clean
        n = len(clean)
        if n == 4:
            return "Retangular"
        if n == 6:
            return "em L"
        if n == 8:
            return "em U"
        if n >= 8:
            cx = sum(float(p[0]) for p in clean) / n
            cy = sum(float(p[1]) for p in clean) / n
            dists = [((float(p[0]) - cx) ** 2 + (float(p[1]) - cy) ** 2) ** 0.5 for p in clean]
            mean_d = sum(dists) / n
            if mean_d > 0:
                variance = sum((d - mean_d) ** 2 for d in dists) / n
                cv = (variance ** 0.5) / mean_d
                if cv < 0.15:
                    return "Circular"
        return "Especial"
    except Exception:
        return "Especial"


def _bbox_dims(bbox: list | tuple | None) -> tuple[float, float] | tuple[None, None]:
    if not bbox or len(bbox) != 4:
        return None, None
    try:
        minx, miny, maxx, maxy = (float(v) for v in bbox)
        return maxx - minx, maxy - miny
    except (TypeError, ValueError):
        return None, None


def _faces_preenchidas_n1(pillar: dict) -> int:
    count = 0
    for slot in _FACE_SLOTS:
        value = str(pillar.get(f"lado_{slot}") or "").strip().casefold()
        if value and value != "nulo":
            count += 1
    return count


def _faces_preenchidas_n2(campos: dict) -> int:
    count = 0
    for slot in _FACE_SLOTS:
        has_height = any(
            as_float(campos.get(f"h{i}_{slot}")) not in (None, 0.0)
            for i in range(1, 6)
        )
        has_width = any(
            as_float(campos.get(f"larg{i}_{slot}")) not in (None, 0.0)
            for i in range(1, 4)
        )
        if has_height or has_width:
            count += 1
    return count


def load_n1_pillars(state_path: str | Path) -> tuple[dict, dict[str, dict]]:
    path = Path(state_path)
    state = json.loads(path.read_text(encoding="utf-8"))
    pillars: dict[str, dict] = {}
    for item in state.get("pilares") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("key") or "").strip().upper()
        if not name:
            continue
        width, height = _bbox_dims(item.get("bbox"))
        pillars[name] = {
            "formato": _pilar_formato(item.get("points") or []),
            "largura_bbox": width,
            "comprimento_bbox": height,
            "classification": item.get("classification"),
            "faces_preenchidas": _faces_preenchidas_n1(item),
        }
    return state, pillars


def load_n2_pillars(
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
            "FROM reverse_eng_fichas WHERE obra_name=? AND classe='PIL' "
            "ORDER BY id DESC",
            (obra,),
        ).fetchall()
    finally:
        connection.close()

    pillars: dict[str, dict] = {}
    for row_id, item, row_pavimento, raw_json, status, confidence in rows:
        name = str(item or "").strip().upper()
        if not name or name in pillars or not same_pavimento(str(row_pavimento or ""), pavimento):
            continue
        try:
            campos = json.loads(raw_json or "{}")
        except json.JSONDecodeError:
            continue
        pillars[name] = {
            "comprimento": as_float(campos.get("comprimento")),
            "largura": as_float(campos.get("largura")),
            "faces_preenchidas": _faces_preenchidas_n2(campos),
            "ficha_id": row_id,
            "status": status,
            "confianca_origem": as_float(confidence),
        }
    return pillars


def diagnose_item(
    name: str,
    n1: dict | None,
    n2: dict | None,
    *,
    obra: str,
    pavimento: str,
    generated_at: str,
) -> dict:
    formato = (n1 or {}).get("formato")
    dim_delta = footprint_delta(
        (n1 or {}).get("largura_bbox"),
        (n1 or {}).get("comprimento_bbox"),
        (n2 or {}).get("comprimento"),
        (n2 or {}).get("largura"),
    )
    quality = classify_delta(dim_delta)
    # `faces_preenchidas` NÃO entra na árvore de decisão de causa: no N1,
    # `lado_A..H` é semântica de vizinhança de laje (o que encosta em cada
    # face); no N2, `hN_X`/`largN_X` é dimensão de painel de fôrma por face
    # — conceitos diferentes que uma ficha completa e uma incompleta podem
    # preencher em proporções completamente diferentes sem que isso seja bug
    # nenhum. Comparar os dois como "faces_match" seria o mesmo erro do caso
    # L318 documentado em ARETE-LOOP-PROCEDIMENTO-GERAL.md §7: diagnosticar
    # a partir de uma comparação que não é logicamente equivalente. Mantido
    # só como par de contagens informativas na evidência, não como gatilho
    # de causa — requer o Mapa de Equivalência de Vocabulário (GAP #V do
    # MASTERPLAN-LOOP-TREINO-MOTOR.md) para virar comparação válida.

    if n1 is None or n2 is None:
        cause = "schema_gap"
        description = (
            "Item presente apenas no N2; falta representação de pilar no estado N1."
            if n1 is None
            else "Item presente apenas no N1; falta ficha PIL correspondente no N2."
        )
        confidence = 0.99
    elif formato != "Retangular":
        # Bounding box de planta em L/U/circular/especial não corresponde a
        # comprimento×largura do N2 (que descreve a seção retangular padrão)
        # — comparar as duas seria falso-positivo garantido. Registrado como
        # fora de escopo, não como "sem divergência" (são coisas diferentes):
        # uma extensão futura por face/parte poderia julgar esses casos, mas
        # não com o footprint bbox usado aqui.
        cause = None
        description = (
            f"Pilar não-retangular (formato detectado: {formato}) — bbox não é "
            "comparável a comprimento/largura do N2 nesta primeira versão do "
            "diagnóstico automático; fora de escopo, não avaliado."
        )
        confidence = 0.3
    elif quality in {"REGULAR", "RUIM"}:
        cause = "extractor_bug"
        description = (
            "Dimensões do pilar (comprimento×largura) divergem entre a "
            "interpretação N1 (bbox) e a ficha N2."
        )
        confidence = 0.95 if quality == "RUIM" else 0.85
    else:
        cause = None
        description = "Sem divergência numérica relevante entre N1 e N2."
        confidence = 0.98 if quality == "EXCELENTE" else 0.90

    evidence = {
        "formato": formato,
        "classificacao": quality,
        "dim_delta": dim_delta,
        "faces_preenchidas_n1": (n1 or {}).get("faces_preenchidas"),
        "faces_preenchidas_n2": (n2 or {}).get("faces_preenchidas"),
        "n1": n1,
        "n2": n2,
    }
    return {
        "data": generated_at,
        "obra": obra,
        "pavimento": pavimento,
        "classe": "PIL",
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
    state, n1_pillars = load_n1_pillars(resolved_state)
    n2_pillars = load_n2_pillars(db_path, obra, pavimento)
    generated_at = datetime.now(timezone.utc).isoformat()
    items = [
        diagnose_item(
            name,
            n1_pillars.get(name),
            n2_pillars.get(name),
            obra=obra,
            pavimento=pavimento,
            generated_at=generated_at,
        )
        for name in sorted(set(n1_pillars) | set(n2_pillars), key=natural_key)
    ]
    quality_counts = Counter(item["evidencia"]["classificacao"] for item in items)
    fora_de_escopo = [
        item for item in items
        if item["causa_raiz"] is None and item["evidencia"]["formato"] not in (None, "Retangular")
    ]
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
            "n1_itens": len(n1_pillars),
            "n2_itens": len(n2_pillars),
            "alertas": len(alerts),
            "fora_de_escopo_nao_retangular": len(fora_de_escopo),
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
    json_path = run_dir / "diagnostico_pil_n1_n2.json"
    jsonl_path = run_dir / "triagem_auto_pil.jsonl"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with jsonl_path.open("w", encoding="utf-8") as file:
        for item in alerts:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")
    return report, json_path, jsonl_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara numericamente pilares N1×N2 sem abrir a UI"
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
