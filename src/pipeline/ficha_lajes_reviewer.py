"""
Revisor interativo de fichas de lajes (Fase 3 → correção humana).

Uso:
    python -m src.pipeline.ficha_lajes_reviewer \
        --fichas DADOS-OBRAS/Obra_X/Fase-3.../fichas_lajes.json \
        --output DADOS-OBRAS/Obra_X/Fase-3.../fichas_lajes_revisadas.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.pipeline.ficha_lajes_schema import (
    FichaFase3Laje,
    carregar_fichas_json,
    salvar_fichas_json,
)

SEPARADOR = "=" * 60


def exibir_ficha(ficha: FichaFase3Laje, indice: int, total: int) -> None:
    print(f"\n{SEPARADOR}")
    print(f"LAJE {indice}/{total}: {ficha.codigo}  (Pavimento: {ficha.pavimento})")
    print(f"Confidence: {ficha.confidence:.0%}  |  Revisado: {ficha.revisado}")
    print(SEPARADOR)
    print(f"  Tipo:      {ficha.tipo}")
    print(f"  Espessura: {ficha.espessura} cm")
    dim = ficha.dimensoes or {}
    print(f"  Dimensões: {dim.get('comprimento', 0)} x {dim.get('largura', 0)} cm")
    print(f"  Nível:     {ficha.nivel} m")
    print(f"  Área:      {ficha.area():.2f} m²")
    armadura = ficha.armadura or {}
    print(f"  Armadura:  {armadura.get('tipo', 'CA-50')} ø{armadura.get('diametro', 0)}@{armadura.get('espacamento', 0)}")
    print(f"  Contorno:  {len(ficha.outline_segs)} vértices")
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


def revisar_ficha_interativo(ficha: FichaFase3Laje) -> FichaFase3Laje:
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
    ficha.tipo = _perguntar("Tipo (macica/pre_moldada/steel_deck)", ficha.tipo)
    ficha.espessura = _perguntar_float("Espessura (cm)", ficha.espessura)
    ficha.nivel = _perguntar_float("Nível (m)", ficha.nivel)

    print("\n  Dimensões:")
    dim = ficha.dimensoes or {}
    dim["comprimento"] = float(_perguntar("Comprimento (cm)", str(dim.get("comprimento", 0))))
    dim["largura"] = float(_perguntar("Largura (cm)", str(dim.get("largura", 0))))
    ficha.dimensoes = dim

    print("\n  Armadura:")
    armadura = ficha.armadura or {}
    armadura["tipo"] = _perguntar("Tipo (CA-50/CA-60)", armadura.get("tipo", "CA-50"))
    armadura["diametro"] = int(_perguntar("Diâmetro (mm)", str(armadura.get("diametro", 0))))
    armadura["espacamento"] = float(_perguntar("Espaçamento (cm)", str(armadura.get("espacamento", 0))))
    armadura["direcao"] = _perguntar("Direção", armadura.get("direcao", "bidirecional"))
    ficha.armadura = armadura

    ficha.revisado = True
    return ficha


def salvar_correcoes_para_treino(fichas_originais, fichas_revisadas, caminho_treino: str) -> int:
    pares = []
    for orig, rev in zip(fichas_originais, fichas_revisadas):
        if not rev.revisado:
            continue
        orig_d = orig.to_dict()
        rev_d = rev.to_dict()
        campos_relevantes = ["espessura", "tipo", "nivel"]
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
    originais = [FichaFase3Laje.from_dict(f.to_dict()) for f in fichas]

    pendentes = [f for f in fichas if f.precisa_revisao()] if apenas_com_baixa_confidence else fichas
    ja_ok = len(fichas) - len(pendentes)

    print(f"\n{SEPARADOR}")
    print(f"REVISOR DE FICHAS - {os.path.basename(caminho_fichas)}")
    print(f"{SEPARADOR}")
    print(f"Total: {len(fichas)} lajes | Já OK: {ja_ok} | Para revisar: {len(pendentes)}")

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
    parser = argparse.ArgumentParser(description="Revisor interativo de fichas de lajes.")
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
