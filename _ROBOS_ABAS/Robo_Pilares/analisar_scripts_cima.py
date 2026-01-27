"""
Script de Análise Comparativa: Parafusos e Grades em Scripts CIMA

Extrai valores de parafusos e grades de scripts gerados e compara com valores esperados.
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


class ScriptCIMAAnalyzer:
    """Analisa scripts CIMA para extrair parafusos e grades"""
    
    def __init__(self, script_path: str):
        self.script_path = script_path
        self.content = None
        self.encoding = None
        
    def read_script(self) -> bool:
        """Lê o script com detecção de encoding"""
        encodings = ['utf-16', 'utf-8', 'latin-1']
        
        for enc in encodings:
            try:
                with open(self.script_path, 'r', encoding=enc) as f:
                    self.content = f.read()
                    self.encoding = enc
                    return True
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        print(f"[ERRO] Não foi possível ler {self.script_path}")
        return False
    
    def extract_parafusos(self) -> List[Tuple[float, float]]:
        """
        Extrai posições de parafusos do script.
        Procura por comandos INSERT com blocos PAR.CIM e PAR.BAI
        Retorna: Lista de tuplas (x, y) para cada parafuso
        """
        if not self.content:
            return []
        
        parafusos = []
        
        # Padrão para INSERT de parafusos
        # Formato: -INSERT\nPAR.CIM\nx,y\n1\n0\n;
        pattern = r'-INSERT\s+PAR\.(CIM|BAI)\s+([-\d.]+)\s*,\s*([-\d.]+)'
        
        matches = re.finditer(pattern, self.content, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            tipo = match.group(1)
            x = float(match.group(2))
            y = float(match.group(3))
            parafusos.append((x, y, tipo))
        
        return parafusos
    
    def extract_grades_info(self) -> Dict:
        """
        Extrai informações sobre grades do script.
        Procura por blocos de grade (retângulos, hachuras, etc.)
        """
        if not self.content:
            return {}
        
        info = {
            'num_retangulos': 0,
            'posicoes': [],
            'dimensoes': []
        }
        
        # Padrão para PLINE (retângulos de grade)
        # Formato: _PLINE\nx1,y1\nx2,y2\nx3,y3\nx4,y4\nC
        pline_pattern = r'_PLINE\s+([-\d.]+)\s*,\s*([-\d.]+)\s+([-\d.]+)\s*,\s*([-\d.]+)\s+([-\d.]+)\s*,\s*([-\d.]+)\s+([-\d.]+)\s*,\s*([-\d.]+)\s+C'
        
        matches = re.finditer(pline_pattern, self.content, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            x1, y1 = float(match.group(1)), float(match.group(2))
            x2, y2 = float(match.group(3)), float(match.group(4))
            x3, y3 = float(match.group(5)), float(match.group(6))
            x4, y4 = float(match.group(7)), float(match.group(8))
            
            # Calcular dimensões
            largura = abs(x2 - x1)
            altura = abs(y3 - y1)
            
            if largura > 10 and altura > 10:  # Filtrar retângulos pequenos (parafusos, etc)
                info['num_retangulos'] += 1
                info['posicoes'].append((x1, y1))
                info['dimensoes'].append((largura, altura))
        
        return info
    
    def analyze(self) -> Dict:
        """Executa análise completa do script"""
        if not self.read_script():
            return {}
        
        resultado = {
            'arquivo': os.path.basename(self.script_path),
            'encoding': self.encoding,
            'tamanho': len(self.content),
            'parafusos': {
                'total': 0,
                'posicoes': [],
                'tipos': {'CIM': 0, 'BAI': 0}
            },
            'grades': self.extract_grades_info()
        }
        
        parafusos = self.extract_parafusos()
        resultado['parafusos']['total'] = len(parafusos)
        
        for x, y, tipo in parafusos:
            resultado['parafusos']['posicoes'].append({'x': x, 'y': y, 'tipo': tipo})
            resultado['parafusos']['tipos'][tipo] = resultado['parafusos']['tipos'].get(tipo, 0) + 1
        
        return resultado


def comparar_com_modelo(analise_script: Dict, dados_modelo: Dict) -> Dict:
    """
    Compara análise do script com dados esperados do modelo
    
    Args:
        analise_script: Resultado de ScriptCIMAAnalyzer.analyze()
        dados_modelo: Dicionário com dados esperados do PilarModel
    """
    comparacao = {
        'parafusos': {
            'esperado': len([v for v in dados_modelo.get('parafusos', {}).values() if v and float(v) > 0]),
            'encontrado': analise_script['parafusos']['total'],
            'diferenca': 0,
            'status': 'OK'
        },
        'grades': {
            'esperado': {
                'grade_1': dados_modelo.get('grade_1', 0),
                'grade_2': dados_modelo.get('grade_2', 0),
                'grade_3': dados_modelo.get('grade_3', 0),
                'distancia_1': dados_modelo.get('distancia_1', 0),
                'distancia_2': dados_modelo.get('distancia_2', 0),
            },
            'encontrado': analise_script['grades'],
            'status': 'PENDENTE'  # Análise de grades requer mais detalhes
        }
    }
    
    # Calcular diferença de parafusos
    comparacao['parafusos']['diferenca'] = abs(
        comparacao['parafusos']['esperado'] - comparacao['parafusos']['encontrado']
    )
    
    if comparacao['parafusos']['diferenca'] > 0:
        comparacao['parafusos']['status'] = 'DIFERENTE'
    else:
        comparacao['parafusos']['status'] = 'OK'
    
    return comparacao


def analisar_diretorio(diretorio: str, pavimento: str = None) -> List[Dict]:
    """
    Analisa todos os scripts CIMA em um diretório
    
    Args:
        diretorio: Caminho do diretório
        pavimento: Nome do pavimento (opcional, para filtrar)
    """
    resultados = []
    
    # Procurar scripts .scr
    path = Path(diretorio)
    scripts = list(path.glob('**/*.scr'))
    
    # Filtrar por pavimento se fornecido
    if pavimento:
        pav_safe = pavimento.replace(' ', '_')
        scripts = [s for s in scripts if pav_safe.lower() in str(s).lower()]
    
    print(f"\n{'='*70}")
    print(f"ANÁLISE DE SCRIPTS CIMA")
    print(f"{'='*70}")
    print(f"Diretório: {diretorio}")
    print(f"Scripts encontrados: {len(scripts)}")
    
    for script_path in scripts:
        print(f"\n[ANALISANDO] {script_path.name}")
        
        analyzer = ScriptCIMAAnalyzer(str(script_path))
        resultado = analyzer.analyze()
        
        if resultado:
            resultados.append(resultado)
            print(f"  ✅ Parafusos encontrados: {resultado['parafusos']['total']}")
            print(f"  ✅ Retângulos de grade: {resultado['grades']['num_retangulos']}")
        else:
            print(f"  ❌ Erro ao analisar")
    
    return resultados


def gerar_relatorio(resultados: List[Dict], arquivo_saida: str = None):
    """Gera relatório em JSON dos resultados"""
    relatorio = {
        'total_scripts': len(resultados),
        'scripts': resultados,
        'resumo': {
            'total_parafusos': sum(r['parafusos']['total'] for r in resultados),
            'total_retangulos': sum(r['grades']['num_retangulos'] for r in resultados),
        }
    }
    
    if arquivo_saida:
        with open(arquivo_saida, 'w', encoding='utf-8') as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Relatório salvo em: {arquivo_saida}")
    else:
        print("\n" + "="*70)
        print("RELATÓRIO")
        print("="*70)
        print(json.dumps(relatorio, indent=2, ensure_ascii=False))
    
    return relatorio


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analisa scripts CIMA para extrair parafusos e grades')
    parser.add_argument('diretorio', help='Diretório contendo scripts .scr')
    parser.add_argument('--pavimento', help='Nome do pavimento para filtrar')
    parser.add_argument('--saida', help='Arquivo de saída JSON (opcional)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.diretorio):
        print(f"[ERRO] Diretório não encontrado: {args.diretorio}")
        return
    
    resultados = analisar_diretorio(args.diretorio, args.pavimento)
    
    if resultados:
        gerar_relatorio(resultados, args.saida)
    else:
        print("\n[AVISO] Nenhum script foi analisado com sucesso")


if __name__ == '__main__':
    main()
