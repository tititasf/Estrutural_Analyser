;; Comando para executar script SCR PAZ
(defun c:PAZ ()
  (command "SCRIPT" "c:/Users/Ryzen/Desktop/GITHUB/Agente-cad-PYSIDE/ferramentas_LOAD_LISP/script_PAZ.scr")
  (princ)
)
(prompt "\nComando PAZ carregado. Digite PAZ para rodar o script atual.")
(princ)
