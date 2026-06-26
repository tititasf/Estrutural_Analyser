#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cad_pipeline_cli.py — CLI unificado do CAD-ANALYZER (CAD-12.1 / 12.2 / 12.3)
===============================================================================
Ponto de entrada único para todas as operações do pipeline.

Comandos:
  run        Processa uma obra E2E (pipeline + certificação)
  run-all    Processa todas as obras em paralelo
  certify    Certifica uma obra já processada
  status     Exibe STATUS_GLOBAL.json formatado
  onboard    Prepara nova obra (atalho para onboarding_obra.py)

Exemplos:
  python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/Obra_TREINO_21
  python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/Obra_TREINO_21 --pav "12 PAV"
  python scripts/cad_pipeline_cli.py run-all --data-dir DADOS-OBRAS --workers 3
  python scripts/cad_pipeline_cli.py certify --obra DADOS-OBRAS/Obra_TREINO_21
  python scripts/cad_pipeline_cli.py status --data-dir DADOS-OBRAS
  python scripts/cad_pipeline_cli.py status  (usa DADOS-OBRAS/ como default)
  python scripts/cad_pipeline_cli.py onboard --nome "Nova Obra" --dir /path/to/dxfs
  python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/Obra_TREINO_21 --dry-run
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import subprocess
import concurrent.futures
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR_DEFAULT = SCRIPT_DIR.parent.parent / "DADOS-OBRAS"  # D:/Agente-cad-PYSIDE/DADOS-OBRAS
STATUS_GLOBAL_FILE = "STATUS_GLOBAL.json"


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════════════════════

def _load_json(path: Path) -> dict | None:
    if not path or not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _run_script(script: str, args: list[str], capture: bool = False) -> tuple[int, str]:
    """Executa script Python. Retorna (returncode, output)."""
    cmd = [sys.executable, str(SCRIPT_DIR / script)] + args
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    else:
        result = subprocess.run(cmd)
        return result.returncode, ""


def _descobrir_pavimento_principal(obra_path: Path) -> str:
    """Tenta descobrir o pavimento principal de uma obra pelo pipeline_report."""
    fase8 = obra_path / "Fase-8_Revisao_Entrega"
    pr = _load_json(fase8 / "pipeline_report.json")
    if pr and pr.get("pavimento"):
        return pr["pavimento"]
    # Fallback: ler dxf_discovery.json
    disc = _load_json(obra_path.parent / "dxf_discovery.json")
    if disc:
        pavs = list((disc.get(obra_path.name) or {}).keys())
        if pavs:
            return pavs[0]
    return "12 PAV"


def _listar_obras(data_dir: Path) -> list[Path]:
    """Lista obras válidas (que têm Fase-1_Ingestao)."""
    obras = []
    for d in sorted(data_dir.iterdir()):
        if d.is_dir() and (d / "Fase-1_Ingestao").exists():
            obras.append(d)
    return obras


# ══════════════════════════════════════════════════════════════════════════════
# STATUS_GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

def _load_status_global(data_dir: Path) -> dict:
    p = data_dir / STATUS_GLOBAL_FILE
    d = _load_json(p)
    if d:
        return d
    return {"timestamp": None, "obras": {}, "total_obras": 0, "total_certificadas": 0}


def _update_status_global(data_dir: Path, obra_path: Path, pavimento: str,
                           score_fidelidade: float | None, certificado: bool):
    status = _load_status_global(data_dir)
    nome = obra_path.name
    obra_entry = status["obras"].get(nome, {
        "pavimentos_processados": [],
        "score_fidelidade": {},
        "certificado": False,
        "ultima_execucao": None,
    })
    if pavimento not in obra_entry["pavimentos_processados"]:
        obra_entry["pavimentos_processados"].append(pavimento)
    if score_fidelidade is not None:
        obra_entry["score_fidelidade"][pavimento] = score_fidelidade
    obra_entry["certificado"]      = certificado
    obra_entry["ultima_execucao"]  = datetime.now(timezone.utc).isoformat()
    status["obras"][nome]          = obra_entry
    status["timestamp"]            = datetime.now(timezone.utc).isoformat()
    status["total_obras"]          = len(status["obras"])
    status["total_certificadas"]   = sum(1 for v in status["obras"].values() if v.get("certificado"))
    _save_json(data_dir / STATUS_GLOBAL_FILE, status)


# ══════════════════════════════════════════════════════════════════════════════
# Comando: run
# ══════════════════════════════════════════════════════════════════════════════

