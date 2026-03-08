
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
Módulo especializado para cálculos automáticos das grades especiais
Implementa todas as regras do Conjunto 1 da aba Dados Gerais
para os pilares especiais A-B e E-F
"""

import math
import traceback

class CalculadoraGradesEspeciais:
    """
    Classe responsável por calcular grades especiais seguindo as regras do Conjunto 1
    """

    def __init__(self):
        """Inicializa a calculadora com as configurações padrão"""
        self.tolerancia_conflito = 3  # cm
        self.tolerancia_soma = 0.1    # cm
        self.max_tentativas = 5       # tentativas de cálculo
        self.max_tentativas_detalhes = 10  # tentativas para detalhes

    def calcular_grades_especiais_com_regras_completas(self, tipo_calculo="ab", dados_entrada=None, forcar_calculo=False):
        """
        Calcula grades especiais usando TODAS as regras do Conjunto 1 da aba Dados Gerais

        Args:
            tipo_calculo: "ab" ou "ef" (grades A-B ou E-F)
            dados_entrada: dicionário com dados necessários

        Returns:
            dict: Resultados do cálculo
        """
        try:
            print(f"[CALCULO-GRADES-ESPECIAL] Iniciando cálculo completo para {tipo_calculo.upper()}")

            # Validação dos dados de entrada
            if not self._validar_dados_entrada(tipo_calculo, dados_entrada):
                return {"sucesso": False, "erro": "Dados de entrada inválidos"}

            # Extrair dados necessários
            comprimento_base = dados_entrada.get("comprimento_base", 0)
            pos_parafusos = dados_entrada.get("pos_parafusos", [])

            print(f"[CALCULO-GRADES-ESPECIAL] Comprimento base: {comprimento_base}cm")
            print(f"[CALCULO-GRADES-ESPECIAL] Parafusos encontrados: {len(pos_parafusos)}")

            # Verificar se há modo específico (NOVA/INI) para aplicar proporções
            modo_calculo = dados_entrada.get("modo_calculo", "NOVA")

            if modo_calculo in ["NOVA", "INI"]:
                # Usar proporções específicas do modo para pilares especiais
                resultado_calculo = self._calcular_grades_com_proporcoes_especiais(
                    comprimento_base, pos_parafusos, modo_calculo, tipo_calculo
                )
            else:
                # Usar EXATAMENTE a mesma lógica do Conjunto 1
                resultado_calculo = self._calcular_grades_com_regras_conjunto1(
                    comprimento_base, pos_parafusos
                )

            if resultado_calculo["num_grades"] > 0:
                print(f"[CALCULO-GRADES-ESPECIAL] Resultado: {resultado_calculo['num_grades']} grades de {resultado_calculo['tamanho_grade']}cm, distância {resultado_calculo['distancia']}cm")

                # Calcular detalhes das grades
                detalhes_grades = self._calcular_detalhes_grades_com_regras_conjunto1(
                    tipo_calculo,
                    resultado_calculo["num_grades"],
                    resultado_calculo["tamanho_grade"],
                    resultado_calculo["distancia"],
                    pos_parafusos
                )

                resultado_completo = {
                    "sucesso": True,
                    "tipo_calculo": tipo_calculo,
                    "num_grades": resultado_calculo["num_grades"],
                    "tamanho_grade": resultado_calculo["tamanho_grade"],
                    "distancia": resultado_calculo["distancia"],
                    "detalhes_grades": detalhes_grades,
                    "pos_parafusos": pos_parafusos
                }

                print(f"[CALCULO-GRADES-ESPECIAL] ✅ Cálculo completo {tipo_calculo.upper()} finalizado")
                return resultado_completo

            else:
                return {"sucesso": False, "erro": "Não foi possível calcular grades válidas"}

        except Exception as e:
            print(f"[CALCULO-GRADES-ESPECIAL] ❌ Erro no cálculo completo {tipo_calculo}: {e}")
            traceback.print_exc()
            return {"sucesso": False, "erro": str(e)}

    def _validar_dados_entrada(self, tipo_calculo, dados_entrada):
        """Valida os dados de entrada necessários"""
        if tipo_calculo not in ["ab", "ef"]:
            print(f"[ERRO] Tipo de cálculo inválido: {tipo_calculo}")
            return False

        if not dados_entrada:
            print("[ERRO] Dados de entrada não fornecidos")
            return False

        comprimento_base = dados_entrada.get("comprimento_base", 0)
        if comprimento_base <= 0:
            print(f"[ERRO] Comprimento base inválido: {comprimento_base}")
            return False

        return True

    def _calcular_grades_com_regras_conjunto1(self, medida_total, pos_parafusos):
        """
        Usa EXATAMENTE a mesma lógica de cálculo de grades do Conjunto 1

        Returns:
            dict: Resultado do cálculo
        """
        print(f"   [CALCULO-GRADES] Calculando grades para {medida_total}cm usando regras do Conjunto 1...")

        # Validação básica
        if not medida_total or float(medida_total) <= 0:
            return {"num_grades": 0, "tamanho_grade": 0, "distancia": 0}

        medida_total = float(medida_total)

        # Ajustar o comprimento adicionando 22cm (regra do Conjunto 1)
        medida_total_ajustada = medida_total + 22

        # LÓGICA: Até 106cm = 1 grade única (pode ter fração)
        if medida_total_ajustada <= 106:
            return {
                "num_grades": 1,
                "tamanho_grade": medida_total_ajustada,
                "distancia": 0
            }

        # LÓGICA: 106cm até 259cm = 2 grades (106 + 15 + 106 = 259)
        elif medida_total_ajustada <= 259:
            return self._calcular_duas_grades(medida_total_ajustada, pos_parafusos)

        # LÓGICA: Acima de 259cm = 3 grades
        else:
            return self._calcular_tres_grades(medida_total_ajustada, pos_parafusos)

    def _calcular_duas_grades(self, medida_total_ajustada, pos_parafusos):
        """Calcula configuração para 2 grades"""
        # Calcular tamanho ideal das grades (máximo 106cm cada)
        tamanho_grade_ideal = min(106, medida_total_ajustada / 2)

        # Tentar encontrar múltiplos de 5 próximos ao tamanho ideal
        tamanho_grade_menor = int(tamanho_grade_ideal / 5) * 5
        tamanho_grade_maior = tamanho_grade_menor + 5

        # Calcular distâncias para cada opção
        distancia_menor = medida_total_ajustada - (2 * tamanho_grade_menor)
        distancia_maior = medida_total_ajustada - (2 * tamanho_grade_maior)

        # Escolher a melhor opção baseada nos critérios
        if tamanho_grade_maior <= 106 and 1 <= distancia_maior <= 15:
            tamanho_grade = tamanho_grade_maior
            distancia = distancia_maior  # Pode ter fração
        elif 1 <= distancia_menor <= 15:
            tamanho_grade = tamanho_grade_menor
            distancia = distancia_menor  # Pode ter fração
        else:
            # Ajustes conforme Conjunto 1
            tamanho_grade, distancia = self._ajustar_configuracao_duas_grades(
                medida_total_ajustada, tamanho_grade_menor, distancia_menor,
                tamanho_grade_maior, distancia_maior
            )

        # Garantir que a soma seja exata (fração fica na distância)
        tamanho_grade, distancia = self._garantir_soma_exata_duas_grades(
            medida_total_ajustada, tamanho_grade, distancia
        )

        # Verificar conflitos e ajustar se necessário
        if pos_parafusos and self._tem_conflitos_grades(tamanho_grade, distancia, pos_parafusos):
            print("   [CONFLITO] Conflitos detectados, buscando alternativas...")
            return self._encontrar_melhor_combinacao_sem_conflitos(
                medida_total_ajustada, tamanho_grade, distancia, 2, pos_parafusos
            )

        return {
            "num_grades": 2,
            "tamanho_grade": tamanho_grade,
            "distancia": distancia
        }

    def _calcular_tres_grades(self, medida_total_ajustada, pos_parafusos):
        """Calcula configuração para 3 grades"""
        # Mesmo processo para 3 grades
        tamanho_grade_ideal = min(106, medida_total_ajustada / 3)

        tamanho_grade_menor = int(tamanho_grade_ideal / 5) * 5
        tamanho_grade_maior = tamanho_grade_menor + 5

        distancia_menor = (medida_total_ajustada - (3 * tamanho_grade_menor)) / 2
        distancia_maior = (medida_total_ajustada - (3 * tamanho_grade_maior)) / 2

        if tamanho_grade_maior <= 106 and 1 <= distancia_maior <= 15:
            tamanho_grade = tamanho_grade_maior
            distancia = distancia_maior  # Pode ter fração
        elif 1 <= distancia_menor <= 15:
            tamanho_grade = tamanho_grade_menor
            distancia = distancia_menor  # Pode ter fração
        else:
            # Ajustes conforme Conjunto 1
            tamanho_grade, distancia = self._ajustar_configuracao_tres_grades(
                medida_total_ajustada, tamanho_grade_menor, distancia_menor,
                tamanho_grade_maior, distancia_maior
            )

        # Garantir soma exata (fração fica na distância)
        tamanho_grade, distancia = self._garantir_soma_exata_tres_grades(
            medida_total_ajustada, tamanho_grade, distancia
        )

        # Verificar conflitos para 3 grades
        if pos_parafusos and self._tem_conflitos_grades(tamanho_grade, distancia, pos_parafusos):
            print("   [CONFLITO] Conflitos detectados, buscando alternativas...")
            return self._encontrar_melhor_combinacao_sem_conflitos(
                medida_total_ajustada, tamanho_grade, distancia, 3, pos_parafusos
            )

        return {
            "num_grades": 3,
            "tamanho_grade": tamanho_grade,
            "distancia": distancia
        }

    def _ajustar_configuracao_duas_grades(self, medida_total_ajustada, tamanho_menor, dist_menor, tamanho_maior, dist_maior):
        """Ajusta configuração para duas grades conforme regras do Conjunto 1"""
        if dist_menor < 1:
            distancia = 1
            tamanho_grade = int((medida_total_ajustada - distancia) / 2)
            tamanho_grade = round(tamanho_grade / 5) * 5
        elif dist_maior > 15:
            distancia = 15
            tamanho_grade = int((medida_total_ajustada - distancia) / 2)
            tamanho_grade = round(tamanho_grade / 5) * 5
        else:
            if abs(dist_menor - 15) < abs(dist_maior - 1):
                tamanho_grade = tamanho_menor
                distancia = dist_menor
            else:
                tamanho_grade = tamanho_maior
                distancia = dist_maior

        return tamanho_grade, distancia

    def _ajustar_configuracao_tres_grades(self, medida_total_ajustada, tamanho_menor, dist_menor, tamanho_maior, dist_maior):
        """Ajusta configuração para três grades conforme regras do Conjunto 1"""
        if dist_menor < 1:
            distancia = 1
            tamanho_grade = int((medida_total_ajustada - (2 * distancia)) / 3)
            tamanho_grade = round(tamanho_grade / 5) * 5
        elif dist_maior > 15:
            distancia = 15
            tamanho_grade = int((medida_total_ajustada - (2 * distancia)) / 3)
            tamanho_grade = round(tamanho_grade / 5) * 5
        else:
            if abs(dist_menor - 15) < abs(dist_maior - 1):
                tamanho_grade = tamanho_menor
                distancia = dist_menor
            else:
                tamanho_grade = tamanho_maior
                distancia = dist_maior

        return tamanho_grade, distancia

    def _garantir_soma_exata_duas_grades(self, medida_total_ajustada, tamanho_grade, distancia):
        """Garante que a soma seja exata para duas grades"""
        soma_atual = (2 * tamanho_grade) + distancia
        if abs(soma_atual - medida_total_ajustada) > self.tolerancia_soma:
            diferenca = medida_total_ajustada - soma_atual
            distancia = distancia + diferenca  # Fração fica na distância
            if distancia < 1:
                distancia = 1
            elif distancia > 15:
                distancia = 15

        return tamanho_grade, distancia

    def _garantir_soma_exata_tres_grades(self, medida_total_ajustada, tamanho_grade, distancia):
        """Garante que a soma seja exata para três grades"""
        soma_atual = (3 * tamanho_grade) + (2 * distancia)
        if abs(soma_atual - medida_total_ajustada) > self.tolerancia_soma:
            diferenca = medida_total_ajustada - soma_atual
            distancia = distancia + (diferenca / 2)  # Fração fica na distância
            if distancia < 1:
                distancia = 1
            elif distancia > 15:
                distancia = 15

        return tamanho_grade, distancia

    def _tem_conflitos_grades(self, tamanho_grade, distancia, pos_parafusos):
        """
        Verifica se uma combinação de tamanho de grade e distância gera conflitos
        """
        if not pos_parafusos:
            return False

        # Simular distribuição de detalhes para as grades
        detalhes_grade = self._simular_detalhes_grade(tamanho_grade)

        # Verificar conflitos na grade 1 (inicia em 0)
        if self._tem_conflitos_distribuicao(detalhes_grade, 0, pos_parafusos):
            return True

        # Verificar conflitos na grade 2 (inicia após grade 1 + distância)
        pos_base_grade2 = tamanho_grade + distancia
        if self._tem_conflitos_distribuicao(detalhes_grade, pos_base_grade2, pos_parafusos):
            return True

        return False

    def _encontrar_melhor_combinacao_sem_conflitos(self, medida_total_ajustada, tamanho_base, distancia_base, num_grades, pos_parafusos):
        """Encontra a melhor combinação sem conflitos"""
        print("   [BUSCA] Procurando combinação sem conflitos...")

        # Testar variações de tamanho
        for variacao in range(-20, 21, 5):
            tamanho_teste = tamanho_base + variacao

            if tamanho_teste < 30 or tamanho_teste > 106:
                continue

            # Calcular distância correspondente
            if num_grades == 2:
                distancia_teste = medida_total_ajustada - (2 * tamanho_teste)
            else:  # 3 grades
                distancia_teste = (medida_total_ajustada - (3 * tamanho_teste)) / 2

            if distancia_teste < 1 or distancia_teste > 15:
                continue

            # Verificar conflitos
            if not self._tem_conflitos_grades(tamanho_teste, distancia_teste, pos_parafusos):
                print(f"   [BUSCA] ✅ Combinação encontrada: {num_grades} grades de {tamanho_teste}cm, distância {distancia_teste}cm")
                return {
                    "num_grades": num_grades,
                    "tamanho_grade": tamanho_teste,
                    "distancia": distancia_teste
                }

        print("   [BUSCA] ❌ Nenhuma combinação sem conflitos encontrada")
        return {
            "num_grades": num_grades,
            "tamanho_grade": tamanho_base,
            "distancia": distancia_base
        }

    def _calcular_detalhes_grades_com_regras_conjunto1(self, tipo_calculo, num_grades, tamanho_grade, distancia, pos_parafusos):
        """
        Calcula detalhes das grades especiais usando as regras do Conjunto 1
        """
        try:
            print(f"[DETALHES] Calculando detalhes para {tipo_calculo.upper()}")

            # Mapear tipo para letras das grades
            mapeamento_grades = {
                "ab": ["a", "b"],
                "ef": ["e", "f"]
            }

            grades = mapeamento_grades.get(tipo_calculo, [])
            detalhes_resultado = {}

            # Calcular detalhes para cada grade
            for i, letra in enumerate(grades):
                if i < num_grades:
                    # Calcular base inicial para esta grade
                    base_inicial = 0
                    if i > 0:
                        base_inicial = tamanho_grade + distancia

                    # Calcular detalhes usando a mesma lógica do Conjunto 1
                    detalhes = self._calcular_distribuicao_equilibrada(tamanho_grade)

                    # Converter para inteiros mantendo soma exata
                    detalhes_inteiros = self._converter_para_inteiros_com_soma_exata(detalhes, int(sum(detalhes)))

                    # Verificar conflitos
                    conflitos = 0
                    if pos_parafusos:
                        conflitos = self._contar_conflitos_distribuicao(detalhes_inteiros, base_inicial, pos_parafusos)

                    detalhes_resultado[letra] = {
                        "detalhes": detalhes_inteiros,
                        "conflitos": conflitos,
                        "base_inicial": base_inicial
                    }

                    print(f"   [DETALHES] Grade {letra.upper()}: {[x for x in detalhes_inteiros if x > 0]} (conflitos: {conflitos})")

            print(f"[DETALHES] ✅ Detalhes calculados para {tipo_calculo.upper()}")
            return detalhes_resultado

        except Exception as e:
            print(f"[DETALHES] ❌ Erro ao calcular detalhes: {e}")
            traceback.print_exc()
            return {}

    def _calcular_distribuicao_equilibrada(self, valor_grade):
        """Calcula distribuição equilibrada para detalhes"""
        quantidade = min(5, max(1, int(math.ceil(valor_grade / 30))))
        valor_base = valor_grade / quantidade

        detalhes = [valor_base] * quantidade

        # Ajustar para soma exata
        soma_atual = sum(detalhes)
        if abs(soma_atual - valor_grade) > 0.01:
            diferenca = valor_grade - soma_atual
            detalhes[0] += diferenca

        return detalhes

    def _converter_para_inteiros_com_soma_exata(self, detalhes, valor_alvo):
        """
        Converte detalhes para inteiros mantendo soma exata
        """
        # Arredondar para baixo inicialmente
        detalhes_inteiros = [int(detalhe) for detalhe in detalhes]

        # Calcular diferença
        soma_atual = sum(detalhes_inteiros)
        diferenca = valor_alvo - soma_atual

        # Distribuir diferença priorizando detalhes que perderam mais no arredondamento
        if diferenca > 0:
            # Calcular perdas no arredondamento
            perdas = [(i, detalhes[i] - int(detalhes[i])) for i in range(len(detalhes)) if detalhes[i] > 0]

            # Ordenar por perda decrescente
            perdas.sort(key=lambda x: x[1], reverse=True)

            # Distribuir diferença
            for i, _ in perdas[:diferenca]:
                if i < len(detalhes_inteiros):
                    detalhes_inteiros[i] += 1

        return detalhes_inteiros

    def _simular_detalhes_grade(self, tamanho_grade):
        """Simula a distribuição de detalhes para uma grade"""
        quantidade = min(5, max(1, int(math.ceil(tamanho_grade / 30))))
        detalhes = self._calcular_distribuicao_equilibrada(tamanho_grade)
        return detalhes[:quantidade]

    def _tem_conflitos_distribuicao(self, detalhes, base_inicial, pos_parafusos):
        """Verifica se uma distribuição de detalhes tem conflitos"""
        pos_acumulada = base_inicial

        for detalhe in detalhes:
            if detalhe > 0:
                pos_acumulada += detalhe
                for pos_parafuso in pos_parafusos:
                    if abs(pos_acumulada - pos_parafuso) <= self.tolerancia_conflito:
                        return True

        return False

    def _contar_conflitos_distribuicao(self, detalhes, base_inicial, pos_parafusos):
        """Conta conflitos entre detalhes e parafusos"""
        conflitos = 0
        pos_acumulada = base_inicial

        for detalhe in detalhes:
            if detalhe > 0:
                pos_acumulada += detalhe
                for pos_parafuso in pos_parafusos:
                    if abs(pos_acumulada - pos_parafuso) <= self.tolerancia_conflito:
                        conflitos += 1

        return conflitos

    def obter_parafusos_especiais(self, interface, prefixo_parafusos):
        """
        Obtém as posições dos parafusos especiais da interface
        """
        pos_parafusos = []

        try:
            for i in range(1, 10):  # par_ab_1 até par_ab_9
                campo_nome = f"{prefixo_parafusos}{i}"
                if hasattr(interface, campo_nome):
                    campo = getattr(interface, campo_nome)
                    valor = campo.get().strip()
                    if valor and valor != "0":
                        try:
                            posicao = float(valor)
                            if posicao > 0:
                                pos_parafusos.append(posicao)
                        except ValueError:
                            continue
        except Exception as e:
            print(f"[ERRO] Erro ao obter parafusos especiais: {e}")

        return pos_parafusos

    def _ajustar_proporcoes_modo_sem_conflitos(self, medida_total_ajustada, tamanho_base, proporcoes, modo_calculo, num_grades, pos_parafusos):
        """
        Tenta ajustar as proporções do modo para resolver conflitos mantendo o mais próximo possível
        das proporções originais NOVA/INI
        """
        try:
            print(f"   [AJUSTE-MODO] Tentando manter proporções do modo {modo_calculo}")

            # Tentar variações pequenas do tamanho mantendo as proporções do modo
            for ajuste in [-2, -1, 1, 2, -5, 5, -10, 10]:  # Ajustes progressivos
                tamanho_teste = tamanho_base + ajuste

                # Manter dentro dos limites
                if tamanho_teste < 30 or tamanho_teste > 106:
                    continue

                # Calcular distância correspondente
                if num_grades == 2:
                    distancia_teste = medida_total_ajustada - (2 * tamanho_teste)
                else:  # 3 grades
                    distancia_teste = (medida_total_ajustada - (3 * tamanho_teste)) / 2

                # Verificar se está dentro dos limites
                if distancia_teste < 1 or distancia_teste > 15:
                    continue

                # Verificar se resolve conflitos
                if not self._tem_conflitos_grades(tamanho_teste, distancia_teste, pos_parafusos):
                    print(f"   [AJUSTE-MODO] ✅ Ajuste encontrado: {tamanho_teste}cm (diferença: {ajuste}cm)")

                    return {
                        "num_grades": num_grades,
                        "tamanho_grade": tamanho_teste,
                        "distancia": distancia_teste
                    }

            print("   [AJUSTE-MODO] ❌ Não foi possível ajustar mantendo proporções do modo")
            return None

        except Exception as e:
            print(f"   [ERRO] Erro no ajuste de proporções: {e}")
            return None

    def _conflitos_sao_aceitaveis(self, tamanho_grade, distancia, pos_parafusos):
        """
        Avalia se os conflitos são toleráveis o suficiente para manter as proporções do modo
        """
        try:
            # Tolerância aumentada para modos específicos (mais permissiva)
            tolerancia_modo = 4  # cm (vs 3cm normal)

            # Simular posições das grades
            detalhes_grade = self._simular_detalhes_grade(tamanho_grade)

            # Verificar conflitos na primeira grade
            pos_acumulada = 0
            for detalhe in detalhes_grade:
                if detalhe > 0:
                    pos_acumulada += detalhe
                    for pos_parafuso in pos_parafusos:
                        distancia_conflito = abs(pos_acumulada - pos_parafuso)
                        if distancia_conflito <= tolerancia_modo:
                            # Conflito encontrado - verificar se é crítico
                            if distancia_conflito < 2:  # Conflito muito próximo
                                return False

            # Verificar conflitos na segunda grade
            if distancia > 0:
                pos_base_segunda = tamanho_grade + distancia
                pos_acumulada = pos_base_segunda
                for detalhe in detalhes_grade:
                    if detalhe > 0:
                        pos_acumulada += detalhe
                        for pos_parafuso in pos_parafusos:
                            distancia_conflito = abs(pos_acumulada - pos_parafuso)
                            if distancia_conflito <= tolerancia_modo:
                                if distancia_conflito < 2:  # Conflito muito próximo
                                    return False

            # Se chegou aqui, conflitos são aceitáveis
            return True

        except Exception as e:
            print(f"   [ERRO] Erro ao avaliar conflitos: {e}")
            return False

    def _calcular_grades_com_proporcoes_especiais(self, comprimento_base, pos_parafusos, modo_calculo, tipo_calculo="ab"):
        """
        ⚠️ DEPRECADO: Calcula grades especiais usando proporções específicas baseadas no modo NOVA/INI.
        
        Esta função usa fórmulas antigas baseadas em proporções e NÃO DEVE ser usada para
        grades A, B, E, F. As novas fórmulas definidas pelo usuário são:
        - Grade A: comp_1 + 22
        - Grade B: comp_1 - 13.2 + (larg_2 - 20)
        - Grade E: comp_2 + 11 + (larg_1 - 20)
        - Grade F (INI): comp_2 - 27.4
        - Grade F (NOVA): comp_1 - 27.4
        
        Esta função é mantida apenas como fallback para outras grades (ex: G-H) ou compatibilidade.
        """
        try:
            print(f"   [CALCULO-ESPECIAL] Usando proporções do modo {modo_calculo} para pilares especiais")

            # Definir proporções baseadas no modo (baseadas em pilar de 100cm)
            if modo_calculo == "NOVA":
                # Modo NOVA (PLINE)
                proporcoes = {
                    'A': 122.4,  # Grade A (para comprimento 1)
                    'B': 89.0,   # Grade B (para comprimento 1)
                    'E': 111.0,  # Grade E (para comprimento 2)
                    'F': 72.6    # Grade F (para comprimento 2)
                }
                print(f"   [PROPORCOES] Modo NOVA: A={proporcoes['A']}, B={proporcoes['B']}, E={proporcoes['E']}, F={proporcoes['F']}")
            else:  # INI
                # Modo INI (MLINE)
                proporcoes = {
                    'A': 120.0,  # Grade A (para comprimento 1)
                    'B': 89.0,   # Grade B (para comprimento 1)
                    'E': 111.0,  # Grade E (para comprimento 2)
                    'F': 72.6    # Grade F (para comprimento 2)
                }
                print(f"   [PROPORCOES] Modo INI: A={proporcoes['A']}, B={proporcoes['B']}, E={proporcoes['E']}, F={proporcoes['F']}")

            # Determinar qual grade específica está sendo calculada baseada no tipo_calculo
            if tipo_calculo == "ab":
                # Para AB, usar proporções de A e B
                grade_principal = 'A'  # Grade A é a principal para AB
                grade_secundaria = 'B'
            elif tipo_calculo == "ef":
                # Para EF, usar proporções de E e F
                grade_principal = 'E'  # Grade E é a principal para EF
                grade_secundaria = 'F'
            else:
                # Fallback para AB
                grade_principal = 'A'
                grade_secundaria = 'B'

            # Calcular diferenças baseadas no comprimento fornecido
            diferenca_comp = comprimento_base - 100.0

            # Aplicar proporções ajustadas usando a grade específica
            tamanho_base = proporcoes[grade_principal] + diferenca_comp

            print(f"   [CALCULO] Comprimento base: {comprimento_base}cm, Diferença: {diferenca_comp}cm")
            print(f"   [CALCULO] Tamanho calculado: {tamanho_base}cm")
            print(f"   [CALCULO] Grade específica: {grade_principal} (proporção base: {proporcoes[grade_principal]}cm)")
            print(f"   [CALCULO] Grade secundária: {grade_secundaria} (proporção base: {proporcoes[grade_secundaria]}cm)")

            # Usar a lógica do Conjunto 1 MAS PRESERVANDO as proporções específicas dos modos
            medida_total_ajustada = comprimento_base + 22

            print(f"   [CALCULO] Medida total ajustada: {medida_total_ajustada}cm")
            print(f"   [CALCULO] Tamanho base das proporções: {tamanho_base}cm")

            # Determinar número de grades baseado no tamanho total
            if medida_total_ajustada <= 106:
                num_grades = 1
                distancia = 0
                # Para 1 grade, usar as proporções calculadas (não o tamanho total)
                tamanho_final = tamanho_base
                print(f"   [GRADE-UNICA] Usando proporções do modo: {tamanho_final}cm")
            elif medida_total_ajustada <= 259:
                num_grades = 2
                # TENTAR preservar as proporções do modo, ajustando se necessário
                tamanho_proposto = tamanho_base

                # Verificar se cabe no espaço disponível
                espaco_necessario = tamanho_proposto * 2
                if espaco_necessario <= medida_total_ajustada:
                    # Cabe! Usar proporções do modo diretamente
                    tamanho_final = tamanho_proposto
                    distancia = medida_total_ajustada - (2 * tamanho_final)
                    print(f"   [MODO-PRESERVADO] Usando proporções do modo: {tamanho_final}cm x2")
                else:
                    # Não cabe completamente, mas tentar manter o máximo possível das proporções
                    espaco_disponivel_por_grade = medida_total_ajustada / 2

                    if espaco_disponivel_por_grade >= tamanho_proposto * 0.5:  # Pelo menos 50% da proporção (mais permissivo)
                        # Reduzir proporcionalmente para caber, mas preservar diferenças entre modos
                        reducao_necessaria = (espaco_necessario - medida_total_ajustada) / espaco_necessario
                        # Usar redução mais agressiva para garantir que caiba
                        tamanho_final = tamanho_proposto * (1 - reducao_necessaria * 0.8)

                        # Ajustar para múltiplo de 5, mas preservar diferenças entre modos
                        tamanho_arredondado = round(tamanho_final / 5) * 5

                        # Preservar diferença entre modos ajustando ligeiramente se necessário
                        if modo_calculo == "NOVA" and tamanho_arredondado < tamanho_final:
                            tamanho_final = tamanho_arredondado + 0.1  # Manter ligeiramente maior para NOVA
                        elif modo_calculo == "INI" and tamanho_arredondado > tamanho_final:
                            tamanho_final = tamanho_arredondado - 0.1  # Manter ligeiramente menor para INI
                        else:
                            tamanho_final = tamanho_arredondado

                        distancia = medida_total_ajustada - (2 * tamanho_final)
                        print(f"   [MODO-AJUSTADO] Proporções ajustadas para caber: {tamanho_final}cm x2")
                    else:
                        # Muito pequeno, usar lógica do Conjunto 1
                        tamanho_ideal = min(106, medida_total_ajustada / 2)
                        tamanho_menor = int(tamanho_ideal / 5) * 5
                        tamanho_maior = tamanho_menor + 5

                        if tamanho_maior <= 106:
                            tamanho_final = tamanho_maior
                        else:
                            tamanho_final = tamanho_menor

                        distancia = medida_total_ajustada - (2 * tamanho_final)
                        print(f"   [CONJUNTO1] Espaço insuficiente, usando lógica padrão: {tamanho_final}cm x2")

                # Ajustes finais de limite APENAS se necessário
                # Só aplicar ajustes se os valores estiverem fora dos limites aceitáveis
                if distancia < 1 or distancia > 15:
                    print(f"   [AJUSTE-FINAL] Distância fora dos limites ({distancia}cm), ajustando...")
                    if distancia < 1:
                        distancia = 1
                    elif distancia > 15:
                        distancia = 15

                    # Recalcular tamanho apenas se a distância foi ajustada
                    if num_grades == 2:
                        tamanho_final = (medida_total_ajustada - distancia) / 2
                    else:  # 3 grades
                        tamanho_final = (medida_total_ajustada - (2 * distancia)) / 3

                    # Aplicar arredondamento para múltiplo de 5, preservando diferenças entre modos
                    tamanho_base_arredondado = round(tamanho_final / 5) * 5

                    # Para modos NOVA/INI, tentar manter uma diferença mínima mesmo em espaço limitado
                    if modo_calculo == "NOVA" and tamanho_base_arredondado < tamanho_final:
                        # NOVA tende a ser ligeiramente maior
                        tamanho_final = tamanho_base_arredondado + 0.1
                    elif modo_calculo == "INI" and tamanho_base_arredondado > tamanho_final:
                        # INI tende a ser ligeiramente menor
                        tamanho_final = tamanho_base_arredondado - 0.1
                    else:
                        tamanho_final = tamanho_base_arredondado

                    print(f"   [AJUSTE-FINAL] Novo tamanho: {tamanho_final}cm")
                else:
                    print(f"   [AJUSTE-FINAL] Valores dentro dos limites, mantendo: {tamanho_final}cm, dist={distancia}cm")
            else:
                num_grades = 3
                # Mesmo processo para 3 grades - preservar proporções do modo
                tamanho_proposto = tamanho_base

                espaco_necessario = tamanho_proposto * 3
                if espaco_necessario <= medida_total_ajustada:
                    # Cabe! Usar proporções do modo diretamente
                    tamanho_final = tamanho_proposto
                    distancia = (medida_total_ajustada - (3 * tamanho_final)) / 2
                    print(f"   [MODO-PRESERVADO] Usando proporções do modo: {tamanho_final}cm x3")
                else:
                    # Não cabe completamente, mas tentar manter o máximo possível das proporções
                    espaco_disponivel_por_grade = medida_total_ajustada / 3

                    if espaco_disponivel_por_grade >= tamanho_proposto * 0.5:  # Pelo menos 50% da proporção (mais permissivo)
                        # Reduzir proporcionalmente para caber, mas preservar diferenças entre modos
                        reducao_necessaria = (espaco_necessario - medida_total_ajustada) / espaco_necessario
                        # Usar redução mais agressiva para garantir que caiba
                        tamanho_final = tamanho_proposto * (1 - reducao_necessaria * 0.8)

                        # Ajustar para múltiplo de 5, mas preservar diferenças entre modos
                        tamanho_arredondado = round(tamanho_final / 5) * 5

                        # Preservar diferença entre modos ajustando ligeiramente se necessário
                        if modo_calculo == "NOVA" and tamanho_arredondado < tamanho_final:
                            tamanho_final = tamanho_arredondado + 0.1  # Manter ligeiramente maior para NOVA
                        elif modo_calculo == "INI" and tamanho_arredondado > tamanho_final:
                            tamanho_final = tamanho_arredondado - 0.1  # Manter ligeiramente menor para INI
                        else:
                            tamanho_final = tamanho_arredondado

                        distancia = (medida_total_ajustada - (3 * tamanho_final)) / 2
                        print(f"   [MODO-AJUSTADO] Proporções ajustadas para caber: {tamanho_final}cm x3")
                    else:
                        # Muito pequeno, usar lógica do Conjunto 1
                        tamanho_ideal = min(106, medida_total_ajustada / 3)
                        tamanho_menor = int(tamanho_ideal / 5) * 5
                        tamanho_maior = tamanho_menor + 5

                        if tamanho_maior <= 106:
                            tamanho_final = tamanho_maior
                        else:
                            tamanho_final = tamanho_menor

                        distancia = (medida_total_ajustada - (3 * tamanho_final)) / 2
                        print(f"   [CONJUNTO1] Espaço insuficiente, usando lógica padrão: {tamanho_final}cm x3")

                # Ajustes finais de limite APENAS se necessário
                # Só aplicar ajustes se os valores estiverem fora dos limites aceitáveis
                if distancia < 1 or distancia > 15:
                    print(f"   [AJUSTE-FINAL] Distância fora dos limites ({distancia}cm), ajustando...")
                    if distancia < 1:
                        distancia = 1
                    elif distancia > 15:
                        distancia = 15

                    # Recalcular tamanho apenas se a distância foi ajustada
                    tamanho_final = (medida_total_ajustada - (2 * distancia)) / 3

                    # Aplicar arredondamento para múltiplo de 5, preservando diferenças entre modos
                    tamanho_base_arredondado = round(tamanho_final / 5) * 5

                    # Para modos NOVA/INI, tentar manter uma diferença mínima mesmo em espaço limitado
                    if modo_calculo == "NOVA" and tamanho_base_arredondado < tamanho_final:
                        # NOVA tende a ser ligeiramente maior
                        tamanho_final = tamanho_base_arredondado + 0.1
                    elif modo_calculo == "INI" and tamanho_base_arredondado > tamanho_final:
                        # INI tende a ser ligeiramente menor
                        tamanho_final = tamanho_base_arredondado - 0.1
                    else:
                        tamanho_final = tamanho_base_arredondado

                    print(f"   [AJUSTE-FINAL] Novo tamanho: {tamanho_final}cm")
                else:
                    print(f"   [AJUSTE-FINAL] Valores dentro dos limites, mantendo: {tamanho_final}cm, dist={distancia}cm")

            # Verificar conflitos se houver parafusos
            if pos_parafusos and self._tem_conflitos_grades(tamanho_final, distancia, pos_parafusos):
                print("   [CONFLITO] Conflitos detectados com proporções do modo")

                # Para modos NOVA/INI, tentar ser mais tolerante e manter proporções
                # Só usar fallback como último recurso
                if modo_calculo in ["NOVA", "INI"]:
                    print("   [PRIORIDADE] Mantendo proporções do modo (tolerância maior)")

                    # Verificar se os conflitos são aceitáveis (distância mínima dos parafusos)
                    conflitos_aceitaveis = self._conflitos_sao_aceitaveis(tamanho_final, distancia, pos_parafusos)
                    print(f"   [PRIORIDADE] Conflitos aceitáveis: {conflitos_aceitaveis}")

                    if conflitos_aceitaveis:
                        print("   [PRIORIDADE] ✅ Conflitos aceitáveis - mantendo proporções do modo")
                        # Continuar com as proporções do modo mesmo com conflitos menores
                        # Pular para o final da função
                        print(f"   [RESULTADO-MODO] {num_grades} grades de {tamanho_final}cm, distância {distancia}cm")
                        return {
                            "num_grades": num_grades,
                            "tamanho_grade": tamanho_final,
                            "distancia": distancia
                        }
                    else:
                        print("   [PRIORIDADE] ❌ Conflitos não aceitáveis - tentando ajustes")
                        # Só então tentar ajustes
                        resultado_ajustado = self._ajustar_proporcoes_modo_sem_conflitos(
                            medida_total_ajustada, tamanho_base, proporcoes, modo_calculo, num_grades, pos_parafusos
                        )

                        if resultado_ajustado:
                            print("   [AJUSTE] Proporções do modo mantidas com ajuste fino")
                            return resultado_ajustado

                # Último recurso: fallback completo
                print("   [FALLBACK] Usando combinação alternativa...")
                return self._encontrar_melhor_combinacao_sem_conflitos(
                    medida_total_ajustada, tamanho_final, distancia, num_grades, pos_parafusos
                )

            print(f"   [RESULTADO] {num_grades} grades de {tamanho_final}cm, distância {distancia}cm")

            return {
                "num_grades": num_grades,
                "tamanho_grade": tamanho_final,
                "distancia": distancia
            }

        except Exception as e:
            print(f"   [ERRO] Erro no cálculo com proporções especiais: {e}")
            # Fallback para cálculo padrão
            return self._calcular_grades_com_regras_conjunto1(comprimento_base, pos_parafusos)
