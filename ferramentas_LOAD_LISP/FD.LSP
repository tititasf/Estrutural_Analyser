;; Comando FD - Fundo Desenhar
;; Carrega e executa o script FD

(defun c:FD ()
  (princ "\nExecutando comando FD - Sistema de Fundos...\n")

  ;; Carregar script FD
  (command "_.SCRIPT" "c:/Users/Ryzen/Desktop/GITHUB/Agente-cad-PYSIDE/ferramentas_LOAD_LISP/FD.scr")

  (princ "\nComando FD concluido.\n")
  (princ)
)
