#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/apply_correction.py — CAD-10.6
CLI de realimentação do interpretador.

Uso:
  # Aplicar todas as correções do log
  python scripts/apply_correction.py --obra DADOS-OBRAS/Obra_TREINO_21 --from-log

  # Mostrar métricas
  python scripts/apply_correction.py --obra DADOS-OBRAS/Obra_TREINO_21 --stats

  # Correção pontual
  python scripts/apply_correction.py --obra DADOS-OBRAS/Obra_TREINO_21 \
      --item P1 --type pilar --field grade_1 --value 88.0
"""
import argparse
import json
import sys
from pathlib import Path

# Garantir que src/ está no path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.core.services.correction_service import (
    apply_correction,
    apply_from_log,
    compute_stats,
    build_log_entry,
    append_correction_log,
    _find_json_path,
)

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")


def _resolve_obra(obra_arg: str) -> Path:
    p = Path(obra_arg)
    if p.is_absolute():
        return p
    if (DADOS_OBRAS_ROOT / obra_arg).exists():
        return DADOS_OBRAS_ROOT / obra_arg
    if p.exists():
        return p
    raise FileNotFoundError(f"Obra não encontrada: {obra_arg}")


def cmd_from_log(obra: Path, dry_run: bool = False) -> int:
    """Aplica todas as correções do correction_log.json."""
    log_path = obra / "Fase-3_Interpretacao_Extracao" / "correction_log.json"
    if not log_path.exists():
        print(f"[WARN] Nenhum log encontrado em: {log_path}")
        return 0

    if dry_run:
        import json as _json
        entries = _json.loads(log_path.read_text(encoding='utf-8'))
        print(f"[DRY-RUN] {len(entries)} entradas no log (nenhuma aplicada)")
        for e in entries:
            print(f"  {e.get('item_id')}.{e.get('field')} -> {e.get('new_value')}")
        return 0

    result = apply_from_log(obra)
    print(f"[OK] Aplicadas: {result['applied']} | Ignoradas: {result['skipped']}")
    if result['by_type']:
        for t, n in result['by_type'].items():
            print(f"  {t}: {n}")
    if result['errors']:
        print(f"[ERROS] {len(result['errors'])}")
        for err in result['errors']:
            print(f"  ✗ {err}")
        return 1
    return 0


def cmd_stats(obra: Path) -> int:
    """Mostra métricas do correction_log.json."""
    stats = compute_stats(obra)
    print(f"=== Métricas de Correção — {stats['obra']} ===")
    print(f"Total de correções: {stats['total']}")
    if not stats['total']:
        print("(sem correções registradas)")
        return 0

    print("\nPor tipo:")
    for t, v in stats.get('by_type', {}).items():
        print(f"  {t}: {v}")

    print("\nTop campos mais corrigidos:")
    for f in stats.get('top_fields', []):
        avg = f['avg_delta']
        avg_str = f"avg_delta={avg:+.2f}" if avg is not None else "não numérico"
        print(f"  {f['field']:30s} × {f['count']}  ({avg_str})")
    return 0


def cmd_single(obra: Path, item_id: str, item_type: str,
               field: str, value: str) -> int:
    """Aplica correção pontual e registra no log."""
    json_path = _find_json_path(obra, item_id, item_type)
    if not json_path:
        print(f"[ERRO] JSON não encontrado: {item_id} ({item_type})")
        return 1

    # Tentar converter para float
    try:
        typed_value: object = float(value)
    except ValueError:
        typed_value = value

    # Ler valor atual
    import json as _json
    data = _json.loads(json_path.read_text(encoding='utf-8-sig'))
    old_value = data.get(field)

    changed = apply_correction(json_path, field, typed_value)
    if changed:
        entry = build_log_entry(
            item_id=item_id,
            item_type=item_type,
            json_key=field,
            detail_field_id=field,
            old_value=old_value,
            new_value=typed_value,
        )
        append_correction_log(obra, entry)
        print(f"[OK] {item_id}.{field}: {old_value!r} -> {typed_value!r}")
    else:
        print(f"[SKIP] {item_id}.{field} já tem valor {typed_value!r}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Realimentação do interpretador CAD — aplica correções nos JSONs Fase-4"
    )
    parser.add_argument('--obra', required=True,
                        help='Caminho ou nome da obra (relativo a DADOS-OBRAS/)')
    parser.add_argument('--from-log', action='store_true',
                        help='Aplica todas as correções do correction_log.json')
    parser.add_argument('--stats', action='store_true',
                        help='Exibe métricas do correction_log.json')
    parser.add_argument('--dry-run', action='store_true',
                        help='Com --from-log: lista sem aplicar')
    parser.add_argument('--item',  help='ID do item (ex: P1)')
    parser.add_argument('--type',  dest='item_type', help='Tipo: pilar|viga|laje')
    parser.add_argument('--field', help='Campo JSON (ex: grade_1)')
    parser.add_argument('--value', help='Novo valor')

    args = parser.parse_args()

    try:
        obra = _resolve_obra(args.obra)
    except FileNotFoundError as e:
        print(f"[ERRO] {e}")
        return 1

    if args.from_log:
        return cmd_from_log(obra, dry_run=args.dry_run)

    if args.stats:
        return cmd_stats(obra)

    if args.item and args.item_type and args.field and args.value is not None:
        return cmd_single(obra, args.item, args.item_type, args.field, args.value)

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
