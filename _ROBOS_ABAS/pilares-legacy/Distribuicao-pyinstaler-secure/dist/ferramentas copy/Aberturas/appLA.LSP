(defun c:appla ()
  (setvar "CMDECHO" 0)
  
  ;Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione segundo ponto do retângulo: "))
  
  ;Extrai coordenadas dos pontos
  (setq x1 (car p1)
        y1 (cadr p1)
        x2 (car p2)
        y2 (cadr p2))
  
  ;Calcula centro para o zoom
  (setq centro_x (/ (+ x1 x2) 2))
  (setq centro_y (/ (+ y1 y2) 2))
  (command "zoom" "c" (list centro_x centro_y) 5)
  
  ;Calcula ponto do break (7cm à direita do ponto esquerdo)
  (setq break_x (+ (min x1 x2) 70))
  
  ;Executa o break
  (command "_break" pause 
          (list break_x (min y1 y2))  ;Primeiro ponto
          (list break_x (max y1 y2))  ;Segundo ponto
  )
  
  (setvar "CMDECHO" 1)
  (princ)
)
