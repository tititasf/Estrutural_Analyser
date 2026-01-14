import tkinter as tk
from tkinter import ttk
import os
import logging

# Configurar o logger
logging.basicConfig(filename='app.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def atualizar_status(mensagem):
    """Atualiza o status da aplicação com a mensagem fornecida e registra no log."""
    status_label = ttk.Label(main_frame, text=mensagem)
    status_label.grid(row=10, column=0, columnspan=3, sticky="w")
    logging.info(mensagem)  # Registrar a mensagem no log

def calcular_paineis_largura(*args):
    try:
        largura_total = validar_entrada(largura_total_entry.get(), "Largura Total")
        
        # Obter valores dos campos travados
        valores_travados = {}  # {posição: valor}
        for i, entry in enumerate(paineis_largura_entries):
            if paineis_largura_locks[i].get():
                try:
                    valor = float(entry.get() or 0)
                    valores_travados[i] = valor
                except ValueError:
                    continue

        # Calcular largura disponível (total menos campos travados)
        largura_disponivel = largura_total - sum(valores_travados.values())
        
        # Limpar TODOS os campos não travados primeiro
        for i in range(5):
            if not paineis_largura_locks[i].get():
                paineis_largura_entries[i].delete(0, tk.END)

        # Reorganizar posições considerando campos travados
        posicoes_livres = [i for i in range(5) if i not in valores_travados]
        
        # Calcular valores baseado na largura total (não na largura disponível)
        if largura_total <= 244:
            if posicoes_livres:
                paineis_largura_entries[posicoes_livres[0]].insert(0, str(int(largura_disponivel)))
                
        elif 245 <= largura_total <= 304:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "122")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, str(int(largura_disponivel - 122)))
                
        elif 305 <= largura_total <= 425:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "244")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, str(int(largura_disponivel - 244)))
                
        elif 426 <= largura_total <= 487:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "244")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, "122")
            if len(posicoes_livres) >= 3:
                paineis_largura_entries[posicoes_livres[2]].insert(0, str(int(largura_disponivel - 244 - 122)))
                
        elif 488 <= largura_total <= 547:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "244")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, "122")
            if len(posicoes_livres) >= 3:
                paineis_largura_entries[posicoes_livres[2]].insert(0, str(int(largura_disponivel - 244 - 122)))
                
        elif 548 <= largura_total <= 609:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "244")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, "244")
            if len(posicoes_livres) >= 3:
                paineis_largura_entries[posicoes_livres[2]].insert(0, str(int(largura_disponivel - 244 - 244)))
                
        elif 610 <= largura_total <= 731:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "244")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, "244")
            if len(posicoes_livres) >= 3:
                paineis_largura_entries[posicoes_livres[2]].insert(0, str(int(largura_disponivel - 244 - 244)))
                
        elif 732 <= largura_total <= 791:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "244")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, "244")
            if len(posicoes_livres) >= 3:
                paineis_largura_entries[posicoes_livres[2]].insert(0, "122")
            if len(posicoes_livres) >= 4:
                paineis_largura_entries[posicoes_livres[3]].insert(0, str(int(largura_disponivel - 244 - 244 - 122)))
                
        elif 792 <= largura_total <= 913:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "244")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, "244")
            if len(posicoes_livres) >= 3:
                paineis_largura_entries[posicoes_livres[2]].insert(0, "244")
            if len(posicoes_livres) >= 4:
                paineis_largura_entries[posicoes_livres[3]].insert(0, str(int(largura_disponivel - 244 - 244 - 244)))
                
        elif 914 <= largura_total <= 974:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "244")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, "244")
            if len(posicoes_livres) >= 3:
                paineis_largura_entries[posicoes_livres[2]].insert(0, "244")
            if len(posicoes_livres) >= 4:
                paineis_largura_entries[posicoes_livres[3]].insert(0, str(int(largura_disponivel - 244 - 244 - 244)))
                
        elif 975 <= largura_total <= 1097:
            if len(posicoes_livres) >= 1:
                paineis_largura_entries[posicoes_livres[0]].insert(0, "244")
            if len(posicoes_livres) >= 2:
                paineis_largura_entries[posicoes_livres[1]].insert(0, "244")
            if len(posicoes_livres) >= 3:
                paineis_largura_entries[posicoes_livres[2]].insert(0, "244")
            if len(posicoes_livres) >= 4:
                paineis_largura_entries[posicoes_livres[3]].insert(0, "122")
            if len(posicoes_livres) >= 5:
                paineis_largura_entries[posicoes_livres[4]].insert(0, str(int(largura_disponivel - 244 - 244 - 244 - 122)))

        # Configurar estado dos campos
        for i, entry in enumerate(paineis_largura_entries):
            if paineis_largura_locks[i].get():
                entry.config(state='readonly')
            else:
                entry.config(state='normal')

    except Exception as e:
        atualizar_status(f"Erro ao calcular larguras: {str(e)}")

