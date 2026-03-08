;; Comando para executar script SCR LAZ
(defun c:LAR ()
  (setvar "filedia" 0)
  (command "_SCRIPT" "C:/Users/Ryzen/Desktop/GITHUB/Agente-cad-PYSIDE/ferramentas_LOAD_LISP/script_LAZ.scr")
  (setvar "filedia" 1)
  (princ)
)
