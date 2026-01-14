(defun c:apv2 ()
  (setvar "CMDECHO" 0)
  
  ; Bloqueia o layer "Painéis" no início
  (command "-layer" "lock" "Painéis" "")
  
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
          
          ;Função auxiliar para criar retângulo
          (defun criar_retangulo (pt1 pt2)
            ;Determina a direção da seleção
            (setq x1 (car pt1))
            (setq y1 (cadr pt2))  ; Usando y do ponto 2 para referência
            (setq x2 (car pt2))
            (setq y2 (cadr pt1))  ; Usando y do ponto 1 para referência
            
            ;Desenha o retângulo
            (command "rectangle" pt1 pt2)
            (setq ret (entlast))
            
            ;Cria retângulo interno com offset mínimo
            (command "offset" 0.01 ret "")
            (setq ret_interno (entlast))
            
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
  
  ; Zoom para linha horizontal
  (command "zoom"
          "w"
          (list (- x1 1) (- linha_y 1))
          (list (+ x2 1) (+ linha_y 1))
  )
  
  ; Desenha linha horizontal 7cm abaixo do topo
  (setq linha_y (- topo_y 7))
  (command "pline"
          (list x1 linha_y)
          (list x2 linha_y)
          ""
  )
  
  ; Zoom para linha vertical esquerda
  (command "zoom"
          "w"
          (list (- x1 1) (- topo_y 3))
          (list (+ x1 1) topo_y)
  )
  
  ; Desenha linha vertical esquerda de 2.2cm
  (command "pline"
          (list x1 topo_y)  ; Ponto inicial (topo esquerdo)
          (list x1 (- topo_y 2.2))  ; Ponto final (2.2cm para baixo)
          ""
  )
  
  ; Zoom para linha vertical direita
  (command "zoom"
          "w"
          (list (- x2 1) (- topo_y 3))
          (list (+ x2 1) topo_y)
  )
  
  ; Desenha linha vertical direita de 2.2cm
  (command "pline"
          (list x2 topo_y)  ; Ponto inicial (topo direito)
          (list x2 (- topo_y 2.2))  ; Ponto final (2.2cm para baixo)
          ""
  )
  
  ; Muda para o layer dos retângulos laterais
  (command "-layer" "m" "SARR_3.5x7" "")
  
  ; Zoom para área do retângulo esquerdo
  (command "zoom"
          "w"
          (list (- x1 8.0) (- topo_y 1))
          (list (- x1 2.5) y1)
  )
  
  ; Desenha retângulo esquerdo
  (command "pline"
          (list x1 (- topo_y 2.2))
          (list (- x1 3.5) (- topo_y 2.2))
          (list (- x1 3.5) y1)
          (list x1 y1)
          "C"
  )
  
  ; Zoom para área do retângulo direito
  (command "zoom"
          "w"
          (list (+ x2 2.5) (- topo_y 1))
          (list (+ x2 8.0) y1)
  )
  
  ; Desenha retângulo direito
  (command "pline"
          (list x2 (- topo_y 2.2))
          (list (+ x2 3.5) (- topo_y 2.2))
          (list (+ x2 3.5) y1)
          (list x2 y1)
          "C"
  )
  
  ;Limpa variáveis
  (setq p1 nil p2 nil ret nil ret_interno nil ret_05 nil ret_5 nil)
  
  ; Desbloqueia o layer "Painéis" no final
  (command "-layer" "unlock" "Painéis" "")
  
  (princ)
) 