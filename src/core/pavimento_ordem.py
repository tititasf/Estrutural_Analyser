# -*- coding: utf-8 -*-
"""
Módulo de Ordenação de Pavimentos - ATAQUE 9

Gerencia a ordem vertical de pavimentos em uma obra para permitir
cross-pavimento linking (ex: laje_inf requer pavimento abaixo).

Uso:
  from src.core.pavimento_ordem import get_pavimento_abaixo, get_pavimento_acima
  pav_inf = get_pavimento_abaixo("TIPO_1", "Obra_TREINO_1", db)
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# Ordem padrão de pavimentos (baixo -> alto)
ORDEM_PADRAO = (
    "FUNDACAO", "SAPATA", "RADIER",
    "SUBSOLO_3", "SUBSOLO-3", "SUBSOLO 3",
    "SUBSOLO_2", "SUBSOLO-2", "SUBSOLO 2",
    "SUBSOLO_1", "SUBSOLO-1", "SUBSOLO 1",
    "SUBSOLO",
    "TERREO", "TÉRREO", "TERREO_1", "PAV_TERREO",
    "TIPO_1", "TIPO-1", "TIPO 1", "PAV_1", "PAVIMENTO_1", "PAVIMENTO_01", "1º PAVIMENTO",
    "TIPO_2", "TIPO-2", "TIPO 2", "PAV_2", "PAVIMENTO_2", "PAVIMENTO_02", "2º PAVIMENTO",
    "TIPO_3", "TIPO-3", "TIPO 3", "PAV_3", "PAVIMENTO_3", "PAVIMENTO_03", "3º PAVIMENTO",
    "TIPO_4", "TIPO-4", "TIPO 4", "PAV_4", "PAVIMENTO_4", "PAVIMENTO_04", "4º PAVIMENTO",
    "TIPO_5", "TIPO-5", "TIPO 5", "PAV_5", "PAVIMENTO_5", "PAVIMENTO_05", "5º PAVIMENTO",
    "TIPO_6", "TIPO-6", "TIPO 6", "PAV_6", "PAVIMENTO_6", "PAVIMENTO_06", "6º PAVIMENTO",
    "TIPO_7", "TIPO-7", "TIPO 7", "PAV_7", "PAVIMENTO_7", "PAVIMENTO_07", "7º PAVIMENTO",
    "TIPO_8", "TIPO-8", "TIPO 8", "PAV_8", "PAVIMENTO_8", "PAVIMENTO_08", "8º PAVIMENTO",
    "INFERIOR", "DINF",
    "DUPLEX", "DSUP",
    "MEZANINO", "MEZANINO_1", "MEZANINO 1",
    "ATICO", "ÁTICO", "ATICO_1",
    "COBERTURA", "COB", "TELHADO",
    "BARRILETE", "TAMPA",
    "CASA_MAQUINAS", "CASA DE MÁQUINAS",
    "RESERVATORIO", "R01", "R02",
    "CAIXA_DAGUA", "CAIXA D'ÁGUA",
    "ESCADA",
    "GERL", "GERAL",
    "DESCONHECIDO", "GENERICO", "OUTRO",
)


def normalizar_pavimento(nome: str) -> str:
    """
    Normaliza nome do pavimento para facilitar matching.

    Ex: "1º Pavimento" -> "1º PAVIMENTO"
        "tipo-2" -> "TIPO-2"
    """
    if not nome:
        return ""
    return nome.strip().upper()


def get_ordem_index(pavimento: str) -> int:
    """
    Retorna índice do pavimento na ORDEM_PADRAO.

    Retorna 999 se não encontrado (assume topo).
    """
    norm = normalizar_pavimento(pavimento)

    # Busca direta na ORDEM_PADRAO
    try:
        return ORDEM_PADRAO.index(norm)
    except ValueError:
        pass

    # Busca por padrão TIPO_N
    for i, pav_padrao in enumerate(ORDEM_PADRAO):
        if pav_padrao == norm:
            return i

    # Tenta extrair número de "TIPO_N" / "TIPO-N" / "TIPO N"
    match = re.search(r"TIPO[_\s-]?(\d+)", norm)
    if match:
        num = int(match.group(1))
        # Encontra o índice base de TIPO_1
        try:
            base_idx = ORDEM_PADRAO.index("TIPO_1")
            # Cada TIPO tem ~7 variantes na ORDEM_PADRAO
            return base_idx + (num - 1) * 7
        except ValueError:
            pass

    logger.warning(f"Pavimento '{pavimento}' não reconhecido, assumindo topo (índice 999)")
    return 999


def ordenar_pavimentos(pavimentos: List[str]) -> List[str]:
    """
    Ordena lista de pavimentos de baixo -> alto.

    Args:
        pavimentos: Lista de nomes de pavimentos

    Returns:
        Lista ordenada (baixo -> alto)

    Exemplo:
        >>> ordenar_pavimentos(["TIPO_2", "TERREO", "COBERTURA", "TIPO_1"])
        ["TERREO", "TIPO_1", "TIPO_2", "COBERTURA"]
    """
    return sorted(pavimentos, key=get_ordem_index)


def get_pavimento_abaixo(
    pavimento_atual: str,
    obra_name: str,
    db=None,
) -> Optional[str]:
    """
    Retorna o pavimento imediatamente abaixo do atual.

    Args:
        pavimento_atual: Nome do pavimento atual (ex: "TIPO_1")
        obra_name: Nome da obra
        db: Instância de DatabaseManager

    Returns:
        Nome do pavimento abaixo ou None se já é o primeiro

    Exemplo:
        >>> get_pavimento_abaixo("TIPO_1", "Obra_TREINO_1", db)
        "TERREO"
    """
    # Tenta obter lista de pavimentos do banco
    pavs = []
    if db:
        try:
            pavs = db.list_pavimentos_by_obra(obra_name)
        except AttributeError:
            logger.warning(
                "Método list_pavimentos_by_obra não encontrado, usando get_projects"
            )
            try:
                projects = db.get_projects()
                for p in projects:
                    if p.get("pavement_name"):
                        pavs.append(p["pavement_name"])
            except Exception:
                pass

    if not pavs:
        logger.warning(f"Nenhum pavimento encontrado para obra '{obra_name}'")
        return None

    # Remove duplicados e ordena
    pavs_unique = list(set(pavs))
    pavs_sorted = ordenar_pavimentos(pavs_unique)

    logger.debug(f"Pavimentos ordenados de '{obra_name}': {pavs_sorted}")

    # Encontra posição do pavimento atual
    norm_atual = normalizar_pavimento(pavimento_atual)
    pavs_sorted_norm = [normalizar_pavimento(p) for p in pavs_sorted]

    try:
        idx = pavs_sorted_norm.index(norm_atual)
    except ValueError:
        logger.warning(f"Pavimento '{pavimento_atual}' não encontrado em {pavs_sorted}")
        return None

    if idx == 0:
        logger.info(f"Pavimento '{pavimento_atual}' já é o primeiro, sem pavimento abaixo")
        return None

    pav_abaixo = pavs_sorted[idx - 1]
    logger.info(f"Pavimento abaixo de '{pavimento_atual}': '{pav_abaixo}'")
    return pav_abaixo


def get_pavimento_acima(
    pavimento_atual: str,
    obra_name: str,
    db=None,
) -> Optional[str]:
    """
    Retorna o pavimento imediatamente acima do atual.

    Args:
        pavimento_atual: Nome do pavimento atual
        obra_name: Nome da obra
        db: Instância de DatabaseManager

    Returns:
        Nome do pavimento acima ou None se já é o último
    """
    pavs = []
    if db:
        try:
            pavs = db.list_pavimentos_by_obra(obra_name)
        except AttributeError:
            try:
                projects = db.get_projects()
                for p in projects:
                    if p.get("pavement_name"):
                        pavs.append(p["pavement_name"])
            except Exception:
                pass

    if not pavs:
        return None

    pavs_unique = list(set(pavs))
    pavs_sorted = ordenar_pavimentos(pavs_unique)

    norm_atual = normalizar_pavimento(pavimento_atual)
    pavs_sorted_norm = [normalizar_pavimento(p) for p in pavs_sorted]

    try:
        idx = pavs_sorted_norm.index(norm_atual)
    except ValueError:
        return None

    if idx >= len(pavs_sorted) - 1:
        return None

    pav_acima = pavs_sorted[idx + 1]
    logger.info(f"Pavimento acima de '{pavimento_atual}': '{pav_acima}'")
    return pav_acima


if __name__ == "__main__":
    print("=== Testes de Ordenação ===")
    test_pavs = ("TIPO_2", "TERREO", "COBERTURA", "TIPO_1", "SUBSOLO")
    result = ordenar_pavimentos(list(test_pavs))
    print(f"Input:  {test_pavs}")
    print(f"Output: {result}")
    assert result == ["SUBSOLO", "TERREO", "TIPO_1", "TIPO_2", "COBERTURA"], "Erro na ordenação"

    print("\n=== Teste de Normalizacao ===")
    print(f"'1 Pavimento' -> '{normalizar_pavimento('1 Pavimento')}'")
    print(f"'tipo-2' -> '{normalizar_pavimento('tipo-2')}'")

    print("\n=== Teste de Indices ===")
    for pav in ("TERREO", "TIPO_1", "COBERTURA", "DESCONHECIDO"):
        idx = get_ordem_index(pav)
        print(f"{pav:20s} -> indice {idx}")

    print("\n[OK] Todos os testes passaram!")
