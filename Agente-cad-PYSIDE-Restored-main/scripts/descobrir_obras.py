#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
descobrir_obras.py — Discovery automático de DXFs por obra/pavimento.

Varre DADOS-OBRAS/* e mapeia quais DXFs existem por obra e pavimento.

Padrão de nomes STOG:
  {EMPRESA} - {OBRA} - {PAVIMENTO} - {TIPO} - R{rev}[_sufixo].dxf
  Ex: "STOG - NIK SUNSET - 12° PAV.- PL - R00_R2018_ASCII_ODA.dxf"
  Ex: "ALIMONTI - PARAISO - 13° PAV.- FV - R00.dxf"

Saída: DADOS-OBRAS/dxf_discovery.json

CLI:
  python scripts/descobrir_obras.py --data-dir DADOS-OBRAS/
  python scripts/descobrir_obras.py --data-dir DADOS-OBRAS/ --obra Obra_TREINO_21
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Tipos de DXF e seus aliases
DXF_TYPES = {
    'PL':  ['PL'],
    'LV':  ['LV'],
    'FV':  ['FV', 'FD'],
    'LJ':  ['LJ'],
    'EVG': ['EVG', 'GF'],  # GF = Garfos em algumas obras
}

# DXFs prioritários (mínimo para processar um pavimento)
DXF_MINIMOS = {'PL'}
DXF_COMPLETO = {'PL', 'LV', 'FV', 'LJ'}


def parse_dxf_nome(nome_arquivo: str):
    """
    Extrai (pav_nome, tipo) do nome de arquivo DXF.

    Padrão STOG: {empresa} - {obra} - {pavimento}[.- ]{tipo}[- R{rev}][- sufixo...]
    O TIPO é o âncora: tudo antes dele (exceto empresa/obra) é o pavimento.

    Variações suportadas:
      Canônico:    "STOG - OBRA - 12 PAV - PL - R00"
      Extra sufixo:"ZAMBETA - LUXOR - 1PV - FV - R00 - 1°ETAPA"
      Prefixo rev: "QUATTRI - IND - 1° SUBOLO - PL - PROJEÇÃO - R00"

    Retorna (pav_nome, tipo) ou (None, None) se não parsear.
    """
    stem = Path(nome_arquivo).stem

    # Remover sufixo de versão ODA: "_R2018_ASCII_ODA", "_R2010_ASCII" etc
    stem = re.sub(r'_R\d{4}[_A-Z]+$', '', stem)

    tipos_re = '|'.join(t for aliases in DXF_TYPES.values() for t in aliases)

    # Estratégia: localizar o TIPO como âncora fixa no meio do nome.
    # Padrão: {prefixo} SEP {tipo} SEP {sufixo_opcional}
    # Prefixo = empresa + obra + pavimento (os dois primeiros tokens são empresa-obra)
    # Separador: " - " ou ".- " ou ". - "
    sep = r'\s*[-\.]+\s*'
    anchor = rf'(?<={sep}|^)({tipos_re})(?={sep}|$)'

    # Dividir o stem por " - " para obter tokens
    tokens = re.split(r'\s+-\s+', stem)
    if len(tokens) < 3:
        return None, None

    # Procurar o token que é um TIPO conhecido
    tipo = None
    tipo_idx = None
    for i, tok in enumerate(tokens):
        tok_up = tok.strip().upper()
        for t, aliases in DXF_TYPES.items():
            if tok_up in aliases:
                tipo = t
                tipo_idx = i
                break
        if tipo:
            break

    if tipo is None or tipo_idx is None:
        return None, None

    # Pavimento = tokens entre o 2º e o tipo (tokens[2..tipo_idx-1])
    # tokens[0] = empresa, tokens[1] = obra (ou obra parte 1)
    # Para nomes com empresa de 1 palavra: pav = tokens[2:tipo_idx]
    # Para nomes com empresa multi-palavra: pegar tudo entre tokens[1] e tipo
    # Heurística: se tipo_idx >= 3, pav = tokens[2:tipo_idx]
    #             se tipo_idx == 2, pav = tokens[1:tipo_idx] (empresa+obra colado)
    if tipo_idx >= 3:
        pav_parts = tokens[2:tipo_idx]
    elif tipo_idx == 2:
        pav_parts = tokens[1:tipo_idx]
    else:
        return None, None

    pav_raw = ' - '.join(p.strip() for p in pav_parts).rstrip('.')
    if not pav_raw:
        return None, None

    # Normalizar pav_nome: padronizar graus e abreviações
    pav_nome = _normalizar_pav(pav_raw)

    return pav_nome, tipo


def _normalizar_pav(pav_raw: str) -> str:
    """
    Normaliza nome de pavimento para agrupar variações do mesmo andar.
    Ex: "12° PAV." e "12º PAVIMENTO" → "12 PAV"
        "2°, 3° E PAV. TIPO" → "2-3 E PAV TIPO"
        "LAJE TECNICA" → "LAJE TECNICA"
    """
    # Remover graus (° º) e pontuação final
    pav = pav_raw.strip().rstrip('.')
    pav = pav.replace('°', '').replace('º', '').replace('ª', '')

    # Normalizar "PAV." → "PAV", "PAVIMENTO" → "PAV"
    pav = re.sub(r'\bPAVIMENTO\b', 'PAV', pav, flags=re.IGNORECASE)
    pav = re.sub(r'\bPAV\.\b', 'PAV', pav, flags=re.IGNORECASE)

    # Remover espaços duplos
    pav = re.sub(r'\s+', ' ', pav).strip()

    return pav.upper()


def descobrir_obra(obra_path: Path, preferir_maior_revisao: bool = True) -> dict:
    """
    Faz descoberta de DXFs em uma obra.

    Retorna: {pav_nome: {tipo: path_absoluto_ou_None, ...}, ...}
    """
    target_dir = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not target_dir.exists():
        return {}

    # {pav: {tipo: {rev: path}}}
    achados = defaultdict(lambda: defaultdict(dict))

    for dxf in target_dir.glob("*.dxf"):
        pav_nome, tipo = parse_dxf_nome(dxf.name)
        if pav_nome is None:
            continue

        # Extrair número de revisão (R00 → 0, R01 → 1)
        stem_clean = re.sub(r'_R\d{4}[_A-Z]+$', '', dxf.stem)
        rev_match = re.search(r'[-\s](R(\d+))$', stem_clean, re.IGNORECASE)
        rev_num = int(rev_match.group(2)) if rev_match else 0

        achados[pav_nome][tipo][rev_num] = str(dxf.resolve())

    # Montar resultado final (maior revisão por tipo)
    resultado = {}
    for pav_nome in sorted(achados.keys()):
        tipos_dict = {t: None for t in DXF_TYPES}
        for tipo, revs in achados[pav_nome].items():
            if revs:
                rev_max = max(revs.keys())
                tipos_dict[tipo] = revs[rev_max]
        resultado[pav_nome] = tipos_dict

    return resultado


def calcular_completude(pav_data: dict) -> dict:
    """Calcula status de completude de um pavimento."""
    presentes = {t for t, p in pav_data.items() if p is not None}
    tem_minimo = DXF_MINIMOS.issubset(presentes)
    tem_completo = DXF_COMPLETO.issubset(presentes)
    faltando = [t for t in DXF_TYPES if pav_data.get(t) is None]

    return {
        'tipos_presentes': sorted(presentes),
        'tipos_faltando': sorted(faltando),
        'tem_minimo_pl': tem_minimo,
        'tem_conjunto_completo': tem_completo,
        'pode_processar': tem_minimo,
    }


def descobrir_todas_obras(data_dir: Path, obra_filtro: str = None) -> dict:
    """Descobre DXFs em todas as obras (ou em obra_filtro se especificado)."""
    discovery = {}

    subdirs = sorted(data_dir.iterdir()) if data_dir.exists() else []
    for obra_dir in subdirs:
        if not obra_dir.is_dir():
            continue
        if obra_filtro and obra_dir.name != obra_filtro:
            continue

        pavs = descobrir_obra(obra_dir)
        if not pavs:
            continue

        discovery[obra_dir.name] = pavs

    return discovery


def relatorio_discovery(discovery: dict) -> None:
    """Imprime relatório de discovery no console."""
    print("\n[DISCOVERY] ===================================")
    total_obras = len(discovery)
    total_pav_ok = 0
    total_pav_parcial = 0

    for obra_nome, pavs in discovery.items():
        print(f"\n  Obra: {obra_nome}")
        for pav_nome, tipos in sorted(pavs.items()):
            compl = calcular_completude(tipos)
            presentes_str = '+'.join(compl['tipos_presentes'])
            faltando_str = ','.join(compl['tipos_faltando']) if compl['tipos_faltando'] else '-'

            if compl['tem_conjunto_completo']:
                status = "OK COMPLETO"
                total_pav_ok += 1
            elif compl['pode_processar']:
                status = "!! PARCIAL"
                total_pav_parcial += 1
            else:
                status = "XX SEM PL"

            print(f"    {pav_nome:<35} {presentes_str:<20} faltando:[{faltando_str}]  {status}")

    print(f"\n[SUMMARY] {total_obras} obras | {total_pav_ok} pavs completos | {total_pav_parcial} parciais")
    print("[DISCOVERY] ===================================\n")


def main():
    parser = argparse.ArgumentParser(description='Discovery de DXFs por obra/pavimento')
    parser.add_argument('--data-dir', required=True, help='Diretório raiz DADOS-OBRAS/')
    parser.add_argument('--obra', default=None, help='Filtrar por obra específica')
    parser.add_argument('--output', default=None, help='Caminho do JSON de saída (default: data-dir/dxf_discovery.json)')
    parser.add_argument('--so-processiveis', action='store_true', help='Incluir apenas pavimentos com PL DXF')
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.exists():
        print(f"[ERROR] Diretório não encontrado: {data_dir}")
        sys.exit(1)

    print(f"[INFO] Scanning: {data_dir}")
    discovery = descobrir_todas_obras(data_dir, args.obra)

    if not discovery:
        print("[WARNING] Nenhuma obra encontrada com DXFs STOG")
        sys.exit(0)

    # Filtrar apenas processáveis
    if args.so_processiveis:
        discovery_filtrado = {}
        for obra, pavs in discovery.items():
            pavs_ok = {pav: tipos for pav, tipos in pavs.items()
                       if calcular_completude(tipos)['pode_processar']}
            if pavs_ok:
                discovery_filtrado[obra] = pavs_ok
        discovery = discovery_filtrado

    # Relatório
    relatorio_discovery(discovery)

    # Salvar JSON
    out_path = Path(args.output) if args.output else data_dir / "dxf_discovery.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(discovery, f, indent=2, ensure_ascii=False)
    print(f"[INFO] Discovery salvo: {out_path}")

    # Contar stats
    total_pavs = sum(len(pavs) for pavs in discovery.values())
    print(f"[INFO] {len(discovery)} obras | {total_pavs} pavimentos descobertos")


if __name__ == '__main__':
    main()
