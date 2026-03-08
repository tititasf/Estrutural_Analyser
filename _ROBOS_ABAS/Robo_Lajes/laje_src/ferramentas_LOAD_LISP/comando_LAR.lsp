;; Comando para executar script SCR LAZ
(defun c:LAR ()
  (setvar "filedia" 0)
  (command "_SCRIPT" "C:/Users/Ryzen/Desktop/GITHUB/Agente-cad-PYSIDE/_ROBOS_ABAS/Robo_Lajes/laje_src/SCRIPTS_ROBOS/script_LAZ.scr")
  (setvar "filedia" 1)
  (princ)
)
