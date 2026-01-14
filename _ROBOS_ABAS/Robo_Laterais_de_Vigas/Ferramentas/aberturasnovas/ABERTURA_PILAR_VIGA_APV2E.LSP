(defun c:apv2E ()
  (setvar "CMDECHO" 0)
  
  ; Bloqueia o layer "Painéis" no início
  (command "-layer" "lock" "Painéis" "")
  
  ;Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione segundo ponto do retângulo: "))
  (setq p3 (getpoint "\nSelecione ponto para definir altura do retângulo direito: "))
  
  ;Verifica se os pontos são válidos antes de criar o retângulo
  (if (and p1 p2 p3)
      (progn
          ;Organiza os pontos para garantir consistência independente da direção
          (setq x1 (min (car p1) (car p2)))
          (setq x2 (max (car p1) (car p2)))
          (setq y1 (min (cadr p1) (cadr p2)))
          (setq y2 (max (cadr p1) (cadr p2)))
          (setq y3 (cadr p3))  ; Coordenada Y do terceiro ponto
          
          ;Redefine os pontos organizados
          (setq p1 (list x1 y2))  ;superior esquerdo
          (setq p2 (list x2 y1))  ;inferior direito
          
          ;Função auxiliar para criar retângulo
          (defun criar_retangulo (pt1 pt2)
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
          
          ;Cria o retângulo principal (apenas uma vez)
          (criar_retangulo p1 p2)
      )
      (princ "\nPontos inválidos. O comando será cancelado.")
  )
  
  ;Calcula coordenada Y do topo
  (setq topo_y (cadr p1))  ; Usando Y do ponto superior
  
  ; Define o layer para "SARR_2.2x7"
  (command "-layer" "m" "SARR_2.2x7" "")
  
  ; Zoom focado antes de desenhar a linha horizontal
  (command "zoom" "w" (list x1 (- topo_y 10)) (list x2 (+ topo_y 10)))
  
  ; Desenha linha horizontal 7cm abaixo do topo
  (setq linha_y (- topo_y 7))
  (command "pline"
          (list x1 linha_y)
          (list x2 linha_y)
          ""
  )
  
  ; Zoom focado antes de desenhar a linha vertical direita
  (command "zoom" "w" (list (- x1 5) (- topo_y 5)) (list (+ x2 5) topo_y))
  
  ; Desenha linha vertical direita de 2.2cm
  (command "pline"
          (list x2 topo_y)  ; Ponto inicial (topo direito)
          (list x2 (- topo_y 2.2))  ; Ponto final (2.2cm para baixo)
          ""
  )
  
  ; Define o layer para "SARR_2.2x7" para a linha vertical esquerda
  (command "-layer" "m" "SARR_2.2x7" "")
  
  ; Verifica se a altura é maior que 30cm para determinar onde a linha vertical termina
  (setq altura (- topo_y y1))
  (setq y_fim_vertical (if (> altura 30) (+ y1 7) y1))
  
  ; Desenha linha vertical a 7cm da parede esquerda, começando 7cm abaixo do topo
  (command "pline"
          (list (+ x1 7) (- topo_y 7))  ; Ponto inicial (7cm abaixo do topo)
          (list (+ x1 7) y_fim_vertical) ; Ponto final (base ou 7cm acima)
          ""
  )
  
  ; Desbloqueia o layer "Painéis" 
  (command "-layer" "unlock" "Painéis" "")
  
  ; Zoom na área de seleção
  (command "zoom" "w"
          (list (- x1 1) (- y1 5))
          (list (+ x2 1) y1)
  )
  
  ; Seleciona e apaga área retangular 2cm abaixo da seleção (seleção verde - da direita para esquerda)
  (command "select" "C"                   ; Crossing selection (verde)
          (list (- x2 2) (- y1 2))        ; Ponto direito primeiro (2cm menor à direita)
          (list (+ x1 2) (- y1 4))        ; Ponto esquerdo depois (2cm maior à esquerda)
          ""
  )
  (command "erase" "p" "")
  
  ; Muda para o layer dos retângulos laterais
  (command "-layer" "m" "SARR_3.5x7" "")
  
  ; Zoom focado antes de desenhar o retângulo direito
  (command "zoom" "c" (list (+ x2 (/ (- x2 x1) 2)) (+ y1 (/ (- topo_y y1) 2))) (/ (- x2 x1) 2))
  
  ; Desenha retângulo direito usando y3 como limite inferior
  (command "pline"
          (list x2 (- topo_y 2.2))
          (list (+ x2 3.5) (- topo_y 2.2))
          (list (+ x2 3.5) y3)  ; Usa y3 em vez de y1
          (list x2 y3)          ; Usa y3 em vez de y1
          "C"
  )
  
  ; Verifica se a altura é maior que 30cm E largura maior que 243
  (setq largura (- x2 x1)) ; Calcula a largura
  (if (and (> altura 30) (> largura 243)) ; Adiciona condição de largura
      (progn
        ; Define o layer para "SARR_2.2x7"
        (command "-layer" "m" "SARR_2.2x7" "")
        
        ; Zoom focado antes de desenhar a linha horizontal inferior
        (command "zoom" "w" (list x1 (- y1 10)) (list x2 (+ y1 10)))
        
        ; Desenha linha horizontal 7cm acima do fundo
        (setq linha_y_inferior (+ y1 7))
        (command "pline"
                (list x1 linha_y_inferior)
                (list x2 linha_y_inferior)
                ""
        )
      )
  )
  
  ; Verifica se a altura está entre 43 e 79cm E largura maior que 243
  (if (and (>= altura 43) (<= altura 79) (> largura 243)) ; Adiciona condição de largura
      (progn
        ; Define o layer para "SARR_2.2x7"
        (command "-layer" "m" "SARR_2.2x7" "")
        
        ; Calcula o centro do retângulo
        (setq centro_y (+ y1 (/ altura 2)))
        
        ; Zoom focado antes de desenhar as linhas horizontais centrais
        (command "zoom" "w" (list x1 (- centro_y 10)) (list x2 (+ centro_y 10)))
        
        ; Desenha linha horizontal 3.5cm acima do centro, começando 7cm da esquerda
        (setq linha_y_superior (+ centro_y 3.5))
        (command "pline"
                (list (+ x1 7) linha_y_superior)  ; Começa 7cm da esquerda
                (list x2 linha_y_superior)
                ""
        )
        
        ; Desenha linha horizontal 3.5cm abaixo do centro, começando 7cm da esquerda
        (setq linha_y_inferior (- centro_y 3.5))
        (command "pline"
                (list (+ x1 7) linha_y_inferior)  ; Começa 7cm da esquerda
                (list x2 linha_y_inferior)
                ""
        )
      )
  )
  
  ; Verifica se a altura é maior que 79cm E largura maior que 243
  (if (and (> altura 79) (> largura 243)) ; Adiciona condição de largura
      (progn
        ; Define o layer para "SARR_2.2x7"
        (command "-layer" "m" "SARR_2.2x7" "")
        
        ; Calcula o espaço útil (altura total - 14cm dos sarrafos superior e inferior)
        (setq espaco_util (- altura 14))
        
        ; Calcula o tamanho de cada espaço entre os casais
        ; Espaço útil menos 14cm (7cm para cada casal) dividido por 3 espaços
        (setq espaco_entre_casais (/ (- espaco_util 14) 3))
        
        ; Calcula as posições Y dos casais
        ; Primeiro casal
        (setq y_casal1_superior (- topo_y (+ 7 espaco_entre_casais)))
        (setq y_casal1_inferior (- y_casal1_superior 7))
        
        ; Segundo casal
        (setq y_casal2_superior (- y_casal1_inferior espaco_entre_casais))
        (setq y_casal2_inferior (- y_casal2_superior 7))
        
        ; Zoom focado antes de desenhar as linhas
        (command "zoom" "w" (list x1 (- topo_y 10)) (list x2 (+ y1 10)))
        
        ; Desenha o primeiro casal de linhas, começando 7cm da esquerda
        (command "pline"
                (list (+ x1 7) y_casal1_superior)  ; Começa 7cm da esquerda
                (list x2 y_casal1_superior)
                ""
        )
        (command "pline"
                (list (+ x1 7) y_casal1_inferior)  ; Começa 7cm da esquerda
                (list x2 y_casal1_inferior)
                ""
        )
        
        ; Desenha o segundo casal de linhas, começando 7cm da esquerda
        (command "pline"
                (list (+ x1 7) y_casal2_superior)  ; Começa 7cm da esquerda
                (list x2 y_casal2_superior)
                ""
        )
        (command "pline"
                (list (+ x1 7) y_casal2_inferior)  ; Começa 7cm da esquerda
                (list x2 y_casal2_inferior)
                ""
        )
      )
  )
  
  (princ)
) 