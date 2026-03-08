
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

"""
========================================================
🔧 Robust Path Resolver - PilarAnalyzer
========================================================
📆 Data: 23/07/2025
✏️ Autor: Kiro AI

📋 Descrição:
Módulo para resolução robusta de caminhos e detecção
de robôs disponíveis no sistema.
"""

import os
import sys
from pathlib import Path
import json

# Importar inicializador frozen ANTES de qualquer outra coisa
# Mas evitar import circular se já estamos dentro de utils
_importing_frozen_init = False
if not _importing_frozen_init:
    try:
        _importing_frozen_init = True
        try:
            from utils.__frozen_init__ import ensure_frozen_paths
            ensure_frozen_paths()
        except (ImportError, AttributeError):
            try:
                import importlib.util
                current_file = os.path.abspath(__file__)
                utils_dir = os.path.dirname(current_file)
                frozen_init_path = os.path.join(utils_dir, '__frozen_init__.py')
                if os.path.exists(frozen_init_path):
                    spec = importlib.util.spec_from_file_location("__frozen_init__", frozen_init_path)
                    if spec and spec.loader:
                        frozen_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(frozen_module)
                        if hasattr(frozen_module, 'ensure_frozen_paths'):
                            frozen_module.ensure_frozen_paths()
            except Exception:
                pass  # Se não conseguir importar, continua normalmente
    except Exception:
        pass  # Se não conseguir importar, continua normalmente
    finally:
        _importing_frozen_init = False

def _is_frozen() -> bool:
    """Retorna True quando executando em binário empacotado (PyInstaller/Nuitka)."""
    is_frozen = getattr(sys, 'frozen', False) is True
    
    # Detecção alternativa para Nuitka (que não define sys.frozen automaticamente)
    if not is_frozen and hasattr(sys, 'executable') and sys.executable:
        exe_name = os.path.basename(sys.executable).lower()
        exe_dir = os.path.dirname(sys.executable)
        
        # 1. Se é .exe e o nome NÃO é python.exe
        if exe_name.endswith('.exe') and exe_name != 'python.exe':
            is_frozen = True
        
        # 2. Verificar caminho do executável (Nuitka usa .dist)
        if not is_frozen:
            if '.dist' in exe_dir or 'dist_nuitka' in exe_dir or 'dist_debug' in exe_dir:
                is_frozen = True
    
    return is_frozen


def _runtime_root() -> str:
    """Diretório base em runtime, ciente de freeze (PyInstaller e Nuitka).
    
    Para PyInstaller onefile:
    - Arquivos de leitura (config, templates) estão em _MEIPASS
    - Arquivos de escrita (output, logs) devem estar no diretório do executável
    """
    if _is_frozen():
        # PyInstaller: usa sys._MEIPASS para arquivos temporários (onefile)
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller onefile: arquivos extraídos estão em _MEIPASS
            # Para arquivos de CONFIGURAÇÃO (leitura), usar _MEIPASS
            # Para arquivos de OUTPUT (escrita), usar diretório do executável
            meipass_config = os.path.join(sys._MEIPASS, 'config')
            if os.path.exists(meipass_config):
                # Retornar _MEIPASS para que config/ seja encontrado
                return sys._MEIPASS
            # Fallback: usar diretório do executável
            return os.path.dirname(sys.executable)
        else:
            # Nuitka: arquivos estão no mesmo diretório do executável
            return os.path.dirname(sys.executable)
    
    # árvore de fontes (não congelado)
    # Se estamos em src/utils/robust_path_resolver.py, precisamos subir 3 níveis para o root
    current_dir = os.path.dirname(os.path.abspath(__file__))  # src/utils
    parent_dir = os.path.dirname(current_dir)  # src
    project_root = os.path.dirname(parent_dir)  # raiz do projeto
    return project_root


def _user_data_root() -> str:
    """Pasta de dados do usuário (para logs/output)"""
    local_appdata = os.getenv('LOCALAPPDATA') or os.path.expanduser('~')
    return os.path.join(local_appdata, 'PilarAnalyzer')


