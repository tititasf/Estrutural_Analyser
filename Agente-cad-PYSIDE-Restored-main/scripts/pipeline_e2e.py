#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_e2e.py — Orquestrador E2E do pipeline CAD-ANALYZER.

Executa todas as fases do pipeline para uma obra/pavimento:
  1. Descoberta de DXFs (descobrir_obras.py)
  2. Engenharia reversa / ground truth (engenharia_reversa_dxf.py)
  3. Extração dimensional (extrair_bh_pilares.py, extrair_vigas_lv.py, etc.)
  4. Extração assembly (extrair_assembly_pl.py)
  5. Motor Fase 4 (motor_fase4.py)
  6. Geração DXF individual (gerar_dxf_pilares.py, vigas, lajes)
  7. Extração de âncoras (extrair_ancoras_dxf.py)
  8. Consolidação DXF coletivo (consolidar_dxf_pilares.py, vigas, lajes)
  9. Validação coletivo (validar_dxf_coletivo.py)
  10. Geração obras_salvas.json (gerar_obras_salvas.py)
  11. Relatório final (pipeline_report.json)

CLI:
  python scripts/pipeline_e2e.py --obra DADOS-OBRAS/Obra_TREINO_21
  python scripts/pipeline_e2e.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
  python scripts/pipeline_e2e.py --obra DADOS-OBRAS/Obra_TREINO_21 --dry-run
  python scripts/pipeline_e2e.py --obra DADOS-OBRAS/Obra_TREINO_21 --force  (reprocessa mesmo se output existe)
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def run_script(script_name: str, args_list: list, dry_run: bool = False) -> bool:
    """Executa um script Python. Retorna True se sucesso."""
    cmd = [sys.executable, str(SCRIPT_DIR / script_name)] + args_list
    if dry_run:
        print(f"  [DRY-RUN] {script_name} {' '.join(args_list)}")
        return True

    print(f"  [RUN] {script_name} ...")
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=False, check=False)
        elapsed = time.time() - t0
        ok = result.returncode == 0
        status = "OK" if ok else f"FALHOU (code {result.returncode})"
        print(f"        -> {status} ({elapsed:.1f}s)")
        return ok
    except Exception as ex:
        print(f"        -> ERRO: {ex}")
        return False


def output_exists(path: Path) -> bool:
    """Verifica se output já existe e não está vazio."""
    return path.exists() and path.stat().st_size > 10


