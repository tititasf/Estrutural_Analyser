#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pos_batch_certify.py — Certificação pós-batch e atualização STATUS_GLOBAL.

Para cada pavimento APROVADO ou PARCIAL no batch_report.json:
  1. Executa certificar_obra.py
  2. Gera/atualiza STATUS_GLOBAL.json com os resultados de certificação

Usage:
  python scripts/pos_batch_certify.py --data-dir DADOS-OBRAS
  python scripts/pos_batch_certify.py --data-dir DADOS-OBRAS --include-parciais
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def _pav_slug(pavimento: str) -> str:
    """Converte nome do pavimento em slug seguro para nome de arquivo."""
    import re
    return re.sub(r'[^A-Za-z0-9_-]', '_', pavimento).strip('_')


def run_certify(obra_path: str, pavimento: str) -> dict:
    """Executa certificar_obra.py com diretório de saída específico por pavimento."""
    slug = _pav_slug(pavimento)
    out_dir = Path(obra_path) / "Fase-8_Revisao_Entrega" / f"cert_{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "certificar_obra.py"),
        "--obra", obra_path,
        "--pavimento", pavimento,
        "--run-all",
        "--out-dir", str(out_dir),
    ]
    try:
        result = subprocess.run(cmd, capture_output=False, check=False)
        return {"returncode": result.returncode, "aprovado": result.returncode == 0, "out_dir": str(out_dir)}
    except Exception as ex:
        return {"returncode": -1, "aprovado": False, "error": str(ex)}


def load_cert(obra_path: Path, pavimento: str) -> dict | None:
    """Carrega cert do diretório específico por pavimento, ou fallback no Fase-8."""
    slug = _pav_slug(pavimento)
    # Primeiro: diretório por pavimento (gerado por esta versão)
    pav_dir = obra_path / "Fase-8_Revisao_Entrega" / f"cert_{slug}"
    search_dirs = [pav_dir, obra_path / "Fase-8_Revisao_Entrega"]
    for fase8 in search_dirs:
        for fname in ["CERTIFICADO_APROVADO.json", "CERTIFICADO_REPROVADO.json"]:
            cert_path = fase8 / fname
            if cert_path.exists():
                try:
                    c = json.loads(cert_path.read_text(encoding='utf-8'))
                    # Verificar se é do pavimento correto
                    if c.get("pavimento") == pavimento or not c.get("pavimento"):
                        return c
                except Exception:
                    pass
    return None


def update_status_global(data_dir: Path, obras_dict: dict) -> None:
    """Atualiza STATUS_GLOBAL.json com resultados de certificação."""
    status_path = data_dir / "STATUS_GLOBAL.json"

    # Carregar status existente
    try:
        status = json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else {}
    except Exception:
        status = {}

    # Atualizar com novos resultados
    for obra_nome, pavimentos in obras_dict.items():
        if obra_nome not in status:
            status[obra_nome] = {}
        for pav, cert in pavimentos.items():
            if cert:
                status[obra_nome][pav] = {
                    "aprovado": cert.get("aprovado", False),
                    "score_global": cert.get("score_global"),
                    "timestamp": cert.get("timestamp", datetime.now().isoformat()),
                    "checks": cert.get("checks_summary", {}),
                }

    status["_updated"] = datetime.now().isoformat()
    status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n[STATUS_GLOBAL] Atualizado: {status_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--include-parciais', action='store_true',
                        help='Certificar tambem pavimentos PARCIAL score>=80pct')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    report_path = data_dir / "batch_report.json"

    if not report_path.exists():
        print(f"[ERROR] batch_report.json não encontrado em {data_dir}")
        sys.exit(1)

    with open(report_path, encoding='utf-8') as f:
        report = json.load(f)

    print(f"[INFO] batch_report.json: {report['timestamp']}")
    print(f"[INFO] Total: {report['total']} | Aprov: {report['aprovados']} | Parc: {report['parciais']}")

    # Selecionar pavimentos para certificar
    targets = []
    for res in report['resultados']:
        status = res['status']
        if status == 'APROVADO':
            targets.append(res)
        elif status == 'PARCIAL' and args.include_parciais:
            targets.append(res)

    print(f"[INFO] Certificando {len(targets)} pavimentos")

    obras_certs = {}
    aprovados = reprovados = erros = 0

    for res in targets:
        obra_nome = res['obra']
        pavimento = res['pavimento']
        obra_path = str(data_dir / obra_nome)

        print(f"\n  Certificando: {obra_nome} | {pavimento}")

        if args.dry_run:
            print(f"    [DRY-RUN] Pulando certificação")
            continue

        cert_result = run_certify(obra_path, pavimento)
        cert = load_cert(data_dir / obra_nome, pavimento)

        if cert:
            aprov = cert.get('aprovado', False)
            if aprov:
                aprovados += 1
                print(f"    -> CERTIFICADO APROVADO")
            else:
                reprovados += 1
                print(f"    -> CERTIFICADO REPROVADO")

            if obra_nome not in obras_certs:
                obras_certs[obra_nome] = {}
            obras_certs[obra_nome][pavimento] = cert
        else:
            erros += 1
            print(f"    -> ERRO: cert file não encontrado")

    print(f"\n{'='*60}")
    print(f"CERTIFICAÇÃO CONCLUÍDA")
    print(f"  Aprovados: {aprovados}")
    print(f"  Reprovados: {reprovados}")
    print(f"  Erros: {erros}")
    print(f"{'='*60}")

    if obras_certs and not args.dry_run:
        update_status_global(data_dir, obras_certs)


if __name__ == '__main__':
    main()
