from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                QScrollArea, QWidget, QFrame, QGridLayout, QLineEdit, 
                                QPushButton, QGroupBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

class RobotFichaDialog(QDialog):
    """
    Ficha Técnica específica para exibição de dados processados pelos robôs (Fase 4).
    Exibe os dados brutos e específicos sem a complexidade de rotulagem do Structural Analyzer.
    """
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.type_str = data.get("type", "Robô")
        self.item_name = data.get("nome", data.get("name", "Item"))
        
        self.setWindowTitle(f"Ficha do Robô: {self.item_name}")
        self.resize(500, 750)
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Arial; }
            QLabel { color: #b0b0b0; font-size: 11px; }
            QLineEdit { 
                background: #1e1e1e; border: 1px solid #333; border-radius: 4px; 
                padding: 6px; color: #00d4ff; font-weight: bold; font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #333; border-radius: 8px; margin-top: 15px;
                font-weight: bold; color: #00d4ff; padding-top: 10px;
            }
        """)
        
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header Premium
        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet("background: #1a1b1e; border-bottom: 2px solid #00d4ff;")
        h_layout = QVBoxLayout(header)
        
        title = QLabel(self.type_str.upper())
        title.setStyleSheet("color: #00d4ff; font-weight: bold; font-size: 10px; letter-spacing: 1px;")
        h_layout.addWidget(title)
        
        name_label = QLabel(self.item_name)
        name_label.setStyleSheet("color: white; font-weight: bold; font-size: 20px;")
        h_layout.addWidget(name_label)
        
        main_layout.addWidget(header)
        
        # Conteúdo Scrollável
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        container = QWidget()
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(10)
        
        # Separar dados em grupos (Geral, Detalhes, Técnicos)
        geral_group = self._create_group("Dados Gerais", [
            ("Nome do Item", "nome"),
            ("Número", "numero"),
            ("Pavimento", "pavimento"),
            ("Obra", "obra")
        ])
        content_layout.addWidget(geral_group)
        
        # Detalhes Geométricos/Técnicos (depende do robô)
        if "Pilar" in self.type_str:
            geo_group = self._create_group("Geometria e Níveis", [
                ("Comprimento (cm)", "comprimento"),
                ("Largura (cm)", "largura"),
                ("Altura (cm)", "altura"),
                ("Nível Chegada", "nivel_chegada"),
                ("Nível Saída", "nivel_saida")
            ])
            content_layout.addWidget(geo_group)
            
            paf_data = self.data.get("parafusos", {})
            if paf_data:
                paf_group = self._create_group("Parafusos / Conexões", [
                    ("P1-2", "P1-2", paf_data),
                    ("P2-3", "P2-3", paf_data),
                    ("P3-4", "P3-4", paf_data),
                    ("P4-5", "P4-5", paf_data)
                ])
                content_layout.addWidget(paf_group)
        
        elif "Viga" in self.type_str:
            viga_group = self._create_group("Dados da Viga", [
                ("Seção", "secao"),
                ("Nível", "nivel_viga"),
                ("Altura", "altura"),
                ("Largura", "largura")
            ])
            content_layout.addWidget(viga_group)

        elif "Laje" in self.type_str:
            laje_group = self._create_group("Dados da Laje", [
                ("Modo Selecionado", "modo_selecionado"),
                ("Observações", "observacoes")
            ])
            content_layout.addWidget(laje_group)
            
            # Mostrar contagens de elementos geométricos
            geo_counts = []
            for k in ["coordenadas", "linhas_verticais", "linhas_horizontais", "obstaculos"]:
                val = self.data.get(k, [])
                if isinstance(val, list):
                    geo_counts.append((f"Total {k.replace('_', ' ').title()}", k))
            
            if geo_counts:
                geo_list_group = QGroupBox("Geometria Detectada")
                g_layout = QGridLayout(geo_list_group)
                for i, (lbl_txt, key) in enumerate(geo_counts):
                    count = len(self.data.get(key, []))
                    g_layout.addWidget(QLabel(lbl_txt.upper()), i, 0)
                    edit = QLineEdit(f"{count} itens")
                    edit.setReadOnly(True)
                    g_layout.addWidget(edit, i, 1)
                content_layout.addWidget(geo_list_group)
        
        # Outros dados não mapeados (Exibição Dinâmica)
        others_data = {}
        known_keys = ["nome", "name", "numero", "pavimento", "obra", "type", "id", "links", "status", "parafusos", 
                      "coordenadas", "linhas_verticais", "linhas_horizontais", "obstaculos", "modo_selecionado", "observacoes"]
        for k, v in self.data.items():
            if k not in known_keys:
                if isinstance(v, list):
                    others_data[k] = f"Lista ({len(v)} itens)"
                elif isinstance(v, dict):
                    others_data[k] = f"Objeto ({len(v)} chaves)"
                else:
                    others_data[k] = v
        
        if others_data:
            others_group = self._create_group("Parâmetros Adicionais", [(k.replace("_", " ").title(), k) for k in others_data.keys()])
            content_layout.addWidget(others_group)
            
        content_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
        
        # Botão Fechar
        footer = QFrame()
        footer.setFixedHeight(50)
        footer.setStyleSheet("background: #1a1b1e; border-top: 1px solid #333;")
        f_layout = QHBoxLayout(footer)
        
        btn_close = QPushButton("FECHAR")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedWidth(120)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #333; color: white; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background: #444; }
        """)
        btn_close.clicked.connect(self.accept)
        f_layout.addStretch()
        f_layout.addWidget(btn_close)
        
        main_layout.addWidget(footer)

    def _create_group(self, title, fields_list, source_dict=None):
        if source_dict is None: source_dict = self.data
        
        group = QGroupBox(title)
        layout = QGridLayout(group)
        layout.setSpacing(10)
        
        for i, (label_text, key) in enumerate(fields_list):
            val = source_dict.get(key, "---")
            
            lbl = QLabel(label_text.upper())
            edit = QLineEdit(str(val))
            edit.setReadOnly(True)
            
            layout.addWidget(lbl, i, 0)
            layout.addWidget(edit, i, 1)
            
        return group
