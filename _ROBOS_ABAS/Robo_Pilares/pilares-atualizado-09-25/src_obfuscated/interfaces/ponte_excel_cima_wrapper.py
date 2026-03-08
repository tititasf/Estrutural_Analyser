
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
🌉 Wrapper da Ponte Excel CIMA com Logs de Depuração
========================================================
📆 Data: 23/07/2025
✏️ Autor: Kiro AIinstco

📋 Descrição:
Wrapper para a Ponte Excel CIMA que adiciona logs de depuração
completos para monitoramento e testes automáticos.
"""

import os
import sys
import time
import traceback
from datetime import datetime
from typing import Optional

# IMPORTAR HELPER FROZEN GLOBAL - garante que paths estão configurados
try:
    from _frozen_helper import ensure_paths
    ensure_paths()
except ImportError:
    try:
        from src._frozen_helper import ensure_paths
        ensure_paths()
    except ImportError:
        try:
            from _ensure_frozen import ensure
            ensure()
        except ImportError:
            # Fallback manual
            if getattr(sys, 'frozen', False):
                script_dir = os.path.dirname(sys.executable)
                if script_dir not in sys.path:
                    sys.path.insert(0, script_dir)
                src_dir = os.path.join(script_dir, 'src')
                if os.path.exists(src_dir) and src_dir not in sys.path:
                    sys.path.insert(0, src_dir)
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                parent_dir = os.path.dirname(current_dir)
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)

# Importar o sistema de logs de depuração com múltiplos fallbacks
try:
    from ..utils.debug_logger import get_ponte_excel_cima_logger
    ponte_logger = get_ponte_excel_cima_logger()
except ImportError:
    try:
        from utils.debug_logger import get_ponte_excel_cima_logger
        ponte_logger = get_ponte_excel_cima_logger()
    except ImportError:
        try:
            from src.utils.debug_logger import get_ponte_excel_cima_logger
            ponte_logger = get_ponte_excel_cima_logger()
        except ImportError:
            ponte_logger = None

# Importar a ponte original com múltiplos fallbacks
try:
    from .CIMA_FUNCIONAL_EXCEL import ConectorExcelCIMA, ExcelManager, DataProcessor
except ImportError:
    try:
        from CIMA_FUNCIONAL_EXCEL import ConectorExcelCIMA, ExcelManager, DataProcessor
    except ImportError:
        try:
            from src.interfaces.CIMA_FUNCIONAL_EXCEL import ConectorExcelCIMA, ExcelManager, DataProcessor
        except ImportError:
            try:
                from interfaces.CIMA_FUNCIONAL_EXCEL import ConectorExcelCIMA, ExcelManager, DataProcessor
            except ImportError:
                print("❌ Erro: Não foi possível importar a Ponte Excel CIMA original")
                ConectorExcelCIMA = None
                ExcelManager = None
                DataProcessor = None


class PonteExcelCIMAWrapper:
    """Wrapper para a Ponte Excel CIMA com logs de depuração"""
    
    def __init__(self, excel_file_path: str = None):
        """Inicializa o wrapper da ponte Excel CIMA"""
        self.start_time = time.time()
        
        if ponte_logger:
            ponte_logger.section("PONTE EXCEL CIMA - INICIALIZAÇÃO")
            ponte_logger.info(f"📅 Data/Hora de início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            ponte_logger.info("🌉 Iniciando Ponte Excel CIMA com logs de depuração")
        
        try:
            # Inicializar componentes da ponte
            if ponte_logger:
                ponte_logger.subsection("INICIALIZAÇÃO DE COMPONENTES")
                ponte_logger.info("🔄 Inicializando ExcelManager...")
            
            self.excel_manager = ExcelManager()
            
            if ponte_logger:
                ponte_logger.info("✅ ExcelManager inicializado")
                ponte_logger.info("🔄 Inicializando DataProcessor...")
            
            self.data_processor = DataProcessor()
            
            if ponte_logger:
                ponte_logger.info("✅ DataProcessor inicializado")
                ponte_logger.info("🔄 Inicializando ConectorExcelCIMA...")
            
            self.conector = ConectorExcelCIMA(excel_file_path)
            
            if ponte_logger:
                ponte_logger.info("✅ ConectorExcelCIMA inicializado")
                ponte_logger.info("✅ Todos os componentes inicializados com sucesso!")
            
        except Exception as e:
            error_msg = f"Erro ao inicializar componentes da Ponte Excel CIMA: {str(e)}"
            if ponte_logger:
                ponte_logger.error(error_msg)
                ponte_logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def conectar_excel(self, file_path: str):
        """Conecta ao arquivo Excel com logs de depuração"""
        if ponte_logger:
            ponte_logger.subsection("CONEXÃO COM EXCEL")
            ponte_logger.info(f"🔄 Conectando ao arquivo Excel: {file_path}")
        
        try:
            resultado = self.conector.conectar_excel(file_path)
            
            if ponte_logger:
                ponte_logger.info("✅ Conexão com Excel estabelecida com sucesso")
                ponte_logger.data_processing("Conexão Excel", f"Resultado: {resultado}")
            
            return resultado
            
        except Exception as e:
            error_msg = f"Erro ao conectar com Excel: {str(e)}"
            if ponte_logger:
                ponte_logger.error(error_msg)
            raise
    
    def ler_dados(self, sheet_name: str = None):
        """Lê dados do Excel com logs de depuração"""
        if ponte_logger:
            ponte_logger.subsection("LEITURA DE DADOS")
            ponte_logger.info(f"🔄 Lendo dados da planilha: {sheet_name or 'padrão'}")
        
        try:
            dados = self.conector.ler_dados(sheet_name)
            
            if ponte_logger:
                ponte_logger.info("✅ Dados lidos com sucesso")
                ponte_logger.data_processing("Dados lidos", f"Quantidade: {len(dados)} registros")
            
            return dados
            
        except Exception as e:
            error_msg = f"Erro ao ler dados do Excel: {str(e)}"
            if ponte_logger:
                ponte_logger.error(error_msg)
            raise
    
    def processar_dados(self, dados):
        """Processa dados com logs de depuração"""
        if ponte_logger:
            ponte_logger.subsection("PROCESSAMENTO DE DADOS")
            ponte_logger.info("🔄 Processando dados...")
        
        try:
            dados_processados = self.data_processor.processar(dados)
            
            if ponte_logger:
                ponte_logger.info("✅ Dados processados com sucesso")
                ponte_logger.data_processing("Dados processados", f"Quantidade: {len(dados_processados)} registros")
            
            return dados_processados
            
        except Exception as e:
            error_msg = f"Erro ao processar dados: {str(e)}"
            if ponte_logger:
                ponte_logger.error(error_msg)
            raise
    
    def escrever_dados(self, dados, sheet_name: str = None):
        """Escreve dados no Excel com logs de depuração"""
        if ponte_logger:
            ponte_logger.subsection("ESCRITA DE DADOS")
            ponte_logger.info(f"🔄 Escrevendo dados na planilha: {sheet_name or 'padrão'}")
        
        try:
            resultado = self.conector.escrever_dados(dados, sheet_name)
            
            if ponte_logger:
                ponte_logger.info("✅ Dados escritos com sucesso")
                ponte_logger.data_processing("Dados escritos", f"Resultado: {resultado}")
            
            return resultado
            
        except Exception as e:
            error_msg = f"Erro ao escrever dados no Excel: {str(e)}"
            if ponte_logger:
                ponte_logger.error(error_msg)
            raise
    
    def validar_dados(self, dados):
        """Valida dados com logs de depuração"""
        if ponte_logger:
            ponte_logger.subsection("VALIDAÇÃO DE DADOS")
            ponte_logger.info("🔄 Validando dados...")
        
        try:
            resultado = self.data_processor.validar(dados)
            
            if ponte_logger:
                ponte_logger.info("✅ Validação de dados concluída")
                ponte_logger.data_processing("Validação", f"Resultado: {resultado}")
            
            return resultado
            
        except Exception as e:
            error_msg = f"Erro na validação de dados: {str(e)}"
            if ponte_logger:
                ponte_logger.error(error_msg)
            raise
    
    def exportar_para_script(self, dados, output_path: str):
        """Exporta dados para script com logs de depuração"""
        if ponte_logger:
            ponte_logger.subsection("EXPORTAÇÃO PARA SCRIPT")
            ponte_logger.info(f"🔄 Exportando dados para script: {output_path}")
        
        try:
            resultado = self.conector.exportar_para_script(dados, output_path)
            
            if ponte_logger:
                ponte_logger.info("✅ Exportação para script concluída")
                ponte_logger.file_operation("Exportação script", output_path, "OK")
            
            return resultado
            
        except Exception as e:
            error_msg = f"Erro ao exportar para script: {str(e)}"
            if ponte_logger:
                ponte_logger.error(error_msg)
            raise
    
    def fechar_conexao(self):
        """Fecha conexão com logs de depuração"""
        if ponte_logger:
            ponte_logger.subsection("FECHAMENTO DE CONEXÃO")
            ponte_logger.info("🔄 Fechando conexão com Excel...")
        
        try:
            self.conector.fechar_conexao()
            
            if ponte_logger:
                ponte_logger.info("✅ Conexão fechada com sucesso")
                
        except Exception as e:
            error_msg = f"Erro ao fechar conexão: {str(e)}"
            if ponte_logger:
                ponte_logger.error(error_msg)
            raise
    
    def finalizar(self):
        """Finaliza a ponte com logs de depuração"""
        if ponte_logger:
            end_time = time.time()
            duration = end_time - self.start_time
            ponte_logger.performance("Tempo total da Ponte Excel CIMA", duration)
            ponte_logger.section("FINALIZAÇÃO DA PONTE EXCEL CIMA")
            ponte_logger.info(f"📅 Data/Hora de término: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            ponte_logger.info("✅ Ponte Excel CIMA finalizada com sucesso!")


# Função de conveniência para criar o wrapper
def criar_ponte_excel_cima(excel_file_path: str = None) -> PonteExcelCIMAWrapper:
    """
    Função de conveniência para criar o wrapper da Ponte Excel CIMA
    
    Args:
        excel_file_path: Caminho para o arquivo Excel
        
    Returns:
        PonteExcelCIMAWrapper: Instância do wrapper configurado
    """
    return PonteExcelCIMAWrapper(excel_file_path)


# Função para executar a ponte Excel CIMA com logs completos
def executar_ponte_excel_cima(excel_file_path: str, output_path: str = None):
    """
    Executa a ponte Excel CIMA com logs de depuração completos
    
    Args:
        excel_file_path: Caminho para o arquivo Excel
        output_path: Caminho para o arquivo de saída
        
    Returns:
        PonteExcelCIMAWrapper: Instância da ponte executada
    """
    try:
        ponte = criar_ponte_excel_cima(excel_file_path)
        ponte.conectar_excel(excel_file_path)
        dados = ponte.ler_dados()
        dados_processados = ponte.processar_dados(dados)
        
        if output_path:
            ponte.exportar_para_script(dados_processados, output_path)
        
        return ponte
    except Exception as e:
        if ponte_logger:
            ponte_logger.error(f"Erro ao executar Ponte Excel CIMA: {str(e)}")
        raise
