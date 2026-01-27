#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrai dados reais do log legacy e compara scripts gerados
"""

import os
import sys
import re
import json
from pathlib import Path

# Adicionar paths
project_root = Path(__file__).parent.parent.parent
robo_pilares_path = project_root / "_ROBOS_ABAS" / "Robo_Pilares" / "pilares-atualizado-09-25"
sys.path.insert(0, str(robo_pilares_path))
sys.path.insert(0, str(robo_pilares_path / "src"))

from models.pilar_model import PilarModel
from models.pavimento_model import PavimentoModel
from models.obra_model import ObraModel
from services.automation_service import AutomationOrchestratorService

def read_utf16(file_path: Path) -> str:
    """Lê arquivo UTF-16 LE"""
    with open(file_path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xff\xfe'):
        raw = raw[2:]
    return raw.decode('utf-16-le', errors='ignore')

def extrair_dados_do_log_legacy():
    """
    Extrai dados reais do log legacy para criar PilarModel idêntico.
    Usa regex para extrair apenas valores primitivos, ignorando objetos Python.
    """
    log_path = project_root / "_ROBOS_ABAS" / "contexto_legacy_pilares" / "logs_geracao_cima_abcd_grades.md"
    
    if not log_path.exists():
        print(f"[ERRO] Log legacy não encontrado: {log_path}")
        return None
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extrair dados manualmente usando regex para valores primitivos
    dados = {}
    
    # Nome
    nome_match = re.search(r"'nome':\s*'([^']+)'", content)
    if nome_match:
        dados['nome'] = nome_match.group(1)
    
    # Comprimento
    comp_match = re.search(r"'comprimento':\s*'([^']+)'", content)
    if comp_match:
        dados['comprimento'] = comp_match.group(1)
    
    # Largura
    larg_match = re.search(r"'largura':\s*'([^']+)'", content)
    if larg_match:
        dados['largura'] = larg_match.group(1)
    
    # Altura (procurar em "dados completos")
    alt_match = re.search(r"'altura':\s*'([^']+)'", content)
    if alt_match:
        dados['altura'] = alt_match.group(1)
    
    # Pavimento
    pav_match = re.search(r"'pavimento':\s*'([^']+)'", content)
    if pav_match:
        dados['pavimento'] = pav_match.group(1)
    
    # Níveis (procurar em "dados completos")
    nivel_saida_match = re.search(r"'nivel_saida':\s*'([^']*)'", content)
    if nivel_saida_match:
        dados['nivel_saida'] = nivel_saida_match.group(1)
    
    nivel_chegada_match = re.search(r"'nivel_chegada':\s*'([^']*)'", content)
    if nivel_chegada_match:
        dados['nivel_chegada'] = nivel_chegada_match.group(1)
    
    nivel_diferencial_match = re.search(r"'nivel_diferencial':\s*'([^']*)'", content)
    if nivel_diferencial_match:
        dados['nivel_diferencial'] = nivel_diferencial_match.group(1)
    
    # Pavimento anterior
    pav_ant_match = re.search(r"'pavimento_anterior':\s*'([^']*)'", content)
    if pav_ant_match:
        dados['pavimento_anterior'] = pav_ant_match.group(1)
    
    # Parafusos
    par_1_2_match = re.search(r"'parafuso_p1_p2':\s*(\d+)", content)
    if par_1_2_match:
        dados['parafuso_p1_p2'] = int(par_1_2_match.group(1))
    
    par_2_3_match = re.search(r"'parafuso_p2_p3':\s*(\d+)", content)
    if par_2_3_match:
        dados['parafuso_p2_p3'] = int(par_2_3_match.group(1))
    
    par_3_4_match = re.search(r"'parafuso_p3_p4':\s*(\d+)", content)
    if par_3_4_match:
        dados['parafuso_p3_p4'] = int(par_3_4_match.group(1))
    
    # Grades Grupo 1
    dados['grades_grupo1'] = {}
    grade_1_match = re.search(r"'grade_1':\s*'([^']*)'", content)
    if grade_1_match:
        dados['grades_grupo1']['grade_1'] = grade_1_match.group(1)
    
    dist_1_match = re.search(r"'distancia_1':\s*'([^']*)'", content)
    if dist_1_match:
        dados['grades_grupo1']['distancia_1'] = dist_1_match.group(1)
    
    grade_2_match = re.search(r"'grade_2':\s*'([^']*)'", content)
    if grade_2_match:
        dados['grades_grupo1']['grade_2'] = grade_2_match.group(1)
    
    dist_2_match = re.search(r"'distancia_2':\s*'([^']*)'", content)
    if dist_2_match:
        dados['grades_grupo1']['distancia_2'] = dist_2_match.group(1)
    
    grade_3_match = re.search(r"'grade_3':\s*'([^']*)'", content)
    if grade_3_match:
        dados['grades_grupo1']['grade_3'] = grade_3_match.group(1)
    
    # Detalhes Grades Grupo 1
    dados['detalhes_grades'] = {}
    for i in range(1, 4):
        for j in range(1, 6):
            key = f'detalhe_grade{i}_{j}'
            pattern = f"'{key}':\\s*'([^']*)'"
            match = re.search(pattern, content)
            if match:
                dados['detalhes_grades'][key] = match.group(1)
    
    # Grades Grupo 2
    dados['grades_grupo2'] = {}
    grade_1_g2_match = re.search(r"'grade_1_grupo2':\s*'([^']*)'", content)
    if grade_1_g2_match:
        dados['grades_grupo2']['grade_1_grupo2'] = grade_1_g2_match.group(1)
    
    dist_1_g2_match = re.search(r"'distancia_1_grupo2':\s*'([^']*)'", content)
    if dist_1_g2_match:
        dados['grades_grupo2']['distancia_1_grupo2'] = dist_1_g2_match.group(1)
    
    grade_2_g2_match = re.search(r"'grade_2_grupo2':\s*'([^']*)'", content)
    if grade_2_g2_match:
        dados['grades_grupo2']['grade_2_grupo2'] = grade_2_g2_match.group(1)
    
    dist_2_g2_match = re.search(r"'distancia_2_grupo2':\s*'([^']*)'", content)
    if dist_2_g2_match:
        dados['grades_grupo2']['distancia_2_grupo2'] = dist_2_g2_match.group(1)
    
    grade_3_g2_match = re.search(r"'grade_3_grupo2':\s*'([^']*)'", content)
    if grade_3_g2_match:
        dados['grades_grupo2']['grade_3_grupo2'] = grade_3_g2_match.group(1)
    
    # Detalhes Grades Grupo 2
    dados['detalhes_grades_grupo2'] = {}
    for i in range(1, 4):
        for j in range(1, 6):
            key = f'detalhe_grade{i}_{j}_grupo2'
            pattern = f"'{key}':\\s*'([^']*)'"
            match = re.search(pattern, content)
            if match:
                dados['detalhes_grades_grupo2'][key] = match.group(1)
    
    # Dados dos Painéis A, B, C, D (extrair do dicionário 'paineis')
    # Procurar por padrão: 'paineis': {'A': {'larg1': '122', 'larg2': '0', 'h1': '2', 'h2': '122', ...
    # Extrair dados de cada painel diretamente usando regex mais simples
    for painel in ['A', 'B', 'C', 'D']:
        # Procurar por padrão: 'A': {'laje': '', 'posicao_laje': '5', 'larg1': '122', ...
        painel_pattern = f"'{painel}':\\s*\\{{[^}}]*'larg1':\\s*'([^']*)'[^}}]*'larg2':\\s*'([^']*)'[^}}]*'larg3':\\s*'([^']*)'[^}}]*'h1':\\s*'([^']*)'[^}}]*'h2':\\s*'([^']*)'[^}}]*'h3':\\s*'([^']*)'[^}}]*'h4':\\s*'([^']*)'[^}}]*'h5':\\s*'([^']*)'[^}}]*'laje':\\s*'([^']*)'[^}}]*'posicao_laje':\\s*'([^']*)'"
        painel_match = re.search(painel_pattern, content, re.DOTALL)
        if painel_match:
            dados[f'larg1_{painel}'] = painel_match.group(1)
            dados[f'larg2_{painel}'] = painel_match.group(2)
            dados[f'larg3_{painel}'] = painel_match.group(3)
            dados[f'h1_{painel}'] = painel_match.group(4)
            dados[f'h2_{painel}'] = painel_match.group(5)
            dados[f'h3_{painel}'] = painel_match.group(6)
            dados[f'h4_{painel}'] = painel_match.group(7)
            dados[f'h5_{painel}'] = painel_match.group(8)
            dados[f'laje_{painel}'] = painel_match.group(9)
            dados[f'posicao_laje_{painel}'] = painel_match.group(10)
        else:
            # Tentar extrair campo por campo se o padrão completo falhar
            for campo in ['larg1', 'larg2', 'larg3', 'h1', 'h2', 'h3', 'h4', 'h5', 'laje', 'posicao_laje']:
                # Procurar padrão: 'A': {...'larg1': '122'...
                campo_pattern = f"'{painel}':\\s*\\{{[^}}]*'{campo}':\\s*'([^']*)'"
                campo_match = re.search(campo_pattern, content, re.DOTALL)
                if campo_match:
                    dados[f'{campo}_{painel}'] = campo_match.group(1)
    
    print(f"[EXTRACAO] Dados extraídos do log legacy:")
    print(f"  nome: {dados.get('nome')}")
    print(f"  comprimento: {dados.get('comprimento')}")
    print(f"  largura: {dados.get('largura')}")
    print(f"  altura: {dados.get('altura')}")
    print(f"  pavimento: {dados.get('pavimento')}")
    print(f"  pavimento_anterior: {dados.get('pavimento_anterior')}")
    print(f"  nivel_saida: {dados.get('nivel_saida')}")
    print(f"  nivel_chegada: {dados.get('nivel_chegada')}")
    print(f"  nivel_diferencial: {dados.get('nivel_diferencial')}")
    print(f"  parafuso_p1_p2: {dados.get('parafuso_p1_p2')}")
    print(f"  parafuso_p2_p3: {dados.get('parafuso_p2_p3')}")
    print(f"  grades_grupo1: {dados.get('grades_grupo1')}")
    print(f"  detalhes_grades: {dados.get('detalhes_grades')}")
    
    return dados

def criar_pilar_model_do_legacy(dados_legacy: dict):
    """
    Cria PilarModel a partir dos dados extraídos do log legacy.
    """
    # Converter valores string para float/int conforme necessário
    def to_float(val):
        if val == '' or val is None:
            return 0.0
        if isinstance(val, str):
            val = val.replace(',', '.')
        try:
            return float(val)
        except:
            return 0.0
    
    def to_int(val):
        if val == '' or val is None:
            return 0
        try:
            return int(float(str(val).replace(',', '.')))
        except:
            return 0
    
    # Extrair dados básicos
    nome = dados_legacy.get('nome', 'P1')
    comprimento = to_float(dados_legacy.get('comprimento', 0))
    largura = to_float(dados_legacy.get('largura', 0))
    altura = to_float(dados_legacy.get('altura', 300))
    pavimento = dados_legacy.get('pavimento', 'P1')
    nivel_saida = to_float(dados_legacy.get('nivel_saida', 0))
    nivel_chegada = to_float(dados_legacy.get('nivel_chegada', 0))
    nivel_diferencial = to_float(dados_legacy.get('nivel_diferencial', 0))
    pavimento_anterior = dados_legacy.get('pavimento_anterior', '')
    
    # Parafusos
    par_1_2 = to_int(dados_legacy.get('parafuso_p1_p2', 0))
    par_2_3 = to_int(dados_legacy.get('parafuso_p2_p3', 0))
    par_3_4 = to_int(dados_legacy.get('parafuso_p3_p4', 0))
    par_4_5 = to_int(dados_legacy.get('parafuso_p4_p5', 0))
    par_5_6 = to_int(dados_legacy.get('parafuso_p5_p6', 0))
    par_6_7 = to_int(dados_legacy.get('parafuso_p6_p7', 0))
    par_7_8 = to_int(dados_legacy.get('parafuso_p7_p8', 0))
    par_8_9 = to_int(dados_legacy.get('parafuso_p8_p9', 0))
    
    # Grades Grupo 1
    grades_g1 = dados_legacy.get('grades_grupo1', {})
    grade_1 = to_float(grades_g1.get('grade_1', 0))
    distancia_1 = to_float(grades_g1.get('distancia_1', 0))
    grade_2 = to_float(grades_g1.get('grade_2', 0))
    distancia_2 = to_float(grades_g1.get('distancia_2', 0))
    grade_3 = to_float(grades_g1.get('grade_3', 0))
    
    # Detalhes Grades Grupo 1
    detalhes_g1 = dados_legacy.get('detalhes_grades', {})
    detalhe_grade1_1 = to_float(detalhes_g1.get('detalhe_grade1_1', 0))
    detalhe_grade1_2 = to_float(detalhes_g1.get('detalhe_grade1_2', 0))
    detalhe_grade1_3 = to_float(detalhes_g1.get('detalhe_grade1_3', 0))
    detalhe_grade1_4 = to_float(detalhes_g1.get('detalhe_grade1_4', 0))
    detalhe_grade1_5 = to_float(detalhes_g1.get('detalhe_grade1_5', 0))
    detalhe_grade2_1 = to_float(detalhes_g1.get('detalhe_grade2_1', 0))
    detalhe_grade2_2 = to_float(detalhes_g1.get('detalhe_grade2_2', 0))
    detalhe_grade2_3 = to_float(detalhes_g1.get('detalhe_grade2_3', 0))
    detalhe_grade2_4 = to_float(detalhes_g1.get('detalhe_grade2_4', 0))
    detalhe_grade2_5 = to_float(detalhes_g1.get('detalhe_grade2_5', 0))
    detalhe_grade3_1 = to_float(detalhes_g1.get('detalhe_grade3_1', 0))
    detalhe_grade3_2 = to_float(detalhes_g1.get('detalhe_grade3_2', 0))
    detalhe_grade3_3 = to_float(detalhes_g1.get('detalhe_grade3_3', 0))
    detalhe_grade3_4 = to_float(detalhes_g1.get('detalhe_grade3_4', 0))
    detalhe_grade3_5 = to_float(detalhes_g1.get('detalhe_grade3_5', 0))
    
    # Grades Grupo 2
    grades_g2 = dados_legacy.get('grades_grupo2', {})
    grade_1_grupo2 = to_float(grades_g2.get('grade_1_grupo2', 0))
    distancia_1_grupo2 = to_float(grades_g2.get('distancia_1_grupo2', 0))
    grade_2_grupo2 = to_float(grades_g2.get('grade_2_grupo2', 0))
    distancia_2_grupo2 = to_float(grades_g2.get('distancia_2_grupo2', 0))
    grade_3_grupo2 = to_float(grades_g2.get('grade_3_grupo2', 0))
    
    # Detalhes Grades Grupo 2
    detalhes_g2 = dados_legacy.get('detalhes_grades_grupo2', {})
    detalhe_grade1_1_grupo2 = to_float(detalhes_g2.get('detalhe_grade1_1_grupo2', 0))
    detalhe_grade1_2_grupo2 = to_float(detalhes_g2.get('detalhe_grade1_2_grupo2', 0))
    detalhe_grade1_3_grupo2 = to_float(detalhes_g2.get('detalhe_grade1_3_grupo2', 0))
    detalhe_grade1_4_grupo2 = to_float(detalhes_g2.get('detalhe_grade1_4_grupo2', 0))
    detalhe_grade1_5_grupo2 = to_float(detalhes_g2.get('detalhe_grade1_5_grupo2', 0))
    detalhe_grade2_1_grupo2 = to_float(detalhes_g2.get('detalhe_grade2_1_grupo2', 0))
    detalhe_grade2_2_grupo2 = to_float(detalhes_g2.get('detalhe_grade2_2_grupo2', 0))
    detalhe_grade2_3_grupo2 = to_float(detalhes_g2.get('detalhe_grade2_3_grupo2', 0))
    detalhe_grade2_4_grupo2 = to_float(detalhes_g2.get('detalhe_grade2_4_grupo2', 0))
    detalhe_grade2_5_grupo2 = to_float(detalhes_g2.get('detalhe_grade2_5_grupo2', 0))
    detalhe_grade3_1_grupo2 = to_float(detalhes_g2.get('detalhe_grade3_1_grupo2', 0))
    detalhe_grade3_2_grupo2 = to_float(detalhes_g2.get('detalhe_grade3_2_grupo2', 0))
    detalhe_grade3_3_grupo2 = to_float(detalhes_g2.get('detalhe_grade3_3_grupo2', 0))
    detalhe_grade3_4_grupo2 = to_float(detalhes_g2.get('detalhe_grade3_4_grupo2', 0))
    detalhe_grade3_5_grupo2 = to_float(detalhes_g2.get('detalhe_grade3_5_grupo2', 0))
    
    # Pilar especial
    pilar_esp = dados_legacy.get('pilar_especial', {})
    pilar_especial_ativo = pilar_esp.get('ativar_pilar_especial', False) if isinstance(pilar_esp, dict) else False
    tipo_pilar_especial = pilar_esp.get('tipo_pilar_especial', 'L') if isinstance(pilar_esp, dict) else 'L'
    
    # Dados dos Painéis A, B, C, D
    paineis_data = {}
    for painel in ['A', 'B', 'C', 'D']:
        paineis_data[f'larg1_{painel}'] = to_float(dados_legacy.get(f'larg1_{painel}', 0))
        paineis_data[f'larg2_{painel}'] = to_float(dados_legacy.get(f'larg2_{painel}', 0))
        paineis_data[f'larg3_{painel}'] = to_float(dados_legacy.get(f'larg3_{painel}', 0))
        paineis_data[f'h1_{painel}'] = to_float(dados_legacy.get(f'h1_{painel}', 0))
        paineis_data[f'h2_{painel}'] = to_float(dados_legacy.get(f'h2_{painel}', 0))
        paineis_data[f'h3_{painel}'] = to_float(dados_legacy.get(f'h3_{painel}', 0))
        paineis_data[f'h4_{painel}'] = to_float(dados_legacy.get(f'h4_{painel}', 0))
        paineis_data[f'h5_{painel}'] = to_float(dados_legacy.get(f'h5_{painel}', 0))
        paineis_data[f'laje_{painel}'] = to_float(dados_legacy.get(f'laje_{painel}', 0))
        paineis_data[f'posicao_laje_{painel}'] = to_float(dados_legacy.get(f'posicao_laje_{painel}', 0))
    
    # Criar dicionário de argumentos para PilarModel
    pilar_kwargs = {
        'numero': "1",
        'nome': nome,
        'comprimento': comprimento,
        'largura': largura,
        'altura': altura,
        'pavimento': pavimento,
        'pavimento_anterior': pavimento_anterior,
        'nivel_saida': nivel_saida,
        'nivel_chegada': nivel_chegada,
        'nivel_diferencial': nivel_diferencial,
        # Parafusos
        'par_1_2': par_1_2,
        'par_2_3': par_2_3,
        'par_3_4': par_3_4,
        'par_4_5': par_4_5,
        'par_5_6': par_5_6,
        'par_6_7': par_6_7,
        'par_7_8': par_7_8,
        'par_8_9': par_8_9,
        # Grades Grupo 1
        'grade_1': grade_1,
        'distancia_1': distancia_1,
        'grade_2': grade_2,
        'distancia_2': distancia_2,
        'grade_3': grade_3,
        # Detalhes Grades Grupo 1
        'detalhe_grade1_1': detalhe_grade1_1,
        'detalhe_grade1_2': detalhe_grade1_2,
        'detalhe_grade1_3': detalhe_grade1_3,
        'detalhe_grade1_4': detalhe_grade1_4,
        'detalhe_grade1_5': detalhe_grade1_5,
        'detalhe_grade2_1': detalhe_grade2_1,
        'detalhe_grade2_2': detalhe_grade2_2,
        'detalhe_grade2_3': detalhe_grade2_3,
        'detalhe_grade2_4': detalhe_grade2_4,
        'detalhe_grade2_5': detalhe_grade2_5,
        'detalhe_grade3_1': detalhe_grade3_1,
        'detalhe_grade3_2': detalhe_grade3_2,
        'detalhe_grade3_3': detalhe_grade3_3,
        'detalhe_grade3_4': detalhe_grade3_4,
        'detalhe_grade3_5': detalhe_grade3_5,
        # Grades Grupo 2
        'grade_1_grupo2': grade_1_grupo2,
        'distancia_1_grupo2': distancia_1_grupo2,
        'grade_2_grupo2': grade_2_grupo2,
        'distancia_2_grupo2': distancia_2_grupo2,
        'grade_3_grupo2': grade_3_grupo2,
        # Detalhes Grades Grupo 2
        'detalhe_grade1_1_grupo2': detalhe_grade1_1_grupo2,
        'detalhe_grade1_2_grupo2': detalhe_grade1_2_grupo2,
        'detalhe_grade1_3_grupo2': detalhe_grade1_3_grupo2,
        'detalhe_grade1_4_grupo2': detalhe_grade1_4_grupo2,
        'detalhe_grade1_5_grupo2': detalhe_grade1_5_grupo2,
        'detalhe_grade2_1_grupo2': detalhe_grade2_1_grupo2,
        'detalhe_grade2_2_grupo2': detalhe_grade2_2_grupo2,
        'detalhe_grade2_3_grupo2': detalhe_grade2_3_grupo2,
        'detalhe_grade2_4_grupo2': detalhe_grade2_4_grupo2,
        'detalhe_grade2_5_grupo2': detalhe_grade2_5_grupo2,
        'detalhe_grade3_1_grupo2': detalhe_grade3_1_grupo2,
        'detalhe_grade3_2_grupo2': detalhe_grade3_2_grupo2,
        'detalhe_grade3_3_grupo2': detalhe_grade3_3_grupo2,
        'detalhe_grade3_4_grupo2': detalhe_grade3_4_grupo2,
        'detalhe_grade3_5_grupo2': detalhe_grade3_5_grupo2,
        # Pilar especial
        'pilar_especial_ativo': pilar_especial_ativo,
        'tipo_pilar_especial': tipo_pilar_especial,
    }
    
    # Adicionar dados dos painéis
    for painel in ['A', 'B', 'C', 'D']:
        pilar_kwargs[f'larg1_{painel}'] = paineis_data[f'larg1_{painel}']
        pilar_kwargs[f'larg2_{painel}'] = paineis_data[f'larg2_{painel}']
        pilar_kwargs[f'larg3_{painel}'] = paineis_data[f'larg3_{painel}']
        pilar_kwargs[f'h1_{painel}'] = paineis_data[f'h1_{painel}']
        pilar_kwargs[f'h2_{painel}'] = paineis_data[f'h2_{painel}']
        pilar_kwargs[f'h3_{painel}'] = paineis_data[f'h3_{painel}']
        pilar_kwargs[f'h4_{painel}'] = paineis_data[f'h4_{painel}']
        pilar_kwargs[f'h5_{painel}'] = paineis_data[f'h5_{painel}']
        pilar_kwargs[f'laje_{painel}'] = paineis_data[f'laje_{painel}']
        pilar_kwargs[f'posicao_laje_{painel}'] = paineis_data[f'posicao_laje_{painel}']
    
    # Criar PilarModel
    pilar = PilarModel(**pilar_kwargs)
    
    print(f"\n[PILAR] PilarModel criado:")
    print(f"  nome: {pilar.nome}")
    print(f"  comprimento: {pilar.comprimento}")
    print(f"  largura: {pilar.largura}")
    print(f"  altura: {pilar.altura}")
    print(f"  nivel_saida: {pilar.nivel_saida}, nivel_chegada: {pilar.nivel_chegada}")
    print(f"  par_1_2: {pilar.par_1_2}, par_2_3: {pilar.par_2_3}")
    print(f"  grade_1: {pilar.grade_1}, distancia_1: {pilar.distancia_1}")
    print(f"  grade_2: {pilar.grade_2}, distancia_2: {pilar.distancia_2}")
    print(f"  grade_3: {pilar.grade_3}")
    print(f"  detalhe_grade1_1: {pilar.detalhe_grade1_1}, detalhe_grade1_2: {pilar.detalhe_grade1_2}")
    print(f"  detalhe_grade2_1: {pilar.detalhe_grade2_1}, detalhe_grade2_2: {pilar.detalhe_grade2_2}")
    print(f"\n[PAINEIS] Dados dos painéis:")
    for painel in ['A', 'B', 'C', 'D']:
        larg1 = getattr(pilar, f'larg1_{painel}', 0)
        h1 = getattr(pilar, f'h1_{painel}', 0)
        h2 = getattr(pilar, f'h2_{painel}', 0)
        h3 = getattr(pilar, f'h3_{painel}', 0)
        h4 = getattr(pilar, f'h4_{painel}', 0)
        print(f"  Painel {painel}: larg1={larg1}, h1={h1}, h2={h2}, h3={h3}, h4={h4}")
    
    return pilar

def gerar_com_dados_legacy():
    """
    Gera scripts usando dados extraídos do log legacy.
    """
    print("\n" + "=" * 100)
    print("GERAÇÃO: Usando Dados Reais do Legacy")
    print("=" * 100)
    
    # Extrair dados do log
    dados_legacy = extrair_dados_do_log_legacy()
    if not dados_legacy:
        print("[ERRO] Não foi possível extrair dados do log")
        return None, None
    
    # Criar PilarModel
    pilar = criar_pilar_model_do_legacy(dados_legacy)
    if not pilar:
        print("[ERRO] Não foi possível criar PilarModel")
        return None, None
    
    # Criar service e gerar
    service = AutomationOrchestratorService(str(project_root))
    obra = ObraModel(nome="Teste", scripts_dir=str(project_root / "SCRIPTS_ROBOS"))
    pavimento = PavimentoModel(nome=pilar.pavimento or "P1", pilares=[pilar])
    
    print(f"\n[GERACAO] Gerando scripts com dados legacy...")
    try:
        result = service.generate_full_paviment_orchestration(pavimento, obra)
        print(f"[GERACAO] ✅ Geração concluída")
        return pavimento.nome, service
    except Exception as e:
        print(f"[GERACAO] ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def comparar_scripts_gerados_vs_legacy(pavimento_nome: str, service):
    """
    Compara scripts gerados com scripts legacy.
    """
    print("\n" + "=" * 100)
    print("COMPARAÇÃO: Scripts Gerados vs Legacy")
    print("=" * 100)
    
    scripts_dir = project_root / "SCRIPTS_ROBOS"
    pav_safe = service._normalize_name(pavimento_nome)
    
    legacy_dir = project_root / "_ROBOS_ABAS" / "contexto_legacy_pilares"
    
    comparacoes = {
        'CIMA': {
            'legacy': legacy_dir / "Ptestelegacy_CIMA.scr",
            'atual_dir': scripts_dir / f"{pav_safe}_CIMA" / "Combinados"
        },
        'ABCD': {
            'legacy': legacy_dir / "Ptestelegacy_ABCD.scr",
            'atual_dir': scripts_dir / f"{pav_safe}_ABCD" / "Combinados"
        },
        'GRADES_A': {
            'legacy': legacy_dir / "Ptestelegacy.A.scr",
            'atual_dir': scripts_dir / f"{pav_safe}_GRADES"
        },
        'GRADES_B': {
            'legacy': legacy_dir / "Ptestelegacy.B.scr",
            'atual_dir': scripts_dir / f"{pav_safe}_GRADES"
        }
    }
    
    resultados = {}
    
    for tipo, paths in comparacoes.items():
        print(f"\n[{tipo}] Comparação:")
        
        legacy_path = paths['legacy']
        atual_dir = paths['atual_dir']
        
        if not legacy_path.exists():
            print(f"  ⚠️ Script legacy não encontrado: {legacy_path}")
            continue
        
        # Procurar script atual
        if tipo.startswith('GRADES'):
            # Para GRADES, procurar .A.scr ou .B.scr
            sufixo = '.A.scr' if tipo == 'GRADES_A' else '.B.scr'
            atual_scripts = list(atual_dir.glob(f"*{sufixo}")) if atual_dir.exists() else []
            if not atual_scripts:
                # Tentar Combinados
                combinados_dir = atual_dir / "Combinados"
                if combinados_dir.exists():
                    atual_scripts = list(combinados_dir.glob(f"*{sufixo}"))
        else:
            # Para CIMA e ABCD, procurar em Combinados
            atual_scripts = list(atual_dir.glob("*.scr")) if atual_dir.exists() else []
        
        if not atual_scripts:
            print(f"  ⚠️ Script atual não encontrado em: {atual_dir}")
            continue
        
        atual_path = atual_scripts[0]
        
        try:
            # Ler arquivos
            legacy_content = read_utf16(legacy_path)
            atual_content = read_utf16(atual_path)
            
            # Estatísticas
            legacy_lines = len(legacy_content.splitlines())
            atual_lines = len(atual_content.splitlines())
            legacy_size = len(legacy_content.encode('utf-16-le'))
            atual_size = len(atual_content.encode('utf-16-le'))
            
            print(f"  Legacy: {legacy_path.name}")
            print(f"  Atual:  {atual_path.name}")
            print(f"  Legacy: {legacy_lines} linhas, {legacy_size} bytes")
            print(f"  Atual:  {atual_lines} linhas, {atual_size} bytes")
            print(f"  Diferença: {atual_lines - legacy_lines:+d} linhas, {atual_size - legacy_size:+d} bytes")
            
            # Contar comandos
            legacy_layers = legacy_content.count('_LAYER')
            atual_layers = atual_content.count('_LAYER')
            legacy_inserts = legacy_content.count('-INSERT')
            atual_inserts = atual_content.count('-INSERT')
            legacy_dimlinear = legacy_content.count('_DIMLINEAR')
            atual_dimlinear = atual_content.count('_DIMLINEAR')
            
            print(f"\n  Comandos:")
            print(f"    LAYER:    Legacy={legacy_layers:3d}, Atual={atual_layers:3d}, Diff={atual_layers - legacy_layers:+d}")
            print(f"    INSERT:   Legacy={legacy_inserts:3d}, Atual={atual_inserts:3d}, Diff={atual_inserts - legacy_inserts:+d}")
            print(f"    DIMLINEAR: Legacy={legacy_dimlinear:3d}, Atual={atual_dimlinear:3d}, Diff={atual_dimlinear - legacy_dimlinear:+d}")
            
            # Verificar se são idênticos
            if legacy_content == atual_content:
                print(f"\n  ✅ Scripts são IDÊNTICOS byte-a-byte!")
                resultados[tipo] = {'status': 'IDENTICO', 'diff_lines': 0, 'diff_bytes': 0}
            else:
                print(f"\n  ⚠️ Scripts são DIFERENTES")
                resultados[tipo] = {
                    'status': 'DIFERENTE',
                    'diff_lines': atual_lines - legacy_lines,
                    'diff_bytes': atual_size - legacy_size,
                    'legacy_lines': legacy_lines,
                    'atual_lines': atual_lines,
                    'legacy_size': legacy_size,
                    'atual_size': atual_size
                }
                
        except Exception as e:
            print(f"  ❌ Erro ao comparar: {e}")
            import traceback
            traceback.print_exc()
            resultados[tipo] = {'status': 'ERRO', 'erro': str(e)}
    
    return resultados

def main():
    """
    Função principal: extrai dados legacy, gera scripts e compara.
    """
    print("\n" + "=" * 100)
    print("EXTRAÇÃO E COMPARAÇÃO: Dados Legacy vs Scripts Gerados")
    print("=" * 100)
    
    # 1. Extrair dados e gerar
    pavimento_nome, service = gerar_com_dados_legacy()
    
    if not pavimento_nome:
        print("\n[ERRO] Falha na geração. Abortando comparação.")
        return
    
    # 2. Comparar
    resultados = comparar_scripts_gerados_vs_legacy(pavimento_nome, service)
    
    # 3. Resumo
    print("\n" + "=" * 100)
    print("RESUMO DA COMPARAÇÃO")
    print("=" * 100)
    
    for tipo, resultado in resultados.items():
        status = resultado.get('status', 'DESCONHECIDO')
        if status == 'IDENTICO':
            print(f"[{tipo}] ✅ IDÊNTICO")
        elif status == 'DIFERENTE':
            diff_lines = resultado.get('diff_lines', 0)
            diff_bytes = resultado.get('diff_bytes', 0)
            print(f"[{tipo}] ⚠️ DIFERENTE: {diff_lines:+d} linhas, {diff_bytes:+d} bytes")
        else:
            print(f"[{tipo}] ❌ ERRO: {resultado.get('erro', 'Desconhecido')}")
    
    print("\n" + "=" * 100)
    print("Próximos passos:")
    print("1. Analisar diferenças específicas usando compare_scripts.py")
    print("2. Verificar se há campos faltantes no mapeamento")
    print("3. Ajustar valores ou lógica de geração conforme necessário")

if __name__ == '__main__':
    main()
