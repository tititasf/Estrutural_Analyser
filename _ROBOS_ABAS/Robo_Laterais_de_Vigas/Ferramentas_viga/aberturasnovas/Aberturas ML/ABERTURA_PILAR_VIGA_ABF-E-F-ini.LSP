;-------------------------------------------------------------------------------
; Função: Abertura em pilar à esquerda da viga (Novo comando: abve)
; Arquivo: ABERTURA_PILAR_VIGA_ESQUERDA.LSP
;-------------------------------------------------------------------------------

(defun c:abFEFINI ()
  (setvar "CMDECHO" 0)

  ; Solicita pontos para definir a área de seleção
  (setq p1 (getpoint "\nSelecione o primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione o segundo ponto do retângulo: "))
  
  ; Verifica se os pontos são válidos
  (if (and p1 p2)
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
          
          ; Linhas de fundo e esquerda removidas (serão geradas pelo script principal as de topo e fundo)

          ; Define o layer para "Sarrafo_de_pressao"
          (command "-layer" "m" "Sarrafo_de_pressao" "")
          
      ; Configura MLINE
          (setvar "CMLSCALE" 7)
          (setvar "CMLSTYLE" "SAR3")
          (setvar "CMLJUST" 0) ; Top/Left Alignment
          
          ; Desenha linha vertical (Mline) - Direita, Expand Right -> Draw Down (Top->Bottom)
          (setq v_x (+ direita_x 7))
          (command "zoom" "c" (list v_x (/ (+ fundo_y topo_y) 2)) 5)
          (command "mline" 
                  (list v_x topo_y)
                  (list v_x fundo_y) 
                  "")
          
          ; Desenha linha horizontal (Mline) - Topo, Expand Up -> Draw Right (Left->Right)
          (setq h_y (+ topo_y 7))
          (command "zoom" "c" (list (/ (+ esquerda_x direita_x) 2) h_y) 5)
          (command "mline" 
                  (list esquerda_x h_y) 
                  (list (+ direita_x 7) h_y) 
                  "")
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  (princ)
) 