def cmd_run(obra_path: Path, pavimento: str, dry_run: bool, force: bool) -> bool:
    """Processa uma obra E2E: pipeline → certificação → atualiza STATUS_GLOBAL."""
    print(f"\n{'═'*65}")
    print(f"  CAD-ANALYZER  run  — {obra_path.name} / {pavimento}")
    print(f"{'═'*65}")

    if not obra_path.exists():
        print(f"[ERRO] Obra não encontrada: {obra_path}")
        return False

    t0 = time.time()

    # ── Passo 1: pipeline_e2e.py ──────────────────────────────
    print("\n[1/2] Pipeline E2E ...")
    e2e_args = ["--obra", str(obra_path), "--pavimento", pavimento]
    if dry_run:
        e2e_args.append("--dry-run")
    if force:
        e2e_args.append("--force")

    rc, _ = _run_script("pipeline_e2e.py", e2e_args)
    pipeline_ok = rc == 0
    if not pipeline_ok and not dry_run:
        print(f"[WARN] pipeline_e2e.py retornou code={rc} — continuando para certificação")

    # ── Passo 2: certificar_obra.py ───────────────────────────
    print("\n[2/2] Certificação ...")
    cert_args = ["--obra", str(obra_path), "--pavimento", pavimento, "--run-all"]
    if dry_run:
        print(f"  [DRY-RUN] certificar_obra.py {' '.join(cert_args)}")
        cert_aprovado = True
    else:
        rc_cert, _ = _run_script("certificar_obra.py", cert_args)
        cert_aprovado = rc_cert == 0  # exit 0 = aprovado, 1 = reprovado

    # ── Score de fidelidade para STATUS_GLOBAL ────────────────
    score_fid = None
    if not dry_run:
        rel = _load_json(obra_path / "Fase-8_Revisao_Entrega" / "relatorio_fidelidade.json")
        if rel:
            score_fid = rel.get("score_global")

    # ── Atualizar STATUS_GLOBAL ───────────────────────────────
    if not dry_run:
        _update_status_global(obra_path.parent, obra_path, pavimento, score_fid, cert_aprovado)

    elapsed = time.time() - t0
    status  = "✅ APROVADO" if cert_aprovado else "❌ REPROVADO"
    print(f"\n[CONCLUÍDO] {obra_path.name} — {status}  ({elapsed:.0f}s)")
    return cert_aprovado


# ══════════════════════════════════════════════════════════════════════════════
# Comando: run-all
# ══════════════════════════════════════════════════════════════════════════════

def _run_obra_worker(args: tuple) -> tuple[str, bool, str]:
    """Worker para multiprocessing: retorna (nome_obra, sucesso, mensagem)."""
    obra_path, pavimento, dry_run, force = args
    try:
        ok = cmd_run(obra_path, pavimento, dry_run, force)
        return obra_path.name, ok, "OK" if ok else "REPROVADO"
    except Exception as ex:
        return obra_path.name, False, f"ERRO: {ex}"


def cmd_run_all(data_dir: Path, workers: int, dry_run: bool, force: bool) -> bool:
    """Processa todas as obras em data_dir em paralelo."""
    obras = _listar_obras(data_dir)
    if not obras:
        print(f"[ERRO] Nenhuma obra encontrada em {data_dir}")
        return False

    print(f"\n{'═'*65}")
    print(f"  CAD-ANALYZER  run-all  — {len(obras)} obras  /  workers={workers}")
    print(f"{'═'*65}")
    for o in obras:
        pav = _descobrir_pavimento_principal(o)
        print(f"  • {o.name} [{pav}]")

    if dry_run:
        print("\n[DRY-RUN] Listagem apenas — nenhuma execução real.")
        return True

    t0 = time.time()
    tasks = [
        (o, _descobrir_pavimento_principal(o), dry_run, force)
        for o in obras
    ]

    resultados = []
    if workers == 1:
        for task in tasks:
            resultados.append(_run_obra_worker(task))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_run_obra_worker, t): t[0].name for t in tasks}
            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result()
                    resultados.append(res)
                    status = "✅" if res[1] else "❌"
                    print(f"  {status} {res[0]}: {res[2]}")
                except Exception as ex:
                    nome = futures[fut]
                    resultados.append((nome, False, f"ERRO: {ex}"))
                    print(f"  ❌ {nome}: ERRO — {ex}")

    # Resumo final
    elapsed = time.time() - t0
    aprovadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"\n{'─'*65}")
    print(f"  Resultado: {aprovadas}/{len(obras)} aprovadas  ({elapsed:.0f}s total)")
    for nome, ok, msg in sorted(resultados):
        emoji = "✅" if ok else "❌"
        print(f"  {emoji} {nome}: {msg}")

    # STATUS_GLOBAL já foi atualizado por cada cmd_run
    print(f"\n[INFO] STATUS_GLOBAL.json atualizado em {data_dir / STATUS_GLOBAL_FILE}")
    return aprovadas == len(obras)


# ══════════════════════════════════════════════════════════════════════════════
# Comando: certify
# ══════════════════════════════════════════════════════════════════════════════

