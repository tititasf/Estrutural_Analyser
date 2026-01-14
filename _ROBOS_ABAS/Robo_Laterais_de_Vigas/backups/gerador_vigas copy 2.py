import tkinter as tk
from tkinter import ttk
import os

def calcular_paineis_largura(*args):
    try:
        largura_total = int(largura_total_entry.get())
        altura_total = int(altura_total_entry.get())

        larguras_paineis = [0] * 5  # Inicializa uma lista para 5 painéis

        if largura_total <= 244:
            larguras_paineis[0] = largura_total  # Todo o comprimento para o Painel 1
        elif 245 <= largura_total <= 305:
            larguras_paineis[0] = 122  # Painel 1 recebe 122 cm
            larguras_paineis[1] = int(largura_total - 122 - 22)  # Painel 2 recebe o restante
        else:
            larguras_paineis[0] = 244  # Painel 1 recebe 244 cm
            if largura_total > 366:
                larguras_paineis[1] = 244  # Painel 2 recebe 244 cm
                if largura_total > 549:
                    larguras_paineis[2] = int(largura_total - 244 - 244 - 22)  # Painel 3 recebe o restante
                if largura_total > 793:
                    larguras_paineis[3] = int(largura_total - 244 - 244 - 244 - 22)  # Painel 4 recebe o restante
                if largura_total > 1037:
                    larguras_paineis[4] = int(largura_total - 244 - 244 - 244 - 244 - 22)  # Painel 5 recebe o restante

        # Garantia de comprimento mínimo
        for i in range(1, len(larguras_paineis)):
            if larguras_paineis[i] < 60:
                excess = 60 - larguras_paineis[i]
                larguras_paineis[i] += excess
                larguras_paineis[i - 1] -= excess

        # Limpar campos existentes
        for entry in paineis_largura_entries:
            entry.delete(0, tk.END)

        # Preencher campos com larguras calculadas
        for i, largura in enumerate(larguras_paineis):
            if i < len(paineis_largura_entries):
                paineis_largura_entries[i].insert(0, str(int(largura)))  

        # Cálculo das alturas
        alturas_paineis = []
        altura_restante = altura_total  # Altura disponível

        while altura_restante > 0 and len(alturas_paineis) < 3:
            if altura_restante >= 122:
                alturas_paineis.append(122)  # Adiciona painel de 122 cm
                altura_restante -= 122
            else:
                alturas_paineis.append(int(altura_restante))  # Último painel pode ser menor
                altura_restante = 0  # Completa a altura

        # Limpar campos existentes
        for entry in paineis_altura_entries:
            entry.delete(0, tk.END)

        # Preencher campos com alturas calculadas
        for i, altura in enumerate(alturas_paineis):
            if i < len(paineis_altura_entries):
                paineis_altura_entries[i].insert(0, str(int(altura)))  

    except ValueError:
        pass

def calcular_paineis_altura(*args):
    try:
        # Obter altura total e altura da laje
        altura_total = int(altura_total_entry.get())
        altura_laje = int(altura_laje_entry.get() or 0)
        
        # Altura disponível para interface = altura total - altura laje
        altura_interface = altura_total - altura_laje
        
        alturas_paineis = []
        altura_restante = altura_interface  # Altura disponível para interface

        while altura_restante > 0 and len(alturas_paineis) < 3:
            if altura_restante >= 122:
                alturas_paineis.append(122)  # Adiciona painel de 122 cm
                altura_restante -= 122
            else:
                alturas_paineis.append(int(altura_restante))  # Último painel pode ser menor
                altura_restante = 0  # Completa a altura

        # Limpar campos existentes
        for entry in paineis_altura_entries:
            entry.delete(0, tk.END)

        # Preencher campos com alturas calculadas
        for i, altura in enumerate(alturas_paineis):
            if i < len(paineis_altura_entries):
                paineis_altura_entries[i].insert(0, str(int(altura)))  

    except ValueError:
        pass  # Ignorar erros de conversão

def atualizar_grades(*args):
    try:
        valor = int(grades_entries[0].get())
        if valor:
            # Pegar número de painéis preenchidos
            num_paineis = sum(1 for entry in paineis_largura_entries if entry.get())
            # Preencher grades existentes (número de painéis + 1)
            for i in range(1, num_paineis + 1):
                if i < len(grades_entries):
                    grades_entries[i].delete(0, tk.END)
                    grades_entries[i].insert(0, valor)
    except ValueError:
        pass

def desenhar_paineis_altura_1(script, x_inicial, y_inicial, larguras_paineis, altura_painel):
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

def desenhar_paineis_altura_2(script, x_inicial, y_inicial, larguras_paineis, altura_painel, altura_painel_1):
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

