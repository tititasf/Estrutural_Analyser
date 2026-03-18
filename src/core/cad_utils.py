# -*- coding: utf-8 -*-
"""
CAD Utilities - Detecta versão de arquivos DWG/DXF.

Identifica a versão do AutoCAD que gerou o arquivo baseado no header.
Suporta DWG (header binário) e DXF (variável $ACADVER).
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)

# Mapeamento de código de versão para nome do AutoCAD
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


def get_cad_version_info(file_path: str) -> dict:
    """
    Retorna informações da versão de um arquivo CAD (DWG ou DXF).

    Args:
        file_path: Caminho para o arquivo .dwg ou .dxf

    Returns:
        Dict com 'version_code', 'version_name', 'file_type', 'error' (se houver)
    """
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".dwg":
            return _get_dwg_version(file_path)
        elif ext == ".dxf":
            return _get_dxf_version(file_path)
        else:
            return {
                "version_code": None,
                "version_name": None,
                "file_type": ext,
                "error": f"Tipo de arquivo não suportado: {ext}",
            }
    except Exception as e:
        return {
            "version_code": None,
            "version_name": None,
            "file_type": None,
            "error": str(e),
        }


def _get_dwg_version(file_path: str) -> dict:
    """Lê a versão de um arquivo DWG a partir do header binário (primeiros 6 bytes)."""
    with open(file_path, "rb") as f:
        header = f.read(6).decode("ascii", errors="replace")

    version_name = ACAD_VERSIONS.get(header, f"Desconhecida ({header})")
    return {
        "version_code": header,
        "version_name": version_name,
        "file_type": "DWG",
    }


def _get_dxf_version(file_path: str) -> dict:
    """Lê a versão de um arquivo DXF buscando a variável $ACADVER."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        found_acadver = False
        for i, line in enumerate(f):
            line = line.strip()
            if line == "$ACADVER":
                found_acadver = True
                continue
            if found_acadver and line.startswith("AC"):
                version_name = ACAD_VERSIONS.get(line, f"Desconhecida ({line})")
                return {
                    "version_code": line,
                    "version_name": version_name,
                    "file_type": "DXF",
                }
            # Limita busca às primeiras 200 linhas do HEADER
            if i > 200:
                break

    return {
        "version_code": None,
        "version_name": None,
        "file_type": "DXF",
        "error": "$ACADVER não encontrada no arquivo DXF",
    }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        info = get_cad_version_info(sys.argv[1])
        print(f"Versão de {sys.argv[1]}: {info}")
