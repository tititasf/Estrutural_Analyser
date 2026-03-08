"""
Adapter: Fase 3 (interpretação) → Fase 4 (formato do robô PilarAnalyzer).

Uso:
    python -m src.adapters.fase3_to_fase4_pilares \
        --fichas DADOS-OBRAS/Obra_X/Fase-3.../fichas_pilares.json \
        --obra "Nome da Obra" \
        --output DADOS-OBRAS/Obra_X/Fase-4.../Dados_Robo_Pilares/
"""

import argparse
import json
import os
import sys

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.pipeline.ficha_pilares_schema import (
    FichaFase3Pilar,
    fichas_to_obras_salvas,
    fichas_to_pilares_salvos,
    carregar_fichas_json,
)


# --------------------------------------------------------------------------
# Leitura de fichas em diferentes formatos de entrada
# --------------------------------------------------------------------------

def carregar_fichas_auto(caminho_json: str, nome_obra: str) -> list[FichaFase3Pilar]:
    """
    Carrega fichas do JSON de Fase 3. Suporta dois formatos:
    1. Lista de FichaFase3Pilar (formato nativo deste pipeline)
    2. Dict legado do pillar_analyzer (formato src_raw_backup)
    """
    with open(caminho_json, "r", encoding="utf-8") as fp:
        dados = json.load(fp)

    fichas = []

    if isinstance(dados, list):
        # Formato nativo: lista de dicts com campos de FichaFase3Pilar
        for item in dados:
            # Compatibilidade com campos extras do pillar_analyzer
            item = _normalizar_campos(item, nome_obra)
            fichas.append(FichaFase3Pilar(**item))

    elif isinstance(dados, dict):
        # Formato legado: { "P1": { "secao": {...}, ... } }
        for pilar_id, info in dados.items():
            ficha_dict = _converter_formato_legado(pilar_id, info, nome_obra)
            fichas.append(FichaFase3Pilar(**ficha_dict))

    return fichas


def _normalizar_campos(item: dict, nome_obra: str) -> dict:
    """Normaliza campos do dict para o dataclass FichaFase3Pilar."""
    # Garantir campos obrigatórios com defaults
    item.setdefault("obra", nome_obra)
    item.setdefault("pavimento_anterior", "")
    item.setdefault("pavimento_numero", 0)
    item.setdefault("confidence", 0.0)
    item.setdefault("revisado_por_humano", False)

    # Remover campos desconhecidos
    campos_validos = {
        "id", "numero", "pavimento", "pavimento_numero", "obra",
        "comprimento", "largura", "altura_cm", "nivel_saida_m", "nivel_chegada_m",
        "pavimento_anterior",
        "par_1_2", "par_2_3", "par_3_4", "par_4_5",
        "par_5_6", "par_6_7", "par_7_8", "par_8_9",
        "grade_1", "distancia_1", "grade_2", "distancia_2", "grade_3",
        "pilar_especial", "tipo_pilar_especial",
        "confidence", "revisado_por_humano",
    }
    return {k: v for k, v in item.items() if k in campos_validos}


def _converter_formato_legado(
    pilar_id: str,
    info: dict,
    nome_obra: str,
) -> dict:
    """
    Converte formato de saída legado do pillar_analyzer para FichaFase3Pilar.

    Formato legado esperado:
    {
      "secao": {"largura": 20, "altura": 50},
      "localizacao": {"x": 100.0, "y": 200.0},
      "pavimento": "TERREO",
      "armacao": {"barras": 8, "diametro": 16, "estribo": 8},
      "confidence": 0.72
    }
    """
    secao = info.get("secao", {})
    armacao = info.get("armacao", {})
    pavimento = info.get("pavimento", "TERREO")

    # Extrair número do id ("P17" → "17")
    numero = "".join(filter(str.isdigit, pilar_id)) or "0"

    # Barras = armação longitudinal — distribuir nos trechos disponíveis
    n_barras = str(armacao.get("barras", 0))
    estribo_diam = str(armacao.get("estribo", ""))

    return {
        "id": pilar_id,
        "numero": numero,
        "pavimento": pavimento,
        "pavimento_numero": _pavimento_para_numero(pavimento),
        "obra": nome_obra,
        "comprimento": float(secao.get("largura", 0)),
        "largura": float(secao.get("altura", 0)),
        "altura_cm": float(info.get("altura_cm", 300)),
        "nivel_saida_m": float(info.get("nivel_saida_m", 0)),
        "nivel_chegada_m": float(info.get("nivel_chegada_m", 3)),
        "pavimento_anterior": info.get("pavimento_anterior", ""),
        # Distribuir barras uniformemente nos trechos ativos
        "par_1_2": n_barras,
        "par_2_3": n_barras,
        "par_3_4": n_barras,
        "par_4_5": n_barras,
        "par_5_6": "0",
        "par_6_7": "0",
        "par_7_8": "0",
        "par_8_9": "0",
        "grade_1": estribo_diam,
        "distancia_1": str(armacao.get("espacamento", "")),
        "grade_2": "",
        "distancia_2": "",
        "grade_3": "",
        "pilar_especial": info.get("pilar_especial", False),
        "tipo_pilar_especial": info.get("tipo_pilar_especial", "L"),
        "confidence": float(info.get("confidence", 0.0)),
        "revisado_por_humano": bool(info.get("revisado_por_humano", False)),
    }