def calcular_paineis_altura(*args):
    try:
        altura_total = int(altura_total_entry.get())
        altura_laje = int(altura_laje_entry.get() or 0)
        
        # Preservar valores dos campos travados
        valores_travados = []
        posicoes_travadas = []
        for i, entry in enumerate(paineis_altura_entries):
            if paineis_altura_locks[i].get():
                try:
                    valor = float(entry.get() or 0)
                    valores_travados.append(valor)
                    posicoes_travadas.append(i)
                except ValueError:
                    continue

        # Subtrair valores travados da altura total
        altura_disponivel = altura_total - altura_laje - sum(valores_travados)

        # Limpar campos não travados
        for i in range(3):
            if not paineis_altura_locks[i].get():
                paineis_altura_entries[i].delete(0, tk.END)

        # Calcular valores para posições não travadas
        altura_restante = altura_disponivel
        posicao_atual = 0
        
        while altura_restante > 0 and posicao_atual < 3:
            if not paineis_altura_locks[posicao_atual].get():
                if altura_restante >= 122:
                    paineis_altura_entries[posicao_atual].insert(0, "122")
                    altura_restante -= 122
                else:
                    paineis_altura_entries[posicao_atual].insert(0, str(int(altura_restante)))
                    altura_restante = 0
            posicao_atual += 1

        # Configurar estado dos campos
        for i, entry in enumerate(paineis_altura_entries):
            if paineis_altura_locks[i].get():
                entry.config(state='readonly')
            else:
                entry.config(state='normal')

    except Exception as e:
        atualizar_status(f"Erro ao calcular alturas: {str(e)}")

# Adicionar bind para os checkboxes
def atualizar_estado_campo(entry, lock_var):
    if lock_var.get():
        entry.config(state='readonly')
    else:
        entry.config(state='normal')

# Configurar binds para os locks
def configurar_binds():
    for i in range(5):
        paineis_largura_locks[i].trace_add('write', 
            lambda *args, e=paineis_largura_entries[i], v=paineis_largura_locks[i]: 
            atualizar_estado_campo(e, v))

    for i in range(3):
        paineis_altura_locks[i].trace_add('write', 
            lambda *args, e=paineis_altura_entries[i], v=paineis_altura_locks[i]: 
            atualizar_estado_campo(e, v))

def atualizar_grades(*args):
    try:
        # Obter o valor da primeira grade
        valor_grade = grades_entries[0].get().strip()
        if not valor_grade:
            return
        
        valor_grade = int(valor_grade)
        
        # Contar quantos painéis têm largura preenchida
        num_paineis = sum(1 for entry in paineis_largura_entries if entry.get().strip())
        
        if num_paineis == 0:
            return
            
        # O número de grades é sempre número de painéis + 1
        num_grades = num_paineis + 1
        
        # Limpar todos os campos de grade que serão usados
        for i in range(1, num_grades):
            if i < len(grades_entries) and not grades_locks[i].get():  # Verifica se não está travado
                grades_entries[i].delete(0, tk.END)
                grades_entries[i].insert(0, str(valor_grade))
        
        # Limpar os campos que não serão usados
        for i in range(num_grades, len(grades_entries)):
            if not grades_locks[i].get():  # Verifica se não está travado
                grades_entries[i].delete(0, tk.END)
                
    except ValueError:
        pass

def desenhar_paineis_altura_1(script, x_inicial, y_inicial, larguras_paineis, altura_painel):  # Validando tamanhos
    if not larguras_paineis or altura_painel <= 0:
        atualizar_status("Erro: Largura ou altura dos painéis inválida.")
        return
    x_atual = x_inicial
    for largura in larguras_paineis:
        if largura <= 0:
            continue  # Ignorar larguras não válidas
        script.append("_PLINE")
        script.append(f"{x_atual},{y_inicial}")
        script.append(f"{x_atual + largura},{y_inicial}")
        script.append(f"{x_atual + largura},{y_inicial + altura_painel}")
        script.append(f"{x_atual},{y_inicial + altura_painel}")
        script.append("C")
        script.append(";")
        x_atual += largura  # Atualizando x_atual para a próxima largura

