(defun c:app3 ()
  (setvar "CMDECHO" 0)
  
  ;Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione segundo ponto do retângulo: "))
  
  ;Organiza os pontos para garantir consistência independente da direção
  (setq x1 (min (car p1) (car p2)))
  (setq x2 (max (car p1) (car p2)))
  (setq y1 (min (cadr p1) (cadr p2)))
  (setq y2 (max (cadr p1) (cadr p2)))
  
  ;Calcula o centro da seleção para aplicar zoom
  (setq centro_x (/ (+ x1 x2) 2.0))
  (setq centro_y (/ (+ y1 y2) 2.0))
  (setq centro_selecao (list centro_x centro_y))
  
  ;Aplica zoom no centro da seleção com fator 50
  (command "zoom" "c" centro_selecao 50)
  
  ;Aumenta a área de seleção em 7 para a esquerda e 7 para baixo
  (setq x1 (- x1 0))  ;Aumenta 7 para a esquerda
  (setq y1 (- y1 0))  ;Aumenta 7 para baixo
  
  ;Redefine os pontos organizados
  (setq p1 (list x1 y2))  ;superior esquerdo
  (setq p2 (list x2 y1))  ;inferior direito
  (setq p3 (list x1 y1))  ;inferior esquerdo
  (setq p4 (list x2 y2))  ;superior direito
  
  ;Função auxiliar para criar retângulo
  (defun criar_retangulo (pt1 pt2)
    ;Determina a direção da seleção
    (setq x1 (car pt1))
    (setq y1 (cadr pt1))
    (setq x2 (car pt2))
    (setq y2 (cadr pt2))
    
    ;Calcula os offsets com valores ainda menores
    (setq offset_x (if (> x2 x1) 1.5 -1.5))  ; Reduzido para 1.5
    (setq offset_y (if (> y2 y1) 1.5 -1.5))  ; Reduzido para 1.5
    
    ;Desenha o retângulo
    (command "rectangle" pt1 pt2)
    (setq ret (entlast))
    
    ;Cria retângulo interno com offset mínimo
    (command "offset" 0.01 ret "")
    (setq ret_interno (entlast))
    
    ;Cria múltiplas linhas de corte com offsets menores e mais densos
    (command "offset" 0.1 ret "")   ; Reduzido para 0.1
    (setq ret_01 (entlast))
    (command "offset" 0.2 ret "")   ; Reduzido para 0.2
    (setq ret_02 (entlast))
    (command "offset" 0.3 ret "")   ; Reduzido para 0.3
    (setq ret_03 (entlast))
    (command "offset" 0.5 ret "")   ; Reduzido para 0.5
    (setq ret_05 (entlast))
    (command "offset" 1.0 ret "")   ; Reduzido para 1.0
    (setq ret_1 (entlast))
    (command "offset" 1.5 ret "")   ; Reduzido para 1.5
    (setq ret_15 (entlast))
    (command "offset" 2.0 ret "")   ; Reduzido para 2.0
    (setq ret_2 (entlast))
    (command "offset" 2.5 ret "")   ; Reduzido para 2.5
    (setq ret_25 (entlast))
    (command "offset" 3.0 ret "")   ; Reduzido para 3.0
    (setq ret_3 (entlast))
    
    ;Executa TRIM com área de seleção mais restrita e múltiplas operações
    (command "trim" ret "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
            
    ;TRIM nas linhas com área ainda mais restrita - múltiplas operações
    (command "trim" ret_01 "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
    (command "trim" ret_02 "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
    (command "trim" ret_03 "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
    (command "trim" ret_05 "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
    (command "trim" ret_1 "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
    (command "trim" ret_15 "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
    (command "trim" ret_2 "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
    (command "trim" ret_25 "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
    (command "trim" ret_3 "" 
            "f" (list (+ x1 0.05) (+ y1 0.05)) 
                (list (- x2 0.05) (- y2 0.05)) ""
            "")
    
    ;Apaga área interna com margem ainda menor
    (command "select" "w" 
            (list (+ x1 0.1) (+ y1 0.1))  ; Margem interna mais segura
            (list (- x2 0.1) (- y2 0.1))  ; Margem interna mais segura
            "")
    (command "erase" "p" "")
  )
  
  ;Cria os 4 retângulos
  (criar_retangulo p1 p2)  ;superior esquerdo para inferior direito
  (criar_retangulo p2 p1)  ;inferior direito para superior esquerdo
  (criar_retangulo p3 p4)  ;inferior esquerdo para superior direito
  (criar_retangulo p4 p3)  ;superior direito para inferior esquerdo
  
  ;Limpa variáveis
  (setq p1 nil p2 nil p3 nil p4 nil ret nil ret_interno nil ret_01 nil ret_02 nil ret_03 nil ret_05 nil ret_1 nil ret_15 nil ret_2 nil ret_25 nil ret_3 nil)
  (princ)
) 