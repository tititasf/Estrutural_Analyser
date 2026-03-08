;-------------------------------------------------------------------------------
; Função: Abertura entre vigas (Novo comando: acv)
; Arquivo: ACV.LSP
;-------------------------------------------------------------------------------

(defun c:acv ()
  (setvar "CMDECHO" 0)

  ;Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione o primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione o segundo ponto do retângulo: "))
  
  ;Verifica se os pontos são válidos antes de criar o retângulo
  (if (and p1 p2)
      (progn
          ;Organiza os pontos para garantir consistência independente da direção
          (setq x1 (min (car p1) (car p2)))
          (setq x2 (max (car p1) (car p2)))
          (setq y1 (min (cadr p1) (cadr p2)))
          (setq y2 (max (cadr p1) (cadr p2)))
          
          ;Redefine os pontos organizados
          (setq p1 (list x1 y2))  ;superior esquerdo
          (setq p2 (list x2 y1))  ;inferior direito

          ; Calcula coordenada Y do fundo ANTES de usar na função criar_retangulo_viga
          (setq fundo_y (cadr p2))  ; Usando Y do ponto inferior
          
          ; Define o layer para "cota"
          (command "-layer" "m" "cota" "")
          
          ; Zoom para a linha na parede esquerda da seleção
          (command "zoom" "c" (list x1 (/ (+ y2 fundo_y) 2)) 5)
          
          ; Define o layer para "Painéis" antes de desenhar a linha
          (command "-layer" "m" "Painéis" "")
          
          ; Desenha linha na parede esquerda da seleção
          (command "line" (list x1 y2) (list x1 fundo_y) "")
          
          ; Define o layer para "cota"
          (command "-layer" "m" "cota" "")
          
          ; Adiciona cota à direita da linha esquerda
          (command "dimlinear" (list x1 y2) (list x1 fundo_y) (list (+ x1 15) (/ (+ y2 fundo_y) 2)) "")
          
          ; Zoom para a linha no topo da seleção
          (command "zoom" "c" (list (/ (+ x1 x2) 2) y2) 5)
          ; Desenha linha no topo da seleção
          (command "line" (list x1 y2) (list x2 y2) "")
          
          ; Adiciona cota acima da linha do topo
          (command "dimlinear" (list x1 y2) (list x2 y2) (list (/ (+ x1 x2) 2) (+ y2 15)) "")
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  ; Calcula coordenada Y do fundo
  (setq fundo_y (cadr p2))  ; Usando Y do ponto inferior
  

  ; Define o layer para "Painéis"
  (command "-layer" "m" "sarr_2.2x7" "")

  ; Zoom para a linha horizontal inferior
  (setq linha_y (- fundo_y 7))
  (command "zoom" "c" (list (/ (+ x1 x2) 2) linha_y) 5)
  ; Desenha linha horizontal 7cm abaixo do fundo
  (command "pline"
          (list (- x1 7) linha_y) 
          (list (+ x2 7) linha_y)
          ""
  )

  ; Define o layer para "Painéis"
  (command "-layer" "m" "Painéis" "")

  ; Zoom para a linha horizontal superior
  (setq linha_y_sup (+ linha_y 7))
  (command "zoom" "c" (list (/ (+ x1 x2) 2) linha_y_sup) 5)
  ; Desenha linha horizontal 7cm acima da atual
  (command "pline"
          (list x1 linha_y_sup)
          (list x2 linha_y_sup)
          ""
  )

  ; Define o layer para "SARR_2.2x7"
  (command "-layer" "m" "SARR_2.2x7" "")
  
  ; Zoom para a nova linha horizontal
  (command "zoom" "c" (list x2 linha_y_sup) 5)
  ; Desenha a nova linha como continuação da linha horizontal "Painéis"
  (command "pline"
          (list x2 linha_y_sup) ; Ponto inicial igual ao final da linha "Painéis"
          (list (+ x2 7) linha_y_sup) ; Ponto final 7cm à direita
          ""
  )
  
  ; Zoom para a linha vertical direita
  (setq linha_x_direita (+ x2 7))
  (command "zoom" "c" (list linha_x_direita (/ (+ y2 fundo_y) 2)) 5)
  ; Desenha linha vertical direita do tamanho da seleção
  (command "pline"
          (list linha_x_direita (- y2 7))  ; Ponto inicial (7cm abaixo do topo)
          (list linha_x_direita (- fundo_y 7))  ; Ponto final (fundo + 7cm)
          ""
  )

  ; Define o layer para "Painéis"
  (command "-layer" "m" "Painéis" "")

  ; Zoom para a linha vertical esquerda
  (setq linha_x_esquerda x2)
  (command "zoom" "c" (list linha_x_esquerda (/ (+ y2 fundo_y) 2)) 5)
  ; Desenha linha vertical 7cm à esquerda da anterior (agora no mesmo lugar que a anterior)
  (command "pline"
          (list linha_x_esquerda y2) ; Ponto inicial (topo da seleção)
          (list linha_x_esquerda fundo_y)  ; Ponto final (fundo)
          ""
  )
  
  ; Define o layer para "SARR_2.2x7"
  (command "-layer" "m" "SARR_2.2x7" "")

  ; Zoom para a nova linha vertical à esquerda
  (setq linha_x_esquerda_nova (- x1 7))
  (command "zoom" "c" (list linha_x_esquerda_nova (/ (+ y2 fundo_y) 2)) 5)

  ; Desenha linha vertical 7cm à esquerda da parede esquerda
  (command "pline"
          (list linha_x_esquerda_nova (- y2 7))  ; Ponto inicial (7cm abaixo do topo)
          (list linha_x_esquerda_nova (- fundo_y 7))  ; Ponto final (fundo + 7cm)
          ""
  )
  
  ; Zoom para a linha horizontal do fundo
  (command "zoom" "c" (list (/ (+ x1 x2) 2) fundo_y) 5)

  ; Desenha linha horizontal 7cm à esquerda do fundo da seleção
  (command "pline"
          (list (- x1 7) fundo_y)  ; Ponto inicial (7cm à esquerda do início da seleção)
          (list x1 fundo_y) ; Ponto final (início da seleção)
          ""
  )
  
  ; Calcula o ponto central da seleção
  (setq centro_x (/ (+ x1 x2) 2))
  (setq centro_y (/ (+ y1 y2) 2))

  ; Zoom para o centro da seleção antes de executar "hhhh"
  (command "zoom" "c" (list centro_x centro_y) 5)

  (princ)
)
