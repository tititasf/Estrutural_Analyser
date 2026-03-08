(defun c:abvD ()
  (setvar "CMDECHO" 0)

  ;Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione segundo ponto do retângulo: "))
  
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

          ; Calcula coordenada Y do fundo ANTES de usar na função criar_retangulo
          (setq fundo_y (cadr p2))  ; Usando Y do ponto inferior
          
          ;Função auxiliar para criar retângulo (renomeada para criar_retangulo_abpd)
          (defun criar_retangulo_abpd_abvd (pt1 pt2)
            ;Determina a direção da seleção
            (setq x1 (car pt1))
            (setq y1 (cadr pt2))  ; Usando y do ponto 2 para referência
            (setq x2 (car pt2))
            (setq y2 (cadr pt1))  ; Usando y do ponto 1 para referência
            
            ; Zoom focado antes de desenhar o retângulo principal
            (command "zoom" "c" (polar pt1 (angle pt1 pt2) (/ (distance pt1 pt2) 2)) (distance pt1 pt2))
            
            ;Desenha o retângulo
            (command "rectangle" pt1 pt2)
            (setq ret (entlast))
            
            ; Zoom focado antes de desenhar o retângulo interno
            (command "zoom" "c" (polar pt1 (angle pt1 pt2) (/ (distance pt1 pt2) 2)) (* (distance pt1 pt2) 0.1))
            
            ;Cria retângulo interno com offset mínimo
            (command "offset" 0.01 ret "")
            (setq ret_interno (entlast))
            
            ; Zoom focado antes de desenhar as linhas de corte
            (command "zoom" "c" (polar pt1 (angle pt1 pt2) (/ (distance pt1 pt2) 2)) (* (distance pt1 pt2) 1.2))
            
            ;Cria linhas de corte
            (command "offset" 0.3 ret "")
            (setq ret_05 (entlast))
            (command "offset" 3 ret "")
            (setq ret_5 (entlast))
            
            ;Executa TRIM
            (command "trim" ret "" 
                    "f" (list (+ x1 0.1) (+ y1 0.1)) 
                        (list (- x2 0.1) (- y2 0.1)) ""
                    "")
                    
            (command "trim" ret_05 "" 
                    "f" (list (+ x1 0.1) (+ y1 0.1)) 
                        (list (- x2 0.1) (- y2 0.1)) ""
                    "")
            (command "trim" ret_5 "" 
                    "f" (list (+ x1 0.1) (+ y1 0.1)) 
                        (list (- x2 0.1) (- y2 0.1)) ""
                    "")
            
            ;Apaga área interna
            (command "select" "w" 
                    (list (+ x1 0.2) (+ y1 0.2))
                    (list (- x2 0.2) (- y2 0.2))
                    "")
            (command "erase" "p" "")
          )
          
          ;Cria o retângulo principal (chamando a função renomeada)
          (criar_retangulo_abpd_abvd p1 p2)
          
          ; Define o layer para "cota"
          (command "-layer" "m" "cota" "")
          
          ; Espelha a linha na parede esquerda para a direita
          ; Ajusta o zoom para a nova linha à direita
          (command "zoom" "w" (list (+ x2 5) (+ y2 5)) (list (- x2 15) (- fundo_y 5)))
          (command "line" (list x2 y2) (list x2 fundo_y) "")
        
          ; Zoom para a linha no topo da seleção
          (command "zoom" "w" (list (- x1 5) (+ y2 5)) (list (+ x2 5) (- y2 5)))
          ; Desenha linha no topo da seleção
          (command "line" (list x1 y2) (list x2 y2) "")
          
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  ; Calcula coordenada Y do fundo
  (setq fundo_y (cadr p2))  ; Usando Y do ponto inferior
  

  ; Define o layer para "Painéis"
  (command "-layer" "m" "sarr_2.2x7" "")

  ; Zoom para a linha horizontal inferior
  ; Ajusta o zoom para incluir a nova linha à esquerda
  (command "zoom" "w" (list (- x1 12) (- fundo_y 12)) (list (+ x2 5) fundo_y))
  ; Desenha linha horizontal 7cm abaixo do fundo
  (setq linha_y (- fundo_y 7))
  (command "pline"
          (list (- x1 7) linha_y) ; Ajuste para espelhar à esquerda
          (list x2 linha_y)
          ""
  )

  ; Define o layer para "Painéis"
  (command "-layer" "m" "Painéis" "")

  ; Zoom para a linha horizontal superior
  ; Ajusta o zoom para incluir a nova linha à esquerda
  (command "zoom" "w" (list (- x1 12) (+ linha_y 12)) (list (+ x2 5) (- linha_y 2)))
  ; Desenha linha horizontal 7cm acima da atual
  (setq linha_y_sup (+ linha_y 7))
  (command "pline"
          (list (- x1 7) linha_y_sup) ; Ajuste para espelhar à esquerda
          (list x2 linha_y_sup)
          ""
  )

  ; Define o layer para "SARR_2.2x7"
  (command "-layer" "m" "SARR_2.2x7" "")
  
  ; Zoom para a nova linha horizontal
  ; Ajusta o zoom para a extremidade esquerda da nova linha
  (command "zoom" "w" (list (- x1 12) (+ linha_y_sup 5)) (list (+ x1 5) (- linha_y_sup 5)))
  ; Desenha a nova linha como continuação da linha horizontal "Painéis"
  (command "pline"
          (list (- x1 7) linha_y_sup) ; Ponto inicial espelhado
          (list x1 linha_y_sup) ; Ponto final na borda esquerda
          ""
  )
  
  ; Zoom para a linha vertical esquerda (espelhada)
  ; Ajusta o zoom para a nova linha à esquerda
  (command "zoom" "w" (list (- x1 19) (+ y2 5)) (list (+ x1 5) (- fundo_y 12)))
  ; Desenha linha vertical esquerda do tamanho da seleção
  (setq linha_x_esquerda (- x1 7)) ; Ajuste para espelhar à esquerda
  (command "pline"
          (list linha_x_esquerda (- y2 7))  ; Ponto inicial (7cm abaixo do topo)
          (list linha_x_esquerda fundo_y)  ; Ponto final (fundo)
          ""
  )

  ; Adiciona uma nova linha para preencher os 7 cm abaixo
  (command "pline"
          (list linha_x_esquerda fundo_y)  ; Ponto inicial (fundo)
          (list linha_x_esquerda (- fundo_y 7))  ; Ponto final (7cm abaixo do fundo)
          ""
  )


  ; Define o layer para "Painéis"
  (command "-layer" "m" "Painéis" "")

  ; Zoom para a linha vertical direita (espelhada)
  ; Mantém o zoom na linha que agora está à direita
  (command "zoom" "w" (list (- x1 5) (+ y2 5)) (list (+ x1 5) (- fundo_y 5)))
  ; Desenha linha vertical 7cm à direita da anterior (agora no mesmo lugar que a anterior)
  (setq linha_x_direita x1) ; Ajuste para espelhar à esquerda
  (command "pline"
          (list linha_x_direita y2) ; Ponto inicial (topo da seleção)
          (list linha_x_direita fundo_y)  ; Ponto final (fundo)
          ""
  )
  
  ; Calcula o ponto central da seleção
  (setq centro_x (/ (+ x1 x2) 2))
  (setq centro_y (/ (+ y1 y2) 2))

  ; Zoom para o centro da seleção antes de executar "hhhh"
  ; Ajusta o fator de zoom para melhor visualização do hatch
  (command "zoom" "c" (list centro_x centro_y) (* (distance p1 p2) 2))
)