def desenhar_paineis_altura_2(script, x_inicial, y_inicial, larguras_paineis, altura_painel, altura_painel_1):  # Validando entradas
    if not larguras_paineis or altura_painel <= 0 or altura_painel_1 <= 0:
        atualizar_status("Erro: Dados inválidos para Painel 2.")
        return
    
    x_atual = x_inicial
    for largura in larguras_paineis:
        if largura <= 0:
            continue  # Ignorar larguras não válidas
        # Posicionar diretamente na posição inicial
        script.append("_PLINE")
        script.append(f"{x_atual},{y_inicial}")
        script.append(f"{x_atual + largura},{y_inicial}")
        script.append(f"{x_atual + largura},{y_inicial + altura_painel}")
        script.append(f"{x_atual},{y_inicial + altura_painel}")
        script.append("C")
        script.append(";")
        x_atual += largura

def desenhar_paineis_altura_3(script, x_inicial, y_inicial, larguras_paineis, altura_painel, altura_painel_2):
    """Desenha os painéis da terceira altura."""
    if not larguras_paineis or altura_painel <= 0 or altura_painel_2 <= 0:
        atualizar_status("Erro: Dados inválidos para Painel 3.")
        return
    
    x_atual = x_inicial
    for largura in larguras_paineis:
        if largura <= 0:
            continue
        script.append("_PLINE")
        script.append(f"{x_atual},{y_inicial}")
        script.append(f"{x_atual + largura},{y_inicial}")
        script.append(f"{x_atual + largura},{y_inicial + altura_painel}")
        script.append(f"{x_atual},{y_inicial + altura_painel}")
        script.append("C")
        script.append(";")
        x_atual += largura

def calcular_posicao_texto(x_inicial, y_inicial, altura_maxima):
    # Posiciona o texto 5cm acima do ponto mais alto do desenho
    y_texto = y_inicial + altura_maxima + 5
    return x_inicial, y_texto

def gerar_script():  # Modularizado
    try:
        validar_todos_campos()
        validar_dimensoes()
        criar_script()
        atualizar_status("Script gerado com sucesso!")
    except Exception as e:
        atualizar_status(f"Erro ao gerar script: {str(e)}")
        logging.error(f"Erro ao gerar script: {str(e)}")  # Registrar erro no log
        return False
    return True

def validar_entrada(valor, campo, tipo=int, opcional=False):  # Nova função de validação
    try:
        if opcional and not valor.strip():
            return 0 if tipo == int else 0.0
        return tipo(valor)
    except ValueError:
        atualizar_status(f"Erro no campo '{campo}': Verifique se o valor é do tipo correto ({tipo.__name__}).")
        raise

def validar_todos_campos():  # Função centralizada para validação de inputs
    validar_entrada(largura_total_entry.get(), "Largura Total")
    validar_entrada(altura_total_entry.get(), "Altura Total")
    validar_entrada(altura_laje_entry.get(), "Altura da Laje", tipo=float, opcional=True)
    validar_entrada(posicao_laje.get(), "Posição da Laje", tipo=int)

def validar_dimensoes():
    """Valida as dimensões inseridas nos campos."""
    try:
        largura = float(largura_total_entry.get())
        altura = float(altura_total_entry.get())
        if largura <= 0 or altura <= 0:
            raise ValueError("Dimensões devem ser maiores que zero")
        return True
    except ValueError as e:
        atualizar_status(f"Erro na validação de dimensões: {str(e)}")
        return False

