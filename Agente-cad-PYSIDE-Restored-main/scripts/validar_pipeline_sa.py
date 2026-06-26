"""
validar_pipeline_sa.py — Validação do Pipeline SA → Robôs
==========================================================
Verifica se os JSONs em Fase-4_Sincronizacao estão prontos para geração DXF/SCR.

Checks realizados:
  1. Todos os JSONs têm _sa_meta (passaram pelo SA)
  2. completude_pct >= threshold (default 80%)
  3. Campos required_nonzero têm valores válidos
  4. Nenhum robot-blocking: JSON corrompido ou vazio

Uso:
  python scripts/validar_pipeline_sa.py --obra DADOS-OBRAS/Obra_TREINO_1
  python scripts/validar_pipeline_sa.py --obra DADOS-OBRAS/Obra_TREINO_1 --threshold 90
  python scripts/validar_pipeline_sa.py --obra DADOS-OBRAS/Obra_TREINO_1 --tipo PL
"""

import json
import argparse
import sys
import io
from pathlib import Path

# Força UTF-8 no Windows (evita UnicodeEncodeError no cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ─── Schema de campos required com valor não-zero ────────────────────────────
REQUIRED_NONZERO = {
    "PL": {"comprimento", "largura", "altura"},
    "LV": {"total_width", "total_height"},
    "FV": {"total_width", "total_height"},
    "LJ": {"comprimento", "largura", "area_cm2"},
}

DIRS_TIPO = {
    "PL": "JSON_Pilares",
    "LV": "JSON_Vigas_Laterais",
    "FV": "JSON_Vigas_Fundo",
    "LJ": "JSON_Lajes",
}


def validate_json(path: Path, tipo: str, threshold: float) -> dict:
    """Valida um JSON individual. Retorna dict com resultado."""
    result = {
        "file": path.name,
        "tipo": tipo,
        "status": "OK",
        "issues": [],
        "completude_pct": None,
    }

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result["status"] = "ERRO"
        result["issues"].append(f"JSONDecodeError: {e}")
        return result
    except Exception as e:
        result["status"] = "ERRO"
        result["issues"].append(f"IOError: {e}")
        return result

    if not data:
        result["status"] = "WARN"
        result["issues"].append("JSON vazio (objeto {})")
        return result

    # Check 1: _sa_meta presente
    meta = data.get("_sa_meta")
    if not meta:
        result["status"] = "WARN"
        result["issues"].append("Sem _sa_meta — JSON não passou pelo SA (motor_fase4)")

    # Check 2: completude_pct
    if meta:
        pct = meta.get("completude_pct", 0)
        result["completude_pct"] = pct
        if pct < threshold:
            result["status"] = "WARN"
            result["issues"].append(f"completude_pct={pct}% < {threshold}% (threshold)")

    # Check 3: campos required_nonzero
    req = REQUIRED_NONZERO.get(tipo, set())
    for campo in req:
        val = data.get(campo)
        if val is None:
            result["status"] = "ERRO"
            result["issues"].append(f"Campo required ausente: {campo}")
        elif val in (0, 0.0, "", "0", "0.0"):
            result["status"] = "WARN" if result["status"] != "ERRO" else "ERRO"
            result["issues"].append(f"Campo required com valor zero/vazio: {campo}={val!r}")

    return result


def validate_obra(obra_path: Path, tipos: list, threshold: float) -> dict:
    """Valida todos os JSONs de Fase-4 da obra."""
    fase4 = obra_path / "Fase-4_Sincronizacao"
    if not fase4.exists():
        return {"error": f"Fase-4_Sincronizacao não existe em {obra_path}"}

    summary = {
        "obra": obra_path.name,
        "threshold": threshold,
        "tipos": {},
        "totals": {"ok": 0, "warn": 0, "erro": 0, "total": 0},
    }

    for tipo in tipos:
        dir_path = fase4 / DIRS_TIPO[tipo]
        if not dir_path.exists():
            summary["tipos"][tipo] = {"exists": False, "items": []}
            continue

        items = []
        for jf in sorted(dir_path.glob("*.json")):
            r = validate_json(jf, tipo, threshold)
            items.append(r)
            summary["totals"][r["status"].lower()] += 1
            summary["totals"]["total"] += 1

        ok_count = sum(1 for i in items if i["status"] == "OK")
        pcts = [i["completude_pct"] for i in items if i["completude_pct"] is not None]
        avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else None

        summary["tipos"][tipo] = {
            "exists": True,
            "count": len(items),
            "ok": ok_count,
            "avg_completude_pct": avg_pct,
            "items": items,
        }

    return summary


