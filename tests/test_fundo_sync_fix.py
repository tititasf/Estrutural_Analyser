import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Adicionar caminhos necessários para encontrar os módulos do robô
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
robo_fundos_path = os.path.join(base_dir, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
if robo_fundos_path not in sys.path:
    sys.path.append(robo_fundos_path)

try:
    from fundo_pyside import FundoMainWindow
except ImportError as e:
    print(f"Erro de importação: {e}")
    sys.exit(1)

def test_fundo_sync():
    app = QApplication(sys.argv)
    window = FundoMainWindow()
    
    print("\n--- TESTE DE SINCRONIZAÇÃO ROBO FUNDO ---")
    
    obra_teste = "OBRA-TESTE-AUT"
    pav_teste = "PAV-99-TESTE"
    
    print(f"Simulando sincronização: {obra_teste} | {pav_teste}")
    window.sync_context(obra_teste, pav_teste)
    
    # Validação 1: Obra no Combo
    obra_actual = window.combo_obra.currentText()
    assert obra_actual == obra_teste, f"ERRO: Obra esperada {obra_teste}, obteve {obra_actual}"
    print(f"[OK] Obra '{obra_actual}' selecionada no combo.")
    
    # Validação 2: Pavimento no Combo
    pav_actual = window.combo_pavimento.currentText()
    assert pav_actual == pav_teste, f"ERRO: Pavimento esperado {pav_teste}, obteve {pav_actual}"
    print(f"[OK] Pavimento '{pav_actual}' selecionada no combo.")
    
    # Validação 3: Campo de texto (Informações Básicas)
    txt_pav = window.fields['pavimento'].text()
    assert txt_pav == pav_teste, f"ERRO: Campo texto pavimento esperado {pav_teste}, obteve {txt_pav}"
    print(f"[OK] Campo de texto pavimento atualizado.")
    
    # Validação 4: Metadados
    assert obra_teste in window.obras_metadata, "ERRO: Obra não está no metadata"
    assert pav_teste in window.obras_metadata[obra_teste], "ERRO: Pavimento não está no metadata da obra"
    print(f"[OK] Metadados atualizados corretamente.")
    
    print("\n--- TODOS OS TESTES PASSARAM ---")
    # Fechar app
    QTimer.singleShot(100, app.quit)
    # app.exec() # Omitido para rodar headless se possível ou apenas encerrar

if __name__ == "__main__":
    from PySide6.QtCore import QTimer
    test_fundo_sync()
