import tkinter as tk
from tkinter import ttk
import os
import logging
import win32com.client
import time

# Configurar o logger
logging.basicConfig(filename='app.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def atualizar_status(mensagem):
    """Atualiza o status da aplicação com a mensagem fornecida e registra no log."""
    status_label = ttk.Label(main_frame, text=mensagem)
    status_label.grid(row=3, column=0, columnspan=2, sticky="w")
    log_text.insert(tk.END, mensagem + "\n")
    log_text.see(tk.END)
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

def desenhar_sarrafo_horizontal(script, x_inicial, y_inicial, largura_painel):
    """Desenha um sarrafo horizontal de 2.2 de altura dentro de um painel."""
    altura_sarrafo = 2.2
    # Desenhar cada linha do retângulo separadamente
    script.append("_PLINE")
    script.append(f"{x_inicial},{y_inicial}")
    script.append(f"{x_inicial},{y_inicial - altura_sarrafo}")
    script.append("")  # Linha vazia antes do ponto e vírgula
    script.append(";")
    
    script.append("_PLINE")
    script.append(f"{x_inicial},{y_inicial - altura_sarrafo}")
    script.append(f"{x_inicial + largura_painel},{y_inicial - altura_sarrafo}")
    script.append("")  # Linha vazia antes do ponto e vírgula
    script.append(";")
    
    script.append("_PLINE")
    script.append(f"{x_inicial + largura_painel},{y_inicial - altura_sarrafo}")
    script.append(f"{x_inicial + largura_painel},{y_inicial}")
    script.append("")  # Linha vazia antes do ponto e vírgula
    script.append(";")
    
    script.append("_PLINE")
    script.append(f"{x_inicial + largura_painel},{y_inicial}")
    script.append(f"{x_inicial},{y_inicial}")
    script.append("")  # Linha vazia antes do ponto e vírgula
    script.append(";")

def desenhar_sarrafos_verticais_adicionais(script, x_inicial, largura_total, y_paineis, alturas_paineis, posicao_laje_valor):
    """Desenha sarrafos verticais simples adicionais quando há laje entre painéis."""
    try:
        # Ajusta o ponto base dependendo da posição da laje
        if posicao_laje_valor == 2 and len(alturas_paineis) > 2:
            # Se a laje está entre painel 2 e 3, base é o fundo do painel 3
            y_topo = y_paineis[2] + alturas_paineis[2]
            y_base = y_paineis[2]  # Base no fundo do painel 3
        else:
            # Outros casos mantém comportamento original
            y_topo = y_paineis[2] + alturas_paineis[2] if len(alturas_paineis) > 2 else y_paineis[1] + alturas_paineis[1]
            y_base = y_paineis[1]  # Base no fundo do painel 2
        
        # Resto do código permanece igual
        script.append("-LAYER")
        script.append("S SARR_2.2x7")
        script.append("")
        script.append(";")
        
        x_sarrafo = x_inicial + 7
        script.append("_PLINE")
        script.append(f"{x_sarrafo},{y_topo}")
        script.append(f"{x_sarrafo},{y_base}")
        script.append("")
        script.append(";")
        
        x_sarrafo = x_inicial + largura_total - 7
        script.append("_PLINE")
        script.append(f"{x_sarrafo},{y_topo}")
        script.append(f"{x_sarrafo},{y_base}")
        script.append("")
        script.append(";")
        
    except Exception as e:
        atualizar_status(f"Erro ao desenhar sarrafos verticais adicionais: {str(e)}")

def desenhar_grades_retangulares_adicionais(script, x_inicial, largura_total, y_paineis, alturas_paineis, larguras_paineis, posicao_laje_valor):
    """Desenha grades retangulares adicionais quando há laje entre painéis."""
    try:
        # Ajustar pontos base e topo dependendo da posição da laje
        if posicao_laje_valor == 2 and len(alturas_paineis) > 2:
            # Se a laje está entre painel 2 e 3, base é o fundo do painel 3
            y_topo = y_paineis[2] + alturas_paineis[2]
            y_base = y_paineis[2]  # Base no fundo do painel 3
        else:
            # Outros casos mantém comportamento original
            y_topo = y_paineis[2] + alturas_paineis[2] if len(alturas_paineis) > 2 else y_paineis[1] + alturas_paineis[1]
            y_base = y_paineis[1]  # Base no fundo do painel 2
        
        y_topo_grade = y_topo - 2.2  # Sempre 2.2 abaixo do topo
        
        # Layer para grades retangulares
        script.append("-LAYER")
        script.append("S SARR_3.5x7")
        script.append("")
        script.append(";")
        
        # 1. Grade no primeiro painel (15cm da esquerda)
        x_grade = x_inicial + 15
        script.append("_PLINE")
        script.append(f"{x_grade},{y_topo_grade}")
        script.append(f"{x_grade+3.5},{y_topo_grade}")
        script.append(f"{x_grade+3.5},{y_base}")
        script.append(f"{x_grade},{y_base}")
        script.append("C")
        script.append(";")
        
        # 2. Grade no último painel (15cm da direita)
        x_grade = x_inicial + largura_total - 15 - 3.5
        script.append("_PLINE")
        script.append(f"{x_grade},{y_topo_grade}")
        script.append(f"{x_grade+3.5},{y_topo_grade}")
        script.append(f"{x_grade+3.5},{y_base}")
        script.append(f"{x_grade},{y_base}")
        script.append("C")
        script.append(";")
        
        # 3. Grades nas uniões entre painéis
        x_atual = x_inicial
        for i in range(len(larguras_paineis)-1):
            x_uniao = x_atual + larguras_paineis[i]
            
            # Grade à esquerda da união
            x_grade = x_uniao - 3.5
            script.append("_PLINE")
            script.append(f"{x_grade},{y_topo_grade}")
            script.append(f"{x_grade+3.5},{y_topo_grade}")
            script.append(f"{x_grade+3.5},{y_base}")
            script.append(f"{x_grade},{y_base}")
            script.append("C")
            script.append(";")
            
            # Grade à direita da união
            x_grade = x_uniao
            script.append("_PLINE")
            script.append(f"{x_grade},{y_topo_grade}")
            script.append(f"{x_grade+3.5},{y_topo_grade}")
            script.append(f"{x_grade+3.5},{y_base}")
            script.append(f"{x_grade},{y_base}")
            script.append("C")
            script.append(";")
            
            x_atual += larguras_paineis[i]
            
    except Exception as e:
        atualizar_status(f"Erro ao desenhar grades retangulares adicionais: {str(e)}")

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
            
            # Adicionar comandos para painéis de altura 1
            for j, largura in enumerate(larguras_paineis):
                opcao = opcoes_paineis[0][j].get()
                if opcao != "Novo":
                    x_centro = x_inicial + sum(larguras_paineis[:j]) + largura/2
                    y_centro = y_paineis[0] + alturas_paineis[0]/2
                    script.append(";")
                    script.append("HH" if opcao == "REAP s/Corte" else "HHH")
                    script.append(f"{x_centro},{y_centro}")
                    script.append(";")
            
            if len(alturas_paineis) > 1:
                desenhar_paineis_altura_2(script, x_inicial, y_paineis[1], larguras_paineis, alturas_paineis[1], alturas_paineis[0])
                
                # Adicionar comandos para painéis de altura 2
                for j, largura in enumerate(larguras_paineis):
                    opcao = opcoes_paineis[1][j].get()
                    if opcao != "Novo":
                        x_centro = x_inicial + sum(larguras_paineis[:j]) + largura/2
                        y_centro = y_paineis[1] + alturas_paineis[1]/2
                        script.append(";")
                        script.append("HH" if opcao == "REAP s/Corte" else "HHH")
                        script.append(f"{x_centro},{y_centro}")
                        script.append(";")
                
                if len(alturas_paineis) > 2:
                    desenhar_paineis_altura_3(script, x_inicial, y_paineis[2], larguras_paineis, alturas_paineis[2], alturas_paineis[1])
                    
                    # Adicionar comandos para painéis de altura 3
                    for j, largura in enumerate(larguras_paineis):
                        opcao = opcoes_paineis[2][j].get()
                        if opcao != "Novo":
                            x_centro = x_inicial + sum(larguras_paineis[:j]) + largura/2
                            y_centro = y_paineis[2] + alturas_paineis[2]/2
                            script.append(";")
                            script.append("HH" if opcao == "REAP s/Corte" else "HHH")
                            script.append(f"{x_centro},{y_centro}")
                            script.append(";")

        # Layer para sarrafos horizontais
        script.append("-LAYER")
        script.append("S SARR_2.2X7")
        script.append("")
        script.append(";")

        # Desenhar sarrafos horizontais em cada painel de cada altura
        for j, altura in enumerate(alturas_paineis):
            # Verifica se deve desenhar neste nível
            if posicao_laje_valor == 3 or (posicao_laje_valor == 2 and len(alturas_paineis) <= 2) or (posicao_laje_valor == 1 and len(alturas_paineis) == 1):
                # Laje acima - só desenha no painel mais alto
                if j < len(alturas_paineis) - 1:
                    continue
            elif posicao_laje_valor == 2 and len(alturas_paineis) > 2:
                # Laje entre painel 2 e 3 - desenha nos painéis 2 e 3
                if j < 1:  # Pula apenas o painel 1
                    continue
            elif posicao_laje_valor == 1:
                if len(alturas_paineis) > 2:
                    # Se existe painel 3, desenha no painel 3 e no painel 1
                    if j == 1:  # Pula apenas o painel 2
                        continue
                else:
                    # Se não existe painel 3, desenha nos painéis 1 e 2
                    pass  # Não pula nenhum, desenha em todos
            
            x_atual = x_inicial
            for i, largura in enumerate(larguras_paineis):
                if i == 0:
                    # Primeiro painel, começa 15 cm à direita
                    desenhar_sarrafo_horizontal(script, x_atual + 15, y_paineis[j] + altura, largura - 15)
                elif i == len(larguras_paineis) - 1:
                    # Último painel, termina 15 cm à esquerda
                    desenhar_sarrafo_horizontal(script, x_atual, y_paineis[j] + altura, largura - 15)
                else:
                    # Painéis intermediários
                    desenhar_sarrafo_horizontal(script, x_atual, y_paineis[j] + altura, largura)
                x_atual += largura

        # Verificar se precisa desenhar os elementos adicionais
        if altura_laje_valor > 0 and posicao_laje_valor in [1, 2]:
            if posicao_laje_valor == 1 and len(alturas_paineis) > 1:
                desenhar_sarrafos_verticais_adicionais(script, x_inicial, largura_total, y_paineis, 
                                                     alturas_paineis, posicao_laje_valor)
                desenhar_grades_retangulares_adicionais(script, x_inicial, largura_total, y_paineis, 
                                                      alturas_paineis, larguras_paineis, posicao_laje_valor)
            elif posicao_laje_valor == 2 and len(alturas_paineis) > 2:
                desenhar_sarrafos_verticais_adicionais(script, x_inicial, largura_total, y_paineis, 
                                                     alturas_paineis, posicao_laje_valor)
                desenhar_grades_retangulares_adicionais(script, x_inicial, largura_total, y_paineis, 
                                                      alturas_paineis, larguras_paineis, posicao_laje_valor)

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

        # Obter valores dos campos do pilar
        distancia_pilar = distancia_pilar_entry.get().strip()
        recorte_pilar = recorte_pilar_entry.get().strip()

        if distancia_pilar and recorte_pilar:
            try:
                distancia_pilar = float(distancia_pilar)
                recorte_pilar = float(recorte_pilar)

                if distancia_pilar >= 0 and recorte_pilar > 0:
                    # Calcular coordenadas do retângulo
                    x_retangulo_1 = x_inicial + distancia_pilar
                    y_retangulo_1 = y_paineis[-1] + alturas_paineis[-1]  # Topo do painel mais alto
                    
                    x_retangulo_2 = x_retangulo_1 + recorte_pilar
                    y_retangulo_2 = y_paineis[0]  # Fundo do primeiro painel
                    
                    # Adicionar comandos para desenhar o retângulo com appv
                    script.append(";")
                    script.append("_ZOOM")
                    script.append("W")
                    script.append(f"{x_retangulo_1-10},{y_retangulo_1+10}")  # Canto superior esquerdo
                    script.append(f"{x_retangulo_2+10},{y_retangulo_2-10}")  # Canto inferior direito
                    script.append(";")
                    script.append("appv")
                    script.append(f"{x_retangulo_1},{y_retangulo_1}")
                    script.append(f"{x_retangulo_2},{y_retangulo_2}")
                    script.append(";")

                    # Adicionar comandos para desenhar o retângulo com apv2
                    script.append(";")
                    script.append("_ZOOM")
                    script.append("W")
                    script.append(f"{x_retangulo_1-10},{y_retangulo_1+10}")  # Canto superior esquerdo
                    script.append(f"{x_retangulo_2+10},{y_retangulo_2-10}")  # Canto inferior direito
                    script.append(";")
                    script.append("apv2")
                    script.append(f"{x_retangulo_1},{y_retangulo_1}")
                    script.append(f"{x_retangulo_2},{y_retangulo_2}")
                    script.append(";")

                    # Posicionar a cota do fundo da abertura do pilar abaixo do fundo dos painéis de altura 1
                    y_cota_fundo = y_paineis[0]  # Alinhado com o fundo dos painéis de altura 1
                    script.append("_DIMLINEAR")
                    script.append(f"{x_retangulo_1},{y_cota_fundo}")
                    script.append(f"{x_retangulo_1 + recorte_pilar},{y_cota_fundo}")
                    script.append(f"{x_retangulo_1 + recorte_pilar/2},{y_cota_fundo - 20}")
                    script.append("")
                    script.append(";")

            except ValueError:
                pass  # Ignorar se os valores não forem numéricos válidos

        # Obter valores dos campos de abertura da viga
        abertura_viga_largura = abertura_viga_largura_entry.get().strip()
        abertura_viga_altura = abertura_viga_altura_entry.get().strip()

        # Verificar qual parede/união está selecionada
        parede_uniao_selecionada_valor = parede_uniao_selecionada.get()

        if parede_uniao_selecionada_valor and abertura_viga_largura and abertura_viga_altura:
            try:
                abertura_viga_largura = float(abertura_viga_largura)
                abertura_viga_altura = float(abertura_viga_altura)

                if abertura_viga_largura > 0 and abertura_viga_altura > 0:
                    # Calcular coordenadas do retângulo com base na parede/união selecionada
                    parede_uniao_selecionada_index = int(parede_uniao_selecionada_valor)
                    if parede_uniao_selecionada_index == 0:
                        x_retangulo = x_inicial
                    else:
                        x_retangulo = x_inicial + sum(larguras_paineis[:parede_uniao_selecionada_index])

                    y_retangulo = y_paineis[-1] + alturas_paineis[-1]  # Topo do painel mais alto

                    # Somar 15.5 à largura da abertura da viga
                    abertura_viga_largura += 15.5

                    # Somar 12.2 à altura da abertura da viga e subtrair a altura da laje
                    abertura_viga_altura += 2.2
                    abertura_viga_altura -= float(altura_laje_entry.get() or 0)

                    # Adicionar comando de zoom antes de desenhar a abertura da viga
                    script.append("_ZOOM")
                    script.append("W")
                    script.append(f"{x_retangulo - 10},{y_retangulo + 10}")  # Canto superior esquerdo
                    script.append(f"{x_retangulo + abertura_viga_largura + 10},{y_retangulo - abertura_viga_altura - 10}")  # Canto inferior direito
                    script.append(";")

                    # Definir layer para as cotas (apenas uma vez)
                    script.append("-LAYER")
                    script.append("S COTA")
                    script.append("")
                    script.append(";")

                    # Adicionar cota da largura da abertura da viga (à direita)
                    script.append("_DIMLINEAR")
                    script.append(f"{x_retangulo + abertura_viga_largura},{y_retangulo + float(altura_laje_entry.get() or 0)}")
                    script.append(f"{x_retangulo + abertura_viga_largura},{y_retangulo - abertura_viga_altura + 2.2}")
                    script.append(f"{x_retangulo + abertura_viga_largura + 20},{y_retangulo - abertura_viga_altura/2 + float(altura_laje_entry.get() or 0)/2}")
                    script.append("")
                    script.append(";")

                    # Adicionar cota da altura da abertura da viga (abaixo)
                    script.append("_DIMLINEAR")
                    script.append(f"{x_retangulo},{y_retangulo - abertura_viga_altura}")
                    script.append(f"{x_retangulo + abertura_viga_largura - 15.5},{y_retangulo - abertura_viga_altura}")
                    script.append(f"{x_retangulo + (abertura_viga_largura - 15.5)/2},{y_retangulo - abertura_viga_altura - 20}")
                    script.append("")
                    script.append(";")

                    # Redefinir layer para "0" antes de desenhar a abertura da viga
                    script.append("-LAYER")
                    script.append("S 0")
                    script.append("")
                    script.append(";")

                    # Adicionar comandos para desenhar o retângulo da abertura da viga
                    script.append("avvsl")
                    script.append(f"{x_retangulo},{y_retangulo}")
                    script.append(f"{x_retangulo + abertura_viga_largura},{y_retangulo - abertura_viga_altura}")
                    script.append(";")

            except ValueError:
                pass  # Ignorar se os valores não forem numéricos válidos

        # Adicionar zoom de distanciamento de 150 ao final do script
        script.append("_ZOOM")
        script.append("0.01")
        script.append(";")

        return script

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

def conectar_autocad():
    try:
        atualizar_status("Tentando conectar ao AutoCAD...")
        acad = win32com.client.Dispatch("AutoCAD.Application")
        atualizar_status("Conexão com o AutoCAD estabelecida.")
        
        arquivo_dwg = r"C:\Users\rvene\Desktop\PROJETOS\AUTOMACAO\ROBO_MANUAL\Vigas\MODELO CAD\ROBO- PARADES DE VIGA.dwg"
        
        # Verificar se o arquivo já está aberto
        doc = None
        for i in range(acad.Documents.Count):
            document = acad.Documents.Item(i)
            if document.FullName.lower() == arquivo_dwg.lower():
                doc = document
                break
        
        if doc is None:
            atualizar_status(f"Abrindo o arquivo: {arquivo_dwg}")
            doc = acad.Documents.Open(arquivo_dwg)
            atualizar_status("Arquivo aberto com sucesso.")
            atualizar_status("Aguardando 15 segundos para o arquivo abrir completamente...")
            time.sleep(15)
            atualizar_status("Tempo de espera concluído.")
        else:
            atualizar_status("O arquivo já está aberto.")
        
        # Selecionar a janela específica do arquivo
        acad.ActiveDocument = doc
        atualizar_status("Janela do arquivo selecionada.")
        
        atualizar_status("AutoCAD conectado com sucesso.")
        return acad, doc
    except Exception as e:
        atualizar_status(f"Erro ao conectar ao AutoCAD: {str(e)}")
        return None, None

def executar_comandos():
    atualizar_status("Iniciando a execução dos comandos no AutoCAD...")
    acad, doc = conectar_autocad()
    if acad is None or doc is None:
        atualizar_status("Não foi possível conectar ao AutoCAD. A execução dos comandos será interrompida.")
        return

    try:
        atualizar_status("Executando comandos no AutoCAD...")
        
        atualizar_status("Apagando todos os objetos...")
        comando_erase = "ERASE\nALL\n\n"
        doc.SendCommand(comando_erase)
        atualizar_status("Objetos apagados.")
        
        atualizar_status("Executando o comando TV...")
        comando_tv = "TV\n"
        doc.SendCommand(comando_tv)
        atualizar_status("Comando TV executado.")

        atualizar_status("Comandos executados no AutoCAD com sucesso.")
    except Exception as e:
        atualizar_status(f"Erro ao executar comandos no AutoCAD: {str(e)}")

def salvar_teste():
    try:
        validar_todos_campos()
        validar_dimensoes()
        script = criar_script()
        
        # Salvar em 0000ZERO.scr
        script_path = os.path.join(os.path.dirname(__file__), "0000ZERO.scr")
        with open(script_path, "w", encoding='utf-16') as f:
            f.write("\n".join(script))
        
        atualizar_status("Teste salvo com sucesso em 0000ZERO.scr!")
    except Exception as e:
        atualizar_status(f"Erro ao salvar teste: {str(e)}")
        logging.error(f"Erro ao salvar teste: {str(e)}")  # Registrar erro no log
        return False
    return True

def salvar_script():
    try:
        validar_todos_campos()
        validar_dimensoes()
        script = criar_script()
        
        nome = nome_entry.get()
        observacoes = observacoes_entry.get()
        nome_arquivo = f"{nome}_{observacoes}.scr"
        
        # Salvar na pasta Testes
        testes_path = os.path.join(os.path.dirname(__file__), "Testes")
        if not os.path.exists(testes_path):
            os.makedirs(testes_path)
        
        script_path = os.path.join(testes_path, nome_arquivo)
        with open(script_path, "w", encoding='utf-16') as f:
            f.write("\n".join(script))
        
        atualizar_status(f"Script salvo com sucesso: {nome_arquivo}")
    except Exception as e:
        atualizar_status(f"Erro ao salvar script: {str(e)}")
        logging.error(f"Erro ao salvar script: {str(e)}")  # Registrar erro no log
        return False
    return True

root = tk.Tk()
root.title("Gerador de Vigas")

# Frame principal
main_frame = ttk.Frame(root, padding="10")
main_frame.grid(row=0, column=0, sticky="nsew")

# Frame para campos à esquerda
left_frame = ttk.Frame(main_frame)
left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

# Frame para campos à direita
right_frame = ttk.Frame(main_frame)
right_frame.grid(row=0, column=1, sticky="nsew")

# Campos iniciais
ttk.Label(left_frame, text="Nome:").grid(row=0, column=0, sticky="w")
nome_entry = ttk.Entry(left_frame, width=40)
nome_entry.insert(0, "teste")
nome_entry.grid(row=0, column=1, columnspan=3, sticky="we")

ttk.Label(left_frame, text="Observações:").grid(row=1, column=0, sticky="w")
observacoes_entry = ttk.Entry(left_frame, width=40)
observacoes_entry.insert(0, "observacoes")
observacoes_entry.grid(row=1, column=1, columnspan=3, sticky="we")

# Frame para laje
laje_frame = ttk.LabelFrame(left_frame, text="Laje", padding="10")
laje_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=10)