def criar_script():
    """Cria o script com os comandos do AutoCAD."""
    try:
        script = []
        x_inicial = 0
        y_inicial = 0

        # Obter valores dos campos
        nome = nome_entry.get()
        observacoes = observacoes_entry.get()
        altura_laje_valor = float(altura_laje_entry.get() or 0)
        posicao_laje_valor = int(posicao_laje.get())

        # Obter larguras e alturas dos painéis
        larguras_paineis = [float(entry.get()) for entry in paineis_largura_entries if entry.get().strip()]
        alturas_paineis = [float(entry.get()) for entry in paineis_altura_entries if entry.get().strip()]
        
        # Calcular largura total
        largura_total = sum(larguras_paineis)

        # Calcular posições Y dos painéis considerando a laje
        y_paineis = []
        y_atual = y_inicial
        
        for i in range(len(alturas_paineis)):
            if i == 0:
                y_paineis.append(y_atual)
                y_atual += alturas_paineis[0]
            else:
                if (posicao_laje_valor == 1 and i == 1):
                    y_laje_temp = y_paineis[0] + alturas_paineis[0]
                    y_paineis.append(y_laje_temp + altura_laje_valor)
                    y_atual = y_paineis[-1] + alturas_paineis[i]
                elif (posicao_laje_valor == 2 and i == 2):
                    y_laje_temp = y_paineis[1] + alturas_paineis[1]
                    y_paineis.append(y_laje_temp + altura_laje_valor)
                    y_atual = y_paineis[-1] + alturas_paineis[i]
                else:
                    y_paineis.append(y_atual)
                    y_atual += alturas_paineis[i]

        # Calcular posição Y da laje
        y_laje = y_inicial
        if posicao_laje_valor == 1 and len(alturas_paineis) > 0:
            y_laje += alturas_paineis[0]
        elif posicao_laje_valor == 2 and len(alturas_paineis) > 1:
            y_laje += alturas_paineis[0] + alturas_paineis[1]
        elif posicao_laje_valor == 3 and len(alturas_paineis) > 2:
            y_laje += sum(alturas_paineis)

        # Comandos básicos de configuração
        script.append("_ZOOM")
        script.append("E")
        script.append(";")

        # Desenhar a laje
        if altura_laje_valor > 0:
            script.append("-LAYER")
            script.append("S COTA")
            script.append("")
            script.append(";")

            script.append("_PLINE")
            script.append(f"{x_inicial},{y_laje}")
            script.append(f"{x_inicial+largura_total},{y_laje}")
            script.append(f"{x_inicial+largura_total},{y_laje+altura_laje_valor}")
            script.append(f"{x_inicial},{y_laje+altura_laje_valor}")
            script.append("C")
            script.append(";")

            # Hatch na laje
            script.append("HHHH")
            x_centro = x_inicial + (largura_total / 2)
            y_centro = y_laje + (altura_laje_valor / 2)
            script.append(f"{x_centro},{y_centro}")
            script.append(";")

        # Layer Painéis e desenho dos painéis
        script.append("-LAYER")
        script.append("S Painéis")
        script.append("")
        script.append(";")

        # Desenhar painéis
        if len(alturas_paineis) > 0:
            desenhar_paineis_altura_1(script, x_inicial, y_paineis[0], larguras_paineis, alturas_paineis[0])
            if len(alturas_paineis) > 1:
                desenhar_paineis_altura_2(script, x_inicial, y_paineis[1], larguras_paineis, alturas_paineis[1], alturas_paineis[0])
                if len(alturas_paineis) > 2:
                    desenhar_paineis_altura_3(script, x_inicial, y_paineis[2], larguras_paineis, alturas_paineis[2], alturas_paineis[1])

        # Layer para sarrafos retangulares verticais
        script.append("-LAYER")
        script.append("S SARR_3.5x7")
        script.append("")
        script.append(";")

        if len(larguras_paineis) > 0:
            # Determinar altura máxima considerando a laje
            altura_maxima = 0
            if posicao_laje_valor == 1 and len(alturas_paineis) > 0:
                altura_maxima = alturas_paineis[0]  # Vai até o primeiro painel se laje está entre 1 e 2
            elif posicao_laje_valor == 2 and len(alturas_paineis) > 1:
                altura_maxima = alturas_paineis[0] + alturas_paineis[1]  # Vai até o segundo painel se laje está entre 2 e 3
            else:
                altura_maxima = sum(alturas_paineis)  # Vai até o topo se não há laje ou laje está no final

            y_topo = y_paineis[0] + altura_maxima

            # Obter apenas as grades com valores válidos
            grades_valores = []
            for entry in grades_entries:
                try:
                    valor = entry.get().strip()
                    if valor:  # Se não estiver em branco
                        grades_valores.append(float(valor))
                except ValueError:
                    continue

            if len(larguras_paineis) > 0 and grades_valores:  # Só desenha se tiver painéis e grades
                # 1. Sarrafo retangular no primeiro painel (15cm da esquerda)
                if len(grades_valores) > 0:  # Verifica se tem pelo menos uma grade
                    x_grade = x_inicial + 15
                    script.append("_PLINE")
                    script.append(f"{x_grade},{y_topo-2.2}")
                    script.append(f"{x_grade+3.5},{y_topo-2.2}")
                    script.append(f"{x_grade+3.5},{y_topo-2.2-grades_valores[0]}")
                    script.append(f"{x_grade},{y_topo-2.2-grades_valores[0]}")
                    script.append("C")
                    script.append(";")

                # 2. Sarrafo retangular no último painel (15cm da direita)
                if grades_valores:  # Usa a última grade disponível
                    x_grade = x_inicial + largura_total - 15 - 3.5
                    script.append("_PLINE")
                    script.append(f"{x_grade},{y_topo-2.2}")
                    script.append(f"{x_grade+3.5},{y_topo-2.2}")
                    script.append(f"{x_grade+3.5},{y_topo-2.2-grades_valores[-1]}")
                    script.append(f"{x_grade},{y_topo-2.2-grades_valores[-1]}")
                    script.append("C")
                    script.append(";")

                # 3. Sarrafos retangulares nas uniões entre painéis
                for i in range(len(larguras_paineis)-1):
                    if i+1 < len(grades_valores):  # Só desenha se tiver grade definida para esta posição
                        x_uniao = x_inicial + sum(larguras_paineis[:i+1])
                        
                        # Sarrafo à direita do painel da esquerda
                        x_grade = x_uniao - 3.5
                        script.append("_PLINE")
                        script.append(f"{x_grade},{y_topo-2.2}")
                        script.append(f"{x_grade+3.5},{y_topo-2.2}")
                        script.append(f"{x_grade+3.5},{y_topo-2.2-grades_valores[i+1]}")
                        script.append(f"{x_grade},{y_topo-2.2-grades_valores[i+1]}")
                        script.append("C")
                        script.append(";")
                        
                        # Sarrafo à esquerda do painel da direita
                        x_grade = x_uniao
                        script.append("_PLINE")
                        script.append(f"{x_grade},{y_topo-2.2}")
                        script.append(f"{x_grade+3.5},{y_topo-2.2}")
                        script.append(f"{x_grade+3.5},{y_topo-2.2-grades_valores[i+1]}")
                        script.append(f"{x_grade},{y_topo-2.2-grades_valores[i+1]}")
                        script.append("C")
                        script.append(";")

        # Layer para sarrafos verticais simples
        script.append("-LAYER")
        script.append("S SARR_2.2x7")
        script.append("")
        script.append(";")

        # Sarrafo na primeira parede (7cm da esquerda)
        x_sarrafo = x_inicial + 7
        script.append("_PLINE")
        script.append(f"{x_sarrafo},{y_paineis[0]}")  # Sem espaço após coordenadas
        script.append(f"{x_sarrafo},{y_topo}")  # Sem espaço após coordenadas
        script.append("")  # Linha vazia antes do ponto e vírgula
        script.append(";")

        # Sarrafo na última parede (7cm da direita)
        x_sarrafo = x_inicial + largura_total - 7
        script.append("_PLINE")
        script.append(f"{x_sarrafo},{y_paineis[0]}")  # Sem espaço após coordenadas
        script.append(f"{x_sarrafo},{y_topo}")  # Sem espaço após coordenadas
        script.append("")  # Linha vazia antes do ponto e vírgula
        script.append(";")

        # Layer para cotas
        script.append("-LAYER")
        script.append("S COTA")
        script.append("")
        script.append(";")

        # Cotas individuais dos painéis de altura 1 (20cm abaixo)
        x_atual = x_inicial
        for i, largura in enumerate(larguras_paineis):
            # Linha de cota
            script.append("_DIMLINEAR")
            # Primeiro ponto no desenho
            script.append(f"{x_atual},{y_paineis[0]}")
            # Segundo ponto no desenho
            script.append(f"{x_atual+largura},{y_paineis[0]}")
            # Posição da linha de cota
            script.append(f"{x_atual+largura/2},{y_paineis[0]-20}")
            script.append("")
            script.append(";")
            x_atual += largura

        # Cota total do desenho (40cm abaixo)
        script.append("_DIMLINEAR")
        # Primeiro ponto no desenho
        script.append(f"{x_inicial},{y_paineis[0]}")
        # Segundo ponto no desenho
        script.append(f"{x_inicial+largura_total},{y_paineis[0]}")
        # Posição da linha de cota
        script.append(f"{x_inicial+largura_total/2},{y_paineis[0]-40}")
        script.append("")
        script.append(";")

        # Adicionar cotas para o último painel (extrema direita)
        if len(larguras_paineis) > 0:
            x_ultimo_painel = x_inicial + sum(larguras_paineis[:-1])
            x_fim_ultimo = x_ultimo_painel + larguras_paineis[-1]
            
            # Cota para altura 1
            script.append("_DIMLINEAR")
            script.append(f"{x_fim_ultimo},{y_paineis[0]}")
            script.append(f"{x_fim_ultimo},{y_paineis[0] + alturas_paineis[0]}")
            script.append(f"{x_fim_ultimo + 20},{y_paineis[0] + alturas_paineis[0]/2}")
            script.append(";")
            
            # Cota para altura 2 (se existir)
            if len(alturas_paineis) > 1:
                script.append("_DIMLINEAR")
                script.append(f"{x_fim_ultimo},{y_paineis[1]}")
                script.append(f"{x_fim_ultimo},{y_paineis[1] + alturas_paineis[1]}")
                script.append(f"{x_fim_ultimo + 20},{y_paineis[1] + alturas_paineis[1]/2}")
                script.append(";")
            
            # Cota para altura 3 (se existir)
            if len(alturas_paineis) > 2:
                script.append("_DIMLINEAR")
                script.append(f"{x_fim_ultimo},{y_paineis[2]}")
                script.append(f"{x_fim_ultimo},{y_paineis[2] + alturas_paineis[2]}")
                script.append(f"{x_fim_ultimo + 20},{y_paineis[2] + alturas_paineis[2]/2}")
                script.append(";")

        # Layer para nomenclatura
        script.append("-LAYER")
        script.append("S NOMENCLATURA")
        script.append("")
        script.append(";")

        # Adicionar texto do nome
        script.append("_TEXT")
        script.append(f"{x_inicial + 5},{y_paineis[0] + sum(alturas_paineis) + 40}")  # 40cm acima do topo
        script.append("16")
        script.append("0")
        script.append(nome)
        script.append(";")

        # Adicionar texto das observações
        script.append("_TEXT")
        script.append(f"{x_inicial + 85},{y_paineis[0] + sum(alturas_paineis) + 40}")  # Alinhado com o nome
        script.append("16")
        script.append("0")
        script.append(observacoes)
        script.append(";")

        # Adicionar textos laterais
        texto_esquerda = texto_esquerda_entry.get()
        texto_direita = texto_direita_entry.get()

        # Alinhar o texto da esquerda com a cota total inferior
        script.append("_TEXT")
        script.append(f"{x_inicial - 5},{y_paineis[0] - 40}")  # Alinhado com a cota total inferior
        script.append("8")
        script.append("90")
        script.append(texto_esquerda)
        script.append(";")

        # Mover o texto da direita 7 cm a mais para a direita e alinhar com a cota total inferior
        script.append("_TEXT")
        script.append(f"{x_inicial + largura_total + 12},{y_paineis[0] - 40}")  # 7 cm a mais para a direita
        script.append("8")
        script.append("90")
        script.append(texto_direita)
        script.append(";")

        # Cota da laje (se existir)
        if altura_laje_valor > 0:
            script.append("_DIMLINEAR")
            script.append(f"{x_fim_ultimo},{y_laje}")
            script.append(f"{x_fim_ultimo},{y_laje + altura_laje_valor}")
            script.append(f"{x_fim_ultimo + 20},{y_laje + altura_laje_valor/2}")
            script.append(";")

        # Cota total vertical (40cm à direita)
        altura_total_desenho = sum(alturas_paineis)
        if altura_laje_valor > 0:
            if posicao_laje_valor == 1:
                altura_total_desenho = alturas_paineis[0] + altura_laje_valor + (sum(alturas_paineis[1:]) if len(alturas_paineis) > 1 else 0)
            elif posicao_laje_valor == 2 and len(alturas_paineis) > 1:
                altura_total_desenho = alturas_paineis[0] + alturas_paineis[1] + altura_laje_valor + (alturas_paineis[2] if len(alturas_paineis) > 2 else 0)

        script.append("_DIMLINEAR")
        script.append(f"{x_fim_ultimo},{y_paineis[0]}")  # Ponto inicial (base)
        script.append(f"{x_fim_ultimo},{y_paineis[0] + altura_total_desenho}")  # Ponto final (topo)
        script.append(f"{x_fim_ultimo + 40},{y_paineis[0] + altura_total_desenho/2}")  # Posição do texto (40cm à direita)
        script.append(";")

        # Salvar os arquivos
        nome_arquivo = f"{nome}_{observacoes}.scr"
        
        # Salvar em 0000ZERO.scr
        script_path = os.path.join(os.path.dirname(__file__), "0000ZERO.scr")
        with open(script_path, "w", encoding='utf-16') as f:
            f.write("\n".join(script))
            
        # Salvar na pasta Testes
        testes_path = os.path.join(os.path.dirname(__file__), "Testes")
        if not os.path.exists(testes_path):
            os.makedirs(testes_path)
            
        teste_script_path = os.path.join(testes_path, nome_arquivo)
        with open(teste_script_path, "w", encoding='utf-16') as f:
            f.write("\n".join(script))
            
        atualizar_status(f"Scripts salvos com sucesso!")
        return True
        
    except Exception as e:
        atualizar_status(f"Erro ao criar script: {str(e)}")
        return False

