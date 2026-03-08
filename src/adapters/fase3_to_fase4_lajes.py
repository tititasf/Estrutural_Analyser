"""
Adapter: Fase 3 (interpretação) → Fase 4 (formato do robô de Lajes).

Uso:
    python -m src.adapters.fase3_to_fase4_lajes \
        --fichas DADOS-OBRAS/Obra_X/Fase-3.../fichas_lajes.json \
        --obra "Nome da Obra" \
        --output DADOS-OBRAS/Obra_X/Fase-4.../Dados_Robo_Lajes/
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.pipeline.ficha_lajes_schema import (
    FichaFase3Laje,
    fichas_to_lajes_salvas,
    fichas_to_lajes_outline,
    fichas_to_pavimentos_lista,
    carregar_fichas_json,
)


def carregar_fichas_auto(caminho_json: str, nome_obra: str):
    """Carrega fichas do JSON de Fase 3."""
    with open(caminho_json, "r", encoding="utf-8") as fp:
        dados = json.load(fp)

    fichas = []
    if isinstance(dados, list):
        for item in dados:
            item.setdefault("obra_nome", nome_obra)
            item.setdefault("confidence", 0.0)
            item.setdefault("revisado", False)
            fichas.append(FichaFase3Laje.from_dict(item))
    elif isinstance(dados, dict):
        for laje_id, info in dados.items():
            ficha_dict = _converter_formato_legado(laje_id, info, nome_obra)
            fichas.append(FichaFase3Laje.from_dict(ficha_dict))
    return fichas


def _converter_formato_legado(laje_id: str, info: dict, nome_obra: str) -> dict:
    """Converte formato legado para FichaFase3Laje."""
    dimensoes = info.get("dimensoes", {})
    armadura = info.get("armadura", {})
    pavimento = info.get("pavimento", "P-1")
    
    return {
        "codigo": laje_id,
        "pavimento": pavimento,
        "obra_nome": nome_obra,
        "tipo": info.get("tipo", "macica"),
        "dimensoes": {
            "comprimento": float(dimensoes.get("comprimento", 300)),
            "largura": float(dimensoes.get("largura", 200)),
            "espessura": float(dimensoes.get("espessura", info.get("espessura", 10))),
        },
        "espessura": float(info.get("espessura", dimensoes.get("espessura", 10))),
        "outline_segs": info.get("outline_segs", []),
        "nivel": float(info.get("nivel", 0)),
        "armadura": armadura,
        "confidence": float(info.get("confidence", 0.0)),
        "revisado": bool(info.get("revisado", False)),
    }


def adaptar_fase3_para_fase4(caminho_fichas: str, nome_obra: str, pasta_saida: str) -> dict:
    """
    Converte fichas da Fase 3 para arquivos de entrada do robô (Fase 4).

    Cria na pasta_saida:
    - lajes_salvas.json
    - lajes_outline.json
    - pavimentos_lista.json
    - relatorio_validacao.json

    Returns:
        dict com estatísticas (total, validas, com_erros, precisam_revisao)
    """
    os.makedirs(pasta_saida, exist_ok=True)
    fichas = carregar_fichas_auto(caminho_fichas, nome_obra)

    validas = []
    com_erros = []
    precisam_revisao = []

    for ficha in fichas:
        erros = ficha.validate()
        if erros:
            com_erros.append({"ficha": ficha.to_dict(), "erros": erros})
        else:
            validas.append(ficha)
            if ficha.precisa_revisao():
                precisam_revisao.append(ficha.codigo)

    lajes_salvas = fichas_to_lajes_salvas(validas)
    _salvar_json(lajes_salvas, os.path.join(pasta_saida, "lajes_salvas.json"))

    lajes_outline = fichas_to_lajes_outline(validas)
    _salvar_json(lajes_outline, os.path.join(pasta_saida, "lajes_outline.json"))

    pavimentos = fichas_to_pavimentos_lista(validas)
    _salvar_json(pavimentos, os.path.join(pasta_saida, "pavimentos_lista.json"))

    relatorio = {
        "total": len(fichas),
        "validas": len(validas),
        "com_erros": len(com_erros),
        "precisam_revisao": precisam_revisao,
        "erros_detalhes": com_erros,
    }
    _salvar_json(relatorio, os.path.join(pasta_saida, "relatorio_validacao.json"))

    return relatorio


def _salvar_json(dados: object, caminho: str) -> None:
    with open(caminho, "w", encoding="utf-8") as fp:
        json.dump(dados, fp, ensure_ascii=False, indent=2)
    print(f"  Salvo: {caminho}")


def main():
    parser = argparse.ArgumentParser(
        description="Adapta fichas Fase 3 para o formato do robô de Lajes (Fase 4)."
    )
    parser.add_argument("--fichas", required=True, help="Caminho do JSON com fichas (Fase 3)")
    parser.add_argument("--obra", required=True, help="Nome da obra")
    parser.add_argument("--output", required=True, help="Pasta de saída para arquivos Fase 4")
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
    print(f"Total de lajes: {relatorio['total']}")
    print(f"Válidas: {relatorio['validas']}")
    print(f"Com erros: {relatorio['com_erros']}")
    if relatorio["precisam_revisao"]:
        print(f"Precisam revisão humana: {', '.join(relatorio['precisam_revisao'])}")
    else:
        print("Nenhuma ficha precisa de revisão adicional.")

    if relatorio["com_erros"] > 0:
        print("\nATENÇÃO: Corrija as fichas com erros antes de executar o robô.")
        print(f"Detalhes em: {args.output}/relatorio_validacao.json")
        sys.exit(1)

    print("\nOK - arquivos prontos para o robô de Lajes.")


if __name__ == "__main__":
    main()
