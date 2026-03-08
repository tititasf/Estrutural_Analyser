
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
Módulo auxiliar 4 - Funcionalidades de Preview e Desenho
Modularização das funções de visualização do funcoes_auxiliares_2.py
"""

import tkinter as tk
from tkinter import ttk

# Tentativa de importação da função parse_valor_soma
try:
    from funcoes_auxiliares_3 import parse_valor_soma
except ImportError:
    # Fallback se não conseguir importar
    def parse_valor_soma(valor_str):
        try:
            if '+' in valor_str:
                return sum(float(parte.strip().replace(',', '.')) for parte in valor_str.split('+'))
            return float(valor_str.replace(',', '.'))
        except:
            return 0.0

class CanvasPreviewMixin:
    """
    Mixin class que fornece funcionalidades de preview em canvas para o PilarAnalyzer
    """
    
    def criar_canvas_preview(self):
        """Cria e configura o canvas para preview visual dos painéis"""
        self.preview_frame = ttk.Frame(self)
        self.preview_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.preview_frame.columnconfigure(0, weight=1)
        self.preview_frame.rowconfigure(0, weight=1)
        
        canvas_frame = ttk.Frame(self.preview_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        self.canvas = tk.Canvas(canvas_frame, width=400, height=250, bg="white",
                              scrollregion=(0, 0, 900, 450))
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.zoom_level = 1.2
        self.cores_paineis = {
            'a': "#C8E6C9", 'b': "#BBDEFB", 'c': "#FFE0B2", 'd': "#E1BEE7",
            'e': "#A5D6A7", 'f': "#90CAF9", 'g': "#FFCC80", 'h': "#CE93D8",
            'laje': "#8D6E63", 'sarrafo': "#FF9800", 'pe_direito': "#EEEEEE",
            'abertura': "#8D6E63", 'divisao': "#000000"
        }
        
        # Configurar eventos do canvas
        self.canvas.bind("<ButtonPress-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.pan)
        self.canvas.bind("<ButtonRelease-1>", self.stop_pan)
        self.canvas.bind("<MouseWheel>", self.mouse_wheel)
        self.canvas.bind("<Button-4>", self.mouse_wheel)
        self.canvas.bind("<Button-5>", self.mouse_wheel)
        
        self.pan_start = None

    def mouse_wheel(self, event):
        """Controla o zoom do canvas com a roda do mouse"""
        if event.num == 5 or event.delta < 0:
            self.zoom_out()
        else:
            self.zoom_in()

    def zoom_in(self):
        """Aumenta o zoom do canvas"""
        new_zoom = min(self.zoom_level + 0.5, 6.0)  # Incremento menor para controle mais suave
        self.update_zoom(new_zoom)

    def zoom_out(self):
        """Diminui o zoom do canvas"""
        new_zoom = max(self.zoom_level - 6, 2.1)  # Decremento menor para controle mais suave
        self.update_zoom(new_zoom)

    def reset_zoom(self):
        """Reseta o zoom para o valor padrão"""
        self.update_zoom(2)
        self.canvas.scan_dragto(0, 0, gain=1)

    def update_zoom(self, value):
        """Atualiza o nível de zoom do canvas"""
        try:
            self.zoom_level = float(value)
            self.atualizar_preview()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except ValueError:
            pass

    def start_pan(self, event):
        """Inicia o movimento panorâmico do canvas"""
        self.canvas.scan_mark(event.x, event.y)
        self.pan_start = (event.x, event.y)

    def pan(self, event):
        """Executa o movimento panorâmico do canvas"""
        if self.pan_start:
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            self.pan_start = (event.x, event.y)

    def stop_pan(self, event):
        """Para o movimento panorâmico do canvas"""
        self.pan_start = None

    def atualizar_preview(self, event=None):
        """Atualiza a visualização do preview com os dados atuais"""
        caller = "desconhecido"
        if event:
            caller = str(event.widget) if hasattr(event, 'widget') else "evento sem widget"

        # Garante que os widgets atualizem seus valores antes de ler
        try:
            self.update_idletasks()
        except Exception:
            pass
        self.canvas.delete("all")
        
        try:
            comprimento_str = self.comprimento.get().strip()
            largura_str = self.largura.get().strip()
            altura_str = self.altura.get().strip()
            nome_pilar = self.nome_pilar.get().strip() if hasattr(self, 'nome_pilar') else ""

            if not comprimento_str or not largura_str or not altura_str:
                return

            comprimento = float(comprimento_str.replace(',', '.'))
            largura = float(largura_str.replace(',', '.'))
            altura = float(altura_str.replace(',', '.'))

            if comprimento <= 0 or largura <= 0 or altura <= 0:
                return

            # Parâmetros de desenho
            dist_paineis = 250  # 150cm extra entre cada painel principal (reduzido de 250 para 150)
            
            # Calcular dimensões totais do desenho
            largura_total_desenho = comprimento * 2 + largura * 2 + 5 * dist_paineis + 300
            altura_total_desenho = altura + 100  # Altura + margem para textos m²
            
            # Calcular escala para ocupar todo o canvas
            canvas_width = 400
            canvas_height = 250
            
            # Escala para ocupar 95% do canvas (deixando margem menor para melhor centralização)
            escala_x = canvas_width * 0.95 / largura_total_desenho
            escala_y = canvas_height * 0.95 / altura_total_desenho
            escala_base = min(escala_x, escala_y)
            
            # Aplicar zoom level
            escala = escala_base * self.zoom_level

            # Centralizar o desenho no canvas - ajuste para centralização perfeita
            largura_desenho_escalado = largura_total_desenho * escala
            x_inicial = (canvas_width - largura_desenho_escalado) / 2
            y_inicial = (canvas_height + altura_total_desenho * escala) / 2

            # Linhas de referência
            self.canvas.create_line(
                x_inicial, y_inicial,
                x_inicial + (comprimento * 2 + largura * 2 + 5 * dist_paineis + 300) * escala, y_inicial,
                fill="black", dash=(4, 4)
            )
            
            self.canvas.create_line(
                x_inicial, y_inicial - altura * escala,
                x_inicial + (comprimento * 2 + largura * 2 + 5 * dist_paineis + 300) * escala, y_inicial - altura * escala,
                fill="black", dash=(4, 4)
            )

            # Cota de altura
            self.canvas.create_line(
                x_inicial - 10, y_inicial,
                x_inicial - 10, y_inicial - altura * escala,
                fill="black", arrow="both"
            )
            
            self.canvas.create_text(
                x_inicial - 25, y_inicial - (altura * escala) / 2,
                text=f"{altura}",
                angle=0  # Agora horizontal
            )

            # Posições dos painéis - com vazio de 150cm antes do primeiro painel
            vazio_inicial = 250  # 150cm de vazio antes do primeiro painel
            x_a = x_inicial + vazio_inicial * escala
            x_b = x_a + (comprimento + dist_paineis) * escala  
            x_c = x_b + (comprimento + dist_paineis) * escala  
            x_d = x_c + (largura + dist_paineis) * escala      

            # Calcular m² de cada painel (usando dados da interface atual)
            m2_a = self.calcular_m2_painel(self._get_painel_dict('A'), 'A')
            m2_b = self.calcular_m2_painel(self._get_painel_dict('B'), 'B')
            m2_c = self.calcular_m2_painel(self._get_painel_dict('C'), 'C')
            m2_d = self.calcular_m2_painel(self._get_painel_dict('D'), 'D')
            m2_total = m2_a + m2_b + m2_c + m2_d

            # Texto informativo no topo
            texto_topo = f"{nome_pilar}  |  {comprimento:.1f} x {largura:.1f} x {altura:.1f} cm  |  Total: {m2_total:.2f} m²"
            x_centro = (x_a + x_d + largura * escala) / 2
            self.canvas.create_text(
                x_centro, y_inicial - altura * escala - 30,
                text=texto_topo,
                fill="black",
                font=("Arial", 12, "bold"),
                anchor="n"
            )

            # Desenhar painéis A, B, C, D
            self.desenhar_painel(x_a, y_inicial, comprimento, altura, 'a', escala)
            self.desenhar_painel(x_b, y_inicial, comprimento, altura, 'b', escala)
            self.desenhar_painel(x_c, y_inicial, largura, altura, 'c', escala)
            self.desenhar_painel(x_d, y_inicial, largura, altura, 'd', escala)

            # Textos de m² embaixo de cada painel (A, B, C, D)
            y_m2 = y_inicial + 12 * self.zoom_level  # Subiu 100cm (30 + 100 = 130, mas y_inicial - 70 = subiu 100)
            self.canvas.create_text(x_a + (comprimento * escala) / 2, y_m2, 
                                  text=f"A: {m2_a:.2f} m²", fill="black", 
                                  font=("Arial", 10, "bold"), anchor="n")
            self.canvas.create_text(x_b + (comprimento * escala) / 2, y_m2, 
                                  text=f"B: {m2_b:.2f} m²", fill="black", 
                                  font=("Arial", 10, "bold"), anchor="n")
            self.canvas.create_text(x_c + (largura * escala) / 2, y_m2, 
                                  text=f"C: {m2_c:.2f} m²", fill="black", 
                                  font=("Arial", 10, "bold"), anchor="n")
            self.canvas.create_text(x_d + (largura * escala) / 2, y_m2, 
                                  text=f"D: {m2_d:.2f} m²", fill="black", 
                                  font=("Arial", 10, "bold"), anchor="n")

            # Desenhar painéis E, F, G, H se pilar especial estiver ativo e tiverem dados
            if hasattr(self, 'ativar_pilar_especial') and self.ativar_pilar_especial.get():
                self.desenhar_paineis_especiais(x_d, y_inicial, largura, altura, escala, dist_paineis, y_m2)
            
            # ========================================================
            # 🎯 ATUALIZAÇÃO FINAL: ABERTURAS E LAJES (ÚLTIMA FUNÇÃO DO CANVAS)
            # ========================================================
            # Esta função deve ser a ÚLTIMA a ser chamada para garantir que
            # todas as aberturas e lajes sejam atualizadas corretamente sobre todos os painéis
            self._atualizar_aberturas_lajes_canvas(x_a, x_b, x_c, x_d, y_inicial, comprimento, largura, altura, escala)

        except Exception as e:
            # Falha silenciosa no preview não deve quebrar a aplicação
            pass
        
        # Aplicar zoom automático ao máximo após atualização
        try:
            # self.zoom_level = 2.0  # Zoom máximo - COMENTADO para manter zoom inicial
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass
    
    def desenhar_paineis_especiais(self, x_d, y_inicial, largura, altura, escala, dist_paineis, y_m2):
        """
        Desenha painéis E, F, G, H quando pilar especial está ativo e têm dados
        Usa exatamente o mesmo padrão dos painéis A, B, C, D
        """
        try:
            x_atual = x_d + (largura + dist_paineis) * escala
            
            # Lista de painéis especiais para verificar
            paineis_especiais = ['E', 'F', 'G', 'H']
            
            for letra in paineis_especiais:
                # Verificar se o painel tem dados
                if self.painel_tem_dados(letra):
                    # Obter largura total do painel (soma das larguras 1, 2, 3)
                    largura_painel = self.obter_largura_painel(letra)
                    
                    # Calcular altura específica do painel baseada nas alturas configuradas
                    altura_painel = self.calcular_altura_painel_especial(letra)
                    
                    # Desenhar painel usando exatamente o mesmo método dos outros
                    self.desenhar_painel(x_atual, y_inicial, largura_painel, altura_painel, letra.lower(), escala)
                    
                    # Calcular m² usando o mesmo método
                    m2_painel = self.calcular_m2_painel(self._get_painel_dict(letra), letra)
                    
                    # Texto de m² embaixo (mesmo padrão)
                    self.canvas.create_text(x_atual + (largura_painel * escala) / 2, y_m2, 
                                          text=f"{letra}: {m2_painel:.2f} m²", fill="black", 
                                          font=("Arial", 10, "bold"), anchor="n")
                    
                    # Atualizar posição para o próximo painel
                    x_atual += (largura_painel + dist_paineis) * escala
            
        except Exception as e:
            print(f"❌ Erro ao desenhar painéis especiais: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def calcular_altura_painel_especial(self, letra):
        """
        Calcula a altura específica de um painel especial baseada nas alturas configuradas
        """
        try:
            # Coletar alturas do painel
            alturas = []
            for i in range(1, 6):
                campo_nome = f"h{i}_{letra.upper()}"
                if hasattr(self, campo_nome):
                    campo = getattr(self, campo_nome)
                    try:
                        altura_str = campo.get().strip()
                        if altura_str:
                            if '+' in altura_str:
                                partes = altura_str.split('+')
                                altura = sum(float(parte.replace(',', '.')) for parte in partes)
                            else:
                                altura = float(altura_str.replace(',', '.'))
                            if altura > 0:
                                alturas.append(altura)
                    except (ValueError, AttributeError):
                        continue
            
            # Se não há alturas configuradas, usar altura padrão
            if not alturas:
                return 300.0
            
            # Retornar soma das alturas
            return sum(alturas)
            
        except Exception as e:
            print(f"❌ Erro ao calcular altura do painel {letra}: {str(e)}")
            return 300.0
    
    def painel_tem_dados(self, letra):
        """
        Verifica se um painel tem dados preenchidos (larguras > 0)
        """
        try:
            for i in range(1, 4):
                campo_nome = f"larg{i}_{letra}"
                if hasattr(self, campo_nome):
                    valor = getattr(self, campo_nome).get().strip()
                    if valor and float(valor.replace(',', '.')) > 0:
                        return True
            return False
        except:
            return False
    
    def obter_largura_painel(self, letra):
        """
        Obtém a largura total de um painel (soma das larguras 1, 2, 3)
        """
        try:
            largura_total = 0
            for i in range(1, 4):
                campo_nome = f"larg{i}_{letra}"
                if hasattr(self, campo_nome):
                    valor = getattr(self, campo_nome).get().strip()
                    if valor:
                        largura_total += float(valor.replace(',', '.'))
            return largura_total if largura_total > 0 else 100  # Largura padrão se não tiver dados
        except:
            return 100  # Largura padrão em caso de erro

    def _get_painel_dict(self, letra):
        """Retorna o dicionário de dados do painel atual para o preview"""
        painel = {}
        
        # Coletando alturas
        for i in range(1, 6):
            campo = getattr(self, f"h{i}_{letra}", None)
            painel[f"h{i}"] = campo.get().strip() if campo else "0"
        
        # Coletando larguras
        for j in range(1, 4):
            campo = getattr(self, f"larg{j}_{letra}", None)
            painel[f"larg{j}"] = campo.get().strip() if campo else "0"
            
        return painel

    def desenhar_painel(self, x, y, largura, altura_total, tipo_painel, escala):
        """Desenha um painel individual no canvas com todos os seus elementos"""
        try:
            # Coletar alturas do painel
            alturas = []
            for i in range(1, 6):
                campo_nome = f"h{i}_{tipo_painel.upper()}"
                if hasattr(self, campo_nome):
                    campo = getattr(self, campo_nome)
                    try:
                        altura_str = campo.get().strip()
                        if altura_str:
                            if '+' in altura_str:
                                partes = altura_str.split('+')
                                altura = sum(float(parte.replace(',', '.')) for parte in partes)
                            else:
                                altura = float(altura_str.replace(',', '.'))
                            if altura > 0:
                                alturas.append(altura)
                    except (ValueError, AttributeError):
                        continue

            # Coletar larguras do painel
            larguras = []
            for i in range(1, 4):
                campo_nome = f"larg{i}_{tipo_painel.upper()}"
                if hasattr(self, campo_nome):
                    campo = getattr(self, campo_nome)
                    try:
                        larg_str = campo.get().strip()
                        if larg_str and float(larg_str.replace(',', '.')) > 0:
                            larguras.append(float(larg_str.replace(',', '.')))
                    except (ValueError, AttributeError):
                        continue

            # Valores padrão se não houver dados
            larguras = larguras or [largura]
            alturas = alturas or [altura_total]

            # Calcular largura total do painel (soma das larguras individuais)
            # Para painéis A e B, usar a soma das larguras (larg1 + larg2 + larg3) em vez do parâmetro largura
            largura_total_painel = sum(larguras) if larguras else largura

            # Coletar dados da laje
            laje_altura = laje_posicao = 0
            
            if hasattr(self, f"laje_{tipo_painel.upper()}"):
                try:
                    laje_str = getattr(self, f"laje_{tipo_painel.upper()}").get().strip()
                    laje_altura = parse_valor_soma(laje_str) if laje_str else 0
                except (ValueError, AttributeError):
                    pass

            if hasattr(self, f"posicao_laje_{tipo_painel.upper()}"):
                try:
                    pos_str = getattr(self, f"posicao_laje_{tipo_painel.upper()}").get().strip()
                    laje_posicao = int(pos_str) if pos_str and pos_str.isdigit() else 0
                except (ValueError, AttributeError):
                    pass

            # Desenhar contorno do painel usando a largura total (soma das larguras individuais)
            # Isso garante que o retângulo corresponda às cotas horizontais
            self.canvas.create_rectangle(
                x, y - altura_total * escala,
                x + largura_total_painel * escala, y,
                outline="black",
                fill=""
            )

            # Desenhar cotas horizontais
            x_atual = x
            for j, larg in enumerate(larguras):
                if larg > 0:
                    self.canvas.create_line(
                        x_atual, y + 5,
                        x_atual + larg * escala, y + 5,
                        fill="black", arrow="both"
                    )
                    # Texto da cota horizontal
                    self.canvas.create_text(
                        x_atual + (larg * escala) / 2, y + 15 + 10 * escala,
                        text=f"{larg}",
                        angle=0
                    )
                    x_atual += larg * escala

            # Desenhar os elementos do painel (divisões, etc.) - SEM laje e SEM aberturas
            # As aberturas e lajes serão desenhadas por último pela função _atualizar_aberturas_lajes_canvas
            # Passar informações da laje para deslocar painéis acima dela
            # Usar largura_total_painel para garantir que os elementos internos usem a mesma largura do retângulo
            self._desenhar_elementos_painel_sem_laje(x, y, largura_total_painel, alturas, larguras, tipo_painel, escala, laje_altura, laje_posicao)
            
            # Desenhar checkboxes de hachura - DESABILITADO (movido para as abas dos painéis)
            # self._desenhar_checkboxes_hachura(x, y, largura, altura_total, tipo_painel, escala)

        except Exception as e:
            # Falha silenciosa no desenho não deve quebrar a aplicação
            pass

    def _desenhar_elementos_painel_sem_laje(self, x, y, largura, alturas, larguras, tipo_painel, escala, laje_altura=0, laje_posicao=0):
        """Desenha os elementos internos do painel SEM a laje (lajes, divisões, sarrafos)
        
        Args:
            laje_altura: Altura da laje (para deslocar painéis acima)
            laje_posicao: Posição da laje (0-5, onde 1-4 significa entre painéis)
        """
        try:
            y_atual = y

            def desenhar_painel_base(altura, painel_id=None):
                nonlocal y_atual
                self.canvas.create_rectangle(
                    x, y_atual - altura * escala,
                    x + largura * escala, y_atual,
                    fill=self.cores_paineis[tipo_painel],
                    outline="black"
                )
                
                # Desenhar hachura diretamente no painel se selecionada
                if painel_id:
                    self._desenhar_hachura_no_painel(x, y_atual - altura * escala, largura * escala, altura * escala, painel_id)
                # Cota vertical
                self.canvas.create_line(
                    x + largura * escala + 5, y_atual,
                    x + largura * escala + 5, y_atual - altura * escala,
                    fill="black", arrow="both"
                )
                # Texto da cota vertical
                self.canvas.create_text(
                    x + largura * escala + 15 + 10 * escala, y_atual - (altura * escala) / 2,
                    text=f"{altura}",
                    angle=0
                )

            def desenhar_divisoes_e_sarrafos(altura):
                x_atual = x
                for j, larg in enumerate(larguras):
                    if j > 0:  # Linha de divisão entre larguras
                        self.canvas.create_line(
                            x_atual, y_atual - altura * escala,
                            x_atual, y_atual,
                            fill=self.cores_paineis['divisao'],
                            width=2
                        )
                    x_atual += larg * escala

                # Desenhar sarrafos (se altura > 10cm)
                if altura > 10:
                    for pos in [7, largura - 7]:
                        self.canvas.create_line(
                            x + pos * escala, y_atual - altura * escala,
                            x + pos * escala, y_atual,
                            fill=self.cores_paineis['sarrafo'],
                            width=3
                        )

            # Desenhar todos os painéis, deslocando os que estão acima da laje
            for i, altura in enumerate(alturas):
                painel_id = f"{tipo_painel.lower()}_{i+1}"
                
                # Calcular deslocamento: se a laje está entre painéis e este painel está acima dela
                deslocamento = 0
                if laje_altura > 0:
                    if laje_posicao == 0:
                        # Posição 0: laje na base, TODOS os painéis são empurrados para cima
                        deslocamento = laje_altura * escala
                    elif laje_posicao > 0 and laje_posicao < 5:
                        # laje_posicao 1 = entre h1 e h2, então h2, h3, h4, h5 são deslocados
                        # laje_posicao 2 = entre h2 e h3, então h3, h4, h5 são deslocados
                        # laje_posicao 3 = entre h3 e h4, então h4, h5 são deslocados
                        # laje_posicao 4 = entre h4 e h5, então h5 é deslocado
                        # i começa em 0, então h1=i=0, h2=i=1, etc.
                        if i >= laje_posicao:  # Este painel está acima da laje
                            # O deslocamento é a altura da laje (para empurrar o painel para cima)
                            deslocamento = laje_altura * escala
                
                # Aplicar deslocamento ao y_atual antes de desenhar
                # O deslocamento empurra os painéis acima da laje para cima
                y_atual_deslocado = y_atual - deslocamento
                
                # Desenhar painel na posição deslocada
                self.canvas.create_rectangle(
                    x, y_atual_deslocado - altura * escala,
                    x + largura * escala, y_atual_deslocado,
                    fill=self.cores_paineis[tipo_painel],
                    outline="black"
                )
                
                # Desenhar hachura diretamente no painel se selecionada
                if painel_id:
                    self._desenhar_hachura_no_painel(x, y_atual_deslocado - altura * escala, largura * escala, altura * escala, painel_id)
                
                # Cota vertical
                self.canvas.create_line(
                    x + largura * escala + 5, y_atual_deslocado,
                    x + largura * escala + 5, y_atual_deslocado - altura * escala,
                    fill="black", arrow="both"
                )
                # Texto da cota vertical
                self.canvas.create_text(
                    x + largura * escala + 15 + 10 * escala, y_atual_deslocado - (altura * escala) / 2,
                    text=f"{altura}",
                    angle=0
                )
                
                # Desenhar divisões e sarrafos
                x_atual_div = x
                for j, larg in enumerate(larguras):
                    if j > 0:  # Linha de divisão entre larguras
                        self.canvas.create_line(
                            x_atual_div, y_atual_deslocado - altura * escala,
                            x_atual_div, y_atual_deslocado,
                            fill=self.cores_paineis['divisao'],
                            width=2
                        )
                    x_atual_div += larg * escala

                # Desenhar sarrafos (se altura > 10cm)
                if altura > 10:
                    for pos in [7, largura - 7]:
                        self.canvas.create_line(
                            x + pos * escala, y_atual_deslocado - altura * escala,
                            x + pos * escala, y_atual_deslocado,
                            fill=self.cores_paineis['sarrafo'],
                            width=3
                        )
                
                # Atualizar y_atual (sem deslocamento para manter a lógica de posicionamento)
                y_atual -= altura * escala

            # Linhas tracejadas para campos com soma
            self._desenhar_linhas_soma_campos(x, y, largura, tipo_painel, escala)

        except Exception as e:
            pass

    def _desenhar_laje_final(self, x, y, largura, alturas, laje_altura, laje_posicao, tipo_painel, escala):
        """Desenha a laje na posição especificada baseada em laje_posicao (0-5)
        
        Quando a laje está entre painéis (posição 1-4), os painéis acima dela já foram
        deslocados pela altura da laje, então a laje é desenhada na posição correta.
        """
        try:
            altura_paineis = sum(alturas)
            
            # Calcular posição Y da laje baseada em laje_posicao
            # laje_posicao: 0 = base (fundo), 1-4 = entre painéis, 5+ = topo
            y_top_laje = None
            y_bottom = None
            
            if laje_posicao == 0:
                # Posição 0: na base (fundo do painel)
                y_bottom = y  # Base do painel
                y_top_laje = y_bottom - laje_altura * escala
            elif laje_posicao >= len(alturas) + 1 or laje_posicao >= 5:
                # Posição 5 ou maior: no topo (acima de todos os painéis)
                # Os painéis acima não foram deslocados, então calcular normalmente
                y_top_painel = y - altura_paineis * escala
                y_top_laje = y_top_painel - laje_altura * escala
                y_bottom = y_top_laje + laje_altura * escala
            else:
                # Posição 1-4: entre os painéis
                # Calcular altura acumulada até a posição anterior
                altura_acumulada = 0
                for i in range(laje_posicao):
                    if i < len(alturas):
                        altura_acumulada += alturas[i]
                
                # A laje fica acima da altura acumulada
                # IMPORTANTE: Os painéis acima da laje (i >= laje_posicao) foram deslocados
                # para cima pela altura da laje, então a laje deve ser desenhada na posição
                # onde os painéis acima começam (já considerando o deslocamento deles)
                # A laje fica logo acima dos painéis abaixo dela, e os painéis acima ficam
                # empurrados para cima pela altura da laje
                y_top_laje = y - altura_acumulada * escala - laje_altura * escala
                y_bottom = y_top_laje + laje_altura * escala
            
            # Desenhar laje como retângulo marrom
            self.canvas.create_rectangle(
                x, y_top_laje,
                x + largura * escala, y_bottom,
                fill=self.cores_paineis['laje'],
                outline="black"
            )
            
            # Desenhar cota vertical para a laje (mesma disposição dos painéis)
            self.canvas.create_line(
                x + largura * escala + 5, y_bottom,
                x + largura * escala + 5, y_top_laje,
                fill="black", arrow="both"
            )
            # Texto da cota vertical da laje
            self.canvas.create_text(
                x + largura * escala + 15 + 10 * escala, y_top_laje + laje_altura * escala / 2,
                text=f"{laje_altura}",
                angle=0
            )
        except Exception as e:
            pass

    def _desenhar_elementos_painel(self, x, y, largura, alturas, larguras, laje_altura, laje_posicao, tipo_painel, escala, altura_total):
        """Desenha os elementos internos do painel (lajes, divisões, sarrafos)"""
        try:
            y_atual = y
            altura_paineis = sum(alturas)

            def desenhar_painel_base(altura, painel_id=None):
                nonlocal y_atual
                self.canvas.create_rectangle(
                    x, y_atual - altura * escala,
                    x + largura * escala, y_atual,
                    fill=self.cores_paineis[tipo_painel],
                    outline="black"
                )
                
                # Desenhar hachura diretamente no painel se selecionada
                if painel_id:
                    self._desenhar_hachura_no_painel(x, y_atual - altura * escala, largura * escala, altura * escala, painel_id)
                # Cota vertical
                self.canvas.create_line(
                    x + largura * escala + 5, y_atual,
                    x + largura * escala + 5, y_atual - altura * escala,
                    fill="black", arrow="both"
                )
                # Texto da cota vertical
                self.canvas.create_text(
                    x + largura * escala + 15 + 10 * escala, y_atual - (altura * escala) / 2,
                    text=f"{altura}",
                    angle=0
                )

            def desenhar_divisoes_e_sarrafos(altura):
                x_atual = x
                for j, larg in enumerate(larguras):
                    if j > 0:  # Linha de divisão entre larguras
                        self.canvas.create_line(
                            x_atual, y_atual - altura * escala,
                            x_atual, y_atual,
                            fill=self.cores_paineis['divisao'],
                            width=2
                        )
                    x_atual += larg * escala

                # Desenhar sarrafos (se altura > 10cm)
                if altura > 10:
                    for pos in [7, largura - 7]:
                        self.canvas.create_line(
                            x + pos * escala, y_atual - altura * escala,
                            x + pos * escala, y_atual,
                            fill=self.cores_paineis['sarrafo'],
                            width=3
                        )

            def desenhar_laje_retangulo(y_top_local: float):
                """Desenha a laje como retângulo marrom a partir de y_top_local (topo) para baixo."""
                y_bottom = y_top_local + laje_altura * escala
                self.canvas.create_rectangle(
                    x, y_top_local,
                    x + largura * escala, y_bottom,
                    fill=self.cores_paineis['laje'],
                    outline="black"
                )

            # Primeiro desenhar todos os painéis normalmente
                for i, altura in enumerate(alturas):
                    painel_id = f"{tipo_painel.lower()}_{i+1}"
                    desenhar_painel_base(altura, painel_id)
                    desenhar_divisoes_e_sarrafos(altura)
                    y_atual -= altura * escala

            # Se houver espaço extra, indicar com linha tracejada
                if altura_total > altura_paineis + laje_altura:
                    altura_extra = altura_total - (altura_paineis + laje_altura)
                    self.canvas.create_line(
                        x, y_atual - altura_extra * escala,
                        x + largura * escala, y_atual - altura_extra * escala,
                        fill="black", dash=(4, 4)
                    )
                    y_atual -= altura_extra * escala

            # Desenhar laje por último (por cima dos painéis) se houver
            if laje_altura > 0:
                # CORRIGIDO: A laje deve ficar no TOPO do painel (acima do painel)
                y_top_painel = y - altura_paineis * escala
                y_top_laje = y_top_painel - laje_altura * escala  # Laje ACIMA do painel

                # Desenhar laje como retângulo marrom por cima dos painéis
                desenhar_laje_retangulo(y_top_laje)

            # Linhas tracejadas para campos com soma
            self._desenhar_linhas_soma_campos(x, y, largura, tipo_painel, escala)

        except Exception as e:
            pass

    def _desenhar_linhas_soma_campos(self, x, y, largura, tipo_painel, escala):
        """Desenha linhas tracejadas para campos que têm soma (+)"""
        try:
            for i in range(1, 6):
                campo_nome = f"h{i}_{tipo_painel.upper()}"
                if hasattr(self, campo_nome):
                    campo = getattr(self, campo_nome)
                    altura_str = campo.get().strip()
                    
                    if '+' in altura_str:
                        partes = altura_str.split('+')
                        if len(partes) == 2:
                            parte1 = float(partes[0].replace(',', '.'))
                            self.canvas.create_line(
                                x, y - parte1 * escala,
                                x + largura * escala, y - parte1 * escala,
                                fill="red", dash=(2, 2)
                            )
        except Exception as e:
            pass

    def _desenhar_hachura_no_painel(self, x, y, largura, altura, painel_id):
        """Desenha hachura diretamente no painel baseado na seleção do radiobutton"""
        try:
            # Verificar se a variável de controle do radiobutton existe
            hachura_var_name = f"hachura_{painel_id}"
            
            if hasattr(self, hachura_var_name):
                hachura_var = getattr(self, hachura_var_name)
                tipo_hachura = hachura_var.get()
                
                # Desenhar hachura baseada na seleção do radiobutton
                if tipo_hachura == "1":  # Diagonal
                    self._desenhar_hachura_diagonal_no_painel(x, y, largura, altura, painel_id)
                elif tipo_hachura == "2":  # Xadrez
                    self._desenhar_hachura_xadrez_no_painel(x, y, largura, altura, painel_id)
        except Exception as e:
            pass

    def _desenhar_hachura_diagonal_no_painel(self, x, y, largura, altura, painel_id):
        """Desenha hachura diagonal diretamente no painel"""
        try:
            # Parâmetros da hachura mais densa e com ângulo pronunciado
            espacamento = 4  # Espaçamento ainda menor para maior densidade
            num_lines = max(12, int((largura + altura) / espacamento))
            
            # Desenhar linhas diagonais com ângulo mais pronunciado
            for i in range(num_lines):
                # Linha diagonal com ângulo de 45 graus
                x1 = x + (i * espacamento)
                y1 = y
                x2 = x + (i * espacamento) + altura  # Diagonal de 45 graus
                y2 = y + altura
                
                # Garantir que as linhas ficam dentro do painel
                if x2 > x + largura:
                    x2 = x + largura
                if x1 > x + largura:
                    x1 = x + largura
                
                # Linha principal mais escura
                self.canvas.create_line(x1, y1, x2, y2, 
                                      fill="black", width=1.2,
                                      tags=[f'hachura_{painel_id}', f'hachura_diagonal_{painel_id}'])
                
                # Linha paralela para densidade
                if i < num_lines - 1:
                    x1_par = x + ((i + 0.5) * espacamento)
                    y1_par = y
                    x2_par = x + ((i + 0.5) * espacamento) + altura
                    y2_par = y + altura
                    
                    # Garantir que as linhas ficam dentro do painel
                    if x2_par > x + largura:
                        x2_par = x + largura
                    if x1_par > x + largura:
                        x1_par = x + largura
                    
                    self.canvas.create_line(x1_par, y1_par, x2_par, y2_par, 
                                          fill="gray", width=0.8,
                                          tags=[f'hachura_{painel_id}', f'hachura_diagonal_{painel_id}'])
        except Exception as e:
            pass

    def _desenhar_hachura_xadrez_no_painel(self, x, y, largura, altura, painel_id):
        """Desenha hachura xadrez diretamente no painel"""
        try:
            # Parâmetros da hachura com quadrados menores
            espacamento = 8  # Espaçamento menor para quadrados menores
            num_cols = int(largura / espacamento)
            num_rows = int(altura / espacamento)
            
            # Desenhar linhas verticais PRETAS mais grossas
            for i in range(num_cols + 1):
                x_line = x + (i * espacamento)
                if x_line <= x + largura:
                    self.canvas.create_line(x_line, y, x_line, y + altura, 
                                          fill="black", width=1.2,
                                          tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
            
            # Desenhar linhas horizontais PRETAS mais grossas
            for i in range(num_rows + 1):
                y_line = y + (i * espacamento)
                if y_line <= y + altura:
                    self.canvas.create_line(x, y_line, x + largura, y_line, 
                                          fill="black", width=1.2,
                                          tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
            
            # Preencher quadrados alternados para efeito xadrez mais contrastado
            for i in range(num_cols):
                for j in range(num_rows):
                    if (i + j) % 2 == 0:  # Quadrados pares
                        x1 = x + (i * espacamento)
                        y1 = y + (j * espacamento)
                        x2 = x + ((i + 1) * espacamento)
                        y2 = y + ((j + 1) * espacamento)
                        
                        # Garantir que o quadrado não sai do painel
                        if x2 > x + largura:
                            x2 = x + largura
                        if y2 > y + altura:
                            y2 = y + altura
                        if x1 < x:
                            x1 = x
                        if y1 < y:
                            y1 = y
                        
                        # Preencher quadrado com cor mais escura
                        self.canvas.create_rectangle(x1, y1, x2, y2, 
                                                   fill="darkgray", outline="",
                                                   tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
        except Exception as e:
            pass

    def desenhar_aberturas(self, x, y, largura, altura_total, tipo_painel, escala):
        """Desenha as aberturas no painel"""
        try:
            print(f"DEBUG ABERTURAS: Desenhando aberturas para painel {tipo_painel}")
            # Painéis A, B, C, D, E e F podem ter aberturas
            if tipo_painel.lower() not in ['a', 'b', 'c', 'd', 'e', 'f']:
                print(f"DEBUG ABERTURAS: Painel {tipo_painel} não tem aberturas")
                return

            aberturas = [('esq1', 'esquerda'), ('esq2', 'esquerda'),
                         ('dir1', 'direita'), ('dir2', 'direita')]

            # Obter altura da laje
            laje_altura = 0
            campo_laje = getattr(self, f"laje_{tipo_painel.upper()}")
            try:
                laje_str = campo_laje.get().strip()
                if laje_str:
                    laje_altura = parse_valor_soma(laje_str)
            except (ValueError, AttributeError):
                pass

            # Coletar alturas dos painéis
            alturas = []
            for i in range(1, 6):
                campo_nome = f"h{i}_{tipo_painel.upper()}"
                if hasattr(self, campo_nome):
                    campo = getattr(self, campo_nome)
                    try:
                        altura_str = campo.get().strip()
                        if altura_str and parse_valor_soma(altura_str) > 0:
                            alturas.append(parse_valor_soma(altura_str))
                    except (ValueError, AttributeError):
                        continue

            # Desenhar cada abertura
            for abertura_id, lado in aberturas:
                prefixo = abertura_id[:3]  # 'esq' ou 'dir'
                numero = abertura_id[-1]   # '1' ou '2'

                # Nomes dos campos
                campos = {
                    'dist': f"dist_{prefixo}_{numero}_{tipo_painel.upper()}",
                    'prof': f"prof_{prefixo}_{numero}_{tipo_painel.upper()}",
                    'larg': f"larg_{prefixo}_{numero}_{tipo_painel.upper()}",
                    'pos': f"pos_{prefixo}_{numero}_{tipo_painel.upper()}"
                }

                # Verificar se todos os campos existem
                if not all(hasattr(self, nome) for nome in campos.values()):
                    continue

                try:
                    # Obter valores dos campos
                    valores = {k: getattr(self, v).get().strip() for k, v in campos.items()}
                    
                    # Verificar se os campos obrigatórios estão preenchidos
                    if not all(valores[k] for k in ['prof', 'larg', 'pos']):
                        print(f"DEBUG ABERTURAS: Abertura {abertura_id} não tem campos obrigatórios preenchidos: {valores}")
                        continue

                    # Converter valores
                    dist_val = parse_valor_soma(valores['dist']) if valores['dist'] else 0
                    prof_val = parse_valor_soma(valores['prof'])
                    larg_val = parse_valor_soma(valores['larg'])
                    pos_val = float(valores['pos'])  # Posição a partir do topo

                    if prof_val <= 0 or larg_val <= 0:
                        continue

                    # Calcular posição da abertura
                    x1 = x + (dist_val if lado == 'esquerda' else largura - dist_val - larg_val) * escala
                    x2 = x1 + larg_val * escala

                    y_base = y - (sum(alturas) + laje_altura) * escala
                    y1 = y_base + pos_val * escala  # Deslocamento a partir do topo
                    y2 = y1 + prof_val * escala

                    # Desenhar retângulo da abertura (marrom sólido)
                    self.canvas.create_rectangle(
                        x1, y1, x2, y2,
                                              fill=self.cores_paineis['abertura'],
                        outline="black"
                    )

                except Exception as e:
                    continue

        except Exception as e:
            pass

    def desenhar_hachura_abertura(self, x1, y1, x2, y2):
        """Compatibilidade: não desenha mais hachuras nas aberturas."""
        return
    
    def _atualizar_aberturas_lajes_canvas(self, x_a, x_b, x_c, x_d, y_inicial, comprimento, largura, altura, escala):
        """
        Atualiza e desenha todas as aberturas e lajes de todos os painéis no canvas.
        Esta função deve ser a ÚLTIMA função do canvas a ser chamada para garantir
        que todas as aberturas e lajes sejam atualizadas corretamente sobre todos os painéis.
        
        Args:
            x_a, x_b, x_c, x_d: Posições X dos painéis A, B, C, D
            y_inicial: Posição Y inicial (base dos painéis)
            comprimento: Comprimento do pilar
            largura: Largura do pilar
            altura: Altura total do pilar
            escala: Escala de desenho
        """
        try:
            # Atualizar aberturas e lajes para cada painel
            paineis = [
                ('a', x_a, comprimento),
                ('b', x_b, comprimento),
                ('c', x_c, largura),
                ('d', x_d, largura)
            ]
            
            # Desenhar lajes e aberturas para cada painel
            for tipo_painel, x_pos, largura_painel in paineis:
                # Coletar alturas do painel
                alturas = []
                for i in range(1, 6):
                    campo_nome = f"h{i}_{tipo_painel.upper()}"
                    if hasattr(self, campo_nome):
                        campo = getattr(self, campo_nome)
                        try:
                            altura_str = campo.get().strip()
                            if altura_str:
                                if '+' in altura_str:
                                    partes = altura_str.split('+')
                                    altura = sum(float(parte.replace(',', '.')) for parte in partes)
                                else:
                                    altura = float(altura_str.replace(',', '.'))
                                if altura > 0:
                                    alturas.append(altura)
                        except (ValueError, AttributeError):
                            continue
                
                # Valores padrão se não houver dados
                if not alturas:
                    alturas = [altura]
                
                # Calcular altura total do painel (soma das alturas)
                altura_total_painel = sum(alturas)
                
                # Para painéis A e B, calcular largura total (soma das larguras individuais)
                # em vez de usar o parâmetro largura_painel (que é o comprimento)
                if tipo_painel.lower() in ['a', 'b']:
                    larguras_ab = []
                    for i in range(1, 4):
                        campo_nome = f"larg{i}_{tipo_painel.upper()}"
                        if hasattr(self, campo_nome):
                            campo = getattr(self, campo_nome)
                            try:
                                larg_str = campo.get().strip()
                                if larg_str and float(larg_str.replace(',', '.')) > 0:
                                    larguras_ab.append(float(larg_str.replace(',', '.')))
                            except (ValueError, AttributeError):
                                continue
                    # Usar soma das larguras se disponível, senão usar largura_painel
                    largura_painel = sum(larguras_ab) if larguras_ab else largura_painel
                
                # Coletar dados da laje
                laje_altura = laje_posicao = 0
                
                if hasattr(self, f"laje_{tipo_painel.upper()}"):
                    try:
                        laje_str = getattr(self, f"laje_{tipo_painel.upper()}").get().strip()
                        laje_altura = parse_valor_soma(laje_str) if laje_str else 0
                    except (ValueError, AttributeError):
                        pass

                if hasattr(self, f"posicao_laje_{tipo_painel.upper()}"):
                    try:
                        pos_str = getattr(self, f"posicao_laje_{tipo_painel.upper()}").get().strip()
                        laje_posicao = int(pos_str) if pos_str and pos_str.isdigit() else 0
                    except (ValueError, AttributeError):
                        pass
                
                # Desenhar laje ANTES das aberturas
                if laje_altura > 0:
                    self._desenhar_laje_final(x_pos, y_inicial, largura_painel, alturas, laje_altura, laje_posicao, tipo_painel, escala)
                
                # Desenhar aberturas POR CIMA da laje
                self.desenhar_aberturas(x_pos, y_inicial, largura_painel, altura_total_painel, tipo_painel, escala)
            
            # Atualizar também painéis especiais (E, F, G, H) se existirem
            if hasattr(self, 'ativar_pilar_especial') and self.ativar_pilar_especial.get():
                # Calcular posições dos painéis especiais
                dist_paineis = 250
                x_atual = x_d + (largura + dist_paineis) * escala
                paineis_especiais = ['E', 'F', 'G', 'H']
                
                for letra in paineis_especiais:
                    if self.painel_tem_dados(letra):
                        largura_painel = self.obter_largura_painel(letra)
                        altura_painel = self.calcular_altura_painel_especial(letra)
                        
                        # Coletar alturas do painel especial
                        alturas_especial = []
                        for i in range(1, 6):
                            campo_nome = f"h{i}_{letra}"
                            if hasattr(self, campo_nome):
                                campo = getattr(self, campo_nome)
                                try:
                                    altura_str = campo.get().strip()
                                    if altura_str:
                                        if '+' in altura_str:
                                            partes = altura_str.split('+')
                                            altura = sum(float(parte.replace(',', '.')) for parte in partes)
                                        else:
                                            altura = float(altura_str.replace(',', '.'))
                                        if altura > 0:
                                            alturas_especial.append(altura)
                                except (ValueError, AttributeError):
                                    continue
                        
                        if not alturas_especial:
                            alturas_especial = [altura_painel]
                        
                        # Coletar dados da laje do painel especial
                        laje_altura_especial = laje_posicao_especial = 0
                        
                        if hasattr(self, f"laje_{letra}"):
                            try:
                                laje_str = getattr(self, f"laje_{letra}").get().strip()
                                laje_altura_especial = parse_valor_soma(laje_str) if laje_str else 0
                            except (ValueError, AttributeError):
                                pass

                        if hasattr(self, f"posicao_laje_{letra}"):
                            try:
                                pos_str = getattr(self, f"posicao_laje_{letra}").get().strip()
                                laje_posicao_especial = int(pos_str) if pos_str and pos_str.isdigit() else 0
                            except (ValueError, AttributeError):
                                pass
                        
                        # Desenhar laje do painel especial
                        if laje_altura_especial > 0:
                            self._desenhar_laje_final(x_atual, y_inicial, largura_painel, alturas_especial, laje_altura_especial, laje_posicao_especial, letra.lower(), escala)
                        
                        # Desenhar aberturas do painel especial (se aplicável)
                        self.desenhar_aberturas(x_atual, y_inicial, largura_painel, altura_painel, letra.lower(), escala)
                        
                        # Atualizar posição para o próximo painel
                        x_atual += (largura_painel + dist_paineis) * escala
        
        except Exception as e:
            # Falha silenciosa não deve quebrar a aplicação
            pass


# ===== FUNÇÕES UTILITÁRIAS ADICIONAIS =====

def center_window(window):
    """Centraliza uma janela na tela"""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')


class UtilsMixin:
    """Mixin com funções utilitárias menores para PilarAnalyzer"""
    
    def center_window(self):
        """Centraliza a janela do PilarAnalyzer na tela"""
        center_window(self)
    
    def calcular_altura_e_atualizar(self, event):
        """Calcula altura e atualiza preview"""
        self.atualizar_altura(event)
        self.atualizar_preview(event)
    
    def atualizar_altura(self, event=None):
        """Calcula altura baseado nos níveis de saída, chegada e diferencial"""
        try:
            nivel_saida_str = self.nivel_saida.get().strip()
            nivel_chegada_str = self.nivel_chegada.get().strip()
            nivel_diferencial_str = self.nivel_diferencial.get().strip()
            
            if not nivel_saida_str or not nivel_chegada_str:
                return None
                
            nivel_saida = float(nivel_saida_str.replace(',', '.'))
            nivel_chegada = float(nivel_chegada_str.replace(',', '.'))
            nivel_diferencial = float(nivel_diferencial_str.replace(',', '.')) if nivel_diferencial_str else 0
            
            altura = (nivel_chegada - nivel_saida) * 100 + nivel_diferencial
            
            self.altura.delete(0, tk.END)
            try:
                from funcoes_auxiliares_3 import formatar_valor_numerico
            except ImportError:
                def formatar_valor_numerico(valor, casas_decimais=2):
                    if isinstance(valor, (int, float)):
                        return f"{valor:.{casas_decimais}f}".replace('.', ',')
                    return str(valor)
            
            valor_formatado = formatar_valor_numerico(altura)
            self.altura.insert(0, valor_formatado)
            
            self.calcular_alturas_painel()
            
            # Atualizar alturas dos painéis especiais se pilar especial estiver ativo
            if hasattr(self, 'ativar_pilar_especial') and self.ativar_pilar_especial.get():
                self.calcular_alturas_todos_paineis_especiais_completo()
            
            # Sincronizar alturas dos detalhes (aplicar desconto de laje se checkbox estiver ativo)
            if hasattr(self, 'sincronizar_altura_detalhes'):
                self.sincronizar_altura_detalhes()
            
            return altura
            
        except ValueError as e:
            pass
        except Exception as e:
            pass
        return None

    def _desenhar_hachura_integrada(self, x, y, largura, altura_total, tipo_painel, escala):
        """Desenha hachura diretamente dentro do painel baseado nos checkboxes"""
        try:
            # Obter informações dos painéis individuais
            paineis_info = self._get_paineis_individuais(tipo_painel, x, y, largura, altura_total, escala)
            
            for i, painel_info in enumerate(paineis_info):
                painel_x = painel_info['x']
                painel_y = painel_info['y']
                painel_largura = painel_info['largura']
                painel_altura = painel_info['altura']
                
                # Identificador único para cada painel individual
                painel_id = f"{tipo_painel.lower()}_{i+1}"
                
                # Verificar se a variável de controle do radiobutton existe
                hachura_var_name = f"hachura_{painel_id}"
                
                if hasattr(self, hachura_var_name):
                    hachura_var = getattr(self, hachura_var_name)
                    tipo_hachura = hachura_var.get()
                    
                    # Desenhar hachura baseada na seleção do radiobutton
                    if tipo_hachura == "1":  # Diagonal
                        self._desenhar_hachura_diagonal_integrada(painel_x, painel_y, painel_largura, painel_altura, painel_id)
                    elif tipo_hachura == "2":  # Xadrez
                        self._desenhar_hachura_xadrez_integrada(painel_x, painel_y, painel_largura, painel_altura, painel_id)
                        
        except Exception as e:
            pass

    def _desenhar_hachura_diagonal_integrada(self, x, y, largura, altura, painel_id):
        """Desenha hachura diagonal integrada no painel"""
        try:
            # Limpar hachura anterior
            self._limpar_hachuras_painel_individual(painel_id)
            
            # Parâmetros da hachura mais harmoniosos
            espacamento = 8  # Maior espaçamento para visual mais limpo
            num_lines = max(5, int(largura / espacamento))
            
            # Coordenadas corretas do painel (y é a base, altura vai para cima)
            y_top = y - altura
            y_bottom = y
            
            # Desenhar linhas diagonais mais suaves
            for i in range(num_lines):
                x1 = x + (i * espacamento)
                y1 = y_top
                x2 = x + largura
                y2 = y_top + (largura - (i * espacamento))
                
                # Garantir que as linhas ficam dentro do painel
                if y2 > y_bottom:
                    y2 = y_bottom
                if x1 > x + largura:
                    x1 = x + largura
                
                # Linha principal mais suave
                self.canvas.create_line(x1, y1, x2, y2, 
                                      fill="gray", width=1.0,  # Cor mais suave e linha mais visível
                                      tags=[f'hachura_{painel_id}', f'hachura_diagonal_{painel_id}'])
                
                # Linha paralela para densidade
                if i < num_lines - 1:
                    x1_par = x + ((i + 0.5) * espacamento)
                    y1_par = y_top
                    x2_par = x + largura
                    y2_par = y_top + (largura - ((i + 0.5) * espacamento))
                    
                    # Garantir que as linhas ficam dentro do painel
                    if y2_par > y_bottom:
                        y2_par = y_bottom
                    if x1_par > x + largura:
                        x1_par = x + largura
                    
                    self.canvas.create_line(x1_par, y1_par, x2_par, y2_par, 
                                          fill="lightgray", width=0.5,  # Cor mais clara
                                          tags=[f'hachura_{painel_id}', f'hachura_diagonal_{painel_id}'])
        except Exception as e:
            pass

    def _desenhar_hachura_xadrez_integrada(self, x, y, largura, altura, painel_id):
        """Desenha hachura xadrez integrada no painel"""
        try:
            # Limpar hachura anterior
            self._limpar_hachuras_painel_individual(painel_id)
            
            # Parâmetros da hachura mais harmoniosos
            espacamento = 12  # Maior espaçamento para visual mais limpo
            num_cols = int(largura / espacamento)
            num_rows = int(altura / espacamento)
            
            # Coordenadas corretas do painel (y é a base, altura vai para cima)
            y_top = y - altura
            y_bottom = y
            
            # Desenhar linhas verticais mais suaves
            for i in range(num_cols + 1):
                x_line = x + (i * espacamento)
                # Garantir que a linha não sai do painel
                if x_line <= x + largura:
                    self.canvas.create_line(x_line, y_top, x_line, y_bottom, 
                                          fill="gray", width=0.8,  # Cor mais suave
                                          tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
            
            # Desenhar linhas horizontais mais suaves
            for i in range(num_rows + 1):
                y_line = y_top + (i * espacamento)
                # Garantir que a linha não sai do painel
                if y_line <= y_bottom:
                    self.canvas.create_line(x, y_line, x + largura, y_line, 
                                          fill="gray", width=0.8,  # Cor mais suave
                                          tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
            
            # Preencher quadrados alternados para efeito xadrez
            for i in range(num_cols):
                for j in range(num_rows):
                    if (i + j) % 2 == 0:  # Quadrados pares
                        x1 = x + (i * espacamento)
                        y1 = y_top + (j * espacamento)
                        x2 = x + ((i + 1) * espacamento)
                        y2 = y_top + ((j + 1) * espacamento)
                        
                        # Garantir que o quadrado não sai do painel
                        if x2 > x + largura:
                            x2 = x + largura
                        if y2 > y_bottom:
                            y2 = y_bottom
                        if x1 < x:
                            x1 = x
                        if y1 < y_top:
                            y1 = y_top
                        
                        # Preencher quadrado com cor suave
                        self.canvas.create_rectangle(x1, y1, x2, y2, 
                                                   fill="lightgray", outline="",
                                                   tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
        except Exception as e:
            pass

    def _desenhar_checkboxes_hachura(self, x, y, largura, altura_total, tipo_painel, escala):
        """Desenha os checkboxes de hachura para cada painel individual"""
        try:
            # Obter informações dos painéis individuais
            paineis_info = self._get_paineis_individuais(tipo_painel, x, y, largura, altura_total, escala)
            
            # Calcular espaçamento entre painéis (mais compacto)
            espacamento_entre_paineis = 1 * escala  # Distância pequena entre painéis (compacto, sem sumir)
            
            for i, painel_info in enumerate(paineis_info):
                painel_x = painel_info['x']
                painel_y = painel_info['y']
                painel_largura = painel_info['largura']
                painel_altura = painel_info['altura']
                
                # Posição dos checkboxes: ajustada para ficar mais compacta
                checkbox_y = painel_y - 10  # 10cm ACIMA da base do painel (desceu 30 da posição anterior)
                checkbox_x_centro = painel_x + painel_largura / 2 + 60  # Centro do painel, 40cm para direita (compacto, visível)
                
                # Identificador único para cada painel individual
                painel_id = f"{tipo_painel.lower()}_{i+1}"
                
                # Criar variável de controle única para radiobuttons se não existir
                hachura_var_name = f'hachura_{painel_id}'
                if not hasattr(self, hachura_var_name):
                    setattr(self, hachura_var_name, tk.StringVar(value="0"))  # 0 = nenhum, 1 = diagonal, 2 = xadrez
                
                hachura_var = getattr(self, hachura_var_name)
                
                # Função para aplicar hachura baseada na seleção
                def aplicar_hachura_radio():
                    self._aplicar_hachura_painel_individual(painel_id, painel_x, painel_y, painel_largura, painel_altura, int(hachura_var.get()))
                    # Atualizar preview após mudança na hachura
                    self.atualizar_preview()
                
                # Criar um frame container para agrupar os radiobuttons
                radio_frame = tk.Frame(self.canvas, bg="lightgray", relief="raised", bd=1)
                
                # Radiobutton 0 (nenhuma hachura) - dentro do frame
                rb0 = tk.Radiobutton(radio_frame, text="0", variable=hachura_var, value="0",
                                   command=aplicar_hachura_radio,
                                   bg="lightgray", font=("Arial", 5), width=1, height=1)
                rb0.pack(side=tk.LEFT, padx=1, pady=0)
                
                # Radiobutton 1 (hachura diagonal) - dentro do frame
                rb1 = tk.Radiobutton(radio_frame, text="1", variable=hachura_var, value="1",
                                   command=aplicar_hachura_radio,
                                   bg="lightgray", font=("Arial", 5), width=1, height=1)
                rb1.pack(side=tk.LEFT, padx=1, pady=0)
                
                # Radiobutton 2 (hachura xadrez) - dentro do frame
                rb2 = tk.Radiobutton(radio_frame, text="2", variable=hachura_var, value="2",
                                   command=aplicar_hachura_radio,
                                   bg="lightgray", font=("Arial", 5), width=1, height=1)
                rb2.pack(side=tk.LEFT, padx=1, pady=0)
                
                # Posicionar o frame container no canvas
                self.canvas.create_window(checkbox_x_centro, checkbox_y, window=radio_frame, anchor="center")
                
        except Exception as e:
            pass

    def _get_paineis_individuais(self, tipo_painel, x, y, largura, altura_total, escala):
        """Obtém informações dos painéis individuais baseado no tipo"""
        try:
            paineis_info = []
            
            # Coletar alturas do painel
            alturas = []
            for i in range(1, 6):
                campo_nome = f"h{i}_{tipo_painel.upper()}"
                if hasattr(self, campo_nome):
                    campo = getattr(self, campo_nome)
                    try:
                        altura_str = campo.get().strip()
                        if altura_str:
                            if '+' in altura_str:
                                partes = altura_str.split('+')
                                altura = sum(float(parte.replace(',', '.')) for parte in partes)
                            else:
                                altura = float(altura_str.replace(',', '.'))
                            if altura > 0:
                                alturas.append(altura)
                    except (ValueError, AttributeError):
                        continue

            # Coletar larguras do painel
            larguras = []
            for i in range(1, 4):
                campo_nome = f"larg{i}_{tipo_painel.upper()}"
                if hasattr(self, campo_nome):
                    campo = getattr(self, campo_nome)
                    try:
                        larg_str = campo.get().strip()
                        if larg_str and float(larg_str.replace(',', '.')) > 0:
                            larguras.append(float(larg_str.replace(',', '.')))
                    except (ValueError, AttributeError):
                        continue

            # Valores padrão se não houver dados
            larguras = larguras or [largura]
            alturas = alturas or [altura_total]

            # Calcular posições dos painéis individuais com espaçamento
            y_atual = y
            espacamento_horizontal = 0.5 * escala  # Espaçamento mínimo entre painéis horizontais (compacto, visível)
            
            for i, altura in enumerate(alturas):
                x_atual = x
                for j, larg in enumerate(larguras):
                    paineis_info.append({
                        'x': x_atual,
                        'y': y_atual,
                        'largura': larg,
                        'altura': altura,
                        'escala': escala
                    })
                    x_atual += larg * escala + espacamento_horizontal  # Adicionar espaçamento
                y_atual -= altura * escala

            return paineis_info
            
        except Exception as e:
            return []

    def _aplicar_hachura_painel_individual(self, painel_id, x, y, largura, altura, tipo_hachura):
        """Aplica hachura a um painel individual específico baseado no radiobutton"""
        try:
            # Limpar hachuras existentes para este painel
            self._limpar_hachuras_painel_individual(painel_id)
            
            # Aplicar nova hachura baseada na seleção do radiobutton
            if tipo_hachura == 1:
                self._desenhar_hachura_diagonal_integrada(x, y, largura, altura, painel_id)
            elif tipo_hachura == 2:
                self._desenhar_hachura_xadrez_integrada(x, y, largura, altura, painel_id)
            # Se tipo_hachura == 0, não desenha nada (apenas limpa)
                    
        except Exception as e:
            pass

    def _limpar_hachuras_painel_individual(self, painel_id):
        """Remove todas as hachuras de um painel individual específico"""
        try:
            # Tags para identificar hachuras deste painel
            tags_to_remove = [f'hachura_{painel_id}', f'hachura_diagonal_{painel_id}', f'hachura_xadrez_{painel_id}']
            
            for tag in tags_to_remove:
                items = self.canvas.find_withtag(tag)
                for item in items:
                    self.canvas.delete(item)
        except Exception as e:
            pass

    def _desenhar_hachura_diagonal_individual(self, x, y, largura, altura, painel_id):
        """Desenha hachura diagonal em um painel individual"""
        try:
            # Parâmetros da hachura - mais delicado e denso
            espacamento = 3  # Espaçamento menor entre linhas
            x1 = x
            y1 = y - altura
            x2 = x + largura
            y2 = y
            
            # Calcular número de linhas diagonais
            diagonal_length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            num_lines = max(int(diagonal_length / espacamento), 10)  # Mínimo 10 linhas
            
            # Desenhar múltiplas linhas diagonais paralelas
            for i in range(num_lines):
                # Calcular posição da linha diagonal
                progress = i / max(num_lines - 1, 1)
                
                # Linha diagonal principal
                line_x1 = x1 + progress * (x2 - x1)
                line_y1 = y1 + progress * (y2 - y1)
                line_x2 = x1 + (1 - progress) * (x2 - x1)
                line_y2 = y1 + (1 - progress) * (y2 - y1)
                
                # Desenhar linha diagonal
                self.canvas.create_line(
                    line_x1, line_y1, line_x2, line_y2,
                    fill="black", width=0.5,  # Linha mais fina
                    tags=[f'hachura_{painel_id}', f'hachura_diagonal_{painel_id}']
                )
                
                # Adicionar linhas paralelas para densidade
                if i < num_lines - 1:
                    offset = espacamento * 0.3
                    # Linha paralela acima
                    self.canvas.create_line(
                        line_x1 - offset, line_y1 - offset, 
                        line_x2 - offset, line_y2 - offset,
                        fill="black", width=0.3,
                        tags=[f'hachura_{painel_id}', f'hachura_diagonal_{painel_id}']
                    )
                    # Linha paralela abaixo
                    self.canvas.create_line(
                        line_x1 + offset, line_y1 + offset, 
                        line_x2 + offset, line_y2 + offset,
                        fill="black", width=0.3,
                        tags=[f'hachura_{painel_id}', f'hachura_diagonal_{painel_id}']
                    )
        except Exception as e:
            pass

    def _desenhar_hachura_xadrez_individual(self, x, y, largura, altura, painel_id):
        """Desenha hachura xadrez em um painel individual"""
        try:
            # Parâmetros da hachura - mais delicado
            espacamento = 6  # Tamanho menor dos quadrados
            x1 = x
            y1 = y - altura
            x2 = x + largura
            y2 = y
            
            # Desenhar padrão xadrez mais delicado
            for i in range(0, int(largura), espacamento):
                for j in range(0, int(altura), espacamento):
                    # Alternar entre quadrados preenchidos e vazios
                    if (i // espacamento + j // espacamento) % 2 == 0:
                        square_x1 = x1 + i
                        square_y1 = y1 + j
                        square_x2 = min(square_x1 + espacamento, x2)
                        square_y2 = min(square_y1 + espacamento, y2)
                        
                        # Desenhar linhas do quadrado mais finas
                        self.canvas.create_line(square_x1, square_y1, square_x2, square_y1, fill="black", width=0.5,
                                              tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
                        self.canvas.create_line(square_x2, square_y1, square_x2, square_y2, fill="black", width=0.5,
                                              tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
                        self.canvas.create_line(square_x2, square_y2, square_x1, square_y2, fill="black", width=0.5,
                                              tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
                        self.canvas.create_line(square_x1, square_y2, square_x1, square_y1, fill="black", width=0.5,
                                              tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
                        
                        # Adicionar linhas diagonais internas para mais densidade
                        if square_x2 - square_x1 > espacamento * 0.5 and square_y2 - square_y1 > espacamento * 0.5:
                            # Linha diagonal principal
                            self.canvas.create_line(square_x1, square_y1, square_x2, square_y2, fill="black", width=0.3,
                                                  tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
                            # Linha diagonal secundária
                            self.canvas.create_line(square_x2, square_y1, square_x1, square_y2, fill="black", width=0.3,
                                                  tags=[f'hachura_{painel_id}', f'hachura_xadrez_{painel_id}'])
        except Exception as e:
            pass

    def _aplicar_hachura_painel(self, tipo_painel, tipo_hachura):
        """Aplica hachura ao painel baseado no tipo selecionado"""
        try:
            # Obter coordenadas do painel
            painel_info = self._get_painel_dict(tipo_painel)
            if not painel_info:
                return
            
            x = painel_info['x']
            y = painel_info['y']
            largura = painel_info['largura']
            altura = painel_info['altura']
            escala = painel_info['escala']
            
            # Limpar hachuras existentes
            self._limpar_hachuras_painel(tipo_painel)
            
            # Aplicar nova hachura se checkbox estiver marcado
            var = getattr(self, f'hachura_{tipo_hachura}_{tipo_painel.lower()}')
            if var.get():
                if tipo_hachura == 1:
                    self._desenhar_hachura_diagonal(x, y, largura, altura, escala, tipo_painel)
                elif tipo_hachura == 2:
                    self._desenhar_hachura_xadrez(x, y, largura, altura, escala, tipo_painel)
                    
        except Exception as e:
            pass

    def _limpar_hachuras_painel(self, tipo_painel):
        """Remove todas as hachuras do painel"""
        try:
            # Tags para identificar hachuras
            tags_to_remove = [f'hachura_{tipo_painel.lower()}', f'hachura_diagonal_{tipo_painel.lower()}', f'hachura_xadrez_{tipo_painel.lower()}']
            
            for tag in tags_to_remove:
                items = self.canvas.find_withtag(tag)
                for item in items:
                    self.canvas.delete(item)
        except Exception as e:
            pass

    def _desenhar_hachura_diagonal(self, x, y, largura, altura, escala, tipo_painel):
        """Desenha hachura diagonal no painel"""
        try:
            # Parâmetros da hachura
            espacamento = 5  # Espaçamento entre linhas
            x1 = x
            y1 = y - altura * escala
            x2 = x + largura * escala
            y2 = y
            
            # Calcular número de linhas
            diagonal_length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            num_lines = int(diagonal_length / espacamento)
            
            # Desenhar linhas diagonais
            for i in range(num_lines):
                progress = i / max(num_lines - 1, 1)
                
                # Linha diagonal de cima para baixo
                line_x1 = x1 + progress * (x2 - x1)
                line_y1 = y1 + progress * (y2 - y1)
                line_x2 = x1 + (1 - progress) * (x2 - x1)
                line_y2 = y1 + (1 - progress) * (y2 - y1)
                
                self.canvas.create_line(
                    line_x1, line_y1, line_x2, line_y2,
                    fill="black", width=1,
                    tags=[f'hachura_{tipo_painel.lower()}', f'hachura_diagonal_{tipo_painel.lower()}']
                )
        except Exception as e:
            pass

    def _desenhar_hachura_xadrez(self, x, y, largura, altura, escala, tipo_painel):
        """Desenha hachura xadrez no painel"""
        try:
            # Parâmetros da hachura
            espacamento = 8  # Tamanho dos quadrados
            x1 = x
            y1 = y - altura * escala
            x2 = x + largura * escala
            y2 = y
            
            # Desenhar padrão xadrez
            for i in range(0, int(largura * escala), espacamento):
                for j in range(0, int(altura * escala), espacamento):
                    # Alternar entre quadrados preenchidos e vazios
                    if (i // espacamento + j // espacamento) % 2 == 0:
                        square_x1 = x1 + i
                        square_y1 = y1 + j
                        square_x2 = min(square_x1 + espacamento, x2)
                        square_y2 = min(square_y1 + espacamento, y2)
                        
                        # Desenhar linhas do quadrado
                        self.canvas.create_line(square_x1, square_y1, square_x2, square_y1, fill="black", width=1,
                                              tags=[f'hachura_{tipo_painel.lower()}', f'hachura_xadrez_{tipo_painel.lower()}'])
                        self.canvas.create_line(square_x2, square_y1, square_x2, square_y2, fill="black", width=1,
                                              tags=[f'hachura_{tipo_painel.lower()}', f'hachura_xadrez_{tipo_painel.lower()}'])
                        self.canvas.create_line(square_x2, square_y2, square_x1, square_y2, fill="black", width=1,
                                              tags=[f'hachura_{tipo_painel.lower()}', f'hachura_xadrez_{tipo_painel.lower()}'])
                        self.canvas.create_line(square_x1, square_y2, square_x1, square_y1, fill="black", width=1,
                                              tags=[f'hachura_{tipo_painel.lower()}', f'hachura_xadrez_{tipo_painel.lower()}'])
        except Exception as e:
            pass


def setup_canvas_preview(pilar_analyzer_instance):
    """
    Função utilitária para configurar as funcionalidades de preview em uma instância do PilarAnalyzer
    """
    # Adicionar métodos do mixin à instância
    for attr_name in dir(CanvasPreviewMixin):
        if not attr_name.startswith('_') or attr_name in ['__init__']:
            attr = getattr(CanvasPreviewMixin, attr_name)
            if callable(attr):
                # Bind the method to the instance
                setattr(pilar_analyzer_instance, attr_name, attr.__get__(pilar_analyzer_instance, type(pilar_analyzer_instance)))
    
    return pilar_analyzer_instance 