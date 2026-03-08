(defun c:BREAK2 ()
  (setvar "CMDECHO" 0)
  
  ; Adiciona zoom na região selecionada
  (command "_zoom" "S" "0.05")
  
  ; Solicita seleção da linha
  (setq ent (car (entsel "\nSelecione a linha para aplicar o break: ")))
  
  ; Solicita os dois pontos de quebra
  (setq p1 (getpoint "\nSelecione o primeiro ponto de break: "))
  (setq p2 (getpoint "\nSelecione o segundo ponto de break: "))

  ; Adiciona zoom na região selecionada
  (command "_zoom" "W" p1 p2)
  
  ; Executa o break na linha selecionada
  (command "_break" ent p1 p2)
  
  (setvar "CMDECHO" 1)
  (princ)
)
