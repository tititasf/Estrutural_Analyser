#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
relatorio_fidelidade.py — Relatório consolidado de fidelidade do pipeline (CAD-10.5)
======================================================================================
Lê os 3 JSONs de fidelidade (pilares, vigas, lajes) + fontes auxiliares (validation_coletivo,
validation_bh, pipeline_report) e produz um relatório global ponderado.

Ponderação:
  score_global = 0.40 * pilares + 0.35 * vigas + 0.25 * lajes

Também executa os 3 scripts de fidelidade automaticamente se os JSONs não existirem.

Saída: Fase-8_Revisao_Entrega/relatorio_fidelidade.json

CLI:
  python scripts/relatorio_fidelidade.py --obra DADOS-OBRAS/Obra_TREINO_21
  python scripts/relatorio_fidelidade.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV" --run-fidelidade
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone


PESOS = {"pilares": 0.40, "vigas": 0.35, "lajes": 0.25}
META_GLOBAL = 0.80  # score_global >= 80 para relatorio aprovado


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as ex:
        print(f"  [WARN] Erro ao ler {path.name}: {ex}")
        return None


def _run_fidelidade(obra_path: Path, pavimento: str, tipo: str) -> bool:
    """Executa o script fidelidade_{tipo}.py e retorna True se OK."""
    scripts_dir = Path(__file__).parent
    script = scripts_dir / f"fidelidade_{tipo}.py"
    if not script.exists():
        print(f"  [WARN] Script não encontrado: {script}")
        return False
    cmd = [sys.executable, str(script), "--obra", str(obra_path), "--pavimento", pavimento]
    print(f"  [RUN] {script.name} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode not in (0, 1):  # 0=aprovado, 1=reprovado — ambos OK para nós
        print(f"  [ERRO] {script.name} falhou (exit={result.returncode})")
        if result.stderr:
            print(result.stderr[:500])
        return False
    return True


def _load_fontes_auxiliares(obra_path: Path) -> dict:
    """Carrega fontes auxiliares: validation_coletivo, validation_bh, pipeline_report."""
    fase6 = obra_path / "Fase-6_Execucao_CAD"
    fase8 = obra_path / "Fase-8_Revisao_Entrega"

    coletivo   = _load_json(fase6 / "validation_coletivo.json") or {}
    bh         = _load_json(obra_path / "Fase-3_Interpretacao_Extracao" / "validation_bh.json") or {}
    pr         = _load_json(fase8 / "pipeline_report.json") or {}

    return {
        "coletivo":        coletivo,
        "dimensional_bh":  bh,
        "pipeline_report": pr,
    }


def construir_relatorio(obra_path: Path, pavimento: str, run_fidelidade: bool) -> dict:
    fase7 = obra_path / "Fase-7_Consolidacao"
    tipos = ["pilares", "vigas", "lajes"]

    # Executar scripts se solicitado ou se JSON ausente
    for tipo in tipos:
        json_path = fase7 / f"fidelidade_{tipo}.json"
        if not json_path.exists() or run_fidelidade:
            print(f"\n[INFO] Executando fidelidade_{tipo}.py ...")
            _run_fidelidade(obra_path, pavimento, tipo)

    # Carregar JSONs de fidelidade
    fidelidade = {}
    for tipo in tipos:
        data = _load_json(fase7 / f"fidelidade_{tipo}.json")
        fidelidade[tipo] = data

    # Calcular score global ponderado
    scores_por_tipo = {}
    for tipo in tipos:
        d = fidelidade.get(tipo)
        if d and d.get("score") is not None:
            scores_por_tipo[tipo] = d["score"]

    if scores_por_tipo:
        soma   = sum(PESOS[t] * s for t, s in scores_por_tipo.items())
        peso_t = sum(PESOS[t] for t in scores_por_tipo)
        score_global = round(soma / peso_t, 1)
    else:
        score_global = 0.0

    meta_pct = META_GLOBAL * 100
    aprovado_global = score_global >= meta_pct

    # Fontes auxiliares
    fontes = _load_fontes_auxiliares(obra_path)

    # Itens abaixo do limiar
    abaixo_limiar = []
    for tipo in tipos:
        d = fidelidade.get(tipo)
        if d and not d.get("aprovado", True):
            abaixo_limiar.append({
                "tipo": tipo,
                "score": d.get("score"),
                "limiar": d.get("limiar"),
            })

    # Observações automáticas
    observacoes = []
    lajes_d = fidelidade.get("lajes", {})
    if lajes_d:
        id_d = lajes_d.get("detalhes", {}).get("id_match", {})
        missed = id_d.get("missed", [])
        if missed:
            observacoes.append(
                f"{len(missed)} laje(s) não extraídas pelo pipeline: {missed}. "
                "Causas conhecidas: lajes tipo L-N (só espessura), faixas estreitas."
            )

    vigas_d = fidelidade.get("vigas", {})
    if vigas_d:
        fv_r = (vigas_d.get("sub_tipos") or {}).get("FV", {})
        if fv_r and not fv_r.get("aprovado", True):
            observacoes.append(
                f"Vigas fundo (FV) abaixo do limiar ({fv_r.get('score')}/{fv_r.get('limiar')}). "
                "FV_gerado usa ezdxf simplificado — sarrafos e chanfros incompletos."
            )

    coletivo_d = fontes["coletivo"]
    coletivo_score = coletivo_d.get("score_global_percent")
    if coletivo_score and coletivo_score >= 95.0:
        observacoes.append(f"Score coletivo (IDs): {coletivo_score}% ≥ 95% — pipeline de IDs aprovado.")

    relatorio = {
        "obra": obra_path.name,
        "pavimento": pavimento,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fidelidade": {
            tipo: {
                "score": (fidelidade.get(tipo) or {}).get("score"),
                "aprovado": (fidelidade.get(tipo) or {}).get("aprovado"),
                "limiar": (fidelidade.get(tipo) or {}).get("limiar"),
            }
            for tipo in tipos
        },
        "score_global": score_global,
        "meta": meta_pct,
        "certificado": aprovado_global,
        "abaixo_limiar": abaixo_limiar,
        "observacoes": observacoes,
        "fontes": {
            "coletivo_score_global": coletivo_score,
            "dimensional_bh": {
                "score_pct": (fontes["dimensional_bh"] or {}).get("score_percent"),
                "aprovado":  (fontes["dimensional_bh"] or {}).get("aprovado"),
            },
            "pipeline_report": {
                "status": (fontes["pipeline_report"] or {}).get("status"),
                "coletivo_global": ((fontes["pipeline_report"] or {}).get("scores") or {}).get("coletivo", {}).get("global"),
            },
        },
    }

    return relatorio