def iniciar_campos():
    """Preenche automaticamente os campos ao iniciar a aplicação."""
    # Remover inserções duplicadas
    # largura_total_entry.insert(0, "600")
    # altura_total_entry.insert(0, "180")
    # altura_laje_entry.insert(0, "30")
    
    # Preencher larguras dos painéis
    paineis_largura_entries[0].insert(0, "244")
    paineis_largura_entries[1].insert(0, "244")
    paineis_largura_entries[2].insert(0, "112")
    
    # Preencher alturas dos painéis
    paineis_altura_entries[0].insert(0, "122")
    paineis_altura_entries[1].insert(0, "28")
    
    # Preencher grades
    grades_entries[0].insert(0, "100")
    grades_entries[1].insert(0, "100")
    grades_entries[2].insert(0, "100")
    grades_entries[3].insert(0, "100")

root = tk.Tk()
root.title("Gerador de Vigas")

# Frame principal
main_frame = ttk.Frame(root, padding="10")
main_frame.grid(row=0, column=0, sticky="nsew")

# Campos iniciais
ttk.Label(main_frame, text="Nome:").grid(row=0, column=0, sticky="w")
nome_entry = ttk.Entry(main_frame, width=40)
nome_entry.insert(0, "teste")
nome_entry.grid(row=0, column=1, columnspan=2, sticky="we")

