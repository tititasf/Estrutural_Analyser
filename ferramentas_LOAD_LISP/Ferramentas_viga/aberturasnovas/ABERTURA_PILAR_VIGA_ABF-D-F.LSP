;-------------------------------------------------------------------------------
; Função: Abertura em pilar à direita da viga (Novo comando: abvD)
; Arquivo: ABERTURA_PILAR_VIGA_DIREITA.LSP
;-------------------------------------------------------------------------------

(defun c:abFDF ()
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
          
          ; Zoom e desenha linha no topo da seleção
          (command "zoom" "c" (list (/ (+ esquerda_x direita_x) 2) topo_y) 5)
          (command "pline" 
                  (list esquerda_x topo_y) 
                  (list direita_x topo_y) 
                  "")
          
          ; Zoom e desenha linha na esquerda da seleção
          (command "zoom" "c" (list esquerda_x (/ (+ fundo_y topo_y) 2)) 5)
          (command "pline" 
                  (list esquerda_x fundo_y) 
                  (list esquerda_x topo_y) 
                  "")

          ; Define o layer para "SARR_2.2x7"
          (command "-layer" "m" "SARR_2.2x7" "")
          
          ; Desenha linha vertical 7cm à esquerda da parede
          (setq linha_esquerda_x (- esquerda_x 7))
          (command "zoom" "c" (list linha_esquerda_x (/ (+ fundo_y topo_y) 2)) 5)
          (command "pline" 
                  (list linha_esquerda_x fundo_y) 
                  (list linha_esquerda_x topo_y) 
                  "")
          
          ; Desenha continuação 7cm acima da linha vertical
          (command "zoom" "c" (list linha_esquerda_x (/ (+ topo_y (+ topo_y 7)) 2)) 5)
          (command "pline" 
                  (list linha_esquerda_x topo_y) 
                  (list linha_esquerda_x (+ topo_y 7)) 
                  "")
          
          ; Desenha linha horizontal 7cm à esquerda do topo
          (command "zoom" "c" (list (/ (+ esquerda_x (- esquerda_x 7)) 2) topo_y) 5)
          (command "pline" 
                  (list esquerda_x topo_y) 
                  (list (- esquerda_x 7) topo_y) 
                  "")
          
          ; Desenha linha 7cm acima do topo com extensão de 7cm à esquerda
          (command "zoom" "c" (list (/ (+ direita_x (- esquerda_x 7)) 2) (+ topo_y 7)) 5)
          (command "pline" 
                  (list direita_x (+ topo_y 7)) 
                  (list (- esquerda_x 7) (+ topo_y 7)) 
                  "")
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  (princ)
)