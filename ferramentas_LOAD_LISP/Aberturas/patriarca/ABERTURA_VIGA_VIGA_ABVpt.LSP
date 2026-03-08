;-------------------------------------------------------------------------------
; Função: Abertura entre vigas (Novo comando: abv)
; Arquivo: ABERTURA_VIGA_VIGA.LSP
;-------------------------------------------------------------------------------

(defun c:abvpt ()
  (setvar "CMDECHO" 0)
  (command "_MLINE" "ST" "SAR2" "S" "7" "") ; Adiciona a configuração MLINE STYLE e SCALE

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
          
          ;Função auxiliar para criar retângulo
          (defun criar_retangulo_viga_abvpt (pt1 pt2)
            ;Determina a direção da seleção
            (setq x1 (car pt1))
            (setq y1 (cadr pt2))  ; Usando y do ponto 2 para referência
            (setq x2 (car pt2))
            (setq y2 (cadr pt1))  ; Usando y do ponto 1 para referência
            
            ; Zoom focado antes de desenhar o retângulo principal
            (command "zoom" "c" (polar pt1 (angle pt1 pt2) (/ (distance pt1 pt2) 2)) 5)
          )
          
          ;Cria o retângulo principal
          (criar_retangulo_viga_abvpt p1 p2)
          
          ; Define o layer para "cota"
          (command "-layer" "m" "CONCRETO" "")
          
          ; Zoom para a linha na parede esquerda da seleção
          (command "zoom" "c" (list x1 (/ (+ y2 fundo_y) 2)) 5)
          
          ; Define o layer para "Painéis" antes de desenhar a linha
          (command "-layer" "m" "Painéis" "")
          
          ; Desenha linha na parede esquerda da seleção
          (command "pline" (list x1 y2) (list x1 fundo_y) "")
          
          ; Define o layer para "cota"
          (command "-layer" "m" "concreto" "")
          
          
          ; Zoom para a linha no topo da seleção
          (command "zoom" "c" (list (/ (+ x1 x2) 2) y2) 5)
          ; Desenha linha no topo da seleção
          (command "-linetype" "s" "HIDDEN" "")  ; Define estilo HIDDEN
          (command "pline" (list x1 y2) (list x2 y2) "")
          (command "-linetype" "s" "CONTINUOUS" "")  ; Restaura para CONTINUOUS
          
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  ; Calcula coordenada Y do fundo
  (setq fundo_y (cadr p2))  ; Usando Y do ponto inferior
  

  ; Define o layer para "Painéis"
  (command "-layer" "m" "SARRAFO_ACABAMENTO" "")

  ; Zoom para a linha horizontal inferior
  (command "zoom" "c" (list (/ (+ x1 x2) 2) (- fundo_y 12)) 5)
  ; Desenha linha horizontal 7cm abaixo do fundo
  (setq linha_y (- fundo_y 7))
  (command "mline"
          (list (- x1 7) (+ linha_y 7)) 
          (list (+ x2 7) (+ linha_y 7))
          ""
  )

  ; Define o layer para "Painéis"
  (command "-layer" "m" "Painéis" "")

  ; Zoom para a linha horizontal superior
  (command "zoom" "c" (list (/ (+ x1 x2) 2) linha_y_sup) 5)
  ; Desenha linha horizontal 7cm acima da atual
  (setq linha_y_sup (+ linha_y 7))
  (command "pline"
          (list x1 linha_y_sup)
          (list x2 linha_y_sup)
          ""
  )

  ; Define o layer para "SARRAFO_ACABAMENTO"
  (command "-layer" "m" "SARRAFO_ACABAMENTO" "")
  
  ; Zoom para a linha vertical direita
  (command "zoom" "c" (list linha_x_direita (/ (+ y2 fundo_y) 2)) 5)
  ; Desenha linha vertical direita do tamanho da seleção
  (setq linha_x_direita (+ x2 7))
  (command "mline"
          (list linha_x_direita (- y2 7))  ; Ponto inicial (7cm abaixo do topo)
          (list linha_x_direita fundo_y)  ; Ponto final (fundo)
          ""
  )

  ; Define o layer para "Painéis"
  (command "-layer" "m" "Painéis" "")

  ; Zoom para a linha vertical esquerda
  (command "zoom" "c" (list linha_x_esquerda (/ (+ y2 fundo_y) 2)) 5)
  ; Desenha linha vertical 7cm à esquerda da anterior (agora no mesmo lugar que a anterior)
  (setq linha_x_esquerda x2)
  (command "pline"
          (list linha_x_esquerda y2) ; Ponto inicial (topo da seleção)
          (list linha_x_esquerda fundo_y)  ; Ponto final (fundo)
          ""
  )
  
  ; Define o layer para "SARR_ACABAMENTO"
  (command "-layer" "m" "SARRAFO_ACABAMENTO" "")

  ; Zoom para a nova linha vertical à esquerda
  (command "zoom" "c" (list linha_x_esquerda_nova (/ (+ y2 fundo_y) 2)) 5)

  ; Desenha linha vertical 7cm à esquerda da parede esquerda
  (setq linha_x_esquerda_nova (- x1 7))
  (command "mline"
          (list (+ linha_x_esquerda_nova 7) (- y2 7))  ; Ponto inicial (7cm abaixo do topo)
          (list (+ linha_x_esquerda_nova 7) fundo_y)  ; Ponto final (fundo)
          ""
  )
  
  (princ))