def cmd_certify(obra_path: Path, pavimento: str, run_all: bool) -> bool:
    """Certifica uma obra (sem re-executar o pipeline)."""
    print(f"\n{'═'*65}")
    print(f"  CAD-ANALYZER  certify  — {obra_path.name} / {pavimento}")
    print(f"{'═'*65}\n")

    if not obra_path.exists():
        print(f"[ERRO] Obra não encontrada: {obra_path}")
        return False

    cert_args = ["--obra", str(obra_path), "--pavimento", pavimento]
    if run_all:
        cert_args.append("--run-all")

    rc, _ = _run_script("certificar_obra.py", cert_args)
    aprovado = rc == 0

    # Atualizar STATUS_GLOBAL
    rel = _load_json(obra_path / "Fase-8_Revisao_Entrega" / "relatorio_fidelidade.json")
    score_fid = rel.get("score_global") if rel else None
    _update_status_global(obra_path.parent, obra_path, pavimento, score_fid, aprovado)

    return aprovado


# ══════════════════════════════════════════════════════════════════════════════
# Comando: status
# ══════════════════════════════════════════════════════════════════════════════

def cmd_status(data_dir: Path, verbose: bool):
    """Exibe STATUS_GLOBAL.json formatado + varredura de obras existentes."""
    status = _load_status_global(data_dir)
    obras_disco = _listar_obras(data_dir)

    # Enriquecer com obras que ainda não estão no STATUS_GLOBAL
    for o in obras_disco:
        if o.name not in status["obras"]:
            # Verificar se tem certificado
            cert_path = o / "Fase-8_Revisao_Entrega" / "CERTIFICADO_APROVADO.json"
            rep_path  = o / "Fase-8_Revisao_Entrega" / "CERTIFICADO_REPROVADO.json"
            cert_data = _load_json(cert_path) or _load_json(rep_path)
            pr        = _load_json(o / "Fase-8_Revisao_Entrega" / "pipeline_report.json")
            rel       = _load_json(o / "Fase-8_Revisao_Entrega" / "relatorio_fidelidade.json")
            status["obras"][o.name] = {
                "pavimentos_processados": [pr["pavimento"]] if pr and pr.get("pavimento") else [],
                "score_fidelidade": {pr["pavimento"]: rel.get("score_global")} if pr and rel else {},
                "certificado": cert_path.exists(),
                "ultima_execucao": (cert_data or {}).get("timestamp"),
                "_discovered": True,  # não está no STATUS_GLOBAL ainda
            }

    total   = len(status["obras"])
    certif  = sum(1 for v in status["obras"].values() if v.get("certificado"))
    process = sum(1 for v in status["obras"].values() if v.get("pavimentos_processados"))

    ts = status.get("timestamp") or "nunca"
    print(f"\n{'═'*65}")
    print(f"  CAD-ANALYZER  Status Dashboard")
    print(f"{'═'*65}")
    print(f"  Última atualização: {ts}")
    print(f"  Obras no disco     : {len(obras_disco)}")
    print(f"  Obras processadas  : {process}/{total}")
    print(f"  Certificadas       : {certif}/{total}")
    print(f"{'─'*65}")
    print(f"  {'Obra':<30} {'Pav':>6}  {'Score':>7}  {'Status':>12}")
    print(f"  {'─'*30}  {'─'*6}  {'─'*7}  {'─'*12}")

    for nome, d in sorted(status["obras"].items()):
        pavs   = d.get("pavimentos_processados", [])
        scores = d.get("score_fidelidade", {})
        cert   = d.get("certificado", False)
        pav_str   = pavs[0][:6] if pavs else "—"
        # Mostrar maior score entre pavimentos (certify pode ter re-rodado com pavimento diferente)
        score_val = max(scores.values()) if scores else None
        score_str = f"{score_val:.1f}" if score_val is not None else "—"
        new_flag  = " *" if d.get("_discovered") else ""
        if cert:
            status_str = "✅ CERTIFICADO"
        elif pavs:
            status_str = "⚠️  PROCESSADO"
        else:
            status_str = "○ PENDENTE"
        print(f"  {nome:<30} {pav_str:>6}  {score_str:>7}  {status_str:>12}{new_flag}")

    if verbose:
        print(f"\n  Detalhes por obra:")
        for nome, d in sorted(status["obras"].items()):
            print(f"\n  [{nome}]")
            for k, v in d.items():
                if not k.startswith("_"):
                    print(f"    {k}: {v}")

    print(f"\n  STATUS_GLOBAL: {data_dir / STATUS_GLOBAL_FILE}")
    print(f"  Para processar nova obra: cad_pipeline_cli.py run --obra DADOS-OBRAS/<nome>")
    print()


# ══════════════════════════════════════════════════════════════════════════════
# Comando: onboard
# ══════════════════════════════════════════════════════════════════════════════

