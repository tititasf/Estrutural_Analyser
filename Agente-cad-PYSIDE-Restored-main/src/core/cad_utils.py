import os
import logging

# Mapeamento de versões do AutoCAD (Magic Numbers / $ACADVER)
ACAD_VERSIONS = {
    "AC1032": "AutoCAD 2018/2024",
    "AC1027": "AutoCAD 2013/2017",
    "AC1024": "AutoCAD 2010/2012",
    "AC1021": "AutoCAD 2007/2009",
    "AC1018": "AutoCAD 2004/2006",
    "AC1015": "AutoCAD 2000/2002",
    "AC1014": "AutoCAD R14",
    "AC1012": "AutoCAD R13",
    "AC1009": "AutoCAD R11/R12",
    "AC1006": "AutoCAD R10",
    "AC1004": "AutoCAD R9",
    "AC1003": "AutoCAD R2.6",
    "AC1002": "AutoCAD R2.5",
}

def get_cad_version_info(file_path):
    """
    Identifica a versão de um arquivo DWG ou DXF.
    Retorna uma string legível ou "Desconhecido".
    """
    if not os.path.exists(file_path):
        return "N/A"

    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == ".dwg":
            return _get_dwg_version(file_path)
        elif ext == ".dxf":
            return _get_dxf_version(file_path)
    except Exception as e:
        logging.error(f"Erro ao ler versão CAD de {file_path}: {e}")
    
    return "Desconhecido"

def _get_dwg_version(file_path):
    """Lê os primeiros 6 bytes de um DWG para obter a versão (ex: AC1032)."""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(6).decode('ascii')
            return ACAD_VERSIONS.get(header, "Desconhecido")
    except Exception:
        return "Desconhecido"

def _get_dxf_version(file_path):
    """Busca a variável $ACADVER no header de um DXF."""
    try:
        with open(file_path, 'r', errors='ignore') as f:
            found_acadver = False
            for i, line in enumerate(f):
                if i > 1000: break # Limite de segurança
                line = line.strip()
                
                if line == "$ACADVER":
                    found_acadver = True
                    continue
                
                if found_acadver:
                    # No DXF, o valor segue a linha de código (geralmente '1')
                    if line == '1':
                        continue
                    # O próximo valor é a versão (ex: AC1027)
                    return ACAD_VERSIONS.get(line, "Desconhecido")
    except Exception:
        pass
    return "Desconhecido"

if __name__ == "__main__":
    # Teste rápido se executado diretamente
    import sys
    if len(sys.argv) > 1:
        print(f"Versão de {sys.argv[1]}: {get_cad_version_info(sys.argv[1])}")