class RobustPathResolver:
    """Classe para resolução robusta de caminhos"""
    
    def __init__(self):
        # Base ciente de freeze
        self.project_root = _runtime_root()
        self.base_dir = os.path.join(self.project_root, 'src', 'utils')
        
    def get_project_root(self):
        """Retorna o diretório raiz do projeto/instalação em runtime."""
        return self.project_root
    
    def get_robots_dir(self):
        """Retorna o diretório dos robôs"""
        return os.path.join(self.project_root, 'src', 'robots')
    
    def get_config_dir(self):
        """Retorna o diretório de configurações"""
        return os.path.join(self.project_root, 'config')
    
    def get_templates_dir(self):
        """Retorna o diretório de templates"""
        return os.path.join(self.project_root, 'templates')

    def get_user_logs_dir(self) -> str:
        """Pasta de logs (usuário) em runtime."""
        return os.path.join(_user_data_root(), 'logs')

    def get_user_output_dir(self) -> str:
        """Pasta de output (usuário) em runtime.
        
        Em frozen mode, retorna o diretório do executável/output
        Em desenvolvimento, retorna a pasta do usuário
        """
        if _is_frozen():
            # Em frozen, output deve estar no mesmo diretório do executável
            return os.path.join(os.path.dirname(sys.executable), 'output')
        return os.path.join(_user_data_root(), 'output')
    
    def validate_installation(self):
        """Valida se a instalação está correta"""
        required_dirs = [
            self.get_robots_dir(),
            self.get_config_dir(),
            self.get_templates_dir()
        ]
        
        missing = []
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                missing.append(dir_path)
        
        return len(missing) == 0, missing
    
    def find_robot_files(self):
        """Encontra todos os arquivos de robô disponíveis"""
        robots_dir = self.get_robots_dir()
        robot_files = []
        
        if os.path.exists(robots_dir):
            for file in os.listdir(robots_dir):
                if file.startswith('Robo_') and file.endswith('.py'):
                    robot_files.append(os.path.join(robots_dir, file))
        
        return robot_files

# Instância global
robust_path_resolver = RobustPathResolver()

def get_directories():
    """Retorna dicionário com diretórios principais"""
    project_root = robust_path_resolver.get_project_root()
    src_dir = os.path.join(project_root, 'src')
    
    return {
        'project_root': project_root,
        'robots': os.path.join(src_dir, 'robots'),
        'config': os.path.join(project_root, 'config'),
        'templates': os.path.join(project_root, 'templates'),
        'utils': os.path.join(src_dir, 'utils'),
        'interfaces': os.path.join(src_dir, 'interfaces'),
        'core': os.path.join(src_dir, 'core'),
        'automacao': os.path.join(project_root, 'output', 'scripts'),
        'scripts': os.path.join(project_root, 'output', 'scripts'),
        'ordenamento': os.path.join(src_dir, 'utils'),  # Para compatibilidade
        'painel': os.path.join(src_dir, 'utils'),  # Para compatibilidade
        'user_logs': robust_path_resolver.get_user_logs_dir(),
        'user_output': robust_path_resolver.get_user_output_dir()
    }