# Campo da Laje
ttk.Label(laje_frame, text="Altura da Laje:").grid(row=0, column=0, sticky="w")
altura_laje_entry = ttk.Entry(laje_frame, width=10)
altura_laje_entry.insert(0, "30")
altura_laje_entry.grid(row=0, column=1, sticky="w")
altura_laje_entry.bind('<KeyRelease>', calcular_paineis_altura)

# Marcadores (bolinhas)
ttk.Label(laje_frame, text="Posição da Laje:").grid(row=0, column=2, sticky="w", padx=(20,0))
marcadores_frame = ttk.Frame(laje_frame)
marcadores_frame.grid(row=0, column=3, sticky="w")

posicao_laje = tk.StringVar(value="1")

style = ttk.Style()
style.configure("Round.TRadiobutton", padding=2)
        
for i in range(3):
    rb = ttk.Radiobutton(marcadores_frame, text=str(i+1), value=str(i+1),
                       variable=posicao_laje, style="Round.TRadiobutton")
    rb.pack(side=tk.LEFT, padx=2)

# Frame para dimensões
dimensoes_frame = ttk.LabelFrame(left_frame, text="Dimensões", padding="10")
dimensoes_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", pady=10)

# Largura total
ttk.Label(dimensoes_frame, text="Largura Total:").grid(row=0, column=0, sticky="w")
largura_total_entry = ttk.Entry(dimensoes_frame, width=10)
largura_total_entry.insert(0, "600")
largura_total_entry.grid(row=0, column=1, sticky="w")
largura_total_entry.bind('<KeyRelease>', calcular_paineis_largura)