def gerar_script():
    try:
        script = []
        x_inicial = 0
        y_inicial = 0

        # Obter valores dos campos
        nome = nome_entry.get()
        observacoes = observacoes_entry.get()
        altura_laje_valor = float(altura_laje_entry.get() or 0)
        posicao_laje_valor = int(posicao_laje.get())

        # Obter larguras dos painéis
        larguras_paineis = []
        for entry in paineis_largura_entries:
            valor = entry.get().strip()
            if valor:
                larguras_paineis.append(float(valor))

        # Calcular largura total
        largura_total = sum(larguras_paineis)

        # Obter alturas dos painéis
        alturas_paineis = []
        for entry in paineis_altura_entries:
            valor = entry.get().strip()
            if valor:
                alturas_paineis.append(float(valor))

        # Calcular posições Y dos painéis considerando a laje
        y_paineis = []
        y_atual = y_inicial
        
        for i in range(len(alturas_paineis)):
            if i == 0:  # Primeiro painel sempre começa do y_inicial
                y_paineis.append(y_atual)
                y_atual += alturas_paineis[0]
            else:
                # Se a laje está entre os painéis atuais
                if (posicao_laje_valor == 1 and i == 1):  # Entre altura 1 e 2
                    # Posiciona o painel 2 encostado na parte superior da laje
                    y_laje_temp = y_paineis[0] + alturas_paineis[0]  # Posição da laje após altura 1
                    y_paineis.append(y_laje_temp + altura_laje_valor)  # Posição do painel 2 logo após a laje
                    y_atual = y_paineis[-1] + alturas_paineis[i]
                elif (posicao_laje_valor == 2 and i == 2):  # Entre altura 2 e 3
                    # Posiciona o painel 3 encostado na parte superior da laje
                    y_laje_temp = y_paineis[1] + alturas_paineis[1]  # Posição da laje após altura 2
                    y_paineis.append(y_laje_temp + altura_laje_valor)  # Posição do painel 3 logo após a laje
                    y_atual = y_paineis[-1] + alturas_paineis[i]
                else:
                    y_paineis.append(y_atual)
                    y_atual += alturas_paineis[i]

        # Calcular posição Y da laje
        y_laje = y_inicial
        if posicao_laje_valor == 1:
            if len(alturas_paineis) > 0:
                y_laje += alturas_paineis[0]
        elif posicao_laje_valor == 2:
            if len(alturas_paineis) > 1:
                y_laje += alturas_paineis[0] + alturas_paineis[1]
        elif posicao_laje_valor == 3:
            if len(alturas_paineis) > 2:
                y_laje += sum(alturas_paineis)

        # Desenhar a laje
        if altura_laje_valor > 0:
            # Layer para laje
            script.append("-LAYER")
            script.append("S COTA")
            script.append("")
            script.append(";")

            # Desenhar retângulo da laje
            script.append("_PLINE")
            script.append(f"{x_inicial},{y_laje}")  # Ponto inicial
            script.append(f"{x_inicial+largura_total},{y_laje}")  # Direita
            script.append(f"{x_inicial+largura_total},{y_laje+altura_laje_valor}")  # Topo direita
            script.append(f"{x_inicial},{y_laje+altura_laje_valor}")  # Topo esquerda
            script.append("C")  # Fechar o retângulo
            script.append(";")

            # Aplicar hatch
            script.append("HHHH")
            # Calcular centro da laje
            x_centro = x_inicial + (largura_total / 2)
            y_centro = y_laje + (altura_laje_valor / 2)
            script.append(f"{x_centro},{y_centro}")
            script.append(";")

        # Continuar com o resto do código...

        # Zoom inicial
        script.append(f"_ZOOM")
        script.append(f"C {x_inicial+largura_total/2},{y_inicial+max(alturas_paineis)/2} 100")
        script.append(";")
        
        # Layer Painéis
        script.append("-LAYER")
        script.append("S Painéis")
        script.append("")
        script.append(";")

        # Ajustar a lógica de cálculo de altura dos painéis
        # Calcular a altura dos painéis
        altura_paineis = []
        if len(alturas_paineis) > 1:
            altura_paineis.append(alturas_paineis[0])  # Altura do primeiro painel
            altura_paineis.append(alturas_paineis[1])  # Altura do segundo painel
        else:
            altura_paineis.append(max(alturas_paineis))  # Definir uma altura padrão se não houver painéis

        # Desenhar os painéis de altura 1
        altura_painel_1 = altura_paineis[0]  # Altura do primeiro painel
        # Desenhar os painéis de altura 1
        if len(larguras_paineis) > 0:
            desenhar_paineis_altura_1(script, x_inicial, y_paineis[0], larguras_paineis, altura_painel_1)

        # Desenhar os painéis de altura 2
        if len(alturas_paineis) > 1:
            altura_painel_2 = alturas_paineis[1]  # Usar a altura do segundo painel se existir
            desenhar_paineis_altura_2(script, x_inicial, y_paineis[1], larguras_paineis, altura_painel_2, altura_painel_1)

        # Calculando a altura máxima dos painéis
        altura_maxima = altura_painel_1
        if len(alturas_paineis) > 1:
            altura_maxima = altura_painel_1 + alturas_paineis[1]
        if len(alturas_paineis) > 2:
            altura_maxima = altura_painel_1 + alturas_paineis[1] + alturas_paineis[2]

        # Layer para sarrafos retangulares verticais
        script.append("-LAYER")
        script.append("S SARR_3.5x7")
        script.append("")
        script.append(";")

        if len(larguras_paineis) > 0:
            y_topo = y_paineis[0] + altura_maxima

            # 1. Sarrafo retangular no primeiro painel (15cm da esquerda)
            x_grade = x_inicial + 15
            script.append("_PLINE")
            script.append(f"{x_grade},{y_topo-2.2}")  # Começa 2.2cm abaixo do topo
            script.append(f"{x_grade+3.5},{y_topo-2.2}")
            script.append(f"{x_grade+3.5},{y_topo-2.2-alturas_grades[0]}")  # Desce conforme altura definida
            script.append(f"{x_grade},{y_topo-2.2-alturas_grades[0]}")
            script.append("C")
            script.append(";")

            # 2. Sarrafo retangular no último painel (15cm da parede direita)
            x_grade = x_inicial + largura_total - 15 - 3.5  # Subtraindo 3.5 para que o sarrafo termine a 15cm da parede
            script.append("_PLINE")
            script.append(f"{x_grade},{y_topo-2.2}")
            script.append(f"{x_grade+3.5},{y_topo-2.2}")
            script.append(f"{x_grade+3.5},{y_topo-2.2-alturas_grades[-1]}")
            script.append(f"{x_grade},{y_topo-2.2-alturas_grades[-1]}")
            script.append("C")
            script.append(";")

            # 3. Sarrafos retangulares nas uniões entre painéis (encostados)
            for i in range(len(larguras_paineis)-1):
                x_uniao = x_inicial + sum(larguras_paineis[:i+1])
                
                # Sarrafo à direita do painel da esquerda (encostado na união)
                x_grade = x_uniao - 3.5  # Termina exatamente na união
                script.append("_PLINE")
                script.append(f"{x_grade},{y_topo-2.2}")
                script.append(f"{x_grade+3.5},{y_topo-2.2}")
                script.append(f"{x_grade+3.5},{y_topo-2.2-alturas_grades[i+1]}")
                script.append(f"{x_grade},{y_topo-2.2-alturas_grades[i+1]}")
                script.append("C")
                script.append(";")
                
                # Sarrafo à esquerda do painel da direita (encostado na união)
                x_grade = x_uniao  # Começa exatamente na união
                script.append("_PLINE")
                script.append(f"{x_grade},{y_topo-2.2}")
                script.append(f"{x_grade+3.5},{y_topo-2.2}")
                script.append(f"{x_grade+3.5},{y_topo-2.2-alturas_grades[i+1]}")
                script.append(f"{x_grade},{y_topo-2.2-alturas_grades[i+1]}")
                script.append("C")
                script.append(";")

        # Layer para sarrafos verticais simples
        script.append("-LAYER")
        script.append("S SARR_2.2x7")
        script.append("")
        script.append(";")

        # Desenhar sarrafos verticais simples
        if len(larguras_paineis) > 0:
            # Sarrafo na primeira parede (7cm da esquerda)
            x_sarrafo = x_inicial + 7
            script.append("_PLINE")
            script.append(f"{x_sarrafo},{y_paineis[0]}")  # Começa na base
            script.append(f"{x_sarrafo},{y_paineis[0] + altura_maxima}")  # Vai até o topo
            script.append("")
            script.append(";")

            # Sarrafo na última parede (7cm da direita)
            x_sarrafo = x_inicial + largura_total - 7
            script.append("_PLINE")
            script.append(f"{x_sarrafo},{y_paineis[0]}")  # Começa na base
            script.append(f"{x_sarrafo},{y_paineis[0] + altura_maxima}")  # Vai até o topo
            script.append("")
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
            script.append(f"{x_fim_ultimo},{y_paineis[0] + altura_painel_1}")
            script.append(f"{x_fim_ultimo + 20},{y_paineis[0] + altura_painel_1/2}")
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

        # Definir layer para o texto
        script.append("-LAYER")
        script.append("S NOMENCLATURA")
        script.append("")
        script.append(";")

        # Adicionar texto
        script.append("_TEXT")
        script.append(f"{x_inicial + 5},{y_paineis[0] + altura_maxima + 40}")  # Alinhado 5 cm acima
        script.append("16")
        script.append("0")
        script.append(nome)
        script.append(";")

        # Adicionar texto
        script.append("_TEXT")
        script.append(f"{x_inicial + 85},{y_paineis[0] + altura_maxima + 40}")  # Alinhado 5 cm acima
        script.append("16")
        script.append("0")
        script.append(observacoes)
        script.append(";")

        # Juntar script
        script_final = "\n".join(script)

        # Criar nome do arquivo
        nome_arquivo = f"{nome}_{observacoes}.scr" if observacoes else f"{nome}.scr"
        caminho_arquivo = os.path.join("C:\\Users\\rvene\\Desktop\\PROJETOS\\AUTOMACAO\\ROBO_MANUAL\\Vigas\\A_B\\Testes", nome_arquivo)
        
        # Salvar arquivo em UTF-16
        try:
            with open(caminho_arquivo, 'w', encoding='utf-16') as f:
                f.write(script_final)
        except FileNotFoundError:
            # Criar o diretório se não existir
            os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
            with open(caminho_arquivo, 'w', encoding='utf-16') as f:
                f.write(script_final)
            
        # Atualizar arquivo 0000ZERO.scr
        caminho_zero = "C:\\Users\\rvene\\Desktop\\PROJETOS\\AUTOMACAO\\ROBO_MANUAL\\Vigas\\A_B\\0000ZERO.scr"
        with open(caminho_zero, 'w', encoding='utf-16') as f:
            f.write(script_final)

    except ValueError as e:
        print(f"Erro ao gerar script: {e}")