def get_all_robots():
    """Retorna dicionário com paths dos robôs disponíveis"""
    robots = {}
    
    # Detectar ambiente frozen
    is_frozen = _is_frozen()
    if not is_frozen:
        # Detecção alternativa para Nuitka: verificar se sys.executable é .exe
        if hasattr(sys, 'executable') and sys.executable and sys.executable.endswith('.exe'):
            exe_dir = os.path.dirname(sys.executable)
            if '.dist' in exe_dir or os.path.basename(exe_dir) in ['run.dist', 'dist', 'dist_nuitka', 'dist_debug']:
                is_frozen = True
    
    # DEBUG: Imprimir informações de debug
    project_root = robust_path_resolver.get_project_root()
    print(f"[DEBUG] Project root: {project_root}")
    print(f"[DEBUG] Ambiente frozen: {is_frozen}")
    
    # Mapear os wrappers Excel
    excel_wrappers_map = {
        'cima_excel': {
            'module_path': 'CIMA_FUNCIONAL_EXCEL',
            'import_paths': [
                'interfaces.CIMA_FUNCIONAL_EXCEL',
                'src.interfaces.CIMA_FUNCIONAL_EXCEL',
                'CIMA_FUNCIONAL_EXCEL'
            ],
            'file_path': None
        },
        'abcd_excel': {
            'module_path': 'Abcd_Excel',
            'import_paths': [
                'interfaces.Abcd_Excel',
                'src.interfaces.Abcd_Excel',
                'Abcd_Excel'
            ],
            'file_path': None
        },
        'grades_excel': {
            'module_path': 'GRADE_EXCEL',
            'import_paths': [
                'interfaces.GRADE_EXCEL',
                'src.interfaces.GRADE_EXCEL',
                'GRADE_EXCEL'
            ],
            'file_path': None
        }
    }
    
    # Em ambiente frozen, tentar importar os módulos em vez de verificar existência física
    if is_frozen:
        print(f"[DEBUG] Ambiente frozen detectado - verificando módulos via importação")
        import importlib
        
        for name, wrapper_info in excel_wrappers_map.items():
            print(f"[DEBUG] Verificando {name}...")
            module_found = False
            
            # Tentar importar de múltiplos caminhos
            for import_path in wrapper_info['import_paths']:
                try:
                    module = importlib.import_module(import_path)
                    # Se conseguir importar, o módulo existe
                    print(f"[OK] Wrapper Excel encontrado (importação): {name} -> {import_path}")
                    # Em ambiente frozen, usar o nome do módulo como path (não o caminho físico)
                    robots[name] = import_path
                    module_found = True
                    break
                except ImportError:
                    continue
            
            if not module_found:
                print(f"[ERRO] Wrapper Excel não encontrado (importação): {name}")
    else:
        # Em ambiente de desenvolvimento, verificar existência física dos arquivos
        interfaces_dir = os.path.join(project_root, 'src', 'interfaces')
        print(f"[DEBUG] Interfaces dir: {interfaces_dir}")
        print(f"[DEBUG] Interfaces dir exists: {os.path.exists(interfaces_dir)}")
        
        excel_wrappers = {
            'cima_excel': os.path.join(interfaces_dir, 'CIMA_FUNCIONAL_EXCEL.py'),
            'abcd_excel': os.path.join(interfaces_dir, 'Abcd_Excel.py'),
            'grades_excel': os.path.join(interfaces_dir, 'GRADE_EXCEL.py')
        }
        
        # Verificar se os wrappers Excel existem e adicioná-los
        for name, path in excel_wrappers.items():
            print(f"[DEBUG] Verificando {name}: {path}")
            print(f"[DEBUG] Arquivo existe: {os.path.exists(path)}")
            if os.path.exists(path):
                robots[name] = path
                print(f"[OK] Wrapper Excel encontrado: {name} -> {path}")
            else:
                print(f"[ERRO] Wrapper Excel não encontrado: {name} -> {path}")
                # DEBUG: Listar conteúdo do diretório
                if os.path.exists(interfaces_dir):
                    print(f"[DEBUG] Conteúdo de {interfaces_dir}:")
                    for item in os.listdir(interfaces_dir):
                        print(f"[DEBUG]   - {item}")
                else:
                    print(f"[DEBUG] Diretório {interfaces_dir} não existe!")
    
    # Depois, mapear os robôs originais como fallback (apenas em ambiente de desenvolvimento)
    if not is_frozen:
        robot_files = robust_path_resolver.find_robot_files()
        
        for robot_file in robot_files:
            robot_name = os.path.basename(robot_file).replace('.py', '').lower()
            robots[robot_name] = robot_file
            
            # Adicionar mapeamentos específicos apenas se os wrappers Excel não existirem
            if 'abcd' in robot_name and 'abcd_excel' not in robots:
                robots['abcd_excel'] = robot_file
            elif 'cima' in robot_name and 'cima_excel' not in robots:
                robots['cima_excel'] = robot_file
            elif 'grade' in robot_name and 'grades_excel' not in robots:
                robots['grades_excel'] = robot_file
    
    # DEBUG: Imprimir resultado final
    print(f"[DEBUG] Robots finais encontrados:")
    for name, path in robots.items():
        print(f"[DEBUG]   {name}: {path}")
    
    return robots

def resolve_path(relative_path):
    """Resolve um caminho relativo para absoluto"""
    if os.path.isabs(relative_path):
        return relative_path
    
    # Tentar a partir do diretório do projeto
    project_path = os.path.join(robust_path_resolver.get_project_root(), relative_path)
    if os.path.exists(project_path):
        return project_path
    
    # Tentar a partir do diretório atual
    current_path = os.path.join(os.getcwd(), relative_path)
    if os.path.exists(current_path):
        return current_path
    
    # Retornar o caminho original se não encontrar
    return relative_path