"""
Revisor interativo de fichas de vigas (Fase 3 → correção humana).

Uso:
    python -m src.pipeline.ficha_vigas_reviewer \
        --fichas DADOS-OBRAS/Obra_X/Fase-3.../fichas_vigas.json \
        --output DADOS-OBRAS/Obra_X/Fase-3.../fichas_vigas_revisadas.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.pipeline.ficha_vigas_schema import (
    FichaFase3Viga,
    carregar_fichas_json,
    salvar_fichas_json,
)

SEPARADOR = "=" * 60


def exibir_ficha(ficha: FichaFase3Viga, indice: int, total: int) -> None:
    print(f"\n{SEPARADOR}")
    print(f"VIGA {indice}/{total}: {ficha.codigo}  (Pavimento: {ficha.pavimento})")
    print(f"Confidence: {ficha.confidence:.0%}  |  Revisado: {ficha.revisado}")
    print(SEPARADOR)
    print(f"  Tipo:      {ficha.tipo}")
    print(f"  Seção:     {ficha.largura} x {ficha.altura} cm")
    print(f"  Comprimento: {ficha.comprimento} cm")
    print(f"  Tramos:    {len(ficha.tramos)}")
    arm_pos = ficha.armadura_positiva or {}
    arm_neg = ficha.armadura_negativa or {}
    estribos = ficha.estribos or {}
    print(f"  Arm. Pos:  {arm_pos.get('qtd_barras', 0)}x{arm_pos.get('diametro', 0)}mm")
    print(f"  Arm. Neg:  {arm_neg.get('qtd_barras', 0)}x{arm_neg.get('diametro', 0)}mm")
    print(f"  Estribos:  {estribos.get('diametro', 0)}mm @{estribos.get('espacamento', 0)}cm")
    if ficha.garfos:
        print(f"  Garfos:    {ficha.garfos}")
    erros = ficha.validate()
    if erros:
        print(f"  ERROS: {'; '.join(erros)}")


def _perguntar(prompt: str, atual: str) -> str:
    resp = input(f"  {prompt} [{atual}]: ").strip()
    if resp == "":
        return atual
    if resp.lower() == "x":
        return ""
    return resp


def _perguntar_float(prompt: str, atual: float) -> float:
    resp = _perguntar(prompt, str(atual))
    try:
        return float(resp)
    except ValueError:
        print(f"    Valor inválido - mantido: {atual}")
        return atual


def revisar_ficha_interativo(ficha: FichaFase3Viga) -> FichaFase3Viga:
    print("\nPressione Enter para confirmar cada campo, ou digite o valor correto.")
    print("Digite 'pular' para aceitar a ficha inteira sem modificar.")
    print("Digite 'skip' para pular para a próxima (mantém pendente).")

    resp = input("\n  [Enter=editar | pular=aceitar | skip=pular]: ").strip().lower()

    if resp == "pular":
        ficha.revisado = True
        return ficha

    if resp == "skip":
        return ficha

    ficha.codigo = _perguntar("Código", ficha.codigo)
    ficha.tipo = _perguntar("Tipo (retangular/L/T)", ficha.tipo)
    ficha.largura = _perguntar_float("Largura (cm)", ficha.largura)
    ficha.altura = _perguntar_float("Altura (cm)", ficha.altura)
    ficha.comprimento = _perguntar_float("Comprimento (cm)", ficha.comprimento)

    print("\n  Armadura positiva:")
    arm_pos = ficha.armadura_positiva or {}
    arm_pos["qtd_barras"] = int(_perguntar("Qtd barras", str(arm_pos.get("qtd_barras", 0))))
    arm_pos["diametro"] = int(_perguntar("Diâmetro (mm)", str(arm_pos.get("diametro", 0))))
    ficha.armadura_positiva = arm_pos

    print("\n  Armadura negativa:")
    arm_neg = ficha.armadura_negativa or {}
    arm_neg["qtd_barras"] = int(_perguntar("Qtd barras", str(arm_neg.get("qtd_barras", 0))))
    arm_neg["diametro"] = int(_perguntar("Diâmetro (mm)", str(arm_neg.get("diametro", 0))))
    ficha.armadura_negativa = arm_neg

    print("\n  Estribos:")
    estribos = ficha.estribos or {}
    estribos["diametro"] = int(_perguntar("Diâmetro (mm)", str(estribos.get("diametro", 0))))
    estribos["espacamento"] = float(_perguntar("Espaçamento (cm)", str(estribos.get("espacamento", 0))))
    ficha.estribos = estribos

    ficha.revisado = True
    return ficha


def salvar_correcoes_para_treino(fichas_originais, fichas_revisadas, caminho_treino: str) -> int:
    pares = []
    for orig, rev in zip(fichas_originais, fichas_revisadas):
        if not rev.revisado:
            continue
        orig_d = orig.to_dict()
        rev_d = rev.to_dict()
        campos_relevantes = ["comprimento", "largura", "altura", "tipo"]
        houve_mudanca = any(str(orig_d.get(c)) != str(rev_d.get(c)) for c in campos_relevantes)
        if houve_mudanca:
            pares.append({"auto_interpretation": orig_d, "human_correction": rev_d})

    if pares:
        os.makedirs(os.path.dirname(caminho_treino) or ".", exist_ok=True)
        with open(caminho_treino, "w", encoding="utf-8") as fp:
            json.dump(pares, fp, ensure_ascii=False, indent=2)
        print(f"\nDataset de treinamento: {len(pares)} pares salvos em {caminho_treino}")
    return len(pares)


def revisar_fichas(caminho_fichas: str, caminho_saida: str, caminho_treino: str = None, apenas_com_baixa_confidence: bool = True) -> dict:
    fichas = carregar_fichas_json(caminho_fichas)
    originais = [FichaFase3Viga.from_dict(f.to_dict()) for f in fichas]

    pendentes = [f for f in fichas if f.precisa_revisao()] if apenas_com_baixa_confidence else fichas
    ja_ok = len(fichas) - len(pendentes)

    print(f"\n{SEPARADOR}")
    print(f"REVISOR DE FICHAS - {os.path.basename(caminho_fichas)}")
    print(f"{SEPARADOR}")
    print(f"Total: {len(fichas)} vigas | Já OK: {ja_ok} | Para revisar: {len(pendentes)}")

    if not pendentes:
        print("Nenhuma ficha precisa de revisão. Tudo OK.")
        salvar_fichas_json(fichas, caminho_saida)
        return {"revisadas": 0, "pares_treino": 0}

    revisadas = 0
    for i, ficha in enumerate(pendentes, 1):
        exibir_ficha(ficha, i, len(pendentes))
        ficha_atualizada = revisar_ficha_interativo(ficha)
        idx = next((j for j, f in enumerate(fichas) if f.codigo == ficha.codigo and f.pavimento == ficha.pavimento), None)
        if idx is not None:
            fichas[idx] = ficha_atualizada
        if ficha_atualizada.revisado:
            revisadas += 1

    salvar_fichas_json(fichas, caminho_saida)
    print(f"\nFichas revisadas salvas em: {caminho_saida}")

    pares_treino = 0
    if caminho_treino:
        pares_treino = salvar_correcoes_para_treino(originais, fichas, caminho_treino)

    return {"revisadas": revisadas, "pares_treino": pares_treino}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Revisor interativo de fichas de vigas.")
    parser.add_argument("--fichas", required=True, help="JSON de fichas da Fase 3")
    parser.add_argument("--output", required=True, help="JSON de saída (fichas revisadas)")
    parser.add_argument("--treino", default=None, help="JSON de pares para treinamento")
    parser.add_argument("--todas", action="store_true", help="Revisar todas as fichas")
    args = parser.parse_args()

    resultado = revisar_fichas(
        caminho_fichas=args.fichas,
        caminho_saida=args.output,
        caminho_treino=args.treino,
        apenas_com_baixa_confidence=not args.todas,
    )
    print(f"\nResumo: {resultado['revisadas']} fichas revisadas, {resultado['pares_treino']} pares de treino gerados.")


if __name__ == "__main__":
    main()