ttk.Label(main_frame, text="Observações:").grid(row=1, column=0, sticky="w")
observacoes_entry = ttk.Entry(main_frame, width=40)
observacoes_entry.insert(0, "observacoes")
observacoes_entry.grid(row=1, column=1, columnspan=2, sticky="we")

# Largura total
ttk.Label(main_frame, text="Largura Total:").grid(row=2, column=0, sticky="w")
largura_total_entry = ttk.Entry(main_frame, width=20)
largura_total_entry.insert(0, "600")
largura_total_entry.grid(row=2, column=1, sticky="w")
largura_total_entry.bind('<KeyRelease>', calcular_paineis_largura)

# Painéis largura
ttk.Label(main_frame, text="Largura dos Painéis:").grid(row=3, column=0, sticky="w")
paineis_largura_frame = ttk.Frame(main_frame)
paineis_largura_frame.grid(row=3, column=1, columnspan=2, sticky="w")

paineis_largura_entries = []
paineis_largura_locks = []

for i in range(5):
    # Frame para cada par entrada/lock
    painel_frame = ttk.Frame(paineis_largura_frame)
    painel_frame.grid(row=0, column=i, padx=2)
    
    # Entry
    entry = ttk.Entry(painel_frame, width=8)
    entry.grid(row=0, column=0)
    paineis_largura_entries.append(entry)
    
    # Lock checkbox
    var = tk.BooleanVar()
    cb = ttk.Checkbutton(painel_frame, variable=var)
    cb.grid(row=0, column=1, padx=(0,5))
    paineis_largura_locks.append(var)

