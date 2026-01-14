import tkinter as tk
from tkinter import ttk
import os

def calcular_paineis_largura(*args):
    try:
        largura_total = float(largura_total_entry.get())
        num_paineis_244 = int(largura_total // 244)
        resto = largura_total % 244

        # Limpar campos existentes
        for entry in paineis_largura_entries:
            entry.delete(0, tk.END)

        if resto < 60 and num_paineis_244 > 0:
            # Último painel de 244 vira 122
            num_paineis_244 -= 1
            resto = resto + 122

        # Verificar se o número de painéis é válido
        if num_paineis_244 > len(paineis_largura_entries):
            return  # Ignorar se o número de painéis exceder o limite

        # Preencher campos com 244
        for i in range(num_paineis_244):
            paineis_largura_entries[i].insert(0, "244")

        # Adicionar o resto se houver
        if resto > 0:
            paineis_largura_entries[num_paineis_244].insert(0, f"{resto:.1f}")

    except ValueError:
        pass

def calcular_paineis_altura(*args):
    try:
        altura_total = float(altura_total_entry.get())
        altura_laje = float(altura_laje_entry.get())
        altura_disponivel = altura_total - altura_laje
        num_paineis_122 = int(altura_disponivel // 122)
        resto = altura_disponivel % 122

        # Limpar campos existentes
        for entry in paineis_altura_entries:
            entry.delete(0, tk.END)

        # Verificar se o número de painéis é válido
        if num_paineis_122 > len(paineis_altura_entries):
            return  # Ignorar se o número de painéis exceder o limite

        # Preencher campos com 122
        for i in range(num_paineis_122):
            paineis_altura_entries[i].insert(0, "122")

        # Adicionar o resto se houver
        if resto > 0:
            paineis_altura_entries[num_paineis_122].insert(0, f"{resto:.1f}")

    except ValueError:
        pass

def atualizar_grades(*args):
    try:
        valor = grades_entries[0].get()
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

def gerar_script():
    try:
        nome = nome_entry.get()
        observacoes = observacoes_entry.get()
        altura_laje = float(altura_laje_entry.get())
        largura_total = float(largura_total_entry.get())
        altura_total = float(altura_total_entry.get())

        # Coletar valores dos painéis
        larguras_paineis = []
        for entry in paineis_largura_entries:
            valor = entry.get()
            if valor:
                larguras_paineis.append(float(valor))

        alturas_paineis = []
        for entry in paineis_altura_entries:
            valor = entry.get()
            if valor:
                alturas_paineis.append(float(valor))

        # Coletar valores das grades
        alturas_grades = []
        for entry in grades_entries:
            valor = entry.get()
            if valor:
                alturas_grades.append(float(valor))

        # Coordenadas iniciais
        x_inicial = 0
        y_inicial = 0

        # Gerar script com formatação correta
        script = []
        
        # Zoom inicial
        script.append(f"_ZOOM")
        script.append(f"C {x_inicial+largura_total/2},{y_inicial+altura_total/2} 100")
        script.append(";")
        
        # Layer Painéis
        script.append("-LAYER")
        script.append("S Painéis")
        script.append("")
        script.append(";")

        # Desenhar painéis
        x_atual = x_inicial
        for i, largura in enumerate(larguras_paineis):
            script.append("_PLINE")
            script.append(f"{x_atual},{y_inicial}")
            script.append(f"{x_atual+largura},{y_inicial}")
            script.append(f"{x_atual+largura},{y_inicial+altura_total}")
            script.append(f"{x_atual},{y_inicial+altura_total}")
            script.append("C")
            script.append(";")
            x_atual += largura

        # Layer para laje
        script.append("-LAYER")
        script.append("S COTA")
        script.append("")
        script.append(";")

        # Desenhar laje
        script.append("_PLINE")
        script.append(f"{x_inicial},{y_inicial+altura_total}")
        script.append(f"{x_inicial+largura_total},{y_inicial+altura_total}")
        script.append(f"{x_inicial+largura_total},{y_inicial+altura_total+altura_laje}")
        script.append(f"{x_inicial},{y_inicial+altura_total+altura_laje}")
        script.append("C")
        script.append(";")
        script.append("HHHH")
        script.append(f"{x_inicial+largura_total/2},{y_inicial+altura_total+altura_laje/2}")
        script.append(";")

        # Layer para sarrafos de grade
        script.append("-LAYER")
        script.append("S SARR_3.5x7")
        script.append("")
        script.append(";")

        # Desenhar sarrafos de grade
        x_atual = x_inicial
        for i in range(len(larguras_paineis)):
            # Grade esquerda 
            if i == 0:
                x_grade = x_atual 
                script.append("_PLINE")
                script.append(f"{x_grade},{y_inicial+altura_total-2.2}")
                script.append(f"{x_grade+3.5},{y_inicial+altura_total-2.2}")
                script.append(f"{x_grade+3.5},{y_inicial+altura_total-2.2-alturas_grades[0]}")
                script.append(f"{x_grade},{y_inicial+altura_total-2.2-alturas_grades[0]}")
                script.append("C")
                script.append(";")

            # Grade direita do painel
            x_grade = x_atual + larguras_paineis[i] 
            script.append("_PLINE")
            script.append(f"{x_grade},{y_inicial+altura_total-2.2}")
            script.append(f"{x_grade+3.5},{y_inicial+altura_total-2.2}")
            script.append(f"{x_grade+3.5},{y_inicial+altura_total-2.2-alturas_grades[i+1]}")
            script.append(f"{x_grade},{y_inicial+altura_total-2.2-alturas_grades[i+1]}")
            script.append("C")
            script.append(";")
            x_atual += larguras_paineis[i]

        # Layer para sarrafos de 7cm
        script.append("-LAYER")
        script.append("S SARR_2.2x7")
        script.append("")
        script.append(";")

        # Sarrafos de 7cm
        x_atual = x_inicial
        for i in range(len(larguras_paineis)):
            if i == 0:
                x_sarrafo = x_atual 
                script.append("_PLINE")
                script.append(f"{x_sarrafo},{y_inicial}")
                script.append(f"{x_sarrafo},{y_inicial+altura_total}")
                script.append("")
                script.append(";")

            x_sarrafo = x_atual + larguras_paineis[i] 
            script.append("_PLINE")
            script.append(f"{x_sarrafo},{y_inicial}")
            script.append(f"{x_sarrafo},{y_inicial+altura_total}")
            script.append("")
            script.append(";")
            x_atual += larguras_paineis[i]

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
nome_entry.grid(row=0, column=1, columnspan=2, sticky="we")

ttk.Label(main_frame, text="Observações:").grid(row=1, column=0, sticky="w")
observacoes_entry = ttk.Entry(main_frame, width=40)
observacoes_entry.grid(row=1, column=1, columnspan=2, sticky="we")

ttk.Label(main_frame, text="Altura da Laje:").grid(row=2, column=0, sticky="w")
altura_laje_entry = ttk.Entry(main_frame, width=20)
altura_laje_entry.grid(row=2, column=1, sticky="w")

# Largura total
ttk.Label(main_frame, text="Largura Total:").grid(row=3, column=0, sticky="w")
largura_total_entry = ttk.Entry(main_frame, width=20)
largura_total_entry.grid(row=3, column=1, sticky="w")
largura_total_entry.bind('<KeyRelease>', calcular_paineis_largura)

# Painéis largura
ttk.Label(main_frame, text="Largura dos Painéis:").grid(row=4, column=0, sticky="w")
paineis_largura_frame = ttk.Frame(main_frame)
paineis_largura_frame.grid(row=4, column=1, columnspan=2, sticky="w")

paineis_largura_entries = []
for i in range(5):
    entry = ttk.Entry(paineis_largura_frame, width=10)
    entry.grid(row=0, column=i, padx=2)
    paineis_largura_entries.append(entry)

# Altura total
ttk.Label(main_frame, text="Altura Total:").grid(row=5, column=0, sticky="w")
altura_total_entry = ttk.Entry(main_frame, width=20)
altura_total_entry.grid(row=5, column=1, sticky="w")
altura_total_entry.bind('<KeyRelease>', calcular_paineis_altura)

# Painéis altura
ttk.Label(main_frame, text="Altura dos Painéis:").grid(row=6, column=0, sticky="w")
paineis_altura_frame = ttk.Frame(main_frame)
paineis_altura_frame.grid(row=6, column=1, columnspan=2, sticky="w")

paineis_altura_entries = []
for i in range(3):
    entry = ttk.Entry(paineis_altura_frame, width=10)
    entry.grid(row=0, column=i, padx=2)
    paineis_altura_entries.append(entry)

# Grades
ttk.Label(main_frame, text="Alturas das Grades:").grid(row=7, column=0, sticky="w")
grades_frame = ttk.Frame(main_frame)
grades_frame.grid(row=7, column=1, columnspan=2, sticky="w")

grades_labels = ['Esquerda', '1ª União', '2ª União', '3ª União', '4ª União', 'Direita']
grades_entries = []
for i, label in enumerate(grades_labels):
    ttk.Label(grades_frame, text=label).grid(row=0, column=i*2, padx=2)
    entry = ttk.Entry(grades_frame, width=8)
    entry.grid(row=1, column=i*2, padx=2)
    grades_entries.append(entry)
    if i == 0:  # Adicionar binding apenas para o primeiro campo
        entry.bind('<KeyRelease>', atualizar_grades)

# Botão gerar
ttk.Button(main_frame, text="Gerar Script", command=gerar_script).grid(row=8, column=0, columnspan=3, pady=10)

# Iniciar aplicação
root.mainloop()