def cmd_onboard(nome: str, src_dir: str | None, data_dir: Path, dry_run: bool) -> bool:
    """Atalho para onboarding_obra.py."""
    onboard_args = ["--nome", nome, "--data-dir", str(data_dir)]
    if src_dir:
        onboard_args += ["--dir", src_dir]
    if dry_run:
        onboard_args.append("--dry-run")

    rc, _ = _run_script("onboarding_obra.py", onboard_args)
    return rc == 0


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="cad_pipeline_cli.py",
        description="CAD-ANALYZER CLI unificado — Processamento, certificação e status de obras.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Processar uma obra completa (pipeline + certificação)
  python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/Obra_TREINO_21

  # Processar com pavimento específico
  python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/Obra_TREINO_21 --pav "12 PAV"

  # Ver o que seria executado sem executar
  python scripts/cad_pipeline_cli.py run --obra DADOS-OBRAS/Obra_TREINO_21 --dry-run

  # Processar todas as obras (2 em paralelo)
  python scripts/cad_pipeline_cli.py run-all --data-dir DADOS-OBRAS --workers 2

  # Certificar obra já processada
  python scripts/cad_pipeline_cli.py certify --obra DADOS-OBRAS/Obra_TREINO_21

  # Ver status de todas as obras
  python scripts/cad_pipeline_cli.py status --data-dir DADOS-OBRAS

  # Integrar nova obra
  python scripts/cad_pipeline_cli.py onboard --nome "Minha Obra" --dir D:/dxfs/minha-obra
""",
    )

    subparsers = parser.add_subparsers(dest="comando", required=True)

    # ── run ──
    p_run = subparsers.add_parser("run", help="Processa uma obra E2E (pipeline + certificação)")
    p_run.add_argument("--obra",      required=True, help="Path da obra. Ex: DADOS-OBRAS/Obra_TREINO_21")
    p_run.add_argument("--pav",       default=None,  help="Pavimento (detecta automaticamente se omitido)")
    p_run.add_argument("--dry-run",   action="store_true", help="Mostra o que seria executado")
    p_run.add_argument("--force",     action="store_true", help="Reprocessa mesmo se outputs já existem")

    # ── run-all ──
    p_all = subparsers.add_parser("run-all", help="Processa todas as obras em paralelo")
    p_all.add_argument("--data-dir",  default=str(DATA_DIR_DEFAULT), help=f"Diretório de obras (default: {DATA_DIR_DEFAULT})")
    p_all.add_argument("--workers",   type=int, default=2, help="Número de obras em paralelo (default: 2)")
    p_all.add_argument("--dry-run",   action="store_true")
    p_all.add_argument("--force",     action="store_true")

    # ── certify ──
    p_cert = subparsers.add_parser("certify", help="Certifica uma obra já processada")
    p_cert.add_argument("--obra",     required=True)
    p_cert.add_argument("--pav",      default=None)
    p_cert.add_argument("--run-all",  action="store_true", help="Força re-cálculo de fidelidade")

    # ── status ──
    p_status = subparsers.add_parser("status", help="Exibe status de todas as obras")
    p_status.add_argument("--data-dir", default=str(DATA_DIR_DEFAULT))
    p_status.add_argument("--verbose",  action="store_true")

    # ── onboard ──
    p_onb = subparsers.add_parser("onboard", help="Prepara nova obra para o pipeline")
    p_onb.add_argument("--nome",      required=True,  help="Nome da obra")
    p_onb.add_argument("--dir",       default=None,   help="Diretório com DXFs para copiar")
    p_onb.add_argument("--data-dir",  default=str(DATA_DIR_DEFAULT))
    p_onb.add_argument("--dry-run",   action="store_true")

    args = parser.parse_args()

    if args.comando == "run":
        obra_path = Path(args.obra).resolve()
        pavimento = args.pav or _descobrir_pavimento_principal(obra_path)
        ok = cmd_run(obra_path, pavimento, args.dry_run, args.force)
        sys.exit(0 if ok else 1)

    elif args.comando == "run-all":
        data_dir = Path(args.data_dir).resolve()
        ok = cmd_run_all(data_dir, args.workers, args.dry_run, args.force)
        sys.exit(0 if ok else 1)

    elif args.comando == "certify":
        obra_path = Path(args.obra).resolve()
        pavimento = args.pav or _descobrir_pavimento_principal(obra_path)
        ok = cmd_certify(obra_path, pavimento, getattr(args, "run_all", False))
        sys.exit(0 if ok else 1)

    elif args.comando == "status":
        data_dir = Path(args.data_dir).resolve()
        cmd_status(data_dir, args.verbose)
        sys.exit(0)

    elif args.comando == "onboard":
        data_dir = Path(args.data_dir).resolve()
        ok = cmd_onboard(args.nome, args.dir, data_dir, args.dry_run)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