# Altura total
ttk.Label(dimensoes_frame, text="Altura Total:").grid(row=0, column=2, sticky="w", padx=(20,0))
altura_total_entry = ttk.Entry(dimensoes_frame, width=10)
altura_total_entry.insert(0, "180")
altura_total_entry.grid(row=0, column=3, sticky="w")
altura_total_entry.bind('<KeyRelease>', calcular_paineis_altura)

# Frame para painéis
paineis_frame = ttk.LabelFrame(left_frame, text="Painéis", padding="10")
paineis_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", pady=10)

# Painéis largura
ttk.Label(paineis_frame, text="Largura dos Painéis:").grid(row=0, column=0, sticky="w")
paineis_largura_frame = ttk.Frame(paineis_frame)
paineis_largura_frame.grid(row=0, column=1, columnspan=3, sticky="w")

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

# Painéis altura
ttk.Label(paineis_frame, text="Altura dos Painéis:").grid(row=1, column=0, sticky="w")
paineis_altura_frame = ttk.Frame(paineis_frame)
paineis_altura_frame.grid(row=1, column=1, columnspan=3, sticky="w")

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

# Frame para grades
grades_frame = ttk.LabelFrame(left_frame, text="Grades", padding="10")
grades_frame.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=10)

ttk.Label(grades_frame, text="Alturas das Grades:").grid(row=0, column=0, sticky="w")
grades_entries_frame = ttk.Frame(grades_frame)
grades_entries_frame.grid(row=0, column=1, columnspan=3, sticky="w")

