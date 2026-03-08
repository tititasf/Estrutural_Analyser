(defun c:HH ()
  (prompt "\nClique dentro do retângulo para aplicar o hatch.")
  ;; Modo de seleção de ponto interno
  (setq pt (getpoint "\nClique dentro do retângulo: "))
  ;; Se um ponto válido foi selecionado
  (if pt
    (progn
      ;; Salva a vista atual
      (setq old-view (getvar "VIEWSIZE"))
      ;; Aplica zoom na área de forma simplificada
      (command "_ZOOM" "C" pt "100")
      ;; Aplica o Hatch
      (command "-HATCH" "LA" "REAPROVEITAMENTO" "P" "ANSI31" "5" "1" pt "")
      ;; Restaura a vista anterior
      (command "ZOOM" "P")
      (princ "\nHatch aplicado com sucesso!\n"))
    ;; Caso o ponto não seja válido
    (prompt "\nPonto inválido ou área não encontrada."))
  (command "_LAYER" "S" "cota" "")
  (princ))