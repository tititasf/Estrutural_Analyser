
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

import os
from natsort import natsorted
import re
from pathlib import Path
import time
import json
import sys

# IMPORTAR HELPER FROZEN GLOBAL - garante que paths estão configurados
try:
    from _frozen_helper import ensure_paths
    ensure_paths()
except ImportError:
    try:
        from src._frozen_helper import ensure_paths
        ensure_paths()
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
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Importar robust_path_resolver com múltiplos fallbacks
try:
    from utils.robust_path_resolver import robust_path_resolver
except ImportError:
    try:
        from src.utils.robust_path_resolver import robust_path_resolver
    except ImportError:
        try:
            import importlib.util
            current_file = os.path.abspath(__file__)
            utils_dir = os.path.join(os.path.dirname(os.path.dirname(current_file)), 'utils')
            robust_path = os.path.join(utils_dir, 'robust_path_resolver.py')
            if os.path.exists(robust_path):
                spec = importlib.util.spec_from_file_location("robust_path_resolver", robust_path)
                if spec and spec.loader:
                    robust_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(robust_module)
                    robust_path_resolver = robust_module.robust_path_resolver
        except Exception:
            raise ImportError("Não foi possível importar robust_path_resolver")

def get_template_path_cima():
    """Obtém o path do template de forma robusta"""
    try:
        from config_paths import TEMPLATES_DIR
        return Path(TEMPLATES_DIR) / "templates_configuracao_ordenador_CIMA.json"
    except ImportError:
        # Fallback relativo
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent
        return project_root / "templates" / "templates_configuracao_ordenador_CIMA.json"

def get_config_path_cima():
    """Obtém o path da configuração de forma robusta"""
    try:
        from config_paths import CONFIG_DIR
        return Path(CONFIG_DIR) / "configuracao_ordenador_CIMA.json"
    except ImportError:
        # Fallback relativo
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent
        return project_root / "config" / "configuracao_ordenador_CIMA.json"