grades_labels = ['1', '2', '3', '4', '5', '6']
grades_entries = []
grades_locks = []

for i, label in enumerate(grades_labels):
    # Frame para cada conjunto label/entrada/lock
    grade_frame = ttk.Frame(grades_entries_frame)
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

grades_entries[0].bind('<KeyRelease>', atualizar_grades)

# Frame para textos laterais
textos_frame = ttk.LabelFrame(left_frame, text="Textos Laterais", padding="10")
textos_frame.grid(row=6, column=0, columnspan=4, sticky="nsew", pady=10)

ttk.Label(textos_frame, text="Texto Esquerda:").grid(row=0, column=0, sticky="w")
texto_esquerda_entry = ttk.Entry(textos_frame, width=20)
texto_esquerda_entry.grid(row=0, column=1, sticky="w")

ttk.Label(textos_frame, text="Texto Direita:").grid(row=0, column=2, sticky="w", padx=(20,0))
texto_direita_entry = ttk.Entry(textos_frame, width=20)
texto_direita_entry.grid(row=0, column=3, sticky="w")

# Frame para pilar
pilar_frame = ttk.LabelFrame(right_frame, text="Pilar", padding="10")
pilar_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=10)

ttk.Label(pilar_frame, text="Distância do Pilar Esquerda:").grid(row=0, column=0, sticky="w")
distancia_pilar_entry = ttk.Entry(pilar_frame, width=10)
distancia_pilar_entry.grid(row=0, column=1, sticky="w")