def run_pipeline(obra_path: str, pavimento: str, dry_run: bool = False,
                 force: bool = False) -> dict:
    obra = Path(obra_path).resolve()
    obra_nome = obra.name
    fase3 = obra / "Fase-3_Interpretacao_Extracao"
    fase4 = obra / "Fase-4_Sincronizacao"
    fase5 = obra / "Fase-5_Geracao_Scripts"
    fase6 = obra / "Fase-6_Execucao_CAD"
    fase8 = obra / "Fase-8_Revisao_Entrega"

    print(f"\n{'='*60}")
    print(f"PIPELINE E2E — {obra_nome} | {pavimento}")
    print(f"{'='*60}\n")

    results = {
        "obra": obra_nome,
        "pavimento": pavimento,
        "timestamp": datetime.now().isoformat(),
        "fases": {},
        "scores": {},
        "status": "INICIANDO",
    }

    # ── Fase 1: Descoberta de DXFs ─────────────────────────────
    print("[FASE 1] Descoberta de DXFs")
    disc_path = obra.parent / "dxf_discovery.json"
    # Verificar se discovery existe E contém esta obra
    _disc_has_obra = False
    if output_exists(disc_path):
        try:
            import json as _json
            with open(disc_path, encoding='utf-8') as _f:
                _disc = _json.load(_f)
            _disc_has_obra = obra_nome in _disc
        except Exception:
            pass
    # Discovery: rodar apenas se arquivo nao existe ou nao contem esta obra
    # (force NAO re-roda discovery — ela e idempotente e lenta para batch)
    if not _disc_has_obra:
        ok = run_script("descobrir_obras.py", [
            "--data-dir", str(obra.parent),
        ], dry_run)
        results["fases"]["descoberta"] = "OK" if ok else "FALHOU"
    else:
        print(f"  [SKIP] dxf_discovery.json ja existe e contem {obra_nome}")
        results["fases"]["descoberta"] = "SKIP"

    # ── Fase 2: Engenharia Reversa / Ground Truth ──────────────
    print("\n[FASE 2] Engenharia Reversa (Ground Truth)")
    gt_pilares = fase3 / "Pilares" / "pilares_ground_truth.json"
    if not output_exists(gt_pilares) or force:
        ok = run_script("engenharia_reversa_dxf.py", [
            "--obra", str(obra),
            "--pavimento", pavimento
        ], dry_run)
        results["fases"]["eng_reversa"] = "OK" if ok else "FALHOU"
    else:
        print(f"  [SKIP] ground truth já existe")
        results["fases"]["eng_reversa"] = "SKIP"

    # ── Fase 3: Extração Dimensional ──────────────────────────
    print("\n[FASE 3] Extração Dimensional")
    bh_path = fase3 / "Pilares" / "pilares_bh.json"
    if not output_exists(bh_path) or force:
        for script, extra_args in [
            ("extrair_bh_pilares.py", []),
            ("extrair_vigas_lv.py", []),
            ("extrair_lajes_lj.py", []),
            ("extrair_poligono_lajes.py", []),
            ("extrair_garfos_evg.py", []),
            ("extrair_largura_vigas_fv.py", []),
            ("extrair_assembly_pl.py", []),
        ]:
            run_script(script, ["--obra", str(obra), "--pavimento", pavimento] + extra_args, dry_run)
        results["fases"]["extracao_dimensional"] = "OK"
    else:
        print(f"  [SKIP] dados dimensionais ja existem")
        results["fases"]["extracao_dimensional"] = "SKIP"
    # Integrar fichas sempre (cria vigas.json + lajes.json para motor_fase4)
    vigas_json = fase3 / "Vigas" / "vigas.json"
    lajes_json = fase3 / "Lajes" / "lajes.json"
    if not output_exists(vigas_json) or not output_exists(lajes_json) or force:
        run_script("integrar_fichas_fase3.py", ["--obra", str(obra)], dry_run)

    # ── Fase 4: Motor Fase 4 ───────────────────────────────────
    print("\n[FASE 4] Motor Fase 4 (Transformacao Fase-3 -> Fase-4)")
    json_pilares_dir = fase4 / "JSON_Pilares"
    json_vigas_dir = fase4 / "JSON_Vigas_Laterais"
    # Skip só se vigas ou pilares já processados (não apenas dir vazio)
    _fase4_done = (json_vigas_dir.exists() and any(json_vigas_dir.iterdir())) or \
                  (json_pilares_dir.exists() and any(json_pilares_dir.iterdir()))
    if not _fase4_done or force:
        # Limpar JSON dirs para evitar contaminacao multi-pav
        for json_subdir, prefix in [
            ("JSON_Pilares", "P"), ("JSON_Vigas_Laterais", "V"),
            ("JSON_Vigas_Fundo", "V"), ("JSON_Lajes", "L")
        ]:
            d = fase4 / json_subdir
            if d.exists():
                old_files = list(d.glob(f"{prefix}*.json"))
                if old_files:
                    print(f"  [CLEAN] Removendo {len(old_files)} JSONs antigos de {json_subdir}/")
                    for f in old_files:
                        f.unlink()
        ok = run_script("motor_fase4.py", [
            "--obra", str(obra),
            "--pavimento", pavimento,
        ], dry_run)
        results["fases"]["motor_fase4"] = "OK" if ok else "FALHOU"
    else:
        print(f"  [SKIP] Fase-4 já processada")
        results["fases"]["motor_fase4"] = "SKIP"

    # ── Fase 5: Geração DXF Individual ────────────────────────
    print("\n[FASE 5] Geração DXF Individual")
    dxf_pilares_dir = fase5 / "DXF_Pilares"
    dxf_vigas_dir = fase5 / "DXF_Vigas"
    dxf_lajes_dir = fase5 / "DXF_Lajes"
    _any_dxf_exists = any(d.exists() for d in [dxf_pilares_dir, dxf_vigas_dir, dxf_lajes_dir])
    if not _any_dxf_exists or force:
        # Limpar DXFs antigos de outros pavimentos antes de regenerar
        # Evita contaminacao multi-pav (V*.dxf de pavimentos anteriores ficam no dir)
        for dxf_dir, prefix in [(dxf_pilares_dir, "P"), (dxf_vigas_dir, "V"), (dxf_lajes_dir, "L")]:
            if dxf_dir.exists():
                old_files = list(dxf_dir.glob(f"{prefix}*.dxf"))
                if old_files:
                    print(f"  [CLEAN] Removendo {len(old_files)} DXFs antigos de {dxf_dir.name}/")
                    for f in old_files:
                        f.unlink()
        for script in ["gerar_dxf_pilares.py", "gerar_dxf_vigas.py", "gerar_dxf_lajes.py"]:
            run_script(script, ["--obra", str(obra), "--pav", pavimento], dry_run)
        results["fases"]["geracao_dxf_individual"] = "OK"
    else:
        print(f"  [SKIP] DXF_Pilares/ já existe")
        results["fases"]["geracao_dxf_individual"] = "SKIP"

    # ── Fase 5b: Comparação DXF Individual ────────────────────
    print("\n[FASE 5b] Comparação DXF Individual vs STOG")
    comparar_out = fase3 / "Pilares" / "validation_pilares.json"
    if not output_exists(comparar_out) or force:
        ok = run_script("comparar_dxf.py", [
            "--obra", str(obra)
        ], dry_run)
        results["fases"]["comparacao_individual"] = "OK" if ok else "FALHOU/SKIP"
    else:
        print(f"  [SKIP] comparação já existe")
        results["fases"]["comparacao_individual"] = "SKIP"

    # ── Fase 6: Extração de Âncoras ───────────────────────────
    print("\n[FASE 6] Extração de Âncoras (coords absolutas)")
    ancoras_path = fase3 / "ancoras_pilares.json"
    if not output_exists(ancoras_path) or force:
        ok = run_script("extrair_ancoras_dxf.py", [
            "--obra", str(obra),
            "--pavimento", pavimento
        ], dry_run)
        results["fases"]["ancoras"] = "OK" if ok else "FALHOU"
    else:
        print(f"  [SKIP] âncoras já existem")
        results["fases"]["ancoras"] = "SKIP"

    # ── Fase 7: Consolidação DXF Coletivo ─────────────────────
    print("\n[FASE 7] Consolidação DXF Coletivo")
    pl_gerado = fase6 / "PL_gerado.dxf"
    if not output_exists(pl_gerado) or force:
        for script in [
            "consolidar_dxf_pilares.py",
            "consolidar_dxf_vigas.py",
            "consolidar_dxf_lajes.py",
        ]:
            run_script(script, ["--obra", str(obra), "--pavimento", pavimento], dry_run)
        results["fases"]["consolidacao_coletivo"] = "OK"
    else:
        print(f"  [SKIP] DXFs coletivos já existem")
        results["fases"]["consolidacao_coletivo"] = "SKIP"

    # ── Fase 8: Validação DXF Coletivo ────────────────────────
    print("\n[FASE 8] Validação DXF Coletivo")
    ok = run_script("validar_dxf_coletivo.py", [
        "--obra", str(obra), "--pavimento", pavimento
    ], dry_run)
    results["fases"]["validacao_coletivo"] = "OK" if ok else "FALHOU"

    # ── Fase 9: obras_salvas.json ──────────────────────────────
    print("\n[FASE 9] Geração obras_salvas.json (formato robô)")
    obras_salvas = fase4 / "obras_salvas.json"
    if not output_exists(obras_salvas) or force:
        ok = run_script("gerar_obras_salvas.py", [
            "--obra", str(obra),
            "--pavimento", pavimento
        ], dry_run)
        results["fases"]["obras_salvas"] = "OK" if ok else "FALHOU"
    else:
        print(f"  [SKIP] obras_salvas.json já existe")
        results["fases"]["obras_salvas"] = "SKIP"

    # ── Carregar scores ────────────────────────────────────────
    coletivo_json = fase6 / "validation_coletivo.json"
    if coletivo_json.exists():
        with open(coletivo_json, encoding='utf-8') as f:
            coletivo = json.load(f)
        results["scores"]["coletivo"] = {
            "pilares": coletivo.get("elementos", {}).get("pilares", {}).get("score_percent"),
            "vigas": coletivo.get("elementos", {}).get("vigas", {}).get("score_percent"),
            "lajes": coletivo.get("elementos", {}).get("lajes", {}).get("score_percent"),
            "global": coletivo.get("score_global_percent"),
            "aprovado": coletivo.get("aprovado"),
        }

    # ── Determinar status final ────────────────────────────────
    score_g = results["scores"].get("coletivo", {}).get("global", 0) or 0
    fases_falhou = [f for f, s in results["fases"].items() if s == "FALHOU"]

    if not fases_falhou and score_g >= 95:
        results["status"] = "APROVADO"
    elif score_g >= 80:
        results["status"] = "PARCIAL"
    else:
        results["status"] = "REPROVADO"

    if fases_falhou:
        results["fases_falhou"] = fases_falhou

    # ── Salvar relatório ───────────────────────────────────────
    fase8.mkdir(parents=True, exist_ok=True)
    report_path = fase8 / "pipeline_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # ── Sumário final ──────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"PIPELINE CONCLUÍDO — {results['status']}")
    print(f"  Score coletivo: {score_g:.1f}%")
    if fases_falhou:
        print(f"  Fases com falha: {fases_falhou}")
    print(f"  Relatório: {report_path}")
    print(f"{'='*60}\n")

    return results


def main():
    parser = argparse.ArgumentParser(description='Orquestrador E2E do pipeline CAD-ANALYZER')
    parser.add_argument('--obra', required=True, help='Path da obra')
    parser.add_argument('--pavimento', default='12 PAV', help='Pavimento (default: "12 PAV")')
    parser.add_argument('--dry-run', action='store_true', help='Mostrar o que faria sem executar')
    parser.add_argument('--force', action='store_true', help='Reprocessar mesmo se outputs existem')
    args = parser.parse_args()

    results = run_pipeline(args.obra, args.pavimento, args.dry_run, args.force)

    # Exit code
    if results.get("status") == "APROVADO":
        sys.exit(0)
    elif results.get("status") == "PARCIAL":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == '__main__':
    main()