def print_report(summary: dict, verbose: bool = False):
    """Imprime o relatório de validação."""
    if "error" in summary:
        print(f"[ERRO] {summary['error']}")
        return 1

    print(f"\n{'='*60}")
    print(f"RELATÓRIO DE VALIDAÇÃO SA → ROBÔS")
    print(f"Obra: {summary['obra']} | Threshold: {summary['threshold']}%")
    print(f"{'='*60}")

    for tipo, info in summary["tipos"].items():
        if not info.get("exists"):
            print(f"\n  {tipo}: ⚠️  Diretório não existe")
            continue

        pct_str = f"completude_média={info['avg_completude_pct']}%" if info['avg_completude_pct'] is not None else "sem _sa_meta"
        ok_ratio = f"{info['ok']}/{info['count']}"
        status_icon = "✅" if info["ok"] == info["count"] else "⚠️"
        print(f"\n  {tipo} ({info['count']} itens) {status_icon}  OK={ok_ratio}  {pct_str}")

        if verbose:
            for item in info["items"]:
                if item["status"] != "OK" or verbose:
                    icon = {"OK": "  ✓", "WARN": "  ⚠", "ERRO": "  ✗"}[item["status"]]
                    pct = f" ({item['completude_pct']}%)" if item["completude_pct"] is not None else ""
                    print(f"    {icon} {item['file']}{pct}")
                    for issue in item["issues"]:
                        print(f"        → {issue}")
        else:
            # Mostrar apenas os que têm issues
            issues_items = [i for i in info["items"] if i["status"] != "OK"]
            for item in issues_items[:5]:
                icon = {"WARN": "  ⚠", "ERRO": "  ✗"}[item["status"]]
                pct = f" ({item['completude_pct']}%)" if item["completude_pct"] is not None else ""
                print(f"    {icon} {item['file']}{pct}")
                for issue in item["issues"]:
                    print(f"        → {issue}")
            if len(issues_items) > 5:
                print(f"    ... e mais {len(issues_items) - 5} com issues (use --verbose para ver todos)")

    t = summary["totals"]
    print(f"\n{'─'*60}")
    print(f"TOTAL: {t['total']} itens | ✅ OK={t['ok']} | ⚠️ WARN={t['warn']} | ✗ ERRO={t['erro']}")

    if t["erro"] > 0:
        print("STATUS: FALHOU — há erros críticos que bloqueiam geração DXF")
        return 1
    elif t["warn"] > 0:
        print("STATUS: ATENÇÃO — há avisos, mas DXF pode ser gerado com dados incompletos")
        return 0
    else:
        print("STATUS: OK — pipeline SA → Robôs pronto para geração DXF/SCR")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Valida pipeline SA → Robôs")
    parser.add_argument("--obra", required=True, help="Caminho da obra")
    parser.add_argument("--threshold", type=float, default=80.0,
                        help="Threshold mínimo de completude SA (default: 80)")
    parser.add_argument("--tipo", choices=["PL", "LV", "FV", "LJ"],
                        help="Validar apenas um tipo (default: todos)")
    parser.add_argument("--verbose", action="store_true",
                        help="Mostrar todos os itens, incluindo os OK")
    args = parser.parse_args()

    obra_path = Path(args.obra)
    if not obra_path.exists():
        print(f"[ERRO] Obra não encontrada: {obra_path}")
        sys.exit(1)

    tipos = [args.tipo] if args.tipo else ["PL", "LV", "FV", "LJ"]
    summary = validate_obra(obra_path, tipos, args.threshold)
    exit_code = print_report(summary, verbose=args.verbose)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