def imprimir_relatorio(r: dict):
    print(f"\n{'='*65}")
    print(f"  RELATÓRIO DE FIDELIDADE — {r['obra']} / {r['pavimento']}")
    print(f"{'='*65}")
    print(f"  {'Tipo':<12} {'Score':>8}  {'Limiar':>8}  {'Status':>10}")
    print(f"  {'-'*50}")
    for tipo, d in r["fidelidade"].items():
        s = d.get("score")
        l = d.get("limiar")
        a = d.get("aprovado")
        score_str  = f"{s:.1f}/100" if s is not None else "N/A"
        limiar_str = f">={l}" if l else "-"
        status_str = "✅ PASS" if a else ("❌ FAIL" if a is False else "—")
        print(f"  {tipo:<12} {score_str:>8}  {limiar_str:>8}  {status_str:>10}")
    print(f"  {'-'*50}")
    print(f"  {'GLOBAL':<12} {r['score_global']:.1f}/100  {'>='+str(r['meta']):>8}  {'✅ APROVADO' if r['certificado'] else '❌ REPROVADO':>10}")
    print(f"\n  Fontes auxiliares:")
    f = r["fontes"]
    cq = f.get("coletivo_score_global")
    bh = f.get("dimensional_bh", {})
    pr = f.get("pipeline_report", {})
    if cq:
        print(f"    Coletivo IDs:   {cq}%")
    if bh.get("score_pct") is not None:
        print(f"    Dimensional B/H: {bh['score_pct']}%  {'✅' if bh.get('aprovado') else '❌'}")
    if pr.get("status"):
        print(f"    Pipeline E2E:    {pr['status']}")
    if r["observacoes"]:
        print(f"\n  ℹ️  Observações:")
        for obs in r["observacoes"]:
            print(f"    • {obs}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Relatório consolidado de fidelidade (CAD-10.5)")
    parser.add_argument("--obra",            required=True)
    parser.add_argument("--pavimento",       default="12 PAV")
    parser.add_argument("--run-fidelidade",  action="store_true",
                        help="Força re-execução dos scripts fidelidade_*.py")
    parser.add_argument("--out",             default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    if not obra_path.exists():
        print(f"[ERRO] Obra não encontrada: {obra_path}")
        sys.exit(1)

    relatorio = construir_relatorio(obra_path, args.pavimento, args.run_fidelidade)
    imprimir_relatorio(relatorio)

    # Salvar
    out_dir = obra_path / "Fase-8_Revisao_Entrega"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / "relatorio_fidelidade.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)
    print(f"[INFO] Relatório salvo em: {out_path}")

    sys.exit(0 if relatorio["certificado"] else 1)


if __name__ == "__main__":
    main()