# Altura total
ttk.Label(main_frame, text="Altura Total:").grid(row=4, column=0, sticky="w")
altura_total_entry = ttk.Entry(main_frame, width=20)
altura_total_entry.insert(0, "180")
altura_total_entry.grid(row=4, column=1, sticky="w")
altura_total_entry.bind('<KeyRelease>', calcular_paineis_altura)

# Campo da Laje e Marcadores
ttk.Label(main_frame, text="Altura da Laje:").grid(row=4, column=2, sticky="w", padx=(20,0))
altura_laje_entry = ttk.Entry(main_frame, width=10)
altura_laje_entry.insert(0, "30")
altura_laje_entry.grid(row=4, column=3, sticky="w")
altura_laje_entry.bind('<KeyRelease>', calcular_paineis_altura)

# Frame para os marcadores (bolinhas)
marcadores_frame = ttk.Frame(main_frame)
marcadores_frame.grid(row=4, column=4, sticky="w", padx=(10,0))

# Variável para controlar qual marcador está selecionado
posicao_laje = tk.StringVar(value="1")

# Criar os marcadores (radio buttons estilizados como bolinhas)
style = ttk.Style()
style.configure("Round.TRadiobutton", padding=2)
        
for i in range(3):
    rb = ttk.Radiobutton(marcadores_frame, text=str(i+1), value=str(i+1),
                       variable=posicao_laje, style="Round.TRadiobutton")
    rb.pack(side=tk.LEFT, padx=2)

