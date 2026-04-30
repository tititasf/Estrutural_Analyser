#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
teste_reproducibilidade.py — Teste de determinismo do pipeline CAD-ANALYZER (CAD-11.2)
========================================================================================
Executa certificar_obra.py 3× consecutivos e verifica que os resultados são idênticos.

Métricas verificadas:
  - Score global de fidelidade (deve ser idêntico)
  - Status de cada critério C1-C8 (PASS/FAIL idênticos)
  - APROVADO/REPROVADO idêntico

Saída: Fase-8_Revisao_Entrega/teste_reproducibilidade.json

CLI:
  python scripts/teste_reproducibilidade.py --obra DADOS-OBRAS/Obra_TREINO_21
  python scripts/teste_reproducibilidade.py --obra DADOS-OBRAS/Obra_TREINO_21 --runs 5
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def _run_certificar(obra_path: Path) -> dict | None:
    """Executa certificar_obra.py e retorna o JSON gerado."""
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "certificar_obra.py"),
        "--obra", str(obra_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    # Ler o certificado gerado (APROVADO ou REPROVADO)
    fase8 = obra_path / "Fase-8_Revisao_Entrega"
    for fname in ("CERTIFICADO_APROVADO.json", "CERTIFICADO_REPROVADO.json"):
        p = fase8 / fname
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return None


def _extrair_snapshot(cert: dict) -> dict:
    """Extrai apenas os campos que devem ser determinísticos."""
    criterios = cert.get("criterios", {})
    snapshot = {
        "aprovado": cert.get("aprovado"),
        "criterios": {
            k: {
                "status": v.get("status"),
                "tipo": v.get("tipo"),
            }
            for k, v in criterios.items()
        },
    }

    # Score de fidelidade global (arredondado para 1 decimal para evitar float noise)
    score_raw = cert.get("score_fidelidade_global")
    if score_raw is not None:
        snapshot["score_fidelidade_global"] = round(float(score_raw), 1)

    # Scores C1 e C5 (numéricos críticos)
    for cid in ("C1_ids_match", "C5_dxf_coletivo", "C2_dimensional_bh"):
        if cid in criterios:
            sc = criterios[cid].get("score")
            if sc is not None:
                snapshot["criterios"][cid]["score"] = round(float(sc), 1)

    return snapshot


def _snapshots_identicos(snaps: list[dict]) -> tuple[bool, list[str]]:
    """Verifica se todos os snapshots são idênticos. Retorna (ok, diffs)."""
    if len(snaps) < 2:
        return True, []

    ref = snaps[0]
    diffs = []

    for i, snap in enumerate(snaps[1:], start=2):
        # aprovado
        if snap.get("aprovado") != ref.get("aprovado"):
            diffs.append(f"Run {i}: aprovado={snap.get('aprovado')} != ref={ref.get('aprovado')}")

        # score global
        if snap.get("score_fidelidade_global") != ref.get("score_fidelidade_global"):
            diffs.append(
                f"Run {i}: score_global={snap.get('score_fidelidade_global')} "
                f"!= ref={ref.get('score_fidelidade_global')}"
            )

        # critérios
        for cid, ref_c in ref.get("criterios", {}).items():
            snap_c = snap.get("criterios", {}).get(cid, {})
            if snap_c.get("status") != ref_c.get("status"):
                diffs.append(
                    f"Run {i} {cid}: status={snap_c.get('status')} != ref={ref_c.get('status')}"
                )
            if "score" in ref_c and snap_c.get("score") != ref_c.get("score"):
                diffs.append(
                    f"Run {i} {cid}: score={snap_c.get('score')} != ref={ref_c.get('score')}"
                )

    return len(diffs) == 0, diffs


def main():
    parser = argparse.ArgumentParser(description="Teste de reproducibilidade — CAD-ANALYZER (CAD-11.2)")
    parser.add_argument("--obra",  required=True,  help="Path da obra")
    parser.add_argument("--runs",  type=int, default=3, help="Número de execuções (default=3)")
    parser.add_argument("--out",   default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra).resolve()
    if not obra_path.exists():
        print(f"[ERRO] Obra não encontrada: {obra_path}")
        sys.exit(1)

    print(f"\n{'═'*65}")
    print(f"  CAD-ANALYZER  Reproducibilidade  — {obra_path.name}")
    print(f"  Runs: {args.runs}")
    print(f"{'═'*65}\n")

    execucoes = []
    snapshots = []

    for i in range(1, args.runs + 1):
        print(f"[Run {i}/{args.runs}] Executando certificar_obra.py ...", flush=True)
        t0 = time.perf_counter()
        cert = _run_certificar(obra_path)
        elapsed = round(time.perf_counter() - t0, 2)

        if cert is None:
            print(f"  [ERRO] certificar_obra.py não retornou certificado válido")
            execucoes.append({"run": i, "ok": False, "elapsed_s": elapsed, "erro": "sem certificado"})
            continue

        snap = _extrair_snapshot(cert)
        snapshots.append(snap)
        aprovado = cert.get("aprovado", False)
        status = "✅ APROVADO" if aprovado else "❌ REPROVADO"
        score = cert.get("score_fidelidade_global", "—")
        print(f"  {status}  score={score}  ({elapsed}s)")

        exec_info = {
            "run": i,
            "ok": True,
            "elapsed_s": elapsed,
            "aprovado": aprovado,
            "score_fidelidade_global": score,
            "criterios_status": {
                k: v.get("status") for k, v in cert.get("criterios", {}).items()
            },
        }
        execucoes.append(exec_info)

    # Verificar determinismo
    print(f"\n[VERIFICAÇÃO] Comparando {len(snapshots)} execuções ...")
    deterministico, diffs = _snapshots_identicos(snapshots)

    print(f"\n{'─'*65}")
    if deterministico and len(snapshots) == args.runs:
        print(f"  ✅ DETERMINÍSTICO — {args.runs} runs idênticos")
        reproducivel = True
    elif not deterministico:
        print(f"  ❌ NÃO DETERMINÍSTICO — {len(diffs)} diferença(s):")
        for d in diffs:
            print(f"    - {d}")
        reproducivel = False
    else:
        print(f"  ⚠️  PARCIAL — {len(snapshots)}/{args.runs} runs completaram")
        reproducivel = False

    # Resultado
    resultado = {
        "obra": obra_path.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runs_solicitados": args.runs,
        "runs_completos": len(snapshots),
        "deterministico": deterministico,
        "reproducivel": reproducivel,
        "diferencas": diffs,
        "execucoes": execucoes,
        "snapshot_referencia": snapshots[0] if snapshots else None,
    }

    out_dir  = obra_path / "Fase-8_Revisao_Entrega"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / "teste_reproducibilidade.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    print(f"\n[INFO] Salvo em: {out_path}")

    # Tempo médio
    tempos = [e["elapsed_s"] for e in execucoes if e.get("ok")]
    if tempos:
        print(f"  Tempo médio por run: {round(sum(tempos)/len(tempos), 2)}s")

    print(f"{'═'*65}\n")
    sys.exit(0 if reproducivel else 1)


if __name__ == "__main__":
    main()
