
# Helper de ofuscação (adicionado automaticamente)
def _get_obf_str(key):
    """Retorna string ofuscada"""
    _obf_map = {
        _get_obf_str("script.google.com"): base64.b64decode("=02bj5SZsd2bvdmL0BXayN2c"[::-1].encode()).decode(),
        _get_obf_str("macros/s/"): base64.b64decode("vM3Lz9mcjFWb"[::-1].encode()).decode(),
        _get_obf_str("AKfycbz"): base64.b64decode("==geiNWemtUQ"[::-1].encode()).decode(),
        _get_obf_str("credit"): base64.b64decode("0lGZlJ3Y"[::-1].encode()).decode(),
        _get_obf_str("saldo"): base64.b64decode("=8GZsF2c"[::-1].encode()).decode(),
        _get_obf_str("consumo"): base64.b64decode("==wbtV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("api_key"): base64.b64decode("==Qelt2XpBXY"[::-1].encode()).decode(),
        _get_obf_str("user_id"): base64.b64decode("==AZp9lclNXd"[::-1].encode()).decode(),
        _get_obf_str("calcular_creditos"): base64.b64decode("=M3b0lGZlJ3YfJXYsV3YsF2Y"[::-1].encode()).decode(),
        _get_obf_str("confirmar_consumo"): base64.b64decode("=8Wb1NnbvN2XyFWbylmZu92Y"[::-1].encode()).decode(),
        _get_obf_str("consultar_saldo"): base64.b64decode("vRGbhN3XyFGdsV3cu92Y"[::-1].encode()).decode(),
        _get_obf_str("debitar_creditos"): base64.b64decode("==wcvRXakVmcj9lchRXaiVGZ"[::-1].encode()).decode(),
        _get_obf_str("CreditManager"): base64.b64decode("==gcldWYuFWT0lGZlJ3Q"[::-1].encode()).decode(),
        _get_obf_str("obter_hwid"): base64.b64decode("==AZpdHafJXZ0J2b"[::-1].encode()).decode(),
        _get_obf_str("generate_signature"): base64.b64decode("lJXd0Fmbnl2cfVGdhJXZuV2Z"[::-1].encode()).decode(),
        _get_obf_str("encrypt_string"): base64.b64decode("=cmbpJHdz9Fdwlncj5WZ"[::-1].encode()).decode(),
        _get_obf_str("decrypt_string"): base64.b64decode("=cmbpJHdz9FdwlncjVGZ"[::-1].encode()).decode(),
        _get_obf_str("integrity_check"): base64.b64decode("rNWZoN2X5RXaydWZ05Wa"[::-1].encode()).decode(),
        _get_obf_str("security_utils"): base64.b64decode("=MHbpRXdflHdpJXdjV2c"[::-1].encode()).decode(),
        _get_obf_str("https://"): base64.b64decode("=8yL6MHc0RHa"[::-1].encode()).decode(),
        _get_obf_str("google.com"): base64.b64decode("==QbvNmLlx2Zv92Z"[::-1].encode()).decode(),
        _get_obf_str("apps.script"): base64.b64decode("=QHcpJ3Yz5ycwBXY"[::-1].encode()).decode(),
    }
    return _obf_map.get(key, key)

#!/usr/bin/env python3
"""
========================================================
🤖 Wrapper do Robô ABCD com Logs de Depuração
========================================================
📆 Data: 23/07/2025
✏️ Autor: Kiro AIinstco

📋 Descrição:
Wrapper para o Robô ABCD que adiciona logs de depuração
completos para monitoramento e testes automáticos.
"""

import time
import traceback
from datetime import datetime
from typing import Optional

# Importar o sistema de logs de depuração
try:
    from ..utils.debug_logger import get_robo_abcd_logger
    robo_logger = get_robo_abcd_logger()
except ImportError:
    try:
        from utils.debug_logger import get_robo_abcd_logger
        robo_logger = get_robo_abcd_logger()
    except ImportError:
        robo_logger = None

# Importar o robô original
try:
    from .Robo_Pilar_ABCD import GeradorPilares, ConfigManager, PainelData, AplicacaoUnificada
except ImportError:
    try:
        from Robo_Pilar_ABCD import GeradorPilares, ConfigManager, PainelData, AplicacaoUnificada
    except ImportError:
        print("❌ Erro: Não foi possível importar o Robô ABCD original")
        GeradorPilares = None
        ConfigManager = None
        PainelData = None
        AplicacaoUnificada = None


class RoboABCDWrapper:
    """Wrapper para o Robô ABCD com logs de depuração"""
    
    def __init__(self, parent=None, master=None):
        """Inicializa o wrapper do robô ABCD"""
        self.start_time = time.time()
        
        if robo_logger:
            robo_logger.section("ROBÔ ABCD - INICIALIZAÇÃO")
            robo_logger.info(f"📅 Data/Hora de início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            robo_logger.info("🤖 Iniciando Robô ABCD com logs de depuração")
        
        try:
            # Inicializar componentes do robô
            if robo_logger:
                robo_logger.subsection("INICIALIZAÇÃO DE COMPONENTES")
                robo_logger.info("🔄 Inicializando ConfigManager...")
            
            self.config_manager = ConfigManager()
            
            if robo_logger:
                robo_logger.info("✅ ConfigManager inicializado")
                robo_logger.info("🔄 Inicializando PainelData...")
            
            self.painel_data = PainelData()
            
            if robo_logger:
                robo_logger.info("✅ PainelData inicializado")
                robo_logger.info("🔄 Inicializando AplicacaoUnificada...")
            
            self.aplicacao = AplicacaoUnificada()
            
            if robo_logger:
                robo_logger.info("✅ AplicacaoUnificada inicializada")
                robo_logger.info("🔄 Inicializando GeradorPilares...")
            
            self.gerador = GeradorPilares(parent, master)
            
            if robo_logger:
                robo_logger.info("✅ GeradorPilares inicializado")
                robo_logger.info("✅ Todos os componentes inicializados com sucesso!")
            
        except Exception as e:
            error_msg = f"Erro ao inicializar componentes do Robô ABCD: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
                robo_logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def carregar_configuracoes(self):
        """Carrega configurações com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("CARREGAMENTO DE CONFIGURAÇÕES")
            robo_logger.info("🔄 Carregando configurações...")
        
        try:
            self.gerador.carregar_configuracoes()
            
            if robo_logger:
                robo_logger.info("✅ Configurações carregadas com sucesso")
                
        except Exception as e:
            error_msg = f"Erro ao carregar configurações: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def salvar_configuracoes(self):
        """Salva configurações com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("SALVAMENTO DE CONFIGURAÇÕES")
            robo_logger.info("🔄 Salvando configurações...")
        
        try:
            self.gerador.salvar_configuracoes()
            
            if robo_logger:
                robo_logger.info("✅ Configurações salvas com sucesso")
                
        except Exception as e:
            error_msg = f"Erro ao salvar configurações: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def criar_interface(self):
        """Cria a interface com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("CRIAÇÃO DA INTERFACE")
            robo_logger.info("🔄 Criando interface do usuário...")
        
        try:
            self.gerador.criar_interface()
            
            if robo_logger:
                robo_logger.info("✅ Interface criada com sucesso")
                
        except Exception as e:
            error_msg = f"Erro ao criar interface: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def gerar_script(self):
        """Gera o script com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("GERAÇÃO DE SCRIPT")
            robo_logger.info("🔄 Gerando script de desenho...")
        
        try:
            script = self.gerador.gerar_script()
            
            if robo_logger:
                robo_logger.info("✅ Script gerado com sucesso")
                robo_logger.data_processing("Script gerado", f"Tamanho: {len(script)} caracteres")
            
            return script
            
        except Exception as e:
            error_msg = f"Erro ao gerar script: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def salvar_script(self):
        """Salva o script com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("SALVAMENTO DE SCRIPT")
            robo_logger.info("🔄 Salvando script...")
        
        try:
            resultado = self.gerador.salvar_script()
            
            if robo_logger:
                robo_logger.info("✅ Script salvo com sucesso")
                robo_logger.data_processing("Script salvo", f"Resultado: {resultado}")
            
            return resultado
            
        except Exception as e:
            error_msg = f"Erro ao salvar script: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def calcular_dimensoes_ab(self):
        """Calcula dimensões AB com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("CÁLCULO DIMENSÕES AB")
            robo_logger.info("🔄 Calculando dimensões do painel AB...")
        
        try:
            resultado = self.gerador.calcular_dimensoes_ab()
            
            if robo_logger:
                robo_logger.info("✅ Dimensões AB calculadas com sucesso")
                robo_logger.data_processing("Dimensões AB", f"Resultado: {resultado}")
            
            return resultado
            
        except Exception as e:
            error_msg = f"Erro ao calcular dimensões AB: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def calcular_dimensoes_cd(self):
        """Calcula dimensões CD com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("CÁLCULO DIMENSÕES CD")
            robo_logger.info("🔄 Calculando dimensões do painel CD...")
        
        try:
            resultado = self.gerador.calcular_dimensoes_cd()
            
            if robo_logger:
                robo_logger.info("✅ Dimensões CD calculadas com sucesso")
                robo_logger.data_processing("Dimensões CD", f"Resultado: {resultado}")
            
            return resultado
            
        except Exception as e:
            error_msg = f"Erro ao calcular dimensões CD: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def validar_entrada(self):
        """Valida entrada com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("VALIDAÇÃO DE ENTRADA")
            robo_logger.info("🔄 Validando dados de entrada...")
        
        try:
            resultado = self.gerador.validar_entrada()
            
            if robo_logger:
                robo_logger.info("✅ Validação de entrada concluída")
                robo_logger.data_processing("Validação", f"Resultado: {resultado}")
            
            return resultado
            
        except Exception as e:
            error_msg = f"Erro na validação de entrada: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def limpar_campos(self):
        """Limpa campos com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("LIMPEZA DE CAMPOS")
            robo_logger.info("🔄 Limpando campos da interface...")
        
        try:
            self.gerador.limpar_campos()
            
            if robo_logger:
                robo_logger.info("✅ Campos limpos com sucesso")
                
        except Exception as e:
            error_msg = f"Erro ao limpar campos: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def preencher_dados_teste(self):
        """Preenche dados de teste com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("PREENCHIMENTO DE DADOS DE TESTE")
            robo_logger.info("🔄 Preenchendo dados de teste...")
        
        try:
            self.gerador.preencher_dados_teste()
            
            if robo_logger:
                robo_logger.info("✅ Dados de teste preenchidos com sucesso")
                
        except Exception as e:
            error_msg = f"Erro ao preencher dados de teste: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def criar_janela_configuracoes(self):
        """Cria janela de configurações com logs de depuração"""
        if robo_logger:
            robo_logger.subsection("JANELA DE CONFIGURAÇÕES")
            robo_logger.info("🔄 Criando janela de configurações...")
        
        try:
            self.gerador.criar_janela_configuracoes()
            
            if robo_logger:
                robo_logger.info("✅ Janela de configurações criada com sucesso")
                
        except Exception as e:
            error_msg = f"Erro ao criar janela de configurações: {str(e)}"
            if robo_logger:
                robo_logger.error(error_msg)
            raise
    
    def finalizar(self):
        """Finaliza o robô com logs de depuração"""
        if robo_logger:
            end_time = time.time()
            duration = end_time - self.start_time
            robo_logger.performance("Tempo total do Robô ABCD", duration)
            robo_logger.section("FINALIZAÇÃO DO ROBÔ ABCD")
            robo_logger.info(f"📅 Data/Hora de término: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            robo_logger.info("✅ Robô ABCD finalizado com sucesso!")


# Função de conveniência para criar o wrapper
def criar_robo_abcd(parent=None, master=None) -> RoboABCDWrapper:
    """
    Função de conveniência para criar o wrapper do Robô ABCD
    
    Args:
        parent: Widget pai
        master: Widget master
        
    Returns:
        RoboABCDWrapper: Instância do wrapper configurado
    """
    return RoboABCDWrapper(parent, master)


# Função para executar o robô ABCD com logs completos
def executar_robo_abcd(parent=None, master=None):
    """
    Executa o robô ABCD com logs de depuração completos
    
    Args:
        parent: Widget pai
        master: Widget master
        
    Returns:
        RoboABCDWrapper: Instância do robô executado
    """
    try:
        robo = criar_robo_abcd(parent, master)
        robo.carregar_configuracoes()
        robo.criar_interface()
        return robo
    except Exception as e:
        if robo_logger:
            robo_logger.error(f"Erro ao executar Robô ABCD: {str(e)}")
        raise