# Painéis altura
ttk.Label(main_frame, text="Altura dos Painéis:").grid(row=5, column=0, sticky="w")
paineis_altura_frame = ttk.Frame(main_frame)
paineis_altura_frame.grid(row=5, column=1, columnspan=2, sticky="w")

paineis_altura_entries = []
paineis_altura_locks = []

for i in range(3):
    # Frame para cada par entrada/lock
    painel_frame = ttk.Frame(paineis_altura_frame)
    painel_frame.grid(row=0, column=i, padx=2)
    
    # Entry
    entry = ttk.Entry(painel_frame, width=8)
    entry.grid(row=0, column=0)
    paineis_altura_entries.append(entry)
    
    # Lock checkbox
    var = tk.BooleanVar()
    cb = ttk.Checkbutton(painel_frame, variable=var)
    cb.grid(row=0, column=1, padx=(0,5))
    paineis_altura_locks.append(var)

# Grades
ttk.Label(main_frame, text="Alturas das Grades:").grid(row=6, column=0, sticky="w")
grades_frame = ttk.Frame(main_frame)
grades_frame.grid(row=6, column=1, columnspan=2, sticky="w")

grades_labels = ['1', '2', '3', '4', '5', '6']
grades_entries = []
grades_locks = []

for i, label in enumerate(grades_labels):
    # Frame para cada conjunto label/entrada/lock
    grade_frame = ttk.Frame(grades_frame)
    grade_frame.grid(row=0, column=i, padx=2)
    
    # Label
    ttk.Label(grade_frame, text=label).grid(row=0, column=0, columnspan=2)
    
    # Entry
    entry = ttk.Entry(grade_frame, width=8)
    entry.grid(row=1, column=0)
    grades_entries.append(entry)
    
    # Lock checkbox
    var = tk.BooleanVar()
    cb = ttk.Checkbutton(grade_frame, variable=var)
    cb.grid(row=1, column=1, padx=(0,5))
    grades_locks.append(var)

# Adicionar o bind para a primeira grade AQUI
grades_entries[0].bind('<KeyRelease>', atualizar_grades)

# Adicionar campos de entrada para os textos laterais na interface
ttk.Label(main_frame, text="Texto Esquerda:").grid(row=8, column=0, sticky="w")
texto_esquerda_entry = ttk.Entry(main_frame, width=20)
texto_esquerda_entry.grid(row=8, column=1, sticky="w")

ttk.Label(main_frame, text="Texto Direita:").grid(row=9, column=0, sticky="w")
texto_direita_entry = ttk.Entry(main_frame, width=20)
texto_direita_entry.grid(row=9, column=1, sticky="w")

# Botão gerar
ttk.Button(main_frame, text="Gerar Script", command=gerar_script).grid(row=7, column=0, columnspan=3, pady=10)

# Iniciar aplicação
iniciar_campos()  # Chamar a função para preencher os campos automaticamente
root.mainloop()
