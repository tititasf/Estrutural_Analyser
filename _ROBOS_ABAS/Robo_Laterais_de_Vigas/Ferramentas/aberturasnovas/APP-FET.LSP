(defun c:appFET ()
  (setvar "CMDECHO" 0)
  
  ;Solicita pontos para desenhar retângulo
  (setq p1 (getpoint "\nSelecione primeiro ponto do retângulo: "))
  (setq p2 (getpoint p1 "\nSelecione segundo ponto do retângulo: "))
  
  ;Organiza os pontos para garantir consistência independente da direção
  (setq x1 (min (car p1) (car p2)))
  (setq x2 (max (car p1) (car p2)))
  (setq y1 (min (cadr p1) (cadr p2)))
  (setq y2 (max (cadr p1) (cadr p2)))
  
  ;Aumenta a área de seleção em 7 para a direita e 7 para baixo
  (setq x2 (+ x2 7))  ;Aumenta 7 para a direita
  (setq y1 (- y1 7))  ;Aumenta 7 para baixo
  
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
    
    ;Cria linhas de corte com offsets menores
    (command "offset" 0.3 ret "")  ; Reduzido para 0.3
    (setq ret_05 (entlast))
    (command "offset" 3 ret "")    ; Reduzido para 3
    (setq ret_5 (entlast))
    
    ;Executa TRIM com área de seleção mais restrita
    (command "trim" ret "" 
            "f" (list (+ x1 0.1) (+ y1 0.1)) 
                (list (- x2 0.1) (- y2 0.1)) ""
            "")
            
    ;TRIM nas linhas com área ainda mais restrita
    (command "trim" ret_05 "" 
            "f" (list (+ x1 0.1) (+ y1 0.1)) 
                (list (- x2 0.1) (- y2 0.1)) ""
            "")
    (command "trim" ret_5 "" 
            "f" (list (+ x1 0.1) (+ y1 0.1)) 
                (list (- x2 0.1) (- y2 0.1)) ""
            "")
    
    ;Apaga área interna com margem ainda menor
    (command "select" "w" 
            (list (+ x1 0.2) (+ y1 0.2))  ; Margem interna mais segura
            (list (- x2 0.2) (- y2 0.2))  ; Margem interna mais segura
            "")
    (command "erase" "p" "")
  )
  
  ;Cria os 4 retângulos
  (criar_retangulo p1 p2)  ;superior esquerdo para inferior direito
  (criar_retangulo p2 p1)  ;inferior direito para superior esquerdo
  (criar_retangulo p3 p4)  ;inferior esquerdo para superior direito
  (criar_retangulo p4 p3)  ;superior direito para inferior esquerdo
  
  ;Limpa variáveis
  (setq p1 nil p2 nil p3 nil p4 nil ret nil ret_interno nil ret_05 nil ret_5 nil)
  (princ)
) 