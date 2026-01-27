;-------------------------------------------------------------------------------
; Função: Abertura em pilar à direita da viga (Novo comando: abvD)
; Arquivo: ABERTURA_PILAR_VIGA_DIREITA.LSP
;-------------------------------------------------------------------------------

(defun c:ABVDF ()
  (setvar "CMDECHO" 0)

  ; Solicita pontos para definir a área de seleção
  (setq p1 (getpoint "\nSelecione o primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione o segundo ponto do retângulo: "))
  (setq p3 (getpoint "\nSelecione o terceiro ponto para definir a altura do retângulo adicional: "))
  
  ; Verifica se os pontos são válidos
  (if (and p1 p2 p3)
      (progn
          ; Organiza os pontos para garantir consistência
          (setq x1 (min (car p1) (car p2)))
          (setq x2 (max (car p1) (car p2)))
          (setq y1 (min (cadr p1) (cadr p2)))
          (setq y2 (max (cadr p1) (cadr p2)))
          
          ; Define coordenadas base
          (setq fundo_y y1)  ; Y do fundo
          (setq topo_y y2)   ; Y do topo
          (setq esquerda_x x1) ; X da esquerda
          (setq direita_x x2)  ; X da direita

          ; Define o layer para "Painéis"
          (command "-layer" "m" "Painéis" "")
          
          ; ZOOM antes de desenhar linha no topo da seleção
          (command "zoom" "c" (list (/ (+ esquerda_x direita_x) 2.0) topo_y) 5)
          ; Desenha linha no topo da seleção
          (command "pline" 
                  (list esquerda_x topo_y) 
                  (list direita_x topo_y) 
                  "")
          
          ; ZOOM antes de desenhar linha na esquerda da seleção
          (command "zoom" "c" (list esquerda_x (/ (+ fundo_y topo_y) 2.0)) 5)
          ; Desenha linha na esquerda da seleção
          (command "pline" 
                  (list esquerda_x fundo_y) 
                  (list esquerda_x topo_y) 
                  "")

          ; Define o layer para "SARR_2.2x7"
          (command "-layer" "m" "SARR_2.2x7" "")
          
          ; Desenha linha vertical 7cm à esquerda da parede
          (setq linha_esquerda_x (- esquerda_x 7))
          (command "zoom" "c" (list linha_esquerda_x (/ (+ fundo_y topo_y) 2.0)) 5)
          (command "pline" 
                  (list linha_esquerda_x fundo_y) 
                  (list linha_esquerda_x topo_y) 
                  "")
          
          ; Desenha continuação 2.2cm acima da linha vertical
          (command "zoom" "c" (list linha_esquerda_x (+ topo_y 2.2)) 5)
          (command "pline" 
                  (list (- linha_esquerda_x 8) topo_y) 
                  (list (- linha_esquerda_x 8) (+ topo_y 2.2)) 
                  "")
          
          ; Desenha linha horizontal 15cm à esquerda do topo
          (command "zoom" "c" (list (/ (+ esquerda_x (- esquerda_x 15)) 2.0) topo_y) 5)
          (command "pline" 
                  (list esquerda_x topo_y) 
                  (list (- esquerda_x 15) topo_y) 
                  "")
          
          ; Desenha linha 2.2cm acima do topo com extensão de 15+2.2cm à esquerda
          (command "zoom" "c" (list (/ (+ direita_x (- esquerda_x 15)) 2.0) (+ topo_y 2.2)) 5)
          (command "pline" 
                  (list (- direita_x 7) (+ topo_y 2.2)) 
                  (list (- esquerda_x 15) (+ topo_y 2.2)) 
                  "")

          ; Zoom antes do TRIM
          (command "zoom" "c" (list (/ (+ direita_x (+ direita_x 1)) 2.0) (- fundo_y 1.2)) 5)
          ; TRIM 1cm acima da linha do fundo do retângulo adicional
          (command "trim" "" "f" (list (+ esquerda_x 1) (+ topo_y 1.2)) (list (- direita_x 8) (+ topo_y 1.2)) "" "" )
          ; Define o layer para "SARR_2.2x3.5"
          (command "-layer" "m" "SARR_2.2x3.5" "")

          ; Desenha retângulo adicional a 15cm à esquerda da abertura
          (setq ret_x2 (- esquerda_x 15))
          (setq ret_x1 (- ret_x2 3.5))
          (setq ret_y1 (+ fundo_y 0))
          (setq ret_y2 (- (cadr p3) 2.2))
          ; Garante que ret_y1 seja o fundo e ret_y2 o topo
          (if (> ret_y1 ret_y2)
              (progn (setq temp ret_y1) (setq ret_y1 ret_y2) (setq ret_y2 temp))
          )
          ; Zoom na região do retângulo
          (command "zoom" "c" (list (/ (+ ret_x1 ret_x2) 2.0) (/ (+ ret_y1 ret_y2) 2.0)) 5)
          ; Desenha o retângulo
          (command "pline"
                  (list ret_x1 ret_y1)
                  (list ret_x2 ret_y1)
                  (list ret_x2 ret_y2)
                  (list ret_x1 ret_y2)
                  (list ret_x1 ret_y1)
                  ""
          ))
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  (princ)
)