#!/usr/bin/env python3
"""
scripts/export_training_data.py -- CAD-13
CLI: exporta dados de treino ML a partir do correction_log.json de uma obra.

Usage:
    python export_training_data.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1
    python export_training_data.py --obra ... --apply
    python export_training_data.py --obra ... --dry-run
    python export_training_data.py --obra ... --stats
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Permite rodar diretamente do diretório raiz do projeto
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def main() -> int:
    parser = argparse.ArgumentParser(
        description='CAD-13: Exporta dados de treino ML a partir do correction_log.json'
    )
    parser.add_argument('--obra', required=True, help='Caminho da obra (DADOS-OBRAS/...)')
    parser.add_argument('--apply', action='store_true',
                        help='Aplica correções do log de volta aos JSONs Fase-4')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simula exportação sem gravar arquivos')
    parser.add_argument('--stats', action='store_true',
                        help='Exibe apenas estatísticas (model insights)')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    if not obra_path.exists():
        print(f'[ERRO] Obra não encontrada: {obra_path}', file=sys.stderr)
        return 1

    try:
        from src.core.services.ml_feedback_service import MLFeedbackService
    except ImportError as e:
        print(f'[ERRO] MLFeedbackService indisponivel: {e}', file=sys.stderr)
        return 1

    svc = MLFeedbackService(obra_path)

    # ── Mode: stats only ─────────────────────────────────────────────────────
    if args.stats:
        insights = svc.get_model_insights()
        total = insights['total_corrections']
        print(f'\n=== Model Insights | Obra: {obra_path.name} ===')
        print(f'Total de correções registradas: {total}')
        for ins in insights['insights']:
            print(f'  • {ins}')
        if insights['accuracy_by_field']:
            print('\nDetalhes por campo:')
            for field, info in list(insights['accuracy_by_field'].items())[:15]:
                print(
                    f"  {field:<30} correções={info['corrections']:>3}  "
                    f"delta_med={info['avg_delta']}  "
                    f"itens_afetados={info['items_affected']}"
                )
        return 0

    # ── Mode: apply calibration ───────────────────────────────────────────────
    if args.apply:
        if args.dry_run:
            print('[DRY-RUN] Simulando calibração — nenhum arquivo será modificado.')
            insights = svc.get_model_insights()
            print(f"Correções disponíveis: {insights['total_corrections']}")
            return 0
        result = svc.apply_calibration()
        print(f"\n=== Calibração Aplicada ===")
        print(f"  Aplicados : {result.get('applied', 0)}")
        print(f"  Ignorados : {result.get('skipped', 0)}")
        if result.get('errors'):
            print(f"  Erros     : {len(result['errors'])}")
            for e in result['errors'][:5]:
                print(f"    - {e}")
        return 0

    # ── Mode: export training data (default) ─────────────────────────────────
    if args.dry_run:
        entries_raw = svc._load_log()
        print(f'[DRY-RUN] {len(entries_raw)} entradas no correction_log — nenhum arquivo escrito.')
        return 0

    result = svc.export_training_data()
    if result['entries'] == 0:
        print(f'[INFO] Nenhuma correção registrada em {obra_path.name} — nada exportado.')
        return 0

    print(f'\n=== Export Training Data | Obra: {obra_path.name} ===')
    print(f'  Entradas exportadas : {result["entries"]}')
    print(f'  Arquivo             : {result["export_path"]}')
    print(f'\nTop campos incertos:')
    for item in result['top_uncertain_fields']:
        print(f"  {item['field']:<30} correções={item['corrections']}")

    print('\nML_TRAINING_EXPORT_RESULT:', json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
