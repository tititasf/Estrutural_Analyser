;; Comando para executar script SCR LAZ
(defun c:LAR ()
  (setvar "filedia" 0)
  (command "_SCRIPT" "C:/Users/Ryzen/Desktop/GITHUB/Agente-cad-PYSIDE/projects_repo/c987bcdb-270b-49f1-ad55-9feba6b6d2e3/laje_data/scripts/script_LAZ.scr")
  (setvar "filedia" 1)
  (princ)
)
