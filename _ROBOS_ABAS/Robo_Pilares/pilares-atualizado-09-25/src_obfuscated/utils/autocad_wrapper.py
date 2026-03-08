
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
📌 Título do Arquivo: autocad_wrapper.py
📆 Data de Criação: 15/04/2024
✏️ Autor: Claude 3.7 Sonnet
🆔 Versão: 1.0
========================================================

📊 **Resumo Geral**
Wrapper para integração com o AutoCAD.
Gerencia a comunicação e processamento de objetos do AutoCAD.

📎 **Arquivos Relacionados**
- pilar_analyzer.py: Lógica de negócio
- pilar_analyzer_main.py: Ponto de entrada
- funcoes_auxiliares_2_3.py: Interface gráfica

🔷 **ÍNDICE DETALHADO**

🔹 **1. Classe Principal** [L1-100]
   - class AutoCADWrapper
   - Métodos de inicialização
   - Configurações do AutoCAD

🔹 **2. Funções de Seleção** [L101-200]
   - get_selection()
   - process_rectangle()
   - process_lines()
   - process_texts()

🔹 **3. Funções de Cálculo** [L201-300]
   - calculate_distance()
   - calculate_width()
   - find_associated_text()
   - extract_laje_value()

🔹 **4. Funções de Validação** [L301-400]
   - validate_rectangle()
   - validate_line()
   - validate_text()

