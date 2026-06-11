#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_meioPont_pl.py — CAD-7.2: Extração de PONTALETE e MEIO_PONTALETE por Laje

Calcula a quantidade de pontaletes necessários para cada laje com base nos dados
de Fase-3 e Fase-4, seguindo regra estrutural NBR 7190:
  - Espaçamento máximo: 100 cm entre pontaletes (longitudinal e transversal)
  - Tipo PONTALETE:      altura >= 230 cm (pé direito alto)
  - Tipo MEIO_PONTALETE: altura <  230 cm (pé direito baixo)

Nota: O layer MEIO_PONT no PL_gerado.dxf é um marcador sintético de fidelidade
(1 LWPOLYLINE por pilar) sem distinção PONTALETE/MEIO_PONTALETE. A classificação
real é calculada a partir da altura do pavimento (nivel_saida - nivel_chegada).

Uso:
  python scripts/extrair_meioPont_pl.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1
  python scripts/extrair_meioPont_pl.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1 --dry-run

Output:
  {obra}/Fase-3_Interpretacao_Extracao/Lajes/lajes_meioPont.json
"""
import sys, io, argparse, json, math, pathlib

# stdout/stderr redirect only when running as script (not when imported by pytest)
def _fix_encoding():
    if hasattr(sys.stdout, 'buffer') and not hasattr(sys.stdout, '_is_pytest'):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass
    if hasattr(sys.stderr, 'buffer') and not hasattr(sys.stderr, '_is_pytest'):
        try:
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass

# ─── Constantes ───────────────────────────────────────────────────────────────
ESPACO_MAX_CM = 100.0        # espaçamento máximo entre pontaletes (cm)
ALTURA_PONT_MIN = 230.0      # altura mínima para PONTALETE (cm); abaixo = MEIO_PONTALETE
MARGEM_BORDA_CM = 20.0       # margem das bordas sem pontalete (cm)


def calcular_pontaletes_laje(comprimento: float, largura: float, altura: float) -> dict:
    """
    Calcula contagem de pontaletes para uma laje.

    Args:
        comprimento: comprimento da laje em cm
        largura:     largura da laje em cm
        altura:      altura do pavimento (nivel_saida - nivel_chegada) em cm

    Returns:
        dict com keys: pontalete, meio_pontalete, total, tipo, linhas, colunas
    """
    if comprimento <= 0 or largura <= 0:
        return {"pontalete": 0, "meio_pontalete": 0, "total": 0,
                "tipo": "INDEFINIDO", "linhas": 0, "colunas": 0}

    # Número de fileiras longitudinais (ao longo do comprimento)
    span_util_comp = max(0.0, comprimento - 2 * MARGEM_BORDA_CM)
    n_colunas = max(1, math.ceil(span_util_comp / ESPACO_MAX_CM) + 1)

    # Número de fileiras transversais (ao longo da largura)
    span_util_larg = max(0.0, largura - 2 * MARGEM_BORDA_CM)
    n_linhas = max(1, math.ceil(span_util_larg / ESPACO_MAX_CM) + 1)

    total = n_linhas * n_colunas

    # Classificação por altura do pavimento
    tipo = "PONTALETE" if altura >= ALTURA_PONT_MIN else "MEIO_PONTALETE"

    return {
        "pontalete":       total if tipo == "PONTALETE" else 0,
        "meio_pontalete":  total if tipo == "MEIO_PONTALETE" else 0,
        "total":           total,
        "tipo":            tipo,
        "linhas":          n_linhas,
        "colunas":         n_colunas,
    }


def extrair(obra_path: pathlib.Path, dry_run: bool = False) -> dict:
    """Processa todas as lajes de uma obra e retorna lajes_meioPont dict."""

    f4_lajes = obra_path / "Fase-4_Sincronizacao" / "JSON_Lajes"
    f4_pavs  = obra_path / "Fase-4_Sincronizacao" / "pavimentos_lista.json"
    out_dir  = obra_path / "Fase-3_Interpretacao_Extracao" / "Lajes"

    if not f4_lajes.exists():
        print(f"  [ERRO] Fase-4/JSON_Lajes não encontrado: {f4_lajes}")
        return {}

    # Ler altura do pavimento (nivel_saida - nivel_chegada)
    altura_pav = 280.0  # default
    if f4_pavs.exists():
        try:
            pdata = json.loads(f4_pavs.read_text(encoding='utf-8-sig'))
            for _, v in pdata.items():
                for pname, pinfo in v.get('pavimentos_data', {}).items():
                    alt = float(pinfo.get('nivel_saida', 280)) - float(pinfo.get('nivel_chegada', 0))
                    if alt > 0:
                        altura_pav = alt
                        break
        except Exception as e:
            print(f"  [WARN] Erro lendo pavimentos_lista.json: {e}")

    print(f"  Altura do pavimento: {altura_pav:.1f} cm")

    resultado = {}
    lajes_json = sorted(f4_lajes.glob("*.json"))
    sem_pontalete = 0

    for lf in lajes_json:
        try:
            lj = json.loads(lf.read_text(encoding='utf-8-sig'))
        except Exception as e:
            print(f"  [WARN] {lf.name}: {e}")
            continue

        nome      = lj.get('nome', lf.stem)
        comp      = float(lj.get('comprimento', 0))
        larg      = float(lj.get('largura', 0))

        if comp <= 0 or larg <= 0:
            sem_pontalete += 1
            resultado[nome] = {
                "pontalete": 0, "meio_pontalete": 0, "total": 0,
                "tipo": "INDEFINIDO", "linhas": 0, "colunas": 0,
                "obs": "comprimento ou largura zerado"
            }
            continue

        counts = calcular_pontaletes_laje(comp, larg, altura_pav)
        counts["comprimento_cm"] = comp
        counts["largura_cm"] = larg
        counts["altura_pav_cm"] = altura_pav
        resultado[nome] = counts

        print(f"  {nome}: {counts['total']} {counts['tipo']} "
              f"({counts['linhas']}x{counts['colunas']}, {comp:.0f}x{larg:.0f}cm)")

    # Cobertura AC-5
    com_pont = sum(1 for v in resultado.values() if v.get('total', 0) > 0)
    total = len(resultado)
    cobertura = (com_pont / total * 100) if total > 0 else 0
    print(f"\n  Cobertura: {com_pont}/{total} lajes ({cobertura:.1f}%) com >= 1 pontalete")
    if cobertura < 80:
        print(f"  [WARN] Cobertura abaixo de 80% (AC-5)")

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "lajes_meioPont.json"
        out_file.write_text(
            json.dumps(resultado, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        print(f"\n  Salvo: {out_file}")

    return resultado


def main():
    parser = argparse.ArgumentParser(description='CAD-7.2: Extração MEIO_PONT por Laje')
    parser.add_argument('--obra', required=True, help='Caminho da obra (ex: D:/DADOS-OBRAS/Obra_TREINO_1)')
    parser.add_argument('--dry-run', action='store_true', help='Não salva o arquivo')
    args = parser.parse_args()

    obra = pathlib.Path(args.obra)
    if not obra.exists():
        sys.stdout.write(f"Erro: obra não encontrada: {obra}\n")
        sys.exit(1)

    sys.stdout.write(f"\n{'='*60}\n")
    sys.stdout.write(f"  CAD-7.2 — Extração MEIO_PONT por Laje\n")
    sys.stdout.write(f"{'='*60}\n")
    sys.stdout.write(f"  Obra: {obra.name}\n\n")

    resultado = extrair(obra, dry_run=args.dry_run)

    total_pont = sum(v.get('pontalete', 0) for v in resultado.values())
    total_meio = sum(v.get('meio_pontalete', 0) for v in resultado.values())
    sys.stdout.write(f"\n  Total PONTALETE:      {total_pont}\n")
    sys.stdout.write(f"  Total MEIO_PONTALETE: {total_meio}\n")
    sys.stdout.write(f"  Total geral:          {total_pont + total_meio}\n\n")

    if args.dry_run:
        sys.stdout.write("  [DRY-RUN] Nenhum arquivo salvo.\n")


if __name__ == '__main__':
    _fix_encoding()
    main()