def carregar_template_cima():
    """Carrega o template específico para visão de cima"""
    caminho_template = get_template_path_cima()
    
    if caminho_template.exists():
        with open(caminho_template, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print(f"ERRO: Template para visão de cima não encontrado em: {caminho_template}")
        return None

def carregar_configuracao_cima():
    """Carrega a configuração específica para visão de cima"""
    caminho_config = get_config_path_cima()
    
    if caminho_config.exists():
        with open(caminho_config, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print(f"ERRO: Configuração para visão de cima não encontrada em: {caminho_config}")
        return None

class ProcessadorCoordenadasCima:
    def __init__(self, numero_colunas=3, distancia_x_colunas=1200, distancia_y_linhas=-1000, distancia_y_extra=200, linhas_para_extra=2):
        """
        Inicializa o processador com as configurações específicas para visão de cima:
        
        Args:
            numero_colunas (int): Quantidade de colunas no layout (padrão: 3 para visão de cima)
            distancia_x_colunas (float): Distância X entre colunas (padrão: 1200 para visão de cima)
            distancia_y_linhas (float): Distância Y entre linhas (padrão: -1000 para visão de cima)
            distancia_y_extra (float): Distância Y extra a ser aplicada (padrão: 200 para visão de cima)
            linhas_para_extra (int): A cada quantas linhas aplicar o Y extra (padrão: 2 para visão de cima)
        """
        # Configurações principais
        self.numero_colunas = numero_colunas
        self.distancia_x_colunas = distancia_x_colunas
        self.distancia_y_linhas = distancia_y_linhas
        self.distancia_y_extra = distancia_y_extra
        self.linhas_para_extra = linhas_para_extra
        
        # Controle interno
        self.movimento_atual = 0
        self.alteracao_x = 0
        self.alteracao_y = 0
        
        # Posição inicial fixa (ponto de referência)
        self.posicao_inicial_x = -800
        
        # Referência da moldura (para alinhamento)
        self.referencia_y_moldura = None
    
    def aplicar_configuracoes(self, config_dict):
        """Aplica configurações vindas da interface"""
        if 'numero_colunas' in config_dict:
            self.numero_colunas = config_dict['numero_colunas']
        if 'distancia_x_colunas' in config_dict:
            self.distancia_x_colunas = config_dict['distancia_x_colunas']
        if 'distancia_y_linhas' in config_dict:
            self.distancia_y_linhas = config_dict['distancia_y_linhas']
        if 'distancia_y_extra' in config_dict:
            self.distancia_y_extra = config_dict['distancia_y_extra']
        if 'linhas_para_extra' in config_dict:
            self.linhas_para_extra = config_dict['linhas_para_extra']
        
        print("Configurações aplicadas com sucesso!")
    
    def get_configuracao_atual(self):
        """Retorna as configurações atuais"""
        return {
            'numero_colunas': self.numero_colunas,
            'distancia_x_colunas': self.distancia_x_colunas,
            'distancia_y_linhas': self.distancia_y_linhas,
            'distancia_y_extra': self.distancia_y_extra,
            'linhas_para_extra': self.linhas_para_extra,
            'movimento_atual': self.movimento_atual
        }
    
    def calcular_deslocamento(self):
        """Calcula o deslocamento X e Y baseado no movimento atual"""
        # Calcula qual linha estamos (quantas linhas completas já foram preenchidas)
        linha_atual = self.movimento_atual // self.numero_colunas
        
        # Calcula a posição dentro da linha atual (0, 1, 2, ...)
        posicao_na_linha = self.movimento_atual % self.numero_colunas
        
        # Calcula o deslocamento X
        if posicao_na_linha == 0:
            # Primeira coluna: posição inicial
            deslocamento_x = self.posicao_inicial_x
        else:
            # Demais colunas: posição inicial + (posição na linha * distância entre colunas)
            deslocamento_x = self.posicao_inicial_x + (posicao_na_linha * self.distancia_x_colunas)
        
        # Calcula o deslocamento Y base
        deslocamento_y = linha_atual * self.distancia_y_linhas
        
        # Aplica distância Y extra se configurada
        if self.linhas_para_extra > 0 and linha_atual > 0:
            # Calcula quantas vezes aplicar o Y extra
            vezes_extra = linha_atual // self.linhas_para_extra
            deslocamento_y += vezes_extra * self.distancia_y_extra
        
        return deslocamento_x, deslocamento_y
    
    def extrair_coordenadas(self, linhas):
        """Extrai coordenadas das linhas 8-11 do arquivo"""
        coords = []
        for linha in linhas[7:11]:  # índices 7-10 para linhas 8-11
            match = re.search(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', linha)
            if match:
                coords.append((float(match.group(1)), float(match.group(2))))
        return coords
    
    def calcular_dimensoes(self, coords):
        """Calcula largura e altura do retângulo"""
        if not coords:
            return 0, 0
        x_coords = [x for x, _ in coords]
        y_coords = [y for _, y in coords]
        largura = abs(max(x_coords) - min(x_coords))
        altura = abs(max(y_coords) - min(y_coords))
        return largura, altura
    
    def find_moldura_y(self, linhas):
        """Encontra a coordenada Y de inserção do bloco MULDURA2 no arquivo .scr."""
        for i, linha in enumerate(linhas):
            if "-INSERT" in linha.upper() and i + 1 < len(linhas):
                # Verifica a linha seguinte para 'MULDURA2'
                if "MULDURA2" in linhas[i+1].upper():
                    # A coordenada estará na próxima linha após 'MULDURA2'
                    if i + 2 < len(linhas):
                        match = re.search(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', linhas[i+2])
                        if match:
                            return float(match.group(2))
        return None
    
    def processar_arquivo(self, caminho_arquivo):
        """Processa um único arquivo .scr, tentando até 100 vezes em caso de erro de permissão."""
        tentativas = 0
        while tentativas < 100:
            try:
                # Lê o arquivo em UTF-16
                with open(caminho_arquivo, 'r', encoding='utf-16') as f:
                    linhas = f.readlines()
                
                # Encontra a coordenada Y da moldura para alinhamento (se necessário)
                ajuste_y_moldura = 0
                if self.referencia_y_moldura is not None:
                    current_moldura_y = self.find_moldura_y(linhas)
                    if current_moldura_y is not None:
                        ajuste_y_moldura = self.referencia_y_moldura - current_moldura_y
                    else:
                        print(f"Aviso: Moldura não encontrada em {Path(caminho_arquivo).name}. O ajuste Y por moldura será ignorado para este arquivo.")
                
                # Extrai e processa coordenadas
                coords = self.extrair_coordenadas(linhas)
                largura, altura = self.calcular_dimensoes(coords)
                
                # Calcula o deslocamento atual
                deslocamento_x, deslocamento_y = self.calcular_deslocamento()
                
                # Aplica ajuste da moldura se necessário
                total_deslocamento_y = deslocamento_y + ajuste_y_moldura
                
                # Cria novo conteúdo com coordenadas ajustadas
                novo_conteudo = []
                for i, linha in enumerate(linhas):
                    # Ignora linhas com PD: ou NÍVEL DE CHEGADA
                    if any(padrao in linha for padrao in ['PD:', 'NÍVEL DE CHEGADA']):
                        nova_linha = linha
                    else:
                        # Verifica se a quarta linha acima contém "_TEXT"
                        if i >= 4 and "_TEXT" in linhas[i-4].upper():
                            nova_linha = linha  # Não processa se _TEXT está 4 linhas acima
                        else:
                            nova_linha = re.sub(
                                r'(-?\d+\.?\d*),(-?\d+\.?\d*)',
                                lambda m: f"{float(m.group(1)) + deslocamento_x:.4f},{float(m.group(2)) + total_deslocamento_y:.4f}",
                                linha
                            )
                    novo_conteudo.append(nova_linha)
                
                # Salva arquivo modificado
                with open(caminho_arquivo, 'w', encoding='utf-16') as f:
                    f.writelines(novo_conteudo)
                
                # Atualiza valores globais
                self.alteracao_x += deslocamento_x
                self.alteracao_y += total_deslocamento_y
                self.movimento_atual += 1
                
                # Log de processamento
                self.exibir_log(
                    Path(caminho_arquivo).name,
                    largura,
                    altura,
                    deslocamento_x,
                    total_deslocamento_y
                )
                break  # Sucesso, sai do loop
            except PermissionError as e:
                tentativas += 1
                print(f"Permissão negada ao acessar {caminho_arquivo}. Tentando novamente ({tentativas}/100)...")
                time.sleep(0.5)
                if tentativas == 100:
                    print(f"Erro de permissão persistente após 100 tentativas: {caminho_arquivo}")
            except Exception as e:
                print(f"Erro ao processar {caminho_arquivo}: {str(e)}")
                break
    
    def exibir_log(self, nome_arquivo, largura, altura, alteracao_x_aplicada, alteracao_y_aplicada):
        """Exibe informações de log do processamento"""
        print(f"\nArquivo: {nome_arquivo}")
        print(f"Dimensões do retângulo: Largura = {largura:.1f}, Altura = {altura:.1f}")
        print(f"Alteracao X aplicada: {alteracao_x_aplicada:.1f}")
        print(f"Alteracao Y aplicada: {alteracao_y_aplicada:.1f}")
        print(f"Atualizacao X ajustada para: {self.alteracao_x:.1f}")
        print(f"Atualizacao Y ajustada para: {self.alteracao_y:.1f}")

    def exibir_configuracao(self):
        """Exibe a configuração atual do processador"""
        config = self.get_configuracao_atual()
        print("\n" + "="*50)
        print("CONFIGURAÇÃO ATUAL DO PROCESSADOR")
        print("="*50)
        print(f"Quantidade de colunas: {config['numero_colunas']}")
        print(f"Distância X entre colunas: {config['distancia_x_colunas']}")
        print(f"Distância Y entre linhas: {config['distancia_y_linhas']}")
        print(f"Distância Y extra: {config['distancia_y_extra']}")
        print(f"A cada quantas linhas aplicar Y extra: {config['linhas_para_extra']}")
        print(f"Movimento atual: {config['movimento_atual']}")
        print("="*50)

def atualizar_comando_pilar_cima(pasta_selecionada):
    """Atualiza o caminho no arquivo comando_pilar_combinado_TPTP.scr (específico para visão de cima)"""
    caminho_comando_pilar = Path(os.path.join(robust_path_resolver.get_project_root(), "output", "comando_pilar_combinado.scr"))
    
    if caminho_comando_pilar.exists():
        with open(caminho_comando_pilar, 'r', encoding='utf-16') as f:
            linhas = f.readlines()
        
        # Adiciona o comando SCRIPT e o novo caminho com barras invertidas
        linhas = ["_SCRIPT\n", f"{pasta_selecionada}/1.scr\n"]
        
        with open(caminho_comando_pilar, 'w', encoding='utf-16') as f:
            f.writelines(linhas)
        print(f"\nVISÃO DE CIMA - Arquivo comando_pilar_combinado_TPTP.scr atualizado com sucesso para a pasta: {pasta_selecionada}")
    else:
        print(f"VISÃO DE CIMA - Arquivo comando_pilar_combinado_TPTP.scr não encontrado no caminho: {caminho_comando_pilar}")

if __name__ == "__main__":
    # Exemplo de uso do sistema para visão de cima
    print("EXEMPLO DE USO DO SISTEMA DE VISÃO DE CIMA")
    print("="*55)
    
    # Cria processador com configurações padrão para visão de cima
    processador = ProcessadorCoordenadasCima(
        numero_colunas=3,
        distancia_x_colunas=1200,
        distancia_y_linhas=-1000,
        distancia_y_extra=200,
        linhas_para_extra=2
    )
    processador.exibir_configuracao()
    
    # Exemplo com configurações personalizadas para visão de cima
    print("\nExemplo com configurações personalizadas para visão de cima:")
    processador2 = ProcessadorCoordenadasCima(
        numero_colunas=4,
        distancia_x_colunas=1300,
        distancia_y_linhas=-1100,
        distancia_y_extra=250,
        linhas_para_extra=3
    )
    processador2.exibir_configuracao()
    
    print("\nPara usar na interface gráfica específica para visão de cima:")
    from interface_ordenador_cima import InterfaceOrdenadorCima
    app = InterfaceOrdenadorCima()
    app.iniciar()