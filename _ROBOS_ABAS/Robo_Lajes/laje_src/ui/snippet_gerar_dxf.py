
    def _gerar_dxf_nativo(self):
        """Gera o DXF nativo para a laje selecionada."""
        if not LajeDXFEngine:
            QMessageBox.warning(self, "Erro", "Engine DXF não disponível.")
            return

        try:
            # Obter laje selecionada da aba
            # Assumindo que LajeTab tem método get_laje_atual() ou acessamos os campos
            # Mas o ideal é pegar do tree widget, que tem os dados
            
            # Vamos tentar pegar do tree widget do laje_tab
            selected = self.laje_tab.tree_widget.selectedItems()
            if not selected:
                QMessageBox.information(self, "Seleção", "Selecione uma laje na lista para gerar o DXF.")
                return
            
            # O item da árvore deve conter o objeto laje ou seu número
            # Verificar como LajeTab popula a árvore
            item = selected[0]
            # Assumindo que data(0, Qt.UserRole) guarda o objeto Laje, padrão comum
            laje = item.data(0, Qt.UserRole)
            
            if not laje and hasattr(self.laje_tab, 'laje_atual'):
                laje = self.laje_tab.laje_atual

            if not laje:
                QMessageBox.warning(self, "Erro", "Não foi possível identificar a laje selecionada.")
                return

            # Definir caminho de saída
            # Tentar salvar na pasta da obra se possível
            output_dir = os.path.join(os.getcwd(), "output", "dxf_nativos")
            if hasattr(self, 'obra_atual') and self.obra_atual:
                 # Criar pasta Fase 6 dentro da estrutura da obra (simulada)
                 # Se obra_atual tiver caminho, melhor. Senão, usa output.
                 pass
            
            os.makedirs(output_dir, exist_ok=True)
            filename = f"Laje_{laje.numero}_{laje.nome.replace(' ', '_')}.dxf"
            filepath = os.path.join(output_dir, filename)

            # Instanciar e processar
            engine = LajeDXFEngine(filepath)
            engine.process_laje(laje)
            engine.save()

            QMessageBox.information(self, "Sucesso", f"DXF gerado com sucesso em:\n{filepath}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erro", f"Erro ao gerar DXF: {str(e)}")