ttk.Label(pilar_frame, text="Recorte Pilar largura:").grid(row=0, column=2, sticky="w", padx=(20,0))
recorte_pilar_entry = ttk.Entry(pilar_frame, width=10)
recorte_pilar_entry.grid(row=0, column=3, sticky="w")

# Frame para abertura da viga
abertura_frame = ttk.LabelFrame(right_frame, text="Abertura da Viga", padding="10")
abertura_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=10)

ttk.Label(abertura_frame, text="Largura:").grid(row=0, column=0, sticky="w")
abertura_viga_largura_entry = ttk.Entry(abertura_frame, width=10)
abertura_viga_largura_entry.grid(row=0, column=1, sticky="w")

ttk.Label(abertura_frame, text="Altura:").grid(row=0, column=2, sticky="w", padx=(20,0))
abertura_viga_altura_entry = ttk.Entry(abertura_frame, width=10)
abertura_viga_altura_entry.grid(row=0, column=3, sticky="w")

ttk.Label(abertura_frame, text="Selecione a Parede/União:").grid(row=1, column=0, sticky="w")
parede_uniao_frame = ttk.Frame(abertura_frame)
parede_uniao_frame.grid(row=1, column=1, columnspan=3, sticky="w")

parede_uniao_vars = []
parede_uniao_labels = [
    "Parede Esquerda Painel 1",
    "União Painel 1 e 2",
    "União Painel 2 e 3",
    "União Painel 3 e 4",
    "União Painel 4 e 5"
]

