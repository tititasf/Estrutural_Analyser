"""
Revisor interativo de fichas de pilares (Fase 3 → correção humana).

Uso:
    python -m src.pipeline.ficha_pilares_reviewer \
        --fichas DADOS-OBRAS/Obra_X/Fase-3.../fichas_pilares.json \
        --output DADOS-OBRAS/Obra_X/Fase-3.../fichas_pilares_revisadas.json

O revisor apresenta cada pilar que precisa de revisão, mostra o que
foi interpretado automaticamente e pede confirmação/correção de cada campo.
As correções são salvas para uso em treinamento futuro.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.pipeline.ficha_pilares_schema import (
    FichaFase3Pilar,
    carregar_fichas_json,
    salvar_fichas_json,
)


# --------------------------------------------------------------------------
# Formatação e exibição
# --------------------------------------------------------------------------

SEPARADOR = "=" * 60


def exibir_ficha(ficha: FichaFase3Pilar, indice: int, total: int) -> None:
    print(f"\n{SEPARADOR}")
    print(f"PILAR {indice}/{total}: {ficha.id}  (Pavimento: {ficha.pavimento})")
    print(f"Confidence: {ficha.confidence:.0%}  |  Revisado: {ficha.revisado_por_humano}")
    print(SEPARADOR)
    print(f"  Seção:     {ficha.comprimento} x {ficha.largura} cm")
    print(f"  Altura:    {ficha.altura_cm} cm")
    print(f"  Níveis:    saída={ficha.nivel_saida_m}m / chegada={ficha.nivel_chegada_m}m")
    print(f"  Armadura (barras/trecho):")
    print(f"    1-2:{ficha.par_1_2}  2-3:{ficha.par_2_3}  3-4:{ficha.par_3_4}  4-5:{ficha.par_4_5}")
    print(f"    5-6:{ficha.par_5_6}  6-7:{ficha.par_6_7}  7-8:{ficha.par_7_8}  8-9:{ficha.par_8_9}")
    print(f"  Grades:    ø{ficha.grade_1}@{ficha.distancia_1}cm")
    if ficha.grade_2:
        print(f"             ø{ficha.grade_2}@{ficha.distancia_2}cm")
    if ficha.pilar_especial:
        print(f"  ESPECIAL:  tipo {ficha.tipo_pilar_especial}")
    erros = ficha.validar()
    if erros:
        print(f"  ERROS: {'; '.join(erros)}")


def _perguntar(prompt: str, atual: str) -> str:
    """Exibe prompt com valor atual. Enter = manter. 'x' = limpar."""
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
        print(f"    Valor inválido — mantido: {atual}")
        return atual


# --------------------------------------------------------------------------
# Loop de revisão interativa
# --------------------------------------------------------------------------

def revisar_ficha_interativo(ficha: FichaFase3Pilar) -> FichaFase3Pilar:
    """
    Apresenta a ficha e permite correção campo a campo.
    Retorna ficha atualizada (com revisado_por_humano=True).
    """
    print("\nPressione Enter para confirmar cada campo, ou digite o valor correto.")
    print("Digite 'pular' para aceitar a ficha inteira sem modificar.")
    print("Digite 'skip' para pular para a próxima (mantém pendente).")

    resp = input("\n  [Enter=editar campo a campo | pular=aceitar tudo | skip=pular]: ").strip().lower()

    if resp == "pular":
        ficha.revisado_por_humano = True
        return ficha

    if resp == "skip":
        return ficha  # não marca como revisado

    # Edição campo a campo
    ficha.id = _perguntar("Código (id)", ficha.id)
    ficha.comprimento = _perguntar_float("Comprimento (cm, lado maior)", ficha.comprimento)
    ficha.largura = _perguntar_float("Largura (cm, lado menor)", ficha.largura)
    ficha.altura_cm = _perguntar_float("Altura total (cm)", ficha.altura_cm)
    ficha.nivel_saida_m = _perguntar_float("Nível saída (m)", ficha.nivel_saida_m)
    ficha.nivel_chegada_m = _perguntar_float("Nível chegada (m)", ficha.nivel_chegada_m)

    print("\n  Armadura longitudinal (barras por trecho):")
    ficha.par_1_2 = _perguntar("Par 1-2", ficha.par_1_2)
    ficha.par_2_3 = _perguntar("Par 2-3", ficha.par_2_3)
    ficha.par_3_4 = _perguntar("Par 3-4", ficha.par_3_4)
    ficha.par_4_5 = _perguntar("Par 4-5", ficha.par_4_5)
    ficha.par_5_6 = _perguntar("Par 5-6", ficha.par_5_6)
    ficha.par_6_7 = _perguntar("Par 6-7", ficha.par_6_7)
    ficha.par_7_8 = _perguntar("Par 7-8", ficha.par_7_8)
    ficha.par_8_9 = _perguntar("Par 8-9", ficha.par_8_9)

    print("\n  Grades (estribos):")
    ficha.grade_1 = _perguntar("Diâmetro grade 1 (mm)", ficha.grade_1)
    ficha.distancia_1 = _perguntar("Espaçamento grade 1 (cm)", ficha.distancia_1)
    ficha.grade_2 = _perguntar("Diâmetro grade 2 (vazio=sem)", ficha.grade_2)
    if ficha.grade_2:
        ficha.distancia_2 = _perguntar("Espaçamento grade 2 (cm)", ficha.distancia_2)
    ficha.grade_3 = _perguntar("Diâmetro grade 3 (vazio=sem)", ficha.grade_3)

    ficha.revisado_por_humano = True
    return ficha


def salvar_correcoes_para_treino(
    fichas_originais: list[FichaFase3Pilar],
    fichas_revisadas: list[FichaFase3Pilar],
    caminho_treino: str,
) -> int:
    """
    Salva pares (original, corrigido) para dataset de treinamento.
    Retorna quantidade de pares com diferença real.
    """
    pares = []
    for orig, rev in zip(fichas_originais, fichas_revisadas):
        if not rev.revisado_por_humano:
            continue
        orig_d = orig.to_dict()
        rev_d = rev.to_dict()
        # Detectar se houve alteração real
        campos_relevantes = [
            "comprimento", "largura", "altura_cm",
            "par_1_2", "par_2_3", "par_3_4", "par_4_5",
            "grade_1", "distancia_1",
        ]
        houve_mudanca = any(
            str(orig_d.get(c)) != str(rev_d.get(c))
            for c in campos_relevantes
        )
        if houve_mudanca:
            pares.append({
                "auto_interpretation": orig_d,
                "human_correction": rev_d,
            })

    if pares:
        os.makedirs(os.path.dirname(caminho_treino) or ".", exist_ok=True)
        with open(caminho_treino, "w", encoding="utf-8") as fp:
            json.dump(pares, fp, ensure_ascii=False, indent=2)
        print(f"\nDataset de treinamento: {len(pares)} pares salvos em {caminho_treino}")

    return len(pares)


# --------------------------------------------------------------------------
# Fluxo principal
# --------------------------------------------------------------------------

def revisar_fichas(
    caminho_fichas: str,
    caminho_saida: str,
    caminho_treino: str | None = None,
    apenas_com_baixa_confidence: bool = True,
) -> dict:
    """
    Fluxo completo de revisão humana.

    Returns:
        dict com estatísticas da revisão
    """
    fichas = carregar_fichas_json(caminho_fichas)
    originais = [FichaFase3Pilar(**f.to_dict()) for f in fichas]  # cópia deep

    pendentes = [f for f in fichas if f.precisa_revisao()] if apenas_com_baixa_confidence else fichas
    ja_ok = len(fichas) - len(pendentes)

    print(f"\n{SEPARADOR}")
    print(f"REVISOR DE FICHAS — {os.path.basename(caminho_fichas)}")
    print(f"{SEPARADOR}")
    print(f"Total: {len(fichas)} pilares | Já revisados/OK: {ja_ok} | Para revisar: {len(pendentes)}")

    if not pendentes:
        print("Nenhuma ficha precisa de revisão. Tudo OK.")
        salvar_fichas_json(fichas, caminho_saida)
        return {"revisadas": 0, "pares_treino": 0}

    revisadas = 0
    for i, ficha in enumerate(pendentes, 1):
        exibir_ficha(ficha, i, len(pendentes))
        ficha_atualizada = revisar_ficha_interativo(ficha)
        # Atualizar na lista original
        idx = next(j for j, f in enumerate(fichas) if f.id == ficha.id and f.pavimento == ficha.pavimento)
        fichas[idx] = ficha_atualizada
        if ficha_atualizada.revisado_por_humano:
            revisadas += 1

    salvar_fichas_json(fichas, caminho_saida)
    print(f"\nFichas revisadas salvas em: {caminho_saida}")

    pares_treino = 0
    if caminho_treino:
        pares_treino = salvar_correcoes_para_treino(originais, fichas, caminho_treino)

    return {"revisadas": revisadas, "pares_treino": pares_treino}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Revisor interativo de fichas de pilares.")
    parser.add_argument("--fichas", required=True, help="JSON de fichas da Fase 3")
    parser.add_argument("--output", required=True, help="JSON de saída (fichas revisadas)")
    parser.add_argument("--treino", default=None, help="JSON de pares para treinamento")
    parser.add_argument(
        "--todas",
        action="store_true",
        help="Revisar todas as fichas (não só as com baixa confidence)",
    )
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
