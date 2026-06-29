import re
import sys

path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\main.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Original block:
#                 # Iniciar Processamento IA Automatizado (Linhas + Cotas)
#                 # automate_ai_for_all_lajes faz um save final ao terminar
#                 if run_ai and hasattr(self.robo_laje.laje_tab, 'automate_ai_for_all_lajes'):
#                     self.robo_laje.laje_tab.automate_ai_for_all_lajes()

new_block = """                # Iniciar Processamento IA Automatizado (Linhas + Cotas)
                if run_ai and hasattr(self.robo_laje.laje_tab, 'automate_ai_for_all_lajes'):
                    self.show_progress("Processando Lajes pela IA...", 0)
                    
                    def prog_cb(pct, msg):
                        self.update_progress(pct, msg)
                        from PySide6.QtWidgets import QApplication
                        QApplication.processEvents()

                    self.robo_laje.laje_tab.automate_ai_for_all_lajes(progress_callback=prog_cb)
                    self.hide_progress()"""

text = re.sub(
    r'# Iniciar Processamento IA Automatizado.*?if run_ai and hasattr.*?automate_ai_for_all_lajes\(\)',
    new_block,
    text,
    flags=re.DOTALL
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