# Criar janela principal
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
for i in range(5):
    entry = ttk.Entry(paineis_largura_frame, width=10)
    entry.grid(row=0, column=i, padx=2)
    paineis_largura_entries.append(entry)

# Inicializar as larguras dos painéis
larguras_paineis = [244, 244, 112]
for i, largura in enumerate(larguras_paineis):
    if i < len(paineis_largura_entries):
        paineis_largura_entries[i].insert(0, str(int(largura)))

# Altura total
ttk.Label(main_frame, text="Altura Total:").grid(row=4, column=0, sticky="w")
altura_total_entry = ttk.Entry(main_frame, width=20)
altura_total_entry.insert(0, "180")
altura_total_entry.grid(row=4, column=1, sticky="w")
altura_total_entry.bind('<KeyRelease>', calcular_paineis_altura)

# Campo da Laje e Marcadores
ttk.Label(main_frame, text="Altura da Laje:").grid(row=4, column=2, sticky="w", padx=(20,0))
altura_laje_entry = ttk.Entry(main_frame, width=10)
altura_laje_entry.grid(row=4, column=3, sticky="w")
altura_laje_entry.bind('<KeyRelease>', calcular_paineis_altura)  # Recalcula quando altura da laje mudar

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
for i in range(3):
    entry = ttk.Entry(paineis_altura_frame, width=10)
    entry.grid(row=0, column=i, padx=2)
    paineis_altura_entries.append(entry)

# Inicializar as alturas dos painéis
alturas_paineis = [122, 43]
for i, altura in enumerate(alturas_paineis):
    if i < len(paineis_altura_entries):
        paineis_altura_entries[i].insert(0, str(int(altura)))

# Grades
ttk.Label(main_frame, text="Alturas das Grades:").grid(row=6, column=0, sticky="w")
grades_frame = ttk.Frame(main_frame)
grades_frame.grid(row=6, column=1, columnspan=2, sticky="w")

grades_labels = ['1', '2', '3', '4', '5', '6']
grades_entries = []
for i, label in enumerate(grades_labels):
    ttk.Label(grades_frame, text=label).grid(row=0, column=i, padx=2)
    entry = ttk.Entry(grades_frame, width=10)
    entry.grid(row=1, column=i, padx=2)
    grades_entries.append(entry)

# Inicializar as alturas das grades
alturas_grades = [100, 100, 100, 100]
for i, altura in enumerate(alturas_grades):
    if i < len(grades_entries):
        grades_entries[i].insert(0, str(altura))

# Botão gerar
ttk.Button(main_frame, text="Gerar Script", command=gerar_script).grid(row=7, column=0, columnspan=3, pady=10)

# Iniciar aplicação
root.mainloop()