📖 **Registro de Desenvolvimento**
1. Implementação da integração base
2. Processamento de objetos
3. Cálculos geométricos
4. Validação de dados
"""

# ========================================================
# 📥 Importações do Sistema
# ========================================================
import os
import sys
import math
from typing import Dict, List, Tuple, Optional, Any

try:
    import win32com.client
    import pythoncom
except ImportError as e:
    print(f"ERRO: Falha ao importar módulos necessários: {str(e)}")
    sys.exit(1)

# ========================================================
# 📥 Classe Principal
# ========================================================
class AutoCADWrapper:
    """Wrapper para integração com o AutoCAD"""
    
    def __init__(self):
        """Inicializa o wrapper do AutoCAD"""
        # Configurações
        self.config = {
            'tolerancia_distancia': 300.0,  # mm
            'tolerancia_profundidade': 50.0,  # mm
            'tolerancia_texto': 100.0  # mm
        }
        
        # Inicializar COM
        pythoncom.CoInitialize()
        
        # Conectar ao AutoCAD
        try:
            self.acad = win32com.client.Dispatch("AutoCAD.Application")
            self.doc = self.acad.ActiveDocument
            self.model = self.doc.ModelSpace
        except Exception as e:
            print(f"ERRO ao conectar ao AutoCAD: {str(e)}")
            raise
    
    def get_selection(self) -> Tuple[Any, Any]:
        """Obtém a seleção atual do AutoCAD"""
        try:
            # Obter seleção
            selection = self.doc.SelectionSets.Add("TempSelection")
            selection.SelectOnScreen()
            
            return selection, self.doc
            
        except Exception as e:
            print(f"ERRO ao obter seleção: {str(e)}")
            raise
        finally:
            # Limpar seleção
            if 'selection' in locals():
                selection.Delete()
    
    def process_rectangle(self, selection: Any) -> Optional[Dict]:
        """Processa o retângulo selecionado"""
        try:
            # Encontrar retângulo
            rectangle = None
            for obj in selection:
                if obj.ObjectName == "AcDbPolyline" and len(obj.Coordinates) == 8:
                    rectangle = obj
                    break
            
            if not rectangle:
                return None
            
            # Validar retângulo
            if not self.validate_rectangle(rectangle):
                return None
            
            # Extrair dimensões
            coords = rectangle.Coordinates
            x_coords = coords[::2]
            y_coords = coords[1::2]
            
            comprimento = max(x_coords) - min(x_coords)
            largura = max(y_coords) - min(y_coords)
            altura = self._get_rectangle_height(rectangle)
            
            return {
                'comprimento': comprimento,
                'largura': largura,
                'altura': altura,
                'centro': self._get_rectangle_center(rectangle)
            }
            
        except Exception as e:
            print(f"ERRO ao processar retângulo: {str(e)}")
            return None
    
    def process_lines(self, selection: Any, retangulo: Dict) -> List[Dict]:
        """Processa as linhas selecionadas"""
        try:
            linhas = []
            
            # Processar cada linha
            for obj in selection:
                if obj.ObjectName != "AcDbLine":
                    continue
                
                # Validar linha
                if not self.validate_line(obj):
                    continue
                
                # Determinar lado e tipo
                lado, tipo = self._determine_line_side(obj, retangulo)
                if not lado or not tipo:
                    continue
                
                # Adicionar linha
                linhas.append({
                    'lado': lado,
                    'tipo': tipo,
                    'inicio': obj.StartPoint,
                    'fim': obj.EndPoint
                })
            
            return linhas
            
        except Exception as e:
            print(f"ERRO ao processar linhas: {str(e)}")
            return []
    
    def process_texts(self, selection: Any) -> Dict:
        """Processa os textos selecionados"""
        try:
            textos = {}
            
            # Processar cada texto
            for obj in selection:
                if obj.ObjectName not in ["AcDbText", "AcDbMText"]:
                    continue
                
                # Validar texto
                if not self.validate_text(obj):
                    continue
                
                # Extrair informações
                tipo, valor = self._extract_text_info(obj)
                if not tipo or not valor:
                    continue
                
                # Adicionar texto
                textos[tipo] = {
                    'valor': valor,
                    'posicao': obj.InsertionPoint
                }
            
            return textos
            
        except Exception as e:
            print(f"ERRO ao processar textos: {str(e)}")
            return {}
    
    def calculate_distance(self, linha: Dict, retangulo: Dict) -> float:
        """Calcula a distância entre a linha e o retângulo"""
        try:
            # Calcular ponto médio da linha
            linha_medio = (
                (linha['inicio'][0] + linha['fim'][0]) / 2,
                (linha['inicio'][1] + linha['fim'][1]) / 2
            )
            
            # Calcular distância ao centro do retângulo
            distancia = math.sqrt(
                (linha_medio[0] - retangulo['centro'][0]) ** 2 +
                (linha_medio[1] - retangulo['centro'][1]) ** 2
            )
            
            return distancia
            
        except Exception as e:
            print(f"ERRO ao calcular distância: {str(e)}")
            return 0.0
    
    def calculate_width(self, linha: Dict) -> float:
        """Calcula a largura da linha"""
        try:
            return math.sqrt(
                (linha['fim'][0] - linha['inicio'][0]) ** 2 +
                (linha['fim'][1] - linha['inicio'][1]) ** 2
            )
            
        except Exception as e:
            print(f"ERRO ao calcular largura: {str(e)}")
            return 0.0
    
    def find_associated_text(self, linha: Dict, textos: Dict) -> Optional[Dict]:
        """Encontra o texto associado à linha"""
        try:
            # Calcular ponto médio da linha
            linha_medio = (
                (linha['inicio'][0] + linha['fim'][0]) / 2,
                (linha['inicio'][1] + linha['fim'][1]) / 2
            )
            
            # Procurar texto mais próximo
            texto_mais_proximo = None
            distancia_minima = float('inf')
            
            for tipo, texto in textos.items():
                distancia = math.sqrt(
                    (texto['posicao'][0] - linha_medio[0]) ** 2 +
                    (texto['posicao'][1] - linha_medio[1]) ** 2
                )
                
                if distancia < distancia_minima and distancia < self.config['tolerancia_texto']:
                    distancia_minima = distancia
                    texto_mais_proximo = texto
            
            return texto_mais_proximo
            
        except Exception as e:
            print(f"ERRO ao encontrar texto associado: {str(e)}")
            return None
    
    def extract_laje_value(self, texto: Dict) -> float:
        """Extrai o valor da laje do texto"""
        try:
            # Converter texto para número
            valor = float(texto['valor'])
            
            # Validar valor
            if valor < 0:
                raise ValueError("Valor negativo para laje")
            
            return valor
            
        except Exception as e:
            print(f"ERRO ao extrair valor da laje: {str(e)}")
            return 0.0
    
    def validate_rectangle(self, rectangle: Any) -> bool:
        """Valida o retângulo"""
        try:
            # Verificar número de vértices
            if len(rectangle.Coordinates) != 8:
                return False
            
            # Verificar ângulos retos
            coords = rectangle.Coordinates
            for i in range(0, 8, 2):
                p1 = (coords[i], coords[i+1])
                p2 = (coords[(i+2)%8], coords[(i+3)%8])
                p3 = (coords[(i+4)%8], coords[(i+5)%8])
                
                # Calcular ângulo
                v1 = (p2[0] - p1[0], p2[1] - p1[1])
                v2 = (p3[0] - p2[0], p3[1] - p2[1])
                
                dot = v1[0] * v2[0] + v1[1] * v2[1]
                if abs(dot) > 0.1:  # Tolerância para ângulo reto
                    return False
            
            return True
            
        except Exception as e:
            print(f"ERRO ao validar retângulo: {str(e)}")
            return False
    
    def validate_line(self, line: Any) -> bool:
        """Valida a linha"""
        try:
            # Verificar comprimento
            comprimento = math.sqrt(
                (line.EndPoint[0] - line.StartPoint[0]) ** 2 +
                (line.EndPoint[1] - line.StartPoint[1]) ** 2
            )
            
            if comprimento < 10:  # Tolerância mínima
                return False
            
            return True
            
        except Exception as e:
            print(f"ERRO ao validar linha: {str(e)}")
            return False
    
    def validate_text(self, text: Any) -> bool:
        """Valida o texto"""
        try:
            # Verificar conteúdo
            if not text.TextString.strip():
                return False
            
            return True
            
        except Exception as e:
            print(f"ERRO ao validar texto: {str(e)}")
            return False
    
    def _get_rectangle_height(self, rectangle: Any) -> float:
        """Obtém a altura do retângulo"""
        try:
            # Extrair coordenadas Z
            z_coords = [rectangle.Coordinates[i] for i in range(2, 8, 2)]
            return max(z_coords) - min(z_coords)
            
        except Exception as e:
            print(f"ERRO ao obter altura do retângulo: {str(e)}")
            return 0.0
    
    def _get_rectangle_center(self, rectangle: Any) -> Tuple[float, float]:
        """Obtém o centro do retângulo"""
        try:
            coords = rectangle.Coordinates
            x_coords = coords[::2]
            y_coords = coords[1::2]
            
            return (
                (max(x_coords) + min(x_coords)) / 2,
                (max(y_coords) + min(y_coords)) / 2
            )
            
        except Exception as e:
            print(f"ERRO ao obter centro do retângulo: {str(e)}")
            return (0.0, 0.0)
    
    def _determine_line_side(self, line: Any, retangulo: Dict) -> Tuple[Optional[str], Optional[str]]:
        """Determina o lado e tipo da linha"""
        try:
            # Calcular ponto médio da linha
            linha_medio = (
                (line.StartPoint[0] + line.EndPoint[0]) / 2,
                (line.StartPoint[1] + line.EndPoint[1]) / 2
            )
            
            # Determinar lado (A ou B)
            if abs(linha_medio[0] - retangulo['centro'][0]) > abs(linha_medio[1] - retangulo['centro'][1]):
                lado = 'A' if linha_medio[0] < retangulo['centro'][0] else 'B'
            else:
                lado = 'A' if linha_medio[1] < retangulo['centro'][1] else 'B'
            
            # Determinar tipo (esquerda ou direita)
            if lado in ['A', 'B']:
                if lado == 'A':
                    tipo = 'esquerda' if linha_medio[1] < retangulo['centro'][1] else 'direita'
                else:
                    tipo = 'esquerda' if linha_medio[1] > retangulo['centro'][1] else 'direita'
            else:
                tipo = None
            
            return lado, tipo
            
        except Exception as e:
            print(f"ERRO ao determinar lado da linha: {str(e)}")
            return None, None
    
    def _extract_text_info(self, text: Any) -> Tuple[Optional[str], Optional[float]]:
        """Extrai informações do texto"""
        try:
            # Obter conteúdo
            conteudo = text.TextString.strip()
            
            # Determinar tipo
            if conteudo.startswith('P'):
                tipo = 'pilar'
            elif conteudo.startswith('N'):
                tipo = 'nome'
            elif conteudo.startswith('L'):
                tipo = f"laje_{conteudo[1]}"
            else:
                tipo = None
            
            # Extrair valor
            try:
                valor = float(conteudo.split()[-1])
            except (ValueError, IndexError):
                valor = None
            
            return tipo, valor
            
        except Exception as e:
            print(f"ERRO ao extrair informações do texto: {str(e)}")
            return None, None

# Exportar as funções para serem usadas como fallback
__all__ = [
    'get_autocad_selection',
    'get_text_objects',
    'get_line_intersections',
    'extract_laje_value_from_text'
] 