def _pavimento_para_numero(nome_pav: str) -> int:
    """Converte nome de pavimento para índice numérico."""
    _MAP = {
        "FUNDACAO": -3, "FUNDAÇÃO": -3,
        "2_SUBSOLO": -2, "SUBSOLO2": -2,
        "1_SUBSOLO": -1, "SUBSOLO": -1,
        "TERREO": 0, "TÉRREO": 0, "TERREO": 0,
        "1_PAVIMENTO": 1, "1PAV": 1,
        "2_PAVIMENTO": 2, "2PAV": 2,
        "3_PAVIMENTO": 3, "3PAV": 3,
        "4_PAVIMENTO": 4, "4PAV": 4,
        "TIPO": 5, "COBERTURA": 6, "ATICO": 7, "ÁTICO": 7,
    }
    chave = nome_pav.upper().replace("-", "_").strip()
    return _MAP.get(chave, 0)


# --------------------------------------------------------------------------
# Função principal de adaptação
# --------------------------------------------------------------------------

def adaptar_fase3_para_fase4(
    caminho_fichas: str,
    nome_obra: str,
    pasta_saida: str,
) -> dict:
    """
    Converte fichas da Fase 3 para arquivos de entrada do robô (Fase 4).

    Cria na pasta_saida:
    - obras_salvas.json — entrada para PilarAnalyzer (formato completo)
    - pilares_salvos.json — estado do pavimento atual
    - pavimentos_lista.json — lista de pavimentos com níveis
    - relatorio_validacao.json — fichas com erros de validação

    Returns:
        dict com estatísticas (total, validas, com_erros, precisam_revisao)
    """
    os.makedirs(pasta_saida, exist_ok=True)

    fichas = carregar_fichas_auto(caminho_fichas, nome_obra)

    validas = []
    com_erros = []
    precisam_revisao = []

    for ficha in fichas:
        erros = ficha.validar()
        if erros:
            com_erros.append({"ficha": ficha.to_dict(), "erros": erros})
        else:
            validas.append(ficha)
            if ficha.precisa_revisao():
                precisam_revisao.append(ficha.id)

    # Gerar obras_salvas.json
    obras_salvas = fichas_to_obras_salvas(validas, nome_obra)
    _salvar_json(obras_salvas, os.path.join(pasta_saida, "obras_salvas.json"))

    # Gerar pilares_salvos.json (último pavimento ou todos juntos)
    pilares_salvos = fichas_to_pilares_salvos(validas)
    _salvar_json(pilares_salvos, os.path.join(pasta_saida, "pilares_salvos.json"))

    # Gerar pavimentos_lista.json — extraído das fichas
    pavimentos = _extrair_pavimentos(validas)
    _salvar_json(pavimentos, os.path.join(pasta_saida, "pavimentos_lista.json"))

    # Gerar relatório de validação
    relatorio = {
        "total": len(fichas),
        "validas": len(validas),
        "com_erros": len(com_erros),
        "precisam_revisao": precisam_revisao,
        "erros_detalhes": com_erros,
    }
    _salvar_json(relatorio, os.path.join(pasta_saida, "relatorio_validacao.json"))

    return relatorio


def _extrair_pavimentos(fichas: list[FichaFase3Pilar]) -> list:
    """Extrai lista de pavimentos únicos com seus níveis."""
    vistos: dict[str, float] = {}
    for ficha in fichas:
        if ficha.pavimento not in vistos:
            vistos[ficha.pavimento] = ficha.nivel_saida_m * 100  # m → cm
    return [[nome, str(nivel)] for nome, nivel in sorted(vistos.items(), key=lambda x: x[1])]


def _salvar_json(dados: object, caminho: str) -> None:
    with open(caminho, "w", encoding="utf-8") as fp:
        json.dump(dados, fp, ensure_ascii=False, indent=2)
    print(f"  Salvo: {caminho}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Adapta fichas Fase 3 para o formato do robô PilarAnalyzer (Fase 4)."
    )
    parser.add_argument(
        "--fichas",
        required=True,
        help="Caminho do JSON com fichas interpretadas (Fase 3)",
    )
    parser.add_argument(
        "--obra",
        required=True,
        help='Nome da obra (ex: "Obra Testes")',
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Pasta de saída para arquivos Fase 4",
    )
    args = parser.parse_args()

    print(f"\nAdaptando fichas: {args.fichas}")
    print(f"Obra: {args.obra}")
    print(f"Saída: {args.output}\n")

    relatorio = adaptar_fase3_para_fase4(
        caminho_fichas=args.fichas,
        nome_obra=args.obra,
        pasta_saida=args.output,
    )

    print("\n--- Relatório ---")
    print(f"Total de pilares: {relatorio['total']}")
    print(f"Válidos: {relatorio['validas']}")
    print(f"Com erros: {relatorio['com_erros']}")
    if relatorio["precisam_revisao"]:
        print(f"Precisam revisão humana: {', '.join(relatorio['precisam_revisao'])}")
    else:
        print("Nenhuma ficha precisa de revisão adicional.")

    if relatorio["com_erros"] > 0:
        print("\nATENÇAO: Corrija as fichas com erros antes de executar o robô.")
        print(f"Detalhes em: {args.output}/relatorio_validacao.json")
        sys.exit(1)

    print("\nOK — arquivos prontos para o PilarAnalyzer.")


if __name__ == "__main__":
    main()
