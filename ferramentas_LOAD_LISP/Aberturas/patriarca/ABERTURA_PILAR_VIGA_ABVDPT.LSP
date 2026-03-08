(defun c:abvDPT ()
  (setvar "CMDECHO" 0)
  (command "_MLINE" "ST" "SAR2" "S" "7" "") ; Adiciona a configuração MLINE STYLE e SCALE
  
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
          (defun criar_retangulo_abpd_abvdpt (pt1 pt2)
            ;Determina a direção da seleção
            (setq x1 (car pt1))
            (setq y1 (cadr pt2))  ; Usando y do ponto 2 para referência
            (setq x2 (car pt2))
            (setq y2 (cadr pt1))  ; Usando y do ponto 1 para referência
            
            ; Zoom focado antes de desenhar o retângulo principal
            (command "zoom" "c" (polar pt1 (angle pt1 pt2) (/ (distance pt1 pt2) 2)) (distance pt1 pt2))
          )
          
          ;Cria o retângulo principal (chamando a função renomeada)
          (criar_retangulo_abpd_abvdpt p1 p2)
          
          ; Define o layer para "cota"
          (command "-layer" "m" "CONCRETO" "")
          
          ; Espelha a linha na parede esquerda para a direita
          ; Ajusta o zoom para a nova linha à direita
          (command "zoom" "c" (list x2 fundo_y) 5)
          (command "-linetype" "s" "HIDDEN" "")  ; Define estilo HIDDEN
          (command "line" (list x2 y2) (list x2 (+ fundo_y 7)) "")
          (command "-linetype" "s" "CONTINUOUS" "")  ; Restaura para CONTINUOUS
        
          ; Zoom para a linha no topo da seleção
          (command "zoom" "c" (list (/ (+ x1 x2) 2) y2) 5)
          ; Desenha linha no topo da seleção
          (command "-linetype" "s" "HIDDEN" "")  ; Define estilo HIDDEN
          (command "line" (list x1 y2) (list x2 y2) "")
          (command "-linetype" "s" "CONTINUOUS" "")  ; Restaura para CONTINUOUS
          
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  ; Calcula coordenada Y do fundo
  (setq fundo_y (cadr p2))  ; Usando Y do ponto inferior
  

  ; Define o layer para "Painéis"
  (command "-layer" "m" "SARRAFO_ACABAMENTO" "")

  ; Zoom para a linha horizontal inferior
  ; Ajusta o zoom para incluir a nova linha à esquerda
  (command "zoom" "c" (list (/ (+ x1 x2) 2) (- fundo_y 12)) 5)
  ; Desenha linha horizontal 7cm abaixo do fundo
  (setq linha_y (+ fundo_y 7))
  (command "mline"
          (list (- x1 0) linha_y) ; Ajuste para espelhar à esquerda
          (list x2 linha_y)
          ""
  )

  ; Define o layer para "Painéis"
  (command "-layer" "m" "Painéis" "")

  ; Zoom para a linha horizontal superior
  ; Ajusta o zoom para incluir a nova linha à esquerda
  (command "zoom" "c" (list (/ (+ x1 x2) 2) linha_y_sup) 5)
  ; Desenha linha horizontal 7cm acima da atual
  (setq linha_y_sup (+ linha_y 0))
  (command "pline"
          (list (- x1 0) linha_y_sup) ; Ajuste para espelhar à esquerda
          (list x2 linha_y_sup)
          ""
  )

  ; Define o layer para "SARR_ACABAMENTO"
  (command "-layer" "m" "SARRAFO_ACABAMENTO" "")

  ; Zoom para a linha vertical esquerda (espelhada)
  ; Ajusta o zoom para a nova linha à esquerda
  (command "zoom" "c" (list (- x1 19) (+ y2 5)) 5)
  ; Desenha linha vertical esquerda do tamanho da seleção
  (setq linha_x_esquerda (+ x1 0)) ; Ajuste para espelhar à esquerda
  (command "mline"
          (list linha_x_esquerda (- y2 7))  ; Ponto inicial (7cm abaixo do topo)
          (list linha_x_esquerda fundo_y)  ; Ponto final (fundo)
          ""
  )

  ; Define o layer para "Painéis"
  (command "-layer" "m" "Painéis" "")

  ; Zoom para a linha vertical direita (espelhada)
  ; Mantém o zoom na linha que agora está à direita
  (command "zoom" "c" (list (- x1 5) (+ y2 5)) 5)
  ; Desenha linha vertical 7cm à direita da anterior (agora no mesmo lugar que a anterior)
  (setq linha_x_direita x1) ; Ajuste para espelhar à esquerda
  (command "pline"
          (list linha_x_direita y2) ; Ponto inicial (topo da seleção)
          (list linha_x_direita (+ fundo_y 7))  ; Ponto final (fundo - 7)
          ""
  )
  
  ; Calcula o ponto central da seleção
  (setq centro_x (/ (+ x1 x2) 2))
  (setq centro_y (/ (+ y1 y2) 2))

  ; Zoom para o centro da seleção antes de executar "hhhh"
  ; Ajusta o fator de zoom para melhor visualização do hatch
  (command "zoom" "c" (list centro_x centro_y) 5)
)