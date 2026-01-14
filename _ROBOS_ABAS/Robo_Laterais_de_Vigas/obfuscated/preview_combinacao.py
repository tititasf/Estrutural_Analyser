import tkinter as tk
from tkinter import ttk
import math # Adiciona a importação do módulo math

class PreviewCombinacao: # Renomeei para classe para gerenciar a janela
    def __init__(self, master):
        self.master = master # A instância do FundoProducaoApp
        self.preview_window = None
        self.cores = {
            'fundo': "#FFFFFF",
            'painel': "#E3F2FD",
            'sarrafo': "#FF9800",
            'abertura': "#FFEB3B",
            'chanfro': "#4CAF50",
            'divisao': "#000000",
            'cota': "#2196F3",
            'texto': "#000000"
        }

        self._scale = 1.0 # Escala inicial do zoom
        self._pan_start_x = 0 # Posição inicial X para o arrasto
        self._pan_start_y = 0 # Posição inicial Y para o arrasto

    def exibir_preview_combinacao(self, combinacao):
        # Fecha a janela de preview anterior se existir
        if self.preview_window and self.preview_window.winfo_exists():
            self.preview_window.destroy()

        nome_combinacao = combinacao['nome']
        fundos_ids = combinacao['ids']

        self.preview_window = tk.Toplevel(self.master)
        self.preview_window.title(f"Preview da Combinação: {nome_combinacao}")
        self.preview_window.geometry("800x400") # Aumentei o tamanho para o preview

        # Frame para o Canvas e Scrollbars
        canvas_frame = ttk.Frame(self.preview_window)
        canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="white", bd=2, relief="sunken")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Adicionar scrollbars
        self.hbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.config(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)

        # Vincular eventos do mouse para zoom e pan
        self.canvas.bind("<MouseWheel>", self._on_mousewheel) # Para Windows e macOS
        self.canvas.bind("<ButtonPress-1>", self._start_pan) # Botão esquerdo para arrastar
        self.canvas.bind("<B1-Motion>", self._pan) # Movimento do mouse enquanto arrasta
        self.canvas.bind("<ButtonRelease-1>", self._stop_pan) # Soltar o botão esquerdo

        # Lógica de desenho dos fundos combinados
        self.canvas.delete("all") # Limpa o canvas antes de desenhar

        if not fundos_ids:
            ttk.Label(self.canvas, text="Nenhum fundo selecionado para esta combinação.", font=("Arial", 12, "bold")).pack(pady=20)
            return

        # Coleta os dados dos fundos
        fundos_para_desenhar = []
        for f_id in fundos_ids:
            if f_id in self.master.fundos_salvos: # Acessa fundos_salvos através de master
                fundos_para_desenhar.append(self.master.fundos_salvos[f_id])
            else:
                print(f"Aviso: Fundo com ID {f_id} não encontrado.")

        if not fundos_para_desenhar or len(fundos_para_desenhar) < 2:
            ttk.Label(self.canvas, text="Dois fundos combinados são necessários para o preview.", font=("Arial", 12, "bold")).pack(pady=20)
            return

        seg1_data = fundos_para_desenhar[0]
        seg2_data = fundos_para_desenhar[1]

        # 1. Obter o maior valor de 'fundo'
        fundo_s1 = self._float_safe(seg1_data.get('fundo', '0.0'))
        fundo_s2 = self._float_safe(seg2_data.get('fundo', '0.0'))
        fundo_width_cm = max(fundo_s1, fundo_s2)

        # Coletar informações de tipo e grade para as alturas
        tipo1_s1 = seg1_data.get('paineis_tipo1', [''])[0]
        grade1_s1 = self._float_safe(seg1_data.get('paineis_grade_altura1', [0.0])[0])
        tipo2_s1 = seg1_data.get('paineis_tipo2', [''])[0]
        grade2_s1 = self._float_safe(seg1_data.get('paineis_grade_altura2', [0.0])[0])

        tipo1_s2 = seg2_data.get('paineis_tipo1', [''])[0]
        grade1_s2 = self._float_safe(seg2_data.get('paineis_grade_altura1', [0.0])[0])
        tipo2_s2 = seg2_data.get('paineis_tipo2', [''])[0]
        grade2_s2 = self._float_safe(seg2_data.get('paineis_grade_altura2', [0.0])[0])


        # Configurações de desenho
        scale = 10 # 1 cm = 10 pixels
        wall_width_cm = 2.2
        wall_width_px = wall_width_cm * scale

        # Calcular as alturas totais de cada lado para determinar a altura da U
        altura1_s1 = self._float_safe(seg1_data.get('paineis_alturas', [0.0])[0])
        laje_inf_s1 = self._float_safe(seg1_data.get('lajes_inf', [0.0])[0])
        laje_central_s1 = self._float_safe(seg1_data.get('lajes_central_alt', [0.0])[0])
        altura2_s1 = self._float_safe(seg1_data.get('paineis_alturas2', [0.0])[0])
        total_height_s1_cm = laje_inf_s1 + altura1_s1 + laje_central_s1 + altura2_s1

        altura1_s2 = self._float_safe(seg2_data.get('paineis_alturas', [0.0])[0])
        laje_inf_s2 = self._float_safe(seg2_data.get('lajes_inf', [0.0])[0])
        laje_central_s2 = self._float_safe(seg2_data.get('lajes_central_alt', [0.0])[0])
        altura2_s2 = self._float_safe(seg2_data.get('paineis_alturas2', [0.0])[0])
        total_height_s2_cm = laje_inf_s2 + altura1_s2 + laje_central_s2 + altura2_s2

        max_u_height_cm = max(total_height_s1_cm, total_height_s2_cm)

        # Margens para centralizar o desenho
        margin_x = 50
        margin_y = 50

        # A altura do canvas é `self.canvas.winfo_height()`, mas pode ser 1 antes da renderização.
        # Usar uma altura de referência para o desenho inicial.
        canvas_height = self.canvas.winfo_height() if self.canvas.winfo_height() > 1 else int(max_u_height_cm * scale) + (2 * margin_y)
        canvas_width = self.canvas.winfo_width() if self.canvas.winfo_width() > 1 else int(wall_width_px * 2 + fundo_width_cm * scale) + (2 * margin_x)

        self.canvas.config(width=canvas_width, height=canvas_height)

        y_base_px = canvas_height - margin_y # Fundo do desenho na parte inferior do canvas

        # X start para a parede esquerda
        x_start_left_px = margin_x

        # X start para a parede direita
        x_start_right_px = x_start_left_px + wall_width_px + (fundo_width_cm * scale)

        # Desenhar a parede esquerda
        self._draw_wall(self.canvas, x_start_left_px, y_base_px, seg1_data, scale, tipo1_s1, grade1_s1, tipo2_s1, grade2_s1)

        # Desenhar a parede direita
        self._draw_wall(self.canvas, x_start_right_px, y_base_px, seg2_data, scale, tipo1_s2, grade1_s2, tipo2_s2, grade2_s2)

        # Desenhar a base da 'U'
        # A base é uma linha que conecta os pontos mais baixos das paredes.
        self.canvas.create_line(x_start_left_px, y_base_px,
                                x_start_right_px + wall_width_px, y_base_px,
                                fill="black", width=2)
        # Adicionar o texto do fundo
        self.canvas.create_text(x_start_left_px + wall_width_px + (fundo_width_cm * scale) / 2, y_base_px + 10,
                                text=f"Fundo: {fundo_width_cm:.2f} cm", font=("Arial", 8), fill=self.cores['texto'])


        # Ajustar o scrollregion e tentar centralizar o desenho
        self.canvas.update_idletasks() # Garante que todos os comandos de desenho foram processados
        bbox = self.canvas.bbox("all")
        if bbox:
            # Calcular o centro do conteúdo desenhado
            center_x_content = (bbox[0] + bbox[2]) / 2
            center_y_content = (bbox[1] + bbox[3]) / 2

            # Calcular o centro do canvas
            canvas_center_x = self.canvas.winfo_width() / 2
            canvas_center_y = self.canvas.winfo_height() / 2

            # Calcular o offset para centralizar
            offset_x = canvas_center_x - center_x_content
            offset_y = canvas_center_y - center_y_content

            # Mover o conteúdo do canvas
            self.canvas.xview_moveto(-bbox[0] / (bbox[2] - bbox[0]))
            self.canvas.yview_moveto(-bbox[1] / (bbox[3] - bbox[1]))
            self.canvas.xview_scroll(int(offset_x), "units")
            self.canvas.yview_scroll(int(offset_y), "units")

    def _desenhar_laje_suave(self, canvas, x, y, largura, altura, fill=None):
        # Função auxiliar para desenhar uma laje com chanfro suave
        if fill is None:
            fill = self.cores['chanfro'] # Cor padrão para lajes
        
        # Desenha o retângulo principal
        canvas.create_rectangle(x, y, x + largura, y + altura, fill=fill, outline="")

        # Calcula os pontos para o chanfro
        chanfro_size = 10  # Tamanho fixo do chanfro
        
        # Canto superior esquerdo
        canvas.create_polygon(
            x, y, 
            x + chanfro_size, y, 
            x, y + chanfro_size,
            fill=self.cores['fundo'], outline="", smooth=True
        )
        # Canto superior direito
        canvas.create_polygon(
            x + largura, y, 
            x + largura - chanfro_size, y, 
            x + largura, y + chanfro_size,
            fill=self.cores['fundo'], outline="", smooth=True
        )
        # Canto inferior esquerdo
        canvas.create_polygon(
            x, y + altura, 
            x + chanfro_size, y + altura, 
            x, y + altura - chanfro_size,
            fill=self.cores['fundo'], outline="", smooth=True
        )
        # Canto inferior direito
        canvas.create_polygon(
            x + largura, y + altura, 
            x + largura - chanfro_size, y + altura, 
            x + largura, y + altura - chanfro_size,
            fill=self.cores['fundo'], outline="", smooth=True
        )
    
    def _desenhar_cotas_verticais_segmentos(self, canvas, x_cota, y_base, segmentos, escala, lado='esq'):
        # Implementação simplificada para o preview
        # Adapte esta função com base na sua lógica original para cotas
        y_atual = y_base
        for label, valor in segmentos:
            if valor > 0:
                y_segmento_fim = y_atual - valor * escala
                # Linha de cota
                canvas.create_line(x_cota, y_atual, x_cota, y_segmento_fim, fill=self.cores['cota'], width=1)
                
                # Linhas de extensão
                if lado == 'esq':
                    canvas.create_line(x_cota, y_atual, x_cota + 5, y_atual, fill=self.cores['cota'], width=1)
                    canvas.create_line(x_cota, y_segmento_fim, x_cota + 5, y_segmento_fim, fill=self.cores['cota'], width=1)
                    texto_x = x_cota - 5
                    anchor = "e"
                else: # lado == 'dir'
                    canvas.create_line(x_cota, y_atual, x_cota - 5, y_atual, fill=self.cores['cota'], width=1)
                    canvas.create_line(x_cota, y_segmento_fim, x_cota - 5, y_segmento_fim, fill=self.cores['cota'], width=1)
                    texto_x = x_cota + 5
                    anchor = "w"

                # Texto da cota
                canvas.create_text(
                    texto_x,
                    (y_atual + y_segmento_fim) / 2,
                    text=f"{valor:.0f}",
                    fill=self.cores['texto'],
                    font=("Arial", 8),
                    anchor=anchor
                )
                y_atual = y_segmento_fim

    def _desenhar_hachura_abertura(self, canvas, x1, y1, x2, y2, espacamento=6):
        """
        Desenha linhas diagonais (hachura) dentro do retângulo da abertura.
        x1, y1: canto superior esquerdo
        x2, y2: canto inferior direito
        espacamento: distância entre as linhas da hachura
        """
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        largura = x2 - x1
        altura = y2 - y1
        for i in range(-int(altura), int(largura), espacamento):
            xi = x1 + max(i, 0)
            yi = y2 - max(-i, 0)
            xf = x1 + min(i + altura, largura)
            yf = y2 - min(i + altura, altura)
            canvas.create_line(xi, yi, xf, yf, fill="#BDB76B", width=1)

    def _float_safe(self, value):
        """Converte um valor para float de forma segura."""
        try:
            if isinstance(value, (tk.DoubleVar, tk.StringVar, tk.BooleanVar)):
                return float(value.get() or 0)
            return float(value or 0)
        except (ValueError, TypeError):
            return 0.0

    def _area_intersecao(self, rx1, ry1, rx2, ry2, ax1, ay1, ax2, ay2):
        """Calcula a área de interseção entre dois retângulos."""
        inter_x1 = max(rx1, ax1)
        inter_y1 = max(ry1, ay1)
        inter_x2 = min(rx2, ax2)
        inter_y2 = min(ry2, ay2)
        if inter_x2 > inter_x1 and inter_y2 > inter_y1:
            return (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        return 0 

    def _on_mousewheel(self, event):
        """Lida com o evento de scroll do mouse para zoom."""
        scale_factor = 1.05 # Fator de zoom base
        
        # Determina o fator de escala a ser aplicado com base na direção do scroll
        if event.delta > 0: # Scroll para cima (zoom in)
            scale_to_apply = scale_factor
        else: # Scroll para baixo (zoom out)
            scale_to_apply = 1.0 / scale_factor # Fator inverso para zoom out

        # Calcula a posição do cursor em relação ao conteúdo atual do canvas
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # Aplica o zoom no canvas
        self.canvas.scale("all", x, y, scale_to_apply, scale_to_apply)
        
        # Atualiza a escala interna (self._scale) - Opcional, dependendo de como _draw_wall usa a escala
        # Se _draw_wall usa self._scale diretamente para desenhar, precisamos atualizar self._scale
        # Se _draw_wall usa a escala passada como argumento 'scale', então self._scale é apenas para controle
        # Pela implementação anterior, _draw_wall RECEBE a escala, mas a escala inicial é 10. 
        # A lógica de zoom atual escala os objetos existentes. 
        # Se quisermos que o desenho inicial _draw_wall respeite o zoom atual, precisaríamos 
        # ou redesenhar tudo em cada zoom (ineficiente) ou garantir que _draw_wall 
        # use a escala de transformação ATUAL do canvas para posicionar/dimensionar.
        # A forma mais comum com canvas.scale é apenas aplicá-la e deixar o canvas gerenciar as coordenadas.
        # Portanto, atualizar self._scale aqui pode ser redundante ou confuso se _draw_wall
        # não for redesenhado com base nisso.
        # Vamos manter a lógica de aplicar a escala no canvas e ver se o comportamento é o desejado.
        # Se o desenho ficar distorcido ou incorreto após o zoom, precisaremos reconsiderar.

        # No entanto, para fins de controle e possível uso futuro, manter self._scale atualizado pode ser útil.
        # Vamos atualizar self._scale com base no fator aplicado.
        if event.delta > 0: 
             self._scale *= scale_factor
        else:
             self._scale /= scale_factor
             # Opcional: Adicionar um limite mínimo para self._scale se necessário
             # if self._scale < 0.01: self._scale = 0.01 # Exemplo de limite

        # Atualiza a região de scroll
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def _start_pan(self, event):
        """Inicia a operação de arrasto."""
        self._pan_start_x = self.canvas.canvasx(event.x)
        self._pan_start_y = self.canvas.canvasy(event.y)
        self.canvas.config(cursor="hand2") # Muda o cursor para indicar arrasto

    def _pan(self, event):
        """Realiza o arrasto do canvas."""
        # Calcula o quanto o mouse se moveu em coordenadas do canvas
        dx = self.canvas.canvasx(event.x) - self._pan_start_x
        dy = self.canvas.canvasy(event.y) - self._pan_start_y

        # Move todos os itens no canvas
        self.canvas.move("all", dx * 0.2, dy * 0.2) # Reduzindo o fator para 0.2

        # Atualiza a região de scroll
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def _stop_pan(self, event):
        """Finaliza a operação de arrasto."""
        self.canvas.config(cursor="") # Retorna o cursor ao normal

    def _draw_wall(self, canvas, x_start, y_base, segment_data, scale, tipo1_info, grade1_info, tipo2_info, grade2_info):
        """
        Desenha uma parede lateral da forma 'U' com base nos dados do segmento.
        y_base é a coordenada Y do fundo (maior valor de Y no canvas, para desenhar para cima).
        """
        altura1 = self._float_safe(segment_data.get('paineis_alturas', [0.0])[0])
        laje_inf = self._float_safe(segment_data.get('lajes_inf', [0.0])[0])
        laje_central = self._float_safe(segment_data.get('lajes_central_alt', [0.0])[0])
        altura2 = self._float_safe(segment_data.get('paineis_alturas2', [0.0])[0])

        wall_width_cm = 2.2
        wall_width_px = wall_width_cm * scale

        current_y_px = y_base # Começa a desenhar do Y mais baixo para cima

        # Desenha Laje Inferior (espaço)
        if laje_inf > 0:
            laje_inf_height_px = laje_inf * scale
            canvas.create_rectangle(x_start, current_y_px - laje_inf_height_px,
                                    x_start + wall_width_px, current_y_px,
                                    fill="lightgray", outline="")
            canvas.create_text(x_start + wall_width_px / 2, current_y_px - laje_inf_height_px / 2,
                               text=f"LI: {laje_inf:.2f}", font=("Arial", 6), fill=self.cores['texto'])
            current_y_px -= laje_inf_height_px

        # Desenha Altura 1
        if altura1 > 0:
            altura1_height_px = altura1 * scale
            canvas.create_rectangle(x_start, current_y_px - altura1_height_px,
                                    x_start + wall_width_px, current_y_px,
                                    fill=self.cores['painel'], outline="black")
            canvas.create_text(x_start + wall_width_px / 2, current_y_px - altura1_height_px / 2,
                               text=f"A1: {altura1:.2f}\n{tipo1_info} {grade1_info:.0f}", font=("Arial", 6), fill=self.cores['texto'], justify="center")
            current_y_px -= altura1_height_px

        # Desenha Laje Central (espaço)
        if laje_central > 0:
            laje_central_height_px = laje_central * scale
            canvas.create_rectangle(x_start, current_y_px - laje_central_height_px,
                                    x_start + wall_width_px, current_y_px,
                                    fill="lightgray", outline="")
            canvas.create_text(x_start + wall_width_px / 2, current_y_px - laje_central_height_px / 2,
                               text=f"LC: {laje_central:.2f}", font=("Arial", 6), fill=self.cores['texto'])
            current_y_px -= laje_central_height_px

        # Desenha Altura 2
        if altura2 > 0:
            altura2_height_px = altura2 * scale
            canvas.create_rectangle(x_start, current_y_px - altura2_height_px,
                                    x_start + wall_width_px, current_y_px,
                                    fill=self.cores['painel'], outline="black")
            canvas.create_text(x_start + wall_width_px / 2, current_y_px - altura2_height_px / 2,
                               text=f"A2: {altura2:.2f}\n{tipo2_info} {grade2_info:.0f}", font=("Arial", 6), fill=self.cores['texto'], justify="center")
            current_y_px -= altura2_height_px

        # Retorna a altura total desenhada da parede
        return y_base - current_y_px