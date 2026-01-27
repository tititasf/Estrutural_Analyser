#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste completo de geração ABCD e GRADES com validação
"""

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

def main():
    print("\n" + "=" * 100)
    print("TESTE COMPLETO: Geração ABCD e GRADES")
    print("=" * 100)
    
    # 1. Extrair dados do log legacy
    print("\n[ETAPA 1] Extraindo dados do log legacy...")
    dados_legacy = extrair_dados_do_log_legacy()
    if not dados_legacy:
        print("[ERRO] Falha na extração de dados")
        return False
    
    print(f"[OK] Dados extraídos: {len(dados_legacy)} campos")
    
    # 2. Criar PilarModel
    print("\n[ETAPA 2] Criando PilarModel...")
    try:
        pilar = criar_pilar_model_do_legacy(dados_legacy)
        if not pilar:
            print("[ERRO] Falha na criação do PilarModel")
            return False
        print(f"[OK] PilarModel criado: {pilar.nome}")
        print(f"  - nivel_chegada: {pilar.nivel_chegada}")
        print(f"  - nivel_saida: {pilar.nivel_saida}")
        print(f"  - nivel_diferencial: {pilar.nivel_diferencial}")
        print(f"  - h1_A: {pilar.h1_A}, h2_A: {pilar.h2_A}, h3_A: {pilar.h3_A}, h4_A: {pilar.h4_A}, h5_A: {pilar.h5_A}")
        print(f"  - larg1_A: {pilar.larg1_A}, larg2_A: {pilar.larg2_A}, larg3_A: {pilar.larg3_A}")
    except Exception as e:
        print(f"[ERRO] Exceção ao criar PilarModel: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. Gerar scripts
    print("\n[ETAPA 3] Gerando scripts ABCD e GRADES...")
    try:
        service = AutomationOrchestratorService(str(project_root))
        obra = ObraModel(nome="Teste", scripts_dir=str(project_root / "SCRIPTS_ROBOS"))
        pavimento = PavimentoModel(nome=pilar.pavimento or "Subsolo", pilares=[pilar])
        
        print(f"[INFO] Gerando scripts para pavimento: {pavimento.nome}")
        
        # Gerar ABCD
        print("\n[INFO] Gerando script ABCD...")
        script_abcd = service.generate_item_script_abcd(pilar, pavimento.nome, obra.nome)
        if script_abcd:
            print(f"[OK] Script ABCD gerado ({len(script_abcd)} caracteres)")
        else:
            print("[AVISO] Script ABCD não foi gerado")
        
        # Gerar GRADES A
        print("\n[INFO] Gerando script GRADES A...")
        # Criar cópia do pilar com nome .A
        pilar_a = pilar.model_copy(update={'nome': f"{pilar.nome}.A"})
        script_grades_a = service.generate_item_script_grades(pilar_a, pavimento.nome, obra.nome)
        if script_grades_a:
            print(f"[OK] Script GRADES A gerado ({len(script_grades_a)} caracteres)")
        else:
            print("[AVISO] Script GRADES A não foi gerado")
        
        # Gerar GRADES B
        print("\n[INFO] Gerando script GRADES B...")
        # Criar cópia do pilar com nome .B
        pilar_b = pilar.model_copy(update={'nome': f"{pilar.nome}.B"})
        script_grades_b = service.generate_item_script_grades(pilar_b, pavimento.nome, obra.nome)
        if script_grades_b:
            print(f"[OK] Script GRADES B gerado ({len(script_grades_b)} caracteres)")
        else:
            print("[AVISO] Script GRADES B não foi gerado")
        
        print(f"\n[OK] Geração concluída")
        return True
    except Exception as e:
        print(f"[ERRO] Erro na geração: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    sucesso = main()
    sys.exit(0 if sucesso else 1)
