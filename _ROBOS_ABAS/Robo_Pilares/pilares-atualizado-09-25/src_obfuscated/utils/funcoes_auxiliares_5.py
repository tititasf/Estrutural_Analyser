
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

import tkinter as tk
from tkinter import messagebox
import math

class GradeParafusosMixin:
    """
    Mixin responsável por gerenciar os cálculos e atualizações de grades e parafusos.
    Contém toda a lógica de cálculo, verificação de conflitos e atualização da interface.
    """
    
    def calcular_parafusos(self, comprimento):
        """
        Calcula a distribuição dos parafusos baseado no comprimento do pilar.
        Retorna uma lista com os valores dos parafusos.
        Os maiores valores ficam nas extremidades e os menores no centro.
        Se houver apenas dois parafusos, permite valor fracionário.
        """
        if not comprimento or float(comprimento) <= 0:
            return [0] * 6  # Retorna lista de zeros se comprimento inválido
        comprimento = float(comprimento)
        comprimento_ajustado = comprimento + 24  # Ajustado para +24cm para parafusos
        quantidade = int(math.ceil(comprimento_ajustado / 72))
        if quantidade == 0:
            return [0] * 6
        if quantidade == 2:
            valor = round(comprimento_ajustado / 2, 1)
            parafusos = [valor, valor]
        else:
            valor_base = int(math.floor(comprimento_ajustado / quantidade))
            resto = int(round(comprimento_ajustado - (valor_base * quantidade)))
            parafusos = [valor_base] * quantidade
            # Distribuir o resto nas extremidades, alternando para dentro
            left = 0
            right = quantidade - 1
            for i in range(resto):
                if i % 2 == 0:
                    parafusos[left] += 1
                    left += 1
                else:
                    parafusos[right] += 1
                    right -= 1
        while len(parafusos) < 6:
            parafusos.append(0)
        return parafusos

    def atualizar_parafusos(self, event=None):
        """
        Atualiza os campos dos parafusos baseado no comprimento atual
        """
        comprimento = self.comprimento.get().strip()
        if not comprimento:
            return
        try:
            parafusos = self.calcular_parafusos(comprimento)
            campos = [
                "par_1_2", "par_2_3", "par_3_4", "par_4_5", "par_5_6", "par_6_7", "par_7_8", "par_8_9"
            ]
            for i, campo_nome in enumerate(campos):
                campo = getattr(self, campo_nome, None)
                if campo:
                    valor = str(parafusos[i]) if i < len(parafusos) else "0"
                    campo.delete(0, tk.END)
                    campo.insert(0, valor)
        except Exception as e:
            print(f"Erro ao calcular parafusos: {e}")

    def calcular_grades(self, medida_total):
        """
        Calcula os valores das grades e distâncias baseado na medida total.
        Retorna uma tupla com (num_grades, tamanho_grade, distancia_maxima).
        
        NOVAS REGRAS:
        1. Até 106cm: 1 grade única (exceção: 105-106cm podem usar tamanho exato)
        2. 106cm até 259cm: dividir em 2 grades (106 + 15 + 106 = 259)
        3. Acima de 259cm: dividir em 3 grades
        4. Grades: preferencialmente múltiplos de 5
        5. Tamanho máximo de grade: 106cm
        6. Distância máxima: 15cm (preferencialmente máxima possível)
        7. Soma exata: grades + distâncias = comprimento + 22
        """
        if not medida_total or float(medida_total) <= 0:
            return 0, 0, 0
            
        medida_total = float(medida_total)
        
        # Ajustar o comprimento adicionando 22cm
        medida_total_ajustada = medida_total + 22
        
        # LÓGICA: Até 106cm = 1 grade única
        if medida_total_ajustada <= 106:
            # Para grades únicas, usar o tamanho exato para garantir soma correta
            return 1, medida_total_ajustada, 0
        
        # LÓGICA: 106cm até 259cm = 2 grades (106 + 15 + 106 = 259)
        elif medida_total_ajustada <= 259:
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
                # Usar a grade maior se estiver dentro dos limites
                tamanho_grade = tamanho_grade_maior
                distancia = distancia_maior
            elif 1 <= distancia_menor <= 15:
                # Usar a grade menor se estiver dentro dos limites
                tamanho_grade = tamanho_grade_menor
                distancia = distancia_menor
            else:
                # Se nenhuma opção estiver dentro dos limites, ajustar
                if distancia_menor < 1:
                    # Reduzir o tamanho das grades para aumentar a distância
                    distancia = 1
                    tamanho_grade = int((medida_total_ajustada - distancia) / 2)
                    # Aproximar para múltiplo de 5
                    tamanho_grade = round(tamanho_grade / 5) * 5
                elif distancia_maior > 15:
                    # Aumentar o tamanho das grades para reduzir a distância
                    distancia = 15
                    tamanho_grade = int((medida_total_ajustada - distancia) / 2)
                    # Aproximar para múltiplo de 5
                    tamanho_grade = round(tamanho_grade / 5) * 5
                else:
                    # Usar a opção que estiver mais próxima dos limites
                    if abs(distancia_menor - 15) < abs(distancia_maior - 1):
                        tamanho_grade = tamanho_grade_menor
                        distancia = distancia_menor
                    else:
                        tamanho_grade = tamanho_grade_maior
                        distancia = distancia_maior
            
            # Garantir que a soma seja exata
            soma_atual = (2 * tamanho_grade) + distancia
            if abs(soma_atual - medida_total_ajustada) > 0.1:
                # Ajustar a distância para compensar a diferença
                diferenca = medida_total_ajustada - soma_atual
                distancia = distancia + diferenca
                
                # Garantir que a distância esteja entre 1 e 15
                if distancia < 1:
                    distancia = 1
                elif distancia > 15:
                    distancia = 15
            
            return 2, tamanho_grade, distancia
        
        # LÓGICA: Acima de 259cm = 3 grades
        else:
            # Calcular tamanho ideal das grades (máximo 106cm cada)
            tamanho_grade_ideal = min(106, medida_total_ajustada / 3)
            
            # Tentar encontrar múltiplos de 5 próximos ao tamanho ideal
            tamanho_grade_menor = int(tamanho_grade_ideal / 5) * 5
            tamanho_grade_maior = tamanho_grade_menor + 5
            
            # Calcular distâncias para cada opção (2 distâncias)
            distancia_menor = (medida_total_ajustada - (3 * tamanho_grade_menor)) / 2
            distancia_maior = (medida_total_ajustada - (3 * tamanho_grade_maior)) / 2
            
            # Escolher a melhor opção baseada nos critérios
            if tamanho_grade_maior <= 106 and 1 <= distancia_maior <= 15:
                # Usar a grade maior se estiver dentro dos limites
                tamanho_grade = tamanho_grade_maior
                distancia = distancia_maior
            elif 1 <= distancia_menor <= 15:
                # Usar a grade menor se estiver dentro dos limites
                tamanho_grade = tamanho_grade_menor
                distancia = distancia_menor
            else:
                # Se nenhuma opção estiver dentro dos limites, ajustar
                if distancia_menor < 1:
                    # Reduzir o tamanho das grades para aumentar a distância
                    distancia = 1
                    tamanho_grade = int((medida_total_ajustada - (2 * distancia)) / 3)
                    # Aproximar para múltiplo de 5
                    tamanho_grade = round(tamanho_grade / 5) * 5
                elif distancia_maior > 15:
                    # Aumentar o tamanho das grades para reduzir a distância
                    distancia = 15
                    tamanho_grade = int((medida_total_ajustada - (2 * distancia)) / 3)
                    # Aproximar para múltiplo de 5
                    tamanho_grade = round(tamanho_grade / 5) * 5
                else:
                    # Usar a opção que estiver mais próxima dos limites
                    if abs(distancia_menor - 15) < abs(distancia_maior - 1):
                        tamanho_grade = tamanho_grade_menor
                        distancia = distancia_menor
                    else:
                        tamanho_grade = tamanho_grade_maior
                        distancia = distancia_maior
            
            # Garantir que a soma seja exata
            soma_atual = (3 * tamanho_grade) + (2 * distancia)
            if abs(soma_atual - medida_total_ajustada) > 0.1:
                # Ajustar a distância para compensar a diferença
                diferenca = medida_total_ajustada - soma_atual
                distancia = distancia + (diferenca / 2)
                
                # Garantir que a distância esteja entre 1 e 15
                if distancia < 1:
                    # Se a distância ficou menor que 1, reduzir o tamanho das grades
                    distancia = 1
                    tamanho_grade = int((medida_total_ajustada - (2 * distancia)) / 3)
                    tamanho_grade = round(tamanho_grade / 5) * 5
                    # Recalcular distância com o novo tamanho
                    distancia = (medida_total_ajustada - (3 * tamanho_grade)) / 2
                    if distancia < 1:
                        distancia = 1
                elif distancia > 15:
                    # Se a distância ficou maior que 15, aumentar o tamanho das grades
                    distancia = 15
                    tamanho_grade = int((medida_total_ajustada - (2 * distancia)) / 3)
                    tamanho_grade = round(tamanho_grade / 5) * 5
                    # Recalcular distância com o novo tamanho
                    distancia = (medida_total_ajustada - (3 * tamanho_grade)) / 2
                    if distancia > 15:
                        distancia = 15
                
                # Verificar novamente a soma após os ajustes
                soma_atual = (3 * tamanho_grade) + (2 * distancia)
                if abs(soma_atual - medida_total_ajustada) > 0.1:
                    # Se ainda houver diferença, ajustar a última grade
                    diferenca_final = medida_total_ajustada - soma_atual
                    tamanho_grade = tamanho_grade + (diferenca_final / 3)
                    # Recalcular distância
                    distancia = (medida_total_ajustada - (3 * tamanho_grade)) / 2
                    if distancia < 1:
                        distancia = 1
                    elif distancia > 15:
                        distancia = 15
            
            # Validação final: garantir que temos 3 grades válidas
            if tamanho_grade < 20:
                print(f"[AVISO] Tamanho de grade muito pequeno ({tamanho_grade}cm) para 3 grades. Ajustando...")
                tamanho_grade = 20
                distancia = (medida_total_ajustada - (3 * tamanho_grade)) / 2
                if distancia < 1:
                    distancia = 1
                elif distancia > 15:
                    distancia = 15
            
            print(f"[CALCULO-GRADES] 3 grades calculadas: tamanho={tamanho_grade}cm, distancia={distancia}cm, soma={(3 * tamanho_grade) + (2 * distancia)}cm, alvo={medida_total_ajustada}cm")
            
            return 3, tamanho_grade, distancia

    def calcular_grades_com_desvio_conflitos(self, medida_total):
        """
        Calcula grades evitando conflitos com parafusos.
        Usa a nova lógica como base, mas testa combinações alternativas se há conflitos.
        
        Estratégia:
        1. Tenta a nova lógica (múltiplos de 5 + distância máxima)
        2. Se há conflitos, testa variações de tamanhos e distâncias
        3. Retorna a melhor combinação sem conflitos
        """
        # Primeiro, tentar a nova lógica padrão
        num_grades_base, tamanho_grade_base, distancia_base = self.calcular_grades(medida_total)
        
        # Se é uma grade única, não há conflitos entre grades
        if num_grades_base == 1:
            return num_grades_base, tamanho_grade_base, distancia_base
        
        # Para 2 ou 3 grades, testar se a combinação base tem conflitos
        medida_total_ajustada = medida_total + 22
        
        # Obter posições dos parafusos para verificar conflitos
        pos_parafusos = self._obter_posicoes_parafusos()
        if not pos_parafusos:
            # Se não há parafusos definidos, usar a lógica padrão
            return num_grades_base, tamanho_grade_base, distancia_base
        
        # Testar a combinação base
        if not self._tem_conflitos_grades(tamanho_grade_base, distancia_base, pos_parafusos, num_grades_base):
            return num_grades_base, tamanho_grade_base, distancia_base
        
        print(f"[CONFLITO-GRADES] Combinação base tem conflitos. Testando alternativas...")
        
        # Gerar todas as combinações possíveis
        combinacoes_testadas = []
        melhor_combinacao = None
        
        # Testar variações de tamanho de grade de forma mais ampla
        tamanho_base = tamanho_grade_base
        
        # Primeiro, testar variações pequenas em múltiplos de 5
        for variacao_tamanho in range(-15, 16, 5):  # -15, -10, -5, 0, +5, +10, +15
            tamanho_teste = tamanho_base + variacao_tamanho
            
            # Garantir que o tamanho está dentro dos limites
            if tamanho_teste < 30 or tamanho_teste > 106:
                continue
            
            # Calcular distância correspondente baseado no número de grades
            if num_grades_base == 2:
                distancia_teste = medida_total_ajustada - (2 * tamanho_teste)
            else:  # 3 grades
                distancia_teste = (medida_total_ajustada - (3 * tamanho_teste)) / 2
            
            # Garantir que a distância está dentro dos limites
            if distancia_teste < 1 or distancia_teste > 15:
                continue
            
            # Verificar se não há conflitos
            if not self._tem_conflitos_grades(tamanho_teste, distancia_teste, pos_parafusos, num_grades_base):
                combinacao = (num_grades_base, tamanho_teste, distancia_teste)
                combinacoes_testadas.append(combinacao)
                
                # Priorizar combinações mais próximas da base
                if melhor_combinacao is None:
                    melhor_combinacao = combinacao
                else:
                    # Preferir múltiplos de 5 e distâncias maiores
                    _, tam_atual, dist_atual = melhor_combinacao
                    
                    # Critérios de prioridade
                    multiplo_5_atual = tam_atual % 5 == 0
                    multiplo_5_teste = tamanho_teste % 5 == 0
                    
                    if (multiplo_5_teste and not multiplo_5_atual) or \
                       (multiplo_5_teste == multiplo_5_atual and distancia_teste > dist_atual):
                        melhor_combinacao = combinacao
        
        # Se ainda não encontrou, testar variações não múltiplas de 5
        if melhor_combinacao is None:
            for variacao_tamanho in range(-20, 21, 1):  # Testar todos os valores de -20 a +20
                tamanho_teste = tamanho_base + variacao_tamanho
                
                # Garantir que o tamanho está dentro dos limites
                if tamanho_teste < 30 or tamanho_teste > 106:
                    continue
                
                # Calcular distância correspondente baseado no número de grades
                if num_grades_base == 2:
                    distancia_teste = medida_total_ajustada - (2 * tamanho_teste)
                else:  # 3 grades
                    distancia_teste = (medida_total_ajustada - (3 * tamanho_teste)) / 2
                
                # Garantir que a distância está dentro dos limites
                if distancia_teste < 1 or distancia_teste > 15:
                    continue
                
                # Verificar se não há conflitos
                if not self._tem_conflitos_grades(tamanho_teste, distancia_teste, pos_parafusos, num_grades_base):
                    combinacao = (num_grades_base, tamanho_teste, distancia_teste)
                    combinacoes_testadas.append(combinacao)
                    
                    if melhor_combinacao is None:
                        melhor_combinacao = combinacao
                    else:
                        # Preferir distâncias maiores quando não há múltiplos de 5
                        _, tam_atual, dist_atual = melhor_combinacao
                        if distancia_teste > dist_atual:
                            melhor_combinacao = combinacao
        
        if melhor_combinacao:
            print(f"[CONFLITO-GRADES] Encontrada combinação sem conflitos: {melhor_combinacao}")
            return melhor_combinacao
        
        # Se não encontrou nenhuma combinação sem conflitos, usar a base
        print(f"[CONFLITO-GRADES] Nenhuma combinação sem conflitos encontrada. Usando base.")
        return num_grades_base, tamanho_grade_base, distancia_base
    
    def _obter_posicoes_parafusos(self):
        """Obtém as posições dos parafusos definidos"""
        pos_parafusos = []
        parafusos_campos = ["par_1_2", "par_2_3", "par_3_4", "par_4_5", "par_5_6", "par_6_7", "par_7_8", "par_8_9"]
        
        for par in parafusos_campos:
            campo_par = getattr(self, par, None)
            if campo_par:
                try:
                    valor = float(campo_par.get()) if campo_par.get().strip() else 0.0
                    if valor > 0:
                        pos_parafusos.append(valor)
                except:
                    pass
        
        return pos_parafusos[:-1] if len(pos_parafusos) > 1 else []  # Remover último como na lógica original
    
    def _tem_conflitos_grades(self, tamanho_grade, distancia, pos_parafusos, num_grades=2):
        """
        Verifica se uma combinação de tamanho de grade e distância gera conflitos
        Suporta 1, 2 ou 3 grades
        """
        if not pos_parafusos:
            return False
        
        # Se é apenas 1 grade, não há conflitos entre grades
        if num_grades == 1:
            return False
        
        # Simular distribuição de detalhes
        tolerancia_conflito = 3
        detalhes_grade = self._simular_detalhes_grade(tamanho_grade)
        
        # Verificar conflitos em cada grade
        for grade_num in range(num_grades):
            # Calcular posição base da grade
            if grade_num == 0:
                pos_base = 0
            elif grade_num == 1:
                pos_base = tamanho_grade + distancia
            else:  # grade_num == 2 (terceira grade)
                pos_base = (2 * tamanho_grade) + (2 * distancia)
            
            # Verificar conflitos nesta grade
            pos_acumulada = pos_base
            for detalhe in detalhes_grade:
                if detalhe > 0:
                    pos_acumulada += detalhe
                    for pos_parafuso in pos_parafusos:
                        if abs(pos_acumulada - pos_parafuso) <= tolerancia_conflito:
                            return True
        
        return False
    
    def _simular_detalhes_grade(self, tamanho_grade):
        """Simula a distribuição de detalhes para uma grade de tamanho específico"""
        if tamanho_grade <= 0:
            return [0, 0, 0, 0, 0]
        
        # Calcular quantidade de detalhes baseado no valor da grade
        quantidade = min(5, max(1, int(math.ceil(tamanho_grade / 30))))
        
        # Distribuir igualmente
        valor_base = tamanho_grade // quantidade
        resto = tamanho_grade - (valor_base * quantidade)
        detalhes = [valor_base] * quantidade
        
        # Distribuir o resto nas extremidades
        left = 0
        right = quantidade - 1
        for i in range(resto):
            if i % 2 == 0:
                detalhes[left] += 1
                left += 1
            else:
                detalhes[right] += 1
                right -= 1
        
        # Completar com zeros
        while len(detalhes) < 5:
            detalhes.append(0)
        
        return detalhes

    def verificar_conflitos_detalhes_grade(self, idx):
        """
        Apenas verifica conflitos e pinta os campos dos detalhes das grades,
        sem recalcular os valores. Usado após carregar dados salvos.
        """
        try:
            # 1. Obter valores dos detalhes atuais dos campos
            detalhes = []
            for i in range(5):
                campo = getattr(self, f"detalhe_grade{idx}_{i+1}", None)
                if campo:
                    try:
                        valor = float(campo.get()) if campo.get().strip() else 0.0
                    except:
                        valor = 0.0
                else:
                    valor = 0.0
                detalhes.append(valor)

            # 2. Obter posições dos parafusos
            pos_parafusos = []
            parafusos_campos = ["par_1_2", "par_2_3", "par_3_4", "par_4_5", "par_5_6", "par_6_7", "par_7_8", "par_8_9"]
            for par in parafusos_campos:
                campo_par = getattr(self, par, None)
                if campo_par:
                    try:
                        valor = float(campo_par.get()) if campo_par.get().strip() else 0.0
                        if valor > 0:
                            pos_parafusos.append(valor)
                    except:
                        pass

            # 3. Calcular posições dos detalhes
            detalhes_anteriores = []
            dist_anteriores = []
            
            if idx > 1:
                # Para grades 2 e 3, considerar detalhes das grades anteriores
                for grade_ant in range(1, idx):
                    for j in range(5):
                        campo_ant = getattr(self, f"detalhe_grade{grade_ant}_{j+1}", None)
                        if campo_ant:
                            try:
                                valor = float(campo_ant.get()) if campo_ant.get().strip() else 0.0
                                if valor > 0:
                                    detalhes_anteriores.append(valor)
                            except:
                                pass
                    
                    # Adicionar distância da grade anterior
                    dist_campo = getattr(self, f"distancia_{grade_ant}", None)
                    if dist_campo:
                        try:
                            dist = float(dist_campo.get()) if dist_campo.get().strip() else 0.0
                            if dist > 0:
                                dist_anteriores.append(dist)
                        except:
                            pass

            # 4. Calcular posições dos detalhes
            base_inicial = sum(detalhes_anteriores) + sum(dist_anteriores)
            pos_detalhes = []
            pos_acumulada = base_inicial
            
            for detalhe in detalhes:
                if detalhe > 0:
                    pos_acumulada += detalhe
                    pos_detalhes.append(pos_acumulada)
                else:
                    pos_detalhes.append(pos_acumulada)

            # 5. Verificar colisões e pintar campos
            pos_parafusos_sem_ultimo = pos_parafusos[:-1] if len(pos_parafusos) > 1 else []
            
            print(f"[DEBUG-VERIFICACAO] Grade {idx}: pos_detalhes={pos_detalhes}, pos_parafusos={pos_parafusos_sem_ultimo}")
            
            # Tolerância de conflito (±3cm)
            tolerancia_conflito = 3
            
            # Verificar e pintar campos
            for i, pos in enumerate(pos_detalhes):
                campo = getattr(self, f"detalhe_grade{idx}_{i+1}", None)
                if campo and detalhes[i] > 0:
                    tem_conflito = False
                    # Conflitos são identificados apenas na régua, não nos campos
                    campo.configure(bg='white')
                elif campo:
                    campo.configure(bg='white')
            
            # Retornar informações para possível uso posterior
            return detalhes, pos_detalhes, pos_parafusos_sem_ultimo, detalhes_anteriores, dist_anteriores
            
        except Exception as e:
            print(f"Erro ao verificar conflitos: {e}")
            return None

    def otimizar_distribuicao_detalhes(self, detalhes, total_grade=None):
        """
        Otimiza a distribuição dos detalhes para que fiquem o mais equilibrados possível.
        Ajusta os valores para minimizar a diferença entre eles.
        
        Args:
            detalhes: Lista com valores dos detalhes
            total_grade: Valor total da grade (se None, usa a soma dos detalhes)
            
        Returns:
            Lista com detalhes otimizados
        """
        # Filtrar apenas detalhes com valor > 0
        detalhes_ativos = [d for d in detalhes if d > 0]
        if not detalhes_ativos or len(detalhes_ativos) <= 1:
            return detalhes
        
        # Se total_grade não foi fornecido, usar a soma atual
        if total_grade is None:
            total_grade = sum(detalhes_ativos)
        
        # Calcular a média ideal
        media = total_grade / len(detalhes_ativos)
        
        # Inicializar com valores próximos da média, mas garantindo que sejam inteiros
        detalhes_otimizados = []
        soma_atual = 0
        
        # Distribuir os valores inteiros mais próximos da média
        for i in range(len(detalhes_ativos)):
            if i == len(detalhes_ativos) - 1:
                # O último detalhe recebe o que falta para completar o total
                valor = total_grade - soma_atual
            else:
                # Arredondar para o inteiro mais próximo
                valor = int(round(media))
            
            detalhes_otimizados.append(valor)
            soma_atual += valor
        
        # Verificar se a soma está correta
        if sum(detalhes_otimizados) != total_grade:
            # Ajustar para garantir que a soma seja exatamente igual ao total
            diferenca = total_grade - sum(detalhes_otimizados)
            
            # Distribuir a diferença
            if diferenca > 0:
                # Adicionar a diferença aos menores valores
                indices_ordenados = sorted(range(len(detalhes_otimizados)), 
                                          key=lambda i: detalhes_otimizados[i])
                for i in range(int(diferenca)):
                    idx = indices_ordenados[i % len(indices_ordenados)]
                    detalhes_otimizados[idx] += 1
            elif diferenca < 0:
                # Subtrair a diferença dos maiores valores
                indices_ordenados = sorted(range(len(detalhes_otimizados)), 
                                          key=lambda i: -detalhes_otimizados[i])
                for i in range(abs(int(diferenca))):
                    idx = indices_ordenados[i % len(indices_ordenados)]
                    if detalhes_otimizados[idx] > 1:  # Evitar zerar um detalhe
                        detalhes_otimizados[idx] -= 1
        
        # Verificar diferenças entre detalhes
        max_diferenca = max(detalhes_otimizados) - min(detalhes_otimizados)
        if max_diferenca > 3:
            # Tentar reduzir diferenças muito grandes (> 3)
            while max_diferenca > 3:
                idx_max = detalhes_otimizados.index(max(detalhes_otimizados))
                idx_min = detalhes_otimizados.index(min(detalhes_otimizados))
                
                # Transferir 1 unidade do maior para o menor
                detalhes_otimizados[idx_max] -= 1
                detalhes_otimizados[idx_min] += 1
                
                # Recalcular a diferença máxima
                max_diferenca = max(detalhes_otimizados) - min(detalhes_otimizados)
        
        # Reconstruir a lista completa
        resultado = []
        idx_ativo = 0
        for d in detalhes:
            if d > 0:
                resultado.append(detalhes_otimizados[idx_ativo])
                idx_ativo += 1
            else:
                resultado.append(0)
        
        # Garantir que a soma seja exatamente igual ao total_grade
        assert sum(d for d in resultado if d > 0) == total_grade, "A soma dos detalhes deve ser igual ao total da grade"
        
        return resultado

    def resolver_conflito_automatico(self, idx, detalhes, pos_detalhes, pos_parafusos_sem_ultimo, detalhes_anteriores, dist_anteriores):
        # Função desabilitada - conflitos devem ser resolvidos manualmente pelos botões
        return detalhes, False, []

    def ajustar_distancias_grades(self):
        """
        Ajusta as distâncias entre grades para maximizar o espaço e melhorar a distribuição dos detalhes.
        Prioriza usar a distância máxima de 15cm, mas ajusta se necessário para garantir que:
        1. Soma das grades + distâncias = comprimento + 22
        2. Distância entre 1 e 15, priorizando o máximo possível
        """
        try:
            # Obter o comprimento total
            comprimento = self.comprimento.get().strip()
            if not comprimento:
                return
                
            comprimento = float(comprimento)
            
            # Ajustar o comprimento adicionando 22cm
            comprimento_ajustado = comprimento + 22
            
            # Obter valores atuais das grades
            grade1 = float(self.grade_1.get() or 0)
            grade2 = float(self.grade_2.get() or 0)
            grade3 = float(self.grade_3.get() or 0)
            
            # Contar quantas grades estão ativas
            grades_ativas = []
            if grade1 > 0:
                grades_ativas.append(grade1)
            if grade2 > 0:
                grades_ativas.append(grade2)
            if grade3 > 0:
                grades_ativas.append(grade3)
            
            num_grades = len(grades_ativas)
            
            if num_grades <= 1:
                return  # Não há distâncias para ajustar
                
            # Calcular a distância ideal
            distancia_maxima = 15  # Máximo de 15cm
            distancia_minima = 1   # Mínimo de 1cm
            
            if num_grades == 2:
                # Duas grades ativas
                soma_grades = sum(grades_ativas)
                
                # Calcular a distância exata para que a soma seja igual ao comprimento ajustado
                distancia = comprimento_ajustado - soma_grades
                
                # Verificar se a distância está dentro dos limites
                if distancia < distancia_minima:
                    print(f"AVISO: Distância calculada ({distancia:.2f}) menor que o mínimo. Ajustando para {distancia_minima}.")
                    distancia = distancia_minima
                elif distancia > distancia_maxima:
                    print(f"AVISO: Distância calculada ({distancia:.2f}) maior que o máximo. Ajustando para {distancia_maxima}.")
                    distancia = distancia_maxima
                
                # Atualizar distância
                self.distancia_1.delete(0, tk.END)
                self.distancia_1.insert(0, str(int(distancia)))
                
            elif num_grades == 3:
                # Três grades ativas
                soma_grades = sum(grades_ativas)
                
                # Calcular a distância total disponível
                distancia_total = comprimento_ajustado - soma_grades
                
                # Dividir igualmente entre as duas distâncias
                distancia = distancia_total / 2
                
                # Verificar se a distância está dentro dos limites
                if distancia < distancia_minima:
                    print(f"AVISO: Distância calculada ({distancia:.2f}) menor que o mínimo. Ajustando para {distancia_minima}.")
                    distancia = distancia_minima
                elif distancia > distancia_maxima:
                    print(f"AVISO: Distância calculada ({distancia:.2f}) maior que o máximo. Ajustando para {distancia_maxima}.")
                    distancia = distancia_maxima
                
                # Atualizar distâncias
                self.distancia_1.delete(0, tk.END)
                self.distancia_1.insert(0, str(int(distancia)))
                
                self.distancia_2.delete(0, tk.END)
                self.distancia_2.insert(0, str(int(distancia)))
                
            # Verificar se a soma das grades + distâncias = comprimento_ajustado
            soma_atual = sum(grades_ativas)
            if num_grades == 2:
                soma_atual += int(self.distancia_1.get() or 0)
            elif num_grades == 3:
                soma_atual += int(self.distancia_1.get() or 0)
                soma_atual += int(self.distancia_2.get() or 0)
            
            if abs(soma_atual - comprimento_ajustado) > 1:
                print(f"AVISO: A soma das grades + distâncias ({soma_atual}) não é igual ao comprimento ajustado ({comprimento_ajustado}).")
                # Ajustar a última grade para compensar a diferença
                diferenca = comprimento_ajustado - soma_atual
                if grade3 > 0:
                    nova_grade = grade3 + diferenca
                    if nova_grade >= 20:  # Mínimo aceitável para grade
                        self.grade_3.delete(0, tk.END)
                        self.grade_3.insert(0, str(int(nova_grade)))
                elif grade2 > 0:
                    nova_grade = grade2 + diferenca
                    if nova_grade >= 20:  # Mínimo aceitável para grade
                        self.grade_2.delete(0, tk.END)
                        self.grade_2.insert(0, str(int(nova_grade)))
                elif grade1 > 0:
                    nova_grade = grade1 + diferenca
                    if nova_grade >= 20:  # Mínimo aceitável para grade
                        self.grade_1.delete(0, tk.END)
                        self.grade_1.insert(0, str(int(nova_grade)))
                
        except Exception as e:
            print(f"Erro ao ajustar distâncias: {e}")

    def atualizar_detalhes_grade(self, idx):
        """
        Atualiza os campos de detalhes da grade correspondente (1, 2 ou 3)
        Agora também colore de vermelho os detalhes que colidem com parafusos (±3cm)
        Para grade 2 e 3, soma cumulativa dos detalhes anteriores e distâncias.
        Inclui resolução automática de conflitos e otimização de distribuição.
        
        Regras fundamentais:
        1. Soma dos detalhes = grade (garantido nesta função)
        2. Soma das grades + distâncias = comprimento + 22 (garantido em ajustar_distancias_grades)
        3. Distância entre 1 e 15, priorizando o máximo possível (garantido em ajustar_distancias_grades)
        """
        grade_field = f"grade_{idx}"
        try:
            valor = self.__getattribute__(grade_field).get()
            valor = float(valor) if valor else 0
            # Garantir que o valor seja um inteiro
            valor = int(valor)
        except Exception:
            valor = 0
            
        # Se o valor for zero, limpar todos os campos de detalhe
        if valor == 0:
            for i in range(5):
                campo = getattr(self, f"detalhe_grade{idx}_{i+1}", None)
                if campo:
                    campo.delete(0, tk.END)
                    campo.insert(0, "0")
                    campo.configure(bg='white')
            return
            
        # Calcular quantidade de detalhes baseado no valor da grade
        quantidade = min(5, max(1, int(math.ceil(valor / 30))))
        
        # Inicialmente, distribuir igualmente
        valor_base = valor // quantidade
        resto = valor - (valor_base * quantidade)
        detalhes = [valor_base] * quantidade
        
        # Distribuir o resto nas extremidades, alternando para dentro
        left = 0
        right = quantidade - 1
        for i in range(resto):
            if i % 2 == 0:
                detalhes[left] += 1
                left += 1
            else:
                detalhes[right] += 1
                right -= 1
                
        # Completar com zeros
        while len(detalhes) < 5:
            detalhes.append(0)
        
        # Otimizar distribuição para que os detalhes fiquem o mais equilibrados possível
        # Garantindo que a soma seja exatamente igual ao valor da grade
        detalhes = self.otimizar_distribuicao_detalhes(detalhes, valor)

        # Verificar conflitos e resolver automaticamente
        resultado = self.verificar_conflitos_detalhes_grade(idx)
        if resultado:
            detalhes_atuais, pos_detalhes, pos_parafusos_sem_ultimo, detalhes_anteriores, dist_anteriores = resultado
            
            # Verificar se há conflitos
            tem_conflito = False
            for i, pos in enumerate(pos_detalhes):
                if detalhes[i] > 0:
                    for p in pos_parafusos_sem_ultimo:
                        if abs(pos - p) <= 3:  # Tolerância de 3cm
                            tem_conflito = True
                            break
                    if tem_conflito:
                        break
            
            # Conflitos são identificados apenas na régua, sem resolução automática
                    
                    # Ajustar distâncias entre grades para melhorar distribuição
                    self.ajustar_distancias_grades()

        # Verificar se a soma dos detalhes é exatamente igual ao valor da grade
        soma_detalhes = sum(detalhes)
        if soma_detalhes != valor:
            # Ajustar o último detalhe para compensar a diferença
            diferenca = valor - soma_detalhes
            for i in range(len(detalhes)-1, -1, -1):
                if detalhes[i] > 0:
                    detalhes[i] += diferenca
                    break
        
        # Atualizar campos
        for i in range(5):
            campo = getattr(self, f"detalhe_grade{idx}_{i+1}", None)
            if campo:
                campo.delete(0, tk.END)
                campo.insert(0, str(detalhes[i]))
                
        # Verificar novamente os conflitos para atualizar as cores
        self.verificar_conflitos_detalhes_grade(idx)
        
        # Salvar automaticamente após atualizar detalhes
        if hasattr(self, 'salvar_pilar'):
            self.salvar_pilar(mostrar_mensagem=False) 