parede_uniao_selecionada = tk.StringVar()

for i in range(5):
    rb = ttk.Radiobutton(parede_uniao_frame, text=parede_uniao_labels[i], variable=parede_uniao_selecionada, value=str(i))
    rb.grid(row=i, column=0, sticky="w")
    parede_uniao_vars.append(rb)

# Frame para opções dos painéis
opcoes_frame = ttk.LabelFrame(right_frame, text="Opções dos Painéis", padding="10")
opcoes_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=10)

ttk.Label(opcoes_frame, text="Altura 1:").grid(row=0, column=0, sticky="w")
ttk.Label(opcoes_frame, text="Altura 2:").grid(row=1, column=0, sticky="w")
ttk.Label(opcoes_frame, text="Altura 3:").grid(row=2, column=0, sticky="w")

opcoes_paineis = []

for i in range(3):  # Alturas
    opcoes_linha = []
    for j in range(5):  # Larguras
        var = tk.StringVar(value="Novo")
        opcoes = ttk.Combobox(opcoes_frame, textvariable=var, values=["Novo", "REAP s/Corte", "REAP c/Corte"], state="readonly", width=12)
        opcoes.grid(row=i, column=j+1, padx=5, pady=5)
        opcoes_linha.append(var)
    opcoes_paineis.append(opcoes_linha)

# Botões Salvar Script e Salvar Teste
ttk.Button(main_frame, text="Salvar Script", command=salvar_script).grid(row=1, column=0, pady=10)
ttk.Button(main_frame, text="Salvar Teste", command=salvar_teste).grid(row=1, column=1, pady=10)

# Botões Conectar AutoCAD e Executar Comandos
ttk.Button(main_frame, text="Conectar AutoCAD", command=conectar_autocad).grid(row=2, column=0, pady=10)
ttk.Button(main_frame, text="Executar Comandos", command=executar_comandos).grid(row=2, column=1, pady=10)

# Frame para log
log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
log_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=10)

log_text = tk.Text(log_frame, wrap=tk.WORD, height=10)
log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

log_text.configure(yscrollcommand=log_scrollbar.set)

def copiar_log():
    log_content = log_text.get("1.0", tk.END)
    root.clipboard_clear()
    root.clipboard_append(log_content)

copy_button = ttk.Button(log_frame, text="Copiar Log", command=copiar_log)
copy_button.pack(side=tk.BOTTOM, pady=(10, 0))

# Iniciar aplicação
iniciar_campos()  # Chamar a função para preencher os campos automaticamente
root.mainloop()
