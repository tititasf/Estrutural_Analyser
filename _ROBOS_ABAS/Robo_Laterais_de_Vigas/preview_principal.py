import tkinter as tk
from tkinter import ttk

class PreviewPrincipal:
    def __init__(self, contexto):
        """
        contexto: pode ser o app principal ou um dicionário com as variáveis necessárias para o preview
        """
        self.contexto = contexto
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
        self.zoom_level = 1.0
        self.pan_start = None
        self.preview_frame = None
        self.canvas = None

    def criar_preview(self, parent):
        # Estrutura básica do preview
        self.preview_frame = ttk.LabelFrame(parent, text="Visualização", padding=5)
        self.preview_frame.pack(fill=tk.X, expand=True)
        self.label_nome_preview = tk.Label(self.preview_frame, text="", font=("Arial", 16, "bold"))
        self.label_nome_preview.pack(side=tk.TOP, pady=(0, 2))
        self.canvas_frame = ttk.Frame(self.preview_frame)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.canvas_frame, width=450, height=220, 
                              bg=self.cores['fundo'],
                              scrollregion=(0, 0, 900, 400))
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Eventos de zoom e pan
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._pan)
        self.canvas.bind("<ButtonRelease-1>", self._stop_pan)
        self.canvas.bind("<MouseWheel>", self._mouse_wheel)
        self.canvas.bind("<Button-4>", self._mouse_wheel)
        self.canvas.bind("<Button-5>", self._mouse_wheel)
        self.preview_frame.update_idletasks()
        self.canvas.update_idletasks()
        # Chamar atualização inicial
        self.atualizar_preview()

    def atualizar_preview(self, *args):
        """Atualiza o preview do painel principal."""
        if not self.canvas or not self.canvas.winfo_exists():
            return
        try:
            self.canvas.delete("all")
            # Acessa variáveis do contexto (app principal)
            try:
                largura = self._float_safe(self.contexto.largura_var)
                altura_geral = self._float_safe(self.contexto.altura_geral_var)
            except Exception:
                return
            if largura <= 0 or altura_geral <= 0:
                return
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            if canvas_width <= 1 or canvas_height <= 1:
                self.canvas.update_idletasks()
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                if canvas_width <= 1 or canvas_height <= 1:
                    return
            escala_x = 400 / (largura * 1.2) * self.zoom_level
            escala_y = 200 / (altura_geral * 1.2) * self.zoom_level
            escala = min(escala_x, escala_y)
            x_inicial = 50 * self.zoom_level
            y_inicial = 250 * self.zoom_level
            # Chama o método de desenho (a ser migrado)
            self.desenhar_elementos(self.canvas, x_inicial, y_inicial, largura, altura_geral, escala)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception as e:
            print(f"[PreviewPrincipal] Erro ao atualizar preview: {str(e)}")

    def _float_safe(self, var):
        try:
            val = str(var.get()).replace(',', '.')
            if '+' in val:
                partes = val.split('+')
                return sum(float(p.strip()) for p in partes if p.strip())
            return float(val)
        except Exception:
            return 0.0

    def desenhar_elementos(self, canvas, x_inicial, y_inicial, largura, altura_geral, escala):
        """Desenha todos os elementos do preview no canvas especificado."""
        # Linha base
        canvas.create_line(
            x_inicial, y_inicial,
            x_inicial + largura * escala, y_inicial,
            fill=self.cores['cota'], dash=(4, 4)
        )
        x_atual = x_inicial
        paineis_validos = []
        ultimo_painel_idx = -1
        for i in range(6):
            largura_painel = self._float_safe(self.contexto.paineis_larguras_vars[i])
            if largura_painel > 0:
                ultimo_painel_idx = i
                paineis_validos.append(i)
        if not paineis_validos:
            return
        # Desenhar linhas tracejadas de altura1 se houver
        for i in range(6):
            largura_painel = self._float_safe(self.contexto.paineis_larguras_vars[i])
            altura1_str = self.contexto.paineis_alturas_vars[i].get()
            if largura_painel > 0 and altura1_str:
                if '+' in altura1_str:
                    partes = altura1_str.split('+')
                    try:
                        h1 = float(partes[0].strip())
                        y_tracejada = y_inicial - h1 * escala
                        canvas.create_line(
                            x_atual, y_tracejada,
                            x_atual + largura_painel * escala, y_tracejada,
                            fill='black', dash=(4, 2), width=2
                        )
                    except Exception:
                        pass
            x_atual += largura_painel * escala
        # Desenhar painéis, lajes, cotas verticais
        x_atual = x_inicial
        for i in range(6):
            largura_painel = self._float_safe(self.contexto.paineis_larguras_vars[i])
            altura1 = self._float_safe(self.contexto.paineis_alturas_vars[i])
            altura2 = self._float_safe(self.contexto.paineis_alturas2_vars[i])
            laje_sup = self._float_safe(self.contexto.lajes_sup_vars[i])
            laje_inf = self._float_safe(self.contexto.lajes_inf_vars[i])
            laje_c_alt = self._float_safe(self.contexto.lajes_central_alt_vars[i])
            altura_painel = altura1 + laje_c_alt + altura2 + laje_sup + laje_inf
            is_primeiro = (i == paineis_validos[0])
            is_ultimo = (i == ultimo_painel_idx)
            if largura_painel > 0 and (altura1 + altura2) > 0:
                if i == paineis_validos[0]:
                    segmentos = [
                        ("Laje Inf.", laje_inf),
                        ("Altura 1", altura1),
                        ("Laje Central", laje_c_alt),
                        ("Altura 2", altura2),
                        ("Laje Sup.", laje_sup)
                    ]
                    x_cota = x_inicial - 35
                    self._desenhar_cotas_verticais_segmentos(
                        canvas, x_cota, y_inicial, segmentos, escala, lado='esq'
                    )
                if i == ultimo_painel_idx:
                    segmentos = [
                        ("Laje Inf.", laje_inf),
                        ("Altura 1", altura1),
                        ("Laje Central", laje_c_alt),
                        ("Altura 2", altura2),
                        ("Laje Sup.", laje_sup)
                    ]
                    x_cota = x_atual + largura_painel * escala + 35
                    self._desenhar_cotas_verticais_segmentos(
                        canvas, x_cota, y_inicial, segmentos, escala, lado='dir'
                    )
                    x_cota_total = x_cota + 35
                    segmentos_total = [("Altura Total", altura_painel)]
                    self._desenhar_cotas_verticais_segmentos(
                        canvas, x_cota_total, y_inicial, segmentos_total, escala, lado='dir'
                    )
                if laje_sup > 0:
                    self._desenhar_laje_suave(
                        canvas,
                        x_atual,
                        y_inicial - altura_painel * escala,
                        largura_painel * escala, laje_sup * escala
                    )
                if laje_inf > 0:
                    self._desenhar_laje_suave(
                        canvas, x_atual, y_inicial,
                        largura_painel * escala, laje_inf * escala
                    )
                if laje_c_alt > 0:
                    y_laje_central = y_inicial - altura1 * escala
                    self._desenhar_laje_suave(
                        canvas,
                        x_atual,
                        y_laje_central - laje_c_alt * escala,
                        largura_painel * escala,
                        laje_c_alt * escala,
                        fill="#888888"
                    )
                if altura1 > 0:
                    y_topo_alt1 = y_inicial - altura1 * escala
                    canvas.create_rectangle(
                        x_atual, y_inicial,
                        x_atual + largura_painel * escala, y_topo_alt1,
                        outline=self.cores['painel'], width=2, fill="#E3F2FD"
                    )
                if altura2 > 0:
                    y_base_alt2 = y_inicial - altura1 * escala
                    if laje_c_alt > 0:
                        y_base_alt2 -= laje_c_alt * escala
                    y_topo_alt2 = y_base_alt2 - altura2 * escala
                    canvas.create_rectangle(
                        x_atual, y_base_alt2,
                        x_atual + largura_painel * escala, y_topo_alt2,
                        outline=self.cores['painel'], width=2, fill="#E3F2FD"
                    )
                if altura2 > 0 and altura1 > 0:
                    y_divisao = y_inicial - altura1 * escala
                    if laje_c_alt > 0:
                        y_divisao -= laje_c_alt * escala
                    canvas.create_line(
                        x_atual, y_divisao,
                        x_atual + largura_painel * escala, y_divisao,
                        fill="#000", width=2
                    )
                if i > 0:
                    y_topo = y_inicial - (altura1 + laje_c_alt + altura2 + laje_sup) * escala
                    y_base = y_inicial + laje_inf * escala
                    canvas.create_line(
                        x_atual, y_base,
                        x_atual, y_topo,
                        fill=self.cores['divisao'], width=2
                    )
            x_atual += largura_painel * escala
        # Desenhar aberturas
        self._desenhar_aberturas(canvas, x_inicial, y_inicial, largura, altura_geral, escala)
        # Desenhar cotas principais
        self._desenhar_cotas(canvas, x_inicial, y_inicial, largura, altura_geral, escala)

    def _mouse_wheel(self, event):
        # Placeholder para zoom
        pass

    def _start_pan(self, event):
        # Placeholder para pan
        pass

    def _pan(self, event):
        # Placeholder para pan
        pass

    def _stop_pan(self, event):
        # Placeholder para pan
        pass

    def _desenhar_laje_suave(self, canvas, x, y, largura, altura, fill=None):
        """Desenha um retângulo de laje com cor cinza escuro e borda cinza clara, ou cor customizada."""
        canvas.create_rectangle(
            x, y, x + largura, y + altura,
            outline="#222", width=1, fill="#444444"
        )
        if fill:
            canvas.create_rectangle(
                x, y, x + largura, y + altura,
                fill=fill,
                outline="#222"
            )

    def _desenhar_cotas(self, canvas, x_inicial, y_inicial, largura, altura, escala):
        """Desenha as cotas do painel principal."""
        canvas.create_line(
            x_inicial, y_inicial + 20,
            x_inicial + largura * escala, y_inicial + 20,
            fill=self.cores['cota'], arrow="both"
        )
        canvas.create_text(
            x_inicial + (largura * escala) / 2, y_inicial + 35,
            text=f"Largura: {largura:.1f}",
            fill=self.cores['texto']
        )
        canvas.create_line(
            x_inicial - 20, y_inicial,
            x_inicial - 20, y_inicial - altura * escala,
            fill=self.cores['cota'], arrow="both"
        )
        canvas.create_text(
            x_inicial - 35, y_inicial - (altura * escala) / 2,
            text=f"Altura: {altura:.1f}",
            fill=self.cores['texto'],
            angle=90
        )

    def _desenhar_painel_principal(self, canvas, x_inicial, y_inicial, largura, altura, escala):
        """Desenha o painel principal."""
        canvas.create_rectangle(
            x_inicial, y_inicial,
            x_inicial + largura * escala, y_inicial - altura * escala,
            outline=self.cores['painel'],
            width=2
        )

    def _desenhar_aberturas(self, canvas, x_inicial, y_inicial, largura, altura, escala):
        """Desenha as aberturas do painel principal nas esquinas corretas dos painéis, considerando lajes e alturas."""
        x_painel_esq = x_inicial
        x_painel_dir = x_inicial + largura * escala
        altura1_esq = self._float_safe(self.contexto.paineis_alturas_vars[0])
        altura2_esq = self._float_safe(self.contexto.paineis_alturas2_vars[0])
        laje_central_esq = self._float_safe(self.contexto.lajes_central_alt_vars[0])
        laje_sup_esq = self._float_safe(self.contexto.lajes_sup_vars[0])
        altura1_dir = self._float_safe(self.contexto.paineis_alturas_vars[2])
        altura2_dir = self._float_safe(self.contexto.paineis_alturas2_vars[2])
        laje_central_dir = self._float_safe(self.contexto.lajes_central_alt_vars[2])
        laje_sup_dir = self._float_safe(self.contexto.lajes_sup_vars[2])
        altura_total_esq = altura1_esq + altura2_esq + laje_central_esq + laje_sup_esq
        altura_total_dir = altura1_dir + altura2_dir + laje_central_dir + laje_sup_dir
        y_topo_esq = y_inicial - altura_total_esq * escala
        y_fundo_esq = y_inicial
        y_topo_dir = y_inicial - altura_total_dir * escala
        y_fundo_dir = y_inicial
        for i, linha in enumerate(self.contexto.aberturas_vars):
            try:
                valores = [self._float_safe(v) for v in linha]
                dist, prof, larg = valores
                if prof <= 0 or larg <= 0:
                    continue
                forcar_altura1_ativo = self.contexto.forcar_altura1_vars[i].get() if hasattr(self.contexto, 'forcar_altura1_vars') and i < len(self.contexto.forcar_altura1_vars) else False
                if i == 0:  # esquerda topo
                    x_pos = x_painel_esq
                    if forcar_altura1_ativo and laje_central_esq > 0:
                        y_pos = y_inicial - altura1_esq * escala - laje_central_esq * escala + dist * escala
                    else:
                        y_pos = y_topo_esq + dist * escala
                elif i == 1:  # esquerda base
                    x_pos = x_painel_esq
                    y_pos = y_fundo_esq - prof * escala - dist * escala
                elif i == 2:  # direita topo
                    x_pos = x_painel_dir - larg * escala
                    if forcar_altura1_ativo and laje_central_dir > 0:
                        y_pos = y_inicial - altura1_dir * escala - laje_central_dir * escala + dist * escala
                    else:
                        y_pos = y_topo_dir + dist * escala
                elif i == 3:  # direita base
                    x_pos = x_painel_dir - larg * escala
                    y_pos = y_fundo_dir - prof * escala - dist * escala
                else:
                    continue
                canvas.create_rectangle(
                    x_pos, y_pos,
                    x_pos + larg * escala, y_pos + prof * escala,
                    fill=self.cores['abertura'],
                    outline=self.cores['divisao']
                )
                # Aqui pode-se chamar um helper para hachura se desejar
                cota_offset = 5 * escala
                if i in [0, 1]:  # aberturas da esquerda
                    x_cota_altura = x_pos - cota_offset
                    lado_cota = 'esq'
                else:  # aberturas da direita
                    x_cota_altura = x_pos + larg * escala + cota_offset
                    lado_cota = 'dir'
                y1_altura = y_pos
                y2_altura = y_pos + prof * escala
                canvas.create_line(
                    x_cota_altura, y1_altura,
                    x_cota_altura, y2_altura,
                    fill=self.cores['cota'], arrow="both"
                )
                canvas.create_text(
                    x_cota_altura - (15 if lado_cota == 'esq' else -15),
                    (y1_altura + y2_altura) / 2,
                    text=f"{prof:.1f}",
                    fill=self.cores['texto'], angle=90
                )
                y_cota_largura = y_pos - cota_offset
                x1_largura = x_pos
                x2_largura = x_pos + larg * escala
                canvas.create_line(
                    x1_largura, y_cota_largura,
                    x2_largura, y_cota_largura,
                    fill=self.cores['cota'], arrow="both"
                )
                canvas.create_text(
                    (x1_largura + x2_largura) / 2,
                    y_cota_largura - 10,
                    text=f"{larg:.1f}",
                    fill=self.cores['texto']
                )
            except Exception as e:
                continue

    # Métodos de desenho e helpers serão migrados aqui 