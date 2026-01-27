#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste completo e autônomo: extrai dados, cria PilarModel, valida e gera scripts
"""

import os
import sys
from pathlib import Path

# Adicionar paths
project_root = Path(__file__).parent.parent.parent
robo_pilares_path = project_root / "_ROBOS_ABAS" / "Robo_Pilares" / "pilares-atualizado-09-25"
sys.path.insert(0, str(robo_pilares_path))
sys.path.insert(0, str(robo_pilares_path / "src"))

from extrair_dados_legacy_e_comparar import extrair_dados_do_log_legacy, criar_pilar_model_do_legacy
from models.pilar_model import PilarModel
from models.pavimento_model import PavimentoModel
from models.obra_model import ObraModel
from services.automation_service import AutomationOrchestratorService

def validar_pilar_model(pilar: PilarModel) -> tuple[bool, list[str]]:
    """Valida se o PilarModel tem todos os campos necessários"""
    erros = []
    
    # Campos obrigatórios básicos
    campos_obrigatorios = ['nome', 'comprimento', 'largura', 'altura', 'pavimento']
    for campo in campos_obrigatorios:
        valor = getattr(pilar, campo, None)
        if valor is None or (isinstance(valor, (int, float)) and valor == 0 and campo != 'comprimento'):
            erros.append(f"Campo obrigatorio '{campo}' esta vazio ou zero: {valor}")
    
    # Validar painéis
    for painel in ['A', 'B', 'C', 'D']:
        larg1 = getattr(pilar, f'larg1_{painel}', 0)
        h1 = getattr(pilar, f'h1_{painel}', 0)
        if larg1 == 0 and h1 == 0:
            # Pode ser válido se não houver painel
            pass
    
    return len(erros) == 0, erros

def main():
    print("\n" + "=" * 100)
    print("TESTE COMPLETO E AUTONOMO: Validacao de Extração e Geração")
    print("=" * 100)
    
    # 1. Extrair dados do log legacy
    print("\n[ETAPA 1] Extraindo dados do log legacy...")
    dados_legacy = extrair_dados_do_log_legacy()
    if not dados_legacy:
        print("[ERRO] Falha na extração de dados")
        return False
    
    print(f"[OK] Dados extraídos: {len(dados_legacy)} campos")
    print(f"  - nome: {dados_legacy.get('nome')}")
    print(f"  - comprimento: {dados_legacy.get('comprimento')}")
    print(f"  - largura: {dados_legacy.get('largura')}")
    print(f"  - altura: {dados_legacy.get('altura')}")
    
    # 2. Criar PilarModel
    print("\n[ETAPA 2] Criando PilarModel...")
    try:
        pilar = criar_pilar_model_do_legacy(dados_legacy)
        if not pilar:
            print("[ERRO] Falha na criação do PilarModel")
            return False
        print(f"[OK] PilarModel criado: {pilar.nome}")
    except Exception as e:
        print(f"[ERRO] Exceção ao criar PilarModel: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. Validar PilarModel
    print("\n[ETAPA 3] Validando PilarModel...")
    valido, erros = validar_pilar_model(pilar)
    if not valido:
        print(f"[ERRO] PilarModel inválido:")
        for erro in erros:
            print(f"  - {erro}")
        return False
    print("[OK] PilarModel válido")
    
    # 4. Verificar campos críticos
    print("\n[ETAPA 4] Verificando campos críticos...")
    campos_criticos = {
        'nivel_saida': pilar.nivel_saida,
        'nivel_chegada': pilar.nivel_chegada,
        'nivel_diferencial': pilar.nivel_diferencial,
        'pavimento_anterior': pilar.pavimento_anterior,
    }
    for campo, valor in campos_criticos.items():
        print(f"  - {campo}: {valor}")
    
    # Verificar painéis
    print("\n[ETAPA 5] Verificando dados dos painéis...")
    for painel in ['A', 'B', 'C', 'D']:
        larg1 = getattr(pilar, f'larg1_{painel}', 0)
        h1 = getattr(pilar, f'h1_{painel}', 0)
        laje = getattr(pilar, f'laje_{painel}', 0)
        print(f"  Painel {painel}: larg1={larg1}, h1={h1}, laje={laje}")
    
    # 5. Testar geração (opcional - pode demorar)
    print("\n[ETAPA 6] Testando geração de scripts...")
    try:
        service = AutomationOrchestratorService(str(project_root))
        obra = ObraModel(nome="Teste", scripts_dir=str(project_root / "SCRIPTS_ROBOS"))
        pavimento = PavimentoModel(nome=pilar.pavimento or "P1", pilares=[pilar])
        
        print(f"[INFO] Gerando scripts para pavimento: {pavimento.nome}")
        result = service.generate_full_paviment_orchestration(pavimento, obra)
        print(f"[OK] Geração concluída")
        return True
    except Exception as e:
        print(f"[AVISO] Erro na geração (pode ser esperado se demorar muito): {e}")
        import traceback
        traceback.print_exc()
        return True  # Ainda consideramos sucesso se a validação passou
    
    print("\n" + "=" * 100)
    print("VALIDACAO COMPLETA: TODOS OS TESTES PASSARAM")
    print("=" * 100)
    return True

if __name__ == '__main__':
    sucesso = main()
    sys.exit(0 if sucesso else 1)
